"""Kino Regina: the theme's POST schedule, its two-week windows, and the film page.

Fixtures follow kinoregina.fi's own markup as read on 2026-09-05: a day header and one
`div.movie` block per screening with the start written with its year, a `grey` block with
"Myynti on päättynyt." once online sales close, the "Lataa lisää" button naming the next
window's first day, and a film page whose age limit is an image, whose Teemat cell links
the cinema's series and whose Kuvaus separates the synopsis from an essay with "***".
"""
import contextlib
import datetime
import functools
import io
import json
import pathlib
import shutil
import tempfile
import types
import unittest

import _ctx                                                # noqa: F401
import build_pages as bp
import registry
import run
import regina

ROOT = _ctx.ROOT
BASE = "https://kinoregina.fi"
SCHEDULE = regina.SCHEDULE
LISTING = regina.LISTING


def day_header(text):
    return f"""
      <div class="row">
        <div class="day-header pr col-12">
          <span class="day d-block">{text}</span>
        </div>
      </div>"""


def block(fid, title, start, state="green", info="", ticket=True, film_link=True):
    info_html = f'<div class="info">{info}</div>' if info else ""
    link = (f'<a href="{BASE}/elokuva/{fid}" class="title d-block d-md-inline-block">{title}</a>'
            if film_link else f'<a href="{BASE}/tapahtuma/{fid}" class="title d-block d-md-inline-block">{title}</a>')
    cart = (f'<a href="https://kauppa.kavi.fi/fi/events/pwdg/event_buybox/show/6a21c8{fid}" target="_blank" '
            f'class="add-to-cart cp pa" aria-label="Osta lippu: {title}" rel="noopener noreferrer">'
            f'<i class="fas fa-shopping-cart" aria-hidden="true"></i></a>') if ticket else ""
    return f"""
        <div class="row">
          <div class="movie pr col-12 {state}">
            {info_html}            <div class="row">
              <div class="content-container d-md-flex col-12">
                <div class="left-side d-md-flex">
                  <div class="img-container sixteen-nine cover d-none d-md-inline-block" style="background-image: url('{BASE}/wp-content/uploads/2021/09/still-300x163-optimized.jpg"></div>
                  <div class="movie-content d-flex d-md-block pr">
                    <span class="time d-block d-md-inline-block">{start[11:]}</span>
                    {link}<br class="d-none d-md-block"/>
                    <p class="d-none d-md-block">Lyhyt kuvaus...</p>
                  </div>
                </div>
                <div class="right-side d-block d-md-flex">
                  <div class="calendar-icon add-to-calendar cp pa addeventatc" role="button" aria-label="Lis&#228;&#228; kalenteriin">
                    <i class="far fa-calendar-alt"></i>
                    <span class="start">{start}</span>
                    <span class="timezone">Europe/Helsinki</span>
                    <span class="title">{title}</span>
                  </div>
                  {cart}
                </div>
              </div>
            </div>
          </div>
        </div>"""


def load_more(day):
    return f"""
  <div class="row">
    <div class="col-12 text-center" style="margin-top: 40px;">
      <button id="loadMoreMovies"
              onclick="loadNextTwoWeeks('{day}', this)"
              style="font-family: relative-bold, sans-serif;">
        <i class="fas fa-list" style="margin-right: 12px;"></i>Lataa lisää
      </button>
    </div>
  </div>
"""


WINDOW_1 = (
    day_header("Lauantai 5.9.")
    + block("202769", "SÁTÁNTANGÓ", "05-09-2026 14:00", state="grey", info="Myynti on päättynyt.")
    + day_header("Sunnuntai 6.9.")
    + block("1415167", "PERSEPOLIS", "06-09-2026 14:00")
    + block("105609", "PIUKAT PAIKAT", "06-09-2026 16:00")
    + block("105609", "PIUKAT PAIKAT", "06-09-2026 16:00")                  # listed twice
    + block("9001", "Keskustelutilaisuus", "06-09-2026 17:30", film_link=False)   # an event, not a film
    + block("1653971", "ONE BATTLE AFTER ANOTHER", "11-09-2026 20:30", ticket=False)
    + load_more("2026-09-21")
)
WINDOW_2 = (
    day_header("Maanantai 21.9.")
    + block("139011", "CARRIE", "21-09-2026 19:30")
    + load_more("2026-10-07")
)
WINDOW_EMPTY = load_more("2026-10-23")


