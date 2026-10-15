import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it, vi } from "vitest";
import type { HttpClient } from "../../../src/lib/http.ts";
import {
  fetchKinoAkseli,
  type KinoAkseliRawSnapshot,
} from "../../../src/providers/kinoakseli/fetch.ts";
import { parseKinoAkseli } from "../../../src/providers/kinoakseli/parse.ts";
import { KINOAKSELI_SITES } from "../../../src/providers/kinoakseli/sites.ts";

const SITE = KINOAKSELI_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/kinoakseli/kinoakseli-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<KinoAkseliRawSnapshot> = {}): KinoAkseliRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 31,
  html: HTML,
  ...overrides,
});

describe("parseKinoAkseli", () => {
  const batch = parseKinoAkseli(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;
  const listing = (key: string) => batch.listings.find((l) => l.sourceId === key)!;

  it("produces a valid batch without warnings; the offer card adds nothing", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.screenings).toHaveLength(17);
    expect(batch.listings.filter((l) => l.title.fi === "Kerro kaikille")).toHaveLength(1);
  });

  it("gives each film the facts written before its heading", () => {
    expect(listing("kerro-kaikille").rating).toBe("K-12");
    expect(listing("pirjo-i-sverige").rating).toBe("S");
    expect(show("kerro-kaikille-202610151745")).toMatchObject({
      startsAt: "2026-10-15T17:45:00+03:00",
      price: { amountCents: 1400, currency: "EUR" },
    });
    expect(show("pirjo-i-sverige-202610151400").price).toEqual({
      amountCents: 1300,
      currency: "EUR",
    });
  });

  it('reads "(dub.)" after a time as that screening\'s version', () => {
    expect(show("unohdettu-saari-202610151200")).toMatchObject({ dubbed: true, audio: ["fi"] });
  });

  it("places nothing when the weekday does not fit the date", () => {
    const wrong = HTML.replace(/To\s+15\.10\.\s+klo\s+17:45/, "Ke 15.10. klo 17:45");
    const result = parseKinoAkseli(snapshot({ html: wrong }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("warns when the headings are gone", () => {
    const result = parseKinoAkseli(snapshot({ html: "<html><body></body></html>" }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});

describe("fetchKinoAkseli", () => {
  it("fails on a captcha challenge instead of parsing it", async () => {
    const http: HttpClient = {
      getJson: vi.fn(),
      getText: vi.fn(async () => "<html>sgcaptcha</html>"),
      postForm: vi.fn(),
    };
    await expect(fetchKinoAkseli(http, SITE, { from: "2026-10-15", days: 7 })).rejects.toThrow(
      /captcha/,
    );
  });
});
