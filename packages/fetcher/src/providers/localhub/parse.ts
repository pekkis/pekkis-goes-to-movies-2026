import {
  makeId,
  type FilmListing,
  type FinnishRating,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, toHelsinkiIso } from "@pgtm/model/time";
import { z } from "zod";
import { own } from "../../lib/records.ts";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { LocalhubRawSnapshot } from "./fetch.ts";
import type { LocalhubSite } from "./sites.ts";

const Page = z.looseObject({
  _id: z.string(),
  name: z.string(),
  globalContentCategories: z.array(z.string()).nullish(),
  hashtags: z.array(z.string()).nullish(),
  price: z
    .looseObject({
      min: z.number().nullish(),
      max: z.number().nullish(),
      currency: z.string().nullish(),
    })
    .nullish(),
  event: z.looseObject({
    timezone: z.string().nullish(),
    urlPurchaseTicket: z.string().nullish(),
    isCancelled: z.boolean().nullish(),
    isSoldOut: z.boolean().nullish(),
    dates: z
      .array(
        z.looseObject({
          /** UTC: "2026-10-17T14:00:00.000Z". */
          start: z.string(),
          isCancelled: z.boolean().nullish(),
          isSoldOut: z.boolean().nullish(),
          urlPurchaseTicket: z.string().nullish(),
        }),
      )
      .nullish(),
  }),
});
const Search = z.looseObject({ pages: z.array(z.unknown()), count: z.number().int().nullish() });

/** The rating as a hashtag: "k-12", "k-7"; "s" is S. */
const RATINGS: Record<string, FinnishRating> = {
  s: "S",
  "k-7": "K-7",
  "k-12": "K-12",
  "k-16": "K-16",
  "k-18": "K-18",
};
/** A trailing "(2026)" is the year, not part of the title. */
const YEAR = /^(.+?)\s*\((\d{4})\)$/;

/** Pure: the calendar's search + site config -> normalized batch. */
export const parseLocalhub = (raw: LocalhubRawSnapshot, site: LocalhubSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const search = Search.safeParse(raw.search);
  if (!search.success) {
    warnings.push({ code: "invalid-response", message: "Not a calendar search answer" });
  } else if (search.data.count && search.data.count > search.data.pages.length) {
    // A cut answer: absent screenings may simply not be on this page.
    warnings.push({
      code: "invalid-response",
      message: `The search found ${search.data.count} pages but returned ${search.data.pages.length}`,
    });
  }
  for (const item of search.success ? search.data.pages : []) {
    const parsed = Page.safeParse(item);
    if (!parsed.success) {
      warnings.push({ code: "invalid-page", message: parsed.error.message });
      continue;
    }
    const page = parsed.data;
    // The calendar's own id for the page ("_id").
    const { _id: pageId } = page;
    const hashtags = (page.hashtags ?? []).map((h) => h.toLowerCase());
    // The calendar is the whole town's: the category and the hashtag must both say cinema.
    if (
      !(page.globalContentCategories ?? []).includes(site.category) ||
      !hashtags.includes(site.hashtag)
    ) {
      continue;
    }
    if (page.event.timezone && page.event.timezone !== "Europe/Helsinki") {
      warnings.push({
        code: "invalid-start",
        message: `Page ${pageId} is in ${page.event.timezone}`,
        context: { id: pageId },
      });
      continue;
    }
    const age = hashtags.find((h) => own(RATINGS, h));
    const rating = age ? own(RATINGS, age) : undefined;
    const yearMatch = page.name.trim().match(YEAR);
    const { title: unprefixed, rule } = splitTitlePrefix(
      yearMatch ? yearMatch[1]! : page.name,
      prefixRules,
    );
    const { title, version } = splitVersion(unprefixed);
    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);
    // A band settles one amount only when its ends meet.
    const band = page.price;
    const price =
      band?.currency === "EUR" && band.min != null && band.min === band.max
        ? toCents(band.min, { zeroIsFree: true })
        : undefined;

    for (const date of page.event.dates ?? []) {
      if (date.isCancelled ?? page.event.isCancelled) {
        continue; // a cancelled screening is not on
      }
      let startsAt: string;
      try {
        startsAt = toHelsinkiIso(date.start);
      } catch {
        warnings.push({
          code: "invalid-start",
          message: `Unreadable start "${date.start}"`,
          context: { id: pageId },
        });
        continue;
      }
      const businessDate = startsAt.slice(0, 10);
      if (businessDate < window.from || businessDate > window.to) {
        continue;
      }
      if (!listings.has(listingId)) {
        listings.set(listingId, {
          id: listingId,
          provider: P,
          sourceId: filmKey,
          title: { fi: title },
          ...(yearMatch && { year: Number(yearMatch[2]) }),
          ...(rating && { rating }),
          genres: [],
          countries: [],
          kind: rule?.event ? "event" : "film",
        });
      }
      const ticketUrl = date.urlPurchaseTicket ?? page.event.urlPurchaseTicket;
      const sourceId = `${pageId}-${startsAt.slice(0, 16).replace(/[-T:]/g, "")}`;
      const id = makeId(P, "show", sourceId);
      screenings.set(id, {
        id,
        provider: P,
        sourceId,
        venueId,
        listingId,
        startsAt,
        businessDate,
        presentation: { projection: "digital", dimension: version.dimension ?? "2d", formats: [] },
        audio: version.audio ? [version.audio] : [],
        ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
        subtitles: { kind: "unknown" },
        tags: [...(rule?.tags ?? [])],
        series: rule?.series ? [rule.series] : [],
        availability: (date.isSoldOut ?? page.event.isSoldOut) ? "sold-out" : "unknown",
        ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
        // The town's ticket shop, as the calendar links it; else the calendar's page.
        ticketUrl:
          ticketUrl && URL.canParse(ticketUrl) ? ticketUrl : `${site.base}/fi/page/${pageId}`,
        unmappedLabels: [],
        fetchedAt: raw.fetchedAt,
      });
    }
  }

  return {
    provider: providerOf(site, "custom", "buy"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: [toVenue(P, venue, venue.slug)],
    auditoriums: [],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
