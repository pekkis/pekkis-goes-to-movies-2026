import {
  makeId,
  type Auditorium,
  type FilmListing,
  type FinnishRating,
  type Lang,
  type ProviderBatch,
  type Screening,
  type Subtitles,
  type Warning,
} from "@pgtm/model";
import { dateWindow, toHelsinkiIso } from "@pgtm/model/time";
import { load } from "cheerio";
import { normalizeLang } from "../../lib/lang.ts";
import { own } from "../../lib/records.ts";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { availabilityFromSeats, byStartThenId, slugify, tally } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import { ScheduleResponse, VistaShow, type VistaRawSnapshot } from "./raw.ts";
import type { VistaSite } from "./sites.ts";

const RATINGS: Record<string, FinnishRating> = {
  SALLITTU: "S",
  S: "S",
  "K-7": "K-7",
  "K-12": "K-12",
  "K-16": "K-16",
  "K-18": "K-18",
};
/** Stated as not known. */
const UNKNOWN_RATINGS = new Set(["EI TIEDOSSA", "(NONE)"]);

/**
 * "K-12", "K12", and Riviera's "K16/13" (the lower age is allowed with an adult): the
 * limit itself, hyphenated.
 */
const ratingKey = (rating: string) => rating.replace(/\/\d+$/, "").replace(/^K(\d)/, "K-$1");

/** A trailing "(1996)" is the production year, not part of the title. */
const YEAR_SUFFIX = /\s*\((\d{4})\)$/;

/** Fields that are numbers in the JSON answer; XML has only text. */
const NUMERIC = new Set([
  "ID",
  "EventID",
  "TheatreID",
  "ProductionYear",
  "LengthInMinutes",
  "AvailableSeats",
  "TotalSeats",
]);

/** XML `<Show>` elements as the objects the JSON answer gives: empty means absent. */
const xmlShows = (xml: string): unknown[] | undefined => {
  const $ = load(xml, { xml: true });
  if ($("Schedule").length === 0) {
    return undefined;
  }
  const value = (el: Parameters<typeof $>[0]) => {
    const node = $(el);
    if (node.children().length > 0) {
      return Object.fromEntries(
        node
          .children()
          .toArray()
          .map((child) => [child.tagName, $(child).text().trim() || null]),
      );
    }
    const text = node.text().trim();
    if (!text) {
      return null;
    }
    return NUMERIC.has((el as { tagName: string }).tagName) ? Number(text) : text;
  };
  return $("Schedule > Shows > Show")
    .toArray()
    .map((show) =>
      Object.fromEntries(
        $(show)
          .children()
          .toArray()
          .map((field) => [field.tagName, value(field)]),
      ),
    );
};

type Language =
  | { Name?: string | null | undefined; ISOTwoLetterCode?: string | null | undefined }
  | null
  | undefined;

/** "Several languages": audio not stated per language, so unknown, not flagged. */
const SEVERAL = "useita kieliä";

const language = (l: Language): Lang | undefined =>
  normalizeLang(l?.ISOTwoLetterCode?.trim() || l?.Name?.trim() || "");

/** Both subtitle fields empty says nothing: unknown, not "none". */
const subtitlesOf = (s: VistaShow, unmapped: string[]): Subtitles => {
  const given = [s.SubtitleLanguage1, s.SubtitleLanguage2].filter(
    (l) => l?.ISOTwoLetterCode?.trim() || l?.Name?.trim(),
  );
  if (given.length === 0) {
    return { kind: "unknown" };
  }
  const languages = given.map(language);
  if (languages.some((l) => !l)) {
    unmapped.push(...given.map((l) => `subtitles:${l?.ISOTwoLetterCode || l?.Name}`));
    return { kind: "unknown" };
  }
  return { kind: "languages", languages: [...new Set(languages as Lang[])] };
};

const showsOf = (payload: unknown): unknown[] | undefined => {
  if (typeof payload === "string") {
    return xmlShows(payload);
  }
  const parsed = ScheduleResponse.safeParse(payload);
  if (!parsed.success) {
    return undefined;
  }
  const shows = parsed.data.Shows;
  if (!shows) {
    return [];
  }
  if (Array.isArray(shows)) {
    return shows;
  }
  return Array.isArray(shows.Show) ? shows.Show : shows.Show ? [shows.Show] : [];
};

