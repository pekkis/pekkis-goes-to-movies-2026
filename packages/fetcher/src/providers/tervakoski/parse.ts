import {
  makeId,
  type FilmListing,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import {
  COMMON_TITLE_PREFIXES,
  isPrivateBooking,
  splitTitlePrefix,
  splitVersion,
} from "../labels.ts";
import { byStartThenId, finnishRating, plainText, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { TervakoskiRawSnapshot } from "./fetch.ts";
import type { TervakoskiSite } from "./sites.ts";

/** Day names by their first two letters. */
const WEEKDAYS = ["ma", "ti", "ke", "to", "pe", "la", "su"];
/** "Keskiviikko 14.10.", "Perjantai 16.10". */
const DAY = /^([a-zäö]{5,})\s+(\d{1,2})\.(\d{1,2})\.?$/i;
/** "Klo 17.00 – Pirjo i Sverige (S), kotimainen, …". */
const ROW = /^Klo\s+(\d{1,2})[.:](\d{2})\s*[–-]\s*(.+)$/i;
/**
 * The title closes with its rating: "Pirjo i Sverige (S),", or a note that it is not set
 * yet: "(Ikäraja ei viellä tiedossa)" (2026-10-31), which leaves the rating unknown.
 */
const TITLE = /^(.+?)\s*\((S|K-?\d{1,2}|ikäraja ei vie?ll?ä tiedossa)\),?\s*(.*)$/i;
const NOT_RATED = /^ikäraja/i;
/** "kesto 1 t 28 min", also "kesto, 1t 57 min" (2026-10-17). */
const RUNTIME = /kesto,?\s+(\d+)\s*t(?:\s*(\d+)\s*min)?/i;
const PRICE = /lippu\s+(\d{1,3}(?:[.,]\d{1,2})?)\s*€/i;
const DUBBED = /\bsuomeksi puhuttu\b/i;

/** Pure: the programme page + site config -> normalized batch. */
export const parseTervakoski = (
  raw: TervakoskiRawSnapshot,
  site: TervakoskiSite,
): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  // The programme runs from the first day heading to the next separator.
  const blocks = $("p, hr").toArray();
  const first = blocks.findIndex((el) => $(el).is("p") && DAY.test(plainText($(el).text())));
  const last = blocks.findIndex((el, i) => i > first && $(el).is("hr"));
  if (first < 0) {
    warnings.push({ code: "invalid-response", message: "No day headings on the programme page" });
  }
  let date: string | undefined;
  let unreadable = 0;
  for (const el of first < 0 ? [] : blocks.slice(first, last < 0 ? undefined : last)) {
    const line = plainText($(el).text());
    const day = line.match(DAY);
    if (day) {
      const iso = nearestDate(Number(day[2]), Number(day[3]), raw.from);
      const fits =
        iso &&
        WEEKDAYS[Temporal.PlainDate.from(iso).dayOfWeek - 1] === day[1]!.slice(0, 2).toLowerCase();
      date = fits ? iso : undefined;
      if (!fits) {
        unreadable += 1;
      }
      continue;
    }
    const row = line.match(ROW);
    if (!row) {
      continue; // empty paragraphs, notes
    }
    if (isPrivateBooking(row[3]!)) {
      continue; // a private event: nothing to list, nothing missing
    }
    const film = row[3]!.match(TITLE);
    const start =
      date &&
      film &&
      helsinkiShowTime({
        year: Number(date.slice(0, 4)),
        month: Number(date.slice(5, 7)),
        day: Number(date.slice(8, 10)),
        hour: Number(row[1]),
        minute: Number(row[2]),
      });
    if (!film || !start) {
      unreadable += 1;
      continue;
    }
    if (start.businessDate < window.from || start.businessDate > window.to) {
      continue;
    }
    const facts = film[3] ?? "";
    const notRated = NOT_RATED.test(film[2]!);
    const age = film[2]!.toUpperCase().replace("-", "");
    const rating = notRated ? undefined : finnishRating(age);
    const duration = facts.match(RUNTIME);
    const runtime = duration ? Number(duration[1]) * 60 + Number(duration[2] ?? 0) : 0;
    const price = toCents(facts.match(PRICE)?.[1], { zeroIsFree: false });
    const dubbed = DUBBED.test(facts);

    const { title: unprefixed, rule } = splitTitlePrefix(film[1]!, prefixRules);
    const { title: name, version } = splitVersion(unprefixed);
    const filmKey = slugify(name);
    const listingId = makeId(P, "film", filmKey);
    if (!listings.has(listingId)) {
      listings.set(listingId, {
        id: listingId,
        provider: P,
        sourceId: filmKey,
        title: { fi: name },
        ...(runtime > 0 && { runtimeMinutes: runtime }),
        ...(rating && { rating }),
        genres: [],
        countries: [],
        kind: rule?.event ? "event" : "film",
      });
    }
    const audio = version.audio ?? (dubbed ? "fi" : undefined);
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
      presentation: { projection: "digital", dimension: version.dimension ?? "2d", formats: [] },
      audio: audio ? [audio] : [],
      ...((version.dubbed !== undefined || dubbed) && { dubbed: version.dubbed ?? dubbed }),
      subtitles: { kind: "unknown" },
      tags: [...(rule?.tags ?? [])],
      series: rule?.series ? [rule.series] : [],
      availability: "unknown",
      ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
      // Tickets at the door: the programme page.
      ticketUrl: site.programme,
      unmappedLabels: rating || notRated ? [] : [`rating:${film[2]}`],
      fetchedAt: raw.fetchedAt,
    });
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} lines not understood (a day whose weekday fits no date, or a row without a title and rating)`,
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
