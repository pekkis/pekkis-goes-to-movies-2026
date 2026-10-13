# Website (`apps/web-front`)

The public website: server-rendered pages that search engines can index, from our own API. Status: **early**. City and venue pages, both server-rendered with no JavaScript.

## Pages

| URL                            | Page                                                                                                                                   | Data                    |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| `/`                            | redirects to `/fi/`                                                                                                                    | –                       |
| `/fi/`                         | cities, as links                                                                                                                       | `/v1/venues`            |
| `/fi/kaupungit/{city}`         | a city's day: its venues, then every screening in start order                                                                          | `/v1/screenings?city=`  |
| `/fi/elokuvateatterit/{venue}` | a venue's day, film by film: address, map link, the cinema's website, each film with its showtimes                                     | `/v1/screenings?venue=` |
| `/fi/kartta`                   | every venue on a map: clusters when zoomed out, a popup per pin linking to the venue page; below it, the same venues as a list by city | `/v1/venues`            |

- **Slugs** are derived from names (`src/lib/cities.ts`, `src/lib/venues.ts`):
  - a city: `Jyväskylä` → `jyvaskyla`;
  - a venue: its name, plus the city unless the name already says it: `plevna-tampere`, `kino-myyri-vantaa`, `studio-123-kouvola`. Names alone collide ("Studio 123", "Maxim", "Kinopalatsi"). This is unique for all 88 venues on 2026-10-13, and a test covers the rule.
  - If a cinema is renamed, its old slug stops working: add a redirect for it then.
- **`?date=YYYY-MM-DD`** picks the day on both page types. It defaults to today in Helsinki; a malformed date falls back to today. The canonical URL leaves the date out, so dated variations count as one page.
- **Swedish and English** will get their own path words (`/sv/biografer/…`, `/en/cinemas/…`) with the same slugs.

## Stack and why

| Need       | Choice                                                        | Why                                                                                                                                                                                                                       |
| ---------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Framework  | **Astro 7**, `output: "server"`, `@astrojs/node` (standalone) | SSR for indexing. Pages ship no JavaScript unless a component asks for it. Vite and Vitest, like the rest of the workspace. Chosen over TanStack Start (whose server components are experimental) and Next.js (not Vite). |
| Components | **React 19** via `@astrojs/react`                             | The team's component language. Astro renders React to static HTML; only `client:*` components hydrate.                                                                                                                    |
| Styling    | **Vanilla Extract**: `css`, `sprinkles`, `recipes`, `dynamic` | Typed, zero-runtime CSS: static files at build time, nothing to hydrate.                                                                                                                                                  |
| API access | `hc<AppType>` from `hono/client`                              | Types come from `@pgtm/backend` with no code generation.                                                                                                                                                                  |

## How a page works

```
request → src/middleware.ts      sets locals.api (API_URL), noindex + cache headers
        → src/pages/…/*.astro    thin: calls a loader, picks a layout
        → src/lib/pages.ts       loader: API calls, validation, 404 → plain data
        → React components       static HTML by default; `client:load` etc. only for islands
```

- **`.astro` files stay thin.** Logic goes in `src/lib/` as plain TypeScript, where `tsc` and unit tests reach it.
- **No JavaScript unless a feature needs it.** The city page ships none: `ScreeningList` is static HTML, and `DateNav` is a plain GET form with the browser's own `<input type="date">`. Phones show their system picker, and accessibility comes from the browser.
- **Islands only where interaction needs them**, and their size is measured before they're added. React's client runtime alone is about 69 kB gzipped, loaded by the first island on a page.
- **Progressive enhancement:** an island first renders something that works without JavaScript.
- **React Aria was tried and dropped (2026-10-13).** Its `DatePicker` island cost about 77 kB gzipped on top of React: translations for 34 languages, which its locale plugin trims to 61 kB, and every calendar system, which `DatePicker` can't drop. For a date choice, the native input is enough. Revisit per widget (film search, map filters): Ark UI, react-day-picker, or Preact islands.
- **Times are formatted in `Europe/Helsinki` explicitly** (`src/lib/time.ts`), so server and browser always agree whatever their own time zones.
- **UI text** is in `src/lib/text.ts` (Finnish), ready to move to an i18n catalogue (Lingui is the plan). Routes are under `/fi/`; `sv` and `en` are configured but have no pages yet.

