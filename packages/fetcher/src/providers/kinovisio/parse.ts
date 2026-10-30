import {
  makeId,
  type FilmListing,
  type ProviderBatch,
  type RawLabel,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import {
  COMMON_TITLE_PREFIXES,
  findLabel,
  LABELS,
  labelEffects,
  splitTitlePrefix,
  splitVersion,
} from "../labels.ts";
import { byStartThenId, finnishRating, plainText, slugify } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { KinoVisioRawSnapshot } from "./fetch.ts";
import type { KinoVisioSite } from "./sites.ts";

const WEEKDAYS = [
  "maanantai",
  "tiistai",
  "keskiviikko",
  "torstai",
  "perjantai",
  "lauantai",
  "sunnuntai",
];
/** The day's heading: "PERJANTAI 30.10.". */
const DAY = new RegExp(`^(${WEEKDAYS.join("|")})\\s+(\\d{1,2})\\.(\\d{1,2})\\.?$`, "i");
/** "18:00 Late Lammas-elokuva: hämäräpuuhissa (7) – ensi-ilta!" */
const ROW = /^(\d{1,2})[:.](\d{2})\s+(.+)$/;
/** The title, the age limit in parentheses, then notes. */
const FILM = /^(.+?)\s*\((S|K?-?\d{1,2})\)\s*(.*)$/i;
/** Stands in for <br> while the paragraph's text is read. */
const LINE_BREAK = "\u2028";
/** "KLAUS HÄRÖ – Keskustelu elokuvasta Ei koskaan yksin": a talk, not a film. */
const TALK = /\s[–-]\s*keskustelu elokuvasta\s/i;

/** "– huom! ikäraja (puhuttu suomeksi) -toiseksi viimeinen näytös!" -> its notes. */
const splitNotes = (notes: string): string[] =>
  notes
    .split(/[–()]|(?:^|\s)-/)
    .map((n) => n.trim().replace(/!+$/, "").trim())
    .filter(Boolean);

/** Pure: the front page + site config -> normalized batch. */
export const parseKinoVisio = (raw: KinoVisioRawSnapshot, site: KinoVisioSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const noteRules = site.labels ?? {};
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  // One paragraph per day, its heading in bold; lines are separated by <br>.
  const days = $("p")
    .toArray()
    .filter((p) => DAY.test(plainText($(p).find("strong").first().text())));
  if (days.length === 0) {
    warnings.push({ code: "invalid-response", message: "No programme days on the front page" });
  }
  let unreadable = 0;
  for (const p of days) {
    // Only <br> ends a line: other whitespace in the markup is just space.
    $(p).find("br").replaceWith(LINE_BREAK);
    const [heading = "", ...lines] = $(p)
      .text()
      .split(LINE_BREAK)
      .map((l) => plainText(l))
      .filter(Boolean);
    const d = heading.match(DAY)!;
    const date = nearestDate(Number(d[2]), Number(d[3]), raw.from);
    // The weekday is the only check on the year we infer.
    const fits =
      date && WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] === d[1]!.toLowerCase();
    for (const line of lines) {
      const row = line.match(ROW);
      const start =
        row &&
        date &&
        fits &&
        helsinkiShowTime({
          year: Number(date.slice(0, 4)),
          month: Number(d[3]),
          day: Number(d[2]),
          hour: Number(row[1]),
          minute: Number(row[2]),
        });
      if (!row || !start) {
        unreadable += 1;
        continue;
      }
      if (start.businessDate < window.from || start.businessDate > window.to) {
        continue;
      }
      const talk = TALK.test(row[3]!);
      const film = talk ? undefined : row[3]!.match(FILM);
      const rawTitle = talk ? row[3]! : (film?.[1] ?? row[3]!);
      const age = film?.[2]?.toUpperCase().replace("-", "");
      const rating = age ? finnishRating(age) : undefined;
      const notes = film ? splitNotes(film[3]!) : [];
      const noteHits = notes.map((n) => findLabel(n, noteRules, LABELS));
      const unmapped = [
        ...(age && !rating ? [`rating:${age}`] : []),
        ...notes.filter((_, i) => !noteHits[i]).map((n) => `note:${n}`),
      ];
      const { title: unprefixed, rule, label } = splitTitlePrefix(rawTitle, prefixRules);
      const { title, version } = talk
        ? { title: unprefixed, version: {} }
        : splitVersion(unprefixed);
      const effects = labelEffects([rule, ...noteHits]);
      const tags = [...new Set([...effects.tags, ...(talk ? (["guest"] as const) : [])])];
      const labels: RawLabel[] = [
        ...(label ? [{ source: "title.prefix", text: label }] : []),
        ...notes.filter((_, i) => noteHits[i]).map((text) => ({ source: "row.note", text })),
      ];
      const filmKey = slugify(title);
      const listingId = makeId(P, "film", filmKey);
      if (!listings.has(listingId)) {
        listings.set(listingId, {
          id: listingId,
          provider: P,
          sourceId: filmKey,
          title: { fi: title },
          ...(rating && { rating }),
          genres: [],
          countries: [],
          kind: talk || effects.event ? "event" : "film",
        });
      }
      const audio = version.audio ?? effects.audio;
      const dubbed = version.dubbed ?? effects.dubbed;
      const sourceId = `${filmKey}-${start.startsAt.slice(0, 16).replace(/[-T:]/g, "")}`;
      const id = makeId(P, "show", sourceId);
      screenings.set(id, {
        id,
        provider: P,
        sourceId,
        venueId,
        listingId,
        startsAt: start.startsAt,
        businessDate: start.businessDate,
        presentation: { projection: "digital", dimension: version.dimension ?? "2d", formats: [] },
        audio: audio ? [audio] : [],
        ...(dubbed !== undefined && { dubbed }),
        subtitles: { kind: "unknown" },
        tags,
        series: effects.series,
        availability: "unknown",
        // Tickets in the lobby, reservations by phone: the programme page.
        ticketUrl: site.programme,
        unmappedLabels: unmapped,
        ...(labels.length > 0 && { labels }),
        fetchedAt: raw.fetchedAt,
      });
    }
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} programme lines not understood, or with a weekday that fits no date`,
    });
  }

  return {
    provider: providerOf(site, "custom", "reserve"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: [toVenue(P, venue, venue.slug)],
    auditoriums: [],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
