import { describe, expect, it, vi } from "vitest";
import type { HttpClient } from "../../../src/lib/http.ts";
import { emptyDaysBefore, fetchMyCloudCinema } from "../../../src/providers/mycloudcinema/fetch.ts";
import { MYCLOUDCINEMA_SITES } from "../../../src/providers/mycloudcinema/sites.ts";

const site = (provider: string) => MYCLOUDCINEMA_SITES.find((s) => s.provider === provider)!;

const fakeHttp = () => {
  const getJson = vi.fn(async (_url: string, _query?: unknown) => ({ data: [], resultCode: 0 }));
  const http: HttpClient = { getJson, getText: vi.fn(), postForm: vi.fn() };
  const showtimeQueries = () =>
    getJson.mock.calls
      .filter(([url]) => String(url).endsWith("getShowTimesDays"))
      .map(([, query]) => query);
  return { http, showtimeQueries };
};

describe("fetchMyCloudCinema", () => {
  it("asks Cine Mäntsälä one day at a time: it answers only the requested day (2026-10-20)", async () => {
    const { http, showtimeQueries } = fakeHttp();
    await fetchMyCloudCinema(http, site("cinemantsala"), { from: "2026-10-20", days: 7 });
    expect(showtimeQueries()).toEqual(
      ["20", "21", "22", "23", "24", "25", "26"].map((d) => ({
        cinema_id: 1,
        date: `2026-10-${d}`,
        number_of_days: 1,
      })),
    );
  });

  it("asks a week per request elsewhere", async () => {
    const { http, showtimeQueries } = fakeHttp();
    await fetchMyCloudCinema(http, site("biorex"), {
      from: "2026-10-20",
      days: 7,
      cinemaIds: [2],
    });
    expect(showtimeQueries()).toEqual([{ cinema_id: 2, date: "2026-10-20", number_of_days: 7 }]);
  });

  it("asks each empty day again when a week's answer stops short (BioRex Verkatehdas, 2026-10-22)", async () => {
    const shows = (...dates: string[]) => ({
      resultCode: 0,
      data: dates.map((d, i) => ({ show_time_id: i, business_date: d })),
    });
    const getJson = vi.fn(async (url: string, query?: unknown) => {
      if (!String(url).endsWith("getShowTimesDays")) {
        return { data: [], resultCode: 0 };
      }
      const { date, number_of_days } = query as { date: string; number_of_days: number };
      // The week's answer has 22.–24.10 only; asked alone, each later day has shows.
      if (number_of_days === 7 && date === "2026-10-22") {
        return shows("2026-10-22", "2026-10-23", "2026-10-24");
      }
      if (number_of_days === 7) {
        return shows("2026-10-29");
      }
      return shows(date);
    });
    const http: HttpClient = { getJson, getText: vi.fn(), postForm: vi.fn() };
    const raw = await fetchMyCloudCinema(http, site("biorex"), {
      from: "2026-10-22",
      days: 14,
      cinemaIds: [1],
    });
    const asked = getJson.mock.calls
      .filter(([url]) => String(url).endsWith("getShowTimesDays"))
      .map(([, q]) => q);
    expect(asked).toEqual([
      { cinema_id: 1, date: "2026-10-22", number_of_days: 7 },
      { cinema_id: 1, date: "2026-10-29", number_of_days: 7 },
      ...["25", "26", "27", "28"].map((d) => ({
        cinema_id: 1,
        date: `2026-10-${d}`,
        number_of_days: 1,
      })),
    ]);
    expect(raw.showtimes["1"]).toHaveLength(6);
  });
});

describe("emptyDaysBefore", () => {
  const answer = (...dates: string[]) => ({ data: dates.map((d) => ({ business_date: d })) });
  it.each([
    ["no gaps", [answer("2026-10-22", "2026-10-23")], []],
    ["a gap before a later day", [answer("2026-10-22"), answer("2026-10-24")], ["2026-10-23"]],
    ["nothing after the last day", [answer("2026-10-22")], []],
    ["no shows at all", [answer()], []],
    ["a broken answer", [{ resultCode: 1 }], []],
  ])("%s", (_, answers, gaps) => {
    expect(emptyDaysBefore(answers, "2026-10-22", 7)).toEqual(gaps);
  });
});
