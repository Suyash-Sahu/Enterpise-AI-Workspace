/**
 * A 409 from a connector call is an expected state, not a failure.
 *
 * The backend answers "No Google account is connected. Connect one to
 * continue." with 409 whenever the signed-in user has never granted Gmail or
 * Drive access. The UI mapped that through two inline booleans and rendered
 * everything outside 409/502 as "Something went wrong reaching the workspace
 * API" — a sentence that both hid the backend's own explanation and offered no
 * next step.
 *
 * These assert the mapping for every status the connector can produce.
 */

import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api-client";
import { describeConnectorError } from "@/lib/connector-state";

/** Exactly what the backend sends when there is no grant. */
const NOT_CONNECTED = new ApiError(
    "No Google account is connected. Connect one to continue.",
    409,
    "No Google account is connected. Connect one to continue."
);

describe("no Google grant", () => {
    it("is a connect prompt, not an error", () => {
        const state = describeConnectorError(NOT_CONNECTED, "Gmail messages");

        expect(state.kind).toBe("not-connected");
        expect(state.title).toBe("No Google account connected");
        expect(state.canConnect).toBe(true);
    });

    it("never shows the generic failure sentence", () => {
        const state = describeConnectorError(NOT_CONNECTED, "Gmail messages");

        expect(state.title).not.toMatch(/something went wrong/i);
        expect(state.body).not.toMatch(/something went wrong/i);
    });

    it("names the resource the user was trying to reach", () => {
        expect(describeConnectorError(NOT_CONNECTED, "Drive files").body).toContain(
            "Drive files"
        );
    });

    it("does not offer a retry, which cannot create a grant", () => {
        expect(describeConnectorError(NOT_CONNECTED, "Gmail messages").canRetry).toBe(
            false
        );
    });
});

describe("real failures still read as failures", () => {
    it("reports Google refusing the call, and offers reconnecting", () => {
        const state = describeConnectorError(
            new ApiError("Google request failed.", 502, "Google request failed."),
            "Drive files"
        );

        expect(state.kind).toBe("grant-rejected");
        expect(state.canRetry).toBe(true);
        expect(state.canConnect).toBe(true);
    });

    it("keeps the backend's own words for an unexpected status", () => {
        // The defect: a 500 rendered the same generic sentence as everything
        // else, so the reason the server gave was never shown to anyone.
        const state = describeConnectorError(
            new ApiError("Database is unavailable", 500, "Database is unavailable"),
            "your workspace"
        );

        expect(state.kind).toBe("failed");
        expect(state.body).toBe("Database is unavailable");
        expect(state.canConnect).toBe(false);
    });

    it("reports an unexpected 4xx with its status rather than swallowing it", () => {
        const state = describeConnectorError(new ApiError("", 418), "Gmail messages");

        expect(state.kind).toBe("failed");
        expect(state.body).toContain("418");
    });

    it("separates an ended session from a missing Google grant", () => {
        for (const status of [401, 403]) {
            const state = describeConnectorError(
                new ApiError("Could not validate credentials", status),
                "Gmail messages"
            );

            expect(state.kind).toBe("signed-out");
            // Sending someone to Google consent will not fix their workspace
            // session, so that action must not be offered here.
            expect(state.canConnect).toBe(false);
        }
    });

    it("says the API was unreachable when there is no status at all", () => {
        const state = describeConnectorError(new ApiError("Network Error"), "Gmail messages");

        expect(state.kind).toBe("failed");
        expect(state.body).toBe("Network Error");
    });

    it("survives something that is not an Error", () => {
        const state = describeConnectorError("just a string", "Gmail messages");

        expect(state.kind).toBe("failed");
        expect(state.body).toBe("The workspace API could not be reached.");
    });
});
