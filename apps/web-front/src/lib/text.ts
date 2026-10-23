import type { ScreeningTag, TAG_GROUPS } from "@pgtm/model";

/**
 * Finnish UI text, in one place so it can move to an i18n catalogue (Lingui) later.
 * Code stays English; this module is data.
 */
const SITE_NAME = "Pekkis goes to movies";

export const fi = {
  siteName: SITE_NAME,
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
  /** "Näytökset päivitetty 23.10. klo 08.59" */
  updatedAt: (when: string) => `Näytökset päivitetty ${when}`,
  /** The source failed at the latest pull: the programme shown may be out of date. */
  sourceDown: (when: string) =>
    `Teatterin sivu ei vastannut viimeisimmässä haussa (${when}). Näytökset voivat olla vanhentuneita; tarkista teatterin omilta sivuilta.`,
  neverUpdated: "Näytöksiä ei ole vielä haettu.",
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
  helsinkiNotice:
    "Osa näytöksistä Helsingin ja Espoon kaupunkien Linked Events -rajapinnoista (CC BY 4.0).",
  // Posters and film pages.
  posterOf: (title: string) => `${title} – juliste`,
  noPoster: (title: string) => `${title} – ei julistetta`,
  filmNotFound: "Elokuvaa ei löytynyt.",
  originalTitle: "Alkuperäinen nimi",
  directedBy: "Ohjaus",
  specials: "Erikoisnäytökset",
  specialsIntro:
    "Valitse näytösten lajit ja sarjat, niin näet niiden näytökset neljän viikon ajalta. Osoitteen voi jakaa.",
  specialsStart: "Valitse ainakin yksi laji tai sarja.",
  kindsOfScreening: "Näytösten lajit",
  changeChoices: "Muuta valintoja",
  chosen: (names: string) => `Valittu: ${names}`,
  seriesHeading: "Sarjat, festivaalit ja kerhot",
  noSeries: "Ei sarjoja tulossa.",
  noKindScreenings: "Ei näytöksiä valituista neljän viikon aikana.",
  kindsMore: (n: number) =>
    `Näytetään ${n} ensimmäistä näytöstä. Rajaa valintoja nähdäksesi loput.`,
  /** "3 näytöstä, pe 23.10. alkaen" */
  seriesUpcoming: (n: number, firstDay: string) =>
    `${n === 1 ? "1 näytös" : `${n} näytöstä`}, ${firstDay} alkaen`,
  filmSeries: "Elokuvasarja",
  finnishPremiere: "Ensi-ilta Suomessa",
  trailer: "Traileri (YouTube)",
  onTmdb: "Elokuva TMDB:ssä",
  screeningsByDay: "Näytökset",
  noScreeningsOn: (day: string) => `Ei näytöksiä ${day}.`,
  newFilms: "Uudet elokuvat",
  newFilmsIntro:
    "Elokuvat, joiden ensi-ilta (tai ensimmäinen näytös, jos ensi-iltaa ei tiedetä) on tulossa tai oli viikon sisällä ja joita esitetään seuraavan viikon aikana.",
  openedThisWeek: "Alkaneet viikon aikana",
  comingThisWeek: "Alkamassa viikon aikana",
  firstShowing: (day: string) => `1. näytös ${day}`,
  premiereOn: (day: string) => `ensi-ilta ${day}`,
  noNewFilms: "Ei uusia elokuvia.",
  reruns: "Uusintaesitykset",
  rerunsIntro:
    "Vähintään viisi vuotta vanhat elokuvat ja teattereiden omat klassikkonäytökset seuraavan viikon aikana.",
  nextShowing: (day: string) => `seuraava näytös ${day}`,
  noReruns: "Ei uusintaesityksiä tällä viikolla.",
  // The search page (/fi/haku).
  search: "Hae",
  searchTitle: "Hae elokuvaa",
  /** "Haku: Lapin sota · Tampere, enintään 25 km · pe 23.10.–su 25.10." */
  searchTitleFor: (parts: string) => `Haku: ${parts}`,
  /** Every page's <title> but the front page's names the site after it. */
  pageTitle: (title: string) => (title === SITE_NAME ? title : `${title} | ${SITE_NAME}`),
  searchIntro:
    "Valitse päivät ja paikka, tai kirjoita elokuvan nimi. Rajaa sitten kellonajan, teatterin ja elokuvan mukaan.",
  days: "Päivät",
  today: "tänään",
  place: "Paikka",
  chooseCity: "Valitse kaupunki",
  myLocation: "Oma sijainti",
  locateMe: "Käytä sijaintiani",
  locating: "Haetaan sijaintia…",
  locationDenied:
    "Selain ei antanut sijaintia. Salli se selaimen (ja käyttöjärjestelmän) asetuksista tai valitse kaupunki.",
  locationUnavailable:
    "Sijaintia ei saatu. Tarkista, että sijaintipalvelut ovat päällä, tai valitse kaupunki.",
  locationTimeout: "Sijaintia ei saatu ajoissa. Yritä uudelleen tai valitse kaupunki.",
  locationFound: "Sijainti haettu. Paina Hae.",
  radius: "Etäisyys enintään",
  km: (n: number) => `${n.toLocaleString("fi-FI")} km`,
  filmName: "Elokuvan nimi (vapaaehtoinen)",
  filmExample: "esim. Lapin sota",
  startHint: "Valitse paikka tai kirjoita elokuvan nimi, niin näet näytökset.",
  noFilmFound: (q: string) => `Elokuvaa ”${q}” ei löytynyt.`,
  filmsFound: "Haetut elokuvat",
  narrow: "Rajaa",
  filmsFacet: "Elokuvat",
  timeOfDay: "Kellonaika",
  timeSlots: {
    morning: "ennen klo 12",
    afternoon: "klo 12–17",
    evening: "klo 17–21",
    late: "klo 21 jälkeen",
  },
  filterFilms: "Etsi listasta",
  clear: "Tyhjennä",
  toResults: (n: number) => `Siirry näytöksiin (${n}) ↓`,
  noMatches: "Valinnoilla ei löytynyt näytöksiä. Poista jokin rajaus.",
  around: (place: string, km: string) => `${place}, enintään ${km}`,
} as const;

/** Every screening tag's name; the type makes a new tag in the model need one here. */
export const TAG_NAMES: Record<ScreeningTag, string> = {
  premiere: "Ensi-illat",
  preview: "Ennakkonäytökset",
  "last-screening": "Viimeiset näytökset",
  classic: "Uusintaesitykset",
  "event-cinema": "Tapahtumat (ooppera, baletti, konsertit)",
  domestic: "Kotimaiset elokuvat",
  senior: "Seniorinäytökset",
  kids: "Lastennäytökset",
  baby: "Vauvanäytökset",
  discount: "Alennusnäytökset",
  free: "Ilmaiset näytökset",
  guest: "Vieraat ja keskustelut",
  "no-dialogue": "Ilman puhetta",
  accessible: "Esteettömät näytökset",
  captions: "Ruututekstitys",
  "audio-description": "Kuvailutulkkaus",
};

/** The model's tag groups, named. */
export const TAG_GROUP_NAMES: Record<keyof typeof TAG_GROUPS, string> = {
  occasion: "Tilaisuus",
  origin: "Alkuperä",
  audience: "Yleisö",
  extras: "Lisäksi",
  accessibility: "Saavutettavuus",
  price: "Hinta",
};

const languageNames = new Intl.DisplayNames(["fi"], { type: "language" });

/** "en" -> "englanti"; unknown codes as they are. */
export const languageName = (code: string): string => languageNames.of(code) ?? code;
