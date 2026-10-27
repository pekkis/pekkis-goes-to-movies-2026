import {
  makeId,
  type FilmListing,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, plainText, slugify } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { SuojaRawSnapshot } from "./fetch.ts";
import type { SuojaSite } from "./sites.ts";

const WEEKDAYS = ["ma", "ti", "ke", "to", "pe", "la", "su"];
/** "pe 16.10. klo 19:00". */
const SHOWN = /^(ma|ti|ke|to|pe|la|su)\s+(\d{1,2})\.(\d{1,2})\.?\s+klo\s+(\d{1,2})[.:](\d{2})$/i;

/** Pure: the front page + site config -> normalized batch. */
export const parseSuoja = (raw: SuojaRawSnapshot, site: SuojaSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  const films = $("div.poster-info").toArray();
  if (films.length === 0) {
    warnings.push({ code: "invalid-response", message: "No films on the front page" });
  }
  let unreadable = 0;
  for (const el of films) {
    const block = $(el).find(".desktop-mode").first();
    const heading = block.find("h2 a").first();
    const rawTitle = plainText(heading.text());
    const slug = (heading.attr("href") ?? "").match(/\/elokuva\/([^/?#]+)/)?.[1];
    const links = block.find(".showtime-list a").toArray();
    if (!rawTitle) {
      unreadable += links.length;
      continue;
    }
    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const filmKey = slug ?? slugify(title);
    const listingId = makeId(P, "film", filmKey);
    for (const a of links) {
      const href = $(a).attr("href") ?? "";
      const showId = href.match(/^\/naytos\/(\d+)$/)?.[1];
      const m = plainText($(a).text()).match(SHOWN);
      const date = m ? nearestDate(Number(m[2]), Number(m[3]), raw.from) : undefined;
      const fits =
        date && WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] === m![1]!.toLowerCase();
      const start =
        showId &&
        m &&
        date &&
        fits &&
        helsinkiShowTime({
          year: Number(date.slice(0, 4)),
          month: Number(m[3]),
          day: Number(m[2]),
          hour: Number(m[4]),
          minute: Number(m[5]),
        });
      if (!start || !showId) {
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
          genres: [],
          countries: [],
          kind: rule?.event ? "event" : "film",
        });
      }
      const id = makeId(P, "show", showId);
      screenings.set(id, {
        id,
        provider: P,
        sourceId: showId,
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
        // The screening's own page on the cinema's ticket site, copied, never requested.
        ticketUrl: `${site.homepage}${href}`,
        unmappedLabels: [],
        fetchedAt: raw.fetchedAt,
      });
    }
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} showtime links not understood, or with a weekday that fits no date`,
    });
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
