import { TZDate } from "@date-fns/tz";
import { formatISO, subDays } from "date-fns";
import {
  makeId,
  type Auditorium,
  type Availability,
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
import { load, type CheerioAPI } from "cheerio";
import { normalizeLang } from "../../lib/lang.ts";
import { dateWindow, FINNISH_TZ } from "../../lib/time.ts";
import {
  COMMON_TITLE_PREFIXES,
  splitTitlePrefix,
  splitVersion,
  type LabelRule,
} from "../labels.ts";
import { providerOf } from "../sites.ts";
import { ExtractedFilm, ExtractedShow, type EtikettiRawSnapshot } from "./raw.ts";
import { baseOf, DEFAULT_TAGS, type EtikettiSite, type EtikettiVenue } from "./sites.ts";

// --- Listing ------------------------------------------------------------------------

const FILM_PATH = /^\/elokuvat\/(\d+)\/[a-z0-9-]+$/;

/** Film page paths linked from the programme listing, deduplicated by film id. */
export const filmLinks = (listingHtml: string): string[] => {
  const $ = load(listingHtml);
  const byId = new Map<string, string>();
  $("a[href]").each((_, a) => {
    const href = $(a).attr("href") ?? "";
    const id = href.match(FILM_PATH)?.[1];
    if (id && !byId.has(id)) byId.set(id, href);
  });
  return [...byId.values()];
};

/** A listing that says there is nothing on, as opposed to a page we cannot read. */
export const isEmptyProgramme = (listingHtml: string): boolean =>
  /ohjelmistoa\s+(?:ei\s+)?(?:ole\s+)?saatavilla|ei\s+ohjelmistoa/i.test(load(listingHtml).text());

// --- Film page extraction (pure HTML -> ExtractedFilm / ExtractedShow) ----------------

const text = (s: string) => s.replace(/\s+/g, " ").trim();

/** Text of a fragment of HTML, entities decoded. */
const fragmentText = (html: string) => text(load(`<div>${html}</div>`)("div").text());

/** The bits of a parsed DOM node we walk (cheerio does not re-export domhandler's types). */
type DomNode = { type: string; name?: string; data?: string; nextSibling: DomNode | null };

/** "<span class=label>Kesto:</span> 2 h 9 min<br>" -> the text up to the next br/label. */
const labelValue = ($: CheerioAPI, label: DomNode): string => {
  let value = "";
  for (let node = label.nextSibling; node; node = node.nextSibling) {
    if (node.type === "tag") {
      if (node.name === "br" || $(node as never).hasClass("label")) break;
      value += $(node as never).text();
    } else if (node.type === "text") {
      value += node.data ?? "";
    }
  }
  return text(value);
};

const DETAILS = /Lippu|Vapaat paikat|Paikkoja vapaana/i;

export const extractFilmPage = (
  html: string,
  path: string,
): { film: unknown; shows: unknown[] } => {
  const $ = load(html);
  const facts: Record<string, string> = {};
  $("span.label").each((_, el) => {
    const key = text($(el).text()).replace(/:$/, "");
    const value = labelValue($, el as unknown as DomNode);
    if (key && value && !(key in facts)) facts[key] = value;
  });
  const genres = $("span.movie-genre")
    .map((_, el) => text($(el).text()))
    .get()
    .filter(Boolean);

  const film = {
    sourceId: path.match(FILM_PATH)?.[1] ?? "",
    title: text($("h1").first().text()),
    age: $("img[src*='ikarajat/']")
      .attr("src")
      ?.match(/fi-(s|\d+)\.svg/i)?.[1]
      ?.toUpperCase(),
    facts,
    genres: genres.length ? genres : (facts["Genre"]?.split(/\s*,\s*/).filter(Boolean) ?? []),
  };

  const shows = $("div.item")
    .filter((_, el) => /\bdate-\d/.test($(el).attr("class") ?? ""))
    .map((_, el) => {
      const row = $(el);
      const date = (row.attr("class") ?? "").match(/\bdate-(\d{1,2}\.\d{1,2}\.\d{4})\b/)?.[1];
      const timeMatch =
        row.text().match(/klo\s*(\d{1,2})[.:](\d{2})/) ??
        row
          .find(".time")
          .text()
          .match(/(\d{1,2})[.:](\d{2})/);
      const time = timeMatch && `${timeMatch[1]!.padStart(2, "0")}:${timeMatch[2]}`;
      // The details paragraph: "PLACE<br>Lippu 15,00€<br>Vapaat paikat 27/35".
      const details = row
        .find("p")
        .filter((_, p) => DETAILS.test($(p).text()))
        .first();
      const firstLine = details.length
        ? fragmentText(($(details).html() ?? "").split(/<br\s*\/?>/i)[0] ?? "")
        : "";
      const place = firstLine && !DETAILS.test(firstLine) ? firstLine : undefined;
      const rowText = text(row.text());
      const price = (row.find(".show-price").text() || rowText).match(
        /(\d+(?:[.,]\d{1,2})?)\s*€/,
      )?.[1];
      const seats = rowText.match(/(?:Vapaat paikat|Paikkoja vapaana):?\s*(\d+)\s*\/\s*(\d+)/i);
      return {
        date,
        time,
        ...(place && { place }),
        ...(row.find("a[href^='/salikartta']").attr("href") && {
          ticketPath: row.find("a[href^='/salikartta']").attr("href"),
        }),
        ...(price && { priceText: price }),
        ...(seats && { seatsFree: Number(seats[1]), seatsTotal: Number(seats[2]) }),
        tags: row
          .find(".tag")
          .map((_, t) => text($(t).text()))
          .get()
          .filter(Boolean),
        licensedIcon: row.find("img[src*='anniskelu']").length > 0,
      };
    })
    .get();

  return { film, shows };
};

// --- Mapping to the model ---------------------------------------------------------------

const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  "7": "K-7",
  "12": "K-12",
  "16": "K-16",
  "18": "K-18",
};

