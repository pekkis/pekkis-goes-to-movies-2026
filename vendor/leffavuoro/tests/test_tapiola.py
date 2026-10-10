"""Kino Tapiola: the server-rendered listing, film runs as slugs, the film page.

The fixtures follow kinotapiola.fi's own markup as read on 2026-09-05: one
`div.movie-list-movie` per screening with the date written out with its year, a strand
as a `cat-` class plus a `special-tag`, and a film page whose age limit is a class name.
The three Autofiktio runs are the case this file exists to pin: three slugs, three pages
that were checked field by field and differ only in Johku show ids, one film.
"""
import contextlib
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import _no_sleep as no_sleep
import build_pages as bp
import common
import registry
import run
import tapiola

ROOT = _ctx.ROOT
BASE = "https://www.kinotapiola.fi"


def row(slug, title, date, cls="all-dates date5-9 all-cats", tag=""):
    tag_html = f'<div class="special-tags"><div class="special-tag">{tag}</div></div>' if tag else ""
    date_html = f'<div class="date">{date}</div>' if date else ""
    return f"""
                      <div class="movie-list-movie {cls}">
          <a href="{BASE}/naytos/{slug}/">
          <div class="image" style="background-image:url('/app/uploads/2026/05/still-1440x810.jpg')">
                        {tag_html}
                        <div class="title">{title}</div>
          </div>
                      {date_html}
                    </a>
        </div>"""


ROWS = "".join([
    row("autofiktio-4", "Autofiktio", "lauantai 5.9.2026 – Klo 15:30"),
    row("autofiktio-5", "Autofiktio", "sunnuntai 6.9.2026 – Klo 16:45", cls="all-dates date6-9 all-cats"),
    row("autofiktio-6", "Autofiktio", "keskiviikko 9.9.2026 – Klo 19:30", cls="all-dates date9-9 all-cats"),
    # A title that ends in a number: the key must keep it.
    row("fez-summer-55", "Fez Summer 55", "lauantai 5.9.2026 – Klo 18:00"),
    row("calle-malaga-muistojeni-katu-11", "Calle Málaga – muistojeni katu",
        "keskiviikko 9.9.2026 – Klo 15:00", cls="all-dates date9-9 all-cats cat-seniorikino",
        tag="Seniorikino"),
    # An entity in the title, and the same screening listed twice.
    row("oasis-dont-look-back-in-anger", "Oasis: Don&#8217;t Look Back in Anger",
        "perjantai 11.9.2026 – Klo 19:30"),
    row("oasis-dont-look-back-in-anger", "Oasis: Don&#8217;t Look Back in Anger",
        "perjantai 11.9.2026 – Klo 19:30"),
    # The "tulossa" shape: a date class and no time. Not a screening.
    row("dyyni-osa-kolme", "Dyyni: osa kolme", "", cls="all-dates date16-12 all-cats"),
    # A date that does not exist.
    row("broken", "Broken", "tiistai 31.2.2026 – Klo 12:00"),
])


def listing(rows):
    return f"""<!doctype html><html><body><main class="main">
 <div class="block block-movie-list">
  <div class="filters"><div class="filter-no-results">Ei näytöksiä valituilla suodatinkriteereillä</div></div>
    <div class="movie-list">{rows}
    </div>
 </div></main></body></html>"""


LISTING = listing(ROWS)
EMPTY = listing("")
# The same rows with the date line written another way: every film is still listed and
# the parser reads no screening out of any of them.
UNDATED = listing(ROWS.replace(" – Klo ", " klo "))
# The same rows under a renamed row class: the container is there and ROW_RE finds nothing.
RENAMED = listing(ROWS.replace('class="movie-list-movie ', 'class="movie-card '))
NO_CONTAINER = "<!doctype html><html><body><main class=\"main\"><p>Huolto</p></main></body></html>"


