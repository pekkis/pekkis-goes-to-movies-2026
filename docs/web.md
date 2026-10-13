# Website (`apps/web-front`)

The public website: server-rendered pages that search engines can index, from our own API. Status: **a spike**. One working slice, the city page (`/fi/kaupungit/tampere`), proves the stack end to end.

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

## Styling pattern

- **`src/styles/theme.css.ts`:** `createThemeContract` defines the color tokens (`vars`). Light and dark values are set globally, following `prefers-color-scheme`, and `<html data-theme="light|dark">` overrides that. It also holds the spacing scale and breakpoints.
- **`sprinkles.css.ts`:** atomic layout, spacing and color classes on those tokens, with `mobile`, `tablet` and `desktop` conditions. Use sprinkles for layout in pages.
- **`recipes/`:** components with variants (`button({ tone, size })`). New shared components follow that pattern.
- **Per-component styles** live next to the component (`ScreeningList.css.ts`) and read `vars`, never raw colors.

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
