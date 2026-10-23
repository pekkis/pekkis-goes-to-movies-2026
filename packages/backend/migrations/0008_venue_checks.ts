import { sql, type Kysely } from "kysely";

/**
 * Each venue's state after each pull: ok (screenings), empty (fetched, nothing on), partial
 * (fetched, some rows unreadable) or failed (the source did not answer). A venue's last
 * successful pull, and its history, come from here.
 */

// oxlint-disable-next-line typescript/no-explicit-any -- migrations work on any schema version
export async function up(db: Kysely<any>): Promise<void> {
  await db.schema
    .createTable("venue_checks")
    .addColumn("venue_id", "text", (c) => c.notNull().references("venues.id").onDelete("cascade"))
    .addColumn("checked_at", "timestamptz", (c) => c.notNull())
    .addColumn("provider_id", "text", (c) => c.notNull())
    .addColumn("status", "text", (c) =>
      c.notNull().check(sql`status in ('ok', 'empty', 'partial', 'failed')`),
    )
    .addColumn("screenings", "integer", (c) => c.notNull().defaultTo(0))
    .addColumn("message", "text")
    .addPrimaryKeyConstraint("venue_checks_pkey", ["venue_id", "checked_at"])
    .execute();
}

// oxlint-disable-next-line typescript/no-explicit-any -- migrations work on any schema version
export async function down(db: Kysely<any>): Promise<void> {
  await db.schema.dropTable("venue_checks").execute();
}
