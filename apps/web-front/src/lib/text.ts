/**
 * Finnish UI text, in one place so it can move to an i18n catalogue (Lingui) later.
 * Code stays English; this module is data.
 */
export const fi = {
  siteName: "Pekkis goes to movies",
  tagline: "Kaikkien Suomen elokuvateattereiden näytökset yhdessä paikassa.",
  cities: "Kaupungit",
  venues: "Elokuvateatterit",
  films: (n: number) => (n === 1 ? "1 elokuva" : `${n} elokuvaa`),
  venueNotFound: "Elokuvateatteria ei löytynyt.",
  showOnMap: "Näytä kartalla",
  map: "Kartta",
  mapTitle: "Elokuvateatterit kartalla",
  mapLabel: "Kartta Suomen elokuvateattereista",
  venuesByCity: "Elokuvateatterit kaupungeittain",
  venuePage: "Teatterin sivu →",
  cinemaWebsite: "Teatterin sivut",
  minutes: (n: number) => `${n} min`,
  ticketsAt: (time: string) => `Liput, klo ${time}`,
  whatsOn: (city: string) => `Elokuvat ${city}`,
  screenings: (n: number) => (n === 1 ? "1 näytös" : `${n} näytöstä`),
  noScreenings: "Tälle päivälle ei löytynyt näytöksiä.",
  date: "Päivä",
  show: "Näytä",
  previousDay: "Edellinen päivä",
  nextDay: "Seuraava päivä",
  tickets: "Liput",
  subtitles: (langs: string) => `tekstit: ${langs}`,
  noSubtitles: "ei tekstitystä",
  dubbed: "puhuttu",
  soldOut: "Loppuunmyyty",
  started: "alkanut",
  startsIn: (minutes: number) => (minutes <= 1 ? "alkaa nyt" : `alkaa ${minutes} min päästä`),
  showStarted: (n: number) => `Näytä alkaneet (${n})`,
  fewLeft: "Vähän paikkoja",
  notFound: "Kaupunkia ei löytynyt.",
  sourceNote: "Näytöstiedot tulevat teattereilta; liput ostetaan aina teatterin omalta sivulta.",
  tmdbNotice: "This product uses the TMDB API but is not endorsed or certified by TMDB.",
  osmNotice: "Teattereiden sijainnit © OpenStreetMap-tekijät (ODbL).",
  helsinkiNotice: "Osa näytöksistä Helsingin kaupungin Linked Events -rajapinnasta (CC BY 4.0).",
} as const;

const languageNames = new Intl.DisplayNames(["fi"], { type: "language" });

/** "en" -> "englanti"; unknown codes as they are. */
export const languageName = (code: string): string => languageNames.of(code) ?? code;
