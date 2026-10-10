"""Elokuvateatteri Huvimylly: a programme typed by hand into one WordPress page.

The fixtures are the shapes read on the live page on 2026-09-19 and in eleven Wayback
captures from 2023-05 to 2026-04. What they exist to prove:

- **The rating marker is what closes a title**, not the line break. A continuation and a
  free-text note sit in the same position, and the captures carry both.
- **The marker is anchored to the end of the line.** An unanchored pattern read the final
  `s` of `Koiramies-k7/4-` as an S rating and published "Koiramie".
- **A line that cannot be placed is left out and counted, and the site fails when more
  fail than succeed.** One capture carries four placeholder rows at once, so raising on
  each would fail the whole site on an ordinary week.
- **Every weekday in the fixtures is derived**, not typed: the captures misspell them and
  `common.resolve_year` places a date from the weekday, so a typed one would test nothing.
- **No poster is published**, because the images are unordered against the rows.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import huvimylly as H
import registry
import run


SITE = H.SITES[0]
PAGE_URL = "https://www.huvimylly.com/"
TODAY = datetime.date(2026, 9, 19)          # a Saturday
FI_LONG = ("Maanantaina", "Tiistaina", "Keskiviikkona", "Torstaina", "Perjantaina",
           "Lauantaina", "Sunnuntaina")
# The standing first item carries the operator's own email address on the live page. It is
# never read for anything but the price and never published, so the fixture carries the
# shape and not the address.
WELCOME = "Tervetuloa viihtymään laatuelokuvien pariin . ota yhteytä"
PRICE_LINE = ("Liput  vain 10-€  lippuja  ennakkoon Raahesalin lipunmyynti    Ovella  "
              "ennen  elokuvaa    käteismaksu    Lasten elokuvat puhuttu suomeksi")
RULE = "………………………………………………………………."


def head(d):
    """A date heading with the weekday the date really has."""
    return f"{FI_LONG[d.weekday()]} {d.day}.{d.month}"


def payload(*lines, welcome=True):
    body = "<ul>"
    if welcome:
        body += f"<li>{WELCOME}</li><li>{PRICE_LINE}</li><li>{RULE}</li>"
    body += "".join(f"<li>{x}</li>" for x in lines)
    body += ('<li><img src="http://www.huvimylly.com/wp-content/uploads/2026/09/'
             'unohdettu-saari-210x300.jpg" width="210" height="300"></li>'
             '<li><img src="http://www.huvimylly.com/wp-content/uploads/2026/09/'
             'pirjo-200x300.jpg" width="200" height="300"></li><li></li></ul>')
    return json.dumps([{"id": 95, "modified_gmt": "2026-09-17T08:36:35",
                        "content": {"rendered": body}}])


SUN = datetime.date(2026, 10, 11)           # a Sunday, 22 days out
LIVE = payload(f"-{head(SUN)}",
               "Klo 14.00   Saapasjalkakissa",
               "unohdettu  saari  -k7/4-",
               "Klo 16.00 Dome Karukosken",
               "Rakkautta  ja  virtahepoja -k12/9-",
               "Klo 18.00  Pirjo  -s-",
               "Klo 19.30 Kerro  se kaikille   -k12/9-")


class ItemsTest(unittest.TestCase):
    def test_the_route_answering_something_else_raises(self):
        """A login wall or a moved slug has to fail rather than parse to zero rows."""
        for body in ("<html>not json</html>", "[]", "{}"):
            with self.subTest(body=body[:12]), self.assertRaises(RuntimeError):
                H.items(body)


class RowsTest(unittest.TestCase):
    def rows(self, doc, today=None):
        return H.rows(SITE, H.items(doc), today or TODAY)

    def test_the_live_page(self):
        shows, report = self.rows(LIVE)
        self.assertEqual([(s["start"][:16], s["title"], s["rating"]) for s in shows],
                         [("2026-10-11T14:00", "Saapasjalkakissa unohdettu saari", "K-7"),
                          ("2026-10-11T16:00", "Dome Karukosken Rakkautta ja virtahepoja",
                           "K-12"),
                          ("2026-10-11T18:00", "Pirjo", "S"),
                          ("2026-10-11T19:30", "Kerro se kaikille", "K-12")])
        self.assertEqual(report["unplaceable"], 0)

    def test_the_marker_closes_the_title_across_two_items(self):
        """Position alone cannot tell a continuation from a note, so the rule is the
        marker. The note after a complete row is left where it is."""
        d = TODAY + datetime.timedelta(days=3)
        shows, report = self.rows(payload(
            head(d),
            "Klo 14.00 Dome Karukosken", "Rakkautta ja virtahepoja -k12/9-",
            "Klo 18.00 Pirjo -s-", "elokuvan jälkeen ilmainen pullakahvitarjoilu"))
        self.assertEqual([s["title"] for s in shows],
                         ["Dome Karukosken Rakkautta ja virtahepoja", "Pirjo"])
        self.assertEqual(report["unplaceable"], 0)
        # The welcome line and the note, counted and not kept.
        self.assertEqual(report["unread"], 2)

    def test_an_unmarked_row_does_not_swallow_the_note_after_it(self):
        """The failure the marker rule exists to stop. Taking the next item on position
        alone publishes `Dome Karukosken elokuvan jälkeen ilmainen pullakahvitarjoilu` as
        a film title, and the title is the key for normTitle(), films-extra.json and
        tmdb-aliases.json, so a note in it fragments the film everywhere."""
        d = TODAY + datetime.timedelta(days=3)
        shows, report = self.rows(payload(
            head(d),
            "Klo 14.00 Dome Karukosken", "elokuvan jälkeen ilmainen pullakahvitarjoilu",
            "Klo 15.00 Pirjo -s-", "Klo 17.00 Kerro se kaikille -k12/9-"))
        self.assertEqual([s["title"] for s in shows], ["Pirjo", "Kerro se kaikille"])
        self.assertEqual(report["unplaceable"], 1)

    def test_a_marker_against_the_title_does_not_eat_the_last_letter(self):
        """`Koiramies-k7/4-` published "Koiramie" with an S rating under an unanchored
        pattern, because the film's own final `s` matched the rating alternative."""
        shows, _ = self.rows(payload("Lauantaina  6.1 2024", "klo 13.00 Koiramies-k7/4-"))
        self.assertEqual([(s["title"], s["rating"]) for s in shows], [("Koiramies", "K-7")])

    def test_every_rating_shape_the_captures_carry(self):
        d = TODAY + datetime.timedelta(days=4)
        cases = [("-k7/4-", "K-7"), ("-k12/9-", "K-12"), ("-s-", "S"), ("k7/4-", "K-7"),
                 ("-k 16/13", "K-16"), ("-k16/13", "K-16"), ("-12/9-", "K-12"),
                 ("-7/4-", "K-7"), ("-k7/-9-", "K-7"), ("-k12/9\u2013", "K-12"),
                 ("-k?", "")]
        for marker, want in cases:
            with self.subTest(marker=marker):
                shows, report = self.rows(payload(head(d), f"Klo 18.00 Elokuva {marker}",
                                                  "Klo 19.00 Pirjo -s-"))
                self.assertEqual(report["unplaceable"], 0)
                self.assertEqual((shows[0]["title"], shows[0]["rating"]),
                                 ("Elokuva", want))

    def test_an_explicit_year_is_used_and_a_run_together_one_is_not_read(self):
        """`Sunnuntaina  7.12024-` types the year straight onto the month and no reading
        of it is safe, so it is not a heading and the row after it has none."""
        shows, _ = self.rows(payload("Lauantaina  6.1 2024", "klo 13.00 Koiramies -k7/4-"))
        self.assertEqual(shows[0]["start"][:10], "2024-01-06")
        with self.assertRaises(H.ShowRowError) as e:
            self.rows(payload("Sunnuntaina  7.12024-", "Klo 13.00 Koiramies -k7/4-"))
        self.assertIn("no date heading", str(e.exception))

    def test_the_standing_price_line_is_read_and_not_assumed(self):
        """The amount is parsed from the line each run rather than hardcoded, because it
        is one hand-typed sentence the cinema can change."""
        d = TODAY + datetime.timedelta(days=3)
        for line, want in (("Liput  vain 10-€  ovella", "10€"),
                           ("Liput vain 12 € ovella", "12€"),
                           ("Liput vain 7,50€ ovella", "7,50€")):
            with self.subTest(line=line):
                shows, _ = self.rows(payload(line, head(d), "Klo 17.00 Pirjo -s-",
                                             welcome=False))
                self.assertEqual({s["price"] for s in shows}, {want})

    def test_a_price_line_naming_two_amounts_settles_neither(self):
        """One line, two tariffs, and nothing on a row to say which applies to it. The
        rule is the project's: a price is published only where it is established for that
        screening."""
        d = TODAY + datetime.timedelta(days=3)
        shows, report = self.rows(payload(
            "Liput  vain 10-€ arkisin   Liput vain 12 € viikonloppuisin",
            head(d), "Klo 17.00 Pirjo -s-", "Klo 19.00 Kerro se kaikille -k12/9-",
            welcome=False))
        self.assertEqual({s["price"] for s in shows}, {""})
        self.assertEqual(report["no_price"], 2)

    def test_an_announcement_carrying_a_date_is_not_a_heading(self):
        """`Paddington seikkailee 24.1 alkaen` and `Tulossa  Lastenelokuva päivät` are both
        in the captures. Read as a heading, the first would place a screening on the
        weekday "seikkailee", which no weekday index resolves, so the date would be taken
        as the nearest 24 January instead."""
        d = TODAY + datetime.timedelta(days=3)
        for line in ("Paddington seikkailee 24.1 alkaen", "Tulossa  Lastenelokuva päivät",
                     "29.5  ja 30.5"):
            with self.subTest(line=line):
                with self.assertRaises(H.ShowRowError) as e:
                    self.rows(payload(line, "Klo 17.00 Pirjo -s-"))
                self.assertIn("no date heading", str(e.exception))
        # and the real heading beside it still works
        shows, _ = self.rows(payload("Paddington seikkailee 24.1 alkaen", head(d),
                                     "Klo 17.00 Pirjo -s-"))
        self.assertEqual(shows[0]["start"][:10], d.isoformat())

    def test_a_code_outside_the_legal_classes_is_no_rating(self):
        """The grammar Alatalo shares: "-k6/13" is a typo for 16/13, not a K-6."""
        d = TODAY + datetime.timedelta(days=5)
        shows, _ = self.rows(payload(head(d), "Klo 18.00 Lapin sota -k6/13",
                                     "Klo 20.00 Kolme kovaa -k 16/13"))
        self.assertEqual([(s["title"], s["rating"]) for s in shows],
                         [("Lapin sota", ""), ("Kolme kovaa", "K-16")])

    def test_consecutive_headings_share_the_times_that_follow(self):
        a = TODAY + datetime.timedelta(days=5)
        b = TODAY + datetime.timedelta(days=6)
        shows, _ = self.rows(payload(head(a), head(b), "Klo 18.00 Kolme kovaa -k 16/13"))
        self.assertEqual([s["start"][:10] for s in shows],
                         [a.isoformat(), b.isoformat()])

    def test_one_line_can_hold_two_times(self):
        a = TODAY + datetime.timedelta(days=5)
        b = TODAY + datetime.timedelta(days=6)
        shows, _ = self.rows(payload(f"{head(a)}   ja {head(b)}",
                                     "Klo 14.00  ja 19.00  Myrskyluodon Maija -k12/9-"))
        self.assertEqual([s["start"][:16] for s in shows],
                         [f"{a}T14:00", f"{a}T19:00", f"{b}T14:00", f"{b}T19:00"])

    def test_a_line_that_cannot_be_placed_is_left_out_and_counted(self):
        """`Klo?` and a dotless `Klo 1900` would both mean guessing an hour; `elokuva
        avoin` is a slot with no film in it."""
        d = TODAY + datetime.timedelta(days=3)
        # "Klo 14.00" bare is the one that also pins the heading pattern's word length:
        # a shorter one would read `Klo 14.00` as the weekday "Klo" on 14 February.
        for line in ("Klo? Levoton Tuhkimo -s-", "Klo 1900   elokuva  avon-",
                     "Klo 17.00   elokuva  avoin", "Klo 14.00 -k7/4-", "Klo 14.00"):
            with self.subTest(line=line):
                shows, report = self.rows(payload(head(d), line,
                                                  "Klo 15.00 Pirjo -s-",
                                                  "Klo 16.00 Kerro se kaikille -k12/9-"))
                self.assertEqual([s["title"] for s in shows], ["Pirjo", "Kerro se kaikille"])
                self.assertEqual(report["unplaceable"], 1)

    def test_more_unplaceable_than_placed_fails_the_site(self):
        """A template change breaks every row rather than a few, which is the case the
        count has to separate from an operator typing an odd one."""
        d = TODAY + datetime.timedelta(days=3)
        with self.assertRaises(H.ShowRowError) as e:
            self.rows(payload(head(d), "Klo? a", "Klo? b", "Klo 15.00 Pirjo -s-"))
        self.assertIn("template has moved", str(e.exception))

    def test_a_screening_line_with_no_heading_raises(self):
        with self.assertRaises(H.ShowRowError) as e:
            self.rows(payload("Klo 18.00 Kolme kovaa -k16/13"))
        self.assertIn("no date heading", str(e.exception))

    def test_a_misspelled_weekday_still_places_the_date(self):
        """`Sunnuntainan`, `Sunnunaina` and `Lauanataina` are all in the captures;
        `common.weekday_index` reads the first two characters."""
        d = TODAY + datetime.timedelta(days=1)   # a Sunday
        for spelling in ("Sunnuntaina", "Sunnuntainan", "Sunnunaina"):
            with self.subTest(spelling=spelling):
                shows, _ = self.rows(payload(f"{spelling} {d.day}.{d.month}",
                                             "Klo 17.00 Pirjo -s-"))
                self.assertEqual(shows[0]["start"][:10], d.isoformat())

    def test_the_standing_line_settles_the_price_for_every_row(self):
        shows, _ = self.rows(LIVE)
        self.assertEqual({s["price"] for s in shows}, {"10€"})

    def test_a_price_line_that_settles_nothing_publishes_nothing(self):
        d = TODAY + datetime.timedelta(days=3)
        shows, report = self.rows(payload(head(d), "Klo 17.00 Pirjo -s-",
                                          "Klo 19.00 Kerro se kaikille -k12/9-",
                                          welcome=False))
        self.assertEqual({s["price"] for s in shows}, {""})
        self.assertEqual(report["no_price"], 2)

    def test_no_poster_is_published(self):
        """The images sit in their own items with no alt text and their order is not the
        rows' order, measured on the 2026-02-17 capture."""
        shows, _ = self.rows(LIVE)
        self.assertEqual({s["img"] for s in shows}, {""})

    def test_every_screening_links_to_the_page_because_there_is_no_ticket_url(self):
        shows, _ = self.rows(LIVE)
        self.assertEqual({s["url"] for s in shows}, {PAGE_URL})
        self.assertEqual(registry.by_id("huvimylly")["book"], "door")

    def test_the_show_shape(self):
        shows, _ = self.rows(LIVE)
        s = shows[0]
        self.assertEqual((s["provider"], s["venue"], s["theatre"], s["aud"]),
                         ("huvimylly", "huvimylly-raahe", "Elokuvateatteri Huvimylly", ""))
        self.assertEqual((s["original"], s["method"], s["genres"], s["lang"],
                          s["len"], s["soldOut"]), ("", "", "", "", "", False))
        self.assertNotIn("_syn", s)

    def test_no_line_of_the_page_is_carried_out_of_the_parse(self):
        """The first item carries the operator's own email address, so the report counts
        what it could not use rather than keeping it: a field holding that line is one
        print away from publishing an address, and tests/test_contact_address.py refuses
        any address in any tracked file."""
        shows, report = self.rows(LIVE)
        blob = " ".join(s["title"] for s in shows)
        self.assertNotIn("@", blob)
        self.assertNotIn("Tervetuloa", blob)
        for value in report.values():
            self.assertIsInstance(value, int)


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
        self._fetch = H.fetch
        self.addCleanup(lambda: setattr(H, "fetch", self._fetch))

    def serve(self, body):
        def fetch(url, **kw):
            if isinstance(body, Exception):
                raise body
            return body.encode("utf-8")
        H.fetch = fetch

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            # --half all: on Actions run.py derives "cloud" from GITHUB_ACTIONS and
            # this module is local, so it would have no sites there and the three
            # tests below would pass locally and fail on the runner, which is what
            # they did on 5dd5080cb. test_regina.py carries the same line.
            code = run.main(["huvimylly", "--half", "all"])
        return code, out.getvalue() + err.getvalue()

    def soon(self, days):
        return datetime.datetime.now(H.FI).date() + datetime.timedelta(days=days)

    def live(self):
        a, b = self.soon(3), self.soon(4)
        return payload(head(a), "Klo 14.00 Pirjo -s-", "Klo 18.00 Kerro se kaikille -k12/9-",
                       head(b), "Klo 15.00 Dome Karukosken", "Rakkautta ja virtahepoja -k12/9-")

    def test_the_site_publishes(self):
        self.serve(self.live())
        code, log = self.main()
        self.assertEqual(code, 0, log)
        shows = json.loads((run.OUT / "area-huvimylly-raahe.json").read_text())["shows"]
        self.assertEqual(len(shows), 3)
        self.assertEqual({s["price"] for s in shows}, {"10€"})
        self.assertIn("0 failures", log)

    def test_a_page_with_no_screening_fails_and_keeps_the_previous_file(self):
        """The site publishes no sentence saying there are none, so zero rows may not read
        as a confirmed empty programme."""
        (run.OUT / "area-huvimylly-raahe.json").write_text(json.dumps(self.PREV))
        self.serve(payload("Tulossa  Lastenelokuva päivät", "29.5  ja 30.5"))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("no evidence", log)
        self.assertNotIn("no programme at the moment", log)
        self.assertEqual(json.loads(
            (run.OUT / "area-huvimylly-raahe.json").read_text()), self.PREV)

    def test_a_refused_page_keeps_the_previous_file(self):
        (run.OUT / "area-huvimylly-raahe.json").write_text(json.dumps(self.PREV))
        self.serve(RuntimeError("HTTP Error 403"))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertEqual(json.loads(
            (run.OUT / "area-huvimylly-raahe.json").read_text()), self.PREV)


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("huvimylly")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Elokuvateatteri Huvimylly", "huvimylly.com", "door",
                          "huvimylly", "local"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"] == p["accent"]), 1)

    def test_the_site_names_the_host_it_reads(self):
        self.assertEqual([s["base"] for s in H.SITES], ["https://www.huvimylly.com"])
        self.assertEqual(len(run.host_groups(H.SITES)), 1)

    def test_the_label_is_the_venue_name(self):
        self.assertEqual(SITE["venues"][0]["name"], registry.by_id("huvimylly")["label"])
        self.assertEqual(SITE["venues"][0]["city"], "Raahe")


if __name__ == "__main__":
    unittest.main()
