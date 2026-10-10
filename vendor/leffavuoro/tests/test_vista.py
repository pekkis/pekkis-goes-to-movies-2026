"""Korjaamo Kino through the Vista adapter: the schedule, the unknown rating, the bare hall.

The fixtures are cut from korjaamokino.fi's own `/xml/Schedule/` and `/xml/Events/`
answers of 2026-09-05, trimmed to three shows and one show from a theatre the site does
not list. The parser is the one Savon Kinot ran on; what Korjaamo added is the "Ei
tiedossa" rating, an auditorium called only "Sali", a festival in EventSeries and a
language the name table did not know.
"""
import contextlib
import datetime
import io
import json
import pathlib
import shutil
import tempfile
import unittest

import _ctx                                                # noqa: F401
import build_pages as bp
import common
import registry
import run
import strands
import vista

ROOT = _ctx.ROOT
BASE = "https://korjaamokino.fi"


def show(sid, eid, title, start_local, start_utc, rating, label, series="", theatre="1045",
         aud="Sali", spoken=("suomi", "fi"), subs=(), length="88", genres="Dokumentti"):
    def lang(tag, name, iso):
        return (f"<{tag}><Name>{name}</Name><NameInLanguage>{name}</NameInLanguage>"
                f"<ISOTwoLetterCode>{iso}</ISOTwoLetterCode></{tag}>")
    sub_xml = "".join(lang(f"SubtitleLanguage{n}", name, iso)
                      for n, (name, iso) in enumerate(subs, 1))
    return f"""
    <Show>
      <ID>{sid}</ID>
      <dttmShowStart>{start_local}</dttmShowStart>
      <dttmShowStartUTC>{start_utc}</dttmShowStartUTC>
      <EventID>{eid}</EventID>
      <Title>{title}</Title>
      <OriginalTitle>{title}</OriginalTitle>
      <ProductionYear>2026</ProductionYear>
      <LengthInMinutes>{length}</LengthInMinutes>
      <Rating>{rating}</Rating>
      <RatingLabel>{label}</RatingLabel>
      <EventType>Movie</EventType>
      <Genres>{genres}</Genres>
      <TheatreID>{theatre}</TheatreID>
      <Theatre>Korjaamo Kino</Theatre>
      <TheatreAuditorium>{aud}</TheatreAuditorium>
      <PresentationMethod>2D</PresentationMethod>
      <EventSeries>{series}</EventSeries>
      <ShowURL>http://korjaamokino.fi/websales/show/{sid}</ShowURL>
      <EventURL>https://korjaamokino.fi/event/{eid}</EventURL>
      {lang("SpokenLanguage", *spoken)}
      {sub_xml}
      <Images />
    </Show>"""


SCHEDULE = f"""<?xml version="1.0" encoding="utf-8"?>
<Schedule xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <PubDate>2026-09-05T00:00:00+00:00</PubDate>
  <Shows>{show("168058", "5202", "Päivien lumo", "2026-09-07T15:00:00", "2026-09-07T12:00:00Z",
                "Sallittu", "S")}
    {show("168094", "5193", "HelAFF: Fez Summer 55", "2026-09-10T17:30:00", "2026-09-10T14:30:00Z",
          "Ei tiedossa", "", series="HelAFF", spoken=("useita kieliä", ""),
          subs=(("englanti", "en"), ("arabia", "")), length="115", genres="Draama")}
    {show("168059", "5204", "Presidentin Kyyditys", "2026-09-07T17:15:00", "2026-09-07T14:15:00Z",
          "K-12", "K-12", subs=(("ruotsi", "sv"),), length="87", genres="Komedia, Draama")}
    {show("168999", "5999", "Not Ours", "2026-09-07T20:00:00", "2026-09-07T17:00:00Z",
          "K-16", "K-16", theatre="9999", aud="Joensuu, Tapio 4")}
  </Shows>
</Schedule>
"""

EVENTS = """<?xml version="1.0" encoding="utf-8"?>
<Events xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Event>
    <ID>5202</ID>
    <Title>Päivien lumo</Title>
    <ShortSynopsis>Lyhyt.</ShortSynopsis>
    <Synopsis>&lt;p&gt;Dokumentti kolmesta kesästä, jotka muuttivat kaiken.&lt;/p&gt;</Synopsis>
  </Event>
  <Event>
    <ID>5193</ID>
    <Title>HelAFF: Fez Summer 55</Title>
    <Synopsis>Fez, kesä 1955.</Synopsis>
  </Event>
</Events>
"""

