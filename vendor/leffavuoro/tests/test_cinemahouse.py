"""Cinemahouse: the cinema-reservations plugin at three cinemas on one adapter.

The fixtures follow the markup read on 2026-09-14 at kinopiispanristi.fi, kinolumo.fi
and laitilankino.fi: a `cr-movies-filter-select` built from the programme's own dates, a
`cr-movie-tile` grid carrying the poster, the age limit, the runtime and the genres, and
a `cr-screening-row` list carrying "15.9. 13:00 · Sali 1", the price, the free seats and
the reservation link with its `data-screening-id`. Each site gets its own page with two
rooms and two dates, because a one-row fixture exercises neither the dedup key nor the
per-site scoping.

Three things this file exists to pin. The screening id is unique inside a site and
collides across them, so it may never be compared across sites. A row's date carries no
year and the programme runs months out, so the year is the nearest one rather than the
current one. And an empty programme is read off the filter's day list, which the film
parse never touches: a page that still offers a day, or still lists a film, and yields no
screening is a broken parse and has to fail.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import cinemahouse as ch
import common
import registry
import run

ROOT = _ctx.ROOT
TODAY = datetime.date(2026, 9, 14)

PIISPANRISTI = ch.SITES[0]
LUMO = ch.SITES[1]
LAITILA = ch.SITES[2]


# ---------------------------------------------------------------- fixtures

def tile(base, title, slug, age="12", runtime="112 min", genres="Draama",
         poster="poster-1.jpg"):
    """One `cr-movie-tile`, in the grid's own order of badges, title and meta."""
    badges = "".join(
        [f'<span class="cr-badge cr-badge--age">{age}</span>' if age else "",
         f'<span class="cr-badge cr-badge--runtime">{runtime}</span>' if runtime else ""])
    img = (f'<img width="500" height="740" src="{base}/wp-content/uploads/2026/09/{poster}" '
           f'class="attachment-cr_poster size-cr_poster" alt="{title}" loading="lazy" '
           f'srcset="{base}/wp-content/uploads/2026/09/{poster} 500w" />') if poster else ""
    meta = f'<div class="cr-movie-tile__meta">{genres}</div>' if genres else ""
    return (f'<article class="cr-movie-tile">'
            f'<a class="cr-movie-tile__link" href="{base}/elokuvat/{slug}/" aria-label="{title}">'
            f'<div class="cr-movie-tile__poster">{img}</div>'
            f'<div class="cr-movie-tile__overlay">'
            f'<div class="cr-movie-tile__badges">{badges}</div>'
            f'<h3 class="cr-movie-tile__title">{title}</h3>{meta}'
            f'<div class="cr-movie-tile__cta" aria-hidden="true">Katso n&#228;yt&#246;sajat</div>'
            f'</div></a></article>')


def row(base, title, when, room="Sali 1", price="12,00 &#8364;", free=89, seats=95,
        sid="3143", cta=True):
    """One `cr-screening-row`. `cta=False` is a row with no reservation link."""
    link = (f'<a class="cr-screening-cta" data-screening-id="{sid}" '
            f'data-embed-url="{base}/varaa/?cr_booking_embed=1&#038;screening_id={sid}" '
            f'href="{base}/varaa/?screening_id={sid}">Varaa</a>') if cta else ""
    seat_line = (f'<div class="cr-screening-seats">Vapaat paikat: {free} / {seats}</div>'
                 if free is not None else "")
    return (f'<div class="cr-screening-row"><div class="cr-screening-main">'
            f'<div class="cr-screening-title">{title}</div>'
            f'<div class="cr-screening-meta">{when}'
            + (f' · {room}' if room else "") + '</div></div>'
            f'<div class="cr-screening-stats">'
            f'<div class="cr-screening-price">{price}</div>{seat_line}</div>{link}</div>')


def day(text):
    """The heading the plugin puts before each day's rows. It bounds the last row of the
    day, so a fixture without one never exercises that boundary."""
    return f'<div class="cr-screening-day-header">{text}</div>'


def page(days=(), tiles=(), rows=(), filter_select=True):
    """The front page: the filter, the film grid and the screening list, then the footer
    markup every real page carries after the last row."""
    options = "".join(f'<option value="date:{d}">x</option>' for d in days)
    select = (f'<div class="cr-movies-filters" data-post-type="cr_movie" '
              f'data-posts-per-page="100"><form class="cr-movies-filter-form" method="get">'
              f'<select name="when" class="cr-movies-filter-select" aria-label="Valitse '
              f'päivä">{options}</select></form></div>') if filter_select else ""
    grid = (f'<div class="cr-movies-tabpanel" data-tab="movies">'
            f'<div class="cr-movies-grid">{"".join(tiles)}</div></div>') if tiles else ""
    body = (f'<div class="cr-movies-tabpanel" data-tab="screenings" style="display:none;">'
            f'<div class="cr-screenings-list">{"".join(rows)}</div></div>'
            ) if rows else '<div class="cr-empty">Ei n&#228;yt&#246;ksi&#228;.</div>'
    return ("<html><body><main>" + select + grid + body +
            '</main><section class="ch-site-footer"><a href="/tietosuoja/">Tietosuoja</a>'
            "</section></body></html>")


