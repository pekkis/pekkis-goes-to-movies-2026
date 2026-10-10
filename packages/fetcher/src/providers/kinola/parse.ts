import { formatISO, parseISO, subHours } from "date-fns";
import { TZDate } from "@date-fns/tz";
import {
  makeId,
  type Availability,
  type Auditorium,
  type FilmListing,
  type FinnishRating,
  type Lang,
  type ProviderBatch,
  type Screening,
  type ScreeningTag,
  type Subtitles,
  type Venue,
  type Warning,
} from "@pgtm/model";
import { normalizeLang } from "../../lib/lang.ts";
import { dateWindow, FINNISH_TZ } from "../../lib/time.ts";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { providerOf } from "../sites.ts";
import { EventsPage, KinolaEvent, type KinolaRawSnapshot } from "./raw.ts";
import type { KinolaSite } from "./sites.ts";

const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  // Estonian "lubatud kõigile" (all ages); Kinola is Estonian.
  L: "S",
  "K-7": "K-7",
  "K-12": "K-12",
  "K-16": "K-16",
  "K-18": "K-18",
};

/** "englanti", "Dubattu englanniksi" -> languages; unknown names are returned too. */
export const parseLanguageList = (
  names: string[] | null | undefined,
): { langs: Lang[]; dubbed: boolean; unknown: string[] } => {
  const langs: Lang[] = [];
  const unknown: string[] = [];
  let dubbed = false;
  for (const raw of names ?? []) {
    const name = raw.trim();
    if (!name) continue;
    const dub = name.match(/^dubattu\s+(.+)$/i);
    if (dub) dubbed = true;
    const lang = normalizeLang(dub ? dub[1]! : name);
    if (lang) langs.push(lang);
    else unknown.push(name);
  }
  return { langs: [...new Set(langs)], dubbed, unknown };
};

/** ["suomi", "ruotsi "] -> languages; "Ei tekstitystä" (or "teksitystä") -> none. */
export const parseSubtitleList = (
  names: string[] | null | undefined,
): { subtitles: Subtitles; unknown: string[] } => {
  const list = (names ?? []).map((n) => n.trim()).filter(Boolean);
  if (list.length === 0) return { subtitles: { kind: "unknown" }, unknown: [] };
  if (list.some((n) => /^ei\s+te\S*tystä/i.test(n)))
    return { subtitles: { kind: "none" }, unknown: [] };
  const { langs, unknown } = parseLanguageList(list);
  return {
    subtitles:
      unknown.length || langs.length === 0
        ? { kind: "unknown" }
        : { kind: "languages", languages: langs },
    unknown,
  };
};

/** Free seats only (no capacity in the API): sold out, or available. */
export const availabilityOf = (e: Pick<KinolaEvent, "freeSeats" | "visibility">): Availability => {
  if (e.visibility === "coming_soon") return "not-bookable";
  if (e.freeSeats === null || e.freeSeats === undefined) return "unknown";
  return e.freeSeats === 0 ? "sold-out" : "available";
};

/** Conservative note reading: only notes that start with the label. */
export const noteTags = (note: string | null | undefined): ScreeningTag[] => {
  const text = note?.trim() ?? "";
  if (/^ennakko/i.test(text)) return ["preview"];
  if (/^(ensi-ilta|premiere)\b/i.test(text)) return ["premiere"];
  return [];
};

const euros = (n: number) => `${n.toFixed(2).replace(".", ",").replace(",00", "")} €`;

/** Shows before 05:00 belong to the previous day's programme. */
const businessDateOf = (localTime: string) => {
  const local = new TZDate(parseISO(localTime), FINNISH_TZ);
  return formatISO(local.getHours() < 5 ? subHours(local, 5) : local, { representation: "date" });
};

