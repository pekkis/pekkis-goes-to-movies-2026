// @vitest-environment happy-dom
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SearchResults } from "../../src/components/SearchResults.tsx";
import { freezeClockAt } from "../clock.tsx";
import { NOON_INSTANT, screening } from "../fixtures.ts";

freezeClockAt();

const film = (id: string, title: string) => ({ ...screening().film, id, title });
const venue = (id: string, name: string) => ({ id, name, city: "Tampere", geo: null });

// Plevna: Digger 18.00, Lapin sota 21.15; Atlas: Lapin sota 13.00 the next day.
const SHOWS = [
  screening({ id: "1", venue: venue("plevna", "Plevna"), film: film("digger", "Digger") }),
  screening({
    id: "2",
    startsAt: "2026-10-13T21:15:00+03:00",
    venue: venue("plevna", "Plevna"),
    film: film("lapin", "Lapin sota"),
  }),
  screening({
    id: "3",
    startsAt: "2026-10-14T13:00:00+03:00",
    businessDate: "2026-10-14",
    venue: venue("atlas", "Atlas"),
    film: film("lapin", "Lapin sota"),
  }),
];

const renderResults = () =>
  render(
    <SearchResults
      screenings={SHOWS}
      distances={{ plevna: 0.4, atlas: 1.2 }}
      now={NOON_INSTANT.toString()}
    />,
  );

const facet = (name: string) =>
  screen.getByText(new RegExp(`^${name}( \\(\\d+\\))?$`), { selector: "summary" }).parentElement!;
const option = (facetName: string, label: string) =>
  within(facet(facetName)).getByRole("checkbox", { name: new RegExp(label) });
const countOf = (facetName: string, label: string) =>
  option(facetName, label).closest("label")!.lastElementChild!.textContent;

describe("SearchResults", () => {
  it("shows everything by day, venues nearest first with their distance", () => {
    renderResults();
    expect(screen.getByText("3 näytöstä")).toBeTruthy();
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual([
      "tiistaina 13.10. · 2 näytöstä",
      "keskiviikkona 14.10. · 1 näytös",
    ]);
    const venues = within(facet("Elokuvateatterit")).getAllByRole("checkbox");
    expect(venues.map((v) => v.closest("label")!.textContent)).toEqual([
      "Plevna · 0,4 km2",
      "Atlas · 1,2 km1",
    ]);
  });

  it("narrows the results and the other facets' counts when a venue is checked", () => {
    renderResults();
    fireEvent.click(option("Elokuvateatterit", "Plevna"));
    expect(screen.getByText("2 näytöstä")).toBeTruthy();
    expect(countOf("Elokuvat", "Lapin sota")).toBe("1");
    // The other venue keeps its count, so it can be added.
    expect(countOf("Elokuvateatterit", "Atlas")).toBe("1");
    fireEvent.click(option("Kellonaika", "klo 21 jälkeen"));
    expect(screen.getByText("1 näytös")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Tyhjennä" }));
    expect(screen.getByText("3 näytöstä")).toBeTruthy();
  });

  it("disables a value that would show nothing, and says so when unchecking leaves nothing", () => {
    renderResults();
    fireEvent.click(option("Elokuvat", "Digger"));
    // Digger plays only at Plevna: Atlas would show nothing.
    expect((option("Elokuvateatterit", "Atlas") as HTMLInputElement).disabled).toBe(true);
    fireEvent.click(option("Elokuvat", "Digger"));
    // Both venues, then Digger; unchecking Plevna leaves Atlas, where Digger never plays.
    fireEvent.click(option("Elokuvateatterit", "Plevna"));
    fireEvent.click(option("Elokuvateatterit", "Atlas"));
    fireEvent.click(option("Elokuvat", "Digger"));
    fireEvent.click(option("Elokuvateatterit", "Plevna"));
    expect(screen.getByText(/Valinnoilla ei löytynyt näytöksiä/)).toBeTruthy();
  });
});

describe("SearchResults: long lists", () => {
  it("narrows a long venue list by name or city as you type", () => {
    const many = Array.from({ length: 10 }, (_, i) =>
      screening({
        id: `v${i}`,
        venue: { id: `v${i}`, name: `Kino ${i}`, city: i === 3 ? "Tampere" : "Oulu", geo: null },
      }),
    );
    render(<SearchResults screenings={many} distances={{}} now={NOON_INSTANT.toString()} />);
    const venues = facet("Elokuvateatterit");
    fireEvent.change(within(venues).getByRole("searchbox"), { target: { value: "tampere" } });
    expect(
      within(venues)
        .getAllByRole("checkbox")
        .map((c) => c.closest("label")!.textContent),
    ).toEqual(["Kino 3 · Tampere1"]);
  });
});
