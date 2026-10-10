"""Heurekan planetaario: the calendar's three arrays, the film page, and the admission mode.

The adapter expands `window.eventCalendarData`, `window.eventExceptionsData` and
`window.disabledHolidays` the way the calendar page's own script does, keeps only the
`Planetaarioelokuvat` category, reports a calendar whose planetarium films all fall outside
the window as a confirmed empty venue, fails one where no item carries the category, and
reads runtime, recommendation, languages and the synopsis off each film's article. The
registry's fifth `book` mode, `admission`, carries the admission semantics in the client's footer and tooltip and in the generated page's
intro, and the per-show `age` field carries the planetarium's five-year floor.

Fixtures are hand-written in the page's own shape: bare keys, blank lines inside the
arrays, doubled and trailing commas, a title with a colon and a comma in it.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import build_pages as bp
import common
import registry
import run

TODAY = datetime.date(2026, 9, 7)          # a Monday; the fixture week runs to Sunday 13.9.
# Past every planetarium item's range, exception and one-day screening in CALENDAR: the
# calendar still lists the films, and none of them runs. That is a paused programme.
PAUSED = datetime.date(2027, 2, 1)
ROOT = _ctx.ROOT


def script(name, body):
    return f"<script>\n  window.{name} = {body};\n</script>\n"


def event(nimi, kategoria, times, kesto=28, start="2025-12-26", end="2027-01-06",
          blog=None, koko_paiva='"Ei"'):
    """One calendar item in the page's JavaScript shape. `times` maps a Finnish weekday
    to a list of clock strings; missing weekdays are the empty lists the page emits."""
    days = ["maanantai", "tiistai", "keskiviikko", "torstai", "perjantai", "lauantai", "sunnuntai"]
    ajat = ",\n".join(
        f"          {d}: [\n            \n            {', '.join(json.dumps(t) for t in times.get(d, []))}\n          ]"
        for d in days)
    blog_js = json.dumps(blog).replace("/", "\\/") if blog else "null"
    return (f"      {{\n        nimi: {json.dumps(nimi, ensure_ascii=False)},\n"
            f"        kuva: \"\\/\\/www.heureka.fi\\/cdn\\/shop\\/files\\/x.jpg?v=1\\u0026width=400\",\n"
            f"        kategoria: {json.dumps(kategoria, ensure_ascii=False)},\n"
            f"        kesto: {kesto if kesto is not None else 'null'},\n"
            f"        koko_paiva: {koko_paiva},\n"
            f"        alkamispaiva: {json.dumps(start)},\n        paattymispaiva: {json.dumps(end)},\n"
            f"        tapahtumasivu: null,\n        tapahtumasivu_blog_post: {blog_js},\n"
            f"        ajat: {{\n{ajat}\n        }}\n      }},\n    \n")


WEEK = {"maanantai": ["12.30", "14.00"], "tiistai": ["12.30", "14.00"],
        "keskiviikko": ["12.30", "14.00"], "torstai": ["12.30", "14.00", "18.30"],
        "perjantai": ["12.30", "14.00"], "lauantai": ["12.00"], "sunnuntai": ["12.00"]}
DAILY = {d: ["13.00"] for d in WEEK}

EVENTS = "[\n    \n" + "".join([
    event("Asteroid Quest", "Planetaarioelokuvat", WEEK,
          blog="/blogs/planetaario/asteroid-quest"),
    # Category decides. The same calendar carries the rat feeding and the laboratory.
    event("Rottien ruokintanäytös", "Heurekan rotat", DAILY, kesto=15,
          blog="/blogs/esitykset/rottien-ruokintanaytos"),
    event("Laboratoriokokeet Lasten Laboratoriossa", "Laboratoriokokeet", DAILY, kesto=30),
    # An all-day event is a banner on the page, never a timed screening.
    event("Dinosaurusten evoluutio", "Uuden näyttelyn avajaispäivä", {"lauantai": ["10.00"]},
          kesto=None, start="2026-09-12", end="2026-09-12", koko_paiva='"Kyllä"'),
    event("Avoin planetaario", "Planetaarioelokuvat", {"lauantai": ["10.00"]},
          start="2026-09-12", end="2026-09-12", koko_paiva='"Kyllä"'),
    # A film whose run ended before the window, and one with no times at all.
    event("Kuun pimeä puoli", "Planetaarioelokuvat", WEEK, start="2026-01-01", end="2026-08-31"),
    event("Yksityisnäytös", "Planetaarioelokuvat", {}, kesto=30, koko_paiva="null"),
    # A one-day festival screening whose title carries a colon and a comma.
    event("Aavistus Festival Näytös: Sergey Prokofjev, Local Dystopias",
          "Planetaarioelokuvat", {"torstai": ["16.15", "17.15"]}, kesto=40,
          start="2026-09-10", end="2026-09-10", koko_paiva="null"),
]) + "  ]"

EXCEPTIONS = """[

      {
        nimi: "Asteroid Quest 9.9.",
        alkaa: "2026-09-09",
        paattyy: "2026-09-09",
        appliesToEvents: ["Asteroid Quest"
],
        tapahtumat: [{"alkamispaiva":"2025-12-26","kategoria":"Planetaarioelokuvat","kesto":28,"nimi":"Asteroid Quest"}],
        ajat: {
          maanantai: [

          ],
          tiistai: [

          ],
          keskiviikko: [
            "11.15"
          ],
          torstai: [

          ],
          perjantai: [

          ],
          lauantai: [

          ],
          sunnuntai: [

          ]
        }
      },

      {
        nimi: "Asteroid Quest, joulu",
        alkaa: "2026-12-24",
        paattyy: "2026-12-26",
        appliesToEvents: ["Asteroid Quest"
],
        tapahtumat: [],
        ajat: {
          maanantai: [
            "09.00"
          ],
          tiistai: [

          ],
          keskiviikko: [

          ],
          torstai: [

          ],
          perjantai: [

          ],
          lauantai: [

          ],
          sunnuntai: [

          ]
        }
      },

  ]"""

HOLIDAYS = """["2026-03-13",
,
"2026-09-11",
,
"2025-12-24",

]"""

CALENDAR = ("<html><body><div class=\"event-calendar-2025\"><h1>Päivän ohjelma</h1></div>\n"
            + script("eventCalendarData", EVENTS) + script("eventExceptionsData", EXCEPTIONS)
            + script("disabledHolidays", HOLIDAYS)
            + "<script>window.disabledHolidays = window.disabledHolidays.filter(Boolean);</script>"
            "</body></html>")

ARTICLE = """<html><body><main>
<dl class="detail-list__grid">
 <div class="detail-list__item"><div class="detail-list__content"><dt class="detail-list__term">Kesto</dt><dd class="detail-list__desc">28 min</dd></div></div>
 <div class="detail-list__item"><div class="detail-list__content"><dt class="detail-list__term">Ikäsuositus</dt><dd class="detail-list__desc">Sopii parhaiten yli 10-vuotiaille</dd></div></div>
 <div class="detail-list__item"><div class="detail-list__content"><dt class="detail-list__term">Tuottaja</dt><dd class="detail-list__desc">Saint Thomas Productions (2024)</dd></div></div>