def film_page(age_cls, desc, kesto, kieli, tekstitys):
    age = (f'<div class="info-icon {age_cls}"><div class="info-icon-inner"><div class="icon"></div>'
           f'<div class="text">Ikäraja<br>{age_cls.split("age-limit-")[1]}</div></div></div>') if age_cls else ""
    return f"""<!doctype html><html><head><title>X - Kino Tapiola</title></head><body><main class="main">
<div class="block block-single-elokuva-content">
  <div class="left">
    <div class="description">{desc}
</div>
    <div class="info-icons">
                    {age}
                    <div class="info-icon centered disturbing">
          <div class="info-icon-inner">
            <div class="icon"></div>
          </div>
        </div>
                          <div class="info-icon duration">
          <div class="info-icon-inner">
            <div class="icon"></div>
            <div class="text">Elokuvan kesto</br>{kesto}</div>
          </div>
        </div>
                    <div class="info-icon language">
          <div class="info-icon-inner">
            <div class="icon"></div>
            <div class="text">Kieli</br>{kieli}</div>
          </div>
        </div>
                    <div class="info-icon subtitles">
          <div class="info-icon-inner">
            <div class="icon"></div>
            <div class="text">Tekstitys</br>{tekstitys}</div>
          </div>
        </div>
                    <div class="info-icon yksityisnaytos">
                      <a href="{BASE}/yksityistilaisuus/yksityisnaytos/" target="_blank">
                    <div class="info-icon-inner">
            <div class="icon"></div>
            <div class="text">Järjestä yksityisnäytös</div>
          </div>
                      </a>
                  </div>
                </div>
    <div class="movie-info"><div class="movie-info-left"><img src="/app/uploads/2026/05/x-214x300.png" /></div></div>
  </div>
  <div class="right"><div class="ticket-box" data-showid="7818"><h2>Osta liput</h2></div></div>
</div></main></body></html>"""


AUTOFIKTIO = film_page(
    "age-limit-K-12",
    "<p><em>&#8221;leikittelee itsetietoisesti tarinatasoilla&#8221;</em> ★★★★ / HS</p>\n"
    "<p>Espanjalaisen ohjaajalegendan Pedro Almodóvarin melodraama <em>Autofiktio</em> (Amarga Navidad) "
    "kertoo luomiskriisissä kamppailevasta elokuvantekijästä, joka ammentaa läheistensä tragedioista "
    "materiaalia teokseensa.</p>",
    "1h 52min", "OV", "Suomi/Ruotsi")
ODYSSEY = film_page(
    "",
    "<p>Christopher Nolanin seuraava elokuva, <em>The Odyssey</em>, on myyttinen toimintaeepos, joka on "
    "kuvattu eri puolilla maailmaa käyttäen uutta IMAX®-filmiteknologiaa.</p>",
    "2h 53min", "Englanti", "Suomi/Ruotsi")

SITE = tapiola.SITES[0]
VENUE = SITE["venues"][0]


class ListingTest(unittest.TestCase):
    def setUp(self):
        self.shows = tapiola.parse(LISTING)
        self.by_slug = {s["url"].rstrip("/").rsplit("/", 1)[1]: s for s in self.shows}

    def test_rows_with_a_time_become_showtimes(self):
        self.assertEqual(len(self.shows), 6)
        self.assertEqual([s["start"] for s in self.shows],
                         ["2026-09-05T15:30:00+03:00", "2026-09-05T18:00:00+03:00",
                          "2026-09-06T16:45:00+03:00", "2026-09-09T15:00:00+03:00",
                          "2026-09-09T19:30:00+03:00", "2026-09-11T19:30:00+03:00"])

    def test_three_runs_of_one_film_share_the_key_and_keep_their_own_pages(self):
        runs = [s for s in self.shows if s["title"] == "Autofiktio"]
        self.assertEqual(len(runs), 3)
        self.assertEqual({s["eventId"] for s in runs}, {"autofiktio"})
        self.assertEqual([s["url"] for s in runs],
                         [f"{BASE}/naytos/autofiktio-4/", f"{BASE}/naytos/autofiktio-5/",
                          f"{BASE}/naytos/autofiktio-6/"])

    def test_a_title_ending_in_a_number_keeps_it(self):
        self.assertEqual(self.by_slug["fez-summer-55"]["eventId"], "fez summer 55")

    def test_the_strand_class_lands_in_method_and_not_in_the_title(self):
        s = self.by_slug["calle-malaga-muistojeni-katu-11"]
        self.assertEqual((s["title"], s["method"]), ("Calle Málaga – muistojeni katu", "Seniorikino"))
        self.assertEqual(self.by_slug["autofiktio-4"]["method"], "")

    def test_entities_are_unescaped_and_a_repeated_row_is_dropped(self):
        s = self.by_slug["oasis-dont-look-back-in-anger"]
        self.assertEqual(s["title"], "Oasis: Don’t Look Back in Anger")
        self.assertEqual(sum(1 for x in self.shows if x["eventId"] == s["eventId"]), 1)

    def test_a_row_without_a_time_and_an_impossible_date_are_skipped(self):
        self.assertNotIn("dyyni-osa-kolme", self.by_slug)
        self.assertNotIn("broken", self.by_slug)

    def test_the_show_shape(self):
        s = self.by_slug["autofiktio-4"]
        self.assertEqual((s["img"], s["price"], s["aud"], s["rating"], s["len"], s["lang"],
                          s["soldOut"], s["provider"], s["venue"], s["theatre"]),
                         ("", "", "", "", "", "", False, "tapiola", "tapiola-espoo", "Kino Tapiola"))

    def test_no_screening_on_the_page_is_a_break(self):
        """No empty state of this site has been seen, so zero rows is never read as an
        empty programme. The `filter-no-results` phrase is no evidence either: the
        populated listing carries it too, for the client-side filter."""
        self.assertIn("filter-no-results", LISTING)
        for name, page in (("empty list", EMPTY), ("no container", NO_CONTAINER),
                           ("undated", UNDATED), ("renamed", RENAMED)):
            with self.subTest(name):
                with self.assertRaises(RuntimeError) as ctx:
                    tapiola.parse(page)
                self.assertNotIsInstance(ctx.exception, common.EmptyProgramme)


