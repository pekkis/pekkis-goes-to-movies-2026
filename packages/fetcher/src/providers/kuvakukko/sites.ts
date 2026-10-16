import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Kuopio's two city cinemas, Kino Kuvakukko and Nilsiä's Kino Manttu, share one WordPress
 * page: under each cinema's `<h2>` heading, paragraphs of "Tiistai 15.9." day lines and
 * "Klo 17.30: Title" rows. No year, no ids, tickets at the door only. Mapped by Leffavuoro
 * (Shady-Dev/kino, scripts/providers/kuvakukko.py, AGPL-3.0); re-verified 2026-10-14.
 */
export const KuvakukkoVenue = SiteVenue.extend({
  /** Text in this venue's schedule heading ("Kino Kuvakukon esitysaikataulu"), any case. */
  heading: z.string().min(1),
});

export const KuvakukkoSite = SiteBase.extend({
  /** The programme page; also where every screening links, as tickets are sold at the door. */
  programme: z.url(),
  venues: z.array(KuvakukkoVenue).min(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
  /**
   * A trailing parenthesis opening with one of these words is a note, not part of the
   * title: "Sopeutumaton (tekijävierailunäytös, paikalla ohjaaja …)", or after the link,
   * "Näytös B (vapaa pääsy)". Matched in any case; the parenthesis may be left unclosed.
   * The rule says what the note means.
   */
  titleNotes: z.record(z.string().min(1), LabelRule),
});
export type KuvakukkoSite = z.infer<typeof KuvakukkoSite>;

export const KUVAKUKKO_SITES: KuvakukkoSite[] = defineSites(KuvakukkoSite, [
  {
    provider: "kuvakukko",
    name: "Kuvakukko",
    homepage: "https://www.kuvakukko.fi",
    programme: "https://www.kuvakukko.fi/ohjelmisto/kuvakukon-ja-kino-mantun-ohjelmisto/",
    verifiedAt: "2026-10-14",
    titlePrefixes: {
      "Kino Manttu": {},
      "Kuvin aluesarja": { series: "Kuvin aluesarja" },
      "Hyvät Kuvat-kerho": { series: "Hyvät Kuvat -kerho" },
      "Hopeatähti-sarja": { series: "Hopeatähti" },
    },
    titleNotes: { tekijävierailu: { tags: ["guest"] }, "vapaa pääsy": { tags: ["free"] } },
    notes:
      "Addresses from the cinema's own page (2026-10-14). OSM puts Manttu's building on Mantunsuora; the cinema says Vesitornintie 1.",
    venues: [
      {
        slug: "kuopio",
        name: "Kino Kuvakukko",
        shortName: "Kuvakukko",
        city: "Kuopio",
        address: "Vuorikatu 27",
        postalCode: "70100",
        geo: { lat: 62.89389, lon: 27.6821422 },
        geoSource: "osm:node/5520821567",
        heading: "kuvakukon",
      },
      {
        slug: "nilsia",
        name: "Kino Manttu",
        shortName: "Manttu",
        city: "Nilsiä",
        address: "Vesitornintie 1",
        postalCode: "73300",
        geo: { lat: 63.2025177, lon: 28.0834834 },
        geoSource: "osm:way/487580170",
        heading: "mantun",
      },
    ],
  },
]);
