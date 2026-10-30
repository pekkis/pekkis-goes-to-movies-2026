import {
  makeId,
  type FilmListing,
  type ProviderBatch,
  type RawLabel,
  type Screening,
  type ScreeningTag,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import { COMMON_TITLE_PREFIXES, labelEffects, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, finnishRating, plainText, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { NuorisokuvatRawSnapshot } from "./fetch.ts";
import type { NuorisokuvatSite } from "./sites.ts";

const WEEKDAYS = ["ma", "ti", "ke", "to", "pe", "la", "su"];
/** One show of a freehand list: "la 31.10. klo 15", "su 1.11 klo 18", or a bare "ke 4.11.". */
const SHOW =
  /^(ma|ti|ke|to|pe|la|su)\s+(\d{1,2})\.(\d{1,2})\.?(?:\s+klo\s+(\d{1,2})(?:[.:](\d{2}))?)?$/i;
/** "1 h 20 min", "1h 27 min", "1 h 44min". */
const RUNTIME = /^(\d)\s*h\s*(\d{1,2})\s*min$/i;
const PRICE = /^(\d{1,3}(?:[.,]\d{1,2})?)\s*€$/;
const FREE = /\bilmai/i;
const DUBBED = /^(?:puhuttu suomeksi|suomeksi puhuttu versio)\.?$/i;
const DESCRIBED = /^kuvailutulkattu versio\.?$/i;

type Show = { month: number; day: number; weekday: string; hour?: number; minute?: number };

/**
 * "la 31.10. klo 15 ja su 1.11 klo 18" -> two shows; "ke 4.11. ja to 5.11. klo 18" -> two at
 * 18. A day without a time takes the next one's. Undefined if any part is not understood.
 */
export const parseShows = (text: string): Show[] | undefined => {
  const parts = text
    .split(/\s*(?:,|\bja\b)\s*/i)
    .map((p) => p.trim())
    .filter(Boolean);
  const shows: Show[] = [];
  for (const part of parts) {
    const m = part.match(SHOW);
    if (!m) {
      return undefined;
    }
    shows.push({
      weekday: m[1]!.toLowerCase(),
      day: Number(m[2]),
      month: Number(m[3]),
      ...(m[4] !== undefined && { hour: Number(m[4]), minute: Number(m[5] ?? 0) }),
    });
  }
  for (let i = shows.length - 2; i >= 0; i--) {
    const next = shows[i + 1]!;
    if (shows[i]!.hour === undefined && next.hour !== undefined) {
      shows[i] = { ...shows[i]!, hour: next.hour, minute: next.minute ?? 0 };
    }
  }
  return shows.every((s) => s.hour !== undefined) ? shows : undefined;
};

/** Pure: the films page + site config -> normalized batch. */
export const parseNuorisokuvat = (
  raw: NuorisokuvatRawSnapshot,
  site: NuorisokuvatSite,
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
  const films = $("div.elokuvat > div.elokuva").toArray();
  if (films.length === 0) {
    warnings.push({ code: "invalid-response", message: "No films on the films page" });
  }
  let unreadable = 0;
  for (const film of films) {
    // The labelled facts: "<span class="bold">Kesto:</span> 1 h 20 min".
    const facts = new Map(
      $(film)
        .find("p")
        .toArray()
        .flatMap((p) => {
          const label = plainText($(p).children("span.bold").first().text());
          return label
            ? [[label.replace(/:$/, ""), plainText($(p).text()).slice(label.length).trim()]]
            : [];
        }) as [string, string][],
    );
    const showText = facts.get("Näytökset") ?? "";
    if (!showText) {
      continue; // on the page, but no shows
    }
    const rawTitle = plainText($(film).find("h3").first().text());
    const shows = parseShows(showText);
    if (!rawTitle || !shows) {
      unreadable += 1;
      continue;
    }
    const lines = $(film)
      .find("p")
      .toArray()
      .flatMap((p) => {
        // Only <br> ends a line: other whitespace in the markup is just space.
        $(p).find("br").replaceWith("\u2028");
        return $(p).text().split("\u2028").map(plainText);
      });
    const dubbed = lines.some((l) => DUBBED.test(l));
    const runtimeMatch = (facts.get("Kesto") ?? "").match(RUNTIME);
    const runtime = runtimeMatch ? Number(runtimeMatch[1]) * 60 + Number(runtimeMatch[2]) : 0;
    const age = facts.get("Ikäraja");
    const rating = age ? finnishRating(age) : undefined;
    const priceText = facts.get("Liput") ?? "";
    const price = toCents(priceText.match(PRICE)?.[1], { zeroIsFree: false });
    const tags: ScreeningTag[] = [
      ...(FREE.test(priceText) ? (["free"] as const) : []),
      ...(lines.some((l) => DESCRIBED.test(l)) ? (["audio-description"] as const) : []),
    ];
    const unmapped = [
      ...(age && !rating ? [`rating:${age}`] : []),
      ...(priceText && price === undefined && !FREE.test(priceText) ? [`price:${priceText}`] : []),
    ];
    const { title: unprefixed, rule, label } = splitTitlePrefix(rawTitle, prefixRules);
    const effects = labelEffects([rule]);
    const { title, version } = splitVersion(unprefixed);
    const labels: RawLabel[] = label ? [{ source: "title.prefix", text: label }] : [];
    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);
    const ticketUrl =
      $(film)
        .find("a")
        .filter((_, a) => /osta liput/i.test($(a).text()))
        .first()
        .attr("href") ?? site.programme;

    for (const show of shows) {
      const date = nearestDate(show.day, show.month, raw.from);
      // The weekday is the only check on the year we infer.
      const fits = date && WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] === show.weekday;
      const start =
        date &&
        fits &&
        helsinkiShowTime({
          year: Number(date.slice(0, 4)),
          month: show.month,
          day: show.day,
          hour: show.hour!,
          minute: show.minute!,
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
          kind: effects.event ? "event" : "film",
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
        tags: [...new Set([...effects.tags, ...tags])],
        series: effects.series,
        availability: "unknown",
        ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
        ticketUrl,
        unmappedLabels: unmapped,
        ...(labels.length > 0 && { labels }),
        fetchedAt: raw.fetchedAt,
      });
    }
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} shows not understood, or with a weekday that fits no date`,
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
