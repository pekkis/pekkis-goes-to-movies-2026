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
- **`title_extension` is a label:** "Ennakkonäytös!" **[V]**, read by the shared title-label rules as a `preview` tag. A site's own whole labels are site config (`titleExtensions`): Cine Mäntsälä's "Cine Matinea" (also "- näytös") is the series Cine Matinea (its matinée strand), and "Cine Konsertti" (also "!") the series Cine Konsertti, event cinema, which makes the listing an event **[V]** 2026-10-15. Leffavuoro also saw "Leffa & Kaffe - näytös" **[A]**; it would show as an unmapped label until added.
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
  | `Ennakko`, `EventCine`, `Klassikko`                  | preview, event cinema, classic (a re-run, seen 2026-10-15)                                                   |
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

## Vista public web services (Korjaamo Kino, Riviera, Bio-Kaari)

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

### Riviera (Kallio, Punavuori)

Probed 2026-10-14, two GETs.

- **Not the website's listing:** rivieracinemas.fi builds its programme with a WordPress `admin-ajax.php` POST (Leffavuoro reads that). We prefer GET, and the ticket host has the same open schedule as Korjaamo: `GET https://tickets.rivieracinemas.fi/xml/Schedule/?nrOfDays=31` **[V]**.
- **XML only:** it answers `text/xml` whatever the `Accept` header, so the site config says `format: "xml"`. The parser turns each `<Show>` into the object the JSON answer gives (empty elements absent, numeric fields numbers).
- **No `area` needed:** one request covers every theatre. Theatres 1075 (Kallio, "Sali 1") and 1114 (Punavuori, "Sali 1" and "Sali 2"); 88–90 shows over a month.
- **Languages are filled in:**
  - `SpokenLanguage` and `SubtitleLanguage1/2` are given on most shows, sometimes with only the ISO code;
  - shows without them leave audio and subtitles unknown.
- **Ratings** read "K16/13", "K12/9" (the lower age is allowed with an adult), "S" or "(none)" (unknown).
- **`ProductionYear` is the release year, not the film's:** "Scream (1996)" says 2026. With `releaseYearAsProductionYear` set, the year comes only from a trailing "(1996)" in the title; otherwise it stays unknown. `OriginalTitle` repeats prefixes and years, and is cleaned like the title.
- **Title prefixes** (site config): "3 Kaveria jäätelönäytös:", "Afternoon Tea:", "Leffabrunssi:", "Mykkäleffakonsertti:", plus the common "Vauvakino:".
- **Tickets:** `ShowURL` (`http://tickets.rivieracinemas.fi/websales/show/{id}/`), copied as printed and never requested. A link is accepted when its host is the site's.
- **Coordinates:** OSM nodes 5175303248 (Harjukatu 2, 00500) and 10186691049 (Telakkakatu 7, 00150); the addresses match the cinema's own site.
- **First run:** 32 films, 88 screenings, no warnings; 23 matched. The rest are repertory screenings without a reliable year: aliases.

### Bio-Kaari (Forssa)

Probed 2026-10-15, one GET.

- **The same open schedule on its ticket host:** `GET https://bio-kaari.azurewebsites.net/xml/Schedule/?nrOfDays=31`, XML **[V]**. Leffavuoro reads the web shop's pages instead.
- **One theatre** (1048) whose single hall is named "-", which is read as no auditorium. 29 shows over two weeks; spoken and subtitle languages on every show; ratings like Riviera's ("K16/13").
- **The cinema's own site** (www.bio-kaari.fi) did not answer at all on 2026-10-15 (no response in 20 s); it is only the homepage link, never read.
- **Coordinates:** OSM node 1142403445 (Vapaudenkatu, 30300 Forssa; no house number in OSM, so the address is left out).
- **First run:** 6 films (all matched), 29 screenings, no warnings.

---

## Kino Tapiola (its own WordPress theme)

Probed 2026-10-14, four GETs. Adapter: `packages/fetcher/src/providers/tapiola/`, site in `sites.ts`. Origin: Leffavuoro's `scripts/providers/tapiola.py`, re-verified.

- **Programme:** `GET https://www.kinotapiola.fi/elokuvat/` renders `div.movie-list` with one `div.movie-list-movie` block per screening **[V]**:
  - the title, with version markers ("Kojootti vs. ACME (dub)" / "(orig)");
  - the date with its year ("keskiviikko 14.10.2026 – Klo 15:00");
  - a link to the screening's run page (`/naytos/{slug}/`, or `/ooppera-ja-baletti-naytos/{slug}/` for event cinema);
  - strand classes on the block (`cat-seniorikino`), mapped in the site config; an unknown one goes to `unmappedLabels`.

  The list reaches months ahead (Royal Opera into 2027); the window cuts it.

