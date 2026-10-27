import {
  makeId,
  type FilmListing,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion, type Version } from "../labels.ts";
import { byStartThenId, eachStartTime, plainText, slugify } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { KirkkonummiRawSnapshot } from "./fetch.ts";
import type { KirkkonummiSite } from "./sites.ts";

/** Weekdays as written, full or short: "Perjantai", "Pe". */
const WEEKDAYS = ["ma", "ti", "ke", "to", "pe", "la", "su"];
const FULL = [
  "maanantai",
  "tiistai",
  "keskiviikko",
  "torstai",
  "perjantai",
  "lauantai",
  "sunnuntai",
];
/** "16.10. Perjantai klo18.00", "14.10. Ke klo13.30!" */
const SHOW = /^(\d{1,2})\.(\d{1,2})\.?\s+([a-zäö]+)\s+klo\s*(\d{1,2})[.:](\d{2})!?$/i;
/** Only rows that look like a screening are read; cast lists and notes are not. */
const LOOKS_LIKE_SHOW = /^\d{1,2}\.\d{1,2}\.?\s+[a-zäö]+\s+klo/i;

const weekdayIndex = (word: string) => {
  const w = word.toLowerCase();
  const i = FULL.indexOf(w);
  return i >= 0 ? i : WEEKDAYS.indexOf(w);
};

/** Pure: the page + site config -> normalized batch. */
export const parseKirkkonummi = (
  raw: KirkkonummiRawSnapshot,
  site: KirkkonummiSite,
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
  // Headings and list rows in document order: a row belongs to the last heading.
  const nodes = $(".elementor-heading-title, .elementor-icon-list-text").toArray();
  if (nodes.length === 0) {
    warnings.push({ code: "invalid-response", message: "No Elementor headings on the page" });
  }
  type Row = { heading: string; show: string };
  const rows: Row[] = [];
  /** "Puhumme suomea" under a film: a version for all its screenings. */
  const notes = new Map<string, Version>();
  let heading = "";
  for (const el of nodes) {
    const value = plainText($(el).text());
    if ($(el).hasClass("elementor-heading-title")) {
      heading = value;
      continue;
    }
    if (LOOKS_LIKE_SHOW.test(value)) {
      rows.push(
        ...value
          .split(/\s+\/\s+/)
          .flatMap(eachStartTime)
          .map((show) => ({ heading, show })),
      );
      continue;
    }
    const { title, version } = splitVersion(`x (${value})`);
    if (title === "x" && (version.audio || version.dubbed !== undefined)) {
      notes.set(heading, version);
    }
  }

  let unreadable = 0;
  for (const { heading: rawHeading, show } of rows) {
    const m = show.match(SHOW);
    const date = m ? nearestDate(Number(m[1]), Number(m[2]), raw.from) : undefined;
    const weekday = m ? weekdayIndex(m[3]!) : -1;
    const start =
      m &&
      date &&
      // The weekday is the only check on the year we infer.
      weekday === Temporal.PlainDate.from(date).dayOfWeek - 1 &&
      helsinkiShowTime({
        year: Number(date.slice(0, 4)),
        month: Number(m[2]),
        day: Number(m[1]),
        hour: Number(m[4]),
        minute: Number(m[5]),
      });
    if (!start || !rawHeading) {
      unreadable += 1;
      continue;
    }
    if (start.businessDate < window.from || start.businessDate > window.to) {
      continue;
    }
    // "Matka Piemonteen / Resan till Piemonte": Finnish, then Swedish.
    const [fi, sv] = rawHeading.split(/\s+\/\s+/);
    const { title: unprefixed, rule } = splitTitlePrefix(fi!, prefixRules);
    const { title, version: titleVersion } = splitVersion(unprefixed);
    const version = { ...notes.get(rawHeading), ...titleVersion };
    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);
    if (!listings.has(listingId)) {
      listings.set(listingId, {
        id: listingId,
        provider: P,
        sourceId: filmKey,
        title: { fi: title, ...(sv && { sv }) },
        genres: [],
        countries: [],
        kind: rule?.event ? "event" : "film",
      });
    }
    // Each block is on the page twice; the same film and minute is one screening.
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
      // One page, reservations by phone: the page is the link.
      ticketUrl: `${site.homepage}/`,
      unmappedLabels: [],
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
