/** Country names as Finnish cinemas write them -> ISO 3166-1 alpha-2. */
const FINNISH_COUNTRY_NAMES: Record<string, string> = {
  alankomaat: "NL",
  australia: "AU",
  belgia: "BE",
  brasilia: "BR",
  bulgaria: "BG",
  espanja: "ES",
  "etelä-afrikka": "ZA",
  "etelä-korea": "KR",
  intia: "IN",
  irlanti: "IE",
  islanti: "IS",
  italia: "IT",
  itävalta: "AT",
  japani: "JP",
  kanada: "CA",
  kiina: "CN",
  kreikka: "GR",
  latvia: "LV",
  liettua: "LT",
  luxemburg: "LU",
  meksiko: "MX",
  norja: "NO",
  "uusi-seelanti": "NZ",
  puola: "PL",
  portugali: "PT",
  ranska: "FR",
  romania: "RO",
  ruotsi: "SE",
  saksa: "DE",
  sveitsi: "CH",
  tanska: "DK",
  "tsekin tasavalta": "CZ",
  tšekki: "CZ",
  turkki: "TR",
  ukraina: "UA",
  unkari: "HU",
  viro: "EE",
  "yhdistynyt kuningaskunta": "GB",
  "iso-britannia": "GB",
  yhdysvallat: "US",
};

/** Unknown names are dropped: they can only weaken evidence, never create it. */
export const toCountryCodes = (names: string[]): string[] => [
  ...new Set(
    names.flatMap((name) => {
      const code = FINNISH_COUNTRY_NAMES[name.trim().toLowerCase()];
      return code ? [code] : [];
    }),
  ),
];
