// @vitest-environment happy-dom
import { describe, expect, it } from "vitest";
import { popupContent } from "../../../src/lib/map/popup.ts";

describe("popupContent", () => {
  it("shows the venue and links to its page", () => {
    const el = popupContent({
      name: "Kino Myyri",
      city: "Vantaa",
      address: "Kinorinne 6, 01600 Vantaa",
      path: "/fi/elokuvateatterit/kino-myyri-vantaa",
    });
    expect(el.textContent).toContain("Kino Myyri");
    expect(el.textContent).toContain("Kinorinne 6, 01600 Vantaa");
    expect(el.querySelector("a")?.getAttribute("href")).toBe(
      "/fi/elokuvateatterit/kino-myyri-vantaa",
    );
  });

  it("treats venue names as text, never markup", () => {
    const el = popupContent({
      name: "<img src=x onerror=alert(1)>",
      city: "X",
      address: "",
      path: "/",
    });
    expect(el.querySelector("img")).toBeNull();
    expect(el.textContent).toContain("<img src=x onerror=alert(1)>");
  });
});
