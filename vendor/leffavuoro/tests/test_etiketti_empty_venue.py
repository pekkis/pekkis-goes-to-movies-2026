"""An eTiketti venue with no screening row is confirmed empty only on evidence (2026-09-13).

Cine Nikkilä's programme ended and the provider read "not updated" on its past shows,
because eTiketti never vouched for an empty venue and run.py kept the previous file on
every run. Now the adapter reports a rowless venue as an empty list when the listing's
theatre navigation names it and the read left nothing unexplained. Fixtures are Cine's
shape in the Kotka template: the town is the place line and the cinema is the room.
"""
import functools
import io
import json
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout

import _ctx                                                # noqa: F401
import common                                              # noqa: F401
from test_etiketti_templates import HIDDEN, Stubbed as StubbedGet, listing, load
from test_etiketti_templates import site as site_of


def site():
    return site_of("cine")


NAV = ('<div class="footer-nav"><ul><li><a href="/teatterit">Teatterit</a><ul>'
       '<li><a href="/teatterit/mantsala">Cine Mäntsälä</a></li>'
       '<li><a href="/teatterit/keuda-talo">Cine Keuda-Talo</a></li>'
       '<li><a href="/teatterit/nikkila">Cine Nikkilä</a></li>'
       '<li><a href="/teatterit/kiertue">Kiertuenäytökset</a></li></ul></li></ul></div>')
NAV_WITHOUT_NIKKILA = NAV.replace('<li><a href="/teatterit/nikkila">Cine Nikkilä</a></li>', "")
PROSE = '<ul><li><a href="/esitysjaksot">Esitysjaksot Keravalla ja Nikkilässä</a></li></ul>'


def cine_listing(*paths, nav=NAV):
    """Cine's listing: the film cards, then the footer prose and the theatre navigation.
    The prose is always there, so every fetch test also proves it identifies nothing."""
    return listing(*paths, nav=PROSE + nav)


def item(day, hhmm, place, room, sid):
    return (f'<div class="item kerava date-{day}.9.2026"> <div> <p> <strong><span>KE {day}.9. klo {hhmm}'
            f"</span></strong> </p> <p> {place} | {room}<br /> Lippu 12,00&euro;<br /> "
            f'Vapaat paikat 40/120 </p> </div> <div> <a class="button-screening" href="/salikartta?id={sid}">'
            " Osta tai varaa </a> </div> </div>")


def film(*items):
    return ("<main><h1>Hetki ennen valoa</h1><h2>Näytökset</h2>"
            f'<div class="screenings">{HIDDEN}{"".join(items)}</div></main>')


KEUDA_FILM = film(item(17, "18.00", "KERAVA", "CINE KEUDA-TALO", 901),
                  item(18, "18.00", "KERAVA", "CINE KEUDA-TALO", 902))
MANTSALA_FILM = film(item(17, "19.00", "MÄNTSÄLÄ", "CINE MÄNTSÄLÄ", 903))
# Keuda's page with the clock gone from both of its screening blocks. `klo 18.00` is what
# TIME_RE reads, so this is the template moving under the parser: the blocks are still
# there and not one of them produces a row.
DRIFTED_FILM = KEUDA_FILM.replace(" klo 18.00", "")
# Keuda's page with its screening blocks renamed off ITEM_RE: the two screenings are still
# on the page, every word of them, and the parser sees no block at all, so nothing counts
# as skipped either.
BLOCKLESS_FILM = KEUDA_FILM.replace('<div class="item ', '<div class="screening-item ')


class Stubbed(StubbedGet):
    def fetch(self, mapping):
        return self.stub(mapping).fetch_site(site(), sleep=0)

    def fetch_logged(self, mapping):
        buf = io.StringIO()
        with redirect_stdout(buf):
            out = self.fetch(mapping)
        return out, buf.getvalue()


