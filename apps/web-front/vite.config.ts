import { defineConfig } from "vite-plus";

/**
 * Tasks only: Astro owns the app's Vite config (astro.config.ts), and Vitest reads
 * vitest.config.ts first. The build reads no environment: API_URL, SITE_URL and INDEXING
 * are server secrets read at runtime.
 */
export default defineConfig({
  run: {
    tasks: {
      typecheck: {
        command: "astro sync && tsc",
        // TypeScript 7's tsc is a native binary whose file reads Vite Task does not see: without
        // these, a type error replays the cached success (found 2026-11-13).
        cache: {
          input: [
            { auto: true },
            "src/**",
            "test/**",
            "*.ts",
            "tsconfig.json",
            ".astro/**",
            { pattern: "packages/*/src/**", base: "workspace" },
            { pattern: "tsconfig.base.json", base: "workspace" },
            { pattern: "pnpm-lock.yaml", base: "workspace" },
          ],
        },
      },
      test: "vp test run",
      build: "astro build",
    },
  },
});
