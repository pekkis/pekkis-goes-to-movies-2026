import {
  makeId,
  type FilmListing,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime } from "@pgtm/model/time";
import { load } from "cheerio";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, plainText, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { LeviSummitRawSnapshot } from "./fetch.ts";
import type { LeviSummitSite } from "./sites.ts";

const WEEKDAYS = ["ma", "ti", "ke", "to", "pe", "la", "su"];
/** "Torstai 15.10.2026". */
const DAY = /(\d{1,2})\.(\d{1,2})\.(\d{4})$/;
/** "To klo 14:00": the weekday must be the section's. */
const SHOWTIME = /^(ma|ti|ke|to|pe|la|su)\s+klo\s+(\d{1,2})[.:](\d{2})$/i;
const PRICE = /^(\d{1,3}(?:[.,]\d{1,2})?)\s*€$/;

/** Pure: the cinema page + site config -> normalized batch. */
export const parseLeviSummit = (
  raw: LeviSummitRawSnapshot,
  site: LeviSummitSite,
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
  if ($(".show-calendar").length === 0) {
    warnings.push({ code: "invalid-response", message: "No show calendar on the cinema page" });
  }
  let unreadable = 0;
  for (const section of $(".levi-summit-cinema-show-day-container").toArray()) {
    const day = plainText($(section).find("h3").first().text()).match(DAY);
    const cards = $(section).find(".levi-summit-cinema-show-day__single").toArray();
    if (!day) {
      unreadable += cards.length;
      continue;
    }
    const date = Temporal.PlainDate.from({
      year: Number(day[3]),
      month: Number(day[2]),
      day: Number(day[1]),
    });
    for (const el of cards) {
      const card = $(el);
      const rawTitle = plainText(card.find("h4").first().text());
      const href = card.find(".title-showtime a").attr("href") ?? "";
      const m = plainText(card.find(".movie-showtime").text()).match(SHOWTIME);
      const start =
        m &&
        WEEKDAYS[date.dayOfWeek - 1] === m[1]!.toLowerCase() &&
        helsinkiShowTime({
          year: date.year,
          month: date.month,
          day: date.day,
          hour: Number(m[2]),
          minute: Number(m[3]),
        });
      if (!rawTitle || !start) {
        unreadable += 1;
        continue;
      }
      if (start.businessDate < window.from || start.businessDate > window.to) {
        continue;
      }
      const price = toCents(
        plainText(card.find(".movie-tickets").first().text()).match(PRICE)?.[1],
        {
          zeroIsFree: false,
        },
      );
      const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
      const { title, version } = splitVersion(unprefixed);
      const filmKey = slugify(title);
      const listingId = makeId(P, "film", filmKey);
      if (!listings.has(listingId)) {
        listings.set(listingId, {
          id: listingId,
          provider: P,
          sourceId: filmKey,
          title: { fi: title },
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
        ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
        // The film's page on the operator's site, copied.
        ticketUrl: href.startsWith(site.filmPagePrefix) ? href : site.programme,
        unmappedLabels: [],
        fetchedAt: raw.fetchedAt,
      });
    }
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} screenings not understood (no title, or a weekday that is not the day's)`,
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
