import { describe, expect, it } from "vitest";
import { mergePullStatus, parsePullStatus, type PullStatus } from "../src/schema.ts";

const status = (provider: string, at: string, ok = true): PullStatus => ({
  provider,
  attemptedAt: at,
  status: ok ? "ok" : "failed",
  ...(!ok && { error: "Request failed with status code 503" }),
  durationMs: 1000,
});

describe("mergePullStatus", () => {
  it("replaces the providers pulled again and keeps the others", () => {
    const old = [
      status("biosavoy", "2026-10-22T05:00:00.000Z", false),
      status("finnkino", "2026-10-22T05:00:00.000Z"),
    ];
    const fresh = [status("biosavoy", "2026-10-23T05:00:00.000Z")];
    expect(mergePullStatus(old, fresh)).toEqual([fresh[0], old[1]]);
  });
});

describe("parsePullStatus", () => {
  it("reads one status per line and skips what it cannot read", () => {
    const line = JSON.stringify(status("biosavoy", "2026-10-23T05:00:00.000Z", false));
    expect(parsePullStatus(`${line}\nnot json\n{"provider":"x"}\n\n`)).toEqual([
      status("biosavoy", "2026-10-23T05:00:00.000Z", false),
    ]);
  });
});
