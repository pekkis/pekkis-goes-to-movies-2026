import {
  makeId,
  type Auditorium,
  type FilmListing,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime } from "@pgtm/model/time";
import { load } from "cheerio";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, finnishRating, plainText, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { BioSavoyRawSnapshot } from "./fetch.ts";
import type { BioSavoySite } from "./sites.ts";

/** A film page's day panel: `id="film-day-2026-10-28"`. */
const DAY_PANEL = /^film-day-(\d{4})-(\d{2})-(\d{2})$/;
/** "19.30". */
const TIME = /^(\d{1,2})[.:](\d{2})$/;
/** "2 h 35 min", "95 min". */
const RUNTIME = /^(?:(\d{1,2})\s*h)?\s*(?:(\d{1,3})\s*min)?$/i;
/** "15 €". */
const PRICE = /^(\d{1,3}(?:[.,]\d{1,2})?)\s*€$/;
/** The schedule's day heading: "Onsdag 28/10". */
const DAY_HEADING = /(\d{1,2})\/(\d{1,2})$/;

/** The film pages `/spelschema` links, in order, once each. */
export const filmUrls = (schedule: string, site: BioSavoySite): string[] => {
  const $ = load(schedule);
  const urls = $(".schedule a.show-row[href^='/film/']")
    .toArray()
    .map((a) => new URL($(a).attr("href")!, `${site.base}/`).href);
  return [...new Set(urls)];
};

/** "lapin-sota|28/10|19.30": a showtime as both pages print it, to compare them. */
const showKey = (slug: string, day: number, month: number, time: string): string =>
  `${slug}|${day}/${month}|${time}`;

/** The schedule's rows, as showKeys; undefined when the page has no schedule. */
const scheduleKeys = (schedule: string): Set<string> | undefined => {
  const $ = load(schedule);
  if ($(".schedule__days").length === 0) {
    return undefined;
  }
  const keys = new Set<string>();
  for (const day of $(".schedule__days > div").toArray()) {
    const date = plainText($(day).find(".schedule__day-heading").first().text()).match(DAY_HEADING);
    for (const row of $(day).find("a.show-row").toArray()) {
      const slug = $(row)
        .attr("href")
        ?.match(/^\/film\/([^/?#]+)/)?.[1];
      const time = plainText($(row).find(".show-row__time").text());
      keys.add(showKey(slug ?? "?", Number(date?.[1]), Number(date?.[2]), time));
    }
  }
  return keys;
};

/** Pure: `/spelschema` and the film pages + site config -> normalized batch. */
export const parseBioSavoy = (raw: BioSavoyRawSnapshot, site: BioSavoySite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const auditoriums = new Map<string, Auditorium>();
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const scheduled = scheduleKeys(raw.schedule);
  if (!scheduled) {
    warnings.push({ code: "invalid-response", message: "No programme on /spelschema" });
  }
  // What the film pages showed, to find schedule rows that no film page has.
  const shown = new Set<string>();
  let unreadable = 0;
  for (const [url, page] of Object.entries(raw.films)) {
    if (page === null) {
      warnings.push({ code: "invalid-film-page", message: `Film page failed: ${url}` });
      continue;
    }
    const $ = load(page);
    const slug = url.match(/\/film\/([^/?#]+)\/?$/)?.[1];
    const rawTitle = plainText($("h1.hero-title").first().text());
    const panels = $(".film-schedule [data-tab-panel]").toArray();
    if (!slug || !rawTitle) {
      warnings.push({ code: "invalid-film-page", message: `Film page not understood: ${url}` });
      continue;
    }

    const unmapped: string[] = [];
    const badge = plainText(
      $(".film-hero__meta .age-badge").first().clone().find(".sr-only").remove().end().text(),
    );
    const rating = badge ? finnishRating(badge) : undefined;
    if (badge && !rating) {
      unmapped.push(`rating:${badge}`);
    }
    const facts = new Map(
      $(".film-facts__item")
        .toArray()
        .map((item) => [
          plainText($(item).find("dt").text()),
          plainText($(item).find("dd").text()),
        ]),
    );
    const runtimeMatch = (facts.get("Speltid") ?? "").match(RUNTIME);
    const runtime = runtimeMatch
      ? Number(runtimeMatch[1] ?? 0) * 60 + Number(runtimeMatch[2] ?? 0)
      : 0;

    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const listingId = makeId(P, "film", slug);

    for (const panel of panels) {
      const date = ($(panel).attr("id") ?? "").match(DAY_PANEL);
      for (const row of $(panel).find("li.show-row").toArray()) {
        const time = plainText($(row).find(".show-row__time").text());
        const clock = time.match(TIME);
        const hall = plainText($(row).find(".show-row__title").text());
        const start =
          date &&
          clock &&
          helsinkiShowTime({
            year: Number(date[1]),
            month: Number(date[2]),
            day: Number(date[3]),
            hour: Number(clock[1]),
            minute: Number(clock[2]),
          });
        if (!date || !start || !hall) {
          unreadable += 1;
          continue;
        }
        shown.add(showKey(slug, Number(date[3]), Number(date[2]), time));
        if (start.businessDate < window.from || start.businessDate > window.to) {
          continue;
        }
        const auditoriumId = makeId(P, "screen", `${venue.slug}-${slugify(hall)}`);
        if (!auditoriums.has(auditoriumId)) {
          auditoriums.set(auditoriumId, { id: auditoriumId, venueId, name: hall, features: [] });
        }
        if (!listings.has(listingId)) {
          listings.set(listingId, {
            id: listingId,
            provider: P,
            sourceId: slug,
            // The site is Swedish: the title is Swedish, not Finnish.
            title: { sv: title },
            ...(runtime > 0 && { runtimeMinutes: runtime }),
            ...(rating && { rating }),
            genres: [],
            countries: [],
            kind: rule?.event ? "event" : "film",
          });
        }
        const priceText = plainText($(row).find(".show-row__meta").text());
        const price = toCents(priceText.match(PRICE)?.[1], { zeroIsFree: false });
        const sourceId = `${slug}-${start.startsAt.slice(0, 16).replace(/[-T:]/g, "")}`;
        const id = makeId(P, "show", sourceId);
        screenings.set(id, {
          id,
          provider: P,
          sourceId,
          venueId,
          auditoriumId,
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
          subtitles: { kind: "unknown" },
          tags: [...(rule?.tags ?? [])],
          series: rule?.series ? [rule.series] : [],
          availability: "unknown",
          ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
          // Bookings by phone: the film's own page, as the schedule links it.
          ticketUrl: url,
          unmappedLabels: unmapped,
          fetchedAt: raw.fetchedAt,
        });
      }
    }
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} film page showtimes without a date, time or hall`,
    });
  }
  const missing = [...(scheduled ?? [])].filter((key) => !shown.has(key));
  if (missing.length > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${missing.length} schedule rows on no film page`,
      context: { rows: missing },
    });
  }

  return {
    provider: providerOf(site, "custom", "reserve"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: [toVenue(P, venue, venue.slug)],
    auditoriums: [...auditoriums.values()],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
