import {
  makeId,
  type FilmListing,
  type FinnishRating,
  type ProviderBatch,
  type RawLabel,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime } from "@pgtm/model/time";
import { load } from "cheerio";
import { own } from "../../lib/records.ts";
import {
  COMMON_TITLE_PREFIXES,
  splitDatedLabel,
  splitTitlePrefix,
  splitVersion,
} from "../labels.ts";
import { byStartThenId, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { KurikanKinoRawSnapshot } from "./fetch.ts";
import type { KurikanKinoSite } from "./sites.ts";

/** "pe 9.10. 19:00": the day and month, and the wall-clock time the stamp must agree with. */
const SHOWN = /(\d{1,2})\.(\d{1,2})\.\s+(\d{1,2})[.:](\d{2})$/;
/** "13 €"; anything else ("10/8 €") settles nothing. */
const PRICE = /^(\d{1,3}(?:[.,]\d{1,2})?)\s*€$/;
const RATINGS: Record<string, FinnishRating> = {
  s: "S",
  "7": "K-7",
  "12": "K-12",
  "16": "K-16",
  "18": "K-18",
};

const text = (value: string | undefined) => (value ?? "").replace(/\s+/g, " ").trim();

/** Pure: the front page + site config -> normalized batch. */
export const parseKurikanKino = (
  raw: KurikanKinoRawSnapshot,
  site: KurikanKinoSite,
): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  const cards = $("li.elokuva-thumb").toArray();
  if (cards.length === 0) {
    warnings.push({ code: "invalid-response", message: "No film cards on the front page" });
  }
  let unreadable = 0;
  for (const el of cards) {
    const card = $(el);
    // The times are printed twice (desktop, mobile); the desktop copy sits in the card.
    const times = card.find(".elokuva-thumb-content .elokuva-aika").toArray();
    if (times.length === 0) {
      continue; // coming soon: no showtimes yet
    }
    const href = card.find("a.elokuva-linkki").attr("href") ?? "";
    const slug = href.match(/\/elokuvat\/([^/?#]+)\/?$/)?.[1];
    const name = card.find(".elokuva-nimi").first().clone();
    const ageClass = name.find(".ikaraja").attr("class") ?? "";
    name.find(".ikaraja").remove();
    const rawTitle = text(name.text());
    if (!rawTitle) {
      unreadable += times.length;
      continue;
    }
    const unmapped: string[] = [];
    const age = ageClass.match(/\bikaraja-([a-z0-9]+)\b/)?.[1];
    const rating = age ? own(RATINGS, age) : undefined;
    if (age && !rating) {
      unmapped.push(`rating:${age}`);
    }
    const [hours, minutes] = card
      .find(".kesto strong")
      .toArray()
      .map((s) => Number(text($(s).text())));
    const runtime = hours !== undefined && minutes !== undefined ? hours * 60 + minutes : undefined;
    const price = toCents(text(card.find(".hinta").first().text()).match(PRICE)?.[1], {
      zeroIsFree: false,
    });

    // "Lapin Sota , Ensi-ilta 23.10.": the premiere is that day's screening (2026-10-17).
    const dated = splitDatedLabel(rawTitle, prefixRules);
    const { title: unprefixed, rule, label } = splitTitlePrefix(dated.title, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const labels: RawLabel[] = [
      ...(label ? [{ source: "title.prefix", text: label }] : []),
      ...(dated.label ? [{ source: "title.note", text: dated.label }] : []),
    ];
    const filmKey = slug ?? slugify(title);
    const listingId = makeId(P, "film", filmKey);

    for (const t of times) {
      const stamp = Number($(t).attr("esitysaika"));
      const shown = text($(t).text()).match(SHOWN);
      if (!Number.isInteger(stamp) || stamp <= 0 || !shown) {
        unreadable += 1;
        continue;
      }
      // The stamp is the Helsinki wall-clock time written as if it were UTC (19:00 on the
      // page is 19:00Z); it carries the year, and the printed day and time must agree.
      const wall = new Date(stamp * 1000);
      const start = helsinkiShowTime({
        year: wall.getUTCFullYear(),
        month: wall.getUTCMonth() + 1,
        day: wall.getUTCDate(),
        hour: wall.getUTCHours(),
        minute: wall.getUTCMinutes(),
      });
      const agrees =
        wall.getUTCDate() === Number(shown[1]) &&
        wall.getUTCMonth() + 1 === Number(shown[2]) &&
        wall.getUTCHours() === Number(shown[3]) &&
        wall.getUTCMinutes() === Number(shown[4]);
      if (!start || !agrees) {
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
          ...(runtime && { runtimeMinutes: runtime }),
          ...(rating && { rating }),
          genres: [],
          countries: [],
          kind: rule?.event ? "event" : "film",
        });
      }
      const sourceId = `${filmKey}-${stamp}`;
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
        tags: [
          ...new Set([
            ...(rule?.tags ?? []),
            ...(wall.getUTCDate() === dated.day && wall.getUTCMonth() + 1 === dated.month
              ? (dated.rule?.tags ?? [])
              : []),
          ]),
        ],
        series: rule?.series ? [rule.series] : [],
        availability: "unknown",
        ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
        // The film's page on the cinema's site, copied.
        ticketUrl: href.startsWith(`${site.homepage}/`) ? href : `${site.homepage}/`,
        unmappedLabels: unmapped,
        ...(labels.length > 0 && { labels }),
        fetchedAt: raw.fetchedAt,
      });
    }
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} showtimes not understood (no title, or a stamp and a printed time that disagree)`,
    });
  }

  return {
    provider: providerOf(site, "custom", "info"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: [toVenue(P, venue, venue.slug)],
    auditoriums: [],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