/** Pure: API pages + site config -> normalized batch. Broken events become warnings. */
export const parseKinola = (raw: KinolaRawSnapshot, site: KinolaSite): ProviderBatch => {
  const P = site.provider;
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };

  const venues: Venue[] = site.venues.map((v) => ({
    id: makeId(P, "venue", v.slug),
    provider: P,
    sourceId: v.kinolaName,
    name: v.name,
    city: v.city,
    ...(v.shortName && { shortName: v.shortName }),
    ...(v.address && { address: v.address }),
    ...(v.postalCode && { postalCode: v.postalCode }),
    ...(v.geo && { geo: v.geo }),
  }));
  const auditoriums = new Map<string, Auditorium>();
  const listings = new Map<string, FilmListing>();
  const screenings = new Map<string, Screening>();
  const unclaimed = new Map<string, number>();

  const events = raw.pages.flatMap((page, i) => {
    const parsed = EventsPage.safeParse(page);
    if (!parsed.success) {
      warnings.push({
        code: "invalid-response",
        message: parsed.error.message,
        context: { page: i },
      });
      return [];
    }
    return parsed.data.data;
  });

  for (const item of events) {
    const parsed = KinolaEvent.safeParse(item);
    if (!parsed.success) {
      warnings.push({ code: "invalid-event", message: parsed.error.message });
      continue;
    }
    const e = parsed.data;
    const venue = site.venues.find((v) => v.kinolaName === e.venue.name);
    if (!venue) {
      unclaimed.set(e.venue.name, (unclaimed.get(e.venue.name) ?? 0) + 1);
      continue;
    }
    const businessDate = businessDateOf(e.local_time);
    if (businessDate < window.from || businessDate > window.to) continue;

    const p = e.production;
    const unmapped: string[] = [];
    const { title: unprefixed, rule: prefix } = splitTitlePrefix(p.name, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const audio = parseLanguageList(p.languages);
    unmapped.push(...audio.unknown.map((n) => `language:${n}`));
    const subs = parseSubtitleList(p.subtitles);
    unmapped.push(...subs.unknown.map((n) => `subtitles:${n}`));
    const rating = p.rating ? RATINGS[p.rating.trim()] : undefined;
    if (p.rating && !rating && p.rating !== "Not rated") unmapped.push(`rating:${p.rating}`);
    const imdbId = p.imdb_id?.trim().match(/^tt\d+$/)?.[0];
    const bare = !p.languages?.some((l) => l.trim()) && !p.distributor?.trim() && !imdbId;
    const isEvent = (prefix?.event ?? false) || (site.bareProductionsAreEvents === true && bare);

    const listingId = makeId(P, "film", p.id);
    if (!listings.has(listingId)) {
      const original = p.originalName?.trim();
      listings.set(listingId, {
        id: listingId,
        provider: P,
        sourceId: p.id,
        title: { fi: title },
        ...(original && original !== title && { originalTitle: original }),
        ...(imdbId && { imdbId }),
        ...(p.year && { year: p.year }),
        ...(p.duration && p.duration > 0 && { runtimeMinutes: Math.round(p.duration) }),
        ...(rating && { rating }),
        genres: [],
        countries: [],
        kind: isEvent ? "event" : "film",
      });
    }

    const tags: ScreeningTag[] = [...(prefix?.tags ?? []), ...noteTags(e.note)];
    const series: string[] = prefix?.series ? [prefix.series] : [];
    let licensed = false;
    const program = e.program?.name.trim();
    if (program) {
      const rule = site.programs?.[program];
      if (!rule) series.push(program);
      else {
        tags.push(...(rule.tags ?? []));
        if (rule.series) series.push(rule.series);
        if (rule.licensed) licensed = true;
      }
    }

    const venueId = makeId(P, "venue", venue.slug);
    const room = e.room?.name.trim();
    const auditoriumId =
      room && room !== venue.kinolaName
        ? makeId(P, "screen", `${venue.slug}-${room.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`)
        : undefined;
    if (auditoriumId && !auditoriums.has(auditoriumId)) {
      auditoriums.set(auditoriumId, { id: auditoriumId, venueId, name: room!, features: [] });
    }

    const price = e.price_range?.currency === "EUR" ? e.price_range : undefined;
    const id = makeId(P, "show", e.id);
    screenings.set(id, {
      id,
      provider: P,
      sourceId: e.id,
      venueId,
      ...(auditoriumId && { auditoriumId }),
      listingId,
      startsAt: e.local_time,
      businessDate,
      presentation: { projection: "digital", dimension: version.dimension ?? "2d", formats: [] },
      audio: version.audio ? [version.audio] : audio.langs,
      ...((version.dubbed !== undefined || audio.dubbed) && {
        dubbed: version.dubbed ?? audio.dubbed,
      }),
      subtitles: subs.subtitles,
      tags: [...new Set(tags)],
      series: [...new Set(series)],
      ...(licensed && { licensed: true }),
      availability: availabilityOf(e),
      ...(price && {
        price: {
          amountCents: Math.round(price.min * 100),
          currency: "EUR" as const,
          ...(price.max > price.min && { note: `${euros(price.min)}–${euros(price.max)}` }),
        },
      }),
      // Copied from the API, never constructed; without one, the programme page.
      ticketUrl: e.checkout_url?.startsWith("https://")
        ? e.checkout_url
        : `${site.homepage}${site.programmePath}`,
      unmappedLabels: unmapped,
      fetchedAt: raw.fetchedAt,
    });
  }

  for (const [name, shows] of unclaimed) {
    warnings.push({
      code: "unclaimed-venue",
      message: `Venue "${name}" belongs to no configured venue (${shows} shows skipped); add it to kinola/sites.ts`,
      context: { venue: name, shows },
    });
  }

  const shown = new Set([...screenings.values()].map((s) => s.listingId));
  return {
    provider: providerOf(site, "kinola", "buy"),
    fetchedAt: raw.fetchedAt,
    window,
    venues,
    auditoriums: [...auditoriums.values()],
    listings: [...listings.values()].filter((l) => shown.has(l.id)),
    screenings: [...screenings.values()].sort(
      (a, b) => Date.parse(a.startsAt) - Date.parse(b.startsAt) || a.id.localeCompare(b.id),
    ),
    warnings,
  };
};
