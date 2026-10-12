import { TZDate } from "@date-fns/tz";
import { formatISO, subDays } from "date-fns";
import {
  makeId,
  type Auditorium,
  type Availability,
  type FilmListing,
  type FinnishRating,
  type ProviderBatch,
  type Screening,
  type ScreeningTag,
  type Venue,
  type Warning,
} from "@pgtm/model";
import { dateWindow, FINNISH_TZ } from "../../lib/time.ts";
import { COMMON_TITLE_PREFIXES, splitTitlePrefix, splitVersion } from "../labels.ts";
import { codes, parseAudio, parseSubtitles, UNKNOWN_CODE } from "../language-codes.ts";
import { providerOf } from "../sites.ts";
import { JohkuEntry, ScheduleResponse, type JohkuRawSnapshot } from "./raw.ts";
import type { JohkuSite } from "./sites.ts";

const RATINGS: Record<string, FinnishRating> = {
  S: "S",
  "K-7": "K-7",
  "K-12": "K-12",
  "K-16": "K-16",
  "K-18": "K-18",
};

const num = (v: string | number | null | undefined): number | undefined => {
  const n = typeof v === "number" ? v : v === null || v === undefined || v === "" ? NaN : Number(v);
  return Number.isFinite(n) ? n : undefined;
};

const blank = (v: string | null | undefined) => !v || v.trim() === "" || v.trim() === "-";

/**
 * Not a public screening: hall hire, a closure notice ("Olemme vapaalla") or a private
 * booking. They have no price, no age limit and no language; every film has at least one.
 */
export const isPublicScreening = (e: Pick<JohkuEntry, "price" | "agelimit" | "maccsboxlanguage">) =>
  num(e.price) !== undefined || !blank(e.agelimit) || !blank(e.maccsboxlanguage);

/** Shown in the storefront's Finnish catalogue (the same rule the storefront applies). */
const inCatalogue = (e: JohkuEntry) =>
  [e.product.enable_catalog, e.product.enable_collection].some(
    (v) => v === 1 || v === "1" || String(v ?? "").includes("fi_FI"),
  );

/** Seats taken vs. capacity. Under a tenth left is "few-left". */
export const availabilityOf = (capacity?: number, taken?: number): Availability => {
  if (capacity === undefined || taken === undefined || capacity <= 0) return "unknown";
  const free = capacity - taken;
  if (free <= 0) return "sold-out";
  return free / capacity < 0.1 ? "few-left" : "available";
};

/** "2026-10-14 19:00" (Helsinki) -> ISO with offset, and the programme day. */
export const startOf = (local: string) => {
  const m = local.trim().match(/^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})$/);
  if (!m) return undefined;
  const [y, mo, d, h, mi] = m.slice(1).map(Number) as [number, number, number, number, number];
  const start = new TZDate(y, mo - 1, d, h, mi, 0, FINNISH_TZ);
  const business = h < 5 ? subDays(start, 1) : start;
  return {
    startsAt: formatISO(start),
    businessDate: formatISO(business, { representation: "date" }),
  };
};

