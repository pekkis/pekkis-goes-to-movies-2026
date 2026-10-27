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
import type { VaakunaRawSnapshot } from "./fetch.ts";
import type { VaakunaSite } from "./sites.ts";

const WEEKDAYS = ["MA", "TI", "KE", "TO", "PE", "LA", "SU"];
/**
 * "Ti 20.10. klo 14:40", "Ke 14.10. klo 14:10 (dub)", "ENNAKKO Ensi-ilta 31.10. klo 19:30":
 * labels, an optional weekday, the date, the time and a version marker.
 */
const ROW =
  /^((?:(?:ennakko|ensi-ilta)\s+)*)(?:(ma|ti|ke|to|pe|la|su)\s+)?(\d{1,2})\.(\d{1,2})\.?\s+klo\s+(\d{1,2})[:.](\d{2})(?:\s*(\([^()]+\)))?$/i;
/** Labels before a row's date. */
const ROW_TAGS = { ennakko: "preview", "ensi-ilta": "premiere" } as const;
/** "1 h 42 min" */
const DURATION = /(?:(\d+)\s*h)?\s*(\d+)\s*min/i;
/** "Liput: 13 €", "Liput: 15€ (lahja/sarjalippu +2€)": the first amount is the ticket. */
const PRICE = /^Liput:\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*€/i;
/** The age-limit icon is named after the limit: ".../icon/16.png", ".../icon/s.png". */
const AGE_ICON = /\/icon\/(s|7|12|16|18)\.png$/i;

/** Pure: the front page + site config -> normalized batch. */
export const parseVaakuna = (raw: VaakunaRawSnapshot, site: VaakunaSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  const cards = $("div.MovieCard").toArray();
  if (cards.length === 0) {
    warnings.push({ code: "invalid-response", message: "No film cards on the front page" });
  }
  let unreadable = 0;
  for (const el of cards) {
    const card = $(el);
    const rawTitle = plainText(card.find("h2").first().text());
    const link = card.find("a.MovieCard__PosterLink").attr("href") ?? "";
    // The film page's name is the film's id: ".../elokuvat/the-odyssey.html".
    const filmId = link.match(/\/elokuvat\/([^/]+)\.html$/)?.[1] ?? slugify(rawTitle);
    if (!rawTitle) {
      continue;
    }
    const facts = card
      .find("li")
      .toArray()
      .map((li) => ({ text: plainText($(li).text()), icon: $(li).find("img").attr("src") }));
    const ageIcon = facts.find((f) => /^Ikäraja/i.test(f.text))?.icon;
    const age = ageIcon?.match(AGE_ICON)?.[1];
    const rating = age ? finnishRating(age.toUpperCase()) : undefined;
    const cardUnmapped = ageIcon && !rating ? [`rating:${ageIcon.split("/").at(-1)}`] : [];
    const duration = facts.find((f) => /^Kesto/i.test(f.text))?.text.match(DURATION);
    const runtime = duration ? Number(duration[1] ?? 0) * 60 + Number(duration[2]) : 0;
    const amount = facts.map((f) => f.text.match(PRICE)?.[1]).find(Boolean);
    const price = toCents(amount, { zeroIsFree: false });

    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const listingId = makeId(P, "film", filmId);

    for (const td of card.find("td").toArray()) {
      const row = plainText($(td).text());
      if (!/\bklo\b/i.test(row)) {
        continue; // "Ensi-ilta 30.10.2026": an opening day, no screening time yet
      }
      const m = row.match(ROW);
      const date = m ? nearestDate(Number(m[3]), Number(m[4]), raw.from) : undefined;
      const weekday = date ? WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] : undefined;
      const start =
        m &&
        date &&
        // The weekday, when given, is the check on the year we infer.
        (!m[2] || weekday === m[2].toUpperCase()) &&
        helsinkiShowTime({
          year: Number(date.slice(0, 4)),
          month: Number(m[4]),
          day: Number(m[3]),
          hour: Number(m[5]),
          minute: Number(m[6]),
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
          sourceId: filmId,
          title: { fi: title },
          ...(runtime > 0 && { runtimeMinutes: runtime }),
          ...(rating && { rating }),
          genres: [],
          countries: [],
          kind: rule?.event ? "event" : "film",
        });
      }
      const unmapped = [...cardUnmapped];
      const rowTags = (m[1] ?? "")
        .toLowerCase()
        .split(/\s+/)
        .flatMap((label) => (label in ROW_TAGS ? [ROW_TAGS[label as keyof typeof ROW_TAGS]] : []));
      // A marker on the row is this screening's version: "(dub)".
      const rowVersion = m[7] ? splitVersion(`x ${m[7]}`).version : {};
      const audio = rowVersion.audio ?? version.audio;
      const dubbed = rowVersion.dubbed ?? version.dubbed;
      if (m[7] && rowVersion.audio === undefined && rowVersion.dubbed === undefined) {
        unmapped.push(`version:${m[7]}`);
      }
      const sourceId = `${filmId}-${start.startsAt.slice(0, 16).replace(/[-T:]/g, "")}`;
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
        ...(dubbed !== undefined && { dubbed }),
        subtitles: { kind: "unknown" },
        tags: [...new Set([...(rule?.tags ?? []), ...rowTags])],
        series: rule?.series ? [rule.series] : [],
        availability: "unknown",
        ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
        // "Varaa liput" leads to the film's page; reservations by phone or email.
        ticketUrl: link.startsWith(`${site.homepage}/`) ? link : site.programme,
        unmappedLabels: [...unmapped],
        fetchedAt: raw.fetchedAt,
      });
    }
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} screening rows not understood, or with a weekday that fits no date`,
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
