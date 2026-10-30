import {
  makeId,
  type FilmListing,
  type FinnishRating,
  type ProviderBatch,
  type RawLabel,
  type Screening,
  type Subtitles,
  type Warning,
} from "@pgtm/model";
import { dateWindow, helsinkiShowTime, nearestDate } from "@pgtm/model/time";
import { load, type CheerioAPI } from "cheerio";
import {
  COMMON_TITLE_PREFIXES,
  findLabel,
  LABELS,
  labelEffects,
  ruleFor,
  splitTitlePrefix,
  type LabelEffects,
} from "../labels.ts";
import { byStartThenId, plainText, slugify, toCents } from "../parsing.ts";
import { providerOf, toVenue } from "../sites.ts";
import type { OulunElokuvakeskusRawSnapshot } from "./fetch.ts";
import type { OulunElokuvakeskusSite } from "./sites.ts";

const WEEKDAYS = ["ma", "ti", "ke", "to", "pe", "la", "su"];
/** "Pe 30.10." */
const DATE = /^(ma|ti|ke|to|pe|la|su)\s+(\d{1,2})\.(\d{1,2})\.?$/i;
/** "18.00" */
const TIME = /^(\d{1,2})[.:](\d{2})$/;
/** "Saksa—Ranska—Turkki 2026" */
const ORIGIN = /^(\D+?)\s+(\d{4})$/;
/** "Sallittu yli 12-vuotiaille", "Sallittu kaikenikäisille": the age limit's image. */
const AGE = /Sallittu yli (\d{1,2})-vuotiaille/i;
const ALL_AGES = /Sallittu kaikenikäisille/i;
/** A closed day ("SULJETTU"): a row with nothing to show. */
const CLOSED = /^suljettu$/i;

/** What a film's first (premiere) table says about it. */
type FilmFacts = {
  title: string;
  /** A programme of several films ("VISIONI SARDE 2026"), not one film. */
  programme: boolean;
  originalTitle?: string;
  year?: number;
  countries: string[];
  runtime?: number;
  rating?: FinnishRating;
  imdbId?: string;
  price?: number;
  effects: LabelEffects;
  labels: RawLabel[];
  unmapped: string[];
};

/** A `table.premiere`'s content cell, loaded on its own -> the film's facts. */
const premiereFacts = ($: CheerioAPI, prefixRules: typeof LABELS): FilmFacts => {
  const lines = $("p")
    .toArray()
    .map((p) => plainText($(p).text()))
    .filter(Boolean);
  const bold = plainText($("p > strong").first().text());
  const titleAt = Math.max(0, bold ? lines.findIndex((l) => l.includes(bold)) : 0);
  const title = lines[titleAt] ?? "";
  const unmapped: string[] = [];
  const rules = [];
  const labels: RawLabel[] = [];
  // Above the title: the director ("Ken Russell:") and any series heading.
  for (const line of lines.slice(0, Math.max(titleAt, 0))) {
    if (line.endsWith(":")) {
      continue;
    }
    const rule = ruleFor(prefixRules, line);
    if (rule) {
      rules.push(rule);
      labels.push({ source: "heading", text: line });
    } else {
      unmapped.push(`heading:${line}`);
    }
  }
  // Several "Director: TITLE" lines under the title: a programme of short films.
  const credits = lines.slice(titleAt + 1).filter((l) => /^[^:]+:\s+\S/.test(l)).length;
  const facts: FilmFacts = {
    title,
    programme: !bold || credits >= 2,
    countries: [],
    effects: labelEffects([]),
    labels,
    unmapped,
  };
  for (const line of lines.slice(titleAt + 1)) {
    const original = line.match(/^\((.+)\)$/);
    const origin = line.match(ORIGIN);
    if (original && !facts.originalTitle) {
      facts.originalTitle = original[1]!.trim();
    } else if (origin && !facts.year) {
      facts.year = Number(origin[2]);
      facts.countries = origin[1]!.split(/\s*[—–,]\s*/).filter(Boolean);
    } else if (/\bmin\b|\bLiput\b/i.test(line) && facts.runtime === undefined) {
      // "115 min • Ei tekstitystä • Liput 11 e"
      for (const part of line.split("•").map((s) => s.trim())) {
        const minutes = part.match(/^(\d{1,3})\s*min$/i);
        const price = part.match(/^Liput\s+(\d{1,3}(?:[.,]\d{1,2})?)\s*e$/i);
        if (minutes) {
          facts.runtime = Number(minutes[1]);
          continue;
        }
        const cents = price ? toCents(price[1], { zeroIsFree: false }) : undefined;
        if (cents !== undefined) {
          facts.price = cents;
          continue;
        }
        const rule = findLabel(part, LABELS);
        if (rule) {
          rules.push(rule);
          labels.push({ source: "facts", text: part });
        } else {
          unmapped.push(`note:${part}`);
        }
      }
    }
  }
  facts.effects = labelEffects(rules);
  const ages = $("img")
    .toArray()
    .map((img) => $(img).attr("title") ?? "");
  const age = ages.map((t) => t.match(AGE)?.[1]).find(Boolean);
  if (age) {
    facts.rating = `K-${age}` as FinnishRating;
  } else if (ages.some((t) => ALL_AGES.test(t))) {
    facts.rating = "S";
  }
  const imdb = $("a[href*='imdb.com/title/']").attr("href")?.match(/tt\d+/)?.[0];
  if (imdb) {
    facts.imdbId = imdb;
  }
  return facts;
};

