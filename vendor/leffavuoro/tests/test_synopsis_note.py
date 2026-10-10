"""A synopsis that is not in the reader's language says so (2026-09-22).

The Swedish sheet for "Hetki ennen valoa" drew Swedish controls, Swedish screening labels
and a Finnish synopsis, with nothing marking the change of language (docs/research/flow-review.md,
2026-09-22). `synPick` already preferred Swedish where it existed; what was missing was the
label for the case where it does not.

Nothing is translated to fix this. The note names the language the text is in, the
paragraph carries `lang` so a screen reader and hyphenation agree with it, and the film's
advertised title is untouched.

The selection itself is `tests/test_synopsis_lang_client.py`. This file covers the label:
when it appears, what it says, and that it exists in all three interface languages.
"""
import json
import re
import unittest

import _ctx


HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")
LANGS = ("fi", "sv", "en")
CODES = ("FI", "SV", "EN")


def lang_block(lang):
    """The `L.<lang>` object out of index.html."""
    m = re.search(rf"\n    {lang}: ?\{{(.*?)\n    \}},?\n", HTML, re.S)
    assert m, lang
    return m.group(1)


class TheStringsTest(unittest.TestCase):
    def test_every_interface_language_can_name_every_source_language(self):
        for lang in LANGS:
            block = lang_block(lang)
            m = re.search(r"synIn:\{(.*?)\}", block, re.S)
            self.assertIsNotNone(m, f"{lang} has no synIn")
            for code in CODES:
                with self.subTest(lang=lang, code=code):
                    self.assertRegex(m.group(1), rf"{code}: ?'[^']+'")

    def test_the_finnish_names_are_not_built_from_a_stem(self):
        """"suomi" + "ksi" is "suomiksi", and the three cases differ. The sentences are
        written out, the same reason city names are never inflected in generated text."""
        m = re.search(r"synIn:\{(.*?)\}", lang_block("fi"), re.S)
        for want in ("suomeksi", "ruotsiksi", "englanniksi"):
            with self.subTest(word=want):
                self.assertIn(want, m.group(1))

    def test_nothing_is_translated_into_the_note(self):
        """The note names a language. It never carries film text, which would be this app
        inventing a translation."""
        m = re.search(r"synIn:\{(.*?)\}", lang_block("en"), re.S)
        self.assertNotIn("{", m.group(1), "a placeholder here would take film text")


class TheRenderTest(unittest.TestCase):
    def sheet(self):
        a = HTML.index("    const synLong = syn.length > 260;")
        return HTML[a:a + 1400]

    def test_the_note_is_drawn_only_when_the_languages_differ(self):
        block = self.sheet()
        self.assertIn("picked.from && picked.from !== lang", block)

    def test_the_note_is_drawn_only_when_there_is_a_synopsis(self):
        self.assertIn("const synNote = (syn && picked.from", self.sheet())

    def test_the_paragraph_declares_the_language_it_is_in(self):
        self.assertIn('lang="${esc(picked.from)}"', self.sheet())

    def test_the_note_is_escaped_like_every_other_interpolation(self):
        self.assertIn("${esc(L[lang].synIn[picked.from.toUpperCase()]", self.sheet())

    def test_the_note_sits_above_the_text_it_describes(self):
        """Below it, a reader has already read the paragraph before being told what
        language it is in. The declaration is always above the template, so this reads the
        template itself: the note is what the synopsis markup opens with."""
        m = re.search(r"const synHtml = syn\n      \? (.*?)\n", self.sheet(), re.S)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1).strip(), "synNote")

    def test_it_has_a_style_of_its_own_and_reads_as_a_caption(self):
        """One rule, on tokens the sheet already uses, so the note is a caption above the
        description rather than a second paragraph of it."""
        i = HTML.index(".synlang{")
        rule = HTML[i:HTML.index("}", i) + 1]
        self.assertIn("var(--muted)", rule)
        self.assertIn("font-size:.76rem", rule)
        self.assertIn(".synlang + .syn{margin-top:4px}", HTML)


class TheLanguageToggleTest(unittest.TestCase):
    def test_the_sheet_is_redrawn_when_the_language_changes(self):
        """The note is the reader's language against the text's, so both halves move when
        the toggle does. `applyLang()` already syncs an open sheet; this holds that line."""
        m = re.search(r"function applyLang\(\)\{(.*?)\n  \}", HTML, re.S)
        self.assertIsNotNone(m)
        self.assertIn("syncSheet()", m.group(1))


if __name__ == "__main__":
    unittest.main()