/** Pure: schedules + site config -> normalized batch. Broken shows become warnings. */
export const parseVista = (raw: VistaRawSnapshot, site: VistaSite): ProviderBatch => {
  const P = site.provider;
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const auditoriums = new Map<string, Auditorium>();
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();
  const unclaimed = new Map<string, number>();

  for (const [area, payload] of Object.entries(raw.schedules)) {
    const shows = showsOf(payload);
    if (!shows) {
      warnings.push({
        code: "invalid-response",
        message: "Not a Vista schedule",
        context: { area },
      });
      continue;
    }
    for (const item of shows) {
      const parsed = VistaShow.safeParse(item);
      if (!parsed.success) {
        warnings.push({ code: "invalid-show", message: parsed.error.message, context: { area } });
        continue;
      }
      const s = parsed.data;
      const venue = site.venues.find((v) => v.theatreId === s.TheatreID);
      if (!venue) {
        tally(unclaimed, `${s.TheatreID} "${s.Theatre ?? ""}"`);
        continue;
      }
      const businessDate = s.dtAccounting.slice(0, 10);
      if (businessDate < window.from || businessDate > window.to) {
        continue;
      }
      let startsAt: string;
      try {
        startsAt = toHelsinkiIso(s.dttmShowStartUTC);
      } catch {
        warnings.push({
          code: "invalid-start",
          message: `Unreadable start "${s.dttmShowStartUTC}"`,
          context: { id: s.ID },
        });
        continue;
      }

      const unmapped: string[] = [];
      const { title: unprefixed, rule } = splitTitlePrefix(s.Title, prefixRules);
      const titleYear = unprefixed.match(YEAR_SUFFIX)?.[1];
      const { title, version } = splitVersion(unprefixed.replace(YEAR_SUFFIX, ""));
      const year = titleYear
        ? Number(titleYear)
        : site.releaseYearAsProductionYear
          ? undefined
          : s.ProductionYear;
      const ratingText = s.Rating?.trim().toUpperCase() ?? "";
      const rating = own(RATINGS, ratingKey(ratingText));
      if (ratingText && !rating && !UNKNOWN_RATINGS.has(ratingText)) {
        unmapped.push(`rating:${s.Rating}`);
      }
      const audio = language(s.SpokenLanguage);
      const spoken = s.SpokenLanguage?.ISOTwoLetterCode || s.SpokenLanguage?.Name;
      if (!audio && spoken && spoken.trim().toLowerCase() !== SEVERAL) {
        unmapped.push(`audio:${spoken}`);
      }
      const method = s.PresentationMethod?.trim().toUpperCase() ?? "";
      if (method && method !== "2D" && method !== "3D") {
        unmapped.push(`presentation:${s.PresentationMethod}`);
      }
      if (s.EventType && s.EventType !== "Movie") {
        unmapped.push(`event-type:${s.EventType}`);
      }

      const listingId = makeId(P, "film", s.EventID);
      if (!listings.has(listingId)) {
        // Cleaned like the title: Riviera repeats prefixes and years in it.
        const original =
          s.OriginalTitle &&
          splitTitlePrefix(s.OriginalTitle, prefixRules).title.replace(YEAR_SUFFIX, "").trim();
        listings.set(listingId, {
          id: listingId,
          provider: P,
          sourceId: String(s.EventID),
          title: { fi: title },
          ...(original &&
            original.toLowerCase() !== title.toLowerCase() && { originalTitle: original }),
          ...(year && { year }),
          ...(s.LengthInMinutes && s.LengthInMinutes > 0 && { runtimeMinutes: s.LengthInMinutes }),
          ...(rating && { rating }),
          genres: (s.Genres ?? "")
            .split(",")
            .map((g) => g.trim())
            .filter(Boolean),
          countries: [],
          kind: rule?.event ? "event" : "film",
        });
      }

      const venueId = makeId(P, "venue", venue.slug);
      // Bio-Kaari's one hall is named "-": no name, no auditorium.
      const hall = s.TheatreAuditorium?.trim().replace(/^[-–]+$/, "");
      const auditoriumId = hall ? makeId(P, "screen", `${venue.slug}-${slugify(hall)}`) : undefined;
      if (auditoriumId && hall && !auditoriums.has(auditoriumId)) {
        auditoriums.set(auditoriumId, { id: auditoriumId, venueId, name: hall, features: [] });
      }

      const series = [
        ...(rule?.series ? [rule.series] : []),
        ...(s.EventSeries?.trim() ? [s.EventSeries.trim()] : []),
      ];
      const url = s.ShowURL?.trim();
      const id = makeId(P, "show", s.ID);
      screenings.set(id, {
        id,
        provider: P,
        sourceId: String(s.ID),
        venueId,
        ...(auditoriumId && { auditoriumId }),
        listingId,
        startsAt,
        ...(s.dttmShowEndUTC && { endsAt: toHelsinkiIso(s.dttmShowEndUTC) }),
        businessDate,
        presentation: {
          projection: "digital",
          dimension: method === "3D" ? "3d" : (version.dimension ?? "2d"),
          formats: [],
        },
        audio: version.audio ? [version.audio] : audio ? [audio] : [],
        ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
        subtitles: subtitlesOf(s, unmapped),
        tags: [...(rule?.tags ?? [])],
        series,
        availability: availabilityFromSeats(
          s.AvailableSeats != null && s.TotalSeats
            ? { free: s.AvailableSeats, capacity: s.TotalSeats }
            : {},
        ),
        // The show's own ticket page, copied from the schedule (Riviera's say http).
        ticketUrl: url && URL.parse(url)?.host === new URL(site.base).host ? url : site.homepage,
        unmappedLabels: unmapped,
        fetchedAt: raw.fetchedAt,
      });
    }
  }

  for (const [theatre, shows] of unclaimed) {
    warnings.push({
      code: "unclaimed-venue",
      message: `Theatre ${theatre} belongs to no venue (${shows} shows skipped); add it to vista/sites.ts`,
      context: { theatre, shows },
    });
  }

  return {
    provider: providerOf(site, "vista-public", "buy"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: site.venues.map((v) => toVenue(P, v, String(v.theatreId))),
    auditoriums: [...auditoriums.values()],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
