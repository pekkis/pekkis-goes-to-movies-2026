"""Finnkino's synopses go in the slot their language gives them, in films.json.

On 2026-09-27 "fi" held English for NT LIVE: All My Sons and "en" only the title for
Pressure, and the app sheet showed both as the language the slot claimed.
"""
import unittest

import _ctx                                                # noqa: F401
import fetch_data
import test_finnkino_partial as tfp

EN = "The hardest part of ending is starting again, and the band is back on the road."
FI = ("Hän on nuori ohjaaja, joka yrittää herättää henkiin elokuvasarjan, ja kun hän "
      "kohtaa sen tähden, kaikki muuttuu.")
MIXED = "Nuori ohjaaja kohtaa tähden TEENAGE SEX AND DEATH AT CAMP MIASMA ja halun pyörteisiin"


class PlaceSynTest(unittest.TestCase):
    def test_english_in_fi_moves_to_en(self):
        self.assertEqual(fetch_data.place_syn({"fi": EN, "en": ""}), {"fi": "", "en": EN})

    def test_a_bare_title_is_dropped(self):
        self.assertEqual(fetch_data.place_syn({"fi": FI, "en": "The Dog Stars"}),
                         {"fi": FI, "en": ""})

    def test_an_unsettled_text_stays_in_its_slot(self):
        self.assertEqual(fetch_data.place_syn({"fi": MIXED, "en": ""}), {"fi": MIXED, "en": ""})

    def test_a_text_in_its_own_slot_wins(self):
        other = EN.replace("band", "group")
        self.assertEqual(fetch_data.place_syn({"fi": other, "en": EN}), {"fi": "", "en": EN})


class FilmsJsonTest(unittest.TestCase):
    setUp = tfp.SevenDayPublishTest.setUp
    restore_env = tfp.SevenDayPublishTest.restore_env
    stub = tfp.SevenDayPublishTest.stub
    published = tfp.SevenDayPublishTest.published

    def test_main_writes_placed_synopses(self):
        self.stub()
        orig = tfp.showtimes_for

        def with_syn(date):
            doc = orig(date)
            a, b = doc["relatedData"]["films"]
            a["synopsis"] = {"text": EN}
            b["synopsis"] = {"text": FI, "translations": [{"languageTag": "en-US",
                                                           "text": "Film B"}]}
            return doc
        tfp.showtimes_for = with_syn
        self.addCleanup(lambda: setattr(tfp, "showtimes_for", orig))
        self.assertEqual(fetch_data.main(), 0, self.err.getvalue())
        films = self.published()["films.json"]["films"]
        self.assertEqual({f: films[f]["s"] for f in films},
                         {"10": {"fi": "", "en": EN}, "11": {"fi": FI, "en": ""}})


if __name__ == "__main__":
    unittest.main()
