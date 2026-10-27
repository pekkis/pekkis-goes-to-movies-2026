import {
  makeId,
  type Auditorium,
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
import { availabilityFromSeats, byStartThenId, plainText, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { CinemahouseRawSnapshot } from "./fetch.ts";
import type { CinemahouseSite } from "./sites.ts";

const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  "7": "K-7",
  "12": "K-12",
  "16": "K-16",
  "18": "K-18",
};

/** "14.10. 12:00 · Sali 2": day, month, time, and the hall after the separator. */
const META = /^(\d{1,2})\.(\d{1,2})\.\s*(\d{1,2})[:.](\d{2})\s*(?:·\s*(.+))?$/;

type Tile = {
  slug: string;
  link: string;
  rating?: FinnishRating;
  runtime?: number;
  genres: string[];
};

/** Pure: the front page + site config -> normalized batch. Broken rows become warnings. */
export const parseCinemahouse = (
  raw: CinemahouseRawSnapshot,
  site: CinemahouseSite,
): ProviderBatch => {
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
  if ($("select.cr-movies-filter-select").length === 0) {
    // The filter survives an empty programme; without it this is not the plugin's page.
    warnings.push({
      code: "invalid-response",
      message: "No cinema-reservations programme on the front page",
    });
  }

  // Film tiles, keyed by the title exactly as the rows print it.
  const tiles = new Map<string, Tile>();
  $("article.cr-movie-tile").each((_index, el) => {
    const tile = $(el);
    const title = plainText(tile.find(".cr-movie-tile__title").text());
    const link = tile.find("a.cr-movie-tile__link").attr("href") ?? "";
    const age = plainText(tile.find(".cr-badge--age").text()).toUpperCase();
    const runtime = Number(
      plainText(tile.find(".cr-badge--runtime").text()).match(/^(\d+)\s*min$/)?.[1],
    );
    const rating = own(RATINGS, age);
    tiles.set(title, {
      slug: link.match(/\/elokuvat\/([^/]+)\/?$/)?.[1] ?? slugify(title),
      link,
      ...(rating && { rating }),
      ...(runtime > 0 && { runtime }),
      genres: plainText(tile.find(".cr-movie-tile__meta").text())
        .split(",")
        .map((g) => g.trim())
        .filter(Boolean)
        .map((g) => g.charAt(0).toUpperCase() + g.slice(1)),
    });
  });

  $("div.cr-screening-row").each((_index, el) => {
    const row = $(el);
    const rawTitle = plainText(row.find(".cr-screening-title").text());
    const meta = plainText(row.find(".cr-screening-meta").text());
    const m = meta.match(META);
    const date = m && nearestDate(Number(m[1]), Number(m[2]), raw.from);
    const start =
      m &&
      date &&
      helsinkiShowTime({
        year: Number(date.slice(0, 4)),
        month: Number(m[2]),
        day: Number(m[1]),
        hour: Number(m[3]),
        minute: Number(m[4]),
      });
    if (!rawTitle || !start) {
      warnings.push({ code: "invalid-start", message: `Unreadable row "${rawTitle}" "${meta}"` });
      return;
    }
    if (start.businessDate < window.from || start.businessDate > window.to) {
      return;
    }

    const cta = row.find("a.cr-screening-cta");
    const screeningId = cta.attr("data-screening-id");
    const href = cta.attr("href");
    const hall = plainText(m[5]);
    const tile = tiles.get(rawTitle);
    const unmapped: string[] = [];
    if (!tile) {
      unmapped.push(`no-film-tile:${rawTitle}`);
    }

    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const listingId = makeId(P, "film", tile?.slug ?? slugify(title));
    if (!listings.has(listingId)) {
      listings.set(listingId, {
        id: listingId,
        provider: P,
        sourceId: tile?.slug ?? slugify(title),
        title: { fi: title },
        ...(tile?.runtime && { runtimeMinutes: tile.runtime }),
        ...(tile?.rating && { rating: tile.rating }),
        genres: tile?.genres ?? [],
        countries: [],
        kind: rule?.event ? "event" : "film",
      });
    }

    const auditoriumId = hall ? makeId(P, "screen", `${venue.slug}-${slugify(hall)}`) : undefined;
    if (auditoriumId && !auditoriums.has(auditoriumId)) {
      auditoriums.set(auditoriumId, { id: auditoriumId, venueId, name: hall, features: [] });
    }

    const seats = plainText(row.find(".cr-screening-seats").text()).match(/(\d+)\s*\/\s*(\d+)/);
    const price = toCents(plainText(row.find(".cr-screening-price").text()).replace(/\s*€$/, ""), {
      zeroIsFree: false,
    });
    // The plugin's own screening id; film, minute and hall when a row has none.
    const sourceId =
      screeningId ??
      `${tile?.slug ?? slugify(title)}-${start.startsAt.slice(0, 16).replace(/[-T:]/g, "")}`;
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
      tags: [...(rule?.tags ?? [])],
      series: rule?.series ? [rule.series] : [],
      availability: availabilityFromSeats(
        seats ? { free: Number(seats[1]), capacity: Number(seats[2]) } : {},
      ),
      ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
      // The cinema's own reservation page for this screening: copied, never requested.
      ticketUrl: href?.startsWith(`${site.base}/`) ? href : tile?.link || `${site.base}/`,
      unmappedLabels: unmapped,
      fetchedAt: raw.fetchedAt,
    });
  });

  return {
    provider: providerOf(site, "cinema-reservations", "reserve"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: [toVenue(P, venue, venue.slug)],
    auditoriums: [...auditoriums.values()],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
