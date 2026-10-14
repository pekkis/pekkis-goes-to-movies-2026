# Data sources

Finnkino and BioRex investigated on 2026-10-09, Nexxo, eTiketti and Kinola on 2026-10-10, Johku on 2026-10-12; all are implemented. Markers: **[V]** = verified with our own request, **[A]** = assumed, or read from a third-party source.

---

## BioRex

### Overview

- `biorex.fi` is a WordPress site (Polylang fi/sv/en, Yoast, custom theme) **[V]**.
- The ticket shop `webshop.biorex.fi` is AngularJS + Express **[V]**. **The platform is MyCloudCinema**: the cinema settings contain `webhook_url: https://api.biorex.mycloudcinema.com/…` **[V]**. The HTML's `<meta name="author" content="Unique X">` points to the developer (Unique X) **[A]**.
- The same MyCloudCinema `/webservices` API serves Cine Mäntsälä (`mantsala.cine.fi`) **[V]** (see below), and according to Leffavuoro, Gilda's WordPress facade **[A]**.
- **Implementation:** the MyCloudCinema platform adapter, [src/providers/mycloudcinema/](../packages/fetcher/src/providers/mycloudcinema/), one site per cinema chain in `sites.ts` (BioRex, Cine Mäntsälä). Run with `pnpm pull --provider mycloudcinema`, or a site id.
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

### Cine Mäntsälä (MyCloudCinema, 2026-10-13)

Origin: Leffavuoro's `scripts/providers/cinemantsala.py`, re-verified with three GETs.

