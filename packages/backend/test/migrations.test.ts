import { readdirSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { MIGRATIONS } from "../migrations/index.ts";

describe("migrations/index.ts", () => {
  it("lists every migration file, in order", () => {
    const files = readdirSync(new URL("../migrations", import.meta.url))
      .filter((f) => /^\d{4}_.+\.ts$/.test(f))
      .map((f) => f.replace(/\.ts$/, ""))
      .sort();
    expect(Object.keys(MIGRATIONS)).toEqual(files);
  });
});
