# Deployment

How the service runs on a server with Docker Compose behind nginx, and how the daily data gets there. Tested locally with the same Compose stack, 2026-10-14 **[V]**; the nginx block below is a template **[A]**: check it against your setup.

## The pieces

| Service    | Image              | Listens on                    | What it does                                                           |
| ---------- | ------------------ | ----------------------------- | ---------------------------------------------------------------------- |
| `postgres` | postgres:18-alpine | `127.0.0.1:${PG_PORT:-5432}`  | the database (volume `pgtm_postgres`)                                  |
| `migrate`  | pgtm-api           | –                             | one-shot: applies migrations on every `up`                             |
| `api`      | pgtm-api           | `127.0.0.1:${API_PORT:-3000}` | HTTP API, `/docs`, and MCP at `/mcp/{MCP_TOKEN}` when the token is set |
| `web`      | pgtm-web           | `127.0.0.1:${WEB_PORT:-4321}` | the website (Astro SSR), reading the API over the Compose network      |
| `ingest`   | pgtm-api           | –                             | on demand: loads `./data/normalized` into Postgres                     |

Everything binds to localhost; nginx publishes it. The server never fetches showtimes: the pull runs at home (Finnkino needs a visible Chrome), and the files are shipped over.

## First time on the server

1. **Check out the repository** wherever your services live, e.g. `/srv/pgtm`.
2. **Write `.env` there** (gitignored); see [.env.example](../.env.example):
   ```sh
   POSTGRES_PASSWORD=…        # before the first `up`: Postgres keeps the password it was created with
   API_PORT=3000              # free local ports for nginx
   WEB_PORT=4321
   SITE_URL=https://elokuvat.dr-kobros.com
   MCP_TOKEN=…                # optional: openssl rand -base64 32 | tr '+/' '-_' | tr -d '='
   ```
   `INDEXING` stays unset (off) until every cinema has been notified (AGENTS.md).
3. **Start the stack:** `docker compose --profile app up -d --build --wait`. This builds both images, starts Postgres, runs the migrations, and starts the API and the website.
4. **Configure nginx** (below) and get a certificate (e.g. `certbot --nginx -d elokuvat.dr-kobros.com`).
5. **First data** from home: `pnpm pull && pnpm data:push`.

**Updating:** `git pull && docker compose --profile app up -d --build --wait` on the server. Migrations run by themselves.

## Daily, at home

```sh
pnpm pull && pnpm data:push
```

`data:push` (`scripts/push-data.ts`):

1. rsyncs `data/normalized/` to `{DEPLOY_TARGET}/data/normalized/` over SSH;
2. runs `docker compose --profile ingest run --rm ingest` on the server.

Set `DEPLOY_TARGET=user@host:/srv/pgtm` in your home `.env`; it needs SSH access and Docker rights on the server. Ingest is idempotent and keeps history, as locally. Your local `pnpm ingest` still works for the local database.

## nginx

One domain, split by path: the API's paths go to the API, everything else to the website. Same origin, so no CORS.

```nginx
server {
    listen 80;
    server_name elokuvat.dr-kobros.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    http2 on;
    server_name elokuvat.dr-kobros.com;
    # ssl_certificate / ssl_certificate_key: from certbot

    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # MCP (Streamable HTTP): responses may stream as server-sent events.
    location /mcp/ {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # The HTTP API and its docs.
    location /v1/ { proxy_pass http://127.0.0.1:3000; }
    location = /openapi.json { proxy_pass http://127.0.0.1:3000; }
    location /docs { proxy_pass http://127.0.0.1:3000; }

    # Everything else: the website.
    location / { proxy_pass http://127.0.0.1:4321; }
}
```

Use your `API_PORT` / `WEB_PORT` if you changed them.

## Backups

The showtimes can be fetched again; their **history** can't: first and last seen, and removals. Back up the database, e.g. daily:

```sh
docker compose exec -T postgres pg_dump -U pgtm -Fc pgtm > backups/pgtm-$(date +%F).dump
```

Restore with `pg_restore -U pgtm -d pgtm --clean` inside the container.

## Checks after deploying

- `https://elokuvat.dr-kobros.com/fi/` shows the cities. `/fi/kartta` draws the map: the browser fetches its tiles and fonts from OpenFreeMap directly.
- `curl -I https://elokuvat.dr-kobros.com/fi/` includes `X-Robots-Tag: noindex, nofollow`.
- `https://elokuvat.dr-kobros.com/v1/health` answers `{"ok":true,…}`.
- MCP: add `https://elokuvat.dr-kobros.com/mcp/{MCP_TOKEN}` as a custom connector in Claude and ask "mitä Tampereella tänään illalla?".
