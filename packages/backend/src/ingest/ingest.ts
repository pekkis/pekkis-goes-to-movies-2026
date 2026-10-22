import { isIncomplete, type FilmCatalog, type ProviderBatch } from "@pgtm/model";
import { sql, type Kysely, type Transaction } from "kysely";
import type { DB } from "../db/types.ts";
import {
  auditoriumRow,
  filmListingRow,
  filmRatingRows,
  filmRow,
  providerRow,
  screeningRow,
  seriesRow,
  venueRow,
} from "./rows.ts";

/** Postgres allows 65,535 bind parameters per statement; screenings have ~30 columns. */
const CHUNK = 500;

const chunks = <T>(items: T[]): T[][] =>
  Array.from({ length: Math.ceil(items.length / CHUNK) }, (_, i) =>
    items.slice(i * CHUNK, (i + 1) * CHUNK),
  );

type Table = "providers" | "venues" | "auditoriums" | "films" | "filmListings" | "series";

/**
 * `insert … on conflict (id) do update set <every column> = excluded.<column>`.
 * Rows of one call must share their keys (the row mappers guarantee that).
 */
const upsert = async (
  db: Kysely<DB> | Transaction<DB>,
  table: Table,
  rows: Record<string, unknown>[],
): Promise<void> => {
  for (const chunk of chunks(rows)) {
    const columns = Object.keys(chunk[0]!).filter((c) => c !== "id");
    await db
      .insertInto(table)
      // oxlint-disable-next-line typescript/no-explicit-any -- rows are typed by the mappers
      .values(chunk as any)
      .onConflict((oc) =>
        oc.column("id").doUpdateSet((eb) => ({
          ...Object.fromEntries(columns.map((c) => [c, eb.ref(`excluded.${c}` as never)])),
          updatedAt: sql<Date>`now()`,
        })),
      )
      .execute();
  }
};

/** Upserts the films and replaces their ratings with the catalog's (a snapshot). */
export const ingestFilms = async (db: Kysely<DB>, catalog: FilmCatalog): Promise<number> => {
  await db.transaction().execute(async (trx) => {
    await upsert(trx, "films", catalog.films.map(filmRow));
    const ids = catalog.films.map((f) => f.id);
    if (ids.length) {
      await trx.deleteFrom("filmRatings").where("filmId", "in", ids).execute();
    }
    for (const chunk of chunks(catalog.films.flatMap(filmRatingRows))) {
      await trx.insertInto("filmRatings").values(chunk).execute();
    }
  });
  return catalog.films.length;
};

export type BatchResult = {
  inserted: number;
  updated: number;
  removed: number;
  /**
   * Why removals were not inferred, or false when they were: "incomplete" (data-missing
   * warnings, see isIncomplete), "empty" (no screenings at all and no warning to say why)
   * or "drop" (far fewer upcoming screenings than we hold: a source answering in part).
   */
  removalsSkipped: false | "incomplete" | "empty" | "drop";
};

/**
 * A batch with under this share of the upcoming screenings we hold for its venues and days,
 * and at least DROP_MIN fewer, is a source answering in part, not a cinema cancelling:
 * Cine Mäntsälä's API returned only today instead of the week on 2026-10-20.
 */
export const DROP_SHARE = 0.5;

/**
 * Screenings starting this soon after the pull are never marked removed: sources drop a
 * show once its online sales close, just before it starts (Finnkino left out a 12:10 show
 * from a 12:05 answer, 2026-10-22). A cancellation this late is rare, and missing it
 * costs nothing.
 */
export const REMOVAL_MARGIN_MINUTES = 30;
export const DROP_MIN = 10;

/** Whether `incoming` upcoming screenings, against `held`, look like a partial answer. */
export const looksPartial = (held: number, incoming: number): boolean =>
  incoming < held * DROP_SHARE && held - incoming >= DROP_MIN;

/**
 * Upserts one provider's batch in a transaction. Screenings keep history:
 * - new ones get first_seen_at = last_seen_at = batch.fetchedAt
 * - seen again: fields updated, last_seen_at bumped, removed_at cleared
 * - missing from the batch, at one of its venues, inside its date window and starting
 *   more than REMOVAL_MARGIN_MINUTES after the pull: removed_at = batch.fetchedAt. Past
 *   and about-to-start screenings are never touched (sources drop those), and
 *   venues the batch does not list (a partial `--venue` pull) are left alone.
 *   Nothing is marked removed from an incomplete batch, or from an empty one: a source
 *   whose whole programme vanishes without a warning is far more often a parser that
 *   silently stopped matching than a cinema cancelling everything.
 * Films must be ingested first (listings and screenings refer to them).
 */
