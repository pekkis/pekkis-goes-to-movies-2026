"""The Localhub reader: one search request, one page per film, one row per date.

The fixtures are the payload's shape as read on 2026-09-21, cut to the smallest form that
still exercises a rule. Two pages and two dates everywhere there is a loop.

What they exist to prove:

- **Two independent things have to agree before a page publishes**: the `Movies / Cinema`
  category and the search term in `hashtags`. The calendar is the whole town's, so a
  concert in the same hall matches the hall and must not publish.
- **A page with no date is the calendar's own parent** and is skipped on the empty `dates`
  rather than on its event-level sold-out flag, which all three live parents carried.
- **`start` is a UTC instant and the published row is Helsinki local.** The three-hour
  offset is the fault that would otherwise ship every screening at the wrong time.
- **A cancelled screening is not published at all**, because the show contract carries
  `soldOut` and no cancelled state.
- **Sold out is per date, with the event-level flag as the fallback.**
- **`end - start` is a booking slot**, so `len` stays empty whatever the payload says.
- **An empty search is not evidence of an empty programme**, so the site fails and the
  previous files stand.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import localhub as L
import registry
import run


SITE = L.SITES[0]
VENUE = SITE["venues"][0]["id"]
LOC = SITE["venues"][0]["loc"]
SEARCH = L.search_url(SITE)
TODAY = datetime.date(2026, 9, 21)
SHOP = "https://verkkokauppa.ylivieska.fi/tuote"


def date(start="2026-09-22T16:00:00.000Z", end="2026-09-22T18:00:00.000Z",
         sold=False, cancelled=False, ticket=None):
    return {"start": start, "end": end, "info": "", "isSoldOut": sold,
            "isCancelled": cancelled, "useQueue": False,
            "urlPurchaseTicket": ticket, "urlSignUp": None}


def page(pid="6a8dd2e4b7dae104a158d8ac", name="Resident Evil (2026)", dates=None,
         categories=("Movies / Cinema", "Adults"), hashtags=("kinoakustiikka",),
         price=None, timezone="Europe/Helsinki", address=LOC,
         ticket=f"{SHOP}/resident-evil-2026", sold=False, cancelled=False,
         short="Zach Creggerin uudelleentulkinta Resident Evil -elokuvasarjasta.",
         long_=""):
    return {
        "_id": pid,
        "name": name,
        "descriptionShort": short,
        "descriptionLong": long_,
        "globalContentCategories": list(categories),
        "hashtags": list(hashtags),
        "price": {"min": 12, "max": 12, "currency": "EUR"} if price is None else price,
        "locations": [{"address": address, "country": "FI"}] if address else [],
        "imageDesktop": "19a65113691c34e37455a02d12bd5f65",
        "event": {"dates": [date()] if dates is None else list(dates),
                  "timezone": timezone, "urlPurchaseTicket": ticket,
                  "isSoldOut": sold, "isCancelled": cancelled},
    }


def payload(*pages):
    return {"pages": list(pages or (page(),)), "sort": "score", "count": len(pages) or 1}


class RowTest(unittest.TestCase):
    def rows(self, *pages, today=TODAY):
        return L.rows(SITE, payload(*pages), today)

    def test_every_date_of_every_film_page_becomes_a_row(self):
        shows, report = self.rows(
            page(dates=[date(), date("2026-10-04T10:00:00.000Z",
                                     "2026-10-04T12:00:00.000Z")]),
            page(pid="6a8e9b61600c7004a13930d4", name="Heart of the Beast",
                 ticket=f"{SHOP}/heart-of-the-beast",
                 dates=[date("2026-09-27T14:00:00.000Z", "2026-09-27T16:00:00.000Z")]))
        self.assertEqual((report["pages"], report["films"]), (2, 2))
        self.assertEqual([(s["title"], s["start"]) for s in shows], [
            ("Resident Evil (2026)", "2026-09-22T19:00:00+03:00"),
            ("Heart of the Beast", "2026-09-27T17:00:00+03:00"),
            ("Resident Evil (2026)", "2026-10-04T13:00:00+03:00"),
        ])

    def test_the_utc_instant_is_published_as_helsinki_local(self):
        """16:00Z is 19:00 in Helsinki in September. A dropped offset ships all ten rows
        three hours out."""
        s = self.rows(page())[0][0]
        self.assertEqual(s["start"], "2026-09-22T19:00:00+03:00")

    def test_a_winter_instant_keeps_its_own_offset(self):
        s = self.rows(page(dates=[date("2026-12-02T15:00:00.000Z",
                                       "2026-12-02T17:00:00.000Z")]))[0][0]
        self.assertEqual(s["start"], "2026-12-02T17:00:00+02:00")

    def test_a_page_outside_the_film_category_never_publishes(self):
        shows, report = self.rows(page(categories=("Concerts", "Adults")))
        self.assertEqual((shows, report["films"]), ([], 0))

    def test_a_page_without_the_search_hashtag_never_publishes(self):
        """The hall hosts the whole town. The venue matching is not enough on its own."""
        shows, report = self.rows(page(hashtags=("akustiikka",)))
        self.assertEqual((shows, report["films"]), ([], 0))

    def test_a_film_page_with_no_date_is_the_calendars_parent_and_is_counted(self):
        shows, report = self.rows(page(dates=[], sold=True), page())
        self.assertEqual(report["undated"], 1)
        self.assertEqual(len(shows), 1)

    def test_a_page_declaring_another_timezone_is_counted_and_left_out(self):
        shows, report = self.rows(page(timezone="Europe/Stockholm"))
        self.assertEqual((shows, report["other_tz"]), ([], 1))

    def test_a_page_at_another_address_is_counted_and_left_out(self):
        shows, report = self.rows(page(address="Ylivieskan kirjasto"))
        self.assertEqual((shows, report["elsewhere"]), ([], 1))

    def test_a_page_with_no_address_at_all_still_publishes(self):
        shows, report = self.rows(page(address=""))
        self.assertEqual((len(shows), report["elsewhere"]), (1, 0))

    def test_a_cancelled_date_is_not_published_and_is_counted(self):
        shows, report = self.rows(page(dates=[date(cancelled=True), date(
            "2026-10-04T10:00:00.000Z", "2026-10-04T12:00:00.000Z")]))
        self.assertEqual([s["start"] for s in shows], ["2026-10-04T13:00:00+03:00"])
        self.assertEqual(report["cancelled"], 1)

    def test_an_event_cancelled_as_a_whole_publishes_none_of_its_dates(self):
        shows, report = self.rows(page(cancelled=True, dates=[date(), date(
            "2026-10-04T10:00:00.000Z", "2026-10-04T12:00:00.000Z")]))
        self.assertEqual((shows, report["cancelled"]), ([], 2))

    def test_sold_out_is_read_from_the_date(self):
        shows, _ = self.rows(page(dates=[date(sold=True), date(
            "2026-10-04T10:00:00.000Z", "2026-10-04T12:00:00.000Z")]))
        self.assertEqual([s["soldOut"] for s in shows], [True, False])

    def test_sold_out_falls_back_to_the_event_when_the_date_states_none(self):
        d = date()
        d["isSoldOut"] = None
        shows, _ = self.rows(page(dates=[d], sold=True))
        self.assertTrue(shows[0]["soldOut"])

    def test_an_unparsable_start_is_counted_and_left_out(self):
        shows, report = self.rows(page(dates=[date(start="soon"), date()]))
        self.assertEqual((len(shows), report["unreadable"]), (1, 1))

    def test_the_booking_slot_never_becomes_a_runtime(self):
        """Nine of the ten live rows measured 120 minutes and one 101."""
        s = self.rows(page())[0][0]
        self.assertEqual(s["len"], "")

    def test_the_show_shape(self):
        s = self.rows(page())[0][0]
        self.assertEqual((s["provider"], s["venue"], s["aud"], s["lang"], s["method"],
                          s["original"], s["genres"], s["rating"], s["img"]),
                         ("kinoakustiikka", VENUE, "", "", "", "", "", "", ""))
        self.assertEqual((s["theatre"], s["eventId"]),
                         ("Kino Akustiikka", "6a8dd2e4b7dae104a158d8ac"))


class LinkTest(unittest.TestCase):
    def test_the_date_link_wins_over_the_event_link(self):
        shows, _ = L.rows(SITE, payload(page(dates=[date(ticket=f"{SHOP}/erikoisnaytos")])),
                          TODAY)
        self.assertEqual(shows[0]["url"], f"{SHOP}/erikoisnaytos")

    def test_the_event_link_is_the_fallback_every_live_row_used(self):
        shows, _ = L.rows(SITE, payload(page()), TODAY)
        self.assertEqual(shows[0]["url"], f"{SHOP}/resident-evil-2026")

    def test_a_page_with_no_ticket_link_falls_back_to_the_calendar_page(self):
        shows, _ = L.rows(SITE, payload(page(ticket=None)), TODAY)
        self.assertEqual(shows[0]["url"],
                         f"{SITE['base']}/fi-FI/page/6a8dd2e4b7dae104a158d8ac")


class PriceTest(unittest.TestCase):
    def test_one_amount_publishes_as_that_amount(self):
        self.assertEqual(L.price_of({"min": 12, "max": 12, "currency": "EUR"}), "12€")
        self.assertEqual(L.price_of({"min": 9.5, "max": 9.5, "currency": "EUR"}),
                         "9,50€")

    def test_a_band_publishes_its_lower_end(self):
        self.assertEqual(L.price_of({"min": 10, "max": 14, "currency": "EUR"}),
                         "alkaen 10€")

    def test_anything_that_settles_no_amount_publishes_none(self):
        for price in ({"min": 12, "max": 12, "currency": "SEK"}, {"min": 0, "max": 0,
                      "currency": "EUR"}, {"currency": "EUR"}, None, "12"):
            with self.subTest(price=price):
                self.assertEqual(L.price_of(price), "")

    def test_a_page_with_no_settled_price_still_publishes_and_is_counted(self):
        shows, report = L.rows(SITE, payload(page(price={"min": 0, "max": 0,
                                                         "currency": "EUR"})), TODAY)
        self.assertEqual((shows[0]["price"], report["no_price"]), ("", 1))


class SynopsisTest(unittest.TestCase):
    def test_a_finnish_blurb_is_declared_finnish(self):
        s = L.rows(SITE, payload(page(short=(
            "Elokuva kertoo siitä, miten nuori nainen palaa kotikaupunkiinsa ja "
            "kohtaa menneisyytensä, kun perheen vanha talo on myytävä."))), TODAY)[0][0]
        self.assertEqual(list(s["_syn"]), ["fi"])

    def test_the_long_description_is_used_when_the_short_one_is_missing(self):
        s = L.rows(SITE, payload(page(short="", long_=(
            "Elokuva kertoo siitä, miten nuori nainen palaa kotikaupunkiinsa ja "
            "kohtaa menneisyytensä, kun perheen vanha talo on myytävä."))), TODAY)[0][0]
        self.assertIn("fi", s["_syn"])

    def test_a_blurb_whose_language_is_unsettled_is_withheld(self):
        s = L.rows(SITE, payload(page(short="Resident Evil.")), TODAY)[0][0]
        self.assertNotIn("_syn", s)


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._get = L.get_text
        self.addCleanup(lambda: setattr(L, "get_text", self._get))
        self.calls = []

    def serve(self, bodies):
        def get_text(url, **kw):
            self.calls.append(url)
            body = bodies.get(url)
            if isinstance(body, Exception):
                raise body
            if body is None:
                raise RuntimeError(f"unexpected fetch {url}")
            return body if isinstance(body, str) else json.dumps(body)
        L.get_text = get_text

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["localhub", "--half", "all"])
        return code, out.getvalue() + err.getvalue()

    def test_the_site_publishes_from_one_request(self):
        self.serve({SEARCH: payload(
            page(), page(pid="6a8e9b61600c7004a13930d4", name="Heart of the Beast",
                         ticket=f"{SHOP}/heart-of-the-beast"))})
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertEqual(self.calls, [SEARCH])
        shows = json.loads(
            (run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))["shows"]
        self.assertEqual(sorted({s["title"] for s in shows}),
                         ["Heart of the Beast", "Resident Evil (2026)"])

    def test_an_empty_search_fails_and_keeps_the_previous_file(self):
        """A reindex and an empty programme look the same from here, so this reader has no
        positive evidence of one and does not raise common.EmptyProgramme."""
        kept = {"generated": "2026-09-20T00:00:00+00:00", "dates": ["2026-09-20"],
                "horizon": "2026-09-20",
                "shows": [{"title": "Yesterday", "start": "2026-09-20T17:00:00+03:00"}]}
        (run.OUT / f"area-{VENUE}.json").write_text(json.dumps(kept), encoding="utf-8")
        self.serve({SEARCH: {"pages": [], "sort": "score", "count": 0}})
        code, log = self.main()
        self.assertNotEqual(code, 0)
        self.assertIn("no dated screening", log)
        after = json.loads((run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))
        self.assertEqual(after["shows"][0]["title"], "Yesterday")

    def test_a_refused_request_keeps_the_previous_file(self):
        kept = {"generated": "2026-09-20T00:00:00+00:00", "dates": [], "horizon": "",
                "shows": [{"title": "Yesterday", "start": "2026-09-20T17:00:00+03:00"}]}
        (run.OUT / f"area-{VENUE}.json").write_text(json.dumps(kept), encoding="utf-8")
        self.serve({SEARCH: RuntimeError("503 refused")})
        code, log = self.main()
        self.assertNotEqual(code, 0)
        after = json.loads((run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))
        self.assertEqual(after["shows"][0]["title"], "Yesterday")


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("kinoakustiikka")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Kino Akustiikka", "ylivieska.fi", "buy", "localhub", "cloud"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"] == p["accent"]), 1)

    def test_the_site_names_the_host_it_is_read_from(self):
        self.assertEqual(SITE["base"], "https://tapahtumat.ylivieska.fi")
        self.assertNotIn("reads", SITE)

    def test_the_search_is_the_visitor_facing_one(self):
        self.assertEqual(SEARCH, "https://tapahtumat.ylivieska.fi/api/collection/"
                                 "65b0e6fdfd13b97001a1b35d/content/general-search"
                                 "?lang=fi&country=FI&q=kinoakustiikka&mode=event"
                                 "&sort=score")


if __name__ == "__main__":
    unittest.main()


class LanguageTest(unittest.TestCase):
    """The three ways the calendar stated a screening's language, read 2026-10-04. Two
    dates per page wherever the date matters."""

    def langs(self, **kw):
        shows, _ = L.rows(SITE, payload(page(**kw)), TODAY)
        return [s["lang"] for s in shows]

    def test_the_title_states_the_audio(self):
        self.assertEqual(self.langs(name="Unohdettu saari (suomeksi puhuttu)", dates=[
            date(), date("2026-10-04T10:00:00.000Z", "2026-10-04T12:00:00.000Z")]),
            ["FI-A", "FI-A"])

    def test_the_subtitle_item_states_the_subtitles(self):
        self.assertEqual(self.langs(long_="<ul><li><strong>Tekstitys: </strong>suomenkielinen "
                                          "ja ruotsinkielinen</li><li><br></li></ul>"),
                         ["FI-S, SV-S"])

    def test_a_dated_list_states_each_screenings_audio(self):
        """Kojootti vs ACME: shown dubbed and in English, the dates listed under
        "Esitykset:". The colon sits outside the bold label on this page."""
        long_ = ("<ul><li><strong>Tekstitys</strong>: suomenkielinen</li></ul><p>Esitykset:</p>"
                 "<ul><li>22.9. suomeksi puhuttu</li><li>4.10. englanniksi puhuttu</li></ul>")
        self.assertEqual(self.langs(name="Kojootti vs ACME", long_=long_, dates=[
            date(), date("2026-10-04T14:00:00.000Z", "2026-10-04T16:00:00.000Z")]),
            ["FI-A, FI-S", "EN-A, FI-S"])

    def test_a_subtitle_item_naming_no_language_states_nothing(self):
        for value in ("Kuvaileva tekstitys", "Päivitetään myöhemmin", "suomenkielinen ja klingon"):
            with self.subTest(value=value):
                self.assertEqual(self.langs(long_=f"<ul><li><strong>Tekstitys:</strong> {value}"
                                                  "</li></ul>"), [""])
