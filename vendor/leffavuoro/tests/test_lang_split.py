"""A screening's language is the screening's, on its own ticket, everywhere (2026-09-23).

From 2026-09-20 the app put a film's language once in its details row when every
screening agreed and on each ticket when they did not, so one list showed it in two
places depending on the film (Hetki ennen valoa split on a single Riviera screening with
English subtitles beside the rest with Swedish). The maintainer asked for one place: each
ticket carries its screening's audio and subtitles as its own line, the details rows never
do, and a screening that states none shows none. A screening's value is still never
borrowed from a neighbour. The generated pages follow the same rule (tests in
test_landing_pages.py).
"""
import re
import unittest

import _ctx


HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")


class LanguageLineTest(unittest.TestCase):
    def test_every_ticket_draws_its_own_screening_s_language(self):
        """The card's stub and the sheet's stub each draw it whenever the screening has one."""
        self.assertIn("<span class=\"aud${t.lang ? ' twoline' : ''}\">", HTML)
        self.assertIn("<span class=\"aud${s.lang ? ' twoline' : ''}\">", HTML)
        self.assertIn("${t.lang ? slangHtml(t.lang, facts.length > 0) : ''}", HTML)  # the card's stub
        self.assertIn("${s.lang ? slangHtml(s.lang, facts.length > 0) : ''}", HTML)  # the sheet's stub
        self.assertEqual(len(re.findall(r'class="slang"', HTML)), 1, "one builder for both")

    def test_the_details_rows_never_carry_it(self):
        meta2 = re.search(r"const meta2 = \[(.*?)\]\.filter", HTML, re.S).group(1)
        self.assertNotIn("langTxt", meta2)
        self.assertIn("const sheetMeta2 = genresOf(sample) ?", HTML)
        sheet = HTML[HTML.index("const sheetMeta2 ="):]
        self.assertNotIn("langTxt", sheet[:sheet.index(";")])
        self.assertNotIn("langSplit", HTML)
        self.assertNotRegex(HTML, r"\bm\.lang\b")

    def test_the_card_no_longer_folds_lang_off_the_first_screening(self):
        """The line the 2026-09-20 rule replaced read `if(!m.lang && s.lang) m.lang = s.lang;`."""
        self.assertNotIn("if(!m.lang && s.lang)", HTML)

    def test_the_language_line_is_the_last_item_in_its_compartment(self):
        """`.slang` takes a full row, so anything after it lands on a third line."""
        seen = 0
        for m in re.finditer(r'<span class="aud\$\{[^"]*?"[^>]*>(.*?)</span><span class="price"',
                             HTML, re.S):
            body = m.group(1)
            if "slangHtml(" not in body:
                continue
            seen += 1
            self.assertGreater(body.index("slangHtml("), body.index("glyphRow"),
                               "the language line must follow the glyph row")
        self.assertEqual(seen, 2, "both stubs checked")

    def test_the_glyph_centres_on_the_whole_compartment_not_its_first_row(self):
        """Reported 2026-09-20: the Anniskelu A looked high on a ticket whose language
        line made the compartment two rows, because a flex item centres inside its own
        wrapped row. The glyphs now have a grid column spanning both rows, centred on it.
        Explicit rows and `span 2`: a negative line counts from the explicit grid in
        WebKit, which broke the landing pages on 2026-09-18."""
        rule = re.search(r"\.stub \.aud\.twoline \.glyphs\{(.*?)\}", HTML, re.S).group(1)
        flat = rule.replace(" ", "").replace("\n", "")
        self.assertIn("grid-column:2", flat)
        self.assertIn("grid-row:1/span2", flat)
        self.assertIn("align-self:center", flat)
        self.assertNotIn("position:absolute", flat)

    def test_the_room_and_language_cannot_run_under_the_glyphs(self):
        """Reported 2026-09-23: an absolute glyph behind a fixed 24 px reservation fitted
        one glyph, and A with 18+ covered the room and the language in the film view at
        1200 in both engines. The text takes the first column, the glyphs the second, so
        the reservation is whatever the glyphs measure. Both selectors, because
        `.stubs.grid .stub .aud` sets display at a higher specificity."""
        self.assertIn(".stub .aud.twoline,\n  .stubs.grid .stub .aud.twoline{display:grid; "
                      "grid-template-columns:minmax(0,1fr) auto;", HTML)
        self.assertIn(".stub .aud.twoline .loc{grid-column:1; grid-row:1}", HTML)
        self.assertIn(".stub .aud.twoline .slang{grid-column:1; grid-row:2}", HTML)
        self.assertNotIn("padding-right:24px", HTML)

    def test_it_reuses_the_existing_translation_helper(self):
        """No second language table: langParts already localises fi, sv and en, for the
        tickets and for the Ajat line alike."""
        self.assertEqual(len(re.findall(r"const LW = \{", HTML)), 1)
        self.assertIn("factSpans(langParts(code).map(p => ['', esc(p)]))", HTML)
        self.assertIn("...langParts(s.lang, !pre.length).map(x => ['', esc(x)])", HTML)

    def test_a_narrow_ticket_breaks_between_the_spoken_and_the_subtitle_part(self):
        """Asked for 2026-09-23: when the line does not fit, the spoken language keeps its
        line and the subtitles take the next, with no dot left at either end. Measured
        that day on Helsinki in Chromium and WebKit: at 393 px 6 of 10 card lines stack
        and 4 fit on one, at 1200 all fit; the dot shows exactly when the parts share a
        line. The separator, a square since 2026-09-23, is the later part's ::before, laid in
        the padding it hangs into the clipped margin with when that part starts a line."""
        self.assertIn(".stub .slang{overflow:hidden; min-width:0}", HTML)
        self.assertIn(".fx, .stub .slang .lp{display:flex; flex-wrap:wrap; margin-left:-9px; min-width:0}",
                      HTML)
        self.assertIn(".fx > span, .stub .slang .lp > span{position:relative; padding-left:9px; "
                      "min-width:0}", HTML)
        self.assertIn(".fx > span + span::before, .stub .slang .lp > span + span::before{\n"
                      "    content:''; display:inline-block; vertical-align:middle;\n"
                      "    width:3px; height:3px; margin:0 3px 0 -6px;", HTML)


if __name__ == "__main__":
    unittest.main()
