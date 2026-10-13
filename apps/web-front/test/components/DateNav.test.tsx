import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { DateNav } from "../../src/components/DateNav.tsx";

describe("DateNav", () => {
  it("is a plain GET form with a native date input, needing no JavaScript", () => {
    const html = renderToString(<DateNav date="2026-10-13" />);
    expect(html).toMatch(/<form [^>]*method="get"/);
    expect(html).toMatch(/<input [^>]*type="date"[^>]*name="date"[^>]*value="2026-10-13"/);
    expect(html).toContain('type="submit"');
    expect(html).toContain('href="?date=2026-10-12"');
    expect(html).toContain('href="?date=2026-10-14"');
  });
});
