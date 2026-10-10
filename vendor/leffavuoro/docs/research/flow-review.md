# Live end-user flow review — 22 September 2026

Written as `FLOW_REVIEW.md` at the repository root and moved here on 2026-09-23, which is
where `CLAUDE.md` puts what was observed probing a site. The decision records in
`docs/archive/` and the source comments that cite it link to this path.

**Status, 22 September 2026: all six confirmed issues are fixed, verified and deployed.**
The outcome of each is recorded under its heading below, and the reasoning and measurements
are in `docs/archive/2026-09-app.md` and `docs/archive/2026-09-pipeline.md`. Merged to
`main` as `5d676314c`; Checks, the Pages deployment and IndexNow all green, and the three
client documents on leffavuoro.fi are byte-identical to that commit.

Two suggestions were **not** built, on the maintainer's instruction during the work not to
change the page's design: the "choose a cinema" shortcut at the top of a city page, and a
general-feedback link beside the screening report. Both are recorded as deferred in
`IDEAS.md` with that reason. One suggestion was **already fixed** before this review and is
marked below.

Reviewed https://leffavuoro.fi/ in Chrome, in one continuous session after the user confirmed clearing site data and cache. The initial page showed the fresh city/cinema chooser with Finnish selected and no saved cinema. State was intentionally retained during the journey to test language, date, reload, and return navigation. Clearing was user-confirmed, not independently inspected. No additional fresh-session tests are claimed.

This report supersedes the earlier local-source review. Production is newer than the local checkout: it has a home chooser, sharing/calendar menus, contextual error reporting, a status page, and privacy information. No product code was changed.

## Confirmed issues and recommended improvements

### 1. High: Swedish changes the page as well as the language

**FIXED (`33896ba16`, sw.js v220).** Swedish landing pages now exist at `/sv/teatteri/{slug}/` and `/sv/kaupunki/{slug}/`, one for every cinema and city the other two languages carry. The selector links three pages and never the app, every page carries an hreflang for all three, and the home chooser sends a Swedish reader to the Swedish page. 303 sitemap URLs became 454. Verified as a round trip: from any page, each language link lands on the same cinema or city and its selector links back to the page it came from.

Reproduced on both Helsinki city and Kino Engel theatre pages:

- `/en/city/helsinki/` → SV → `/?area=city%3AHelsinki&lang=sv`.
- `/teatteri/kino-engel-helsinki/` → SV → `/?area=engel-helsinki&lang=sv`.
- FI ↔ EN stays on equivalent static detail pages.
- Selecting EN after entering the Swedish app changes the app language but does not return to the static detail page.

The cinema/city is preserved, but layout, available controls, and programme scope change. On Kino Engel, the static page said no showtimes were published for the next few days, while the app displayed the previously selected 28 September. Both can be correct, but changing only the language appears to change availability.

Recommendation: provide equivalent Swedish detail pages, using the same page structure and date scope in all languages. Alternatively, unify these pages with the programme view. Until then, explicitly say that the Swedish link opens the full programme.

### 2. High: Home from an English detail page loses the visible language

**FIXED (`f216dd5bf`).** The wordmark is `/?lang={lang}` on every generated page, Finnish included, matching the CTA beside it. `/status/` and `/tietosuoja/` carry the language on their own links too, in the two commits below.

Fresh-session reproduction: Home → Helsinki → EN → Leffavuoro logo. The result was the Finnish home chooser. The logo link on the English city page is `/`; choosing English on a static page did not establish the corresponding home language.

Recommendation: carry the current language on Home links, e.g. `/?lang=en`. Apply the same rule consistently across city, theatre, status, and privacy pages.

### 3. High: returning from a screening report loses the screening context

**FIXED (`b7046828a`, sw.js v217).** The app sends `area` and `back`, `back` being the same `screeningUrl()` the draft quotes, built once. `/status/` prefers `back`, falls back to `area`, labels the link "Back to this screening", and rewrites the language into it when the reader changes language on that page. `back` is followed only when it resolves to this origin. The wordmark there stays Home.

Reproduction: Kino Engel → Hetki ennen valoa → 28 September 16:30 actions → “Rapportera felaktiga uppgifter”. The status/contact page correctly prepared an email link containing the film, cinema, date, time, and detailed screening URL. Switching the status page to English worked.

