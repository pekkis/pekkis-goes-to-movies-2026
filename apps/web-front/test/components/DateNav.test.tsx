// @vitest-environment happy-dom
import { cleanup, render, screen } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";
import { DateNav } from "../../src/components/DateNav.tsx";

afterEach(cleanup);

describe("DateNav", () => {
  it("renders a plain GET form on the server, which works without JavaScript", () => {
    const html = renderToString(<DateNav date="2026-10-13" />);
    expect(html).toMatch(/<form [^>]*method="get"/);
    expect(html).toContain('name="date"');
    expect(html).toContain('value="2026-10-13"');
  });

  it("becomes React Aria's date picker once hydrated", async () => {
    render(<DateNav date="2026-10-13" navigate={() => {}} />);
    // After the effect runs, the native input is gone and a labelled date group is there.
    expect(await screen.findByRole("group", { name: "Päivä" })).toBeTruthy();
    expect(document.querySelector('input[name="date"]')).toBeNull();
    expect(screen.getByRole("button", { name: /Avaa kalenteri/ })).toBeTruthy();
  });
});
