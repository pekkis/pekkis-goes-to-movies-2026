import type { Lang } from "@pgtm/model";

/**
 * Upstream language codes that are not ISO 639-1. `SE` is the ISO 3166 country code
 * for Sweden and is used by several Finnish cinemas to mean Swedish.
 */
const NON_ISO: Record<string, Lang> = {
  se: "sv",
  swe: "sv",
  fin: "fi",
  eng: "en",
};

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
  hindi: "hi",
  georgian: "ka",
  yiddish: "yi",
  nepali: "ne",
};

/**
 * Names seen in the wild that are not plain language names: Finnish adjective forms
 * ("italialainen"), translative forms ("englanniksi"), and a machine translation of
 * "Polish" as the verb "kiillottaa" (to polish).
 */
const OTHER_NAMES: Record<string, Lang> = {
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

/** Code or Finnish/English name -> ISO 639-1, or undefined when not recognized. */
export const normalizeLang = (input: string): Lang | undefined => {
  const key = input.trim().toLowerCase();
  if (key === "") return undefined;
  if (key in NON_ISO) return NON_ISO[key];
  if (key in FINNISH_NAMES) return FINNISH_NAMES[key];
  if (key in ENGLISH_NAMES) return ENGLISH_NAMES[key];
  if (key in OTHER_NAMES) return OTHER_NAMES[key];
  const stem = fromAdjective(key);
  if (stem !== key) return FINNISH_NAMES[stem] ?? OTHER_NAMES[stem];
  if (/^[a-z]{2}$/.test(key)) return key;
  return undefined;
};
