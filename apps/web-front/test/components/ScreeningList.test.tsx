// @vitest-environment happy-dom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { languageLine, ScreeningList } from "../../src/components/ScreeningList.tsx";
import { screening } from "../fixtures.ts";

afterEach(cleanup);

describe("ScreeningList", () => {
  it("shows time, film, venue and the cinema's own ticket link", () => {
    render(<ScreeningList screenings={[screening()]} />);
    expect(screen.getByText("18.00")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Unohdettu saari" }).getAttribute("href")).toBe(
      "https://www.themoviedb.org/movie/1185806",
    );
    expect(screen.getByRole("link", { name: "Liput" }).getAttribute("href")).toBe(
      "https://kino.example/liput/1",
    );
    expect(screen.getByText(/Kino Testi, Sali 2/)).toBeTruthy();
  });

  it("links only matched films to TMDB and hides tickets when sold out", () => {
    render(
      <ScreeningList
        screenings={[
          screening({
            availability: "sold-out",
            film: { ...screening().film, id: "kino:film:9", kind: "listing", title: "Ooppera" },
          }),
        ]}
      />,
    );
    expect(screen.queryByRole("link", { name: "Ooppera" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Liput" })).toBeNull();
    expect(screen.getByText("Loppuunmyyty")).toBeTruthy();
  });

  it.each([
    [
      { audio: ["fi"], dubbed: true, subtitles: { kind: "none", languages: [] } },
      "puhuttu suomi, ei tekstitystä",
    ],
    [
      { audio: ["en"], dubbed: false, subtitles: { kind: "languages", languages: ["fi", "sv"] } },
      "englanti, tekstit: suomi, ruotsi",
    ],
    [{ audio: [], dubbed: null, subtitles: { kind: "unknown", languages: [] } }, ""],
  ])("describes languages: %j", (s, expected) => {
    expect(languageLine(s)).toBe(expected);
  });
});
