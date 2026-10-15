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
import { fetchCinemahouse } from "./cinemahouse/fetch.ts";
import { parseCinemahouse } from "./cinemahouse/parse.ts";
import { CINEMAHOUSE_SITES, type CinemahouseSite } from "./cinemahouse/sites.ts";
import { fetchVista } from "./vista/fetch.ts";
import { parseVista } from "./vista/parse.ts";
import { VISTA_SITES, type VistaSite } from "./vista/sites.ts";
import { fetchTapiola } from "./tapiola/fetch.ts";
import { parseTapiola } from "./tapiola/parse.ts";
import { TAPIOLA_SITES, type TapiolaSite } from "./tapiola/sites.ts";
import { fetchKuvakukko } from "./kuvakukko/fetch.ts";
import { parseKuvakukko } from "./kuvakukko/parse.ts";
import { KUVAKUKKO_SITES, type KuvakukkoSite } from "./kuvakukko/sites.ts";
import { fetchIsohannu } from "./isohannu/fetch.ts";
import { parseIsohannu } from "./isohannu/parse.ts";
import { ISOHANNU_SITES, type IsohannuSite } from "./isohannu/sites.ts";
import { fetchTribe } from "./tribe/fetch.ts";
import { parseTribe } from "./tribe/parse.ts";
import { TRIBE_SITES, type TribeSite } from "./tribe/sites.ts";
import { fetchEngel } from "./engel/fetch.ts";
import { parseEngel } from "./engel/parse.ts";
import { ENGEL_SITES, type EngelSite } from "./engel/sites.ts";
import { fetchLinkedEvents } from "./linkedevents/fetch.ts";
import { parseLinkedEvents } from "./linkedevents/parse.ts";
import { LINKED_EVENTS_SITES, type LinkedEventsSite } from "./linkedevents/sites.ts";
import { fetchJulia } from "./julia/fetch.ts";
import { parseJulia } from "./julia/parse.ts";
import { JULIA_SITES, type JuliaSite } from "./julia/sites.ts";
import { fetchVaakuna } from "./vaakuna/fetch.ts";
import { parseVaakuna } from "./vaakuna/parse.ts";
import { VAAKUNA_SITES, type VaakunaSite } from "./vaakuna/sites.ts";
import { fetchKirkkonummi } from "./kirkkonummi/fetch.ts";
import { parseKirkkonummi } from "./kirkkonummi/parse.ts";
import { KIRKKONUMMI_SITES, type KirkkonummiSite } from "./kirkkonummi/sites.ts";
import { fetchBioSavoy } from "./biosavoy/fetch.ts";
import { parseBioSavoy } from "./biosavoy/parse.ts";
import { BIOSAVOY_SITES, type BioSavoySite } from "./biosavoy/sites.ts";
import { fetchKinoAkseli } from "./kinoakseli/fetch.ts";
import { parseKinoAkseli } from "./kinoakseli/parse.ts";
import { KINOAKSELI_SITES, type KinoAkseliSite } from "./kinoakseli/sites.ts";
import { fetchHamina } from "./hamina/fetch.ts";
import { parseHamina } from "./hamina/parse.ts";
import { HAMINA_SITES, type HaminaSite } from "./hamina/sites.ts";
import { fetchElavienkuvien } from "./elavienkuvien/fetch.ts";
import { parseElavienkuvien } from "./elavienkuvien/parse.ts";
import { ELAVIENKUVIEN_SITES, type ElavienkuvienSite } from "./elavienkuvien/sites.ts";
import { fetchKuusamotalo } from "./kuusamotalo/fetch.ts";
import { parseKuusamotalo } from "./kuusamotalo/parse.ts";
import { KUUSAMOTALO_SITES, type KuusamotaloSite } from "./kuusamotalo/sites.ts";
import { fetchLieksa } from "./lieksa/fetch.ts";
import { parseLieksa } from "./lieksa/parse.ts";
import { LIEKSA_SITES, type LieksaSite } from "./lieksa/sites.ts";
import { fetchMarita } from "./marita/fetch.ts";
import { parseMarita } from "./marita/parse.ts";
import { MARITA_SITES, type MaritaSite } from "./marita/sites.ts";
import { fetchKinoHuovi } from "./kinohuovi/fetch.ts";
import { parseKinoHuovi } from "./kinohuovi/parse.ts";
import { KINOHUOVI_SITES, type KinoHuoviSite } from "./kinohuovi/sites.ts";
import { fetchMatinTupa } from "./matintupa/fetch.ts";
import { parseMatinTupa } from "./matintupa/parse.ts";
import { MATINTUPA_SITES, type MatinTupaSite } from "./matintupa/sites.ts";
import { fetchMyCalendar } from "./mycalendar/fetch.ts";
import { parseMyCalendar } from "./mycalendar/parse.ts";
import { MYCALENDAR_SITES, type MyCalendarSite } from "./mycalendar/sites.ts";
import { fetchNavetta } from "./navetta/fetch.ts";
import { parseNavetta } from "./navetta/parse.ts";
import { NAVETTA_SITES, type NavettaSite } from "./navetta/sites.ts";
import { fetchLocalhub } from "./localhub/fetch.ts";
import { parseLocalhub } from "./localhub/parse.ts";
import { LOCALHUB_SITES, type LocalhubSite } from "./localhub/sites.ts";
import { fetchBioPallas } from "./biopallas/fetch.ts";
import { parseBioPallas } from "./biopallas/parse.ts";
import { BIOPALLAS_SITES, type BioPallasSite } from "./biopallas/sites.ts";
import { fetchAlatalo } from "./alatalo/fetch.ts";
import { parseAlatalo } from "./alatalo/parse.ts";
import { ALATALO_SITES, type AlataloSite } from "./alatalo/sites.ts";
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

