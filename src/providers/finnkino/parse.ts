import { normalizeLang } from "../../lib/lang.ts";
import { toHelsinkiIso } from "../../lib/time.ts";
import {
  makeId,
  type Auditorium,
  type Availability,
  type Feature,
  type FilmListing,
  type FinnishRating,
  type Lang,
  type Localized,
  type Provider,
  type ProviderBatch,
  type Screening,
  type ScreeningTag,
  type Subtitles,
  type Venue,
  type Warning,
} from "../../model/schema.ts";
import {
  RawAdvanceBookingRule,
  RawAttribute,
  RawCensorRating,
  RawFilm,
  RawGenre,
  RawScreen,
  RawShowtime,
  RawSite,
  ShowtimesResponse,
  SitesResponse,
  type FinnkinoRawSnapshot,
  type Text,
} from "./raw.ts";

export const PROVIDER: Provider = {
  id: "finnkino",
  name: "Finnkino",
  homepage: "https://www.finnkino.fi",
  platform: "vista-ocapi",
  booking: "buy",
};

const P = PROVIDER.id;

/** Verified 2026-10-09 by clicking a showtime on finnkino.fi. */
export const ticketUrl = (showtimeId: string): string =>
  `https://www.finnkino.fi/liput/valitse-paikat/?showtimeId=${encodeURIComponent(showtimeId)}`;

/** Finnkino's own language codes where they are not ISO 639-1 (SE is handled by normalizeLang). */
const FINNKINO_LANGS: Record<string, Lang> = { tu: "tr", ma: "ml", li: "lt" };

const toLang = (code: string): Lang | undefined =>
  FINNKINO_LANGS[code.toLowerCase()] ?? normalizeLang(code);

/** "KO-JA-A" -> spoken Korean and Japanese; "SE-S" -> Swedish subtitles. */
export const parseLanguageAttribute = (
  shortName: string,
): { role: "audio" | "subtitles"; languages: Lang[] } | undefined => {
  const match = shortName.match(/^([A-Z]{2}(?:-[A-Z]{2})*)-([AS])$/);
  if (!match?.[1]) return undefined;
  const languages = match[1].split("-").map(toLang);
  if (languages.some((lang) => lang === undefined)) return undefined;
  return { role: match[2] === "A" ? "audio" : "subtitles", languages: languages as Lang[] };
};

const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  "7": "K-7",
  "12": "K-12",
  "16": "K-16",
  "18": "K-18",
};

/** "16 VA" -> "K-16" (letters describe content); "Tulossa" (pending) -> undefined. */
export const parseRating = (classification: string | undefined): FinnishRating | undefined => {
  const age = classification?.trim().match(/^(S|7|12|16|18)\b/)?.[1];
  return age ? RATINGS[age] : undefined;
};

const FORMATS: Record<string, Feature> = {
  IMAX: "imax",
  iSense: "isense",
  LUXE: "luxe",
  "4DX": "4dx",
  ScreenX: "screenx",
};

const TAGS: Record<string, ScreeningTag> = {
  Ennakko: "preview",
  EventCine: "event-cinema",
};

/**
 * Attributes that carry no information for viewers: regional marketing groups, a site
 * name, and an internal booking setting.
 */
const IGNORED = new Set(["Tampere", "Pkseutu", "TKU & R", "Maxim", "Varaus20"]);

const localized = (text: Text): Localized => {
  const out: Localized = {};
  if (text.text.trim()) out.fi = text.text.trim();
  for (const t of text.translations ?? []) {
    const lang = t.languageTag.slice(0, 2).toLowerCase();
    if ((lang === "en" || lang === "sv") && !out[lang] && t.text.trim()) out[lang] = t.text.trim();
  }
  return out;
};

type Lookup = {
  attributes: Map<string, string>;
  ratings: Map<string, string>;
  genres: Map<string, string>;
  rules: Map<string, RawAdvanceBookingRule>;
};

const ruleKey = (siteId: string, filmId: string) => `${siteId}|${filmId}`;

const availability = (s: RawShowtime, lookup: Lookup, fetchedAt: string): Availability => {
  if (s.isSoldOut) return "sold-out";
  if (s.restrictions.includes("FilmAdvanceBookingRule")) {
    // The rule says when sales open (all restrictions were "None" when profiled).
    const rule = lookup.rules.get(ruleKey(s.siteId, s.filmId));
    const opens = rule?.bookingPeriods.map((p) => Date.parse(p.startsAt)).sort((a, b) => a - b)[0];
    if (opens !== undefined && opens > Date.parse(fetchedAt)) return "not-bookable";
  }
  return "available";
};

