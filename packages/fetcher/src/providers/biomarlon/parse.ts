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
import type { BioMarlonRawSnapshot } from "./fetch.ts";
import type { BioMarlonSite } from "./sites.ts";

const WEEKDAYS = ["ma", "ti", "ke", "to", "pe", "la", "su"];
/** "pe 16.10. 19:00", "Ensi-ilta pe 16.10. 15:30". */
const ROW =
  /^(Ensi-ilta\s+)?(ma|ti|ke|to|pe|la|su)\s+(\d{1,2})\.(\d{1,2})\.?\s+(\d{1,2})[.:](\d{2})$/i;
/** A screening row without a time ("Ensi-ilta pe 23.10.", "Tulossa"): announced, not yet on. */
const UNTIMED = /^(?:Ensi-ilta\s+)?(?:(?:ma|ti|ke|to|pe|la|su)\s+\d{1,2}\.\d{1,2}\.?|Tulossa)$/i;
/** "(ke 21.10. 10:00 yksityisnäytös)": a private screening. */
const PRIVATE = /yksityisnäytös/i;
/** The facts: "-S- 1 t 25 min 14 €", "K-7/4 1 t 40 min 13 €", "-S- 1 t 13 €", "0 €". */
const AGE = /^(?:-S-|-?K-?(\d{1,2})(?:\/\d{1,2})?-?)(?=\s|$)/i;
const RUNTIME = /\b(\d)\s*t(?:\s+(\d{1,2})\s*min)?\b/;
const PRICE = /(\d{1,3}(?:[.,]\d{1,2})?)\s*€$/;
const DUBBED = /^Suomea puhutaan!?$/i;
const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  "7": "K-7",
  "12": "K-12",
  "16": "K-16",
  "18": "K-18",
};

const text = (value: string | undefined) => (value ?? "").replace(/\s+/g, " ").trim();

/** Pure: the front page + site config -> normalized batch. */
export const parseBioMarlon = (raw: BioMarlonRawSnapshot, site: BioMarlonSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  const blocks = $(".elementor-widget-text-editor")
    .toArray()
    .filter((el) => $(el).find("h1").length > 0 && $(el).find("h4").length > 0);
  if (blocks.length === 0) {
    warnings.push({ code: "invalid-response", message: "No film blocks on the front page" });
  }
  let unreadable = 0;
  for (const el of blocks) {
    const block = $(el);
    const rawTitle = text(block.find("h1").first().text());
    const paragraphs = block
      .find("p")
      .toArray()
      .map((p) => text($(p).text()));
    const facts = paragraphs[0] ?? "";
    const unmapped: string[] = [];
    const age = facts.match(AGE);
    const rating = age ? own(RATINGS, age[1] ?? "S") : undefined;
    if (age && !rating) {
      unmapped.push(`rating:${age[0]}`);
    }
    const duration = facts.match(RUNTIME);
    const runtime = duration ? Number(duration[1]) * 60 + Number(duration[2] ?? 0) : 0;
    const price = toCents(facts.match(PRICE)?.[1], { zeroIsFree: true });
    const dubbed = paragraphs.some((p) => DUBBED.test(p));

    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);

    for (const h of block.find("h4").toArray()) {
      const line = text($(h).text());
      if (PRIVATE.test(line) || UNTIMED.test(line)) {
        continue;
      }
      const m = line.match(ROW);
      const date = m ? nearestDate(Number(m[3]), Number(m[4]), raw.from) : undefined;
      const fits =
        date && WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] === m![2]!.toLowerCase();
      const start =
        m &&
        date &&
        fits &&
        helsinkiShowTime({
          year: Number(date.slice(0, 4)),
          month: Number(m[4]),
          day: Number(m[3]),
          hour: Number(m[5]),
          minute: Number(m[6]),
        });
      if (!rawTitle || !start) {
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
      const audio = version.audio ?? (dubbed ? "fi" : undefined);
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
        ...((version.dubbed ?? (dubbed || undefined)) !== undefined && {
          dubbed: version.dubbed ?? dubbed,
        }),
        subtitles: { kind: "unknown" },
        tags: [...(m[1] ? (["premiere"] as const) : []), ...(rule?.tags ?? [])],
        series: rule?.series ? [rule.series] : [],
        availability: "unknown",
        ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
        // Tickets at the door: the programme page.
        ticketUrl: `${site.homepage}/`,
        unmappedLabels: unmapped,
        fetchedAt: raw.fetchedAt,
      });
    }
  }
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
