# Ticketing platforms: what each one publishes and how it is read

Research notes, moved out of `IDEAS.md` on 2026-09-14 so that file can stay an index of
open work. Open items live in `IDEAS.md`, the dated decision records in
`docs/archive/2026-09-providers.md`, and accepted working rules in `CLAUDE.md`. Nothing
here is a rule.

Every reading below was taken as an ordinary visitor, through the same public interface
the cinema's own site uses. Booking, payment and administrative endpoints are not called
and are not inventoried; see "Access and ethics" in `CLAUDE.md`.

Each topic separates what was observed from what was concluded, because several
conclusions here were wrong the first time and the observations were not.

---

## BioRex

**Findings** (biorex.fi, probed 2026-08-26)

WordPress with `admin-ajax`. No auth, no nonce, no Cloudflare block. Twelve requests per
run, since `date=-1` returns every date at once.

```
GET  https://biorex.fi/elokuvat/                      # session cookie
POST https://biorex.fi/teatterin-valinta/   location={venueId}
POST https://biorex.fi/wp-admin/admin-ajax.php?lang=fi
     action=br_movies_handler&genre=-1&date=-1&format=-1&language=-1&activeType=showtimes
```

- The response is `{"posts": "<html>"}`: HTML inside JSON.
- **The cookie step is required.** Without it the answer is BioRex Verkatehdas rather
  than an error, so a missing session is wrong data, not a failure.
- `?cinema_id=` in page URLs is decorative; the cookie decides the venue.
- `f_cinemas={slug}` handles the within-city sub-filter (`all` / `helsinki` / `redi`).
- Each `.showtime-item` carries a `data-click-data-layer` JSON attribute with `movieId,
  movieName, showId, showCinemaId, showCinemaName, showDate, showTime, showDateTime`
  (ISO, +03:00) and `showWeekday`. That attribute is the data; text scraping is not.
- Also in the item: `.showtime-item__place__value` ("BioRex Tripla, Sali 6"),
  `.showtime-item__movie-rating` ("(K-16)"), `.showtime-item__format` (`["EN","FI&SV"]`,
  audio then subtitles), `icon-puhekieli` for a Finnish dub, a poster `data-srcset`
  (1080w variant on `web.biorex.mycloudcinema.com`) and a booking href through
  `biorex.fi/secure-redirect/`.
- Venue ids: 13 Helsinki Tripla, 14 Helsinki Redi, 1 Hämeenlinna, 9 Hyvinkää, 7 Kajaani,
  4 Pietarsaari, 10 Porvoo, 8 Riihimäki, 2 Rovaniemi, 12 Seinäjoki, 3 Tornio, 5 Vaasa.
- Dates are sparse (27–31.8, 1–3.9, then 5.9, 9.9, 11–13.9, 30.9): special events, not a
  rolling window. Read the `#dayselect` options rather than generating dates.
- Missing against Finnkino: runtime, genres, synopsis, sold-out state. TMDB covers
  rating, trailer and poster through `movieName`; runtime needs the film page.

**Inferences and open questions**

- `<input type="date">` cannot disable individual days, so dimming the sparse dates would
  need a custom picker. Deferred, and still unbuilt.
- Whether the sparse pattern is scheduling policy or a publishing lag was never
  established, and nothing here tests it.

**Status and next step**

Live as `scripts/providers/biorex.py`, twelve venues, cloud half. **Correction, checked
2026-09-14:** this note used to say the HTML-in-JSON is parsed "with BeautifulSoup". It is
not, and never was in the committed adapter. `biorex.py` parses with stdlib `re`
(`ITEM_RE`, `DL_RE`, `HREF_RE`), and `bs4` appears nowhere in the repository. See
`tooling-evaluation.md` for the measurement behind keeping it that way. No next step.

---

## Nexxo Scope

**Findings** (kinoset.fi, probed 2026-08-26; ten hosts swept 2026-08-29)

A WordPress plugin with a clean JSON API, so adding a cinema on it is a `SITES` entry
rather than a parser.

```
GET {base}/wp-content/plugins/nexxo-scope/public_api.php
    ?action=exportdailyshows&locationid=N&days=21&lang=fi&upcoming=0
-> {"shows": {"YYYY-MM-DD": [ {...} ]}}
```

- `upcoming=1` returns the coming-soon list with `startDate: null`; use `upcoming=0`.
- Fields: `movieTitle, startTime, klo, roomTitle, ageLimit, duration, genre,
  priceIncludingTax, posterurl, showId, code_language, code_subtitles, showTypeTitle`.
- Posters need the prefix `{base}/wp-content/plugins/nexxo-scope/banners/`.
- `code_subtitles` can be multi ("FI-SE") and splits to `FI-S, SE-S`; `OV` means
  unspecified. `code_external_title` is a distributor code, not a title.
- No per-show booking URL, so a showtime opens the programme page filtered to the
  location. That is why every Nexxo provider is registered `book="reserve"`.
- Kinoset ids: 1 Huittinen (Kino 1-2), 2 Loimaa (Kinema), 3 Sastamala (Bio). Their film
  week runs Friday to Thursday and is published on Tuesdays.
- The same API also exposes write actions. Not used, not probed.
- **A host is not a venue.** `ksek.fi` and `kinoaurora.fi` are one deployment with
  identical payloads at locationid 1 and 2; adding both would have published every
  showtime twice under two chain names in one city. `kinohirvi.fi` serves Bio Säde on
  locationid 4, in Mänttä, about 80 km from Kino Hirvi, while `biosade.fi` serves an
  empty programme. Ids were discovered by asking the endpoint, not by reading host lists.

**Inferences and open questions**

- Three hosts have answered 403 under load (`Server: LiteSpeed`, `openresty`, `Apache`,
  no CF-Ray), which reads as the origin rather than an edge. Whether closely spaced runs
  cause it is an open question that would need probing a third party's server to settle,
  so it stays an observation. See "A run reads unrelated hosts at once" in
  `docs/archive/2026-09-pipeline.md`.

**Status and next step**

Live as `scripts/providers/nexxo.py`, eight providers on six hosts, cloud half. No next
step; a further Nexxo cinema is a `SITES` entry.

---

## eTiketti

**Findings** (kotkanleffat.fi, probed 2026-08-26; second template 2026-09-02)

The API host `{customer}.etiketti.app/api/yleiset/...` sits behind Cloudflare, so the
adapter reads the cinema's own server-rendered pages instead.

```
/elokuvat/ohjelmistossa      -> movie links /elokuvat/{id}/{slug}
/elokuvat/{id}/{slug}        -> every screening for that film
```

Per screening, inside `<div class="item ... date-D.M.YYYY">`:

- the `date-27.8.2026` class carries the full date including the year; the time comes
  from `klo HH.MM`;
- `TRIO 123 | VIP-SALI`, but **Kinopalatsi screenings have no room and no `|`**, so the
  room has to be optional in the pattern. Requiring it silently dropped 17 showtimes.
- `Lippu 18,00€` and `Vapaat paikat 13/22` give the price and a real sold-out state.
- The booking link is `/salikartta?id=NNNN`.

Film level: `<h1>` title, `ikarajat/fi-16.svg` for the rating, `Kesto: 2 h 53 min` for
minutes, `Kieli:` / `Tekstitys:` for language tags, `<img class="poster-img">` for the
poster. About one listing plus fifteen film pages per run, paced 1.2 s apart.

**A second template exists.** Cinema Niagara renders screenings as `<div\n class="item
tampere date-3.9.2026">` with `<div class="time"><span>16.15`, `<div class="show-price">
13,00€`, `Paikkoja vapaana: 126/127`, tags in `movie-specs` and no place line, where Kotka
prints `KE 2.9. klo 20.00`, `TRIO 123 | SALI 2`, `Lippu 15,00€`, `Vapaat paikat 27/35`.
Labels carry no colon and genres sit under a label reading `genre`. `/?shows=all` renders
every screening twice, in a desktop and a mobile wrapper, which is why a screening is
keyed on its `/salikartta?id=` href.

**Only six of the twenty hosts render a theatre navigation** (measured 2026-09-14, one
listing per host), and the `match` text has to be looked for *inside* an anchor rather
than compared to the whole of it: Leffabuumi prints "Mikkeli Kinolinna" against the match
`kinolinna`.

**Inferences and open questions**

- Counting film links on a listing proved less than it reads as: Cinema Niagara served the
  listing and rendered its screenings in a template the parser of the day read as zero.
- The nineteen hosts without a navigation cannot have an empty venue confirmed, so they
  keep the previous file. That is the safe side and is not a defect to chase.

**Status and next step**

Live as `scripts/providers/etiketti.py`, twenty providers and thirty venues, four of them
on the local half. No next step.

---

## Vista, public XML services

**Findings** (savonkinot.fi 2026-08-27, korjaamokino.fi 2026-09-05)

Vista is the platform Finnkino also runs. A site that leaves its `/xml/` services open
needs no auth and is a `SITES` entry with a base URL and a venue list. Test a candidate
with `{base}/xml/TheatreAreas/`.

```
GET {base}/xml/TheatreAreas/                     -> ID + Name per area
GET {base}/xml/Schedule/?area={id}&nrOfDays=31   -> every Show in the window
GET {base}/xml/ScheduleDates/                    -> published date list
GET {base}/xml/Events/                           -> per-film synopsis, cast, credits
```

- No auth, no Cloudflare, datacenter addresses fine.
- `nrOfDays=31` is honoured, so one request per area covers the window. A one-day fetch is
  not enough: Kitee had 0 shows today and 7 in the window.
- Areas map to one or two theatres and each Show carries `TheatreID`, so venues split from
  the data.
- The richest field set of any provider: `OriginalTitle`, `LengthInMinutes`, `Genres`,
  `PresentationMethod`, four poster sizes, nested language elements with ISO codes and a
  per-show deep link in `ShowURL`. No seat counts.
- Shapes that need handling: `Rating` is `"K-7 (4)"` or `"Sallittu kaikenikäisille"`
  rather than a bare `"K-7"`, which a kids filter would silently miss; `dttmShowStartUTC`
  converts through `Europe/Helsinki`; `SubtitleLanguage2` can carry a `Name` with an empty
  ISO code; `TheatreAuditorium` is `"Joensuu, Tapio 4"`, so the city is stripped and a room
  repeating the venue is blanked; synopsis tag names vary between versions.
