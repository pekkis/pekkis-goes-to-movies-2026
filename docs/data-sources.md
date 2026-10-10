# Data sources

Finnkino and BioRex investigated on 2026-10-09, Nexxo on 2026-10-10; all three adapters are implemented. Markers: **[V]** = verified with our own request, **[A]** = assumed, or read from a third-party source.

---

## BioRex

### Overview

- `biorex.fi` is a WordPress site (Polylang fi/sv/en, Yoast, custom theme) **[V]**.
- The ticket shop `webshop.biorex.fi` is AngularJS + Express **[V]**. **The platform is MyCloudCinema**: the cinema settings contain `webhook_url: https://api.biorex.mycloudcinema.com/…` **[V]**. The HTML's `<meta name="author" content="Unique X">` points to the developer (Unique X) **[A]**.
- According to Leffavuoro, the same MyCloudCinema `/webservices` API is used by Cine Mäntsälä (`mantsala.cine.fi`) and Gilda (`*.mycloudcinema.com`) **[A]**. The adapter can therefore later become a generic MyCloudCinema adapter.
- **Implementation:** [src/providers/biorex/](../packages/fetcher/src/providers/biorex/), run with `pnpm pull`.
- `robots.txt` allows everything (`User-agent: * / Disallow:`) **[V]**. The terms of service contain no ban on scraping.

### Webshop JSON API (no authentication, GET)

Every response is wrapped as `{"data": [...], "resultCode": 0}` **[V]**.

**Values profiled on 2026-10-09 (1,044 showtimes, 12 cinemas, 7 days) [V]:**

- `show_time` and `show_time_end` are UTC. `business_date` looks like `"2026-10-09T00:00:00.000Z"`; only the date part is used.
- **Languages:**
  - `audio_lang`: `EN`, `FI`, `SE` (= Swedish), `IT`, `DE`.
  - `movie_audio_style_id`: 1 = original language, 2 = dubbed.
- **`subtitle_lang`:** `"Suomi & Ruotsi -"` (Finnish & Swedish), `"SE"` or `"-"` (= no subtitles).
- **`title_extension`:** `null`, `FI DUB`, `SWE DUB`, `ORIG`, `FI`, `ATMOS` or `FI ATMOS`. The language labels repeat what the language fields already say; the only new information is `ATMOS`.
- **`rating`:** an icon file name, e.g. `rating_fi_12.svg` or `rating_fi_s.svg`.
- **`screen_name`:** `Sali 3`, `4 Plus`, `1 PRIME` and `6 REX (K-18)`. REX screens are K-18.
- **`premiere`:** 1 on about half of the rows, so it means "new film", not a premiere screening. The field is **not** used.
- **`bookable` and `allow_purchases`:** 0 when sales have closed (e.g. the show has already started).
- **`version_*` flags:** only `digital` and `atmos` were in use; the rest were 0. The parser reports unknown flags.
- **Cinemas:**
  - `offline: 1` and an `xxx` name prefix mark closed cinemas, and `screen_count: 0` is the company itself (id 11).
  - Tripla and Redi have empty `city`, `address` and `postal_code`, but coordinates are present.
- **Poster** (**not used**: posters come from TMDB): `https://webshop.biorex.fi/media/posters/{movie_id}/1080/{movie_poster}` **[V]**. Width 1080 is the one that works: 300, 500 and `original` return 404, and 54 is a tiny thumbnail.

| Endpoint                                                                                 | Status | Description                                                                   |
| ---------------------------------------------------------------------------------------- | ------ | ----------------------------------------------------------------------------- |
| `/webservices/cinemas/getCinemasList`                                                    | [V]    | All cinemas                                                                   |
| `/webservices/show_times/getShowTimes?cinema_id=1&date=2026-10-09`                       | [V]    | One cinema, one day                                                           |
| `/webservices/show_times/get?id=431685`                                                  | [V]    | A single show + description HTML, `screen_info`, `premiere`, `preshow_length` |
| `/webservices/show_times/getShowTimesDays?cinema_id&date&number_of_days`                 | [V]    | Several days at once. **The adapter uses this.**                              |
| `/webservices/show_times/getMovieShowTimes?cinema_id&movie_id`                           | [A]    |                                                                               |
| `/webservices/show_times/getPlayingNow`, `getComingSoon`, `getPremieres`, `getShowDates` | [A]    |                                                                               |
| `/webservices/cinemas/getCinemas`                                                        | [A]    |                                                                               |
| `/webservices/show_times/search` (POST)                                                  | [A]    |                                                                               |

