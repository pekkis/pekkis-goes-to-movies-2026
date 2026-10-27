import {
  makeId,
  type FilmListing,
  type FinnishRating,
  type Lang,
  type ProviderBatch,
  type RawLabel,
  type Screening,
  type Subtitles,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate, type ShowTime } from "@pgtm/model/time";
import { load } from "cheerio";
import { normalizeLang } from "../../lib/lang.ts";
import { own } from "../../lib/records.ts";
import {
  COMMON_TITLE_PREFIXES,
  labelEffects,
  type LabelRule,
  splitTitlePrefix,
  splitVersion,
} from "../labels.ts";
import { byStartThenId, plainText, slugify } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { KuvakukkoRawSnapshot } from "./fetch.ts";
import type { KuvakukkoSite } from "./sites.ts";

const WEEKDAYS = [
  "maanantai",
  "tiistai",
  "keskiviikko",
  "torstai",
  "perjantai",
  "lauantai",
  "sunnuntai",
];

/** "Keskiviikko 14.10." */
const DAY = /^([a-zäö]+)\s+(\d{1,2})\.(\d{1,2})\.?$/i;
/** "Klo 13: …", "Klo 17.30: …" */
const ROW = /^klo\s*(\d{1,2})(?:[.:](\d{2}))?\s*:\s*(.*)$/i;
const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  "K-7": "K-7",
  "K-12": "K-12",
  "K-16": "K-16",
  "K-18": "K-18",
};

/** A link to a page, not to an uploaded image. */
const IMAGE = /\.(?:jpe?g|png|gif|webp)$/i;

type Note = { text: string; rule: LabelRule };

/** Splits off a trailing note in parentheses (closed or not) that opens with a configured word. */
const splitNote = (
  title: string,
  notes: Record<string, LabelRule>,
): { title: string; note?: Note } => {
  const open = title.lastIndexOf("(");
  if (open < 0) {
    return { title };
  }
  const inner = title
    .slice(open + 1)
    .replace(/\)\s*$/, "")
    .trim();
  const word = Object.keys(notes).find((n) => inner.toLowerCase().startsWith(n.toLowerCase()));
  return word
    ? { title: title.slice(0, open).trim(), note: { text: inner, rule: notes[word]! } }
    : { title };
};

type Row = {
  venue: KuvakukkoSite["venues"][number];
  /** As printed, notes dropped. */
  rawTitle: string;
  /** A note in parentheses, in the title or after the linked title. */
  note?: Note;
  start: ShowTime;
  /** The row's link to a film page on this site, when it has one. */
  href?: string;
};

/** Both cinemas' rows, each under its own heading. Shared by the fetch and the parser. */
const readRows = (html: string, site: KuvakukkoSite, from: string) => {
  const warnings: Warning[] = [];
  const rows: Row[] = [];
  const $ = load(html);
  const headings = $("h2").toArray();
  for (const venue of site.venues) {
    const heading = headings.find((h) => {
      const title = plainText($(h).text()).toLowerCase();
      return title.includes(venue.heading) && title.includes("esitysaikataulu");
    });
    if (!heading) {
      warnings.push({
        code: "invalid-response",
        message: `No schedule heading for ${venue.name}`,
        context: { venue: venue.slug },
      });
      continue;
    }
    // Everything up to the next heading is this cinema's; a paragraph may hold several days.
    const lines = $(heading)
      .nextUntil("h2")
      .filter("p")
      .toArray()
      .flatMap((p) => ($(p).html() ?? "").split(/<br\s*\/?>/i));

    let date: string | undefined;
    for (const line of lines) {
      const fragment = load(line, null, false);
      const lineText = plainText(fragment.text());
      const day = lineText.match(DAY);
      if (day && WEEKDAYS.includes(day[1]!.toLowerCase())) {
        date = nearestDate(Number(day[2]), Number(day[3]), from);
        const weekday = date ? WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] : undefined;
        if (weekday !== day[1]!.toLowerCase()) {
          // The weekday is the only check on the year we infer: a mismatch places nothing.
          warnings.push({
            code: "invalid-start",
            message: `Day "${lineText}" has no matching date near ${from}`,
            context: { venue: venue.slug },
          });
          date = undefined;
        }
        continue;
      }
      const row = lineText.match(ROW);
      if (!row) {
        continue; // prices, addresses, "next week's programme is published on Tuesday"
      }
      // The first link with text is the title (an empty link sometimes precedes it);
      // unlinked rows are the whole rest of the line.
      const link = fragment("a")
        .toArray()
        .find((a) => plainText(fragment(a).text()));
      const { title: rawTitle, note: titleNote } = splitNote(
        link ? plainText(fragment(link).text()) : plainText(row[3]),
        site.titleNotes,
      );
      const note =
        titleNote ?? (link ? splitNote(plainText(row[3]), site.titleNotes).note : undefined);
      const href = link ? fragment(link).attr("href") : undefined;
      const start =
        date &&
        helsinkiShowTime({
          year: Number(date.slice(0, 4)),
          month: Number(date.slice(5, 7)),
          day: Number(date.slice(8, 10)),
          hour: Number(row[1]),
          minute: Number(row[2] ?? 0),
        });
      if (!rawTitle || !start) {
        warnings.push({
          code: "invalid-row",
          message: `Unreadable row "${lineText}"${date ? "" : " (no day before it)"}`,
          context: { venue: venue.slug },
        });
        continue;
      }
      rows.push({
        venue,
        rawTitle,
        ...(note && { note }),
        start,
        ...(href?.startsWith(`${site.homepage}/`) && !IMAGE.test(href) && { href }),
      });
    }
  }
  return { rows, warnings };
};

