import { normalizeLang, normalizeLangs } from "../../lib/lang.ts";
import { dateWindow, toHelsinkiIso } from "@pgtm/model/time";
import {
  makeId,
  type Auditorium,
  type Availability,
  type Feature,
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
import { Envelope, RawCinema, RawShowtime, type MyCloudCinemaRawSnapshot } from "./raw.ts";
import type { MyCloudCinemaSite } from "./sites.ts";
import { providerOf } from "../sites.ts";
import { own } from "../../lib/records.ts";
import { COMMON_TITLE_PREFIXES, isPrivateBooking, type LabelRule } from "../labels.ts";
import { byStartThenId, finnishRating } from "../parsing.ts";

/** The pattern the cinema's own programme page links to: `{ticketBase}/#/book/{id}`. */
export const ticketUrl = (site: Pick<MyCloudCinemaSite, "ticketBase">, showTimeId: number) =>
  `${site.ticketBase}/#/book/${showTimeId}`;

/** "rating_fi_12.svg" -> "K-12" */
export const parseRating = (icon: string | null | undefined): FinnishRating | undefined => {
  const match = icon?.match(/^rating_fi_(s|\d+)\.svg$/i);
  return match?.[1] ? finnishRating(match[1]) : undefined;
};

/**
 * Subtitles, in either vocabulary the platform's cinemas use: BioRex's "Suomi & Ruotsi -",
 * "SE", "-" and Cine Mäntsälä's "Suomeksi ja ruotsiksi", "Ruotsiksi", "Ei".
 */
export const parseSubtitles = (raw: string | null | undefined): Subtitles => {
  const value = raw?.trim();
  if (!value) {
    return { kind: "unknown" };
  }
  if (value === "-" || value.toLowerCase() === "ei") {
    return { kind: "none" };
  }

  const parts = value
    .replace(/-$/, "")
    .split(/&|,|\/|\s+ja\s+/i)
    .map((part) => part.trim())
    .filter(Boolean);
  const languages = parts.map(normalizeLang);
  if (languages.length === 0 || languages.some((lang) => lang === undefined)) {
    return { kind: "unknown" };
  }
  return { kind: "languages", languages: languages as Lang[] };
};

/** Tokens of `title_extension` that only repeat what audio/dubbing fields already say. */
const LANGUAGE_TOKENS = new Set(["FI", "SWE", "DUB", "ORIG"]);

/** A whole `title_extension` that is a known label ("Ennakkonäytös!"): the site's, then shared. */
const labelRule = (raw: string, site: Record<string, LabelRule>) => {
  const phrase = raw.trim().replace(/!+$/, "").toLowerCase();
  return Object.entries({ ...COMMON_TITLE_PREFIXES, ...site }).find(
    ([label]) => label.toLowerCase() === phrase,
  )?.[1];
};

/**
 * `title_extension`: a known label as a whole ("Ennakkonäytös!" at Cine Mäntsälä -> preview),
 * otherwise format words (BioRex's "FI ATMOS") and labels we do not understand.
 */
export const parseTitleExtension = (
  raw: string | null | undefined,
  siteLabels: Record<string, LabelRule> = {},
): {
  formats: Feature[];
  tags: ScreeningTag[];
  series: string[];
  event: boolean;
  licensed?: boolean;
  ageLimit?: FinnishRating;
  unmapped: string[];
} => {
  const rule = raw ? labelRule(raw, siteLabels) : undefined;
  if (rule) {
    return {
      formats: [],
      tags: [...(rule.tags ?? [])],
      series: rule.series ? [rule.series] : [],
      event: rule.event ?? false,
      ...(rule.licensed && { licensed: true }),
      ...(rule.ageLimit && { ageLimit: rule.ageLimit }),
      unmapped: [],
    };
  }
  const formats: Feature[] = [];
  const unmapped: string[] = [];
  for (const token of raw?.trim().split(/\s+/).filter(Boolean) ?? []) {
    const upper = token.toUpperCase();
    if (upper === "ATMOS") {
      formats.push("atmos");
    } else if (upper === "IMAX") {
      formats.push("imax");
    } else if (!LANGUAGE_TOKENS.has(upper)) {
      unmapped.push(`title_extension:${token}`);
    }
  }
  return { formats, tags: [], series: [], event: false, unmapped };
};

/** "6 REX (K-18)" -> features and the hall's own age limit. */
export const parseScreenName = (
  name: string,
): { features: Feature[]; ageLimit?: FinnishRating } => {
  const features: Feature[] = [];
  if (/\bprime\b/i.test(name)) {
    features.push("prime");
  }
  if (/\bplus\b/i.test(name)) {
    features.push("plus");
  }
  if (/\bluxe\b/i.test(name)) {
    features.push("luxe");
  }
  if (/\bimax\b/i.test(name)) {
    features.push("imax");
  }
  const age = name.match(/\(K-(18|16|12|7)\)/)?.[1];
  const ageLimit = age ? finnishRating(age) : undefined;
  return ageLimit ? { features, ageLimit } : { features };
};

const splitList = (raw: string | null | undefined): string[] =>
  raw
    ?.split(",")
    .map((s) => s.trim())
    .filter(Boolean) ?? [];

/** `version_*` flags mapped to the model; any other flag set to 1 is reported as unmapped. */
const MAPPED_VERSION_FLAGS = new Set([
  "version_3d",
  "version_16mm",
  "version_35mm",
  "version_70mm",
  "version_atmos",
  "version_dbox",
  "version_imax",
  "version_luxe",
  "version_kids",
  "version_digital",
]);

const availability = (s: RawShowtime): Availability => {
  if (!s.bookable || !s.allow_purchases || s.show_locked) {
    return "not-bookable";
  }
  if (s.sold_out) {
    return "sold-out";
  }
  if (s.seats_low) {
    return "few-left";
  }
  return "available";
};

const parseVenue = (P: string, site: MyCloudCinemaSite, c: RawCinema): Venue | undefined => {
  const city = c.city?.trim() || own(site.cityOverrides, String(c.cinema_id));
  if (!city) {
    return undefined;
  }
  const address = c.address?.trim();
  const postalCode = c.postal_code?.trim();
  return {
    id: makeId(P, "venue", c.cinema_id),
    provider: P,
    sourceId: String(c.cinema_id),
    name: c.cinema_name.trim(),
    city,
    ...(address && { address }),
    ...(postalCode && { postalCode }),
    ...(c.latitude != null &&
      c.longitude != null && { geo: { lat: c.latitude, lon: c.longitude } }),
  };
};

/** Offline cinemas, the company record (0 screens) and "xxx"-prefixed closed ones are skipped. */
export const isActiveCinema = (c: RawCinema): boolean =>
  c.offline === 0 && c.screen_count > 0 && !/^xxx\b/i.test(c.cinema_name);

const parseScreening = (
  P: string,
  site: MyCloudCinemaSite,
  s: RawShowtime,
  venueId: string,
  fetchedAt: string,
): Screening => {
  const title = parseTitleExtension(s.title_extension, site.titleExtensions);
  const unmapped = [...title.unmapped];
  for (const [key, value] of Object.entries(s)) {
    if (key.startsWith("version_") && value === 1 && !MAPPED_VERSION_FLAGS.has(key)) {
      unmapped.push(key);
    }
  }

  const formats = new Set<Feature>(title.formats);
  if (s.version_atmos) {
    formats.add("atmos");
  }
  if (s.version_imax) {
    formats.add("imax");
  }
  if (s.version_dbox) {
    formats.add("dbox");
  }
  if (s.version_luxe) {
    formats.add("luxe");
  }

  // "EN & FI": a film spoken in both (Yön lapsi, 2026-10-22), not two versions.
  const audio = s.audio_lang ? normalizeLangs(s.audio_lang) : undefined;
  if (s.audio_lang && !audio) {
    unmapped.push(`audio_lang:${s.audio_lang}`);
  }

  const subtitles = parseSubtitles(s.subtitle_lang);
  if (subtitles.kind === "unknown" && s.subtitle_lang) {
    unmapped.push(`subtitle_lang:${s.subtitle_lang}`);
  }

  const tags: ScreeningTag[] = [...title.tags, ...(s.version_kids ? (["kids"] as const) : [])];
  // The screen's own limit (BioRex's K-18 screens) first, then what the label says.
  const ageLimit = parseScreenName(s.screen_name).ageLimit ?? title.ageLimit;
  const extensionText = s.title_extension?.trim();
  const status = availability(s);

  return {
    id: makeId(P, "show", s.show_time_id),
    provider: P,
    sourceId: String(s.show_time_id),
    venueId,
    auditoriumId: makeId(P, "screen", s.cinema_screen_id),
    listingId: makeId(P, "film", s.movie_id),
    startsAt: toHelsinkiIso(s.show_time),
    ...(s.show_time_end && { endsAt: toHelsinkiIso(s.show_time_end) }),
    businessDate: s.business_date.slice(0, 10),
    presentation: {
      projection: s.version_35mm
        ? "35mm"
        : s.version_70mm
          ? "70mm"
          : s.version_16mm
            ? "16mm"
            : "digital",
      dimension: s.version_3d ? "3d" : "2d",
      formats: [...formats],
    },
    audio: audio ?? [],
    ...(s.movie_audio_style_id === 1 && { dubbed: false }),
    ...(s.movie_audio_style_id === 2 && { dubbed: true }),
    subtitles,
    ...(ageLimit && { ageLimit }),
    tags,
    series: title.series,
    ...(title.licensed && { licensed: true }),
    availability: status,
    ...(status !== "not-bookable" && { ticketUrl: ticketUrl(site, s.show_time_id) }),
    unmappedLabels: unmapped,
    ...(extensionText && {
      labels: [{ source: "mycloudcinema.titleExtension", text: extensionText }],
    }),
    fetchedAt,
  };
};

const parseListing = (P: string, site: MyCloudCinemaSite, s: RawShowtime): FilmListing => {
  const rating = parseRating(s.rating);
  const extension = parseTitleExtension(s.title_extension, site.titleExtensions);
  return {
    id: makeId(P, "film", s.movie_id),
    provider: P,
    sourceId: String(s.movie_id),
    title: { fi: s.title.trim() },
    ...(s.running_time && s.running_time > 0 && { runtimeMinutes: s.running_time }),
    ...(rating && { rating }),
    genres: splitList(s.genre),
    countries: splitList(s.countries),
    // The platform does not mark event cinema; a site's label may ("Cine Konsertti").
    kind: extension.event ? "event" : "film",
  };
};

const parseAuditorium = (P: string, s: RawShowtime, venueId: string): Auditorium => {
  const { features, ageLimit } = parseScreenName(s.screen_name);
  return {
    id: makeId(P, "screen", s.cinema_screen_id),
    venueId,
    name: s.screen_name.trim(),
    features,
    ...(ageLimit && { ageLimit }),
  };
};

const unwrap = (response: unknown, warnings: Warning[], context: Record<string, unknown>) => {
  const envelope = Envelope.safeParse(response);
  if (!envelope.success) {
    warnings.push({ code: "invalid-envelope", message: envelope.error.message, context });
    return [];
  }
  if (envelope.data.resultCode !== undefined && envelope.data.resultCode !== 0) {
    warnings.push({
      code: "result-code",
      message: `resultCode ${envelope.data.resultCode}`,
      context,
    });
  }
  return envelope.data.data;
};

/** Pure: raw snapshot + site -> normalized batch. Invalid rows become warnings, never exceptions. */
export const parseMyCloudCinema = (
  raw: MyCloudCinemaRawSnapshot,
  site: MyCloudCinemaSite,
): ProviderBatch => {
  const P = site.provider;
  const warnings: Warning[] = [];
  const { fetchedAt } = raw;

  const venues = new Map<number, Venue>();
  for (const item of unwrap(raw.cinemas, warnings, { endpoint: "getCinemasList" })) {
    const cinema = RawCinema.safeParse(item);
    if (!cinema.success) {
      warnings.push({ code: "invalid-cinema", message: cinema.error.message, context: { item } });
      continue;
    }
    if (!isActiveCinema(cinema.data)) {
      continue;
    }
    if (site.cinemaIds && !site.cinemaIds.includes(cinema.data.cinema_id)) {
      continue;
    }
    const venue = parseVenue(P, site, cinema.data);
    if (!venue) {
      warnings.push({
        code: "venue-without-city",
        message: `No city for ${cinema.data.cinema_name}`,
        context: { cinemaId: cinema.data.cinema_id },
      });
      continue;
    }
    venues.set(cinema.data.cinema_id, venue);
  }

  const auditoriums = new Map<string, Auditorium>();
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  for (const [cinemaId, responses] of Object.entries(raw.showtimes)) {
    const venue = venues.get(Number(cinemaId));
    if (!venue) {
      warnings.push({
        code: "unknown-venue",
        message: `Showtimes for unknown or inactive cinema ${cinemaId}`,
      });
      continue;
    }
    const items = (Array.isArray(responses) ? responses : [responses]).flatMap((response) =>
      unwrap(response, warnings, { endpoint: "getShowTimesDays", cinemaId }),
    );
    for (const item of items) {
      const row = RawShowtime.safeParse(item);
      if (!row.success) {
        warnings.push({
          code: "invalid-showtime",
          message: row.error.message,
          context: { cinemaId, showTimeId: (item as { show_time_id?: unknown })?.show_time_id },
        });
        continue;
      }
      // A hall rented out ("Yritystapahtuma", "Tilavaraus - 6h"): nothing for the public.
      if (isPrivateBooking(row.data.title) || isPrivateBooking(row.data.title_extension ?? "")) {
        continue;
      }
      const screening = parseScreening(P, site, row.data, venue.id, fetchedAt);
      screenings.set(screening.id, screening);

      const auditorium = parseAuditorium(P, row.data, venue.id);
      auditoriums.set(auditorium.id, auditorium);

      const listing = parseListing(P, site, row.data);
      if (!listings.has(listing.id)) {
        listings.set(listing.id, listing);
      }
    }
  }

  return {
    provider: providerOf(site, "mycloudcinema", "buy"),
    fetchedAt,
    window: dateWindow(raw.from, raw.days),
    venues: [...venues.values()],
    auditoriums: [...auditoriums.values()],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