def film_page(age_alt, kesto, tekstitys, teemat, kopiotieto, lisatieto, kuvaus,
              heading="X (2025)", maa="Yhdysvallat", original=""):
    original_span = f'<span class="original-name">{original}</span>' if original else ""
    age = (f'<span><img src="{BASE}/wp-content/themes/kinoregina2/assets/img/K16.jpg" width="32" height="32" '
           f'alt="{age_alt}" /></span>') if age_alt else "<span></span>"
    teemat_html = "".join(f'<span><a href="{BASE}/teemat/{slug}">{name}</a></span>' for slug, name in teemat)
    lisatieto_row = (f'<div class="col-4 col-md-2"><b><span>Lisätieto</span></b></div>'
                     f'<div class="col-8 col-md-4"><span>{lisatieto}</span></div>') if lisatieto else ""
    return f"""<!doctype html><html><head><title>X - Kino Regina</title>
<meta property="og:image" content="http://kinoregina.fi/wp-content/uploads/2026/06/still-optimized.jpg"></head><body>
<header><div class="col-12"><h1>Elokuvat</h1></div></header>
<div class="main-content col-12 col-lg-9 col-xl-6" id="main-content"><div class="row"><div class="col-12"><h1>{heading}</h1></div></div>
<div class="row"><div class="col-12"><img src="{BASE}/wp-content/uploads/2026/06/still-optimized.jpg" class="featured-image w-100 movie" alt="{heading}" /> {original_span}</div></div>
<a name="lisatiedot"></a><div class="row"><div class="col-12"><div class="row">
<div class="col-4 col-md-2"><b><span>Ohjaaja</span></b></div><div class="col-8 col-md-4"><span>Joku Ohjaaja</span></div>
<div class="col-4 col-md-2"><b><span>Maa</span></b></div><div class="col-8 col-md-4"><span>{maa}</span></div>
<div class="col-4 col-md-2"><b><span>Tekstitys</span></b></div><div class="col-8 col-md-4"><span>{tekstitys}</span></div>
<div class="col-4 col-md-2"><b><span>Kesto</span></b></div><div class="col-8 col-md-4"><span>{kesto}</span></div>
<div class="col-4 col-md-2"><b><span>Teemat</span></b></div><div class="col-8 col-md-4">{teemat_html}</div>
<div class="col-4 col-md-2"><b><span>Kopiotieto</span></b></div><div class="col-8 col-md-4"><span>{kopiotieto}</span></div>
{lisatieto_row}
<div class="col-4 col-md-2"><b><span>Ikäraja</span></b></div><div class="col-8 col-md-4">{age}</div>
</div></div></div>
<a name="kuvaus"></a><div class="row"> <!--<style> .single-movie-main-content-area p:first-child {{ font-size: 17px; }} </style>--><div class="col-12 single-movie-main-content-area">{kuvaus}</div></div>
<a name="naytosajat"></a><div class="row"><div class="col-12"><h2>Näytökset</h2></div></div>
</div></body></html>"""


ONE_BATTLE = film_page(
    "Ikäraja: K12", "162 min", "ei tekstitystä",
    [("paul-thomas-anderson", "PAUL THOMAS ANDERSON"), ("jatkoaika-kesa-2026", "JATKOAIKA KESÄ 2026")],
    "70 mm", "Thomas Pynchonin romaanista",
    "<p>Loistokkaalta 70 mm:n kopiolta nähtävä <em>One Battle After Another</em> (2025) on harvinaista ison "
    "kankaan poliittista toimintaelokuvaa.</p><p>***</p><p>Paul Thomas Anderson kuuluu yhdysvaltalaisen "
    "nykyelokuvan arvostetuimpiin auteur-ohjaajiin.</p>")
PERSEPOLIS = film_page(
    "Ikäraja: K16", "97 min", "suom. tekstit/svenska texter",
    [("koko-perheelle-frankofonia-sarjakuvan-kesa", "KOKO PERHEELLE: FRANKOFONIA-SARJAKUVAN KESÄ"),
     ("kesajazzit", "KESÄJAZZIT"), ("kesajazzit", "KESÄJAZZIT")],
    "35 mm", "15 min väliaika",
    "<p>Iranista Itävaltaan emigroituneen sarjakuvataiteilijan elämään perustuva teos on vaikuttava, "
    "klassisen animaation keinoin kerrottu tarina.</p>")
PLAIN = film_page("", "120 min", "English subtitles", [], "DCP", "",
                  "<p>Kaksi chicagolaista jazzmuusikkoa todistaa vahingossa mafian verilöylyn ja pakenee.</p>")

SITE = regina.SITES[0]
VENUE = SITE["venues"][0]


class ScheduleTest(unittest.TestCase):
    def setUp(self):
        self.shows = regina.parse_schedule(WINDOW_1)
        self.by_id = {}
        for s in self.shows:
            self.by_id.setdefault(s["eventId"], []).append(s)

    def test_rows_become_showtimes_keyed_on_the_film_id(self):
        self.assertEqual([(s["eventId"], s["start"]) for s in self.shows],
                         [("202769", "2026-09-05T14:00:00+03:00"), ("1415167", "2026-09-06T14:00:00+03:00"),
                          ("105609", "2026-09-06T16:00:00+03:00"), ("1653971", "2026-09-11T20:30:00+03:00")])

    def test_a_closed_sale_is_a_showtime_and_not_sold_out(self):
        s = self.by_id["202769"][0]
        self.assertEqual((s["title"], s["soldOut"]), ("Sátántangó", False))
        self.assertTrue(s["url"].startswith("https://kauppa.kavi.fi/fi/events/pwdg/event_buybox/show/"))

    def test_the_ticket_link_is_the_shows_own_and_the_film_page_is_the_fallback(self):
        self.assertEqual(self.by_id["1415167"][0]["url"],
                         "https://kauppa.kavi.fi/fi/events/pwdg/event_buybox/show/6a21c81415167")
        self.assertEqual(self.by_id["1653971"][0]["url"], f"{BASE}/elokuva/1653971/")

    def test_an_event_without_a_film_link_and_a_repeated_row_are_dropped(self):
        self.assertNotIn("9001", self.by_id)
        self.assertEqual(len(self.by_id["105609"]), 1)

    def test_the_show_shape(self):
        s = self.by_id["1415167"][0]
        self.assertEqual((s["title"], s["img"], s["price"], s["aud"], s["rating"], s["method"], s["lang"],
                          s["provider"], s["venue"], s["theatre"]),
                         ("Persepolis", "", "", "", "", "", "", "regina", "regina-helsinki", "Kino Regina"))

    def test_an_empty_window_parses_to_nothing(self):
        self.assertEqual(regina.parse_schedule(WINDOW_EMPTY), [])


