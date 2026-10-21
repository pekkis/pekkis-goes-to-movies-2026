import { describe, expect, it } from "vitest";
import { createHttpClient, decodeBody, retryAfterMs } from "../../src/lib/http.ts";

const bytes = (...values: number[]) => new Uint8Array(values).buffer;

describe("decodeBody", () => {
  it("decodes by the charset the Content-Type states", () => {
    // "Ä" in ISO-8859-1 is one byte, 0xC4.
    expect(decodeBody(bytes(0xc4, 0x4c), "text/html;charset=ISO-8859-1")).toBe("ÄL");
    expect(decodeBody(bytes(0xc4, 0x4c), 'text/html; charset="iso-8859-1"')).toBe("ÄL");
  });

  it("assumes UTF-8 when no charset or an unknown one is stated", () => {
    expect(decodeBody(bytes(0xc3, 0x84), "text/html")).toBe("Ä");
    expect(decodeBody(bytes(0xc3, 0x84), null)).toBe("Ä");
    expect(decodeBody(bytes(0xc3, 0x84), "text/html; charset=nonsense")).toBe("Ä");
  });
});

describe("retryAfterMs", () => {
  const now = new Date("2026-10-21T14:00:00Z");
  it.each([
    ["7200", 7_200_000],
    ["0", 0],
    ["Wed, 21 Oct 2026 14:00:30 GMT", 30_000],
    ["Wed, 21 Oct 2026 13:00:00 GMT", 0],
    ["soon", undefined],
    [null, undefined],
  ])("%s -> %s ms", (value, ms) => {
    expect(retryAfterMs(value, now)).toBe(ms);
  });
});

describe("retries", () => {
  /** A fetch that answers 503 with the given Retry-After, counting its calls. */
  const maintenance = (retryAfter: string) => {
    let calls = 0;
    const impl = (async () => {
      calls++;
      return new Response("<title>Sivusto on hetken huollossa</title>", {
        status: 503,
        headers: { "Retry-After": retryAfter, "content-type": "text/html" },
      });
    }) as typeof fetch;
    return { impl, calls: () => calls };
  };

  it("gives up at once on maintenance (Retry-After: 7200), not after two hours (2026-10-21)", async () => {
    const fake = maintenance("7200");
    const http = createHttpClient({ intervalMs: 0, fetch: fake.impl });
    const started = Date.now();
    await expect(http.getText("https://kino.example/")).rejects.toThrow(/503/);
    expect(fake.calls()).toBe(1);
    expect(Date.now() - started).toBeLessThan(5_000);
  });

  it("still retries a short Retry-After", async () => {
    const fake = maintenance("0");
    const http = createHttpClient({ intervalMs: 0, fetch: fake.impl });
    await expect(http.getText("https://kino.example/")).rejects.toThrow(/503/);
    expect(fake.calls()).toBe(3);
  });
});
