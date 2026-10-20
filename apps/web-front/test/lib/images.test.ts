import { describe, expect, it } from "vitest";
import { posterSource } from "../../src/lib/images.ts";

const TMDB = "https://image.tmdb.org/t/p/w500/abc.jpg";

describe("posterSource", () => {
  it.each([
    [64, "w92", "w154"],
    [144, "w154", "w342"],
    [224, "w342", "w500"],
    [500, "w500", "w780"],
  ])("%d px -> %s, %s for 2x", (px, one, two) => {
    expect(posterSource(TMDB, px)).toEqual({
      src: `https://image.tmdb.org/t/p/${one}/abc.jpg`,
      srcSet: `https://image.tmdb.org/t/p/${one}/abc.jpg 1x, https://image.tmdb.org/t/p/${two}/abc.jpg 2x`,
    });
  });

  it("caps at TMDB's largest width and leaves other URLs alone", () => {
    expect(posterSource(TMDB, 900)).toEqual({ src: "https://image.tmdb.org/t/p/w780/abc.jpg" });
    expect(posterSource("https://img.example/p.jpg", 144)).toEqual({
      src: "https://img.example/p.jpg",
    });
  });
});
