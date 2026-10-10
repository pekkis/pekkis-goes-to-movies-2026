"""Riviera's screening language, read off the ticket page the price pass fetches (2026-09-23).

The page states the audio and the subtitles on two lines, in capitalised Finnish names and
once in English ("Kieli: Spanish" on Autofiktio). A line is published only when every
word in it names a language; a missing subtitle line says nothing, not "none". Probe:
docs/research/screening-language-sources.md. Through fetch_site so the wiring is covered.
"""
import json
import pathlib
import re
import tempfile
import unittest
from unittest import mock

import _ctx
import prices
import riviera
from test_riviera_links import TICKETS, button, item, listing
from test_riviera_prices import NOW, ORDINARY, price_page

HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")


def lines(audio=None, subs=None):
    """The two lines as the page prints them; None leaves a line out."""
    out = ""
    if audio is not None:
        out += f'<p class="spokenLanguage"> Kieli: <b>{audio}</b> </p>'
    if subs is not None:
        out += f'<p class="showSubtitles"> Tekstitys : <b>{subs}</b> </p>'
    return out


class ScreeningLanguageTest(unittest.TestCase):
    def test_the_shapes_read_on_the_day(self):
        cases = {("Suomi", "Englanti"): "FI-A, EN-S",
                 ("Englanti", "Suomi, Ruotsi"): "EN-A, FI-S, SV-S",
                 ("Spanish", "Suomi, Ruotsi"): "ES-A, FI-S, SV-S",
                 ("Suomi", None): "FI-A",
                 ("Englanti", None): "EN-A"}
        for (a, s), want in cases.items():
            with self.subTest(audio=a, subs=s):
                self.assertEqual(riviera.screening_language(lines(a, s)), want)

    def test_a_line_that_names_anything_else_says_nothing(self):
        self.assertEqual(riviera.screening_language(lines("Alkuperäinen", "Suomi")), "FI-S")
        self.assertEqual(riviera.screening_language(lines("Suomi, Klingon", "Suomi")), "FI-S")
        self.assertEqual(riviera.screening_language(lines("Suomi", "-")), "FI-A")
        self.assertEqual(riviera.screening_language(lines("", "")), "")
        self.assertEqual(riviera.screening_language("<html>no lines</html>"), "")
        self.assertEqual(riviera.screening_language(None), "")

    def test_two_audio_languages_joined_by_ja(self):
        self.assertEqual(riviera.screening_language(lines("Suomi ja ruotsi")), "FI-A, SV-A")

    def test_the_english_names_are_the_client_s(self):
        """Any language the client can name in English, the page can too."""
        block = re.search(r"const LN = \{(.*?)\n  \};", HTML, re.S).group(1)
        en = dict(re.findall(r"([A-Z]{2}):'([^']*)'",
                             re.search(r"\ben:\{(.*?)\}", block, re.S).group(1)))
        self.assertEqual(riviera.EN_NAMES, {name.lower(): code for code, name in en.items()})


class FetchSiteLanguageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = pathlib.Path(self.tmp.name) / "prices-riviera.json"

    def run_site(self, pages, fail=()):
        page = listing(item("Odyssey", "Ma 14.9.2026", "18:00", "Kallio, Sali 1", button(1)),
                       item("Odyssey", "Ti 15.9.2026", "20:00", "Kallio, Sali 1", button(2)))

        def fake(url, headers=None, data=None, **kw):
            if data is not None:
                return json.dumps({"success": True, "data": {"movies": page}}).encode()
            sid = url.rsplit("/", 1)[1]
            if sid in fail:
                raise OSError("boom")
            return pages[sid].encode()

        with mock.patch.object(riviera, "fetch", fake), mock.patch.object(prices, "fetch", fake), \
             mock.patch.object(prices.time, "sleep"):
            out = riviera.fetch_site(riviera.SITE, price_sleep=0, prices_path=self.path, now=NOW)
        return sorted((s for v in out.values() for s in v), key=lambda s: s["start"])

    def test_each_screening_carries_its_page_s_language_and_price(self):
        shows = self.run_site({
            "1": price_page([(ORDINARY, "20,00 €")]).replace("</body>", lines("Englanti", "Suomi, Ruotsi") + "</body>"),
            "2": price_page([(ORDINARY, "22,00 €")]).replace("</body>", lines("Englanti") + "</body>")})
        self.assertEqual([(s["price"], s["lang"]) for s in shows],
                         [("20€", "EN-A, FI-S, SV-S"), ("22€", "EN-A")])
        cache = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(cache["1"]["fields"], {"lang": "EN-A, FI-S, SV-S"})

    def test_a_page_without_the_lines_keeps_its_price_and_no_language(self):
        shows = self.run_site({"1": price_page([(ORDINARY, "20,00 €")]),
                               "2": price_page([(ORDINARY, "22,00 €")])})
        self.assertEqual([(s["price"], s["lang"]) for s in shows], [("20€", ""), ("22€", "")])

    def test_a_failed_page_leaves_the_screening_whole(self):
        shows = self.run_site({"2": price_page([(ORDINARY, "22,00 €")]) + lines("Suomi")},
                              fail=("1",))
        self.assertEqual(len(shows), 2)
        self.assertEqual([(s["price"], s["lang"]) for s in shows], [("", ""), ("22€", "FI-A")])


if __name__ == "__main__":
    unittest.main()
