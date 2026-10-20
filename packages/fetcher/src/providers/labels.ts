import {
  Availability,
  FinnishRating,
  Lang,
  Projection,
  ScreeningTag,
  type ProviderBatch,
} from "@pgtm/model";
import { z } from "zod";
import { own } from "../lib/records.ts";
import { findSeries } from "../series/registry.ts";
import { labelKey } from "./label-key.ts";

/**
 * What a cinema's free-text label (a show type, a tag, a note, a title prefix) means.
 * The shared table is LABELS below; sites override or extend it in their sites.ts.
 * - `{}`: ignore (a label that only means something inside the cinema)
 * - `tags`: screening tags; `series`: a series or festival name (resolved against
 *   config/series.json by the pull); `event: true`: the listing is event cinema
 * - the rest set one fact each: bar service, the age limit that comes with it,
 *   availability, the spoken language, subtitles ("none" or a language), projection.
 * A label with no rule is not guessed at: it goes to `unmappedLabels` (docs/classification.md).
 */
export const LabelRule = z.object({
  tags: z.array(ScreeningTag).optional(),
  series: z.string().optional(),
  event: z.boolean().optional(),
  licensed: z.boolean().optional(),
  ageLimit: FinnishRating.optional(),
  availability: Availability.optional(),
  audio: Lang.optional(),
  dubbed: z.boolean().optional(),
  subtitles: z.union([z.literal("none"), Lang]).optional(),
  projection: Projection.optional(),
});
export type LabelRule = z.infer<typeof LabelRule>;

/**
 * Labels Finnish cinemas print, one meaning each wherever they appear: as a title prefix
 * ("Ennakkonäytös: Pikkuli"), an eTiketti tag, a Nexxo show type, a Kinola note.
 * Matched without regard to case, punctuation or spacing (labelKey).
 */
export const LABELS: Record<string, LabelRule> = {
  // Occasion
  "Ennakkoensi-ilta": { tags: ["preview"] },
  Ennakkonäytös: { tags: ["preview"] },
  Ennakkonäytökset: { tags: ["preview"] },
  Ennakko: { tags: ["preview"] },
  "Ensi-ilta": { tags: ["premiere"] },
  "Suomen ensi-ilta": { tags: ["premiere"] },
  "Viimeinen näytös": { tags: ["last-screening"] },
  "Viimeiset näytökset": { tags: ["last-screening"] },
  // Audience
  Vauvakino: { tags: ["baby"] },
  Perhekino: { tags: ["kids"] },
  Lastenkino: { tags: ["kids"] },
  Seniorikino: { tags: ["senior"] },
  Seniorinäytös: { tags: ["senior"] },
  // "First time at the movies", for small children (Bio Marilyn, 2026-10-20).
  "EkaKertaLeffassa-näytös": { series: "EkaKertaLeffassa", tags: ["kids"] },
  EkaKertaLeffassa: { series: "EkaKertaLeffassa", tags: ["kids"] },
  // Event cinema
  Ooppera: { tags: ["event-cinema"], event: true },
  Baletti: { tags: ["event-cinema"], event: true },
  "Oopperat ja muut eventit": { tags: ["event-cinema"], event: true },
  // Extras, price
  Tekijävierailu: { tags: ["guest"] },
  "Vapaa pääsy": { tags: ["free"] },
  "Ilmainen sisäänpääsy": { tags: ["free"] },
  "Edullinen päivänäytös": { tags: ["discount"] },
  // Bar service; the age limit only where the label states it (Finnkino separates the two).
  Anniskelunäytös: { licensed: true },
  "Anniskelunäytös K18": { licensed: true, ageLimit: "K-18" },
  "Anniskelunäytös K-18": { licensed: true, ageLimit: "K-18" },
  // The age first: Bio Rex Kokkola (2026-10-18).
  "K18 - Anniskelunäytös": { licensed: true, ageLimit: "K-18" },
  "K-18 - Anniskelunäytös": { licensed: true, ageLimit: "K-18" },
  // Availability
  Kiirehdi: { availability: "few-left" },
  "Viimeiset liput": { availability: "few-left" },
  Loppuunmyyty: { availability: "sold-out" },
  // Language
  "Puhuttu suomeksi": { audio: "fi", dubbed: true },
  "Puhuttu ruotsiksi": { audio: "sv", dubbed: true },
  "Puhuttu englanniksi": { audio: "en" },
  "Ei tekstitystä": { subtitles: "none" },
  "Ei puhetta": { audio: "zxx", tags: ["no-dialogue"] },
  // Accessibility: subtitles describing sound too, for the hard of hearing
  "Kuvaileva tekstitys": { tags: ["captions"] },
  "Tekstitetty heikkokuuloisille": { tags: ["captions"] },
  Kuvailutulkkaus: { tags: ["audio-description"] },
  // Projection
  "35mm": { projection: "35mm" },
  "35 mm": { projection: "35mm" },
  "70mm": { projection: "70mm" },
  "70 mm": { projection: "70mm" },
  // Meaningful only inside the cinema
  Erikoisnäytös: {},
};

