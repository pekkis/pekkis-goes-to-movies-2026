import { describe, expect, it } from "vitest";
import { HttpUrl, Screening } from "../src/schema.ts";

describe("HttpUrl", () => {
  it.each([
    ["https://kino.example/liput/1", true],
    ["http://kino.example/", true],
    ["HTTPS://KINO.EXAMPLE/", true],
    ["javascript:alert(1)", false],
    ["JavaScript:alert(1)", false],
    ["data:text/html,<script>alert(1)</script>", false],
    ["vbscript:msgbox", false],
    ["ftp://kino.example/", false],
    ["/relative/path", false],
  ])("%s -> %s", (url, ok) => {
    expect(HttpUrl.safeParse(url).success).toBe(ok);
  });

  it("is what a screening's ticket link must be", () => {
    expect(Screening.shape.ticketUrl.safeParse("javascript:alert(1)").success).toBe(false);
  });
});
