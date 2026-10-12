import type { Lang, Subtitles } from "@pgtm/model";
import { normalizeLang } from "../lib/lang.ts";
import { own } from "../lib/records.ts";

/**
 * Language codes as Finnish ticketing systems write them (Nexxo, Johku's Maccs Box fields):
 * "FI", "OV" (original version: language unknown), "FI-SE" (two subtitle languages),
 * "XX" (no subtitles), "SE" (= Swedish), "IW" (= Hebrew).
 */

/** Codes that are not ISO 639-1 (SE is handled by normalizeLang). */
const EXTRA_CODES: Record<string, Lang> = { iw: "he" };
export const UNKNOWN_CODE = "OV";
const NO_SUBTITLES = "XX";

export const codes = (raw: string | null | undefined) =>
  (raw ?? "")
    .toUpperCase()
    .split(/[^A-Z]+/)
    .filter(Boolean);

const toLang = (code: string): Lang | undefined =>
  own(EXTRA_CODES, code.toLowerCase()) ?? normalizeLang(code);

/** "FI" / "OV" -> ["fi"] / []. Unknown codes are returned for unmappedLabels. */
export const parseAudio = (
  raw: string | null | undefined,
): { audio: Lang[]; unknown: string[] } => {
  const audio: Lang[] = [];
  const unknown: string[] = [];
  for (const code of codes(raw).filter((c) => c !== UNKNOWN_CODE)) {
    const lang = toLang(code);
    if (lang) audio.push(lang);
    else unknown.push(code);
  }
  return { audio, unknown };
};

/** "FI-SE" -> fi, sv; "XX" -> none; "OV" or "" -> unknown. */
export const parseSubtitles = (raw: string | null | undefined): Subtitles => {
  const list = codes(raw);
  if (list.length === 0 || list.includes(UNKNOWN_CODE)) return { kind: "unknown" };
  const langs = list.filter((c) => c !== NO_SUBTITLES).map(toLang);
  if (langs.length === 0) return { kind: "none" };
  if (langs.some((l) => l === undefined)) return { kind: "unknown" };
  return { kind: "languages", languages: [...new Set(langs as Lang[])] };
};
