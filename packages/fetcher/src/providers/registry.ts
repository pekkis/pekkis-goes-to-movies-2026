import { join } from "node:path";
import type { Env } from "../lib/env.ts";
import { createHttpClient } from "../lib/http.ts";
import type { ProviderBatch } from "@pgtm/model";
import { fetchBiorex } from "./biorex/fetch.ts";
import { parseBiorex } from "./biorex/parse.ts";
import { fetchFinnkino } from "./finnkino/fetch.ts";
import { parseFinnkino } from "./finnkino/parse.ts";
import { getToken } from "./finnkino/token.ts";

export type PullContext = { env: Env; out: string };

export type PullOptions = {
  from: string;
  days: number;
  /** Source venue ids to limit to (default: all). */
  venues?: string[];
};

export type Adapter = {
  id: string;
  /** Fetches (I/O) and parses (pure); returns the raw snapshot for archiving too. */
  pull: (
    ctx: PullContext,
    options: PullOptions,
  ) => Promise<{ raw: { fetchedAt: string }; batch: ProviderBatch }>;
};

const contact = (env: Env) => (env.CONTACT ? { contact: env.CONTACT } : {});

export const ADAPTERS: Adapter[] = [
  {
    id: "biorex",
    pull: async ({ env }, { from, days, venues }) => {
      const http = createHttpClient(contact(env));
      const raw = await fetchBiorex(http, {
        from,
        days,
        ...(venues && { cinemaIds: venues.map(Number) }),
      });
      return { raw, batch: parseBiorex(raw) };
    },
  },
  {
    id: "finnkino",
    pull: async ({ env, out }, { from, days, venues }) => {
      const token = await getToken({ cachePath: join(out, "cache", "finnkino-token.json") });
      const http = createHttpClient({
        headers: { authorization: `Bearer ${token}` },
        ...contact(env),
      });
      const raw = await fetchFinnkino(http, { from, days, ...(venues && { siteIds: venues }) });
      return { raw, batch: parseFinnkino(raw) };
    },
  },
];
