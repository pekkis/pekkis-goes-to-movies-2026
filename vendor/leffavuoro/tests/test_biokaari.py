"""Bio-Kaari, Forssa: ten day containers, repeated rows, one ticket id per screening.

The fixtures follow `bio-kaari.fi` as read on 2026-09-15: a `div.searchResults` per day
whose **id is the date**, holding a `div.searchItem` per film, whose `ul.searchItemShows`
holds one `<li>` per screening with an upper-case `<P>`/`<DIV>`/`<A>` row.

Three days and two films, because the failure this page invites is publishing one day's
times on every day: the rows repeat verbatim across containers and only the container id
separates them. A one-day fixture would never show it. One film also carries two `<li>`
rows on a single day, which is the other shape the page uses.
"""
import unittest

import _ctx                                                # noqa: F401
import biokaari
import common

BASE = "https://www.bio-kaari.fi"
TICKETS = "http://bio-kaari.azurewebsites.net/websales/show"


def item(event, title, year, shows, poster=True):
    """`shows` is [(time, ticket_id), ...] -- a film can screen more than once a day."""
    img = (f'<div class="searchItemImage"><a href="tapahtuma/?event={event}">'
           f'<img decoding="async" src="https://mcswebsites.blob.core.windows.net/1018/'
           f'Event_{event}/portrait_medium/{event}.jpg"></a></div>') if poster else ""
    lis = "".join(
        f'<li><P class="searchItemEventTime">{t}</P>'
        f'<DIV class="searchItemEventLink"><A href="{TICKETS}/{tid}/">'
        f'<SPAN>Osta lippu</SPAN></A></DIV></li>' for t, tid in shows)
    yr = f"<small><span> ({year})</span></small>" if year else ""
    return (f'<div class="searchItem">{img}'
            f'<div class="searchItemData"><a href="tapahtuma/?event={event}">'
            f'<h2>{title}{yr}</h2></a>'
            f'<ul class="searchItemShows">{lis}</ul></div></div>'
            f'<!-- tapahtuma loppuu -->')


def day(ddmmyyyy, *items, hidden=False):
    style = ' style="display:none"' if hidden else ""
    return (f'<div class="searchResults" id="{ddmmyyyy}"{style}>' + "".join(items) +
            '</div><!-- paiva loppuu -->')


def page(*days):
    return ('<html><body><div class="eventSearch">'
            '<select id="dateSelection"><option value="15092026">Tänään 15.09.2026</option>'
            '</select>' + "".join(days) + '</div></body></html>')


# The same two films, at the same times, on three days: only the container id differs.
LISTING = page(
    day("15092026",
        item("31671", "Hetki ennen valoa", "2026", [("17:30", "984056")]),
        item("31668", "Presidentin kyyditys", "2026", [("19:30", "984055")])),
    day("16092026",
        item("31671", "Hetki ennen valoa", "2026", [("17:30", "984058")]),
        item("31668", "Presidentin kyyditys", "2026", [("19:30", "984057")]), hidden=True),
    day("19092026",
        # Two screenings of one film on one day.
        item("31671", "Hetki ennen valoa", "2026",
             [("15:00", "984070"), ("17:00", "984071")]), hidden=True),
)

FILM_PAGE = ("<html><body>ELOKUVA Hetki ennen valoa (2026) Lajityyppi: Draama "
             "Ik&auml;raja: K7/4 N&auml;yt&ouml;kset Ensi-ilta: 11.09.2026 "
             "Kesto: 1 h 27 min Jakelija: B-Plan Distribution</body></html>")


class ProgrammeTest(unittest.TestCase):
    def setUp(self):
        self.shows = biokaari.parse(LISTING)

    def test_each_day_container_supplies_its_own_date(self):
        """The rows repeat across days; the container id is the only thing that separates
        them. Reading rows without their container would put every time on every day."""
        self.assertEqual(sorted({s["start"][:10] for s in self.shows}),
                         ["2026-09-15", "2026-09-16", "2026-09-19"])
        by_day = {}
        for s in self.shows:
            by_day.setdefault(s["start"][:10], []).append(s["start"][11:16])
        self.assertEqual(sorted(by_day["2026-09-15"]), ["17:30", "19:30"])
        self.assertEqual(sorted(by_day["2026-09-19"]), ["15:00", "17:00"])

    def test_a_hidden_day_is_still_read(self):
        """The later days are in the markup with display:none, so they are published."""
        self.assertIn("2026-09-16", {s["start"][:10] for s in self.shows})

    def test_two_screenings_of_one_film_on_one_day_are_both_published(self):
        d19 = [s for s in self.shows if s["start"][:10] == "2026-09-19"]
        self.assertEqual(len(d19), 2)
        self.assertEqual(len({s["url"] for s in d19}), 2)

    def test_every_screening_has_its_own_ticket_id(self):
        self.assertEqual(len({s["url"] for s in self.shows}), len(self.shows))

    def test_the_ticket_link_is_read_from_the_page_and_upgraded_to_https(self):
        for s in self.shows:
            self.assertTrue(s["url"].startswith("https://bio-kaari.azurewebsites.net/"), s["url"])
        self.assertNotIn("http://", " ".join(s["url"] for s in self.shows))

    def test_the_release_year_leaves_the_title_and_becomes_its_own_field(self):
        """`title` is the TMDB and merge key, so the year is not part of the name."""
        s = self.shows[0]
        self.assertEqual(s["title"], "Hetki ennen valoa")
        self.assertEqual(s["year"], "2026")
        self.assertNotIn("2026", s["title"])

    def test_the_event_id_is_the_film_and_folds_its_runs_together(self):
        runs = {s["eventId"] for s in self.shows}
        self.assertEqual(runs, {"31671", "31668"})

    def test_the_poster_is_the_platforms_own_host(self):
        self.assertTrue(self.shows[0]["img"].startswith(
            "https://mcswebsites.blob.core.windows.net/"))

    def test_every_show_meets_the_contract(self):
        common.check_shows({biokaari.VENUE["id"]: self.shows}, "biokaari",
                           {biokaari.VENUE["id"]})


