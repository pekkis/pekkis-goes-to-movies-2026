import { readdirSync } from "node:fs";
import { describe, expect, it } from "vite-plus/test";
import { MIGRATIONS } from "../migrations/index.ts";

describe("migrations/index.ts", () => {
  it("lists every migration file, in order", () => {
    const files = readdirSync(new URL("../migrations", import.meta.url))
      .filter((f) => /^\d{4}_.+\.ts$/.test(f))
      .map((f) => f.replace(/\.ts$/, ""))
      .toSorted();
    expect(Object.keys(MIGRATIONS)).toEqual(files);
  });
});