PR = PIISPANRISTI["base"]
LU = LUMO["base"]
LA = LAITILA["base"]

# Kino Piispanristi: two rooms, two dates, a dubbed run, a strand run, a sold-out row,
# the same screening listed twice and a row whose clock cannot be read.
PR_PAGE = page(
    days=("2026-09-15", "2026-09-16"),
    tiles=(tile(PR, "Hetki ennen valoa", "hetki-ennen-valoa", age="7", runtime="87 min",
                genres="Draama", poster="poster-999.jpg"),
           tile(PR, "Kojootti vs. ACME SUOMEKSI", "kojootti-vs-acme-suomeksi", age="7",
                runtime="104 min", genres="Komedia, seikkailu", poster="poster-1033.jpg"),
           tile(PR, "ENNAKKON&#196;YT&#214;S: Dyyni: Osa kolme", "ennakkonaytos-dyyni-osa-kolme",
                age="", runtime="145 min", genres="Scifi", poster="poster-1018.jpg")),
    rows=(day("Huomenna 15.9."),
          row(PR, "Hetki ennen valoa", "15.9. 13:00", sid="3143"),
          # The same screening a second time: a repeated surface must collapse to one.
          row(PR, "Hetki ennen valoa", "15.9. 13:00", sid="3143"),
          row(PR, "Kojootti vs. ACME SUOMEKSI", "15.9. 17:45", room="Vip 4",
              price="15,00 &#8364;", free=0, seats=40, sid="3154"),
          day("keskiviikkona 16.9."),
          row(PR, "ENNAKKON&#196;YT&#214;S: Dyyni: Osa kolme", "16.9. 21:00",
              room="Sali 3", price="16,50 &#8364;", sid="3197"),
          # No clock in the meta line: one odd row, dropped, the rest kept.
          row(PR, "Rikkinäinen", "16.9.", room="Sali 1", sid="3198")))

# Kino Lumo: the screening ids collide with Piispanristi's on purpose.
LU_PAGE = page(
    days=("2026-09-15", "2026-09-17"),
    tiles=(tile(LU, "Hetki ennen valoa", "hetki-ennen-valoa", age="7", runtime="87 min",
                genres="Draama", poster="poster-592.jpg"),
           tile(LU, "Spider-Man: Brand New Day", "spider-man-brand-new-day", age="12",
                runtime="145 min", genres="Action, seikkailu", poster="poster-526.jpg")),
    rows=(day("Huomenna 15.9."),
          row(LU, "Hetki ennen valoa", "15.9. 18:00", room="Premium 3",
              price="14,00 &#8364;", sid="3143"),
          day("torstaina 17.9."),
          row(LU, "Spider-Man: Brand New Day", "17.9. 19:30", room="Sali 1",
              price="12,00 &#8364;", sid="3154")))

# Laitilan Kino: one room, a fortnightly programme, a title whose age limit is "S".
LA_PAGE = page(
    days=("2026-09-24", "2026-10-08"),
    tiles=(tile(LA, "Presidentin kyyditys (Kahvi ja Kino)", "presidentin-kyyditys-kahvi-ja-kino",
                age="12", runtime="87 min", genres="Comedy, Drama", poster="poster-198.jpg"),
           tile(LA, "Pirjo i Sverige (Kahvi ja Kino)", "pirjo-i-sverige-kahvi-ja-kino",
                age="S", runtime="88 min", genres="Comedy, koko perheen",
                poster="poster-213.jpg")),
    rows=(day("torstaina 24.9."),
          row(LA, "Presidentin kyyditys (Kahvi ja Kino)", "24.9. 13:00",
              price="11,00 &#8364;", free=74, seats=77, sid="149"),
          day("torstaina 8.10."),
          row(LA, "Pirjo i Sverige (Kahvi ja Kino)", "8.10. 13:00",
              price="11,00 &#8364;", free=67, seats=77, sid="150")))

# A programme that ran out: the filter offers no day, the grid lists no film.
EMPTY_PAGE = page(days=(), tiles=(), rows=())
# The same page with the film grid still full: the parse found nothing and must fail.
FILMS_BUT_NO_ROWS = page(days=(), tiles=(tile(PR, "Hetki ennen valoa", "hetki-ennen-valoa"),),
                         rows=())
