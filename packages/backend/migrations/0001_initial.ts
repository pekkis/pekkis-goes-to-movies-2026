import { sql, type Kysely } from "kysely";

/**
 * Initial schema. Names follow the model (src: packages/model) in snake_case.
 * Ids are the model's namespaced text ids ("biorex:show:436478", "tmdb:1185806").
 * Enum-like values are text, validated by Zod at ingest: Postgres enums are painful to change.
 * Migrations are append-only: never edit this file once applied anywhere; add a new one.
 */

const textArray = sql`text[]`;
const emptyArray = sql`'{}'::text[]`;

// oxlint-disable-next-line typescript/no-explicit-any -- migrations work on any schema version
type Db = Kysely<any>;

export async function up(db: Db): Promise<void> {
  await db.schema
    .createTable("providers")
    .addColumn("id", "text", (c) => c.primaryKey())
    .addColumn("name", "text", (c) => c.notNull())
    .addColumn("homepage", "text", (c) => c.notNull())
    .addColumn("platform", "text", (c) => c.notNull())
    .addColumn("booking", "text", (c) => c.notNull())
    .addColumn("created_at", "timestamptz", (c) => c.notNull().defaultTo(sql`now()`))
    .addColumn("updated_at", "timestamptz", (c) => c.notNull().defaultTo(sql`now()`))
    .execute();

  await db.schema
    .createTable("venues")
    .addColumn("id", "text", (c) => c.primaryKey())
    .addColumn("provider_id", "text", (c) => c.notNull().references("providers.id"))
    .addColumn("source_id", "text", (c) => c.notNull())
    .addColumn("name", "text", (c) => c.notNull())
    .addColumn("short_name", "text")
    .addColumn("city", "text", (c) => c.notNull())
    .addColumn("address", "text")
    .addColumn("postal_code", "text")
    .addColumn("lat", "double precision")
    .addColumn("lon", "double precision")
    .addColumn("url", "text")
    .addColumn("created_at", "timestamptz", (c) => c.notNull().defaultTo(sql`now()`))
    .addColumn("updated_at", "timestamptz", (c) => c.notNull().defaultTo(sql`now()`))
    .execute();
  await db.schema.createIndex("venues_city_idx").on("venues").column("city").execute();

  await db.schema
    .createTable("auditoriums")
    .addColumn("id", "text", (c) => c.primaryKey())
    .addColumn("venue_id", "text", (c) => c.notNull().references("venues.id"))
    .addColumn("name", "text", (c) => c.notNull())
    .addColumn("seats", "integer")
    .addColumn("features", textArray, (c) => c.notNull().defaultTo(emptyArray))
    .addColumn("age_limit", "text")
    .addColumn("created_at", "timestamptz", (c) => c.notNull().defaultTo(sql`now()`))
    .addColumn("updated_at", "timestamptz", (c) => c.notNull().defaultTo(sql`now()`))
    .execute();

  await db.schema
    .createTable("films")
    .addColumn("id", "text", (c) => c.primaryKey())
    .addColumn("tmdb_id", "integer", (c) => c.notNull().unique())
    .addColumn("imdb_id", "text")
    .addColumn("title_fi", "text")
    .addColumn("title_sv", "text")
    .addColumn("title_en", "text")
    .addColumn("original_title", "text", (c) => c.notNull())
    .addColumn("original_language", "text")
    .addColumn("release_date", "date")
    .addColumn("finnish_release_date", "date")
    .addColumn("runtime_minutes", "integer")
    .addColumn("rating", "text")
    .addColumn("genres", textArray, (c) => c.notNull().defaultTo(emptyArray))
    .addColumn("countries", textArray, (c) => c.notNull().defaultTo(emptyArray))
    .addColumn("overview_fi", "text")
    .addColumn("overview_sv", "text")
    .addColumn("overview_en", "text")
    .addColumn("poster_path", "text")
    .addColumn("backdrop_path", "text")
    .addColumn("trailers", "jsonb", (c) => c.notNull().defaultTo(sql`'[]'::jsonb`))
    .addColumn("fetched_at", "timestamptz", (c) => c.notNull())
    .addColumn("created_at", "timestamptz", (c) => c.notNull().defaultTo(sql`now()`))
    .addColumn("updated_at", "timestamptz", (c) => c.notNull().defaultTo(sql`now()`))
    .execute();

  await db.schema
    .createTable("film_listings")
    .addColumn("id", "text", (c) => c.primaryKey())
    .addColumn("provider_id", "text", (c) => c.notNull().references("providers.id"))
    .addColumn("source_id", "text", (c) => c.notNull())
    .addColumn("title_fi", "text")
    .addColumn("title_sv", "text")
    .addColumn("title_en", "text")
    .addColumn("original_title", "text")
    .addColumn("year", "integer")
    .addColumn("runtime_minutes", "integer")
    .addColumn("rating", "text")
    .addColumn("genres", textArray, (c) => c.notNull().defaultTo(emptyArray))
    .addColumn("countries", textArray, (c) => c.notNull().defaultTo(emptyArray))
    .addColumn("kind", "text", (c) => c.notNull())
    .addColumn("film_id", "text", (c) => c.references("films.id"))
    .addColumn("match", "text")
    .addColumn("created_at", "timestamptz", (c) => c.notNull().defaultTo(sql`now()`))
    .addColumn("updated_at", "timestamptz", (c) => c.notNull().defaultTo(sql`now()`))
    .execute();
  await db.schema
    .createIndex("film_listings_film_id_idx")
    .on("film_listings")
    .column("film_id")
    .execute();

  await db.schema
    .createTable("screenings")
    .addColumn("id", "text", (c) => c.primaryKey())
    .addColumn("provider_id", "text", (c) => c.notNull().references("providers.id"))
    .addColumn("source_id", "text", (c) => c.notNull())
    .addColumn("venue_id", "text", (c) => c.notNull().references("venues.id"))
    .addColumn("auditorium_id", "text", (c) => c.references("auditoriums.id"))
    .addColumn("listing_id", "text", (c) => c.notNull().references("film_listings.id"))
    .addColumn("film_id", "text", (c) => c.references("films.id"))
    .addColumn("starts_at", "timestamptz", (c) => c.notNull())
    .addColumn("ends_at", "timestamptz")
    .addColumn("business_date", "date", (c) => c.notNull())
    .addColumn("projection", "text", (c) => c.notNull())
    .addColumn("dimension", "text", (c) => c.notNull())
    .addColumn("formats", textArray, (c) => c.notNull().defaultTo(emptyArray))
    .addColumn("audio", textArray, (c) => c.notNull().defaultTo(emptyArray))
    .addColumn("dubbed", "boolean")
    .addColumn("subtitles_kind", "text", (c) => c.notNull())
    .addColumn("subtitles_languages", textArray, (c) => c.notNull().defaultTo(emptyArray))
    .addColumn("age_limit", "text")
    .addColumn("age_recommendation", "integer")
    .addColumn("licensed", "boolean")
    .addColumn("tags", textArray, (c) => c.notNull().defaultTo(emptyArray))
    .addColumn("series", textArray, (c) => c.notNull().defaultTo(emptyArray))
    .addColumn("availability", "text", (c) => c.notNull())
    .addColumn("price_amount_cents", "integer")
    .addColumn("price_currency", "text")
    .addColumn("price_note", "text")
    .addColumn("ticket_url", "text")
    .addColumn("unmapped_labels", textArray, (c) => c.notNull().defaultTo(emptyArray))
    .addColumn("fetched_at", "timestamptz", (c) => c.notNull())
    // History: rows are never deleted.
    .addColumn("first_seen_at", "timestamptz", (c) => c.notNull())
    .addColumn("last_seen_at", "timestamptz", (c) => c.notNull())
    .addColumn("removed_at", "timestamptz")
    .addColumn("created_at", "timestamptz", (c) => c.notNull().defaultTo(sql`now()`))
    .addColumn("updated_at", "timestamptz", (c) => c.notNull().defaultTo(sql`now()`))
    .execute();
  await db.schema
    .createIndex("screenings_starts_at_idx")
    .on("screenings")
    .column("starts_at")
    .execute();
  await db.schema
    .createIndex("screenings_venue_id_business_date_idx")
    .on("screenings")
    .columns(["venue_id", "business_date"])
    .execute();
  await db.schema
    .createIndex("screenings_film_id_starts_at_idx")
    .on("screenings")
    .columns(["film_id", "starts_at"])
    .execute();
  await db.schema
    .createIndex("screenings_listing_id_idx")
    .on("screenings")
    .column("listing_id")
    .execute();
  await db.schema
    .createIndex("screenings_provider_id_business_date_idx")
    .on("screenings")
    .columns(["provider_id", "business_date"])
    .execute();
}

export async function down(db: Db): Promise<void> {
  for (const table of [
    "screenings",
    "film_listings",
    "films",
    "auditoriums",
    "venues",
    "providers",
  ]) {
    await db.schema.dropTable(table).execute();
  }
}
