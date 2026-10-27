import {
  makeId,
  type FilmListing,
  type FinnishRating,
  type ProviderBatch,
  type RawLabel,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import { own } from "../../lib/records.ts";
import {
  COMMON_TITLE_PREFIXES,
  findLabel,
  LABELS,
  labelEffects,
  splitTitlePrefix,
  splitVersion,
} from "../labels.ts";
import { byStartThenId, plainText, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { KinoRioRawSnapshot } from "./fetch.ts";
import type { KinoRioSite } from "./sites.ts";

const WEEKDAYS = ["ma", "ti", "ke", "to", "pe", "la", "su"];
/** "Pe 16.10. klo 18.30", then maybe a fact on the same line. */
const ROW =
  /^(ma|ti|ke|to|pe|la|su)\s+(\d{1,2})\.(\d{1,2})\.?\s+klo\s+(\d{1,2})[.:](\d{2})\s*(.*)$/i;
const ROWISH = /^(ma|ti|ke|to|pe|la|su)\s+\d/i;
const RUNTIME = /Kesto:\s*(\d+)\s*h\s*(\d+)\s*min/i;
const AGE = /Ikäraja:\s*(S|K-?\d{1,2})\b/i;
const PRICE = /Liput\s*:\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*€/i;
const DUBBED = /^puhuttu suomeksi$/i;
const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  K7: "K-7",
  K12: "K-12",
  K16: "K-16",
  K18: "K-18",
};

/** Pure: the front page + site config -> normalized batch. */
export const parseKinoRio = (raw: KinoRioRawSnapshot, site: KinoRioSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  // One block per film between the separators; blocks without a list are not films.
  const blocks = raw.html
    .split(/<hr\b[^>]*>/i)
    .map((chunk) => load(chunk, null, false))
    .filter((b) => b("li").length > 0);
  if (blocks.length === 0) {
    warnings.push({ code: "invalid-response", message: "No film blocks on the front page" });
  }
  let unreadable = 0;
  for (const $ of blocks) {
    const rawTitle = $("p strong")
      .toArray()
      .map((el) => plainText($(el).text()))
      .find((t) => t && !/^Lue lisää$/i.test(t) && !DUBBED.test(t));
    const lines = $("li")
      .toArray()
      .map((el) => plainText($(el).text()));
    const notes = $("p")
      .toArray()
      .map((el) => plainText($(el).text()));
    const facts = lines.join(" ");
    const duration = facts.match(RUNTIME);
    const runtime = duration ? Number(duration[1]) * 60 + Number(duration[2]) : 0;
    const age = facts.match(AGE)?.[1]?.toUpperCase().replace("-", "");
    const rating = age ? own(RATINGS, age) : undefined;
    const unmapped = age && !rating ? [`rating:${age}`] : [];
    const price = toCents(facts.match(PRICE)?.[1], { zeroIsFree: false });
    const dubbed = notes.some((n) => DUBBED.test(n));
    // Block notes the label table knows are kept as labels. Only "viimeiset näytökset"
    // speaks of every row listed; "Suomen ensi-ilta" is the film's, not each row's.
    const known = notes.filter((n) => findLabel(n, LABELS));
    const lastRows = labelEffects(known.map((n) => findLabel(n, LABELS))).tags.includes(
      "last-screening",
    );
    if (!rawTitle) {
      unreadable += lines.filter((l) => ROWISH.test(l)).length;
      continue;
    }
    const { title: unprefixed, rule, label } = splitTitlePrefix(rawTitle, prefixRules);
    const effects = labelEffects([rule]);
    const tags = [
      ...new Set([...effects.tags, ...(lastRows ? (["last-screening"] as const) : [])]),
    ];
    const labels: RawLabel[] = [
      ...(label ? [{ source: "title.prefix", text: label }] : []),
      ...known.map((note) => ({ source: "block.note", text: note })),
    ];
    const { title, version } = splitVersion(unprefixed);
    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);

    for (const line of lines.filter((l) => ROWISH.test(l))) {
      const m = line.match(ROW);
      const date = m ? nearestDate(Number(m[2]), Number(m[3]), raw.from) : undefined;
      const fits =
        date && WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] === m![1]!.toLowerCase();
      const start =
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
          sourceId: filmKey,
          title: { fi: title },
          ...(runtime > 0 && { runtimeMinutes: runtime }),
          ...(rating && { rating }),
          genres: [],
          countries: [],
          kind: rule?.event ? "event" : "film",
        });
      }
      const audio = version.audio ?? (dubbed ? "fi" : undefined);
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
        ...((version.dubbed !== undefined || dubbed) && { dubbed: version.dubbed ?? dubbed }),
        subtitles: { kind: "unknown" },
        tags,
        series: effects.series,
        availability: "unknown",
        ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
        // Tickets at the door: the programme page.
        ticketUrl: site.programme,
        unmappedLabels: unmapped,
        ...(labels.length > 0 && { labels }),
        fetchedAt: raw.fetchedAt,
      });
    }
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} screening rows not understood, or with a weekday that fits no date`,
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
