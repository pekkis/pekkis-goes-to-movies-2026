import { ScreeningTag, type Lang } from "@pgtm/model";
import { z } from "zod";
import { own } from "../lib/records.ts";

/**
 * How a cinema's free-text label (a show type, a tag, a title prefix) maps onto the model.
 * Shared by platform adapters; sites override per label in their sites.ts.
 * - `{}`: ignore (a label that only means something inside the cinema)
 * - `tags`: screening tags; `series`: a series or festival name; `licensed`: bar service
 * - `event: true`: the listing is event cinema (opera, concert), not a film
 * A label with no rule becomes a `series` entry, so nothing is lost.
 */
export const LabelRule = z.object({
  tags: z.array(ScreeningTag).optional(),
  series: z.string().optional(),
  event: z.boolean().optional(),
  licensed: z.boolean().optional(),
});
export type LabelRule = z.infer<typeof LabelRule>;

/** "Prefix: Title" labels common to Finnish cinemas. */
export const COMMON_TITLE_PREFIXES: Record<string, LabelRule> = {
  "Ennakkoensi-ilta": { tags: ["preview"] },
  Ennakkonäytös: { tags: ["preview"] },
  Ennakko: { tags: ["preview"] },
  "Ensi-ilta": { tags: ["premiere"] },
  Vauvakino: { tags: ["baby"] },
  Perhekino: { tags: ["kids"] },
  Lastenkino: { tags: ["kids"] },
  Seniorikino: { tags: ["senior"] },
  Ooppera: { tags: ["event-cinema"], event: true },
  Baletti: { tags: ["event-cinema"], event: true },
};

/**
 * "Ennakkonäytös: Pikkuli" -> { title: "Pikkuli", rule } when the prefix has a rule.
 * Only listed prefixes are touched: "Ryhmä Hau: Dinoelokuva" is a title, not a label.
 * The same labels at the end: "Pirjo i Sverige – Vauvakino", "Pikkuli (Ennakkonäytös!)".
 */
/** A label's rule, matched without regard to case ("ENNAKKONÄYTÖS" is "Ennakkonäytös"). */
const ruleFor = (rules: Record<string, LabelRule>, label: string): LabelRule | undefined => {
  const exact = own(rules, label);
  if (exact) {
    return exact;
  }
  const lower = label.toLowerCase();
  return Object.entries(rules).find(([key]) => key.toLowerCase() === lower)?.[1];
};

export const splitTitlePrefix = (
  raw: string,
  rules: Record<string, LabelRule>,
): { title: string; rule?: LabelRule } => {
  const title = raw.trim();
  const prefix = title.match(/^([^:]+):\s*(.+)$/);
  const prefixRule = prefix ? ruleFor(rules, prefix[1]!.trim()) : undefined;
  if (prefix && prefixRule) {
    return { title: prefix[2]!.trim(), rule: prefixRule };
  }
  // The same labels after a dash at the end: "Pirjo i Sverige – Vauvakino".
  const suffix = title.match(/^(.+?)\s+[–-]\s+([^–-]+)$/);
  const suffixRule = suffix ? ruleFor(rules, suffix[2]!.trim()) : undefined;
  if (suffix && suffixRule) {
    return { title: suffix[1]!.trim(), rule: suffixRule };
  }
  // In parentheses at the end, an exclamation mark allowed: "(Ennakkonäytös!)" (TMB).
  const paren = title.match(/^(.+?)\s*\(([^()]+?)!?\)$/);
  const parenRule = paren ? ruleFor(rules, paren[2]!.trim()) : undefined;
  if (paren && parenRule) {
    return { title: paren[1]!.trim(), rule: parenRule };
  }
  return { title };
};

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