const subtitlesOf = (effects: LabelEffects): Subtitles =>
  effects.subtitles === "none"
    ? { kind: "none" }
    : effects.subtitles
      ? { kind: "languages", languages: [effects.subtitles] }
      : { kind: "unknown" };

/** Pure: the programme page + site config -> normalized batch. */
export const parseOulunElokuvakeskus = (
  raw: OulunElokuvakeskusRawSnapshot,
  site: OulunElokuvakeskusSite,
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
  // Ticketmaster's venue page, as the programme links it; else the programme itself.
  const ticketUrl = $("a[href*='ticketmaster.fi']").first().attr("href") ?? site.programme;
  const tables = $("table.premiere, table.regular").toArray();
  if (tables.length === 0) {
    warnings.push({ code: "invalid-response", message: "No programme tables on the page" });
  }
  // Films by title, from their premiere tables, for the regular rows that follow.
  const films = new Map<string, FilmFacts>();
  let date: { year: number; month: number; day: number } | undefined;
  let unreadable = 0;
  for (const table of tables) {
    const kind = $(table).hasClass("premiere") ? "premiere" : "regular";
    const cell = (name: string) => $(table).find(`td.${kind}-${name}`).first();
    const dateText = plainText(cell("date").text());
    const timeText = plainText(cell("time").text());
    const content = cell("content");
    if (dateText) {
      const d = dateText.match(DATE);
      const iso = d ? nearestDate(Number(d[2]), Number(d[3]), raw.from) : undefined;
      // The weekday is the only check on the year we infer.
      const fits =
        iso && WEEKDAYS[Temporal.PlainDate.from(iso).dayOfWeek - 1] === d![1]!.toLowerCase();
      date =
        iso && fits
          ? { year: Number(iso.slice(0, 4)), month: Number(d![3]), day: Number(d![2]) }
          : undefined;
      if (!date) {
        unreadable += 1;
        continue;
      }
    }
    const firstLine = plainText(content.find("p").first().text());
    if (!timeText) {
      // A closed day, or a block that only links elsewhere (a festival's own programme).
      if (firstLine && !CLOSED.test(firstLine) && content.find("strong").length > 0) {
        unreadable += 1;
      }
      continue;
    }
    const time = timeText.match(TIME);
    const start =
      time && date && helsinkiShowTime({ ...date, hour: Number(time[1]), minute: Number(time[2]) });
    if (!start) {
      unreadable += 1;
      continue;
    }

    let facts: FilmFacts | undefined;
    let rule;
    let label: string | undefined;
    if (kind === "premiere") {
      facts = premiereFacts(load(content.html() ?? "", null, false), prefixRules);
      films.set(slugify(facts.title), facts);
    } else {
      // "MATINEANÄYTÖS: BERLIININ SANKARI • Liput eläkeläisille, … 9 e": the title first.
      const split = splitTitlePrefix(firstLine.split("•")[0]!.trim(), prefixRules);
      rule = split.rule;
      label = split.label;
      facts = films.get(slugify(split.title)) ?? {
        title: split.title,
        programme: false,
        countries: [],
        effects: labelEffects([]),
        labels: [],
        unmapped: [],
      };
    }
    if (!facts.title) {
      unreadable += 1;
      continue;
    }
    if (start.businessDate < window.from || start.businessDate > window.to) {
      continue;
    }
    const effects = labelEffects([rule]);
    const filmKey = slugify(facts.title);
    const listingId = makeId(P, "film", filmKey);
    if (!listings.has(listingId)) {
      listings.set(listingId, {
        id: listingId,
        provider: P,
        sourceId: filmKey,
        title: { fi: facts.title },
        ...(facts.originalTitle && { originalTitle: facts.originalTitle }),
        ...(facts.imdbId && { imdbId: facts.imdbId }),
        ...(facts.year && { year: facts.year }),
        ...(facts.runtime && { runtimeMinutes: facts.runtime }),
        ...(facts.rating && { rating: facts.rating }),
        genres: [],
        countries: facts.countries,
        kind: facts.programme || facts.effects.event ? "event" : "film",
      });
    }
    const audio = facts.effects.audio;
    const labels: RawLabel[] = [
      ...facts.labels,
      ...(label ? [{ source: "title.prefix", text: label }] : []),
    ];
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
      presentation: { projection: "digital", dimension: "2d", formats: [] },
      audio: audio ? [audio] : [],
      ...(facts.effects.dubbed !== undefined && { dubbed: facts.effects.dubbed }),
      subtitles: subtitlesOf(facts.effects),
      tags: [...new Set([...facts.effects.tags, ...effects.tags])],
      series: [...new Set([...facts.effects.series, ...effects.series])],
      availability: "unknown",
      ...(facts.price !== undefined && {
        price: { amountCents: facts.price, currency: "EUR" as const },
      }),
      ticketUrl,
      unmappedLabels: facts.unmapped,
      ...(labels.length > 0 && { labels }),
      fetchedAt: raw.fetchedAt,
    });
  }
  if (unreadable > 0) {
    warnings.push({
      code: "invalid-row",
      message: `${unreadable} programme rows not understood, or with a weekday that fits no date`,
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
