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
import { dateWindow, helsinkiShowTime, toHelsinkiIso } from "@pgtm/model/time";
import { load } from "cheerio";
import { normalizeLang } from "../../lib/lang.ts";
import { own } from "../../lib/records.ts";
import { splitVersion } from "../labels.ts";
import { byStartThenId, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import { TribeEvent, TribePage, type TribeRawSnapshot } from "./raw.ts";
import type { TribeSite } from "./sites.ts";

const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  SALLITTU: "S",
  K7: "K-7",
  K12: "K-12",
  K16: "K-16",
  K18: "K-18",
};

/** "2026-10-18 13:00:00" */
const LOCAL = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/;
/** A trailing "(2006)": the year, not part of the title. */
const YEAR = /^(.+?)\s*\((\d{4})\)$/;
/** A trailing "(K18)": the age limit. */
const AGE = /^(.+?)\s*\((S|K-?\d{1,2})\)$/i;

const text = (value: string | undefined) =>
  (value ?? "").replace(/ /g, " ").replace(/\s+/g, " ").trim();

const ratingOf = (value: string) => own(RATINGS, value.toUpperCase().replace(/[\s-]/g, ""));

const languages = (value: string, unmapped: string[], role: string): Lang[] | undefined => {
  const names = value
    .split(/,| and | ja /)
    .map((n) => n.trim())
    .filter(Boolean);
  const codes = names.map(normalizeLang);
  if (names.length === 0 || !codes.every(Boolean)) {
    unmapped.push(`${role}:${value}`);
    return undefined;
  }
  return [...new Set(codes as Lang[])];
};

type Facts = {
  audio?: Lang[];
  subtitles?: Subtitles;
  runtime?: number;
  rating?: FinnishRating | undefined;
  unmapped: string[];
};

/**
 * The description's labelled lines and "|"-separated facts, never its prose: "Language:
 * German", "Subtitles: Finnish, English", "82 min" (Ritz); "Ikäraja K-7. Aikuisen
 * seurassa …", "Kesto 2 h 38 min | K-16 | Liput 13 €" (Muhos).
 */
const factsOf = (description: string): Facts => {
  const lines = description
    .split(/<br\s*\/?>|<\/?(?:p|div|h\d)\b[^>]*>/i)
    .flatMap((chunk) => text(load(chunk, null, false).text()).split(" | "))
    .map((line) => line.trim());
  const facts: Facts = { unmapped: [] };
  for (const line of lines) {
    const label = line.match(/^(language|subtitles|kieli|tekstitys)\s*:\s*(.+)$/i);
    const runtime = line.match(/^(?:kesto\s*)?(?:(\d)\s*h\s*)?(\d{1,3})\s*min\.?$/i);
    // Labelled, or a whole "|" segment: a prose line opening "S-ryhmä" is no rating.
    const age =
      line.match(/^ikäraja:?\s*(sallittu|S|K-?\d{1,2})\b/i) ?? line.match(/^(S|K-?\d{1,2})$/);
    if (label) {
      const role = /^(language|kieli)$/i.test(label[1]!) ? "audio" : "subtitles";
      const codes = languages(label[2]!, facts.unmapped, role);
      if (codes && role === "audio") {
        facts.audio = codes;
      } else if (codes) {
        facts.subtitles = { kind: "languages", languages: codes };
      }
    } else if (runtime) {
      facts.runtime = Number(runtime[1] ?? 0) * 60 + Number(runtime[2]);
    } else if (age) {
      facts.rating = ratingOf(age[1]!);
    }
  }
  return facts;
};