class ConfirmedEmptyTest(Stubbed):

    def test_the_module_vouches_for_the_venues_it_returns_empty(self):
        self.assertTrue(load().EMPTY_VENUES_CONFIRMED)

    def test_a_rowless_venue_named_by_the_navigation_comes_back_empty(self):
        out = self.fetch({"/elokuvat/ohjelmistossa": cine_listing("/elokuvat/13/hetki"),
                          "/elokuvat/13/hetki": KEUDA_FILM})
        self.assertEqual(sorted(out), ["cine-keuda", "cine-nikkila"])
        self.assertEqual(out["cine-nikkila"], [])
        self.assertEqual([s["start"] for s in out["cine-keuda"]],
                         ["2026-09-17T18:00:00+03:00", "2026-09-18T18:00:00+03:00"])
        self.assertEqual(out["cine-keuda"][0]["theatre"], "Cine Keuda-Talo")

    def test_a_film_page_that_failed_to_fetch_fails_the_site(self):
        """Changed 2026-09-25 (audit A11): this pinned Keuda publishing its other film's
        rows. The screenings are on the film pages, so a page that did not answer is a
        venue publishing part of its day, and which venues that film plays at is on the
        page that failed. `budget_or_raise` states the rule: a partial schedule is worse
        than none, and run.py keeps every previous file when the site fails."""
        with self.assertRaisesRegex(RuntimeError, "movie 21"):
            self.fetch({"/elokuvat/ohjelmistossa": cine_listing("/elokuvat/13/hetki", "/elokuvat/21/myrsky"),
                        "/elokuvat/13/hetki": KEUDA_FILM,
                        "/elokuvat/21/myrsky": RuntimeError("HTTP 503")})

    def test_a_row_for_a_place_nobody_registered_leaves_the_venue_unconfirmed(self):
        """A renamed venue looks exactly like an unregistered place, and the navigation
        naming that place deliberately does not excuse it: Cine's navigation names Cine
        Mäntsälä, and a `match` rotted off a registered venue would drop that venue's rows
        onto a navigation-named place in exactly the same way. The log says which place
        withheld the confirmation, which is otherwise invisible."""
        out, log = self.fetch_logged(
            {"/elokuvat/ohjelmistossa": cine_listing("/elokuvat/13/hetki", "/elokuvat/2/prima"),
             "/elokuvat/13/hetki": KEUDA_FILM,
             "/elokuvat/2/prima": MANTSALA_FILM})
        self.assertEqual(sorted(out), ["cine-keuda"])
        self.assertIn("MÄNTSÄLÄ", log)
        self.assertIn("no venue of this site is confirmed empty", log)

    def test_a_venue_the_navigation_does_not_name_is_not_identified(self):
        out = self.fetch({"/elokuvat/ohjelmistossa": cine_listing("/elokuvat/13/hetki", nav=NAV_WITHOUT_NIKKILA),
                          "/elokuvat/13/hetki": KEUDA_FILM})
        self.assertEqual(sorted(out), ["cine-keuda"])

    def test_a_page_whose_blocks_lost_their_time_vouches_for_no_venue(self):
        """The failure EMPTY_VENUES_CONFIRMED makes dangerous: a parse that stops reading
        screening blocks leaves every venue rowless, which is indistinguishable from a
        chain with nothing on. Both venues are named by the navigation, so without the
        guard both would come back confirmed empty."""
        out = self.fetch({"/elokuvat/ohjelmistossa": cine_listing("/elokuvat/13/hetki"),
                          "/elokuvat/13/hetki": DRIFTED_FILM})
        self.assertEqual(out, {}, "a drifted screening pattern confirms nothing")

    def test_a_page_whose_blocks_the_parser_no_longer_finds_vouches_for_no_venue(self):
        """The same drift one step earlier: the block pattern itself stops matching, so the
        page yields no row and no skipped block. Both venues are named by the navigation,
        and a film page that produced no row is no evidence that either has nothing on."""
        self.assertEqual(load().parse_movie(BLOCKLESS_FILM, site(), "/elokuvat/13/hetki")[0], [],
                         "fixture must defeat ITEM_RE, or it tests nothing")
        self.assertIn("CINE KEUDA-TALO", BLOCKLESS_FILM)
        out = self.fetch({"/elokuvat/ohjelmistossa": cine_listing("/elokuvat/13/hetki"),
                          "/elokuvat/13/hetki": BLOCKLESS_FILM})
        self.assertEqual(out, {}, "a page with no block found confirms nothing")

    def test_a_blockless_page_beside_a_readable_one_publishes_rows_and_confirms_nothing(self):
        out, log = self.fetch_logged({"/elokuvat/ohjelmistossa": cine_listing("/elokuvat/13/hetki",
                                                                              "/elokuvat/21/myrsky"),
                                      "/elokuvat/13/hetki": KEUDA_FILM,
                                      "/elokuvat/21/myrsky": BLOCKLESS_FILM})
        self.assertEqual(sorted(out), ["cine-keuda"])
        self.assertEqual(len(out["cine-keuda"]), 2)
        self.assertIn("movie 21: no screening row", log)

    def test_one_unreadable_block_beside_a_readable_one_is_not_drift(self):
        """Where the line sits, and why it is not "any skipped block": a page that still
        produced a row is a page this parser reads, so a single odd block does not
        withhold the confirmation. nexxo.py draws it in the same place."""
        mixed = film(item(17, "18.00", "KERAVA", "CINE KEUDA-TALO", 901),
                     item(18, "18.00", "KERAVA", "CINE KEUDA-TALO", 902).replace(" klo 18.00", ""))
        out = self.fetch({"/elokuvat/ohjelmistossa": cine_listing("/elokuvat/13/hetki"),
                          "/elokuvat/13/hetki": mixed})
        self.assertEqual(sorted(out), ["cine-keuda", "cine-nikkila"])
        self.assertEqual(len(out["cine-keuda"]), 1)

    def test_a_drifted_page_beside_a_readable_one_still_publishes_the_rows_it_read(self):
        """Disqualifying the read is not failing the site: Keuda's rows are real and get
        published, and only the empty-venue confirmation is withheld."""
        out = self.fetch({"/elokuvat/ohjelmistossa": cine_listing("/elokuvat/13/hetki",
                                                                  "/elokuvat/21/myrsky"),
                          "/elokuvat/13/hetki": KEUDA_FILM,
                          "/elokuvat/21/myrsky": DRIFTED_FILM})
        self.assertEqual(sorted(out), ["cine-keuda"])
        self.assertEqual(len(out["cine-keuda"]), 2)

    def test_prose_naming_the_town_identifies_nothing(self):
        e = load()
        self.assertEqual(e.identified_venues(PROSE + NAV_WITHOUT_NIKKILA, site()), {"cine-keuda"})
        self.assertEqual(e.identified_venues(PROSE, site()), set())
        self.assertEqual(e.identified_venues(NAV, site()), {"cine-keuda", "cine-nikkila"})


