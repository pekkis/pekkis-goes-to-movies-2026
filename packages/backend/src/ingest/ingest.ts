import type { FilmCatalog, ProviderBatch } from "@pgtm/model";
import { sql, type Kysely, type Transaction } from "kysely";
import type { DB } from "../db/types.ts";
import {
  auditoriumRow,
  filmListingRow,
  filmRow,
  providerRow,
  screeningRow,
  venueRow,
} from "./rows.ts";

/** Postgres allows 65,535 bind parameters per statement; screenings have ~30 columns. */
const CHUNK = 500;

const chunks = <T>(items: T[]): T[][] =>
  Array.from({ length: Math.ceil(items.length / CHUNK) }, (_, i) =>
    items.slice(i * CHUNK, (i + 1) * CHUNK),
  );

type Table = "providers" | "venues" | "auditoriums" | "films" | "filmListings";

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

export const ingestFilms = async (db: Kysely<DB>, catalog: FilmCatalog): Promise<number> => {
  await upsert(db, "films", catalog.films.map(filmRow));
  return catalog.films.length;
};

export type BatchResult = { inserted: number; updated: number; removed: number };

/**
 * Upserts one provider's batch in a transaction. Screenings keep history:
 * - new ones get first_seen_at = last_seen_at = batch.fetchedAt
 * - seen again: fields updated, last_seen_at bumped, removed_at cleared
 * - missing from the batch, at one of its venues, inside its date window and still in
 *   the future: removed_at = batch.fetchedAt. Past screenings are never touched, and
 *   venues the batch does not list (a partial `--venue` pull) are left alone.
 * Films must be ingested first (listings and screenings refer to them).
 */
export const ingestBatch = (db: Kysely<DB>, batch: ProviderBatch): Promise<BatchResult> =>
  db.transaction().execute(async (trx) => {
    const seenAt = batch.fetchedAt;
    await upsert(trx, "providers", [providerRow(batch.provider)]);
    await upsert(trx, "venues", batch.venues.map(venueRow));
    await upsert(trx, "auditoriums", batch.auditoriums.map(auditoriumRow));
    await upsert(trx, "filmListings", batch.listings.map(filmListingRow));

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
        if (row.inserted) inserted++;
        else updated++;
      }
    }

    const removed = await trx
      .updateTable("screenings")
      .set({ removedAt: seenAt, updatedAt: sql<Date>`now()` })
      .where("providerId", "=", batch.provider.id)
      .where(sql<boolean>`venue_id = any(${batch.venues.map((v) => v.id)}::text[])`)
      .where("businessDate", ">=", batch.window.from)
      .where("businessDate", "<=", batch.window.to)
      .where("startsAt", ">", new Date(seenAt))
      .where("removedAt", "is", null)
      .where(sql<boolean>`not (id = any(${batch.screenings.map((s) => s.id)}::text[]))`)
      .executeTakeFirst();

    return { inserted, updated, removed: Number(removed.numUpdatedRows) };
  });