const parseScreening = (s: RawShowtime, lookup: Lookup, fetchedAt: string): Screening => {
  const audio: Lang[] = [];
  const subtitleLangs: Lang[] = [];
  const formats: Feature[] = [];
  const tags: ScreeningTag[] = [];
  const unmapped: string[] = [];
  let dimension: "2d" | "3d" = s.requires3dGlasses ? "3d" : "2d";
  let licensed = false;
  let ageLimit: FinnishRating | undefined;
  let captions = false;

  for (const attributeId of s.attributeIds) {
    const name = lookup.attributes.get(attributeId);
    if (name === undefined) {
      unmapped.push(`attribute:${attributeId}`);
      continue;
    }
    const language = parseLanguageAttribute(name);
    if (language) {
      (language.role === "audio" ? audio : subtitleLangs).push(...language.languages);
    } else if (name === "2D") dimension = "2d";
    else if (name === "3D") dimension = "3d";
    else if (name in FORMATS) formats.push(FORMATS[name]!);
    else if (name in TAGS) tags.push(TAGS[name]!);
    else if (name === "Annisk_K18") {
      licensed = true;
      ageLimit = "K-18";
    } else if (name === "Anniskelu") licensed = true;
    else if (name === "OCAP") {
      // Open captions: Finnish subtitles for the hard of hearing.
      captions = true;
      tags.push("accessible");
    } else if (name === "SEVERAL") {
      // "Several languages": spoken languages not listed, so audio stays unknown.
    } else if (!IGNORED.has(name)) unmapped.push(name);
  }

  if (captions && !subtitleLangs.includes("fi")) subtitleLangs.push("fi");
  const subtitles: Subtitles =
    subtitleLangs.length > 0
      ? { kind: "languages", languages: [...new Set(subtitleLangs)] }
      : audio.length > 0
        ? // Finnkino lists subtitles consistently; spoken language without any means none.
          { kind: "none" }
        : { kind: "unknown" };

  const status = availability(s, lookup, fetchedAt);
  return {
    id: makeId(P, "show", s.id),
    provider: P,
    sourceId: s.id,
    venueId: makeId(P, "venue", s.siteId),
    auditoriumId: makeId(P, "screen", s.screenId),
    listingId: makeId(P, "film", s.filmId),
    startsAt: toHelsinkiIso(s.schedule.startsAt),
    ...(s.schedule.endsAt && { endsAt: toHelsinkiIso(s.schedule.endsAt) }),
    businessDate: s.schedule.businessDate,
    presentation: { projection: "digital", dimension, formats },
    audio: [...new Set(audio)],
    subtitles,
    ...(ageLimit && { ageLimit }),
    ...(licensed && { licensed }),
    tags,
    series: [],
    availability: status,
    ...(status !== "not-bookable" && { ticketUrl: ticketUrl(s.id) }),
    unmappedLabels: unmapped,
    fetchedAt,
  };
};

/** Finnkino files operas, concerts and the like under this genre (and the EventCine attribute). */
const EVENT_GENRE = "Event cinema";

const parseListing = (film: RawFilm, lookup: Lookup, isEvent: boolean): FilmListing => {
  const rating = parseRating(
    film.censorRatingId ? lookup.ratings.get(film.censorRatingId) : undefined,
  );
  const genres = (film.genreIds ?? []).flatMap((id) => {
    const name = lookup.genres.get(id);
    return name ? [name] : [];
  });
  return {
    id: makeId(P, "film", film.id),
    provider: P,
    sourceId: film.id,
    title: localized(film.title),
    ...(film.runtimeInMinutes &&
      film.runtimeInMinutes > 0 && { runtimeMinutes: film.runtimeInMinutes }),
    ...(rating && { rating }),
    genres,
    // Finnkino publishes no production countries.
    countries: [],
    kind: isEvent || genres.includes(EVENT_GENRE) ? "event" : "film",
  };
};

const parseVenue = (site: RawSite): Venue | undefined => {
  const address = site.contactDetails?.address;
  const city = address?.city?.trim();
  if (!city) return undefined;
  const street = address?.line1?.trim();
  const postalCode = address?.line2?.trim();
  return {
    id: makeId(P, "venue", site.id),
    provider: P,
    sourceId: site.id,
    name: site.name.text.trim(),
    city,
    ...(street && { address: street }),
    ...(postalCode && /^\d{5}$/.test(postalCode) && { postalCode }),
    ...(site.location && { geo: { lat: site.location.latitude, lon: site.location.longitude } }),
  };
};

