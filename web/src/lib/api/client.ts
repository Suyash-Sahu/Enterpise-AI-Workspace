import { apiClient as axiosClient, ApiError } from "@/lib/api-client";

interface RequestOptions {
    method?: string;
    body?: unknown;
    headers?: Record<string, string>;
    params?: Record<string, string>;
}

/**
 * Thin wrapper over the shared axios client.
 *
 * This used to be a standalone fetch client with its own hardcoded base URL —
 * pointing at port 8000 while the backend runs on 8001 — and it sent no
 * Authorization header. Delegating means every caller now gets the correct
 * base URL, the bearer token, and refresh-on-401 for free.
 */
export async function apiClient<T>(
    endpoint: string,
    options: RequestOptions = {}
): Promise<T> {
    const { params, headers, method = "GET", body } = options;

    try {
        const res = await axiosClient.request<T>({
            url: endpoint,
            method,
            params,
            headers,
            data: body instanceof FormData ? body : body ?? undefined,
        });
        return res.data;
    } catch (error) {
        // axiosClient's own interceptor already throws a real ApiError with
        // the actual HTTP status (409/401/502/...) -- rethrow it as-is rather
        // than discarding that status behind a hardcoded 0.
        if (error instanceof ApiError) {
            throw error;
        }
        throw new ApiError((error as Error).message || "API request failed", 0);
    }
}
