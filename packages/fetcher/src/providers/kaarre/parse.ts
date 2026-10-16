import {
  makeId,
  type FilmListing,
  type FinnishRating,
  type ProviderBatch,
  type Screening,
  type RawLabel,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import { own } from "../../lib/records.ts";
import {
  COMMON_TITLE_PREFIXES,
  findLabel,
  LABELS,
  labelEffects,
  splitTitlePrefix,
  splitVersion,
} from "../labels.ts";
import { byStartThenId, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { KaarreRawSnapshot } from "./fetch.ts";
import type { KaarreSite } from "./sites.ts";

const WEEKDAYS = ["ma", "ti", "ke", "to", "pe", "la", "su"];
/** "Pe 9.10. klo 18", "Su 18.10. klo 15.30 kiirehdi!". */
const ROW =
  /^(ma|ti|ke|to|pe|la|su)\s+(\d{1,2})\.(\d{1,2})\.?\s+klo\s+(\d{1,2})(?:[.:](\d{2}))?\b\s*(.*)$/i;
const ROWISH = /^(ma|ti|ke|to|pe|la|su)\s+\d/i;
/** "Ikäraja K7, liput 10 €, kesto 1 h 27 min". */
const AGE = /Ikäraja\s+(-S-|S\b|K-?\d{1,2}\b)/i;
const PRICE = /liput\s+(\d{1,3}(?:[.,]\d{1,2})?)\s*€/i;
const RUNTIME = /kesto\s+(\d+)\s*h\s*(\d+)\s*min/i;
const DUBBED = /\bdub\.?\s+suomeksi\b/i;
const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  K7: "K-7",
  K12: "K-12",
  K16: "K-16",
  K18: "K-18",
};

const text = (value: string | undefined) => (value ?? "").replace(/\s+/g, " ").trim();

/** Pure: the cinema page + site config -> normalized batch. */
export const parseKaarre = (raw: KaarreRawSnapshot, site: KaarreSite): ProviderBatch => {
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
    .find((el) => /viikon elokuvaesitysten/i.test($(el).text()));
  if (!heading) {
    warnings.push({ code: "invalid-response", message: "No weekly programme heading on the page" });
  }
  // The programme's paragraphs run from the heading to the next heading.
  const paragraphs = heading ? $(heading).nextUntil("h2", "p").toArray() : [];
  let unreadable = 0;
  for (const el of paragraphs) {
    const p = $(el);
    const rawTitle = text(p.find("strong").first().text());
    const lines = (p.html() ?? "")
      .split(/<br\s*\/?>/i)
      .map((chunk) => text(load(chunk, null, false).text()))
      .filter(Boolean);
    const rows = lines.filter((l) => ROWISH.test(l));
    if (rows.length === 0) {
      continue; // notes (ticket sales, hashtags)
    }
    if (!rawTitle) {
      unreadable += rows.length;
      continue;
    }
    const facts = lines.join(" ");
    const age = facts.match(AGE)?.[1]?.toUpperCase().replace(/^-S-$/, "S").replace("-", "");
    const rating = age ? own(RATINGS, age) : undefined;
    const unmapped = age && !rating ? [`rating:${age}`] : [];
    const duration = facts.match(RUNTIME);
    const runtime = duration ? Number(duration[1]) * 60 + Number(duration[2]) : 0;
    const price = toCents(facts.match(PRICE)?.[1], { zeroIsFree: false });
    const dubbed = DUBBED.test(facts);

    const { title: unprefixed, rule, label } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);
    for (const line of rows) {
      const m = line.match(ROW);
      const date = m ? nearestDate(Number(m[2]), Number(m[3]), raw.from) : undefined;
      const fits =
        date && WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] === m![1]!.toLowerCase();
      const start =
        m &&
        date &&
        fits &&
        helsinkiShowTime({
          year: Number(date.slice(0, 4)),
          month: Number(m[3]),
          day: Number(m[2]),
          hour: Number(m[4]),
          minute: Number(m[5] ?? 0),
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
          kind: rule?.event ? "event" : "film",
        });
      }
      // The rest of the line is a note: "kiirehdi!", "viimeinen näytös".
      const note = m[6]?.trim() ?? "";
      const noteRule = note ? findLabel(note, LABELS) : undefined;
      const rowUnmapped = note && !noteRule ? [...unmapped, `note:${note}`] : unmapped;
      const effects = labelEffects([rule, noteRule]);
      const labels: RawLabel[] = [
        ...(label ? [{ source: "title.prefix", text: label }] : []),
        ...(note ? [{ source: "row.note", text: note }] : []),
      ];
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
        tags: effects.tags,
        series: effects.series,
        availability: effects.availability ?? "unknown",
        ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
        // Tickets at the door: the cinema's page.
        ticketUrl: site.programme,
        unmappedLabels: rowUnmapped,
        ...(labels.length > 0 && { labels }),
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
