"""A site with nothing on must not fail the run; a broken parse still must.

A site parsing zero showtimes fails the run, which catches a silently broken parser. Eight
sites are a single small venue (K-Kino publishes 3 showtimes, Kino Saimaa 2), so a quiet
week must not turn the run red. The adapter has the information run.py lacks: an empty
listing is a cinema with no programme (`EmptyProgramme`); a listing full of films that
yields no showtimes is a broken parser and keeps failing.
"""
import datetime
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import common
import run


SITE = {
    "provider": "fakechain", "label": "Fake Chain",
    "venues": [{"id": "fc-a", "name": "Alpha", "short": "Alpha", "city": "Espoo"}],
}


TWO_VENUES = {
    "provider": "fakechain", "label": "Fake Chain",
    "venues": [{"id": "fc-a", "name": "Alpha", "short": "Alpha", "city": "Espoo"},
               {"id": "fc-b", "name": "Beta", "short": "Beta", "city": "Espoo"}],
}

PREV = {"generated": "2026-08-01T00:00:00+00:00", "dates": ["2026-08-02"],
        "horizon": "2026-08-02",
        "shows": [{"title": "Dyyni", "start": "2026-08-02T18:00:00+03:00"}]}


class Mod:
    __name__ = "fakemod"
    SITES = [SITE]

    def __init__(self, behaviour):
        self.behaviour = behaviour

    def fetch_site(self, site):
        if isinstance(self.behaviour, Exception):
            raise self.behaviour
        return self.behaviour


class EmptyProgrammeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._saved = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._saved))

    def run_mod(self, mod, site=None):
        if site is not None:
            mod.SITES = [site]
        import importlib
        real = importlib.import_module
        importlib.import_module = lambda name: mod if name == "fakemod" else real(name)
        self.addCleanup(lambda: setattr(importlib, "import_module", real))
        return run.main(["fakemod", "--half", "all"])

    def test_an_empty_listing_does_not_fail_the_run(self):
        code = self.run_mod(Mod(common.EmptyProgramme("listing lists no films")))
        self.assertEqual(code, 0)

    def test_a_listing_with_films_and_no_showtimes_still_fails(self):
        """The case the rule exists for. An adapter that parsed a full listing into
        nothing is broken, and must not be able to hide behind the same silence."""
        code = self.run_mod(Mod({"fc-a": []}))
        self.assertEqual(code, 1)

    def test_a_fetch_error_still_fails(self):
        code = self.run_mod(Mod(RuntimeError("connection reset")))
        self.assertEqual(code, 1)

    def test_an_empty_programme_publishes_every_venue_empty_and_pending(self):
        """The site answered that it has nothing on, so the record says so at once: fresh
        empty files and every venue pending, the state Heureka's paused programme takes."""
        self.run_mod(Mod(common.EmptyProgramme("nothing on")), TWO_VENUES)
        for vid in ("fc-a", "fc-b"):
            area = json.loads((run.OUT / f"area-{vid}.json").read_text(encoding="utf-8"))
            self.assertEqual((area["shows"], area["dates"]), ([], []))
        doc = json.loads((run.OUT / "venues-fakechain.json").read_text(encoding="utf-8"))
        self.assertEqual((doc["status"], doc["pending"], doc["stale"], doc["unverified"]),
                         ("ok", ["fc-a", "fc-b"], [], []))

    def test_a_confirmed_empty_single_venue_module_exits_0_and_publishes_the_empty_venue(self):
        """A module that vouches for emptiness and reports its one venue empty: the run is
        green, the area file is fresh and empty, the provider file lists the venue pending.
        The unconfirmed twin below keeps failing."""
        (run.OUT).mkdir(exist_ok=True)
        prev = {"generated": "2026-08-01T00:00:00+00:00", "dates": ["2026-08-02"],
                "horizon": "2026-08-02",
                "shows": [{"title": "Dyyni", "start": "2026-08-02T18:00:00+03:00"}]}
        (run.OUT / "area-fc-a.json").write_text(json.dumps(prev), encoding="utf-8")
        mod = Mod({"fc-a": []})
        mod.EMPTY_VENUES_CONFIRMED = True
        self.assertEqual(self.run_mod(mod), 0)
        area = json.loads((run.OUT / "area-fc-a.json").read_text(encoding="utf-8"))
        self.assertEqual(area["shows"], [])
        self.assertNotEqual(area["generated"], prev["generated"])
        venues = json.loads((run.OUT / "venues-fakechain.json").read_text(encoding="utf-8"))
        self.assertEqual((venues["status"], venues["pending"]), ("ok", ["fc-a"]))

    def test_a_confirming_module_that_reports_no_venue_still_fails(self):
        """The flag is not enough on its own: an empty answer that names no venue is
        unexplained, and stays a failure with the previous file untouched."""
        (run.OUT).mkdir(exist_ok=True)
        # A day ahead of the real clock: a kept file whose every day has passed is
        # published empty, and this is about one still worth keeping.
        ahead = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
        prev = {"generated": "2026-08-01T00:00:00+00:00", "dates": [ahead],
                "horizon": ahead,
                "shows": [{"title": "Dyyni", "start": f"{ahead}T18:00:00+03:00"}]}
        (run.OUT / "area-fc-a.json").write_text(json.dumps(prev), encoding="utf-8")
        mod = Mod({})
        mod.EMPTY_VENUES_CONFIRMED = True
        self.assertEqual(self.run_mod(mod), 1)
        self.assertEqual(json.loads((run.OUT / "area-fc-a.json").read_text(encoding="utf-8")), prev)
        doc = json.loads((run.OUT / "venues-fakechain.json").read_text(encoding="utf-8"))
        self.assertEqual((doc["status"], doc["stale"], doc["pending"]), ("partial", ["fc-a"], []))
        self.assertEqual(doc["oldest"], prev["generated"], "the record ages, it does not refresh")

    def test_a_module_with_no_sites_for_this_half_is_not_a_failure(self):
        """Site-level routing made this reachable: `run.py biorex --half local` has
        nothing to do and must say so with 0, not fail. Before routing, a run that
        produced no venues could only mean everything broke."""
        class CloudOnly(Mod):
            SITES = [SITE]
        mod = CloudOnly({"fc-a": []})
        import registry
        real = registry.by_id
        registry.by_id = lambda pid: ({"where": "cloud"} if pid == "fakechain"
                                      else real(pid))
        self.addCleanup(lambda: setattr(registry, "by_id", real))
        import importlib
        realimp = importlib.import_module
        importlib.import_module = lambda n: mod if n == "fakemod" else realimp(n)
        self.addCleanup(lambda: setattr(importlib, "import_module", realimp))
        self.assertEqual(run.main(["fakemod", "--half", "local"]), 0)

    def test_an_empty_programme_clears_screenings_the_cinema_withdrew(self):
        """Kept, the previous file went on offering screenings the cinema had taken down,
        ticket links included, for as long as the listing stayed empty. EmptyProgramme is
        raised only on the upstream's own empty state, so it is trusted like a confirmed
        empty venue. Both venues had data; neither may keep it."""
        (run.OUT).mkdir(exist_ok=True)
        for vid in ("fc-a", "fc-b"):
            (run.OUT / f"area-{vid}.json").write_text(json.dumps(PREV), encoding="utf-8")
        self.assertEqual(self.run_mod(Mod(common.EmptyProgramme("nothing on")), TWO_VENUES), 0)
        for vid in ("fc-a", "fc-b"):
            area = json.loads((run.OUT / f"area-{vid}.json").read_text(encoding="utf-8"))
            self.assertEqual(area["shows"], [])
            self.assertNotEqual(area["generated"], PREV["generated"])
        doc = json.loads((run.OUT / "venues-fakechain.json").read_text(encoding="utf-8"))
        self.assertEqual((doc["pending"], doc["stale"]), (["fc-a", "fc-b"], []))
        self.assertNotEqual(doc["oldest"], PREV["generated"])


