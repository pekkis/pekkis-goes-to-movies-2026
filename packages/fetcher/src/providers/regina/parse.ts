import {
  makeId,
  type FilmListing,
  type FinnishRating,
  type Lang,
  type ProviderBatch,
  type Screening,
  type Subtitles,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime } from "@pgtm/model/time";
import { load } from "cheerio";
import { normalizeLang } from "../../lib/lang.ts";
import { own } from "../../lib/records.ts";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { ReginaRawSnapshot } from "./fetch.ts";
import type { ReginaSite } from "./sites.ts";

/** "15-10-2026 17:30": the row's own start, with its year. */
const START = /^(\d{1,2})-(\d{1,2})-(\d{4})\s+(\d{1,2}):(\d{2})$/;
const FILM_ID = /\/elokuva\/(\d+)/;
const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  K7: "K-7",
  K12: "K-12",
  K16: "K-16",
  K18: "K-18",
};
/** "Kopiotieto": the print. */
const PRINTS: Record<string, "digital" | "35mm" | "70mm" | "16mm"> = {
  "35 mm": "35mm",
  "35mm": "35mm",
  "70 mm": "70mm",
  "70mm": "70mm",
  "16 mm": "16mm",
  "16mm": "16mm",
  dcp: "digital",
  "4k dcp": "digital",
  "2k dcp": "digital",
  digitaalinen: "digital",
};

const text = (value: string | undefined) => (value ?? "").replace(/\s+/g, " ").trim();

type Row = { filmId: string; title: string; start: string; ticketUrl?: string };

const rowsOf = (html: string) => {
  const $ = load(html);
  const rows: Row[] = [];
  let unreadable = 0;
  $("div.movie").each((_index, el) => {
    const movie = $(el);
    const link = movie.find("a.title").first();
    const filmId = link.attr("href")?.match(FILM_ID)?.[1];
    const start = text(movie.find(".add-to-calendar .start").text());
    if (!filmId) {
      return; // an event without a film page (Leffavuoro skips these too)
    }
    if (!START.test(start)) {
      unreadable += 1;
      return;
    }
    const ticketUrl = movie.find("a.add-to-cart").attr("href");
    rows.push({ filmId, title: text(link.text()), start, ...(ticketUrl && { ticketUrl }) });
  });
  return { rows, unreadable, found: $("div.day-header").length > 0 || rows.length > 0 };
};

const inWindow = (start: string, from: string, days: number) => {
  const m = start.match(START)!;
  const iso = `${m[3]}-${m[2]!.padStart(2, "0")}-${m[1]!.padStart(2, "0")}`;
  const window = dateWindow(from, days);
  return iso >= window.from && iso <= window.to;
};

/** The film pages to read: every film with a screening in the window. */
export const filmIds = (schedule: string, from: string, days: number) => [
  ...new Set(
    rowsOf(schedule)
      .rows.filter((r) => inWindow(r.start, from, days))
      .map((r) => r.filmId),
  ),
];

type Details = {
  /** From the page's heading, "CASABLANCA (1942)": classics need it to be matched. */
  year?: number;
  runtime?: number;
  countries: string[];
  subtitles?: Subtitles;
  series: string[];
  projection?: "digital" | "35mm" | "70mm" | "16mm";
  rating?: FinnishRating;
  unmapped: string[];
};

