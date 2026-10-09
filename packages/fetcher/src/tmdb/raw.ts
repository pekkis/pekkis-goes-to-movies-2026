import { z } from "zod";

/** TMDB v3 response shapes. Only fields we read; the rest passes through. */

export const SearchResult = z.looseObject({
  id: z.number().int(),
  title: z.string(),
  original_title: z.string(),
  release_date: z.string().nullish(),
  popularity: z.number().nullish(),
});
export type SearchResult = z.infer<typeof SearchResult>;

export const SearchResponse = z.looseObject({
  results: z.array(SearchResult),
  total_results: z.number().int(),
});

const Translation = z.looseObject({
  iso_639_1: z.string(),
  iso_3166_1: z.string(),
  data: z.looseObject({
    title: z.string().nullish(),
    overview: z.string().nullish(),
  }),
});

const Image = z.looseObject({
  file_path: z.string(),
  iso_639_1: z.string().nullable(),
  vote_average: z.number().nullish(),
});

export const MovieDetails = z.looseObject({
  id: z.number().int(),
  imdb_id: z.string().nullish(),
  title: z.string(),
  original_title: z.string(),
  original_language: z.string().nullish(),
  release_date: z.string().nullish(),
  runtime: z.number().int().nullish(),
  popularity: z.number().nullish(),
  genres: z.array(z.looseObject({ id: z.number(), name: z.string() })),
  production_countries: z.array(z.looseObject({ iso_3166_1: z.string() })),
  poster_path: z.string().nullish(),
  backdrop_path: z.string().nullish(),
  translations: z.looseObject({ translations: z.array(Translation) }),
  alternative_titles: z.looseObject({
    titles: z.array(z.looseObject({ iso_3166_1: z.string(), title: z.string() })),
  }),
  release_dates: z.looseObject({
    results: z.array(
      z.looseObject({
        iso_3166_1: z.string(),
        release_dates: z.array(
          z.looseObject({
            certification: z.string().nullish(),
            release_date: z.string(),
            /** 1 premiere, 2 limited theatrical, 3 theatrical, 4 digital, 5 physical, 6 TV */
            type: z.number().int(),
          }),
        ),
      }),
    ),
  }),
  videos: z.looseObject({
    results: z.array(
      z.looseObject({
        site: z.string(),
        key: z.string(),
        type: z.string(),
        name: z.string(),
        official: z.boolean().nullish(),
        iso_639_1: z.string().nullish(),
      }),
    ),
  }),
  images: z.looseObject({ posters: z.array(Image) }),
});
export type MovieDetails = z.infer<typeof MovieDetails>;
