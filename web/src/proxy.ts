import { NextRequest, NextResponse } from "next/server";

const ACCESS_COOKIE = "amof_access";
const REFRESH_COOKIE = "amof_refresh";

/**
 * Route guard for the workspace.
 *
 * Uses the `proxy` file convention. `middleware` is deprecated and renamed
 * in this Next version — see
 * node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/proxy.md
 *
 * This is a UX guard, not the security boundary. It deliberately does not
 * verify the token signature: the backend signs these tokens and is the only
 * party that should hold that key, and copying a signing secret into the web
 * tier to enable a redirect would be a worse trade than this check is worth.
 * Every route that returns data enforces auth server-side in the backend.
 */
function hasSession(request: NextRequest): boolean {
  return Boolean(
    request.cookies.get(ACCESS_COOKIE)?.value ||
      request.cookies.get(REFRESH_COOKIE)?.value
  );
}

export function proxy(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;
  const authenticated = hasSession(request);

  if (pathname === "/login") {
    // A cookie that exists is not a cookie that works, and this guard cannot
    // tell the difference — it deliberately does not verify signatures. When
    // the client has just been refused and sent the user here, sending them
    // back to the app produced a full-page redirect loop:
    //
    //   /dashboard -> API 401 -> /login -> guard -> /dashboard -> ...
    //
    // An explicit error means the credential has already been rejected once,
    // so believe that over the cookie's mere presence.
    const rejected = searchParams.has("error");

    if (authenticated && !rejected) {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }

    return NextResponse.next();
  }

  if (!authenticated) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

// Covers the whole (workspace) route group, not just /dashboard. Previously
// ~20 workspace pages were left to a client-side guard alone.
export const config = {
  matcher: [
    "/login",
    "/approvals/:path*",
    "/calendar/:path*",
    "/chat/:path*",
    "/communication/:path*",
    "/dashboard/:path*",
    "/database/:path*",
    "/documents/:path*",
    "/drive/:path*",
    "/execution/:path*",
    "/gmail/:path*",
    "/integrations/:path*",
    "/jira/:path*",
    "/knowledge/:path*",
    "/meet/:path*",
    "/notifications/:path*",
    "/projects/:path*",
    "/research/:path*",
    "/settings/:path*",
    "/supervisor/:path*",
    "/tasks/:path*",
    "/writer/:path*",
  ],
};
