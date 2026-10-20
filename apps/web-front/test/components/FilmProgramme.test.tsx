// @vitest-environment happy-dom
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FilmProgramme } from "../../src/components/FilmProgramme.tsx";
import { renderWithClock, freezeClockAt } from "../clock.tsx";
import { screening } from "../fixtures.ts";

freezeClockAt();

describe("FilmProgramme", () => {
  it("lists each film once, every showtime linking to the cinema's ticket page", () => {
    renderWithClock(
      <FilmProgramme
        screenings={[
          screening({
            id: "a",
            startsAt: "2026-10-13T20:00:00+03:00",
            ticketUrl: "https://kino.example/2",
          }),
          screening({ id: "b", startsAt: "2026-10-13T16:00:00+03:00" }),
        ]}
      />,
    );
    const film = screen.getByRole("heading", { name: "Unohdettu saari" });
    expect(within(film).getByRole("link").getAttribute("href")).toBe(
      "/fi/elokuvat/unohdettu-saari-1185806",
    );
    expect(screen.getByText("K-7 · 100 min · 2026")).toBeTruthy();
    const tickets = screen.getAllByRole("link", { name: /^Liput, klo/ });
    expect(tickets.map((a) => [a.textContent, a.getAttribute("href")])).toEqual([
      ["16.00", "https://kino.example/liput/1"],
      ["20.00", "https://kino.example/2"],
    ]);
  });

  it("shows a sold-out time without a ticket link", () => {
    renderWithClock(<FilmProgramme screenings={[screening({ availability: "sold-out" })]} />);
    expect(screen.queryByRole("link", { name: /^Liput/ })).toBeNull();
    expect(screen.getByText("18.00")).toBeTruthy();
    expect(screen.getByText("Loppuunmyyty")).toBeTruthy();
  });

  it("marks started and soon showtimes; a long-started one is no longer a ticket link", () => {
    renderWithClock(
      <FilmProgramme
        screenings={[
          screening({ id: "a", startsAt: "2026-10-13T11:00:00+03:00" }),
          screening({ id: "b", startsAt: "2026-10-13T12:45:00+03:00" }),
        ]}
      />,
    );
    expect(screen.getByText("alkanut")).toBeTruthy();
    expect(screen.getByText("alkaa 45 min päästä")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Liput, klo 11.00" })).toBeNull();
    expect(screen.getByRole("link", { name: "Liput, klo 12.45" })).toBeTruthy();
  });
});