class NexxoEmptyTest(unittest.TestCase):
    """Nexxo is where this case is not hypothetical: four hosts answer public_api.php
    with valid JSON and no shows at any locationid, permanently. The distinction the
    adapter has to make is between that and a request that never landed."""

    SITE = {"provider": "p", "base": "https://example.test", "programme": "/ohjelmisto/",
            "venues": [
                {"id": "a", "locationid": "1", "name": "A", "short": "A", "city": "X"},
                {"id": "b", "locationid": "2", "name": "B", "short": "B", "city": "Y"},
            ]}

    ROW = {"movieId": "9", "movieTitle": "Film", "roomId": 1, "roomTitle": "A",
           "startDate": "2026-09-02", "startTime": "2026-09-02 18:00:00"}

    def patch(self, fn):
        """The seam is fetch_payload, one call per locationid: room-split venues made
        fetch_site fetch a location once and parse it per venue, so patching the
        per-venue helper would leave the code under test talking to the network."""
        import nexxo
        real = nexxo.fetch_payload
        nexxo.fetch_payload = fn
        self.addCleanup(lambda: setattr(nexxo, "fetch_payload", real))
        return nexxo

    def test_every_locationid_answering_with_no_shows_is_an_empty_programme(self):
        nexxo = self.patch(lambda site, loc, **kw: {"shows": {}})
        with self.assertRaises(common.EmptyProgramme):
            nexxo.fetch_site(self.SITE, sleep=0)

    def test_a_failed_request_is_a_failure_not_an_empty_programme(self):
        """If a locationid never answered we do not know what the site holds, so this
        must stay a plain empty result and fail the run the way it always did."""
        def boom(site, loc, **kw):
            raise RuntimeError("403")
        nexxo = self.patch(boom)
        self.assertEqual(nexxo.fetch_site(self.SITE, sleep=0), {})

    def test_one_answering_and_one_failing_is_not_an_empty_programme(self):
        def half(site, loc, **kw):
            if loc == "1":
                return {"shows": {}}
            raise RuntimeError("403")
        nexxo = self.patch(half)
        self.assertEqual(nexxo.fetch_site(self.SITE, sleep=0), {"a": []})

    def test_any_showtime_anywhere_means_a_normal_result(self):
        nexxo = self.patch(lambda site, loc, **kw:
                           {"shows": {"d": [dict(self.ROW)]}} if loc == "1"
                           else {"shows": {}})
        out = nexxo.fetch_site(self.SITE, sleep=0)
        self.assertEqual(len(out["a"]), 1)


# --- eTiketti listing classification -------------------------------------------------
#
# Fixtures are minimal reconstructions of the shapes measured live on 2026-08-31, not
# copies of anyone's page: a populated listing wraps per-film cards in a movie-list
# container, and the one genuinely empty cinema renders a phrase there instead. Every
# site carries the hidden `no-results` container regardless, which is why it appears in
# these fixtures and is never the thing under test.

HIDDEN_NO_RESULTS = (
    '<div class="no-results" id="no-results" style="display: none;">'
    "<p>Ei näytöksiä valitsemallasi päivämäärällä.</p></div>")


def listing(cards="", extra=""):
    return ('<main><div class="screenings movie-list">' + cards + "</div>"
            + extra + HIDDEN_NO_RESULTS + "</main>")


def card(mid, slug, href=None):
    href = href if href is not None else f'href="/elokuvat/{mid}/{slug}"'
    return (f'<div class="item kemi date-1.9.2026 name-{slug}">'
            f"<a {href}>{slug}</a></div>")


POPULATED = listing(card(26, "hetki-ennen-valoa") + card(31, "autofiktio"))
GENUINELY_EMPTY = listing("<p>Ei ohjelmistoa saatavilla.</p>")
# Same two films, but the href shape changed upstream: an uppercase letter in the slug is
# enough for MOVIE_LINK_RE to match nothing while the cards are still there.
PARSER_BREAK = listing(card(26, "Hetki-Ennen-Valoa", href='href="/elokuvat/26/Hetki-Ennen-Valoa"')
                       + card(31, "Autofiktio", href='href="/elokuvat/31/Autofiktio"'))
FOREIGN_TEMPLATE = "<main><section><p>Tervetuloa</p></section></main>" + HIDDEN_NO_RESULTS
# The phrase in ordinary page copy rather than in the film container. Only the
# container check separates this from a real empty programme.
PHRASE_OUTSIDE_CONTAINER = (
    "<main><section><p>Kesällä ei ollut ohjelmistoa saatavilla.</p></section></main>"
    + HIDDEN_NO_RESULTS)