/** "Prefix: Title" labels: the shared table (kept under its old name for the adapters). */
export const COMMON_TITLE_PREFIXES: Record<string, LabelRule> = LABELS;

export { labelKey };

/** The rule for a label, looked up in each table in turn (site rules first). */
export const findLabel = (
  label: string,
  ...tables: Record<string, LabelRule>[]
): LabelRule | undefined => {
  const key = labelKey(label);
  for (const table of tables) {
    const exact = own(table, label);
    if (exact) {
      return exact;
    }
    const hit = Object.entries(table).find(([k]) => labelKey(k) === key)?.[1];
    if (hit) {
      return hit;
    }
  }
  return undefined;
};

/** What a set of matched rules says, merged; later rules win for single facts. */
export type LabelEffects = {
  tags: ScreeningTag[];
  series: string[];
  event?: boolean;
  licensed?: boolean;
  ageLimit?: FinnishRating;
  availability?: Availability;
  audio?: Lang;
  dubbed?: boolean;
  subtitles?: "none" | Lang;
  projection?: Projection;
};

export const labelEffects = (rules: (LabelRule | undefined)[]): LabelEffects => {
  const effects: LabelEffects = { tags: [], series: [] };
  for (const rule of rules) {
    if (!rule) {
      continue;
    }
    effects.tags.push(...(rule.tags ?? []));
    if (rule.series) {
      effects.series.push(rule.series);
    }
    for (const key of [
      "event",
      "licensed",
      "ageLimit",
      "availability",
      "audio",
      "dubbed",
      "subtitles",
      "projection",
    ] as const) {
      if (rule[key] !== undefined) {
        Object.assign(effects, { [key]: rule[key] });
      }
    }
  }
  effects.tags = [...new Set(effects.tags)];
  effects.series = [...new Set(effects.series)];
  return effects;
};

/** A label's rule, matched without regard to case or punctuation. */
// A series the registry knows is a label too: "Kuukauden pohjoismainen: Knyckertz",
// "Geel (Taidekaupungin elokuvajuhlat)". The pull resolves the name to its id.
const ruleFor = (rules: Record<string, LabelRule>, label: string): LabelRule | undefined =>
  findLabel(label, rules) ?? (findSeries(label) ? { series: label } : undefined);

/**
 * "Ennakkonäytös: Pikkuli" -> { title: "Pikkuli", rule } when the prefix has a rule.
 * Only listed prefixes are touched: "Ryhmä Hau: Dinoelokuva" is a title, not a label.
 * The same labels at the end: "Pirjo i Sverige – Vauvakino", "Pikkuli (Ennakkonäytös!)".
 */
export const splitTitlePrefix = (
  raw: string,
  rules: Record<string, LabelRule>,
): { title: string; rule?: LabelRule; label?: string } => {
  const title = raw.trim();
  const prefix = title.match(/^([^:]+):\s*(.+)$/);
  const prefixRule = prefix ? ruleFor(rules, prefix[1]!.trim()) : undefined;
  if (prefix && prefixRule) {
    return { title: prefix[2]!.trim(), rule: prefixRule, label: prefix[1]!.trim() };
  }
  // The same labels after a dash at the end: "Pirjo i Sverige – Vauvakino".
  const suffix = title.match(/^(.+?)\s+[–-]\s+([^–-]+)$/);
  const suffixRule = suffix ? ruleFor(rules, suffix[2]!.trim()) : undefined;
  if (suffix && suffixRule) {
    return { title: suffix[1]!.trim(), rule: suffixRule, label: suffix[2]!.trim() };
  }
  // In parentheses at the end, an exclamation mark allowed: "(Ennakkonäytös!)" (TMB).
  const paren = title.match(/^(.+?)\s*\(([^()]+?)!?\)$/);
  const parenRule = paren ? ruleFor(rules, paren[2]!.trim()) : undefined;
  if (paren && parenRule) {
    return { title: paren[1]!.trim(), rule: parenRule, label: paren[2]!.trim() };
  }
  return { title };
};

/**
 * A label with a date after a comma or dash at the end of a title: "Lapin Sota , Ensi-ilta
 * 23.10." -> { title: "Lapin Sota", label: "Ensi-ilta 23.10.", rule, day: 23, month: 10 }.
 * The rule holds only on that day (the premiere is one screening's, not the run's). Only
 * labels the rules know are taken off; any other text stays in the title.
 */
export const splitDatedLabel = (
  raw: string,
  rules: Record<string, LabelRule>,
): { title: string; label?: string; rule?: LabelRule; day?: number; month?: number } => {
  const title = raw.trim();
  // The last comma, or dash between spaces ("Ensi-ilta" keeps its own hyphen).
  const m = title.match(/^(.+)(?:\s*,\s*|\s+[–-]\s+)(.+?)\s+(\d{1,2})\.(\d{1,2})\.?$/);
  const rule = m ? findLabel(m[2]!, rules) : undefined;
  if (!m || !rule) {
    return { title };
  }
  return {
    title: m[1]!.trim(),
    label: title.slice(m[1]!.length).replace(/^(?:\s*,\s*|\s+[–-]\s+)/, ""),
    rule,
    day: Number(m[3]),
    month: Number(m[4]),
  };
};

