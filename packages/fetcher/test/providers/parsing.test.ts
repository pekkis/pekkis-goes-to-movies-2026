import { describe, expect, it } from "vitest";
import { availabilityFromSeats, slugify, toCents } from "../../src/providers/parsing.ts";

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
});