# A day still on offer and no row: the screening template moved.
DAY_BUT_NO_ROWS = page(days=("2026-09-15",), tiles=(), rows=())
NO_FILTER = page(days=("2026-09-15",), tiles=(), rows=(), filter_select=False)


def film_page(paragraphs):
    body = "".join(f'<p class="wp-block-paragraph">{p}</p>' for p in paragraphs)
    return ('<html><body><main class="kassa-app kassa-app--single-movie">'
            '<header class="cr-movie-hero"><h1 class="cr-movie-title">Film</h1></header>'
            '<section class="cr-movie-body"><div class="cr-movie-synopsis"><h2>Synopsis</h2>'
            f'<div class="cr-prose">{body}</div></div></section>'
            '<section class="cr-showtimes"><h2>Näytösajat</h2></section>'
            "</main></body></html>")


SYNOPSIS = ("Tositapahtumiin perustuva elokuva kuvaa jännittävät 72 tuntia "
            "ennen h-hetkeä, jolloin vapaan maailman kohtalo on vaakalaudalla.")
FILM = film_page([SYNOPSIS])
# A screening note before the blurb, the Gilda shape, in its two forms: one that quotes a
# price, which synmerge refuses on its own, and one that only names the cinema, which is
# the half the site's `notes` stems are there for.
PRICED_NOTE = film_page(["Liput 11 euroa, maksu ovella.", SYNOPSIS])
NAMED_NOTE = film_page(["Laitilan Kinon kahvitarjoilu alkaa puoli tuntia ennen "
                        "n\u00e4yt\u00f6st\u00e4.", SYNOPSIS])


# ---------------------------------------------------------------- parsing

