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
/** "su 01.11 klo 17:00 - Varaa": a screening under the card's "Näytökset". */
const SHOW = /^(ma|ti|ke|to|pe|la|su)\s+(\d{1,2})\.(\d{1,2})\.?\s+klo\s+(\d{1,2})[:.](\d{2})\b/i;
/** The card's facts: "K16, kesto 158 min, liput 11 €", "Kesto 1 h 27 min, K12, liput 10 €". */
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
  const cards = $("div.w3-card").toArray();
  if (cards.length === 0) {
    warnings.push({ code: "invalid-response", message: "No film cards on the page" });
  }
  let unreadable = 0;
  for (const card of cards) {
    const rawTitle = plainText($(card).find("h2").first().text());
    const factsLine = $(card)
      .find("p")
      .toArray()
      .map((p) => plainText($(p).text()))
      .find((l) => FACTS.test(l));
    const film = factsLine ? factsOf(factsLine) : undefined;
    // The paragraphs after "Näytökset", one screening each (or several, split at <br>).
    const shows = $(card)
      .find("h4")
      .filter((_, h) => /^näytökset$/i.test(plainText($(h).text())))
      .nextAll("p")
      .toArray()
      .flatMap((p) =>
        ($(p).html() ?? "").split(/<br\s*\/?>/i).map((part) => load(part, null, false)),
      )
      .map((part) => ({
        line: plainText(part.text()),
        href: part("a[href]").first().attr("href"),
      }))
      .filter((s) => s.line);
    if (!rawTitle) {
      unreadable += shows.length;
      continue;
    }
    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);

    for (const { line, href } of shows) {
      const m = line.match(SHOW);
      const date = m ? nearestDate(Number(m[2]), Number(m[3]), raw.from) : undefined;
      const weekday = date ? WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] : undefined;
      const at =
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
      if (!at) {
        unreadable += 1;
        continue;
      }
      if (at.businessDate < window.from || at.businessDate > window.to) {
        continue;
      }
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
        // The screening's reservation page, as the card links it; else the front page.
        ticketUrl: href ? new URL(href, `${site.homepage}/`).href : `${site.homepage}/`,
        unmappedLabels: [...(film?.unmapped ?? [])],
        fetchedAt: raw.fetchedAt,
      });
    }
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} screening lines not understood, or with a weekday that fits no date`,
    });
  }

  return {
    provider: providerOf(site, "custom", "reserve"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: [toVenue(P, venue, venue.slug)],
    auditoriums: [],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
