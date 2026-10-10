"""The Kino K13 reader: one page, one section, prose rather than a list.

The fixtures are the section as read on 2026-09-21, cut to the smallest shape that still
exercises a rule. Two blocks and two rows everywhere there is a loop.

What they exist to prove:

- **Only a line with a weekday, a date and a clock is a screening.** The four Kinokka
  evenings on the live page carry a date and no time, and the organiser page they link
  publishes no clock either, so they publish nothing and are counted.
- **A festival heading is a date range, not a row.**
- **Free admission belongs to the block it is stated under**, not to the page.
- **No date carries a year**, so the weekday places it.
- **The rating is the trailing sentence**, and a row without one leaves it empty.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import k13 as K
import registry
import run


SITE = K.SITES[0]
BASE = SITE["base"]
VENUE = SITE["venues"][0]["id"]
LISTING = BASE + SITE["listing"]
URL = BASE + SITE["listing"] + SITE["anchor"]
TODAY = datetime.date(2026, 9, 21)

FESTIVAL = "5.–9.10.2026 Puolan elokuvaviikot – Polish Film Weeks"
FREE = "Näytöksiin on vapaa pääsy. Saliin mahtuu 150 katsojaa."
ROW1 = ("ma 5.10. klo 18: LUVATTU MAA (Ziemia obiecana) 1974, 179 min. "
        "Sallittu yli 16-vuotiaille.")
ROW2 = ("ti 6.10. klo 18: KUORIPOJAT (Ministranci) 2025, 105 min. "
        "Sallittu yli 12-vuotiaille.")
SHORTS = "ke 7.10. klo 18: STUDIO MUNKA, 3 lyhytelokuvaa."
KINOKKA = "27.9.2026 Kinokka: Ei karhuja"
KINOKKA_BODY = "Ohjaaja: Jafar Panahi, 2022, Iran. Sallittu yli 7-vuotiaille."


def page(*lines):
    body = "".join(f"<p>{x}</p>" for x in (lines or (FESTIVAL, FREE, ROW1)))
    return ('<html><body><section id=ohjelmisto class="l-visual-editor">'
            '<h2>Avoimet yleisönäytökset</h2>'
            f'<div class="l-visual-editor__item wysiwyg">{body}</div>'
            "</section></body></html>")


class SectionTest(unittest.TestCase):
    def rows(self, *lines, today=TODAY):
        return K.rows(SITE, page(*lines), today)

    def test_every_timed_line_of_the_block_becomes_a_row(self):
        shows, report = self.rows(FESTIVAL, FREE, ROW1, ROW2)
        self.assertEqual([(s["title"], s["start"]) for s in shows], [
            ("LUVATTU MAA", "2026-10-05T18:00:00+03:00"),
            ("KUORIPOJAT", "2026-10-06T18:00:00+03:00"),
        ])
        self.assertEqual(report["headings"], 1)

    def test_a_dated_entry_with_no_clock_publishes_nothing_and_is_counted(self):
        """The Kinokka evenings. Nothing publicly fetchable settles their hour."""
        shows, report = self.rows(KINOKKA, KINOKKA_BODY, FESTIVAL, FREE, ROW1)
        self.assertEqual([s["title"] for s in shows], ["LUVATTU MAA"])
        self.assertEqual(report["no_time"], 1)

    def test_a_festival_heading_is_not_a_screening(self):
        shows, report = self.rows(FESTIVAL, FREE)
        self.assertEqual((shows, report["headings"]), ([], 1))

    def test_free_admission_reaches_the_rows_under_its_heading(self):
        shows, _ = self.rows(FESTIVAL, FREE, ROW1, ROW2)
        self.assertEqual([s["price"] for s in shows], ["Vapaa pääsy"] * 2)

    def test_free_admission_does_not_cross_into_the_next_block(self):
        """A later block states its own terms or states none."""
        shows, _ = self.rows(FESTIVAL, FREE, ROW1,
                             "6.–8.11.2026 Serbian elokuvapäivät",
                             "pe 6.11. klo 18: ODOTUS, 95 min.")
        self.assertEqual([(s["title"], s["price"]) for s in shows],
                         [("LUVATTU MAA", "Vapaa pääsy"), ("ODOTUS", "")])

    def test_a_row_with_no_free_admission_line_publishes_no_price(self):
        shows, _ = self.rows(FESTIVAL, ROW1)
        self.assertEqual(shows[0]["price"], "")

    def test_the_year_comes_from_the_weekday_because_the_row_prints_none(self):
        """5.10. is a Monday in 2026 and a Sunday in 2025, and the row says ma."""
        shows, _ = self.rows(FESTIVAL, ROW1)
        self.assertEqual(shows[0]["start"], "2026-10-05T18:00:00+03:00")

    def test_a_weekday_no_candidate_year_holds_is_counted_and_left_out(self):
        shows, report = self.rows(FESTIVAL, "su 5.10. klo 18: LUVATTU MAA, 179 min.")
        self.assertEqual((shows, report["undated"]), ([], 1))

    def test_a_clock_without_minutes_is_read_as_the_hour(self):
        shows, _ = self.rows(FESTIVAL, "to 8.10 klo 18: HYVÄ TALO (Dom dobry) 2025, 107 min.")
        self.assertEqual(shows[0]["start"], "2026-10-08T18:00:00+03:00")

    def test_a_clock_with_minutes_keeps_them(self):
        shows, _ = self.rows(FESTIVAL, "ma 5.10. klo 18.30: LUVATTU MAA, 179 min.")
        self.assertEqual(shows[0]["start"], "2026-10-05T18:30:00+03:00")

    def test_the_original_title_and_the_runtime_are_read_when_the_row_states_them(self):
        s = self.rows(FESTIVAL, ROW1)[0][0]
        self.assertEqual((s["title"], s["original"], s["len"]),
                         ("LUVATTU MAA", "Ziemia obiecana", "179"))

    def test_a_row_stating_neither_leaves_both_empty(self):
        s = self.rows(FESTIVAL, SHORTS)[0][0]
        self.assertEqual((s["title"], s["original"], s["len"], s["rating"]),
                         ("STUDIO MUNKA", "", "", ""))

    def test_the_rating_is_the_trailing_sentence(self):
        self.assertEqual(K.rating_of("Sallittu yli 16-vuotiaille."), "K-16")
        self.assertEqual(K.rating_of("Sallittu yli 7-vuotiaille."), "K-7")
        self.assertEqual(K.rating_of("Sallittu kaikenikäisille."), "S")
        self.assertEqual(K.rating_of("3 lyhytelokuvaa."), "")

    def test_the_emitted_row_carries_the_rating_from_its_own_line(self):
        shows, _ = self.rows(FESTIVAL, ROW1, ROW2, SHORTS)
        self.assertEqual([(s["title"], s["rating"]) for s in shows],
                         [("LUVATTU MAA", "K-16"), ("KUORIPOJAT", "K-12"),
                          ("STUDIO MUNKA", "")])

    def test_a_line_whose_hour_is_only_implied_publishes_nothing(self):
        """`27.9.2026 Kinokka: Ei karhuja` has a date, a colon and a title, and the hour
        would have to be invented. A parser that defaulted it to midnight would publish
        every Kinokka evening at 00:00."""
        shows, report = self.rows(FESTIVAL, "27.9.2026 Kinokka: Ei karhuja", ROW1)
        self.assertEqual([s["title"] for s in shows], ["LUVATTU MAA"])
        self.assertNotIn("00:00", [s["start"][11:16] for s in shows])
        self.assertEqual(report["no_time"], 1)

    def test_the_show_shape(self):
        s = self.rows(FESTIVAL, FREE, ROW1)[0][0]
        self.assertEqual((s["provider"], s["venue"], s["aud"], s["lang"], s["method"],
                          s["genres"], s["img"], s["soldOut"]),
                         ("k13", VENUE, "", "", "", "", "", False))
        self.assertEqual((s["theatre"], s["eventId"], s["url"]),
                         ("Kino K13", "luvattu-maa", URL))


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._get = K.get_text
        self.addCleanup(lambda: setattr(K, "get_text", self._get))
        self.calls = []

    def serve(self, pages):
        def get_text(url, **kw):
            self.calls.append(url)
            body = pages.get(url)
            if isinstance(body, Exception):
                raise body
            if body is None:
                raise RuntimeError(f"unexpected fetch {url}")
            return body
        K.get_text = get_text

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["k13", "--half", "all"])
        return code, out.getvalue() + err.getvalue()

    def test_the_site_publishes_from_one_request(self):
        self.serve({LISTING: page(KINOKKA, KINOKKA_BODY, FESTIVAL, FREE, ROW1, ROW2)})
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertEqual(self.calls, [LISTING])
        shows = json.loads(
            (run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))["shows"]
        self.assertEqual(sorted({s["title"] for s in shows}), ["KUORIPOJAT", "LUVATTU MAA"])
        self.assertIn("with no clock", log)

    def test_a_section_with_no_timed_row_fails_and_keeps_the_previous_file(self):
        kept = {"generated": "2026-09-20T00:00:00+00:00", "dates": ["2026-09-20"],
                "horizon": "2026-09-20",
                "shows": [{"title": "Yesterday", "start": "2026-09-20T17:00:00+03:00"}]}
        (run.OUT / f"area-{VENUE}.json").write_text(json.dumps(kept), encoding="utf-8")
        self.serve({LISTING: page(KINOKKA, KINOKKA_BODY)})
        code, log = self.main()
        self.assertNotEqual(code, 0)
        self.assertIn("no screening line", log)
        after = json.loads((run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))
        self.assertEqual(after["shows"][0]["title"], "Yesterday")

    def test_a_refused_request_keeps_the_previous_file(self):
        kept = {"generated": "2026-09-20T00:00:00+00:00", "dates": [], "horizon": "",
                "shows": [{"title": "Yesterday", "start": "2026-09-20T17:00:00+03:00"}]}
        (run.OUT / f"area-{VENUE}.json").write_text(json.dumps(kept), encoding="utf-8")
        self.serve({LISTING: RuntimeError("503 refused")})
        code, log = self.main()
        self.assertNotEqual(code, 0)
        after = json.loads((run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))
        self.assertEqual(after["shows"][0]["title"], "Yesterday")


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("k13")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Kino K13", "ses.fi", "list", "k13", "cloud"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"] == p["accent"]), 1)

    def test_the_site_names_the_host_it_is_read_from(self):
        self.assertEqual(SITE["base"], "https://www.ses.fi")
        self.assertNotIn("reads", SITE)


if __name__ == "__main__":
    unittest.main()
