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
import {
  COMMON_TITLE_PREFIXES,
  splitTitlePrefix,
  splitVersion,
  type LabelRule,
} from "../labels.ts";
import { byStartThenId, plainText, slugify } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { TapiolaRawSnapshot } from "./fetch.ts";
import type { TapiolaSite } from "./sites.ts";

const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  "K-7": "K-7",
  "K-12": "K-12",
  "K-16": "K-16",
  "K-18": "K-18",
};

/** "keskiviikko 14.10.2026 – Klo 15:00" */
const DATE = /(\d{1,2})\.(\d{1,2})\.(\d{4})\s*[–-]\s*klo\s*(\d{1,2})[:.](\d{2})/i;
/** "1h 49min", "95min" */
const DURATION = /^(?:(\d+)\s*h)?\s*(\d+)\s*min$/i;
/** "Original version": the spoken language is not named. */
const ORIGINAL_VERSION = "OV";

type Row = {
  url: string;
  /** The title as the list prints it, version markers included. */
  title: string;
  startsAt: string;
  businessDate: string;
  categories: string[];
};

/** The screening blocks of `/elokuvat/` that read as one; the rest are counted. */
const rowsOf = (html: string, site: TapiolaSite) => {
  const $ = load(html);
  const rows: Row[] = [];
  let unreadable = 0;
  $("div.movie-list div.movie-list-movie").each((_index, el) => {
    const block = $(el);
    const href = block.find("a").first().attr("href") ?? "";
    const title = plainText(block.find(".title").text());
    const date = plainText(block.find(".date").text());
    if (!date) {
      // A "coming soon" block: the same markup, no time yet.
      return;
    }
    const d = date.match(DATE);
    const start =
      d &&
      helsinkiShowTime({
        year: Number(d[3]),
        month: Number(d[2]),
        day: Number(d[1]),
        hour: Number(d[4]),
        minute: Number(d[5]),
      });
    if (!title || !start || !href) {
      unreadable += 1;
      return;
    }
    rows.push({
      url: new URL(href, site.base).href,
      title,
      ...start,
      categories: (block.attr("class") ?? "")
        .split(/\s+/)
        .flatMap((c) => (c.startsWith("cat-") ? [c.slice(4)] : [])),
    });
  });
  return { found: $("div.movie-list").length > 0, rows, unreadable };
};

const inWindow = (rows: Row[], from: string, days: number) => {
  const window = dateWindow(from, days);
  return rows.filter((r) => r.businessDate >= window.from && r.businessDate <= window.to);
};

/** The run page to read for each distinct title in the window (the first run's page). */
export const filmPages = (html: string, site: TapiolaSite, from: string, days: number) =>
  Object.values(Object.groupBy(inWindow(rowsOf(html, site).rows, from, days), (r) => r.title))
    .map((runs) => runs![0]!.url)
    .toSorted();

type Details = {
  rating?: FinnishRating;
  runtime?: number;
  audio?: Lang;
  subtitles: Subtitles;
  unmapped: string[];
};

