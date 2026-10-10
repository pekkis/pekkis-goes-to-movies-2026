"""Kinotour: one card per screening on one page, and a venue set that moves.

The fixtures follow the card markup read on 2026-09-29, which replaced the Events Manager
table that day. What they exist to prove:

- **An undeclared town is ordinary, not a failure.** Every fixture that touches the town
  rule carries at least two towns, one this repo lists and one it does not, so the loop is
  exercised rather than the body alone. The count reaches the run log and the declared
  town still publishes.
- **The start is the `<time>` element's instant**, and the clock printed beside it has to
  agree with it.
- **The price is the card's one amount**, and the link is the listing, since the booking
  is a button on it.
"""
import contextlib
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import kinotour as K
import registry
import run


SITE = K.SITES[0]
LISTING = "https://www.kinotour.fi/varaa-liput-elokuvatapahtumiin/"


def card(title="Hetki ennen valoa", iso="2026-10-04T13:30:00+03:00", shown="4.10.2026 · klo 13.30",
         city="Naantali", place="Naantali · Kristoffer-sali", meta="87 min · K7",
         price="11,00 € <small>/ hlö</small>"):
    data_city = f' data-city="{city}"' if city is not None else ""
    return (f'<article class="kt-event"{data_city} data-type="indoor">'
            '<div class="kt-card-poster"><img src="https://www.kinotour.fi/p.jpg" alt=""></div>'
            '<div class="kt-event-main"><div class="kt-event-tags"><span class="kt-tag">'
            f'Kiertuenäytös</span></div><h3>{title}</h3>'
            f'<p class="kt-event-date"><time datetime="{iso}">{shown}</time></p>'
            f'<p class="kt-location">{place}</p><p class="kt-meta">{meta}</p>'
            '<details class="kt-details"><summary>Elokuvasta ja saapumisesta</summary>'
            '<p>Liput maksetaan kassalle. Eläkeläis ja opiskelija alennus -1€.</p></details>'
            f'</div><div class="kt-event-action"><strong>{price}</strong><button type="button" '
            'class="kt-primary kt-book" data-event="{&quot;id&quot;:3626}">Varaa liput</button>'
            '</div></article>')


def page(*cards):
    return ('<html><body><p class="kt-results">Kaikki paikkakunnat</p>'
            '<div class="kt-event-list">' + "".join(cards) + "</div></body></html>")


DECLARED = card()
UNDECLARED = card(title="Presidentin kyyditys", iso="2026-10-04T15:15:00+03:00",
                  shown="4.10.2026 · klo 15.15", city="Karkkila", place="Karkkila · Karkkilasali",
                  meta="87 min · K12")


