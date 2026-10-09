# Data sources: Finnkino and BioRex

Investigated on 2026-10-09. Markers: **[V]** = verified with our own request, **[A]** = assumed, or read from a third-party source.

---

## BioRex

### Overview

- `biorex.fi` is a WordPress site (Polylang fi/sv/en, Yoast, custom theme) **[V]**.
- The ticket shop `webshop.biorex.fi` is AngularJS + Express **[V]**. **The platform is MyCloudCinema**: the cinema settings contain `webhook_url: https://api.biorex.mycloudcinema.com/…` **[V]**. The HTML's `<meta name="author" content="Unique X">` points to the developer (Unique X) **[A]**.
- According to Leffavuoro, the same MyCloudCinema `/webservices` API is used by Cine Mäntsälä (`mantsala.cine.fi`) and Gilda (`*.mycloudcinema.com`) **[A]**. The adapter can therefore later become a generic MyCloudCinema adapter.
- **Implementation:** [src/providers/biorex/](../src/providers/biorex/), run with `pnpm pull`.
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
- All of `finnkino.fi` sits behind Cloudflare bot protection: `403` + `cf-mitigated: challenge` **[V]**. `robots.txt` is behind it too.

### Old XML API: dead

- `/xml/TheatreAreas/` and `/xml/Schedule/?area=1014` return a 403 Cloudflare challenge **[V]**.
- Web Archive: `/xml/Schedule/` returned 200 XML until March 2025 and 404 on 4 Mar 2026 **[V]**.
- Old ids and `/websales/show/…` links do not carry over to the new system.

### Vista OCAPI (current)

- Base: `https://digital-api.finnkino.fi/WSVistaWebClient/ocapi/v1/` (Vista tenant `ODEFI`).
- `GET /sites` without a token **[V]**:
  ```json
  {
    "status": 401,
    "title": "Authentication Token Failed",
    "detail": "No global authentication JWT supplied, and is required for the current call."
  }
  ```
- According to [Shady-Dev/kino](https://github.com/Shady-Dev/kino) (`scripts/fetch_data.py`) **[A]**:
  - A JWT (`eyJ…`) is extracted from the HTML of `https://www.finnkino.fi/` and sent as `Authorization: Bearer <token>`.
  - Endpoints: `/sites` and `/showtimes/by-business-date/{YYYY-MM-DD}?siteIds=…`.
  - Showtime: `id, filmId, siteId, screenId, attributeIds, schedule.startsAt (ISO + offset), isSoldOut`.
  - `relatedData`: `films` (`id, title, originalTitle, releaseDate, runtimeInMinutes, genreIds, censorRatingId, synopsis, trailers`), `genres`, `screens`, `censorRatings`, `attributes`. 2D/3D, IMAX, 4DX, iSense and language/subtitle codes (e.g. `.FI-S`) are attributes.
  - Ticket link: `https://www.finnkino.fi/lipts/valitse-paikat/?showtimeId={id}`.
  - Cloudflare blocks datacenter IPs, so that project fetches from a home connection about 4 times a day.
- Vista's public documentation: [developer.vista.co](https://developer.vista.co/digital-platform/getting-started/conventions). The API returns 429 responses, but the limits are not published.
- Unknown: how far ahead schedules are available (the old XML allowed 31 days).

### Conclusion

HTML crawling does not help, since the same Cloudflare protection covers the HTML pages. The realistic route is to get the token with a (headless) browser from a residential IP and call the OCAPI JSON with it. This is fragile and legally grey. The sustainable route is to ask Finnkino (Odeon/AMC Nordic) for permission or partner access.

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
- **Finnkino:** the token is passed in the `FINNKINO_TOKEN` environment variable and obtained by a private local wrapper that is **not in the repository**. The fallback is a direct fetch in which an `eyJ…` regex picks the token from the front page HTML (works from a residential IP only). Language code fixes: `SE→SV`, `TU→TR`, `MA→ML`, `LI→LT`.
- **BioRex:** Leffavuoro reads WordPress `admin-ajax.php` (POST + a cinema selection cookie). We found a more direct route, `webshop.biorex.fi/webservices` (GET, no cookies).
- **Data model:** shaped for the frontend and string-heavy (`len: "129"`, `lang: "EN-A, FI-S, SV-S"`). Films are matched through TMDB (`enrich_tmdb.py`, 1,670 lines), with hand-written aliases.
- **Ethics rules (CLAUDE.md):** own User-Agent with contact details; no residential proxies, fingerprint spoofing or captcha solving; no booking or payment endpoints; ticket links are copied, never constructed.
- **License:** the code is **AGPL-3.0-or-later**. The data (`data/area-*.json`) and posters are **not** covered by the license; they belong to the cinemas. The README states explicitly that a fork grants no right to the data.
