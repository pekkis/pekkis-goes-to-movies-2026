import type { Screening, Venue } from "../src/lib/api.ts";

const provider = { id: "testchain", name: "Test Chain", homepage: null, booking: "buy" };

export const venue = (over: Partial<Venue> = {}): Venue =>
  ({
    id: "testchain:venue:1",
    name: "Kino Testi",
    shortName: null,
    city: "Jyväskylä",
    address: null,
    postalCode: null,
    geo: { lat: 62.24, lon: 25.75 },
    url: null,
    provider,
    ...over,
  }) as Venue;

export const screening = (over: Partial<Screening> = {}): Screening => ({
  id: "testchain:show:1",
  startsAt: "2026-10-13T18:00:00+03:00",
  endsAt: null,
  businessDate: "2026-10-13",
  venue: { id: "testchain:venue:1", name: "Kino Testi", city: "Jyväskylä", geo: null },
  auditorium: "Sali 2",
  film: {
    id: "tmdb:1185806",
    kind: "film",
    isEvent: false,
    title: "Unohdettu saari",
    originalTitle: null,
    year: 2026,
    runtimeMinutes: 100,
    rating: "K-7",
    posterUrl: null,
    ratings: [],
  },
  projection: "digital",
  dimension: "2d",
  formats: [],
  audio: ["fi"],
  dubbed: true,
  subtitles: { kind: "none", languages: [] },
  tags: [],
  series: [],
  ageLimit: null,
  availability: "available",
  price: null,
  ticketUrl: "https://kino.example/liput/1",
  ...over,
});

/** A fetch that answers from a route table, recording each request; no network. */
export const fakeFetch = (routes: Record<string, unknown>) => {
  const requests: URL[] = [];
  const impl = (async (input: RequestInfo | URL) => {
    const url = new URL(input instanceof Request ? input.url : input);
    requests.push(url);
    const body = routes[url.pathname];
    return body === undefined
      ? new Response(JSON.stringify({ error: "not found" }), { status: 404 })
      : new Response(JSON.stringify(typeof body === "function" ? body(url) : body), {
          headers: { "content-type": "application/json" },
        });
  }) as typeof fetch;
  return { impl, requests };
};