## Visual style: grey mockup

**Until user testing, the website is a grey wireframe made of boxes** (AGENTS.md has the rule). There's no visual identity yet, and we don't want testers judging colors and polish when we ask about structure and content.

- **Neutral greys only:** the `vars.color` tokens; `accent` is a dark grey (light grey in dark mode). Links are recognized by their underline.
- **Boxes:** plain rectangles with visible 1 px borders. No `borderRadius`, `boxShadow`, gradients or decorative images.
- **System font** and plain sizes. No icons for decoration, no animation.
- **Never color alone for meaning:** sold-out, few-left and the like are words.
- **Exceptions, required as is:** the TMDB logo and notice, and the map tiles (OpenFreeMap's grey `positron` and `dark` styles). MapLibre's pins and clusters use the grey `accent` token.
- **Later:** the visual identity changes token values and recipes, not components. That's why components never use raw colors.

## User interface rules

1. **Mobile first.** The phone layout is the default style; wider layouts are added with `min-width` conditions. Design and test at phone width (about 390 px) first.
2. **Container queries, always when possible.** A component adapts to the space it's given, not to the screen. So it works the same in a page column, a sidebar or a popup.
   - Use `@container (min-width: …)` from `src/styles/containers.ts` (`minWidth("wide")`).
   - Responsive sprinkles (`wide`, `widest`) query the nearest container; `main` is one.
   - A component whose layout changes declares its own container (`containerType: "inline-size"`, like `ScreeningList`).
   - Viewport `@media` queries only where a container can't work. User preferences (`prefers-color-scheme`, `prefers-reduced-motion`) aren't layout and are fine.
3. **The design system is the Vanilla Extract theme, and the theme is the source of truth.** Every design value is a token in `src/styles/theme.css.ts`: color, spacing, font sizes and weights, borders and fixed sizes. Container widths live in `containers.ts`. Components and pages use `vars` (or sprinkles and recipes built on them), never literal colors, rem/px sizes or fonts. A new value goes into the theme first. When the visual identity arrives, it changes the theme, not the components.

## Styling pattern

- **`src/styles/theme.css.ts`:** `createThemeContract` defines every token (`vars`). Only the colors differ between light and dark mode; light and dark follow `prefers-color-scheme`, and `<html data-theme="light|dark">` overrides that.
- **`src/styles/containers.ts`:** the container widths (`wide` 40 rem, `widest` 64 rem) and `minWidth()`. It's a plain module because `.css.ts` files may only export data (a function there fails the build), and because CSS can't use custom properties in container conditions.
- **`sprinkles.css.ts`:** atomic layout, spacing and color classes on the tokens, with `narrow` (the default), `wide` and `widest` container conditions. Use sprinkles for layout in pages.
- **`recipes/`:** components with variants (`button({ tone, size })`). New shared components follow that pattern.
- **Per-component styles** live next to the component (`ScreeningList.css.ts`) and read `vars` only.
- **Vanilla Extract only, for `.astro` files too.** A style is just a class-name string, so `.astro` files use it as `class={css.page}` (`Base.astro` ↔ `Base.css.ts`), and React components as `className=`. No Astro `<style>` blocks and no inline styles.
- **`pnpm check` builds the website**, because some Vanilla Extract errors only show at build time.

## The map (`/fi/kartta`)

- **Library:** MapLibre GL JS (BSD-3), chosen over Leaflet (2026-10-13) for vector maps, built-in clustering and popups, and active development. It's written without React: a plain Astro `<script>` mounts `src/lib/map/venue-map.ts`, so React stays off this page too.
- **Cost:** one script, about 279 kB gzipped (Leaflet with clustering would be about 51 kB). Only `/fi/kartta` loads it; every other page stays JavaScript-free.
- **Tiles: OpenFreeMap** [V 2026-10-13]: free, commercial use allowed, no key, no limits. Required credit: "OpenFreeMap © OpenMapTiles Data from OpenStreetMap", which MapLibre adds itself. Styles: `positron` (light), `dark`. Self-hosting a Finland PMTiles extract is the fallback if we ever need independence.
- **Labels are in Finnish:** `localizeLabels` rewrites the style's place labels to `name:fi`, then the Latin-script name, then the local one ("Tukholma", "Pietari"). The styles default to English.
- **Theme:** the map style follows `prefers-color-scheme` (and `<html data-theme>`). Pins and clusters use our accent token; MapLibre's popup is themed in `map.css.ts`.
- **Clustering:** a GeoJSON source with `cluster: true` (radius 48 px, up to zoom 12). Clicking a cluster zooms to where it splits; clicking a pin opens a popup with the name, the address and a link to the venue page. Popup content is built with `textContent`, never HTML strings.
- **Worker:** MapLibre 6 loads its web worker from next to its own file, which bundling breaks, so `venue-map.ts` imports `maplibre-gl/dist/maplibre-gl-worker.mjs?url` and calls `setWorkerUrl`.
- **Without JavaScript,** the map container stays `hidden` and the list by city is the page. That list is also the keyboard and screen-reader route to every venue.
- **Testing:** GeoJSON, bounds, labels and popup content have unit tests. The map itself needs WebGL, so it's checked in a real browser (headless Chrome: clusters, popup, link, both themes) when it changes.

## Configuration (runtime)

| Variable       | Default                 | Meaning                                                                                                                                 |
| -------------- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `API_URL`      | `http://127.0.0.1:3000` | Our API, as the server reaches it.                                                                                                      |
| `INDEXING`     | `off`                   | `on` drops `noindex` (meta tag and `X-Robots-Tag`). **Only for production, and only after every cinema has been notified** (AGENTS.md). |
| `HOST`, `PORT` | `localhost`, `4321`     | The standalone Node server.                                                                                                             |

They're declared with `access: "secret"` in `astro.config.ts`, which in Astro means "read at runtime". `public` values would be inlined at build time, and the built server would ignore the deployment's settings.

## Attribution

Every page carries the following (`src/layouts/Base.astro`). A test checks the TMDB part.

- the TMDB logo (`public/tmdb-logo.svg`, TMDB's official alternate short logo) and TMDB's notice;
- the OpenStreetMap credit;
- a note that tickets are always bought on the cinema's own page.

Ratings are not shown yet. When they are, they're opt-in and credit OMDb.

## Running

```sh
pnpm db:up && pnpm api:dev          # the API on :3000
pnpm web:dev                        # the website on http://localhost:4321/fi/
pnpm web:build && node apps/web-front/dist/server/entry.mjs   # production server
```

`pnpm web:dev` puts Astro 7's dev server in the background: use `pnpm --filter @pgtm/web-front exec astro dev stop`, or `… status`, or `… logs`.

## Testing

- `test/lib/`: loaders and helpers, with `fakeFetch` from `test/fixtures.ts`. No network.
- `test/components/`: Testing Library under `// @vitest-environment happy-dom`.
- `test/pages/`: Astro's Container API renders a real page, with a fake API passed in `locals`.

## Known gaps

- **Typecheck:** `astro check` doesn't support TypeScript 7. `tsc` checks the `.ts`/`.tsx` files (`src/env.d.ts` declares `*.astro` modules), and the `.astro` templates themselves go unchecked.
- **Formatting and linting:** oxfmt doesn't format `.astro` files. oxlint does check their frontmatter.

## Next

- Map (MapLibre GL + OpenFreeMap tiles) as one island beside the list.
- Film and venue pages, sitemap, JSON-LD (`MovieTheater`, `ScreeningEvent`), `hreflang`.
- Lingui; `sv` and `en`.
- Web Docker image + nginx; a `/v1/cities` endpoint, if the city list grows costly.