class ScreeningsTest(unittest.TestCase):
    def parse(self, site, text, today=TODAY):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            shows = ch.parse(text, site, today=today)
        return shows, out.getvalue()

    def test_a_row_becomes_a_showtime_with_the_grid_metadata(self):
        shows, _ = self.parse(PIISPANRISTI, PR_PAGE)
        s = shows[0]
        self.assertEqual(
            (s["title"], s["start"], s["aud"], s["price"], s["rating"], s["len"],
             s["genres"], s["provider"], s["venue"], s["theatre"]),
            ("Hetki ennen valoa", "2026-09-15T13:00:00+03:00", "Sali 1", "12€",
             "K-7", "87", "Draama", "kinopiispanristi", "piispanristi-kaarina",
             "Kino Piispanristi"))
        self.assertEqual(s["url"], f"{PR}/varaa/?screening_id=3143")
        self.assertEqual(s["img"], f"{PR}/wp-content/uploads/2026/09/poster-999.jpg")
        self.assertEqual(s["movieUrl"], f"{PR}/elokuvat/hetki-ennen-valoa/")

    def test_a_repeated_row_collapses_to_one_screening(self):
        shows, _ = self.parse(PIISPANRISTI, PR_PAGE)
        at_13 = [s for s in shows if s["start"].endswith("T13:00:00+03:00")]
        self.assertEqual(len(at_13), 1)
        self.assertEqual(len(shows), 3)

    def test_a_row_with_no_readable_clock_is_dropped_and_the_rest_kept(self):
        shows, log = self.parse(PIISPANRISTI, PR_PAGE)
        self.assertNotIn("Rikkinäinen", [s["title"] for s in shows])
        self.assertIn("1 screening row(s) with no readable date", log)
        self.assertEqual(len(shows), 3)

    def test_the_screening_id_is_never_compared_across_sites(self):
        """3143 and 3154 are Piispanristi's ids and Lumo's. Deduplicating on the bare id
        across the two sites would silently drop Lumo's whole programme."""
        pr, _ = self.parse(PIISPANRISTI, PR_PAGE)
        lu, _ = self.parse(LUMO, LU_PAGE)
        self.assertEqual(len(lu), 2)
        self.assertEqual({s["venue"] for s in pr}, {"piispanristi-kaarina"})
        self.assertEqual({s["venue"] for s in lu}, {"lumo-salo"})
        self.assertEqual({s["provider"] for s in lu}, {"kinolumo"})
        self.assertEqual(sorted(s["start"] for s in lu),
                         ["2026-09-15T18:00:00+03:00", "2026-09-17T19:30:00+03:00"])

    def test_a_row_with_no_reservation_link_keeps_its_own_identity(self):
        rows = (row(PR, "Hetki ennen valoa", "15.9. 13:00", cta=False),
                row(PR, "Hetki ennen valoa", "15.9. 15:00", cta=False))
        shows, _ = self.parse(PIISPANRISTI, page(days=("2026-09-15",), rows=rows,
                                                 tiles=(tile(PR, "Hetki ennen valoa", "x"),)))
        self.assertEqual(len(shows), 2)
        self.assertEqual({s["url"] for s in shows}, {PR + "/"})

    def test_sold_out_comes_from_the_free_seats_and_no_count_is_published(self):
        shows, _ = self.parse(PIISPANRISTI, PR_PAGE)
        by_title = {s["title"]: s for s in shows}
        self.assertTrue(by_title["Kojootti vs. ACME SUOMEKSI"]["soldOut"])
        self.assertFalse(by_title["Hetki ennen valoa"]["soldOut"])
        self.assertNotIn("40", json.dumps(shows))
        self.assertNotIn("free", json.dumps(shows))

    def test_the_price_keeps_a_cent_and_drops_a_trailing_zero(self):
        shows, _ = self.parse(PIISPANRISTI, PR_PAGE)
        self.assertEqual({s["price"] for s in shows}, {"12€", "15€", "16.5€"})

    def test_an_amount_with_no_decimals_keeps_its_zero(self):
        self.assertEqual(ch._price("10 €"), "10€")
        self.assertEqual(ch._price("Vapaa pääsy"), "Vapaa pääsy")
        self.assertEqual(ch._price(""), "")

    def test_the_strand_prefix_leaves_one_film_id_behind(self):
        """run.py takes ENNAKKONÄYTÖS off the title after the adapter, so an id taken
        from the published title would leave the preview and the plain run as two
        cards with one name."""
        shows, _ = self.parse(PIISPANRISTI, PR_PAGE)
        dyyni = [s for s in shows if "Dyyni" in s["title"]][0]
        self.assertEqual(dyyni["eventId"], "dyyni osa kolme")
        self.assertEqual(dyyni["title"], "ENNAKKONÄYTÖS: Dyyni: Osa kolme")

    def test_a_trailing_language_marker_becomes_the_audio_tag(self):
        shows, _ = self.parse(PIISPANRISTI, PR_PAGE)
        by_title = {s["title"]: s for s in shows}
        self.assertEqual(by_title["Kojootti vs. ACME SUOMEKSI"]["lang"], "FI-A")
        self.assertEqual(by_title["Hetki ennen valoa"]["lang"], "")
        self.assertEqual(ch._audio("Kojootti vs. ACME ENGLANNIKSI"), "EN-A")
        self.assertEqual(ch._audio("Suomeksi puhuttu elokuva"), "")

    def test_the_age_badge_is_whitelisted(self):
        self.assertEqual(ch._rating("12"), "K-12")
        self.assertEqual(ch._rating("7"), "K-7")
        self.assertEqual(ch._rating("S"), "S")
        self.assertEqual(ch._rating("K-16"), "K-16")
        self.assertEqual(ch._rating("Tulossa"), "")
        self.assertEqual(ch._rating(""), "")

    def test_a_film_with_no_tile_keeps_its_screening_without_metadata(self):
        rows = (row(PR, "Tuntematon", "15.9. 13:00", sid="1"),
                row(PR, "Tuntematon", "15.9. 16:00", sid="2"))
        shows, _ = self.parse(PIISPANRISTI, page(days=("2026-09-15",), rows=rows))
        self.assertEqual(len(shows), 2)
        self.assertEqual((shows[0]["rating"], shows[0]["len"], shows[0]["img"],
                          shows[0]["movieUrl"]), ("", "", "", ""))
        self.assertEqual(shows[0]["eventId"], "tuntematon")

    def test_laitila_publishes_one_room_and_two_dates(self):
        shows, _ = self.parse(LAITILA, LA_PAGE)
        self.assertEqual([s["aud"] for s in shows], ["Sali 1", "Sali 1"])
        self.assertEqual(sorted({s["start"][:10] for s in shows}),
                         ["2026-09-24", "2026-10-08"])
        self.assertEqual({s["rating"] for s in shows}, {"K-12", "S"})
        self.assertEqual({s["venue"] for s in shows}, {"laitilankino-laitila"})


