import { expect, it } from "vitest";
import { filmRow, screeningRow, venueRow } from "../src/ingest/rows.ts";
import { batch, film, screening } from "./factory.ts";

it("maps a screening to a flat row, unknowns as NULL", () => {
  expect(
    screeningRow(screening("1", { dubbed: undefined, subtitles: { kind: "none" } })),
  ).toMatchObject({
    id: "testchain:show:1",
    providerId: "testchain",
    projection: "digital",
    dimension: "2d",
    formats: ["imax"],
    dubbed: null,
    subtitlesKind: "none",
    subtitlesLanguages: [],
    ageLimit: null,
    licensed: null,
    priceAmountCents: null,
  });
});

it("keeps subtitle languages and price", () => {
  const row = screeningRow(
    screening("1", { price: { amountCents: 1490, currency: "EUR", note: "Senior" } }),
  );
  expect(row).toMatchObject({
    subtitlesKind: "languages",
    subtitlesLanguages: ["fi", "sv"],
    priceAmountCents: 1490,
    priceCurrency: "EUR",
    priceNote: "Senior",
  });
});

it("flattens localized texts into columns and serializes trailers", () => {
  expect(filmRow(film())).toMatchObject({
    titleFi: "Testielokuva",
    titleSv: null,
    titleEn: "Test Film",
    overviewFi: null,
    overviewEn: "A film for tests.",
    trailers: JSON.stringify([{ site: "YouTube", key: "abc", name: "Trailer" }]),
  });
});

it("maps venue coordinates", () => {
  expect(venueRow(batch([]).venues[0]!)).toMatchObject({ lat: 62.24, lon: 25.75, address: null });
});
