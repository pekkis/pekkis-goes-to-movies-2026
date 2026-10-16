/** Lowercase, strip punctuation and extra whitespace. Keeps Nordic letters. */
export const normalizeTitle = (title: string): string =>
  title
    .normalize("NFKC")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .replace(/\s+/g, " ");

/**
 * The part before a subtitle separator, e.g. "Practical Magic: Lumotut sisaret" -> "Practical Magic".
 * Undefined when the title has no separator or the prefix is too short to be meaningful.
 */
export const titlePrefix = (title: string): string | undefined => {
  const match = title.match(/^(.+?)(?:\s*:\s+|\s+[-–]\s+|\s+-elokuva\b)/);
  const prefix = match?.[1]?.trim();
  return prefix && prefix.length >= 4 && prefix !== title.trim() ? prefix : undefined;
};

/**
 * Drops trailing parenthesized qualifiers cinemas add to a title:
 * "Nalle Puhin elokuva (dub)", "Vaiana (liveaction)", "Autot (uudelleenjulkaisu)".
 */
/**
 * A production year the cinema writes into the title's trailing parentheses:
 * "NOSFERATU (1922)", "Scream (1996)". stripQualifiers drops it, so read it first.
 */
export const yearInTitle = (title: string): number | undefined => {
  const year = title.match(/\((1[89]\d{2}|20\d{2})\)(?:\s*\([^()]*\))*\s*$/)?.[1];
  return year ? Number(year) : undefined;
};

export const stripQualifiers = (title: string): string => {
  const stripped = title.replace(/(\s*\([^()]*\))+\s*$/, "").trim();
  return stripped || title.trim();
};
