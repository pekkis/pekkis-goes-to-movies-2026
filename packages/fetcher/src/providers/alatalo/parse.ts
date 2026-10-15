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
import { byStartThenId, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { AlataloRawSnapshot } from "./fetch.ts";
import type { AlataloSite } from "./sites.ts";

/** Weekdays by their first two letters: the words are often misspelt past those. */
const WEEKDAYS = ["ma", "ti", "ke", "to", "pe", "la", "su"];
/** "Lauantaina 17.10", "Sunnuntaina 1.11", "Tiistaina 2.1.2024". */
const DATE = /^([a-zäö]{5,}?)\s+(\d{1,2})\.(\d{1,2})\.?(?:(\d{4}))?\.?$/i;
/** "Klo 14.00 Title", "Klo 13.00", "16.30 Title", "Kl 18.00 Title". */
const ROW = /^(?:kl(?:o)?\.?\s*)?(\d{1,2})[.:](\d{2})!?(?:\s+(.*))?$/i;
/** A rating marker closing a title: "-k16/13-", "k16/13", "-s-", "-k6/13". */
const MARKER = /\s*-?\s*(?:k\s?-?\s?(\d{1,2})(?:\s*\/\s*-?\s*\d{1,2})?|(s))\s*-?$/i;
/** A line that is only a marker. */
const BARE_MARKER = /^-?\s*(?:k\s?-?\s?\d{1,2}(?:\s*\/\s*-?\s*\d{1,2})?|s)\s*-?$/i;
const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  "7": "K-7",
  "12": "K-12",
  "16": "K-16",
  "18": "K-18",
};

const text = (value: string | undefined) => (value ?? "").replace(/\s+/g, " ").trim();

type Row = {
  time: [number, number];
  title: string;
  marker?: string;
  dates: string[];
  venueSlug: string;
};

/** The marker's rating text ("16", "S"), and the title without it. */
const splitMarker = (title: string) => {
  const m = title.match(MARKER);
  if (!m || BARE_MARKER.test(title)) {
    return BARE_MARKER.test(title)
      ? { title: "", marker: (title.match(/(\d{1,2})/)?.[1] ?? "S").toUpperCase() }
      : { title };
  }
  return { title: title.slice(0, m.index).trim(), marker: (m[1] ?? m[2] ?? "").toUpperCase() };
};