However, “← To showtimes” linked to `/?lang=en` and returned to the home chooser, losing the selected cinema and open film. The report route did not supply an area-aware return link.

Recommendation: retain an explicit internal return URL containing area, language, film, and date. Label the action “Back to this screening”. Preserve it when the status-page language changes.

### 4. Medium: English privacy navigation opens the Finnish section

**FIXED (`bd72b0064`, sw.js v218).** The app links to `/tietosuoja/?area=…&lang=…#{lang}`, and the privacy page rebuilds its wordmark, back link and two footer links from what it was given, labels in the reader's language. `<html lang="fi">` is left alone: the document holds all three sections.

From the English home page, “Privacy” opened `/tietosuoja/` at the Finnish heading and introduction. The document provides “Suomeksi”, “På svenska”, and “In English” anchor links, but the incoming link does not select the reader’s language.

Recommendation: link directly to the appropriate language section (`#en` or `#sv`), with language-preserving return navigation. Separate translated pages would also work.

### 5. Medium: Swedish film details contain an unlabelled Finnish synopsis

**FIXED (`a51c4db22`, sw.js v219).** A caption above the description names the language the text is in whenever it is not the reader's, and the paragraph carries `lang`. Not only Swedish: a Finnish reader is shown English text as often. No translation is invented and no advertised title moves.

The Swedish sheet for Hetki ennen valoa displayed Swedish controls and screening labels but a Finnish synopsis. The difference is visible in the actual movie sheet, not just inferred from source.

Recommendation: use a Swedish synopsis when available. Otherwise add a clear “Description available in Finnish” label. Keeping the cinema’s advertised movie title is reasonable; the description fallback should be explicit.

### 6. Medium: duplicate film cards make city comparison harder

**FIXED (`2814b4ffb`).** City pages fold films with the app's own two signals, the normalised title key and the TMDB id, unioned. 7 within-day collisions became 0. A merged heading never advertises one audio version of a card holding both, and format joins language in splitting per screening where it differs, so nothing the fold covers is lost. Theatre pages are unchanged.

The live Helsinki static city page contained separate same-day cards for “Keltaiset Kirjeet” and “Keltaiset kirjeet”, and “Myrskyn ikkuna” and “Myrskyn Ikkuna”. It also showed Coyote vs. Acme and Kojootti vs. ACME separately.

Recommendation: group confirmed matches across providers using stable film identity, with normalized titles as a cautious fallback. Keep audio/version differences attached to individual screenings. This makes comparison across cinemas easier without hiding dubbed versions.

## What worked in the tested journey

| Journey | Observed result |
|---|---|
| Fresh Home → Helsinki | Clear city list opened the corresponding city page. |
| City FI → EN | Same city and static-page structure. |
| English city → Kino Engel theatre | Correct English theatre page and an English “All cinemas – Helsinki” return link. |
| Main app SV → EN → SV → FI | Controls translated while the selected cinema remained. |
| Tomorrow + By time → English | By time remained selected and programme rows translated. |
| Search with no matches | Explained the empty state; offered wider search and Clear filters. |
| Cinema picker search “engel” | Found Kino Engel directly. |
| No shows on selected date | Offered “Next screenings → Mo 28.9.”; clicking it loaded films. |
| Date beyond initial chips | 28 September remained selected through Swedish translation; choosing 30 September in the calendar remained selected after switching to English. |
| Film details and reload | Reload reopened the same film sheet with the same theatre and Swedish language. |
| Film Back / Forward / close | Back removed the film fragment; Forward reopened the sheet; close returned visibly to the programme. |
| Ticket handoff | Opened Kino Engel in a new tab on the correct film page, displaying 28 and 30 September at 16:30. No purchase was attempted. |
| Report incorrect screening | Generated a contextual email link with film, theatre, date, time, and screening URL. No email was sent. |
| Status SV → EN | Translated the page in place and retained the report details. |

## End-user flow and design ideas

A straightforward user journey should be:

1. Choose a city or cinema.
2. Choose a date and, if needed, a film search or filter.
3. Compare films or switch to By time.
4. Open a film for description, trailer, and other showtimes.
5. Choose a screening to continue on the cinema’s site.
6. Return to the same programme, or use the screening menu to share, add to calendar, or report a problem.

