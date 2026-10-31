import {
  makeId,
  type Auditorium,
  type Feature,
  type FilmListing,
  type Lang,
  type ProviderBatch,
  type Screening,
  type ScreeningTag,
  type Subtitles,
  type Venue,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTimeAt } from "@pgtm/model/time";
import { normalizeLang } from "../../lib/lang.ts";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { parseScreenName, parseSubtitles } from "../mycloudcinema/parse.ts";
import { byStartThenId, finnishRating, tally } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import {
  FilmPost,
  GildaFilm,
  GildaShow,
  isSet,
  MoviesResponse,
  type GildaRawSnapshot,
} from "./raw.ts";
import type { GildaSite } from "./sites.ts";

/** Stated as unrated: nothing to publish, nothing to flag. */
const UNRATED = new Set(["T", "EI MÄÄR."]);

/** Album listening sessions: listed with films, but not films. */
const EVENT_STYLES = new Set(["albumikuuntelu"]);
/**
 * "Amy Winehouse 'Back To Black' (20th Anniversary)": an anniversary special, an event
 * whatever its style says (two album sessions came as "Ei tekstitystä", 2026-10-31).
 */
const ANNIVERSARY = /\(\d+(?:st|nd|rd|th) Anniversary\)\s*$/i;

/** Loose title key for matching a film to its WordPress page. */
const titleKey = (title: string): string =>
  title
    .replace(/<[^>]+>/g, " ")
    .replace(/&#8217;|&#8216;|&#039;/g, "'")
    .replace(/&#8211;/g, "-")
    .replace(/&amp;/g, "&")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();

/**
 * "-" means no subtitles only together with the style "Ei tekstitystä"; with "Tekstitetty"
 * (subtitled) it contradicts itself and stays unknown.
 */
export const gildaSubtitles = (
  raw: string | null | undefined,
  style: string | null | undefined,
): Subtitles => {
  if (raw?.trim() === "-") {
    return style?.trim().toLowerCase() === "ei tekstitystä"
      ? { kind: "none" }
      : { kind: "unknown" };
  }
  return parseSubtitles(raw);
};

/** Pure: raw snapshot + site config -> normalized batch. Broken entries become warnings. */
export const parseGilda = (raw: GildaRawSnapshot, site: GildaSite): ProviderBatch => {
  const P = site.provider;
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const programme = `${site.base}${site.programmePath}`;

  const venues: Venue[] = site.venues.map((v) => toVenue(P, v, v.slug));
  const auditoriums = new Map<string, Auditorium>();
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();
  const unclaimed = new Map<string, number>();

  const pages = new Map<string, string>();
  for (const item of Array.isArray(raw.posts) ? raw.posts : []) {
    const post = FilmPost.safeParse(item);
    if (post.success && post.data.link.startsWith(site.base)) {
      pages.set(titleKey(post.data.title.rendered), post.data.link);
    }
  }

  const response = MoviesResponse.safeParse(raw.movies);
  if (!response.success) {
    warnings.push({ code: "invalid-response", message: response.error.message });
  }
  if (response.data?.fi.resultCode !== undefined && response.data.fi.resultCode !== 0) {
    warnings.push({ code: "result-code", message: `resultCode ${response.data.fi.resultCode}` });
  }

  for (const item of response.data?.fi.data ?? []) {
    const film = GildaFilm.safeParse(item);
    if (!film.success) {
      warnings.push({ code: "invalid-film", message: film.error.message });
      continue;
    }
    for (const entry of film.data.show_times) {
      const parsed = GildaShow.safeParse(entry);
      if (!parsed.success) {
        warnings.push({ code: "invalid-show", message: parsed.error.message });
        continue;
      }
      const s = parsed.data;
      if (isSet(s.deleted) || (s.show_is_visible != null && !isSet(s.show_is_visible))) {
        continue;
      }
      const venue = site.venues.find((v) => v.screens.includes(s.cinema_screen_id));
      if (!venue) {
        tally(unclaimed, `${s.cinema_screen_id} "${s.screen_name}"`);
        continue;
      }
      const start = helsinkiShowTimeAt(s.show_time);
      if (!start) {
        warnings.push({
          code: "invalid-start",
          message: `Unreadable show_time "${s.show_time}"`,
          context: { showTimeId: s.show_time_id },
        });
        continue;
      }
      if (start.businessDate < window.from || start.businessDate > window.to) {
        continue;
      }

      const unmapped: string[] = [];
      const { title: unprefixed, rule: prefix } = splitTitlePrefix(s.movie_name, prefixRules);
      const { title, version } = splitVersion(unprefixed);
      const style = s.movie_audio_style_name?.trim().toLowerCase() ?? "";
      const isEvent =
        EVENT_STYLES.has(style) || ANNIVERSARY.test(s.movie_name) || (prefix?.event ?? false);

      const rawAudio = s.audio_lang?.trim() ?? "";
      const audio: Lang | undefined = rawAudio ? normalizeLang(rawAudio) : undefined;
      if (rawAudio && !audio && rawAudio !== "MULTI") {
        unmapped.push(`audio_lang:${rawAudio}`);
      }
      const subtitles = gildaSubtitles(s.subtitle_lang, s.movie_audio_style_name);
      if (subtitles.kind === "unknown" && s.subtitle_lang && s.subtitle_lang.trim() !== "-") {
        unmapped.push(`subtitle_lang:${s.subtitle_lang}`);
      }
      const ratingName = s.rating_name?.trim() ?? "";
      const rating = finnishRating(ratingName.toUpperCase());
      if (ratingName && !rating && !UNRATED.has(ratingName.toUpperCase())) {
        unmapped.push(`rating_name:${ratingName}`);
      }

      const listingId = makeId(P, "film", s.movie_id);
      if (!listings.has(listingId)) {
        const original = s.original_title?.trim();
        const imdbId = film.data.imdb_id?.trim().match(/^tt\d+$/)?.[0];
        listings.set(listingId, {
          id: listingId,
          provider: P,
          sourceId: String(s.movie_id),
          title: { fi: title },
          ...(original &&
            original.toLowerCase() !== title.toLowerCase() && { originalTitle: original }),
          ...(imdbId && { imdbId }),
          ...(s.running_time && s.running_time > 0 && { runtimeMinutes: s.running_time }),
          ...(rating && { rating }),
          genres: (film.data.genre ?? "")
            .split(",")
            .map((g) => g.trim())
            .filter(Boolean),
          countries: [],
          kind: isEvent ? "event" : "film",
        });
      }

      const venueId = makeId(P, "venue", venue.slug);
      const auditoriumId = makeId(P, "screen", s.cinema_screen_id);
      const hall = parseScreenName(s.screen_name);
      if (!auditoriums.has(auditoriumId)) {
        auditoriums.set(auditoriumId, {
          id: auditoriumId,
          venueId,
          name: s.screen_name.replace(/\s*\(K-\d+\)\s*$/, "").trim(),
          features: hall.features,
          ...(hall.ageLimit && { ageLimit: hall.ageLimit }),
        });
      }

      const formats = new Set<Feature>();
      if (isSet(s.version_atmos) || s.movie_sound_name?.trim().toLowerCase() === "atmos") {
        formats.add("atmos");
      }
      if (isSet(s.version_imax)) {
        formats.add("imax");
      }
      const tags: ScreeningTag[] = [...(prefix?.tags ?? [])];
      const bookable = s.allow_purchases == null || isSet(s.allow_purchases);
      const id = makeId(P, "show", s.show_time_id);
      screenings.set(id, {
        id,
        provider: P,
        sourceId: String(s.show_time_id),
        venueId,
        auditoriumId,
        listingId,
        startsAt: start.startsAt,
        businessDate: start.businessDate,
        presentation: {
          projection: isSet(s.version_70mm)
            ? "70mm"
            : isSet(s.version_35mm)
              ? "35mm"
              : isSet(s.version_16mm)
                ? "16mm"
                : "digital",
          dimension: isSet(s.version_3d) ? "3d" : (version.dimension ?? "2d"),
          formats: [...formats],
        },
        audio: version.audio ? [version.audio] : audio ? [audio] : [],
        ...(style === "dubattu" && { dubbed: true }),
        ...((style === "tekstitetty" || style === "ei tekstitystä") && { dubbed: false }),
        subtitles,
        ...(hall.ageLimit && { ageLimit: hall.ageLimit }),
        tags: [...new Set(tags)],
        series: prefix?.series ? [prefix.series] : [],
        // No seat counts in the facade: only whether sales are open.
        availability: bookable ? "unknown" : "not-bookable",
        // The film's own page on gilda.fi (booking happens there), copied from the site's
        // film list; the programme page when the film has none.
        ...(bookable && { ticketUrl: pages.get(titleKey(s.movie_name)) ?? programme }),
        unmappedLabels: unmapped,
        fetchedAt: raw.fetchedAt,
      });
    }
  }

  for (const [screen, shows] of unclaimed) {
    warnings.push({
      code: "unclaimed-screen",
      message: `Screen ${screen} belongs to no venue (${shows} shows skipped); add it to gilda/sites.ts`,
      context: { screen, shows },
    });
  }

  return {
    provider: providerOf(site, "mycloudcinema", "buy"),
    fetchedAt: raw.fetchedAt,
    window,
    venues,
    auditoriums: [...auditoriums.values()],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