- **Same API as BioRex** on the cinema's own host: `https://mantsala.cine.fi/webservices/` `cinemas/getCinemasList`, `show_times/getShowTimesDays?cinema_id=1&date=&number_of_days=` **[V]**. No key, no session.
- **Two cinemas in the list:** 1 Cine Mäntsälä, and 2 **Cine Keuda-talo** (Kerava), which we read from eTiketti (`kiertue.cine.fi`) **[V]**. Neither source had Keuda-talo shows on 2026-10-13. The site config reads cinema 1 only, so a venue never appears twice.
- **No coordinates** in the API **[V]**: set in `config/venue-overrides.json` (OSM way 1225638695, with the API's own address).
- **Rows** look like BioRex's **[V]**:
  - the same rating icons (`rating_fi_12.svg`) and `business_date` convention;
  - two halls, "Sali 1" and "Sali 2";
  - `audio_lang` codes and `movie_audio_style_id` for dubs.
- **`subtitle_lang` is a Finnish phrase**, not a code **[V]**: "Suomeksi ja ruotsiksi", "Ruotsiksi", "suomeksi", "Ei" (none). The platform parser reads both vocabularies.
- **`title_extension` is a label:** "Ennakkonäytös!" **[V]**, read by the shared title-label rules as a `preview` tag. Leffavuoro also saw "Cine Matinea" and "Leffa & Kaffe - näytös" **[A]**; they'd show as unmapped labels until added.
- **Days per request:** Leffavuoro measured `number_of_days` as a cap of 7 **[A]**, so the platform fetches in windows of at most 7 days and deduplicates by show id. A 7-day pull is still one request per cinema.
- **Ticket links:** `https://mantsala.cine.fi/#/book/{show_time_id}`, the anchor the cinema's own programme page renders **[A, Leffavuoro]**. Copied by pattern, never requested.
- **First run:** 18 films, 30 screenings, all films matched to TMDB, no warnings.

### Gilda (MyCloudCinema through a WordPress facade, 2026-10-13)

Origin: Leffavuoro's `scripts/providers/gilda.py`, re-verified with two GETs. Adapter: `packages/fetcher/src/providers/gilda/`.

- **What the cinema's own page reads:** `GET https://www.gilda.fi/wp-json/gilda-react-booking/v1/movies` **[V]**. One response, `{"fi": {"data": [film…], "resultCode": 0}}`, holds every film with its `show_times`: 53 films and 202 shows, reaching January 2027. No auth.
- **Not used:** the same data is also on `web.atlanticfilm.mycloudcinema.com/webservices` (cinema 15, "Gilda", Narinkka 2) **[V]**, but gilda.fi's own programme reads the facade, so we do too. The namespace also has write and admin routes: never called.
- **Venues by screen** **[V]**: one cinema (15) holds screens 66–68, "Gilda 1–3" in Kamppi, and 69, "Bio Rex Lasipalatsi (K-18)". The "(K-18)" is the house's door policy, so it becomes the hall's age limit, not a film rating. An unknown screen gives an `unclaimed-screen` warning.
- **Rows are MyCloudCinema-like but not the same** **[V]**:
  - no `business_date` (we derive the programme day), no seat flags (only `allow_purchases`, so availability is "unknown" or "not bookable");
  - booleans as `true`/`false` or `"1"`/`"0"`, and shows can be `deleted` or `show_is_visible: "0"` (2 of 202; skipped).
- **Ratings** `rating_name` **[V]**: "7", "12", "16", "18"; "T" and "EI MÄÄR." are unrated and stay unknown.
- **Languages** **[V]**:
  - `audio_lang` is a code, "MULTI" (several languages, so unknown), or "Ei puhetta" (no dialogue, `zxx`);
  - `subtitle_lang` is "suomi, ruotsi", "SE", "FI", "EN" or "-".
- **The "-" subtitle value:** it means none only with `movie_audio_style_name` "Ei tekstitystä". The 10 rows with "-" and "Tekstitetty" (subtitled) contradict themselves, so they stay unknown, as in Leffavuoro.
- **Event-like shows:** style "Albumikuuntelu" (album listening, e.g. Coltrane) marks events, not films.
- **Title prefixes:** "Seniorikino:" (shared rule) and, in the site config, "70mm:" (format only) and "Pieni elokuvakerho:" (series).
- **Film ids:** each film carries `imdb_id` (40 of 53) and `tmdb_id`. We store the IMDb id, so matching is exact via TMDB `/find`.
- **Ticket links:** no per-show link in the data. A show links to its film's page on gilda.fi, copied from the public `/wp-json/wp/v2/movies?per_page=100&_fields=link,title` list and matched by title. Otherwise it links to the programme page `/elokuvat/`. About half match on the first page of that list.
- **Coordinates** from OSM (node 11701088977 Gilda, node 1381017800 BioRex Lasipalatsi), both with the cinemas' own addresses.
- **First run:** 23 films, 75 screenings in a 7-day window; 21 matched to TMDB; no warnings.

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

## TMB Cinema (one HTML template, four cinemas)

Probed 2026-10-13, one GET per site. Adapter: `packages/fetcher/src/providers/tmb/`, sites in `sites.ts`. Origin: Leffavuoro's `scripts/providers/tmb.py`, re-verified.

- **Who:** TMB Cinema Oy runs Kino-Toijala (Akaa), Kino-Sampo (Valkeakoski), KinoMania (Pieksämäki) and Elokuvateatteri Elo (Heinola), each on its own site built on one template ("Mediapalvelu W3D").
- **Four cinemas, not mirrors** **[A, Leffavuoro]**: their programmes coincide, but each has its own booking ids.
- **The programme:** `GET {base}/?lista=1`, the list view **[V]**:
  - each row is `<small>KE&nbsp;14.10.2026 klo&nbsp;13:30[, sali&nbsp;1]</small>`, followed by `<h2><a href="?ohjelmisto={id}">Title</a></h2>` and a rating image `/files/images/ikaraja_N.png`;
  - the year is always there. Halls appear only at KinoMania and Elo.
- **Date-only rows** ("23.10.2026", no weekday or time) **[V]**: announcements, not screenings; skipped.
- **A weekday that contradicts its date** is rejected with a warning: the template must have changed.
- **Rating images** **[V]**:
  - `_2` K-7, `_3` K-12 and `_4` K-16 were checked by Leffavuoro against other cinemas' ratings of the same films;
  - `_1` is S: we checked it on 2026-10-13 ("Pirjo i Sverige" is S at 13 other cinemas, "Pikkuli ja Tähtipeura" at 6), and it also appears on operas and ballets;
  - `_0` is titled "Ikärajaa ei ole määritetty" (no rating set);
  - `_5` (one festival screening) is reported as an unmapped label.
- **Labels in titles** **[V]**: "(Ennakkonäytös)" / "(Ennakkonäytös!)" (preview), "(Puhumme suomea!)" (Finnish dub, also without the space), "Ooppera:", "Baletti:" (events), "Akaan elokuvajuhla 2026:" (series, in Toijala's config). They're read by the shared label rules in `labels.ts`, which now also take labels in parentheses at the end.
- **No screening ids in the list:** a screening's id is film, minute and hall: `867-202610141330`, `847-202610141745-1`.
- **Ticket links:** the film's public page `?ohjelmisto={id}`, which lists its screenings with the site's own booking buttons. Never `?varaa=` (the seat-reservation action). So booking is `reserve`.
- **Not read:** the film pages, which state runtime, genre and a price per screening, at about one request per film per site. Possible later; TMDB gives the runtime anyway.
- **Coordinates** **[V]**:
  - Toijala and Sampo: OSM nodes with the cinemas' own addresses;
  - KinoMania: an OSM node about 45 m from the Kauppakatu 5–7 address points;
  - Elo: OSM has no cinema in Heinola and Nominatim can't place Kauppakatu 16, so the point is the maintainer's (`manual`, 2026-10-13).
- **First run:** 19 + 19 + 26 + 26 screenings, about 9 of every 10 films matched, no warnings apart from Elo's coordinates.

---

## Cinemahouse (WordPress `cinema-reservations` plugin)

Probed 2026-10-13, one GET per site. Adapter: `packages/fetcher/src/providers/cinemahouse/`. Origin: Leffavuoro's `scripts/providers/cinemahouse.py`, re-verified.

- **Who:** Kino Piispanristi (Kaarina), Kino Lumo (Salo) and Laitilan Kino (Laitila).
- **The programme:** the front page renders the whole programme **[V]**:
  - `article.cr-movie-tile`: title, age badge (S/7/12/16), runtime "129 min", genres;
  - `div.cr-screening-row`: title, "14.10. 12:00 · Sali 2" (**no year**), price "12,00 €", "Vapaat paikat: 53 / 65", and `a.cr-screening-cta` with `data-screening-id` and the reservation link `/varaa/?screening_id=N`.
- **Joining tiles to rows:** every row title had a tile with exactly the same title (labels included) **[V]**.
- **The year:** `nearestDate` (in `@pgtm/model/time`) puts a date at most 30 days before the programme's first day, otherwise ahead. Programmes reach mid-December.
- **Labels are in capitals** **[V]**: "ENNAKKO:", "ENNAKKONÄYTÖS:", "ENSI-ILTA:" and trailing "SUOMEKSI" / "PÅ SVENSKA". The shared label rules now match without regard to case and read capitalized trailing languages (lower case "suomeksi" at the end of a title is left alone).
- **Dubbed and subtitled runs are separate films** (separate WordPress posts), so the listing id is the film page's slug.
- **Halls:** "Vip 4" and "Premium 5" are kept as names, not features.
- **The reservation link** is the cinema's own page, copied, never requested.
- **Coordinates** **[V]**: all three from OSM. Kino Lumo is mapped as "Elokuvateatteri Lumo" at its own address (Savipajankatu 2B, Salo).
- **First run:** 126 + 82 + 16 screenings this week, 24 of 25 films matched at Piispanristi, no unmapped labels.

---

## Vista public web services (Korjaamo Kino)

Probed 2026-10-13, two GETs. Adapter: `packages/fetcher/src/providers/vista/`, sites in `sites.ts`. Origin: Leffavuoro's `scripts/providers/vista.py`, re-verified.

- **What it is:** Vista's older public web services, left open by some Vista cinemas: no token, unlike Finnkino's OCAPI. `GET {base}/xml/Schedule/?area={id}&nrOfDays=31` answers **JSON** by default **[V]**. One request covers the published window (13 shows over 31 days at Korjaamo).
- **Korjaamo Kino** (Helsinki): area 1007, theatre 1045, one hall "Sali" **[V]**.
- **Fields** **[V]**:
  - times: `dttmShowStartUTC` (UTC), and `dtAccounting`, the programme day at local midnight (used as the business date);
  - film: `Rating` ("K-12", "Sallittu" = S, "Ei tiedossa" = unknown), `LengthInMinutes`, `ProductionYear`, `Genres`, `EventSeries`, `PresentationMethod` ("2D");
  - languages: `SpokenLanguage` with an ISO code, or the name "useita kieliä" (several languages: audio stays unknown, unflagged); `SubtitleLanguage1/2`, both empty on every show seen, so subtitles stay unknown, never "none";
  - booking: `AvailableSeats` / `TotalSeats` (empty at Korjaamo), and `ShowURL`, the show's own ticket page `/websales/show/{id}`, copied.
- **Title prefixes** (site config): "Kirjastokino:" and "Tekijätorstai:" / "TEKIJÄTORSTAI:", both series.
- **Coordinates:** OSM node 4394184115 "Korjaamo Kino"; address from the cinema's own page (Töölönkatu 51 B, 00250 Helsinki).
- **First run:** 12 films, 13 screenings over 31 days, 8 matched to TMDB (the rest mostly classics: aliases later), no warnings.

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

## eTiketti (server-rendered HTML)

Profiled on 2026-10-10 against all 21 sites (listing + 2 film pages each). Adapter: `packages/fetcher/src/providers/etiketti/`, sites in `sites.ts`. Origin: Leffavuoro's `scripts/providers/etiketti.py`, re-verified.

### Pages [V]

- **Listing:** `GET {base}/elokuvat/ohjelmistossa` links every film page as `/elokuvat/{id}/{slug}`. Niagara's listing has no `.movie-list` container, so links are found by URL pattern.
- **Film page:** carries **all** of the film's screenings, so there is no paging and no date parameter. About 15 film pages per site, ~330 pages a day for all 21.
- **Screening rows:** `<div class="item {location} date-D.M.YYYY">`. The second class is a location word (`kotka`, `joensuu`, `nurmijÄrvi`: oddly cased).
  - **Kotka template (20 sites):** "LA 10.10. klo 20.00", then a details paragraph "PLACE<br>Lippu 18,00€<br>Vapaat paikat 10/22". Some rows put a tag box and an empty `<p></p>` before it, so the parser finds the paragraph by content, not position.
  - **Niagara:** time in `.time`, price in `.show-price`, "Paikkoja vapaana: 124/127", and no place line.
  - **Ticket link:** `/salikartta?id=N` on the cinema's own host. Copied, never requested. The id is the show id.
- **Place lines** vary by site:

  | Shape                    | Example                                                           |
  | ------------------------ | ----------------------------------------------------------------- |
  | `CINEMA \| ROOM`         | `STAR \| SALI 4`, `TRIO 123 \| VIP-SALI`, `BIO 1&2 REX \| DIGI 1` |
  | `CITY \| CINEMA \| ROOM` | `JOENSUU \| TAPIO \| TAPIO 3`, `MIKKELI \| KINOLINNA \| VIP`      |
  | `CITY \| CINEMA`         | `KERAVA \| CINE KEUDA-TALO`, `SAVONLINNA \| KUVALINNA`            |
  | Room repeats the cinema  | `IISALMI \| KUVALIPAS \| KUVALIPAS`                               |
  | Cinema only              | `KINO JUHA`, `VIP-SALI`                                           |

  The adapter matches one part exactly to a venue's `place` and takes the part after it as the room. Savon Kinot's lines gained the city part since Leffavuoro's notes. Kotka's Kinopalatsi now prints "KINOPALATSI", and Kitee's is "KINO-HOVI".

- **Film facts** are `<span class="label">` followed by text, with a colon on most sites and without on Niagara:
  - `Kesto` ("2 h 9 min");
  - `Kieli`: "englanti", "suomi", "Alkuperäinen" (original, which tells us nothing, so audio is left unknown);
  - `Tekstitys`: "Suomi ja ruotsi", "Ei tekstitystä";
  - `Ensi-ilta`: the Finnish premiere, except on Niagara where it is the original one, so it is not used;
  - `Valmistumisvuosi` (production year, Niagara only).

  Age comes from `ikarajat/fi-12.svg`. Genres are in `span.movie-genre`, or in a "Genre" label on Niagara.

- **Tags** (`<span class="tag">`), on most sites:
  - "Viimeinen näytös" → `last-screening`
  - "Edullinen päivänäytös" → `discount`
  - "Anniskelunäytös" → licensed; an `anniskelu.svg` icon also means licensed
  - "Erikoisnäytös" → ignored
  - anything else becomes a series (e.g. "Saatana saapuu valkokankaalle")
- **Title variants:**
  - **Version markers**, at the end, in brackets or after a comma: "(DUB)", "(Dub.)", "DUB", "DUP." (typo), "SUB", "(ORIG)", "(suomeksi)", ", englanniksi", "(på svenska)", "2D", "– ohjaajan versio". They become audio, dubbed or dimension data and are stripped, so all versions match one TMDB film.
  - **Labels**, as a prefix or after a dash: "Ennakkonäytös:", "Vauvakino", "Ooppera:".
- **Access:** all 21 sites answered our User-Agent with 200, including the ones that block GitHub runners. A whole-run pull took 99 s with 6 sites at a time.

### Coordinates

- 22 venues match OpenStreetMap cinemas.
- 6 were geocoded from addresses on the cinemas' own pages (Nominatim). Kinotar 123 resolved only to its street.
- 3 more (Kuvalipas in Iisalmi, Ihme Kompleksi in Kankaanpää, Haapamäen Elokuvat) were geocoded from addresses the maintainer supplied, since neither the sites nor OSM had them.
- A test fails if any eTiketti venue lacks coordinates.

---

## Kinola (public JSON API)

Found on 2026-10-10. Adapter: `packages/fetcher/src/providers/kinola/`, cinemas in `sites.ts`.

- **What Kinola is [V]:** an Estonian cinema ticketing service (kinola.ee). Each cinema is a tenant `{tenant}.kinola.ee`, and its WordPress site runs Kinola's plugin, which copies the programme from Kinola.
- **The API [V]:** Kinola's plugin is open source ([kinola-ee/kinola-wp](https://github.com/kinola-ee/kinola-wp), `src/Api/Kinola_Api.php`). It reads `https://{tenant}.kinola.ee/api/public/v1/` ("Public API for productions, events, etc") with plain GETs and no key.
  - `events?limit=500` returns every upcoming event with its production embedded. It is paginated (`links.next`); the plugin also passes `time_from`.
  - Leffavuoro scrapes these sites' HTML instead; it never found the API.
- **Requests:** one per cinema per day (all events fit in one page of 500).
- **Event fields** (260 events of six tenants, 2026-10-10):
  - `local_time` (with offset), `venue.name`, `room.name`, `freeSeats` (no capacity), `price_range` {min, max, EUR}.
  - `checkout_url`: the cinema's own booking page, copied as `ticketUrl`. Orion's goes to `orion.kinola.ee/web/screening/…`. Kilta gives none (it sells elsewhere), so its shows link the programme page.
  - `visibility`: `public` or `coming_soon` (listed, not on sale yet, giving `not-bookable`).
  - `program.name`: a series or a category (mapped per site); `note` (free text, read only when it starts with "Ensi-ilta"/"Premiere"/"Ennakko…"); `event_type` (`paid`/`free_public`, not film vs. live act).
- **Production fields:**
  - `name`, `originalName`, `year`, `duration`, `distributor`.
  - `rating`: K-*, S, `L` (Estonian all-ages, giving S), "Not rated".
  - `languages` and `subtitles` as names: Finnish, English, adjective forms ("italialainen"), typos ("ruotsi ", "Ei teksitystä"), and "kiillottaa" (a machine translation of "Polish").
  - `imdb_id`: Kilta gives it for nearly every film, the others sometimes.
- **Film vs. live act:** concerts and films are both productions, and nothing structural separates them. At Kino Laika (only there, checked against its programme), productions with no language, no distributor and no IMDb id are live acts. The rule is a per-site option, because Orion has real films missing all three.
- **Cinemas [V]:**
  - Kino Myyri (`myyri`, Vantaa), Cinema Orion (`orion`, Helsinki), Kino Kilta (`kilta`, Turku), Kino Laika (`laika`, Karkkila), Kino Konepaja (`konepaja`, Helsinki).
  - Cinema Sheryl (`sheryl`): the API says "Marsio, Helsinki", but Marsio is Aalto's building at Otakaari 2, Espoo.
  - All six are in OpenStreetMap with addresses. Konepaja had no screenings when Leffavuoro looked; it now has about 47.

---

## Johku (storefront schedule JSON)

Found on 2026-10-12. Adapter: `packages/fetcher/src/providers/johku/`, cinemas in `sites.ts`.

- **What Johku is:** a Finnish shop and booking platform (johku.com). Some cinemas' whole site is a Johku storefront, a Nuxt app.
- **The endpoint [V]:**
  - The storefront's code builds `https://{host}/api/{shop}/fi_FI/showschedule.json?details=true&storefront=true&version=fi_FI&from={date}&category={n}` (Leffavuoro read this in the bundle).
  - It adds `X-ApiKey` only for a signed-in user, so the anonymous call is the one a visitor's page would make.
  - Called anonymously with our User-Agent on 2026-10-12, it answered 200 with JSON on all seven storefronts.
  - Leffavuoro reads the same data from the `__NUXT_DATA__` copy embedded in the front page instead.
- **Finding the parameters:** the front page's `__NUXT_DATA__` names `storefront-{shop}-fi_FI` and one `showschedule-fi_FI-f{date}-c{category}` per programme block.
- **Not used:** KuvaTähti loads its shows only through `/api/auth/widget-session` and the widget's `X-ApiKey`, which we never use. Kino Engel and Kino Tapiola embed the Johku widget for tickets only; their programmes are on their own server-rendered pages, which Leffavuoro reads as HTML (`engel.py`, `tapiola.py`) **[A]**, and which we may read the same way.
- **Entry fields:**
  - `text` (title as written, with labels: "Perhekino:", "Seniorikino:", "Vauvakino:", "På svenska:", "MLL-näytös:");
  - `start_date` (Helsinki local, "2026-10-14 19:00") and `resource_name` (the hall);
  - **`resource_capacity` and `resource_reservations`**, which give sold-out and few-left;
  - `price` (the base ticket; `multipleprices` = 1 when other ticket types exist);
  - `originaltitle`, `duration`, `agelimit`, `director`, `imdb` (empty so far);
  - Maccs Box codes `maccsboxlanguage` / `maccsboxsubtitles` (FI, OV, FI-SE, XX, as on Nexxo);
  - `storefronturl` (the film's booking page, copied as `ticketUrl`).
- **Left out:**
  - `upcoming` = 1 entries: coming soon, with no time yet (Bio Marilyn lists 20).
  - Entries with no price, no age limit and no language. Kinokulma's hall hire ("Salivaraus"), closure notice ("Olemme vapaalla") and a private booking all look like this, while every film has at least one of the three. `product.displayedtype` is "movie" for all of them, so it does not help.
  - Kulttuurimylly's block 5, which is theatre ("Feeniks-sali (Teatteri)"); only its cinema block 2 is read.
- **Cinemas [V]:**
  - Bio Marilyn (Lapua, blocks 1 and 9, sharing some shows), Vihdin Kino (Vihti), Bio Forum (Tammisaari, Raasepori), Kinokulma (Oulainen), Kino Hannikainen (Nurmes), Kino Virta (Kalajoki, `kinovirta.johku.com`).
  - Kino Kulttuurimylly (Helsinki, Myllypuro): new since Leffavuoro's sweep, when its programme was paused.
- **First run:** 85 screenings a week. All 61 film listings matched TMDB (56 by search, 5 by sibling).

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
