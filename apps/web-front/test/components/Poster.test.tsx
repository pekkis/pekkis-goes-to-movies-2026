// @vitest-environment happy-dom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Poster } from "../../src/components/Poster.tsx";

afterEach(cleanup);

describe("Poster", () => {
  it("asks TMDB for the size it is shown at, and twice that for sharp screens", () => {
    render(<Poster url="https://image.tmdb.org/t/p/w500/a.jpg" title="Lapin sota" size="md" />);
    const img = screen.getByRole("img", { name: "Lapin sota – juliste" }) as HTMLImageElement;
    expect(img.getAttribute("src")).toBe("https://image.tmdb.org/t/p/w154/a.jpg");
    expect(img.getAttribute("srcset")).toContain("w342/a.jpg 2x");
    expect(img.getAttribute("loading")).toBe("lazy");
    expect([img.getAttribute("width"), img.getAttribute("height")]).toEqual(["144", "216"]);
  });

  it("loads a page's own poster at once", () => {
    render(<Poster url="https://image.tmdb.org/t/p/w500/a.jpg" title="X" size="lg" eager />);
    expect(screen.getByRole("img").getAttribute("loading")).toBe("eager");
  });

  it("is a box with the title when there is no poster", () => {
    render(<Poster url={null} title="Kotimaiset lyhytelokuvat" />);
    const box = screen.getByRole("img", { name: "Kotimaiset lyhytelokuvat – ei julistetta" });
    expect(box.tagName).toBe("SPAN");
    expect(box.textContent).toBe("Kotimaiset lyhytelokuvat");
  });
});