- Finnkino's own host answers a plain client a Cloudflare challenge (403, `cf-mitigated:
  challenge`, probed 2026-09-13) and is read through OCAPI with a token instead. Its
  `/xml/` was never probed past the challenge.

**Inferences and open questions**

- Cinamon and other non-Finnish Vista users are untested.

**Status and next step**

Live as `scripts/providers/vista.py`, one site: Korjaamo Kino. Savon Kinot left Vista for
eTiketti on 2026-08-30. Next step, if anyone wants it: probe a non-Finnish Vista customer.

---

## Johku

**Findings** (kinoengel.fi 2026-08-29, four known Johku cinemas 2026-09-05)

Johku is the shop behind the button, not a listing template. Each cinema renders its
programme with its own site builder, so there is no shared parser to write.

The Engel chase, six rounds of probing, and why it stopped: the film page renders a table
with the year, the auditorium, the per-screening price and a booking button, cleanly
classed (`_kj_showtime_*`), and none of it is in the 81 kB the server sends. The path was
`johku.com/kinoengel/allproducts.json` 403 (wrong path); `widget-module.js` publishes the
shop id and locale; `settings/public.json`, `storefrontsettings.json` and
`widgets/{id}.json` are public; `categories/2/allproducts.json?details=true` is 200 with
781 products but carries only the next show per product; per-product detail is empty, 404
or 403; the `rs-johku-wordpress` loader hands off to an authenticated widget call. The show
list is reachable only with the widget's `X-ApiKey`, which is the line "Access and ethics"
draws.

The sweep of the four known sites, read 2026-09-05:

- **Kino Tapiola** (Espoo): its own WordPress theme. Johku is the basket embed and a
  per-film schedule widget drawn client-side. The programme is server-rendered on
  `/elokuvat/`, one `div.movie-list-movie` per screening with the date and year. The slug
  is per run (`autofiktio-4`, `-5`, `-6`), so the `eventId` cannot be the slug. No age
  rating on the film page, no `og:image`, no per-show booking URL.
- **Kulttuurimylly** (Helsinki): Squarespace, programme only inside `<johku-widget>`
  filled by `johku.com/widget.js`. The storefront is a Nuxt app whose `__NUXT_DATA__`
  carries `showschedule-*` keys, empty on the day because public screenings resume in
  autumn 2026.
- **KuvaTähti** (Kuvala, Kauttuan Kuva): the storefront sits behind Cloudflare and loads
  showtimes client-side through `/api/auth/widget-session` and `X-ApiKey`, the route
  declined above. Both venues listed nothing during a maintenance break.
- **Virtasali** (Kalajoki): WordPress, a municipal culture hall with 0 of 12 events in
  `category-elokuvat`. Dropped, and **that was wrong**: re-read 2026-09-20, every ticket
  button on the page points at `kinovirta.johku.com`, a Johku storefront serving the
  standard grid. The cinema calls itself Kino Virta and the hall is Virta-sali. Built
  2026-09-20 as the seventh storefront. This entry read the page for a Johku *widget* and
  found none; the storefront was a link away and was not followed.

Two probe details worth keeping: the storefront answers with an HTTP 103 Early Hints
interim response followed by a 200, and `urllib` reports the 103 as the final status while
curl reads through it. Also, `?k=elokuvat` needs quoting in zsh. On 2026-10-05 all six
Johku hosts sent the 103 and then the 200, with no `cf-ray` header and no Cloudflare
`Server` header. Earlier versions of this note said Cloudflare sends the 103. The missing
headers leave that unsupported, but they do not show that Cloudflare was never involved.

The same 2026-09-05 pass found **Korjaamo Kino is a Vista site** with the public services
open, and **Kino Regina** runs a WordPress theme whose own `getShowtimesMoviesV2.php`
returns the day list as server-rendered HTML.

**Inferences and open questions**

- The two wrong assumptions that cost round trips: that the first 403 meant a closed API,
  and that `widget-module.js` rendered the table. Find the code that builds the URL before
  trying URLs.
- Kulttuurimylly is worth re-reading when its programme resumes: if the `showschedule-*`
  array fills, the storefront HTML is the read.
- A headless render of one Engel film page was measured on 2026-09-13: 6 s to a settled
  DOM, and the widget's own table carried date, time, hall and price per screening, the
  times matching the committed rows exactly. It would need Chrome on the local machine and
  about fifteen pages a run.

**Inferences the data settled against us**

Johku looked like a platform win and is not one. Three integrations, three HTML shapes.

**Status and next step**

Kino Tapiola got its own parser on 2026-09-05 (`scripts/providers/tapiola.py`). Kino Engel
is read from its front page and keeps `price` and `aud` empty; the headless-render option
was deferred by the maintainer the same day, with no more polling on the local half for
now. KuvaTähti and Kulttuurimylly stay unread. Next step: none open.

---

## The 2026-09-15 candidate batch: nine names, one cinema

**Findings** (each host read once as a visitor, 2026-09-15)

The nine candidates `IDEAS.md` carried. Classified by fingerprinting the host and then
verifying against the endpoint an adapter would need, never on the fingerprint alone.

- **Bio Salo, Bio Stara, Bio Jukola** run `nexxo-scope` and answer `public_api.php` with
  `{"shows": []}` at every locationid 1-5, `days=60`, `upcoming=0` and `upcoming=1` alike.
  Their sites render no `/ohjelmisto` and no clock time anywhere; the only programme-ish
  link is `/tilausnaytokset/`, which is group hire. The 2026-08-30 reading that they are
  permanently empty therefore still held sixteen days later. Each also carries a Johku
  fingerprint the 2026-08-30 note did not record, so the shop is Johku while the
  (empty) programme is Nexxo.
- **Kino Kaustinen** is a real eTiketti tenant: `etiketti.app` on the page, the
  `/elokuvat/ohjelmistossa` listing served, `/salikartta?id=` answering with eTiketti's
  own "Linkki vanhentunut" and a "Powered by eTiketti" footer. Its id space is its own,
  not Bio Rex Kokkola's: `/elokuvat/3216` is "The Odyssey" on biorex.org and a 404 here,
  and 3168 is a different film on each, so the two would not double-publish. **It has no
  screenings.** The listing renders "Ei ohjelmistoa saatavilla", the front page
  "Ohjelmistossamme ei ole näytöksiä tällä hetkellä", and `etiketti._classify_no_films`
  run against the live listing raises `EmptyProgramme`, which is the sanctioned path. Its
  `/ohjelmisto` page states a Monday update adding the next Fri-Thu week; none was
  published for the week this was read. `/elokuvat/tulossa` does list coming films, so
  the cinema is alive rather than closed.
- **Iso-Hannu**, Rauma, is on none of the platforms here and got the batch's one parser.
  See `scripts/providers/isohannu.py`.
- **Kino Kirkkonummi** is WordPress with Elementor, and this entry deferred it as
  "parseable only by reading page-builder markup that carries no contract". That was a
  maintenance judgement, not a demonstration, and it did not survive a second look:
  the screenings are server-rendered in a consistent shape and it was implemented the same
  day. See the Kirkkonummi section below. Corrected 2026-09-15.
- **Teatteri Union** is WHS's stage, not a cinema. Its own words: a programme of
  "visuaalista teatteria, eläviä kuvia ja poikkitaiteellisia esityksiä". The four events
  on `/esitys/` when read were concerts and performances, one of them titled
  *elokuvaton*. `/ohjelmisto/` renders nothing server-side.
- **"Julia" was the wrong cinema.** This entry read `turunleffat.biokuva.fi`, a local
  cinema-history archive, and closed the candidate as a defunct Turku house. The page is
  genuine and the reading of it was right; the identity was not. The operating cinema is
  **Julia 1&2 in Hyvinkää**, `juliaelokuvat.fi`, and it was added on 2026-09-15. Corrected
  the same day. The lesson is the one already in this file's inferences and it was not
  applied here: a name on a candidate list is not a cinema, and matching a name against a
  search result is not identifying it. Confirm town and operator before classifying.
- **Kino Diana** has closed. `kinodiana.fi` is 2.4 kB whose entire visible text is "Kino
  Diana www.kinopiispanristi.fi www.kinodiana.fi". Its audience moved to Kino
  Piispanristi and Kino Lumo, both already providers here.
- **Eventio** powers `kauppa.kavi.fi`, evidenced on the page itself rather than by a
  string match: a `powered-by-eventio.png` badge linking to `https://www.eventio.fi/`.
  That is a shop rather than a listing, and shops are not inventoried here; Kino Regina,
  the cinema behind it, is already read from its own WordPress.
  **The vendor has split, which is why its site looks wrong for the product.** eventio.fi
  is Eventio Group Oy and now sells bingo and fundraising; its own front page states it
  sold the ticketing software business ("lipunmyyntiohjelmiston liiketoimintansa") to
  Eventio Oy to concentrate on "bingo- ja arpaliiketoimintaan". The badge still points at
  the seller. So the vendor site carries no customer list worth reading, and reading it as
  "a fundraising company, not a ticketing platform" is the wrong conclusion: it was both,
  and the ticketing half moved.
  **Superseded 2026-09-19, read from the pages themselves.** The ticketing half did not
  move to another Eventio: eventio.fi now states "Evention lipunmyyntipalvelut on nyt osa
  Livetoa", so it is part of **Liveto**. eventio.fi is still Eventio Group Oy, bingo and
  fundraising, and `www.eventio.com` is a CNAME to `www.eventio.fi`, which is why the .com
  name fails TLS and looks dead. The product is served from the **eventio.com apex**, on
  AWS eu-west-1.
  **The endpoint is `https://ws-api.eventio.com/v1/{key}/events.json?custom.EKID={id}`**,
  200 JSON, 5.7 kB for one film: dated screenings, per-ticket-type prices and names,
  availability, and a `urls.buybox` into the tenant's shop. The key is the tenant's and
  the EKID is the cinema's own film id. It is read as a visitor's browser reads it; the
  buybox is a booking endpoint and is neither called nor inventoried.
  **The per-site path discovery this left open has an empty set, checked 2026-09-19.** One
  Eventio tenant is known anywhere in this repository and it is `kauppa.kavi.fi`, the shop
  behind **Kino Regina**, which is already a provider read from its own WordPress by
  `regina.py`. There is therefore no Eventio cinema "without a path" to find a key and an
  EKID for, and no Eventio adapter is written: a second reader of the one cinema already
  covered would be a duplicate provider on one venue, which is the thing per-site routing
  exists to prevent. The customer sweep that would find a second tenant is the one the
  section below records as not working, and the three passes it took to establish that.
  **Observed and not acted on:** `regina.py` takes its prices by parsing the `Peruslippu`
  row out of each shop page, while `events.json` returns every ticket type with its own
  name, amount and availability in one request. That is a change to a working provider and
  not this item, so it is written down rather than made.

**Inferences and open questions**

- A name on a candidate list is not a cinema. Three of these nine were a closed cinema, a
  history page and a theatre company, and no amount of adapter work would have changed
  that. Classify before estimating.
- An empty platform API is not proof of an empty cinema: Bio Säde's schedule lives on
  another host. Here the sites' own pages agreed with their APIs, which is what settled it.
- Whether Kaustinen's silence is a seasonal break or a longer pause is not established.
  Nothing here tests it, and its own pages say only what is quoted above.

**Status and next step**

Iso-Hannu is live. Kino Kaustinen is one `SITES` entry away and is held only by having no
screening to verify a ticket destination against, which is the rule six dead Nexxo links
bought. Re-read 2026-09-20: the page answers 200 and says "Ei ohjelmistoa saatavilla. Ei
näytöksiä valitsemallasi päivämäärällä." Unchanged since 2026-09-19. Next step: re-read on
a later Monday and add it when it lists a film. **Ask for that path without a trailing
slash** -- `/elokuvat/ohjelmistossa/` answers 302 to `/404`, which reads like a dead site
and is not one.

---

## TMB Cinema: four cinemas on one template (2026-09-15)

**Findings** (all four sites read as a visitor, 2026-09-15)

TMB Cinema Oy runs Kino-Toijala (Akaa), Kino-Sampo (Valkeakoski), KinoMania (Pieksämäki)
and Elokuvateatteri Elo (Heinola). Four sites, one template, footer "Mediapalvelu W3D".

- **Not an existing platform.** `/elokuvat/ohjelmistossa` answers 200 with zero film links
  on all four, so they are not eTiketti tenants despite carrying
  `cdn.etiketti.app/studio123/...` image URLs: those are syndicated opera posters, which
  is a fingerprint of a shared poster source and not of a tenancy. Counting the films, not
  the 200s, again.
- **Four cinemas, not one mirrored four times.** This had to be settled first, because the
  schedules coincide: Toijala and Sampo published an identical set of 23 screenings, and
  Mania and Elo an identical set of 32. The booking id separates them. For the same film
  at the same minute `?varaa=` is 21001 at Toijala, 21006 at Sampo, 21012 at Elo and 21015
  at Mania: four rows in the operator's system. The screen counts differ too, which a
  mirror could not do: Mania and Elo print `, sali 1` / `, sali 2`, the other two print no
  auditorium.
- **`{base}/?lista=1` is the whole published programme**, one request per venue: a
  `<small>` with weekday, full date including the year, time and the optional hall, then
  the title in `<h2><a href="?ohjelmisto=N">`, then the age limit as an image filename.
  12 dates out to 2026-11-07 when read. Every row in this view is a timed screening; the
  coming-soon entries are in the default grid view and are not read.
- **The age limit is only an image.** The film page states it in no text at all.
  `ikaraja_2`, `_3` and `_4` were checked against this repo's own committed ratings for
  five films other providers also carry and agree: K-7, K-12 twice, K-16 twice.
  `ikaraja_1` appears only on opera events, which no provider here rates, so it is left
  unmapped. The sequence looks like S, K-7, K-12, K-16, but a classification is not
  something to infer from a filename's ordinal.
- **The film page carries a per-screening price and a runtime**, and this adapter reads
  neither. That would be one request per film per venue, about 68 a run against a third
  party, for fields the card does without. A deliberate omission rather than an oversight.

**Findings** (all four sites read as a visitor, 2026-09-16, on the price page)

- **The price is also on a page of its own, one per venue**, and each list view links it
  in its own nav: `?hinnat=2` at Toijala, `3` at Sampo, `4` at Mania, `1` at Elo. All four
  state the same table that day.

      Liput   2D  Aikuinen 14.45 €  Eläkeläinen 12.45 €  Lapsi 11.45 €
                  LA, SU ja arkipyhät +0.50 €
              3D  Aikuinen 16.95 €  Eläkeläinen 15.95 €  Lapsi 13.95 €
              Lastenliput on alle 13-vuotiaille.  Ma-To opiskelijat -2 €

- **The surcharge is visible in the schedule.** The film page prints the price beside each
  screening, and a Sunday row reads 14.95 / 12.95 / 11.95 where the Wednesday above it
  reads 14.45 / 12.45 / 11.45.
- **The list view carries no price and no 3D marker.** Zero `€` on the page; the three
  `3D` strings are the `<title>` and the "Mediapalvelu W3D" footer, none of them on a row.
  No screening on any of the four was 3D that day.

