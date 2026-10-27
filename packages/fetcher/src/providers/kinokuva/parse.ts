import {
  makeId,
  type FilmListing,
  type FinnishRating,
  type ProviderBatch,
  type Screening,
  type ScreeningTag,
  type Subtitles,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import { own } from "../../lib/records.ts";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, plainText, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { KinoKuvaRawSnapshot } from "./fetch.ts";
import type { KinoKuvaSite } from "./sites.ts";

const WEEKDAYS = ["MA", "TI", "KE", "TO", "PE", "LA", "SU"];
/** "KE 14.10. KLO 19.00", "TO 15.10. KLO 14.00 JA KLO 17.00". */
const ROW = /^(MA|TI|KE|TO|PE|LA|SU)\s+(\d{1,2})\.(\d{1,2})\.?\s+KLO\s+(.+)$/i;
const ROWISH = /^(MA|TI|KE|TO|PE|LA|SU)\s+\d/i;
const TIME = /^(\d{1,2})[.:](\d{2})$/;
/** "Kesto: 1 h 52 min -K12-", "Kesto: 1 h 03 min -S-". */
const DURATION = /Kesto:\s*(\d+)\s*h\s*(\d+)\s*min/i;
const AGE = /-(S|K\d{1,2})-/i;
const PRICE = /^Liput\s+(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:,-|€)?$/i;
const FREE = /^Ilmainen sisäänpääsy!?$/i;
const PREVIEW = /^ENNAKKONÄYTÖ(?:S|KSET)!?$/i;
/** "Elokuvassa englanninkielinen tekstitys!" (also misspelt "teksitys"). */
const SUBTITLES = /\b(suomen|ruotsin|englannin)kielinen\s+tekst?i?tys/i;
const SUBTITLE_LANGS = { suomen: "fi", ruotsin: "sv", englannin: "en" } as const;
/** "Puolan elokuvaviikot:": a strand heading above the rows. */
const STRAND = /^([^:]{3,60}):$/;
const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  K7: "K-7",
  K12: "K-12",
  K16: "K-16",
  K18: "K-18",
};

/** Pure: the front page + site config -> normalized batch. */
export const parseKinoKuva = (raw: KinoKuvaRawSnapshot, site: KinoKuvaSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  const films = $("td.elokuva").toArray();
  if (films.length === 0) {
    warnings.push({ code: "invalid-response", message: "No films on the front page" });
  }
  let unreadable = 0;
  for (const el of films) {
    const head = $(el);
    const rawTitle = plainText(head.find("h1").first().text());
    const facts = plainText(head.text());
    const details = head.closest("table").find("td.elokuva_tiedot pre").first();
    const lines = (details.html() ?? "")
      .split(/<br\s*\/?>/i)
      .map((chunk) => plainText(load(chunk, null, false).text()))
      .filter(Boolean);

    const unmapped: string[] = [];
    const age = facts.match(AGE)?.[1]?.toUpperCase();
    const rating = age ? own(RATINGS, age) : undefined;
    if (age && !rating) {
      unmapped.push(`rating:${age}`);
    }
    const duration = facts.match(DURATION);
    const runtime = duration ? Number(duration[1]) * 60 + Number(duration[2]) : 0;
    const price = lines.some((l) => FREE.test(l))
      ? 0
      : toCents(lines.map((l) => l.match(PRICE)?.[1]).find(Boolean), { zeroIsFree: false });
    const preview = lines.some((l) => PREVIEW.test(l));
    const subtitleLang = lines.map((l) => l.match(SUBTITLES)?.[1]?.toLowerCase()).find(Boolean);
    const subtitles: Subtitles = subtitleLang
      ? {
          kind: "languages",
          languages: [SUBTITLE_LANGS[subtitleLang as keyof typeof SUBTITLE_LANGS]],
        }
      : { kind: "unknown" };
    const strand = lines
      .filter((l) => !ROWISH.test(l))
      .map((l) => l.match(STRAND)?.[1])
      .find(Boolean);

    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);
    const tags: ScreeningTag[] = [
      ...(preview ? (["preview"] as const) : []),
      ...(rule?.tags ?? []),
    ];
    const series = [...(rule?.series ? [rule.series] : []), ...(strand ? [strand] : [])];

    for (const line of lines.filter((l) => ROWISH.test(l))) {
      const m = line.match(ROW);
      const date = m ? nearestDate(Number(m[2]), Number(m[3]), raw.from) : undefined;
      const fits =
        date && WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] === m![1]!.toUpperCase();
      if (!m || !date || !fits || !rawTitle) {
        unreadable += 1;
        continue;
      }
      // "14.00 JA KLO 17.00": several screenings on one day.
      for (const t of m[4]!.split(/\s*(?:,|\bJA\b)\s*(?:KLO\s*)?/i)) {
        const tm = t.trim().match(TIME);
        const start =
          tm &&
          helsinkiShowTime({
            year: Number(date.slice(0, 4)),
            month: Number(m[3]),
            day: Number(m[2]),
            hour: Number(tm[1]),
            minute: Number(tm[2]),
          });
        if (!start) {
          unreadable += 1;
          continue;
        }
        if (start.businessDate < window.from || start.businessDate > window.to) {
          continue;
        }
        if (!listings.has(listingId)) {
          listings.set(listingId, {
            id: listingId,
            provider: P,
            sourceId: filmKey,
            title: { fi: title },
            ...(runtime > 0 && { runtimeMinutes: runtime }),
            ...(rating && { rating }),
            genres: [],
            countries: [],
            kind: rule?.event ? "event" : "film",
          });
        }
        const sourceId = `${filmKey}-${start.startsAt.slice(0, 16).replace(/[-T:]/g, "")}`;
        const id = makeId(P, "show", sourceId);
        screenings.set(id, {
          id,
          provider: P,
          sourceId,
          venueId,
          listingId,
          startsAt: start.startsAt,
          businessDate: start.businessDate,
          presentation: {
            projection: "digital",
            dimension: version.dimension ?? "2d",
            formats: [],
          },
          audio: version.audio ? [version.audio] : [],
          ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
          subtitles,
          tags,
          series,
          availability: "unknown",
          ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
          // Tickets at the door: the programme page.
          ticketUrl: `${site.homepage}/`,
          unmappedLabels: unmapped,
          fetchedAt: raw.fetchedAt,
        });
      }
    }
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} screening rows not understood, or with a weekday that fits no date`,
    });
  }

  return {
    provider: providerOf(site, "custom", "door"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: [toVenue(P, venue, venue.slug)],
    auditoriums: [],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