Language switching should translate whichever step the visitor is on, retaining the same page type, entity, date, and meaningful context.

Additional ideas:

- Move a “Choose cinema” shortcut near the top of static city pages. The individual cinema links currently come after a long two-day programme.
  - **Deferred**, with the general-feedback link below: both move or add something a reader
    sees, and the maintainer asked during this work for no change to the page's design.
    Recorded in `IDEAS.md`.
- Show the next known screening date directly on an empty theatre landing page, where available. Kino Engel’s app offered 28 September, but its landing page gave only the generic no-upcoming-showtimes message.
  - **BUILT (`669e46a9a`).** 25 of the 134 Finnish theatre pages carried the generic
    sentence; each now names its cinema's next known date after it, in the page's language,
    in the same element. Kino Engel reads “Seuraava näytös: Ma 28.9.”
- Make “Share / Calendar / Report” easier to discover than the small screening action menu, while preserving the existing contextual functionality.
- Add a direct general-feedback link for usability ideas. Reporting incorrect screening data is already implemented and should remain separate.
  - **Deferred**, see the cinema shortcut above.
- Label external ticket destinations consistently so users know whether they will reach a specific screening or a cinema’s film/programme page.
- Minor localization polish: English/Swedish programme timestamps still contained Finnish “klo”; the status footer navigation accessible name remained Finnish “Lisätietoja”.
  - **“klo”: already fixed before this review.** `atTime` is `klo`/`kl.`/`at` in the app and
    `at` is `klo {t}`/`kl. {t}`/`at {t}` on the status page; re-measured against the current
    code, both are translated in all three languages.
  - **“Lisätietoja”: FIXED (`b7046828a`).** The status footer nav's accessible name is
    translated with the rest.

## What was verified after the fixes, 22 September 2026

Automated, on the merged commit:

- The unit suite, 3121 tests, twice: plain and with `GITHUB_ACTIONS=true`. Both OK with the
  five expected Pillow skips and no `ResourceWarning`. One failure that was already red on
  `main` before this work, an unknown `LI` language code in the committed Finnkino data, was
  traced and fixed (`cc21ba830`); it was not part of the review.
- `tests/browser/`, 37 tests, in **Chromium 151.0.7922.34 and WebKit 26.5**.
- 116 flow checks in the same two engines, at **1280×900 desktop and 393×852 phone**, each
  scenario in a brand-new browser context so cookies, cache, local storage and the service
  worker start empty, with state preserved only inside a scenario. All passed, first against
  a local server on the merged tree and then against the deployed site.

What those 116 cover: the language round trip on a city page and a theatre page in all
three directions; the wordmark from each language; the next-known-date line in all three
languages; opening a film, its dots menu and the report route, then the labelled way back,
a language change on the status page rewriting it, and following it back to the same
screening; the privacy link naming the section and returning in the reader's language;
every synopsis agreeing with its language caption over six films; reload, Back and Forward
on an open film; the day, the view segment and a filter surviving two language changes; and
every ticket on a Swedish city page still leaving for its cinema's own host.

Not done: no ticket was bought and no feedback email was sent.

Not verified: real devices, other cinemas and providers beyond those named, offline
behaviour, trailer playback, cross-device shared links, full keyboard accessibility, and
every filter combination. Those were out of scope of this pass as they were of the review.

## Scope and limitations

Representative desktop flow review covering Home, Helsinki city pages, Kino Engel theatre pages, the programme, movie detail, status/reporting, privacy, and one external cinema handoff. This is not an exhaustive audit of every cinema, mobile device, or provider.

Sharing and calendar menu entries were verified as present. The share action was clicked, but successful delivery/copy was not confirmed from the page; no recipient was selected. Calendar export/import was not completed. Trailer playback, purchases, email delivery, offline behavior, cross-device shared-link opening, full keyboard accessibility, mobile layouts, favourite persistence, and every filter combination remain unverified. No claim is made that all these flows pass.

Earlier local checks: 31 area/language routing tests and 3 film direct-load source checks passed. The 50-test landing-page run had 16 failure entries associated with missing current showtime content against old local data (areas timestamp 6 September). These local results are not evidence of a production outage. Live programme data showed an update on 22 September.

Suggested priority: fix Swedish page continuity, language-preserving Home links, and the report return path first; then privacy routing, translation fallbacks, and city-card grouping.