const norm = (s: string) => s.normalize("NFC").toLowerCase().replace(/\s+/g, " ").trim();

const slugify = (s: string) =>
  norm(s)
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");

/** "2 h 9 min" -> 129, "95 min" -> 95. */
export const parseDuration = (raw: string | undefined): number | undefined => {
  const m = raw?.match(/^(?:(\d+)\s*h)?\s*(?:(\d+)\s*min)?$/i);
  if (!m || (!m[1] && !m[2])) return undefined;
  const minutes = Number(m[1] ?? 0) * 60 + Number(m[2] ?? 0);
  return minutes > 0 ? minutes : undefined;
};

/** "Suomi ja ruotsi" -> ["fi", "sv"]; undefined when any name is unknown. */
export const parseLanguages = (raw: string): Lang[] | undefined => {
  const langs = raw
    .split(/\s*(?:,|\/|&|\bja\b|\boch\b)\s*/i)
    .filter(Boolean)
    .map((name) => normalizeLang(name));
  return langs.length && langs.every(Boolean) ? [...new Set(langs as Lang[])] : undefined;
};

/** "Kieli": the audio. "Alkuperäinen" (original) says nothing, so it gives none. */
export const parseAudio = (raw: string | undefined): { audio: Lang[]; unknown?: string } => {
  if (!raw || /^alkuperäinen/i.test(raw)) return { audio: [] };
  const langs = parseLanguages(raw);
  return langs ? { audio: langs } : { audio: [], unknown: raw };
};

/** "Tekstitys": "Suomi ja ruotsi", "Ei tekstitystä". */
export const parseSubtitles = (
  raw: string | undefined,
  noSubtitlesUnreliable: boolean,
): { subtitles: Subtitles; unknown?: string } => {
  if (!raw) return { subtitles: { kind: "unknown" } };
  if (/^ei\b/i.test(raw))
    return { subtitles: noSubtitlesUnreliable ? { kind: "unknown" } : { kind: "none" } };
  const langs = parseLanguages(raw);
  return langs
    ? { subtitles: { kind: "languages", languages: langs } }
    : { subtitles: { kind: "unknown" }, unknown: raw };
};

/** Seats left -> availability. Under a tenth left is "few-left". */
export const availabilityOf = (free?: number, total?: number): Availability => {
  if (free === undefined || total === undefined) return "unknown";
  if (free === 0) return "sold-out";
  return free / total < 0.1 ? "few-left" : "available";
};