- **A slug is a run, not a film:** `tony-4`, `tony-5` are separate posts with the same page. The film is therefore the title; a screening's id is its slug plus its start minute **[V]**.
- **Run pages:** one GET per distinct title in the window (the first run's page; 16 at the first run), paced 1 s. Labelled boxes in `div.info-icons` **[V]**:
  - the age limit as a class (`info-icon age-limit-K-16`);
  - "Elokuvan kesto 1h 49min";
  - "Kieli Englanti" (a Finnish language name, or "OV" for an original version, which leaves audio unknown);
  - "Tekstitys Suomi/Ruotsi"; no box means unknown, not "none".

  A page that fails gives a `film-page-missing` warning: the details stay unknown, the screenings (which come from the list) stay complete. Opera pages state their language only in the description text **[A]** (Leffavuoro); not read.

- **Not read:** stills behind the titles and the cinema's synopses (TMDB only); seats and prices (the Johku widget draws them client-side, and its API key is never used, per the rules).
- **Tickets:** the run page is the ticket page (Johku's widget on it), so `ticketUrl` is that page, copied.
- **Coordinates:** OSM node 1430315541 "Kino Tapiola"; address from the site's footer (Mäntyviita 2, 02110 Espoo).
- **First run:** 16 films, 26 screenings over 31 days, no warnings.

---

## Kuvakukko and Kino Manttu (one shared WordPress page)

Probed 2026-10-14: the programme page, then the linked film pages. Adapter: `packages/fetcher/src/providers/kuvakukko/`, site in `sites.ts`. Origin: Leffavuoro's `scripts/providers/kuvakukko.py`, re-verified.

- **The page:** `https://www.kuvakukko.fi/ohjelmisto/kuvakukon-ja-kino-mantun-ohjelmisto/` holds both of the city of Kuopio's cinemas **[V]**:
  - under each `<h2>` heading ("Kino Kuvakukon esitysaikataulu", "Nilsiän Kino Mantun esitysaikataulu"), paragraphs of `<br>`-separated lines;
  - a day line ("Keskiviikko 14.10.", no year; a new day can start mid-paragraph after an empty line) and rows ("Klo 13: Title", "Klo 17.30: Title").

  The heading is the venue boundary; the config names a word of each heading.

- **The year** is inferred (`nearestDate`, at most 30 days back) and checked against the weekday. A mismatch places nothing and warns.
- **Titles:**
  - The first link with text is the title (one row opens with an empty link); an unlinked row is the rest of the line.
  - Configured series prefixes: "Kuvin aluesarja:", "Hyvät Kuvat-kerho:", "Hopeatähti-sarja:", and "Kino Manttu:" (no meaning).
  - A trailing parenthesis opening with a configured word ("tekijävierailu…", "vapaa pääsy…") is a note, closed or not, and is dropped.
  - Festival rows keep their full title ("Kuopion mediataidefestarit: Näytös B"), as the part after the colon means nothing alone.
- **Links are not used:** the rows link to reused pages of other films (`/kino-manttu-digger/` holds "Two Seasons, Two Strangers"), or even to an image. Tickets are sold at the door only ("lipunmyynti vain Kuvakukossa", "Ei ennakkovarauksia … vain käteinen"), so `booking` is `door` and every screening links to the programme page.
- **No ids:** a screening is venue, title and start minute.
- **Kino Manttu** publishes every other weekend, so its section is often a weekend already past: no screenings in the window is normal for it.
- **Film pages:** one GET per linked title in the window, paced 1.5 s (images and off-site links skipped). A facts line **[V]**: "Italia 2025 • draama • 133 min • K7 • kieli: italia • tekstitys: suomi/ruotsi".
  - The first segment's year is the production year; "K7" is K-7; "tekstitys: –" stays unknown.
  - Exactly one such line (a runtime segment, all segments short), or nothing is read.
  - **A page counts only when its `<h1>` names the row's film:** pages are reused (`/the-invite/` holds LA GRAZIA, `/kino-manttu-digger/` other films).
  - Values outside the Finnish classes are flagged, not published ("K17" on Matka Piemonteen, a typo for K-7).
- **Not read:** `/liput/` states each cinema's ticket price **[A]** (Leffavuoro), with exceptions for outside organisers; left out.
- **Coordinates:** Kuvakukko: OSM node 5520821567. Manttu: OSM way 487580170 (the building on Mantunsuora); the cinema gives its address as Vesitornintie 1.
- **First run:** 18 films, 35 screenings (all Kuvakukko), no warnings. With film pages, Rose, Tony and Matka Piemonteen match too; what stays unmatched is festival shows and classics (aliases).

---

## Iso-Hannu (its own PHP site)

Probed 2026-10-14, four GETs. Adapter: `packages/fetcher/src/providers/isohannu/`, site in `sites.ts`. Origin: Leffavuoro's `scripts/providers/isohannu.py`, re-verified.

- **Programme:** `GET https://www.isohannu.fi/` renders `#showtable`, a week ahead **[V]**:
  - an `h3.showtable-title` per day, with the year ("Keskiviikko 14.10.2026");
  - then one `.showtable-container` per hall (`.showtable-hall`: Sali 1–3), one `.showtable-row` per screening.
- **A row** sits inside a link to the film's page, `/leffasivu.php?id={film}`; that id is the film, not the run. The row holds:
  - `.showtable-time` and `.showtable-name`, titles in capitals, as published;
  - the ticket link **nested inside** the film link (`http://lipunmyynti.isohannu.fi/app/movies/{film}/shows/{show}/products/list.html`). The page is parsed with htmlparser2, which keeps that nesting; an HTML5 parser would undo it.
  - The show id from the ticket link is the screening's id. The link is copied as printed (http) and never requested.
- **Tags:** `showtable-{name}` classes, mapped in the site config:
  - `children` → kids, `premiere`, `finalshow` → last-screening, `3d` → 3D;
  - `tickets` (the buy button) is ignored; unknown ones go to `unmappedLabels`.
- **Not screenings:** "Salissa yksityisvaraus" (a private booking of a hall) has a row and a ticket button; titles listed in the config are skipped.
- **Film pages:** one GET per film in the window, paced 1 s. `#kuvaus` holds "Label: value" lines between `<hr>`s **[V]**:
  - "Elokuvan kesto: 109 min";
  - "Elokuvan ikäraja: K16" (written without the hyphen);
  - "Genre: draama";
  - "Puhekieli: englanti", or several ("Ruotsi, Italia").

  No subtitles are stated, so they stay unknown. A failed page gives `film-page-missing`.

- **Not read:** prices. The front page states Mon–Thu and Fri–Sun tariffs, but there are surcharges for films over two hours, and public holidays move the tariff.
- **Coordinates:** OSM way 128190368 "Iso-Hannu"; the address is from the cinema's own page (Savilankatu 4, 26100 Rauma).
- **First run:** 18 films (all matched to TMDB), 83 screenings over 7 days, no warnings.

---

## The Events Calendar (WordPress): Ritz Vaasa, Tähti Kino Muhos

Probed 2026-10-14, two GETs. Adapter: `packages/fetcher/src/providers/tribe/`, sites in `sites.ts`. Origin: Leffavuoro's `scripts/providers/tribe.py`, re-verified.

- **API** **[V]**: `GET {base}/?rest_route=/tribe/events/v1/events&per_page=50&page=N&start_date=…&end_date=…&categories={id}`, public JSON with no key. `?rest_route=` works whatever the permalinks are. `total_pages` is followed to the end (budget 10).
- **A calendar is not a programme:** the film category is configured by its numeric id (Ritz 19 "kino", Muhos 106 "elokuvat"). An event outside it (a filter the server ignored) is skipped with `unclaimed-event`.
- **Times:** `start_date` (local) and `utc_start_date` must agree through Europe/Helsinki; a disagreement gives `invalid-start` and the event is skipped. All-day events have no time and are skipped (`all-day-event`).
- **Price:** `cost_details.values` with exactly one value is this screening's price (Muhos: 11 €, 13 €). Several values are a band ("10€ – 12€" at Ritz) and settle nothing.
- **Facts come from the description's labelled lines, never its prose:**
  - Ritz writes English labels ("Language: English, Lithuanian", "Subtitles: Finnish, English") and a runtime line ("114 min");
  - Muhos uses headings: "Ikäraja sallittu." / "Ikäraja K-7. Aikuisen seurassa …", or "Kesto 2 h 38 min | K-16 | Liput 13 €".
- **Titles:**
  - Muhos ends every title in "-elokuvanäytös" (a configured suffix).
  - Ritz puts the year ("Wholetrain (2006)") or an age limit ("Knitting Cinema! (K18)") in a trailing parenthesis; both are read off the title.
  - Other parentheses stay: "Two Seasons, Two Strangers (Tabi to hibi)".
- **Event series** ("Knitting Cinema!", "Ritz Horrorfest!") are listed as events of their own name; which film plays is not stated, so they stay unmatched.
- **Tickets:** at the door at both ("sold at the door", "ovelta"); `ticketUrl` is the event's own page, copied.
- **Not read:** images (a generic calendar picture at Muhos; posters come from TMDB) and synopses.
- **Coordinates:** Ritz: OSM node 3060592153 (Kirkkopuistikko 22a, 65100 Vaasa). Tähti Kino: OSM node 4946909729, the cinema at Muhostie 2, the address the events' venue gives ("Muhoksen Koivu ja Tähti -sali").
- **First run:** Ritz 6 films, 10 screenings; Muhos 4 films, 17 screenings; no warnings.

---

## Kino Engel (WordPress, the Johku schedule rendered server-side)

Probed 2026-10-14 from a home connection: the front page, then the film pages. Adapter: `packages/fetcher/src/providers/engel/`, site in `sites.ts`. Origin: Leffavuoro's `scripts/providers/engel.py`, re-verified.

- **Access:** kinoengel.fi (SiteGround) challenges datacenter addresses with a captcha **[A]** (Leffavuoro: HTTP 202 and `SG-Captcha: challenge`). From home it answered 200 with the page **[V]**. A challenge fails the pull with a clear error, so the previous data stands; it is never solved or worked around. Like Finnkino, this runs from the maintainer's machine only.
- **The page:** a WordPress plugin renders Johku's schedule on the cinema's own server; we read only the HTML. Johku and its API key are never touched **[V]**.
  - `.rs-johku-movies` holds one `.johku-movie-matrix` per day, its id the full date (`rsj_2026-10-14`), so no year is inferred.
  - Each `.rs-johku-schedule` row has `.movie-name`, "Ke 14.10." (checked against the block's date) and "klo 18:30", in a link to the film's page `/elokuva/{slug}/`, where "Osta liput" leads. That link is the ticket link.
- **Every day appears twice** on the page (about 110 rows for 55 screenings); a screening is film plus start minute, so the copies merge.
- **"Coming soon" entries** have an opening day and no time ("Pe 30.10. Osta liput", "Lue lisää"); they are not screenings and are skipped.
- **Strands:** "BARNSÖNDAGAR:" (series, kids) and "KESÄKINO:" (the summer outdoor screen; series) as title prefixes.
- **Film pages** (`/elokuva/{slug}/`, one GET per film in the window, paced 1 s): `<label>`/`<span>` pairs **[V]**:
  - ALKUPERÄINEN NIMI (original title) and KESTO ("1h 34 min");
  - LISÄTIEDOT "puhuttu kieli: saksa" (the spoken language; KIELI only says "Alkuperäinen");
  - TEKSTITYS "Suomi-Ruotsi", or "Ei tekstitystä" (none).

  The runtime is what lets the matcher link title-only listings like "Rose". The age limit is **not** read: every page seen says "Ikäraja ei vielä tiedossa" while its CSS class names a limit. A failed page (the Barnsöndagar post was a 404 once) gives `film-page-missing`.

- **Not read:** posters (Johku's images; TMDB only), seats, prices.
- **Coordinates:** OSM node 2493674692 "Kino Engel" (Sofiankatu 4, 00170 Helsinki).
- **First run:** 16 films, 49 screenings, no warnings; 9 matched from the front page alone, all 16 once film pages were read.

---

## Linked Events (Helsinki, Espoo): Kino Helios, Kanneltalo and Vuotalo, Kannusali

Probed 2026-10-15. Adapter: `packages/fetcher/src/providers/linkedevents/`, sites in `sites.ts`.

- **Why not Malmitalo's own calendar:** Leffavuoro (`helios.py`) POSTs to Malmitalo's `EventCalendarService.svc/GetEvents`; we prefer GET. The same events are in the city's open **Linked Events** API **[V]**: `GET https://api.hel.fi/linkedevents/v1/event/?location=tprek:8740&start=…&end=…&page_size=100&sort=start_time`, with `meta.next` followed to the end (budget 10 pages).
- **License:** the city publishes Linked Events data under CC BY 4.0 **[A]**. It is credited on every page of the website, in the OpenAPI description and in the MCP server's text.
- **A culture house's calendar is not a programme:** Malmitalo's place also holds concerts, courses (Nuorten elokuvakerho) and library groups. An event is a screening only when its title carries a configured label **[V]**:
  - "Tony (16) – Kino Helios" (the cinema's name);
  - "HopeaCine: …" (series, seniors);
  - "… – Yleisön suosikit" (series).

  Doc Helios is another strand of the house and is not read.

- **Fields** **[V]**:
  - `start_time` is UTC.
  - The age limit is in parentheses after the title: "(16)", "(S)".
  - `offers[0].price.fi` is "9 €" (a plain amount is published) and `is_free` means free.
  - `offers[0].info_url.fi` is the lippu.fi ticket page, copied; otherwise the house's own `info_url`.
  - `event_status` "EventCancelled" and "EventPostponed" are skipped; "EventRescheduled" (on almost every event, meaning edited) is kept.
  - Ids ("kulke:68847") are source ids; our ids use a dash instead of the colon.
- **Coordinates:** OSM way 29553571 "Malmitalo" (Ala-Malmin tori 1, 00700 Helsinki).
- **Kanneltalo and Vuotalo** (2026-10-15) [V]: one site, `helsinginkulttuuritalot`, for the two houses with a public film strand: Kino Kuutamo at Kanneltalo (free Mondays, about monthly; "Aleksi Salmenperä: Isänpäivä – Kino Kuutamo | Maksuttomat maanantait") and HopeaCine at Vuotalo ("HopeaCine: Lapin sota, ohj. Aku Louhimies"). Their titles carry the director, so the site sets `credits`: a leading "Name Surname:" (two or three capitalised words) or a trailing ", ohj. Name" is dropped. Per site only, since elsewhere "Name: Title" is a franchise. School screenings (Yläkoulukino, Alakoulukino, Skidikino) and festivals carry no label and stay out. First run (60 days): 4 screenings, all matched.
- **Other houses:** Stoa, Caisa and Annantalo hold only school screenings, festival date ranges or holiday children's screenings (2026-10-15); a house showing films is a site entry with its place id and labels.
- **First run:** 7 films (all matched), 15 screenings, no warnings.

---

- **Kannusali** (Espoo, 2026-10-15) **[V]**: Espoo runs its own Linked Events instance; `GET https://api.espoo.fi/events/v1/event/?location=tprek:21430&…` answers like Helsinki's. Its `meta.next` points at the instance's canonical host (`espooevents.prod.espoon-voltti.fi`), so `next` is followed when it is an https events URL. Leffavuoro POSTs to `espoo.fi/api/events` instead; that is not needed.
  - Labels: "Elokuva: Kevlarsjäl (K12)", "Lasten viikonloppu, Elokuva: …" (kids), "… - Elokuvakonsertti" (event cinema). Plays and concerts at the house carry none and are not read. The age limit is "(K12)" or "(16)".
  - Free screenings (`is_free`); no ticket page, so screenings link the house's page.
  - License assumed CC BY 4.0 like Helsinki's **[A]**; credited with it.
  - Coordinates: OSM node 13744741583 (Kannusillankatu 4, 02770 Espoo).

## Elokuvateatteri Julia (Hyvinkää)

Probed 2026-10-15, one GET. Adapter: `packages/fetcher/src/providers/julia/`, site in `sites.ts`. Origin: Leffavuoro's `scripts/providers/julia.py`, re-verified.

- **The programme:** `GET https://juliaelokuvat.fi/ohjelmisto/` has one `div.elokuva` per film **[V]**:
  - `h2` title in a link to the film's page;
  - `div#b{id}` with the screenings, one per line: "15.10.26 klo 16:00, 1. sali". The year is published with two digits (20YY); the hall becomes "Sali 1".
  - Labelled facts after it: Ikäraja "S" / "7", Kesto "1t 28min" or "2t 55min + väliaika" (an intermission besides), Genre "Komedia Kotimainen" (spaces, or commas), Hinta "14€ / 12€" (two prices, not read).
- **Events:** an "Ooppera:" title prefix, or a genre listed in `eventGenres` (Ooppera, Baletti, Konsertti), makes the listing an event.
- **Tickets** at the door; each screening links the film's page.
- **Coordinates:** OSM node 2388923543 (Hämeenkatu 34, 05800 Hyvinkää; the number from the cinema's page).
- **First run:** 4 films, 19 screenings, no warnings; 3 matched, the opera left for an alias.

---

## Kino Vaakuna (Lohja)

Probed 2026-10-15, one GET. Adapter: `packages/fetcher/src/providers/vaakuna/`, site in `sites.ts`. Origin: Leffavuoro's `scripts/providers/vaakuna.py`, re-verified.

- **The front page** (`/etusivu.html`) has one `div.MovieCard` per film **[V]**:
  - the title (`h2`) and the film page (`/elokuvat/{slug}.html`, the film's id);
  - "Liput: 13 €" or "Liput: 15€ (lahja/sarjalippu +2€)": the first amount is published;
  - "Kesto: 1 h 42 min";
  - the age limit as an icon named after it (`icon/12.png`, `icon/s.png`);
  - a table of screenings.
- **Rows:**
  - "Ti 20.10. klo 14:40": no year, so it is inferred and checked against the weekday.
  - "Ke 14.10. klo 14:10 (dub)" carries the screening's version.
  - "ENNAKKO Ensi-ilta 31.10. klo 19:30" has labels (preview, premiere) and no weekday.
  - "Ensi-ilta 30.10.2026" is an opening day without a time and is skipped.
- **Reservations** by phone or email ("Varaa liput" leads to the film's page): `booking: "reserve"`.
- **Address:** Koulukatu 4, 08100 Lohja (the cinema's page and OSM way 857803366 agree; Leffavuoro's Laurinkatu 48 is out of date).
- **First run:** 12 films, 37 screenings, no warnings. "Heart Of Beast" (the site's spelling) needs an alias.

---

## Kino Kirkkonummi

Probed 2026-10-15, one GET. Adapter: `packages/fetcher/src/providers/kirkkonummi/`, site in `sites.ts`. Origin: Leffavuoro's `scripts/providers/kirkkonummi.py`, re-verified.

- **One Elementor page:** each film is an `.elementor-heading-title` followed by `.elementor-icon-list-text` rows, read in document order (a row belongs to the last heading) **[V]**.
  - "16.10. Perjantai klo18.00" / "18.10. Su klo18.00 / 21.10. Ke klo18.30": no year (inferred and checked against the weekday, full or short); two screenings may share a row.
  - Cast lists and notes are rows too; only rows shaped like a screening are read.
  - "Puhumme suomea" under a film marks its screenings dubbed into Finnish.
  - "Tulossa 23.10. alkaen" is an opening day, not a screening.
- **Every block is on the page twice** (desktop and mobile); a screening is film plus start minute, so the copies merge.
- **Titles** may be "Finnish / Swedish" ("Matka Piemonteen / Resan till Piemonte"), read into `title.fi` and `title.sv`.
- **Reservations by phone**; there are no film pages, so every screening links the page.
- **Coordinates:** OSM way 136880152 (Munkinmäentie 17, 02400 Kirkkonummi).
- **First run:** 4 films, 14 screenings, no warnings. Title-only, so Matka Piemonteen (aliased) and TONY need aliases.

---

## Bio Savoy (Maarianhamina / Mariehamn)

Probed 2026-10-15, one GET. Adapter: `packages/fetcher/src/providers/biosavoy/`, site in `sites.ts`. Origin: Leffavuoro's `scripts/providers/biosavoy.py`, re-verified.

- **HTTP only:** the host refuses port 443 **[A]** (Leffavuoro, 2026-09-15); `http://www.biosavoy.ax/` answered 200 **[V]**. Links are published as http.
- **The front page** (Drupal) has an `h2.block-title` "Filmvisningar - Sal 1" / "Sal 2" per hall, then rows **[V]**: `<a href="/film/{slug}"><span content="2026-10-15T18:00:00+03:00">18:00</span> - BORTGLÖMDA ÖN</a>`. The `content` attribute is the start, with date and offset: nothing is inferred. The slug is the film's id; the link (the film's page) is copied.
- **Titles are Swedish**, in capitals, stored as `title.sv`. The API falls back to the Swedish title when a listing has no Finnish one.
- **Reservations by phone**; no age limits or runtimes on the page.
- **City** is Maarianhamina, the Finnish name, like our other cities (Pietarsaari, Raasepori).
- **Coordinates:** OSM node 1459454818; the address is from the cinema's page (Nygatan 14, AX-22100).
- **First run:** 8 films (all matched), 36 screenings, no warnings.

---

## Kino Akseli (Nummela)

Probed 2026-10-15 from a home connection, one GET. Adapter: `packages/fetcher/src/providers/kinoakseli/`, site in `sites.ts`. Origin: Leffavuoro's `scripts/providers/kinoakseli.py`, re-verified.

- **Access:** kinoakseli.fi challenges datacenter addresses (SiteGround captcha) **[A]** (Leffavuoro); from home it answered 200 **[V]**. A challenge fails the pull; it is never worked around. Home pulls only, like Kino Engel.
- **The front page** (Elementor) **[V]**:
  - Each film's facts come **before** its heading: "Ikäraja : 12", "Liput : 14€", and on the month's-offer card "Kesto : 112min".
  - The film heading (`h2` with a link to `/elokuva-…`) follows.
  - The screenings come **after** it: "Näytösajat To 15.10. klo 17:45 La 17.10. klo 13:15 (dub)".

  The parser marks each heading in the page text and gives a film the last facts before its heading.

- **Elements run together in the text** ("Ikäraja : 12Liput"), so patterns cannot rely on word boundaries.
- **The month's-offer card** repeats a film with no screenings; it adds nothing.
- **No year:** inferred and checked against the weekday. "(dub.)" after a time marks that screening dubbed.
- **Tickets at the door**; screenings link the film's page.
- **City:** Nummela (a village of Vihti), as the cinema names itself.
- **Coordinates:** OSM node 8193549402 (Vihdintie 4-6, 03100 Nummela).
- **First run:** 7 films, 17 screenings, no warnings; Pikku Kummitus Lapanen keppostelee (no runtime here) aliased.

---

## Kino Hamina

Probed 2026-10-15, one GET. Adapter: `packages/fetcher/src/providers/hamina/`, site in `sites.ts`. Origin: Leffavuoro's `scripts/providers/hamina.py`, re-verified.

- **The town's own page**, moved to `https://www.hamina.fi/hyvinvointi-vapaa-aika/kino-hamina/` (the old `/asukkaalle/…` path redirects) **[V]**. One `.large-content-showcase` block per film:
  - title;
  - a paragraph of labelled fields: "Ikäraja: 7", "Kesto: 1 h 57 min" or "1 t 28 min", "Liput: 11€", "Versio: DUB" (and Ensi-ilta, Levittäjä, Ohjaus, not read);
  - a paragraph of screenings: "To 22.10. Klo 15:00 (Liput 8€)", no year (inferred and checked against the weekday). A price on the row overrides the film's.
- **Versions** by the page's own legend, in the site config: "OG = Alkuperäinen kieli, tekstitys suomeksi (ja) ruotsiksi" gives Finnish subtitles (the Swedish is hedged, not published); "DUB = Puhuttu suomeksi" gives dubbed Finnish.
- **Tickets at the door**, no reservations; screenings link the page.
- **Coordinates:** the page gives Isoympyräkatu 30 A, 49400 Hamina; OSM has no cinema there, so the point is the address geocoded with Nominatim (the building's café node).
- **First run:** 4 films (all matched), 18 screenings, no warnings.

---

## Elävienkuvien teatteri (Forssa)

Probed 2026-10-15: the listing and the film pages. Adapter: `packages/fetcher/src/providers/elavienkuvien/`, site in `sites.ts`. Origin: Leffavuoro's `scripts/providers/elavienkuvien.py`, re-verified.

- **Listing:** `/ohjelmisto/`. Film links (`ohjelmisto/{slug}/`, relative to `<base href>`) are read from `.movielifts` only; the sub-navigation shares the path space (`ohjelmisto/erikoisnaytokset/`) **[V]**.
- **Film pages** (one GET each, about 16, paced 1 s) **[V]**:
  - `h2` title;
  - `p.movielength`: "Kesto 1 h 52 min" and the age limit as an image's name (`agelimit_12.png`; `agelimit_notset` is none);
  - `div.screenings`: one line per screening, "to 15.10.2026 klo 17:00 | Osta liput | 13€ / 11€", the year printed. The line's link (`lipunvaraus/?movieid=…&date=…&time=…`, the cinema's own reservation page) is copied, never requested. A date without a time ("ke 16.12.2026", an opening day) is skipped.
- **No price:** every line has two fares and nothing says which applies.
- **A film page that fails** is `invalid-film-page`, which is missing data (the screenings are only on the film pages), so removals are not inferred that run.
- **Coordinates:** OSM node 6733240707 (Keskuskatu 1, 30100 Forssa).
- **First run:** 14 films, 48 screenings; 13 matched (Unesta tehty mies, title only, needs an alias).

---

## Kino Kuusamotalo (Kuusamo)

Probed 2026-10-15, one GET. Adapter: `packages/fetcher/src/providers/kuusamotalo/`, site in `sites.ts`. Origin: Leffavuoro's `scripts/providers/kuusamotalo.py`, re-verified.

- **WordPress's public REST route:** `GET https://kinokuusamotalo.fi/wp-json/wp/v2/posts?per_page=40&_fields=id,link,title,content`. One post per film, plus old notices (gift cards, closing times) **[V]**.
- **A film post** carries:
  - a list of facts: "-S-", "Kesto 1h 28min", "Liput 12€";
  - an "Esitysajat:" heading with lines like "Ke 14.10. klo 15 ja 19" (several times a day; no year, inferred and checked against the weekday).

  Posts without "Esitysajat:" are notices and are skipped.

- **The film's id** is the post id; screenings link the post. Tickets at the door.
- **Coordinates:** OSM way 167231017 "Kuusamotalo"; the address is from the cinema's page (Kaarlo Hännisen tie 2, 93600 Kuusamo).
- **First run:** 1 film (matched), 7 screenings, no warnings. The programme is small; Lapin sota has a post but no times yet.

---

## Lieksan Kino

Probed 2026-10-15, one GET. Adapter: `packages/fetcher/src/providers/lieksa/`, site in `sites.ts`. Origin: Leffavuoro's `scripts/providers/lieksa.py`, re-verified.

- **One hand-written page** (`https://www.lieksanelokuvat.net/`) **[V]**:
  - `#section-b` ("Elokuvissa nyt") has one `article.entry` per film: `h3` title (capitals), "Liput: 13 €", "Kesto: 112 min", the rating as an icon's name (`rating-icon-12.svg`, `-s`), and `.showtimes li` lines.
  - Lines read "La 17.10. 15.00"; no year (inferred and checked against the weekday). A note may follow the time: "Tekstitetty" means Finnish subtitles; any other note is flagged as unmapped.
  - `#section-c` ("Tulossa esitettäväksi") uses the same markup for coming films and is not read.
- **Tickets at the door** ("Lieksan kulttuurikeskuksen aulasta noin 30 minuuttia ennen"); screenings link the page.
- **Coordinates:** OSM node 14184528958 "Brahe-sali", in the culture centre (Pielisentie 9–11, 81720 Lieksa, from the cinema's page).
- **First run:** 3 films (all matched), 7 screenings, no warnings.

---

## Elokuvateatteri Marita (Outokumpu)

Probed 2026-10-15, one GET. Adapter: `packages/fetcher/src/providers/marita/`, site in `sites.ts`. Origin: Leffavuoro's `scripts/providers/marita.py`, re-verified.

- **The front page's `#show-times` module** has one `.movie-info` block per screening **[V]**:
  - `h3` title linking the film's page;
  - "Hinta: 10 €" (a single amount is published; "10/8 €" is not);
  - "Kieli: Suomi", the print's spoken language (no subtitles are stated anywhere);
  - `img.age-img` named after the limit (`12.png`, `s.png`); the `label-img` images beside it are content warnings, not ratings;
  - the date with its year ("17.10.2026") and "klo 16.00".
- **The film pages** carry runtime and genre **[A]** (Leffavuoro); not read yet.
- **Tickets at the door**; screenings link the film's page.
- **Coordinates:** OSM node 7202242999 "Elokuvateatteri Marita" (Koulukatu 1, 83500 Outokumpu).
- **First run:** 4 films (all matched), 5 screenings, no warnings.

---

## Kino-Huovi (Harjavalta)

Probed 2026-10-15, one GET. Adapter: `packages/fetcher/src/providers/kinohuovi/`, site in `sites.ts`. Origin: Leffavuoro's `scripts/providers/kinohuovi.py`, re-verified.

- **A Duda front page:** one `.postArticle` card per film; the `.postDescription` text holds everything **[V]**:
  - groups of screenings: "12.10. MA klo 18.00" or a range with its weekdays, "23.-27.10. PE, LA, SU, MA ja TI klo 18.00", several groups per card;
  - "Dub." (dubbed into Finnish), "Kestoaika n. 2t 35min." (runtime), "Liput 15€." (a bare amount is published).
- **A range expands only when its weekdays prove its dates,** one weekday per date in order, ending on the range's last day. Otherwise the group is not placed and warns. There is no year: it is inferred, and the weekdays check it.
- **The card's link is a recycled alias** (Kerro kaikille at `/kero kaikille`, Lapin sota at `/kopio-seuraavasta-…`), so the film is its title and screenings link the front page.
- **No rating** is printed. Tickets at the door.
- **Coordinates:** OSM way 1154064070 "Kino-Huovi" (Harjavallankatu 33, 29200 Harjavalta).
- **First run:** 3 films (all matched), 8 screenings, no warnings.

---

## Elokuvateatteri Matin-Tupa (Ylistaro)

Probed 2026-10-15, one GET. Adapter: `packages/fetcher/src/providers/matintupa/`. Origin: Leffavuoro's `scripts/providers/matintupa.py`, re-verified.

- **`/ohjelmistossa/`** renders one `div.col-sm-6` per film **[V]**:
  - an `h2` link to `/elokuvat/{slug}/` (the slug is the film's id);
  - "Esitysajat:" lines ("ti 13.10. klo 19.20"; no year, inferred and checked against the weekday);
  - "Liput:" (a bare amount is published; "Alle 9 -vuotiaat 11 €, muut 14 €" is not), "Kesto: 1 t 28 min", "Genre:";
  - the rating image `ikaraja_{sallittu|7|12|16|18}`;
  - free notes, of which "Puhumme suomea" (dubbed) and the KAVI sentence are read.
- **Tickets at the door.** Ylistaro is part of Seinäjoki; OSM way 243044340 (Västilänkuja, no number).
- **First run:** 5 films, 16 screenings, no warnings. Unohdettu saari is listed at 98 min (TMDB 109), so it needs an alias.

---

## My Calendar (WordPress): Pyhäsalmen VPK

Probed 2026-10-15, two GETs. Adapter: `packages/fetcher/src/providers/mycalendar/`, sites in `sites.ts`. Origin: Leffavuoro's `scripts/providers/vpk.py`, re-verified.

- **API** **[V]**: `GET {base}/wp-json/my-calendar/v1/events?from=…&to=…&category=1` returns `{date: [occurrence…]}`, or `[]` for none. Each occurrence has:
  - `occur_id` (the screening's id), `event_title`, `category_id`;
  - `occur_begin` (local) and `ts_occur_begin` (Unix), which must agree.

  An occurrence outside the configured category is skipped with `unclaimed-event`. Events carry no location, runtime or rating.

- **Price:** the cinema's page says "Elokuvalipun hinta: 12 euroa", one price for every screening, read by a configured pattern. If that page fails, the programme still publishes, without a price.
- **Pyhäsalmen VPK** (a volunteer fire brigade's cinema since 1944): category 1 "Elokuvat"; tickets at the door; screenings link the cinema's page.
- **Coordinates:** Palotie 4, 86800 Pyhäsalmi (from its page), geocoded with Nominatim; OSM has the building unnamed. The city is the municipality, Pyhäjärvi.
- **First run:** 2 films, 7 screenings, no warnings. Late Lammas is aliased (no runtime to match on).

---

## Navettakino (Konnevesi)

Probed 2026-10-15, one GET. Adapter: `packages/fetcher/src/providers/navetta/`. Origin: Leffavuoro's `scripts/providers/navetta.py`, re-verified.

- **The front page is prose** (WordPress blocks) **[V]**. After the "Tulevan viikonlopun näytökset" paragraph:
  - screening lines, either "Pirjo i Sverige la 17.10 klo 15:00" (title on the line) or a title line then "la 17.10 klo 15:00";
  - film blocks: a title paragraph, a figure (the poster, not read), the cinema's synopsis (not read), and a facts line "S, 88 min, liput 10 €" / "Kesto 1 h 27 min, K12, liput 10 €".
- **Each block's facts** attach to its title (the paragraph before its figure). A screening may be listed twice (in the list and in its block); film plus start minute makes it one.
- **No year** in the dates: inferred and checked against the weekday. The editor sometimes splits a title's markup ("Presidentin kyydity</strong>s"); the text is read, not the markup.
- **Weekends only, tickets at the door.**
- **Coordinates:** the cinema's contact page gives the visiting address, Pyhälahdentie 972, 44370 Konnevesi, and GPS N 62° 48.330′, E 26° 5.232′ (`geoSource: manual`); it is not in OSM.
- **First run:** 1 film (matched), 1 screening, no warnings.

---

## Localhub (a town's event calendar): Kino Akustiikka

Probed 2026-10-15, one GET. Adapter: `packages/fetcher/src/providers/localhub/`, sites in `sites.ts`. Origin: Leffavuoro's `scripts/providers/localhub.py`, re-verified.

- **The calendar's search** (Ylivieska's `tapahtumat.ylivieska.fi`) **[V]**: `GET {base}/api/collection/{collection}/content/general-search?lang=fi&country=FI&q=kinoakustiikka&mode=event&sort=score` returns `{pages, count}`, one page per screening (31 on 2026-10-15).
- **A page is a screening only when** its `globalContentCategories` include "Movies / Cinema" and its hashtags include the cinema's; the calendar is the whole town's.
- **Fields:**
  - `event.dates[].start` (UTC), its timezone required to be Europe/Helsinki;
  - cancelled dates skipped, sold-out read;
  - `price` `{min, max, currency}`, published only when min equals max (12 €);
  - `event.urlPurchaseTicket`: the town's shop, copied;
  - the rating as a hashtag ("k-12");
  - a trailing "(2026)" in the name is the year.
- **A cut answer** (`count` larger than the pages returned) is missing data.
- **Coordinates:** OSM node 2507982005 "Kulttuurikeskus Akustiikka" (Koulukatu 2 B, 84100 Ylivieska).
- **First run:** 10 films, 26 screenings, no warnings. Late Lammas and Resident Evil (no runtime here) are aliased.

---

## Bio Pallas (Karjaa, Raasepori)

Probed 2026-10-15, one GET. Adapter: `packages/fetcher/src/providers/biopallas/`. Origin: Leffavuoro's `scripts/providers/pallas.py`, re-verified.

- **A Wix front page, server-rendered:** the rich-text blocks (`[data-testid=richTextElement]`), in document order, are the structure **[V]**:
  - the title block: "Kerro kaikille", an optional version line ("På svenska", "Suomeksi"), "1h 52min -K12-";
  - the date-and-time block: "Ke/Ons 14.10" and "Klo 19.00" (bilingual weekday, Finnish first; no year, inferred and checked against the weekday);
  - the price block: "13€", or "12€ med kaffeserv./kahvitarjoilulla" (one amount is published; "22/25€" is not).

  Component ids change on every edit, so nothing is keyed on them. Day headings repeat the dates and are not read. The coming-soon list has a lone date with no "Klo" and is not a screening.

- **Tickets at the door**; screenings link the page.
- **Coordinates:** OSM node 2068950851 "Bio Pallas" (Nils Grabbegatan, no number, so no address). The city is Raasepori, as with Bio Forum.
- **First run:** 11 films, 23 screenings, no warnings. Hetki ennen valoa is listed at 97 min (TMDB 87), so it waits for an alias.

---

## Freehand programmes: Movie Company Alatalo and Huvimylly

Probed 2026-10-15. Adapter: `packages/fetcher/src/providers/alatalo/`, sites in `sites.ts`. Origin: Leffavuoro's `alatalo.py` and `huvimylly.py`, re-verified. One author types both programmes by hand, in the same grammar **[V]**:

- **Sources:**
  - Alatalo, a touring operator in northern Finland: `http://www.moviecompanyalatalo.fi/` (HTTP only; 443 refused).
  - Huvimylly in Raahe: its WordPress front page's content through `/wp-json/wp/v2/pages?slug=etusivu`.
- **Lines** (split on block tags and `<br>`):
  - **Town heading** (Alatalo): "Haapajärvi Teatterisali", matched by its first word in the config. A line followed by a date heading that names no configured town clears the venue, and its rows warn `unclaimed-venue` instead of landing under the town above.
  - **Date heading:** "Lauantaina 17.10", the weekday by its first two letters (misspellings are common). No year: inferred, and checked against the weekday. Consecutive headings share the rows below them.
  - **Row:** "Klo 14.00 Title -k16/13-", also "16.30 Title", "Kl 18.00". The rating marker ("-k12/9-", "k16/13", "-s-") closes the title; the second number (the age allowed with an adult) is not read. "k6/13" is a typo and is flagged.
  - **Continuation:** a row without a marker takes the next line as the rest of its title when that line has a marker or the row has no title yet ("Klo 13.00" then "Pikkuli ja Tähtipeura -s-"). A bare marker line ("-k16/13-") rates the unmarked rows of one film above it.
- **Price:** the page's one line ("Liput elokuviin vain10-€"; Huvimylly "Liput vain 10-€"), by a configured pattern. Tickets at the door, cash; screenings link the page.
- **Titles are typed freely** ("Kero se kaikille", "Pirjo", "Saapasajalkakissa tekiöiltä Unohdettu saari"); they're kept as published and aliased by hand.
- **Coordinates:**
  - Kemijärvi's culture centre: OSM way 221824429.
  - Huvimylly: Raahesali, OSM node 8827057758.
  - Pudasjärvi (Pohjantähti), Haapajärvi (Teatterisali) and Kiuruvesi (Kiurusali): not in OSM under these names, so no coordinates yet (`venue-without-geo`).
- **First run:** Alatalo 7 films, 13 screenings in four towns; Huvimylly 2 films, 3 screenings.

---

## Kino Regina (KAVI, Oodi): the first POST source

Probed 2026-10-15. Adapter: `packages/fetcher/src/providers/regina/`. Origin: Leffavuoro's `scripts/providers/regina.py`, re-verified.

- **The programme is only a POST** **[V]**: `POST …/themes/kinoregina2/assets/functions/getShowtimesMoviesV2.php` with the form field `getShowtimesMovies={YYYY-MM-DD}` answers HTML for the whole published window from that date (40 screenings to 1.11. on 2026-10-15). A GET of the same address answers empty; the programme page itself draws the list with script; KAVI's shop has no open schedule; Linked Events does not carry it. The maintainer allowed this read-only POST (it is the request the cinema's own page makes) through `HttpClient.postForm`.
- **Rows:** `div.movie`, each with:
  - `a.title`, linking `/elokuva/{id}` (the film's id; titles are in capitals);
  - `.add-to-calendar .start`: "15-10-2026 17:30", with its year;
  - `a.add-to-cart`: KAVI's shop for the screening (`kauppa.kavi.fi/…/event_buybox/show/{id}`), copied, never requested.

  "grey" rows have closed online sales but are still screenings. Rows without a film link (events) are skipped.

- **Film pages** (`/elokuva/{id}/`, GET, one per film in the window, paced 1 s):
  - `#main-content h1` "CASABLANCA (1942)" gives the **year**, which the classics need to be matched;
  - the `.movie-details` grid: Maa ("Espanja/Portugali/Ranska"), Tekstitys ("suom. tekstit/svenska texter", "ei tekstitystä"), Kesto ("102 min"), Teemat (series), Kopiotieto ("35 mm", "DCP", "4k dcp" → projection), Ikäraja (an image, `alt="Ikäraja: K12"`).
- **Coordinates:** OSM node 9628528752 "Kino Regina" (Töölönlahdenkatu 4, 00100 Helsinki, as on its info page).
- **First run:** 30 films, 40 screenings, no warnings; 17 matched with the years. The rest are lectures and workshops, Laurel & Hardy shorts, and classics TMDB's search ranks below namesakes (Casablanca, Nosferatu): aliases.

---

## Kurikan Kino (Kurikka)

- **Found** through elokuviin.com's list of cinemas (2026-10-15); not in Leffavuoro.
- **The front page** [V] has one `li.elokuva-thumb` card per film: the film page link, `.elokuva-nimi` with the age class (`ikaraja-7`, `ikaraja-s`), the runtime as "1 h 49 min", one price ("13 €"), and each showtime as `span.elokuva-aika`. Cards without times are coming soon and skipped.
- **The stamp** `esitysaika` is the Helsinki wall-clock time written as if it were UTC (1791572400 is 19:00Z, printed "pe 9.10. 19:00") [V]. It gives the year; the printed day and time must agree with it, or the row is `invalid-row`.
- **Times are printed twice** (the desktop card and a mobile copy); only the card's own copy is read.
- **The page lists the past week too**, so the window filter drops the old ones.
- **Tickets:** the site states no way of buying, so booking is `info` and each screening links to the film's page.

## KisaKino (Saarijärvi)

- **Found** through elokuviin.com's list of cinemas (2026-10-15); not in Leffavuoro. Run by the sports club Pullistus in the town hall's Saarijärvi hall.
- **The front page** [V] links each film (`h2.etusivu-otsikko a`) but shows only its next three screenings, so each film's page is read too (at most 30).
- **The film page's sidebar** [V]: "Kesto 02 h 38 min", "Lipun hinta: 12€", then "Elokuvan näytökset" and one line per screening ("La 24.10.2026 16:00"), whose weekday must fit the date; the age image (`k16.png`) closes it.
- **A failed film page** is `invalid-film-page` (its screenings are missing), so removals are not inferred that run.
- **Tickets** at the box office before the show: booking `door`, each screening links to the film's page.

## Pajakkakino (Kuhmo)

- **Found** through elokuviin.com's list of cinemas (2026-10-15); not in Leffavuoro. The front page is an Instagram feed; the programme is one WordPress post per film, read through `/wp-json/wp/v2/posts` (one GET) [V].
- **A film post** [V]: a facts line ("Draama, jännitys I 1h 57min I 2.10.2026 I AUDIO englanti TEKSTIT suomi": genres, runtime, release date, audio and subtitles), the age image (`ikaraja_12.png`, from the distributors' press service), then "ESITYKSET:" and one row per screening ("PE 16.10. KLO 15:30", also "SU 18.10 KLO 18:00" and "PE 9.10 KLO.16:30"). No year: the nearest date whose weekday fits.
- **Cancelled screenings** are struck through (`<del>`) with "PERUTTU!" below; they are skipped, so ingest marks them removed [V].
- **Tickets** at the box office or reserved by phone, WhatsApp or the site's form (never requested): booking `reserve`. Prices depend on age and length, so none is published.
- **Coordinates and address** from OSM (way 238296413, Rajakatu 56).

## Bio Marlon (Kauhajoki)

- **Found** by the maintainer (biomarlon.fi), 2026-10-15; not in Leffavuoro.
- **The front page** [V] is Elementor: one text block per film with the title in `h1` (linking to nytleffaan.fi, not used), one `h4` per screening ("pe 16.10. 19:00"; no year, the nearest date whose weekday fits) and a facts paragraph ("K-7/4 1 t 40 min 13 €": rating, runtime, price; "0 €" is free).
- **Row variants** [V]: "Ensi-ilta pe 16.10. 15:30" is a premiere (`premiere` tag); a row without a time ("Ensi-ilta pe 23.10.", "Tulossa") is announced, not on; "(ke 21.10. 10:00 yksityisnäytös)" is private and skipped. "Suomea puhutaan!" below the facts marks a Finnish-dubbed print.
- **Tickets** at the door: booking `door`, links to the front page. The programme is published on Mondays, 1.5 weeks ahead.
- **First run:** 17 screenings of 5 films, no warnings; a local documentary (not on TMDB) stays unmatched.

## Kino-Kuva (Teuva)

- **Found** by the maintainer (kinokuva.fi), 2026-10-15; not in Leffavuoro.
- **Encoding:** the page is ISO-8859-1 and says so in Content-Type [V]. `getText` decodes by the stated charset (`decodeBody` in `lib/http.ts`), since `Response.text()` always assumes UTF-8.
- **The front page** [V]: one table row per film, `td.elokuva` with the `h1` title and "Kesto: 1 h 52 min -K12-" (runtime, rating), then `td.elokuva_tiedot pre` with lines: rows ("KE 14.10. KLO 19.00", "TO 15.10. KLO 14.00 JA KLO 17.00"; no year, the weekday must fit), notes, the price ("Liput 14,-" or "Ilmainen sisäänpääsy!" for free).
- **Notes read** [V]: "ENNAKKONÄYTÖKSET!" tags the film's rows `preview`; a heading ending in a colon ("Puolan elokuvaviikot:") is the series; "englanninkielinen tekstitys" (also misspelt "teksitys") gives the subtitle language. Other notes ("ENSI-ILTA 30.10.", "SYYSLOMAN KUNNIAKSI") are ignored.
- **Tickets** at the door: booking `door`, links to the front page.
- **First run:** 9 screenings of 5 films, no warnings; 4 matched.

## Cinema Levi Summit (Kittilä)

- **Found** by the maintainer (via levi.fi, which links levisummit.fi/cinema/), 2026-10-15; not in Leffavuoro.
- **The cinema page** [V] has a show calendar for the current week: one `section.levi-summit-cinema-show-day-container` per day with its date in `h3` ("Torstai 15.10.2026"), then one card per screening with the `h4` title, `.movie-showtime` ("To klo 14:00"; the weekday must be the day's) and `.movie-tickets` (the adult price; the child price beside it is not read).
- **Film pages** are on the operator's WordPress (`kassiopeia.fi/levi-summit/…`) and are copied as the screening link; booking `info`.
- **No runtime** is stated, so titles that share a name with other films need aliases (The Odyssey, Ryhmä Hau).
- **Address:** the site states none; OSM's Levi Summit node (Levin portaat, 99130 Sirkka, Kittilä).

## Kino Tervakoski (Janakkala)

- **Found** by the maintainer (janakkala.fi/kino), 2026-10-15; not in Leffavuoro. Run by the municipality's youth services in Tervakosken Seuratalo.
- **The programme page** [V] (`/kino/ohjelmisto-2-2-2/`, the municipality's WordPress path, which may change): day headings in bold ("Keskiviikko 14.10.", no year; the weekday must fit the nearest date), then one paragraph per screening ("Klo 17.00 – Pirjo i Sverige (S), kotimainen, komedia, kesto 1 t 28 min, lippu 10,00 €"). The title closes with its rating in parentheses; "SUOMEKSI PUHUTTU" marks a Finnish-dubbed print. The list ends at the first separator (`hr`) after the first day; posters and synopses follow it.
- **Tickets** at the door: booking `door`, links to the programme page.
- **First run:** 4 screenings of 4 films (the page lists the current week), all matched.

## Virtain Pirtti (Virrat)

- **Found** by the maintainer (virtainpirtti.fi), 2026-10-15; not in Leffavuoro.
- **The programme page** [V] (`/ohjelmistossa-nyt.html`, Weebly): one `div.paragraph` per film, its lines split by `<br>`: "Kerro kaikille K-12" (title and rating; "K-7 dub." is Finnish-dubbed), notes ("Ennakkonäytös" tags the rows `preview`, "(Ensi-ilta 30.10.)" is ignored), rows ("pe 16.10. klo 15.15*"; no year, the weekday must fit), a footnote for starred rows ("*16.10. ja 21.10. tekstitys suomeksi": those rows get Finnish subtitles) and "Kesto 1 h 52 min". A row may start with a zero-width space.
- **Tickets** at the door: booking `door`, links to the programme page.
- **Address:** the site states none; OSM's Virtain Pirtti node (Virtaintie 15, 34800 Virrat).
- **First run:** 10 screenings of 5 films, no warnings, all matched.

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

- **Kino Kaustinen** (2026-10-15): a real eTiketti tenant (kinokaustinen.fi) that Leffavuoro found with no programme in September; now five films, place line "KINO KAUSTINEN". One site entry. Coordinates: OSM way 768088981 (Pajalantie 19, 69600 Kaustinen) **[V]**.
- **The `data-dates` template** (2026-10-15) **[V]**: some sites' film pages moved a screening row's date from a `date-17.10.2026` class to a JSON attribute, `data-dates='["17.10.2026"]'`. The rows were then silently skipped: Savon Kinot (6 cinemas) and Leffabuumi (3) published nothing, and others lost part of their rows. Both forms are read now. A row inside the screenings block without a readable date warns `invalid-show` (missing data) instead of disappearing.

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

- **Pop Up Kino Helsinki** (2026-10-15): Kino Myyri's feed also carries Pop Up Kino's screenings (popupkino.fi, Myyri's owner) under the venue "Pop Up Kino Helsinki". Pop Up Kino screens at changing places (KOM-teatteri in Hakaniemi in October 2026, next the Salvation Army hall), and the feed names none, so the venue has **no address or coordinates**: it shows in Helsinki's listings but not on the map, with a `venue-without-geo` warning each pull **[V]**.

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
