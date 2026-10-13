import { z } from "zod";

/**
 * Gilda's booking API: a WordPress facade over its MyCloudCinema data, the endpoint the
 * cinema's own React programme reads (`/wp-json/gilda-react-booking/v1/movies`). One GET
 * returns every film with its showtimes. Only fields we read; the rest passes through.
 * Profiled 2026-10-13 over 202 showtimes of 53 films.
 */

/** Booleans arrive as true/false, "1"/"0" or 1/0 depending on the field. */
const Flag = z.union([z.boolean(), z.literal("1"), z.literal("0"), z.literal(1), z.literal(0)]);
export const isSet = (flag: z.infer<typeof Flag> | null | undefined): boolean =>
  flag === true || flag === "1" || flag === 1;

export const GildaShow = z.looseObject({
  show_time_id: z.number().int(),
  movie_id: z.number().int(),
  cinema_screen_id: z.number().int(),
  /** "Gilda 1", "Bio Rex Lasipalatsi (K-18)" */
  screen_name: z.string(),
  /** The title as the cinema lists it, labels included ("Seniorikino: Lapin Sota"). */
  movie_name: z.string(),
  original_title: z.string().nullish(),
  /** UTC with an offset: "2026-10-23T15:00:00.000+00:00". */
  show_time: z.string(),
  running_time: z.number().int().nullish(),
  /** Bare: "7", "12", "16", "18", "S"; "T" and "EI MÄÄR." are unrated. */
  rating_name: z.string().nullish(),
  /** A code ("EN", "SE"), "MULTI", or "Ei puhetta". */
  audio_lang: z.string().nullish(),
  /** "suomi, ruotsi", "SE", "FI", "-" */
  subtitle_lang: z.string().nullish(),
  /** "Tekstitetty", "Ei tekstitystä", "Dubattu", "Albumikuuntelu" (album listening). */
  movie_audio_style_name: z.string().nullish(),
  /** "Atmos" or "". */
  movie_sound_name: z.string().nullish(),
  allow_purchases: Flag.nullish(),
  show_is_visible: Flag.nullish(),
  deleted: Flag.nullish(),
  version_3d: Flag.nullish(),
  version_35mm: Flag.nullish(),
  version_70mm: Flag.nullish(),
  version_16mm: Flag.nullish(),
  version_atmos: Flag.nullish(),
  version_imax: Flag.nullish(),
});
export type GildaShow = z.infer<typeof GildaShow>;

export const GildaFilm = z.looseObject({
  movie_id: z.number().int(),
  /** "tt28088049" or empty. */
  imdb_id: z.string().nullish(),
  /** "Draama, Seikkailu" */
  genre: z.string().nullish(),
  show_times: z.array(z.unknown()),
});
export type GildaFilm = z.infer<typeof GildaFilm>;

export const MoviesResponse = z.looseObject({
  fi: z.looseObject({ resultCode: z.number().optional(), data: z.array(z.unknown()) }),
});

/** Gilda's public WordPress film pages: where a film's showtimes are booked. */
export const FilmPost = z.looseObject({
  link: z.url(),
  title: z.looseObject({ rendered: z.string() }),
});

export type GildaRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  movies: unknown;
  /** `/wp-json/wp/v2/movies?per_page=100&_fields=link,title`: film page links. */
  posts: unknown;
};
