import { defineConfig } from "vite-plus";

// Integration tests need TEST_DATABASE_URL from the repo-root .env.
try {
  process.loadEnvFile(new URL("../../.env", import.meta.url));
} catch {
  // no .env: rely on the real environment
}

export default defineConfig({
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
