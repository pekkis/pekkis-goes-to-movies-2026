import {
  makeId,
  type FilmListing,
  type FinnishRating,
  type ProviderBatch,
  type Screening,
  type Subtitles,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import { own } from "../../lib/records.ts";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { HaminaRawSnapshot } from "./fetch.ts";
import type { HaminaSite } from "./sites.ts";

const WEEKDAYS = ["MA", "TI", "KE", "TO", "PE", "LA", "SU"];
/** "To 22.10. Klo 15:00", optionally "(Liput 8€)" or "| Liput 8€" for that showing. */
const ROW =
  /^(Ma|Ti|Ke|To|Pe|La|Su)\s+(\d{1,2})\.(\d{1,2})\.?\s+Klo\s+(\d{1,2})[:.](\d{2})(?:\s*[|(]?\s*Liput\s+(\d{1,3}(?:[.,]\d{1,2})?)\s*€\s*\)?)?$/i;
/** "1 h 57 min", "1 t 28 min" */
const DURATION = /^(?:(\d+)\s*[ht])?\s*(\d+)\s*min$/i;
/** One plain amount: "11€". A range or "alkaen" settles nothing. */
const PRICE = /^(\d{1,3}(?:[.,]\d{1,2})?)\s*€$/;
const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  "7": "K-7",
  "12": "K-12",
  "16": "K-16",
  "18": "K-18",
};

const text = (value: string | undefined) => (value ?? "").replace(/\s+/g, " ").trim();
const lines = (html: string | null) =>
  (html ?? "").split(/<br\s*\/?>/i).map((part) => text(load(part, null, false).text()));

/** Pure: the cinema's page + site config -> normalized batch. */
export const parseHamina = (raw: HaminaRawSnapshot, site: HaminaSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  const blocks = $(".large-content-showcase").toArray();
  if (blocks.length === 0) {
    warnings.push({ code: "invalid-response", message: "No film blocks on the cinema's page" });
  }
  let unreadable = 0;
  for (const el of blocks) {
    const block = $(el);
    const rawTitle = text(block.find(".large-content-showcase__title").first().text());
    const paragraphs = block.find(".large-content-showcase__paragraph p").toArray();
    if (!rawTitle || paragraphs.length === 0) {
      continue;
    }
    // The first paragraph is the film's labelled fields, the rest its screenings.
    const fields = new Map<string, string>();
    for (const line of lines($(paragraphs[0]).html())) {
      const m = line.match(/^([A-Za-zäö-]+):\s*(.+)$/);
      if (m) {
        fields.set(m[1]!.toLowerCase(), m[2]!);
      }
    }
    const unmapped: string[] = [];
    const age = fields.get("ikäraja")?.toUpperCase();
    const rating = age ? own(RATINGS, age) : undefined;
    if (age && !rating) {
      unmapped.push(`rating:${age}`);
    }
    const duration = fields.get("kesto")?.match(DURATION);
    const runtime = duration ? Number(duration[1] ?? 0) * 60 + Number(duration[2]) : 0;
    const filmPrice = toCents(fields.get("liput")?.match(PRICE)?.[1], { zeroIsFree: false });
    const versionText = fields.get("versio")?.toUpperCase();
    const siteVersion = versionText ? own(site.versions, versionText) : undefined;
    if (versionText && !siteVersion) {
      unmapped.push(`version:${versionText}`);
    }

    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);
    const audio = version.audio ?? siteVersion?.audio;
    const dubbed = version.dubbed ?? siteVersion?.dubbed;
    const subtitles: Subtitles = siteVersion?.subtitles
      ? { kind: "languages", languages: siteVersion.subtitles }
      : { kind: "unknown" };

    for (const p of paragraphs.slice(1)) {
      for (const row of lines($(p).html())) {
        if (!row) {
          continue;
        }
        const m = row.match(ROW);
        const date = m ? nearestDate(Number(m[2]), Number(m[3]), raw.from) : undefined;
        const weekday = date ? WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] : undefined;
        const start =
          m &&
          date &&
          // The weekday is the only check on the year we infer.
          weekday === m[1]!.toUpperCase() &&
          helsinkiShowTime({
            year: Number(date.slice(0, 4)),
            month: Number(m[3]),
            day: Number(m[2]),
            hour: Number(m[4]),
            minute: Number(m[5]),
          });
        if (!m || !start) {
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
        // A price on the row is that showing's ("(Liput 8€)"); otherwise the film's.
        const price = m[6] ? toCents(m[6], { zeroIsFree: false }) : filmPrice;
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
          audio: audio ? [audio] : [],
          ...(dubbed !== undefined && { dubbed }),
          subtitles,
          tags: [...(rule?.tags ?? [])],
          series: rule?.series ? [rule.series] : [],
          availability: "unknown",
          ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
          // Tickets at the door: the cinema's page.
          ticketUrl: site.programme,
          unmappedLabels: [...unmapped],
          fetchedAt: raw.fetchedAt,
        });
      }
    }
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} screening lines not understood, or with a weekday that fits no date`,
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