/**
 * Which venue a place line belongs to, and the room. The venue is the part equal to a
 * venue's `place`; the room is the part after it, unless it repeats the venue
 * ("IISALMI | KUVALIPAS | KUVALIPAS"). Rows without a place line go to the venue without
 * a `place`, if the site has exactly one.
 */
export const resolvePlace = (
  venues: EtikettiVenue[],
  place: string | undefined,
): { venue: EtikettiVenue; room?: string } | undefined => {
  if (!place) {
    const placeless = venues.filter((v) => !v.place);
    return placeless.length === 1 ? { venue: placeless[0]! } : undefined;
  }
  const parts = place.split("|").map(text).filter(Boolean);
  for (const venue of venues) {
    if (!venue.place) continue;
    const i = parts.findIndex((p) => norm(p) === norm(venue.place!));
    if (i === -1) continue;
    const room = parts[i + 1];
    return room && norm(room) !== norm(venue.place) ? { venue, room } : { venue };
  }
  return undefined;
};

/** "SALI 3" -> "Sali 3", "VIP-SALI" -> "VIP-sali"; mixed-case names stay as printed. */
export const roomName = (raw: string): string => {
  if (raw !== raw.toUpperCase()) return raw;
  const lower = raw.toLowerCase().replace(/\b(vip|imax|3d|4dx)\b/g, (m) => m.toUpperCase());
  return lower.charAt(0).toUpperCase() + lower.slice(1);
};

/** "15,00" -> 1500 cents. */
const cents = (raw: string | undefined) => {
  const n = raw ? Number(raw.replace(",", ".")) : NaN;
  return Number.isFinite(n) && n > 0 ? Math.round(n * 100) : undefined;
};

/** Calendar date + time in Helsinki; shows before 05:00 belong to the previous day's programme. */
const startOf = (date: string, time: string) => {
  const [d, m, y] = date.split(".").map(Number) as [number, number, number];
  const [hh, mm] = time.split(":").map(Number) as [number, number];
  const start = new TZDate(y, m - 1, d, hh, mm, 0, FINNISH_TZ);
  const business = hh < 5 ? subDays(start, 1) : start;
  return {
    startsAt: formatISO(start),
    businessDate: formatISO(business, { representation: "date" }),
  };
};