class RecaseTest(unittest.TestCase):
    def test_capitals_become_sentence_case(self):
        for raw, want in (("PIUKAT PAIKAT", "Piukat paikat"), ("KÄPY SELÄN ALLA", "Käpy selän alla"),
                          ("PHANTASM - YÖN KAUHUT", "Phantasm - Yön kauhut"),
                          ("70 MM: 2001: AVARUUSSEIKKAILU", "70 mm: 2001: Avaruusseikkailu"),
                          ("PRINSSI JA REVYYTYTTÖ", "Prinssi ja revyytyttö"),
                          ("ELÄMÄ ON JUHLA", "Elämä on juhla"),                     # "on" is not a marker
                          ("SORRY, BABY", "Sorry, baby"), ("SÁTÁNTANGÓ", "Sátántangó")):
            with self.subTest(raw=raw):
                self.assertEqual(regina.recase(raw), want)

    def test_an_english_title_gets_title_case_with_small_words_lowered(self):
        for raw, want in (("THE TURIN HORSE", "The Turin Horse"),
                          ("ONCE UPON A TIME IN CHINA II", "Once Upon a Time in China II"),
                          ("THE ZONE OF INTEREST", "The Zone of Interest"),
                          ("KISS OF THE SPIDER WOMAN", "Kiss of the Spider Woman"),
                          ("ONE BATTLE AFTER ANOTHER", "One battle after another")):   # no marker word
            with self.subTest(raw=raw):
                self.assertEqual(regina.recase(raw), want)

    def test_a_mixed_case_title_is_left_alone(self):
        self.assertEqual(regina.recase("The Turin Horse"), "The Turin Horse")
        self.assertEqual(regina.recase("Sisko tahtoisin jäädä"), "Sisko tahtoisin jäädä")
        self.assertEqual(regina.recase(""), "")

    def test_the_synopsis_casing_wins_when_it_spells_the_same_title(self):
        text = "Loistokkaalta kopiolta nähtävä One Battle After Another (2025) on toimintaelokuvaa."
        self.assertEqual(regina.cased_in(text, "One battle after another"), "One Battle After Another")
        self.assertEqual(regina.cased_in("Mestarillinen Sátántango on", "Sátántangó"), "")     # not the same title
        self.assertEqual(regina.cased_in("PIUKAT PAIKAT on komedia", "Piukat paikat"), "")     # capitals do not win
        self.assertEqual(regina.cased_in("Carrie Whiten elämä", "Carrie"), "")                  # same spelling, no change
        self.assertEqual(regina.cased_in("", "Carrie"), "")