class YearTest(unittest.TestCase):
    """The rows carry no year and the programme runs months out."""

    def test_a_january_row_read_in_december_belongs_to_the_next_year(self):
        rows = (row(LA, "Joulu", "20.12. 13:00", sid="1"),
                row(LA, "Tammikuu", "15.1. 13:00", sid="2"))
        with contextlib.redirect_stdout(io.StringIO()):
            shows = ch.parse(page(days=("2026-12-20",), rows=rows), LAITILA,
                             today=datetime.date(2026, 12, 20))
        self.assertEqual(sorted(s["start"][:10] for s in shows),
                         ["2026-12-20", "2027-01-15"])

    def test_a_december_row_read_in_january_belongs_to_the_previous_year(self):
        self.assertEqual(ch._iso(20, 12, 13, 0, today=datetime.date(2027, 1, 10))[:10],
                         "2026-12-20")

    def test_the_current_year_is_never_assumed(self):
        """Taken blindly, 15.1. read on 2026-12-20 would publish a screening eleven
        months in the past."""
        self.assertEqual(ch._iso(15, 1, 13, 0, today=datetime.date(2026, 12, 20))[:10],
                         "2027-01-15")
        self.assertEqual(ch._iso(31, 2, 13, 0, today=TODAY), "")

    def test_a_stale_row_is_skipped_and_the_current_one_keeps_its_date(self):
        """Before 2026-09-19 a private loop took the first candidate year inside a
        -45..+320 window and tried the current year first, so `1.8.` read on 2026-09-19
        published as 2027-08-01. Two rows, because the skip is a `continue` in the loop."""
        rows = (row(PR, "Hetki ennen valoa", "15.9. 13:00", sid="1"),
                row(PR, "Vanha", "1.8. 18:00", sid="2"))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            shows = ch.parse(page(days=("2026-09-15",),
                                  tiles=[tile(PR, "Hetki ennen valoa", "hetki-ennen-valoa")],
                                  rows=rows), PIISPANRISTI, today=TODAY)
        self.assertEqual([s["start"][:10] for s in shows], ["2026-09-15"])
        self.assertIn("1 screening row(s)", out.getvalue())
        self.assertIn("inside the window", out.getvalue())

    def test_the_window_is_measured_from_what_the_three_sites_publish(self):
        """They reached +89 days on 2026-09-19, Laitila publishing to mid-December."""
        self.assertEqual(ch.WINDOW, (30, 180))
        for days, published in ((120, True), (200, False)):
            with self.subTest(days=days):
                d = TODAY + datetime.timedelta(days=days)
                got = ch._iso(d.day, d.month, 18, 0, TODAY)
                self.assertEqual(got[:10], d.isoformat() if published else "")

    def test_winter_time_is_the_zone_and_not_a_fixed_offset(self):
        """Laitilan Kino's own JSON-LD stamps a 13:00 Helsinki screening +00:00; the
        rendered clock is what a visitor reads and what is parsed."""
        self.assertEqual(ch._iso(17, 12, 13, 0, today=TODAY),
                         "2026-12-17T13:00:00+02:00")
        self.assertEqual(ch._iso(24, 9, 13, 0, today=TODAY),
                         "2026-09-24T13:00:00+03:00")


class ServedTest(unittest.TestCase):
    """`common.served`: the two facts a guard can state without keeping a raw page."""

    def setUp(self):
        # served() appends the headers of this thread's last fetch; an earlier test's
        # local server leaves "Server: BaseHTTP/..." behind otherwise.
        common._seen.headers = {}
        self.addCleanup(lambda: setattr(common._seen, "headers", {}))

    def test_it_separates_a_programme_from_a_challenge(self):
        real = '<html><head><title>Kino Piispanristi</title></head>' + "x" * 170000
        block = '<html><head><title>Just a moment...</title></head>' + "y" * 1100
        self.assertEqual(common.served(real),
                         '170051 B served, titled "Kino Piispanristi"')
        self.assertEqual(common.served(block), '1150 B served, titled "Just a moment..."')

    def test_a_page_with_no_title_still_reports_its_size(self):
        self.assertEqual(common.served("<html><body>x</body></html>"),
                         "27 B served, no <title>")
        self.assertEqual(common.served(""), "0 B served, no <title>")

    def test_a_third_party_title_is_unescaped_collapsed_and_cut(self):
        """It goes into a committed log in a public repo, so it is one line and bounded.
        Never the body: this repo keeps no raw probe dump."""
        page = "<title>\n  Kino &amp; Kahvi   \n  Oy\n</title>"
        self.assertEqual(common.served(page), '43 B served, titled "Kino & Kahvi Oy"')
        self.assertEqual(common.served("<title>" + "a" * 200 + "</title>", limit=12),
                         "215 B served, titled \"" + "a" * 12 + '"')


