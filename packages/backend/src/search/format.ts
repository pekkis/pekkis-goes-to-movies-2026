import type { FilmDetails, ListingDetails, ShowtimeRow } from "./showtimes.ts";

/** Pure text formatting for the `showtimes` CLI. */

const TMDB_POSTER = "https://image.tmdb.org/t/p/w500";

const time = (d: Date) =>
  d.toLocaleTimeString("fi-FI", {
    timeZone: "Europe/Helsinki",
    hour: "2-digit",
    minute: "2-digit",
  });

const list = (items: string[]) => items.join(", ");

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

export const formatScreenings = (rows: ShowtimeRow[], withLinks: boolean): string => {
  if (rows.length === 0) return "  No screenings on this date.";
  const header = [
    "Time",
    "City",
    "Venue",
    "Screen",
    "Language",
    "Extras",
    ...(withLinks ? ["Tickets"] : []),
  ];
  const body = rows.map((r) => [
    time(r.startsAt),
    r.city,
    r.venue,
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

export const formatFilm = (film: FilmDetails, score: number): string => {
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
