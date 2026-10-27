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
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, finnishRating, plainText, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { NavettaRawSnapshot } from "./fetch.ts";
import type { NavettaSite } from "./sites.ts";

const WEEKDAYS = ["MA", "TI", "KE", "TO", "PE", "LA", "SU"];
/** "[Title] la 17.10 klo 15:00": the title may share the line or be the line before. */
const SHOW =
  /^(.*?)\s*\b(ma|ti|ke|to|pe|la|su)\s+(\d{1,2})\.(\d{1,2})\.?\s+klo\s+(\d{1,2})[:.](\d{2})$/i;
/** The film block's facts: "K7, 87 min, liput 10 €", "Kesto 1 h 27 min, K12, liput 10 €". */
const FACTS = /\bliput\s+\d/i;

type Facts = { rating?: FinnishRating; runtime?: number; price?: number; unmapped: string[] };

const factsOf = (line: string): Facts => {
  const unmapped: string[] = [];
  const age = line.match(/\b(S|K-?\d{1,2})\b/)?.[1]?.replace("-", "");
  const rating = age ? finnishRating(age) : undefined;
  if (age && !rating) {
    unmapped.push(`rating:${age}`);
  }
  const hm = line.match(/Kesto\s+(\d+)\s*h\s*(\d+)\s*min/i);
  const m = line.match(/\b(\d{2,3})\s*min/i);
  const runtime = hm ? Number(hm[1]) * 60 + Number(hm[2]) : m ? Number(m[1]) : 0;
  const price = toCents(line.match(/liput\s+(\d{1,3}(?:[.,]\d{1,2})?)\s*€\s*$/i)?.[1], {
    zeroIsFree: false,
  });
  return {
    ...(rating && { rating }),
    ...(runtime > 0 && { runtime }),
    ...(price !== undefined && { price }),
    unmapped,
  };
};

/** Pure: the front page + site config -> normalized batch. */
export const parseNavetta = (raw: NavettaRawSnapshot, site: NavettaSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  // Paragraphs and figures in order; a figure marks the paragraph before it as a title.
  const nodes = $("p, figure").toArray();
  const start = nodes.findIndex((n) => plainText($(n).text()) === site.heading);
  if (start < 0) {
    warnings.push({ code: "invalid-response", message: `No "${site.heading}" on the page` });
  }
  type Shown = { title: string; date: RegExpMatchArray };
  const shown: Shown[] = [];
  const facts = new Map<string, Facts>();
  let unreadable = 0;
  let lastLine = "";
  let blockTitle = "";
  for (const node of start >= 0 ? nodes.slice(start + 1) : []) {
    if (node.tagName === "figure") {
      blockTitle = lastLine;
      continue;
    }
    const lines = ($(node).html() ?? "")
      .split(/<br\s*\/?>/i)
      .map((part) => plainText(load(part, null, false).text()))
      .filter(Boolean);
    for (const line of lines) {
      const m = line.match(SHOW);
      if (m) {
        const title = m[1] || lastLine;
        if (title) {
          shown.push({ title, date: m });
        } else {
          unreadable += 1;
        }
      } else if (FACTS.test(line) && blockTitle) {
        facts.set(blockTitle.toLowerCase(), factsOf(line));
      }
      lastLine = m && !m[1] ? lastLine : line;
    }
  }

  for (const { title: rawTitle, date: m } of shown) {
    const date = nearestDate(Number(m[3]), Number(m[4]), raw.from);
    const weekday = date ? WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] : undefined;
    const at =
      date &&
      // The weekday is the only check on the year we infer.
      weekday === m[2]!.toUpperCase() &&
      helsinkiShowTime({
        year: Number(date.slice(0, 4)),
        month: Number(m[4]),
        day: Number(m[3]),
        hour: Number(m[5]),
        minute: Number(m[6]),
      });
    if (!at) {
      unreadable += 1;
      continue;
    }
    if (at.businessDate < window.from || at.businessDate > window.to) {
      continue;
    }
    const film = facts.get(rawTitle.toLowerCase());
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
        ...(film?.runtime && { runtimeMinutes: film.runtime }),
        ...(film?.rating && { rating: film.rating }),
        genres: [],
        countries: [],
        kind: rule?.event ? "event" : "film",
      });
    }
    // The page may list a screening twice (the list and the film's block): one screening.
    const sourceId = `${filmKey}-${at.startsAt.slice(0, 16).replace(/[-T:]/g, "")}`;
    const id = makeId(P, "show", sourceId);
    screenings.set(id, {
      id,
      provider: P,
      sourceId,
      venueId,
      listingId,
      startsAt: at.startsAt,
      businessDate: at.businessDate,
      presentation: { projection: "digital", dimension: version.dimension ?? "2d", formats: [] },
      audio: version.audio ? [version.audio] : [],
      ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
      subtitles: { kind: "unknown" },
      tags: [...(rule?.tags ?? [])],
      series: rule?.series ? [rule.series] : [],
      availability: "unknown",
      ...(film?.price !== undefined && {
        price: { amountCents: film.price, currency: "EUR" as const },
      }),
      // Tickets at the door: the page.
      ticketUrl: `${site.homepage}/`,
      unmappedLabels: [...(film?.unmapped ?? [])],
      fetchedAt: raw.fetchedAt,
    });
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} screening lines without a title, or with a weekday that fits no date`,
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
