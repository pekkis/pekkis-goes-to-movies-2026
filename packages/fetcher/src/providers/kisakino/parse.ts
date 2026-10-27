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
import { byStartThenId, finnishRating, plainText, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { KisaKinoRawSnapshot } from "./fetch.ts";
import type { KisaKinoSite } from "./sites.ts";

const WEEKDAYS = ["ma", "ti", "ke", "to", "pe", "la", "su"];
/** "La 24.10.2026 16:00". */
const SHOW = /^([a-zäö]{2})\s+(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2})[.:](\d{2})$/i;
/** "Kesto 02 h 38 min". */
const RUNTIME = /^Kesto\s+(\d{1,2})\s*h\s*(\d{1,2})\s*min$/i;
/** "Lipun hinta: 12€"; anything else settles nothing. */
const PRICE = /^Lipun hinta:\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*€$/i;
/** The age image: "k16.png", "s.png". */
const AGE_IMAGE = /\/(?:k)?(s|7|12|16|18)\.png$/i;

/** The film pages the front page links, in order, once each. */
export const filmUrls = (front: string, site: KisaKinoSite): string[] => {
  const $ = load(front);
  const urls = $("h2.etusivu-otsikko a")
    .toArray()
    .map((a) => $(a).attr("href") ?? "")
    .filter((href) => href.startsWith(`${site.homepage}/elokuvat/`));
  return [...new Set(urls)];
};

/** Pure: the front page and the film pages + site config -> normalized batch. */
export const parseKisaKino = (raw: KisaKinoRawSnapshot, site: KisaKinoSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  if (filmUrls(raw.front, site).length === 0 && !/etusivu-otsikko/.test(raw.front)) {
    warnings.push({ code: "invalid-response", message: "No film links on the front page" });
  }
  let unreadable = 0;
  for (const [url, page] of Object.entries(raw.films)) {
    if (page === null) {
      warnings.push({ code: "invalid-film-page", message: `Film page failed: ${url}` });
      continue;
    }
    const $ = load(page);
    const rawTitle = plainText($("h1.sivuotsikko").first().text());
    const slug = url.match(/\/elokuvat\/([^/?#]+)\/?$/)?.[1];
    const sidebar = $("#sidebar").first();
    const lines = (sidebar.html() ?? "")
      .split(/<br\s*\/?>|<\/?p\b[^>]*>|<hr\s*\/?>/i)
      .map((chunk) => plainText(load(chunk, null, false).text()))
      .filter(Boolean);
    if (!rawTitle || !slug || lines.length === 0) {
      warnings.push({ code: "invalid-film-page", message: `Film page not understood: ${url}` });
      continue;
    }
    const unmapped: string[] = [];
    const ageImage = sidebar.find("img[src*='/images/']").attr("src") ?? "";
    const age = ageImage.match(AGE_IMAGE)?.[1]?.toLowerCase();
    const rating = age ? finnishRating(age) : undefined;
    if (ageImage && !rating) {
      unmapped.push(`rating:${ageImage.split("/").at(-1)}`);
    }
    const runtimeMatch = lines.map((l) => l.match(RUNTIME)).find(Boolean);
    const runtime = runtimeMatch ? Number(runtimeMatch[1]) * 60 + Number(runtimeMatch[2]) : 0;
    const priceLine = lines.find((l) => /^Lipun hinta/i.test(l));
    const price = toCents(priceLine?.match(PRICE)?.[1], { zeroIsFree: false });

    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const listingId = makeId(P, "film", slug);

    const at = lines.findIndex((l) => /^Elokuvan näytökset$/i.test(l));
    for (const line of at < 0 ? [] : lines.slice(at + 1)) {
      if (/^Ikäraja$/i.test(line)) {
        break;
      }
      const m = line.match(SHOW);
      const weekday = m ? WEEKDAYS.indexOf(m[1]!.toLowerCase()) : -1;
      const start =
        m &&
        helsinkiShowTime({
          year: Number(m[4]),
          month: Number(m[3]),
          day: Number(m[2]),
          hour: Number(m[5]),
          minute: Number(m[6]),
        });
      if (
        !start ||
        weekday < 0 ||
        Temporal.PlainDate.from(start.startsAt.slice(0, 10)).dayOfWeek - 1 !== weekday
      ) {
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
        ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
        // Tickets at the box office: the film's page, copied.
        ticketUrl: url,
        unmappedLabels: unmapped,
        fetchedAt: raw.fetchedAt,
      });
    }
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} showtime lines not understood (or a weekday that does not fit the date)`,
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