SITE = vista.SITES[0]
VENUE = SITE["venues"][0]


class RatingTest(unittest.TestCase):
    def test_not_known_is_no_rating(self):
        for v in ("Ei tiedossa", "ei tiedossa", "  Ei tiedossa ", "", None):
            with self.subTest(v=v):
                self.assertEqual(vista._rating(v), "")

    def test_the_savon_kinot_shapes_still_normalise(self):
        self.assertEqual(vista._rating("K-7 (4)"), "K-7")
        self.assertEqual(vista._rating("Sallittu kaikenikäisille"), "S")
        self.assertEqual(vista._rating("Sallittu"), "S")
        self.assertEqual(vista._rating("K-12"), "K-12")
        self.assertEqual(vista._rating("K16"), "K-16")


class AuditoriumTest(unittest.TestCase):
    def aud(self, raw):
        import xml.etree.ElementTree as ET
        return vista._aud(ET.fromstring(f"<Show><TheatreAuditorium>{raw}</TheatreAuditorium></Show>"),
                          VENUE)

    def test_a_bare_hall_is_no_room(self):
        self.assertEqual(self.aud("Sali"), "")
        self.assertEqual(self.aud("Korjaamo Kino, Sali"), "")
        self.assertEqual(self.aud("Korjaamo Kino"), "")

    def test_a_named_room_survives(self):
        self.assertEqual(self.aud("Joensuu, Tapio 4"), "Tapio 4")
        self.assertEqual(self.aud("Sali 2"), "Sali 2")


class ScheduleTest(unittest.TestCase):
    def setUp(self):
        self.by_venue = vista.parse_schedule(SCHEDULE, SITE, SITE["venues"])
        self.shows = {s["eventId"]: s for s in self.by_venue["korjaamo-helsinki"]}

    def test_only_the_listed_theatre_is_kept(self):
        self.assertEqual(set(self.by_venue), {"korjaamo-helsinki"})
        self.assertEqual(sorted(self.shows), ["5193", "5202", "5204"])

    def test_the_unknown_rating_is_blank_and_the_known_ones_are_kept(self):
        self.assertEqual({k: s["rating"] for k, s in self.shows.items()},
                         {"5202": "S", "5193": "", "5204": "K-12"})

    def test_start_is_the_utc_time_in_helsinki(self):
        self.assertEqual(self.shows["5202"]["start"], "2026-09-07T15:00:00+03:00")
        self.assertEqual(self.shows["5193"]["start"], "2026-09-10T17:30:00+03:00")

    def test_the_hall_is_blank_and_the_ticket_link_is_https(self):
        for s in self.shows.values():
            self.assertEqual(s["aud"], "")
            self.assertEqual(s["url"], f"https://korjaamokino.fi/websales/show/{s['url'].rsplit('/', 1)[1]}")
            self.assertEqual(s["theatre"], "Korjaamo Kino")
            self.assertEqual((s["img"], s["price"], s["soldOut"], s["provider"]),
                             ("", "", False, "korjaamo"))

    def test_the_festival_lands_in_method_with_the_client_separator(self):
        self.assertEqual(self.shows["5193"]["method"], "2D · HelAFF")
        self.assertEqual(self.shows["5202"]["method"], "2D")

    def test_languages(self):
        self.assertEqual(self.shows["5202"]["lang"], "FI-A")
        self.assertEqual(self.shows["5204"]["lang"], "FI-A, SV-S")
        # "useita kieliä" has no code and no tag; Arabic is mapped by its Finnish name.
        self.assertEqual(self.shows["5193"]["lang"], "EN-S, AR-S")

    def test_metadata(self):
        s = self.shows["5193"]
        self.assertEqual((s["title"], s["len"], s["genres"], s["original"]),
                         ("HelAFF: Fez Summer 55", "115", "Draama", "HelAFF: Fez Summer 55"))

    def test_synopses_strip_markup(self):
        self.assertEqual(vista.synopses(EVENTS),
                         {"5202": "Dokumentti kolmesta kesästä, jotka muuttivat kaiken.",
                          "5193": "Fez, kesä 1955."})
        self.assertEqual(vista.synopses("not xml"), {})


