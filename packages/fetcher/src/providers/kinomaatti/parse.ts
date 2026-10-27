import {
  makeId,
  type FilmListing,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, finnishRating, plainText, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { KinomaattiRawSnapshot } from "./fetch.ts";
import type { KinomaattiSite } from "./sites.ts";

/** Day names by their first two letters. */
const WEEKDAYS = ["ma", "ti", "ke", "to", "pe", "la", "su"];
/** "keskiviikko, 21.10. klo 18.00". */
const SHOWN = /^([a-zäö]{5,}),?\s+(\d{1,2})\.(\d{1,2})\.?\s+klo\s*(\d{1,2})[.:](\d{2})$/i;
const PRICE = /^(\d{1,3}(?:[.,]\d{1,2})?)\s*€$/;
/** The age image: ".../kino-age-12-150x150.jpg", "kino-age-s". */
const AGE_IMAGE = /kino-age-(s|7|12|16|18)\b/i;

/** Pure: the timetable page + site config -> normalized batch. */
export const parseKinomaatti = (
  raw: KinomaattiRawSnapshot,
  site: KinomaattiSite,
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
  const rows = $("tr.tulossa-movie").toArray();
  if (rows.length === 0) {
    warnings.push({ code: "invalid-response", message: "No timetable rows on the page" });
  }
  let unreadable = 0;
  for (const el of rows) {
    const row = $(el);
    const link = row.find("a.tulossa-movie-name").first();
    const href = link.attr("href") ?? "";
    const slug = href.match(/\/elokuva\/([^/?#]+)\/?$/)?.[1];
    const heading = link.find("h3").first().clone();
    const ageStyle = heading.find(".age").attr("style") ?? "";
    const format = plainText(heading.find(".tyyppi").text());
    heading.find(".age, .tyyppi").remove();
    const rawTitle = plainText(heading.text());
    const m = plainText(row.find(".tulossa-esitysaika").text()).match(SHOWN);
    const date = m ? nearestDate(Number(m[2]), Number(m[3]), raw.from) : undefined;
    const fits =
      date &&
      WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] === m![1]!.slice(0, 2).toLowerCase();
    const start =
      m &&
      date &&
      fits &&
      helsinkiShowTime({
        year: Number(date.slice(0, 4)),
        month: Number(m[3]),
        day: Number(m[2]),
        hour: Number(m[4]),
        minute: Number(m[5]),
      });
    if (!rawTitle || !start) {
      unreadable += 1;
      continue;
    }
    if (start.businessDate < window.from || start.businessDate > window.to) {
      continue;
    }
    const unmapped: string[] = [];
    const age = ageStyle.match(AGE_IMAGE)?.[1]?.toLowerCase();
    const rating = age ? finnishRating(age) : undefined;
    if (/kino-age-/i.test(ageStyle) && !rating) {
      unmapped.push(`rating:${ageStyle.match(/kino-age-[a-z0-9]+/i)?.[0]}`);
    }
    const dimension = /^3d$/i.test(format) ? "3d" : /^2d$/i.test(format) ? "2d" : undefined;
    if (format && !dimension) {
      unmapped.push(`format:${format}`);
    }
    const price = toCents(plainText(row.find(".tulossa-hinta").text()).match(PRICE)?.[1], {
      zeroIsFree: false,
    });

    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const filmKey = slug ?? slugify(title);
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
      presentation: {
        projection: "digital",
        dimension: version.dimension ?? dimension ?? "2d",
        formats: [],
      },
      audio: version.audio ? [version.audio] : [],
      ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
      subtitles: { kind: "unknown" },
      tags: [...(rule?.tags ?? [])],
      series: rule?.series ? [rule.series] : [],
      availability: "unknown",
      ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
      // The film's page on the cinema's site, copied.
      ticketUrl: href.startsWith(`${site.homepage}/`) ? href : site.programme,
      unmappedLabels: unmapped,
      fetchedAt: raw.fetchedAt,
    });
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} timetable rows not understood, or with a weekday that fits no date`,
    });
  }

  return {
    provider: providerOf(site, "custom", "info"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: [toVenue(P, venue, venue.slug)],
    auditoriums: [],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
