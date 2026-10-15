import {
  makeId,
  type FilmListing,
  type FinnishRating,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, toHelsinkiIso } from "@pgtm/model/time";
import { own } from "../../lib/records.ts";
import { splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import { LinkedEvent, LinkedEventsPage, type LinkedEventsRawSnapshot } from "./raw.ts";
import type { LinkedEventsSite } from "./sites.ts";

/** The age limit in parentheses after the title: "Tony (16)", "Pirjo i Sverige (S)". */
const AGE = /^(.+?)\s*\((S|7|12|16|18)\)$/;
const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  "7": "K-7",
  "12": "K-12",
  "16": "K-16",
  "18": "K-18",
};
/** Events that will not take place as listed. */
const NOT_ON = new Set(["EventCancelled", "EventPostponed"]);
/** "9 €", "12,50 €": one plain amount. */
const PRICE = /^(\d{1,3}(?:[.,]\d{1,2})?)\s*€$/;

/** The place id from its URL: ".../place/tprek:8740/" -> "tprek:8740". */
const placeOf = (url: string | undefined) => url?.match(/\/place\/([^/]+)\/?$/)?.[1];

/** Pure: the locations' events + site config -> normalized batch. */
export const parseLinkedEvents = (
  raw: LinkedEventsRawSnapshot,
  site: LinkedEventsSite,
): ProviderBatch => {
  const P = site.provider;
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  for (const payload of raw.pages) {
    const page = LinkedEventsPage.safeParse(payload);
    if (!page.success) {
      warnings.push({ code: "invalid-response", message: "Not a Linked Events page" });
      continue;
    }
    for (const item of page.data.data) {
      const parsed = LinkedEvent.safeParse(item);
      if (!parsed.success) {
        warnings.push({ code: "invalid-event", message: parsed.error.message });
        continue;
      }
      const e = parsed.data;
      const name = e.name?.fi?.trim() ?? "";
      // Only events carrying one of the site's labels are screenings.
      const { title: labelled, rule } = splitTitlePrefix(name, site.labels);
      if (!rule || e.deleted || NOT_ON.has(e.event_status ?? "")) {
        continue;
      }
      const venue = site.venues.find((v) => v.place === placeOf(e.location?.["@id"]));
      if (!venue) {
        warnings.push({
          code: "unclaimed-place",
          message: `Event ${e.id} is at ${e.location?.["@id"] ?? "no place"}; skipped`,
          context: { id: e.id },
        });
        continue;
      }
      let startsAt: string;
      try {
        startsAt = toHelsinkiIso(e.start_time);
      } catch {
        warnings.push({
          code: "invalid-start",
          message: `Unreadable start "${e.start_time}"`,
          context: { id: e.id },
        });
        continue;
      }
      const businessDate = startsAt.slice(0, 10);
      if (businessDate < window.from || businessDate > window.to) {
        continue;
      }

      const age = labelled.match(AGE);
      const rating = age ? own(RATINGS, age[2]!) : undefined;
      const { title, version } = splitVersion(age ? age[1]! : labelled);
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
          kind: rule.event ? "event" : "film",
        });
      }

      const offer = e.offers?.[0];
      const amount = offer?.price?.fi?.trim().match(PRICE)?.[1];
      const price = offer?.is_free ? 0 : toCents(amount, { zeroIsFree: false });
      const ticketUrl = offer?.info_url?.fi ?? e.info_url?.fi;
      // "kulke:68847": a colon is not allowed inside our ids.
      const id = makeId(P, "show", e.id.replace(/:/g, "-"));
      screenings.set(id, {
        id,
        provider: P,
        sourceId: e.id,
        venueId: makeId(P, "venue", venue.slug),
        listingId,
        startsAt,
        businessDate,
        presentation: { projection: "digital", dimension: version.dimension ?? "2d", formats: [] },
        audio: version.audio ? [version.audio] : [],
        ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
        subtitles: { kind: "unknown" },
        tags: [...(rule.tags ?? [])],
        series: rule.series ? [rule.series] : [],
        availability: "unknown",
        ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
        // The ticket page the city publishes for the event (lippu.fi), copied.
        ticketUrl: ticketUrl && URL.canParse(ticketUrl) ? ticketUrl : site.homepage,
        unmappedLabels: [],
        fetchedAt: raw.fetchedAt,
      });
    }
  }

  return {
    provider: providerOf(site, "linked-events", "buy"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: site.venues.map((v) => toVenue(P, v, v.place)),
    auditoriums: [],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
