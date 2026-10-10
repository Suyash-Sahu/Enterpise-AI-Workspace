import { ApiError } from "@/lib/api-client";

/**
 * What a failed connector call actually means, and what the user can do next.
 *
 * The mapping used to live inline in ConnectorErrorState as two booleans, with
 * everything that was not 409 or 502 collapsing into the sentence "Something
 * went wrong reaching the workspace API." That sentence threw away the reason
 * the backend had just supplied, so a signed-out session, a 500 and a dropped
 * network connection all read identically — and none of them told the user
 * what to do.
 *
 * "No Google account is connected" (409) is not an error at all: it is the
 * expected state before the user has granted Gmail/Drive access, and it must
 * render as a connect prompt rather than a failure.
 *
 * Kept as a pure function so every status can be asserted directly, without
 * standing up a renderer.
 */

export type ConnectorErrorKind =
    /** 409 — expected before consent. Not a failure. */
    | "not-connected"
    /** 502 — the grant exists but Google refused the call. */
    | "grant-rejected"
    /** 401/403 — the workspace session, not the Google grant. */
    | "signed-out"
    /** Anything else, including a transport failure with no status. */
    | "failed";

export interface ConnectorErrorDescriptor {
    kind: ConnectorErrorKind;
    title: string;
    /** Never a generic stand-in when the server explained itself. */
    body: string;
    /** Offer the connector OAuth flow. */
    canConnect: boolean;
    /** Offer a retry. Pointless for a refusal that retrying cannot change. */
    canRetry: boolean;
    status?: number;
}

/** The backend's own words, if it supplied any. */
function serverDetail(error: unknown): string | undefined {
    if (error instanceof ApiError) {
        const detail = error.detail?.trim() || error.message?.trim();
        return detail || undefined;
    }

    if (error instanceof Error) {
        return error.message.trim() || undefined;
    }

    return undefined;
}

export function describeConnectorError(
    error: unknown,
    resource: string
): ConnectorErrorDescriptor {
    const status = error instanceof ApiError ? error.status : undefined;
    const detail = serverDetail(error);

    if (status === 409) {
        return {
            kind: "not-connected",
            title: "No Google account connected",
            body: `Connect a Google account to see your ${resource} here.`,
            canConnect: true,
            // Retrying cannot conjure a grant; connecting is the only route.
            canRetry: false,
            status,
        };
    }

    if (status === 502) {
        return {
            kind: "grant-rejected",
            title: `Could not load ${resource}`,
            body:
                detail ??
                "Google refused the request. Your access may have expired.",
            canConnect: true,
            canRetry: true,
            status,
        };
    }

    if (status === 401 || status === 403) {
        return {
            kind: "signed-out",
            title: "Your session has ended",
            body: detail ?? "Sign in again to continue.",
            // A Google grant is not the problem, so do not send them to consent.
            canConnect: false,
            canRetry: false,
            status,
        };
    }

    return {
        kind: "failed",
        title: `Could not load ${resource}`,
        // The real reason, every time one exists. A generic sentence here is
        // what made unexpected failures unreportable.
        body:
            detail ??
            (status === undefined
                ? "The workspace API could not be reached."
                : `The workspace API returned an unexpected error (${status}).`),
        canConnect: false,
        canRetry: true,
        status,
    };
}
