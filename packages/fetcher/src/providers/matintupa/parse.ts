import {
  makeId,
  type FilmListing,
  type FinnishRating,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { MatinTupaRawSnapshot } from "./fetch.ts";
import type { MatinTupaSite } from "./sites.ts";

const WEEKDAYS = ["MA", "TI", "KE", "TO", "PE", "LA", "SU"];
/** "ti 13.10. klo 19.20" */
const ROW = /^(ma|ti|ke|to|pe|la|su)\s+(\d{1,2})\.(\d{1,2})\.?\s+klo\s+(\d{1,2})[.:](\d{2})$/i;
/** "Kesto: 1 t 28 min" */
const DURATION = /^Kesto:\s*(?:(\d+)\s*t)?\s*(\d+)\s*min$/i;
/** "Liput: 14 €" and nothing else: an age band or extra settles no single price. */
const PRICE = /^Liput:\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*€$/i;
/** The KAVI sentence in the notes: "Sallittu yli 7-vuotiaille.", "Sallittu kaikenikäisille." */
const AGE = /Sallittu\s+(?:yli\s+(7|12|16|18)-vuotiaille|kaikenikäisille)/i;
/** The rating image: ".../ikaraja_sallittu-wpcf_30x30.png", "ikaraja_12-…". */
const AGE_IMAGE = /ikaraja_(sallittu|s|7|12|16|18)\b/i;
const RATINGS: Record<string, FinnishRating> = {
  sallittu: "S",
  s: "S",
  "7": "K-7",
  "12": "K-12",
  "16": "K-16",
  "18": "K-18",
};

const text = (value: string | undefined) => (value ?? "").replace(/\s+/g, " ").trim();

/** Pure: the programme page + site config -> normalized batch. */
export const parseMatinTupa = (raw: MatinTupaRawSnapshot, site: MatinTupaSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  const links = $("h2 a[href*='/elokuvat/']").toArray();
  if (links.length === 0) {
    warnings.push({ code: "invalid-response", message: "No film blocks on the programme page" });
  }
  let unreadable = 0;
  for (const a of links) {
    const rawTitle = text($(a).text());
    const href = $(a).attr("href") ?? "";
    const slug = href.match(/\/elokuvat\/([^/?#]+)\/?$/)?.[1];
    const block = $(a).closest("div.col-sm-6");
    if (!rawTitle || !slug) {
      continue;
    }
    // The block as lines: labels, screening rows and the notes after them.
    const lines = (block.html() ?? "")
      .split(/<br\s*\/?>|<\/?(?:p|div|h\d)\b[^>]*>/i)
      .map((chunk) => text(load(chunk, null, false).text()))
      .filter(Boolean);
    const runtimeMatch = lines.map((l) => l.match(DURATION)).find(Boolean);
    const runtime = runtimeMatch ? Number(runtimeMatch[1] ?? 0) * 60 + Number(runtimeMatch[2]) : 0;
    const price = toCents(lines.map((l) => l.match(PRICE)?.[1]).find(Boolean), {
      zeroIsFree: false,
    });
    const genres = (lines.find((l) => /^Genre:/i.test(l)) ?? "")
      .replace(/^Genre:\s*/i, "")
      .split(",")
      .map((g) => g.trim())
      .filter(Boolean);
    const notes = lines.join(" ");
    // The rating image first; the KAVI sentence in the notes otherwise.
    const imageAge = block
      .find("img")
      .toArray()
      .map((img) => ($(img).attr("src") ?? "").match(AGE_IMAGE)?.[1]?.toLowerCase())
      .find(Boolean);
    const sentence = notes.match(AGE);
    const rating: FinnishRating | undefined = imageAge
      ? RATINGS[imageAge]
      : sentence
        ? sentence[1]
          ? RATINGS[sentence[1]]
          : "S"
        : undefined;
    // "Puhumme suomea." in the notes: dubbed into Finnish.
    const noteVersion = /puhumme suomea/i.test(notes)
      ? splitVersion("x (puhumme suomea)").version
      : {};

    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version: titleVersion } = splitVersion(unprefixed);
    const version = { ...noteVersion, ...titleVersion };
    const listingId = makeId(P, "film", slug);

    const at = lines.findIndex((l) => /^Esitysajat:?$/i.test(l));
    for (const row of at >= 0 ? lines.slice(at + 1) : []) {
      if (/^(Liput|Kesto|Genre):/i.test(row)) {
        break;
      }
      const m = row.match(ROW);
      const date = m ? nearestDate(Number(m[2]), Number(m[3]), raw.from) : undefined;
      const weekday = date ? WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] : undefined;
      const start =
        m &&
        date &&
        // The weekday is the only check on the year we infer.
        weekday === m[1]!.toUpperCase() &&
        helsinkiShowTime({
          year: Number(date.slice(0, 4)),
          month: Number(m[3]),
          day: Number(m[2]),
          hour: Number(m[4]),
          minute: Number(m[5]),
        });
      if (!start) {
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
          genres,
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
        // Tickets at the door: the film's page, copied.
        ticketUrl: href.startsWith(`${site.homepage}/`) ? href : site.programme,
        unmappedLabels: [],
        fetchedAt: raw.fetchedAt,
      });
    }
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} screening lines not understood, or with a weekday that fits no date`,
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
