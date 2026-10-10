import type { FilmDetails, ListingDetails, RatingRow, ShowtimeRow } from "./showtimes.ts";

/** Pure text formatting for the `showtimes` CLI. */

const TMDB_POSTER = "https://image.tmdb.org/t/p/w500";

const time = (d: Date) =>
  d.toLocaleTimeString("fi-FI", {
    timeZone: "Europe/Helsinki",
    hour: "2-digit",
    minute: "2-digit",
  });

const list = (items: string[]) => items.join(", ");

const RATING_LABELS: Record<string, string> = {
  "rotten-tomatoes": "RT",
  metacritic: "Metacritic",
  imdb: "IMDb",
  tmdb: "TMDB",
};

/** 199714 -> "200k", 1497908 -> "1.5M". */
const compactVotes = (n: number) =>
  n >= 1_000_000
    ? `${(n / 1_000_000).toFixed(1)}M`
    : n >= 1000
      ? `${Math.round(n / 1000)}k`
      : String(n);

/** "RT 93% · Metacritic 81 · IMDb 7.9 (200k) · TMDB 7.9" */
export const formatRatings = (ratings: RatingRow[]): string =>
  ratings
    .map((r) => {
      const value = r.display.replace(/\/(10|100)$/, "");
      const votes = r.votes ? ` (${compactVotes(r.votes)})` : "";
      return `${RATING_LABELS[r.source] ?? r.source} ${value}${r.source === "imdb" ? votes : ""}`;
    })
    .join(" · ");

/** "EN, subs FI/SV" or "FI" or "?" */
export const languageLabel = (
  row: Pick<ShowtimeRow, "audio" | "subtitlesKind" | "subtitlesLanguages">,
): string => {
  const audio = row.audio.length ? row.audio.map((l) => l.toUpperCase()).join("+") : "?";
  return row.subtitlesKind === "languages"
    ? `${audio}, subs ${row.subtitlesLanguages.map((l) => l.toUpperCase()).join("/")}`
    : audio;
};

const extras = (row: ShowtimeRow) =>
  [
    ...row.formats.map((f) =>
      f === "imax" ? "IMAX" : f === "luxe" ? "LUXE" : f === "isense" ? "iSense" : f,
    ),
    ...(row.licensed ? ["bar"] : []),
    ...(row.ageLimit ? [row.ageLimit] : []),
    ...(row.availability !== "available" && row.availability !== "unknown"
      ? [row.availability]
      : []),
  ].join(" ");

/** Left-aligned columns, two spaces apart; long cells are not truncated. */
export const table = (header: string[], rows: string[][]): string => {
  const widths = header.map((h, i) => Math.max(h.length, ...rows.map((r) => (r[i] ?? "").length)));
  const line = (cells: string[]) =>
    cells
      .map((c, i) => c.padEnd(widths[i]!))
      .join("  ")
      .trimEnd();
  return [line(header), line(widths.map((w) => "-".repeat(w))), ...rows.map(line)].join("\n");
};

/** "3.5" under 10 km, whole kilometres above. */
const km = (d: number) => (d < 10 ? d.toFixed(1) : d.toFixed(0));

export const formatScreenings = (
  rows: ShowtimeRow[],
  withLinks: boolean,
  { withFilm = false, withRatings = false } = {},
): string => {
  if (rows.length === 0) return "  No screenings found.";
  const withDistance = rows.some((r) => r.distanceKm !== null);
  const header = [
    "Time",
    ...(withDistance ? ["Km"] : []),
    "City",
    "Venue",
    ...(withFilm ? ["Film"] : []),
    ...(withFilm && withRatings ? ["RT", "IMDb"] : []),
    "Screen",
    "Language",
    "Extras",
    ...(withLinks ? ["Tickets"] : []),
  ];
  const body = rows.map((r) => [
    time(r.startsAt),
    ...(withDistance ? [r.distanceKm === null ? "" : km(r.distanceKm)] : []),
    r.city,
    r.venue,
    ...(withFilm ? [r.film] : []),
    ...(withFilm && withRatings
      ? [
          r.rottenTomatoes === null ? "" : `${r.rottenTomatoes}%`,
          r.imdb === null ? "" : (r.imdb / 10).toFixed(1),
        ]
      : []),
    r.screen ?? "",
    languageLabel(r),
    extras(r),
    ...(withLinks ? [r.ticketUrl ?? ""] : []),
  ]);
  return table(header, body)
    .split("\n")
    .map((l) => `  ${l}`)
    .join("\n");
};

/** Ratings are opt-in: some people do not want to know what critics thought beforehand. */
export const formatFilm = (
  film: FilmDetails,
  score: number,
  { withRatings = false } = {},
): string => {
  const title = film.titleFi ?? film.localTitle ?? film.titleEn ?? film.originalTitle;
  const year = film.releaseDate?.slice(0, 4);
  const facts = [
    year,
    film.runtimeMinutes && `${film.runtimeMinutes} min`,
    film.rating,
    list(film.genres),
    list(film.countries),
  ].filter(Boolean);
  const overview = film.overviewFi ?? film.overviewEn ?? film.overviewSv;
  return [
    `${title}${title !== film.originalTitle ? ` (${film.originalTitle})` : ""}  [match ${score.toFixed(2)}]`,
    `  ${facts.join(" · ")}`,
    ...(withRatings && film.ratings.length ? [`  ${formatRatings(film.ratings)}`] : []),
    ...(film.finnishReleaseDate ? [`  Finnish premiere ${film.finnishReleaseDate}`] : []),
    `  ${film.id}${film.imdbId ? ` · https://www.imdb.com/title/${film.imdbId}/` : ""}`,
    ...(film.posterPath ? [`  Poster ${TMDB_POSTER}${film.posterPath}`] : []),
    ...(overview ? [`  ${overview.length > 300 ? `${overview.slice(0, 297)}...` : overview}`] : []),
  ].join("\n");
};

export const formatListing = (listing: ListingDetails, score: number): string => {
  const title = listing.titleFi ?? listing.titleEn ?? listing.titleSv ?? listing.sourceId;
  const facts = [
    listing.kind === "event" ? "event" : "not on TMDB",
    listing.runtimeMinutes && `${listing.runtimeMinutes} min`,
    listing.rating,
    list(listing.genres),
  ].filter(Boolean);
  return [
    `${title}  [match ${score.toFixed(2)}]`,
    `  ${facts.join(" · ")}`,
    `  ${listing.id}`,
  ].join("\n");
};
