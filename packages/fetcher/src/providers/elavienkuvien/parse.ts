import {
  makeId,
  type FilmListing,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime } from "@pgtm/model/time";
import { load } from "cheerio";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, finnishRating, plainText } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { ElavienkuvienRawSnapshot } from "./fetch.ts";
import type { ElavienkuvienSite } from "./sites.ts";

/** "to 15.10.2026 klo 17:00": the year printed, the weekday not needed. */
const ROW = /^(?:[a-zäö]{2}\s+)?(\d{1,2})\.(\d{1,2})\.(\d{4})\s+klo\s+(\d{1,2})[:.](\d{2})/i;
/** "Kesto 1 h 52 min" */
const DURATION = /Kesto\s+(?:(\d+)\s*h)?\s*(\d+)\s*min/i;
/** The age limit is only the image's name: "agelimit_12.png"; "agelimit_notset" is none. */
const AGE = /agelimit_(S|7|12|16|18)\.png$/i;
/** A film's path on the site: "ohjelmisto/tony/". */
const FILM_PATH = /^\/?(ohjelmisto\/[^/?#]+\/)$/;

/** The film pages the listing links, from its film lifts only (not the sub-navigation). */
export const filmPaths = (listing: string): string[] => {
  const $ = load(listing);
  return [
    ...new Set(
      $(".movielifts a[href]")
        .toArray()
        .flatMap((a) => {
          const href = ($(a).attr("href") ?? "").replace(/^https?:\/\/[^/]+/, "");
          const m = href.match(FILM_PATH);
          return m ? [m[1]!] : [];
        }),
    ),
  ].toSorted();
};

/** Pure: the listing + film pages + site config -> normalized batch. */
export const parseElavienkuvien = (
  raw: ElavienkuvienRawSnapshot,
  site: ElavienkuvienSite,
): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  if (filmPaths(raw.listing).length === 0) {
    warnings.push({ code: "invalid-response", message: "No film lifts on /ohjelmisto/" });
  }
  let unreadable = 0;
  for (const [path, html] of Object.entries(raw.films)) {
    if (html === null) {
      // The film's screenings are only on its page: missing data, not a missing detail.
      warnings.push({
        code: "invalid-film-page",
        message: "Film page unreadable",
        context: { path },
      });
      continue;
    }
    const $ = load(html);
    const slug = path.split("/")[1]!;
    const rawTitle = plainText($("h2").first().text());
    const facts = $("p.movielength");
    const duration = plainText(facts.text()).match(DURATION);
    const runtime = duration ? Number(duration[1] ?? 0) * 60 + Number(duration[2]) : 0;
    const ageImage = facts.find("img").attr("src") ?? "";
    const age = ageImage.match(AGE)?.[1];
    const rating = age ? finnishRating(age.toUpperCase()) : undefined;
    const unmapped =
      ageImage && !rating && !/agelimit_notset/i.test(ageImage)
        ? [`rating:${ageImage.split("/").at(-1)}`]
        : [];
    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const listingId = makeId(P, "film", slug);

    for (const line of ($(".screenings p").html() ?? "").split(/<br\s*\/?>/i)) {
      const row = load(line, null, false);
      const rowText = plainText(row.root().text());
      if (!rowText || !/\bklo\b/i.test(rowText)) {
        continue; // "ke 16.12.2026": an opening day without a time
      }
      const m = rowText.match(ROW);
      const start =
        m &&
        helsinkiShowTime({
          year: Number(m[3]),
          month: Number(m[2]),
          day: Number(m[1]),
          hour: Number(m[4]),
          minute: Number(m[5]),
        });
      if (!start || !rawTitle) {
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
          sourceId: slug,
          title: { fi: title },
          ...(runtime > 0 && { runtimeMinutes: runtime }),
          ...(rating && { rating }),
          genres: [],
          countries: [],
          kind: rule?.event ? "event" : "film",
        });
      }
      // The row's own reservation page, copied; else the film's page.
      const href = row("a").attr("href");
      const sourceId = `${slug}-${start.startsAt.slice(0, 16).replace(/[-T:]/g, "")}`;
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
        ticketUrl: new URL(href ?? path, site.base).href,
        unmappedLabels: unmapped,
        fetchedAt: raw.fetchedAt,
      });
    }
  }
  if (unreadable > 0) {
    warnings.push({ code: "invalid-row", message: `${unreadable} screening lines not understood` });
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
