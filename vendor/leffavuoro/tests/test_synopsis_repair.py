"""synmerge.repair_from_twin: transcribe from a copy we hold, never guess.

Finnkino publishes "Catherine Laga?aia" where the name carries an okina; the pipeline does
not cause it (json.loads raises on malformed UTF-8, and the decode uses errors="replace",
which yields U+FFFD). A "?" could be an apostrophe, an okina or a real question mark, so
the substitution is made only against another chain's copy of the same sentence, and only
where that copy agrees everywhere else.
"""
import unittest

import _ctx                                                # noqa: F401
import synmerge


def films(fi, title="Vaiana"):
    return {"HO1": {"t": {"fi": title}, "s": {"fi": fi}}}


def extra(fi, title="vaiana"):
    return {title: {"s": {"fi": fi}}}


BAD = "Vaiana (Catherine Laga?aia) ja Auli?i Cravalho."
GOOD = "Vaiana (Catherine Lagaʻaia) ja Auliʻi Cravalho."


class RepairFromTwinTest(unittest.TestCase):
    def test_restores_every_replaced_character(self):
        f = films(BAD)
        self.assertEqual(synmerge.repair_from_twin(f, extra(GOOD)), 2)
        self.assertEqual(f["HO1"]["s"]["fi"], GOOD)

    def test_a_twin_that_differs_elsewhere_is_not_used(self):
        """The whole point. A different synopsis for the same title is not a source of
        truth about this one, however close it looks."""
        other = GOOD.replace("Vaiana", "Vaiaka")
        f = films(BAD)
        self.assertEqual(synmerge.repair_from_twin(f, extra(other)), 0)
        self.assertEqual(f["HO1"]["s"]["fi"], BAD)

    def test_a_real_question_mark_survives(self):
        text = "Mitä tapahtui? Kukaan ei tiedä."
        f = films(text)
        self.assertEqual(synmerge.repair_from_twin(f, extra(text)), 0)
        self.assertEqual(f["HO1"]["s"]["fi"], text)

    def test_a_twin_that_is_also_broken_changes_nothing(self):
        f = films(BAD)
        self.assertEqual(synmerge.repair_from_twin(f, extra(BAD)), 0)
        self.assertEqual(f["HO1"]["s"]["fi"], BAD)

    def test_a_different_length_twin_is_ignored(self):
        f = films(BAD)
        self.assertEqual(synmerge.repair_from_twin(f, extra(GOOD + " Lisää tekstiä.")), 0)
        self.assertEqual(f["HO1"]["s"]["fi"], BAD)

    def test_no_twin_at_all_is_not_an_error(self):
        f = films(BAD)
        self.assertEqual(synmerge.repair_from_twin(f, {}), 0)
        self.assertEqual(f["HO1"]["s"]["fi"], BAD)

    def test_the_title_is_matched_through_the_shared_normalisation(self):
        """films-extra.json is keyed by synmerge.norm(), not by the raw title, so a
        lookup on the raw string would silently never hit."""
        f = films(BAD, title="Vaiana (liveaction)")
        self.assertEqual(synmerge.repair_from_twin(f, extra(GOOD, "vaiana liveaction")), 2)

    def test_each_language_is_repaired_from_its_own_twin(self):
        f = {"HO1": {"t": {"fi": "Vaiana"}, "s": {"fi": BAD, "en": "Auli?i sings."}}}
        e = {"vaiana": {"s": {"fi": GOOD, "en": "Auliʻi sings."}}}
        self.assertEqual(synmerge.repair_from_twin(f, e), 3)
        self.assertEqual(f["HO1"]["s"]["en"], "Auliʻi sings.")

    def test_an_entry_with_no_synopsis_dict_is_skipped(self):
        f = {"HO1": {"t": {"fi": "Vaiana"}}, "HO2": {"t": {"fi": "X"}, "s": None}}
        self.assertEqual(synmerge.repair_from_twin(f, extra(GOOD)), 0)


if __name__ == "__main__":
    unittest.main()