const inWindow = (rows: Row[], from: string, days: number) => {
  const window = dateWindow(from, days);
  return rows.filter(
    (r) => r.start.businessDate >= window.from && r.start.businessDate <= window.to,
  );
};

/** The film pages to read: each linked title's first page in the window. */
export const filmPages = (html: string, site: KuvakukkoSite, from: string, days: number) => {
  const pages = new Map<string, string>();
  for (const row of inWindow(readRows(html, site, from).rows, from, days)) {
    if (row.href && !pages.has(row.rawTitle)) {
      pages.set(row.rawTitle, row.href);
    }
  }
  return [...new Set(pages.values())].toSorted();
};

type Details = {
  /** The page's own `<h1>`: its facts count only for the film it names. */
  heading: string;
  year?: number;
  runtime?: number;
  rating?: FinnishRating;
  audio?: Lang[];
  subtitles?: Subtitles;
  unmapped: string[];
};

/** A title as compared with a page's heading: no case, no version marker, one space. */
const comparable = (title: string, site: KuvakukkoSite) =>
  splitVersion(
    splitTitlePrefix(title, { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes }).title,
  ).title.toLowerCase();

const languages = (value: string, unmapped: string[], role: string) => {
  const names = value
    .split(/[/,]| ja /)
    .map((n) => n.trim())
    .filter(Boolean);
  const codes = names.map(normalizeLang);
  if (names.length === 0 || !codes.every(Boolean)) {
    unmapped.push(`${role}:${value}`);
    return undefined;
  }
  return [...new Set(codes as Lang[])];
};

/**
 * A film page's facts line: "Italia 2025 • draama • 133 min • K7 • kieli: italia •
 * tekstitys: suomi/ruotsi". Exactly one line with a runtime and only short segments, or
 * nothing: a quoted paragraph can run into the line.
 */
