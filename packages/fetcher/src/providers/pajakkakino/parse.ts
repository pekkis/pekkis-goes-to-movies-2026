import {
  makeId,
  type FilmListing,
  type FinnishRating,
  type Lang,
  type ProviderBatch,
  type Screening,
  type Subtitles,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load } from "cheerio";
import { z } from "zod";
import { normalizeLang } from "../../lib/lang.ts";
import { own } from "../../lib/records.ts";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { byStartThenId } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { PajakkakinoRawSnapshot } from "./fetch.ts";
import type { PajakkakinoSite } from "./sites.ts";

const Post = z.looseObject({
  id: z.number().int(),
  link: z.string(),
  title: z.looseObject({ rendered: z.string() }),
  content: z.looseObject({ rendered: z.string() }),
});

const WEEKDAYS = ["MA", "TI", "KE", "TO", "PE", "LA", "SU"];
/** "PE 16.10. KLO 15:30", "SU 18.10 KLO 18:00", "PE 9.10 KLO.16:30". */
const ROW = /^(MA|TI|KE|TO|PE|LA|SU)\s+(\d{1,2})\.(\d{1,2})\.?\s+KLO\.?\s*(\d{1,2})[.:](\d{2})$/i;
/** Starts like a screening row: anything else after the heading is a note ("PERUTTU!"). */
const ROWISH = /^(MA|TI|KE|TO|PE|LA|SU)\s+\d/i;
/** A struck-through (cancelled) row is marked before the HTML becomes text. */
const STRUCK = "✖";
const RUNTIME = /^(?:(\d+)\s*h)?\s*(\d+)\s*min$/i;
const AUDIO = /\bAUDIO\s+([a-zäö]+)/i;
const SUBTITLES = /\bTEKSTIT\s+([a-zäö]+)/i;
const AGE_IMAGE = /ikaraja_(s|7|12|16|18)\.png/i;
const RATINGS: Record<string, FinnishRating> = {
  s: "S",
  "7": "K-7",
  "12": "K-12",
  "16": "K-16",
  "18": "K-18",
};

const text = (value: string | undefined) => (value ?? "").replace(/\s+/g, " ").trim();

/** Pure: the posts + site config -> normalized batch. */
export const parsePajakkakino = (
  raw: PajakkakinoRawSnapshot,
  site: PajakkakinoSite,
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
    const html = post.content.rendered.replace(/<del\b[^>]*>/gi, `$&${STRUCK}`);
    const lines = html
      .split(/<br\s*\/?>|<\/?(?:p|li|h\d|div|span|strong)\b[^>]*>/i)
      .map((chunk) => text(load(chunk, null, false).text()))
      .filter(Boolean);
    const at = lines.findIndex((l) => /^ESITYKSET:?$/i.test(l));
    if (at < 0) {
      continue; // not a film post
    }
    const facts = lines.slice(0, at);
    const unmapped: string[] = [];
    const age = post.content.rendered.match(AGE_IMAGE)?.[1]?.toLowerCase();
    const rating = age ? own(RATINGS, age) : undefined;
    const duration = facts.map((l) => l.match(RUNTIME)).find(Boolean);
    const runtime = duration ? Number(duration[1] ?? 0) * 60 + Number(duration[2]) : 0;
    const factLine = facts.join(" ");
    const spoken = factLine.match(AUDIO)?.[1];
    const audio: Lang | undefined = spoken ? normalizeLang(spoken) : undefined;
    if (spoken && !audio) {
      unmapped.push(`audio:${spoken}`);
    }
    const subtitled = factLine.match(SUBTITLES)?.[1];
    const subtitleLang = subtitled ? normalizeLang(subtitled) : undefined;
    if (subtitled && !subtitleLang) {
      unmapped.push(`subtitles:${subtitled}`);
    }
    const subtitles: Subtitles = subtitleLang
      ? { kind: "languages", languages: [subtitleLang] }
      : { kind: "unknown" };

    const rawTitle = text(load(post.title.rendered, null, false).text());
    const { title: unprefixed, rule } = splitTitlePrefix(rawTitle, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const listingId = makeId(P, "film", String(post.id));

    for (const line of lines.slice(at + 1)) {
      if (line.startsWith(STRUCK)) {
        continue; // cancelled
      }
      if (!ROWISH.test(line)) {
        continue; // a note ("PERUTTU!", "VIIMEINEN NÄYTÖS") or the credits
      }
      const m = line.match(ROW);
      const date = m ? nearestDate(Number(m[2]), Number(m[3]), raw.from) : undefined;
      const weekday = date ? WEEKDAYS[Temporal.PlainDate.from(date).dayOfWeek - 1] : undefined;
      const start =
        m &&
        date &&
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
          sourceId: String(post.id),
          title: { fi: title },
          ...(runtime > 0 && { runtimeMinutes: runtime }),
          ...(rating && { rating }),
          genres: [],
          countries: [],
          kind: rule?.event ? "event" : "film",
        });
      }
      const spokenAudio = version.audio ?? audio;
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
        presentation: { projection: "digital", dimension: version.dimension ?? "2d", formats: [] },
        audio: spokenAudio ? [spokenAudio] : [],
        ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
        subtitles,
        tags: [...(rule?.tags ?? [])],
        series: rule?.series ? [rule.series] : [],
        availability: "unknown",
        // The film's post on the cinema's site, copied.
        ticketUrl: post.link.startsWith(`${site.base}/`) ? post.link : site.homepage,
        unmappedLabels: unmapped,
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
    provider: providerOf(site, "custom", "reserve"),
    fetchedAt: raw.fetchedAt,
    window,
    venues: [toVenue(P, venue, venue.slug)],
    auditoriums: [],
    listings: [...listings.values()],
    screenings: [...screenings.values()].toSorted(byStartThenId),
    warnings,
  };
};
