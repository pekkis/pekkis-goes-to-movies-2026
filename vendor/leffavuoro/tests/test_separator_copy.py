"""The copy Leffavuoro writes carries no middle dot (2026-09-23).

Separators became layout: a CSS square between a ticket's facts, spans and spacing in the
footers and on the page subtitles, and punctuation or words in sentences, titles and
accessible names. This pins the places where the site's own words live, and nothing
else: the providers' method strings use " \u00b7 " as an internal delimiter, which the
client and the generator split on, and film titles, cinema names and synopses are
third-party text that keeps whatever it carries. So this is not a scan of the sources:
it reads the app's translation table and static markup, the status and privacy pages
(which hold neither delimiter code nor third-party text), and the generator's own
templates. The rendered tickets are covered in tests/browser/test_ticket_separators.py.
"""
import re
import unittest

import _ctx

DOT = "\u00b7"
HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")


def markup_outside_scripts(html):
    """The page's markup with <script> and <style> bodies removed."""
    return re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", html, flags=re.S)


class AppCopyTest(unittest.TestCase):
    def test_the_translation_table_has_none(self):
        start = HTML.index("  const L = {")
        table = HTML[start:HTML.index("\n  };", start)]
        for probe in ("staleSite:'Tarkista", "staleSite:'Kontrollera", "staleSite:'Check"):
            self.assertIn(probe, table, "the table was not found whole")
        self.assertNotIn(DOT, table)
        self.assertNotIn("\\u00b7", table)

    def test_the_static_markup_has_none(self):
        self.assertNotIn(DOT, markup_outside_scripts(HTML))

    def test_the_css_draws_no_dot(self):
        for style in re.findall(r"<style\b[^>]*>(.*?)</style>", HTML, re.S):
            self.assertNotRegex(style, r"content:\s*['\"](\\0*b7|" + DOT + ")")


class StaticPagesTest(unittest.TestCase):
    def test_the_status_page_has_none(self):
        self.assertNotIn(DOT, (_ctx.ROOT / "status/index.html").read_text(encoding="utf-8"))

    def test_the_privacy_page_has_none(self):
        self.assertNotIn(DOT, (_ctx.ROOT / "tietosuoja/index.html").read_text(encoding="utf-8"))


class GeneratorCopyTest(unittest.TestCase):
    """The generated pages' own words: their language tables, stylesheet and subtitle."""

    @classmethod
    def setUpClass(cls):
        import build_pages as bp
        cls.bp = bp

    def test_the_language_tables_have_none(self):
        for lang, table in self.bp.L.items():
            for key, value in table.items():
                if isinstance(value, str):
                    with self.subTest(lang=lang, key=key):
                        self.assertNotIn(DOT, value)

    def test_the_stylesheet_draws_no_dot(self):
        self.assertNotRegex(self.bp.CSS, r"content:\s*['\"](\\+0*b7|" + DOT + ")")

    def test_a_cinema_page_s_subtitle_is_two_spans(self):
        self.assertEqual(self.bp.sub_html(("Pori", "finnkino.fi")),
                         '<span class="city">Pori</span><span class="sr-only">, </span>'
                         '<span class="host">finnkino.fi</span>')
        self.assertEqual(self.bp.sub_html("12 teatteria"), "12 teatteria")


if __name__ == "__main__":
    unittest.main()
