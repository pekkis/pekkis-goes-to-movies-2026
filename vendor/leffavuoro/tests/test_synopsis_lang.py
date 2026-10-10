"""A synopsis carries a language, and each language is merged on its own.

`_syn` was a bare string until 2026-09-16 and every adapter that publishes one still writes
that shape; it means Finnish, and that has to keep being true. Bio Savoy is the first
adapter to declare: Åland's only official language is Swedish and its film pages carry a
native Swedish blurb. The slot is keyed by normalised title and read by every chain showing
that film, so Swedish text in the Finnish slot would be served as Finnish everywhere.

The cases here are the ones that would corrupt the file rather than merely miss text: a
Swedish text settling the Finnish slot, a Finnish text blocking a Swedish one, a later run
losing what an earlier one wrote, and the TMDB pass dropping a language it does not know.
"""
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import enrich_tmdb
import synmerge


FI = "Kahden naisen kohtaaminen keskellä hoitoalan kriisiä, ja mitä siitä seuraa."
SV = "Andrew Garfield spelar den mytomspunne ledaren för det stora upproret."
EN = "Two women meet in the middle of a crisis in care, and what follows from it."


def show(title, syn=None):
    """One show as far as synmerge reads it: a title and whatever `_syn` holds."""
    s = {"title": title}
    if syn is not None:
        s["_syn"] = syn
    return s


class TextsTest(unittest.TestCase):
    """`synmerge.texts` is the whole compatibility contract, in one function."""

    def test_a_bare_string_is_finnish(self):
        self.assertEqual(synmerge.texts(FI), {"fi": FI})

    def test_a_mapping_is_read_as_declared(self):
        self.assertEqual(synmerge.texts({"sv": SV}), {"sv": SV})
        self.assertEqual(synmerge.texts({"fi": FI, "sv": SV}), {"fi": FI, "sv": SV})

    def test_nothing_at_all_is_nothing(self):
        for value in (None, "", "   ", {}, {"sv": ""}, {"fi": None}):
            with self.subTest(value=value):
                self.assertEqual(synmerge.texts(value), {})

    def test_a_language_nothing_reads_is_dropped_rather_than_stored(self):
        """A junk slot in a file every chain reads is worse than a missing synopsis."""
        synmerge.reset()
        self.addCleanup(synmerge.reset)
        self.assertEqual(synmerge.texts({"de": "Auf Deutsch", "sv": SV}), {"sv": SV})
        self.assertIn("de", synmerge._unknown)

    def test_the_languages_are_the_ones_the_client_offers(self):
        self.assertEqual(sorted(synmerge.LANGS), ["en", "fi", "sv"])
        self.assertEqual(synmerge.LEGACY_LANG, "fi")


class MergeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = pathlib.Path(tmp.name)
        synmerge.reset()
        self.addCleanup(synmerge.reset)

    def merge(self, *shows, label="p", order=0):
        synmerge.merge(self.out, {"v": list(shows)}, label, order)
        return self.films()

    def films(self):
        return json.loads((self.out / "films-extra.json").read_text())["films"]

    def slot(self, title="Hetki ennen valoa"):
        return self.films()[synmerge.norm(title)]["s"]

    def test_a_legacy_string_still_lands_in_the_finnish_slot(self):
        self.merge(show("Hetki ennen valoa", FI))
        self.assertEqual(self.slot()["fi"], FI)
        self.assertNotIn("sv", self.slot())

    def test_a_declared_swedish_text_lands_in_its_own_slot(self):
        self.merge(show("The Uprising", {"sv": SV}))
        s = self.slot("The Uprising")
        self.assertEqual(s["sv"], SV)
        self.assertEqual(s["fi"], "", "Swedish text must never be served as Finnish")

    def test_a_language_slot_is_created_only_when_there_is_text_for_it(self):
        """403 entries carry no `sv` today and an entry without one is the normal case:
        every reader falls back. An empty slot on every film would be 403 of them."""
        self.merge(show("Hetki ennen valoa", FI))
        self.assertEqual(sorted(self.slot()), ["en", "fi"])

    def test_swedish_arrives_beside_an_existing_finnish_text_and_neither_moves(self):
        self.merge(show("Hetki ennen valoa", FI))
        self.merge(show("Hetki ennen valoa", {"sv": SV}), label="q", order=1)
        self.assertEqual(self.slot(), {"fi": FI, "en": "", "sv": SV})

    def test_a_finnish_text_does_not_stop_a_swedish_one_from_the_same_site(self):
        self.merge(show("Hetki ennen valoa", {"fi": FI, "sv": SV}))
        self.assertEqual(self.slot()["fi"], FI)
        self.assertEqual(self.slot()["sv"], SV)

    def test_an_earlier_site_wins_a_slot_per_language_and_not_across_them(self):
        """The SITES-order tie-break applied to the whole film would let a site that only
        speaks Swedish settle the Finnish slot, or be locked out of Swedish by a Finnish
        text an earlier site wrote."""
        self.merge(show("Hetki ennen valoa", {"sv": "site 3 sv"}), order=3)
        self.merge(show("Hetki ennen valoa", {"fi": "site 5 fi"}), order=5)
        self.merge(show("Hetki ennen valoa", {"sv": "site 1 sv"}), order=1)
        self.assertEqual(self.slot()["sv"], "site 1 sv", "the earlier site takes Swedish")
        self.assertEqual(self.slot()["fi"], "site 5 fi", "and says nothing about Finnish")

    def test_a_later_site_does_not_take_a_slot_an_earlier_one_filled(self):
        self.merge(show("Hetki ennen valoa", {"sv": "site 1 sv"}), order=1)
        self.merge(show("Hetki ennen valoa", {"sv": "site 4 sv"}), order=4)
        self.assertEqual(self.slot()["sv"], "site 1 sv")

    def test_text_from_before_this_run_stands_whatever_the_order(self):
        self.merge(show("Hetki ennen valoa", {"sv": "yesterday"}), order=9)
        synmerge.reset()                      # a new run
        self.merge(show("Hetki ennen valoa", {"sv": "today"}), order=0)
        self.assertEqual(self.slot()["sv"], "yesterday")

    def test_a_cinemas_synopsis_replaces_the_text_tmdb_filled(self):
        """The provider's own synopsis beats TMDB's. A slot the TMDB pass filled, recorded
        in `ts`, blocked every later cinema text for good: merge read any text as spoken
        for, and "synopses merged: 0" was the only trace (audit E4, 2026-09-25)."""
        (self.out / "films-extra.json").write_text(json.dumps({"films": {
            "hetki ennen valoa": {"s": {"fi": "TMDB fi", "en": "TMDB en"}, "ts": ["en", "fi"],
                                  "id": 1015881, "r": 7.1, "tr": ""}}}))
        self.merge(show("Hetki ennen valoa", FI))
        e = self.films()["hetki ennen valoa"]
        self.assertEqual(e["s"], {"fi": FI, "en": "TMDB en"})
        self.assertEqual(e["ts"], ["en"], "the Finnish slot is the cinema's now")
        # And the TMDB pass that follows leaves it there.
        enrich_tmdb.sync_extra(e, {"i": 1015881, "fi": "TMDB fi", "en": "TMDB en", "r": 7.1})
        self.assertEqual(e["s"]["fi"], FI)

    def test_the_last_tmdb_slot_taken_drops_the_record(self):
        (self.out / "films-extra.json").write_text(json.dumps({"films": {
            "hetki ennen valoa": {"s": {"fi": "TMDB fi", "en": ""}, "ts": ["fi"],
                                  "id": 1015881, "r": 0, "tr": ""}}}))
        self.merge(show("Hetki ennen valoa", FI))
        e = self.films()["hetki ennen valoa"]
        self.assertEqual(e["s"]["fi"], FI)
        self.assertNotIn("ts", e)

    def test_a_second_run_loses_nothing_the_first_wrote(self):
        self.merge(show("Hetki ennen valoa", {"fi": FI, "sv": SV}))
        synmerge.reset()
        self.merge(show("Toinen elokuva", FI))
        self.assertEqual(self.slot(), {"fi": FI, "en": "", "sv": SV})

    def test_a_screening_note_is_refused_in_every_language(self):
        """PRICE_RE is about what the text is, not what language it is in."""
        self.merge(show("Hetki ennen valoa", {"sv": "Biljetter 9€ vid kassan",
                                              "fi": FI}))
        self.assertEqual(self.slot()["fi"], FI)
        self.assertNotIn("sv", self.slot())

    def test_the_log_names_the_language_only_when_it_is_not_the_legacy_one(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.merge(show("Hetki ennen valoa", FI))
        self.assertIn("[p] synopses merged: 1", buf.getvalue())
        self.assertNotIn("by language", buf.getvalue())
        synmerge.reset()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.merge(show("The Uprising", {"sv": SV}))
        self.assertIn("by language: sv 1", buf.getvalue())


class EnrichmentPreservesEveryLanguageTest(unittest.TestCase):
    """The TMDB pass knows two languages and must not take a third away.

    It fills fi and en when they are blank and, for a film it no longer trusts, takes back
    the English it published and a Finnish text it can prove was its own. A Swedish text is
    a provider's and is neither its to fill nor its to withdraw.
    """

    def entry(self):
        return {"s": {"fi": FI, "en": EN, "sv": SV}, "r": 7, "tr": "t", "img": "i"}

    def test_unpublishing_an_untrusted_film_leaves_swedish_alone(self):
        e = self.entry()
        enrich_tmdb.unpublish_extra(e, {"fi": FI, "en": EN})
        self.assertEqual(e["s"]["en"], "", "English is TMDB's and goes")
        self.assertEqual(e["s"]["fi"], "", "this Finnish text was TMDB's own and goes")
        self.assertEqual(e["s"]["sv"], SV, "Swedish is the cinema's and stands")

    def test_unpublishing_leaves_a_providers_finnish_and_swedish_alone(self):
        e = self.entry()
        enrich_tmdb.unpublish_extra(e, {"fi": "something else", "en": EN})
        self.assertEqual(e["s"]["fi"], FI)
        self.assertEqual(e["s"]["sv"], SV)

    def test_an_entry_with_no_s_map_is_given_the_two_it_knows(self):
        e = {}
        enrich_tmdb.unpublish_extra(e, None)
        self.assertEqual(sorted(e["s"]), ["en", "fi"])

    def test_the_merge_pass_fills_the_blanks_it_knows_and_keeps_the_rest(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        extra = pathlib.Path(tmp.name) / "films-extra.json"
        key = synmerge.norm("The Uprising")
        extra.write_text(json.dumps({"generated": "2026-09-15",
                                     "films": {key: {"s": {"fi": "", "en": "", "sv": SV},
                                                     "r": 0, "tr": ""}}}),
                         encoding="utf-8")
        saved = enrich_tmdb.EXTRA
        enrich_tmdb.EXTRA = extra
        self.addCleanup(lambda: setattr(enrich_tmdb, "EXTRA", saved))
        enrich_tmdb.merge_extra({key: {"fi": FI, "en": EN, "p": "/p.jpg", "n": "n",
                                       "x": True, "i": 1, "g": [], "r": 7}},
                                "2026-09-16", live={key})
        s = json.loads(extra.read_text())["films"][key]["s"]
        self.assertEqual((s["fi"], s["en"]), (FI, EN))
        self.assertEqual(s["sv"], SV, "the pass dropped a language it does not know")


if __name__ == "__main__":
    unittest.main()


class UnreadableFileTest(unittest.TestCase):
    """An unparsable films-extra.json was read as {} and rewritten from one site's
    synopses: one stray comma from a hand edit, and the first site to publish cut 568
    entries to 1, with every cinema `sv` slot, `id`, `ts` and `kr` gone (audit C5,
    2026-09-25). A missing file is still an empty one; a file that is there and cannot be
    read fails the step and is left as it was."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = pathlib.Path(tmp.name)
        self.path = self.out / "films-extra.json"
        whole = json.dumps({"generated": "2026-09-25", "films": {
            "a": {"s": {"fi": FI, "en": "", "sv": SV}, "r": 0, "tr": ""},
            "b": {"s": {"fi": FI, "en": EN}, "id": 7, "ts": ["en"], "r": 6.5, "tr": ""}}})
        self.body = whole[: len(whole) // 2]          # a truncated write
        self.path.write_text(self.body)
        synmerge.reset()
        self.addCleanup(synmerge.reset)

    def assertUntouched(self):
        self.assertEqual(self.path.read_text(), self.body)

    def test_the_synopsis_merge_fails_and_leaves_the_file(self):
        with self.assertRaises(ValueError):
            synmerge.merge(self.out, {"v": [show("Toinen elokuva", FI)]}, "p", 0)
        self.assertUntouched()

    def test_the_tmdb_passes_fail_and_leave_the_file(self):
        saved = enrich_tmdb.EXTRA
        enrich_tmdb.EXTRA = self.path
        self.addCleanup(lambda: setattr(enrich_tmdb, "EXTRA", saved))
        with self.assertRaises(ValueError):
            enrich_tmdb.merge_extra({}, "2026-09-25")
        self.assertUntouched()
        with self.assertRaises(ValueError):
            enrich_tmdb.merge_shared({}, "2026-09-25")
        self.assertUntouched()

    def test_a_document_that_is_not_an_object_fails_too(self):
        self.path.write_text("[]")
        self.body = "[]"
        with self.assertRaises(ValueError):
            synmerge.merge(self.out, {"v": [show("Toinen elokuva", FI)]}, "p", 0)
        self.assertUntouched()

    def test_a_missing_file_is_still_an_empty_one(self):
        self.path.unlink()
        synmerge.merge(self.out, {"v": [show("Toinen elokuva", FI)]}, "p", 0)
        self.assertEqual(json.loads(self.path.read_text())["films"]["toinen elokuva"]["s"]["fi"], FI)

