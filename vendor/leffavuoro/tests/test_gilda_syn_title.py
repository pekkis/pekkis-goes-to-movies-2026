"""Gilda: a Finnish blurb is placed without the film's own English title in it.

On 2026-09-28 "70mm: The Odyssey" and "The Lighthouse" had Finnish descriptions that
syn_language placed nowhere, because the title inside them counts as English. The title
is left out of the judgement only; the published text is unchanged.
"""
import io
import unittest
from contextlib import redirect_stdout

import _ctx                                                # noqa: F401
import gilda
from test_gilda_duplicates import SITE, film, payload, show

FI = ("Hypnoottinen The Lighthouse kertoo kahdesta majakanvartijasta syrjäisellä ja "
      "mystisellä saarella myrskyn keskellä.")
EN = ("The film follows two keepers on a remote island, and the storm is the thing that "
      "breaks them.")


def described(movie_id, name, text, original=None):
    shows = [show(movie_id, name, f"2026-09-30T1{h}:00:00+00:00",
                  original_title=original or name) for h in (5, 8)]
    return {**film(movie_id, name, shows), "description": f"<p>{text}</p>"}


class TitleLeftOutTest(unittest.TestCase):
    def syn(self, *films):
        with redirect_stdout(io.StringIO()):
            rows = gilda.parse(payload(*films), SITE)["gd-gilda"]
        return {r["title"]: r.get("_syn") for r in rows}

    def test_a_finnish_blurb_with_an_english_title_is_finnish(self):
        self.assertEqual(self.syn(described(1, "The Lighthouse", FI)),
                         {"The Lighthouse": {"fi": FI}})

    def test_a_strand_prefix_does_not_hide_the_title(self):
        self.assertEqual(self.syn(described(1, "70mm: The Lighthouse", FI)),
                         {"70mm: The Lighthouse": {"fi": FI}})

    def test_the_original_title_is_left_out_too(self):
        self.assertEqual(self.syn(described(1, "Majakka", FI, original="The Lighthouse")),
                         {"Majakka": {"fi": FI}})

    def test_a_text_that_places_whole_is_unchanged(self):
        self.assertEqual(self.syn(described(2, "The Lighthouse", EN)),
                         {"The Lighthouse": {"en": EN}})

    def test_a_title_that_carries_the_evidence_is_kept(self):
        """Judged whole first: here the title's own words are what make it Finnish."""
        text = "Kun hän ja minä kertoo kahdesta sisaresta."
        self.assertEqual(self.syn(described(4, "Kun hän ja minä", text)),
                         {"Kun hän ja minä": {"fi": text}})

    def test_a_placeholder_is_still_withheld(self):
        self.assertEqual(self.syn(described(3, "Hunger Games Maraton", "Not Supplied")),
                         {"Hunger Games Maraton": None})


if __name__ == "__main__":
    unittest.main()
