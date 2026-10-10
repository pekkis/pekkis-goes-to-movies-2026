"""A festival prefix is not the film's name, on the fallback tile (2026-09-20).

Reported from the live site: the Rakkautta & Anarkiaa films at Cinema Orion had no
posters. 29 of the 30 R&A titles had no TMDB match, and the fallback tile made that worse
than it had to be: the word split is on letters, so `&` and `:` break "R&A:" into two
words and every one of the 30 drew the identical tile **RA**.

`tileInitials` takes the prefix off the two letters and off nothing else. It is display
only. `strands.py` refuses an "r&a" prefix split because searching the *stripped* title
would resolve one- and two-word names (Mouse, NOX, Redoubt, Blue Film) onto the wrong film
by popularity, none of them carrying a year; that refusal stands, and nothing here reaches
a search, a match, a merge key or the displayed title.

Sliced verbatim out of index.html by tests/tile_initials_harness.js.
"""
import json
import pathlib
import re
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "tile_initials_harness.js"
HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class TileInitialsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    def test_no_case_threw(self):
        self.assertEqual({k: v for k, v in self.r.items() if isinstance(v, dict)}, {})

    def test_the_festival_prefix_no_longer_eats_both_letters(self):
        """All 30 drew RA before this."""
        self.assertEqual(self.r["ra_two_words"], "DL")
        self.assertEqual(self.r["ra_finnish"], "YL")
        self.assertEqual(self.r["ra_one_word"], "N")
        self.assertEqual(self.r["ra_shorts"], "S")
        self.assertEqual(self.r["ra_digits"], "2F")

    def test_it_matches_however_the_cinema_spaces_and_cases_it(self):
        self.assertEqual(self.r["ra_spaced"], "BF")
        self.assertEqual(self.r["ra_lowercase"], "MO")

    def test_a_prefix_with_nothing_behind_it_keeps_its_letters(self):
        """Otherwise the tile would read "?" for a title that has letters in it."""
        self.assertEqual(self.r["ra_only"], "RA")
        self.assertEqual(self.r["ra_only_spaced"], "RA")

    def test_an_ordinary_title_is_untouched(self):
        self.assertEqual(self.r["plain"], "C")
        self.assertEqual(self.r["colon_franchise"], "DO")
        self.assertEqual(self.r["other_strand"], "SH")
        self.assertEqual(self.r["digits_only"], "2")

    def test_a_title_merely_starting_with_r_is_not_the_prefix(self):
        self.assertEqual(self.r["r_word"], "R")
        self.assertEqual(self.r["rafiki"], "RY")

    def test_nothing_usable_still_gives_the_placeholder(self):
        for key in ("empty", "null_title", "punctuation_only"):
            with self.subTest(key):
                self.assertEqual(self.r[key], "?")


class DisplayOnlyTest(unittest.TestCase):
    """The refusal in strands.py is not reversed by any of this."""

    def test_the_prefix_list_is_not_used_for_matching(self):
        block = re.search(r"// --- tileInitials.*?// --- end tileInitials ---", HTML, re.S).group(0)
        # The code only: the comment above it explains the refusal and names those words.
        code = "\n".join(l for l in block.split("\n") if not l.strip().startswith("//"))
        for forbidden in ("normTitle", "mergeKey", "tmdb", "search", "eventId"):
            self.assertNotIn(forbidden, code, f"{forbidden} must not be reachable from the tile")

    def test_only_the_initials_read_it(self):
        self.assertEqual(len(re.findall(r"TILE_PREFIX", HTML)), 2, "declared once, used once")
        self.assertIn("const initials = tileInitials(title);", HTML)

    def test_the_displayed_title_keeps_the_marker(self):
        """`disp()` feeds the title; the tile takes a copy and strips nothing from it."""
        card = re.search(r"const card = m => \{(.*?)const posterUrl", HTML, re.S).group(1)
        self.assertIn("const title = disp(m);", card)
        self.assertIn("filmTitle(title, m.oyear, fiYear())", card)

    def test_strands_still_refuses_the_blanket_split(self):
        strands = (_ctx.ROOT / "scripts" / "providers" / "strands.py").read_text(encoding="utf-8")
        self.assertIn('"r&a"', strands, "the recorded refusal must stay in the file")
        self.assertNotIn('"r&a",', strands.split("EVENT_PREFIXES = (")[1].split(")")[0]
                         .replace('and "r&a"', ""), "r&a must not be in the active list")

    def test_the_two_aliases_are_present_and_reasoned(self):
        raw = (_ctx.ROOT / "scripts" / "providers" / "tmdb-aliases.json").read_text(encoding="utf-8")
        aliases = json.loads(raw)
        self.assertEqual(aliases.get("r a yön lapsi"), "964849")
        self.assertEqual(aliases.get("r a teenage sex and death at camp miasma"), "1240889")
        note = aliases.get("_comment_2026_09_20_ra", "")
        self.assertIn("does NOT reverse", note)
        self.assertIn("Hanna Bergholm", note, "the record, not the title, is what was checked")
        self.assertIn("Jane Schoenbrun", note)

    def test_no_other_ra_title_was_aliased(self):
        """Explicitly not a pass over every festival title."""
        aliases = json.loads((_ctx.ROOT / "scripts" / "providers"
                              / "tmdb-aliases.json").read_text(encoding="utf-8"))
        ra = [k for k in aliases if k.startswith("r a ") and not k.startswith("_")]
        # "r a mouse" predates this change and is the one R&A row that already had a
        # poster. Two were added here, and no sweep of the remaining 27.
        self.assertEqual(sorted(ra), ["r a mouse",
                                      "r a teenage sex and death at camp miasma",
                                      "r a yön lapsi"])


if __name__ == "__main__":
    unittest.main()
