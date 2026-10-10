import { ProviderId, type Provider } from "@pgtm/model";
import { z } from "zod";

/**
 * Shared shape for platform adapters that serve many cinema sites (Nexxo, eTiketti, …).
 *
 * The rule: **a site is data, not code.** Everything that differs between sites on one
 * platform is a field in its config, validated by a Zod schema, so fixing a breakage or
 * adding a cinema is an edit to a `sites.ts` list, never a change to the parser:
 *
 * - Common fields (this file): provider id, name, homepage, venues with slug/name/city,
 *   and `verifiedAt`, the date someone last checked the entry against the live site.
 * - Platform fields (the platform's own schema, extending these): where the data lives,
 *   how venues are selected, which links work.
 * - Quirks: named, documented options with platform defaults that a site may override
 *   (e.g. Nexxo's `showTypes`), rather than `if (site === "x")` branches in the parser.
 *
 * Each `sites.ts` is covered by a test that parses every entry and checks id uniqueness.
 */

export const Slug = z.string().regex(/^[a-z0-9-]+$/, "lowercase letters, digits and hyphens");

export const SiteVenue = z.object({
  /** Becomes `{provider}:venue:{slug}`. Stable: changing it orphans the venue's history. */
  slug: Slug,
  name: z.string().min(1),
  city: z.string().min(1),
  shortName: z.string().optional(),
  address: z.string().optional(),
  postalCode: z.string().optional(),
});
export type SiteVenue = z.infer<typeof SiteVenue>;

export const SiteBase = z.object({
  provider: ProviderId,
  name: z.string().min(1),
  /** The cinema's public site: where people are sent. */
  homepage: z.url(),
  /** When this entry was last checked against the live site (YYYY-MM-DD). */
  verifiedAt: z.iso.date(),
  /** Free-form notes for maintainers: why a quirk is set, what was observed. */
  notes: z.string().optional(),
});

export const providerOf = (
  site: z.infer<typeof SiteBase>,
  platform: Provider["platform"],
  booking: Provider["booking"],
): Provider => ({
  id: site.provider,
  name: site.name,
  homepage: site.homepage,
  platform,
  booking,
});

/** Validates a site list: schema, unique providers, unique venue slugs per site. */
export const defineSites = <S extends { provider: string; venues: { slug: string }[] }>(
  schema: z.ZodType<S>,
  sites: S[],
): S[] => {
  const parsed = sites.map((site) => schema.parse(site));
  const providers = new Set<string>();
  for (const site of parsed) {
    if (providers.has(site.provider)) throw new Error(`Duplicate site provider: ${site.provider}`);
    providers.add(site.provider);
    const slugs = site.venues.map((v) => v.slug);
    if (new Set(slugs).size !== slugs.length) {
      throw new Error(`Duplicate venue slug in ${site.provider}: ${slugs.join(", ")}`);
    }
  }
  return parsed;
};
