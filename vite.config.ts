// vp migrate: merged .oxlintrc.json (f4c348f6fc04f79af9e36f61e81e61ad).
import { defineConfig } from "vite-plus";

export default defineConfig({
  fmt: {
    ignorePatterns: [
      "vendor/**",
      "apps/fpgm/**",
      "apps/web-front/.astro/**",
      "apps/web-front/dist/**",
      "packages/fetcher/test/fixtures/tapiola/**",
    ],
  },
  lint: {
    plugins: ["eslint", "typescript", "unicorn", "oxc", "react"],
    categories: {
      correctness: "error",
      suspicious: "warn",
    },
    rules: {
      "eslint/curly": ["error", "all"],
      "react/rules-of-hooks": "error",
      "react/exhaustive-deps": "error",
      "react/no-direct-mutation-state": "error",
      "react/jsx-key": "error",
      "react/react-in-jsx-scope": "off",
      "typescript/no-floating-promises": "error",
      "typescript/no-misused-promises": "error",
      "typescript/await-thenable": "error",
      "typescript/no-unnecessary-condition": "warn",
      "typescript/no-unsafe-type-assertion": "off",
      "vite-plus/prefer-vite-plus-imports": "error",
    },
    ignorePatterns: [
      "vendor/**",
      "apps/fpgm/**",
      "apps/web-front/.astro/**",
      "apps/web-front/dist/**",
    ],
    overrides: [
      {
        files: ["**/test/**"],
        rules: {
          "unicorn/consistent-function-scoping": "off",
          "typescript/require-array-sort-compare": "off",
        },
      },
    ],
    options: {
      typeAware: true,
      typeCheck: false,
    },
    jsPlugins: [
      {
        name: "vite-plus",
        specifier: "vite-plus/oxlint-plugin",
      },
    ],
  },
});