/** Validates every item of a list, collecting failures as warnings. */
const each = <T>(
  items: unknown[] | null | undefined,
  schema: {
    safeParse: (v: unknown) => { success: true; data: T } | { success: false; error: Error };
  },
  code: string,
  warnings: Warning[],
): T[] =>
  (items ?? []).flatMap((item) => {
    const result = schema.safeParse(item);
    if (result.success) return [result.data];
    warnings.push({ code, message: result.error.message, context: { item } });
    return [];
  });

/** Pure: raw snapshot -> normalized batch. Invalid rows become warnings, never exceptions. */
export const parseFinnkino = (raw: FinnkinoRawSnapshot): ProviderBatch => {
  const warnings: Warning[] = [];
  const { fetchedAt } = raw;

  const sitesResponse = SitesResponse.safeParse(raw.sites);
  if (!sitesResponse.success) {
    warnings.push({ code: "invalid-sites", message: sitesResponse.error.message });
  }
  const venues = new Map<string, Venue>();
  for (const site of each(sitesResponse.data?.sites, RawSite, "invalid-site", warnings)) {
    const venue = parseVenue(site);
    if (venue) venues.set(site.id, venue);
    else warnings.push({ code: "venue-without-city", message: `No city for site ${site.id}` });
  }

  const lookup: Lookup = {
    attributes: new Map(),
    ratings: new Map(),
    genres: new Map(),
    rules: new Map(),
  };
  const films = new Map<string, RawFilm>();
  const screens = new Map<string, string>();
  const showtimes: RawShowtime[] = [];

  for (const [date, response] of Object.entries(raw.showtimes)) {
    const parsed = ShowtimesResponse.safeParse(response);
    if (!parsed.success) {
      warnings.push({
        code: "invalid-showtimes",
        message: parsed.error.message,
        context: { date },
      });
      continue;
    }
    const related = parsed.data.relatedData;
    for (const a of each(related.attributes, RawAttribute, "invalid-attribute", warnings)) {
      lookup.attributes.set(a.id, a.shortName.text.trim());
    }
    for (const r of each(related.censorRatings, RawCensorRating, "invalid-rating", warnings)) {
      lookup.ratings.set(r.id, r.classification.text);
    }
    for (const g of each(related.genres, RawGenre, "invalid-genre", warnings)) {
      lookup.genres.set(g.id, g.name.text.trim());
    }
    for (const r of each(
      related.filmAdvanceBookingRules,
      RawAdvanceBookingRule,
      "invalid-rule",
      warnings,
    )) {
      lookup.rules.set(ruleKey(r.siteId, r.filmId), r);
    }
    for (const f of each(related.films, RawFilm, "invalid-film", warnings)) films.set(f.id, f);
    for (const s of each(related.screens, RawScreen, "invalid-screen", warnings)) {
      screens.set(s.id, s.name.text.trim());
    }
    showtimes.push(...each(parsed.data.showtimes, RawShowtime, "invalid-showtime", warnings));
  }

  const auditoriums = new Map<string, Auditorium>();
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  for (const s of showtimes) {
    if (!venues.has(s.siteId)) {
      warnings.push({
        code: "unknown-venue",
        message: `Showtime ${s.id} at unknown site ${s.siteId}`,
      });
      continue;
    }
    const film = films.get(s.filmId);
    if (!film) {
      warnings.push({
        code: "unknown-film",
        message: `Showtime ${s.id} refers to unknown film ${s.filmId}`,
      });
      continue;
    }
    const screening = parseScreening(s, lookup, fetchedAt);
    screenings.set(screening.id, screening);

    const auditoriumId = makeId(P, "screen", s.screenId);
    if (!auditoriums.has(auditoriumId)) {
      auditoriums.set(auditoriumId, {
        id: auditoriumId,
        venueId: makeId(P, "venue", s.siteId),
        name: screens.get(s.screenId) ?? s.screenId,
        features: [],
      });
    }
    const existing = listings.get(screening.listingId);
    if (!existing || (existing.kind === "film" && screening.tags.includes("event-cinema"))) {
      listings.set(
        screening.listingId,
        parseListing(film, lookup, screening.tags.includes("event-cinema")),
      );
    }
  }

  return {
    provider: PROVIDER,
    fetchedAt,
    venues: [...venues.values()],
    auditoriums: [...auditoriums.values()],
    listings: [...listings.values()],
    screenings: [...screenings.values()].sort(
      (a, b) => Date.parse(a.startsAt) - Date.parse(b.startsAt) || a.id.localeCompare(b.id),
    ),
    warnings,
  };
};
