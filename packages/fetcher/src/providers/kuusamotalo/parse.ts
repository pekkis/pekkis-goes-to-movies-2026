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
import { z } from "zod";
import { own } from "../../lib/records.ts";
import {
  COMMON_TITLE_PREFIXES,
  findLabel,
  LABELS,
  splitTitlePrefix,
  splitVersion,
} from "../labels.ts";
import { byStartThenId, plainText, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { KuusamotaloRawSnapshot } from "./fetch.ts";
import type { KuusamotaloSite } from "./sites.ts";

const Post = z.looseObject({
  id: z.number().int(),
  link: z.string(),
  title: z.looseObject({ rendered: z.string() }),
  content: z.looseObject({ rendered: z.string() }),
});

const WEEKDAYS = ["MA", "TI", "KE", "TO", "PE", "LA", "SU"];
/** "Ke 14.10. klo 15 ja 19", "Su 18.10. klo 16.30" */
const ROW = /^(Ma|Ti|Ke|To|Pe|La|Su)\s+(\d{1,2})\.(\d{1,2})\.?\s+klo\s+(.+)$/i;
/** One time in a row: "15", "16.30", "16:30". */
const TIME = /^(\d{1,2})(?:[.:](\d{2}))?$/;
const AGE = /^-?\s*(S|K-?\d{1,2})\s*-?$/i;
const DURATION = /^Kesto\s+(?:(\d+)\s*h)?\s*(\d+)\s*min$/i;
const PRICE = /^Liput\s+(\d{1,3}(?:[.,]\d{1,2})?)\s*€$/i;
const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  "K-7": "K-7",
  "K-12": "K-12",
  "K-16": "K-16",
  "K-18": "K-18",
};

/** Pure: the posts + site config -> normalized batch. */
export const parseKuusamotalo = (
  raw: KuusamotaloRawSnapshot,
  site: KuusamotaloSite,
): ProviderBatch => {
  const P = site.provider;
  const venue = site.venues[0]!;
  const venueId = makeId(P, "venue", venue.slug);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();

  const posts = z.array(z.unknown()).safeParse(raw.posts);
  if (!posts.success) {
    warnings.push({ code: "invalid-response", message: "Not a list of posts" });
  }
  let unreadable = 0;
  for (const item of posts.success ? posts.data : []) {
    const parsed = Post.safeParse(item);
    if (!parsed.success) {
      warnings.push({ code: "invalid-post", message: parsed.error.message });
      continue;
    }
    const post = parsed.data;
    // The post's text, one entry per line or paragraph.
    const lines = post.content.rendered
      .split(/<br\s*\/?>|<\/?(?:p|li|h\d)\b[^>]*>/i)
      .map((chunk) => plainText(load(chunk, null, false).text()))
      .filter(Boolean);
    const at = lines.findIndex((l) => /^Esitysajat:?$/i.test(l));
    if (at < 0) {
      continue; // a notice (gift cards, closing times), not a film
    }
    const before = lines.slice(0, at);
    const age = before.map((l) => l.match(AGE)?.[1]).find(Boolean);
    const rating = age ? own(RATINGS, age.toUpperCase().replace(/^K(\d)/, "K-$1")) : undefined;
    const duration = before.map((l) => l.match(DURATION)).find(Boolean);
    const runtime = duration ? Number(duration[1] ?? 0) * 60 + Number(duration[2]) : 0;
    const price = toCents(before.map((l) => l.match(PRICE)?.[1]).find(Boolean), {
      zeroIsFree: false,
    });
    const rawTitle = plainText(load(post.title.rendered, null, false).text());
    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const listingId = makeId(P, "film", String(post.id));

    for (const row of lines.slice(at + 1)) {
      const m = row.match(ROW);
      if (!m) {
        // The list ends where the lines stop looking like days.
        break;
      }
      const date = nearestDate(Number(m[2]), Number(m[3]), raw.from);
      const weekday = date ? WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] : undefined;
      if (!date || weekday !== m[1]!.toUpperCase()) {
        unreadable += 1;
        continue;
      }
      // A note after the times: "klo 15 ja 19 ( viimeinen näytös )" (2026-10-18).
      const noted = m[4]!.match(/^(.*?)\s*\(\s*([^()]+?)\s*\)\s*$/);
      const note = noted?.[2];
      const noteRule = note ? findLabel(note, LABELS) : undefined;
      // "klo 15 ja 19": several screenings on one day.
      const times = (noted ? noted[1]! : m[4]!).split(/\s*(?:,|\bja\b)\s*/i);
      for (const [i, t] of times.entries()) {
        const tm = t.trim().match(TIME);
        const start =
          tm &&
          helsinkiShowTime({
            year: Number(date.slice(0, 4)),
            month: Number(m[3]),
            day: Number(m[2]),
            hour: Number(tm[1]),
            minute: Number(tm[2] ?? 0),
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
            sourceId: String(post.id),
            title: { fi: title },
            ...(runtime > 0 && { runtimeMinutes: runtime }),
            ...(rating && { rating }),
            genres: [],
            countries: [],
            kind: rule?.event ? "event" : "film",
          });
        }
        const sourceId = `${post.id}-${start.startsAt.slice(0, 16).replace(/[-T:]/g, "")}`;
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
          tags: [
            ...new Set([
              ...(rule?.tags ?? []),
              // "Viimeinen näytös" is the day's last time; any other note covers the row.
              ...(noteRule?.tags ?? []).filter(
                (tag) => tag !== "last-screening" || i === times.length - 1,
              ),
            ]),
          ],
          series: rule?.series ? [rule.series] : [],
          availability: noteRule?.availability ?? "unknown",
          ...(price !== undefined && { price: { amountCents: price, currency: "EUR" as const } }),
          // The film's post on the cinema's site, copied.
          ticketUrl: post.link.startsWith(`${site.base}/`) ? post.link : site.homepage,
          unmappedLabels: note && !noteRule ? [`note:${note}`] : [],
          ...(note && { labels: [{ source: "row.note", text: note }] }),
          fetchedAt: raw.fetchedAt,
        });
      }
    }
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} screening times not understood, or with a weekday that fits no date`,
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
