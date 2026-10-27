import {
  makeId,
  type Auditorium,
  type FilmListing,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, toHelsinkiIso } from "@pgtm/model/time";
import { load } from "cheerio";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, plainText, slugify } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { BioSavoyRawSnapshot } from "./fetch.ts";
import type { BioSavoySite } from "./sites.ts";

/** "Filmvisningar - Sal 1": the hall is the block's. */
const BLOCK = /^Filmvisningar\s*[-–]\s*(.+)$/i;

/** Pure: the front page + site config -> normalized batch. */
export const parseBioSavoy = (raw: BioSavoyRawSnapshot, site: BioSavoySite): ProviderBatch => {
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
  const blocks = $("h2.block-title")
    .toArray()
    .flatMap((h) => {
      const hall = plainText($(h).text()).match(BLOCK)?.[1];
      return hall
        ? [{ hall, rows: $(h).nextAll(".block-content").first().find("a[href^='/film/']") }]
        : [];
    });
  if (blocks.length === 0) {
    warnings.push({
      code: "invalid-response",
      message: "No Filmvisningar blocks on the front page",
    });
  }
  let unreadable = 0;
  for (const { hall, rows } of blocks) {
    const auditoriumId = makeId(P, "screen", `${venue.slug}-${slugify(hall)}`);
    for (const el of rows.toArray()) {
      const row = $(el);
      const href = row.attr("href") ?? "";
      const slug = href.match(/^\/film\/([^/?#]+)/)?.[1];
      const iso = row.find("[content]").attr("content");
      // The text after the clock and the dash: "18:00 - BORTGLÖMDA ÖN".
      const rawTitle = plainText(row.clone().children().remove().end().text()).replace(
        /^[-–]\s*/,
        "",
      );
      let startsAt: string | undefined;
      try {
        startsAt = iso ? toHelsinkiIso(iso) : undefined;
      } catch {
        startsAt = undefined;
      }
      if (!slug || !startsAt || !rawTitle) {
        unreadable += 1;
        continue;
      }
      const businessDate = startsAt.slice(0, 10);
      if (businessDate < window.from || businessDate > window.to) {
        continue;
      }
      if (!auditoriums.has(auditoriumId)) {
        auditoriums.set(auditoriumId, { id: auditoriumId, venueId, name: hall, features: [] });
      }
      const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
      const { title, version } = splitVersion(unprefixed);
      const listingId = makeId(P, "film", slug);
      if (!listings.has(listingId)) {
        listings.set(listingId, {
          id: listingId,
          provider: P,
          sourceId: slug,
          // The site is Swedish: the title is Swedish, not Finnish.
          title: { sv: title },
          genres: [],
          countries: [],
          kind: rule?.event ? "event" : "film",
        });
      }
      const sourceId = `${slug}-${startsAt.slice(0, 16).replace(/[-T:]/g, "")}`;
      const id = makeId(P, "show", sourceId);
      screenings.set(id, {
        id,
        provider: P,
        sourceId,
        venueId,
        auditoriumId,
        listingId,
        startsAt,
        businessDate,
        presentation: { projection: "digital", dimension: version.dimension ?? "2d", formats: [] },
        audio: version.audio ? [version.audio] : [],
        ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
        subtitles: { kind: "unknown" },
        tags: [...(rule?.tags ?? [])],
        series: rule?.series ? [rule.series] : [],
        availability: "unknown",
        // Reservations by phone: the film's own page, copied (http, as the host serves).
        ticketUrl: new URL(href, `${site.base}/`).href,
        unmappedLabels: [],
        fetchedAt: raw.fetchedAt,
      });
    }
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} rows without a film, time or title`,
    });
  }

  return {
    provider: providerOf(site, "custom", "reserve"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: [toVenue(P, venue, venue.slug)],
    auditoriums: [...auditoriums.values()],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
