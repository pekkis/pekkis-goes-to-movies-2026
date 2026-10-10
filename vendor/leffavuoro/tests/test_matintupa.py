"""The Matin-Tupa reader: one programme page, one film block per film.

The fixtures are the markup as read on 2026-09-20, cut to the smallest shape that still
exercises a rule. Two blocks and two screening lines everywhere there is a loop.

What they exist to prove:

- **No date on the page carries a year**, so every screening is placed by
  `common.resolve_year` from the two-letter weekday. A page left up past its week selects
  a year that the window then refuses, rather than becoming a future screening.
- **A ticket line settles a price only when it is one bare amount.** The live page had
  `14,00 €. Kts. lisätiedot` on a Neulekino evening sold with a serving and a discount the
  row does not state.
- **The poster's dimensions are in its filename**, because Toolset's resizer writes them
  there, so a landscape file is refused instead of being published as a poster.
- **The rating is only ever the KAVI icon's filename.** The page prints no rating text.
"""
import contextlib
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import matintupa as M
import registry
import run


SITE = M.SITES[0]
BASE = SITE["base"]
VENUE = SITE["venues"][0]["id"]
LISTING = BASE + SITE["listing"]


def poster(w=235, h=336):
    return (f'<a href="{BASE}/elokuvat/x/"><img decoding="async" '
            f'src="{BASE}/mt/wp-content/uploads/2026/07/JULISTE-wpcf_{w}x{h}.jpg" '
            f'class="alignleft" /></a>')


def block(slug="presidentin-kyyditys", title="Presidentin kyyditys",
          times=("la 19.9. klo 17.15", "su 20.9. klo 13.00"), liput="14 €",
          kesto="1 t 27 min", genre="Draama, Komedia, Kotimainen", age="12",
          img=None):
    """One `col-sm-6` film block, in the order the live page renders the fields."""
    art = poster() if img is None else img
    age_img = (f'<a href="/palvelut/ikarajat/"><img src="{BASE}/mt/wp-content/uploads/'
               f'2015/06/ikaraja_{age}-wpcf_30x30.png" title="Katso ikärajat" /></a>'
               if age else "")
    return (f'<div class="col-sm-6"><h2><a href="{BASE}/elokuvat/{slug}/">{title}</a></h2>'
            f'{art}<b>Esitysajat:</b> <br>' + "<br> ".join(times) + "<p><br>\n"
            f'<b>Liput:</b> {liput} <br>\n<b>Kesto:</b> {kesto}<br><br>\n'
            f'<b>Genre:</b> {genre}<p>\n<p>Kimppakyydillä elokuviin!</p>\n<p>'
            f'{age_img}<p>\n<a href="{BASE}/elokuvat/{slug}/"> &gt;&gt; Lue lisää</a>\n'
            f'</div>')


def page(*blocks):
    return ('<html><body><div id="content"><div class="row">'
            + "".join(blocks or (block(),)) + "</div></div></body></html>")


TODAY = __import__("datetime").date(2026, 9, 20)


