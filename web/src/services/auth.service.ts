import { apiClient } from "@/lib/api-client";
import type { User } from "@/types/auth";

/**
 * Auth surface.
 *
 * Every one of these is a backend route. This app no longer verifies
 * identities, mints tokens, or sets cookies of its own — the backend owns the
 * whole session lifecycle, and these URLs are same-origin only because Next
 * proxies /api/v1/* to it.
 *
 *   sign in  -> GET  /api/v1/auth/google/login   (redirects to Google)
 *   sign out -> POST /api/v1/auth/logout         (revokes and clears cookies)
 *   whoami   -> GET  /api/v1/users/me
 */
export const SIGN_IN_URL = "/api/v1/auth/google/login";
export const LOGOUT_URL = "/api/v1/auth/logout";

/** The signed-in user, or null when there is no session. */
export async function getCurrentUser(): Promise<User | null> {
    try {
        const response = await apiClient.get<User>("/users/me");
        return response.data ?? null;
    } catch {
        // Not signed in, or the session has ended. Either way: no user.
        return null;
    }
}

export const authService = {
    getCurrentUser,
    signInUrl: SIGN_IN_URL,
    logoutUrl: LOGOUT_URL,
};

export const AuthService = authService;

export default authService;