/** The run page's labelled boxes: "Ikäraja K-16", "Elokuvan kesto 1h 49min", "Kieli Englanti". */
const detailsOf = (html: string): Details => {
  const $ = load(html);
  const box = (kind: string) => {
    const lines = $(`.info-icons .info-icon.${kind} .text`)
      .first()
      .html()
      ?.split(/<\/?br\s*\/?>/i);
    return plainText(load(lines?.slice(1).join(" ") ?? "").text());
  };
  const unmapped: string[] = [];
  const age = $(".info-icons .info-icon")
    .toArray()
    .flatMap((el) => ($(el).attr("class") ?? "").match(/\bage-limit-(\S+)/)?.[1] ?? [])[0];
  const rating = age ? own(RATINGS, age.toUpperCase()) : undefined;
  if (age && !rating) {
    unmapped.push(`rating:${age}`);
  }
  const duration = box("duration").match(DURATION);
  const runtime = duration ? Number(duration[1] ?? 0) * 60 + Number(duration[2]) : 0;

  const spoken = box("language");
  // "OV" would pass for a two-letter code; it names no language.
  const audio = spoken.toUpperCase() === ORIGINAL_VERSION ? undefined : normalizeLang(spoken);
  if (spoken && !audio && spoken.toUpperCase() !== ORIGINAL_VERSION) {
    unmapped.push(`audio:${spoken}`);
  }
  // No subtitle box says nothing: unknown, not "none".
  const named = box("subtitles")
    .split(/[/,;]| ja /)
    .map((s) => s.trim())
    .filter(Boolean);
  const languages = named.map(normalizeLang);
  let subtitles: Subtitles = { kind: "unknown" };
  if (named.length > 0 && languages.every(Boolean)) {
    subtitles = { kind: "languages", languages: [...new Set(languages as Lang[])] };
  } else if (named.length > 0) {
    unmapped.push(`subtitles:${named.join("/")}`);
  }
  return {
    ...(rating && { rating }),
    ...(runtime > 0 && { runtime }),
    ...(audio && { audio }),
    subtitles,
    unmapped,
  };
};

/** Pure: the list + run pages + site config -> normalized batch. */
export const parseTapiola = (raw: TapiolaRawSnapshot, site: TapiolaSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const { found, rows, unreadable } = rowsOf(raw.listing, site);
  if (!found) {
    warnings.push({ code: "invalid-response", message: "No programme list on /elokuvat/" });
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} programme blocks without a title, a readable date or a link`,
    });
  }

  const details = new Map<string, Details>();
  for (const [url, html] of Object.entries(raw.films)) {
    if (html === null) {
      warnings.push({
        code: "film-page-missing",
        message: `Run page unreadable; the film's details stay unknown`,
        context: { url },
      });
      continue;
    }
    details.set(url, detailsOf(html));
  }
  // Every run of a title shares one page: the one fetched for the title.
  const pageOf = new Map(
    rows.flatMap((r) => (raw.films[r.url] !== undefined ? [[r.title, r.url] as const] : [])),
  );

  for (const row of inWindow(rows, raw.from, raw.days)) {
    const { title: unprefixed, rule: prefixRule } = splitTitlePrefix(row.title, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const page = pageOf.get(row.title);
    const film = page ? details.get(page) : undefined;
    const unmapped = [...(film?.unmapped ?? [])];
    const categoryRules: LabelRule[] = [];
    for (const category of row.categories) {
      const rule = own(site.categories, category);
      if (rule) {
        categoryRules.push(rule);
      } else {
        unmapped.push(`category:${category}`);
      }
    }
    const rules = [...(prefixRule ? [prefixRule] : []), ...categoryRules];

    // A slug is one run of a film ("tony-4"), so the film is its title.
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
        kind: rules.some((r) => r.event) ? "event" : "film",
      });
    }

    const slug = new URL(row.url).pathname.split("/").filter(Boolean).at(-1) ?? filmKey;
    const sourceId = `${slug}-${row.startsAt.slice(0, 16).replace(/[-T:]/g, "")}`;
    const id = makeId(P, "show", sourceId);
    const audio = version.audio ?? film?.audio;
    screenings.set(id, {
      id,
      provider: P,
      sourceId,
      venueId,
      listingId,
      startsAt: row.startsAt,
      businessDate: row.businessDate,
      presentation: { projection: "digital", dimension: version.dimension ?? "2d", formats: [] },
      audio: audio ? [audio] : [],
      ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
      subtitles: film?.subtitles ?? { kind: "unknown" },
      tags: [...new Set(rules.flatMap((r) => r.tags ?? []))],
      series: [...new Set(rules.flatMap((r) => (r.series ? [r.series] : [])))],
      availability: "unknown",
      // The run's own page, where the cinema sells its tickets: copied, never requested.
      ticketUrl: row.url.startsWith(`${site.base}/`) ? row.url : site.homepage,
      unmappedLabels: unmapped,
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
