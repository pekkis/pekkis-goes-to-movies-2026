import {
  makeId,
  type FilmListing,
  type FinnishRating,
  type ProviderBatch,
  type Screening,
  type ScreeningTag,
  type Subtitles,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import { own } from "../../lib/records.ts";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, slugify } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { VirtainPirttiRawSnapshot } from "./fetch.ts";
import type { VirtainPirttiSite } from "./sites.ts";

const WEEKDAYS = ["ma", "ti", "ke", "to", "pe", "la", "su"];
/** "Kerro kaikille K-12", "Unohdettu saari K-7 dub.", "Pirjo i Sverige -S-". */
const HEAD = /^(.+?)\s+(-S-|K-?\d{1,2})(\s+dub\.?)?$/i;
/** "pe 16.10. klo 15.15*": the star points to the footnote. */
const ROW = /^(ma|ti|ke|to|pe|la|su)\s+(\d{1,2})\.(\d{1,2})\.?\s+klo\s+(\d{1,2})[.:](\d{2})(\*)?$/i;
const ROWISH = /^(ma|ti|ke|to|pe|la|su)\s+\d/i;
/** "*16.10. ja 21.10. tekstitys suomeksi". */
const FOOTNOTE_FI = /^\*.*tekstitys suomeksi/i;
const PREVIEW = /^Ennakkonäytös$/i;
const DURATION = /^Kesto\s+(\d+)\s*h\s*(\d+)\s*min$/i;
const RATINGS: Record<string, FinnishRating> = {
  "-S-": "S",
  K7: "K-7",
  K12: "K-12",
  K16: "K-16",
  K18: "K-18",
};

const text = (value: string | undefined) =>
  (value ?? "").replace(/​/g, "").replace(/\s+/g, " ").trim();

/** Pure: the programme page + site config -> normalized batch. */
export const parseVirtainPirtti = (
  raw: VirtainPirttiRawSnapshot,
  site: VirtainPirttiSite,
): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  const films = $("div.paragraph")
    .toArray()
    .map((el) =>
      ($(el).html() ?? "")
        .split(/<br\s*\/?>/i)
        .map((chunk) => text(load(chunk, null, false).text()))
        .filter(Boolean),
    )
    .filter((lines) => lines.some((l) => ROWISH.test(l)));
  if (films.length === 0) {
    warnings.push({ code: "invalid-response", message: "No films on the programme page" });
  }
  let unreadable = 0;
  for (const lines of films) {
    const head = lines[0]!.match(HEAD);
    const rows = lines.filter((l) => ROWISH.test(l));
    if (!head) {
      unreadable += rows.length;
      continue;
    }
    const age = head[2]!.toUpperCase().replace(/^K-?/, "K");
    const rating = own(RATINGS, age);
    const dubbed = Boolean(head[3]);
    const duration = lines.map((l) => l.match(DURATION)).find(Boolean);
    const runtime = duration ? Number(duration[1]) * 60 + Number(duration[2]) : 0;
    const starredFi = lines.some((l) => FOOTNOTE_FI.test(l));
    const tags: ScreeningTag[] = lines.some((l) => PREVIEW.test(l)) ? ["preview"] : [];

    const { title: unprefixed, rule } = splitTitlePrefix(head[1]!, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const filmKey = slugify(title);
    const listingId = makeId(P, "film", filmKey);
    for (const line of rows) {
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
      const subtitles: Subtitles =
        m[6] && starredFi ? { kind: "languages", languages: ["fi"] } : { kind: "unknown" };
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
        subtitles,
        tags: [...tags, ...(rule?.tags ?? [])],
        series: rule?.series ? [rule.series] : [],
        availability: "unknown",
        // Tickets at the door: the programme page.
        ticketUrl: site.programme,
        unmappedLabels: rating ? [] : [`rating:${head[2]}`],
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
