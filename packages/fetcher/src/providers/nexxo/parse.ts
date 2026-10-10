import { TZDate } from "@date-fns/tz";
import { formatISO } from "date-fns";
import {
  makeId,
  type Auditorium,
  type FilmListing,
  type FinnishRating,
  type Lang,
  type ProviderBatch,
  type Screening,
  type ScreeningTag,
  type Subtitles,
  type Venue,
  type Warning,
} from "@pgtm/model";
import { normalizeLang } from "../../lib/lang.ts";
import { dateWindow, FINNISH_TZ } from "../../lib/time.ts";
import { providerOf } from "../sites.ts";
import { RawShow, ShowsResponse, type NexxoRawSnapshot } from "./raw.ts";
import {
  DEFAULT_SHOW_TYPES,
  DEFAULT_TITLE_PREFIXES,
  type NexxoSite,
  type NexxoVenue,
  type ShowTypeRule,
  type TitlePrefixRule,
} from "./sites.ts";

/** Nexxo codes that are not ISO 639-1 (SE is handled by normalizeLang). */
const NEXXO_LANGS: Record<string, Lang> = { iw: "he" };
const UNKNOWN = "OV";
const NO_SUBTITLES = "XX";

const codes = (raw: string | null | undefined) =>
  (raw ?? "")
    .toUpperCase()
    .split(/[^A-Z]+/)
    .filter(Boolean);

const toLang = (code: string): Lang | undefined =>
  NEXXO_LANGS[code.toLowerCase()] ?? normalizeLang(code);

/** "FI" / "OV" -> ["fi"] / []. Unknown codes are returned for unmappedLabels. */
export const parseAudio = (
  raw: string | null | undefined,
): { audio: Lang[]; unknown: string[] } => {
  const audio: Lang[] = [];
  const unknown: string[] = [];
  for (const code of codes(raw).filter((c) => c !== UNKNOWN)) {
    const lang = toLang(code);
    if (lang) audio.push(lang);
    else unknown.push(code);
  }
  return { audio, unknown };
};

/** "FI-SE" -> fi, sv; "XX" -> none; "OV" or "" -> unknown. */
export const parseSubtitles = (raw: string | null | undefined): Subtitles => {
  const list = codes(raw);
  if (list.length === 0 || list.includes(UNKNOWN)) return { kind: "unknown" };
  const langs = list.filter((c) => c !== NO_SUBTITLES).map(toLang);
  if (langs.length === 0) return { kind: "none" };
  if (langs.some((l) => l === undefined)) return { kind: "unknown" };
  return { kind: "languages", languages: [...new Set(langs as Lang[])] };
};

const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  "7": "K-7",
  "12": "K-12",
  "16": "K-16",
  "18": "K-18",
};

/** "12" / "s" / "K16" -> rating; "Tapahtuma K18" -> an age limit on the screening. */
export const parseAge = (
  raw: string | null | undefined,
): { rating?: FinnishRating; ageLimit?: FinnishRating } => {
  const value = (raw ?? "").trim().toUpperCase();
  const strict = value.match(/^(?:K-?)?(S|7|12|16|18)$/)?.[1];
  if (strict) return { rating: RATINGS[strict]! };
  const loose = value.match(/\bK-?(7|12|16|18)\b/)?.[1];
  return loose ? { ageLimit: RATINGS[loose]! } : {};
};

/** "2026-10-10 15:00:00" (Helsinki) -> ISO with offset. */
export const toIso = (local: string): string | undefined => {
  const m = local.trim().match(/^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})(?::(\d{2}))?$/);
  if (!m) return undefined;
  const [y, mo, d, h, mi, s] = m.slice(1).map((part) => Number(part ?? 0)) as number[];
  return formatISO(new TZDate(y!, mo! - 1, d!, h!, mi!, s!, FINNISH_TZ));
};

const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

const showTypeRule = (site: NexxoSite, title: string): ShowTypeRule | undefined =>
  site.showTypes?.[title] ?? DEFAULT_SHOW_TYPES[title];

