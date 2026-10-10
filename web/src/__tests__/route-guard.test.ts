/**
 * The route guard must never bounce a user between two pages.
 *
 * Second half of the infinite loop. The guard cannot verify a token — it
 * deliberately holds no signing key — so it treated the mere presence of a
 * cookie as "signed in". When the API had already rejected that cookie, the
 * client sent the user to /login and the guard sent them straight back:
 *
 *   /dashboard -> API 401 -> /login -> guard -> /dashboard -> ...
 *
 * a full-page redirect loop that reloaded the app indefinitely.
 */

import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { proxy } from "@/proxy";

const ACCESS_COOKIE = "amof_access";

function request(path: string, { cookie = true }: { cookie?: boolean } = {}) {
    const req = new NextRequest(new URL(`http://localhost:3000${path}`));

    if (cookie) {
        req.cookies.set(ACCESS_COOKIE, "a-cookie-that-exists-but-may-not-work");
    }

    return req;
}

/** Where the guard sends this request, or null when it lets it through. */
function destinationOf(path: string, opts?: { cookie?: boolean }): string | null {
    const response = proxy(request(path, opts));
    const location = response.headers.get("location");

    return location ? new URL(location).pathname + new URL(location).search : null;
}

describe("route guard redirects", () => {
    it("does not send a rejected session back into the app", () => {
        // The exact loop: arriving at /login *because* the API refused must
        // not redirect to /dashboard, whatever the cookie jar still holds.
        expect(destinationOf("/login?error=session_expired")).toBeNull();
    });

    it("still sends a signed-in user from /login into the app", () => {
        expect(destinationOf("/login")).toBe("/dashboard");
    });

    it("lets an anonymous visitor reach /login", () => {
        expect(destinationOf("/login", { cookie: false })).toBeNull();
    });

    it("sends an anonymous visitor away from a workspace route", () => {
        expect(destinationOf("/dashboard", { cookie: false })).toBe(
            "/login?from=%2Fdashboard"
        );
    });

    it("settles: the redirect chain from a rejected session terminates", () => {
        // Walk the guard the way a browser would, following each hop.
        let path = "/login?error=session_expired";
        const visited: string[] = [];

        for (let hop = 0; hop < 10; hop += 1) {
            visited.push(path);
            const next = destinationOf(path);

            if (next === null) break;

            expect(visited).not.toContain(next);
            path = next;
        }

        // One hop, then it settles. A loop would have thrown above or run out.
        expect(visited.length).toBeLessThanOrEqual(2);
    });

    it("authenticated navigation to workspace routes passes straight through", () => {
        // Requirement 12: these must not redirect at all, or every page load
        // becomes a reload.
        for (const path of [
            "/dashboard",
            "/integrations",
            "/gmail",
            "/drive",
            "/chat",
        ]) {
            expect(destinationOf(path)).toBeNull();
        }
    });

    it("leaves both Google flows alone", () => {
        // Requirement 10 and 11: both OAuth legs live under /api/v1, which the
        // matcher never covers, so the guard cannot interpose a redirect
        // between sign-in and connect.
        for (const apiPath of [
            "/api/v1/auth/google/login",
            "/api/v1/auth/google/callback",
            "/api/v1/connectors/google/login",
            "/api/v1/connectors/google/oauth/callback",
        ]) {
            expect(destinationOf(apiPath)).toBeNull();
        }
    });
});
