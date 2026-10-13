import { join } from "node:path";
import type { Env } from "../lib/env.ts";
import { createHttpClient } from "../lib/http.ts";
import { helsinkiToday } from "@pgtm/model/time";
import { restrictToVenues, type Adapter } from "./adapter.ts";
import { fetchMyCloudCinema } from "./mycloudcinema/fetch.ts";
import { parseMyCloudCinema } from "./mycloudcinema/parse.ts";
import { MYCLOUDCINEMA_SITES, type MyCloudCinemaSite } from "./mycloudcinema/sites.ts";
import { fetchGilda } from "./gilda/fetch.ts";
import { parseGilda } from "./gilda/parse.ts";
import { GILDA_SITES, type GildaSite } from "./gilda/sites.ts";
import { fetchTmb } from "./tmb/fetch.ts";
import { parseTmb } from "./tmb/parse.ts";
import { TMB_SITES, type TmbSite } from "./tmb/sites.ts";
import { fetchFinnkino } from "./finnkino/fetch.ts";
import { parseFinnkino } from "./finnkino/parse.ts";
import { getToken } from "./finnkino/token.ts";
import { fetchEtiketti } from "./etiketti/fetch.ts";
import { parseEtiketti } from "./etiketti/parse.ts";
import { ETIKETTI_SITES, type EtikettiSite } from "./etiketti/sites.ts";
import { fetchJohku } from "./johku/fetch.ts";
import { parseJohku } from "./johku/parse.ts";
import { JOHKU_SITES, type JohkuSite } from "./johku/sites.ts";
import { fetchKinola } from "./kinola/fetch.ts";
import { parseKinola } from "./kinola/parse.ts";
import { KINOLA_SITES, type KinolaSite } from "./kinola/sites.ts";
import { fetchNexxo } from "./nexxo/fetch.ts";
import { parseNexxo } from "./nexxo/parse.ts";
import { NEXXO_SITES, type NexxoSite } from "./nexxo/sites.ts";

export type { Adapter, PullContext, PullOptions } from "./adapter.ts";

const contact = (env: Env) => (env.CONTACT ? { contact: env.CONTACT } : {});

/** Limits a multi-site config to the given venue slugs (`--venue`). */
const onlyVenues = <S extends { provider: string; venues: { slug: string }[] }>(
  site: S,
  slugs: string[] | undefined,
): S => {
  if (!slugs) {
    return site;
  }
  const venues = site.venues.filter((v) => slugs.includes(v.slug));
  if (venues.length === 0) {
    throw new Error(
      `No venues ${slugs.join(", ")} in ${site.provider} (has ${site.venues.map((v) => v.slug).join(", ")})`,
    );
  }
  return { ...site, venues };
};

const nexxoAdapter = (site: NexxoSite): Adapter => ({
  id: site.provider,
  platform: "nexxo",
  pull: async ({ env }, { from, days, venues }) => {
    // Small WordPress hosts answer 403 when hit faster than this.
    const http = createHttpClient({ intervalMs: 2500, ...contact(env) });
    // Fetch only the selected venues' locations, but parse with the full config so rooms
    // of unselected venues sharing a location are not reported as unclaimed.
    const raw = await fetchNexxo(http, onlyVenues(site, venues), {
      from,
      days,
      today: helsinkiToday(),
    });
    return { raw, batch: restrictToVenues(parseNexxo(raw, site), venues) };
  },
});

const etikettiAdapter = (site: EtikettiSite): Adapter => ({
  id: site.provider,
  platform: "etiketti",
  pull: async ({ env }, { from, days, venues }) => {
    // Small sites: one page at a time, 1.5 s apart.
    const http = createHttpClient({ intervalMs: 1500, ...contact(env) });
    onlyVenues(site, venues); // validates --venue slugs before any request
    const raw = await fetchEtiketti(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseEtiketti(raw, site), venues) };
  },
});

const kinolaAdapter = (site: KinolaSite): Adapter => ({
  id: site.provider,
  platform: "kinola",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient({ intervalMs: 1500, ...contact(env) });
    onlyVenues(site, venues);
    const raw = await fetchKinola(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseKinola(raw, site), venues) };
  },
});

const johkuAdapter = (site: JohkuSite): Adapter => ({
  id: site.provider,
  platform: "johku",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient({ intervalMs: 2000, ...contact(env) });
    onlyVenues(site, venues);
    const raw = await fetchJohku(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseJohku(raw, site), venues) };
  },
});

/** MyCloudCinema: venues come from the API, so `--venue` takes cinema ids. */
const myCloudCinemaAdapter = (site: MyCloudCinemaSite): Adapter => ({
  id: site.provider,
  platform: "mycloudcinema",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    const raw = await fetchMyCloudCinema(http, site, {
      from,
      days,
      ...(venues && { cinemaIds: venues.map(Number) }),
    });
    return { raw, batch: restrictToVenues(parseMyCloudCinema(raw, site), venues) };
  },
});

/** Gilda: MyCloudCinema data through the cinema's own WordPress facade. */
const gildaAdapter = (site: GildaSite): Adapter => ({
  id: site.provider,
  platform: "mycloudcinema",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchGilda(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseGilda(raw, site), venues) };
  },
});

/** TMB Cinema: one list page per site. */
const tmbAdapter = (site: TmbSite): Adapter => ({
  id: site.provider,
  platform: "tmb",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchTmb(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseTmb(raw, site), venues) };
  },
});

export const ADAPTERS: Adapter[] = [
  ...MYCLOUDCINEMA_SITES.map(myCloudCinemaAdapter),
  ...GILDA_SITES.map(gildaAdapter),
  ...TMB_SITES.map(tmbAdapter),
  {
    id: "finnkino",
    platform: "vista-ocapi",
    pull: async ({ env, out }, { from, days, venues }) => {
      const token = await getToken({ cachePath: join(out, "cache", "finnkino-token.json") });
      const http = createHttpClient({
        headers: { authorization: `Bearer ${token}` },
        ...contact(env),
      });
      const raw = await fetchFinnkino(http, { from, days, ...(venues && { siteIds: venues }) });
      return { raw, batch: restrictToVenues(parseFinnkino(raw), venues) };
    },
  },
  ...NEXXO_SITES.map(nexxoAdapter),
  ...ETIKETTI_SITES.map(etikettiAdapter),
  ...KINOLA_SITES.map(kinolaAdapter),
  ...JOHKU_SITES.map(johkuAdapter),
];

/** Resolves `--provider` values: an adapter id (`kinoaurora`) or a platform (`nexxo`). */
export const selectAdapters = (names: string[] | undefined): Adapter[] | undefined => {
  if (!names) {
    return ADAPTERS;
  }
  const selected = ADAPTERS.filter((a) => names.includes(a.id) || names.includes(a.platform));
  const known = new Set(ADAPTERS.flatMap((a) => [a.id, a.platform]));
  return names.every((n) => known.has(n)) ? selected : undefined;
};
