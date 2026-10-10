"""The footer says a price is indicative (2026-09-13).

The amounts on the tickets are what a provider publishes for a screening; the final
price is set at the cinema's checkout. One sentence in the footer, in the reader's
language, redrawn by renderContact() like the status link. No banner, no icon.
"""
import re
import unittest

import _ctx                                                # noqa: F401

HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")

NOTE = {
    "fi": "Suuntaa-antava hinta. Lopullinen hinta teatterin lipunmyynnissä.",
    "sv": "Riktpris. Slutligt pris i biografens biljettförsäljning.",
    "en": "Indicative price. Final price at the cinema’s ticket checkout.",
}


def block(lang):
    """One language block of the client's L table -> {key: string}, \\uXXXX resolved."""
    start = HTML.index(f"\n    {lang}:{{")
    nxt = {"fi": "\n    sv:{", "sv": "\n    en:{", "en": "\n  };"}[lang]
    text = HTML[start:HTML.index(nxt, start)]
    unescape = lambda v: re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)),
                                v.replace("\\'", "'"))
    return {k: unescape(v) for k, v in re.findall(r"(\w+):'((?:[^'\\]|\\.)*)'", text)}


class PriceNoteTest(unittest.TestCase):
    def test_the_sentence_is_in_the_static_footer(self):
        footer = re.search(r"<footer>(.*?)</footer>", HTML, re.S).group(1)
        self.assertIn(f'<div id="priceNote">{NOTE["fi"]}</div>', footer)

    def test_every_language_carries_it_verbatim(self):
        for lang, want in NOTE.items():
            self.assertEqual(block(lang)["priceNote"], want, lang)

    def test_the_language_toggle_redraws_it(self):
        self.assertRegex(HTML, r"#priceNote'\);\s*if\(note\) note\.textContent = L\[state\.lang\]\.priceNote;")

    def test_it_stays_one_line_of_the_footer(self):
        self.assertNotIn("#priceNote{", HTML)          # footer typography, nothing of its own
        self.assertEqual(HTML.count('id="priceNote"'), 1)


if __name__ == "__main__":
    unittest.main()
