import {
  makeId,
  type Auditorium,
  type FilmListing,
  type FinnishRating,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime } from "@pgtm/model/time";
import { load } from "cheerio";
import { own } from "../../lib/records.ts";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, plainText, slugify } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { JuliaRawSnapshot } from "./fetch.ts";
import type { JuliaSite } from "./sites.ts";

/** "15.10.26 klo 16:00, 1. sali": a two-digit year, published. */
const ROW = /^(\d{1,2})\.(\d{1,2})\.(\d{2})\s+klo\s+(\d{1,2})[:.](\d{2})(?:,\s*(\d+)\.\s*sali)?$/i;
/** "1t 28min", "95min", "2t 55min + väliaika" (an intermission besides) */
const DURATION = /^(?:(\d+)\s*t)?\s*(\d+)\s*min\b/i;
const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  SALLITTU: "S",
  "7": "K-7",
  "12": "K-12",
  "16": "K-16",
  "18": "K-18",
};

/** Pure: the programme page + site config -> normalized batch. */
export const parseJulia = (raw: JuliaRawSnapshot, site: JuliaSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const auditoriums = new Map<string, Auditorium>();
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  const films = $("div.elokuva").toArray();
  if (films.length === 0) {
    warnings.push({ code: "invalid-response", message: "No div.elokuva on the programme page" });
  }
  let unreadable = 0;
  for (const el of films) {
    const film = $(el);
    const rawTitle = plainText(film.find("h2").first().text());
    const link = film.find("a").first().attr("href") ?? site.homepage;
    const times = film.find("div[id^=b]").first();
    // The film's own id is on its screening list ("b1843"); a film without one has no rows.
    const filmId = times.attr("id")?.slice(1);
    if (!rawTitle || !filmId) {
      continue;
    }
    // "<strong>Ikäraja:</strong> S<br>": the label, then the text up to the next break.
    const facts = new Map<string, string>();
    for (const part of (film.html() ?? "").split(/<br\s*\/?>/i)) {
      const m = plainText(load(part, null, false).text()).match(
        /^(Ikäraja|Kesto|Genre|Hinta):\s*(.+)$/i,
      );
      if (m) {
        facts.set(m[1]!.toLowerCase(), m[2]!);
      }
    }
    const unmapped: string[] = [];
    const age = facts.get("ikäraja")?.toUpperCase();
    const rating = age ? own(RATINGS, age.replace(/^K-?/, "")) : undefined;
    if (age && !rating) {
      unmapped.push(`rating:${age}`);
    }
    const duration = facts.get("kesto")?.match(DURATION);
    const runtime = duration ? Number(duration[1] ?? 0) * 60 + Number(duration[2]) : 0;

    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const listingId = makeId(P, "film", filmId);
    // "Komedia Kotimainen" or "Draama, Kotimainen": commas when given, else spaces.
    const genreText = facts.get("genre") ?? "";
    const genres = genreText.split(genreText.includes(",") ? /\s*,\s*/ : /\s+/).filter(Boolean);
    const event =
      rule?.event ||
      genres.some((g) => site.eventGenres.some((e) => e.toLowerCase() === g.toLowerCase()));

    for (const line of (times.html() ?? "").split(/<br\s*\/?>/i)) {
      const row = plainText(load(line, null, false).text());
      if (!row) {
        continue;
      }
      const m = row.match(ROW);
      const start =
        m &&
        helsinkiShowTime({
          year: 2000 + Number(m[3]),
          month: Number(m[2]),
          day: Number(m[1]),
          hour: Number(m[4]),
          minute: Number(m[5]),
        });
      if (!m || !start) {
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
          genres,
          countries: [],
          kind: event ? "event" : "film",
        });
      }
      const hall = m[6] ? `Sali ${m[6]}` : undefined;
      const auditoriumId = hall ? makeId(P, "screen", `${venue.slug}-${slugify(hall)}`) : undefined;
      if (auditoriumId && hall && !auditoriums.has(auditoriumId)) {
        auditoriums.set(auditoriumId, { id: auditoriumId, venueId, name: hall, features: [] });
      }
      const sourceId = `${filmId}-${start.startsAt.slice(0, 16).replace(/[-T:]/g, "")}`;
      const id = makeId(P, "show", sourceId);
      screenings.set(id, {
        id,
        provider: P,
        sourceId,
        venueId,
        ...(auditoriumId && { auditoriumId }),
        listingId,
        startsAt: start.startsAt,
        businessDate: start.businessDate,
        presentation: { projection: "digital", dimension: version.dimension ?? "2d", formats: [] },
        audio: version.audio ? [version.audio] : [],
        ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
        subtitles: { kind: "unknown" },
        tags: [
          ...(rule?.tags ?? []),
          ...(event && !rule?.event ? (["event-cinema"] as const) : []),
        ],
        series: rule?.series ? [rule.series] : [],
        availability: "unknown",
        // Tickets at the door: the film's own page on the site, copied.
        ticketUrl: link.startsWith(`${site.homepage}/`) ? link : site.programme,
        unmappedLabels: unmapped,
        fetchedAt: raw.fetchedAt,
      });
    }
  }
  if (unreadable > 0) {
    warnings.push({ code: "invalid-row", message: `${unreadable} screening rows not understood` });
  }

  return {
    provider: providerOf(site, "custom", "door"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: [toVenue(P, venue, venue.slug)],
    auditoriums: [...auditoriums.values()],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