**Inferences and open questions**

- Reading the price page costs **one request per venue**, not one per film, which is the
  objection the 2026-09-15 omission rested on. That objection still stands for the runtime,
  which is only on the film page.
- Two things the price cannot be read exactly for. *Arkipyhä*: the same +0.50 applies on a
  weekday public holiday, which needs a calendar this repo does not carry, so such a
  screening publishes 0.50 low. *3D*: nothing on the row distinguishes it, so a 3D
  screening would publish at the 2D price and nothing would notice. Both are stated in
  `tmb.py` rather than worked around.

**Inferences and open questions**

- Whether the four ever diverge in programme is not established; on the day read they ran
  in two identical pairs. Nothing here depends on it, since each venue is read from its
  own host.
- `Leffa & Kaffe` is a labelled screening group on the film page and does not appear in
  the list view, so no strand label is published. Reading it would need the film pages.

**Status and next step**

Live as `scripts/providers/tmb.py`, four providers, four venues, cloud half, published in
`d216607b` on 2026-09-15. Re-checked 2026-09-19: `logs/run-tmb.log` reads `exit=0`, and
Toijala and Sampo carry 16 showtimes each against Mania's and Elo's 22, every one of them
with a runtime and a price.

The price and the runtime both come from the **film page**, on the maintainer's
instruction of 2026-09-16, and the tariff page this section measured is read by nothing:
the operator prints `Hinta:` under each screening with its own tariff already applied, so
the 2D/3D question and the *arkipyhä* question that sank the tariff reading are not
questions there. Next step: none. If a list-view row ever carries a 3D marker, that is the
signal to split the two tables.

---

## Julia 1&2, Hyvinkää (2026-09-15)

**Findings** (juliaelokuvat.fi, read as a visitor 2026-09-15)

An operating two-hall cinema at Hämeenkatu 34, on its own WordPress. Not the Turku "Julia"
an earlier entry in this file closed; see the correction in the batch section above.

- `/ohjelmisto/` is the whole published programme in one request: one `div.elokuva` per
  film with the film-page link, the poster, a `<div id='bNNNN'>` of `<br>`-separated
  screenings and `<strong>`-labelled `Hinta`, `Ikäraja`, `Kesto` and `Genre`.
- **The films are listed twice.** An index above the programme repeats every title with a
  "Katso näytösajat tästä" link and no screening, so a parser anchored on the title alone
  would publish dateless rows. Anchoring on the film block and requiring a screening row
  handles it.
- **The year is two digits**, `15.09.26`. Published, not missing, so it is read as 2000+YY
  and nothing is taken from the clock. Two films ran 4 screenings over 2 dates when read.
- `Salit` states two halls, 110 and 57 seats; screenings carry `1. sali` / `2. sali`.
- **No online booking anywhere.** Tickets at the door, reservations by phone, and `/liput/`
  sells only gift tickets. So the showtime links to the film's own page and the registry
  entry is `book="door"`; no ticket host exists and none is invented.

**Inferences and open questions**

- The programme was two films deep on the day read. Whether it is always that short is not
  established and nothing here depends on it.

**Status and next step**

Live as `scripts/providers/julia.py`, one provider, one venue, cloud half. Published in
`d216607b` on 2026-09-15; `logs/run-julia.log` reads `exit=0` and the venue carried 12
showtimes when this was re-checked on 2026-09-19. No next step.

---

## Bio-Kaari, Forssa (2026-09-15)

**Findings** (bio-kaari.fi, read as a visitor 2026-09-15)

WordPress with a site-specific plugin, `wp-content/plugins/biokaari/`, that renders the
whole programme server-side.

- **MyCloudCinema, and that did not make it a `SITES` entry.** Posters come from
  `mcswebsites.blob.core.windows.net` and tickets from
  `bio-kaari.azurewebsites.net/websales/`, the platform BioRex and Gilda also run on.
  All three render it differently: BioRex is `admin-ajax` returning HTML inside JSON,
  Gilda is MyCloudCinema's own document, this is a bespoke WordPress plugin. Same
  conclusion this file already reached about Johku, on a different platform.
- **The date is the day container's id.** `<div class="searchResults" id="15092026">`, ten
  of them, all in the markup with the later ones `display:none`. The film rows repeat
  verbatim across days, so the container is the only thing that separates them: 15
  screenings over 10 days when read, each with its own `websales/show/{id}`, which is what
  confirms no day's times are being published on another.
- A film can hold several `<li>` rows on one day. The screening-row tags are upper case
  (`<P>`, `<DIV>`, `<A>`) where the rest of the markup is lower case.
- The title carries a release year, `(2026)`, taken as the optional `year` field rather
  than left in `title`, which is the TMDB and merge key.
- The ticket link is published as `http://` on a host that answers `https://` and
  redirects there. It is upgraded, and it is read from the page rather than constructed.
  The sales page was not fetched until 2026-10-09; since then the price pass reads it for
  the price and the language, as Riviera's does.
- The film page adds `Lajityyppi`, `Ikäraja: K7/4` (the 4 is the flexibility years, not
  part of the classification) and `Kesto: 1 h 27 min`. Three films when read, so the
  per-film pass is a few requests a run.

**Inferences and open questions**

- The weekly articles under `/elokuvat-naytosajat-ja-hinnat-DD-DD-M/` restate the same
  programme in prose with prices. The front page's day containers are the structured
  source and are what this adapter reads; whether the articles ever carry a screening the
  containers do not is not established, and nothing here depends on it.
- No price is published in the day containers. Since 2026-10-09 it comes from the ticket
  page instead.

**Status and next step**

Live as `scripts/providers/biokaari.py`, one provider, one venue, cloud half. Published in
`d216607b` on 2026-09-15; `logs/run-biokaari.log` reads `exit=0` and the venue carried 8
showtimes when this was re-checked on 2026-09-19. No next step.

---

## The year nobody publishes, and Kino Vaakuna (2026-09-15)

**Findings**

Three of the secondary candidates publish a programme with **no year anywhere**: Kino
Vaakuna (`Ti 15.09.   klo 18:40`), Kino Kirkkonummi (`20.9. Sunnuntai klo18.00`) and
Kuvakukko/Kino Manttu (`Tiistai 15.9.` headings with `Klo 13:` rows). It is one problem,
not three, and it is solved once in `common.resolve_year`.

**Narrowed 2026-09-15.** A published weekday **selects uniquely within the assumed
three-year window** and nothing more: it does not independently establish the intended
date. A page left up for years, or one with a mistyped weekday, still resolves to one of
the three, and neither the helper nor the caller can see that from the page. So the answer
is bounded as well as selected: a candidate more than 300 days ahead or 180 days behind is
refused. The asymmetry is the point. A stale row in the past is hidden by the client; a
phantom row a year ahead is shown to readers, and that is exactly what a wrong weekday
produces. The widest real programme seen on 2026-09-15 reached 88 days ahead.

**The fallback: nearest occurrence, ties to the future.** Candidates are the same day and
month in last year, this year and next; the one closest to today wins. The obvious rule,
"next occurrence", is wrong in a way that matters: on 2 January a page still showing
`28.12.` means five days ago, and a forward-only rule publishes it eleven months out,
where nothing filters it. Nearest gets both directions right without a special case, and
bounds every answer to about six months either side of today. A day and month that name no
real date in the window, 29.02. outside a leap year, resolve to nothing and the row is
skipped rather than moved to a date the page did not publish.

Ties are reachable, which was not obvious: 195 of them in a twelve-year sweep, all at 183
days across a leap year, so the tie-break is live code and not decoration. The first test
written for it used 181 days against 184, which is not a tie, and the mutation that flips
the tie-break scored **VOID** against it.

**Kino Vaakuna, Lohja** (kinovaakuna.fi, read 2026-09-15) is the first adapter using it.
One `div.MovieCard` per film on the front page with the film-page link, poster, `Liput:`,
`Kesto:` and a screening table. 19 screenings over 8 dates and 8 films when read.

- **The age limit is an image whose filename is the number**, `icon/16.png`, so it is read
  rather than inferred. One film carried `icon/.png`, an empty name, and publishes no
  rating: the site rates it nowhere and neither does this.
- **No online purchase.** "Varaa liput" opens the film's own page; reservations are by
  phone and email. `book="reserve"`, and no auditorium is invented because the page names
  none.

**Inferences and open questions**

- Whether Vaakuna ever publishes a year is not established; it did not on the day read.
- The same rule is what Kirkkonummi and Kuvakukko will need, and neither is implemented.

**Status and next step**

`scripts/providers/vaakuna.py` is live, one provider, one venue, cloud half, published in
`d216607b` on 2026-09-15; `logs/run-vaakuna.log` reads `exit=0` and the venue carried 24
showtimes when this was re-checked on 2026-09-19. `common.resolve_year` is shared and
tested on its own, and Kuvakukko and Kino Kirkkonummi both reuse it. No next step.

---

## Kuvakukko and Kino Manttu (2026-09-15)

**Findings** (kuvakukko.fi, read as a visitor 2026-09-15)

The city of Kuopio's two cinemas, Kino Kuvakukko in Kuopio and Nilsiän Kino Manttu, whose
schedules share one WordPress page. One provider, two venues, one request.

- **Two `<h2>` headings are the venue boundary**, "Kino Kuvakukon esitysaikataulu" and
  "Nilsiän Kino Mantun esitysaikataulu". Reading the page without them files Nilsiä's
  weekend under Kuopio, and nothing downstream would notice.
- **A paragraph is a day only if it opens with a weekday and a date.** The same element
  type carries addresses, prices and notices, so the pattern is anchored to the start.
  That anchoring turns out to be enforced twice, by the `^` in the pattern and by
  `re.match`, so no single edit defeats it: the mutation that tried scored VOID until it
  changed both.
- **No year, but a weekday**, `Tiistai 15.9.`, which determines the year. See the year
  section above.
- **Manttu publishes every other weekend**, so its section is routinely already past: on
  the day read it showed 11.–13.9. against Kuvakukko's 15.–24.9. That is correct output.
  A rule that pushed past dates forward would have moved Manttu's whole weekend a year.
- The time is written `Klo 13:` and `Klo 17.30:`, hours alone or hours and minutes.
- Some rows link to a third party (isak.fi for the Hopeatähti series, hyvätkuvat.fi for a
  club). A showtime opens this cinema's own page instead, the programme page when the row
  has no page of its own here.
- Titles carry strand prefixes, "Hopeatähti-sarja: Laula minulle Arja". They are published
  verbatim; `run.py` splits the prefixes `strands.EVENT_PREFIXES` names and that list is
  exact on purpose. **"Hopeatähti-sarja" is not in it**, so that title reaches TMDB whole
  and will not match. Adding it is a one-line change to a shared list and is its own
  decision, not made here.
- `book="door"` for both: "Lipunmyynti vain Kuvakukossa", and for Manttu "Ei
  ennakkovarauksia ... Maksuvälineenä käy vain käteinen."

**Inferences and open questions**

- 36 screenings at Kuvakukko and 9 at Manttu when read. Whether Manttu's cadence is exactly
  fortnightly is stated by the page, not measured here.
- No price is published per screening, only per venue in prose, so `price` stays empty.

**Status and next step**

Live as `scripts/providers/kuvakukko.py`, one provider, two venues, cloud half. Published
in `d216607b` on 2026-09-15; `logs/run-kuvakukko.log` reads `exit=0` and the two venues
carried 33 showtimes between them when this was re-checked on 2026-09-19.

**"Hopeatähti-sarja" stays out of `strands.EVENT_PREFIXES`, decided 2026-09-20.** Nothing
published carries it. Zero of the 4,478 committed showtimes do, and zero titles on the
programme page re-read that day: *Laula minulle Arja* is now published bare and links to
the cinema's own page rather than to isak.fi, and the strand has a section of its own at
`/ohjelmisto/hopeatahti/`. That list is exact because every entry was checked against a
published title, and an entry with nothing behind it is a guess at the next spelling the
cinema will use. If the prefix comes back it arrives in a no-match list with a title
attached, which is when it gets added and how the other entries got there. No next step.

---

## Kino Kirkkonummi (2026-09-15)

**Findings** (kinokirkkonummi.fi, read as a visitor 2026-09-15)

WordPress built in Elementor. The whole cinema is one page and there is no semantic class
for a screening: a film title sits in `<p class="elementor-heading-title">` and its
screenings in following `<span class="elementor-icon-list-text">` items, so the parser
walks headings and items in document order and keeps the last heading as the current film.

- **Everything is published twice**, once for desktop and once for mobile: 21 headings and
  46 list items for 6 films. 11 real screenings on the day read. A parser that trusted the
  count would double the whole programme.
