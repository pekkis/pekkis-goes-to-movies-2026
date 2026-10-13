import {
  makeId,
  type Auditorium,
  type FilmListing,
  type FinnishRating,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime } from "@pgtm/model/time";
import { load } from "cheerio";
import { own } from "../../lib/records.ts";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, slugify } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { TmbRawSnapshot } from "./fetch.ts";
import type { TmbSite } from "./sites.ts";

/**
 * The rating is only in the image name. `_2`/`_3`/`_4` were checked by Leffavuoro against
 * other cinemas' ratings of the same films; `_1` against ours on 2026-10-13 ("Pirjo i
 * Sverige" S at 13 cinemas, "Pikkuli ja Tähtipeura" S at 6). `_0` is titled "Ikärajaa ei
 * ole määritetty" (no rating set). Anything else is reported, not guessed.
 */
const RATINGS: Record<string, FinnishRating> = { "1": "S", "2": "K-7", "3": "K-12", "4": "K-16" };
const UNRATED = "0";

const WEEKDAYS = ["MA", "TI", "KE", "TO", "PE", "LA", "SU"];

/** "KE 14.10.2026 klo 13:30" or "KE 14.10.2026 klo 17:45, sali 1". */
const ROW =
  /^([A-ZÄÖ]{2})\s+(\d{1,2})\.(\d{1,2})\.(\d{4})\s+klo\s+(\d{1,2}):(\d{2})(?:\s*,\s*sali\s+(\S+))?\s*$/i;

/** Pure: the list view + site config -> normalized batch. Broken rows become warnings. */
export const parseTmb = (raw: TmbRawSnapshot, site: TmbSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const auditoriums = new Map<string, Auditorium>();
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  if (!/Valkokankaalla/i.test($("body").text())) {
    warnings.push({
      code: "invalid-response",
      message: "No 'Valkokankaalla' programme on the page: not the list view this parser reads",
    });
  }

  $("small").each((_index, el) => {
    const label = $(el).text().replace(/ /g, " ").trim();
    const m = label.match(ROW);
    const link = $(el).closest("td").find("h2 a[href^='?ohjelmisto=']").first();
    const filmId = link.attr("href")?.match(/^\?ohjelmisto=(\d+)$/)?.[1];
    if (!m || !filmId) {
      return;
    }
    const [, weekday, day, month, year, hour, minute, hall] = m;
    const start = helsinkiShowTime({
      year: Number(year),
      month: Number(month),
      day: Number(day),
      hour: Number(hour),
      minute: Number(minute),
    });
    const date = start && Temporal.PlainDate.from(start.startsAt.slice(0, 10));
    if (!start || !date || WEEKDAYS[date.dayOfWeek - 1] !== weekday!.toUpperCase()) {
      // A weekday that contradicts its date means the template moved fields around.
      warnings.push({
        code: "invalid-start",
        message: `Unreadable or inconsistent row "${label}"`,
      });
      return;
    }
    if (start.businessDate < window.from || start.businessDate > window.to) {
      return;
    }

    const unmapped: string[] = [];
    const rawTitle = link.text().replace(/\s+/g, " ").trim();
    const { title: unprefixed, rule: label_ } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const image = $(el)
      .closest("tr")
      .find("img[src*='ikaraja_']")
      .attr("src")
      ?.match(/ikaraja_(\w+)\.png/)?.[1];
    const rating = image ? own(RATINGS, image) : undefined;
    if (image && !rating && image !== UNRATED) {
      unmapped.push(`ikaraja:${image}`);
    }

    const listingId = makeId(P, "film", filmId);
    if (!listings.has(listingId)) {
      listings.set(listingId, {
        id: listingId,
        provider: P,
        sourceId: filmId,
        title: { fi: title },
        ...(rating && { rating }),
        genres: [],
        countries: [],
        kind: label_?.event ? "event" : "film",
      });
    }

    const auditoriumId = hall ? makeId(P, "screen", `${venue.slug}-${slugify(hall)}`) : undefined;
    if (auditoriumId && !auditoriums.has(auditoriumId)) {
      auditoriums.set(auditoriumId, {
        id: auditoriumId,
        venueId,
        name: `Sali ${hall}`,
        features: [],
      });
    }

    // The list carries no screening id: film, minute and hall identify one.
    const stamp = start.startsAt.slice(0, 16).replace(/[-T:]/g, "");
    const sourceId = `${filmId}-${stamp}${hall ? `-${slugify(hall)}` : ""}`;
    const id = makeId(P, "show", sourceId);
    screenings.set(id, {
      id,
      provider: P,
      sourceId,
      venueId,
      ...(auditoriumId && { auditoriumId }),
      listingId,
      startsAt: start.startsAt,
      businessDate: start.businessDate,
      presentation: { projection: "digital", dimension: version.dimension ?? "2d", formats: [] },
      audio: version.audio ? [version.audio] : [],
      ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
      subtitles: { kind: "unknown" },
      tags: [...(label_?.tags ?? [])],
      series: label_?.series ? [label_.series] : [],
      // No seat or sale state in the list view.
      availability: "unknown",
      // The film's public page, which lists its screenings and the site's own booking
      // buttons; never the `?varaa=` reservation action.
      ticketUrl: `${site.base}/?ohjelmisto=${filmId}`,
      unmappedLabels: unmapped,
      fetchedAt: raw.fetchedAt,
    });
  });

  return {
    provider: providerOf(site, "tmb", "reserve"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: [toVenue(P, venue, venue.slug)],
    auditoriums: [...auditoriums.values()],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