ETIKETTI_SITE = {"provider": "fakechain", "base": "https://example.test", "label": "Fake",
                 "venues": [{"id": "fc-a", "match": "kemi", "name": "A", "short": "A",
                             "city": "Kemi"}]}


class EtikettiListingTest(unittest.TestCase):
    """Zero movie links is not evidence of an empty programme."""

    def fetch(self, page):
        import etiketti
        real = etiketti.get
        etiketti.get = lambda url, tries=3: page
        self.addCleanup(lambda: setattr(etiketti, "get", real))
        return etiketti

    def test_the_templates_empty_state_is_an_empty_programme(self):
        e = self.fetch(GENUINELY_EMPTY)
        with self.assertRaises(common.EmptyProgramme):
            e.fetch_site(ETIKETTI_SITE, sleep=0)

    def test_a_listing_of_films_with_unreadable_links_is_not_empty(self):
        """The regression this guards. The cards are still on the page; only the href
        shape changed. Reading that as an empty programme exits 0, keeps stale data and
        says nothing -- which is the failure the zero-showtime rule exists to catch."""
        e = self.fetch(PARSER_BREAK)
        self.assertEqual(len(e.MOVIE_LINK_RE.findall(PARSER_BREAK)), 0,
                         "fixture must defeat the link regex, or it tests nothing")
        with self.assertRaises(Exception) as ctx:
            e.fetch_site(ETIKETTI_SITE, sleep=0)
        self.assertNotIsInstance(ctx.exception, common.EmptyProgramme)
        self.assertIn("parser break", str(ctx.exception))

    def test_a_response_without_the_film_container_is_not_empty(self):
        """Three live hosts carry the eTiketti signature and serve a different page
        entirely. No container means the expected listing never rendered."""
        e = self.fetch(FOREIGN_TEMPLATE)
        with self.assertRaises(Exception) as ctx:
            e.fetch_site(ETIKETTI_SITE, sleep=0)
        self.assertNotIsInstance(ctx.exception, common.EmptyProgramme)

    def test_the_hidden_no_results_container_is_not_an_empty_marker(self):
        """Every site ships it, populated ones included, hidden behind display:none for
        client-side date filtering. Treating its presence as emptiness would classify a
        broken parse as a quiet week on every host in the platform."""
        e = self.fetch(listing(""))          # container, no cards, no empty phrase
        with self.assertRaises(Exception) as ctx:
            e.fetch_site(ETIKETTI_SITE, sleep=0)
        self.assertNotIsInstance(ctx.exception, common.EmptyProgramme)
        self.assertIn("no evidence", str(ctx.exception))

    def test_the_phrase_in_a_hidden_sibling_is_not_an_empty_marker(self):
        """The failure mode this template is already one step away from. It ships a
        hidden `no-results` element on every site, populated ones included; if the empty
        state ever moves into one, a page-wide text search would call a live cinema
        empty. Everything is therefore asked of the container's own contents."""
        page = listing(card(26, "hetki-ennen-valoa"),
                       extra='<div style="display: none;"><p>Ei ohjelmistoa '
                             "saatavilla.</p></div>")
        # the cards are still there, but with links this parser cannot read
        page = page.replace('href="/elokuvat/26/hetki-ennen-valoa"',
                            'href="/elokuvat/26/Hetki-Ennen-Valoa"')
        e = self.fetch(page)
        self.assertEqual(len(e.MOVIE_LINK_RE.findall(page)), 0)
        with self.assertRaises(Exception) as ctx:
            e.fetch_site(ETIKETTI_SITE, sleep=0)
        self.assertNotIsInstance(ctx.exception, common.EmptyProgramme)
        self.assertIn("parser break", str(ctx.exception))

    def test_cards_outside_the_container_do_not_mask_a_genuine_empty_state(self):
        """The mirror of the case above: an unrelated `item` elsewhere on the page must
        not make a genuinely empty container look populated."""
        page = listing("<p>Ei ohjelmistoa saatavilla.</p>",
                       extra='<div class="item promo">Tulossa</div>')
        e = self.fetch(page)
        with self.assertRaises(common.EmptyProgramme):
            e.fetch_site(ETIKETTI_SITE, sleep=0)

    def test_the_phrase_outside_the_film_container_is_not_an_empty_marker(self):
        """Text anywhere on the page is not the template saying it has nothing on. The
        container check is the only thing separating this from a genuine empty state,
        and without it any page mentioning the words would silence a failure."""
        e = self.fetch(PHRASE_OUTSIDE_CONTAINER)
        with self.assertRaises(Exception) as ctx:
            e.fetch_site(ETIKETTI_SITE, sleep=0)
        self.assertNotIsInstance(ctx.exception, common.EmptyProgramme)
        self.assertIn("not the listing this parser reads", str(ctx.exception))

    def test_a_populated_listing_is_classified_normally(self):
        """The fixture the others are measured against: links readable, so the empty
        question never arises."""
        e = self.fetch(POPULATED)
        self.assertEqual(len(e.MOVIE_LINK_RE.findall(POPULATED)), 2)