class StrandTest(unittest.TestCase):
    def test_the_festival_prefix_comes_off_a_feature(self):
        self.assertEqual(strands.split("HelAFF: Fez Summer 55"), ("Fez Summer 55", "HelAFF"))

    def test_a_short_programme_keeps_its_title(self):
        self.assertEqual(strands.split("HelAFF Short Films 1"), ("HelAFF Short Films 1", ""))

    def test_the_series_tag_is_not_doubled(self):
        s = {"title": "HelAFF: Fez Summer 55", "method": "2D · HelAFF"}
        self.assertTrue(strands.apply(s))
        self.assertEqual((s["title"], s["method"]), ("Fez Summer 55", "2D · HelAFF"))

    def test_the_strand_comes_off_the_original_title_too(self):
        """Gilda's shape: it publishes the strand in both fields, and only `title` was
        ever cleaned, so six shows carried "Seniorikino: ..." into the evidence
        `enrich_tmdb.gather()` reads."""
        s = {"title": "Seniorikino: Myrskyn Ikkuna",
             "original": "Seniorikino: Myrskyn Ikkuna", "method": ""}
        self.assertTrue(strands.apply(s))
        self.assertEqual(s["title"], "Myrskyn Ikkuna")
        self.assertEqual(s["original"], "Myrskyn Ikkuna")
        self.assertEqual(s["method"], "Seniorikino")

    def test_a_real_original_language_title_is_never_replaced_by_the_display_title(self):
        """The failure this must not become. `original` is the search's second query, so
        overwriting Regina's French title with the Finnish one would cost the match the
        original title exists to win."""
        s = {"title": "Lucky luke sotapolulla", "original": "La ballade des Dalton",
             "method": ""}
        self.assertFalse(strands.apply(s))
        self.assertEqual(s["original"], "La ballade des Dalton")

    def test_a_strand_on_a_real_original_leaves_the_rest_of_it_alone(self):
        s = {"title": "Seniorikino: Lucky luke sotapolulla",
             "original": "Seniorikino: La ballade des Dalton", "method": ""}
        self.assertTrue(strands.apply(s))
        self.assertEqual(s["title"], "Lucky luke sotapolulla")
        self.assertEqual(s["original"], "La ballade des Dalton")

    def test_an_original_nobody_published_stays_empty(self):
        s = {"title": "Seniorikino: Hetki", "original": "", "method": ""}
        self.assertTrue(strands.apply(s))
        self.assertEqual(s["original"], "")

    def test_a_strand_on_the_original_alone_is_still_split(self):
        """The title is clean and the original is not; the strand still has to come off
        the field the search reads, and the clean title must not gain a tag it never had."""
        s = {"title": "Myrskyn Ikkuna", "original": "Seniorikino: Myrskyn Ikkuna",
             "method": "Ensi-ilta"}
        self.assertTrue(strands.apply(s))
        self.assertEqual(s["original"], "Myrskyn Ikkuna")
        self.assertEqual((s["title"], s["method"]), ("Myrskyn Ikkuna", "Ensi-ilta"))

    def test_a_franchise_colon_is_not_a_strand_in_either_field(self):
        s = {"title": "Spider-Man: Brand New Day",
             "original": "Spider-Man: Brand New Day", "method": ""}
        self.assertFalse(strands.apply(s))
        self.assertEqual(s["original"], "Spider-Man: Brand New Day")


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._get, self._sleep = vista.get, vista.time.sleep
        self.addCleanup(lambda: setattr(vista, "get", self._get))
        self.addCleanup(lambda: setattr(vista.time, "sleep", self._sleep))
        vista.time.sleep = lambda s: None
        self.calls = []

    # The ticket page each screening links to, as vista.ordinary_price() reads it: one
    # unrestricted category. Served for every websales/show URL the run asks for.
    TICKET_PAGE = ('<html><body><ul class="ticket-list__list"><li class="ticket-list__item">'
                   '<p class="ticket-list__label bold">Normaali lippu</p>'
                   '<span class="ticket-list__price">13,00 €</span></li></ul></body></html>')

    def serve(self, pages):
        def get(url, tries=3, timeout=40):
            self.calls.append(url)
            page = pages.get(url)
            if isinstance(page, Exception):
                raise page
            if page is None and url.startswith(vista.SITES[0]["tickets"]):
                return self.TICKET_PAGE
            if page is None:
                raise RuntimeError(f"unexpected fetch {url}")
            return page
        vista.get = get

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["vista"])
        return code, out.getvalue() + err.getvalue()

    EVENTS_URL = f"{BASE}/xml/Events/"
    SCHEDULE_URL = f"{BASE}/xml/Schedule/?area=1007&nrOfDays=31"

    def test_a_full_run_publishes_the_venue(self):
        self.serve({self.EVENTS_URL: EVENTS, self.SCHEDULE_URL: SCHEDULE})
        code, log = self.main()
        self.assertEqual(code, 0, log)
        area = json.loads((run.OUT / "area-korjaamo-helsinki.json").read_text())
        venues = json.loads((run.OUT / "venues-korjaamo.json").read_text())
        self.assertEqual([s["title"] for s in area["shows"]],
                         ["Päivien lumo", "Presidentin Kyyditys", "Fez Summer 55"])
        fez = area["shows"][2]
        self.assertEqual((fez["rating"], fez["method"], fez["aud"]), ("", "2D · HelAFF", ""))
        self.assertNotIn("_syn", area["shows"][0])
        self.assertEqual(area["dates"], ["2026-09-07", "2026-09-10"])
        self.assertEqual(venues["venues"], [{"id": "korjaamo-helsinki", "name": "Korjaamo Kino",
                                            "short": "Korjaamo Kino", "city": "Helsinki"}])
        self.assertEqual((venues["status"], venues["stale"], venues["pending"]), ("ok", [], []))
        tickets = vista.SITES[0]["tickets"]
        self.assertEqual(self.calls[:2], [self.EVENTS_URL, self.SCHEDULE_URL])
        # Then one ticket page per screening, after the schedule, through the same getter.
        self.assertEqual(self.calls[2:], [s["url"] for s in area["shows"]])
        self.assertTrue(all(u.startswith(tickets) for u in self.calls[2:]))
        self.assertEqual([s["price"] for s in area["shows"]], ["13€"] * 3)
        self.assertTrue((run.OUT / "prices-korjaamo.json").exists())
        self.assertIn("prices: 3 screenings, 3 priced, 3 pages read", log)
        self.assertIn("Korjaamo Kino: 3 showtimes, 2 dates", log)
        self.assertIn("0 failures", log)

    def test_a_refused_schedule_fails_the_site_and_keeps_the_previous_file(self):
        prev = {"generated": "2026-09-01T00:00:00+00:00", "dates": ["2026-09-01"],
                "horizon": "2026-09-01", "shows": [{"title": "Old", "start": "2026-09-01T12:00:00+03:00"}]}
        (run.OUT / "area-korjaamo-helsinki.json").write_text(json.dumps(prev))
        self.serve({self.EVENTS_URL: EVENTS, self.SCHEDULE_URL: RuntimeError("HTTP Error 403: Forbidden")})
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", log)
        self.assertEqual(json.loads((run.OUT / "area-korjaamo-helsinki.json").read_text()), prev)
        self.assertFalse((run.OUT / "venues-korjaamo.json").exists())

    def test_missing_events_cost_synopses_and_not_the_schedule(self):
        self.serve({self.EVENTS_URL: RuntimeError("HTTP Error 500"), self.SCHEDULE_URL: SCHEDULE})
        code, log = self.main()
        self.assertEqual(code, 0, log)
        area = json.loads((run.OUT / "area-korjaamo-helsinki.json").read_text())
        self.assertEqual(len(area["shows"]), 3)
        self.assertIn("Events unavailable", log)


