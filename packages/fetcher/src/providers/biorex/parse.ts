import { normalizeLang } from "../../lib/lang.ts";
import { dateWindow, toHelsinkiIso } from "../../lib/time.ts";
import {
  makeId,
  type Auditorium,
  type Availability,
  type Feature,
  type FilmListing,
  type FinnishRating,
  type Lang,
  type Provider,
  type ProviderBatch,
  type Screening,
  type ScreeningTag,
  type Subtitles,
  type Venue,
  type Warning,
} from "@pgtm/model";
import { Envelope, RawCinema, RawShowtime, type BiorexRawSnapshot } from "./raw.ts";

export const PROVIDER: Provider = {
  id: "biorex",
  name: "BioRex",
  homepage: "https://biorex.fi",
  platform: "mycloudcinema",
  booking: "buy",
};

const P = PROVIDER.id;
const WEBSHOP = "https://webshop.biorex.fi";

/** The API leaves `city` empty for these (verified 2026-10-09). */
const CITY_OVERRIDES: Record<number, string> = {
  13: "Helsinki", // BioRex Tripla
  14: "Helsinki", // BioRex Redi
};

/** Same pattern the cinema's own site links to (data-click-data-layer on biorex.fi). */
export const ticketUrl = (showTimeId: number): string => `${WEBSHOP}/fi/#/book/${showTimeId}`;

const RATINGS: Record<string, FinnishRating> = {
  s: "S",
  "7": "K-7",
  "12": "K-12",
  "16": "K-16",
  "18": "K-18",
};

/** "rating_fi_12.svg" -> "K-12" */
export const parseRating = (icon: string | null | undefined): FinnishRating | undefined => {
  const match = icon?.match(/^rating_fi_(s|\d+)\.svg$/i);
  return match?.[1] ? RATINGS[match[1].toLowerCase()] : undefined;
};