class DetailsTest(unittest.TestCase):
    def test_the_film_page(self):
        d = tapiola.details(AUTOFIKTIO)
        self.assertEqual((d["rating"], d["len"], d["lang"]), ("K-12", "112", "FI-S, SV-S"))
        self.assertTrue(d["_syn"].startswith("Espanjalaisen ohjaajalegendan Pedro Almodóvarin melodraama Autofiktio (Amarga"))
        self.assertNotIn("★", d["_syn"])
        self.assertNotIn("leikittelee", d["_syn"])

    def test_a_spoken_language_and_no_age_limit(self):
        d = tapiola.details(ODYSSEY)
        self.assertNotIn("rating", d)
        self.assertEqual((d["len"], d["lang"]), ("173", "EN-A, FI-S, SV-S"))
        self.assertIn("elokuva, The Odyssey, on myyttinen", d["_syn"])

    def test_an_opera_states_its_language_in_the_description(self):
        """Carmen and Tosca, read 2026-10-04: no language box, a line in the description.
        A ballet's page states none."""
        carmen = film_page("", "<p>The Royal Opera: Carmen<br />\nKesto: \xa03h 35min / 215min, "
                               "yksi väliaika<br />\nKieli: ranska, tekstitetty englanniksi</p>",
                           "", "", "")
        tosca = film_page("", "<p>The Royal Opera: Tosca<br />Kesto: &nbsp;3h 15min / 195min, "
                              "kaksi väliaikaa<br />Kieli: italia, tekstitetty englanniksi</p>",
                          "", "", "")
        ballet = film_page("", "<p>The Royal Ballet: Joutsenlampi<br />Kesto: 3h</p>", "", "", "")
        self.assertEqual([tapiola.details(p).get("lang") for p in (carmen, tosca, ballet)],
                         ["FR-A, EN-S", "IT-A, EN-S", None])

    def test_the_boxes_win_over_a_description_line(self):
        page = film_page("", "<p>Kieli: ranska, tekstitetty englanniksi</p>", "", "Englanti",
                         "Suomi")
        self.assertEqual(tapiola.details(page)["lang"], "EN-A, FI-S")

    def test_the_venue_notice_is_not_the_synopsis(self):
        """Every opera and ballet page opens with the cinema's own evening notice, which
        films-extra.json then served as the Finnish synopsis of six Royal Opera and
        Ballet titles to every chain showing them (2026-09-25)."""
        page = film_page(
            "",
            "<p>Kino Tapiolassa ooppera- ja baletti-iltoihin kuuluu laadukkaan ohjelmiston "
            "lisäksi myös oikea oopperatunnelma: Takit jätetään narikkaan!</p>\n"
            "<p>Viinibaarimme palvelee ennen näytöstä sekä väliajalla, ja myös alkoholijuomat "
            "saa ottaa mukaan saliin kaikissa näytöksissämme.</p>\n"
            "<p>Liput 29 € sisältävät väliaikatarjoilun.</p>\n"
            "<p>Floria Tosca ja Mario Cavaradossi elävät toisilleen ja taiteelleen, kunnes "
            "Cavaradossi auttaa karannutta vankia.</p>",
            "3h 15min", "Italia", "Englanti")
        d = tapiola.details(page)
        self.assertTrue(d["_syn"].startswith("Floria Tosca ja Mario Cavaradossi"), d["_syn"])
        self.assertNotIn("Viinibaarimme", d["_syn"])
        self.assertNotIn("29 €", d["_syn"])

    def test_nothing_on_the_page_is_nothing(self):
        self.assertEqual(tapiola.details("<html><body>Huolto</body></html>"), {})