class NavigationAnchorTest(unittest.TestCase):
    """What an anchor has to look like to identify a venue. Measured 2026-09-14 across the
    20 hosts: 6 render `/teatterit/` anchors, naming all 10 of their registered venues."""

    def test_an_anchor_carrying_other_attributes_still_identifies(self):
        """A class on the anchor would otherwise stop identification with no symptom: the
        venue silently goes back to reading "not updated" for as long as it is empty."""
        nav = ('<a class="theatre-link" href="/teatterit/keuda-talo" title="x">Cine Keuda-Talo</a>'
               '<a href="/teatterit/nikkila" class="theatre-link">Cine Nikkilä</a>')
        self.assertEqual(load().identified_venues(nav, site()), {"cine-keuda", "cine-nikkila"})

    def test_the_town_printed_in_front_of_the_cinema_still_identifies_it(self):
        """Leffabuumi's anchors name the town with the cinema, as its screening rows do.
        Compared whole, its three venues identified as none."""
        nav = ('<a href="/teatterit/kinolinna">Mikkeli Kinolinna</a>'
               '<a href="/teatterit/ritz">Mikkeli Ritz</a>'
               '<a href="/teatterit/kino-saimaa">Puumala Kino Saimaa</a>')
        self.assertEqual(load().identified_venues(nav, site_of("leffabuumi")),
                         {"lb-kinolinna", "lb-ritz", "lb-saimaa"})

    def test_a_link_that_is_not_the_theatre_navigation_identifies_nothing(self):
        """The evidence is the site listing the venue as one of its theatres. A link that
        merely prints the name -- a campaign page, a news item -- is not that."""
        nav = '<a href="/esitysjaksot/nikkila">Cine Nikkilä</a>'
        self.assertEqual(load().identified_venues(nav, site()), set())

    def test_a_venue_no_anchor_names_is_still_not_identified(self):
        """The substring is looked for in the anchor, not the anchor in the venue."""
        nav = '<a href="/teatterit/keuda-talo">Cine Keuda-Talo</a>'
        self.assertEqual(load().identified_venues(nav, site()), {"cine-keuda"})