- **A list item is a screening only if it reads `D.M. Weekday kloHH.MM`.** The same element
  carries cast lists, directors, "vain tämä näytös", the street address and the phone
  number, and none of them match.
- **"Tulossa 25.9. alkaen" is a release date, not a screening**, and it is excluded three
  times over: the row must start with the date, carry a weekday, and carry a time. Relaxing
  any one of those still excludes it; only relaxing all three admits it. `tulossa` also
  appears as a heading above films that *do* have screenings, so it is not usable as a
  marker either way.
- **No year, but every row carries a weekday**, which determines it.
- The time is written `klo18.00`: no space, minutes after a dot.
- **No per-film page and no booking host.** The site is one page and tickets are reserved
  by phone, so a showtime opens that page and the registry entry is `book="list"`, the mode
  that exists for exactly this. The page names two seat counts, 112 and 68, but never says
  which screening uses which, so no auditorium is published.

**Inferences and open questions**

- No price, runtime or age limit is published per film, so those stay empty and the TMDB
  pass fills what it can.
- Three to five screenings a week is a small programme; nothing here depends on its size.

**Status and next step**

Live as `scripts/providers/kirkkonummi.py`, one provider, one venue, cloud half. Published
in `d216607b` on 2026-09-15; `logs/run-kirkkonummi.log` reads `exit=0` and the venue
carried 10 showtimes over 5 dates when this was re-checked on 2026-09-19. No next step.

---

## Three research candidates, assessed not implemented (2026-09-15)

Read as a visitor. None is implemented; what separates them is whether anything was
demonstrated or merely not tried.

### Sun Kino group, elokuviin.info: blocked, re-established on direct evidence

Four venues on one site, Kino Kyntäjä (Alavus), Y-Kino (Kauhava), Sun Kino (Ähtäri) and
Alareksi (Alajärvi), which would be an attractive single integration.

- `urllib` reports HTTP 103 for this host. That is the same 103 Early Hints interim
  response, followed by a 200, that this file records under Johku. It is a limitation of
  the reader and does not block anything: `curl` reads through it and gets 200 with 163 kB.
- **Corrected 2026-09-15.** The first reading of this rested on the *absence* of
  `showschedule` keys on the home page, which establishes nothing: a key can be named
  anything. Re-done properly by reading the site's own public code and its own endpoints.
- Per-venue schedule pages exist, `/fi_FI/naytosajat/sun-kino-ahtari` and one each for the
  other three. All render the venue name and **zero times, zero dates** server-side, so the
  schedule is client-side. That still says nothing about *what* the client fetches.
- The evidence is in the site's own Nuxt bundle, `/_nuxt/DNEBalWQ.js`, 821 kB: it contains
  `/api/auth/widget-session`, `X-ApiKey` and `/allproducts.json?details=true&version=`.
  Those are the three things `docs/research` already records for KuvaTähti.
- And the public endpoint answers for itself: `johku.com/elokuviin/allproducts.json?
  details=true` returns **403** with `"Et ole kirjautunut sisään tai kirjautumisesi on
  vanhentunut."` No session was sought and none should be.
- So **that endpoint is closed**: demonstrated by the vendor's own response rather than by
  an absent key, and it is the route "Access and ethics" draws a line at. No session was
  sought and none should be.

**Two separate things, and only the first is settled.** What is demonstrated is that
`allproducts.json` requires a session. What is *not* established is whether any other public
programme source exists for these four cinemas at all: the four venue pages were read and
render nothing, but no sweep was made of the cinemas' own municipal or tourism listings, and
the Engel investigation separately found that `allproducts.json` carries only the next show
per product even when it does answer, which would not be a programme anyway. "This endpoint
is closed" is not "there is no public source".

### Cine Mäntsälä, mantsala.cine.fi: implementable, through its own page's request

**Established 2026-09-15 by reading the page's own code**, not by guessing a Gilda
endpoint on another host. The 3.6 kB shell carries one inline script:

    var jsonURL='/webservices/structured_data/get?cinema_id=1&url=https://mantsala.cine.fi';
    $.getJSON(jsonURL, function(data){ ...append as application/ld+json... });

That is the page's own public request, fetched to inject JSON-LD. It answers 200 with a
list of screenings: `location.name`, `name`, `startDate`, `endDate`, poster and still
`image` URLs, and an `offers.url` of `https://mantsala.cine.fi/#/book/{id}`.

**Coverage settled 2026-09-15, and the JSON-LD is the wrong source.** Two earlier reads
the same day left "today only" and "currently showing" indistinguishable, because both fell
on one day. Comparing the feed with the requests the page itself makes settles it without
waiting for another day. All read 2026-09-15 at 11:41 UTC:

| request | screenings |
|---|---|
| `structured_data/get` | 4, all 2026-09-15, booking ids 13391-13394 |
| `show_times/getShowTimes?date=2026-09-15` | the same 4, same `show_time_id` values |
| `show_times/getShowTimesDays?date=2026-09-15&number_of_days=7` | 37 over 6 dates |
| `show_times/getShowDates` | 17 dates, 2026-09-15 to 2026-12-22 |

The feed is the same day-scoped query rendered as JSON-LD. It carries 4 of the 37
screenings a visitor reaches this week, and one of the 17 dates the cinema publishes.

**The visitor's own loading requests, read from the page's network activity.** Three, all
under `/webservices/show_times/` on the site's own host, all answering 200 to a plain
client with no key and no session: `getShowDates?cinema_id=1` for the date list,
`getShowTimesDays?cinema_id=1&date=&number_of_days=` for a window, and
`getShowTimes?cinema_id=1&date=` for one date. The page also calls `getPlayingNow`,
`getComingSoon` and `getPremieres`, which are film-level. `number_of_days` behaves as a
cap of 7: 7, 14 and 120 from 2026-09-15 each returned the same 37 rows over 09-15 to
09-20, while a 7-day window from 2026-12-01 returned 12-01 and 12-05. A full programme
therefore means walking `getShowDates` or paging the window in sevens. The `ts=` the page
appends is a cache-buster and is not required. The bundle also names
`webservices/authorisationrequests/managerLogin`; that is an administrative route and was
not touched.

**Timezone: source evidence, and the JSON-LD is three hours early.** `show_time` is
`2026-09-15T13:45:00.000Z` and the site's own booking anchor for that id renders `16.45`,
so the Z is a real UTC instant which the app converts for the reader. The JSON-LD
`startDate` for the same screening is `2026-09-15T13:45`: the same instant with the Z
dropped, so reading it as a local time publishes every showtime three hours early.
Independent of any browser, `getShowDates` gives each show date as the preceding
`21:00:00.000Z` through 2026-10-19 and `22:00:00.000Z` from 2026-11-02, tracking Finland's
2026-10-25 DST change exactly, so the platform stores Europe/Helsinki and serves UTC. That
mapping was checked three ways: the window's first business date, `getShowTimes` on
2026-10-06 (one screening), and the window from 2026-12-01. One trap in the same payload:
`business_date` is the local date stamped `T00:00:00.000Z`, which is not a UTC instant and
disagrees with `getShowDates` by one day.

**Ticket destination, read and not constructed.** The rendered page emits `#/book/{id}`
anchors and `#/movie/{movie_id}` film links, and for all four of that day's screenings the
`{id}` in the emitted href equals the API's `show_time_id`; absolute form
`https://mantsala.cine.fi/#/book/13394`. Each row carries `bookable`, `allow_purchases`,
`allow_reservations` and `sold_out`, plus `rating_name`, `running_time`, `audio_lang`,
`subtitle_lang`, `screen_name` and `premiere`.

**Coverage: settled, and not an open question.** `getShowDates` is the date list the app
offers an ordinary visitor, which is the coverage standard this repo reads to, so whether
some larger undisclosed programme exists behind it is not a gap to chase. Nothing found
declares a horizon and nothing needs to. The host serves no `robots.txt`: that path answers
200 with the SPA's own not-found screen, the soft-404 shape that would have reported ten
false hits in the Vista sweep.

- Cine is already a provider here and Mäntsälä is a venue it does not carry.

### Bio Savoy, Mariehamn: ready, and the cleanest source in the batch

Åland, which this repo covers nowhere. Drupal, server-rendered, and it publishes what
every other candidate this week made us infer:

    <span class="date-display-single" property="dc:date" datatype="xsd:dateTime"
          content="2026-09-15T18:00:00+03:00">18:00</span> - THE DOG STARS

A **full ISO datetime with its offset**, in the markup. No year resolution, no weekday
verification, nothing inferred. Films link to `/film/{slug}`. The site states its own
cadence: "Bioprogrammet framställs veckovis, Fredag - Torsdag, och uppdateras på tisdagar."
Bookings are by phone, so `book` would be `door` or `list`.

**One real wrinkle:** the site is **http only**. Port 443 is refused on both `biosavoy.ax`
and `www.biosavoy.ax`, and `http://biosavoy.ax/` redirects to `http://www.biosavoy.ax/`.
Reading it is fine; every URL published for it would be http, which `safeUrl` accepts but
which is worse for a reader than everything else here. Worth a decision before adding.

**Status and next step**

Sun Kino is blocked on the Johku key. Bio Savoy was the highest-value of the three, for a
new autonomous region, a source that needs no date inference and Swedish-language content
for an interface that already has a Swedish mode; it was added on 2026-09-15 in `aec9ff4d`.
Cine Mäntsälä's source question is answered as of 2026-09-15: read `show_times/`, never the
JSON-LD. The adapter was written the same day, `scripts/providers/cinemantsala.py`, and the
decisions it rests on are in
[docs/archive/2026-09-providers.md](../archive/2026-09-providers.md). It is committed and
unpublished until a cloud run fetches it. **Next action:** none. Reading the visitor's own
date list meets the coverage standard, so this investigation is closed rather than
waiting on anything.

---

## Johku storefront (2026-09-18)

**Findings** (four storefronts read as a visitor, 2026-09-18)

The Johku section above concluded the show list needs the widget's `X-ApiKey`. That holds
for a WordPress site with the widget embedded (Kino Engel, Kino Tapiola). A cinema whose
whole site is a Johku storefront server-renders the programme on its front page:

    biomarilyn.com   15 timed rows, 18.9. to 14.12.   location "Bio Marilyn"    Lapua
    vihdinkino.fi    12 timed rows, 19.9. to 24.9.    location "Vihdin Kino"    Vihti
    bioforum.fi      15 timed rows, 18.9. to 24.9.    location "Bio Forum"      Tammisaari
    kinokulma.fi     29 timed rows, 18.9. to 21.11.   location "Kulmasali"      Oulainen

Row shape, inside a day group:

    <div class="showgroup"><h3 class="daytitle">Lauantai 19.9.2026</h3>
      <a href="/fi_FI/{category}/{slug}" class="js-grid-item js-grid-show" data-product="1038">
        <span class="showrating rating-icon rating-12">K-12</span>
        <h3 class="grid-content-title" data-name="...">...</h3>
        <span class="showlocation" data-location="Bio Marilyn">Bio Marilyn</span>
        <span class="showtime" data-showtime="2026-09-19T14:30:00.000Z">klo 17.30</span>
        <span class="showduration">1 h 27 min</span>

- `data-showtime` is a UTC instant. All 71 rows converted through `Europe/Helsinki` to the
  clock printed beside them.
- The day group carries the year.
- Rating classes seen: `rating-7`, `-12`, `-16`, `-18`, `-s`, `-unknown`.
- The category path is per tenant: `/fi_FI/nyt-ohjelmistossa/`, `/fi_FI/naytokset/`,
  `/fi_FI/ohjelmisto/`, and at Kinokulma the bare `/fi_FI/{slug}`.
- A grid item inside a day group with no `data-showtime` is a coming-soon entry. Bio
  Marilyn had 14 of them; the other three sites had none.
- Film page answers 200 and carries `Kesto NN min`, `Luokittelu`, `Alkuperainen nimi`,
  `Ohjaaja`, cast and a synopsis under `Kuvaus`.
- No price anywhere. Vihdin Kino's `Liput` page states bands: normal 13 to 15, family 10
  to 13, weekday matinee 11 to 13, specials priced separately. Bio Forum's info page lists
  none.
- Artwork is landscape. `og:image` measured 2048x1365 (Vihti), 2048x1152 (Lapua),
  2048x857 (Oulainen); grid thumbnails are 3:2 crops.
- Tammisaari publishes Swedish titles.

**Inferences and open questions**

- The 2026-09-05 reading was of a WordPress site with the widget embedded. Read a Johku
  cinema's own front page before classifying it.
- `kuvatahti.fi` matches the old finding: same storefront, `/fi_FI/naytosajat` names both
  venues, neither page carries a `data-showtime`. Cause not established.

**Status and next step**

