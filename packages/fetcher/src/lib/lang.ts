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
  pohjoissaame: "se",
};

/** Code or Finnish name -> ISO 639-1, or undefined when not recognized. */
export const normalizeLang = (input: string): Lang | undefined => {
  const key = input.trim().toLowerCase();
  if (key === "") return undefined;
  if (key in NON_ISO) return NON_ISO[key];
  if (key in FINNISH_NAMES) return FINNISH_NAMES[key];
  if (/^[a-z]{2}$/.test(key)) return key;
  return undefined;
};
