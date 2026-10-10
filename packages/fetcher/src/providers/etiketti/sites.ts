import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * eTiketti sites: small cinemas whose own sites are server-rendered by the eTiketti
 * platform. There is no public API (etiketti.app's API is behind Cloudflare), so the
 * adapter reads the programme listing and each film page as HTML.
 *
 * Adding a cinema = adding an entry here. Check, as a visitor would:
 * - `{base}/elokuvat/ohjelmistossa` lists the films ("Powered by eTiketti" in the footer),
 * - a film page's screening rows print a place line ("STAR | SALI 4"): its venue part goes
 *   into `place`. `pnpm pull` warns `unclaimed-place` for a place no venue claims.
 *
 * Origin: Leffavuoro (vendor/leffavuoro/scripts/providers/etiketti.py, AGPL-3.0),
 * re-verified 2026-10-10 against the live sites.
 */

/** Platform defaults for screening tags (`<span class="tag">`); sites may override. */
export const DEFAULT_TAGS: Record<string, LabelRule> = {
  "Ensi-ilta": { tags: ["premiere"] },
  "Viimeinen näytös": { tags: ["last-screening"] },
  Seniorinäytös: { tags: ["senior"] },
  Seniorikino: { tags: ["senior"] },
  Vauvakino: { tags: ["baby"] },
  Lastenkino: { tags: ["kids"] },
  "Edullinen päivänäytös": { tags: ["discount"] },
  Anniskelunäytös: { licensed: true },
  Erikoisnäytös: {},
};

export const EtikettiVenue = SiteVenue.extend({
  /**
   * The venue's part of the place line, e.g. "TRIO 123" in "TRIO 123 | VIP-SALI" or
   * "TAPIO" in "JOENSUU | TAPIO | TAPIO 3" (case-insensitive, whole part). The part after
   * it is the room. Leave out for the one venue whose rows print no place line.
   */
  place: z.string().min(1).optional(),
});
export type EtikettiVenue = z.infer<typeof EtikettiVenue>;

export const EtikettiSite = SiteBase.extend({
  /** Where the eTiketti pages live, if not the homepage (Star: lippu.…). */
  base: z.url().optional(),
  venues: z.array(EtikettiVenue).min(1),
  /** "Ei tekstitystä" is printed even when there are subtitles: treat as unknown. */
  noSubtitlesUnreliable: z.boolean().optional(),
  /** Site-specific tag rules, merged over DEFAULT_TAGS. */
  tags: z.record(z.string(), LabelRule).optional(),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type EtikettiSite = z.infer<typeof EtikettiSite>;

export const baseOf = (site: EtikettiSite): string => site.base ?? site.homepage;

const V = "2026-10-10";

export const ETIKETTI_SITES: EtikettiSite[] = defineSites(EtikettiSite, [
  {
    provider: "kotkanleffat",
    name: "Kotkan Leffat",
    homepage: "https://kotkanleffat.fi",
    verifiedAt: V,
    venues: [
      {
        slug: "kinopalatsi",
        geo: { lat: 60.464416, lon: 26.940987 },
        geoSource: "osm:node/1676791935",
        name: "Kinopalatsi",
        city: "Kotka",
        place: "KINOPALATSI",
      },
      {
        slug: "trio-123",
        address: "Kotkankatu 9",
        postalCode: "48100",
        geo: { lat: 60.463428, lon: 26.936563 },
        geoSource: "nominatim",
        name: "Trio 123",
        city: "Kotka",
        place: "TRIO 123",
      },
    ],
    notes: 'Leffavuoro saw no place line for Kinopalatsi; on 2026-10-10 it prints "KINOPALATSI".',
  },
  {
    provider: "biorexkokkola",
    name: "Bio Rex Kokkola",
    homepage: "https://www.biorex.org",
    verifiedAt: V,
    venues: [
      {
        slug: "kokkola",
        address: "Pitkänsillankatu 33",
        postalCode: "67100",
        geo: { lat: 63.837357, lon: 23.133527 },
        geoSource: "osm:node/207728869",
        name: "Bio Rex",
        city: "Kokkola",
        place: "BIO 1&2 REX",
      },
    ],
    notes: "Independent; not the BioRex chain.",
  },
  {
    provider: "savonkinot",
    name: "Savon Kinot",
    homepage: "https://www.savonkinot.fi",
    verifiedAt: V,
    notes: 'Place lines are "CITY | CINEMA | ROOM"; a room repeating the cinema means no room.',
    venues: [
      {
        slug: "tapio",
        address: "Kauppakatu 27",
        postalCode: "80100",
        geo: { lat: 62.602556, lon: 29.762217 },
        geoSource: "osm:node/256080035",
        name: "Tapio",
        city: "Joensuu",
        place: "TAPIO",
      },
      {
        slug: "killa",
        address: "Punkaharjuntie 3",
        postalCode: "57130",
        geo: { lat: 61.866741, lon: 28.898677 },
        geoSource: "osm:node/1150666518",
        name: "Killa",
        city: "Savonlinna",
        place: "KILLA",
      },
      {
        slug: "kuvalinna",
        address: "Olavinkatu 13",
        postalCode: "57130",
        geo: { lat: 61.866907, lon: 28.896621 },
        geoSource: "osm:node/7276302404",
        name: "Kuvalinna",
        city: "Savonlinna",
        place: "KUVALINNA",
      },
      {
        slug: "kuvalipas",
        name: "Kuvalipas",
        city: "Iisalmi",
        place: "KUVALIPAS",
        address: "Pohjolankatu 6",
        postalCode: "74100",
        geo: { lat: 63.558534, lon: 27.191831 },
        geoSource: "nominatim",
      },
      {
        slug: "maxim",
        address: "Kauppakatu 27",
        postalCode: "78200",
        geo: { lat: 62.314913, lon: 27.876064 },
        geoSource: "osm:node/12304430425",
        name: "Maxim",
        city: "Varkaus",
        place: "MAXIM",
      },
      {
        slug: "kinohovi",
        address: "Hovintie 6",
        geo: { lat: 62.100679, lon: 30.13436 },
        geoSource: "osm:way/340118158",
        name: "Kino-Hovi",
        city: "Kitee",
        place: "KINO-HOVI",
      },
    ],
  },
  {
    provider: "kinopirtti",
    name: "Kinopirtti",
    homepage: "https://kinopirtti.fi",
    verifiedAt: V,
    venues: [
      {
        slug: "kemi",
        address: "Valtakatu 12",
        postalCode: "94100",
        geo: { lat: 65.737297, lon: 24.566197 },
        geoSource: "nominatim",
        name: "Kinopirtti",
        city: "Kemi",
        place: "KINOPIRTTI",
      },
    ],
  },
  {
    provider: "leffabuumi",
    name: "Leffabuumi",
    homepage: "https://leffabuumi.fi",
    verifiedAt: V,
    venues: [
      {
        slug: "kinolinna",
        geo: { lat: 61.69131, lon: 27.27261 },
        geoSource: "osm:node/1100527721",
        name: "Kinolinna",
        city: "Mikkeli",
        place: "KINOLINNA",
      },
      {
        slug: "ritz",
        address: "Mikonkatu",
        postalCode: "50100",
        geo: { lat: 61.686786, lon: 27.26905 },
        geoSource: "osm:node/600298243",
        name: "Ritz",
        city: "Mikkeli",
        place: "RITZ",
      },
      {
        slug: "kino-saimaa",
        address: "Kirkkotie 3",
        postalCode: "52200",
        geo: { lat: 61.526302, lon: 28.174933 },
        geoSource: "osm:node/8734612902",
        name: "Kino Saimaa",
        city: "Puumala",
        place: "KINO SAIMAA",
      },
    ],
  },
  {
    provider: "studio123jarvenpaa",
    name: "Studio 123 Järvenpää",
    homepage: "https://studiot123.com",
    verifiedAt: V,
    venues: [
      {
        slug: "jarvenpaa",
        address: "Helsingintie 12",
        postalCode: "04400",
        geo: { lat: 60.471044, lon: 25.088721 },
        geoSource: "osm:node/298100934",
        name: "Studio 123",
        city: "Järvenpää",
        place: "STUDIO 123",
      },
    ],
  },
  {
    provider: "studio123kouvola",
    name: "Studio 123 Kouvola",
    homepage: "https://studio123.fi",
    verifiedAt: V,
    venues: [
      {
        slug: "kuusankoski",
        address: "Kymenlaaksonkatu",
        postalCode: "45700",
        geo: { lat: 60.906534, lon: 26.627534 },
        geoSource: "osm:node/473696813",
        name: "Studio 123",
        city: "Kouvola",
        place: "STUDIO 123",
      },
    ],
  },
  {
    provider: "ihmekompleksi",
    name: "Ihme Kompleksi",
    homepage: "https://ihmekompleksi.fi",
    verifiedAt: V,
    venues: [
      {
        slug: "kankaanpaa",
        name: "Ihme Kompleksi",
        city: "Kankaanpää",
        place: "IHME KOMPLEKSI",
        address: "Keskuskatu 28",
        postalCode: "38700",
        geo: { lat: 61.807582, lon: 22.385363 },
        geoSource: "nominatim",
      },
    ],
  },
  {
    provider: "kino123",
    name: "Kino 123",
    homepage: "https://kino123.fi",
    verifiedAt: V,
    venues: [
      {
        slug: "kouvola",
        address: "Tervasharjunkatu",
        postalCode: "45720",
        geo: { lat: 60.876964, lon: 26.650293 },
        geoSource: "osm:way/206082598",
        name: "Kino 123",
        city: "Kouvola",
        place: "KINO 123",
      },
    ],
  },
  {
    provider: "kinotar",
    name: "Kinotar 123",
    homepage: "https://jamsankinotar.fi",
    verifiedAt: V,
    venues: [
      {
        slug: "jamsa",
        address: "Pääskyläntie 25",
        postalCode: "42100",
        geo: { lat: 61.873137, lon: 25.173818 },
        geoSource: "nominatim",
        name: "Kinotar 123",
        city: "Jämsä",
        place: "KINOTAR 123",
      },
    ],
  },
  {
    provider: "kinojuha",
    name: "Kino Juha",
    homepage: "https://kinojuha.fi",
    verifiedAt: V,
    notes: "Two places on one listing: the main hall and the VIP-Sali, each its own venue.",
    venues: [
      {
        slug: "kino-juha",
        address: "Keskustie 7",
        postalCode: "01900",
        geo: { lat: 60.461579, lon: 24.806087 },
        geoSource: "osm:way/305580053",
        name: "Kino Juha",
        city: "Nurmijärvi",
        place: "KINO JUHA",
      },
      {
        slug: "vip-sali",
        address: "Keskustie 7",
        postalCode: "01900",
        geo: { lat: 60.462821, lon: 24.804487 },
        geoSource: "osm:node/13684947367",
        name: "Kino Juha VIP-Sali",
        city: "Nurmijärvi",
        place: "VIP-SALI",
      },
    ],
  },
  {
    provider: "biogrand",
    name: "Bio Grand",
    homepage: "https://biogrand.fi",
    verifiedAt: V,
    venues: [
      {
        slug: "vantaa",
        address: "Kielotie 7",
        postalCode: "01300",
        geo: { lat: 60.289696, lon: 25.036234 },
        geoSource: "osm:node/477201172",
        name: "Bio Grand",
        city: "Vantaa",
        place: "BIO GRAND",
      },
    ],
  },
  {
    provider: "biovuoksi",
    name: "Bio Vuoksi",
    homepage: "https://biovuoksi.fi",
    verifiedAt: V,
    venues: [
      {
        slug: "imatra",
        address: "Torikatu 13",
        geo: { lat: 61.225873, lon: 28.833082 },
        geoSource: "osm:node/3790585786",
        name: "Bio Vuoksi",
        city: "Imatra",
        place: "BIO VUOKSI",
      },
    ],
  },
  {
    provider: "kinoiiris",
    name: "Kino Iiris",
    homepage: "https://kinoiiris.com",
    verifiedAt: V,
    venues: [
      {
        slug: "lahti",
        address: "Saimaankatu 12",
        postalCode: "15140",
        geo: { lat: 60.982536, lon: 25.666838 },
        geoSource: "osm:node/5261729786",
        name: "Kino Iiris",
        city: "Lahti",
        place: "KINO IIRIS",
      },
    ],
  },
  {
    provider: "joutsankino",
    name: "Joutsan Kino",
    homepage: "https://kino.joutsa.fi",
    verifiedAt: V,
    venues: [
      {
        slug: "joutsa",
        address: "Jousitie 27",
        postalCode: "19650",
        geo: { lat: 61.739517, lon: 26.111957 },
        geoSource: "nominatim",
        name: "Joutsan Kino",
        city: "Joutsa",
        place: "JOUTSAN KINO",
      },
    ],
  },
  {
    provider: "kkino",
    name: "K-Kino",
    homepage: "https://k-kino.fi",
    verifiedAt: V,
    titlePrefixes: { "Kauhujen Kangasala -elokuvanäytös": { series: "Kauhujen Kangasala" } },
    venues: [
      {
        slug: "kangasala",
        address: "Kuohunharjuntie 6",
        postalCode: "36200",
        geo: { lat: 61.46328, lon: 24.073056 },
        geoSource: "nominatim",
        name: "K-Kino",
        city: "Kangasala",
        place: "K-KINO",
      },
    ],
  },
  {
    provider: "biograni",
    name: "Bio Grani",
    homepage: "https://biograni.fi",
    verifiedAt: V,
    venues: [
      {
        slug: "kauniainen",
        address: "Teinikuja 4",
        postalCode: "02700",
        geo: { lat: 60.21439, lon: 24.725234 },
        geoSource: "osm:node/614453911",
        name: "Bio Grani",
        city: "Kauniainen",
        place: "BIO GRANI",
      },
    ],
  },
  {
    provider: "cine",
    name: "Cine",
    homepage: "https://kiertue.cine.fi",
    verifiedAt: V,
    notes: 'Touring cinema; place lines are "TOWN | HALL".',
    venues: [
      {
        slug: "keuda-talo",
        address: "Keskikatu 3A",
        postalCode: "04200",
        geo: { lat: 60.405191, lon: 25.101092 },
        geoSource: "osm:node/9839721870",
        name: "Cine Keuda-talo",
        city: "Kerava",
        place: "CINE KEUDA-TALO",
      },
      {
        slug: "nikkila",
        address: "Pohjoinen koulutie 2",
        postalCode: "04130",
        geo: { lat: 60.375475, lon: 25.266763 },
        geoSource: "nominatim",
        name: "Cine Nikkilä",
        city: "Sipoo",
        place: "CINE NIKKILÄ",
      },
    ],
  },
  {
    provider: "cinemaniagara",
    name: "Cinema Niagara",
    homepage: "https://cinemaniagara.fi",
    verifiedAt: V,
    noSubtitlesUnreliable: true,
    notes:
      'Own template: no place line, time in .time, labels without colons. "Ensi-ilta" is the ' +
      "original premiere here, so it is not used.",
    venues: [
      {
        slug: "tampere",
        geo: { lat: 61.495435, lon: 23.763675 },
        geoSource: "osm:node/896600870",
        name: "Cinema Niagara",
        city: "Tampere",
      },
    ],
  },
  {
    provider: "elokuvateatteristar",
    name: "Elokuvateatteri Star",
    homepage: "https://elokuvateatteristar.fi",
    base: "https://lippu.elokuvateatteristar.fi",
    verifiedAt: V,
    noSubtitlesUnreliable: true,
    venues: [
      {
        slug: "oulu",
        address: "Kalliotie 6",
        postalCode: "90500",
        geo: { lat: 65.024569, lon: 25.48275 },
        geoSource: "osm:node/355551782",
        name: "Star",
        city: "Oulu",
        place: "STAR",
      },
    ],
  },
  {
    provider: "haapamaenelokuvat",
    name: "Haapamäen Elokuvat",
    homepage: "https://haapamaenelokuvat.fi",
    verifiedAt: V,
    venues: [
      {
        slug: "haapamaki",
        name: "Haapamäen Elokuvat",
        city: "Keuruu",
        place: "HAAPAMÄEN ELOKUVAT",
        address: "Pihlajavedentie 1A",
        postalCode: "42800",
        geo: { lat: 62.253529, lon: 24.456869 },
        geoSource: "nominatim",
      },
    ],
  },
]);