/** The cinema-reservations WordPress plugin: one front page per site. */
const cinemahouseAdapter = (site: CinemahouseSite): Adapter => ({
  id: site.provider,
  platform: "cinema-reservations",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchCinemahouse(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseCinemahouse(raw, site), venues) };
  },
});

/** Vista's open public web services: one GET per area. */
const vistaAdapter = (site: VistaSite): Adapter => ({
  id: site.provider,
  platform: "vista-public",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchVista(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseVista(raw, site), venues) };
  },
});

/** Kino Tapiola's own theme: the programme list, then one run page per title. */
const tapiolaAdapter = (site: TapiolaSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient({ intervalMs: 1000, ...contact(env) });
    onlyVenues(site, venues);
    const raw = await fetchTapiola(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseTapiola(raw, site), venues) };
  },
});

/** Kuvakukko and Kino Manttu: one shared programme page. */
const kuvakukkoAdapter = (site: KuvakukkoSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient({ intervalMs: 1500, ...contact(env) });
    onlyVenues(site, venues);
    const raw = await fetchKuvakukko(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseKuvakukko(raw, site), venues) };
  },
});

/** Iso-Hannu's own site: the front page's show table, then one page per film. */
const isohannuAdapter = (site: IsohannuSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient({ intervalMs: 1000, ...contact(env) });
    onlyVenues(site, venues);
    const raw = await fetchIsohannu(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseIsohannu(raw, site), venues) };
  },
});

/** The Events Calendar (WordPress): the film category's events over REST. */
const tribeAdapter = (site: TribeSite): Adapter => ({
  id: site.provider,
  platform: "events-calendar",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchTribe(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseTribe(raw, site), venues) };
  },
});

/** Kino Engel's front page; from a home connection only (it challenges datacenters). */
const engelAdapter = (site: EngelSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient({ intervalMs: 1000, ...contact(env) });
    onlyVenues(site, venues);
    const raw = await fetchEngel(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseEngel(raw, site), venues) };
  },
});

/** The City of Helsinki's Linked Events: a culture house's labelled screenings. */
const linkedEventsAdapter = (site: LinkedEventsSite): Adapter => ({
  id: site.provider,
  platform: "linked-events",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchLinkedEvents(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseLinkedEvents(raw, site), venues) };
  },
});

/** Elokuvateatteri Julia's programme page. */
const juliaAdapter = (site: JuliaSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchJulia(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseJulia(raw, site), venues) };
  },
});

/** Kino Vaakuna's front page. */
const vaakunaAdapter = (site: VaakunaSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchVaakuna(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseVaakuna(raw, site), venues) };
  },
});

/** Kino Kirkkonummi's one page. */
const kirkkonummiAdapter = (site: KirkkonummiSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchKirkkonummi(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseKirkkonummi(raw, site), venues) };
  },
});

/** Bio Savoy's front page (HTTP only). */
const bioSavoyAdapter = (site: BioSavoySite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchBioSavoy(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseBioSavoy(raw, site), venues) };
  },
});

/** Kino Akseli's front page; from a home connection only (it challenges datacenters). */
const kinoAkseliAdapter = (site: KinoAkseliSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchKinoAkseli(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseKinoAkseli(raw, site), venues) };
  },
});

/** Kino Hamina's page on the town's site. */
const haminaAdapter = (site: HaminaSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchHamina(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseHamina(raw, site), venues) };
  },
});