**Cinema fields:** `cinema_id, cinema_name, city, address, latitude, longitude, screen_count, number_of_seats, ticket_prices, time_zone, external_id, offline…`

**Showtime fields:** `show_time_id, movie_id, movie_version_id, title, title_extension, cinema_name, screen_name, show_time (UTC ISO), show_time_end, business_date, running_time, rating, rating_name, genre, countries, audio_lang, subtitle_lang, sold_out, seats_low, bookable, allow_purchases, maximum_capacity, version_3d, version_4k, version_imax, version_dbox, version_atmos…, movie_poster, movie_thumbnail`

Example (trimmed):

```json
{
  "show_time_id": 436478,
  "title": "Heart of the Beast",
  "cinema_name": "BioRex Verkatehdas",
  "screen_name": "1 PRIME",
  "show_time": "2026-10-09T17:00:00.000Z",
  "title_extension": "ATMOS",
  "sold_out": 0,
  "seats_low": 0
}
```

- **Ticket link:** `https://webshop.biorex.fi/fi/#/book/<show_time_id>` **[V]**. The languages `sv` and `en` probably work too **[A]**.

### Cinemas (`getCinemasList`) [V]

| id  | Name               | City                        |
| --- | ------------------ | --------------------------- |
| 1   | BioRex Verkatehdas | Hämeenlinna                 |
| 2   | BioRex Rovaniemi   | Rovaniemi                   |
| 3   | BioRex Tornio      | Tornio                      |
| 4   | BioRex Pietarsaari | Pietarsaari                 |
| 5   | BioRex Vaasa       | Vaasa                       |
| 7   | BioRex Kajaani     | Kajaani                     |
| 8   | BioRex Riihimäki   | Riihimäki                   |
| 9   | BioRex Sveitsi     | Hyvinkää                    |
| 10  | BioRex Porvoo      | Porvoo                      |
| 12  | BioRex Seinäjoki   | Seinäjoki                   |
| 13  | BioRex Tripla      | Helsinki (city field empty) |
| 14  | BioRex Redi        | Helsinki (city field empty) |

Filtered out: ids 6, 15 and 16 (`xxx` name prefix, closed) and id 11 (the company itself). The `offline` field is checked too.

### Fallbacks

- `biorex.fi/wp-json/wp/v2/br_movie` provides synopsis, genres and Yoast metadata. `br_cinema` provides id, slug and link **[V]**. Neither has showtimes.
- On film pages (e.g. `/elokuvat/the-devils/`) every showtime carries a `data-click-data-layer` JSON **[V]**:
  ```json
  {
    "event": "WebshopShowtimeClick",
    "movieId": 1466,
    "movieName": "Dyyni: Osa kolme",
    "showId": "431685_fi",
    "showCinemaId": 1,
    "showCinemaName": "BioRex Verkatehdas",
    "showDateTime": "2026-12-15T21:00:00+02:00"
  }
  ```
- The listing page uses `admin-ajax.php?action=br_movies_handler` (POST). A GET returned 503.

---

## Finnkino

### Background

- Finnkino moved to **Vista Cloud** from 25 Aug 2025, and all cinemas had moved by the end of October 2025 **[A]** (Cision, Muropaketti).
- **Implementation:** [src/providers/finnkino/](../packages/fetcher/src/providers/finnkino/), run with `pnpm pull --provider finnkino`.

### Cloudflare and the token [V]