class EmptyProgrammeTest(unittest.TestCase):
    def test_no_day_and_no_film_is_a_confirmed_empty_programme(self):
        with self.assertRaises(common.EmptyProgramme):
            ch.parse(EMPTY_PAGE, LAITILA)

    def test_a_page_that_still_lists_a_film_fails(self):
        with self.assertRaisesRegex(RuntimeError, "no screening row parsed"):
            ch.parse(FILMS_BUT_NO_ROWS, PIISPANRISTI)

    def test_a_page_that_still_offers_a_day_fails(self):
        with self.assertRaisesRegex(RuntimeError, "no screening row parsed"):
            ch.parse(DAY_BUT_NO_ROWS, PIISPANRISTI)

    def test_a_missing_filter_is_a_failure_not_an_empty_cinema(self):
        """It is a failure whatever caused it, and the message does not pick one: on
        2026-09-16 every guard of this shape said "the template changed" while the sites
        were serving their real pages to an ordinary connection."""
        with self.assertRaises(RuntimeError) as cm:
            ch.parse(NO_FILTER, PIISPANRISTI)
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)
        self.assertIn("cr-movies-filter-select", str(cm.exception))
        self.assertNotIn("the template changed", str(cm.exception))

    def test_every_failure_says_what_was_served(self):
        """The evidence that separates a changed template from a page this reader was
        handed instead: how much came back and what the document calls itself."""
        for page in (NO_FILTER, FILMS_BUT_NO_ROWS, DAY_BUT_NO_ROWS):
            with self.subTest(page=page[:40]):
                with self.assertRaises(RuntimeError) as cm:
                    ch.parse(page, PIISPANRISTI)
                self.assertRegex(str(cm.exception), r"\d+ B served")

    def test_rows_that_all_fail_to_parse_fail_the_site(self):
        """Rows found and none readable is the same class of fault as a missing row
        pattern, and must not publish an empty programme."""
        rows = (row(PR, "A", "ei aikaa", sid="1"), row(PR, "B", "ei aikaa", sid="2"))
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "none parsed"):
                ch.parse(page(days=("2026-09-15",), rows=rows), PIISPANRISTI)


class FilmPageTest(unittest.TestCase):
    def test_the_synopsis_comes_out_of_the_prose_block(self):
        self.assertEqual(ch.parse_film(FILM), SYNOPSIS)

    def test_a_note_quoting_a_price_is_dropped_at_the_paragraph_boundary(self):
        self.assertEqual(ch.parse_film(PRICED_NOTE, LAITILA["notes"]), SYNOPSIS)

    def test_a_note_that_only_names_the_cinema_is_dropped_too(self):
        """The site's own stems are the only thing that can drop this one: it quotes no
        amount, so synmerge's price rule never sees it."""
        self.assertEqual(ch.parse_film(NAMED_NOTE, LAITILA["notes"]), SYNOPSIS)
        self.assertIn("kahvitarjoilu", ch.parse_film(NAMED_NOTE))

    def test_a_page_with_no_prose_block_yields_nothing(self):
        self.assertEqual(ch.parse_film("<html><body>x</body></html>"), "")

    def test_a_very_short_text_is_not_a_synopsis(self):
        self.assertEqual(ch.parse_film(film_page(["Tulossa pian."])), "")