class EtikettiThroughRunTest(unittest.TestCase):
    """The same distinction as run.py sees it: exit code and what happens to the data."""

    PREV = {"generated": "2026-08-01T00:00:00+00:00", "dates": ["2026-08-02"],
            "horizon": "2026-08-02",
            "shows": [{"title": "Dyyni", "start": "2026-08-02T18:00:00+03:00"}]}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._saved = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._saved))
        (run.OUT / "area-fc-a.json").write_text(json.dumps(self.PREV), encoding="utf-8")

    def run_with(self, page):
        import etiketti, importlib
        realget, realimp = etiketti.get, importlib.import_module
        etiketti.get = lambda url, tries=3: page
        mod = type("M", (), {"__name__": "fakemod", "SITES": [ETIKETTI_SITE],
                             "fetch_site": staticmethod(etiketti.fetch_site)})
        importlib.import_module = lambda n: mod if n == "fakemod" else realimp(n)
        self.addCleanup(lambda: setattr(etiketti, "get", realget))
        self.addCleanup(lambda: setattr(importlib, "import_module", realimp))
        return run.main(["fakemod", "--half", "all"])

    def test_a_genuine_empty_programme_exits_zero(self):
        self.assertEqual(self.run_with(GENUINELY_EMPTY), 0)

    def test_a_genuine_empty_programme_clears_the_previous_data(self):
        """The template's own empty state withdraws the old screenings: the file is
        rewritten empty and fresh, and the provider file names the venue pending."""
        self.run_with(GENUINELY_EMPTY)
        after = json.loads((run.OUT / "area-fc-a.json").read_text(encoding="utf-8"))
        self.assertEqual(after["shows"], [])
        self.assertNotEqual(after["generated"], self.PREV["generated"])
        doc = json.loads((run.OUT / "venues-fakechain.json").read_text(encoding="utf-8"))
        self.assertEqual((doc["status"], doc["pending"]), ("ok", ["fc-a"]))

    def test_a_parser_break_fails_the_run(self):
        self.assertEqual(self.run_with(PARSER_BREAK), 1)

    def test_a_parser_break_leaves_the_previous_data_untouched(self):
        self.run_with(PARSER_BREAK)
        after = json.loads((run.OUT / "area-fc-a.json").read_text(encoding="utf-8"))
        self.assertEqual(after, self.PREV)

    def test_a_fetch_error_still_fails(self):
        import etiketti
        real = etiketti.get
        def boom(url, tries=3):
            raise RuntimeError("connection reset")
        etiketti.get = boom
        self.addCleanup(lambda: setattr(etiketti, "get", real))
        import importlib
        realimp = importlib.import_module
        mod = type("M", (), {"__name__": "fakemod", "SITES": [ETIKETTI_SITE],
                             "fetch_site": staticmethod(etiketti.fetch_site)})
        importlib.import_module = lambda n: mod if n == "fakemod" else realimp(n)
        self.addCleanup(lambda: setattr(importlib, "import_module", realimp))
        self.assertEqual(run.main(["fakemod", "--half", "all"]), 1)


if __name__ == "__main__":
    unittest.main()