/** "Suomi & Ruotsi -" / "SE" / "-" -> structured subtitles. */
export const parseSubtitles = (raw: string | null | undefined): Subtitles => {
  const value = raw?.trim();
  if (!value) return { kind: "unknown" };
  if (value === "-") return { kind: "none" };

  const parts = value
    .replace(/-$/, "")
    .split(/&|,|\//)
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

/** Splits `title_extension` into formats and labels we do not understand. */
export const parseTitleExtension = (
  raw: string | null | undefined,
): { formats: Feature[]; unmapped: string[] } => {
  const formats: Feature[] = [];
  const unmapped: string[] = [];
  for (const token of raw?.trim().split(/\s+/).filter(Boolean) ?? []) {
    const upper = token.toUpperCase();
    if (upper === "ATMOS") formats.push("atmos");
    else if (upper === "IMAX") formats.push("imax");
    else if (!LANGUAGE_TOKENS.has(upper)) unmapped.push(`title_extension:${token}`);
  }
  return { formats, unmapped };
};

/** "6 REX (K-18)" -> features and the hall's own age limit. */
export const parseScreenName = (
  name: string,
): { features: Feature[]; ageLimit?: FinnishRating } => {
  const features: Feature[] = [];
  if (/\bprime\b/i.test(name)) features.push("prime");
  if (/\bplus\b/i.test(name)) features.push("plus");
  if (/\bluxe\b/i.test(name)) features.push("luxe");
  if (/\bimax\b/i.test(name)) features.push("imax");
  const age = name.match(/\(K-(18|16|12|7)\)/)?.[1];
  const ageLimit = age ? RATINGS[age] : undefined;
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
  if (!s.bookable || !s.allow_purchases || s.show_locked) return "not-bookable";
  if (s.sold_out) return "sold-out";
  if (s.seats_low) return "few-left";
  return "available";
};

const parseVenue = (c: RawCinema): Venue | undefined => {
  const city = c.city?.trim() || CITY_OVERRIDES[c.cinema_id];
  if (!city) return undefined;
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

const parseScreening = (s: RawShowtime, venueId: string, fetchedAt: string): Screening => {
  const title = parseTitleExtension(s.title_extension);
  const unmapped = [...title.unmapped];
  for (const [key, value] of Object.entries(s)) {
    if (key.startsWith("version_") && value === 1 && !MAPPED_VERSION_FLAGS.has(key)) {
      unmapped.push(key);
    }
  }

  const formats = new Set<Feature>(title.formats);
  if (s.version_atmos) formats.add("atmos");
  if (s.version_imax) formats.add("imax");
  if (s.version_dbox) formats.add("dbox");
  if (s.version_luxe) formats.add("luxe");

  const audio = s.audio_lang ? normalizeLang(s.audio_lang) : undefined;
  if (s.audio_lang && !audio) unmapped.push(`audio_lang:${s.audio_lang}`);

  const subtitles = parseSubtitles(s.subtitle_lang);
  if (subtitles.kind === "unknown" && s.subtitle_lang) {
    unmapped.push(`subtitle_lang:${s.subtitle_lang}`);
  }

  const tags: ScreeningTag[] = s.version_kids ? ["kids"] : [];
  const { ageLimit } = parseScreenName(s.screen_name);
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
    audio: audio ? [audio] : [],
    ...(s.movie_audio_style_id === 1 && { dubbed: false }),
    ...(s.movie_audio_style_id === 2 && { dubbed: true }),
    subtitles,
    ...(ageLimit && { ageLimit }),
    tags,
    series: [],
    availability: status,
    ...(status !== "not-bookable" && { ticketUrl: ticketUrl(s.show_time_id) }),
    unmappedLabels: unmapped,
    fetchedAt,
  };
};

const parseListing = (s: RawShowtime): FilmListing => {
  const rating = parseRating(s.rating);
  return {
    id: makeId(P, "film", s.movie_id),
    provider: P,
    sourceId: String(s.movie_id),
    title: { fi: s.title.trim() },
    ...(s.running_time && s.running_time > 0 && { runtimeMinutes: s.running_time }),
    ...(rating && { rating }),
    genres: splitList(s.genre),
    countries: splitList(s.countries),
    // BioRex does not mark event cinema.
    kind: "film",
  };
};

const parseAuditorium = (s: RawShowtime, venueId: string): Auditorium => {
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

/** Pure: raw snapshot -> normalized batch. Invalid rows become warnings, never exceptions. */
export const parseBiorex = (raw: BiorexRawSnapshot): ProviderBatch => {
  const warnings: Warning[] = [];
  const { fetchedAt } = raw;

  const venues = new Map<number, Venue>();
  for (const item of unwrap(raw.cinemas, warnings, { endpoint: "getCinemasList" })) {
    const cinema = RawCinema.safeParse(item);
    if (!cinema.success) {
      warnings.push({ code: "invalid-cinema", message: cinema.error.message, context: { item } });
      continue;
    }
    if (!isActiveCinema(cinema.data)) continue;
    const venue = parseVenue(cinema.data);
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

  for (const [cinemaId, response] of Object.entries(raw.showtimes)) {
    const venue = venues.get(Number(cinemaId));
    if (!venue) {
      warnings.push({
        code: "unknown-venue",
        message: `Showtimes for unknown or inactive cinema ${cinemaId}`,
      });
      continue;
    }
    for (const item of unwrap(response, warnings, { endpoint: "getShowTimesDays", cinemaId })) {
      const row = RawShowtime.safeParse(item);
      if (!row.success) {
        warnings.push({
          code: "invalid-showtime",
          message: row.error.message,
          context: { cinemaId, showTimeId: (item as { show_time_id?: unknown })?.show_time_id },
        });
        continue;
      }
      const screening = parseScreening(row.data, venue.id, fetchedAt);
      screenings.set(screening.id, screening);

      const auditorium = parseAuditorium(row.data, venue.id);
      auditoriums.set(auditorium.id, auditorium);

      const listing = parseListing(row.data);
      if (!listings.has(listing.id)) listings.set(listing.id, listing);
    }
  }

  return {
    provider: PROVIDER,
    fetchedAt,
    window: dateWindow(raw.from, raw.days),
    venues: [...venues.values()],
    auditoriums: [...auditoriums.values()],
    listings: [...listings.values()],
    screenings: [...screenings.values()].sort(
      (a, b) => Date.parse(a.startsAt) - Date.parse(b.startsAt) || a.id.localeCompare(b.id),
    ),
    warnings,
  };
};
