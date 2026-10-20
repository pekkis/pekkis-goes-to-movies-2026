import { posterSource } from "../lib/images.ts";
import { fi } from "../lib/text.ts";
import * as css from "./Poster.css.ts";

export type PosterSize = "sm" | "md" | "lg";

/** CSS pixels at 16 px per rem, as the theme's posterSm/Md/Lg tokens: the image to ask for. */
const POSTER_PX: Record<PosterSize, number> = { sm: 64, md: 144, lg: 224 };

/**
 * A film's poster (TMDB's, through lib/images.ts, so its source can change in one place).
 * Without one, a bordered box with the title keeps the layout: a wireframe placeholder.
 */
export const Poster = ({
  url,
  title,
  size = "md",
  eager = false,
}: {
  url: string | null;
  title: string;
  size?: PosterSize;
  /** Above the fold (a film page's own poster): load at once. */
  eager?: boolean;
}) => {
  if (!url) {
    return (
      <span
        className={css.poster({ size, placeholder: true })}
        role="img"
        aria-label={fi.noPoster(title)}
      >
        {title}
      </span>
    );
  }
  const px = POSTER_PX[size];
  const { src, srcSet } = posterSource(url, px);
  return (
    <img
      className={css.poster({ size })}
      src={src}
      {...(srcSet && { srcSet })}
      alt={fi.posterOf(title)}
      width={px}
      height={Math.round(px * 1.5)}
      loading={eager ? "eager" : "lazy"}
      decoding="async"
    />
  );
};