</dl>
<div class="image-with-text__content"><p class="image-with-text__text caption">Asteroideista paljastuu salaisuuksia</p>
<h2 class="image-with-text__heading h2 rte"> Asteroid Quest </h2>
<div class="image-with-text__text rte body"><p>Millaisia asteroidit ovat? Ovatko ne uhkia vai keinoja?</p><p>Asteroid Quest -planetaarioelokuvassa opit asteroideista &amp; niiden salaisuuksista.</p></div></div>
<h2 class="collapsible-content__heading"> Usein kysyttyä planetaarioelämyksestä </h2>
<details><summary><h3>Kuuluuko planetaario Heureka-lipun hintaan?</h3></summary>
<div class="accordion__content rte"><p>Kyllä, planetaario kuuluu Heureka-lipun hintaan.</p><p>Huom! Koulu- ja varhaiskasvatusryhmille elokuvat lisämaksusta 1,50 € / lapsi.</p></div></details>
<details><summary><h3>Onko planetaariolla ikärajaa?</h3></summary><div class="accordion__content rte"><p>Planetaarion ikäraja on 5 vuotta.</p></div></details>
<details><summary><h3>Kieliversiot planetaariossa</h3></summary>
<div class="accordion__content rte"><p>Asteroid Quest -elokuva löytyy nelikielisenä. Kieliversioita kuunnellaan kuulokkeilla. <br/><br/><strong>Kielivaihtoehdot: </strong>suomi (oletuskieli), englanti, ruotsi ja selkokieli.</p></div></details>
</main></body></html>"""

SILENT_ARTICLE = ARTICLE.replace(
    "<strong>Kielivaihtoehdot: </strong>suomi (oletuskieli), englanti, ruotsi ja selkokieli.",
    "Recombination-planetaarioelokuvassa ei ole puhetta.").replace(
    "Sopii parhaiten yli 10-vuotiaille", "Elokuva sopii parhaiten taiteesta kiinnostuneille aikuisille")


def heureka():
    import heureka as mod           # inside the function: the EmptyProgramme reload trap
    return mod


# ---------------------------------------------------------------- the arrays

class ArrayParsingTest(unittest.TestCase):
    def test_bare_keys_trailing_and_doubled_commas_become_json(self):
        h = heureka()
        got = json.loads(h._js_to_json('[\n {\n nimi: "A: b, c",\n x: null,\n y: [\n \n "1",\n ],\n },\n \n]'))
        self.assertEqual(got, [{"nimi": "A: b, c", "x": None, "y": ["1"]}])
        self.assertEqual(json.loads(h._js_to_json('["a",\n,\n"b",\n\n]')), ["a", "b"])
        self.assertEqual(json.loads(h._js_to_json("['it\\'s', \"q\"]")), ["it's", "q"])

    def test_the_three_arrays_are_read_off_the_page(self):
        events, exceptions, holidays = heureka().calendar_arrays(CALENDAR)
        self.assertEqual(len(events), 8)
        self.assertEqual(events[0]["nimi"], "Asteroid Quest")
        self.assertEqual(events[0]["ajat"]["torstai"], ["12.30", "14.00", "18.30"])
        self.assertEqual(events[0]["kuva"], "//www.heureka.fi/cdn/shop/files/x.jpg?v=1&width=400")
        self.assertEqual([e["nimi"] for e in exceptions], ["Asteroid Quest 9.9.", "Asteroid Quest, joulu"])
        self.assertEqual(exceptions[0]["ajat"]["keskiviikko"], ["11.15"])
        self.assertEqual(holidays, ["2026-03-13", "2026-09-11", "2025-12-24"])

    def test_a_page_without_the_calendar_is_a_break_not_an_empty_programme(self):
        h = heureka()
        with self.assertRaises(RuntimeError):
            h.parse_calendar("<html><body>Heureka</body></html>", TODAY)
        with self.assertRaises(RuntimeError):
            h.parse_calendar(script("eventCalendarData", "[\n  ]"), TODAY)


# ---------------------------------------------------------------- the expansion

class ExpansionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shows, cls.blogs = heureka().parse_calendar(CALENDAR, TODAY, days=7)

    def by_day(self, title=None):
        out = {}
        for s in self.shows:
            if title and s["title"] != title:
                continue
            out.setdefault(s["start"][:10], []).append(s["start"][11:16])
        return out

    def test_only_planetarium_films_survive(self):
        self.assertEqual({s["title"] for s in self.shows},
                         {"Asteroid Quest", "Aavistus Festival Näytös: Sergey Prokofjev, Local Dystopias"})

    def test_the_weekday_pattern_expands_inside_the_window(self):
        aq = self.by_day("Asteroid Quest")
        self.assertEqual(aq["2026-09-07"], ["12:30", "14:00"])           # Monday
        self.assertEqual(aq["2026-09-10"], ["12:30", "14:00", "18:30"])  # Thursday
        self.assertEqual(aq["2026-09-12"], ["12:00"])                    # Saturday
        self.assertEqual(aq["2026-09-13"], ["12:00"])                    # Sunday
        self.assertNotIn("2026-09-14", aq)                               # past the window

    def test_a_holiday_closes_the_house(self):
        self.assertNotIn("2026-09-11", self.by_day())                    # Friday, disabledHolidays

    def test_an_exception_replaces_the_weekday_schedule_for_its_range_only(self):
        aq = self.by_day("Asteroid Quest")
        self.assertEqual(aq["2026-09-09"], ["11:15"])                    # the exception's Wednesday
        self.assertEqual(aq["2026-09-08"], ["12:30", "14:00"])           # Tuesday: the rule

    def test_the_festival_screening_keeps_its_whole_title(self):
        fest = self.by_day("Aavistus Festival Näytös: Sergey Prokofjev, Local Dystopias")
        self.assertEqual(fest, {"2026-09-10": ["16:15", "17:15"]})

    def test_the_show_is_an_admission_screening(self):
        s = next(x for x in self.shows if x["title"] == "Asteroid Quest")
        self.assertEqual(s["url"], "https://www.heureka.fi/collections/liput")
        self.assertEqual(s["price"], "")
        self.assertEqual(s["age"], "K-5")
        self.assertEqual(s["rating"], "")
        self.assertEqual(s["aud"], "")
        self.assertEqual(s["len"], "28")
        self.assertEqual(s["img"], "data/posters/card-heureka-asteroid-quest.jpg")
        self.assertEqual((s["provider"], s["venue"], s["theatre"]),
                         ("heureka", "hk-vantaa", "Heurekan planetaario"))
        self.assertEqual(s["eventId"], "asteroid-quest")
        self.assertTrue(s["start"].endswith("+03:00"), s["start"])
        self.assertFalse(s["soldOut"])

    def test_a_mapped_title_gets_its_title_card_and_nothing_else_does(self):
        """The card is Leffavuoro's own illustration, not Heureka's artwork, and it is
        keyed on the published title character for character. A film that is not in the
        map keeps an empty `img` and draws an initials tile, which is the behaviour every
        Heureka film had before 2026-09-20."""
        by_title = {x["title"]: x for x in self.shows}
        self.assertEqual(by_title["Asteroid Quest"]["img"],
                         "data/posters/card-heureka-asteroid-quest.jpg")
        fest = next(x for x in self.shows if x["title"].startswith("Aavistus"))
        self.assertEqual(fest["img"], "")

    def test_a_title_card_is_never_marked_as_tmdbs(self):
        """enrich_tmdb reclaims a poster it marked `isrc: "tmdb"` and leaves anything else
        as the cinema's own. Marking a card would let a later TMDB candidate replace it."""
        for show in self.shows:
            with self.subTest(title=show["title"]):
                self.assertNotIn("isrc", show)

    def test_every_card_in_the_map_exists_and_is_a_portrait_image(self):
        """A mapping to a file that is not there publishes a broken image on every card.
        Read as bytes rather than with Pillow, which the pipeline does not require: the
        JPEG SOF segment carries the dimensions."""
        import struct
        mod = heureka()
        root = pathlib.Path(__file__).resolve().parent.parent
        self.assertTrue(mod.CARDS, "the map must not be empty while this test guards it")
        for title, rel in mod.CARDS.items():
            with self.subTest(title=title):
                path = root / rel
                self.assertTrue(path.exists(), f"{rel} is mapped and missing")
                raw = path.read_bytes()
                self.assertEqual(raw[:2], b"\xff\xd8", "not a JPEG")
                i, w, h = 2, None, None
                while i < len(raw) - 9:
                    if raw[i] != 0xFF:
                        i += 1
                        continue
                    marker = raw[i + 1]
                    if marker in (0xC0, 0xC1, 0xC2):
                        h, w = struct.unpack(">HH", raw[i + 5:i + 9])
                        break
                    if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                        i += 2
                        continue
                    i += 2 + struct.unpack(">H", raw[i + 2:i + 4])[0]
                self.assertEqual((w, h), (342, 513), "cards are 2:3 at the mirrored width")

    def test_the_adapter_map_and_the_generator_agree(self):
        """The two lists have to name the same films and the same files, or the adapter
        publishes a card the generator does not make and `make_cards.py --check` cannot
        see it. Mapping a title to some other existing 342x513 image passes every other
        check here, which is the gap this closes: a card is identified by the generator
        that drew it, not by having plausible dimensions."""
        import make_cards
        mod = heureka()
        drawn = {c["title"]: f"data/posters/{c['slug']}.jpg" for c in make_cards.CARDS}
        self.assertEqual(mod.CARDS, drawn)

    def test_a_film_without_an_article_gets_a_slug_id(self):
        s = next(x for x in self.shows if x["title"].startswith("Aavistus"))
        self.assertEqual(s["eventId"], "aavistus-festival-naytos-sergey-prokofjev-local-dystopias")

    def test_articles_are_listed_once_per_film(self):
        self.assertEqual(self.blogs, {"/blogs/planetaario/asteroid-quest": "asteroid-quest"})

    def test_shows_are_sorted_by_start(self):
        starts = [s["start"] for s in self.shows]
        self.assertEqual(starts, sorted(starts))

    def test_planetarium_films_whose_runs_have_all_ended_are_a_confirmed_empty_list(self):
        """The category matched and every schedule was read in the page's shape: the
        calendar says these films do not run in the window."""
        h = heureka()
        self.assertEqual(h.parse_calendar(CALENDAR, PAUSED, days=7), ([], {}))
        self.assertTrue(h.EMPTY_VENUES_CONFIRMED)

    def test_no_item_in_the_planetarium_category_fails_rather_than_emptying(self):
        """A renamed category leaves the calendar full and the filter matching nothing."""
        h = heureka()
        page = CALENDAR.replace('kategoria: "Planetaarioelokuvat"', 'kategoria: "Tiedeteatteri"')
        with self.assertRaises(RuntimeError):
            h.parse_calendar(page, TODAY, days=7)

    def test_renamed_weekday_keys_fail_rather_than_emptying(self):
        """The films are listed and every schedule lookup misses: a schema change."""
        h = heureka()
        page = CALENDAR
        for n, day in enumerate(h.WEEKDAYS):
            page = page.replace(f"{day}: [", f"paiva{n}: [")
        self.assertNotIn("maanantai: [", page)
        with self.assertRaises(RuntimeError):
            h.parse_calendar(page, TODAY, days=7)

    def test_an_exception_in_another_shape_blocks_a_confirmed_empty_list(self):
        """Paused, but an exception naming a film no longer carries the weekday lists."""
        h = heureka()
        renamed = EXCEPTIONS
        for n, day in enumerate(h.WEEKDAYS):
            renamed = renamed.replace(f"{day}: [", f"paiva{n}: [")
        page = CALENDAR.replace(EXCEPTIONS, renamed)
        self.assertNotEqual(page, CALENDAR)
        with self.assertRaises(RuntimeError):
            h.parse_calendar(page, PAUSED, days=7)

    def test_unreadable_clocks_fail_the_venue_rather_than_emptying_it(self):
        h = heureka()
        page = CALENDAR.replace('"12.30"', '"12h30"').replace('"14.00"', '"14h00"') \
                       .replace('"18.30"', '"18h30"').replace('"12.00"', '"12h00"') \
                       .replace('"11.15"', '"11h15"').replace('"16.15"', '"16h15"') \
                       .replace('"17.15"', '"17h15"')
        with self.assertRaises(RuntimeError):
            h.parse_calendar(page, TODAY, days=7)


