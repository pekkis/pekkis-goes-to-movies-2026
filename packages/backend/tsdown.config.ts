import { defineConfig } from "tsdown";

/**
 * Production bundle for the Docker image only; development runs the .ts sources directly.
 * @pgtm/model is TypeScript source and Node will not strip types inside node_modules, so it
 * is bundled in. Everything else in `dependencies` stays external and is installed by
 * `pnpm deploy --prod`.
 */
export default defineConfig({
  entry: { serve: "src/cli/serve.ts", migrate: "src/cli/migrate.ts" },
  outDir: "dist",
  format: "esm",
  platform: "node",
  target: "node24",
  clean: true,
  dts: false,
  deps: { alwaysBundle: ["@pgtm/model"] },
});