/**
 * A booking that is no public screening, listed in a programme: "Yksityistilaisuus"
 * (Kino Tervakoski 2026-10-17, Bio Pallas 2026-10-19), "Yksityisnäytös". Nothing to list
 * and nothing missing, so parsers skip it without a warning.
 */
export const isPrivateBooking = (title: string): boolean =>
  /^(?:yksityistilaisuus|yksityisnäytös|yksityinen tilaisuus|suljettu tilaisuus)\b/i.test(
    title.trim(),
  );

export type Version = {
  dubbed?: boolean;
  /** Audio language the version marker states. */
  audio?: Lang;
  dimension?: "2d" | "3d";
};

/** Version markers at the end of a title, as Finnish cinemas write them. */
const VERSIONS: [RegExp, Version][] = [
  [
    // "DUP." is a typo seen in the wild for DUB.
    /^(?:dub|dup|dubattu|suomeksi|suomeksi puhuttu|puhuttu suomeksi|puhumme suomea!?)\.?$/i,
    { dubbed: true, audio: "fi" },
  ],
  [/^(?:på svenska|ruotsiksi)$/i, { dubbed: true, audio: "sv" }],
  [/^(?:englanniksi|eng|english)$/i, { dubbed: false, audio: "en" }],
  [/^(?:orig|original|alkuperäinen|sub|tekstitetty)$/i, { dubbed: false }],
  // A cut of the film, not a different film: strip it so TMDB matching sees the title.
  [/^(?:ohjaajan versio|director's cut|restauroitu|restored)$/i, {}],
  [/^2d$/i, { dimension: "2d" }],
  [/^3d$/i, { dimension: "3d" }],
];

/**
 * Strips version markers ("(DUB)", "SUB", "(suomeksi)", "2D") off the end of a title and
 * returns what they say, so all versions of a film share one title for TMDB matching.
 */
export const splitVersion = (raw: string): { title: string; version: Version } => {
  let title = raw.trim();
  const version: Version = {};
  // A leading marker: "På svenska: Bortglömda ön" (Bio Forum).
  const lead = title.match(/^([^:]+):\s*(.+)$/);
  const leadHit = lead && VERSIONS.find(([re]) => re.test(lead[1]!.trim()));
  if (lead && leadHit) {
    Object.assign(version, leadHit[1]);
    title = lead[2]!.trim();
  }
  // A trailing capitalised language: "Unohdettu saari SUOMEKSI", "… PÅ SVENSKA" (Cinemahouse).
  // Upper case only, so a title that merely ends in the word is left alone.
  const caps = title.match(/^(.*\S)\s+(SUOMEKSI|RUOTSIKSI|ENGLANNIKSI|PÅ SVENSKA)$/);
  const capsHit = caps && VERSIONS.find(([re]) => re.test(caps[2]!));
  if (caps && capsHit) {
    Object.assign(version, capsHit[1]);
    title = caps[1]!.trim();
  }
  for (;;) {
    // "(DUB)", "DUB", or after a comma or dash: "Unohdettu saari, englanniksi".
    const m = title.match(
      /^(.*?)\s*(?:\(([^()]+)\)|\b(DU[BP]\.?|SUB|ORIG|ENG|2D|3D)|(?:,|\s[–-])\s*([^,()–-]+))$/i,
    );
    const marker = m && (m[2] ?? m[3] ?? m[4])?.trim();
    const hit = marker ? VERSIONS.find(([re]) => re.test(marker)) : undefined;
    if (!m || !hit || !m[1]) {
      return { title, version };
    }
    Object.assign(version, hit[1]);
    title = m[1].trim();
  }
};

/**
 * Tags that follow from other facts, whichever parser set them: a screening whose only
 * audio is "zxx" (no linguistic content: "Ei puhetta", a silent film) has no dialogue.
 */
export const deriveTags = (batch: ProviderBatch): ProviderBatch => ({
  ...batch,
  screenings: batch.screenings.map((s) =>
    s.audio.length === 1 && s.audio[0] === "zxx" && !s.tags.includes("no-dialogue")
      ? { ...s, tags: [...s.tags, "no-dialogue"] }
      : s,
  ),
});

/**
 * A film released this many years ago or more is shown again, whoever shows it: a derived
 * `classic` tag, next to the cinemas' own "Klassikko" (Finnkino). The front page lists these
 * as re-runs ("Uusintaesitykset"). 5 years, the maintainer's choice (2026-10-20), takes in
 * anniversary and re-releases like Avengers: Endgame Encore (2019), not this year's films.
 */
export const CLASSIC_AGE_YEARS = 5;

/** The screening tagged `classic` when its film's `year` is old enough; unchanged otherwise. */
export const withClassicTag = <S extends { tags: ScreeningTag[] }>(
  screening: S,
  year: number | undefined,
  currentYear: number,
): S =>
  year !== undefined &&
  currentYear - year >= CLASSIC_AGE_YEARS &&
  !screening.tags.includes("classic")
    ? { ...screening, tags: [...screening.tags, "classic"] }
    : screening;
