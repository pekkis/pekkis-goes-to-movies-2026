// @vitest-environment happy-dom
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { FilmProgramme } from "../../src/components/FilmProgramme.tsx";
import { screening } from "../fixtures.ts";

afterEach(cleanup);

describe("FilmProgramme", () => {
  it("lists each film once, every showtime linking to the cinema's ticket page", () => {
    render(
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
      "https://www.themoviedb.org/movie/1185806",
    );
    expect(screen.getByText("K-7 · 100 min · 2026")).toBeTruthy();
    const tickets = screen.getAllByRole("link", { name: /^Liput, klo/ });
    expect(tickets.map((a) => [a.textContent, a.getAttribute("href")])).toEqual([
      ["16.00", "https://kino.example/liput/1"],
      ["20.00", "https://kino.example/2"],
    ]);
  });

  it("shows a sold-out time without a ticket link", () => {
    render(<FilmProgramme screenings={[screening({ availability: "sold-out" })]} />);
    expect(screen.queryByRole("link", { name: /^Liput/ })).toBeNull();
    expect(screen.getByText("18.00")).toBeTruthy();
    expect(screen.getByText("Loppuunmyyty")).toBeTruthy();
  });
});
