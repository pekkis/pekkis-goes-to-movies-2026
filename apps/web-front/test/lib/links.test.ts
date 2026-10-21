import { describe, expect, it } from "vitest";
import { safeHref } from "../../src/lib/links.ts";

describe("safeHref", () => {
  it.each([
    ["https://kino.example/liput/1", "https://kino.example/liput/1"],
    ["http://kino.example/", "http://kino.example/"],
    ["javascript:alert(1)", undefined],
    [" JavaScript:alert(1)", undefined],
    ["java\tscript:alert(1)", undefined],
    ["data:text/html,<script>alert(1)</script>", undefined],
    ["/relative", undefined],
    ["", undefined],
    [null, undefined],
    [undefined, undefined],
  ])("%j -> %j", (url, expected) => {
    expect(safeHref(url)).toBe(expected);
  });
});
