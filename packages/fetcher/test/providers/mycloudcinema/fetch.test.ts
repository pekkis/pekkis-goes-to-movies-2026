import { describe, expect, it, vi } from "vitest";
import type { HttpClient } from "../../../src/lib/http.ts";
import { fetchMyCloudCinema } from "../../../src/providers/mycloudcinema/fetch.ts";
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
});