/** "Ennakkoensi-ilta: Pikkuli" -> { title: "Pikkuli", rule } when the prefix is configured. */
export const splitTitlePrefix = (
  site: NexxoSite,
  raw: string,
): { title: string; rule?: TitlePrefixRule } => {
  const title = raw.trim();
  const m = title.match(/^([^:]+):\s*(.+)$/);
  const rule = m && (site.titlePrefixes?.[m[1]!.trim()] ?? DEFAULT_TITLE_PREFIXES[m[1]!.trim()]);
  return rule ? { title: m[2]!, rule } : { title };
};

const ticketUrl = (site: NexxoSite, venue: NexxoVenue): string =>
  venue.page
    ? `${site.homepage}${venue.page}`
    : `${site.homepage}${site.programmePath}?location=${venue.locationId}`;

/** Which venue a row belongs to: by roomId where venues split a location, else the only one. */
const venueFor = (venues: NexxoVenue[], row: RawShow): NexxoVenue | undefined => {
  const roomed = venues.filter((v) => v.roomIds);
  if (roomed.length === 0) return venues[0];
  return roomed.find((v) => v.roomIds!.includes(row.roomId ?? ""));
};

/** Pure: raw snapshot + site config -> normalized batch. Broken rows become warnings. */
export const parseNexxo = (raw: NexxoRawSnapshot, site: NexxoSite): ProviderBatch => {
  const P = site.provider;
  const warnings: Warning[] = [];
  const window = dateWindow(raw.from, raw.days);
  const venues = new Map<string, Venue>();
  const auditoriums = new Map<string, Auditorium>();
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();
  const unclaimed = new Map<
    string,
    {
      locationId: string;
      roomId: string | null | undefined;
      roomTitle: string | null | undefined;
      shows: number;
    }
  >();

  for (const v of site.venues) {
    venues.set(v.slug, {
      id: makeId(P, "venue", v.slug),
      provider: P,
      sourceId: v.page ? `${v.locationId}:${v.slug}` : v.locationId,
      name: v.name,
      city: v.city,
      ...(v.shortName && { shortName: v.shortName }),
      ...(v.address && { address: v.address }),
      ...(v.postalCode && { postalCode: v.postalCode }),
    });
  }

  for (const [locationId, payload] of Object.entries(raw.payloads)) {
    const response = ShowsResponse.safeParse(payload);
    if (!response.success) {
      warnings.push({
        code: "invalid-response",
        message: response.error.message,
        context: { locationId },
      });
      continue;
    }
    const shows = response.data.shows;
    const items = Array.isArray(shows) ? shows : Object.values(shows).flat();
    const here = site.venues.filter((v) => v.locationId === locationId);

    for (const item of items) {
      const parsed = RawShow.safeParse(item);
      if (!parsed.success) {
        warnings.push({
          code: "invalid-show",
          message: parsed.error.message,
          context: { locationId },
        });
        continue;
      }
      const row = parsed.data;
      if (row.isUpcoming === "1" && !row.startDate) continue; // coming soon, not scheduled

      const venue = venueFor(here, row);
      if (!venue) {
        const key = `${locationId}:${row.roomId}`;
        const seen = unclaimed.get(key);
        if (seen) seen.shows++;
        else
          unclaimed.set(key, {
            locationId,
            roomId: row.roomId,
            roomTitle: row.roomTitle,
            shows: 1,
          });
        continue;
      }
      const startsAt = toIso(row.startTime);
      if (!startsAt) {
        warnings.push({
          code: "invalid-start",
          message: `Unreadable startTime "${row.startTime}"`,
          context: { showId: row.showId },
        });
        continue;
      }
      const businessDate = row.startDate ?? row.startTime.slice(0, 10);
      if (businessDate < window.from || businessDate > window.to) continue;

      const unmapped: string[] = [];
      const { audio, unknown } = parseAudio(row.code_language);
      unmapped.push(...unknown.map((c) => `code_language:${c}`));
      const subtitles = parseSubtitles(row.code_subtitles);
      if (
        subtitles.kind === "unknown" &&
        row.code_subtitles &&
        !codes(row.code_subtitles).includes(UNKNOWN)
      ) {
        unmapped.push(`code_subtitles:${row.code_subtitles}`);
      }
      const age = parseAge(row.ageLimit);
      if (row.ageLimit?.trim() && !age.rating && !age.ageLimit)
        unmapped.push(`ageLimit:${row.ageLimit}`);

      const { title, rule: prefix } = splitTitlePrefix(site, row.movieTitle);
      const tags: ScreeningTag[] = [...(prefix?.tags ?? [])];
      const series: string[] = prefix?.series ? [prefix.series] : [];
      let isEvent = false;
      const showType = row.showTypeTitle?.trim();
      if (showType) {
        const rule = showTypeRule(site, showType);
        if (rule) {
          tags.push(...(rule.tags ?? []));
          isEvent ||= rule.event ?? false;
        } else {
          series.push(showType);
        }
      }
      if (age.ageLimit && /tapahtuma/i.test(row.ageLimit ?? "")) isEvent = true;

      const price = Number(row.priceIncludingTax);
      const venueId = makeId(P, "venue", venue.slug);
      const auditoriumId = row.roomId
        ? makeId(P, "screen", `${locationId}-${row.roomId}`)
        : undefined;
      if (auditoriumId && !auditoriums.has(auditoriumId)) {
        auditoriums.set(auditoriumId, {
          id: auditoriumId,
          venueId,
          name: row.roomTitle?.trim() || venue.name,
          features: [],
        });
      }

      const listingId = makeId(P, "film", row.movieId);
      const year = row.release_year?.trim();
      const existing = listings.get(listingId);
      if (!existing || (isEvent && existing.kind === "film")) {
        listings.set(listingId, {
          id: listingId,
          provider: P,
          sourceId: row.movieId,
          title: { fi: title },
          ...(year && /^\d{4}$/.test(year) && { year: Number(year) }),
          ...(Number(row.duration) > 0 && { runtimeMinutes: Number(row.duration) }),
          ...(age.rating && { rating: age.rating }),
          genres: (row.genre ?? "")
            .split(",")
            .map((g) => capitalize(g.trim()))
            .filter(Boolean),
          countries: [],
          kind: isEvent ? "event" : "film",
        });
      }

      const id = makeId(P, "show", row.showId);
      screenings.set(id, {
        id,
        provider: P,
        sourceId: row.showId,
        venueId,
        ...(auditoriumId && { auditoriumId }),
        listingId,
        startsAt,
        businessDate,
        presentation: {
          projection: "digital",
          dimension: row.is3D === "1" ? "3d" : "2d",
          formats: [],
        },
        audio,
        subtitles,
        ...(age.ageLimit && { ageLimit: age.ageLimit }),
        tags: [...new Set(tags)],
        series,
        // Nexxo publishes no seat counts.
        availability: "unknown",
        ...(price > 0 && {
          price: { amountCents: Math.round(price * 100), currency: "EUR" as const },
        }),
        // No per-show booking link: the venue's programme page (verified per site).
        ticketUrl: ticketUrl(site, venue),
        unmappedLabels: unmapped,
        fetchedAt: raw.fetchedAt,
      });
    }
  }

  for (const room of unclaimed.values()) {
    warnings.push({
      code: "unclaimed-room",
      message:
        `Room ${room.roomId} "${room.roomTitle}" at location ${room.locationId} belongs to no ` +
        `venue (${room.shows} shows skipped); add it to sites.ts`,
      context: { ...room },
    });
  }

  return {
    provider: providerOf(site, "nexxo", "reserve"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: [...venues.values()],
    auditoriums: [...auditoriums.values()],
    listings: [...listings.values()],
    screenings: [...screenings.values()].sort(
      (a, b) => Date.parse(a.startsAt) - Date.parse(b.startsAt) || a.id.localeCompare(b.id),
    ),
    warnings,
  };
};
