import { mkdtemp, readFile, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { getToken, tokenExpiry } from "../../../src/providers/finnkino/token.ts";

/** An unsigned JWT with the given expiry; only the payload matters here. */
const jwt = (exp: Date) =>
  [
    "eyJhbGciOiJub25lIn0",
    Buffer.from(
      JSON.stringify({ exp: exp.getTime() / 1000, sub: "test-client-xxxxxxxx" }),
    ).toString("base64url"),
    "signature-signature-signature",
  ].join(".");

const NOW = new Date("2026-10-09T12:00:00.000Z");
const hours = (h: number) => new Date(NOW.getTime() + h * 3_600_000);

describe("getToken", () => {
  it("reads the expiry from the token", () => {
    expect(tokenExpiry(jwt(hours(12)))).toEqual(hours(12));
  });

  it("fetches once and reuses the cached token while it is valid", async () => {
    const cachePath = join(await mkdtemp(join(tmpdir(), "finnkino-")), "token.json");
    let calls = 0;
    const readToken = async () => (calls++, jwt(hours(12)));

    const first = await getToken({ cachePath, now: () => NOW, readToken });
    const second = await getToken({ cachePath, now: () => hours(10), readToken });

    expect(second).toBe(first);
    expect(calls).toBe(1);
    expect(JSON.parse(await readFile(cachePath, "utf8"))).toEqual({
      token: first,
      expiresAt: hours(12).toISOString(),
    });
    expect((await stat(cachePath)).mode & 0o777).toBe(0o600);
  });

  it("renews when less than an hour is left", async () => {
    const cachePath = join(await mkdtemp(join(tmpdir(), "finnkino-")), "token.json");
    let calls = 0;
    const readToken = async () => (calls++, jwt(hours(12)));

    await getToken({ cachePath, now: () => NOW, readToken });
    await getToken({ cachePath, now: () => hours(11.5), readToken });
    expect(calls).toBe(2);
  });
});
