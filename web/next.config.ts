import type { NextConfig } from "next";

/**
 * The API is proxied rather than called directly.
 *
 * Sessions are httpOnly cookies with SameSite=strict, which the browser sends
 * only on same-site requests. With the app on :3000 and the API on :8001 those
 * are different sites, so every cookie would be silently dropped and the user
 * would look permanently signed out. Proxying /api/v1/* through Next puts the
 * browser on one origin, which is what makes strict cookies workable — and it
 * keeps the backend off the public network in production.
 */
const BACKEND_URL =
    process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8001";

const nextConfig: NextConfig = {
    // Standalone output: the Docker image copies only .next/standalone
    // instead of the full node_modules tree. Doesn't affect `next dev`.
    output: "standalone",
    async rewrites() {
        return [
            {
                source: "/api/v1/:path*",
                destination: `${BACKEND_URL}/api/v1/:path*`,
            },
        ];
    },
};

export default nextConfig;
