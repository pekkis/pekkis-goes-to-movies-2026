# Website (`apps/web-front`)

The public website: server-rendered pages that search engines can index, from our own API. Status: **early**. City and venue pages and a venue map, all server-rendered; React islands make them live.

## Pages

| URL                            | Page                                                                                                                                   | Data                                                                    |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `/`                            | redirects to `/fi/`                                                                                                                    | –                                                                       |
| `/fi/`                         | cities, as links                                                                                                                       | `/v1/venues`                                                            |
| `/fi/kaupungit/{city}`         | a city's day: its venues, then every screening in start order                                                                          | `/v1/screenings?city=`                                                  |
| `/fi/elokuvateatterit/{venue}` | a venue's day, film by film: address, map link, the cinema's website, each film (alphabetical) with its showtimes                      | `/v1/screenings?venue=`                                                 |
| `/fi/kartta`                   | every venue on a map: clusters when zoomed out, a popup per pin linking to the venue page; below it, the same venues as a list by city | `/v1/venues`                                                            |
| `/fi/haku`                     | search: days, a place and maybe a film name, then narrow by time of day, venue and film ([below](#search-fihaku))                      | `/v1/screenings?bbox=`, `/v1/films/search`, `/v1/films/{id}/screenings` |

- **Slugs** are derived from names (`src/lib/cities.ts`, `src/lib/venues.ts`):
  - a city: `Jyväskylä` → `jyvaskyla`;
  - a venue: its name, plus the city unless the name already says it: `plevna-tampere`, `kino-myyri-vantaa`, `studio-123-kouvola`. Names alone collide ("Studio 123", "Maxim", "Kinopalatsi"). This is unique for all 88 venues on 2026-10-13, and a test covers the rule.
  - If a cinema is renamed, its old slug stops working: add a redirect for it then.
- **`?date=YYYY-MM-DD`** picks the day on both page types. It defaults to today in Helsinki; a malformed date falls back to today. The canonical URL leaves the date out, so dated variations count as one page.
- **Swedish and English** will get their own path words (`/sv/biografer/…`, `/en/cinemas/…`) with the same slugs.

## Stack and why

| Need       | Choice                                                        | Why                                                                                                                                                                                                                                                                  |
| ---------- | ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Framework  | **Astro 7**, `output: "server"`, `@astrojs/node` (standalone) | SSR for indexing: every page is complete HTML first, and React islands hydrate where the page is interactive or live. Vite and Vitest, like the rest of the workspace. Chosen over TanStack Start (whose server components are experimental) and Next.js (not Vite). |
| Components | **React 19** via `@astrojs/react`                             | The team's component language. Astro renders React to static HTML; only `client:*` components hydrate.                                                                                                                                                               |
| Styling    | **Vanilla Extract**: `css`, `sprinkles`, `recipes`, `dynamic` | Typed, zero-runtime CSS: static files at build time, nothing to hydrate.                                                                                                                                                                                             |
| API access | `hc<AppType>` from `hono/client`                              | Types come from `@pgtm/backend` with no code generation.                                                                                                                                                                                                             |

## How a page works

```
request → src/middleware.ts      sets locals.api (API_URL), noindex + cache headers
        → src/pages/…/*.astro    thin: calls a loader, picks a layout
        → src/lib/pages.ts       loader: API calls, validation, 404 → plain data
        → React components       static HTML by default; `client:load` etc. only for islands
```

- **`.astro` files stay thin.** Logic goes in `src/lib/` as plain TypeScript, where `tsc` and unit tests reach it.
- **Interactive and live UI is written in React islands.** It's the team's language, and React's runtime (about 69 kB gzipped, decided 2026-10-13) is a fair price that browsers cache across pages. Don't hand-write DOM scripts for UI; the map is the exception, because MapLibre does its own drawing.
- **Server first:** an island is rendered on the server, so the HTML is complete and correct before any JavaScript runs, for search engines, slow phones and people without JavaScript. Hydrate with `client:idle` unless the UI must react at once.
- **Static where nothing changes:** `DateNav` is a plain GET form with the browser's own `<input type="date">`. Phones show their system picker, and accessibility comes from the browser.
- **React Aria was tried and dropped (2026-10-13).** Its `DatePicker` island cost about 77 kB gzipped on top of React: translations for 34 languages, which its locale plugin trims to 61 kB, and every calendar system, which `DatePicker` can't drop. For a date choice, the native input is enough. Revisit per widget (film search, map filters), weighing what a library adds on top of React.
- **Dates and times are Temporal** (`@pgtm/model/time` for the logic, shared with the backend and fetcher). `src/lib/temporal.ts` loads `temporal-polyfill` (about 20 kB gzipped) only where `Temporal` is missing, which today means Safari. It's checked in Chrome both natively and with `Temporal` removed. Formatting is `Intl` in `src/lib/time.ts`, in `Europe/Helsinki` explicitly with a 23-hour clock, so server and browser, native and polyfill print the same (`00.30`, never `0.30`).
- **UI text** is in `src/lib/text.ts` (Finnish), ready to move to an i18n catalogue (Lingui is the plan). Routes are under `/fi/`; `sv` and `en` are configured but have no pages yet.

## Visual style: grey mockup

**Until user testing, the website is a grey wireframe made of boxes** (AGENTS.md has the rule). There's no visual identity yet, and we don't want testers judging colors and polish when we ask about structure and content.

- **Neutral greys only:** the `vars.color` tokens; `accent` is a dark grey (light grey in dark mode). Links are recognized by their underline.
- **Boxes:** plain rectangles with visible 1 px borders. No `borderRadius`, `boxShadow`, gradients or decorative images.
- **System font** and plain sizes. No icons for decoration, no animation.
- **Never color alone for meaning:** sold-out, few-left and the like are words.
- **Exceptions, required as is:** the TMDB logo and notice, and the map tiles (OpenFreeMap's grey `positron` and `dark` styles). MapLibre's pins and clusters use the grey `accent` token.
- **Later:** the visual identity changes token values and recipes, not components. That's why components never use raw colors.

## Live showtimes: one clock, reusable

Showtimes say whether a show has started, starts soon or is later, and they keep saying it correctly while the page stays open.

| Piece                       | Where                      | Use                                                                                                                                                                                                                                                                                           |
| --------------------------- | -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `showStatus(startsAt, now)` | `src/lib/show-status.ts`   | Pure: `started` / `soon` (within `SOON_MINUTES`, 60) / `later`, the label ("alkanut", "alkaa 25 min päästä"), and `ticketsOpen` (until `TICKETS_AFTER_START_MINUTES`, 15, after the start: cinemas sell during the ads). Compares instants, so shows after midnight and other days just work. |
| `nowAtom`                   | `src/components/clock.tsx` | A jotai atom holding the current time. While anything reads it, it ticks once a minute (`onMount`).                                                                                                                                                                                           |
| `useNow()`                  | `src/components/clock.tsx` | The current time, e.g. for `collapseStarted` (started shows behind "Näytä alkaneet" while something is still to come).                                                                                                                                                                        |
| `useShowStatus(startsAt)`   | `src/components/clock.tsx` | A show's live status. **Use this wherever a showtime is shown.**                                                                                                                                                                                                                              |
| `<ClockIsland now={iso}>`   | `src/components/clock.tsx` | The root of every island that shows showtimes: a jotai `Provider` (its own store), seeded with the server's time by `useHydrateAtoms`.                                                                                                                                                        |

- **Pattern for a new island:** pass the screenings and `now={Astro.locals.now.toISOString()}` (set per request by the middleware) to a component that wraps its content in `<ClockIsland now={now}>`. Presentational components (`ScreeningList`, `FilmProgramme`, `Showtime`) only call `useShowStatus` or `useNow`.
- **Why each island has its own store:** on the server, jotai's default store would be shared by every request in the Node process, so one request's time would stick for the next. A `Provider` per island gives each render a fresh store. A test covers this. The server's time is also the store's starting value, so hydration matches the server's HTML.
- **How states look (grey only):** started is muted with "alkanut"; soon gets a strong border and "alkaa N min päästä"; the label always says it.
- **Tests:** `test/clock.tsx` fixes the clock with fake timers (`freezeClockAt`), renders inside a provider (`renderWithClock`) and moves time (`advanceMinutes`).

## React

- **React 19, written the modern way:** `use(Context)`, `<Context value>`, `ref` as a prop, function components only.
- **Shared client state: jotai.** Atoms instead of hand-written contexts and stores; an atom's `onMount` subscribes to external sources (the clock's minute timer). Each island root is a jotai `Provider`, because on the server the default store would be shared between requests. Never `setState` inside an effect to sync with the outside world.
- **Lint:** oxlint's React plugin enforces the rules of hooks, exhaustive effect dependencies and no `setState` in effects. `react-in-jsx-scope` is off, because the automatic JSX runtime doesn't need it.
- **Test helpers aren't hooks:** don't name them `use…`, or the hook rules apply to them (`freezeClockAt`, not `useFixedClock`).

## User interface rules

1. **Mobile first.** The phone layout is the default style; wider layouts are added with `min-width` conditions. Design and test at phone width (about 390 px) first.
2. **Container queries, always when possible.** A component adapts to the space it's given, not to the screen. So it works the same in a page column, a sidebar or a popup.
   - Use `@container (min-width: …)` from `src/styles/containers.ts` (`minWidth("wide")`).
   - Responsive sprinkles (`wide`, `widest`) query the nearest container; `main` is one.
   - A component whose layout changes declares its own container (`containerType: "inline-size"`, like `ScreeningList`).
   - Viewport `@media` queries only where a container can't work. User preferences (`prefers-color-scheme`, `prefers-reduced-motion`) aren't layout and are fine.
3. **Lists of films are alphabetical by title** (Finnish order: Å, Ä, Ö after Z; `byTitle` in `src/lib/films.ts`). A film's showtimes stay in time order, and so do the city page's screenings, which are a timetable, not a list of films.
4. **The design system is the Vanilla Extract theme, and the theme is the source of truth.** Every design value is a token in `src/styles/theme.css.ts`: color, spacing, font sizes and weights, borders and fixed sizes. Container widths live in `containers.ts`. Components and pages use `vars` (or sprinkles and recipes built on them), never literal colors, rem/px sizes or fonts. A new value goes into the theme first. When the visual identity arrives, it changes the theme, not the components.

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

## Search (`/fi/haku`)

Built for the mockup presentation and the first user tests (2026-10-23). It shows the two ways people look for something to watch, on one page, in either order:

- **Time and place first:** check days, choose a city or "Käytä sijaintiani" and a radius, then narrow by time of day, venue and film.
- **Film first:** type a film name. Its screenings on the checked days come up nationwide, or within the radius once a place is set.

**The query** is a plain GET form, server-rendered, which works without JavaScript ([SearchForm.tsx](../apps/web-front/src/components/SearchForm.tsx)):

| Parameter      | Meaning                                                                                                                                           |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `paiva` (0–7×) | days, from today's programme day and the six after it; none or invalid means today                                                                |
| `kaupunki`     | a city slug; its centre is the mean of its venues' coordinates. Wins over `lat`/`lon`                                                             |
| `lat`, `lon`   | the browser's location, filled in by the `LocateButton` island, which clears `kaupunki` and shows "Oma sijainti"; like a city, it waits for "Hae" |
| `sade`         | radius: 5, 10, 15, 20, 25 (default), 50, 100 or 200 km                                                                                            |
| `elokuva`      | a film name, two characters or more: up to 3 films from `/v1/films/search`                                                                        |

**Locating** (`LocateButton`) always ends: found, or a message for each failure (permission denied, location unavailable, timed out). The browser's own `timeout` starts only once permission is given, so a dismissed permission prompt (Firefox) or a macOS without location services for the browser can leave the request unanswered. A 20-second watchdog ends the wait, and the button can be pressed again; a late answer to an abandoned request is ignored (seen on the live site, 2026-10-19 [V]).

**Loading** ([lib/search.ts](../apps/web-front/src/lib/search.ts)):

- Without a place or a film, only the form is shown, so the whole country is never loaded.
- With a place, each day is loaded with `bbox` (`bboxAround` from `@pgtm/model/geo`), and screenings beyond the radius are dropped by `distanceKm`.
- With a film, each film's screenings are loaded per day, with the `bbox` too when a place is set.

**Facets** ([lib/facets.ts](../apps/web-front/src/lib/facets.ts), the `SearchResults` island):

- There are three: time of day (before 12, 12–17, 17–21, 21 and later, where a show after midnight counts as late), venue and film (alphabetical).
- **Venues are listed by provider**, nearest first within each. A provider with two or more venues in the results gets its own checkbox, which checks or unchecks all of them, and shows half-checked when only some are. A season ticket holder can pick "Finnkino" in one click (maintainer's feedback, 2026-10-19). A cinema that is its own provider is a plain row.
- Nothing checked means everything is shown.
- Each value's count applies the _other_ facets. A value that would show nothing is disabled, and unchecking can still lead to an empty result, which the page says.
- Long lists get a type-to-narrow field; the venue field matches the city and the provider too.
- The selection is a jotai atom in the island's own store (its `ClockIsland`).

## Known gaps

- **Search:**
  - facet choices are not in the URL, so a narrowed view can't be shared or bookmarked;
  - there is no address search, only a city or the browser's location;
  - a wide search is heavy. Seven days around Helsinki is about 3 MB of HTML, because the screenings are rendered and also passed to the island as props. nginx's gzip brings it to roughly a twentieth. Trimming the island's props or rendering only the first part would help.

- **Typecheck:** `astro check` doesn't support TypeScript 7. `tsc` checks the `.ts`/`.tsx` files (`src/env.d.ts` declares `*.astro` modules), and the `.astro` templates themselves go unchecked.
- **Formatting and linting:** oxfmt doesn't format `.astro` files. oxlint does check their frontmatter.

## Next

- Map (MapLibre GL + OpenFreeMap tiles) as one island beside the list.
- Film and venue pages, sitemap, JSON-LD (`MovieTheater`, `ScreeningEvent`), `hreflang`.
- Lingui; `sv` and `en`.
- Web Docker image + nginx; a `/v1/cities` endpoint, if the city list grows costly.
