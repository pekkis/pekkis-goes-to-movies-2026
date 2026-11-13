import { defineConfig } from "vite-plus";

// Integration tests need TEST_DATABASE_URL from the repo-root .env.
try {
  process.loadEnvFile(new URL("../../.env", import.meta.url));
} catch {
  // no .env: rely on the real environment
}

export default defineConfig({
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
            "migrations/**",
            "tsconfig.json",
            { pattern: "packages/*/src/**", base: "workspace" },
            { pattern: "tsconfig.base.json", base: "workspace" },
            { pattern: "pnpm-lock.yaml", base: "workspace" },
          ],
        },
      },
      test: {
        command: "vp test run",
        // Tasks run in a clean environment: CI passes the database here, not in .env.
        cache: { env: ["TEST_DATABASE_URL"] },
      },
    },
  },
  test: {
    globalSetup: "test/global-setup.ts",
    // Integration tests share one database.
    fileParallelism: false,
  },
  /**
   * Production bundle for the Docker image only; development runs the .ts sources directly.
   * @pgtm/model is TypeScript source and Node will not strip types inside node_modules, so it
   * is bundled in, subpaths (`@pgtm/model/time`) included. Everything else in `dependencies`
   * stays external and is installed by `pnpm deploy --prod`.
   */
  pack: {
    entry: {
      serve: "src/cli/serve.ts",
      migrate: "src/cli/migrate.ts",
      ingest: "src/cli/ingest.ts",
    },
    outDir: "dist",
    format: "esm",
    platform: "node",
    target: "node26",
    clean: true,
    dts: false,
    deps: { alwaysBundle: [/^@pgtm\/model(\/|$)/] },
  },
});
