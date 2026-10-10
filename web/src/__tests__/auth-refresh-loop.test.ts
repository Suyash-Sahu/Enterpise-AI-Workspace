/**
 * Regression suite for the infinite authentication loop.
 *
 * Drives the real apiClient and its real interceptor against a stubbed
 * transport, counting exactly how many times each endpoint is called.
 *
 * The loop: an expired session made every query 401, each 401 asked to renew,
 * the renewals tripped the refresh rate limit, and a 429 was then treated as
 * "session over" — so the client signed the user out, the route guard saw the
 * still-present cookie and sent them back into the app, and the cycle
 * restarted. Two of these assertions failed before the fix; the storm case
 * counted ten refreshes for ten requests.
 */

import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient, resetSessionState } from "@/lib/api-client";

const originalAdapter = apiClient.defaults.adapter;
const realFetch = globalThis.fetch;

/** Counts every call the client makes, by target. */
interface Counters {
    api: number;
    refresh: number;
}

let counters: Counters;
let refreshStatus: number;
let apiStatus: number;
/** After a *successful* refresh, the API starts answering with this instead. */
let apiStatusAfterRefresh: number | null;
/** Tracks real renewals; a 429 is not one. */
let refreshSucceeded: boolean;

function installTransport() {
    apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
        counters.api += 1;

        const status =
            apiStatusAfterRefresh !== null && refreshSucceeded
                ? apiStatusAfterRefresh
                : apiStatus;

        if (status === 200) {
            return {
                data: { ok: true },
                status: 200,
                statusText: "OK",
                headers: new AxiosHeaders(),
                config,
            };
        }

        throw new AxiosError(
            `Request failed with status code ${status}`,
            String(status),
            config,
            {},
            {
                data: { detail: "nope" },
                status,
                statusText: "",
                headers: new AxiosHeaders(),
                config,
            }
        );
    };

    globalThis.fetch = (async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url.includes("/auth/refresh")) {
            counters.refresh += 1;
            const ok = refreshStatus === 200;
            if (ok) refreshSucceeded = true;
            return {
                ok,
                status: refreshStatus,
                headers: { get: (h: string) => (h === "Retry-After" ? "60" : null) },
            } as unknown as Response;
        }

        throw new Error(`unexpected fetch to ${url}`);
    }) as typeof fetch;
}

beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    counters = { api: 0, refresh: 0 };
    refreshStatus = 200;
    apiStatus = 401;
    apiStatusAfterRefresh = null;
    refreshSucceeded = false;
    resetSessionState();
    installTransport();

    // The interceptor navigates on terminal failure; keep that observable
    // without letting jsdom/node complain.
    Object.defineProperty(globalThis, "window", {
        configurable: true,
        writable: true,
        value: {
            location: { pathname: "/dashboard", href: "/dashboard" },
        },
    });
});

afterEach(() => {
    vi.useRealTimers();
    apiClient.defaults.adapter = originalAdapter;
    globalThis.fetch = realFetch;
    resetSessionState();
    // @ts-expect-error - test-only global
    delete globalThis.window;
});

const call = () => apiClient.get("/workspace/dashboard").catch((e) => e);

describe("refresh loop", () => {
    it("B: one expired access token causes exactly ONE refresh, even with many concurrent failures", async () => {
        apiStatusAfterRefresh = 200;

        await Promise.all([call(), call(), call(), call(), call(), call()]);

        expect(counters.refresh).toBe(1);
    });

    it("B: a successful refresh replays each original request exactly once", async () => {
        apiStatusAfterRefresh = 200;

        await call();

        // One initial attempt + one replay. Never more.
        expect(counters.api).toBe(2);
        expect(counters.refresh).toBe(1);
    });

    it("C: a definitively failed refresh is not retried by later requests", async () => {
        refreshStatus = 401;

        await call();
        await call();
        await call();

        expect(counters.refresh).toBe(1);
    });

    it("D: a 401 that survives refresh does not loop", async () => {
        // Refresh "succeeds" but the API keeps refusing — the shape that
        // produces 401 -> refresh -> 401 -> refresh forever.
        refreshStatus = 200;
        apiStatusAfterRefresh = 401;

        await call();

        expect(counters.refresh).toBeLessThanOrEqual(1);
        expect(counters.api).toBeLessThanOrEqual(2);
    });

    it("E: a 429 on refresh does not invalidate the session", async () => {
        refreshStatus = 429;

        await call();
        expect(counters.refresh).toBe(1);

        // Inside the server's Retry-After window: no further calls at all.
        await call();
        expect(counters.refresh).toBe(1);

        // Once the window passes the session must still be renewable — a 429
        // must never have permanently locked the user out.
        vi.setSystemTime(new Date(Date.now() + 61_000));
        refreshStatus = 200;
        apiStatusAfterRefresh = 200;

        await call();
        expect(counters.refresh).toBe(2);
    });

    it("E: a 429 storm does not produce unbounded refreshes", async () => {
        refreshStatus = 429;

        for (let i = 0; i < 10; i += 1) {
            await call();
        }

        // Ten failing page requests must not mean ten refresh attempts.
        expect(counters.refresh).toBeLessThanOrEqual(2);
    });

    it("F: a non-401 refusal never triggers a refresh", async () => {
        apiStatus = 409;

        await call();

        expect(counters.refresh).toBe(0);
        expect(counters.api).toBe(1);
    });

    it("A: a valid session performs no refresh at all", async () => {
        apiStatus = 200;

        await call();

        expect(counters.refresh).toBe(0);
        expect(counters.api).toBe(1);
    });
});


describe("refresh recursion", () => {
    it("never routes the refresh call through the intercepted client", async () => {
        // If renewSession used apiClient, a 401 from /auth/refresh would be
        // intercepted, trigger another renewal, and recurse without bound.
        // It uses fetch, so the client must never see that path.
        const seen: string[] = [];

        apiClient.defaults.adapter = async (config) => {
            seen.push(String(config.url));
            throw new AxiosError(
                "401",
                "401",
                config,
                {},
                {
                    data: { detail: "no" },
                    status: 401,
                    statusText: "",
                    headers: new AxiosHeaders(),
                    config,
                }
            );
        };

        await apiClient.get("/workspace/dashboard").catch(() => undefined);

        expect(seen.some((url) => url.includes("/auth/refresh"))).toBe(false);
        expect(counters.refresh).toBe(1);
    });

    it("bounds a single request to one replay", async () => {
        // The replay 401s too. It must not earn a second renewal.
        refreshStatus = 200;
        apiStatus = 401;
        apiStatusAfterRefresh = 401;

        await call();

        expect(counters.api).toBe(2);
        expect(counters.refresh).toBe(1);
    });
});