class SynopsisLanguageTest(unittest.TestCase):
    """Vista's Events feed carries one synopsis per film and no language field, yet ten
    Korjaamo texts in films-extra's Finnish slot were English. Each text is placed by
    `common.syn_language`, as Gilda's are, and one no language settles is withheld."""

    EN = ("A young woman returns to the town where she grew up and finds that the house of "
          "her childhood has been sold, and that the people she left behind have moved on "
          "without her.")
    FI = ("Nuori nainen palaa kotikaupunkiinsa ja huomaa, että hänen lapsuudenkotinsa on "
          "myyty ja että ihmiset, jotka hän jätti taakseen, ovat jatkaneet elämäänsä ilman "
          "häntä.")

    def run_site(self, events):
        self._get, self._sleep = vista.get, vista.time.sleep
        self.addCleanup(lambda: setattr(vista, "get", self._get))
        self.addCleanup(lambda: setattr(vista.time, "sleep", self._sleep))
        vista.time.sleep = lambda s: None
        pages = {f"{BASE}/xml/Events/": events,
                 f"{BASE}/xml/Schedule/?area=1007&nrOfDays=31": SCHEDULE}
        vista.get = lambda url, tries=3, timeout=40: pages[url]
        site = dict(SITE); site.pop("tickets", None)
        shows = [s for v in vista.fetch_site(site).values() for s in v]
        return {s["eventId"]: s.get("_syn") for s in shows}

    def events(self, first, second):
        return EVENTS.replace("&lt;p&gt;Dokumentti kolmesta kesästä, jotka muuttivat kaiken.&lt;/p&gt;",
                              first).replace("Fez, kesä 1955.", second)

    def test_each_synopsis_is_filed_in_its_own_language(self):
        syn = self.run_site(self.events(self.EN, self.FI))
        self.assertEqual(syn["5202"], {"en": self.EN})
        self.assertEqual(syn["5193"], {"fi": self.FI})

    def test_a_synopsis_no_language_settles_is_withheld(self):
        syn = self.run_site(self.events("Lyhyt.", self.FI))
        self.assertIsNone(syn["5202"])
        self.assertEqual(syn["5193"], {"fi": self.FI})


class RegistryAndPagesTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("korjaamo")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Korjaamo Kino", "korjaamokino.fi", "buy", "vista", "cloud"))
        # Moved from #C07E7E on 2026-09-21, when Helsinki reached ten chains and its
        # palette was solved jointly; the record is in docs/archive/2026-09-providers.md.
        self.assertEqual(p["accent"], "#80709C")
        self.assertEqual(sum(1 for q in registry.PROVIDERS if q["accent"] == p["accent"]), 1)
        self.assertEqual((VENUE["id"], VENUE["name"], VENUE["short"], VENUE["city"],
                          VENUE["theatre"], VENUE["area"]),
                         ("korjaamo-helsinki", "Korjaamo Kino", "Korjaamo Kino", "Helsinki",
                          "1045", "1007"))
        self.assertEqual(SITE["base"], BASE)
        self.assertEqual(bp.label_of({**VENUE, "provider": "korjaamo"}, {"korjaamo": "Korjaamo Kino"}),
                         "Korjaamo Kino")            # the chain prefix collapses, no doubling

    def test_the_committed_page_follows_the_theatre_template(self):
        """What holds whatever the programme is.

        The screening-shaped markers moved to TheatrePageTest below: whether the committed
        page carries a stub is a fact about the cinema's week, not about the generator.
        What is still asserted here is that the page is whole and internally consistent --
        screenings *and* the day and list markup that carry them, or no screenings and the
        line that says so. Half of one is the failure this exists for.
        """
        fi = (ROOT / "teatteri" / "korjaamo-kino-helsinki" / "index.html").read_text(encoding="utf-8")
        en = (ROOT / "en" / "theatre" / "korjaamo-kino-helsinki" / "index.html").read_text(encoding="utf-8")
        orion = (ROOT / "teatteri" / "cinema-orion-helsinki" / "index.html").read_text(encoding="utf-8")
        for page in (fi, en, orion):
            self.assertNotIn("Ei tiedossa", page)
        for marker in ('class="langseg"', 'class="cta"', '<p class="intro">',
                       'rel="canonical"'):
            self.assertIn(marker, fi)
            self.assertIn(marker, en)
            self.assertIn(marker, orion)
        self.assertEqual(fi.count("<style"), orion.count("<style"))
        for page, lang in ((fi, "fi"), (en, "en"), (orion, "fi")):
            with self.subTest(page=lang):
                if 'class="stub"' in page:
                    self.assertIn('<ul class="times">', page)
                    self.assertIn('<h2 class="day">', page)
                    self.assertNotIn(bp.L[lang]["no_shows"], page)
                else:
                    self.assertIn(bp.L[lang]["no_shows"], page)
                    self.assertNotIn('<ul class="times">', page)
                    self.assertNotIn('<h2 class="day">', page)

    def test_the_helsinki_city_page_lists_the_cinema(self):
        city = (ROOT / "kaupunki" / "helsinki" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Korjaamo Kino", city)
        self.assertIn("chain-korjaamo", city)


class TheatrePageTest(unittest.TestCase):
    """What a Vista screening renders, and what a page with nothing in its window does.

    Both used to be asserted against the committed page, which carries a stub only while
    Korjaamo happens to have a screening inside the four days `build_pages.DAYS` renders.
    On 2026-09-16 it did not -- its nearest was 2026-09-22, six days out -- so the test went
    red on a correct page built from data fetched twenty minutes earlier. The generator is
    what is under test, so it is driven here from fixture screenings at a fixed date, and
    both cases are covered rather than whichever one the week happens to supply.
    """

    TODAY = datetime.date(2026, 9, 16)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        (self.root / "data").mkdir()
        for p in (ROOT / "data").glob("*.json"):
            shutil.copy2(p, self.root / "data" / p.name)
        for name in ("ROOT", "DATA"):
            self.addCleanup(setattr, bp, name, getattr(bp, name))
        bp.ROOT, bp.DATA = self.root, self.root / "data"
        bp._unmirrored_hosts.clear()
        self.addCleanup(bp._unmirrored_hosts.clear)

    def row(self, n, day):
        """One screening meeting common.Show, blank where the page does not read it."""
        s = {k: ("" if typ is str else False)
             for k, typ in common.Show.__annotations__.items()}
        s.update(eventId=f"fixture-{n}", title=f"Fixture Film {n}", len="88",
                 rating="K-12", theatre="Korjaamo Kino", aud="Sali",
                 start=f"{day}T1{n}:30:00+03:00", lang="FI-A",
                 url=f"https://korjaamokino.fi/websales/show/{1000 + n}/",
                 provider="korjaamo", venue="korjaamo-helsinki")
        return s

    def korjaamo(self, *offsets):
        """Put Korjaamo's screenings this many days from the build date, then build.

        -> (the Finnish theatre page, the English one). Two screenings on two days, so a
        page rendering one film on one day is never what is being read.
        """
        rows = [self.row(n, (self.TODAY + datetime.timedelta(days=off)).isoformat())
                for n, off in enumerate(offsets)]
        days = sorted({s["start"][:10] for s in rows})
        area = self.root / "data" / "area-korjaamo-helsinki.json"
        doc = json.loads(area.read_text(encoding="utf-8"))
        doc.update(shows=rows, dates=days, horizon=days[-1])
        area.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            bp.main(today=self.TODAY)
        return tuple(
            (self.root / p / "korjaamo-kino-helsinki" / "index.html").read_text(encoding="utf-8")
            for p in ("teatteri", pathlib.Path("en") / "theatre"))

    def test_a_screening_in_the_window_renders_its_websales_ticket_link(self):
        fi, en = self.korjaamo(0, 2)
        for page, lang in ((fi, "fi"), (en, "en")):
            with self.subTest(page=lang):
                self.assertIn('href="https://korjaamokino.fi/websales/show/1000/', page)
                self.assertIn('href="https://korjaamokino.fi/websales/show/1001/', page)
                for marker in ('class="stub"', '<ul class="times">', '<h2 class="day">'):
                    self.assertIn(marker, page)
                self.assertNotIn(bp.L[lang]["no_shows"], page)

    def test_a_programme_beyond_the_window_still_renders_a_whole_page(self):
        """Korjaamo's real state on 2026-09-16, and a valid one: screenings published, none
        of them inside the four days the page renders. The page must say so and stay whole;
        what it must not do is go half-rendered or lose its own furniture."""
        fi, en = self.korjaamo(6, 20)
        for page, lang in ((fi, "fi"), (en, "en")):
            with self.subTest(page=lang):
                self.assertIn(bp.L[lang]["no_shows"], page)
                self.assertNotIn("websales/show/", page)
                for absent in ('class="stub"', '<ul class="times">', '<h2 class="day">'):
                    self.assertNotIn(absent, page)
                for marker in ('class="langseg"', 'class="cta"', '<p class="intro">',
                               'rel="canonical"', "Korjaamo Kino"):
                    self.assertIn(marker, page)

    def test_the_window_is_what_decides_between_the_two(self):
        """The same screening inside and outside it, so the difference is the date and
        nothing else. `DAYS` is today plus three."""
        inside, _ = self.korjaamo(bp.DAYS - 1)
        outside, _ = self.korjaamo(bp.DAYS)
        self.assertIn("websales/show/1000/", inside)
        self.assertNotIn("websales/show/1000/", outside)
        self.assertIn(bp.L["fi"]["no_shows"], outside)


if __name__ == "__main__":
    unittest.main()
