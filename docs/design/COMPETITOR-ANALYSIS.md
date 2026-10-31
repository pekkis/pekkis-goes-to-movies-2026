# Competitor analysis

What the other Finnish showtime aggregators can do that we can't, and the other way round. Observed on 2026-10-30 from public pages only: front pages, Tampere's city pages, and the film pages of Lapin sota. Two sites (Kinossa, kinot.fi) render in the browser, so their features were read from the interface text and routes in their JavaScript bundles; no APIs were called.

**[V]** marks what was seen on the page; **[A]** marks an inference or a figure the site states about itself. Features that sit behind interaction (voting, favourites) were seen only as labels. Repeat the survey before relying on it: these sites change.

## The sites

| Site                                    | Coverage (their own figures)                            | Operator                                          | In one line                                                               |
| --------------------------------------- | ------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------- |
| [Leffavuoro](https://leffavuoro.fi/)    | 141 venues, 100 cities (13.10) [A]                      | A hobbyist; open source (AGPL), our code ancestor | City pages by day; Finnish, Swedish and English UI                        |
| [Elokuviin.com](https://elokuviin.com/) | 162 cinemas, 118 places, "6,100+ screenings a week" [A] | Lunta Labs Oy (also Keikkalista.fi)               | A film magazine with showtimes: reviews, trailers, articles               |
| [Kinoon.fi](https://kinoon.fi/)         | 171 cinemas, 128 cities [A]                             | Kinoon Oy                                         | Personal features and seat data; a demand-voting product for distributors |
| [Kinossa.fi](https://kinossa.fi/)       | not stated                                              | not stated                                        | Bare: films, cinemas, days and a film search                              |
| [kinot.fi](https://www.kinot.fi/)       | Helsinki-area neighbourhood cinemas only                | Korttelikinot ry                                  | One filter for cinema and one for day                                     |

For comparison, we had 157 venues in 110 cities from 102 providers on the same day.

## Each site in detail

### Leffavuoro

- **Front page:** search "Valitse kaupunki tai teatteri" with tabs for cities and areas; 19 cities linked, "Ja paljon muita…" [V].
- **Quick filters:** "Suom. puhe" (Finnish speech), "Lapsille" (for children), "Anniskelu" (licensed bar) [V]. No subtitle, format, accessibility, date or time filters [V].
- **City page:** grouped by day ("Pe 30.10."), then by film [V]. Each film has a poster, a TMDB score with its vote count, the age rating, genres, runtime, and a synopsis from the cinema [V]. Each showtime row has the time, cinema and hall, spoken language, subtitles ("tekstitys: suomi/ruotsi", "ei tekstitystä"), labels ("Ensi-ilta", "Anniskelu", "iSense") and the price where known, and it links to the cinema's ticket page [V].
- **Also:** FI / SV / EN interface, a theme toggle (◐), a favourites star (unlabelled) and a public status page [V]. Its Tampere page listed three cinemas [V].

### Elokuviin.com

- **Navigation:** places, films (now showing, coming soon, best rated by IMDb), festivals, cinemas, articles [V].
- **City page:** day tabs (today, tomorrow, then dates), a cinema filter ("Kaikki" plus each cinema), and two views: by film ("Elokuvittain") or by showtime ("Näytöksittäin") [V]. Rows show only the cinema and times: no hall, language, subtitles, price or ticket link [V].
- **Film page:** poster, genres, IMDb score, "Katso traileri", synopsis without a source, director, cast, writers, runtime, premiere, year and countries [V]. Critics' scores as one line each ("Helsingin Sanomat: arvio 2/5 tähteä", "Episodi: arvio 3/5 tähteä") [V]. Showtimes: a city filter with counts, day buttons, and a table of time, cinema and "Osta liput →" to the cinema's own site [V]. Also sharing (Facebook, X, copy link) and ten recommendations ("Sinua voisi kiinnostaa myös") [V].
- **Counts:** Lapin sota's page claimed "1505 näytöstä · 99 paikkakunnalla" [V]. That points to a longer window than ours, or looser grouping of titles [A].
- **Editorial:** festival pages (Cinemare, Night Visions, Rokumentti) and articles such as "Halloween 2026 | Vuoden parhaat kauhuelokuvat" [V].

### Kinoon.fi

- **Navigation:** films, showtimes, "Äänestä elokuva teatteriin" (voting), "Historia"; on phones a bottom tab bar with "Jaa" (share) and "Hae" (search) [V]. Browse menu: premieres, now showing, Finnish films, the film archive, festivals, cities, cinemas, genres [V].
- **City page:** "Tänään" and "Tällä viikolla" tabs, genre chips with counts ("Uutuudet 41", "Klassikot 4", "Kauhu 9" …), and showtimes grouped by day, film, then cinema [V]. Time buttons go to the cinema's ticket page through a redirect that adds UTM parameters [V].
- **Film page:** synopsis, stills, a video, director and cast (TMDB). Showtimes in time order with the hall, **seat count ("106 paikkaa")**, the format ("iSense", "LUXE", "PRIME", "VIP"), subtitle codes ("SUO/RUO"), and availability: "Loppuunmyyty" or "Liput ovelta" [V]. "Suosikki" (favourite) and "Piilota" (hide) controls [V].
- **Personal:** "Historiani", a viewing history to share with a friend when planning a movie night [V]. Whether it needs an account was not visible [A].
- **Voting ("Äänestä valkokankaalle"):** people suggest and vote for films they want on the big screen; the most wanted are ranked (new films and classics) [V]. Distributors and cinemas who get in touch are offered a notification when a film passes a chosen number of votes, an understanding of the audience by region, and a way to reach the people who wished for a film when its screening goes on sale [V]. No prices or terms are given, and the page does not say what it collects from voters [V]; whether this is paid is not known.

### Kinossa.fi

- Routes: films, a day view, cinemas, a cinema, a film [V]. Interface text: "Hae elokuvaa…", "Valitse päivä", "Kaupungit", "Pääkaupunkiseutu", "Päivän ohjelma" [V]. No location, trailers, ratings or sharing in the bundle [V].

### kinot.fi

- A WordPress site with a Vue app, run by Korttelikinot ry for the Helsinki-area neighbourhood cinemas [V]. Filters: "Kaikki teatterit", "Kaikki päivät", "Tänään" [V].

## What they have that we don't

1. **Seat counts and "sold out"** (Kinoon). "Is it full yet?" is a hobbyist's question. Our model has `availability`, and some sources give it ("Kiirehdi", "Loppuunmyyty"; Cinema Niagara's "Loppuunvarattu" is still unmapped), but the site does not show it as a feature.
2. **Swedish and English** (Leffavuoro). We are Finnish-only, yet we cover Swedish-speaking cinemas (Bio Savoy, Bio Pallas, Bio Dux).
3. **Keeping films** (Kinoon: favourites, hiding, history). We have no way to follow a film.
4. **Trailers and critics' scores on film pages** (Elokuviin). Trailers from TMDB are allowed by our rules. We have critics' scores, but they are opt-in on purpose.
5. **Discovery and editorial:** coming soon and premieres, genre pages, recommendations, articles (Elokuviin, Kinoon).
6. **A share button** (Elokuviin, Kinoon). Our addresses can be shared, but there is no button.
7. **A choice of views:** by film or by showtime (Elokuviin).
8. **Coverage at the edges.** Elokuviin lists about 25 places we don't have, after joining villages to their municipalities (Karjaa and Tammisaari are Raasepori; Toijala, Akaa; Nikkilä, Sipoo; Tervakoski, Janakkala; Järvelä, Kärkölä):
   - **Confirmed gap:** Kino Visio, Sotkamo, with three screenings on 30.10 [V].
   - **To check:** Ähtäri, Alajärvi, Alavus, Enontekiö, Eura, Huhtamo, Ilomantsi, Kangasniemi, Kauhava, Kolari, Luumäki, Mäntyharju, Nivala, Närpiö, Parikkala, Pomarkku, Punkalaidun, Rautjärvi, Ruokolahti, Sodankylä, Sulkava, Sysmä, Utsjoki, Uusikaupunki, Vimpeli. Some are empty listings: Uusikaupunki's Kuvala had nothing on [V].
   - **Ours only:** about 20 places Elokuviin lacks, Maarianhamina (Bio Savoy) among them [V].

**Follow-up, 2026-10-30:** of the cinemas Elokuviin had with shows and we lacked, ten are now read: Kino Kellokas (Kolari), Kino Visio (Vuokatti, Sotkamo), Oulun Elokuvakeskus's Studio, Vimpelin Nuorisokuvat, and the six thought to need Johku's widget key (the Sun Kino group's four, Kauttuan Kuva and Kuvala), which the storefronts' anonymous schedule call serves after all. Two publish only on Facebook (Sysmä, Enontekiö), and Kino Näyttämö's source is not found. Details in [data-sources.md](../data-sources.md#not-read-yet-candidates-2026-10-15).

## What we have that they don't

1. **Search by the hobbyist's question.** Several days at once, a place with a radius or "near me", time of day, venue and film, with faceted counts (`/fi/haku`). The others offer one city and one day, or a week.
2. **Special screenings as a dimension of their own.** Series, festivals, clubs and audiences: knitting, seniors, babies, captions, audio description, 35 mm, guests. A series spans cinemas (knitting screenings at Kino Pirtti and Bio Pallas). Elokuviin and Kinoon have festival pages; no one has the rest.
3. **Live showtimes:** started, starting within an hour, later.
4. **A venue map.**
5. **The version at every source:** spoken language, dubbing, subtitles, projection, price. Leffavuoro comes closest; Elokuviin and Kinoon show only times on their city pages.
6. **Certain matches only.** A film is linked to TMDB only when the match is certain; otherwise it stays unmatched.
7. **More than a website:** an open API, the CLI, the MCP server for chatbots, and history in the database.
8. **The ethical line:** ticket links copied as the cinemas give them, without tracking parameters (Kinoon adds UTM); no cinemas' texts (Leffavuoro shows the cinemas' synopses).
9. **Open source** (AGPL). Only Leffavuoro is too.

## Questions for user testing

- Does seat availability matter more than critics' scores?
- Would hobbyists keep a list of films, and want word when one comes to their area?
- Is a Swedish or English interface needed?
- One view by film, or a choice between by film and by showtime?
- How much discovery (coming soon, recommendations) do hobbyists want, given they follow films closely already?

Kinoon's voting is a different product: audience demand shown to distributors and cinemas. It is noted here, not proposed.