class FilmPageTest(unittest.TestCase):
    def test_the_age_limit_drops_the_flexibility_years(self):
        """The page writes `K7/4`: the 4 is how many years the limit may flex, not part
        of the classification."""
        self.assertEqual(biokaari.details(FILM_PAGE)["rating"], "K-7")
        self.assertEqual(biokaari._rating("K12/3"), "K-12")
        self.assertEqual(biokaari._rating("S"), "S")
        self.assertEqual(biokaari._rating("ei tiedossa"), "")

    def test_runtime_and_genre(self):
        d = biokaari.details(FILM_PAGE)
        self.assertEqual(d["len"], "87")
        self.assertEqual(d["genres"], "draama")

    def test_details_fold_onto_every_screening_of_the_film(self):
        shows = biokaari.parse(LISTING)
        biokaari.enrich(shows, get=lambda u: FILM_PAGE, sleep=0)
        for s in shows:
            self.assertEqual(s["rating"], "K-7")

    def test_a_film_page_that_fails_leaves_the_others_enriched(self):
        shows = biokaari.parse(LISTING)

        def get(u):
            if u.endswith("=31671"):
                raise OSError("boom")
            return FILM_PAGE

        biokaari.enrich(shows, get=get, sleep=0)
        self.assertEqual({s["rating"] for s in shows if s["eventId"] == "31671"}, {""})
        self.assertEqual({s["rating"] for s in shows if s["eventId"] == "31668"}, {"K-7"})


class EmptyAndBrokenTest(unittest.TestCase):
    def test_day_containers_with_no_screening_fail_rather_than_empty_the_venue(self):
        """No empty state is recorded for this plugin. Empty day containers are what a
        renamed film-item class would also produce, so zero rows fails."""
        with self.assertRaises(RuntimeError) as cm:
            biokaari.parse(page(day("15092026"), day("16092026")))
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_films_whose_screening_rows_the_parser_cannot_read_fail_the_site(self):
        """Two days, two films, every time in a format SHOW_RE misses: the page is full of
        films, so this is a template change and must not read as nothing on."""
        with self.assertRaises(RuntimeError) as cm:
            biokaari.parse(page(
                day("15092026",
                    item("31671", "Hetki ennen valoa", "2026", [("klo 17", "984056")]),
                    item("31668", "Presidentin kyyditys", "2026", [("klo 19", "984055")])),
                day("16092026",
                    item("31671", "Hetki ennen valoa", "2026", [("klo 17", "984058")]),
                    hidden=True)))
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)
        self.assertIn("3 film item", str(cm.exception))

    def test_a_page_without_a_day_container_is_a_failure(self):
        with self.assertRaises(RuntimeError) as cm:
            biokaari.parse("<html><body><p>Tervetuloa</p></body></html>")
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_an_impossible_date_does_not_abort_the_page(self):
        out = biokaari.parse(page(
            day("31022026", item("1", "X", "2026", [("18:00", "1")])),
            day("16092026", item("2", "Y", "2026", [("18:00", "2")]))))
        self.assertEqual([s["title"] for s in out], ["Y"])

    def test_a_film_without_a_year_still_publishes(self):
        out = biokaari.parse(page(day("16092026", item("1", "X", None, [("18:00", "1")]))))
        self.assertEqual(out[0]["title"], "X")
        self.assertNotIn("year", out[0])


class SiteTest(unittest.TestCase):
    def test_one_venue_in_forssa(self):
        self.assertEqual([v["city"] for v in biokaari.SITES[0]["venues"]], ["Forssa"])
        self.assertEqual(biokaari.SITES[0]["base"], BASE)

    def test_the_ticket_host_the_price_pass_reads_is_declared(self):
        import run
        self.assertEqual(sorted(run.hosts_of(biokaari.SITES[0])),
                         ["bio-kaari.azurewebsites.net", "www.bio-kaari.fi"])