/** Pure: raw snapshot + site config -> normalized batch. Broken pages and rows become warnings. */
export const parseEtiketti = (raw: EtikettiRawSnapshot, site: EtikettiSite): ProviderBatch => {
  const P = site.provider;
  const base = baseOf(site);
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const tagRules = { ...DEFAULT_TAGS, ...site.tags };
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };

  const venues: Venue[] = site.venues.map((v) => ({
    id: makeId(P, "venue", v.slug),
    provider: P,
    sourceId: v.slug,
    name: v.name,
    city: v.city,
    ...(v.shortName && { shortName: v.shortName }),
    ...(v.address && { address: v.address }),
    ...(v.postalCode && { postalCode: v.postalCode }),
    ...(v.geo && { geo: v.geo }),
  }));
  const auditoriums = new Map<string, Auditorium>();
  const listings: FilmListing[] = [];
  const screenings = new Map<string, Screening>();
  const unclaimed = new Map<string, number>();

  for (const [path, html] of Object.entries(raw.films)) {
    const extracted = extractFilmPage(html, path);
    const film = ExtractedFilm.safeParse(extracted.film);
    if (!film.success) {
      warnings.push({ code: "invalid-film", message: film.error.message, context: { path } });
      continue;
    }
    const f = film.data;
    const unmapped: string[] = [];

    // Title: "Ennakkonäytös: Pikkuli (DUB)" -> "Pikkuli", preview tag, Finnish dub.
    const { title: unprefixed, rule: prefix } = splitTitlePrefix(f.title, prefixRules);
    const { title, version } = splitVersion(unprefixed);
    const facts = f.facts;
    const languageFact = parseAudio(facts["Kieli"]);
    if (languageFact.unknown) unmapped.push(`Kieli:${languageFact.unknown}`);
    const subs = parseSubtitles(facts["Tekstitys"], site.noSubtitlesUnreliable ?? false);
    if (subs.unknown) unmapped.push(`Tekstitys:${subs.unknown}`);
    const audio = version.audio ? [version.audio] : languageFact.audio;
    const year = facts["Valmistumisvuosi"]?.match(/^\d{4}$/)?.[0];
    const rating = f.age ? RATINGS[f.age] : undefined;
    if (f.age && !rating) unmapped.push(`age:${f.age}`);

    const listingId = makeId(P, "film", f.sourceId);
    let isEvent = prefix?.event ?? false;
    let shown = 0;

    for (const item of extracted.shows) {
      const parsed = ExtractedShow.safeParse(item);
      if (!parsed.success) {
        warnings.push({ code: "invalid-show", message: parsed.error.message, context: { path } });
        continue;
      }
      const s = parsed.data;
      const where = resolvePlace(site.venues, s.place);
      if (!where) {
        const key = s.place ?? "(no place line)";
        unclaimed.set(key, (unclaimed.get(key) ?? 0) + 1);
        continue;
      }
      const { startsAt, businessDate } = startOf(s.date, s.time);
      if (businessDate < window.from || businessDate > window.to) continue;

      const tags: ScreeningTag[] = [...(prefix?.tags ?? [])];
      const series: string[] = prefix?.series ? [prefix.series] : [];
      let licensed = s.licensedIcon;
      for (const tag of s.tags) {
        const rule: LabelRule | undefined = tagRules[tag];
        if (!rule) {
          series.push(tag);
          continue;
        }
        tags.push(...(rule.tags ?? []));
        if (rule.series) series.push(rule.series);
        if (rule.licensed) licensed = true;
        if (rule.event) isEvent = true;
      }

      const venueId = makeId(P, "venue", where.venue.slug);
      const auditoriumId = where.room
        ? makeId(P, "screen", `${where.venue.slug}-${slugify(where.room)}`)
        : undefined;
      if (auditoriumId && !auditoriums.has(auditoriumId)) {
        auditoriums.set(auditoriumId, {
          id: auditoriumId,
          venueId,
          name: roomName(where.room!),
          features: [],
        });
      }

      const showId =
        s.ticketPath?.match(/id=(\d+)/)?.[1] ??
        `${f.sourceId}-${s.date}-${s.time}-${where.venue.slug}`;
      const id = makeId(P, "show", showId);
      if (screenings.has(id)) continue; // Niagara prints each row twice
      const price = cents(s.priceText);
      screenings.set(id, {
        id,
        provider: P,
        sourceId: showId,
        venueId,
        ...(auditoriumId && { auditoriumId }),
        listingId,
        startsAt,
        businessDate,
        presentation: { projection: "digital", dimension: version.dimension ?? "2d", formats: [] },
        audio,
        ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
        subtitles: subs.subtitles,
        ...(rating && { ageLimit: rating }),
        tags: [...new Set(tags)],
        series: [...new Set(series)],
        ...(licensed && { licensed: true }),
        availability: availabilityOf(s.seatsFree, s.seatsTotal),
        ...(price && { price: { amountCents: price, currency: "EUR" as const } }),
        // Copied from the page, never constructed or requested.
        ticketUrl: s.ticketPath ? `${base}${s.ticketPath}` : `${base}${path}`,
        unmappedLabels: unmapped,
        fetchedAt: raw.fetchedAt,
      });
      shown++;
    }

    if (shown > 0) {
      listings.push({
        id: listingId,
        provider: P,
        sourceId: f.sourceId,
        title: { fi: title },
        ...(year && { year: Number(year) }),
        ...(parseDuration(facts["Kesto"]) && { runtimeMinutes: parseDuration(facts["Kesto"]) }),
        ...(rating && { rating }),
        genres: f.genres,
        countries: [],
        kind: isEvent ? "event" : "film",
      });
    }
  }

  for (const [place, shows] of unclaimed) {
    warnings.push({
      code: "unclaimed-place",
      message: `Place "${place}" belongs to no venue (${shows} shows skipped); add it to etiketti/sites.ts`,
      context: { place, shows },
    });
  }

  return {
    provider: providerOf(site, "etiketti", "buy"),
    fetchedAt: raw.fetchedAt,
    window,
    venues,
    auditoriums: [...auditoriums.values()],
    listings,
    screenings: [...screenings.values()].sort(
      (a, b) => Date.parse(a.startsAt) - Date.parse(b.startsAt) || a.id.localeCompare(b.id),
    ),
    warnings,
  };
};
