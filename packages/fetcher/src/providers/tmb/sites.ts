import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * TMB Cinema Oy: four cinemas, four sites on one template ("Mediapalvelu W3D"). Each site
 * serves one venue; `{base}/?lista=1` lists its whole programme, one row per screening.
 * They are four cinemas, not mirrors: the same film at the same minute has a different
 * booking id at each. Mapped by Leffavuoro (Shady-Dev/kino, scripts/providers/tmb.py,
 * AGPL-3.0); re-verified 2026-10-13.
 */
export const TmbSite = SiteBase.extend({
  /** The site root; the programme is `{base}/?lista=1`. */
  base: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type TmbSite = z.infer<typeof TmbSite>;

const V = "2026-10-13";

export const TMB_SITES: TmbSite[] = defineSites(TmbSite, [
  {
    provider: "kinotoijala",
    name: "Kino-Toijala",
    homepage: "https://toijalan-kino.info",
    base: "https://toijalan-kino.info",
    verifiedAt: V,
    titlePrefixes: { "Akaan elokuvajuhla 2026": { series: "Akaan elokuvajuhla" } },
    venues: [
      {
        slug: "toijala",
        name: "Kino-Toijala",
        city: "Akaa",
        address: "Pätsiniementie 9",
        postalCode: "37800",
        geo: { lat: 61.169169, lon: 23.861699 },
        geoSource: "osm:node/10656400773",
      },
    ],
  },
  {
    provider: "kinosampo",
    name: "Kino-Sampo",
    homepage: "https://kinosampo.info",
    base: "https://kinosampo.info",
    verifiedAt: V,
    venues: [
      {
        slug: "valkeakoski",
        name: "Kino-Sampo",
        city: "Valkeakoski",
        address: "Valtakatu 19",
        postalCode: "37600",
        geo: { lat: 61.267585, lon: 24.027222 },
        geoSource: "osm:node/5913894885",
      },
    ],
  },
  {
    provider: "kinomania",
    name: "KinoMania",
    homepage: "https://kino-mania.info",
    base: "https://kino-mania.info",
    verifiedAt: V,
    notes: "OSM node has no address; it is about 45 m from the Kauppakatu 5-7 address points.",
    venues: [
      {
        slug: "pieksamaki",
        name: "KinoMania",
        city: "Pieksämäki",
        address: "Kauppakatu 5",
        postalCode: "76100",
        geo: { lat: 62.300365, lon: 27.160519 },
        geoSource: "osm:node/2094955209",
      },
    ],
  },
  {
    provider: "kinoelo",
    name: "Elokuvateatteri Elo",
    homepage: "https://elokuvat-elo.info",
    base: "https://elokuvat-elo.info",
    verifiedAt: V,
    notes:
      "No coordinates yet: OSM has no cinema here and Nominatim knows Kauppakatu but not number 16.",
    venues: [
      {
        slug: "heinola",
        name: "Elokuvateatteri Elo",
        city: "Heinola",
        address: "Kauppakatu 16",
        postalCode: "18100",
      },
    ],
  },
]);
