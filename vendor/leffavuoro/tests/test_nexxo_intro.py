"""Nexxo: the synopsis is in `intro`, judged paragraph by paragraph.

`description` was empty for all 74 films on the eight Nexxo sites on 2026-09-28, so none
published a synopsis. `intro` holds the blurb with the screening's notes between its
paragraphs: a bold festival or dub line, "Puhuttu suomeksi.", a price, the cinema's name.
"""
import unittest

import _ctx                                                # noqa: F401
import nexxo
from test_nexxo_rooms import PLAIN_VENUE, row

FI1 = ("Kaksi toisilleen tuntematonta ihmistä kohtaavat ystäviensä häissä, ja kun he "
       "tapaavat, kaikki muuttuu heidän elämässään.")
FI2 = "Hän on ohjaaja, joka palaa kotiin ja kun hän näkee äitinsä, kaikki on toisin kuin ennen."
SV1 = ("Två främlingar möter varandra på ett bröllop, och när de ses så förändras allt för "
       "dem, och det är inte som det var förr.")
SV2 = ("Hon är en skådespelare som har spelat på många scener och i flera tv-serier, och hon "
       "har gett ut två album.")
INTRO = (f"<p><strong>Tämä on elokuvan suomeksi dubattu versio, ja kun haluat nähdä toisen, "
         f"löydät sen täältä.</strong></p>\r\n"
         f"<p>{FI1}</p>\r\n<p>Puhuttu suomeksi.</p>\r\n"
         f"<p>Kino X:n sali on esteetön, ja kun hän tarvitsee apua, hän voi ottaa yhteyttä ennen "
         f"kuin tulee.</p>\r\n"
         f"<p>Liput maksavat 10€ ja ne voi varata etukäteen.</p>\r\n<p>{FI2}</p>")
SITE = {"provider": "kinox", "label": "Kino X", "base": "https://api.example",
        "programme": "/ohjelmisto/", "venues": [PLAIN_VENUE]}


class IntroSynTest(unittest.TestCase):
    def test_the_notes_are_left_out(self):
        self.assertEqual(nexxo.intro_syn(INTRO, names=("Kino X",)), {"fi": FI1 + " " + FI2})

    def test_a_bold_run_inside_a_paragraph_keeps_it(self):
        text = f"<p><strong>Kaksi</strong> {FI1[6:]}</p>"
        self.assertEqual(nexxo.intro_syn(text), {"fi": FI1})

    def test_the_most_common_language_is_kept(self):
        text = f"<p>{FI1}</p><p>{SV1}</p><p>{SV2}</p>"
        self.assertEqual(nexxo.intro_syn(text), {"sv": SV1 + " " + SV2})

    def test_nothing_placed_nothing_published(self):
        self.assertEqual(nexxo.intro_syn("<p>Puhuttu suomeksi.</p>"), {})
        self.assertEqual(nexxo.intro_syn(None), {})


class ParseTest(unittest.TestCase):
    def shows(self, **fields):
        r = {**row(1, "Kino X", "Film A"), **fields}
        later = {**r, "startTime": "2026-09-02 20:00:00"}
        return nexxo.parse({"shows": {"2026-09-02": [r, later]}}, SITE, PLAIN_VENUE)

    def test_a_row_publishes_its_intro(self):
        self.assertEqual([s["_syn"] for s in self.shows(description="", intro=INTRO)],
                         [{"fi": FI1 + " " + FI2}] * 2)

    def test_a_description_goes_first(self):
        self.assertEqual([s["_syn"] for s in self.shows(description=f"<p>{SV1}</p>",
                                                         intro=INTRO)], [{"sv": SV1}] * 2)


if __name__ == "__main__":
    unittest.main()