/** Elävienkuvien teatteri: the listing, then each film's page. */
const elavienkuvienAdapter = (site: ElavienkuvienSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient({ intervalMs: 1000, ...contact(env) });
    onlyVenues(site, venues);
    const raw = await fetchElavienkuvien(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseElavienkuvien(raw, site), venues) };
  },
});

/** Kino Kuusamotalo: WordPress posts, one per film. */
const kuusamotaloAdapter = (site: KuusamotaloSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchKuusamotalo(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseKuusamotalo(raw, site), venues) };
  },
});

/** Lieksan Kino's hand-written page. */
const lieksaAdapter = (site: LieksaSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchLieksa(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseLieksa(raw, site), venues) };
  },
});

/** Elokuvateatteri Marita's front page. */
const maritaAdapter = (site: MaritaSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchMarita(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseMarita(raw, site), venues) };
  },
});

/** Kino-Huovi's Duda front page. */
const kinoHuoviAdapter = (site: KinoHuoviSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchKinoHuovi(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseKinoHuovi(raw, site), venues) };
  },
});

/** Elokuvateatteri Matin-Tupa's programme page. */
const matinTupaAdapter = (site: MatinTupaSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchMatinTupa(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseMatinTupa(raw, site), venues) };
  },
});

/** The My Calendar WordPress plugin: the film category's occurrences over REST. */
const myCalendarAdapter = (site: MyCalendarSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchMyCalendar(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseMyCalendar(raw, site), venues) };
  },
});

/** Navettakino's front page. */
const navettaAdapter = (site: NavettaSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchNavetta(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseNavetta(raw, site), venues) };
  },
});

/** A town's Localhub event calendar: the cinema's hashtag, one page per screening. */
const localhubAdapter = (site: LocalhubSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchLocalhub(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseLocalhub(raw, site), venues) };
  },
});

/** Bio Pallas's Wix front page. */
const bioPallasAdapter = (site: BioPallasSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchBioPallas(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseBioPallas(raw, site), venues) };
  },
});

/** Freehand programmes by one author: Alatalo's touring cinema and Huvimylly. */
const alataloAdapter = (site: AlataloSite): Adapter => ({
  id: site.provider,
  platform: "custom",
  pull: async ({ env }, { from, days, venues }) => {
    const http = createHttpClient(contact(env));
    onlyVenues(site, venues);
    const raw = await fetchAlatalo(http, site, { from, days });
    return { raw, batch: restrictToVenues(parseAlatalo(raw, site), venues) };
  },
});

export const ADAPTERS: Adapter[] = [
  ...MYCLOUDCINEMA_SITES.map(myCloudCinemaAdapter),
  ...GILDA_SITES.map(gildaAdapter),
  ...TMB_SITES.map(tmbAdapter),
  ...CINEMAHOUSE_SITES.map(cinemahouseAdapter),
  ...VISTA_SITES.map(vistaAdapter),
  ...TAPIOLA_SITES.map(tapiolaAdapter),
  ...KUVAKUKKO_SITES.map(kuvakukkoAdapter),
  ...ISOHANNU_SITES.map(isohannuAdapter),
  ...TRIBE_SITES.map(tribeAdapter),
  ...ENGEL_SITES.map(engelAdapter),
  ...LINKED_EVENTS_SITES.map(linkedEventsAdapter),
  ...JULIA_SITES.map(juliaAdapter),
  ...VAAKUNA_SITES.map(vaakunaAdapter),
  ...KIRKKONUMMI_SITES.map(kirkkonummiAdapter),
  ...BIOSAVOY_SITES.map(bioSavoyAdapter),
  ...KINOAKSELI_SITES.map(kinoAkseliAdapter),
  ...HAMINA_SITES.map(haminaAdapter),
  ...ELAVIENKUVIEN_SITES.map(elavienkuvienAdapter),
  ...KUUSAMOTALO_SITES.map(kuusamotaloAdapter),
  ...LIEKSA_SITES.map(lieksaAdapter),
  ...MARITA_SITES.map(maritaAdapter),
  ...KINOHUOVI_SITES.map(kinoHuoviAdapter),
  ...MATINTUPA_SITES.map(matinTupaAdapter),
  ...MYCALENDAR_SITES.map(myCalendarAdapter),
  ...NAVETTA_SITES.map(navettaAdapter),
  ...LOCALHUB_SITES.map(localhubAdapter),
  ...BIOPALLAS_SITES.map(bioPallasAdapter),
  ...ALATALO_SITES.map(alataloAdapter),
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
