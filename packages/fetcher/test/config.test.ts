import { describe, expect, it } from "vitest";
import { loadAliases } from "../src/matching/aliases.ts";
import { loadVenueOverrides } from "../src/providers/overrides.ts";

// The hand-maintained files in config/ are read only by pull and match, so a broken one
// (a merge that dropped a "},", 2026-10-27) would otherwise surface on the next run.
describe("config files", () => {
  it("tmdb-aliases.json is valid", async () => {
    expect(Object.keys(await loadAliases()).length).toBeGreaterThan(0);
  });

  it("venue-overrides.json is valid", async () => {
    expect(Object.keys(await loadVenueOverrides()).length).toBeGreaterThan(0);
  });
});
