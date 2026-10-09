import type { FinnishRating } from "../model/schema.ts";
import type { MovieDetails } from "../tmdb/raw.ts";
import { normalizeTitle, titlePrefix } from "./titles.ts";

export type ListingFacts = {
  title: string;
  runtimeMinutes?: number;
  /** ISO 3166-1 alpha-2 */
  countries: string[];
  year?: number;
  rating?: FinnishRating;
};

export type Evidence = {
  tmdbId: number;
  title: "exact" | "prefix" | "none";
  year: "window" | "listing" | "outside" | "unknown";
  runtime: "close" | "near" | "far" | "unknown";
  countries: "overlap" | "disjoint" | "unknown";
  /** Cinema's age rating vs. TMDB's Finnish certification. Only used to break ties. */
  rating: "same" | "different" | "unknown";
};

/** Films in cinemas are almost always recent; older ones need stronger evidence. */
const WINDOW_BEFORE = 3;
const WINDOW_AFTER = 1;

/** What may follow the prefix in a sequel's title: " 2", " ii"... */
const SEQUEL = /^ (\d{1,2}|ii|iii|iv|v|vi)$/;

const candidateTitles = (details: MovieDetails): string[] => [
  details.title,
  details.original_title,
  ...details.translations.translations.flatMap((t) => (t.data.title ? [t.data.title] : [])),
  ...details.alternative_titles.titles.map((t) => t.title),
];

export const gatherEvidence = (
  listing: ListingFacts,
  details: MovieDetails,
  currentYear: number,
): Evidence => {
  const titles = candidateTitles(details).map(normalizeTitle);
  const wanted = normalizeTitle(listing.title);
  const prefix = titlePrefix(listing.title);
  const normalizedPrefix = prefix && normalizeTitle(prefix);

  const releaseYear = details.release_date ? Number(details.release_date.slice(0, 4)) : undefined;

  // A prefix match is only "the same title, possibly numbered": "Practical Magic 2" for
  // "Practical Magic: Lumotut sisaret". "Ryhmä Hau: Mahtipennut" is a different film of the
  // same franchise and must not match "Ryhmä Hau: Dinoelokuva". Only brand-new films qualify.
  const isPrefixMatch = (t: string) =>
    t === normalizedPrefix || SEQUEL.test(t.slice(normalizedPrefix!.length));
  const title = titles.includes(wanted)
    ? "exact"
    : normalizedPrefix &&
        releaseYear !== undefined &&
        releaseYear >= currentYear - 1 &&
        titles.some((t) => t.startsWith(normalizedPrefix) && isPrefixMatch(t))
      ? "prefix"
      : "none";

  const year =
    releaseYear === undefined
      ? "unknown"
      : listing.year !== undefined && Math.abs(listing.year - releaseYear) <= 1
        ? "listing"
        : releaseYear >= currentYear - WINDOW_BEFORE && releaseYear <= currentYear + WINDOW_AFTER
          ? "window"
          : "outside";

  const delta =
    listing.runtimeMinutes && details.runtime
      ? Math.abs(listing.runtimeMinutes - details.runtime)
      : undefined;
  const runtime =
    delta === undefined ? "unknown" : delta <= 3 ? "close" : delta <= 8 ? "near" : "far";

  const theirs = details.production_countries.map((c) => c.iso_3166_1);
  const countries =
    listing.countries.length === 0 || theirs.length === 0
      ? "unknown"
      : listing.countries.some((c) => theirs.includes(c))
        ? "overlap"
        : "disjoint";

  const certification = details.release_dates.results
    .find((r) => r.iso_3166_1 === "FI")
    ?.release_dates.map((d) => d.certification?.trim())
    .find(Boolean);
  const rating =
    !listing.rating || !certification
      ? "unknown"
      : listing.rating === certification
        ? "same"
        : "different";

  return { tmdbId: details.id, title, year, runtime, countries, rating };
};

export type Tier = "exact" | "prefix" | "sparse";

/**
 * "Certain or nothing": a wrong poster is worse than a missing one. Tiers, strongest first:
 * - `exact`: exact title, plausible year, no contradiction, and runtime or countries agree.
 *   An old film (outside the year window) needs both runtime and countries.
 * - `prefix`: title matches only up to the subtitle ("Practical Magic: …" -> "Practical
 *   Magic 2"); needs close runtime, overlapping countries and a recent year.
 * - `sparse`: exact title and recent year, but TMDB has neither runtime nor countries
 *   (typical for small Finnish films). Accepted only if it is the sole candidate in its tier.
 */
export const tierOf = (e: Evidence): Tier | undefined => {
  if (e.runtime === "far" || e.countries === "disjoint") return undefined;
  const recent = e.year === "window" || e.year === "listing";
  const corroborated = e.runtime === "close" || e.runtime === "near" || e.countries === "overlap";
  const strong = e.runtime === "close" && e.countries === "overlap";

  if (e.title === "exact") {
    if (recent ? corroborated : strong) return "exact";
    if (recent && e.runtime === "unknown" && e.countries === "unknown") return "sparse";
  }
  if (e.title === "prefix" && recent && strong) return "prefix";
  return undefined;
};

export type Decision =
  | { kind: "match"; tmdbId: number; tier: Tier }
  | { kind: "none"; reason: string };

/**
 * Two films with the same title in one tier ("The Furious", 2026, twice): prefer the only
 * one whose runtime is within 3 minutes, then the only one whose Finnish rating agrees.
 */
const TIE_BREAKERS: ((e: Evidence) => boolean)[] = [
  (e) => e.runtime === "close",
  (e) => e.rating === "same",
];

/** The strongest tier with any candidate decides; an unbreakable tie there is ambiguous. */
export const decide = (evidence: Evidence[]): Decision => {
  for (const tier of ["exact", "prefix", "sparse"] as const) {
    let inTier = evidence.filter((e) => tierOf(e) === tier);
    for (const prefer of TIE_BREAKERS) {
      if (inTier.length <= 1) break;
      const preferred = inTier.filter(prefer);
      if (preferred.length > 0) inTier = preferred;
    }
    if (inTier.length === 1) return { kind: "match", tmdbId: inTier[0]!.tmdbId, tier };
    if (inTier.length > 1) {
      return {
        kind: "none",
        reason: `ambiguous (${tier}): ${inTier.map((e) => e.tmdbId).join(", ")}`,
      };
    }
  }
  if (evidence.length === 0) return { kind: "none", reason: "no search results" };
  const best = evidence.find((e) => e.title !== "none") ?? evidence[0]!;
  return {
    kind: "none",
    reason: `not confident (best ${best.tmdbId}: title ${best.title}, year ${best.year}, runtime ${best.runtime}, countries ${best.countries})`,
  };
};
