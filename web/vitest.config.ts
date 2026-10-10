import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

/**
 * There was no vitest config, so the `@/...` alias every test and source file
 * uses did not resolve and the suite failed at import with "Cannot find
 * package '@/services/auth.service'". The tests had therefore never run.
 */
export default defineConfig({
    resolve: {
        alias: {
            "@": fileURLToPath(new URL("./src", import.meta.url)),
        },
    },
    test: {
        environment: "node",
        include: ["src/**/*.{test,spec}.{ts,tsx}"],
    },
});
