import {
  makeId,
  type FilmListing,
  type FinnishRating,
  type Lang,
  type ProviderBatch,
  type Screening,
  type Subtitles,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import { own } from "../../lib/records.ts";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, slugify } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { BioDuxRawSnapshot } from "./fetch.ts";
import type { BioDuxSite } from "./sites.ts";

/** Weekday abbreviations, Finnish and Swedish, Monday first. */
const WEEKDAY: Record<string, number> = {
  ma: 1,
  mån: 1,
  ti: 2,
  tis: 2,
  ke: 3,
  ons: 3,
  to: 4,
  tor: 4,
  pe: 5,
  fre: 5,
  la: 6,
  lör: 6,
  su: 7,
  sön: 7,
};
/** "fre/pe 16.10. 18.00", "lör 17.10. 12.30 på svenska", "su 18.10. 12.30 suomeksi". */
const ROW =
  /^([a-zåäö]{2,3})(?:\/([a-zåäö]{2,3}))?\s+(\d{1,2})\.(\d{1,2})\.?\s+(\d{1,2})[.:](\d{2})\s*(.*)$/i;
/** "Forgotten Island 109 min". */
const RUNTIME = /\s+(\d{2,3})\s*min$/i;
/** "åldersgräns 7 ikäraja": closes a film (0 is S). */
const AGE = /^åldersgräns\s+(\d{1,2})\s+ikäraja$/i;
const RATINGS: Record<string, FinnishRating> = {
  "0": "S",
  "7": "K-7",
  "12": "K-12",
  "16": "K-16",
  "18": "K-18",
};
const ROW_AUDIO: Record<string, Lang> = { "på svenska": "sv", suomeksi: "fi" };
const DUBBED = /^dubbad\s*-\s*dubattu$/i;
/** "in English - svenskt text - suom. tekstit". */
const ENGLISH = /\bin English\b/i;
const SUBTITLE_LANGS: [RegExp, Lang][] = [
  [/\bsvenskt? text\b/i, "sv"],
  [/\bsuom\.? tekstit\b/i, "fi"],
];

const text = (value: string | undefined) => (value ?? "").replace(/\s+/g, " ").trim();

type Film = {
  title: string;
  runtime?: number;
  rows: { date: string; hour: number; minute: number; audio?: Lang }[];
};

/** Pure: the front page + site config -> normalized batch. */
export const parseBioDux = (raw: BioDuxRawSnapshot, site: BioDuxSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  $("script, style, figure, img").remove();
  const lines = ($("body").html() ?? "")
    .split(/<br\s*\/?>|<\/?(?:p|h\d|div|button|li|section)\b[^>]*>/i)
    .map((chunk) => text(load(chunk, null, false).text()))
    .filter(Boolean);
  if (!lines.some((l) => AGE.test(l))) {
    warnings.push({ code: "invalid-response", message: "No films on the front page" });
  }

  let unreadable = 0;
  let group: Film[] = [];
  let groupFacts: string[] = [];
  const emit = (rating: FinnishRating | undefined) => {
    const dubbed = groupFacts.some((l) => DUBBED.test(l));
    const english = groupFacts.some((l) => ENGLISH.test(l));
    const subtitleLangs = SUBTITLE_LANGS.filter(([re]) => groupFacts.some((l) => re.test(l))).map(
      ([, lang]) => lang,
    );
    const subtitles: Subtitles =
      subtitleLangs.length > 0
        ? { kind: "languages", languages: subtitleLangs }
        : { kind: "unknown" };
    for (const film of group) {
      // "Matka Piemonteen - Resan till Piemonte": Finnish, then Swedish.
      const [fi, sv, ...rest] = film.title.split(/\s+-\s+/);
      const bilingual = sv !== undefined && rest.length === 0;
      const { title: unprefixed, rule } = splitTitlePrefix(
        bilingual ? fi! : film.title,
        prefixRules,
      );
      const { title, version } = splitVersion(unprefixed);
      const filmKey = slugify(title);
      const listingId = makeId(P, "film", filmKey);
      for (const row of film.rows) {
        const start = helsinkiShowTime({
          year: Number(row.date.slice(0, 4)),
          month: Number(row.date.slice(5, 7)),
          day: Number(row.date.slice(8, 10)),
          hour: row.hour,
          minute: row.minute,
        });
        if (!start) {
          unreadable += 1;
          continue;
        }
        if (start.businessDate < window.from || start.businessDate > window.to) {
          continue;
        }
        if (!listings.has(listingId)) {
          listings.set(listingId, {
            id: listingId,
            provider: P,
            sourceId: filmKey,
            title: { fi: title, ...(bilingual && { sv: sv! }) },
            ...(film.runtime && { runtimeMinutes: film.runtime }),
            ...(rating && { rating }),
            genres: [],
            countries: [],
            kind: rule?.event ? "event" : "film",
          });
        }
        const audio = version.audio ?? row.audio ?? (english ? "en" : undefined);
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
          presentation: {
            projection: "digital",
            dimension: version.dimension ?? "2d",
            formats: [],
          },
          audio: audio ? [audio] : [],
          ...((version.dubbed !== undefined || dubbed) && { dubbed: version.dubbed ?? dubbed }),
          subtitles,
          tags: [...(rule?.tags ?? [])],
          series: rule?.series ? [rule.series] : [],
          availability: "unknown",
          // Tickets at the door: the front page.
          ticketUrl: `${site.homepage}/`,
          unmappedLabels: [],
          fetchedAt: raw.fetchedAt,
        });
      }
    }
    group = [];
    groupFacts = [];
  };

  lines.forEach((line, i) => {
    const age = line.match(AGE);
    if (age) {
      const rating = own(RATINGS, age[1]!);
      if (!rating) {
        unreadable += group.reduce((n, f) => n + f.rows.length, 0);
        group = [];
        groupFacts = [];
        return;
      }
      emit(rating);
      return;
    }
    const row = line.match(ROW);
    const weekday = row
      ? (WEEKDAY[(row[2] ?? row[1]!).toLowerCase()] ?? WEEKDAY[row[1]!.toLowerCase()])
      : undefined;
    if (row && weekday) {
      const film = group.at(-1);
      const date = nearestDate(Number(row[3]), Number(row[4]), raw.from);
      if (!film || !date || Temporal.PlainDate.from(date).dayOfWeek !== weekday) {
        unreadable += 1;
        return;
      }
      const note = text(row[7]).toLowerCase();
      const audio = note ? own(ROW_AUDIO, note) : undefined;
      film.rows.push({
        date,
        hour: Number(row[5]),
        minute: Number(row[6]),
        ...(audio && { audio }),
      });
      return;
    }
    // A title is a line followed by a screening row.
    const next = lines[i + 1] ?? "";
    const nextRow = next.match(ROW);
    if (
      nextRow &&
      (WEEKDAY[(nextRow[2] ?? nextRow[1]!).toLowerCase()] ?? WEEKDAY[nextRow[1]!.toLowerCase()])
    ) {
      const runtime = line.match(RUNTIME);
      group.push({
        title: runtime ? line.slice(0, runtime.index).trim() : line,
        ...(runtime && { runtime: Number(runtime[1]) }),
        rows: [],
      });
      return;
    }
    if (group.length > 0) {
      groupFacts.push(line);
    }
  });
  // Films without a closing age line are still published, without a rating.
  emit(undefined);

  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} screening rows not understood, or with a weekday that fits no date`,
    });
  }

  return {
    provider: providerOf(site, "custom", "door"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: [toVenue(P, venue, venue.slug)],
    auditoriums: [],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