/** Pure: the programme + site config -> normalized batch. */
export const parseAlatalo = (raw: AlataloRawSnapshot, site: AlataloSite): ProviderBatch => {
  const P = site.provider;
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  $("script, style").remove();
  const lines = ($("body").html() ?? raw.html)
    .split(/<br\s*\/?>|<\/?(?:p|div|li|h\d|tr|td|span|table|tbody|ul|ol)\b[^>]*>/i)
    .map((chunk) => text(load(chunk, null, false).text()))
    .filter(Boolean);
  const priceText = lines.join(" ");
  const price = site.pricePattern
    ? toCents(priceText.match(new RegExp(site.pricePattern, "i"))?.[1], { zeroIsFree: false })
    : undefined;

  const single = site.venues.length === 1 && !site.venues[0]!.heading;
  let venueSlug: string | undefined = single ? site.venues[0]!.slug : undefined;
  let dates: string[] = [];
  let datesUsed = false;
  const rows: Row[] = [];
  let open: Row[] = []; // rows still waiting for a title or a marker
  let unreadable = 0;
  const unclaimed = new Map<string, number>();

  const close = () => {
    for (const r of open) {
      if (r.title) {
        rows.push(r);
      } else {
        unreadable += 1;
      }
    }
    open = [];
  };

  lines.forEach((line, i) => {
    const date = line.match(DATE);
    const weekday = date ? WEEKDAYS.indexOf(date[1]!.slice(0, 2).toLowerCase()) : -1;
    if (date && weekday >= 0) {
      close();
      const iso = date[4]
        ? `${date[4]}-${date[3]!.padStart(2, "0")}-${date[2]!.padStart(2, "0")}`
        : nearestDate(Number(date[2]), Number(date[3]), raw.from);
      const fits = iso && Temporal.PlainDate.from(iso).dayOfWeek - 1 === weekday;
      // Consecutive date headings share the rows below them.
      if (datesUsed) {
        dates = [];
        datesUsed = false;
      }
      if (fits) {
        dates.push(iso);
      } else {
        unreadable += 1;
      }
      return;
    }
    const venue = site.venues.find(
      (v) => v.heading && line.toLowerCase().startsWith(v.heading.toLowerCase()),
    );
    if (venue) {
      close();
      venueSlug = venue.slug;
      dates = [];
      return;
    }
    // A line followed by a date heading is a town heading; one we do not know clears the venue.
    if (!single && !ROW.test(line) && DATE.test(lines[i + 1] ?? "")) {
      close();
      venueSlug = undefined;
      const town = line.match(/^[A-ZÄÖ][a-zäö]{3,19}/)?.[0] ?? "?";
      unclaimed.set(town, (unclaimed.get(town) ?? 0) + 0);
      dates = [];
      return;
    }
    const row = line.match(ROW);
    if (row) {
      // Unmarked rows stay open: a bare marker below may close several of one film.
      if (MARKER.test(text(row[3])) || open.some((r) => !r.title)) {
        close();
      }
      datesUsed = true;
      if (!venueSlug) {
        const town = [...unclaimed.keys()].at(-1) ?? "?";
        unclaimed.set(town, (unclaimed.get(town) ?? 0) + 1);
        return;
      }
      const { title, marker } = splitMarker(text(row[3]));
      const r: Row = {
        time: [Number(row[1]), Number(row[2])],
        title,
        dates: [...dates],
        venueSlug,
        ...(marker && { marker }),
      };
      if (marker) {
        rows.push(r);
      } else {
        open.push(r);
      }
      return;
    }
    if (open.length === 0) {
      return; // notes, prices, decorations
    }
    const { title, marker } = splitMarker(line);
    const last = open.at(-1)!;
    if (!title && marker) {
      // A bare marker closes the unmarked rows of one film directly above it.
      for (const r of open) {
        if (r.title && r.title.toLowerCase() === last.title.toLowerCase()) {
          r.marker = marker;
        }
      }
      close();
    } else if (marker || !last.title) {
      // A continuation: the row's title runs onto this line.
      last.title = text(`${last.title} ${title}`);
      if (marker) {
        last.marker = marker;
      }
      close();
    }
  });
  close();

  for (const r of rows) {
    const venue = site.venues.find((v) => v.slug === r.venueSlug)!;
    if (r.dates.length === 0) {
      unreadable += 1;
      continue;
    }
    const unmapped: string[] = [];
    const rating = r.marker ? own(RATINGS, r.marker) : undefined;
    if (r.marker && !rating) {
      unmapped.push(`rating:${r.marker}`);
    }
    const { title: unprefixed, rule } = splitTitlePrefix(r.title, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);
    for (const date of r.dates) {
      const start = helsinkiShowTime({
        year: Number(date.slice(0, 4)),
        month: Number(date.slice(5, 7)),
        day: Number(date.slice(8, 10)),
        hour: r.time[0],
        minute: r.time[1],
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
          ...(rating && { rating }),
          genres: [],
          countries: [],
          kind: rule?.event ? "event" : "film",
        });
      }
      const sourceId = `${venue.slug}-${filmKey}-${start.startsAt.slice(0, 16).replace(/[-T:]/g, "")}`;
      const id = makeId(P, "show", sourceId);
      screenings.set(id, {
        id,
        provider: P,
        sourceId,
        venueId: makeId(P, "venue", venue.slug),
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
        // Tickets at the door, cash: the programme page.
        ticketUrl: site.homepage,
        unmappedLabels: unmapped,
        fetchedAt: raw.fetchedAt,
      });
    }
  }

  if (lines.length === 0) {
    warnings.push({ code: "invalid-response", message: "An empty programme page" });
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} lines not placed (no title, no date, or a weekday that fits no date)`,
    });
  }
  for (const [town, shows] of unclaimed) {
    warnings.push({
      code: "unclaimed-venue",
      message: `Town heading "${town}" belongs to no venue (${shows} rows skipped); add it to alatalo/sites.ts`,
      context: { town, shows },
    });
  }

  return {
    provider: providerOf(site, "custom", "door"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: site.venues.map((v) => toVenue(P, v, v.slug)),
    auditoriums: [],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