class RowsTest(unittest.TestCase):
    def test_a_declared_town_publishes_and_an_undeclared_one_is_counted(self):
        per_venue, report = K.rows(SITE, page(DECLARED, UNDECLARED))
        self.assertEqual([s["title"] for s in per_venue["kinotour-naantali"]],
                         ["Hetki ennen valoa"])
        self.assertEqual(report["undeclared"], {"Karkkila": 1})

    def test_several_screenings_in_one_undeclared_town_are_counted_together(self):
        _, report = K.rows(SITE, page(UNDECLARED, UNDECLARED.replace("15.15", "17.15")
                                      .replace("T15:15", "T17:15"), DECLARED))
        self.assertEqual(report["undeclared"], {"Karkkila": 2})

    def test_each_declared_town_files_under_its_own_venue(self):
        per_venue, _ = K.rows(SITE, page(
            DECLARED, card(city="Kyrö", place="Kyrö · Kurkisali"),
            card(city="Lieto", place="Lieto · Valtuustosali")))
        self.assertEqual({k: len(v) for k, v in per_venue.items()},
                         {"kinotour-kyro": 1, "kinotour-naantali": 1, "kinotour-lieto": 1})

    def test_the_town_is_the_place_line_when_the_card_names_no_city(self):
        per_venue, _ = K.rows(SITE, page(card(city=None)))
        self.assertEqual(len(per_venue["kinotour-naantali"]), 1)

    def test_the_cards_city_wins_over_its_place_line(self):
        per_venue, _ = K.rows(SITE, page(card(place="Kristoffer-sali")))
        self.assertEqual(len(per_venue["kinotour-naantali"]), 1)

    def test_the_show_shape(self):
        per_venue, _ = K.rows(SITE, page(DECLARED))
        (s,) = per_venue["kinotour-naantali"]
        self.assertEqual((s["start"], s["title"], s["rating"], s["price"], s["len"], s["url"]),
                         ("2026-10-04T13:30:00+03:00", "Hetki ennen valoa", "K-7", "11\u20ac", "",
                          LISTING))
        self.assertEqual((s["theatre"], s["venue"], s["provider"]),
                         ("Kristoffersali", "kinotour-naantali", "kinotour"))

    def test_an_instant_given_in_another_zone_is_published_in_helsinki(self):
        per_venue, _ = K.rows(SITE, page(card(iso="2026-10-04T10:30:00+00:00")))
        self.assertEqual(per_venue["kinotour-naantali"][0]["start"], "2026-10-04T13:30:00+03:00")

    def test_a_printed_clock_that_disagrees_with_the_instant_fails_the_site(self):
        with self.assertRaises(K.RowError):
            K.rows(SITE, page(card(shown="4.10.2026 · klo 16.30")))

    def test_a_card_with_no_readable_start_fails_the_site(self):
        for bad in (card(iso="lauantaina"), card(iso="2026-10-04T13:30:00"),
                    DECLARED.replace("<time", "<span").replace("</time>", "</span>")):
            with self.subTest(card=bad[:0]), self.assertRaises(K.RowError):
                K.rows(SITE, page(bad))

    def test_a_card_that_names_no_place_fails_the_site(self):
        with self.assertRaises(K.RowError):
            K.rows(SITE, page(card(city=None, place="")))

    def test_a_card_with_no_title_fails_the_site(self):
        with self.assertRaises(K.RowError):
            K.rows(SITE, page(card(title="")))


class PriceTest(unittest.TestCase):
    def test_the_cards_one_amount(self):
        self.assertEqual(K.price_of("11,00 € <small>/ hlö</small>"), "11\u20ac")
        self.assertEqual(K.price_of("8,50 €"), "8.5\u20ac")
        self.assertEqual(K.price_of("€12"), "12\u20ac")

    def test_two_different_amounts_or_none_settle_nothing(self):
        self.assertEqual(K.price_of("11,00 € / 9,00 €"), "")
        self.assertEqual(K.price_of("Vapaa pääsy"), "")

    def test_a_card_without_an_amount_publishes_no_price(self):
        per_venue, _ = K.rows(SITE, page(card(price="Liput ovelta")))
        self.assertEqual(per_venue["kinotour-naantali"][0]["price"], "")