/** The film page's details grid: label cells followed by value cells. */
const detailsOf = (html: string): Details => {
  const $ = load(html);
  const fields = new Map<string, ReturnType<typeof $>>();
  $(".movie-details b span").each((_index, el) => {
    const value = $(el).closest("div").next("div");
    fields.set(text($(el).text()).toLowerCase(), value);
  });
  const field = (name: string) => text(fields.get(name)?.text());
  const unmapped: string[] = [];
  const runtime = Number(field("kesto").match(/^(\d{2,3})\s*min/)?.[1] ?? 0);
  const year = Number(
    text($("#main-content h1").first().text()).match(/\((\d{4})\)\s*$/)?.[1] ?? 0,
  );
  // "Espanja/Portugali/Ranska", "Yhdysvallat".
  const countries = field("maa")
    .split(/\s*[,/]\s*/)
    .filter(Boolean);
  // "suom. tekstit/svenska texter", "English subtitles", "ei tekstitystä".
  const subtitleText = field("tekstitys").toLowerCase();
  let subtitles: Subtitles | undefined;
  if (/ei tekstitystä|no subtitles/.test(subtitleText)) {
    subtitles = { kind: "none" };
  } else if (subtitleText) {
    const languages = [
      ...(/suom/.test(subtitleText) ? ["fi"] : []),
      ...(/svensk|ruots/.test(subtitleText) ? ["sv"] : []),
      ...(/english|engl/.test(subtitleText) ? ["en"] : []),
    ] as Lang[];
    if (languages.length > 0) {
      subtitles = { kind: "languages", languages };
    } else {
      const lang = normalizeLang(subtitleText);
      if (lang) {
        subtitles = { kind: "languages", languages: [lang] };
      } else {
        unmapped.push(`subtitles:${subtitleText}`);
      }
    }
  }
  const series = fields.get("teemat")
    ? fields
        .get("teemat")!
        .find("a")
        .toArray()
        .map((a) => text($(a).text()))
        .filter(Boolean)
    : [];
  const print = field("kopiotieto").toLowerCase();
  const projection = print ? own(PRINTS, print) : undefined;
  if (print && !projection) {
    unmapped.push(`print:${print}`);
  }
  // The age limit is an image: alt="Ikäraja: K12".
  const age = (fields.get("ikäraja")?.find("img").attr("alt") ?? "").match(
    /Ikäraja:\s*(S|K-?\d{1,2})/i,
  )?.[1];
  const rating = age ? own(RATINGS, age.toUpperCase().replace("-", "")) : undefined;
  if (age && !rating) {
    unmapped.push(`rating:${age}`);
  }
  return {
    ...(year > 0 && { year }),
    ...(runtime > 0 && { runtime }),
    countries,
    ...(subtitles && { subtitles }),
    series,
    ...(projection && { projection }),
    ...(rating && { rating }),
    unmapped,
  };
};

/** Pure: the programme + film pages + site config -> normalized batch. */
export const parseRegina = (raw: ReginaRawSnapshot, site: ReginaSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const { rows, unreadable, found } = rowsOf(raw.schedule);
  if (!found) {
    warnings.push({ code: "invalid-response", message: "No programme in the endpoint's answer" });
  }
  if (unreadable > 0) {
    warnings.push({ code: "invalid-row", message: `${unreadable} rows without a readable start` });
  }
  const details = new Map<string, Details>();
  for (const [id, html] of Object.entries(raw.films)) {
    if (html === null) {
      warnings.push({
        code: "film-page-missing",
        message: "Film page unreadable; the film's details stay unknown",
        context: { id },
      });
      continue;
    }
    details.set(id, detailsOf(html));
  }

  for (const row of rows) {
    const m = row.start.match(START)!;
    const start = helsinkiShowTime({
      year: Number(m[3]),
      month: Number(m[2]),
      day: Number(m[1]),
      hour: Number(m[4]),
      minute: Number(m[5]),
    });
    if (!start || start.businessDate < window.from || start.businessDate > window.to) {
      continue;
    }
    const film = details.get(row.filmId);
    const { title: unprefixed, rule } = splitTitlePrefix(row.title, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const listingId = makeId(P, "film", row.filmId);
    if (!listings.has(listingId)) {
      listings.set(listingId, {
        id: listingId,
        provider: P,
        sourceId: row.filmId,
        title: { fi: title },
        ...(film?.year && { year: film.year }),
        ...(film?.runtime && { runtimeMinutes: film.runtime }),
        ...(film?.rating && { rating: film.rating }),
        genres: [],
        countries: film?.countries ?? [],
        kind: rule?.event ? "event" : "film",
      });
    }
    const id = makeId(
      P,
      "show",
      `${row.filmId}-${start.startsAt.slice(0, 16).replace(/[-T:]/g, "")}`,
    );
    screenings.set(id, {
      id,
      provider: P,
      sourceId: `${row.filmId}-${start.startsAt.slice(0, 16).replace(/[-T:]/g, "")}`,
      venueId,
      listingId,
      startsAt: start.startsAt,
      businessDate: start.businessDate,
      presentation: {
        projection: film?.projection ?? "digital",
        dimension: version.dimension ?? "2d",
        formats: [],
      },
      audio: version.audio ? [version.audio] : [],
      ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
      subtitles: film?.subtitles ?? { kind: "unknown" },
      tags: [...(rule?.tags ?? [])],
      series: [...new Set([...(rule?.series ? [rule.series] : []), ...(film?.series ?? [])])],
      availability: "unknown",
      // KAVI's shop for this screening, copied; never requested.
      ticketUrl: row.ticketUrl && URL.canParse(row.ticketUrl) ? row.ticketUrl : site.homepage,
      unmappedLabels: [...(film?.unmapped ?? [])],
      fetchedAt: raw.fetchedAt,
    });
  }

  return {
    provider: providerOf(site, "custom", "buy"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: [toVenue(P, venue, venue.slug)],
    auditoriums: [],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
