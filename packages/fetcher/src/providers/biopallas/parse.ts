import {
  makeId,
  type FilmListing,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import {
  COMMON_TITLE_PREFIXES,
  isPrivateBooking,
  splitTitlePrefix,
  splitVersion,
  type Version,
} from "../labels.ts";
import { byStartThenId, finnishRating, plainText, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { BioPallasRawSnapshot } from "./fetch.ts";
import type { BioPallasSite } from "./sites.ts";

const WEEKDAYS = ["MA", "TI", "KE", "TO", "PE", "LA", "SU"];
/** "Ke/Ons 14.10", "Ti 13.10": the Finnish weekday first. */
const DATE = /^(Ma|Ti|Ke|To|Pe|La|Su)(?:\/[A-Za-zåäö]+)?\s+(\d{1,2})\.(\d{1,2})\.?$/i;
const TIME = /^Klo\s+(\d{1,2})[.:](\d{2})$/i;
/** "1h 52min -K12-", "1h 33min -K-16-", "1h 26min -S-" */
const FACTS = /^(?:(\d+)\s*h)?\s*(\d+)\s*min\s*-?(S|K-?\d{1,2})?-?$/i;

/** Pure: the front page + site config -> normalized batch. */
export const parseBioPallas = (raw: BioPallasRawSnapshot, site: BioPallasSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  // Each rich-text block as its lines, in document order.
  const blocks = $("[data-testid='richTextElement']")
    .toArray()
    .map((b) =>
      $(b)
        .find("p, h1, h2, h3, h4, h5, h6, li")
        .toArray()
        .map((p) => plainText($(p).text()))
        .filter(Boolean),
    );
  if (blocks.length === 0) {
    warnings.push({ code: "invalid-response", message: "No text blocks on the front page" });
  }
  let unreadable = 0;
  blocks.forEach((lines, i) => {
    // A screening is a block of a date and a time; a lone date is "coming soon".
    const d = lines[0]?.match(DATE);
    const t = lines[1]?.match(TIME);
    if (!d || !t || lines.length !== 2) {
      return;
    }
    const titleBlock = blocks[i - 1] ?? [];
    const priceBlock = blocks[i + 1] ?? [];
    const factsLine = titleBlock.find((l) => FACTS.test(l));
    const facts = factsLine?.match(FACTS);
    const rawTitle = titleBlock[0] ?? "";
    // A line between the title and the facts is the print's version: "På svenska".
    const versionLine = titleBlock.slice(1).find((l) => l !== factsLine);
    const lineVersion: Version = versionLine ? splitVersion(`x (${versionLine})`).version : {};
    const date = nearestDate(Number(d[2]), Number(d[3]), raw.from);
    const weekday = date ? WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] : undefined;
    const start =
      date &&
      // The weekday is the only check on the year we infer.
      weekday === d[1]!.toUpperCase() &&
      helsinkiShowTime({
        year: Number(date.slice(0, 4)),
        month: Number(d[3]),
        day: Number(d[2]),
        hour: Number(t[1]),
        minute: Number(t[2]),
      });
    if (!start || !rawTitle || DATE.test(rawTitle)) {
      unreadable += 1;
      return;
    }
    if (start.businessDate < window.from || start.businessDate > window.to) {
      return;
    }
    if (isPrivateBooking(rawTitle)) {
      return; // a private event: nothing to list, nothing missing (2026-10-19)
    }
    const unmapped: string[] = [];
    if (versionLine && lineVersion.audio === undefined && lineVersion.dubbed === undefined) {
      unmapped.push(`version:${versionLine}`);
    }
    const age = facts?.[3]?.toUpperCase().replace("-", "");
    const rating = age ? finnishRating(age) : undefined;
    if (age && !rating) {
      unmapped.push(`rating:${age}`);
    }
    const runtime = facts ? Number(facts[1] ?? 0) * 60 + Number(facts[2]) : 0;
    // One amount settles the price ("12€ med kaffeserv."); "22/25€" does not.
    const priceLine = priceBlock.find((l) => l.includes("€")) ?? "";
    const amounts = priceLine.match(/\d{1,3}(?:[.,]\d{1,2})?/g) ?? [];
    const price = amounts.length === 1 ? toCents(amounts[0], { zeroIsFree: false }) : undefined;

    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version: titleVersion } = splitVersion(unprefixed);
    const version = { ...lineVersion, ...titleVersion };
    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);
    if (!listings.has(listingId)) {
      listings.set(listingId, {
        id: listingId,
        provider: P,
        sourceId: filmKey,
        title: { fi: title },
        ...(runtime > 0 && { runtimeMinutes: runtime }),
        ...(rating && { rating }),
        genres: [],
        countries: [],
        kind: rule?.event ? "event" : "film",
      });
    }
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
      audio: version.audio ? [version.audio] : [],
      ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
      subtitles: { kind: "unknown" },
      tags: [...(rule?.tags ?? [])],
      series: rule?.series ? [rule.series] : [],
      availability: "unknown",
      ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
      // Tickets at the door: the programme page.
      ticketUrl: `${site.homepage}/`,
      unmappedLabels: unmapped,
      fetchedAt: raw.fetchedAt,
    });
  });
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} screenings without a title, or with a weekday that fits no date`,
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
