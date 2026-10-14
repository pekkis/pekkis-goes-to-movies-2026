import {
  makeId,
  type FilmListing,
  type ProviderBatch,
  type Screening,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId, slugify } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { KuvakukkoRawSnapshot } from "./fetch.ts";
import type { KuvakukkoSite } from "./sites.ts";

const WEEKDAYS = [
  "maanantai",
  "tiistai",
  "keskiviikko",
  "torstai",
  "perjantai",
  "lauantai",
  "sunnuntai",
];

/** "Keskiviikko 14.10." */
const DAY = /^([a-zäö]+)\s+(\d{1,2})\.(\d{1,2})\.?$/i;
/** "Klo 13: …", "Klo 17.30: …" */
const ROW = /^klo\s*(\d{1,2})(?:[.:](\d{2}))?\s*:\s*(.*)$/i;

const text = (value: string | undefined) =>
  (value ?? "").replace(/ /g, " ").replace(/\s+/g, " ").trim();

/** Drops a trailing note in parentheses (closed or not) that opens with a configured word. */
const withoutNotes = (title: string, notes: string[]) => {
  const open = title.lastIndexOf("(");
  if (open <= 0) {
    return title;
  }
  const note = title.slice(open + 1).toLowerCase();
  return notes.some((n) => note.startsWith(n.toLowerCase())) ? title.slice(0, open).trim() : title;
};

/** Pure: the programme page + site config -> normalized batch. */
export const parseKuvakukko = (raw: KuvakukkoRawSnapshot, site: KuvakukkoSite): ProviderBatch => {
  const P = site.provider;
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  const headings = $("h2").toArray();
  for (const venue of site.venues) {
    const heading = headings.find((h) => {
      const title = text($(h).text()).toLowerCase();
      return title.includes(venue.heading) && title.includes("esitysaikataulu");
    });
    if (!heading) {
      warnings.push({
        code: "invalid-response",
        message: `No schedule heading for ${venue.name}`,
        context: { venue: venue.slug },
      });
      continue;
    }
    const venueId = makeId(P, "venue", venue.slug);
    // Everything up to the next heading is this cinema's; a paragraph may hold several days.
    const lines = $(heading)
      .nextUntil("h2")
      .filter("p")
      .toArray()
      .flatMap((p) => ($(p).html() ?? "").split(/<br\s*\/?>/i));

    let date: string | undefined;
    for (const line of lines) {
      const fragment = load(line, null, false);
      const lineText = text(fragment.text());
      const day = lineText.match(DAY);
      if (day && WEEKDAYS.includes(day[1]!.toLowerCase())) {
        date = nearestDate(Number(day[2]), Number(day[3]), raw.from);
        const weekday = date ? WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] : undefined;
        if (weekday !== day[1]!.toLowerCase()) {
          // The weekday is the only check on the year we infer: a mismatch places nothing.
          warnings.push({
            code: "invalid-start",
            message: `Day "${lineText}" has no matching date near ${raw.from}`,
            context: { venue: venue.slug },
          });
          date = undefined;
        }
        continue;
      }
      const row = lineText.match(ROW);
      if (!row) {
        continue; // prices, addresses, "next week's programme is published on Tuesday"
      }
      // The first link with text is the title (an empty link sometimes precedes it);
      // unlinked rows are the whole rest of the line.
      const linked = fragment("a")
        .toArray()
        .map((a) => text(fragment(a).text()))
        .find(Boolean);
      const rawTitle = withoutNotes(linked ?? text(row[3]), site.titleNotes);
      const start =
        date &&
        helsinkiShowTime({
          year: Number(date.slice(0, 4)),
          month: Number(date.slice(5, 7)),
          day: Number(date.slice(8, 10)),
          hour: Number(row[1]),
          minute: Number(row[2] ?? 0),
        });
      if (!rawTitle || !start) {
        warnings.push({
          code: "invalid-row",
          message: `Unreadable row "${lineText}"${date ? "" : " (no day before it)"}`,
          context: { venue: venue.slug },
        });
        continue;
      }
      if (start.businessDate < window.from || start.businessDate > window.to) {
        continue;
      }

      const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
      const { title, version } = splitVersion(unprefixed);
      const filmKey = slugify(title);
      const listingId = makeId(P, "film", filmKey);
      if (!listings.has(listingId)) {
        listings.set(listingId, {
          id: listingId,
          provider: P,
          sourceId: filmKey,
          title: { fi: title },
          genres: [],
          countries: [],
          kind: rule?.event ? "event" : "film",
        });
      }
      // No ids on the page: venue, film and start minute.
      const sourceId = `${venue.slug}-${filmKey}-${start.startsAt.slice(0, 16).replace(/[-T:]/g, "")}`;
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
        // Tickets are sold at the door; the programme is the page to send people to. The
        // rows' own links are not used: they often point at a reused page of another film.
        ticketUrl: site.programme,
        unmappedLabels: [],
        fetchedAt: raw.fetchedAt,
      });
    }
  }

  return {
    provider: providerOf(site, "custom", "door"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: site.venues.map((v) => toVenue(P, v, v.slug)),
    auditoriums: [],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