def ticket_page(spoken="Suomi", subs=None, no_subs=False, rows=(("Normaali", "14,00 \u20ac"),)):
    """The MyCloudCinema ticket page's shape as Bio-Kaari served it on 2026-10-09, cut to
    the lines read: the two language lines and the price table."""
    info = ['<p class="showPresentationMethod"> Esitysmenetelm\u00e4: <b>2D</b> </p>']
    if spoken:
        info.append(f'<p class="spokenLanguage"> Kieli: <b>{spoken}</b> </p>')
    if subs:
        info.append(f'<p class="showSubtitles"> Tekstitys : <b>{subs}</b> </p>')
    if no_subs:
        info.append('<p class="no-subtitles"> Tekstitys : <b>No Subtitles</b> </p>')
    table = "".join(
        f'<tr><td class="col-xs-5 showPrices-table-ticketCategory"><h4 class="no-margin"> '
        f'{cat} </h4></td><td class="col-xs-3 showPrices-table-price no-wrap"><span> {amount} '
        f'</span></td></tr>' for cat, amount in rows)
    return (f'<html><body><div class="block-show-info col-md-8">{"".join(info)}</div>'
            f'<table class="table showPrices-table">{table}</table></body></html>')


class TicketPageTest(unittest.TestCase):
    """The ticket page, read since 2026-10-09 on the maintainer's decision."""

    def test_the_audio_and_subtitle_lines(self):
        self.assertEqual(biokaari.page_fields(ticket_page("Englanti", "Suomi")),
                         {"lang": "EN-A, FI-S"})
        self.assertEqual(biokaari.page_fields(ticket_page("Suomi")), {"lang": "FI-A"})

    def test_the_platforms_no_subtitles_line_is_not_read(self):
        """Riviera's page for an English film shows it with no language line at all, so
        the line tells us nothing. Not read, on the maintainer's decision of 2026-10-09."""
        self.assertEqual(biokaari.page_fields(ticket_page("Suomi", no_subs=True)),
                         {"lang": "FI-A"})
        self.assertEqual(biokaari.page_fields(ticket_page(None, no_subs=True)), {"lang": ""})

    def test_the_ordinary_row_is_the_price(self):
        self.assertEqual(biokaari.ordinary_price(ticket_page()), "14\u20ac")
        self.assertEqual(biokaari.ordinary_price(ticket_page(rows=(
            ("Lapsi", "10,00 \u20ac"), ("Normaali", "13,00 \u20ac")))), "13\u20ac")

    def test_no_ordinary_row_or_two_that_disagree_is_no_price(self):
        for rows in ((("Lapsi", "10,00 \u20ac"),),
                     (("Normaali", "13,00 \u20ac"), ("Normaali", "14,00 \u20ac"))):
            with self.subTest(rows=rows):
                self.assertEqual(biokaari.ordinary_price(ticket_page(rows=rows)), "")


class FetchSiteTest(unittest.TestCase):
    """The whole run on fixtures: front page, film pages, then one ticket page per
    screening, with nothing else requested."""

    def setUp(self):
        import tempfile, pathlib as pl
        self.tmp = pl.Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.urls = []
        # Every screening but 984057 has its page; prices.py ends a pass after three
        # failures in a row, so one gap is the case a run meets.
        tickets = {t: ticket_page("Suomi", rows=(("Normaali", "14,00 \u20ac"),))
                   for t in ("984055", "984058", "984070", "984071")}
        tickets["984056"] = ticket_page("Englanti", "Suomi",
                                        rows=(("Normaali", "13,00 \u20ac"),))

        def fake(url, headers=None, **kw):
            self.urls.append(url)
            if url == BASE + "/":
                return LISTING.encode()
            if "/tapahtuma/" in url:
                return FILM_PAGE.encode()
            tid = url.rstrip("/").rsplit("/", 1)[-1]
            if tid in tickets:
                return tickets[tid].encode()
            raise OSError("no such page")

        saved = biokaari.fetch
        biokaari.fetch = fake
        self.addCleanup(lambda: setattr(biokaari, "fetch", saved))

    def test_each_screening_takes_its_own_ticket_pages_price_and_language(self):
        shows = biokaari.fetch_site(prices_path=self.tmp / "prices.json",
                                    price_sleep=0)["biokaari-forssa"]
        got = {s["url"].rstrip("/").rsplit("/", 1)[-1]: (s["price"], s["lang"]) for s in shows}
        self.assertEqual(got["984055"], ("14\u20ac", "FI-A"))
        self.assertEqual(got["984056"], ("13\u20ac", "EN-A, FI-S"))
        # A ticket page that could not be read leaves its screening as it was.
        self.assertEqual(got["984057"], ("", ""))

    def test_nothing_past_the_ticket_page_is_requested(self):
        biokaari.fetch_site(prices_path=self.tmp / "prices.json", price_sleep=0)
        for url in self.urls:
            with self.subTest(url=url):
                self.assertTrue(url == BASE + "/" or url.startswith(BASE + "/tapahtuma/?event=")
                                or (url.startswith(biokaari.TICKETS)
                                    and url[len(biokaari.TICKETS):].strip("/").isdigit()), url)
        self.assertEqual(sum(u.startswith(biokaari.TICKETS) for u in self.urls), 6)


if __name__ == "__main__":
    unittest.main()
