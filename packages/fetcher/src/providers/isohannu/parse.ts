import {
  makeId,
  type Auditorium,
  type FilmListing,
  type FinnishRating,
  type Lang,
  type ProviderBatch,
  type Screening,
  type ScreeningTag,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime } from "@pgtm/model/time";
import { load } from "cheerio";
import { normalizeLang } from "../../lib/lang.ts";
import { own } from "../../lib/records.ts";
import { splitVersion } from "../labels.ts";
import { byStartThenId, slugify } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { IsohannuRawSnapshot } from "./fetch.ts";
import type { IsohannuSite } from "./sites.ts";

/** Written without the hyphen: "K16". */
const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  K7: "K-7",
  K12: "K-12",
  K16: "K-16",
  K18: "K-18",
};

/** "Keskiviikko 14.10.2026" */
const DAY = /(\d{1,2})\.(\d{1,2})\.(\d{4})\s*$/;
const TIME = /^(\d{1,2})[:.](\d{2})$/;
const FILM_ID = /[?&]id=(\d+)/;

const text = (value: string | undefined) => (value ?? "").replace(/\s+/g, " ").trim();

type Row = {
  filmId: string;
  /** As printed, in capitals: "KERRO KAIKILLE". */
  title: string;
  hall: string;
  startsAt: string;
  businessDate: string;
  ticketUrl?: string;
  tagClasses: string[];
};

/**
 * The show table's rows. Parsed with htmlparser2, which keeps the page's nesting as
 * written: the ticket link sits inside the film link, which an HTML5 parser would undo.
 */
const rowsOf = (html: string, site: IsohannuSite) => {
  const $ = load(html, { xml: { xmlMode: false, decodeEntities: true } });
  const rows: Row[] = [];
  let unreadable = 0;
  let skipped = 0;
  const notScreenings = new Set(site.notScreenings.map((t) => t.toLowerCase()));
  $("#showtable h3.showtable-title").each((_index, heading) => {
    const d = text($(heading).text()).match(DAY);
    const containers = $(heading).nextUntil("h3.showtable-title", ".showtable-container");
    if (!d) {
      unreadable += containers.find(".showtable-row").length || 1;
      return;
    }
    containers.each((_c, container) => {
      const hall = text($(container).find(".showtable-hall").first().text());
      $(container)
        .find(".showtable-row")
        .each((_r, el) => {
          const row = $(el);
          const name = row.find(".showtable-name").first();
          // The title is the text before the nested ticket link.
          const title = text(
            name
              .contents()
              .filter((_i, node) => node.type === "text")
              .text(),
          );
          const time = text(row.find(".showtable-time").text()).match(TIME);
          const filmId = row.closest("a").attr("href")?.match(FILM_ID)?.[1];
          const start =
            time &&
            helsinkiShowTime({
              year: Number(d[3]),
              month: Number(d[2]),
              day: Number(d[1]),
              hour: Number(time[1]),
              minute: Number(time[2]),
            });
          if (!title || !start || !filmId) {
            unreadable += 1;
            return;
          }
          if (notScreenings.has(title.toLowerCase())) {
            skipped += 1;
            return;
          }
          const ticketUrl = name.find("a").attr("href");
          rows.push({
            filmId,
            title,
            hall,
            ...start,
            ...(ticketUrl && { ticketUrl }),
            tagClasses: row
              .find(".showtable-tag")
              .toArray()
              .flatMap((t) =>
                ($(t).attr("class") ?? "")
                  .split(/\s+/)
                  .flatMap((c) =>
                    c.startsWith("showtable-") && c !== "showtable-tag"
                      ? [c.slice("showtable-".length)]
                      : [],
                  ),
              ),
          });
        });
    });
  });
  return { found: $("#showtable").length > 0, rows, unreadable, skipped };
};

const inWindow = (rows: Row[], from: string, days: number) => {
  const window = dateWindow(from, days);
  return rows.filter((r) => r.businessDate >= window.from && r.businessDate <= window.to);
};

/** The film pages to read: every film with a screening in the window. */
export const filmIds = (html: string, site: IsohannuSite, from: string, days: number) => [
  ...new Set(inWindow(rowsOf(html, site).rows, from, days).map((r) => r.filmId)),
];

type Details = {
  rating?: FinnishRating;
  runtime?: number;
  genres: string[];
  /** "Ruotsi, Italia": every language spoken. */
  audio: Lang[];
  unmapped: string[];
};