# ---------------------------------------------------------------- the film page

class FilmPageTest(unittest.TestCase):
    def test_runtime_recommendation_languages_and_synopsis(self):
        m = heureka().film_meta(ARTICLE)
        self.assertEqual(m["len"], "28")
        self.assertEqual(m["method"], "Suositus yli 10 v")
        self.assertEqual(m["lang"], "FI-A, EN-A, SV-A")
        self.assertEqual(m["_syn"], "Millaisia asteroidit ovat? Ovatko ne uhkia vai keinoja? "
                                    "Asteroid Quest -planetaarioelokuvassa opit asteroideista & "
                                    "niiden salaisuuksista.")

    def test_the_faq_and_its_school_price_stay_out_of_the_synopsis(self):
        m = heureka().film_meta(ARTICLE)
        for word in ("1,50", "Kuuluuko", "ikäraja", "Kielivaihtoehdot", "Heureka-lipun"):
            self.assertNotIn(word, m["_syn"])
        self.assertFalse(__import__("synmerge").is_note(m["_syn"]))

    def test_a_silent_film_has_no_language_and_an_adult_recommendation(self):
        m = heureka().film_meta(SILENT_ARTICLE)
        self.assertEqual(m["lang"], "")
        self.assertEqual(m["method"], "Suositus aikuisille")

    def test_the_recommendation_wordings(self):
        rec = heureka().recommendation
        self.assertEqual(rec("Sopii parhaiten yli 7-vuotiaille"), "Suositus yli 7 v")
        self.assertEqual(rec("Sopii parhaiten 5–10-vuotiaille"), "Suositus 5–10 v")
        self.assertEqual(rec("Suositellaan erityisesti 5-10-vuotiaille"), "Suositus 5–10 v")
        self.assertEqual(rec("Elokuva sopii parhaiten taiteesta kiinnostuneille aikuisille"),
                         "Suositus aikuisille")
        self.assertEqual(rec("Sopii kaikille"), "")
        self.assertEqual(rec(""), "")
        for text in ("Sopii parhaiten yli 10-vuotiaille", "5–10-vuotiaille", "aikuisille"):
            self.assertTrue(rec(text).startswith("Suositus "), text)
        # "over ten" must not become "ten and over": the boundary is the source's.
        self.assertEqual(rec("Sopii parhaiten yli 10-vuotiaille"), "Suositus yli 10 v")
        self.assertNotIn("10+", rec("Sopii parhaiten yli 10-vuotiaille"))
        self.assertNotIn("7+", rec("Sopii parhaiten yli 7-vuotiaille"))

    def test_missing_parts_stay_empty(self):
        m = heureka().film_meta("<html><body><main><p>Tulossa</p></main></body></html>")
        self.assertEqual(m, {"len": "", "method": "", "lang": "", "_syn": ""})


