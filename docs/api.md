# HTTP API

Read-only JSON API over the showtimes database. Code: `packages/backend/src/api/`.

- **Live documentation:** `/docs` (Scalar), generated from `/openapi.json` (OpenAPI 3.1). The schema is the contract; this page is the overview.
- **No authentication**, GET only, CORS open by default.
- **Versioned** under `/v1`. Breaking changes go to `/v2`.

## Running it

```sh
pnpm db:up && pnpm migrate   # Postgres with the schema
pnpm pull && pnpm ingest     # data (see AGENTS.md)
pnpm api:dev                 # http://127.0.0.1:3000, reloads on change
```

The API can also run in Docker, as it will in production:

```sh
pnpm api:up     # builds the image, runs migrations once, starts the API (healthcheck: /v1/health)
pnpm api:down   # stops the API containers; Postgres keeps running
```

## Conventions

- **Ids** are namespaced strings and may contain colons. Use them as they are, URL-encoded if your client does not do it.
  - Venue ids look like `kinoaurora:venue:jyvaskyla` or `finnkino:venue:1004`.
  - A film id is `tmdb:1185806` when the film is matched to TMDB. Otherwise it is the cinema's listing id, e.g. `finnkino:film:HO00000563`; `kind: "listing"` tells the two apart.
- **Times** are Helsinki local time with offset, e.g. `2026-10-10T18:00:00+03:00`.
  - `businessDate` is the cinema's programme day. A show at 00:30 belongs to the previous day's programme.
- **Unknown is `null`** (or an empty list), never a guess. For example, `availability: "unknown"` means the cinema publishes no seat counts.
- **Ticket links** always go to the cinema's own page. We never sell tickets.

## Endpoints

| Endpoint                                                            | Purpose                                           |
| ------------------------------------------------------------------- | ------------------------------------------------- |
| `GET /v1/health`                                                    | `{ ok, db }`; 503 when the database is down       |
| `GET /v1/venues?bbox=&city=`                                        | Venues with coordinates and provider              |
| `GET /v1/venues/{id}`                                               | One venue                                         |
| `GET /v1/screenings?date=&bbox=&venue=&film=&after=&limit=&cursor=` | What's on: one day's screenings, filtered         |
| `GET /v1/films/search?q=&limit=`                                    | Fuzzy title search in any language, typos allowed |
| `GET /v1/films/{id}`                                                | Film details (TMDB) or listing details            |
| `GET /v1/films/{id}/screenings?date=&bbox=&after=`                  | Where and when a film plays on a day              |

**Parameters:**

- `bbox`: the map viewport as `minLon,minLat,maxLon,maxLat`, e.g. `24.5,60.1,25.3,60.4` for the Helsinki area.
- `date`: `YYYY-MM-DD`, defaulting to today in Helsinki.
- `after`: `HH:MM` Helsinki time. Shows after midnight are kept.
- `limit` / `cursor`: `/v1/screenings` returns pages of up to 500 items by default (`limit` ≤ 2000). Pass `nextCursor` back as `cursor` until it is `null`.

**Errors** are JSON `{ "error": "…", "issues": [...] }`:

- `400` for invalid parameters, with Zod's issue list;
- `404` for an unknown id or path.

**Examples:**

```sh
curl 'http://127.0.0.1:3000/v1/venues?bbox=24.5,60.1,25.3,60.4'
curl 'http://127.0.0.1:3000/v1/screenings?bbox=25.6,62.1,25.9,62.3&after=18:00'
curl 'http://127.0.0.1:3000/v1/films/search?q=odysey'
curl 'http://127.0.0.1:3000/v1/films/tmdb:1185806/screenings?date=2026-10-11'
```

Responses carry `Cache-Control: public, max-age=60`. The data changes when someone runs `pnpm ingest`, about daily.

## Clients

**Flutter / Dart:** generate a client from the OpenAPI document, for example:

```sh
curl -o openapi.json http://127.0.0.1:3000/openapi.json
openapi-generator generate -i openapi.json -g dart-dio -o pgtm_api
```

**React / TypeScript (this workspace):** use Hono's typed client. Routes, parameters and response bodies are all typed from the server code:

```ts
import { hc } from "hono/client";
import type { AppType } from "@pgtm/backend";

const api = hc<AppType>("https://api.example.fi");
const res = await api.v1.screenings.$get({
  query: { bbox: "24.5,60.1,25.3,60.4", after: "18:00" },
});
if (res.ok) {
  const { items, nextCursor } = await res.json();
}
```

## Attribution (required in every client UI)

- **Ratings are opt-in in the UI:** `ratings` is always in the data, but some people do not want to know critics' verdicts before seeing a film. Show scores only when the user asks (a toggle, or a score filter), as the CLI does.
- **Ratings:** Rotten Tomatoes, Metacritic and IMDb scores come from OMDb (omdbapi.com, CC BY-NC 4.0: non-commercial, credit "OMDb API"). Show where each score comes from ("Rotten Tomatoes 93%"), and treat them as the sources' trademarks.
- **TMDB:** film data and images come from TMDB. Show the TMDB logo and the notice "This product uses the TMDB API but is not endorsed or certified by TMDB."
- **OpenStreetMap:** some venue coordinates are © OpenStreetMap contributors (ODbL). Any map tiles need their own attribution too.

## Deployment

The image (`Dockerfile` at the repo root) holds a tsdown bundle (`dist/serve.mjs`, `dist/migrate.mjs`) and production dependencies only. It runs as the `node` user and has a healthcheck. It is configured entirely by environment variables:

| Variable       | Default                | Meaning                        |
| -------------- | ---------------------- | ------------------------------ |
| `DATABASE_URL` | (required)             | `postgres://…`                 |
| `PORT`         | `3000`                 | Listen port                    |
| `HOST`         | `0.0.0.0` in the image | Listen address                 |
| `CORS_ORIGINS` | `*`                    | `*` or comma-separated origins |

**On a server with Docker Compose and nginx:**

1. Run the same `compose.yaml` with the `app` profile. Put a real database password in a compose override or an env file (not committed).
2. `migrate` runs once per deploy, before `api` starts.
3. The API listens on `127.0.0.1:3000`. nginx terminates TLS and proxies to it:

```nginx
location / {
    proxy_pass http://127.0.0.1:3000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**Open question:** how data reaches the server's database. The fetcher runs on the maintainer's laptop (Finnkino needs a visible Chrome). Options are running `pnpm ingest` against the remote database over an SSH tunnel, or shipping a dump. Not decided yet.
