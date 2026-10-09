import type { Film, FilmListing, Unmatched } from "../model/schema.ts";
import type { TmdbClient } from "../tmdb/client.ts";
import { toFilm } from "../tmdb/film.ts";
import type { MovieDetails, SearchResult } from "../tmdb/raw.ts";
import type { Aliases } from "./aliases.ts";
import { toCountryCodes } from "./countries.ts";
import { decide, gatherEvidence, type ListingFacts } from "./score.ts";
import { titlePrefix } from "./titles.ts";

/** How many search hits get their details fetched and scored. */
const MAX_CANDIDATES = 5;

export type MatchOutcome = {
  films: Film[];
  /** listing id -> decision */
  links: Map<string, { filmId: string; method: "auto" | "alias" }>;
  unmatched: Unmatched[];
};

const yearOf = (date: string | null | undefined) =>
  date ? Number(date.slice(0, 4)) || undefined : undefined;

/** Recent films first, then by popularity, so the details budget goes to likely hits. */
const rankHits = (hits: SearchResult[], currentYear: number): SearchResult[] =>
  [...new Map(hits.map((h) => [h.id, h])).values()].sort((a, b) => {
    const recent = (h: SearchResult) => ((yearOf(h.release_date) ?? 0) >= currentYear - 3 ? 1 : 0);
    return recent(b) - recent(a) || (b.popularity ?? 0) - (a.popularity ?? 0);
  });

export const matchListings = async (
  listings: FilmListing[],
  tmdb: TmdbClient,
  aliases: Aliases,
  now: Date = new Date(),
): Promise<MatchOutcome> => {
  const fetchedAt = now.toISOString();
  const currentYear = now.getUTCFullYear();
  const films = new Map<number, Film>();
  const links: MatchOutcome["links"] = new Map();
  const unmatched: Unmatched[] = [];

  const keep = (details: MovieDetails) => {
    if (!films.has(details.id)) films.set(details.id, toFilm(details, fetchedAt));
    return `tmdb:${details.id}`;
  };

  for (const listing of listings) {
    const title = listing.title.fi ?? listing.title.en ?? listing.title.sv;
    if (!title) continue;

    const alias = aliases[listing.id];
    if (alias) {
      if (alias.tmdb !== null) {
        links.set(listing.id, { filmId: keep(await tmdb.movie(alias.tmdb)), method: "alias" });
      }
      continue;
    }

    const facts: ListingFacts = {
      title,
      countries: toCountryCodes(listing.countries),
      ...(listing.runtimeMinutes && { runtimeMinutes: listing.runtimeMinutes }),
      ...(listing.year && { year: listing.year }),
    };
    const queries = [title, titlePrefix(title)].filter((q): q is string => Boolean(q));
    const hits = (await Promise.all(queries.map((q) => tmdb.search(q)))).flat();
    const ranked = rankHits(hits, currentYear).slice(0, MAX_CANDIDATES);
    const details = await Promise.all(ranked.map((hit) => tmdb.movie(hit.id)));
    const decision = decide(details.map((d) => gatherEvidence(facts, d, currentYear)));

    if (decision.kind === "match") {
      const chosen = details.find((d) => d.id === decision.tmdbId)!;
      links.set(listing.id, { filmId: keep(chosen), method: "auto" });
    } else {
      unmatched.push({
        listingId: listing.id,
        title,
        reason: decision.reason,
        candidates: ranked.map((hit) => {
          const year = yearOf(hit.release_date);
          return { tmdbId: hit.id, title: hit.title, ...(year && { year }) };
        }),
      });
    }
  }

  return { films: [...films.values()], links, unmatched };
};