export const ingestBatch = (db: Kysely<DB>, batch: ProviderBatch): Promise<BatchResult> =>
  db.transaction().execute(async (trx) => {
    const seenAt = batch.fetchedAt;
    // Removals consider only screenings starting after this: see REMOVAL_MARGIN_MINUTES.
    const cutoff = new Date(Date.parse(seenAt) + REMOVAL_MARGIN_MINUTES * 60_000);
    // What we hold for this batch's venues and days still to come, before writing anything.
    const upcoming = () =>
      trx
        .selectFrom("screenings")
        .where("providerId", "=", batch.provider.id)
        .where(sql<boolean>`venue_id = any(${batch.venues.map((v) => v.id)}::text[])`)
        .where("businessDate", ">=", batch.window.from)
        .where("businessDate", "<=", batch.window.to)
        .where("startsAt", ">", cutoff)
        .where("removedAt", "is", null);
    const held = batch.venues.length
      ? Number(
          (
            await upcoming()
              .select(sql<number>`count(*)`.as("n"))
              .executeTakeFirstOrThrow()
          ).n,
        )
      : 0;
    const incoming = batch.screenings.filter(
      (s) => Date.parse(s.startsAt) > cutoff.getTime(),
    ).length;
    await upsert(trx, "providers", [providerRow(batch.provider)]);
    await upsert(trx, "venues", batch.venues.map(venueRow));
    await upsert(trx, "auditoriums", batch.auditoriums.map(auditoriumRow));
    await upsert(trx, "filmListings", batch.listings.map(filmListingRow));
    // The series the screenings point to; a name or kind the registry changed is updated.
    await upsert(trx, "series", (batch.series ?? []).map(seriesRow));

    let inserted = 0;
    let updated = 0;
    for (const chunk of chunks(batch.screenings.map(screeningRow))) {
      const columns = Object.keys(chunk[0]!).filter((c) => c !== "id");
      const rows = await trx
        .insertInto("screenings")
        .values(chunk.map((row) => ({ ...row, firstSeenAt: seenAt, lastSeenAt: seenAt })))
        .onConflict((oc) =>
          oc.column("id").doUpdateSet((eb) => ({
            ...Object.fromEntries(columns.map((c) => [c, eb.ref(`excluded.${c}` as never)])),
            lastSeenAt: seenAt,
            removedAt: null,
            updatedAt: sql<Date>`now()`,
          })),
        )
        // xmax = 0 only for freshly inserted rows.
        .returning(sql<boolean>`(xmax = 0)`.as("inserted"))
        .execute();
      for (const row of rows) {
        if (row.inserted) {
          inserted++;
        } else {
          updated++;
        }
      }
    }

    // Part of the source failed to parse: absence proves nothing this time.
    if (isIncomplete(batch)) {
      return { inserted, updated, removed: 0, removalsSkipped: "incomplete" };
    }
    // Nothing at all, and nothing said why: assume the parser, not the cinema.
    if (batch.screenings.length === 0) {
      return { inserted, updated, removed: 0, removalsSkipped: "empty" };
    }
    // Most of what we hold vanished at once: assume the source answered in part.
    if (looksPartial(held, incoming)) {
      return { inserted, updated, removed: 0, removalsSkipped: "drop" };
    }

    const removed = await trx
      .updateTable("screenings")
      .set({ removedAt: seenAt, updatedAt: sql<Date>`now()` })
      .where("providerId", "=", batch.provider.id)
      .where(sql<boolean>`venue_id = any(${batch.venues.map((v) => v.id)}::text[])`)
      .where("businessDate", ">=", batch.window.from)
      .where("businessDate", "<=", batch.window.to)
      .where("startsAt", ">", cutoff)
      .where("removedAt", "is", null)
      .where(sql<boolean>`not (id = any(${batch.screenings.map((s) => s.id)}::text[]))`)
      .executeTakeFirst();

    return { inserted, updated, removed: Number(removed.numUpdatedRows), removalsSkipped: false };
  });
