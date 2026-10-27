import {
  makeId,
  type FilmListing,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, toHelsinkiIso } from "@pgtm/model/time";
import { load } from "cheerio";
import { z } from "zod";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, plainText, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { MyCalendarRawSnapshot } from "./fetch.ts";
import type { MyCalendarSite } from "./sites.ts";

const Occurrence = z.looseObject({
  occur_id: z.union([z.string(), z.number()]),
  /** Local wall-clock time: "2026-10-23 18:00:00". */
  occur_begin: z.string(),
  /** The same instant as Unix seconds. */
  ts_occur_begin: z.union([z.string(), z.number()]),
  event_title: z.string(),
  category_id: z.union([z.string(), z.number()]),
});

const LOCAL = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/;

/** Pure: the occurrences + the price page + site config -> normalized batch. */
export const parseMyCalendar = (
  raw: MyCalendarRawSnapshot,
  site: MyCalendarSite,
): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  // The cinema's one price, when its page states it.
  const infoText = raw.info ? plainText(load(raw.info).text()) : "";
  const price = site.pricePattern
    ? toCents(infoText.match(new RegExp(site.pricePattern, "i"))?.[1], { zeroIsFree: false })
    : undefined;

  // The route answers `{date: [occurrence…]}`, or `[]` for no events.
  const days = z
    .union([z.record(z.string(), z.array(z.unknown())), z.array(z.never()).length(0)])
    .safeParse(raw.events);
  if (!days.success) {
    warnings.push({ code: "invalid-response", message: "Not a My Calendar events answer" });
  }
  const items = days.success && !Array.isArray(days.data) ? Object.values(days.data).flat() : [];
  for (const item of items) {
    const parsed = Occurrence.safeParse(item);
    if (!parsed.success) {
      warnings.push({ code: "invalid-event", message: parsed.error.message });
      continue;
    }
    const e = parsed.data;
    if (Number(e.category_id) !== site.category) {
      warnings.push({
        code: "unclaimed-event",
        message: `Occurrence ${e.occur_id} is not in category ${site.category}; skipped`,
        context: { id: String(e.occur_id) },
      });
      continue;
    }
    const local = e.occur_begin.match(LOCAL);
    const start =
      local &&
      helsinkiShowTime({
        year: Number(local[1]),
        month: Number(local[2]),
        day: Number(local[3]),
        hour: Number(local[4]),
        minute: Number(local[5]),
      });
    // Both stamps are the plugin's: a disagreement would move every time silently.
    const instant = toHelsinkiIso(new Date(Number(e.ts_occur_begin) * 1000));
    if (!start || start.startsAt !== instant) {
      warnings.push({
        code: "invalid-start",
        message: `Occurrence ${e.occur_id}: ${e.occur_begin} and ${e.ts_occur_begin} disagree`,
        context: { id: String(e.occur_id) },
      });
      continue;
    }
    if (start.businessDate < window.from || start.businessDate > window.to) {
      continue;
    }
    const { title: unprefixed, rule } = splitTitlePrefix(plainText(e.event_title), prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);
    if (!listings.has(listingId)) {
      listings.set(listingId, {
        id: listingId,
        provider: P,
        sourceId: filmKey,
        title: { fi: title },
        genres: [],
        countries: [],
        kind: rule?.event ? "event" : "film",
      });
    }
    const sourceId = String(e.occur_id);
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
      audio: version.audio ? [version.audio] : [],
      ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
      subtitles: { kind: "unknown" },
      tags: [...(rule?.tags ?? [])],
      series: rule?.series ? [rule.series] : [],
      availability: "unknown",
      ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
      // Tickets at the door: the cinema's page.
      ticketUrl: site.info,
      unmappedLabels: [],
      fetchedAt: raw.fetchedAt,
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