/** The film page's `#kuvaus` block: "Label: value" lines between `<hr>`s. */
const detailsOf = (html: string): Details => {
  const $ = load(html);
  const fields = new Map<string, string>();
  for (const part of ($("#kuvaus").html() ?? "").split(/<hr\b[^>]*>/i)) {
    const line = text(load(part, null, false).text());
    const m = line.match(/^([^:]{2,30}):\s*(.+)$/);
    if (m) {
      fields.set(m[1]!.toLowerCase(), m[2]!);
    }
  }
  const unmapped: string[] = [];
  const age = fields.get("elokuvan ikäraja")?.toUpperCase().replace(/[\s-]/g, "");
  const rating = age ? own(RATINGS, age) : undefined;
  if (age && !rating) {
    unmapped.push(`rating:${age}`);
  }
  const runtime = Number(fields.get("elokuvan kesto")?.match(/^(\d+)\s*min/)?.[1]);
  const spoken = (fields.get("puhekieli") ?? "")
    .split(/,| ja /)
    .map((l) => l.trim())
    .filter(Boolean);
  const languages = spoken.map(normalizeLang);
  const known = languages.every(Boolean);
  if (!known) {
    unmapped.push(`audio:${spoken.join(", ")}`);
  }
  return {
    ...(rating && { rating }),
    ...(runtime > 0 && { runtime }),
    genres: (fields.get("genre") ?? "")
      .split(",")
      .map((g) => g.trim())
      .filter(Boolean)
      .map((g) => g.charAt(0).toUpperCase() + g.slice(1)),
    audio: known ? [...new Set(languages as Lang[])] : [],
    unmapped,
  };
};

/** Pure: the front page + film pages + site config -> normalized batch. */
export const parseIsohannu = (raw: IsohannuRawSnapshot, site: IsohannuSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const auditoriums = new Map<string, Auditorium>();
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const { found, rows, unreadable } = rowsOf(raw.html, site);
  if (!found) {
    warnings.push({ code: "invalid-response", message: "No #showtable on the front page" });
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} show table rows without a readable day, time, title or film id`,
    });
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

  for (const row of inWindow(rows, raw.from, raw.days)) {
    const film = details.get(row.filmId);
    const { title, version } = splitVersion(row.title);
    const unmapped = [...(film?.unmapped ?? [])];
    const tags: ScreeningTag[] = [];
    let dimension = version.dimension;
    for (const tag of row.tagClasses) {
      const mapped = own(site.tags, tag);
      if (tag === "3d") {
        dimension = "3d";
      } else if (mapped) {
        tags.push(...mapped);
      } else {
        unmapped.push(`tag:${tag}`);
      }
    }

    const listingId = makeId(P, "film", row.filmId);
    if (!listings.has(listingId)) {
      listings.set(listingId, {
        id: listingId,
        provider: P,
        sourceId: row.filmId,
        title: { fi: title },
        ...(film?.runtime && { runtimeMinutes: film.runtime }),
        ...(film?.rating && { rating: film.rating }),
        genres: film?.genres ?? [],
        countries: [],
        kind: "film",
      });
    }

    const auditoriumId = row.hall
      ? makeId(P, "screen", `${venue.slug}-${slugify(row.hall)}`)
      : undefined;
    if (auditoriumId && !auditoriums.has(auditoriumId)) {
      auditoriums.set(auditoriumId, { id: auditoriumId, venueId, name: row.hall, features: [] });
    }

    // The ticket system's show id when there is one; film and minute otherwise.
    const showId = row.ticketUrl?.match(/\/shows\/(\d+)\//)?.[1];
    const sourceId = showId ?? `${row.filmId}-${row.startsAt.slice(0, 16).replace(/[-T:]/g, "")}`;
    const id = makeId(P, "show", sourceId);
    const audio = version.audio ? [version.audio] : (film?.audio ?? []);
    screenings.set(id, {
      id,
      provider: P,
      sourceId,
      venueId,
      ...(auditoriumId && { auditoriumId }),
      listingId,
      startsAt: row.startsAt,
      businessDate: row.businessDate,
      presentation: { projection: "digital", dimension: dimension ?? "2d", formats: [] },
      audio,
      ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
      // The film page states no subtitles: unknown, not "none".
      subtitles: { kind: "unknown" },
      tags: [...new Set(tags)],
      series: [],
      availability: "unknown",
      // The screening's own ticket page, copied as printed (http), never requested.
      ticketUrl: row.ticketUrl ?? `${site.base}/leffasivu.php?id=${row.filmId}`,
      unmappedLabels: unmapped,
      fetchedAt: raw.fetchedAt,
    });
  }

  return {
    provider: providerOf(site, "custom", "buy"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: [toVenue(P, venue, venue.slug)],
    auditoriums: [...auditoriums.values()],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