/** Pure: the category's event pages + site config -> normalized batch. */
export const parseTribe = (raw: TribeRawSnapshot, site: TribeSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  for (const payload of raw.pages) {
    const page = TribePage.safeParse(payload);
    if (!page.success) {
      warnings.push({ code: "invalid-response", message: "Not an events page" });
      continue;
    }
    for (const item of page.data.events) {
      const parsed = TribeEvent.safeParse(item);
      if (!parsed.success) {
        warnings.push({ code: "invalid-event", message: parsed.error.message });
        continue;
      }
      const e = parsed.data;
      if (!e.categories.some((c) => c.id === site.category)) {
        // The server filters by category; one outside it means the filter was ignored.
        warnings.push({
          code: "unclaimed-event",
          message: `Event ${e.id} is not in category ${site.category}; skipped`,
          context: { id: e.id },
        });
        continue;
      }
      if (e.all_day) {
        warnings.push({
          code: "all-day-event",
          message: `Event ${e.id} has no time; skipped`,
          context: { id: e.id },
        });
        continue;
      }
      const local = e.start_date.match(LOCAL);
      const start =
        local &&
        helsinkiShowTime({
          year: Number(local[1]),
          month: Number(local[2]),
          day: Number(local[3]),
          hour: Number(local[4]),
          minute: Number(local[5]),
        });
      let utc: string | undefined;
      try {
        utc = toHelsinkiIso(`${e.utc_start_date.replace(" ", "T")}Z`);
      } catch {
        utc = undefined;
      }
      // Both stamps are the plugin's own: a disagreement would move every time silently.
      if (!start || start.startsAt !== utc) {
        warnings.push({
          code: "invalid-start",
          message: `Event ${e.id}: local ${e.start_date} and UTC ${e.utc_start_date} disagree`,
          context: { id: e.id },
        });
        continue;
      }
      if (start.businessDate < window.from || start.businessDate > window.to) {
        continue;
      }

      const facts = factsOf(e.description ?? "");
      let rawTitle = text(load(e.title, null, false).text());
      for (const suffix of site.titleSuffixes) {
        if (rawTitle.toLowerCase().endsWith(suffix.toLowerCase())) {
          rawTitle = rawTitle.slice(0, -suffix.length).trim();
        }
      }
      const age = rawTitle.match(AGE);
      const titleRating = age ? ratingOf(age[2]!) : undefined;
      if (age) {
        rawTitle = age[1]!;
      }
      const year = rawTitle.match(YEAR);
      if (year) {
        rawTitle = year[1]!;
      }
      // "Tell Everyone [Kerro kaikille]": the Finnish title in brackets, the English before.
      const bracketed = site.bracketedFinnishTitle
        ? rawTitle.match(/^(.+?)\s*\[([^\]]+)\]\s*$/)
        : undefined;
      const english = bracketed?.[1]!.trim();
      const { title, version } = splitVersion(bracketed ? bracketed[2]!.trim() : rawTitle);
      const rating = facts.rating ?? titleRating;

      const filmKey = slugify(title);
      const listingId = makeId(P, "film", filmKey);
      if (!listings.has(listingId)) {
        listings.set(listingId, {
          id: listingId,
          provider: P,
          sourceId: filmKey,
          title: { fi: title, ...(english && english !== title && { en: english }) },
          ...(year && { year: Number(year[2]) }),
          ...(facts.runtime && { runtimeMinutes: facts.runtime }),
          ...(rating && { rating }),
          genres: [],
          countries: [],
          kind: "film",
        });
      }

      // One value is this event's price; several are a band that settles none.
      const values = e.cost_details?.values ?? [];
      const price = values.length === 1 ? toCents(values[0]!, { zeroIsFree: false }) : undefined;
      const sourceId = String(e.id);
      const id = makeId(P, "show", sourceId);
      const audio = version.audio ? [version.audio] : (facts.audio ?? []);
      screenings.set(id, {
        id,
        provider: P,
        sourceId,
        venueId,
        listingId,
        startsAt: start.startsAt,
        businessDate: start.businessDate,
        presentation: { projection: "digital", dimension: version.dimension ?? "2d", formats: [] },
        audio,
        ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
        subtitles: facts.subtitles ?? { kind: "unknown" },
        tags: [],
        series: [],
        availability: "unknown",
        ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
        // The event's own page on the site: copied.
        ticketUrl: e.url.startsWith(`${site.base}/`) ? e.url : site.homepage,
        unmappedLabels: facts.unmapped,
        fetchedAt: raw.fetchedAt,
      });
    }
  }

  return {
    provider: providerOf(site, "events-calendar", site.booking),
    fetchedAt: raw.fetchedAt,
    window,
    venues: [toVenue(P, venue, venue.slug)],
    auditoriums: [],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