class RunSiteTest(Stubbed):
    """What run.py writes for the two venues, from a previous Nikkilä file with past shows."""

    PREV = {"generated": "2026-09-13T11:10:39+00:00", "dates": ["2026-09-13"], "horizon": "2026-09-13",
            "shows": [{"title": "Hetki ennen valoa", "start": "2026-09-13T15:00:00+03:00"},
                      {"title": "Presidentin kyyditys", "start": "2026-09-13T16:45:00+03:00"}]}
    NOW = "2026-09-13T20:10:00+00:00"

    def setUp(self):
        import run
        self.run = run
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        saved = run.OUT
        run.OUT = pathlib.Path(tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", saved))
        (run.OUT / "area-cine-nikkila.json").write_text(json.dumps(self.PREV), encoding="utf-8")

    def run_site(self, mapping):
        e = self.stub(mapping)
        # run.py calls fetch_site with the module's own pacing sleep, 1.2 s per film page.
        # That is what a cinema sees on a real run and pure wall clock here.
        real = e.fetch_site
        e.fetch_site = functools.partial(real, sleep=0)
        self.addCleanup(lambda: setattr(e, "fetch_site", real))
        return self.run.run_site(e, site(), self.NOW)

    def read(self, name):
        return json.loads((self.run.OUT / name).read_text(encoding="utf-8"))

    def test_a_confirmed_empty_nikkila_gets_a_fresh_empty_file_and_the_provider_is_fresh(self):
        live, total, stale, unverified, pending = self.run_site(
            {"/elokuvat/ohjelmistossa": cine_listing("/elokuvat/13/hetki"), "/elokuvat/13/hetki": KEUDA_FILM})
        self.assertEqual((live, total, stale, unverified, pending), (1, 2, [], [], ["cine-nikkila"]))
        nik = self.read("area-cine-nikkila.json")
        self.assertEqual((nik["generated"], nik["shows"], nik["dates"]), (self.NOW, [], []))
        keuda = self.read("area-cine-keuda.json")
        self.assertEqual(len(keuda["shows"]), 2)
        prov = self.read("venues-cine.json")
        self.assertEqual((prov["status"], prov["oldest"], prov["pending"]), ("ok", self.NOW, ["cine-nikkila"]))

    def test_an_uncertain_read_keeps_the_previous_file_and_the_old_stamp(self):
        """The keep-previous branch never advances the stamp, so without confirmation
        the provider stays "not updated" for as long as the venue has no row. The read is
        uncertain through a row for an unregistered place; a film page that fails to
        fetch fails the site since 2026-09-25, below."""
        live, total, stale, unverified, pending = self.run_site(
            {"/elokuvat/ohjelmistossa": cine_listing("/elokuvat/13/hetki", "/elokuvat/2/prima"),
             "/elokuvat/13/hetki": KEUDA_FILM, "/elokuvat/2/prima": MANTSALA_FILM})
        self.assertEqual((stale, pending), (["cine-nikkila"], []))
        self.assertEqual(self.read("area-cine-nikkila.json"), self.PREV)
        prov = self.read("venues-cine.json")
        self.assertEqual((prov["status"], prov["oldest"]), ("partial", self.PREV["generated"]))

    def test_a_film_page_that_fails_keeps_every_previous_file(self):
        """Keuda's other film did not answer: publishing Keuda's rows from the page that
        did would be part of its day, so nothing is written."""
        (self.run.OUT / "area-cine-keuda.json").write_text(json.dumps(self.PREV), encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.run_site({"/elokuvat/ohjelmistossa": cine_listing("/elokuvat/13/hetki", "/elokuvat/21/myrsky"),
                           "/elokuvat/13/hetki": KEUDA_FILM,
                           "/elokuvat/21/myrsky": RuntimeError("HTTP 503")})
        self.assertEqual(self.read("area-cine-keuda.json"), self.PREV)
        self.assertEqual(self.read("area-cine-nikkila.json"), self.PREV)


class DriftedParseTest(RunSiteTest):
    """The same drift through run.py, with a previous file for both venues."""

    def setUp(self):
        super().setUp()
        (self.run.OUT / "area-cine-keuda.json").write_text(json.dumps(self.PREV), encoding="utf-8")

    def test_a_drifted_parse_keeps_both_files_and_leaves_the_site_failing(self):
        live, total, stale, unverified, pending = self.run_site(
            {"/elokuvat/ohjelmistossa": cine_listing("/elokuvat/13/hetki"),
             "/elokuvat/13/hetki": DRIFTED_FILM})
        self.assertEqual((live, total, unverified, pending), (0, 0, [], []))
        self.assertEqual(sorted(stale), ["cine-keuda", "cine-nikkila"])
        self.assertEqual(self.read("area-cine-keuda.json"), self.PREV)
        self.assertEqual(self.read("area-cine-nikkila.json"), self.PREV)
        # No live venue and nothing confirmed empty is the run's failure condition, and
        # the provider file records both venues stale on the previous stamp, so the health
        # line reads degraded at once rather than waiting for the age to cross STALE_H.
        self.assertFalse(self.run.confirmed_empty_site(site(), pending))
        doc = json.loads((self.run.OUT / "venues-cine.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["status"], "partial")
        self.assertEqual(sorted(doc["stale"]), ["cine-keuda", "cine-nikkila"])
        self.assertEqual(doc["oldest"], self.PREV["generated"])

    def test_a_page_with_no_block_found_keeps_both_files_and_leaves_the_site_failing(self):
        live, total, stale, unverified, pending = self.run_site(
            {"/elokuvat/ohjelmistossa": cine_listing("/elokuvat/13/hetki"),
             "/elokuvat/13/hetki": BLOCKLESS_FILM})
        self.assertEqual((live, total, unverified, pending), (0, 0, [], []))
        self.assertEqual(sorted(stale), ["cine-keuda", "cine-nikkila"])
        self.assertEqual(self.read("area-cine-keuda.json"), self.PREV)
        self.assertEqual(self.read("area-cine-nikkila.json"), self.PREV)
        self.assertFalse(self.run.confirmed_empty_site(site(), pending))


if __name__ == "__main__":
    unittest.main()
