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
