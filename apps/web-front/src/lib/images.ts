/**
 * Image URLs for the website, in one place. Posters come straight from TMDB for now; when
 * our own imgproxy arrives, only this module changes: components ask for a width and get
 * a `src` and a `srcSet`.
 */

/** The widths TMDB serves posters in (`/t/p/w342/…`); "original" is avoided. */
const TMDB_POSTER_WIDTHS = [92, 154, 185, 342, 500, 780] as const;
const TMDB_IMAGE = /^https:\/\/image\.tmdb\.org\/t\/p\/[^/]+(\/.+)$/;

/** The smallest TMDB width that covers `px`, or the largest there is. */
const tmdbWidth = (px: number) =>
  TMDB_POSTER_WIDTHS.find((w) => w >= px) ?? TMDB_POSTER_WIDTHS.at(-1)!;

export type ImageSource = { src: string; srcSet?: string };

/**
 * A poster for display at `px` CSS pixels wide: the size that covers it, and twice that for
 * sharp screens. A URL we don't recognise is used as it is.
 */
export const posterSource = (url: string, px: number): ImageSource => {
  const tmdb = url.match(TMDB_IMAGE);
  if (!tmdb) {
    return { src: url };
  }
  const at = (w: number) => `https://image.tmdb.org/t/p/w${w}${tmdb[1]}`;
  const one = tmdbWidth(px);
  const two = tmdbWidth(px * 2);
  return { src: at(one), ...(two !== one && { srcSet: `${at(one)} 1x, ${at(two)} 2x` }) };
};
