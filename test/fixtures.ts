import { readFileSync } from "node:fs";
import { join } from "node:path";

export const loadFixture = (...path: string[]): unknown =>
  JSON.parse(readFileSync(join(import.meta.dirname, "fixtures", ...path), "utf8"));
