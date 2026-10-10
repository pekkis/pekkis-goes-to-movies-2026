"""Four codes in the committed data were not in the client's name table, and each was a
defect somewhere else (measured 2026-09-02): `TU` and `MA` are Finnkino's own vocabulary
for Turkish and Malayalam, `XX` is Nexxo's "no subtitles", `LT` is Lithuanian and simply
missing. The app showed all four raw; the landing pages aliased them. These tests pin the
fixes at their sources. The landing-page aliases that covered the data meanwhile were
deleted on 2026-09-15, once no committed `data/area-*.json` carried TU, MA or XX.

A fifth arrived on 2026-09-22: `LI`, Finnkino's own for Lithuanian, on the two
"Sve\u010dias \u2013 The Visitor" rows at Kinopalatsi Helsinki. It reached the committed data
and the app drew the raw code; the fix is one more entry in the same table, at the same
source.

Provider modules are imported inside the tests rather than at module level: they bind
`common.EmptyProgramme` at import time and `test_common_fetch` reloads `common`, so a
module-level import here would make the suite's result depend on file order.
"""
import json
import re
import shutil
import subprocess
import unittest
from itertools import product
from string import ascii_uppercase

import _ctx


HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")


def client_tables():
    """`LN.fi`, `LN.sv` and `LN.en` read out of index.html, in source order."""
    block = re.search(r"const LN = \{(.*?)\n  \};", HTML, re.S).group(1)
    out = {}
    for lang in ("fi", "sv", "en"):
        body = re.search(rf"\b{lang}:\{{(.*?)\}}", block, re.S).group(1)
        out[lang] = dict(re.findall(r"([A-Z]{2}):'([^']*)'", body))
    return out


class FinnkinoLangTagTest(unittest.TestCase):
    """`fetch_data.lang_tag`: the OCAPI attribute becomes this app's tag, with Finnkino's
    non-ISO codes mapped on the way. `SE` -> `SV` has worked this way since 2026-08-29."""

    def tag(self, lbl):
        import fetch_data
        return fetch_data.lang_tag(lbl)

    def test_tu_is_turkish_in_both_roles(self):
        self.assertEqual(self.tag(".TU-A"), "TR-A")
        self.assertEqual(self.tag(".TU-S"), "TR-S")

    def test_ma_is_malayalam_in_both_roles(self):
        self.assertEqual(self.tag(".MA-A"), "ML-A")
        self.assertEqual(self.tag(".MA-S"), "ML-S")

    def test_li_is_lithuanian_in_both_roles(self):
        self.assertEqual(self.tag(".LI-A"), "LT-A")
        self.assertEqual(self.tag(".LI-S"), "LT-S")

    def test_swedish_still_maps_and_a_compound_keeps_its_shape(self):
        self.assertEqual(self.tag(".FI-SE-A"), "FI-SV-A")
        self.assertEqual(self.tag(".TU-SE-S"), "TR-SV-S")
        self.assertEqual(self.tag(".FI-S"), "FI-S")
        self.assertEqual(self.tag("EN-A"), "EN-A")

    def test_no_other_code_changes(self):
        """Every other two-letter code passes through untouched, in both roles."""
        import fetch_data
        for a, b in product(ascii_uppercase, repeat=2):
            code = a + b
            if code in fetch_data.FINNKINO_LANG:
                continue
            with self.subTest(code=code):
                self.assertEqual(self.tag(f".{code}-A"), f"{code}-A")
                self.assertEqual(self.tag(f".{code}-S"), f"{code}-S")

    def test_the_map_is_exactly_these_four(self):
        """Adding a fifth is a decision about Finnkino's vocabulary and gets written
        here first."""
        import fetch_data
        self.assertEqual(fetch_data.FINNKINO_LANG,
                         {"SE": "SV", "TU": "TR", "MA": "ML", "LI": "LT"})