Live as `scripts/providers/johku.py`, four providers, four venues, cloud half, published
2026-09-18 and verified on the runner in the dispatch that committed `ca17dc58`. No next
step. `kuvatahti.fi` runs the same storefront and renders no `data-showtime`; why is not
established.

---

## Johku storefront: the listing renders whole only some of the time (2026-10-03)

**Findings** (front pages read as a visitor, 2026-10-03, with the adapter's user agent)

- From the 2026-10-01 05:22Z cloud run on, 1 to 3 of the six storefronts failed per run
  with no screening in any day group, and all but Bio Forum from 2026-10-02 11:18Z. The
  same happens from an ordinary connection, so it is not the runner's address.
- The front page holds one `js-shows` block per programme category, and each comes back
  either rendered or as a placeholder: `<div class="product-list-skeleton" role="status"
  aria-busy="true">` with `sk-product-card` items. Response headers are identical apart
  from the length; nothing but the body tells the shapes apart.
- Bio Marilyn came in three shapes over 8 reads in a row: a skeleton (3), "nyt-ohjelmistossa"
  rendered beside a skeleton "tulossa" (4, 9 screenings to 7.10.), and both rendered (1, 14
  screenings to 14.12.). The committed file held the 9.
- Whole listings, counted on the placeholder over all blocks: Bio Forum 8 of 9 reads,
  Vihdin Kino and Kino Virta about half, Bio Marilyn 1 of 19, Kinokulma and Kino
  Hannikainen 0 of 17.
- The page's script fills the placeholder from `johku.com` with an `X-ApiKey` header added
  to every request for the store's API, the flow declined above. Film pages carry no
  screening time at all, and the category pages (`/fi_FI/ohjelmisto`, `/fi_FI/tulossa`)
  either show the same placeholder or render nothing.

**Inferences, not verified**

- The server renders each category's shows within some time budget and sends the
  placeholder when the backend answers late; the larger programmes miss it more often.

**Status and next step**

`johku.py` reads a listing only when every block is rendered, re-reads up to five times,
5 s apart, and otherwise fails the site with its previous files standing. Kinokulma and
Kino Hannikainen stay stale until the storefront renders whole again (IDEAS, Blocked).
Superseded on 2026-10-09 by the next section.

---

## Johku storefront: the programme is in the page's own payload (2026-10-09)

**Findings** (read 2026-10-09 as a visitor: the six front pages with the adapter's user
agent, kinokulma.fi in the built-in browser, and the storefront's JavaScript bundle)

- The storefront is a Nuxt application. Each front page carries a `__NUXT_DATA__` script
  in devalue's flat JSON. It holds the layout, `storefront-{shop}-fi_FI`, and one
  `showschedule-fi_FI-f{today}-c{category}` entry for each layout item whose `view` is
  `showtimes`, shaped `{"data": [...]}` with one object per screening or coming-soon film.
- Loaded in the browser, kinokulma.fi made no request for schedule data after the HTML.
  Its same-origin calls were `time.json`, three `get-session`, the web manifest and the
  build manifest. The page drew 42 rows, the 42 entries in the payload, from HTML whose
  listing was a skeleton.
- The bundle (`/_nuxt/BfTgRy77.js` that day) builds that key and fetches
  `{apiUrl}{shop}/{locale}/showschedule.json?details=true&storefront=true&version={locale}
  &from={today}&category={id}` through Nuxt's `useAsyncData`. While hydrating,
  `useAsyncData` takes the payload's value when it holds data or an error and requests
  nothing.
- The MovieList component draws an entry only when `product.enable_catalog` or
  `product.enable_collection` is 1 or names the locale, and only when it has not started.
  ShowItem prints no time when `upcoming` is 1. `js-shows` is MovieList's root class and
  no other component uses it. MovieList is drawn only for a `showtimes` layout item.
- The server's `apiUrl` is internal (`http://backend-nginx/`) and the browser's is `/api/`
  on the storefront's own host. The fetch plugin adds `X-ApiKey` only when the store holds
  an `apiKey`, which the sign-in code sets to `betterauth:{session token}`. An anonymous
  page carries none. This is read in the code; the endpoint was not requested.
- Five reads per tenant, 5 s apart: the markup was a skeleton on 25 of 30 (every read but
  Bio Forum's), and the payload held every block's schedule with no error on all 30, with
  the same counts each time: Bio Marilyn 22 and 25 over two blocks, Vihdin Kino 27, Bio
  Forum 32, Kinokulma 42, Kino Hannikainen 24, Kino Virta 14.
- An entry's `storefronturl` is the product path, `/fi_FI/{canonical}`, or
  `/fi_FI/products/{id}-{shop}-{name}` for a product with no canonical name (Kinokulma's
  Salivaraus). The page's own link puts the block's category in front,
  `/fi_FI/ohjelmisto/digger`. Both answer 200 with the same film page. Bio Marilyn's
  `storefronturl` host is biomarilyn.johku.com, and the path answers on www.biomarilyn.com.
- Read again 2026-10-10: Bio Marilyn's 45 entries all name biomarilyn.johku.com, and the
  other five tenants' entries name their own site's host. Bio Marilyn's film pages on
  both hosts parse to the same film facts.
- An entry also carries `price` and `pricing_name` ("Elokuva 13 €") with `multipleprices`,
  plus director, original title and MACCS language fields. None of these is read.
- Bio Marilyn lists four Kerro Kaikille screenings in both of its blocks, and the
  committed file held each of them twice.
- kuvatahti.fi's front page carries the payload with no `showtimes` item, so no schedule.

**Inferences, not verified**

- The server sends a block's markup before its schedule request returns and serialises
  the payload after it, which is how a skeleton and a whole schedule arrive together.

**Status and next step**

`johku.py` reads the payload from 2026-10-09 and publishes `storefronturl` unchanged from
2026-10-10; the decisions are in
[docs/archive/2026-09-providers.md](../archive/2026-09-providers.md). A live parse that
day matched each cinema's rendered page. No next step for the six. Kuva-Tähti's
`/fi_FI/naytosajat` was not read for a `showtimes` block.

---

## Helsinki culture centres: one events service (2026-09-18)

**Findings** (malmitalo.fi and caisa.fi, read as a visitor 2026-09-18)

Kino Helios (Malmitalo) and Kino Caisa (Caisa) run the same application,
`prime_product_resurssivaraus/kulke`. The programme comes from one service, spelled out in
`EventCalendar/app/services/events.service.js`:

    POST https://{house}/services/Resurssivaraus/EventCalendarService.svc/GetEvents
         {"StartTime": "2026-09-18", "EndTime": "2026-10-20", "Language": "fi"}
    ->   {"EventData": "<JSON string of every house's events>"}

- No auth, no cookie, no key. 326 events for a month, 725 for three and a half.
- `eventLocation` is the house (41 Kanneltalo, 42 Malmitalo, 44 Stoa, 45 Vuotalo,
  46 Annantalo, 47 Caisa, 49 Savoy). `mainEventType` 29 is film. Either host answers for
  all houses.
- Per event: `title` with the age rating in brackets, `subtitle` with the cinema brand,
  `description` as a short Finnish synopsis, `start`/`end` as epoch ms, `timeSpanToShow`,
  `specificLocation`, `ticketLink` to lippu.fi.
- Kino Helios: 25 events in the month read, 8 films, 25 with a ticket link, all in
  `Malmitalon Pieni sali`.
- Kino Caisa: one type 29 row with that subtitle to the end of the year, the Cinemaissi
  festival 14. to 18.10., a date range with no screening time.
- Type 29 also holds school screenings (`Pulpettikino`), the Rakkautta & Anarkiaa festival
  and free Monday screenings. `subtitle` is the only labelled signal for Kino Helios.
- `priceinfo` is null on every Malmitalo film event. The Kino Helios page states "alkaen
  9 EUR" and "alkaen 7 EUR" for children's films.
- `Embeds/EventPic_{masterID}.jpg` measured 1080x648 on three tested.

**Inferences and open questions**

- The service is a POST, so the datacenter probe used elsewhere here cannot exercise it.
  Only a runner settles it.
- The whole feed was assessed on 2026-09-18, over 2026-09-18 to 12-31: 725 events, 94 of
  type 29, across seven houses.

      42 Malmitalo    37 rows, 37 timed, 26 ticket links   Kino Helios 26, Doc Helios 1
      49 Savoy        20 rows, 20 timed, 20 ticket links   all Rakkautta & Anarkiaa
      45 Vuotalo      18 rows, 18 timed,  7 ticket links   festival tie-ins, one Muumi day
      44 Stoa          8 rows,  8 timed,  0 ticket links   festival, Barnens Estrad
      46 Annantalo     7 rows,  7 timed,  0 ticket links   the autumn-break children's week
      41 Kanneltalo    3 rows,  3 timed,  0 ticket links   Kino Kuutamo, free Mondays
      47 Caisa         1 row,   0 timed,  0 ticket links   Cinemaissi, a date range

  One accent buys one venue. Malmitalo is the only house with a standing cinema brand and
  regular ticketed screenings; the rest is festival programming, a children's week and a
  three-row free-Monday series.

**Status and next step**

Not built. Declined 2026-09-18 on the accent rather than on the reading: no colour in the
L* band clears the combined-city floor against Helsinki's eight chains, 0 of 226,580 swept,
best reachable 12.2. That would be the first exception the city rule has ever taken, and it
is recorded in `IDEAS.md` as a policy question about a full city rather than as this
cinema's.

---

## The 2026-09-18 candidate batch: thirty-two names

**Findings** (each host read once or twice as a visitor, 2026-09-18)

Source list: the Finnish Wikipedia article "Luettelo Suomen elokuvateattereista", edited
2025-07-18, plus five towns with no entry on it. Identity confirmed against
`nytleffaan.fi/elokuvateatterit/`, which carries 225 cinemas with address and site.

**Closed on identity, no endpoint called.**

- **Bio Marilyn Hameenlinna** and **Bio Marilyn Seinajoki**: sold to Bio Rex Cinemas 2016;
  Hameenlinna closed early 2017 and moved to BioRex Verkatehdas, Seinajoki ran as Bio Rex
  Marilyn to December 2021 and was replaced by BioRex Seinajoki. Both already covered here
  under their BioRex names. Lapua is the operating Bio Marilyn.
- **Davvenasti**, Utsjoki: `davvenasti.fi` and `www.davvenasti.fi` have no A record.
- **Kino Sampo, Riihimaki**: a film society. News posts, seasonal series of five films,
  schedule in prose ("Naytokset ovat paasaantoisesti sunnuntaisin klo 18.00. Liput 6 EUR
  jasenet ja 8 EUR ei-jasenet"). No listing.
- **Kampus Kino**, Jyvaskyla: directory entry points at Facebook; `ilokivi.fi` carries no
  film listing.
- **Kinoset Somero** is Bio Jukola, and the directory gives Kinoset's own contact address.
  `kinoset.fi`'s `public_api.php` answers 0 shows at locationid 4, 5 and 6; 1, 2 and 3 are
  the published Huittinen, Loimaa and Sastamala venues.
- **Paimion Kino** is historical. Paimio's cinema is Bio Stara, re-read after paimio.fi
  announced an autumn 2026 series there: no clock time on the site, Nexxo endpoint empty.

**On a platform already read.**

- **Kino Myyri**, Vantaa (`kinomyyri.fi`, linked from `myyrikino.fi`): Kinola. Its
  `/ohjelmisto/` renders `kinola-event` blocks with `media.kinola.ee` posters,
  `kinola-event-title` to `/film/{slug}/`, `-venue`, `-date`, `-tickets-link`. Film pages
  carry `Ohjaus`, `Ikaraja`, `Kesto`. Two differences from Laika: the date reads
  "pe 18.9. klo 19:30" with no year, and the ticket link is `/checkout/{uuid}`. No price on
  the listing or the film page. One film page carried an English synopsis.

**Own parser, server-rendered to a plain fetch.**

    Kino Hamina        hamina.fi          WordPress    14 rows, K rating, 8/10/11 EUR
    Ritz Vaasa         ritz.fi            Elementor    12 rows, 10 to 12 EUR band
    Bio Pallas         biopallas.com      Wix          19 rows, bilingual, 12 or 13 EUR
    Bio Huvimylly      huvimylly.com      WordPress    4 rows, portrait posters
    Kinotour           kinotour.fi        Events Mgr   19 rows: date, time, film, venue
    Marita             elokuvateatterimarita.fi        3 rows, 10 EUR, portrait posters
    Lieksan Kino       lieksanelokuvat.net             7 rows, 12 to 13 EUR
    Navettakino        navettakino.fi                  2 rows, 10 EUR
    Pyhasalmen VPK     pyhasalmenvpk.fi                5 rows, 12 EUR, My Calendar
    Alatalo-kiertue    moviecompanyalatalo.fi          13 rows, touring Kemijarvi

- Kinotour names venue and town on every row: Kyro, Naantali and Lieto on the day read. A
  touring venue set moves and this repo declares venues in the registry.
- Bio Pallas takes reservations by phone and Facebook Messenger. No ticket URL per row.
- Kino Hamina, Marita, Navettakino and Huvimylly publish portrait posters on their hosts.

**Browser only.**

- **Kino-Huovi**, Harjavalta: Duda site served as a JSON document; two screenings in prose
  with no year ("19.9. LA klo 18.00", "20.-21.9. SU ja MA klo 18.00").
- **Kino Akustiikka**, Ylivieska: town event system renders client-side.
- **Kino Kuusamotalo**: front page names one film, one post per film. **Off this
  list 2026-09-20**: the posts carry `Esitysajat:` with dated lines, and
  `/wp-json/wp/v2/posts` serves the same content, so no browser is needed. Built.
- **Lapinsuu**, Sodankyla: Webnode; the programme path its own navigation gives answers 404.
- **Rekolan Kino**, Vantaa: `popupkino.fi` publishes occasional screenings as one page or
  Facebook event each.
- **Kuvala**, Uusikaupunki: KuvaTahti storefront, above.
- **Kino K13**, Helsinki: `ses.fi` publishes festival weeks in prose ("ma 5.10. klo 18:
  LUVATTU MAA").
- **Juvan Kino**: municipal cinema paths 404, events page renders client-side.

**Runner reachability, 2026-09-18.** A non-residential fetcher read every readable
candidate's real page except **huvimylly.com**, which answered it 403 and an ordinary
connection 200, with `Server: Apache` and no `CF-Ray`. Cine and Star answered the same way
on 2026-09-08: the refusal is at the origin. The Helsinki service is a POST and was not
probed this way.

**Inferences and open questions**

- Three of the thirty-two were covered under another name, closed, or unreachable at DNS,
  so identity decided them before any endpoint was called.
- A cinema running a shop platform and a cinema embedding that shop's widget are two
  cases. The 2026-09-05 entry measured the second and closed Johku on it.

**Status and next step**

Fifteen of the thirty-two are built. Kino Myyri went in on 2026-09-18 as a third tenant on
`kinola.py`, with the four Johku storefronts, Ritz Vaasa, Kino Hamina and Kinotour; Marita,
Lieksan Kino, Navettakino and Pyhäsalmen VPK followed on 2026-09-19, each with a section of
its own below, and Bio Pallas, Bio Huvimylly and Alatalo-kiertue closed the server-rendered
list the same day. Kino Helios is declined on the accent. The eight browser-only and the
eight with nothing wait.

**Alatalo turned out to be five cinemas, not one.** The sweep row reads "13 rows, touring
Kemijarvi" and counted the rows without reading the headings above them: the page carries
Pudasjärvi, Haapajärvi, Kiuruvesi, Toholampi and Kemijärvi, and 2024 captures add a sixth,
Haapavesi. It is also the same operator as Bio Huvimylly, which the sweep listed as an
unrelated candidate: both pages carry the same operator's own address. Neither is visible from
a row count, which is what a sweep produces.

---

## The five from the nytleffaan diff (2026-09-19)

**Findings**, each read as an ordinary visitor on 2026-09-19.

| cinema | town | platform | outcome |
|---|---|---|---|
| Cinema Sheryl | Espoo | Kinola | built, fourth tenant |
| Haapamäen Elokuvat | Haapamäki | eTiketti | built as the fifth Johku storefront; on eTiketti from 2026-09-29 |
| Elävienkuvien teatteri | Forssa | none, own Foxy CMS | built, own parser |
| Bio-Salo | Salo | Nexxo | **publishes nothing** |
| Bio Sydväst | Parainen | none | **publishes nothing dated** |

Three are in `docs/archive/2026-09-providers.md`, one section each. The two that are not
built are here, because neither is a decision about an adapter.

**Bio-Salo is a real Nexxo tenant whose public API is empty.** biosalo.fi carries
`nexxo-scope` and its config names
`https://biosalo.fi/wp-content/plugins/nexxo-scope/public_api.php`, which is the endpoint
`nexxo.py` reads. Asked for `action=exportdailyshows` with `days=21&lang=fi` at
`locationid` 0 through 6, and with `upcoming=1` as well, it answered `{"shows":[]}` every
time. The pages agree: `/elokuva/` and the front page render the plugin's chrome -- the
labels `Ikäraja`, `Kesto`, `Liput`, `Esitykset` and the whole reservation dialog -- and not
one film, because the films are injected from that API. So this is not a parser problem and
not a missing `locationid`; the cinema is publishing no screening through the platform
today. **When it does, it is one `SITES` entry** against the existing adapter, with the
`locationid` discovered by asking rather than assumed, which is the rule the 2026-08-30
sweep's six dead ticket links wrote.

**Bio Sydväst publishes a rhythm, not a programme.** Parainen's cinema is municipal and
touring, and `pargas.fi/fi/biosydvast` and `pargas.fi/fi/-/bio` describe it in prose: every
other Friday at 18.00 in Houtskari, every other Sunday at 15.00 in Parainen, and four more
of the same shape across Nauvo, Korppoo and Iniö. Six such sentences and, on both pages,
**not one dated screening**: 602 and 558 text lines, zero carrying a date or a clock time
beside a film. The page itself says the programme goes out in the local paper, on Facebook
and on posters. That is the Kino Sampo Riihimäki case, a schedule in prose, and there is
nothing here for an adapter to read.

**Inferences and open questions**

- Three of the five ran on a platform this repo already reads, which is the sweep result
  the "check for an existing platform first" rule predicts and the reason two of the three
  cost a `SITES` entry each.
- Whether Bio-Salo's silence is a pause or a configuration is not established. The API
  answers in schema at every id, which is what an empty tenant and a mis-keyed one both
  look like from outside.

**Status and next step**

Re-read 2026-09-20, the one request at `locationid=1` this section asked for: HTTP 200,
`{"shows":[]}`, 12 bytes. Asked again the same day at `locationid` 0 to 3, all four
answered the same 12 bytes. Nothing has changed and nothing is owed here. Bio-Salo publishes
no screening through the platform, and the day it does it is one `SITES` entry with the
`locationid` discovered by asking. Bio Sydväst needs the municipality to publish dates in
a page rather than in prose, and nothing here tests for that.

---

## The Events Calendar, and the sweep that sized it (2026-09-18)

**Findings** (148 hosts swept once each, 2026-09-18)

Ritz Vaasa runs the WordPress plugin The Events Calendar, whose REST route is public:

    GET {base}/?rest_route=/tribe/events/v1/events&per_page=50&start_date=YYYY-MM-DD
        &categories={id}

`?rest_route=` rather than `/wp-json/`, since Ritz serves its REST under a language prefix.
One request per page, `total_pages` says how many, and `categories={id}` filters server
side. The category object carries `id`, `slug` and `taxonomy: tribe_events_cat`, and the id
is what a site declares here because the name is display text.

The sweep took the Filmikamari directory's 152 hosts, dropped four aggregators, and asked
each one for that route. **Four answered, two are usable cinemas.**

    ritz.fi              56 events   category Kino 19        6 film events
    muhos.fi             35 events   category Elokuvat 106   3 film events
    www.inkoo.fi        147 events   no film category
    www.teatteriunion.fi 26 events   the theatre company closed on 2026-09-15

- **Ritz Vaasa**: film artwork is portrait (1500x2138, 1080x1592) against 1200x800 for
  concerts. `cost_details.values` has one entry on a fixed price and two on a band
  ("10€ – 12€"), which is the structural answer to what settles a screening. One screening
  reads `Free` with `values: ["0"]`.
- **Tähti Kino**, Muhos: every film carries the same 768x470 `Tapahtumakalenteri.png`, so
  no poster is publishable there, and `cost` is a single amount ("11 €", "13 €").
- Both give `start_date` local, `timezone: Europe/Helsinki` and `utc_start_date`.

**Iobio, Inkoo, is unresolved and not implemented.** Its films sit in the generic
`Tapahtumakalenteri` and `Evenemangskalender` categories with no film category of their
own, and the same screening appears once under each, so a reader would have to deduplicate
across the two languages. The only thing marking a row as a film is the "IoBio:" prefix in
its title, and classifying on a word in a title is what the Kinola policy adopted on
2026-09-15 forbids. Two screenings were listed on the day this was read, 20.9. and 31.10.

**Inferences and open questions**

- 4 of 148 is a thin platform. It is worth one reader for two cinemas and is not an
  eTiketti-scale sweep.
- Whether Iobio has another source, or whether the maintainer wants a title-prefix
  exception for it, is open. Nothing here tests it.

**Status and next step**

Live as `scripts/providers/tribe.py`, two sites, cloud half, verified on the runner in the
dispatch that committed `8ef45c0e`. Iobio was declined on 2026-09-18 and the entry in
`IDEAS.md` names what would reopen it: a film category of its own, or one calendar rather
than two.

---

## Elokuvateatteri Marita, Outokumpu (2026-09-19)

**Findings** (elokuvateatterimarita.fi read as a visitor, plus ten Wayback captures of the
same page between 2025-05-29 and 2026-05-15)

WordPress on a theme of its own, no platform fingerprint. The front page renders the whole
programme in a `show-times` module, one `movie-info` block per screening with the film
page's href, a portrait poster with its dimensions in the tag, `Hinta:`, `Kieli:`, an
`age-img` and its content descriptors, and the date with its year beside `klo 17.00`.
`/naytokset/` renders the same module and the same rows.

- **`Kieli` is the spoken language.** The captures carry `Englanti` on *Five Nights At
  Freddy's 2*, *Sydäntalvi* and *Michael*, the lowercase `saksa` on one festival screening,
  and `Suomi` on Finnish films and on the dubbed prints of *Zootropolis 2* and *The Super
  Mario Galaxy Movie*. No subtitle field exists anywhere on the site.
- **The labels directory holds ratings and descriptors together**: `7`, `12`, `16`, `18`
  and `s` on `age-img`, `a`, `v`, `p` and `x` on `label-img`. The second set is KAVI's
  content descriptors, which this app does not render.
- **A price is per screening and not always one amount.** `Hinta: 10 €` is the ordinary
  case; the festival rows of 2025-09-13 read `Hinta: 10/8 €` and one row of 2026-05-16
  carried no price element at all.
- **An empty programme has a sentence.** Three captures, 2025-10-12, 2026-02-09 and
  2026-04-14, render the module with no `show-times-movies` container and the words `Ei
  tulevia näytösaikoja` in its place.
- The film page adds `Kesto`, `Lajityyppi`, `Ikäraja` as `K-7 (4)` and a Finnish synopsis
  under `Kuvaus`. No `liput`, `varaa`, `osta` or `lipunmyynti` string exists on the
  programme or the contact page, and `wp-json` exposes no custom post type for films or
  screenings.

**Inferences and open questions**

- Two films printing `1 h 27 min` on the same day is the pages' own figure, checked
  against both.
- Whether the cinema ever prints two languages in one cell is not established; the reader
  publishes nothing for a cell it cannot place in one.

**Status and next step**

Live as `scripts/providers/marita.py`, one provider, one venue, cloud half. Verified
2026-09-20 against the cinema's own page rather than only the log: `logs/run-marita.log`
reads `exit=0`, and the 2 showtimes in the committed data, 20.09. at 14.00 and 16.00 for
10 € each, are the two the site lists. Both carry a poster, and both per-film ticket
links answer 200. No next step.


## Lieksan Kino (2026-09-19)

**Findings** (lieksanelokuvat.net read as a visitor)

Hand-written HTML, no platform fingerprint and no WordPress. Five `<section>` elements
carry the page, and `section-b`, "Elokuvissa nyt", is the programme: one `article.entry`
per film with `<h3>` title in capitals, an `entry-text` synopsis, and a `<side>` holding
`Liput:`, `Kesto:`, a `rating-icon-{7,12,16,18,s}.svg` and a `showtimes` list of
`<li><p>Su 20.09. 15.00</p><p></p><p></p></li>`. 7 screenings over 4 films when read.

- **`section-c`, "Tulossa esitettäväksi", renders the same article markup** for five films
  with no `<side>` and no screening row, so the section is the only boundary between the
  programme and the coming-soon list.
- **The screening line prints no year**, and each line carries two further empty `<p>`
  elements whose purpose is not established; all seven were empty.
- Prices are per film, 12, 11, 13 and 13 euro. Two other figures on the page are different
  products: an advance-ticket voucher (1 for 13 €, 5 for 60 €) bought from the cinema by
  phone, and a PAM members' five euro discount.
- **Every film image is portrait**, 512x724 to 512x768 measured on all nine films across
  both sections, on the site's own host. The dimensions are not in the markup. The two
  landscape images on the page, 512x342 and 512x512, are in the notices section.
- No ticket sale, no per-film page and no booking host: "Liput ovat ostettavissa Lieksan
  kulttuurikeskuksen aulasta noin 30 minuuttia ennen näytöksen alkua."
- No language and no genre anywhere on the site.

**Inferences and open questions**

- The Wayback captures of this domain stop in 2021 on an older design, so nothing shows
  what an emptied programme looks like on this template.
- What the two empty `<p>` elements are for is unknown; the parser ignores them.

**Status and next step**

Live as `scripts/providers/lieksa.py`, one provider, one venue, cloud half. Verified
2026-09-20 against the cinema's own page rather than only the log: `logs/run-lieksa.log`
reads `exit=0`, and the 7 showtimes in the committed data, over 3 dates and 4 films at 11
to 13 €, are the seven the site lists, each with a poster and a ticket link. No next
step.


## Navettakino, Konnevesi (2026-09-19)

**Findings** (navettakino.fi read as a visitor)

WordPress block editor, no page builder and no ticketing platform. The front page is the
programme page, and the programme is prose inside `entry-content`:

    <p><strong>Tulevan viikolopun näytökset</strong></p>
    <p>Hetki ennen valoa<br>su 20.9 klo 15:00</p>
    <p>Presidentin kyyditys<br>su 20.9 klo 17:00</p>
    <p><br><br></p>
    <p><strong>Hetki ennen valoa</strong></p>  <figure>...719x1024 poster...</figure>
    <p>Klaus Härön uutuuselokuva ...</p>
    <p>K7, 87 min, liput 10 €</p>

- **The weekend list and the film blocks are different things.** Three blocks and two
  screenings on the day read: Ryhmä Hau had a block and no showing.
- **The editor's markup is not reliable and the paragraph text is.** One film heading
  closes its `<strong>` before the last letter, `Presidentin kyydity</strong>s`.
- The date prints no year and no dot after the month, `su 20.9 klo 15:00`.
- The metadata line varies in order: `K7, 87 min, liput 10 €`, `Kesto 1 h 27 min, K12,
  liput 10 €`, `Kesto 1 h 29 min, K7, liput 10 €`.
- Posters are portrait with the dimensions in the tag, 700x1000 to 719x1024.
- No online sale: "Lippukassa avataan 30 minuuttia ennen ensimmäistä näytöstä." No
  `varaa`, `osta` or booking link on the programme page.
- **The page states its own emptiness rule**: "Meillä on näytöksiä pääsääntöisesti vain
  viikonloppuisin, mutta toiminta on hieman epäsäännöllistä. Esitysajat ilmestyvät tälle
  sivulle aina alkuviikosta, mikäli viikonlopulle on näytöksiä tulossa."

**Inferences and open questions**

- The Wayback captures stop in 2024 on an older template and the two 2026 ones are the
  host's own challenge page, so what the page looks like with no screenings is not known.
  The adapter therefore confirms an empty weekend only from the heading rendering with
  nothing under it, and raises when the heading itself is gone.
- A runner read this host cleanly in the 2026-09-18 reachability pass, so `where="cloud"`
  is provisional on the first committed run as always.

**Status and next step**

Live as `scripts/providers/navetta.py`, one provider, one venue, cloud half. Verified
2026-09-20 against the cinema's own page rather than only the log: `logs/run-navetta.log`
reads `exit=0`, and the 2 showtimes in the committed data, su 20.9. at 15:00 and 17:00 for
10 € each, are the two the site lists, both with a poster and a ticket link. No next
step.


## Pyhäsalmen VPK, and the My Calendar plugin (2026-09-19)

**Findings** (pyhasalmenvpk.fi read as a visitor)

A volunteer fire brigade running a cinema since 1944, on WordPress with the My Calendar
plugin. The plugin registers a public REST namespace, `my-calendar/v1`, with one route:

    GET /wp-json/my-calendar/v1/events?from=YYYY-MM-DD&to=YYYY-MM-DD&category=1
    -> {"2026-09-25": [{occur_id, occur_begin, ts_occur_begin, event_title,
                        category_id, category_name, event_image, event_desc, ...}]}

- **Categories are real and declared.** `category_id` 1 is `Elokuvat`, and the route takes
  either the id or the name. 57 occurrences between 2026-01-02 and 2026-11-07 all carry
  it, and the room-booking page renders a calendar of its own.
- **An empty answer is ambiguous.** The route answers a bare `[]` to a quiet window, to
  `category=2` and to `category=999` alike, so an empty window says nothing about whether
  the category still exists.
- **The time is stated twice**: `occur_begin` as a local clock and `ts_occur_begin` as a
  Unix instant, and the two agree through Europe/Helsinki.
- **`occur_end` is always one hour after `occur_begin`**, the plugin's default rather than
  a runtime. No rating anywhere in the payload.
- `event_image` is a full-size upload with no dimensions in the payload; four measured run
  from 188x268 to 1000x1250. `event_desc` was empty on 56 of the 57.
- **Each event has a page** under `/mc-events/{slug}`, but the permalinks appear only in
  the calendar page's JSON-LD and carry numeric suffixes (`marsupilami-3`). The post type
  is not exposed in `wp/v2`, so the endpoint cannot give them.
- The cinema's own page states one price, `Elokuvalipun hinta: 12 euroa`, with no
  condition on the day, the format or the film, and says tickets are sold at the door
  30 minutes before and reserved by telephone.
- The programme has an eight-week gap, 2026-05-29 to 07-25.

**Inferences and open questions**

- 4 hosts on The Events Calendar and 1 here is not a platform sweep. Whether other Finnish
  cinemas run My Calendar is untested, and the route is cheap to ask.
- Whether the room bookings share this calendar under another category was not
  established; `category=2` answered empty for the window read.

**Status and next step**

Live as `scripts/providers/vpk.py`, one provider, one venue, cloud half. Verified
2026-09-20 against the cinema's own calendar rather than only the log: `logs/run-vpk.log`
reads `exit=0`, and the route this adapter reads returned the same 6 occurrences the
committed data carries, 12 € each, every one with a poster and a ticket link. No next
step.

**The page is not the check, the route is.** `/pyhasalmen-vpkn-elokuvat` renders a My
Calendar *upcoming* widget, and on 2026-09-20 it held five of those six: the 7.11. 14:00
screening fell outside it while the route still returned it. Comparing published rows
against that widget reports a row the cinema is in fact publishing.


## Why Huvimylly's own poster images are not published (2026-09-19)

Read 2026-09-19 off the live page and eleven Wayback captures of huvimylly.com between
2023-05-28 and 2026-04-11. Written down because the decision looks like a gap and is not
one, and because the obvious "fix" is the thing that would break it.

**What the site gives.** The posters sit in their own `<li>` after all the screening rows,
`alt=""` on every one, no link, no title, and no attribute tying an image to a row. The
`src` is `http://` while the `srcset` entries are `https://`. Full sizes on 2026-09-19 were
800x1143, 800x1142, 800x1200 and 800x1131, all portrait.

**Why position cannot pair them.** On 2026-09-19 the four happen to fall in row order with
filename slugs that match. On the 2026-02-17 capture they do not: the images run `vin`,
`lm`, `humiseva-harju`, `kaija`, `otso` against rows Vinski 2, Kaija Koo, Luottomies,
Humiseva Harju, Otso Karu. The filenames are hand-abbreviated and key back to nothing
(`lm` for Luottomies, `vin` for Vinski). Across the eleven captures the image count
disagrees with the row count in both directions, and twice a landscape still is used as a
poster (`mission-300x169.jpg`, `ohjus.jpg` at 300x168).

**What is published instead, measured on the live site 2026-09-19 after the first run.**
All four showtimes carry a mirrored portrait poster from the shared TMDB pass:
`data/posters/{9bcaf7ef167a0f8f,3630a8c5eeb607ff,a8cdd21dca604433,133d5c0758982817}.jpg`,
each 342x513, each answering 200 from this origin, 0 off-origin references. **There is no
initials tile on this cinema**, which is worth stating plainly because a "no poster from
the site" decision reads as if there were.

**The trap this section exists for.** The way to lose this is to pair the site's images to
the rows by position, which looks right on any single reading and puts another film's
poster on a row on the next one. That is the same failure class as a weak TMDB match and
is worse than a blank tile. If the cinema ever gives its images an `alt`, a link or a
title, the pairing becomes readable and the decision can be revisited on that evidence.

**Status.** Settled, not open. The adapter's docstring and the dated record in
[docs/archive/2026-09-providers.md](../archive/2026-09-providers.md) carry the same call;
this is where the measurement behind it lives.

## Kinotour's towns are more than the three declared (2026-09-19)

**Findings** (read once as a visitor from an ordinary connection, 2026-09-19)

- `www.kinotour.fi/locations/` answers 200, 55 kB, titled "Tapahtumapaikat". Its location
  links give slugs, and the ones on the first page alone are `askaisten-koulu`,
  `aurasali`, `drive-in-piispanristi`, `himolan-teatteri`, `holiday-club-caribia` (twice),
  `ikaalisten-tori`, `karkkilasali` (twice) and `kauppakeskus-mylly`. A `page` slug among
  them says the directory is paginated, so this is a floor and not the whole set.
- The registry declares three: Kyrö, Naantali and Lieto. Karkkila, Ikaalinen and
  Piispanristi are therefore towns this repository does not list.
- `/varaa-liput-elokuvatapahtumiin/`, the booking table the adapter reads, answered the
  same ordinary connection 200 with 11 `<tr>` rows on the same read.

**Inferences and open questions**

- A touring operator's location directory is not its programme. A town appears there
  whether or not it has a screening in the window, so adding a venue off this list alone
  would declare venues that publish nothing and sit unverified.
- `rows()` already counts the towns it cannot place, in `report["undeclared"]`, and the
  run prints them. That is the evidence a venue should be declared on, because it says the
  town has a screening *and* gives the string the row prints.

**Status and next step**

Not built. Declare a venue when `run-kinotour.log` names its town in the undeclared count,
not from the directory. No probe of the remaining pages of `/locations/` was made.

---

## Which platforms exist: the directory and domain sweeps

**Findings** (nytleffaan.fi, probed 2026-08-29; Vista domain sweeps 2026-08-27 and -29)

`nytleffaan.fi/elokuvateatterit/`, run by Suomen Filmikamari, lists every Finnish cinema:
225 entries across 152 hosts, each linking the cinema's own site. The page needs a browser
to render, which is why it sat unprobed for two days.

103 of the 152 hosts were swept, two requests each: the homepage for a platform
fingerprint and `/xml/TheatreAreas/`. **A signature in someone's HTML proves they are a
platform's customer, not that the platform answers us**, so every hit was verified against
the endpoint the adapter would need.

- eTiketti: 22 hosts carry `etiketti.app`; 16 serve the `/elokuvat/ohjelmistossa` listing.
- Nexxo: all 10 hosts carrying `nexxo-scope` answer `public_api.php`; six had live shows.
  Four return valid JSON with zero shows at every id.
- Johku: `kuvatahti.johku.com` is in the directory. The widget claims for kinotapiola.fi,
  kulttuurimylly.com and virtasali.fi were corrected on 2026-09-05 (see Johku above).
- MyCloudCinema: mantsala.cine.fi.

The **Vista domain sweep failed twice.** 45 guessed domains, then the real 103-host list:
zero hits beyond Savon Kinot. Azure blob enumeration on the shared asset host and a search
for the vendor's client list were also dead. Ten hosts answered 200 with their own HTML, a
soft-404 whose first bytes are not `<?xml`, so status alone would have reported ten false
hits. The sweep was blocked for two days on a presumed missing input, the domain list,
which turned out not to be what made it fail, and korjaamokino.fi, a real Vista site, was
not among the hosts probed at all.

**Inferences and open questions**

- Roughly 196 cinemas and 306 screens existed in Finland in 2009, and the tail clusters
  onto a few platforms. Platform adapters first; a bespoke parser only when a cinema is on
  none of them.
- Competitive picture: nytleffaan.fi is industry-run, gets exhibitor data and excludes
  event cinema and festivals; elokuviin.com includes festivals; kinossa.fi exists. "Suomen
  kattavin" is not a defensible claim against 225 directory entries and two services
  claiming full coverage.
- **Eventio** is a ticketing platform with cinema customers and was unprobed when this
  sweep was written. Kino Regina's film pages carry an Eventio `events.json` URL with the
  page's key, so KAVI's shop runs on it. Probed 2026-09-15; see the batch section above,
  which supersedes the next step this section used to set.

**Status and next step**

The eTiketti and Nexxo sweeps both landed (2026-08-30). The open candidate list lives in
`IDEAS.md` under "Provider coverage, and what is next", which is the status index. Eventio
was probed on 2026-09-15 and the finding is in the batch section above, so the next step
this section used to set is done. What is left here: a customer sweep for Eventio if
anyone wants one, and re-reading Kulttuurimylly when its programme resumes. The Eventio
sweep is answered above as far as it can be: the vendor is settled and the per-site set is
empty.

**The customer sweep was attempted on 2026-09-19 and it is not a fingerprint sweep.** The
marker is a `data-url` attribute on each rendered screening, emitted by the cinema's own
theme, so it exists only on a page that lists screenings. On Kino Regina that is the film
page, one level below the listing: its homepage carries nothing and its
`/ohjelmisto/elokuvat/` listing carries nothing.

Two passes were run and both were blind, which a control caught rather than a reviewer:

| pass | reach | result | control on kinoregina.fi |
|---|---|---|---|
| homepage only | 103 hosts, 97 answered | 0 hits | **miss** |
| homepage + one programme link | 103 hosts, 91 answered | 0 hits | **miss**, the picker took a JPG |
| homepage + listing + one film page | 17 uncovered hosts | 0 hits | **hit** |

The third pass finds Regina, so it works. It still establishes almost nothing about the
other seventeen: fifteen of them stopped after one request because their homepage offers
no programme link a plain fetch can recognise, which is the same property that already put
most of them on the browser-only list. **What a real sweep costs is per-site path
discovery, not a pattern**, and that is why "no sweep was run" stood for so long. Anyone
picking this up should keep the control in the run and print the per-host request count;
without both, a zero reads as an answer when it is a failure to ask.

---

## Six candidates, sized 2026-09-20

**Findings**, each read as an ordinary visitor on 2026-09-20.

| cinema | town | seats | platform | outcome |
|---|---|---:|---|---|
| Kino Hannikainen | Nurmes | 250 | Johku | built, sixth storefront |
| Kino Virta | Kalajoki | 216 | Johku | built, seventh storefront |
| Elokuvateatteri Matin-Tupa | Ylistaro | 201 | none, own WordPress | built, own parser |
| Kino Kuusamotalo | Kuusamo | 520 | none, own WordPress | built, own parser |
| Bio-Salo | Salo | 304 | Nexxo | **publishes nothing**, unchanged |
| Kinoma | Hyvinkää | 225 | none reachable | **no published programme** |

The four that were built have a section each in
[docs/archive/2026-09-providers.md](docs/archive/2026-09-providers.md). Seat counts are the
maintainer's brief and were not independently measured, except Kino Hannikainen's 250,
which the storefront's own `og:description` states, and Kino Kuusamotalo's 520, which
kuusamotalo.fi states.

**Two of six ran on a platform this repo already reads**, which is the rule "check for an
existing platform first" predicting itself again. Both cost one `SITES` entry. One of the
two, Kino Virta, had already been looked at on 2026-09-05 and recorded as "no Johku": that
pass read the page for an embedded widget, and the storefront was one link away on a
different host.

**Kinoma has no published programme this can read.** The cinema is listed by Hyvinkää's
own event calendar, at `tapahtumat.hyvinkaa.fi`, and that listing is a venue profile: a
description, an address, a phone number and links, and **not one dated screening**. Its
"Kotisivut" button points at `kinoma.fi`, which does not serve HTTPS at all -- the TLS
handshake is reset -- and over plain HTTP answers `302` to `https://showup.fi/varattu`, a
hosting company's "this address is reserved" page. The second domain the directories give,
`hyvleffat.fi`, answers `302` to `https://showup.fi/huoltokatko/?service=hyvleffat.fi`, the
same company's maintenance-break page. Both resolve to one address, `95.216.9.239`. The
operator address on the municipal listing, `mindfitmovies.com`, does not answer at all.

So there is no source, not a parser problem: nothing the cinema publishes carries a date
and a time. **What would change it** is the cinema bringing a site back up, or the
municipal calendar carrying its screenings as events rather than as a venue profile.
Neither is work in this repository, and no aggregator is read in their place: this repo
reads each cinema through the same public interface its own site uses.

## Eight cinemas, read 2026-09-21

Two were built and are recorded in `docs/archive/2026-09-providers.md`: Kino Akustiikka
(Ylivieska) on the town's Localhub calendar, and Kino-Huovi (Harjavalta) with its own
parser. What the other six are, as measured that day, and what each one waits on.

### Kuva-Tähti's two cinemas run Johku's client-rendered storefront

**Kauttuan Kuva (Eura) and Kuvala (Uusikaupunki)**, one merchant, `johku.com/kuvatahti`.
Not the storefront the seven built Johku cinemas use. Those render the programme
server-side, in `showgroup` / `daytitle` / `js-grid-show` blocks that `johku.py` reads.
This merchant's pages are a Nuxt application: `kuvatahti.fi` and `kuvatahti.johku.com`
serve the same markup, and on both the whole visible page is 23 lines of chrome with no
film, no date and no time. Five surfaces were read and none carries a dated row:
the storefront root, `/fi_FI/naytosajat`, `/fi_FI/naytosajat/kauttuan-kuva`,
`/fi_FI/naytosajat/kuvala`, and `/fi_FI/tulevia-elokuvia`, which renders an empty category.

The `__NUXT_DATA__` payload, 1,471 entries on each cinema's page, holds the shop's own
furniture, its payment methods and the word `showtimes`, and **not one date-like string**.
So there is no last visible programme date to report: no surface this repository may read
carries one at all. The rows the visitor sees are fetched by the widget afterwards, which
is the `/api/auth/widget-session` and `X-ApiKey` flow the maintainer declined for Kino
Engel on 2026-09-20. That decision is not reopened here and no key was copied, replayed or
recorded; the token-shaped string in the page is deliberately not written down.

**What would change it:** this merchant moving to the server-rendered storefront template,
the cinemas publishing a feed, or the maintainer separately approving the widget flow.
The first two make both cinemas an ordinary `johku.py` `SITES` entry.

### Rekolan Kino, Vantaa, has no upcoming screening

Its own Squarespace site at `rekolankino.fi/elokuvat` renders the programme server-side and
the structure is readable: an `h4` per screening carrying the title and a Finnish date and
time, a description, an image and an "Osta lippuja" button. Read 2026-09-21 it held five
rows, `Pe, 18.9.` twice and `Su, 20.9.` three times, **every one of them in the past**, and
nothing dated later anywhere on the page.

A parser could be written against that shape, and it would return zero rows today. Zero
rows has to fail the site, because the page still lists films and `common.EmptyProgramme`
takes positive evidence of an empty listing rather than a parse that found nothing. So the
adapter would fail every run from its first, and no published row could be checked against
the cinema's own page, which is the step six dead Nexxo links bought.

One finding for whoever picks it up: **the ticket buttons go to `myyri.kinola.ee`**, the
Kinola storefront of Kino Myyri, already a provider here. Whether Rekola is a second venue
of that tenant or a separate account on one storefront is not settled, and settling it
decides whether this is a `kinola.py` `SITES` entry rather than a new parser.

**What would change it:** the cinema publishing its next programme.

### Juvan Kino publishes through a municipal calendar that has nothing on

The cinema category of `juvantapahtumat.fi` is the first-party route and it is empty. Read
2026-09-21, `/kategoriat/elokuvat` lists **"Elokuvat ( 0 tapahtumaa)"** in its own sidebar
and renders "Valitussa kategoriassa ei ole tapahtumia", and the RSS twin,
`?format=feed&type=rss`, is a 1,033-byte channel with a `lastBuildDate` and **no `item`
element at all**. Eleven other categories on the same calendar do carry events, so the
calendar itself is alive and the cinema's category is the empty one.

The general JSON feed the municipality's own homepage consumes was not used: it carries
unrelated events and exposes no clean per-row venue field, so it could not establish that a
row is this cinema's. A title that looks like a film is not evidence of the organiser.

**What would change it:** the municipality publishing the next programme in that category.
The RSS carries enough for a row when it does.

### Kino K13 and Kino Helios are readable, and blocked on the accent contract

Both are in Helsinki, and both were parsed against live data before anything was written.

**Kino K13**, `ses.fi/kinok13/`, renders its programme server-side in a
`<section id=ohjelmisto>` whose free prose holds four timed rows for the Polish Film Weeks,
`ma 5.10.` to `to 8.10.`, each `klo 18`, with a runtime and a Finnish rating sentence on
three of the four and free admission stated for the block. The four Kinokka evenings on the
same page carry a date and **no time**; the organiser page they link,
`kaupunginosat.fi/skatta/ohjelmisto/`, was fetched and contains no `klo` anywhere, so
nothing publicly fetchable settles those four and inventing a time is not an option. Two
festival headings, `5.-9.10.2026 Puolan elokuvaviikot` and `6.-8.11.2026 Serbian
elokuvapäivät`, are date ranges and not screenings.

**Kino Helios**, the Malmitalo hall, answers a JSON `EventData` string at
`malmitalo.fi/services/Resurssivaraus/EventCalendarService.svc/GetEvents`. Filtering it on
`eventLocation == "42"`, `mainEventType == "29"` and `subtitle == "Kino Helios"` gave
**exactly 22 rows** over 2026-09-23 to 2026-10-24, every one at `Malmitalon Pieni sali`,
every one with a `lippu.fi` ticket link and a rating suffix in its title. The eleven other
type-29 rows at that location are `Doc Helios`, `Yleisön suosikit` and blank-subtitle
strands and are not this cinema. `end - start` is 120 minutes on 21 of the 22 rows and 300
on one, so it is a booking slot and settles no runtime, and `priceinfo` is the string
`None` on every row, so the house tariff is not a per-screening amount.

**Neither can be registered.** Helsinki already holds eight chains, and a ninth accent has
to clear 14.4 dE00 against all eight in the combined-city view that
`tests/test_accent_check.py::test_every_combined_city_pair_clears_the_floor` holds without
exception. Swept here at step 4 over the whole cube, 262,144 colours: **0 of the 94,359
inside the L\* 38-60 band clear it**, and the best reachable is 12.12 (`#886098`), whose
worst Helsinki pair `scripts/accent_check.py --candidate '#886098' --city Helsinki` prints
as 12.1 against Gilda. Outside the band 70,460 colours clear it, all of them too light or
too dark for the 3 px rule the band exists for.

So the blocker is not the data and not the parse. It is the open maintainer decision
already recorded in `IDEAS.md` under "Helsinki is full at eight chains": what the city view
does when a city is full. Two real candidates now trigger it.

### Rekolan Kino and Kino Myyri: one ticketing host, and that is all it proves (2026-09-21)

Read-only follow-up to the finding above, asked because a shared Kinola account would make
Rekolan Kino a `kinola.py` `SITES` entry rather than a new parser. Measured that day:

- **The ticket host is shared.** All five "Osta lippuja" buttons on `rekolankino.fi/elokuvat`
  point at `myyri.kinola.ee/web/screening/{uuid}`, the same storefront host Kino Myyri sells
  through.
- **Kino Myyri's own listing does not carry Rekola.** `kinomyyri.fi/ohjelmisto/` mentions
  "Rekola" zero times, names no hall anywhere, and the committed `area-myyri-vantaa.json`
  has an empty `aud` on all 20 rows. Neither cinema's site names the other.
- **The storefront has no public programme.** `myyri.kinola.ee/` is a Kinola login page,
  and `/web/` answers 404. The only public surface is the per-screening page, which is
  client-rendered and carries the single word "myyri" server-side.

**So it is not settled**, and nothing publicly readable settles it: sharing a ticketing
host is consistent with one account holding two venues and equally with two cinemas selling
through one storefront. What is settled is the consequence. `kinola.py` reads each tenant's
own WordPress `kinola-event` listing, and Rekolan Kino's site is Squarespace, so it would
need its own parser even if the account were shared. Registration waits on the cinema
publishing a programme either way, which is the blocker already recorded.

### Riviera: a disabled screening button and the seat count (2026-09-25)

**Findings.** Read once on 2026-09-25 through the listing request `riviera.py` makes (the
`filter_movies` POST to `admin-ajax.php`, area 1040): 88 screenings, 2 with a `disabled`
button, "Twin Peaks: Kausi 1 (1990)" on 26.9. at 34/34 seats taken and "Dyyni: Osa kolme"
on 15.12. at 50/50. No row carried a disabled button over free seats. Every row printed a
"Varatut paikat" count.

**Inference.** A disabled button has meant "no seats left" in every row seen. What the
theme draws for a sale not yet open was not observed, and nothing on the page states it.

**Implementation.** `riviera.parse` takes the seat count where one is printed and the
button only where none is; see the 2026-09-25 entry in `docs/archive/2026-09-providers.md`.