- `www.finnkino.fi` (and its `robots.txt`) answers **every non-browser client** with `403` + `cf-mitigated: challenge`, **even from a home connection** and with ordinary `Accept` headers. Headless Chrome is challenged too. Only a **visible (headed) Chrome** passes, on its own, with no captcha. This contradicts Leffavuoro's comment that only datacenter IPs are blocked.
- `digital-api.finnkino.fi` is **not** behind the challenge. Without a token it answers `401 "No global authentication JWT supplied"`; with one, plain HTTP works with our own User-Agent.
- The token is a JWT embedded in the front page HTML. Issuer `https://auth.moviexchange.com/`, client "Finnkino Omnia", minted at page load, **valid for exactly 12 hours**.
- Vista's [security docs](https://developer.vista.co/digital-platform/getting-started/security) describe this token as "safe to make available to public facing clients", meant to be cached and reused. It is not a secret.
- **Our approach** ([token.ts](../packages/fetcher/src/providers/finnkino/token.ts)): open the locally installed Chrome (Playwright, `channel: "chrome"`, `headless: false`) for a few seconds, read the token from the page, cache it in `data/cache/finnkino-token.json` (mode 600), and renew it when less than an hour is left. In practice a Chrome window appears about twice a day. **Works only on a desktop machine with Chrome, never in CI.**

### Old XML API: dead

- `/xml/TheatreAreas/` and `/xml/Schedule/?area=1014` return a 403 Cloudflare challenge **[V]**.
- Web Archive: `/xml/Schedule/` returned 200 XML until March 2025 and 404 on 4 Mar 2026 **[V]**.

### Vista OCAPI [V]

Base: `https://digital-api.finnkino.fi/WSVistaWebClient/ocapi/v1` (Vista tenant `ODEFI`). Finnkino's own frontend calls `/films`, `/films/{slug}`, `/sites`, `/films/availability` and `/film-screening-dates?siteIds=…`.

| Endpoint                                                 | Use                                                                                                                                                         |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/sites`                                                 | 17 sites: name, coordinates, address (`line1` street, `line2` postal code, `city`)                                                                          |
| `/showtimes/by-business-date/{date}?siteIds=…&siteIds=…` | **The adapter uses this.** One call per day covers every site, with `relatedData` for films, attributes, ratings, genres, screens and advance booking rules |
| `/film-screening-dates?siteIds=…`                        | Business dates with screenings: **80 dates, up to 2027-06-20** (advance sales)                                                                              |
| `/films/availability`                                    | Gave no response to plain HTTP; not needed                                                                                                                  |

**Values profiled on 2026-10-09 (2,889 showtimes, 59 films, 17 sites, 7 days):**

- **Showtime:** `id` like `"1004-5832"`, `schedule.businessDate`, `schedule.startsAt`/`endsAt` already in Helsinki time with offset, `isSoldOut`, `filmId`, `siteId`, `screenId`, `attributeIds`, `requires3dGlasses`, `restrictions`. Only upcoming shows are returned for today.
- **Sites:** every site claims `ianaTimeZoneName: "Europe/Kyiv"`. Wrong, but the same offset; ignored.
- **Films:** `title` in Finnish with an `en-US` translation; **no original title**; `releaseDate` is the Finnish release; `runtimeInMinutes`; `externalIds` holds only a Moviexchange release id (**no TMDB or IMDb id**); synopsis and trailers (not used). **No production countries.**
- **Qualifiers in titles:** "Nalle Puhin elokuva (dub)", "Vaiana (liveaction)", "Autot (uudelleenjulkaisu)" (re-release).
- **Ratings** (`censorRatings[].classification`): the KAVI number followed by content letters: `S`, `7 A`, `12 VA`, `16 P`, ... (V violence, A anxiety, S sex, P substances). `Tulossa` means the rating is pending. `ageRestriction.minimumAge` is always 0, so it is useless.
- **Genres** have trailing spaces. The genre `Event cinema` marks operas, concerts and similar.
- **Attributes** (`shortName`):

  | Attribute                                            | Meaning                                                                                                      |
  | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
  | `FI-A`, `EN-A`, `KO-JA-A`, `FI-SE-A`, ...            | spoken language(s); `SE` = Swedish; `TU`, `MA`, `LI` = Turkish, Malayalam, Lithuanian (Finnkino's own codes) |
  | `FI-S`, `SE-S`, `EN-S`                               | subtitles. No `-S` with a spoken language means no subtitles                                                 |
  | `SEVERAL`                                            | several spoken languages, not listed                                                                         |
  | `OCAP`                                               | open captions: Finnish subtitles for the hard of hearing                                                     |
  | `2D`                                                 | always present; no 3D in the sample                                                                          |
  | `IMAX`, `iSense`, `LUXE`                             | premium formats                                                                                              |
  | `Annisk_K18`                                         | alcohol served, K-18                                                                                         |
  | `Anniskelu`                                          | licensed auditorium                                                                                          |
  | `Ennakko`, `EventCine`                               | preview, event cinema                                                                                        |
  | `Tampere`, `Pkseutu`, `TKU & R`, `Maxim`, `Varaus20` | regional marketing groups, a site name, an internal booking setting: ignored                                 |

- **Advance booking:** `restrictions: ["FilmAdvanceBookingRule"]` on 667 shows. All 82 rules had a single period with `restriction: "None"`; the period's `startsAt` is when sales open. Before that the show is not bookable.
- **Availability:** no sold-out shows in the sample, and **no "few seats left" flag** exists.
- **Ticket link:** `https://www.finnkino.fi/liput/valitse-paikat/?showtimeId={id}`. **Verified** by clicking a showtime on finnkino.fi, and it matches the `/liput/valitse-paikat/` route in Finnkino's JS bundle. Leffavuoro's `/lipts/…` is wrong.
- **Film page:** `https://www.finnkino.fi/elokuvat/{slug}/{filmId}/`, e.g. `/elokuvat/the-odyssey/HO00000334/`.

