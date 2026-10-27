import { describe, expect, it } from "vitest";
import {
  availabilityFromSeats,
  eachStartTime,
  plainText,
  slugify,
  toCents,
} from "../../src/providers/parsing.ts";

describe("toCents", () => {
  it("reads euros in either decimal style", () => {
    expect(toCents("15,00", { zeroIsFree: false })).toBe(1500);
    expect(toCents("12.5", { zeroIsFree: false })).toBe(1250);
    expect(toCents(8.5, { zeroIsFree: true })).toBe(850);
  });

  it("keeps 0 only where the source means free", () => {
    expect(toCents("0.00", { zeroIsFree: false })).toBeUndefined();
    expect(toCents(0, { zeroIsFree: true })).toBe(0);
  });

  it("rejects what is not a price", () => {
    expect(toCents(null, { zeroIsFree: true })).toBeUndefined();
    expect(toCents("", { zeroIsFree: true })).toBeUndefined();
    expect(toCents("ilmainen", { zeroIsFree: true })).toBeUndefined();
    expect(toCents(-1, { zeroIsFree: true })).toBeUndefined();
  });
});

describe("availabilityFromSeats", () => {
  it("maps free seats and capacity", () => {
    expect(availabilityFromSeats({ free: 0, capacity: 100 })).toBe("sold-out");
    expect(availabilityFromSeats({ free: 9, capacity: 100 })).toBe("few-left");
    expect(availabilityFromSeats({ free: 10, capacity: 100 })).toBe("available");
    expect(availabilityFromSeats({ free: -2, capacity: 100 })).toBe("sold-out");
  });

  it("tells only sold-out from available without the capacity", () => {
    expect(availabilityFromSeats({ free: 3 })).toBe("available");
    expect(availabilityFromSeats({ free: 0 })).toBe("sold-out");
    expect(availabilityFromSeats({})).toBe("unknown");
  });
});

describe("slugify", () => {
  it("makes id-safe slugs, Nordic letters included", () => {
    expect(slugify("Feeniks-sali (Teatteri)")).toBe("feeniks-sali-teatteri");
    expect(slugify("Sali Ä")).toBe("sali-a");
    expect(slugify("VIP-SALI")).toBe("vip-sali");
  });

  it("ignores soft hyphens and zero-width characters (Kino Hamina, 2026-10-27)", () => {
    expect(slugify("Late Lammas Hä­mä­rä­puu­his­sa")).toBe("late-lammas-hamarapuuhissa");
    expect(slugify("Zero​width﻿")).toBe("zerowidth");
  });
});

describe("plainText", () => {
  it.each([
    ["  Late Lammas\n  Hä­mä­rä­puu­his­sa ", "Late Lammas Hämäräpuuhissa"],
    ["﻿Kino​ Hamina", "Kino Hamina"],
    [undefined, ""],
  ])("plainText(%j) = %j", (value, expected) => {
    expect(plainText(value)).toBe(expected);
  });
});

describe("eachStartTime", () => {
  it.each([
    ["pe 23.10. 16:00 ja 19:15", ["pe 23.10. 16:00", "pe 23.10. 19:15"]],
    [
      "Ensi-ilta pe 23.10. 16:00 ja 19:15",
      ["Ensi-ilta pe 23.10. 16:00", "Ensi-ilta pe 23.10. 19:15"],
    ],
    ["24.10. La klo17.00 ja klo18.00", ["24.10. La klo 17.00", "24.10. La klo 18.00"]],
    ["TO 29.10. KLO 16:30 & 18:30", ["TO 29.10. KLO 16:30", "TO 29.10. KLO 18:30"]],
    ["la 24.10. 12:00, 14:00 ja 18:30", ["la 24.10. 12:00", "la 24.10. 14:00", "la 24.10. 18:30"]],
    ["pe 23.10. 19:00", ["pe 23.10. 19:00"]],
    ["Tulossa", ["Tulossa"]],
  ])("%s", (row, rows) => {
    expect(eachStartTime(row)).toEqual(rows);
  });
});