class EnrichTest(unittest.TestCase):
    def setUp(self):
        no_sleep.patch(self, tapiola)           # the 0.5 s pause between film pages

    def test_one_page_per_film_folded_onto_every_run(self):
        shows = tapiola.parse(LISTING)
        calls = []

        def get(url):
            calls.append(url)
            return AUTOFIKTIO if "autofiktio" in url else ODYSSEY
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            tapiola.enrich(shows, get=get)
        self.assertEqual(calls.count(f"{BASE}/naytos/autofiktio-4/"), 1)
        self.assertFalse(any("autofiktio-5" in c or "autofiktio-6" in c for c in calls))
        self.assertEqual(len(calls), 4)                    # four films, six showtimes
        runs = [s for s in shows if s["title"] == "Autofiktio"]
        self.assertEqual({(s["rating"], s["len"], s["lang"]) for s in runs}, {("K-12", "112", "FI-S, SV-S")})
        # Only the Autofiktio page carries an age limit, so three of six are rated.
        self.assertIn("4 parsed, 0 with nothing usable, 3/6 showtimes rated", out.getvalue())

    def test_a_failing_page_costs_that_film_its_metadata_only(self):
        shows = tapiola.parse(LISTING)

        def get(url):
            if "autofiktio" in url:
                raise RuntimeError("HTTP Error 500")
            return ODYSSEY
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            tapiola.enrich(shows, get=get)
        self.assertEqual({s["len"] for s in shows if s["title"] == "Autofiktio"}, {""})
        self.assertEqual({s["len"] for s in shows if s["title"] != "Autofiktio"}, {"173"})
        self.assertIn("film page autofiktio-4 failed", out.getvalue())


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._fetch = tapiola.fetch
        self.addCleanup(lambda: setattr(tapiola, "fetch", self._fetch))
        # Scoped to tapiola's own `time`: replacing `time.sleep` itself reached every
        # thread in the process for the length of the test.
        no_sleep.patch(self, tapiola)
        self.calls = []

    def serve(self, pages):
        def fetch(url, **kw):
            self.calls.append(url)
            page = pages.get(url)
            if isinstance(page, Exception):
                raise page
            if page is None:
                raise RuntimeError(f"unexpected fetch {url}")
            return page.encode("utf-8")
        tapiola.fetch = fetch

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["tapiola"])
        return code, out.getvalue() + err.getvalue()

    PAGES = {f"{BASE}/naytos/autofiktio-4/": AUTOFIKTIO,
             f"{BASE}/naytos/fez-summer-55/": ODYSSEY,
             f"{BASE}/naytos/calle-malaga-muistojeni-katu-11/": ODYSSEY,
             f"{BASE}/naytos/oasis-dont-look-back-in-anger/": ODYSSEY}

    def test_a_full_run_publishes_the_venue(self):
        self.serve({tapiola.LISTING: LISTING, **self.PAGES})
        code, log = self.main()
        self.assertEqual(code, 0, log)
        area = json.loads((run.OUT / "area-tapiola-espoo.json").read_text())
        venues = json.loads((run.OUT / "venues-tapiola.json").read_text())
        self.assertEqual(len(area["shows"]), 6)
        auto = [s for s in area["shows"] if s["title"] == "Autofiktio"]
        self.assertEqual({(s["eventId"], s["rating"], s["len"]) for s in auto}, {("autofiktio", "K-12", "112")})
        self.assertNotIn("_syn", area["shows"][0])
        self.assertEqual(area["dates"], ["2026-09-05", "2026-09-06", "2026-09-09", "2026-09-11"])
        self.assertEqual(venues["venues"], [{"id": "tapiola-espoo", "name": "Kino Tapiola",
                                            "short": "Kino Tapiola", "city": "Espoo"}])
        self.assertEqual((venues["status"], venues["pending"]), ("ok", []))
        self.assertEqual(self.calls[0], tapiola.LISTING)
        self.assertEqual(len(self.calls), 5)                # the listing and four film pages
        self.assertIn("Kino Tapiola: 6 showtimes, 4 dates", log)
        self.assertIn("0 failures", log)

    def test_a_listing_with_no_readable_screening_fails_and_keeps_the_previous_file(self):
        """An empty list and listed films the parser cannot read end the same way: the
        site fails and the old screenings stay, never an empty file published fresh."""
        self.assertFalse(hasattr(tapiola, "EMPTY_VENUES_CONFIRMED"))
        prev = {"generated": "2026-09-01T00:00:00+00:00", "dates": ["2026-09-01"],
                "horizon": "2026-09-01", "shows": [{"title": "Old", "start": "2026-09-01T12:00:00+03:00"}]}
        for name, page in (("empty list", EMPTY), ("undated", UNDATED)):
            with self.subTest(name):
                (run.OUT / "area-tapiola-espoo.json").write_text(json.dumps(prev))
                self.calls = []
                self.serve({tapiola.LISTING: page})
                code, log = self.main()
                self.assertEqual(code, 1, log)
                self.assertIn("FAILED", log)
                self.assertEqual(json.loads((run.OUT / "area-tapiola-espoo.json").read_text()), prev)
                self.assertFalse((run.OUT / "venues-tapiola.json").exists())
                self.assertEqual(self.calls, [tapiola.LISTING])

    def test_a_changed_template_fails_the_site_and_keeps_the_previous_file(self):
        prev = {"generated": "2026-09-01T00:00:00+00:00", "dates": ["2026-09-01"],
                "horizon": "2026-09-01", "shows": [{"title": "Old", "start": "2026-09-01T12:00:00+03:00"}]}
        (run.OUT / "area-tapiola-espoo.json").write_text(json.dumps(prev))
        self.serve({tapiola.LISTING: NO_CONTAINER})
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", log)
        self.assertEqual(json.loads((run.OUT / "area-tapiola-espoo.json").read_text()), prev)
        self.assertFalse((run.OUT / "venues-tapiola.json").exists())

    def test_a_refused_listing_fails_the_site(self):
        self.serve({tapiola.LISTING: RuntimeError("HTTP Error 403: Forbidden")})
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", log)


class RegistryAndPagesTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("tapiola")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Kino Tapiola", "kinotapiola.fi", "buy", "tapiola", "cloud"))
        self.assertEqual(p["accent"], "#003CFC")
        self.assertEqual(sum(1 for q in registry.PROVIDERS if q["accent"] == p["accent"]), 1)
        self.assertEqual((VENUE["id"], VENUE["name"], VENUE["short"], VENUE["city"]),
                         ("tapiola-espoo", "Kino Tapiola", "Kino Tapiola", "Espoo"))
        self.assertEqual(SITE["base"], BASE)
        self.assertEqual(bp.label_of({**VENUE, "provider": "tapiola"}, {"tapiola": "Kino Tapiola"}),
                         "Kino Tapiola")

    def test_the_committed_page_follows_the_theatre_template(self):
        fi = (ROOT / "teatteri" / "kino-tapiola-espoo" / "index.html").read_text(encoding="utf-8")
        en = (ROOT / "en" / "theatre" / "kino-tapiola-espoo" / "index.html").read_text(encoding="utf-8")
        sello = (ROOT / "teatteri" / "finnkino-sello-espoo" / "index.html").read_text(encoding="utf-8")
        for page in (fi, en):
            self.assertIn('href="https://www.kinotapiola.fi/naytos/', page)
        for marker in ('class="langseg"', 'class="cta"', '<h2 class="day">', '<p class="intro">',
                       'class="stub"', '<ul class="times">'):
            self.assertIn(marker, fi)
            self.assertIn(marker, sello)
        self.assertEqual(fi.count("<style"), sello.count("<style"))

    def test_the_espoo_city_page_lists_the_cinema(self):
        city = (ROOT / "kaupunki" / "espoo" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Kino Tapiola", city)
        self.assertIn("chain-tapiola", city)
        # Four from 2026-09-19, when Cinema Sheryl joined Otaniemi beside the two
        # Finnkinos and this one.
        self.assertIn("4 teatteria", city)


if __name__ == "__main__":
    unittest.main()
