import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { ElavienkuvienRawSnapshot } from "../../../src/providers/elavienkuvien/fetch.ts";
import { filmPaths, parseElavienkuvien } from "../../../src/providers/elavienkuvien/parse.ts";
import { ELAVIENKUVIEN_SITES } from "../../../src/providers/elavienkuvien/sites.ts";

const SITE = ELAVIENKUVIEN_SITES[0]!;
const fixture = (name: string) =>
  readFileSync(join(import.meta.dirname, "../../fixtures/elavienkuvien", name), "utf8");
const LISTING = fixture("elavienkuvien-ohjelmisto.html");
const KERRO = fixture("elavienkuvien-elokuva-kerro-kaikille.html");
const snapshot = (overrides: Partial<ElavienkuvienRawSnapshot> = {}): ElavienkuvienRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 31,
  listing: LISTING,
  films: { "ohjelmisto/kerro-kaikille/": KERRO },
  ...overrides,
});

describe("parseElavienkuvien", () => {
  const batch = parseElavienkuvien(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "buy" });
    expect(batch.screenings.length).toBeGreaterThan(0);
  });

  it("reads the printed year and copies the row's reservation link", () => {
    expect(show("kerro-kaikille-202610151700")).toMatchObject({
      startsAt: "2026-10-15T17:00:00+03:00",
      ticketUrl:
        "https://www.elavienkuvienteatteri.fi/lipunvaraus/?movieid=1395&date=2026-10-15&time=17:00",
    });
    // Two fares on every row and nothing saying which applies: no price.
    expect(show("kerro-kaikille-202610151700").price).toBeUndefined();
  });

  it("reads the runtime and the age limit from the image's name", () => {
    expect(batch.listings[0]).toMatchObject({
      title: { fi: "Kerro kaikille" },
      runtimeMinutes: 112,
      rating: "K-12",
    });
  });

  it("reads film links from the lifts only, not the sub-navigation", () => {
    expect(filmPaths(LISTING)).toEqual([
      "ohjelmisto/dyyni-osa-kolme/",
      "ohjelmisto/kerro-kaikille/",
    ]);
  });

  it("skips an opening day without a time", () => {
    const soon = KERRO.replace(/<p>/, "<p>ke 16.12.2026<br />");
    const result = parseElavienkuvien(
      snapshot({ films: { "ohjelmisto/kerro-kaikille/": soon } }),
      SITE,
    );
    expect(result.warnings).toEqual([]);
  });

  it("marks the batch incomplete when a film page fails", () => {
    const result = parseElavienkuvien(
      snapshot({ films: { "ohjelmisto/kerro-kaikille/": null } }),
      SITE,
    );
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-film-page"]);
    expect(isIncomplete(result)).toBe(true);
  });
});
