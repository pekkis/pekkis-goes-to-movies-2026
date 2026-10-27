import {
  makeId,
  type FilmListing,
  type ProviderBatch,
  type Screening,
  type Subtitles,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import { own } from "../../lib/records.ts";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, finnishRating, plainText, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { LieksaRawSnapshot } from "./fetch.ts";
import type { LieksaSite } from "./sites.ts";

const WEEKDAYS = ["MA", "TI", "KE", "TO", "PE", "LA", "SU"];
/** "La 17.10. 15.00", "Ti 20.10. 13.00 Tekstitetty" */
const ROW =
  /^(Ma|Ti|Ke|To|Pe|La|Su)\s+(\d{1,2})\.(\d{1,2})\.?\s+(\d{1,2})[.:](\d{2})(?:\s+(.+))?$/i;
/** Notes after the time that this parser understands. */
const NOTES: Record<string, { subtitles?: Subtitles }> = {
  // Finnish films "tekstitetty": Finnish subtitles.
  tekstitetty: { subtitles: { kind: "languages", languages: ["fi"] } },
};
/** The rating icon: "graphics/rating-icon-12.svg", "rating-icon-s.svg". */
const AGE_ICON = /rating-icon-(s|7|12|16|18)\.svg$/i;

/** Pure: the page + site config -> normalized batch. */
export const parseLieksa = (raw: LieksaRawSnapshot, site: LieksaSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  // Only the programme section: the coming-soon section uses the same markup.
  const section = $("#section-b");
  if (section.length === 0) {
    warnings.push({ code: "invalid-response", message: "No #section-b programme on the page" });
  }
  let unreadable = 0;
  for (const el of section.find("article.entry").toArray()) {
    const article = $(el);
    const rawTitle = plainText(article.find("h3").first().text());
    if (!rawTitle) {
      continue;
    }
    const cells = article
      .find(".side-row-cell")
      .toArray()
      .map((c) => ({ text: plainText($(c).text()), icon: $(c).find("img").attr("src") ?? "" }));
    const price = toCents(
      cells
        .map((c) => c.text.match(/^Liput:\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*€$/i)?.[1])
        .find(Boolean),
      { zeroIsFree: false },
    );
    const runtime = Number(
      cells.map((c) => c.text.match(/^Kesto:\s*(\d{2,3})\s*min$/i)?.[1]).find(Boolean) ?? 0,
    );
    const icon = cells.map((c) => c.icon).find((src) => /rating-icon/.test(src)) ?? "";
    const age = icon.match(AGE_ICON)?.[1];
    const rating = age ? finnishRating(age.toUpperCase()) : undefined;
    const iconUnmapped = icon && !rating ? [`rating:${icon.split("/").at(-1)}`] : [];

    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);

    for (const li of article.find(".showtimes li").toArray()) {
      const row = plainText($(li).text());
      if (!row) {
        continue;
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
      if (!m || !start) {
        unreadable += 1;
        continue;
      }
      if (start.businessDate < window.from || start.businessDate > window.to) {
        continue;
      }
      const unmapped = [...iconUnmapped];
      const note = m[6]?.toLowerCase();
      const noteRule = note ? own(NOTES, note) : undefined;
      if (note && !noteRule) {
        unmapped.push(`note:${m[6]}`);
      }
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
        subtitles: noteRule?.subtitles ?? { kind: "unknown" },
        tags: [...(rule?.tags ?? [])],
        series: rule?.series ? [rule.series] : [],
        availability: "unknown",
        ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
        // Tickets at the door: the page.
        ticketUrl: `${site.homepage}/`,
        unmappedLabels: unmapped,
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