### Conclusion

Finnkino works, with one manual-ish step: a visible Chrome window on the maintainer's machine about twice a day to renew a public 12-hour token. Everything else is plain HTTP against the JSON API.

The real risk is breakage, not permission: Finnkino could tighten the Cloudflare check or stop embedding the token in the page. The Cloudflare check covers the whole site (shop, login, loyalty programme) and looks like generic bot protection rather than an attempt to hide showtimes, which Finnkino publishes to sell tickets. We have not contacted Finnkino; if the service goes truly public, we notify them (and every other source) first and remove them if they object.

---

## Nexxo (Nexxo Scope WordPress plugin)

Profiled on 2026-10-10 over 214 shows on 10 locations. Adapter: `packages/fetcher/src/providers/nexxo/`, site list in `sites.ts`. Origin: Leffavuoro's `scripts/providers/nexxo.py`, re-verified.

### API [V]

`GET {host}/wp-content/plugins/nexxo-scope/public_api.php?action=exportdailyshows&locationid=N&days=D&lang=fi&upcoming=0`

- No authentication, plain JSON. `{"shows": {"2026-10-10": [rows…]}}`, or `{"shows": []}` when the programme is empty.
- `days` counts from **today**; there is no start date. A later `--from` asks for more days and the parser trims to the window.
- Each row is a movie merged with a show; **every value is a string**. Fields we read: `showId`, `movieId`, `movieTitle`, `startTime` (Helsinki local, `2026-10-10 15:00:00`), `startDate`, `roomId`, `roomTitle`, `ageLimit`, `duration`, `genre`, `priceIncludingTax` (`0.00` = not set), `code_language`, `code_subtitles`, `showTypeTitle`, `release_year`, `is3D`, `isUpcoming`.
- **Pacing:** the hosts are small WordPress sites and answer **403** when hit too often. The adapter waits 2.5 s between requests per host.
- Seen values:
  - `code_language`: `FI`, `EN`, `SE` (= Swedish), `IW` (= Hebrew), `OV` (original version: language unknown), and ISO codes.
  - `code_subtitles`: `FI-SE`, `FI`, `EN`, `XX` (none), `OV` (unknown).
  - `ageLimit`: `S`, `s`, `7`, `12`, `16`, `18`, empty, `Tapahtuma K18` (an event with an age limit; becomes the screening's `ageLimit` and marks the listing an event).
  - `release_year`: `2026`, empty, or a range such as `1937-1949` for a shorts programme (ignored).
  - `showTypeTitle`: `Tavallinen näytös` / `Viikko-ohjelmisto` (regular), `Konsertti`, `Taikashow`, `Muut tapahtumat` (events), otherwise festival and series names (kept as `series`).
  - Titles: some sites put labels before a colon (`Ennakkoensi-ilta: …`, `Rauhanviikko: …`). Only prefixes listed in the config (`titlePrefixes`) are stripped; `Ryhmä Hau: Dinoelokuva` is a title.

### Sites and their quirks [V]

`locationId`s cannot be guessed; ask the API. One host can serve several cinemas, and a cinema's data can live on another host:

- **Bio Säde** (Mänttä): biosade.fi's own API is empty; its page reads kinohirvi.fi's API, location 4 (`apiBase`).
- **Kino Metso** (KSEK's touring cinema): location 2 on kinoaurora.fi, where each **room is a town** (`roomIds` per venue; Riihivuori, room 21, is folded into Muurame as KSEK's site does). Laukaa (24) and Viitasaari (10) were not in Leffavuoro's list; the `unclaimed-room` warning found them.
- No seat counts (`availability: "unknown"`) and no per-show booking links in the API. **Ticket links point to the venue's programme page** (`programmePath?location=N`, or the venue's own `page`), which differs per site. Each was opened by hand on 2026-10-10 and shows the plugin's showlist.

