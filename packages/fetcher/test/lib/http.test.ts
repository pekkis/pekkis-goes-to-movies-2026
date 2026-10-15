import { describe, expect, it } from "vitest";
import { decodeBody } from "../../src/lib/http.ts";

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
