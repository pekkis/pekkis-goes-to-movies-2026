import { defineConfig } from "vitest/config";

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
});
