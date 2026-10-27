import type { Availability, FinnishRating, Screening } from "@pgtm/model";
import { own } from "../lib/records.ts";

/**
 * Small helpers shared by the provider parsers, so that the same fact means the same
 * thing whichever cinema it comes from.
 */

/**
 * "13", "12,50", 8.5 -> cents. `zeroIsFree`: whether the source writes 0 for a free show
 * (Kinola, Johku) or for "not set" (Nexxo's "0.00", eTiketti), in which case 0 is unknown.
 */
export const toCents = (
  value: string | number | null | undefined,
  { zeroIsFree }: { zeroIsFree: boolean },
): number | undefined => {
  const n =
    typeof value === "number"
      ? value
      : Number(
          String(value ?? "")
            .replace(",", ".")
            .trim() || NaN,
        );
  if (!Number.isFinite(n) || n < 0) {
    return undefined;
  }
  if (n === 0 && !zeroIsFree) {
    return undefined;
  }
  return Math.round(n * 100);
};

/** Below this share of free seats a show is "few-left". */
export const FEW_LEFT_SHARE = 0.1;

/**
 * Seats left -> availability. Without the capacity only sold-out vs. available can be
 * told apart (Kinola).
 */
export const availabilityFromSeats = ({
  free,
  capacity,
}: {
  free?: number | undefined;
  capacity?: number | undefined;
}): Availability => {
  if (free === undefined || !Number.isFinite(free)) {
    return "unknown";
  }
  if (free <= 0) {
    return "sold-out";
  }
  if (capacity !== undefined && capacity > 0 && free / capacity < FEW_LEFT_SHARE) {
    return "few-left";
  }
  return "available";
};

/**
 * Characters that print nothing: soft hyphens (`&shy;`, a CMS's hyphenation hints, as in Kino
 * Hamina's "Hä&shy;mä&shy;rä&shy;puu&shy;his&shy;sa", 2026-10-27), zero-width spaces and
 * joiners, word joiners and byte-order marks.
 */
const INVISIBLE = /[­​-‍⁠﻿]/g;

/** Text as a reader sees it: invisible characters removed, whitespace collapsed, trimmed. */
export const plainText = (value: string | undefined): string =>
  (value ?? "").replace(INVISIBLE, "").replace(/\s+/g, " ").trim();

const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  SALLITTU: "S",
  K7: "K-7",
  K12: "K-12",
  K16: "K-16",
  K18: "K-18",
};

/**
 * A Finnish age rating however a cinema spells it: "S", "Sallittu", "-S-", "7", "K7", "K-7",
 * "k 12" (case, spaces and hyphens ignored). Anything else is undefined: a source's own codes
 * (TMB's 1–4, Kinola's Estonian "L") stay in that parser.
 */
export const finnishRating = (value: string | undefined): FinnishRating | undefined => {
  const key = (value ?? "").toUpperCase().replace(/[\s-]/g, "");
  return own(RATINGS, /^\d+$/.test(key) ? `K${key}` : key);
};

/** "Feeniks-sali (Teatteri)" -> "feeniks-sali-teatteri", "Sali Ä" -> "sali-a": for ids. */
export const slugify = (name: string): string =>
  name
    .replace(INVISIBLE, "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");

/** The order every batch lists its screenings in. */
export const byStartThenId = (a: Screening, b: Screening): number =>
  Date.parse(a.startsAt) - Date.parse(b.startsAt) || a.id.localeCompare(b.id);

/** Counts how many rows each unclaimed key (a room, a place line) skipped. */
export const tally = <K>(counts: Map<K, number>, key: K): void => {
  counts.set(key, (counts.get(key) ?? 0) + 1);
};

/**
 * A row with several start times on one day, as one row per time: "pe 23.10. 16:00 ja 19:15"
 * -> ["pe 23.10. 16:00", "pe 23.10. 19:15"]; "24.10. La klo17.00 ja klo18.00" -> ["24.10. La
 * klo 17.00", "24.10. La klo 18.00"] (both 2026-10-22). Times are joined by "ja", "&" or a
 * comma; "klo" stays, as written, when the row had it. Any other row is returned as it is.
 */
export const eachStartTime = (row: string): string[] => {
  const TIME = String.raw`(?:klo\s*)?\d{1,2}[.:]\d{2}`;
  const m = row.match(
    new RegExp(String.raw`^(.*?)\s+(${TIME}(?:\s*(?:ja|&|,)\s*${TIME})+)!?$`, "i"),
  );
  if (!m) {
    return [row];
  }
  const klo = m[2]!.match(/^klo/i)?.[0];
  return [...m[2]!.matchAll(/\d{1,2}[.:]\d{2}/g)].map(
    (t) => `${m[1]} ${klo ? `${klo} ` : ""}${t[0]}`,
  );
};