class WindowTest(unittest.TestCase):
    def fetch(self, answers):
        calls = []

        def get(day):
            calls.append(day)
            return answers[day]
        pages = regina.fetch_schedule(today=__import__("datetime").date(2026, 9, 5), get=get, sleep=0)
        return calls, pages

    def test_windows_are_followed_until_one_is_empty(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            calls, pages = self.fetch({"2026-09-05": WINDOW_1, "2026-09-21": WINDOW_2, "2026-10-07": WINDOW_EMPTY})
        self.assertEqual(calls, ["2026-09-05", "2026-09-21", "2026-10-07"])
        self.assertEqual(len(pages), 3)
        shows = regina.parse_schedule("".join(pages))
        self.assertEqual([s["eventId"] for s in shows], ["202769", "1415167", "105609", "1653971", "139011"])
        self.assertIn("3 window(s), the last from 2026-10-07", out.getvalue())

    def test_a_window_without_a_next_day_ends_the_walk(self):
        with contextlib.redirect_stdout(io.StringIO()):
            calls, pages = self.fetch({"2026-09-05": WINDOW_1.replace("loadNextTwoWeeks('2026-09-21', this)", "")})
        self.assertEqual(calls, ["2026-09-05"])

    def test_a_next_day_that_does_not_advance_ends_the_walk(self):
        with contextlib.redirect_stdout(io.StringIO()):
            calls, _ = self.fetch({"2026-09-05": WINDOW_1.replace("'2026-09-21'", "'2026-09-05'")})
        self.assertEqual(calls, ["2026-09-05"])

    def test_the_walk_is_bounded(self):
        # A server that always offers another window is cut off at MAX_PAGES.
        pages_seen = []

        def get(day):
            pages_seen.append(day)
            nxt = f"2026-12-{len(pages_seen):02d}"
            return WINDOW_2.replace("'2026-10-07'", f"'{nxt}'")
        with contextlib.redirect_stdout(io.StringIO()):
            pages = regina.fetch_schedule(today=__import__("datetime").date(2026, 9, 5), get=get, sleep=0)
        self.assertEqual(len(pages), 4)                      # the literal bound, not the constant


class DetailsTest(unittest.TestCase):
    def test_rating_runtime_series_gauge_and_synopsis(self):
        d = regina.details(ONE_BATTLE, title="One battle after another")
        self.assertEqual((d["rating"], d["len"], d["method"]), ("K-12", "162", "PAUL THOMAS ANDERSON · 70 mm"))
        self.assertEqual(d["title"], "One Battle After Another")          # the Kuvaus spelling
        self.assertNotIn("title", regina.details(ONE_BATTLE))              # only asked for with a title
        self.assertNotIn("title", regina.details(PLAIN, title="Piukat paikat"))   # not in that text
        self.assertEqual(d["lang"], "XX-S")                           # "ei tekstitystä"
        self.assertEqual(d["_syn"], "Loistokkaalta 70 mm:n kopiolta nähtävä One Battle After Another (2025) "
                                    "on harvinaista ison kankaan poliittista toimintaelokuvaa.")
        self.assertNotIn("auteur", d["_syn"])                         # the essay after *** is not the synopsis
        self.assertNotIn("Pynchon", d["_syn"])                        # Lisätieto is never appended

    def test_subtitles_series_filter_and_dedupe(self):
        d = regina.details(PERSEPOLIS)
        self.assertEqual((d["rating"], d["len"], d["lang"], d["method"]), ("K-16", "97", "FI-S, SV-S", "KESÄJAZZIT · 35 mm"))

    def test_no_rating_english_subtitles_and_dcp_dropped(self):
        d = regina.details(PLAIN)
        self.assertNotIn("rating", d)
        self.assertEqual(d["lang"], "EN-S")
        self.assertNotIn("method", d)

    def test_no_subtitles_is_the_whole_cell(self):
        """Read 2026-10-04: Niskavuoren naiset and Sound of Metal. A cell that only mentions
        the words, or names subtitles as well, is not the statement."""
        for cell, want in (("ei tekstityst\u00e4", "XX-S"), ("Ei tekstityst\u00e4.", "XX-S"),
                           ("suom. tekstit", "FI-S"), ("", None),
                           ("ei tekstityst\u00e4 ensimm\u00e4isess\u00e4 osassa", None)):
            with self.subTest(cell=cell):
                d = regina.details(film_page("", "90 min", cell, [], "35 mm", "", "<p>x</p>"))
                self.assertEqual(d.get("lang"), want)

    def test_a_lisatieto_segment_can_state_the_audio(self):
        """Read 2026-10-04: Tiikerin oma elokuva and Nalle Puhin elokuva. A whole segment
        only: "suomenkielisen version ohjaus ..." is a credit, and a segment naming another
        version's date is about another screening."""
        tiger = film_page("", "77 min", "", [], "35 mm",
                          "animaatio A. A. Milnen Nalle Puh -hahmoista * suomenkielinen versio",
                          "<p>Tiikeri etsii sukuaan.</p>")
        pooh = film_page("", "69 min", "", [], "35 mm",
                         "suomenkielisen version ohjaus Markus Bäckman * puhumme suomea",
                         "<p>Nalle Puh ja ystävät.</p>")
        credit = film_page("", "69 min", "suom. tekstit", [], "35 mm",
                           "suomenkielisen version ohjaus Markus Bäckman", "<p>Nalle Puh.</p>")
        other = film_page("", "69 min", "", [], "35 mm",
                          "suomenkielinen versio * ruotsinkielinen versio näytetään 12.10.",
                          "<p>Nalle Puh.</p>")
        self.assertEqual([regina.details(p).get("lang") for p in (tiger, pooh, credit, other)],
                         ["FI-A", "FI-A", "FI-S", "FI-A"])

    def test_the_series_rule(self):
        self.assertEqual(regina.series_tag("PAUL THOMAS ANDERSON"), "PAUL THOMAS ANDERSON")
        self.assertEqual(regina.series_tag("TARR &amp; KRASZNAHORKAI"), "TARR & KRASZNAHORKAI")
        self.assertEqual(regina.series_tag("JATKOAIKA KESÄ 2026"), "")
        self.assertEqual(regina.series_tag("KURITTOMAT SUKUPOLVET: NUORISOA SUOMALAISESSA ELOKUVASSA"), "")
        self.assertEqual(regina.series_tag("50 VUOTTA SITTEN: ELOKUVAVUOSI 1976"), "")
        self.assertEqual(regina.series_tag("MARILYN MONROE 100 VUOTTA"), "MARILYN MONROE 100 VUOTTA")
        self.assertEqual(regina.series_tag("KESÄ"), "")
        # Each rule on its own: too long with few words, a colon in a short value.
        self.assertEqual(regina.series_tag("ELOKUVAHISTORIAN SUURET MESTARITEOKSET"), "")
        self.assertEqual(regina.series_tag("TEEMA: KESÄ"), "")

    def test_the_gauge_rule(self):
        for raw, want in (("35 mm", "35 mm"), ("70mm", "70 mm"), ("16 mm", "16 mm"), ("8 mm", "8 mm"),
                          ("DCP", ""), ("Digitaalinen kopio, 4K-restauroitu", ""), ("", "")):
            with self.subTest(raw=raw):
                self.assertEqual(regina.gauge_tag(raw), want)

    def test_the_age_alt_shapes(self):
        for alt, want in (("Ikäraja: K12", "K-12"), ("Ikäraja: K7", "K-7"), ("Ikäraja: K-18", "K-18"),
                          ("Ikäraja: S", "S"), ("Ikäraja: T", "S")):
            with self.subTest(alt=alt):
                self.assertEqual(regina.details(film_page(alt, "90 min", "", [], "", "", ""))["rating"], want)

    def test_nothing_on_the_page_is_nothing(self):
        self.assertEqual(regina.details("<html><body>Huolto</body></html>"), {})


class RunnerTest(unittest.TestCase):
    """The whole run, with the first window's date injected rather than read off the clock.

    The fixture names the later windows as literals, `2026-09-21` and `2026-10-07`, and
    this test used to key the first one on the real date. On any day the clock reached one
    of those literals the two keys collided, the later window's body replaced the first's,
    and three tests failed with nothing in the diff to explain it. That is not a
    hypothetical: it fired on 2026-09-21 and would have fired again on 2026-10-07.
    `regina.fetch_site` takes `today` for exactly this, and `run.py` never passes one.
    """

    TODAY = datetime.date(2026, 9, 5)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._fetch, self._sleep = regina.fetch, regina.time.sleep
        self._site = regina.fetch_site
        self.addCleanup(lambda: setattr(regina, "fetch", self._fetch))
        self.addCleanup(lambda: setattr(regina.time, "sleep", self._sleep))
        self.addCleanup(lambda: setattr(regina, "fetch_site", self._site))
        regina.fetch_site = functools.partial(self._site, today=self.TODAY)
        regina.time.sleep = lambda s: None
        self.calls = []

    # KAVI's shop page each screening links to, as regina.ordinary_price() reads it.
    BUYBOX = ('<html><body><form class="jsonformify buybox-form"><div class="row">'
              '<label for="event_add_form_products_1">Peruslippu</label>'
              '<span itemprop="price">10,00 €</span></div></form></body></html>')

    def serve(self, answers):
        """answers: {url or (url, post body): html or Exception}. A ticket page not in
        `answers` is served as BUYBOX."""
        def fetch(url, data=None, **kw):
            key = (url, data.decode("ascii")) if data else url
            self.calls.append(key)
            page = answers.get(key)
            if isinstance(page, Exception):
                raise page
            if page is None and not data and url.startswith(regina.TICKETS):
                return self.BUYBOX.encode("utf-8")
            if page is None:
                raise RuntimeError(f"unexpected fetch {key}")
            return page.encode("utf-8")
        regina.fetch = fetch

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            # --half all: on Actions run.py derives "cloud" from GITHUB_ACTIONS, and a
            # local module has no cloud sites (test_empty_programme does the same).
            code = run.main(["regina", "--half", "all"])
        return code, out.getvalue() + err.getvalue()

    def test_the_pinned_date_is_not_one_the_fixture_already_names(self):
        """The guard on the guard. If TODAY is ever set to a window the fixture names,
        the two keys collide again and three tests fail with nothing saying why. This
        fails first, and says why."""
        named = {"2026-09-21", "2026-10-07", "2026-10-23"}
        self.assertNotIn(self.TODAY.isoformat(), named,
                         "TODAY collides with a window the fixture names as a literal")

    def films(self):
        return {f"{BASE}/elokuva/202769/": PLAIN, f"{BASE}/elokuva/1415167/": PERSEPOLIS,
                f"{BASE}/elokuva/105609/": PLAIN, f"{BASE}/elokuva/1653971/": ONE_BATTLE,
                f"{BASE}/elokuva/139011/": PLAIN}

    def test_a_full_run_publishes_the_venue_across_two_windows(self):
        self.serve({(SCHEDULE, "getShowtimesMovies=2026-09-05"): WINDOW_1,
                    (SCHEDULE, "getShowtimesMovies=2026-09-21"): WINDOW_2,
                    (SCHEDULE, "getShowtimesMovies=2026-10-07"): WINDOW_EMPTY, **self.films()})
        code, log = self.main()
        self.assertEqual(code, 0, log)
        area = json.loads((run.OUT / "area-regina-helsinki.json").read_text())
        venues = json.loads((run.OUT / "venues-regina.json").read_text())
        self.assertEqual([s["eventId"] for s in area["shows"]], ["202769", "1415167", "105609", "1653971", "139011"])
        self.assertEqual([s["title"] for s in area["shows"]],
                         ["Sátántangó", "Persepolis", "Piukat paikat", "One Battle After Another", "Carrie"])
        one = area["shows"][3]
        self.assertEqual((one["rating"], one["len"], one["method"], one["url"]),
                         ("K-12", "162", "PAUL THOMAS ANDERSON · 70 mm", f"{BASE}/elokuva/1653971/"))
        self.assertNotIn("_syn", area["shows"][0])
        self.assertEqual(venues["venues"], [{"id": "regina-helsinki", "name": "Kino Regina",
                                            "short": "Kino Regina", "city": "Helsinki"}])
        self.assertEqual((venues["status"], venues["pending"]), ("ok", []))
        self.assertEqual(self.calls[:3], [(SCHEDULE, "getShowtimesMovies=2026-09-05"),
                                          (SCHEDULE, "getShowtimesMovies=2026-09-21"),
                                          (SCHEDULE, "getShowtimesMovies=2026-10-07")])
        tickets = [s["url"] for s in area["shows"] if s["url"].startswith(regina.TICKETS)]
        # Three windows, five film pages, then one ticket page per screening that links
        # to the shop, after the film pages and through the same fetch.
        self.assertEqual(len(self.calls), 8 + len(tickets))
        self.assertEqual(sorted(self.calls[8:]), sorted(tickets))   # never-read keys, in key order
        self.assertEqual([s["price"] for s in area["shows"] if s["url"] in tickets],
                         ["10€"] * len(tickets))
        self.assertTrue(tickets)
        self.assertIn(f"prices: {len(tickets)} screenings, {len(tickets)} priced", log)
        self.assertIn("Kino Regina: 5 showtimes, 4 dates", log)
        self.assertIn("0 failures", log)

    PREV = {"generated": "2026-09-01T00:00:00+00:00", "dates": ["2026-09-01"],
            "horizon": "2026-09-01", "shows": [{"title": "Old", "start": "2026-09-01T12:00:00+03:00"}]}

    def serve_sequence(self, first_answers, rest):
        """The same POST answered differently on successive calls: `first_answers` in
        order for today's window, then `rest` for anything else."""
        queue = list(first_answers)

        def fetch(url, data=None, **kw):
            key = (url, data.decode("ascii")) if data else url
            self.calls.append(key)
            if key == (SCHEDULE, "getShowtimesMovies=2026-09-05") and queue:
                return queue.pop(0).encode("utf-8")
            page = rest.get(key)
            if isinstance(page, Exception):
                raise page
            if page is None:
                raise RuntimeError(f"unexpected fetch {key}")
            return page.encode("utf-8")
        regina.fetch = fetch

    def test_an_empty_first_window_is_asked_once_more_and_then_published(self):
        """2026-09-05, 16:57 UTC: one empty answer from a runner while the site listed 21
        rows to everyone else. One retry covers a single such answer."""
        self.serve_sequence([WINDOW_EMPTY, WINDOW_1],
                            {(SCHEDULE, "getShowtimesMovies=2026-09-21"): WINDOW_EMPTY, **self.films()})
        code, log = self.main()
        self.assertEqual(code, 0, log)
        area = json.loads((run.OUT / "area-regina-helsinki.json").read_text())
        self.assertEqual(len(area["shows"]), 4)
        self.assertEqual(self.calls[:3], [(SCHEDULE, "getShowtimesMovies=2026-09-05")] * 2
                         + [(SCHEDULE, "getShowtimesMovies=2026-09-21")])
        self.assertIn("has no screenings: ", log)
        self.assertIn("asking once more", log)

    def test_an_empty_schedule_twice_fails_the_site_and_keeps_the_previous_file(self):
        (run.OUT / "area-regina-helsinki.json").write_text(json.dumps(self.PREV))
        self.serve_sequence([WINDOW_EMPTY, WINDOW_EMPTY], {})
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", log)
        self.assertIn("answered twice with no screenings", log)
        self.assertEqual(json.loads((run.OUT / "area-regina-helsinki.json").read_text()), self.PREV)
        self.assertFalse((run.OUT / "venues-regina.json").exists())
        self.assertNotIn(LISTING, self.calls)              # the listing is no evidence and is not read

    def test_a_challenge_shell_is_named_and_fails_the_site(self):
        (run.OUT / "area-regina-helsinki.json").write_text(json.dumps(self.PREV))
        shell = ('<html><head><meta http-equiv="refresh" content="0;url=/.well-known/sgcaptcha/?r=%2F">'
                 '</head><body></body></html>')
        self.serve_sequence([shell], {})
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("challenged", log)
        self.assertEqual(len(self.calls), 1)               # no retry against a challenge
        self.assertEqual(json.loads((run.OUT / "area-regina-helsinki.json").read_text()), self.PREV)
        self.assertFalse(hasattr(regina, "EMPTY_VENUES_CONFIRMED"))

    def test_a_refused_schedule_fails_the_site(self):
        self.serve({(SCHEDULE, "getShowtimesMovies=2026-09-05"): RuntimeError("HTTP Error 403: Forbidden")})
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", log)

    def test_a_failing_film_page_costs_that_film_its_metadata_only(self):
        films = self.films()
        films[f"{BASE}/elokuva/1653971/"] = RuntimeError("HTTP Error 500")
        self.serve({(SCHEDULE, "getShowtimesMovies=2026-09-05"): WINDOW_1,
                    (SCHEDULE, "getShowtimesMovies=2026-09-21"): WINDOW_EMPTY, **films})
        code, log = self.main()
        self.assertEqual(code, 0, log)
        area = json.loads((run.OUT / "area-regina-helsinki.json").read_text())
        by_id = {s["eventId"]: s for s in area["shows"]}
        self.assertEqual(by_id["1653971"]["len"], "")
        self.assertEqual(by_id["1415167"]["len"], "97")
        self.assertIn("film page 1653971 failed", log)


class RegistryAndPagesTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("regina")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Kino Regina", "kinoregina.fi", "buy", "regina", "local"))
        self.assertEqual(p["accent"], "#8A4854")
        self.assertEqual(sum(1 for q in registry.PROVIDERS if q["accent"] == p["accent"]), 1)
        self.assertEqual((VENUE["id"], VENUE["name"], VENUE["short"], VENUE["city"]),
                         ("regina-helsinki", "Kino Regina", "Kino Regina", "Helsinki"))
        self.assertEqual(SITE["base"], BASE)
        self.assertEqual(bp.label_of({**VENUE, "provider": "regina"}, {"regina": "Kino Regina"}), "Kino Regina")

    def test_the_committed_page_follows_the_theatre_template(self):
        """The parts of the template a day with no screening still has."""
        fi = (ROOT / "teatteri" / "kino-regina-helsinki" / "index.html").read_text(encoding="utf-8")
        orion = (ROOT / "teatteri" / "cinema-orion-helsinki" / "index.html").read_text(encoding="utf-8")
        for marker in ('class="langseg"', 'class="cta"', '<p class="intro">'):
            self.assertIn(marker, fi)
            self.assertIn(marker, orion)
        self.assertEqual(fi.count("<style"), orion.count("<style"))

    def test_a_page_built_for_a_day_it_screens_carries_the_stubs_and_the_kavi_links(self):
        """The screening half of the template, on a day the committed data names.

        This used to read the committed page, which tied it to the day the suite runs.
        Kino Regina is the film archive's cinema and programmes in blocks: on 2026-09-18
        its next screening was 2026-09-30, twelve days past the window a landing page
        renders, so the page correctly said nothing was on and the ticket-link and stub
        assertions went red with nothing wrong anywhere. The day is read from `dates[0]`
        now, so there is always a screening on the page under test.
        """
        dates = json.loads((ROOT / "data" / "area-regina-helsinki.json")
                           .read_text(encoding="utf-8"))["dates"]
        self.assertTrue(dates, "Kino Regina publishes no date at all")

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        (root / "data").mkdir()
        for f in (ROOT / "data").glob("*.json"):
            shutil.copy2(f, root / "data" / f.name)
        saved = (bp.ROOT, bp.DATA)
        bp.ROOT, bp.DATA = root, root / "data"
        self.addCleanup(lambda: setattr(bp, "DATA", saved[1]))
        self.addCleanup(lambda: setattr(bp, "ROOT", saved[0]))
        bp._SHOWS.clear()
        bp._unmirrored_hosts.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            bp.main(today=datetime.date.fromisoformat(dates[0]))

        fi = (root / "teatteri" / "kino-regina-helsinki" / "index.html").read_text(encoding="utf-8")
        en = (root / "en" / "theatre" / "kino-regina-helsinki" / "index.html").read_text(encoding="utf-8")
        for page in (fi, en):
            self.assertIn('href="https://kauppa.kavi.fi/fi/events/pwdg/event_buybox/show/', page)
            for marker in ('<h2 class="day">', 'class="stub"', '<ul class="times">'):
                self.assertIn(marker, page)

    def test_the_helsinki_city_page_lists_the_cinema(self):
        city = (ROOT / "kaupunki" / "helsinki" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Kino Regina", city)
        self.assertIn("chain-regina", city)
        # 16 since 2026-09-21: Kino K13 and Kino Helios took Helsinki to ten chains
        # over sixteen venues.
        self.assertIn("16 teatteria", city)


class FilmIdentityTest(unittest.TestCase):
    """The year and the original title the film page publishes, for the TMDB search.

    Three repertory films sat unmatched on their Finnish titles while the page named the
    original and the year: "LUCKY LUKE SOTAPOLULLA (1978)" over "La ballade des
    Dalton/Lucky Luke på krigsstigen/The Ballad of the Daltons"."""

    def setUp(self):
        # The 0.5 s between film pages is the courtesy to the site, not behaviour under test.
        real = regina.time
        regina.time = types.SimpleNamespace(sleep=lambda *_: None)
        self.addCleanup(lambda: setattr(regina, "time", real))

    def page(self, **kw):
        return film_page("", "84 min", "suom. tekstit/svensk text", [], "35 mm", "",
                         "<p>Daltonin veljekset karkaavat.</p>", **kw)

    # -- the year -----------------------------------------------------------------------

    def test_the_bracketed_year_in_the_main_heading_is_the_year(self):
        d = regina.details(self.page(heading="LUCKY LUKE SOTAPOLULLA (1978)"))
        self.assertEqual(d["year"], "1978")

    def test_a_heading_without_a_year_publishes_none(self):
        """No field at all, so the enrichment sees older-shaped data and searches on the
        title alone; never a guess from the screening date."""
        self.assertNotIn("year", regina.details(self.page(heading="LUCKY LUKE SOTAPOLULLA")))

    def test_only_a_trailing_bracketed_year_counts(self):
        self.assertNotIn("year", regina.details(self.page(heading="2001: AVARUUSSEIKKAILU")))
        self.assertEqual(regina.details(self.page(heading="2001: AVARUUSSEIKKAILU (1968)"))["year"],
                         "1968")

    def test_the_site_heading_outside_the_main_content_is_not_read(self):
        """Every page opens with an h1 "Elokuvat"; the film's own heading is the one
        inside #main-content."""
        d = regina.details(self.page(heading="RAKASTA TAI TUHOUDU (1962)"))
        self.assertEqual(d["year"], "1962")
        self.assertEqual(regina.published_year(self.page(heading="X")), "")

    # -- the original title -------------------------------------------------------------

    def test_the_first_segment_of_the_original_name_span_is_the_original(self):
        d = regina.details(self.page(
            maa="Ranska/ Belgia",
            original="La ballade des Dalton/Lucky Luke på krigsstigen/The Ballad of the Daltons"))
        self.assertEqual(d["original"], "La ballade des Dalton")

    def test_a_single_segment_is_the_original(self):
        d = regina.details(self.page(maa="Iso-Britannia", original="All Night Long/Nattens makt"))
        self.assertEqual(d["original"], "All Night Long")

    def test_a_finnish_film_publishes_no_original(self):
        """The span then holds the Swedish title alone, "En kotte under ryggen" for Käpy
        selän alla, and the Finnish title is already the original."""
        for maa in ("Suomi", "Suomi/Ruotsi", "suomi"):
            with self.subTest(maa=maa):
                self.assertNotIn("original", regina.details(self.page(maa=maa, original="En kotte under ryggen")))

    def test_a_co_production_with_a_finnish_share_in_any_position_publishes_none(self):
        """Nothing observed says whether the first segment is the original or the Swedish
        title when Finland co-produced, so the field stays empty and the year stays."""
        d = regina.details(self.page(maa="Ranska/Suomi", original="Le Havre/Le Havre"))
        self.assertNotIn("original", d)
        self.assertEqual(d["year"], "2025")

    def test_a_missing_country_row_publishes_the_year_and_no_original(self):
        page = self.page(maa="Yhdysvallat", original="All Night Long/Nattens makt")
        page = page.replace('<div class="col-4 col-md-2"><b><span>Maa</span></b></div>'
                            '<div class="col-8 col-md-4"><span>Yhdysvallat</span></div>', "")
        self.assertNotIn("Maa", page)
        d = regina.details(page)
        self.assertNotIn("original", d)
        self.assertEqual(d["year"], "2025")

    def test_a_lone_segment_is_not_taken_as_the_original(self):
        """Every observed foreign page lists at least original and Swedish; one segment
        could be either."""
        d = regina.details(self.page(maa="Ranska/ Belgia", original="La ballade des Dalton"))
        self.assertNotIn("original", d)
        self.assertEqual(d["year"], "2025")

    def test_no_span_means_no_original(self):
        self.assertNotIn("original", regina.details(self.page(maa="Yhdysvallat")))

    def test_entities_in_the_span_are_decoded(self):
        d = regina.details(self.page(maa="Yhdysvallat", original="Who&#8217;s Afraid/Vem &auml;r r&auml;dd"))
        self.assertEqual(d["original"], "Who\u2019s Afraid")

    # -- reaching the showtimes without the ticket page -------------------------------------

    def test_year_and_original_reach_every_showtime_from_the_film_page_alone(self):
        """The ticket page prints the same line but is read only for prices and under a
        quota. enrich() folds the film page onto the rows and asks nothing else."""
        shows = regina.parse_schedule(WINDOW_1)
        asked = []

        def get(url):
            asked.append(url)
            return self.page(heading="RAKASTA TAI TUHOUDU (1962)", maa="Iso-Britannia",
                             original="All Night Long/Nattens makt")

        regina.enrich(shows, get=get)
        self.assertGreater(len(shows), 1)
        self.assertEqual({(s["year"], s["original"]) for s in shows}, {("1962", "All Night Long")})
        self.assertTrue(all(u.startswith(f"{BASE}/elokuva/") for u in asked), asked)
        self.assertFalse(any("kauppa.kavi.fi" in u for u in asked))

    def test_a_row_that_already_carries_an_original_keeps_it(self):
        shows = regina.parse_schedule(WINDOW_1)
        shows[0]["original"] = "Kept"
        regina.enrich(shows, get=lambda u: self.page(maa="Yhdysvallat", original="Other/Annan"))
        self.assertEqual(shows[0]["original"], "Kept")


if __name__ == "__main__":
    unittest.main()
