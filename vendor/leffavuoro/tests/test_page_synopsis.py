"""A generated page falls back to Finnkino's own synopsis when films-extra has none.

The pages read films-extra.json by title only, while the app's sheet reads films.json by
Finnkino's film id first, so Mysteerinäytös, Operaatio Ave Maria and others had a
description in the app and none on 49 page cards (audit, 2026-09-27). Iso-Hannu's
"KÄTYRIT & MONSTERIT (suomeksi puhuttu)" has the TMDB id Finnkino's own pass trusted for
its "Kätyrit & Monsterit", and gets that text. Another cinema's text is never borrowed.
"""
import json
import pathlib
import re
import tempfile
import unittest
from unittest import mock

import _ctx                                                # noqa: F401
import build_pages as bp

FILMS = {"HO1": {"s": {"fi": "Suomenkielinen kuvaus elokuvasta, jossa tapahtuu paljon.",
                       "en": "Mystery"}},
         "HO2": {"s": {"fi": "The hardest part of ending is starting again, they said."}},
         "HO3": {"s": {"fi": "Toinen suomenkielinen kuvaus, joka kertoo elokuvan juonesta."}}}
NATIVE = (FILMS, {77: ["HO3"]})


def finnkino(fid="HO1", title="Mysteerinäytös"):
    return {"eventId": fid, "title": title, "start": "2026-09-27T18:00:00+03:00",
            "url": "https://www.finnkino.fi/", "rating": "", "len": ""}


def other(title="KÄTYRIT (suomeksi puhuttu)", tmdb=77, eid="HO1"):
    return {**finnkino(eid, title), "provider": "isohannu", "tmdbId": tmdb}


def syn(shows, extra=None, lang="fi", native=NATIVE, seen=None):
    html = bp.film_block(shows[0]["title"], shows, extra or {}, {lang: {}}, lang, bp.L[lang],
                         False, set() if seen is None else seen, current_year=2026,
                         native=native)
    m = re.search(r'<p class="syn">(.*?)</p>', html, re.S)
    return m.group(1) if m else ""


class NativeSynopsisTest(unittest.TestCase):

    def test_a_finnkino_card_takes_its_own_film_s_text(self):
        self.assertIn("Suomenkielinen kuvaus", syn([finnkino()]))

    def test_films_extra_still_comes_first(self):
        extra = {"mysteerinäytös": {"s": {"fi": "Teksti films-extrasta."}}}
        self.assertEqual(syn([finnkino()], extra), "Teksti films-extrasta.")

    def test_another_cinema_reaches_it_through_a_trusted_tmdb_id(self):
        self.assertIn("Toinen suomenkielinen", syn([other()]))

    def test_another_cinema_s_event_id_is_not_a_finnkino_film_id(self):
        self.assertEqual(syn([other(tmdb=None)]), "")

    def test_a_slot_in_another_language_or_only_a_title_is_skipped(self):
        self.assertEqual(syn([finnkino("HO2", "LINKIN PARK")]), "")
        self.assertEqual(syn([finnkino()], lang="en"), "")

    def test_only_the_first_appearance_carries_it(self):
        seen = set()
        self.assertTrue(syn([finnkino()], seen=seen))
        self.assertEqual(syn([finnkino()], seen=seen), "")

    def test_without_the_files_nothing_changes(self):
        self.assertEqual(syn([finnkino()], native=None), "")


class NativeIndexTest(unittest.TestCase):
    """Only an id Finnkino's pass trusted maps a TMDB id to a Finnkino film."""

    def test_a_weak_id_or_a_film_not_in_films_json_maps_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "films.json").write_text(json.dumps({"films": {"HO1": {}, "HO2": {}}}))
            (d / "tmdb.json").write_text(json.dumps({"HO1": {"i": 5, "x": True},
                                                     "HO2": {"i": 6, "x": False},
                                                     "HO9": {"i": 7, "x": True}}))
            with mock.patch.object(bp, "DATA", d):
                self.assertEqual(bp.native_synopses()[1], {5: ["HO1"]})

    def test_missing_files_read_as_none(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(bp, "DATA", pathlib.Path(d)):
            self.assertEqual(bp.native_synopses(), ({}, {}))


if __name__ == "__main__":
    unittest.main()