/** Pure: schedules + site config -> normalized batch. Broken entries become warnings. */
export const parseJohku = (raw: JohkuRawSnapshot, site: JohkuSite): ProviderBatch => {
  const P = site.provider;
  const window = dateWindow(raw.from, raw.days);
  const warnings: Warning[] = [];
  const prefixRules = { ...COMMON_TITLE_PREFIXES, ...site.titlePrefixes };

  const venues: Venue[] = site.venues.map((v) => ({
    id: makeId(P, "venue", v.slug),
    provider: P,
    sourceId: v.resource,
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

  for (const [category, payload] of Object.entries(raw.schedules)) {
    const response = ScheduleResponse.safeParse(payload);
    if (!response.success) {
      warnings.push({
        code: "invalid-response",
        message: response.error.message,
        context: { category },
      });
      continue;
    }
    for (const item of response.data.data) {
      const parsed = JohkuEntry.safeParse(item);
      if (!parsed.success) {
        warnings.push({
          code: "invalid-entry",
          message: parsed.error.message,
          context: { category },
        });
        continue;
      }
      const e = parsed.data;
      // Coming soon (no time yet), hidden, outside the catalogue, or not a screening.
      if (e.upcoming === "1" || e.upcoming === 1 || e.hideinternet === "1" || e.hideinternet === 1)
        continue;
      if (!inCatalogue(e) || !isPublicScreening(e)) continue;

      const venue = site.venues.find((v) => v.resource === e.resource_name);
      if (!venue) {
        const hall = e.resource_name ?? "(no hall)";
        unclaimed.set(hall, (unclaimed.get(hall) ?? 0) + 1);
        continue;
      }
      const start = startOf(e.start_date);
      if (!start) {
        warnings.push({
          code: "invalid-start",
          message: `Unreadable start "${e.start_date}"`,
          context: { id: e.id },
        });
        continue;
      }
      if (start.businessDate < window.from || start.businessDate > window.to) continue;
      const id = makeId(P, "show", e.id);
      if (screenings.has(id)) continue; // a show can sit in two programme blocks

      const unmapped: string[] = [];
      const { title: unprefixed, rule: prefix } = splitTitlePrefix(e.text, prefixRules);
      const { title, version } = splitVersion(unprefixed);
      const audio = parseAudio(blank(e.maccsboxlanguage) ? undefined : e.maccsboxlanguage);
      unmapped.push(...audio.unknown.map((c) => `language:${c}`));
      const subtitles = parseSubtitles(
        blank(e.maccsboxsubtitles) ? undefined : e.maccsboxsubtitles,
      );
      if (
        subtitles.kind === "unknown" &&
        !blank(e.maccsboxsubtitles) &&
        !codes(e.maccsboxsubtitles).includes(UNKNOWN_CODE)
      ) {
        unmapped.push(`subtitles:${e.maccsboxsubtitles}`);
      }
      const rating = blank(e.agelimit) ? undefined : RATINGS[e.agelimit!.trim()];
      if (!blank(e.agelimit) && !rating) unmapped.push(`agelimit:${e.agelimit}`);
      const imdbId = e.imdb?.trim().match(/^tt\d+$/)?.[0];

      const listingId = makeId(P, "film", e.product.id);
      if (!listings.has(listingId)) {
        const original = e.originaltitle?.trim();
        const runtime = num(e.duration);
        listings.set(listingId, {
          id: listingId,
          provider: P,
          sourceId: e.product.id,
          title: { fi: title },
          ...(original &&
            original.toLowerCase() !== title.toLowerCase() && { originalTitle: original }),
          ...(imdbId && { imdbId }),
          ...(runtime && runtime > 0 && { runtimeMinutes: Math.round(runtime) }),
          ...(rating && { rating }),
          genres: [],
          countries: [],
          kind: prefix?.event ? "event" : "film",
        });
      }

      const venueId = makeId(P, "venue", venue.slug);
      const hall = e.resource_name!;
      const auditoriumId =
        hall !== venue.name
          ? makeId(
              P,
              "screen",
              `${venue.slug}-${hall
                .toLowerCase()
                .replace(/[^a-z0-9]+/g, "-")
                .replace(/^-|-$/g, "")}`,
            )
          : undefined;
      if (auditoriumId && !auditoriums.has(auditoriumId)) {
        auditoriums.set(auditoriumId, {
          id: auditoriumId,
          venueId,
          name: hall,
          ...(num(e.resource_capacity) && { seats: num(e.resource_capacity) }),
          features: [],
        });
      }

      const tags: ScreeningTag[] = [...(prefix?.tags ?? [])];
      const price = num(e.price);
      const url = e.storefronturl?.trim();
      screenings.set(id, {
        id,
        provider: P,
        sourceId: e.id,
        venueId,
        ...(auditoriumId && { auditoriumId }),
        listingId,
        startsAt: start.startsAt,
        businessDate: start.businessDate,
        presentation: { projection: "digital", dimension: version.dimension ?? "2d", formats: [] },
        audio: version.audio ? [version.audio] : audio.audio,
        ...(version.dubbed !== undefined && { dubbed: version.dubbed }),
        subtitles,
        tags: [...new Set(tags)],
        series: prefix?.series ? [prefix.series] : [],
        availability: availabilityOf(num(e.resource_capacity), num(e.resource_reservations)),
        ...(price !== undefined && {
          price: {
            amountCents: Math.round(price * 100),
            currency: "EUR" as const,
            ...((e.multipleprices === "1" || e.multipleprices === 1) && {
              note: "other ticket types available",
            }),
          },
        }),
        // Copied from the schedule, never constructed; it opens the film's booking page.
        ticketUrl: url?.startsWith("https://") ? url : site.homepage,
        unmappedLabels: unmapped,
        fetchedAt: raw.fetchedAt,
      });
    }
  }

  for (const [hall, shows] of unclaimed) {
    warnings.push({
      code: "unclaimed-hall",
      message: `Hall "${hall}" belongs to no venue (${shows} shows skipped); add it to johku/sites.ts`,
      context: { hall, shows },
    });
  }

  const shown = new Set([...screenings.values()].map((s) => s.listingId));
  return {
    provider: providerOf(site, "johku", "buy"),
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
