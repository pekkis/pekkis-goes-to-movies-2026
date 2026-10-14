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
import { byStartThenId, slugify } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { EngelRawSnapshot } from "./fetch.ts";
import type { EngelSite } from "./sites.ts";

/** The day block's id: "rsj_2026-10-14". */
const DAY_ID = /^rsj_(\d{4})-(\d{2})-(\d{2})$/;
/** "Ke 14.10." beside the time: checked against the block's date. */
const SHOWN_DAY = /(\d{1,2})\.(\d{1,2})\./;
const TIME = /klo\s*(\d{1,2})[:.](\d{2})/i;

const text = (value: string | undefined) => (value ?? "").replace(/\s+/g, " ").trim();

/** Pure: the front page + site config -> normalized batch. */
export const parseEngel = (raw: EngelRawSnapshot, site: EngelSite): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const $ = load(raw.html);
  if ($(".rs-johku-movies").length === 0) {
    warnings.push({ code: "invalid-response", message: "No schedule on the front page" });
  }
  let unreadable = 0;
  // Each day appears twice on the page; the same screening twice is one.
  $(".johku-movie-matrix").each((_index, day) => {
    const d = ($(day).attr("id") ?? "").match(DAY_ID);
    $(day)
      .find(".rs-johku-schedule")
      .each((_r, el) => {
        const row = $(el);
        const rawTitle = text(row.find(".movie-name").text());
        const when = text(row.find(".movie-date-time").text());
        const time = when.match(TIME);
        if (!/\bklo\b/i.test(when)) {
          // "Coming soon": the opening day without a time ("Pe 30.10. Lue lisää").
          return;
        }
        const shown = when.match(SHOWN_DAY);
        const href = row.find("a").first().attr("href") ?? "";
        const start =
          d &&
          time &&
          helsinkiShowTime({
            year: Number(d[1]),
            month: Number(d[2]),
            day: Number(d[3]),
            hour: Number(time[1]),
            minute: Number(time[2]),
          });
        const agrees =
          !shown || (Number(shown[1]) === Number(d?.[3]) && Number(shown[2]) === Number(d?.[2]));
        if (!rawTitle || !start || !agrees || !href.startsWith(`${site.base}/`)) {
          unreadable += 1;
          return;
        }
        if (start.businessDate < window.from || start.businessDate > window.to) {
          return;
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
        // No screening ids on the page: film and start minute.
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
          presentation: {
            projection: "digital",
            dimension: version.dimension ?? "2d",
            formats: [],
          },
          audio: version.audio ? [version.audio] : [],
          ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
          subtitles: { kind: "unknown" },
          tags: [...(rule?.tags ?? [])],
          series: rule?.series ? [rule.series] : [],
          availability: "unknown",
          // The film's page, where its "Osta liput" button leads: copied.
          ticketUrl: href,
          unmappedLabels: [],
          fetchedAt: raw.fetchedAt,
        });
      });
  });
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} schedule rows without a title, a readable date and time, or a link`,
    });
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