class BlockTest(unittest.TestCase):
    def rows(self, *blocks, today=TODAY):
        return M.rows(SITE, page(*blocks), today)

    def test_every_screening_line_of_every_block_becomes_a_row(self):
        shows, report = self.rows(
            block(),
            block(slug="hetki-ennen-valoa", title="Hetki ennen valoa", age="7",
                  liput="13 €", times=("su 20.9. klo 14.45", "ma 21.9. klo 17.30")))
        self.assertEqual(report["blocks"], 2)
        self.assertEqual([(s["title"], s["start"]) for s in shows], [
            ("Presidentin kyyditys", "2026-09-19T17:15:00+03:00"),
            ("Presidentin kyyditys", "2026-09-20T13:00:00+03:00"),
            ("Hetki ennen valoa", "2026-09-20T14:45:00+03:00"),
            ("Hetki ennen valoa", "2026-09-21T17:30:00+03:00"),
        ])

    def test_the_year_comes_from_the_weekday_because_the_page_prints_none(self):
        """19.9. is a Saturday in 2026 and a Friday in 2025, and the page says `la`."""
        shows, _ = self.rows(block(times=("la 19.9. klo 17.15",)))
        self.assertEqual(shows[0]["start"], "2026-09-19T17:15:00+03:00")

    def test_a_date_the_window_refuses_is_counted_and_left_out(self):
        """A page left up: `ti 1.6.` selects 2027, 254 days out, far past anything these
        cinemas publish. The row is dropped rather than shown as a future screening."""
        shows, report = self.rows(
            block(times=("la 19.9. klo 17.15", "ti 1.6. klo 18.00")))
        self.assertEqual(len(shows), 1)
        self.assertEqual(report["undated"], 1)

    def test_a_weekday_no_candidate_year_holds_is_left_out(self):
        shows, report = self.rows(block(times=("ma 19.9. klo 17.15",)))
        self.assertEqual((shows, report["undated"]), ([], 1))

    def test_the_slug_keys_the_row_and_the_title_is_published_verbatim(self):
        shows, _ = self.rows(block(slug="kaunis-rietas", title="Kaunis Rietas Onnellinen"))
        self.assertEqual(shows[0]["eventId"], "kaunis-rietas")
        self.assertEqual(shows[0]["title"], "Kaunis Rietas Onnellinen")
        self.assertEqual(shows[0]["url"], f"{BASE}/elokuvat/kaunis-rietas/")

    def test_the_show_shape(self):
        s = self.rows(block())[0][0]
        self.assertEqual((s["provider"], s["venue"], s["aud"], s["lang"], s["method"],
                          s["original"], s["soldOut"]),
                         ("matintupa", VENUE, "", "", "", "", False))
        self.assertEqual(s["theatre"], "Elokuvateatteri Matin-Tupa")
        self.assertEqual((s["len"], s["genres"], s["rating"]),
                         ("87", "Draama, Komedia, Kotimainen", "K-12"))


class PriceTest(unittest.TestCase):
    def test_one_bare_amount_is_published(self):
        for liput, want in (("14 €", "14€"), ("13 €", "13€"), ("9,50 €", "9,50€"),
                            ("€ 12", "12€")):
            with self.subTest(liput=liput):
                self.assertEqual(M.price_of(liput), want)

    def test_an_amount_with_anything_beside_it_settles_nothing(self):
        for liput in ("14,00 €. Kts. lisätiedot", "14 € / 12 €", "14 € (jäsenille 10 €)",
                      "vaihtelee", ""):
            with self.subTest(liput=liput):
                self.assertEqual(M.price_of(liput), "")

    def test_the_unsettled_row_publishes_without_a_price_and_is_counted(self):
        shows, report = M.rows(SITE, page(
            block(),
            block(slug="neulekino", title="Kaunis Rietas Onnellinen",
                  liput="14,00 €. Kts. lisätiedot",
                  times=("to 24.9. klo 18.00",))), TODAY)
        self.assertEqual([s["price"] for s in shows], ["14€", "14€", ""])
        self.assertEqual(report["no_price"], 1)