class EnrichTest(unittest.TestCase):
    def setUp(self):
        self._sleep = ch.time.sleep
        ch.time.sleep = lambda s: None
        self.addCleanup(lambda: setattr(ch.time, "sleep", self._sleep))

    def shows(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return ch.parse(PR_PAGE, PIISPANRISTI, today=TODAY)

    def test_one_page_per_film_folded_onto_every_screening_of_it(self):
        shows = self.shows()
        shows.append(dict(shows[0], start="2026-09-15T20:00:00+03:00"))
        calls = []

        def get(url):
            calls.append(url)
            return FILM
        with contextlib.redirect_stdout(io.StringIO()) as out:
            ch.enrich(shows, PIISPANRISTI, get=get, sleep=0)
        self.assertEqual(len(calls), 3)                 # three films, four screenings
        self.assertEqual(len(set(calls)), 3)
        self.assertEqual([s["_syn"] for s in shows], [SYNOPSIS] * 4)
        self.assertIn("3 with a synopsis", out.getvalue())

    def test_the_site_passes_its_own_stems_to_the_note_rule(self):
        """The loop has to hand the site's `notes` on, or a paragraph naming the cinema
        reaches the slot every chain showing that film reads from."""
        shows = self.shows()
        with contextlib.redirect_stdout(io.StringIO()):
            ch.enrich(shows, LAITILA, get=lambda u: NAMED_NOTE, sleep=0)
        self.assertEqual({s["_syn"] for s in shows}, {SYNOPSIS})

    def test_a_failing_page_costs_that_film_its_synopsis_only(self):
        shows = self.shows()

        def get(url):
            if "hetki" in url:
                raise RuntimeError("HTTP Error 500")
            return FILM
        with contextlib.redirect_stdout(io.StringIO()) as out:
            ch.enrich(shows, PIISPANRISTI, get=get, sleep=0)
        by_title = {s["title"]: s for s in shows}
        self.assertNotIn("_syn", by_title["Hetki ennen valoa"])
        self.assertEqual(by_title["Kojootti vs. ACME SUOMEKSI"]["_syn"], SYNOPSIS)
        self.assertIn("failed", out.getvalue())
        self.assertEqual(by_title["Hetki ennen valoa"]["rating"], "K-7")

    def test_the_loop_is_capped_and_the_schedule_survives_the_cap(self):
        """An enrichment loop, so the cap trims it rather than raising: the schedule is
        already parsed and a film past the cap loses its synopsis for one run and
        nothing else. Checked by tripping the cap, not by reading it."""
        budget = common.PAGE_BUDGET
        common.PAGE_BUDGET = 1
        self.addCleanup(lambda: setattr(common, "PAGE_BUDGET", budget))
        shows, calls = self.shows(), []
        with contextlib.redirect_stdout(io.StringIO()) as out:
            ch.enrich(shows, PIISPANRISTI, get=lambda u: calls.append(u) or FILM, sleep=0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(sum(1 for s in shows if s.get("_syn")), 1)
        self.assertEqual(len(shows), 3)                  # every screening still published
        self.assertIn("page budget", out.getvalue())


class TicketUrlTest(unittest.TestCase):
    def test_a_relative_href_is_resolved_against_the_site(self):
        self.assertEqual(ch._ticket(PR, "/varaa/?screening_id=7"),
                         f"{PR}/varaa/?screening_id=7")

    def test_an_absolute_href_is_left_alone(self):
        self.assertEqual(ch._ticket(PR, "https://example.org/x"), "https://example.org/x")

    def test_a_scheme_that_is_not_http_falls_back_to_the_programme_page(self):
        self.assertEqual(ch._ticket(PR, "javascript:alert(1)"), PR + "/")
        self.assertEqual(ch._ticket(PR, ""), PR + "/")


# ---------------------------------------------------------------- the runner

class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._fetch, self._sleep = ch.fetch, ch.time.sleep
        self.addCleanup(lambda: setattr(ch, "fetch", self._fetch))
        self.addCleanup(lambda: setattr(ch.time, "sleep", self._sleep))
        ch.time.sleep = lambda s: None
        self.calls = []

    def serve(self, pages):
        def fetch(url, **kw):
            self.calls.append(url)
            body = pages.get(url)
            if isinstance(body, Exception):
                raise body
            if body is None:
                raise RuntimeError(f"unexpected fetch {url}")
            return body.encode("utf-8")
        ch.fetch = fetch

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["cinemahouse"])
        return code, out.getvalue() + err.getvalue()

    def all_pages(self, **over):
        pages = {PR + "/": PR_PAGE, LU + "/": LU_PAGE, LA + "/": LA_PAGE}
        for base, src in ((PR, PR_PAGE), (LU, LU_PAGE), (LA, LA_PAGE)):
            for slug in ("hetki-ennen-valoa", "kojootti-vs-acme-suomeksi",
                         "ennakkonaytos-dyyni-osa-kolme", "spider-man-brand-new-day",
                         "presidentin-kyyditys-kahvi-ja-kino", "pirjo-i-sverige-kahvi-ja-kino"):
                pages[f"{base}/elokuvat/{slug}/"] = FILM
        pages.update(over)
        return pages

    def test_a_full_run_publishes_all_three_venues(self):
        self.serve(self.all_pages())
        code, log = self.main()
        self.assertEqual(code, 0, log)
        counts = {}
        for vid in ("piispanristi-kaarina", "lumo-salo", "laitilankino-laitila"):
            doc = json.loads((run.OUT / f"area-{vid}.json").read_text())
            counts[vid] = len(doc["shows"])
            self.assertNotIn("_syn", doc["shows"][0])
            self.assertNotIn("movieUrl", doc["shows"][0])
        self.assertEqual(counts, {"piispanristi-kaarina": 3, "lumo-salo": 2,
                                  "laitilankino-laitila": 2})
        venues = json.loads((run.OUT / "venues-kinolumo.json").read_text())
        self.assertEqual(venues["venues"], [{"id": "lumo-salo", "name": "Kino Lumo",
                                             "short": "Kino Lumo", "city": "Salo"}])
        self.assertEqual((venues["status"], venues["stale"], venues["pending"]),
                         ("ok", [], []))
        extra = json.loads((run.OUT / "films-extra.json").read_text())
        self.assertIn(SYNOPSIS, json.dumps(extra, ensure_ascii=False))
        self.assertIn("3 venues, 7 showtimes", log)
        self.assertIn("0 failures", log)

    def test_the_strand_prefix_comes_off_the_title_in_the_run(self):
        self.serve(self.all_pages())
        self.assertEqual(self.main()[0], 0)
        shows = json.loads((run.OUT / "area-piispanristi-kaarina.json").read_text())["shows"]
        dyyni = [s for s in shows if s["eventId"] == "dyyni osa kolme"][0]
        self.assertEqual(dyyni["title"], "Dyyni: Osa kolme")
        self.assertIn("ENNAKKONÄYTÖS", dyyni["method"])

    def test_an_empty_programme_clears_the_previous_file_and_stays_green(self):
        prev = {"generated": "2026-09-01T00:00:00+00:00", "dates": ["2026-09-01"],
                "horizon": "2026-09-01",
                "shows": [{"title": "Old", "start": "2026-09-01T12:00:00+03:00"}]}
        (run.OUT / "area-laitilankino-laitila.json").write_text(json.dumps(prev))
        self.serve(self.all_pages(**{LA + "/": EMPTY_PAGE}))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        area = json.loads((run.OUT / "area-laitilankino-laitila.json").read_text())
        self.assertEqual(area["shows"], [])
        self.assertNotEqual(area["generated"], prev["generated"])
        self.assertIn("no programme published", log)
        self.assertIn("1 with no programme", log)
        doc = json.loads((run.OUT / "venues-laitilankino.json").read_text())
        self.assertEqual((doc["status"], doc["pending"]), ("ok", ["laitilankino-laitila"]))

    def test_a_page_that_still_lists_films_fails_its_site_and_keeps_the_previous_file(self):
        prev = {"generated": "2026-09-01T00:00:00+00:00", "dates": ["2026-09-01"],
                "horizon": "2026-09-01",
                "shows": [{"title": "Old", "start": "2026-09-01T12:00:00+03:00"}]}
        (run.OUT / "area-piispanristi-kaarina.json").write_text(json.dumps(prev))
        self.serve(self.all_pages(**{PR + "/": FILMS_BUT_NO_ROWS}))
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", log)
        self.assertEqual(json.loads((run.OUT / "area-piispanristi-kaarina.json").read_text()),
                         prev)
        self.assertFalse((run.OUT / "venues-kinopiispanristi.json").exists())
        # The other two sites still publish: one refusal is not the run.
        self.assertTrue((run.OUT / "area-lumo-salo.json").exists())

    def test_a_refused_front_page_fails_that_site_only(self):
        self.serve(self.all_pages(**{LU + "/": RuntimeError("HTTP Error 403: Forbidden")}))
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", log)
        self.assertFalse((run.OUT / "area-lumo-salo.json").exists())
        self.assertTrue((run.OUT / "area-piispanristi-kaarina.json").exists())

    def test_the_front_page_is_read_once_per_site(self):
        self.serve(self.all_pages())
        self.main()
        fronts = [c for c in self.calls if c.endswith("/") and "/elokuvat/" not in c]
        self.assertEqual(sorted(fronts), sorted([PR + "/", LU + "/", LA + "/"]))


class RegistryTest(unittest.TestCase):
    def test_the_three_registry_entries(self):
        for pid, label, host, accent, venue, city in (
                ("kinopiispanristi", "Kino Piispanristi", "kinopiispanristi.fi",
                 "#0096EA", "piispanristi-kaarina", "Kaarina"),
                ("kinolumo", "Kino Lumo", "kinolumo.fi", "#F64EAE", "lumo-salo", "Salo"),
                ("laitilankino", "Laitilan Kino", "laitilankino.fi", "#3C7872",
                 "laitilankino-laitila", "Laitila")):
            with self.subTest(provider=pid):
                p = registry.by_id(pid)
                self.assertEqual((p["label"], p["host"], p["accent"], p["book"],
                                  p["module"], p["where"]),
                                 (label, host, accent, "reserve", "cinemahouse", "cloud"))
                self.assertEqual(sum(1 for q in registry.PROVIDERS
                                     if q["accent"] == p["accent"]), 1)
                site = next(s for s in ch.SITES if s["provider"] == pid)
                v = site["venues"][0]
                self.assertEqual((v["id"], v["name"], v["short"], v["city"]),
                                 (venue, label, label, city))

    def test_every_site_names_the_host_it_reads(self):
        """`base` is run.py's pacing key, so a site without one shares a group with every
        other base-less site instead of being read on its own host."""
        self.assertEqual([s["base"] for s in ch.SITES],
                         ["https://www.kinopiispanristi.fi", "https://www.kinolumo.fi",
                          "https://www.laitilankino.fi"])
        self.assertEqual(len({run.host_of(s) for s in ch.SITES}), 3)
        self.assertEqual(len(run.host_groups(ch.SITES)), 3)

    def test_the_booking_mode_is_reserve(self):
        """/varaa/?screening_id=N asks for a name, an email and a phone number and ends
        in "Vahvista varaus"; nothing on it takes payment."""
        for pid in ("kinopiispanristi", "kinolumo", "laitilankino"):
            self.assertEqual(registry.by_id(pid)["book"], "reserve")


if __name__ == "__main__":
    unittest.main()
