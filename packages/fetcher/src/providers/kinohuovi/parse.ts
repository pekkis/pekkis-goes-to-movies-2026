import {
  makeId,
  type FilmListing,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { addDays, dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { KinoHuoviRawSnapshot } from "./fetch.ts";
import type { KinoHuoviSite } from "./sites.ts";

const WEEKDAYS = ["MA", "TI", "KE", "TO", "PE", "LA", "SU"];
/**
 * One group of screenings: a date or a range, its weekdays, one time.
 * "12.10. MA klo 18.00", "23.-27.10. PE, LA, SU, MA ja TI klo 18.00".
 */
const GROUP =
  /(\d{1,2})\.(?:\s*-\s*(\d{1,2})\.)?\s*(\d{1,2})\.\s+((?:MA|TI|KE|TO|PE|LA|SU)(?:\s*(?:,|\bja\b)\s*(?:MA|TI|KE|TO|PE|LA|SU))*)\s+klo\s*(\d{1,2})[.:](\d{2})/gi;
/** "Kestoaika n. 2t 35min." */
const DURATION = /Kestoaika\s+(?:n\.\s*)?(?:(\d+)\s*t)?\s*(\d+)\s*min/i;
/** "Liput 12€." and nothing else on the line. */
const PRICE = /Liput\s+(\d{1,3}(?:[.,]\d{1,2})?)\s*€\.?(?:\s|$)/i;

const text = (value: string | undefined) => (value ?? "").replace(/\s+/g, " ").trim();

/** Pure: the front page + site config -> normalized batch. */
export const parseKinoHuovi = (raw: KinoHuoviRawSnapshot, site: KinoHuoviSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  const cards = $(".postArticle").toArray();
  if (cards.length === 0) {
    warnings.push({ code: "invalid-response", message: "No .postArticle cards on the front page" });
  }
  let unreadable = 0;
  for (const el of cards) {
    const card = $(el);
    const rawTitle = text(card.find(".postTitle h3").first().text());
    const body = text(card.find(".postDescription").text());
    if (!rawTitle) {
      continue;
    }
    const groups = [...body.matchAll(GROUP)];
    if (groups.length === 0) {
      unreadable += 1;
      continue;
    }
    const duration = body.match(DURATION);
    const runtime = duration ? Number(duration[1] ?? 0) * 60 + Number(duration[2]) : 0;
    const price = toCents(body.match(PRICE)?.[1], { zeroIsFree: false });
    // "Dub." on the card: the screenings are dubbed into Finnish.
    const cardVersion = /\bDub\b\.?/i.test(body) ? splitVersion("x (dub)").version : {};
    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version: titleVersion } = splitVersion(unprefixed);
    const version = { ...cardVersion, ...titleVersion };
    // The card's link is a recycled alias (another film's), so the film is its title.
    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);

    for (const g of groups) {
      const weekdays = g[4]!.split(/\s*(?:,|\bja\b)\s*/i).map((w) => w.toUpperCase());
      const first = Number(g[1]);
      const last = g[2] ? Number(g[2]) : first;
      const month = Number(g[3]);
      // A range across a month end ("30.-2.11.") starts in the month before.
      const firstMonth = last < first ? (month === 1 ? 12 : month - 1) : month;
      const start = nearestDate(first, firstMonth, raw.from);
      const dates = start
        ? Array.from({ length: Math.max(0, weekdays.length) }, (_v, k) => addDays(start, k))
        : [];
      const span = start && g[2] ? dates.at(-1)?.slice(8, 10) : undefined;
      // The weekdays prove the days: one per date, in order, or the group is not placed.
      const fits =
        dates.length > 0 &&
        (!g[2] || Number(span) === last) &&
        (g[2] ? true : weekdays.length === 1) &&
        dates.every((d, k) => WEEKDAYS[Temporal.PlainDate.from(d).dayOfWeek - 1] === weekdays[k]);
      if (!fits) {
        unreadable += 1;
        continue;
      }
      for (const date of dates) {
        const shown = helsinkiShowTime({
          year: Number(date.slice(0, 4)),
          month: Number(date.slice(5, 7)),
          day: Number(date.slice(8, 10)),
          hour: Number(g[5]),
          minute: Number(g[6]),
        });
        if (!shown) {
          unreadable += 1;
          continue;
        }
        if (shown.businessDate < window.from || shown.businessDate > window.to) {
          continue;
        }
        if (!listings.has(listingId)) {
          listings.set(listingId, {
            id: listingId,
            provider: P,
            sourceId: filmKey,
            title: { fi: title },
            ...(runtime > 0 && { runtimeMinutes: runtime }),
            genres: [],
            countries: [],
            kind: rule?.event ? "event" : "film",
          });
        }
        const sourceId = `${filmKey}-${shown.startsAt.slice(0, 16).replace(/[-T:]/g, "")}`;
        const id = makeId(P, "show", sourceId);
        screenings.set(id, {
          id,
          provider: P,
          sourceId,
          venueId,
          listingId,
          startsAt: shown.startsAt,
          businessDate: shown.businessDate,
          presentation: {
            projection: "digital",
            dimension: version.dimension ?? "2d",
            formats: [],
          },
          audio: version.audio ? [version.audio] : [],
          ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
          subtitles: { kind: "unknown" },
          tags: [...(rule?.tags ?? [])],
          series: rule?.series ? [rule.series] : [],
          availability: "unknown",
          ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
          ticketUrl: `${site.homepage}/`,
          unmappedLabels: [],
          fetchedAt: raw.fetchedAt,
        });
      }
    }
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} cards or date groups whose dates and weekdays do not fit`,
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
