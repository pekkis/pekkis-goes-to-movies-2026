// @vitest-environment happy-dom
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CityProgramme } from "../../src/components/CityProgramme.tsx";
import { languageLine, ScreeningList } from "../../src/components/ScreeningList.tsx";
import { advanceMinutes, renderWithClock, freezeClockAt } from "../clock.tsx";
import { screening } from "../fixtures.ts";

freezeClockAt();

const at = (time: string, id = time) => screening({ id, startsAt: `2026-10-13T${time}:00+03:00` });

describe("ScreeningList", () => {
  it("shows time, film, venue and the cinema's own ticket link", () => {
    renderWithClock(<ScreeningList screenings={[screening()]} />);
    expect(screen.getByText("18.00")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Unohdettu saari" }).getAttribute("href")).toBe(
      "https://www.themoviedb.org/movie/1185806",
    );
    expect(screen.getByRole("link", { name: "Liput" }).getAttribute("href")).toBe(
      "https://kino.example/liput/1",
    );
    expect(screen.getByRole("link", { name: "Kino Testi" }).getAttribute("href")).toBe(
      "/fi/elokuvateatterit/kino-testi-jyvaskyla",
    );
    expect(screen.getByText(/, Sali 2/)).toBeTruthy();
  });

  it("links only matched films to TMDB and hides tickets when sold out", () => {
    renderWithClock(
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

  it("marks shows that start soon or have started, and keeps it current", () => {
    // Noon: 11.50 started 10 min ago (tickets still sold), 12.30 starts in 30 min.
    renderWithClock(<ScreeningList screenings={[at("11:50"), at("12:30"), at("18:00")]} />);
    const rows = screen.getAllByRole("listitem");
    expect(rows.map((r) => r.dataset["state"])).toEqual(["started", "soon", "later"]);
    expect(screen.getByText("alkanut")).toBeTruthy();
    expect(screen.getByText("alkaa 30 min päästä")).toBeTruthy();
    expect(screen.getAllByRole("link", { name: "Liput" })).toHaveLength(3);

    // Six minutes on, 11.50 is past its 15-minute ticket window; 12.30 is 24 min away.
    advanceMinutes(6);
    expect(screen.getByText("alkaa 24 min päästä")).toBeTruthy();
    expect(screen.getAllByRole("link", { name: "Liput" })).toHaveLength(2);
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

describe("CityProgramme", () => {
  it("puts started shows behind 'Näytä alkaneet' while others are still to come", () => {
    renderWithClock(
      <CityProgramme
        now={new Date().toISOString()}
        screenings={[at("10:00"), at("11:00"), at("19:00")]}
      />,
    );
    const details = screen.getByText("Näytä alkaneet (2)").closest("details");
    expect(details?.querySelectorAll("li")).toHaveLength(2);
    expect(details?.open).toBe(false);
  });

  it("shows everything as it is when nothing is left to come", () => {
    renderWithClock(
      <CityProgramme now={new Date().toISOString()} screenings={[at("10:00"), at("11:00")]} />,
    );
    expect(screen.queryByText(/Näytä alkaneet/)).toBeNull();
    expect(screen.getAllByText("alkanut")).toHaveLength(2);
  });
});
