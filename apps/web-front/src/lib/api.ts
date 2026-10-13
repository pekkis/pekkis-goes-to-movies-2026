import type { AppType } from "@pgtm/backend";
import { hc, type InferResponseType } from "hono/client";

/** Typed client for our API. Tests pass a fake `fetch`, so they never touch the network. */
export const createApi = (baseUrl: string, fetchImpl: typeof fetch = fetch) =>
  hc<AppType>(baseUrl, { fetch: fetchImpl });

export type Api = ReturnType<typeof createApi>;
export type Venue = InferResponseType<Api["v1"]["venues"]["$get"], 200>[number];
export type Screening = InferResponseType<Api["v1"]["screenings"]["$get"], 200>["items"][number];

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, path: string) {
    super(`API ${path} answered ${status}`);
    this.status = status;
  }
}

export const listVenues = async (api: Api, city?: string): Promise<Venue[]> => {
  const res = await api.v1.venues.$get({ query: city ? { city } : {} });
  if (!res.ok) throw new ApiError(res.status, "/v1/venues");
  return res.json();
};

/** One day's screenings in a city, following `nextCursor` through every page. */
export const cityScreenings = async (
  api: Api,
  query: { city: string; date?: string | undefined },
): Promise<{ date: string; items: Screening[] }> => {
  const items: Screening[] = [];
  let cursor: string | undefined;
  let date = query.date ?? "";
  do {
    const res = await api.v1.screenings.$get({
      query: {
        city: query.city,
        ...(query.date && { date: query.date }),
        ...(cursor && { cursor }),
      },
    });
    if (!res.ok) throw new ApiError(res.status, "/v1/screenings");
    const page = await res.json();
    items.push(...page.items);
    date = page.date;
    cursor = page.nextCursor ?? undefined;
  } while (cursor);
  return { date, items };
};
