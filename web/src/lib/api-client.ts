import axios, { AxiosError, AxiosRequestConfig, InternalAxiosRequestConfig } from "axios";

/**
 * Same-origin by design.
 *
 * The session is an httpOnly, SameSite=strict cookie set by the backend, so
 * the browser only attaches it to same-site requests. Next proxies /api/v1/*
 * to the API (see next.config.ts), which is what lets the cookie travel at
 * all. This client therefore has no token handling of its own: it holds no
 * token, reads no token, and cannot leak one.
 */
const BASE_URL = "/api/v1";

/**
 * Error carrying the HTTP status the backend actually returned.
 *
 * The interceptor used to reject with a bare `new Error(message)`, discarding
 * the status. Callers could therefore never distinguish "connect an account"
 * (409) from "Google refused" (502) from "your session ended" (401) — every
 * failure looked identical, so every error UI had to show the same unhelpful
 * message.
 */
export class ApiError extends Error {
    readonly status?: number;
    readonly detail?: string;

    constructor(message: string, status?: number, detail?: string) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.detail = detail;
    }
}

/** True when the backend reported this exact status. */
export function isApiErrorStatus(error: unknown, status: number): boolean {
    return error instanceof ApiError && error.status === status;
}

export interface ApiResponse<T = unknown> {
    success: boolean;
    data: T;
    message: string;
    timestamp: string;
    execution_time: number;
}

interface RetriableConfig extends InternalAxiosRequestConfig {
    _retried?: boolean;
}

export const apiClient = axios.create({
    baseURL: BASE_URL,
    headers: {
        "Content-Type": "application/json",
    },
    // Send the session cookie. Same-origin, so this is the only credential.
    withCredentials: true,
});

/**
 * Outcome of an attempt to renew the session.
 *
 * The three cases need different handling and were previously collapsed into
 * one boolean, which is what produced the loop: "rate limited" was treated the
 * same as "session over", so the client signed the user out and then, because
 * the session was not actually over, immediately tried again.
 */
type RenewalOutcome = "renewed" | "rate-limited" | "ended";

/** In-flight renewal, so concurrent callers share one request. */
let refreshInFlight: Promise<RenewalOutcome> | null = null;

/**
 * Terminal state: the refresh credential was rejected. Nothing can renew it,
 * so stop asking. Cleared only by a fresh sign-in.
 */
let sessionEnded = false;

/**
 * Epoch ms before which we must not call the refresh endpoint again.
 *
 * Set from the server's own Retry-After header on a 429. This is backpressure
 * the server asked for, not an invented delay: continuing to call a limiter
 * that is already refusing us is what turned an expired session into an
 * unbounded refresh loop.
 */
let refreshBlockedUntil = 0;

/** Module-level because the session is a single per-tab fact, not per-caller. */
function renewSession(): Promise<RenewalOutcome> {
    if (sessionEnded) return Promise.resolve("ended");

    if (Date.now() < refreshBlockedUntil) {
        // Still inside the window the server told us to wait out.
        return Promise.resolve("rate-limited");
    }

    if (refreshInFlight) return refreshInFlight;

    refreshInFlight = (async (): Promise<RenewalOutcome> => {
        try {
            const response = await fetch(`${BASE_URL}/auth/refresh`, {
                method: "POST",
                credentials: "same-origin",
                cache: "no-store",
            });

            if (response.ok) {
                refreshBlockedUntil = 0;
                return "renewed";
            }

            if (response.status === 429) {
                // Says nothing about the credential — only that we asked too
                // often. Honour the server's own backoff and keep the session.
                const retryAfter = Number(
                    response.headers?.get?.("Retry-After") ?? ""
                );
                const waitSeconds =
                    Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : 60;

                refreshBlockedUntil = Date.now() + waitSeconds * 1000;
                return "rate-limited";
            }

            // Anything else is the credential being rejected.
            sessionEnded = true;
            return "ended";
        } catch {
            // A transport failure says nothing about the session's validity,
            // and must not sign the user out. Back off briefly so a flapping
            // network cannot become a request loop either.
            refreshBlockedUntil = Date.now() + 5000;
            return "rate-limited";
        } finally {
            refreshInFlight = null;
        }
    })();

    return refreshInFlight;
}

/** Called after a successful sign-in so renewal is armed again. */
export function resetSessionState(): void {
    sessionEnded = false;
    refreshBlockedUntil = 0;
    refreshInFlight = null;
}

/**
 * On 401, renew once and replay the original request.
 *
 * Bounded lifecycle: `_retried` marks a request as having had its one replay,
 * so a replay that 401s again falls through to the error path rather than
 * renewing forever. renewSession is single-flight, so concurrent 401s share
 * one refresh. The refresh call itself uses fetch, not this client, so it can
 * never be intercepted and can never recurse.
 *
 * Only a terminal outcome signs the user out. Being rate limited is not
 * terminal — treating it as such is what made the client bounce to /login,
 * get sent back by the route guard, and start over.
 */
apiClient.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
        const original = error.config as RetriableConfig | undefined;

        if (
            error.response?.status === 401 &&
            original &&
            !original._retried &&
            typeof window !== "undefined"
        ) {
            original._retried = true;

            const outcome = await renewSession();

            if (outcome === "renewed") {
                return apiClient.request(original as AxiosRequestConfig);
            }

            // "rate-limited" means we could not ask, not that the session is
            // over: surface the 401 and let the next request try once the
            // server's window has passed. Navigating here would restart the
            // whole cycle.
            if (
                outcome === "ended" &&
                !window.location.pathname.startsWith("/login")
            ) {
                window.location.href = "/login?error=session_expired";
            }
        }

        const data = error.response?.data as
            | { detail?: string; message?: string }
            | undefined;

        const errorMsg =
            data?.detail || data?.message || error.message || "API request failed";

        console.error("[API Error]:", error.response?.status ?? "network", errorMsg);

        return Promise.reject(
            new ApiError(errorMsg, error.response?.status, data?.detail)
        );
    }
);
