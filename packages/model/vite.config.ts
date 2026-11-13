import { defineConfig } from "vite-plus";

export default defineConfig({
  // Cached by `vp run`. Vitest runs on Node, so its inputs are tracked automatically.
  run: {
    tasks: {
      typecheck: {
        command: "tsc",
        // TypeScript 7's tsc is a native binary whose file reads Vite Task does not see: without
        // these, a type error replays the cached success (found 2026-11-13).
        cache: {
          input: [
            { auto: true },
            "src/**",
            "test/**",
            "tsconfig.json",
            { pattern: "packages/*/src/**", base: "workspace" },
            { pattern: "tsconfig.base.json", base: "workspace" },
            { pattern: "pnpm-lock.yaml", base: "workspace" },
          ],
        },
      },
      test: "vp test run",
    },
  },
});
