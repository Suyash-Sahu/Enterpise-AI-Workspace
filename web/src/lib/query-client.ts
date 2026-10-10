import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api-client";

/**
 * Retrying a rejected request cannot make it succeed.
 *
 * Every query retried once by default, including on 401. A page runs roughly
 * ten queries, so an expired session produced ~20 failures, each of which
 * asked the API client to renew — enough to trip the refresh rate limit and
 * turn "your session ended" into a storm of 429s.
 *
 * 4xx means the server understood and refused: wrong credentials, no Google
 * account connected, not allowed. Only genuine faults are worth a second go.
 */
function shouldRetry(failureCount: number, error: unknown): boolean {
    const status = error instanceof ApiError ? error.status : undefined;

    if (status !== undefined && status >= 400 && status < 500) {
        return false;
    }

    return failureCount < 1;
}

export const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 1000 * 60 * 5, // 5 minutes
            retry: shouldRetry,
            refetchOnWindowFocus: false,
        },
        mutations: {
            retry: shouldRetry,
        },
    },
});