class RunnerTest(unittest.TestCase):
    PREV = {"generated": "2026-09-01T00:00:00+00:00", "dates": ["2026-09-01"],
            "horizon": "2026-09-01",
            "shows": [{"title": "Old", "start": "2026-09-01T12:00:00+03:00"}]}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._fetch = K.fetch
        self.addCleanup(lambda: setattr(K, "fetch", self._fetch))
        self.calls = []

    def serve(self, body):
        def fetch(url, **kw):
            self.calls.append(url)
            if isinstance(body, Exception):
                raise body
            return body.encode("utf-8")
        K.fetch = fetch

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["kinotour"])
        return code, out.getvalue() + err.getvalue()

    def test_the_run_publishes_from_one_request_and_names_the_undeclared_town(self):
        self.serve(page(DECLARED, UNDECLARED))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertEqual(self.calls, [LISTING])
        shows = json.loads((run.OUT / "area-kinotour-naantali.json").read_text())["shows"]
        self.assertEqual([(s["title"], s["price"]) for s in shows], [("Hetki ennen valoa", "11\u20ac")])
        self.assertIn("Karkkila (1)", log)
        self.assertIn("does not list", log)
        self.assertIn("0 failures", log)

    def test_a_declared_town_the_page_does_not_mention_is_published_empty(self):
        """The page is the whole programme, so a town it does not mention has nothing on,
        once a card filed under another declared town shows the town key reads.
        `EMPTY_VENUES_CONFIRMED` turns that into a fresh empty file rather than a last
        visit ageing for weeks. The page here has no undeclared card: see the next test."""
        (run.OUT / "area-kinotour-kyro.json").write_text(json.dumps(self.PREV))
        self.serve(page(DECLARED))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertIn("no programme at the moment", log)
        body = json.loads((run.OUT / "area-kinotour-kyro.json").read_text())
        self.assertEqual(body["shows"], [])
        self.assertNotEqual(body["generated"], self.PREV["generated"])

    def test_an_undeclared_town_card_vouches_no_declared_town_empty(self):
        """A card filed under an undeclared town may be a declared town's screening under a
        place that reads differently, so the empty town keeps its previous file, as
        eTiketti, Nexxo and Alatalo do (audit A3, 2026-09-25)."""
        future = {**self.PREV, "dates": ["2027-01-09"], "horizon": "2027-01-09",
                  "shows": [{"title": "Old", "start": "2027-01-09T12:00:00+02:00"}]}
        (run.OUT / "area-kinotour-kyro.json").write_text(json.dumps(future))
        self.serve(page(card(city="Pöytyä", place="Pöytyä · Kurkisali"), DECLARED))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertEqual(json.loads((run.OUT / "area-kinotour-kyro.json").read_text()), future)
        self.assertNotIn("Kyrö: no programme at the moment", log)
        self.assertIn("no declared town is confirmed empty", log)
        shows = json.loads((run.OUT / "area-kinotour-naantali.json").read_text())["shows"]
        self.assertEqual([s["title"] for s in shows], ["Hetki ennen valoa"])

    def test_a_page_of_nothing_but_undeclared_towns_fails_and_keeps_the_previous_file(self):
        """No card filed under a declared town is also what a town key that stopped
        reading produces, so it says nothing about the declared towns being empty."""
        (run.OUT / "area-kinotour-kyro.json").write_text(json.dumps(self.PREV))
        self.serve(page(UNDECLARED, card(city="Ikaalinen", place="Ikaalinen · tori")))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("Ikaalinen (1), Karkkila (1)", log)
        self.assertEqual(json.loads(
            (run.OUT / "area-kinotour-kyro.json").read_text()), self.PREV)

    def test_a_town_key_that_stopped_reading_fails_the_site(self):
        """Every card is a declared town's screening and the key reads none of them: the
        city attribute gone and the hall first on the place line."""
        (run.OUT / "area-kinotour-kyro.json").write_text(json.dumps(self.PREV))
        self.serve(page(card(city=None, place="Kristoffer-sali · Naantali"),
                        card(city=None, place="Kurkisali · Kyrö")))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertEqual(json.loads(
            (run.OUT / "area-kinotour-kyro.json").read_text()), self.PREV)

    def test_a_page_with_no_card_fails_and_keeps_the_previous_file(self):
        """The Events Manager table this adapter read until 2026-09-29 is such a page."""
        (run.OUT / "area-kinotour-kyro.json").write_text(json.dumps(self.PREV))
        self.serve('<table class="events-table"><tr><td>la 19.09.2026<br />14:00</td>'
                   '<td><a href="https://www.kinotour.fi/events/x/">Pirjo, K12</a></td></tr></table>')
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("no evidence of one", log)
        self.assertEqual(json.loads(
            (run.OUT / "area-kinotour-kyro.json").read_text()), self.PREV)

    def test_a_refused_page_keeps_the_previous_file(self):
        (run.OUT / "area-kinotour-kyro.json").write_text(json.dumps(self.PREV))
        self.serve(RuntimeError("HTTP Error 503"))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertEqual(json.loads(
            (run.OUT / "area-kinotour-kyro.json").read_text()), self.PREV)


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("kinotour")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Kinotour", "kinotour.fi", "buy", "kinotour", "cloud"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"] == p["accent"]), 1)

    def test_every_venue_declares_the_town_it_is_matched_on(self):
        """The town is the key, because the hall changes while the tour returns."""
        for v in SITE["venues"]:
            with self.subTest(venue=v["id"]):
                self.assertTrue(v["town"])
                self.assertEqual(v["city"], v["town"])
                self.assertNotIn(v["town"], v["name"])

    def test_the_site_names_the_host_it_reads(self):
        self.assertEqual([s["base"] for s in K.SITES], ["https://www.kinotour.fi"])
        self.assertEqual(len(run.host_groups(K.SITES)), 1)


if __name__ == "__main__":
    unittest.main()
