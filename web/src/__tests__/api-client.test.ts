import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from "axios";
import { afterEach, describe, expect, it } from "vitest";

import { ApiError, apiClient, isApiErrorStatus } from "@/lib/api-client";

/**
 * The response interceptor used to reject with `new Error(message)`, throwing
 * away the HTTP status the backend had just gone to the trouble of choosing.
 *
 * That made every failure indistinguishable at the call site: "no Google
 * account connected" (409), "Google refused the call" (502) and "your session
 * ended" (401) all arrived as the same anonymous Error, so no error UI could
 * offer the right next step.
 */

const originalAdapter = apiClient.defaults.adapter;

/** Make the next request fail the way a real backend response would. */
function respondWith(status: number, data: unknown) {
    apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
        throw new AxiosError(
            "Request failed with status code " + status,
            String(status),
            config,
            {},
            {
                data,
                status,
                statusText: "",
                headers: new AxiosHeaders(),
                config,
            }
        );
    };
}

/** Make the next request fail before any response exists. */
function failWithoutResponse() {
    apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
        throw new AxiosError("Network Error", "ERR_NETWORK", config);
    };
}

afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
});

describe("apiClient error mapping", () => {
    it("keeps the status so 'not connected' can be told apart from a failure", async () => {
        respondWith(409, { detail: "No Google account is connected." });

        const error = await apiClient
            .get("/connectors/google/gmail/messages")
            .then(() => null)
            .catch((e: unknown) => e);

        expect(error).toBeInstanceOf(ApiError);
        expect((error as ApiError).status).toBe(409);
        expect(isApiErrorStatus(error, 409)).toBe(true);
        expect(isApiErrorStatus(error, 502)).toBe(false);
    });

    it("distinguishes an upstream failure from a missing connection", async () => {
        respondWith(502, { detail: "Google request failed." });

        const error = await apiClient
            .get("/connectors/google/drive/files")
            .then(() => null)
            .catch((e: unknown) => e);

        expect(isApiErrorStatus(error, 502)).toBe(true);
        expect(isApiErrorStatus(error, 409)).toBe(false);
    });

    it("surfaces the backend's detail message to the caller", async () => {
        respondWith(409, { detail: "No Google account is connected." });

        const error = (await apiClient
            .get("/connectors/google/gmail/profile")
            .then(() => null)
            .catch((e: unknown) => e)) as ApiError;

        expect(error.message).toBe("No Google account is connected.");
        expect(error.detail).toBe("No Google account is connected.");
    });

    it("still reports a network failure, with no status to report", async () => {
        failWithoutResponse();

        const error = (await apiClient
            .get("/workspace/dashboard")
            .then(() => null)
            .catch((e: unknown) => e)) as ApiError;

        expect(error).toBeInstanceOf(ApiError);
        expect(error.status).toBeUndefined();
        expect(isApiErrorStatus(error, 409)).toBe(false);
    });

    it("is a real Error, so existing callers reading .message still work", async () => {
        respondWith(500, { message: "boom" });

        const error = (await apiClient
            .get("/anything")
            .then(() => null)
            .catch((e: unknown) => e)) as ApiError;

        expect(error).toBeInstanceOf(Error);
        expect(error.message).toBe("boom");
    });
});

/**
 * An expired session used to produce a storm rather than a sign-out.
 *
 * Every query retried once by default, including on 401. A page runs about ten
 * queries, so ~20 failures each asked the client to renew the session — enough
 * to trip the /auth/refresh rate limit, so the user saw 429s instead of being
 * sent to the login page.
 */
describe("retry policy", () => {
    it("does not retry a request the server refused", async () => {
        const { queryClient } = await import("@/lib/query-client");
        const retry = queryClient.getDefaultOptions().queries?.retry;

        expect(typeof retry).toBe("function");

        const shouldRetry = retry as (n: number, e: unknown) => boolean;

        // Refusals: retrying cannot change the answer.
        for (const status of [400, 401, 403, 404, 409, 422, 429]) {
            expect(shouldRetry(0, new ApiError("refused", status))).toBe(false);
        }
    });

    it("still retries a genuine fault once", async () => {
        const { queryClient } = await import("@/lib/query-client");
        const shouldRetry = queryClient.getDefaultOptions().queries?.retry as (
            n: number,
            e: unknown
        ) => boolean;

        expect(shouldRetry(0, new ApiError("upstream broke", 502))).toBe(true);
        expect(shouldRetry(1, new ApiError("upstream broke", 502))).toBe(false);

        // A network failure has no status and is worth one retry.
        expect(shouldRetry(0, new ApiError("Network Error"))).toBe(true);
    });

    it("applies the same policy to mutations", async () => {
        const { queryClient } = await import("@/lib/query-client");
        const shouldRetry = queryClient.getDefaultOptions().mutations?.retry as (
            n: number,
            e: unknown
        ) => boolean;

        expect(typeof shouldRetry).toBe("function");
        expect(shouldRetry(0, new ApiError("refused", 401))).toBe(false);
    });
});
