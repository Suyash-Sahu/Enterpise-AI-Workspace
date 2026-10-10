/**
 * The two Google flows are different things and must stay different.
 *
 *   /api/v1/auth/google/login       — sign in. Proves who you are. Issues the
 *                                     workspace session cookies. Grants no
 *                                     access to Gmail or Drive.
 *   /api/v1/connectors/google/login — connect. Requests Gmail/Drive scopes for
 *                                     the already-signed-in user and creates
 *                                     the oauth_tokens row on consent.
 *
 * Signing in with Google therefore leaves the connector disconnected, and the
 * connector's 409 is the correct answer until the second flow is completed.
 * These pin both halves: that "Connect Account" starts the connector flow, and
 * that a connector 409 is never mistaken for a session problem.
 */

import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiClient, resetSessionState } from "@/lib/api-client";
import { SIGN_IN_URL } from "@/services/auth.service";
import { googleService } from "@/services/google.service";

const CONNECT_URL = "/connectors/google/login";
const AUTHORIZATION_URL =
    "https://accounts.google.com/o/oauth2/v2/auth?client_id=test&scope=" +
    encodeURIComponent(
        "email https://www.googleapis.com/auth/drive.readonly " +
            "https://www.googleapis.com/auth/gmail.readonly"
    );

const originalAdapter = apiClient.defaults.adapter;

/** Every request the client made, in order. */
let requested: string[] = [];
/** Every fetch the client made — the refresh path uses fetch, not axios. */
let fetched: string[] = [];

function ok(data: unknown) {
    apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
        requested.push(config.url ?? "");
        return {
            data: { success: true, data, message: "", timestamp: "", execution_time: 0 },
            status: 200,
            statusText: "OK",
            headers: new AxiosHeaders(),
            config,
        };
    };
}

function failWith(status: number, detail: string) {
    apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
        requested.push(config.url ?? "");
        throw new AxiosError(
            `Request failed with status code ${status}`,
            String(status),
            config,
            {},
            {
                data: { detail },
                status,
                statusText: "",
                headers: new AxiosHeaders(),
                config,
            }
        );
    };
}

beforeEach(() => {
    requested = [];
    fetched = [];
    resetSessionState();

    // The interceptor renews through fetch. Record any call so a refresh
    // triggered by a connector 409 would be visible here.
    vi.stubGlobal(
        "fetch",
        vi.fn(async (input: RequestInfo | URL) => {
            fetched.push(String(input));
            return new Response("{}", { status: 200 });
        })
    );

    // jsdom is not configured for this suite, so window is stubbed to just the
    // surface the client and service touch.
    vi.stubGlobal("window", {
        location: { pathname: "/integrations", href: "http://localhost:3000/integrations" },
    });
});

afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
    vi.unstubAllGlobals();
    resetSessionState();
});

describe("Connect Account starts the connector OAuth flow", () => {
    it("asks the connector endpoint, not the sign-in endpoint", async () => {
        ok({ authorization_url: AUTHORIZATION_URL });

        await googleService.startGoogleConnect();

        expect(requested).toEqual([CONNECT_URL]);
        expect(requested).not.toContain(SIGN_IN_URL);
    });

    it("sends the browser to the authorization URL Google was given", async () => {
        ok({ authorization_url: AUTHORIZATION_URL });

        await googleService.startGoogleConnect();

        // Without this the button called the API and then did nothing, so
        // consent was never reached.
        expect(window.location.href).toBe(AUTHORIZATION_URL);
    });

    it("requests Gmail and Drive scopes — sign-in requests neither", async () => {
        ok({ authorization_url: AUTHORIZATION_URL });

        await googleService.startGoogleConnect();

        const url = decodeURIComponent(window.location.href);
        expect(url).toContain("auth/gmail.readonly");
        expect(url).toContain("auth/drive.readonly");
    });

    it("reports the backend's reason when the flow cannot start", async () => {
        failWith(403, "Not permitted to connect an account.");

        await expect(googleService.startGoogleConnect()).rejects.toThrow(
            "Not permitted to connect an account."
        );

        // And it must not have navigated anywhere.
        expect(window.location.href).toBe("http://localhost:3000/integrations");
    });
});

describe("sign-in and connector OAuth stay separate", () => {
    it("uses two different endpoints", () => {
        expect(SIGN_IN_URL).toBe("/api/v1/auth/google/login");
        expect(SIGN_IN_URL).not.toContain("/connectors/");
        expect(CONNECT_URL).not.toContain("/auth/");
    });
});

describe("a connector 409 is not a session problem", () => {
    it("does not try to renew the session", async () => {
        failWith(409, "No Google account is connected. Connect one to continue.");

        await expect(googleService.fetchGmailProfile()).rejects.toBeInstanceOf(ApiError);

        // The loop this guards against: treating "connect an account" as
        // "your token is stale", refreshing, retrying, and refreshing again.
        expect(fetched).toEqual([]);
    });

    it("makes exactly one request, with no replay", async () => {
        failWith(409, "No Google account is connected. Connect one to continue.");

        await expect(googleService.fetchGmailProfile()).rejects.toThrow();

        expect(requested).toEqual(["/connectors/google/gmail/profile"]);
    });

    it("keeps the 409 so the UI can offer Connect Account", async () => {
        failWith(409, "No Google account is connected. Connect one to continue.");

        const error = (await googleService
            .fetchGmailProfile()
            .then(() => null)
            .catch((e: unknown) => e)) as ApiError;

        expect(error.status).toBe(409);
    });

    it("survives repeated 409s without ever refreshing", async () => {
        failWith(409, "No Google account is connected. Connect one to continue.");

        for (let i = 0; i < 10; i += 1) {
            await googleService.fetchGmailProfile().catch(() => undefined);
        }

        expect(requested).toHaveLength(10);
        expect(fetched).toEqual([]);
    });
});

describe("a connected account reads normally", () => {
    it("returns the real mailbox address", async () => {
        ok({
            emailAddress: "suyash1811980@gmail.com",
            messagesTotal: 4821,
            threadsTotal: 3190,
        });

        const profile = await googleService.fetchGmailProfile();

        expect(profile.emailAddress).toBe("suyash1811980@gmail.com");
        expect(profile.messagesTotal).toBe(4821);
    });

    it("reports the connected account from the status endpoint", async () => {
        ok({ connected: true, email: "suyash1811980@gmail.com" });

        await expect(googleService.getGoogleStatus()).resolves.toEqual({
            connected: true,
            email: "suyash1811980@gmail.com",
        });
    });

    it("reports a disconnected account as disconnected, not as an error", async () => {
        ok({ connected: false });

        await expect(googleService.getGoogleStatus()).resolves.toEqual({
            connected: false,
        });
    });
});

describe("connection status is never invented", () => {
    it("surfaces a failed status check instead of claiming disconnected", async () => {
        // The defect: every failure was swallowed into { connected: false },
        // so an unreachable backend rendered a confident "Disconnected" badge.
        failWith(502, "Google request failed.");

        await expect(googleService.getGoogleStatus()).rejects.toBeInstanceOf(ApiError);
    });

    it("does not accept a response that omits the connected flag", async () => {
        ok({ email: "someone@example.com" });

        await expect(googleService.getGoogleStatus()).rejects.toThrow(
            /not understood/i
        );
    });
});
