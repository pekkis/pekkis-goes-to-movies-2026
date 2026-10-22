import { describe, expect, it } from "vitest";
import { createApi } from "../../src/lib/api.ts";
import { KIND_DAYS, loadKindsPage, parseKindsParams } from "../../src/lib/kinds.ts";
import { fakeFetch, screening } from "../fixtures.ts";

const TODAY = "2026-10-22";
const q = (query: string) => new URLSearchParams(query);
const NEULEKINO = {
  id: "neulekino",
  name: "Neulekino",
  kind: "strand",
  screenings: 2,
  firstDay: "2026-10-22",
};

describe("parseKindsParams", () => {
  it("keeps known tags and well-formed series ids, each once", () => {
    expect(
      parseKindsParams(
        q(
          "tunniste=baby&tunniste=baby&tunniste=knitting&sarja=neulekino&sarja=kinoregina/elia-suleiman&sarja=<x>",
        ),
      ),
    ).toEqual({ tags: ["baby"], series: ["neulekino", "kinoregina/elia-suleiman"] });
  });
});

describe("loadKindsPage", () => {
  it("lists the series and asks for no screenings until something is chosen", async () => {
    const fake = fakeFetch({ "/v1/series": [NEULEKINO] });
    const page = await loadKindsPage(createApi("http://api", fake.impl), q(""), TODAY);
    expect(page).toMatchObject({ state: "start", series: [NEULEKINO], days: [] });
    expect(fake.requests.map((u) => u.pathname)).toEqual(["/v1/series"]);
    expect(fake.requests[0]!.searchParams.get("to")).toBe("2026-11-18");
    expect(KIND_DAYS).toBe(28);
  });

  it("loads the chosen kinds' screenings for four weeks, by day", async () => {
    const fake = fakeFetch({
      "/v1/series": [NEULEKINO],
      "/v1/screenings": {
        date: TODAY,
        nextCursor: null,
        items: [
          screening({ id: "a", businessDate: "2026-10-22", series: ["Neulekino"] }),
          screening({ id: "b", businessDate: "2026-10-29", series: ["Neulekino"] }),
        ],
      },
    });
    const page = await loadKindsPage(
      createApi("http://api", fake.impl),
      q("sarja=neulekino&tunniste=baby"),
      TODAY,
    );
    expect(page.state).toBe("results");
    expect(page.days.map((d) => [d.date, d.screenings.map((s) => s.id)])).toEqual([
      ["2026-10-22", ["a"]],
      ["2026-10-29", ["b"]],
    ]);
    const asked = fake.requests.find((u) => u.pathname === "/v1/screenings")!;
    expect(Object.fromEntries(asked.searchParams)).toEqual({
      date: "2026-10-22",
      to: "2026-11-18",
      limit: "300",
      tags: "baby",
      series: "neulekino",
    });
    expect(page.more).toBe(false);
  });

  it("says when there are more screenings than it shows", async () => {
    const fake = fakeFetch({
      "/v1/series": [],
      "/v1/screenings": { date: TODAY, nextCursor: "next", items: [screening()] },
    });
    const page = await loadKindsPage(
      createApi("http://api", fake.impl),
      q("tunniste=domestic"),
      TODAY,
    );
    expect(page.more).toBe(true);
  });

  it("keeps a shared series checked although nothing of it is on now", async () => {
    const fake = fakeFetch({
      "/v1/series": [],
      "/v1/screenings": { date: TODAY, nextCursor: null, items: [] },
    });
    const page = await loadKindsPage(
      createApi("http://api", fake.impl),
      q("sarja=neulekino"),
      TODAY,
    );
    expect(page.series).toEqual([expect.objectContaining({ id: "neulekino", screenings: 0 })]);
    expect(page.days).toEqual([]);
  });
});
