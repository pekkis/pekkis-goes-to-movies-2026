"""What a Nexxo `ageLimit` publishes as the screening's rating.

The client compares against "S" and "K-n" only (`kidsRated()`, the Lapsille filter), so a
value published in any other shape silently falls out of every filter. Kino Aurora sent a
lowercase "s" on two Animaatioaarteet screenings on 2026-09-25, published verbatim.
"""
import unittest

import _ctx                                                # noqa: F401
import nexxo
from test_nexxo_rooms import PLAIN_VENUE, SITE, row


class RatingTest(unittest.TestCase):

    def test_a_number_is_the_k_rating(self):
        self.assertEqual([nexxo.rating(a) for a in ("7", "12", "16", "18")],
                         ["K-7", "K-12", "K-16", "K-18"])

    def test_a_lowercase_s_is_the_general_rating(self):
        self.assertEqual(nexxo.rating("s"), "S")
        self.assertEqual(nexxo.rating(" S "), "S")

    def test_a_k_prefix_in_any_case_is_read(self):
        self.assertEqual([nexxo.rating(a) for a in ("K-12", "k12", "K 16")],
                         ["K-12", "K-12", "K-16"])

    def test_anything_else_is_no_rating(self):
        for a in ("", None, "Tulossa", "-", "Kaikille", "123"):
            with self.subTest(age=a):
                self.assertEqual(nexxo.rating(a), "")

    def test_the_parsed_show_carries_it_for_two_rows(self):
        p = {"shows": {"2026-10-14": [dict(row(1, "Sali 1", "Animaatioaarteet"), ageLimit="s"),
                                      dict(row(1, "Sali 1", "Film B"), ageLimit="12")]}}
        shows = nexxo.parse(p, SITE, PLAIN_VENUE)
        self.assertEqual({s["title"]: s["rating"] for s in shows},
                         {"Animaatioaarteet": "S", "Film B": "K-12"})


if __name__ == "__main__":
    unittest.main()
