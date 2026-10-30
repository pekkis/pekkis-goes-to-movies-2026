import type { Lang } from "@pgtm/model";
import { own } from "./records.ts";

/**
 * Upstream language codes that are not ISO 639-1. `SE` is the ISO 3166 country code
 * for Sweden and is used by several Finnish cinemas to mean Swedish.
 */
const NON_ISO: Record<string, Lang> = {
  se: "sv",
  swe: "sv",
  fin: "fi",
  eng: "en",
  // Country codes written for the language (BioRex, Gilda: "JP" for Japanese).
  jp: "ja",
  dk: "da",
  cz: "cs",
  gr: "el",
  // Hebrew's withdrawn ISO code.
  iw: "he",
};

/** ICU's language names: a two-letter code without one is not a language. */
const LANGUAGE_NAMES = new Intl.DisplayNames(["en"], { type: "language", fallback: "none" });

/** Finnish language names as cinemas write them. */
const FINNISH_NAMES: Record<string, Lang> = {
  suomi: "fi",
  ruotsi: "sv",
  englanti: "en",
  saksa: "de",
  ranska: "fr",
  italia: "it",
  espanja: "es",
  japani: "ja",
  korea: "ko",
  venäjä: "ru",
  heprea: "he",
  puola: "pl",
  tanska: "da",
  norja: "no",
  islanti: "is",
  viro: "et",
  unkari: "hu",
  tšekki: "cs",
  kiina: "zh",
  mandariini: "zh",
  kantoni: "zh",
  hindi: "hi",
  arabia: "ar",
  turkki: "tr",
  persia: "fa",
  portugali: "pt",
  hollanti: "nl",
  kreikka: "el",
  ukraina: "uk",
  saame: "se",
  saami: "se",
  pohjoissaame: "se",
};

/** English language names, as some cinemas write them (Cinema Sheryl, Kinola data). */
const ENGLISH_NAMES: Record<string, Lang> = {
  english: "en",
  finnish: "fi",
  swedish: "sv",
  spanish: "es",
  german: "de",
  french: "fr",
  italian: "it",
  russian: "ru",
  polish: "pl",
  japanese: "ja",
  korean: "ko",
  chinese: "zh",
  cantonese: "zh",
  mandarin: "zh",
  danish: "da",
  norwegian: "no",
  icelandic: "is",
  dutch: "nl",
  portuguese: "pt",
  ukrainian: "uk",
  arabic: "ar",
  turkish: "tr",
  persian: "fa",
  farsi: "fa",
  dari: "fa",
  pashto: "ps",
  hebrew: "he",
  greek: "el",
  romanian: "ro",
  estonian: "et",
  lithuanian: "lt",
  tamil: "ta",
  kannada: "kn",
  hindi: "hi",
  georgian: "ka",
  yiddish: "yi",
  nepali: "ne",
};

/**
 * Names seen in the wild that are not plain language names: Finnish adjective forms
 * ("italialainen"), translative forms ("englanniksi"), a machine translation of
 * "Polish" as the verb "kiillottaa" (to polish), and "no dialogue" (Gilda's album sessions).
 */
const OTHER_NAMES: Record<string, Lang> = {
  "ei puhetta": "zxx",
  // A silent film has no spoken language (Kino Myyri, 2026-10-15).
  "mykkä elokuva": "zxx",
  mykkä: "zxx",
  englanniksi: "en",
  suomeksi: "fi",
  ruotsiksi: "sv",
  kiillottaa: "pl",
  mandariinikiina: "zh",
  kantoninkiina: "zh",
  tamili: "ta",
  nepali: "ne",
  romania: "ro",
  liettua: "lt",
  latvia: "lv",
  georgia: "ka",
  gruusia: "ka",
  jiddiš: "yi",
  jiddish: "yi",
  paštu: "ps",
  pastu: "ps",
  pashtu: "ps",
  pushto: "ps",
  dari: "fa",
  farsi: "fa",
  urdu: "ur",
  bengali: "bn",
  thai: "th",
  vietnam: "vi",
  indonesia: "id",
};

/** "italialainen" -> "italia", "heprealainen" -> "heprea", "nepalilainen" -> "nepali". */
const fromAdjective = (key: string) => key.replace(/l(?:ainen|äinen)$/, "");

/** The genitive, "saksan" -> "saksa" (Kino Myyri, 2026-10-30); names without gradation only. */
const fromGenitive = (key: string) => key.replace(/n$/, "");

/** Code or Finnish/English name -> ISO 639-1, or undefined when not recognized. */
export const normalizeLang = (input: string): Lang | undefined => {
  const key = input.trim().toLowerCase();
  if (key === "") {
    return undefined;
  }
  const named =
    own(NON_ISO, key) ??
    own(FINNISH_NAMES, key) ??
    own(ENGLISH_NAMES, key) ??
    own(OTHER_NAMES, key);
  if (named) {
    return named;
  }
  const stem = fromAdjective(key);
  if (stem !== key) {
    return own(FINNISH_NAMES, stem) ?? own(OTHER_NAMES, stem);
  }
  const genitive = own(FINNISH_NAMES, fromGenitive(key));
  if (genitive) {
    return genitive;
  }
  if (/^[a-z]{2}$/.test(key) && LANGUAGE_NAMES.of(key) !== undefined) {
    return key;
  }
  return undefined;
};

/**
 * A list of spoken languages, as one field writes it: "EN & FI" -> ["en", "fi"] (BioRex,
 * Yön lapsi, 2026-10-22); also joined by a comma, "ja" or "and". All or nothing: undefined
 * if any part is unknown. Not "/": in cinema codes "FI/SV" usually describes subtitles.
 */
export const normalizeLangs = (input: string): Lang[] | undefined => {
  const parts = input.split(/\s*(?:&|,|\bja\b|\band\b)\s*/i).filter((p) => p.trim() !== "");
  const langs = parts.map(normalizeLang);
  return langs.length > 0 && langs.every((l) => l !== undefined) ? [...new Set(langs)] : undefined;
};
