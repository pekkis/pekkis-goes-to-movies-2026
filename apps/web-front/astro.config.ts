import node from "@astrojs/node";
import react from "@astrojs/react";
import { vanillaExtractPlugin } from "@vanilla-extract/vite-plugin";
import { defineConfig, envField } from "astro/config";

export default defineConfig({
  // Every page is rendered per request: the programme changes daily and pages read the API.
  output: "server",
  adapter: node({ mode: "standalone" }),
  integrations: [react()],
  i18n: {
    locales: ["fi", "sv", "en"],
    defaultLocale: "fi",
    routing: { prefixDefaultLocale: true },
  },
  env: {
    // "secret" is Astro's runtime access: "public" values are inlined at build time, and
    // these are deployment settings read when the server starts. Neither is actually secret.
    schema: {
      API_URL: envField.string({
        context: "server",
        access: "secret",
        default: "http://127.0.0.1:3000",
      }),
      // Search engines stay out until every cinema has been notified (AGENTS.md).
      INDEXING: envField.enum({
        context: "server",
        access: "secret",
        values: ["on", "off"],
        default: "off",
      }),
    },
  },
  vite: {
    plugins: [vanillaExtractPlugin()],
    // MapLibre (~1 MB, 279 kB gzipped) is one chunk on purpose, loaded only by /fi/kartta.
    build: { chunkSizeWarningLimit: 1200 },
  },
});