class NexxoLangTest(unittest.TestCase):
    """`nexxo._lang`: code_language / code_subtitles -> `FI-A, SV-S`. `XX` alone in the
    subtitle column is a screening without subtitles, `XX-S`."""

    TAG_LIST = re.compile(r"^[A-Z]{2}-[AS](?:, [A-Z]{2}-[AS])*$")

    def lang(self, language, subtitles):
        import nexxo
        return nexxo._lang({"code_language": language, "code_subtitles": subtitles})

    def test_xx_alone_is_no_subtitles(self):
        """Kino Aurora's Rakkautta ja virtahepoja and Kino Marilyn's, read 2026-10-04."""
        self.assertEqual(self.lang("FI", "XX"), "FI-A, XX-S")
        self.assertEqual(self.lang("EN", "XX"), "EN-A, XX-S")
        self.assertEqual(self.lang("OV", "XX"), "XX-S")
        self.assertEqual(self.lang("", "XX"), "XX-S")
        self.assertEqual(self.lang(None, "XX"), "XX-S")

    def test_xx_beside_a_real_subtitle_code_drops_only_itself(self):
        self.assertEqual(self.lang("FI", "XX/SE"), "FI-A, SV-S")
        self.assertEqual(self.lang("FI", "SE/XX"), "FI-A, SV-S")
        self.assertEqual(self.lang("FI-SE", "XX"), "FI-A, SV-A, XX-S")

    def test_ov_subtitles_say_nothing(self):
        """Kino Hirvi's unknown subtitle is OV, not XX."""
        self.assertEqual(self.lang("OV", "OV"), "")
        self.assertEqual(self.lang("FI", "OV"), "FI-A")

    def test_existing_semantics_are_untouched(self):
        """Compounds split, SE becomes SV, OV is unspecified and dropped, LT passes as
        the real code it is, and duplicates are kept here: the renderers collapse them."""
        self.assertEqual(self.lang("FI", "SE"), "FI-A, SV-S")
        self.assertEqual(self.lang("FI-SE", "FI"), "FI-A, SV-A, FI-S")
        self.assertEqual(self.lang("OV", "FI"), "FI-S")
        self.assertEqual(self.lang("LT", "FI"), "LT-A, FI-S")
        self.assertEqual(self.lang("FI/FI", "FI"), "FI-A, FI-A, FI-S")
        self.assertEqual(self.lang("", ""), "")
        self.assertEqual(self.lang(None, None), "")

    def test_the_withdrawn_hebrew_code_becomes_he(self):
        """Kino Aurora's "Naza", 2026-10-02: IW-A beside EN-S."""
        self.assertEqual(self.lang("IW", "EN"), "HE-A, EN-S")
        self.assertEqual(self.lang("EN-IW", "FI/IW"), "EN-A, HE-A, FI-S, HE-S")

    def test_every_output_is_a_well_formed_tag_list_or_empty(self):
        cases = [("FI", "XX"), ("", "XX"), ("OV", "XX"), ("FI", "XX/SE"), ("FI-SE", "XX"),
                 ("EN", "FI/XX"), ("SV", "XX"), ("FI", "SE"), ("", "")]
        for language, subtitles in cases:
            with self.subTest(language=language, subtitles=subtitles):
                out = self.lang(language, subtitles)
                self.assertTrue(out == "" or self.TAG_LIST.match(out), repr(out))


class NameTableTest(unittest.TestCase):
    """The client's `LN` gained LT and ML in all three UI languages; the generator's
    mirror is held equal to fi and en by `tests/test_landing_pages.py`."""

    def test_lt_and_ml_have_names_in_every_client_table(self):
        t = client_tables()
        self.assertEqual((t["fi"]["LT"], t["fi"]["ML"]), ("liettua", "malajalam"))
        self.assertEqual((t["sv"]["LT"], t["sv"]["ML"]), ("litauiska", "malayalam"))
        self.assertEqual((t["en"]["LT"], t["en"]["ML"]), ("Lithuanian", "Malayalam"))

    def test_the_three_tables_share_one_key_order_and_the_new_codes_come_last(self):
        """Ordering preserved: the existing keys keep their sequence in every table and the
        additions are appended, so a diff of the tables reads as two entries."""
        t = client_tables()
        self.assertEqual(list(t["fi"]), list(t["sv"]))
        self.assertEqual(list(t["fi"]), list(t["en"]))
        self.assertEqual(list(t["fi"])[-9:],
                         ["LT", "ML", "FA", "HE", "PS", "EL", "NE", "RO", "YI"])
        self.assertEqual(len(t["fi"]), 33)

    def test_the_names_follow_the_tables_style(self):
        """Lower-case nominatives in fi and sv, capitalised in en, like every neighbour."""
        t = client_tables()
        for code in ("LT", "ML", "FA", "HE", "PS", "EL", "NE", "RO", "YI"):
            with self.subTest(code=code):
                self.assertTrue(t["fi"][code].islower() and t["sv"][code].islower())
                self.assertTrue(t["en"][code][0].isupper())

    def test_the_new_names_render_through_the_generator(self):
        import build_pages as bp
        self.assertEqual(bp.lang_parts("LT-A, FI-S", "fi"), ["liettua", "tekstitys: suomi"])
        self.assertEqual(bp.lang_parts("LT-A, FI-S", "en"), ["Lithuanian", "Finnish subtitles"])
        self.assertEqual(bp.lang_parts("ML-A, EN-S", "fi"), ["malajalam", "tekstitys: englanti"])
        self.assertEqual(bp.lang_parts("ML-A, EN-S", "en"), ["Malayalam", "English subtitles"])


