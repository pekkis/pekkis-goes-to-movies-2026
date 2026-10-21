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

**Containers are locked down** (`x-hardened` in `compose.yaml`): a read-only filesystem with a small `/tmp` in memory, no Linux capabilities, `no-new-privileges`, and limits of 512 MB, 128 processes and one core's worth of CPU each. Our images run as `node` and write nothing. Postgres keeps only the capabilities its entrypoint needs to hand its files to the `postgres` user, and has 4 GB (with 256 MB of `/dev/shm`) and two cores' worth of CPU. On 2026-10-21 the whole stack ran this way in a separate Compose project with a fresh volume **[V]**: Postgres initialised and restarted, migrations ran, a full ingest ran, pages, the API and MCP answered, `docker diff` showed no writes, and each service used under 100 MB. If a container ever needs to write, give it a `tmpfs` or a volume for that path; don't drop `read_only`.

## First time on the server

1. **Check out the repository** wherever your services live, e.g. `/srv/pgtm`.
2. **Write `.env` there** (gitignored); see [.env.example](../.env.example):
   ```sh
   POSTGRES_PASSWORD=…        # before the first `up`: Postgres keeps the password it was created with
   API_PORT=3579              # free local ports for nginx (3000 is often taken)
   WEB_PORT=4321
   SITE_URL=https://movies.pekkis.eu
   MCP_TOKEN=…                # optional: openssl rand -base64 32 | tr '+/' '-_' | tr -d '='
   ```
   `INDEXING` stays unset (off) until every cinema has been notified (AGENTS.md).
3. **Start the stack:** `docker compose --profile app up -d --build --wait`. This builds both images, starts Postgres, runs the migrations, and starts the API and the website.
4. **Configure nginx** (below) and get a certificate for both names.
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

Two names: the website at `movies.pekkis.eu`, the API (with `/docs` and MCP) at `api.movies.pekkis.eu`. The website reads the API over the Compose network, so it doesn't care where the API is published. Browsers and apps calling the API from elsewhere are allowed by `CORS_ORIGINS` (`*` by default). One certificate covers both: `certbot --nginx -d movies.pekkis.eu -d api.movies.pekkis.eu`.

```nginx
server {
    listen 80;
    server_name movies.pekkis.eu api.movies.pekkis.eu;
    return 301 https://$host$request_uri;
}

# The website.
server {
    listen 443 ssl http2;
    server_name movies.pekkis.eu;
    # ssl_certificate / ssl_certificate_key: from certbot

    location / {
        limit_req zone=pgtm_web burst=30 nodelay;
        proxy_pass http://127.0.0.1:4321;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# The API: /v1/…, /openapi.json, /docs, and MCP at /mcp/{MCP_TOKEN}.
server {
    listen 443 ssl http2;
    server_name api.movies.pekkis.eu;
    # ssl_certificate / ssl_certificate_key: from certbot

    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # MCP (Streamable HTTP): responses may stream as server-sent events.
    location /mcp/ {
        # The token is in the path: keep it out of nginx's log (the API logs it redacted).
        access_log off;
        client_max_body_size 64k;
        limit_req zone=pgtm_slow burst=10 nodelay;
        proxy_pass http://127.0.0.1:3579;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # Fuzzy search costs the database the most.
    location /v1/films/search {
        limit_req zone=pgtm_slow burst=10 nodelay;
        proxy_pass http://127.0.0.1:3579;
    }

    location / {
        limit_req zone=pgtm_api burst=40 nodelay;
        proxy_pass http://127.0.0.1:3579;
    }
}
```

**Compression and headers.** Ubuntu's default `nginx.conf` turns `gzip on` but leaves `gzip_types` commented out, so only `text/html` is compressed. On 2026-10-19 [V], the site's JavaScript, CSS and the API's JSON went out uncompressed: MapLibre's chunk on `/fi/kartta` was 1.05 MB instead of 279 kB, and React's client 213 kB instead of 66 kB. Put this in the `http {}` block, for example as `/etc/nginx/conf.d/compression.conf`:

```nginx
gzip on;
gzip_vary on;                 # Vary: Accept-Encoding, so caches keep both versions apart
gzip_proxied any;
gzip_comp_level 5;
gzip_min_length 1024;
gzip_types text/css text/javascript application/javascript application/json
           image/svg+xml text/plain application/xml;
# Not text/event-stream: compressing MCP's server-sent events would hold them back.
server_tokens off;            # no nginx version in the Server header
```

Optionally, add HSTS in each `server { listen 443 … }` block above (no `includeSubDomains`, since other sites share the domain):

```nginx
add_header Strict-Transport-Security "max-age=31536000" always;
```

**Rate limits.** The `limit_req` lines above need their zones in the `http {}` block, for example as `/etc/nginx/conf.d/pgtm-limits.conf` **[A]** (not yet tried on the server):

```nginx
# Per client address. A page load is one request (assets come from the browser's cache or
# arrive within the burst); the website's own API calls go over the Compose network, past nginx.
limit_req_zone $binary_remote_addr zone=pgtm_web:10m  rate=5r/s;
limit_req_zone $binary_remote_addr zone=pgtm_api:10m  rate=10r/s;
limit_req_zone $binary_remote_addr zone=pgtm_slow:10m rate=2r/s;
limit_req_status 429;
```

The limits are generous for people and apps and stop one address from hammering the database. If a proxy or CDN is ever put in front of nginx, `$binary_remote_addr` becomes the proxy's address: set `real_ip_header` first.

**Check it after `nginx -t && systemctl reload nginx`:**

```sh
W=https://movies.pekkis.eu A=https://api.movies.pekkis.eu
js=$(curl -s $W/fi/ | grep -o '/_astro/[^"]*\.js' | head -1)
for u in $W/fi/ $W$js $A/v1/venues; do
  curl -s -o /dev/null -D - -H 'accept-encoding: gzip' "$u" | grep -i -E 'content-encoding|vary'
done   # each should say content-encoding: gzip and vary: Accept-Encoding
curl -s -o /dev/null -D - $W/fi/ | grep -i x-robots-tag   # noindex, nofollow until launch
```

These match `API_PORT=3579` and `WEB_PORT=4321`; use your own if they differ. `listen 443 ssl http2` works on every nginx version; from 1.25.1 on it's deprecated in favour of a separate `http2 on;`, which older versions reject as an unknown directive.

## Backups

The showtimes can be fetched again; their **history** can't: first and last seen, and removals. Back up the database, e.g. daily:

```sh
docker compose exec -T postgres pg_dump -U pgtm -Fc pgtm > backups/pgtm-$(date +%F).dump
```

Restore with `pg_restore -U pgtm -d pgtm --clean` inside the container.

## Checks after deploying

- `https://movies.pekkis.eu/fi/` shows the cities. `/fi/kartta` draws the map: the browser fetches its tiles and fonts from OpenFreeMap directly.
- `curl -I https://movies.pekkis.eu/fi/` includes `X-Robots-Tag: noindex, nofollow`.
- `https://api.movies.pekkis.eu/v1/health` answers `{"ok":true,…}`; the API docs are at `https://api.movies.pekkis.eu/docs`.
- MCP: add `https://api.movies.pekkis.eu/mcp/{MCP_TOKEN}` as a custom connector in Claude and ask "mitä Tampereella tänään illalla?".