# ---------------------------------------------------------------- through the runner

class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self.h = heureka()
        self._get, self._today = self.h.get, self.h.datetime
        self.addCleanup(lambda: setattr(self.h, "get", self._get))
        self.calls = []

    def serve(self, pages):
        def get(path):
            self.calls.append(path)
            page = pages.get(path)
            if isinstance(page, Exception):
                raise page
            if page is None:
                raise RuntimeError(f"unexpected fetch {path}")
            return page
        self.h.get = get

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["heureka", "--half", "all"])
        return code, out.getvalue() + err.getvalue()

    def test_a_full_run_publishes_the_venue_with_film_metadata(self):
        self.serve({self.h.CALENDAR: CALENDAR, "/blogs/planetaario/asteroid-quest": ARTICLE})
        # fetch_site reads today's date; the fixture is built for one week of September
        # 2026, so drive parse_calendar's `today` through the module's own clock.
        self.h.fetch_site.__defaults__ = (self.h.SITES[0], 0, TODAY)
        self.addCleanup(lambda: setattr(self.h.fetch_site, "__defaults__", (self.h.SITES[0], 1.2, None)))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        area = json.loads((run.OUT / "area-hk-vantaa.json").read_text())
        venues = json.loads((run.OUT / "venues-heureka.json").read_text())
        aq = [s for s in area["shows"] if s["title"] == "Asteroid Quest"]
        self.assertTrue(aq)
        self.assertEqual({(s["len"], s["method"], s["lang"], s["age"], s["price"]) for s in aq},
                         {("28", "Suositus yli 10 v", "FI-A, EN-A, SV-A", "K-5", "")})
        self.assertTrue(all(s["url"] == self.h.TICKETS for s in area["shows"]))
        self.assertNotIn("_syn", area["shows"][0])
        self.assertEqual(venues["venues"][0]["city"], "Vantaa")
        self.assertEqual(venues["status"], "ok")
        self.assertEqual(self.calls, [self.h.CALENDAR, "/blogs/planetaario/asteroid-quest"])
        self.assertIn("Heurekan planetaario:", log)
        self.assertIn("0 failures", log)

    def test_a_confirmed_empty_programme_clears_old_screenings_and_stays_green(self):
        """Heureka pauses its programme: the calendar still lists its planetarium films and
        none runs in the window. The old screenings must go, the venue reads pending, the
        run is green."""
        prev = {"generated": "2026-09-01T00:00:00+00:00", "dates": ["2026-09-01"],
                "horizon": "2026-09-01", "shows": [{"title": "Old", "start": "2026-09-01T12:00:00+03:00"}]}
        (run.OUT / "area-hk-vantaa.json").write_text(json.dumps(prev))
        self.serve({self.h.CALENDAR: CALENDAR})
        self.h.fetch_site.__defaults__ = (self.h.SITES[0], 0, PAUSED)
        self.addCleanup(lambda: setattr(self.h.fetch_site, "__defaults__", (self.h.SITES[0], 1.2, None)))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        area = json.loads((run.OUT / "area-hk-vantaa.json").read_text())
        self.assertEqual(area["shows"], [])
        self.assertNotEqual(area["generated"], prev["generated"])
        venues = json.loads((run.OUT / "venues-heureka.json").read_text())
        self.assertEqual((venues["status"], venues["pending"], venues["stale"]), ("ok", ["hk-vantaa"], []))
        self.assertEqual(venues["oldest"], area["generated"])
        self.assertIn("pending", log)
        self.assertIn("0 failures", log)
        self.assertEqual(self.calls, [self.h.CALENDAR])

    def test_a_calendar_whose_filter_matches_nothing_fails_and_keeps_the_previous_file(self):
        prev = {"generated": "2026-09-01T00:00:00+00:00", "dates": ["2026-09-01"],
                "horizon": "2026-09-01", "shows": [{"title": "Old", "start": "2026-09-01T12:00:00+03:00"}]}
        (run.OUT / "area-hk-vantaa.json").write_text(json.dumps(prev))
        page = CALENDAR.replace('kategoria: "Planetaarioelokuvat"', 'kategoria: "Tiedeteatteri"')
        self.serve({self.h.CALENDAR: page})
        self.h.fetch_site.__defaults__ = (self.h.SITES[0], 0, TODAY)
        self.addCleanup(lambda: setattr(self.h.fetch_site, "__defaults__", (self.h.SITES[0], 1.2, None)))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("FAILED", log)
        self.assertEqual(json.loads((run.OUT / "area-hk-vantaa.json").read_text()), prev)

    def test_a_refused_calendar_fails_the_site_and_keeps_the_previous_file(self):
        prev = {"generated": "2026-09-01T00:00:00+00:00", "dates": ["2026-09-01"],
                "horizon": "2026-09-01", "shows": [{"title": "Old", "start": "2026-09-01T12:00:00+03:00"}]}
        (run.OUT / "area-hk-vantaa.json").write_text(json.dumps(prev))
        self.serve({self.h.CALENDAR: RuntimeError("HTTP Error 403: Forbidden")})
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", log)
        self.assertEqual(json.loads((run.OUT / "area-hk-vantaa.json").read_text()), prev)
        self.assertFalse((run.OUT / "venues-heureka.json").exists())

    def test_a_failing_film_page_costs_metadata_and_not_the_schedule(self):
        self.serve({self.h.CALENDAR: CALENDAR,
                    "/blogs/planetaario/asteroid-quest": RuntimeError("HTTP Error 500")})
        self.h.fetch_site.__defaults__ = (self.h.SITES[0], 0, TODAY)
        self.addCleanup(lambda: setattr(self.h.fetch_site, "__defaults__", (self.h.SITES[0], 1.2, None)))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        area = json.loads((run.OUT / "area-hk-vantaa.json").read_text())
        aq = [s for s in area["shows"] if s["title"] == "Asteroid Quest"]
        self.assertTrue(aq)
        self.assertEqual({(s["len"], s["method"], s["lang"]) for s in aq}, {("28", "", "")})
        self.assertIn("film page /blogs/planetaario/asteroid-quest failed", log)


