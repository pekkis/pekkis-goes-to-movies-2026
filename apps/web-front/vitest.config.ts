/// <reference types="vitest/config" />
import { getViteConfig } from "astro/config";

export default getViteConfig({
  test: {
    // Component tests opt into a DOM with `// @vitest-environment happy-dom`.
    environment: "node",
  },
});
