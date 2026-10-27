import {
  makeId,
  type FilmListing,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime } from "@pgtm/model/time";
import { load } from "cheerio";
import { normalizeLang } from "../../lib/lang.ts";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, finnishRating, plainText, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { MaritaRawSnapshot } from "./fetch.ts";
import type { MaritaSite } from "./sites.ts";

const DATE = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/;
const TIME = /^klo\s+(\d{1,2})[.:](\d{2})$/i;
/** "Hinta: 10 €"; "10/8 €" settles nothing. */
const PRICE = /^Hinta:\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*€$/i;
/** Only the age image is a rating; the other label images are KAVI content warnings. */
const AGE_IMAGE = /\/(s|7|12|16|18)\.png$/i;

/** Pure: the front page + site config -> normalized batch. */
export const parseMarita = (raw: MaritaRawSnapshot, site: MaritaSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  if ($("#show-times").length === 0) {
    warnings.push({ code: "invalid-response", message: "No #show-times module on the front page" });
  }
  let unreadable = 0;
  for (const el of $("#show-times .movie-info").toArray()) {
    const block = $(el);
    const link = block.find("h3 a").first();
    const rawTitle = plainText(link.text());
    const href = link.attr("href") ?? "";
    const slug = href.match(/\/elokuva\/([^/?#]+)\/?$/)?.[1];
    const d = plainText(block.find(".movie-info-times-date").text()).match(DATE);
    const t = plainText(block.find(".movie-info-times-time").text()).match(TIME);
    const start =
      d &&
      t &&
      helsinkiShowTime({
        year: Number(d[3]),
        month: Number(d[2]),
        day: Number(d[1]),
        hour: Number(t[1]),
        minute: Number(t[2]),
      });
    if (!rawTitle || !start) {
      unreadable += 1;
      continue;
    }
    if (start.businessDate < window.from || start.businessDate > window.to) {
      continue;
    }
    const unmapped: string[] = [];
    const ageImage = block.find("img.age-img").attr("src") ?? "";
    const age = ageImage.match(AGE_IMAGE)?.[1];
    const rating = age ? finnishRating(age.toUpperCase()) : undefined;
    if (ageImage && !rating) {
      unmapped.push(`rating:${ageImage.split("/").at(-1)}`);
    }
    // "Kieli: Suomi": the print's spoken language (the site states no subtitles).
    const spoken = plainText(block.find(".movie-info-language").text()).replace(/^Kieli:\s*/i, "");
    const language = spoken ? normalizeLang(spoken) : undefined;
    if (spoken && !language) {
      unmapped.push(`audio:${spoken}`);
    }
    const price = toCents(plainText(block.find(".movie-info-price").text()).match(PRICE)?.[1], {
      zeroIsFree: false,
    });

    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const filmKey = slug ?? slugify(title);
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
        kind: rule?.event ? "event" : "film",
      });
    }
    const audio = version.audio ?? language;
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
      ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
      subtitles: { kind: "unknown" },
      tags: [...(rule?.tags ?? [])],
      series: rule?.series ? [rule.series] : [],
      availability: "unknown",
      ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
      // The film's page on the cinema's site, copied.
      ticketUrl: href.startsWith(`${site.homepage}/`) ? href : `${site.homepage}/`,
      unmappedLabels: unmapped,
      fetchedAt: raw.fetchedAt,
    });
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} screening blocks not understood`,
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