### Adding a Nexxo cinema

1. Find the host (the page source mentions `nexxo-scope`) and its `locationId`s (`locationid=1,2,…` until empty).
2. Find the programme page a visitor uses and check that `?location=N` (or the venue's own page) shows its shows.
3. Add an entry to `sites.ts` with `verifiedAt`, run `pnpm pull --provider <id>` and read the warnings.

---

## Film ratings: OMDb

Set up on 2026-10-10. Code: `packages/fetcher/src/ratings/omdb.ts`, run by `pnpm pull` / `pnpm match` after TMDB matching when `OMDB_APIKEY` is set.

- **Why OMDb [V]:**
  - Rotten Tomatoes, Metacritic and Letterboxd have no public API (scraping RT breaks its terms).
  - OpenCritic covers video games only.
  - OMDb returns RT, Metacritic and IMDb scores in one call, looked up by the IMDb id TMDB gives us, so there is no title guessing.
- **API:** `GET https://www.omdbapi.com/?i={imdbId}&apikey=…`.
  - Free key: 1,000 requests a day. Answers are cached a week in `data/cache/omdb/`, so a daily run only asks for new films.
  - **The key is in the URL:** errors are rethrown without it, and the cache key leaves it out.
- **First run (2026-10-10):** 47 of 67 films got scores (44 RT, 37 Metacritic, 42 IMDb). The rest are mostly new or small Finnish releases.
- **TMDB's own score** (`vote_average`) comes with the details we already fetch. It is used only from 20 votes up, since fewer is noise.
- **Licence:** OMDb data is CC BY-NC 4.0 (non-commercial, attribution). The RT score ultimately belongs to Rotten Tomatoes: before going truly public, it goes on the same "ask first" list as the cinemas.

---

## Venue coordinates: OpenStreetMap

Set up on 2026-10-10. Code: `packages/fetcher/src/geo/`, CLI `pnpm venues:locate`.

- **Overpass [V]:** one query for every cinema in Finland (`nwr["amenity"="cinema"]` inside the `ISO3166-1=FI` area, `out center tags`): 148 cinemas on 2026-10-10. Ways and relations come with a centre point. Cached for a week in `data/cache/osm/`.
- **Nominatim [V]:** `nominatim.openstreetmap.org/search?q=…&format=jsonv2&countrycodes=fi&limit=3` for halls that OSM does not tag as cinemas (Kino Metso plays in school auditoriums and sports halls). At most one request per second, cached for a month. Addresses come from the cinema's own page.
- **Licence:** OSM data is ODbL. Credit "© OpenStreetMap contributors" in the UI.
- **Google Maps is not a source:** its terms forbid storing coordinates taken from it.
- **First run, 2026-10-10:**
  - 7 Nexxo venues matched OSM cinemas by name, city and address.
  - 8 were geocoded from their halls' addresses. Kino Aurora was then added to OSM by the maintainer (node 14270115364) and now uses that node. Viitasaari first resolved only to the street; it now uses the OSM cinema node in the youth centre (Nuorisotalon Teatteri, Koulukuja 8), confirmed by the maintainer.
  - Finnkino's own point for **Promenadi Pori** was 3.7 km off. The OSM node has Finnkino's address and operator, so an override in `config/venue-overrides.json` corrects it.
  - **BioRex Riihimäki** is not in OSM, and BioRex's own point was about 1.1 km north-east of the cinema. The maintainer added it to OSM (node 14052479733, Keskuskatu 8), and an override uses that point.

---

## References

- [Cision: Finnkino introduces new digital services (26 Aug 2025, in Finnish)](https://news.cision.com/fi/finnkino/r/lehdistotiedote--finnkino-ottaa-kayttoon-uudet-digitaaliset-palvelut---ensimmaisena-mukana-espoon-el,c4222617)
- [Muropaketti (31 Oct 2025, in Finnish)](https://muropaketti.com/elokuvat/elokuvauutiset/finnkino-sai-koko-syksyn-jatkuneen-urakan-valmiiksi-moni-taitaa-tosin-toivoa-ettei-sita-olisi-koskaan-edes-aloitettu/)
- [Shady-Dev/kino (Leffavuoro)](https://github.com/Shady-Dev/kino)
- [Vista OCAPI showtime endpoint](https://developer.vista.co/openapi/digital-platform/openapi/showtimes/ocapishowtimes_getshowtime)
- [OzQu/finnkino-wrapper](https://github.com/OzQu/finnkino-wrapper) (old XML)
- [Unique X](https://uniquex.com/)

---

## Prior work: Leffavuoro (Shady-Dev/kino)

Reviewed on 2026-10-09: <https://github.com/Shady-Dev/kino>, site <https://leffavuoro.fi>.

- **Scope:** about 40 adapters and 230 cinemas, including Finnkino, BioRex and practically every small cinema. Many small cinemas share ticketing platforms: eTiketti, Nexxo, Johku, MyCloudCinema, Kinola and cinema-reservations.
- **Technology:** Python stdlib, about 21,000 lines of adapter code and about 200 test files. Data is fetched ahead of time and committed as static JSON served from GitHub Pages. Some sources are fetched from a home machine (`where="local"`), others in GitHub Actions.
- **Maintenance:** a single developer, created 2026-08-26, very active (over 1,200 commits). Clearly AI-assisted (CLAUDE.md is 29 kB).
- **Finnkino:** the token is passed in the `FINNKINO_TOKEN` environment variable and obtained by a private local wrapper that is **not in the repository**. The fallback is a direct fetch in which an `eyJ…` regex picks the token from the front page HTML. In our tests that fallback is challenged even from a residential IP. Language code fixes: `SE→SV`, `TU→TR`, `MA→ML`, `LI→LT`.
- **BioRex:** Leffavuoro reads WordPress `admin-ajax.php` (POST + a cinema selection cookie). We found a more direct route, `webshop.biorex.fi/webservices` (GET, no cookies).
- **Data model:** shaped for the frontend and string-heavy (`len: "129"`, `lang: "EN-A, FI-S, SV-S"`). Films are matched through TMDB (`enrich_tmdb.py`, 1,670 lines), with hand-written aliases.
- **Ethics rules (CLAUDE.md):** own User-Agent with contact details; no residential proxies, fingerprint spoofing or captcha solving; no booking or payment endpoints; ticket links are copied, never constructed.
- **License:** the code is **AGPL-3.0-or-later**. The data (`data/area-*.json`) and posters are **not** covered by the license; they belong to the cinemas. The README states explicitly that a fork grants no right to the data.