# ---------------------------------------------------------------- registry, client, pages

class AdmissionModeTest(unittest.TestCase):
    HTML = (ROOT / "index.html").read_text(encoding="utf-8")

    def test_the_registry_entry(self):
        p = registry.by_id("heureka")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Heureka", "heureka.fi", "admission", "heureka", "local"))
        self.assertEqual(p["accent"], "#0B8468")
        self.assertEqual(sum(1 for q in registry.PROVIDERS if q["accent"] == p["accent"]), 1)
        h = heureka()
        v = h.SITES[0]["venues"][0]
        self.assertEqual((v["id"], v["name"], v["short"], v["city"]),
                         ("hk-vantaa", "Heurekan planetaario", "Heurekan planetaario", "Vantaa"))
        self.assertEqual(bp.label_of({**v, "provider": "heureka"}, {"heureka": "Heureka"}),
                         "Heurekan planetaario")       # the chain prefix collapses; no "Heureka Heurekan"

    def test_the_client_has_the_admission_strings_in_every_language(self):
        self.assertEqual(self.HTML.count("actAdmission:'"), 3)
        self.assertEqual(self.HTML.count("tipAdmission:'"), 3)
        for line in self.HTML.splitlines():
            if "actAdmission:'" in line:
                self.assertIn("{host}", line)
        self.assertIn("bk === 'admission' ? T.actAdmission", self.HTML)
        self.assertIn("admission:'tipAdmission'", self.HTML)

    def test_the_tag_key_samples_the_limit_on_screen(self):
        key = self.HTML[self.HTML.index("function tagKey("):]
        key = key[:key.index("return `<div class=\"tagkey\">")]
        self.assertIn("ageGlyph(aged)", key)
        self.assertNotIn("18+", key)

    def test_the_generated_intro_for_admission(self):
        for lang, host_word in (("fi", "sisältyvät pääsylipun hintaan"), ("en", "included in the admission ticket")):
            text = bp.venue_intro(bp.L[lang], "admission", "heureka.fi")
            self.assertIn(host_word, text)
            self.assertIn("heureka.fi", text)
            self.assertNotEqual(text, bp.venue_intro(bp.L[lang], "buy", "heureka.fi"))

    def test_the_age_sentence_fires_only_when_every_screening_shares_a_limit(self):
        t = bp.L["fi"]
        self.assertEqual(bp.age_note(t, [{"age": "K-5"}, {"age": "K-5"}]), "Näytösten ikäraja on 5 vuotta.")
        self.assertEqual(bp.age_note(bp.L["en"], [{"age": "K-5"}]), "Age limit 5 years.")
        self.assertEqual(bp.age_note(t, [{"age": "K-18"}, {"age": ""}]), "")
        self.assertEqual(bp.age_note(t, [{"age": ""}, {}]), "")
        self.assertEqual(bp.age_note(t, []), "")

    def test_the_committed_heureka_page_follows_the_theatre_template(self):
        fi = (ROOT / "teatteri" / "heurekan-planetaario-vantaa" / "index.html").read_text(encoding="utf-8")
        en = (ROOT / "en" / "theatre" / "heurekan-planetaario-vantaa" / "index.html").read_text(encoding="utf-8")
        flamingo = (ROOT / "teatteri" / "finnkino-flamingo-vantaa" / "index.html").read_text(encoding="utf-8")
        for page in (fi, en):
            self.assertIn("Näytösten ikäraja on 5 vuotta." if page is fi else "Age limit 5 years.", page)
            self.assertIn("Esitykset sisältyvät pääsylipun hintaan" if page is fi
                          else "included in the admission ticket", page)
            self.assertIn('href="https://www.heureka.fi/collections/liput"', page)
            self.assertNotIn("€", page.split("<h2", 1)[1])          # no price on any stub
            self.assertNotIn("Suositus", page)                            # method tags are not ported
        # The same template as any other theatre page: header, selector, CTA, day headings.
        for marker in ('class="langseg"', 'class="cta"', '<h2 class="day">', '<p class="intro">',
                       'class="stub"', '<ul class="times">'):
            self.assertIn(marker, fi)
            self.assertIn(marker, flamingo)
        self.assertNotIn('class="times grid"', fi)
        self.assertEqual(fi.count("<style"), flamingo.count("<style"))

    def test_the_vantaa_city_page_lists_the_planetarium_beside_the_cinemas(self):
        city = (ROOT / "kaupunki" / "vantaa" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Heurekan planetaario", city)
        self.assertIn("chain-heureka", city)
        self.assertIn('class="times grid"', city)
        # Four since 2026-09-18, when Kino Myyri joined Bio Grand, Finnkino Flamingo and
        # the planetarium in Vantaa.
        self.assertIn("4 teatteria", city)


if __name__ == "__main__":
    unittest.main()