const detailsOf = (html: string, site: KuvakukkoSite): Details => {
  const $ = load(html);
  const heading = comparable(plainText($("h1").first().text()), site);
  const unmapped: string[] = [];
  const candidates = ($("body").html() ?? "")
    .split(/<br\s*\/?>|<\/?(?:p|li|div|h\d)\b[^>]*>/i)
    .map((chunk) =>
      plainText(load(chunk, null, false).text())
        .split("•")
        .map((s) => s.trim()),
    )
    .filter(
      (segments) =>
        segments.some((s) => /^\d{2,3}\s*min$/i.test(s)) && segments.every((s) => s.length <= 80),
    );
  if (candidates.length !== 1) {
    return { heading, unmapped };
  }
  const details: Details = { heading, unmapped };
  for (const segment of candidates[0]!) {
    const runtime = segment.match(/^(\d{2,3})\s*min$/i);
    const age = segment.match(/^(?:K\s?(\d{1,2})|S)$/i);
    const label = segment.match(/^(kieli|tekstitys)\s*:\s*(.+)$/i);
    const year = segment.match(/\b((?:19|20)\d{2})$/);
    if (runtime) {
      details.runtime = Number(runtime[1]);
    } else if (age) {
      const rating = own(RATINGS, age[1] ? `K-${Number(age[1])}` : "S");
      if (rating) {
        details.rating = rating;
      } else {
        unmapped.push(`rating:${segment}`);
      }
    } else if (label?.[1]!.toLowerCase() === "kieli") {
      const codes = languages(label[2]!, unmapped, "audio");
      if (codes) {
        details.audio = codes;
      }
    } else if (label && /^[–-]$/.test(label[2]!.trim())) {
      // "tekstitys: –": not stated, so unknown rather than "none".
    } else if (label) {
      const codes = languages(label[2]!, unmapped, "subtitles");
      if (codes) {
        details.subtitles = { kind: "languages", languages: codes };
      }
    } else if (year && segment === candidates[0]![0]) {
      // The first segment is the countries and the year: "Yhdysvallat – Kanada 2026".
      details.year = Number(year[1]);
    }
  }
  return details;
};

/** Pure: the programme page + film pages + site config -> normalized batch. */
export const parseKuvakukko = (raw: KuvakukkoRawSnapshot, site: KuvakukkoSite): ProviderBatch => {
  const P = site.provider;
  const window = dateWindow(raw.from, raw.days);
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const { rows, warnings } = readRows(raw.html, site, raw.from);
  const details = new Map<string, Details>();
  for (const [url, html] of Object.entries(raw.films)) {
    if (html === null) {
      warnings.push({
        code: "film-page-missing",
        message: "Film page unreadable; the film's details stay unknown",
        context: { url },
      });
      continue;
    }
    details.set(url, detailsOf(html, site));
  }

  for (const row of inWindow(rows, raw.from, raw.days)) {
    const { venue, rawTitle, start, note } = row;
    const venueId = makeId(P, "venue", venue.slug);
    const { title: unprefixed, rule, label } = splitTitlePrefix(rawTitle, prefixRules);
    const effects = labelEffects([rule, note?.rule]);
    const labels: RawLabel[] = [
      ...(label ? [{ source: "title.prefix", text: label }] : []),
      ...(note ? [{ source: "title.note", text: note.text }] : []),
    ];
    const { title, version } = splitVersion(unprefixed);
    // Pages are reused for other films (`/the-invite/` holds La Grazia): a page counts
    // only when its heading names this row's film.
    const page = row.href ? details.get(row.href) : undefined;
    const film = page?.heading === title.toLowerCase() ? page : undefined;

    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);
    if (!listings.has(listingId) || (film && !listings.get(listingId)!.runtimeMinutes)) {
      listings.set(listingId, {
        id: listingId,
        provider: P,
        sourceId: filmKey,
        title: { fi: title },
        ...(film?.year && { year: film.year }),
        ...(film?.runtime && { runtimeMinutes: film.runtime }),
        ...(film?.rating && { rating: film.rating }),
        genres: [],
        countries: [],
        kind: effects.event ? "event" : "film",
      });
    }
    // No ids on the page: venue, film and start minute.
    const sourceId = `${venue.slug}-${filmKey}-${start.startsAt.slice(0, 16).replace(/[-T:]/g, "")}`;
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
      audio: version.audio ? [version.audio] : (film?.audio ?? []),
      ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
      subtitles: film?.subtitles ?? { kind: "unknown" },
      tags: effects.tags,
      series: effects.series,
      availability: "unknown",
      // Tickets are sold at the door; the programme is the page to send people to. The
      // rows' own links are not used for this: they often point at another film's page.
      ticketUrl: site.programme,
      unmappedLabels: [...(film?.unmapped ?? [])],
      ...(labels.length > 0 && { labels }),
      fetchedAt: raw.fetchedAt,
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