def client_lang_txt(lang, calls):
    """Run the app's `langTxt` block verbatim in node. -> langParts' list per (code, lead)."""
    block = re.search(r"// --- langTxt: [^\n]*\n(.*?)\n\s*// --- end langTxt ---", HTML, re.S).group(1)
    js = (f"const state = {{lang: {json.dumps(lang)}}};\n{block}\n"
          f"process.stdout.write(JSON.stringify({json.dumps(calls)}.map(([c, l]) => langParts(c, l))));")
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
    if out.returncode:
        raise AssertionError(out.stderr)
    return json.loads(out.stdout)


class SwedishSubtitleLabelTest(unittest.TestCase):
    """"Textning:" opens a label of its own; after the audio or another part of the line it
    is "textning:". The app and the generated pages say the same thing."""

    CASES = [("EN-A, FI-S", True, "engelska · textning: finska"),
             ("FI-S, SV-S", True, "Textning: finska/svenska"),
             ("FI-S, SV-S", False, "textning: finska/svenska"),
             ("FI-A", True, "finska"),
             ("", True, "")]

    def test_the_generator(self):
        import build_pages as bp
        for code, lead, want in self.CASES:
            with self.subTest(code=code, lead=lead):
                self.assertEqual(" · ".join(bp.lang_parts(code, "sv", lead=lead)), want)
        # Finnish and English have one form wherever the phrase stands.
        self.assertEqual(bp.lang_parts("FI-S", "fi"), ["tekstitys: suomi"])
        self.assertEqual(bp.lang_parts("FI-S", "en"), ["Finnish subtitles"])

    def test_a_ticket_s_own_language_line_opens_its_label(self):
        """The language is the stub's own line (2026-09-23), so the label opens it."""
        import build_pages as bp
        self.assertIn("<span>Textning: finska/<wbr>svenska</span>",
                      bp.lang_line({"aud": "Sali 2", "lang": "FI-S, SV-S"}, "sv"))
        self.assertIn('<span>engelska<span class="sr-only">, </span></span><span>textning: finska</span>',
                      bp.lang_line({"lang": "EN-A, FI-S"}, "sv"))
        self.assertEqual(bp.lang_line({"lang": ""}, "sv"), "")
        self.assertEqual(bp.stub_parts({"aud": "Sali 2", "lang": "FI-S"}, False, "sv"),
                         [("a", "Sali 2")])

    @unittest.skipIf(shutil.which("node") is None, "node not installed")
    def test_the_app_matches_the_generator(self):
        import build_pages as bp
        got = client_lang_txt("sv", [[c, l] for c, l, _ in self.CASES])
        for (code, lead, want), g in zip(self.CASES, got):
            with self.subTest(code=code, lead=lead):
                self.assertEqual(" · ".join(g), want)      # the parts, joined as CASES writes them
                self.assertEqual(g, bp.lang_parts(code, "sv", lead=lead))
        self.assertEqual(client_lang_txt("fi", [["FI-S", True]]), [["tekstitys: suomi"]])


class NoSubtitlesTest(unittest.TestCase):
    """`XX-S` is a source saying outright that there are no subtitles (Kino Engel's "Ei
    tekstitystä", 2026-09-29). The app and the pages say it in words, the same words in
    Finnish and Swedish; English follows each one's own subtitle label, "subs" on a ticket
    and "subtitles" on a page. A named subtitle language wins over it."""

    CASES = [["SV-A, XX-S", True], ["XX-S", True], ["XX-S", False], ["FI-S, XX-S", True]]
    WANT = {"fi": [["ruotsi", "ei tekstitystä"], ["ei tekstitystä"], ["ei tekstitystä"],
                   ["tekstitys: suomi"]],
            "sv": [["svenska", "ingen textning"], ["Ingen textning"], ["ingen textning"],
                   ["Textning: finska"]]}

    def test_the_generator(self):
        import build_pages as bp
        for lang, want in self.WANT.items():
            with self.subTest(lang=lang):
                self.assertEqual([bp.lang_parts(c, lang, lead=l) for c, l in self.CASES], want)
        self.assertEqual(bp.lang_parts("SV-A, XX-S", "en"), ["Swedish", "no subtitles"])

    @unittest.skipIf(shutil.which("node") is None, "node not installed")
    def test_the_app_says_the_same(self):
        for lang, want in self.WANT.items():
            with self.subTest(lang=lang):
                self.assertEqual(client_lang_txt(lang, self.CASES), want)
        self.assertEqual(client_lang_txt("en", [["SV-A, XX-S", True]]), [["Swedish", "no subtitles"]])

    def test_the_page_line_carries_it(self):
        import build_pages as bp
        self.assertIn("<span>ingen textning</span>", bp.lang_line({"lang": "SV-A, XX-S"}, "sv"))


if __name__ == "__main__":
    unittest.main()