class FieldTest(unittest.TestCase):
    def test_the_runtime_counts_the_hours(self):
        for kesto, want in (("1 t 27 min", "87"), ("1 h 57 min", "117"),
                            ("95 min", "95"), ("", "")):
            with self.subTest(kesto=kesto):
                self.assertEqual(M.minutes_of(kesto), want)

    def test_the_rating_is_the_icon_file_name(self):
        self.assertEqual(M.rating_of('<img src="/x/ikaraja_12-wpcf_30x30.png">'), "K-12")
        self.assertEqual(M.rating_of('<img src="/x/ikaraja_7-wpcf_30x30.png">'), "K-7")
        self.assertEqual(M.rating_of('<img src="/x/ikaraja_s-wpcf_30x30.png">'), "S")

    def test_an_icon_this_parser_does_not_know_leaves_the_rating_empty(self):
        self.assertEqual(M.rating_of('<img src="/x/sisaltaa_vakivalta.png">'), "")
        self.assertEqual(M.rating_of(""), "")

    def test_the_portrait_poster_is_published_absolute(self):
        got = M.poster_of(poster(236, 336), BASE)
        self.assertTrue(got.startswith(BASE + "/mt/wp-content/"))
        self.assertTrue(got.endswith("-wpcf_236x336.jpg"))

    def test_a_landscape_file_is_not_a_poster(self):
        """The resizer serves whatever the editor uploaded. A still is not artwork."""
        self.assertEqual(M.poster_of(poster(640, 360), BASE), "")
        self.assertEqual(M.poster_of(poster(300, 300), BASE), "")

    def test_a_block_with_no_image_still_publishes(self):
        shows, _ = M.rows(SITE, page(block(img="")), TODAY)
        self.assertEqual(shows[0]["img"], "")
        self.assertEqual(len(shows), 2)


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._get = M.get_text
        self.addCleanup(lambda: setattr(M, "get_text", self._get))
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
        M.get_text = get_text

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["matintupa", "--half", "all"])
        return code, out.getvalue() + err.getvalue()

    def test_the_site_publishes_from_one_request(self):
        self.serve({LISTING: page(
            block(),
            block(slug="myrskyn-ikkuna", title="Myrskyn ikkuna", liput="13 €",
                  times=("su 20.9. klo 18.15", "ma 21.9. klo 19.00")))})
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertEqual(self.calls, [LISTING])
        shows = json.loads(
            (run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))["shows"]
        self.assertEqual(sorted({s["title"] for s in shows}),
                         ["Myrskyn ikkuna", "Presidentin kyyditys"])

    def test_a_page_with_no_film_block_fails_and_keeps_the_previous_file(self):
        """No sentence on this site says the programme is empty, so a zero-block parse is
        a broken read rather than evidence of one."""
        kept = {"generated": "2026-09-19T00:00:00+00:00", "dates": ["2026-09-19"],
                "horizon": "2026-09-19",
                "shows": [{"title": "Yesterday", "start": "2026-09-19T17:00:00+03:00"}]}
        (run.OUT / f"area-{VENUE}.json").write_text(json.dumps(kept), encoding="utf-8")
        self.serve({LISTING: "<html><body><div id='content'></div></body></html>"})
        code, log = self.main()
        self.assertNotEqual(code, 0)
        self.assertIn("no film block", log)
        after = json.loads((run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))
        self.assertEqual(after["shows"][0]["title"], "Yesterday")

    def test_a_refused_request_keeps_the_previous_file(self):
        kept = {"generated": "2026-09-19T00:00:00+00:00", "dates": [], "horizon": "",
                "shows": [{"title": "Yesterday", "start": "2026-09-19T17:00:00+03:00"}]}
        (run.OUT / f"area-{VENUE}.json").write_text(json.dumps(kept), encoding="utf-8")
        self.serve({LISTING: RuntimeError("503 refused")})
        code, log = self.main()
        self.assertNotEqual(code, 0)
        after = json.loads((run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))
        self.assertEqual(after["shows"][0]["title"], "Yesterday")


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("matintupa")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Elokuvateatteri Matin-Tupa", "matin-tupa.fi", "door",
                          "matintupa", "cloud"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"] == p["accent"]), 1)

    def test_the_town_is_ylistaro_and_not_seinajoki(self):
        """Ylistaro has belonged to Seinäjoki since 2009. Filing it under Seinäjoki would
        put this accent in that city view beside BioRex, below the 14.4 floor, and the
        cinema gives Ylistaro as its own address. Nilsiä and Haapamäki are the same call.
        """
        self.assertEqual(SITE["venues"][0]["city"], "Ylistaro")
        cities = {v["city"] for s in M.SITES for v in s["venues"]}
        self.assertNotIn("Seinäjoki", cities)

    def test_the_site_names_the_host_it_is_read_from(self):
        self.assertEqual(SITE["base"], "https://www.matin-tupa.fi")
        self.assertNotIn("reads", SITE)


if __name__ == "__main__":
    unittest.main()
