import {
  makeId,
  type FilmListing,
  type FinnishRating,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import { own } from "../../lib/records.ts";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, plainText, slugify } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { KinoYlariRawSnapshot } from "./fetch.ts";
import type { KinoYlariSite } from "./sites.ts";

const WEEKDAYS = ["ma", "ti", "ke", "to", "pe", "la", "su"];
/** "to 15.10. klo 15.00 Kätyrit & Monsterit K7": the title is the bold part. */
const ROW =
  /^(ma|ti|ke|to|pe|la|su)\s+(\d{1,2})\.(\d{1,2})\.?\s+klo\s+(\d{1,2})[.:](\d{2})\s+(.+)$/i;
/** The rating after the title; "K?" is not rated yet. */
const AGE = /\b(S|K\d{1,2}|K\?)\s*(.*)$/;
const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  K7: "K-7",
  K12: "K-12",
  K16: "K-16",
  K18: "K-18",
};

/** Pure: the cinema page + site config -> normalized batch. */
export const parseKinoYlari = (raw: KinoYlariRawSnapshot, site: KinoYlariSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  const heading = $("h2")
    .toArray()
    .find((el) => /^Ohjelmisto$/i.test(plainText($(el).text())));
  if (!heading) {
    warnings.push({ code: "invalid-response", message: "No Ohjelmisto heading on the page" });
  }
  const rows = heading ? $(heading).next("div").find("div").toArray() : [];
  let unreadable = 0;
  for (const el of rows) {
    const line = plainText($(el).text());
    const m = line.match(ROW);
    if (!m) {
      continue; // spacers, links, notes
    }
    const bold = plainText($(el).find("strong").first().text());
    // A bold line that is itself a showtime announces the row below it.
    if (!bold || ROW.test(bold)) {
      continue;
    }
    const after = plainText(line.slice(line.indexOf(bold) + bold.length));
    const age = after.match(AGE)?.[1]?.toUpperCase();
    const rating = age && age !== "K?" ? own(RATINGS, age) : undefined;
    const unmapped = age && age !== "K?" && !rating ? [`rating:${age}`] : [];
    const date = nearestDate(Number(m[2]), Number(m[3]), raw.from);
    const fits =
      date && WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] === m[1]!.toLowerCase();
    const start =
      date &&
      fits &&
      helsinkiShowTime({
        year: Number(date.slice(0, 4)),
        month: Number(m[3]),
        day: Number(m[2]),
        hour: Number(m[4]),
        minute: Number(m[5]),
      });
    if (!start) {
      unreadable += 1;
      continue;
    }
    if (start.businessDate < window.from || start.businessDate > window.to) {
      continue;
    }
    const { title: unprefixed, rule } = splitTitlePrefix(bold, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);
    if (!listings.has(listingId)) {
      listings.set(listingId, {
        id: listingId,
        provider: P,
        sourceId: filmKey,
        title: { fi: title },
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
      presentation: { projection: "digital", dimension: version.dimension ?? "2d", formats: [] },
      audio: version.audio ? [version.audio] : [],
      ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
      subtitles: { kind: "unknown" },
      tags: [...(rule?.tags ?? [])],
      series: rule?.series ? [rule.series] : [],
      availability: "unknown",
      // Tickets at the door: the cinema's page.
      ticketUrl: site.programme,
      unmappedLabels: unmapped,
      fetchedAt: raw.fetchedAt,
    });
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
