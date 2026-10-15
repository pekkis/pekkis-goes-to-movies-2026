import {
  makeId,
  type FilmListing,
  type FinnishRating,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import { own } from "../../lib/records.ts";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { KinoAkseliRawSnapshot } from "./fetch.ts";
import type { KinoAkseliSite } from "./sites.ts";

const WEEKDAYS = ["MA", "TI", "KE", "TO", "PE", "LA", "SU"];
/** "To 15.10. klo 17:45", "La 17.10. klo 13:15 (dub)" */
const SHOW =
  /(Ma|Ti|Ke|To|Pe|La|Su)\s*(\d{1,2})\.(\d{1,2})\.\s*klo\s*(\d{1,2})[:.](\d{2})(\s*\([^()]{1,20}\))?/gi;
/** Elements run together in the text ("Ikäraja : 12Liput"): no word boundary to rely on. */
const AGE = /Ikäraja\s*:\s*(S|7|12|16|18)(?!\d)/gi;
const PRICE = /Liput\s*:\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*€/gi;
const DURATION = /Kesto\s*:\s*(\d{2,3})\s*min/gi;
const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  "7": "K-7",
  "12": "K-12",
  "16": "K-16",
  "18": "K-18",
};

const text = (value: string | undefined) => (value ?? "").replace(/\s+/g, " ").trim();
/** The last match in a stretch of text: the facts nearest the heading that follows. */
const last = (re: RegExp, value: string) => [...value.matchAll(re)].at(-1)?.[1];

/** Pure: the front page + site config -> normalized batch. */
export const parseKinoAkseli = (
  raw: KinoAkseliRawSnapshot,
  site: KinoAkseliSite,
): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  // The page as text, with each film heading marked: facts sit before a heading, the
  // screenings after it.
  const $ = load(raw.html);
  const headings = $("h2.elementor-heading-title a[href*='/elokuva-']").toArray();
  if (headings.length === 0) {
    warnings.push({ code: "invalid-response", message: "No film headings on the front page" });
  }
  const MARK = "@@pgtm-film@@";
  headings.forEach((a) => $(a).closest("h2").before(`<p>${MARK}</p>`));
  const titles = headings.map((a) => ({ title: text($(a).text()), href: $(a).attr("href") ?? "" }));
  const body = text($("body").text());
  const chunks = body.split(MARK);

  let unreadable = 0;
  titles.forEach(({ title: rawTitle, href }, i) => {
    const before = chunks[i] ?? "";
    const after = chunks[i + 1] ?? "";
    // The heading text opens the chunk after it; the screenings follow "Näytösajat".
    const showsText = after.includes("Näytösajat") ? after.slice(after.indexOf("Näytösajat")) : "";
    const shows = [...showsText.matchAll(SHOW)];
    if (!rawTitle || shows.length === 0) {
      return; // the month's-offer card repeats a film with no screenings
    }
    const age = last(AGE, before);
    const rating = age ? own(RATINGS, age.toUpperCase()) : undefined;
    const price = toCents(last(PRICE, before), { zeroIsFree: false });
    const runtime = Number(last(DURATION, before) ?? 0);

    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);

    for (const m of shows) {
      const date = nearestDate(Number(m[2]), Number(m[3]), raw.from);
      const weekday = date ? WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] : undefined;
      const start =
        date &&
        // The weekday is the only check on the year we infer.
        weekday === m[1]!.toUpperCase() &&
        helsinkiShowTime({
          year: Number(date.slice(0, 4)),
          month: Number(m[3]),
          day: Number(m[2]),
          hour: Number(m[4]),
          minute: Number(m[5]),
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
          title: { fi: title },
          ...(runtime > 0 && { runtimeMinutes: runtime }),
          ...(rating && { rating }),
          genres: [],
          countries: [],
          kind: rule?.event ? "event" : "film",
        });
      }
      // "(dub.)" after the time is this screening's version.
      const marker = m[6]?.trim().replace(/^\(|\.?\)$/g, "");
      const rowVersion = marker ? splitVersion(`x (${marker})`).version : {};
      const audio = rowVersion.audio ?? version.audio;
      const dubbed = rowVersion.dubbed ?? version.dubbed;
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
        tags: [...(rule?.tags ?? [])],
        series: rule?.series ? [rule.series] : [],
        availability: "unknown",
        ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
        // Tickets at the door: the film's page on the site, copied.
        ticketUrl: href.startsWith(`${site.homepage}/`) ? href : `${site.homepage}/`,
        unmappedLabels:
          marker && !rowVersion.audio && rowVersion.dubbed === undefined
            ? [`version:${marker}`]
            : [],
        fetchedAt: raw.fetchedAt,
      });
    }
  });
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} screenings with a weekday that fits no date`,
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
