"""A KAVI classification published at one chain, filling a blank at another.

A cinema that publishes no age rating is not saying the film is unrestricted, it is saying
it publishes none, and 381 of 2916 showtimes are in that state. The classification is
national, so a cinema reports the same fact rather than forming an opinion, and the tree
agrees: of 37 films rated at more than one chain, none disagree.

What the rules have to hold, and what these test:
  * only exact TMDB matches take part, on both sides;
  * every non-empty rating for the film has to agree, and a disagreement publishes nothing
    and is reported rather than resolved;
  * runtimes have to be compatible where both sides publish one, so an alternate cut is
    not treated as the same film;
  * a cinema's own rating is never replaced.
"""
import contextlib
import io
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

import _ctx                                                # noqa: F401
import enrich_tmdb as et


def show(**kw):
    s = {"title": "Elokuva", "provider": "riviera", "rating": "", "len": "100",
         "tmdbId": 1}
    s.update(kw)
    return s


class SharedRatingTableTest(unittest.TestCase):
    """What `shared_ratings` publishes, and what it refuses to."""

    def test_one_chains_rating_becomes_the_films_shared_value(self):
        table, clashes = et.shared_ratings([
            show(provider="finnkino", rating="K-7", len="95"),
        ])
        self.assertEqual(clashes, [])
        self.assertEqual(table[1]["rating"], "K-7")
        self.assertEqual(table[1]["sources"], ["finnkino"])

    def test_chains_that_agree_are_all_recorded_as_sources(self):
        table, clashes = et.shared_ratings([
            show(provider="finnkino", rating="S", len="95"),
            show(provider="biorex", rating="S", len="95"),
        ])
        self.assertEqual(clashes, [])
        self.assertEqual(table[1]["rating"], "S")
        self.assertEqual(table[1]["sources"], ["biorex", "finnkino"])

    def test_a_disagreement_publishes_nothing_and_is_reported(self):
        """Two cinemas disagreeing about a national classification means one is wrong.
        Strictest-wins would hide that; the run says so instead."""
        table, clashes = et.shared_ratings([
            show(provider="finnkino", rating="K-12", len="95"),
            show(provider="biorex", rating="K-16", len="95"),
        ])
        self.assertNotIn(1, table)
        self.assertEqual(len(clashes), 1)
        self.assertEqual(clashes[0]["values"],
                         {"K-12": ["finnkino"], "K-16": ["biorex"]})

    def test_an_unrated_showing_never_becomes_a_source(self):
        """A blank is not a vote for anything."""
        table, _ = et.shared_ratings([
            show(provider="finnkino", rating="K-7"),
            show(provider="riviera", rating=""),
        ])
        self.assertEqual(table[1]["sources"], ["finnkino"])

    def test_a_value_outside_the_legal_classes_is_never_lent(self):
        """One chain's "K-6" was a typo and reached four chains through this table."""
        for bad in ("K-6", "s", "K-11", "Kaikille"):
            with self.subTest(rating=bad):
                table, clashes = et.shared_ratings([show(provider="alatalo", rating=bad)])
                self.assertEqual((table, clashes), ({}, []))

    def test_a_typo_beside_a_real_class_does_not_block_it(self):
        table, clashes = et.shared_ratings([show(provider="alatalo", rating="K-6"),
                                            show(provider="star", rating="K-16")])
        self.assertEqual(clashes, [])
        self.assertEqual(table[1]["rating"], "K-16")

    def test_a_film_with_no_id_is_not_grouped(self):
        table, clashes = et.shared_ratings([show(tmdbId=None, rating="S")])
        self.assertEqual((table, clashes), ({}, []))


class BorrowTest(unittest.TestCase):
    """What one showing may take from the table."""

    def setUp(self):
        self.table, _ = et.shared_ratings([
            show(provider="finnkino", rating="K-7", len="95")])

    def test_a_blank_rating_is_filled(self):
        self.assertEqual(et.borrowed_rating(show(len="95"), self.table), "K-7")

    def test_a_cinemas_own_rating_is_never_replaced(self):
        """Even when the two differ. The cinema is the one enforcing it at the door."""
        self.assertIsNone(et.borrowed_rating(show(rating="K-12", len="95"), self.table))

    def test_a_film_nobody_rated_gets_nothing(self):
        self.assertIsNone(et.borrowed_rating(show(tmdbId=999), self.table))

    # -- versions and runtime ---------------------------------------------------------------

    def test_a_matching_runtime_borrows(self):
        self.assertEqual(et.borrowed_rating(show(len="97"), self.table), "K-7")

    def test_an_alternate_cut_does_not_borrow(self):
        """Riviera lists Practical Magic at 110 minutes against a 130-minute listing. The
        measured gaps in the whole tree are 0, 1 and 20 minutes with nothing between, so
        five sits in the gap and the 20-minute cluster is refused."""
        self.assertIsNone(et.borrowed_rating(show(len="115"), self.table))
        self.assertIsNone(et.borrowed_rating(show(len="75"), self.table))

    def test_the_tolerance_boundary_is_inclusive(self):
        self.assertEqual(et.borrowed_rating(show(len="100"), self.table), "K-7")
        self.assertIsNone(et.borrowed_rating(show(len="101"), self.table))

    def test_a_missing_runtime_on_either_side_still_borrows(self):
        """Ten of the candidates are in this state. The runtime rule is a veto on evidence
        of a different cut, not a requirement that both sides publish one."""
        self.assertEqual(et.borrowed_rating(show(len=""), self.table), "K-7")
        self.assertEqual(et.borrowed_rating(show(len="not a number"), self.table), "K-7")
        nolen, _ = et.shared_ratings([show(provider="finnkino", rating="S", len="")])
        self.assertEqual(et.borrowed_rating(show(len="95"), nolen), "S")

    def test_the_tolerance_is_the_documented_one(self):
        self.assertEqual(et.RUNTIME_TOL_MIN, 5)


class WeakMatchGroupingTest(unittest.TestCase):
    def test_a_weak_match_carries_no_id_so_it_cannot_group(self):
        """The caller passes no `tmdbId` without `x`, and an entry with none is skipped.
        The run this was written against had 13 weak titles, one of them "Kapina" matched
        to "Matilda ja lasten kapina": that classification on that film fails in the
        unsafe direction. The area pass is covered end to end in RunTest."""
        table, _ = et.shared_ratings([show(tmdbId=None, rating="K-7"),
                                      show(tmdbId=None, rating="S")])
        self.assertEqual(table, {})


class RunTest(unittest.TestCase):
    """The pass over real files: donor scan, area writes, provenance and cleanup.

    The source-text checks these replace could only confirm the source says what it says,
    which is the failure mode that shipped the /status/ refetch loop. This runs `main()`
    against a temporary tree and reads the files back.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)
        (self.dir / "data").mkdir()

    # -- the tree --------------------------------------------------------------------------

    def cache(self, **extra):
        """tmdb-titles.json: "yhteinen" is an exact match, "hatara" a weak one.

        Each carries the search string it was judged on. Without one `reconsider()` reads
        the entry as judged by an unknown cleaner and re-judges it, which turns these runs
        into TMDB searches instead of the sharing pass they are about.
        """
        blank = {"r": 0, "n": 0, "v": "", "g": [], "c": "", "fi": "", "en": "", "p": ""}
        # "tarkka" and "hatara" are the same film id under two titles, one matched
        # exactly and one weakly, so each side of the gate can be tested on its own.
        c = {"yhteinen": {"x": True, "i": 77, "q": "yhteinen", **blank},
             "tarkka": {"x": True, "i": 88, "q": "tarkka", **blank},
             "hatara": {"x": False, "i": 88, "q": "hatara", **blank}}
        c.update(extra)
        return c

    def write(self, cache, areas, extra=None):
        (self.dir / "data" / "tmdb-titles.json").write_text(json.dumps(cache))
        (self.dir / "data" / "films-extra.json").write_text(
            json.dumps(extra if extra is not None else {"generated": "", "films": {}}))
        for name, shows in areas.items():
            (self.dir / "data" / f"area-{name}.json").write_text(
                json.dumps({"generated": "2026-09-07T06:00:00+00:00", "shows": shows}))

    def run_pass(self):
        """`main()` against the temporary tree with the network off.

        A token is required or the pass returns immediately; `due()` returning nothing
        means no title is ever looked up, so the pre-seeded cache is the only source and
        no request is made. `get` is stubbed as well, so a rule change that started
        fetching fails here rather than reaching out."""
        def no_network(*a, **k):
            raise AssertionError("the pass made a network request")
        with mock.patch.object(et, "DATA", self.dir / "data"), \
             mock.patch.object(et, "CACHE", self.dir / "data" / "tmdb-titles.json"), \
             mock.patch.object(et, "EXTRA", self.dir / "data" / "films-extra.json"), \
             mock.patch.object(et, "due", lambda *a, **k: ([], [], [])), \
             mock.patch.object(et, "get", no_network), \
             mock.patch.dict(os.environ, {"TMDB_TOKEN": "test"}), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            et.main()
        return out.getvalue()

    def area(self, name):
        return json.loads((self.dir / "data" / f"area-{name}.json").read_text())["shows"]

    def extra(self):
        return json.loads((self.dir / "data" / "films-extra.json").read_text())["films"]

    # -- one run ----------------------------------------------------------------------------

    def test_a_rating_crosses_from_one_area_file_to_another(self):
        self.write(self.cache(), {
            "donor": [dict(title="Yhteinen", provider="finnkino", rating="K-7", len="95")],
            "taker": [dict(title="Yhteinen", provider="riviera", rating="", len="95")],
        })
        self.run_pass()
        got = self.area("taker")[0]
        self.assertEqual(got["rating"], "K-7")
        self.assertEqual(got["rsrc"], "shared", "no provenance on the borrowed value")
        self.assertEqual(self.area("donor")[0].get("rsrc"), None,
                         "the cinema's own rating was marked as borrowed")

    def test_films_extra_records_the_value_and_its_sources(self):
        self.write(self.cache(), {
            "donor": [dict(title="Yhteinen", provider="finnkino", rating="K-7", len="95")],
            "taker": [dict(title="Yhteinen", provider="riviera", rating="", len="95")],
        })
        self.run_pass()
        self.assertEqual(self.extra()["yhteinen"]["kr"], "K-7")
        self.assertEqual(self.extra()["yhteinen"]["krs"], ["finnkino"])

    def test_a_weak_match_neither_donates_nor_receives(self):
        self.write(self.cache(), {
            "donor": [dict(title="Hatara", provider="finnkino", rating="S", len="95")],
            "taker": [dict(title="Hatara", provider="riviera", rating="", len="95")],
        })
        self.run_pass()
        self.assertEqual(self.area("taker")[0]["rating"], "")
        self.assertNotIn("kr", self.extra().get("hatara", {}))

    def test_a_weak_match_cannot_donate_to_an_exact_one(self):
        """"Kapina" matched to "Matilda ja lasten kapina" is this shape, and it would hand
        a children's classification to whatever film really is Matilda.

        Two things stop it and this asserts the outcome rather than either: the `x` gate in
        the pass, and main() deleting weak entries that carry an id as it loads the cache.
        The deletion runs first, so no mutation of the gate alone can turn this red."""
        self.write(self.cache(), {
            "donor": [dict(title="Hatara", provider="finnkino", rating="S", len="95")],
            "taker": [dict(title="Tarkka", provider="riviera", rating="", len="95")],
        })
        self.run_pass()
        self.assertEqual(self.area("taker")[0]["rating"], "")

    def test_an_exact_match_cannot_donate_to_a_weak_one(self):
        """The same pairing the other way round, and the same two mechanisms."""
        self.write(self.cache(), {
            "donor": [dict(title="Tarkka", provider="finnkino", rating="S", len="95")],
            "taker": [dict(title="Hatara", provider="riviera", rating="", len="95")],
        })
        self.run_pass()
        self.assertEqual(self.area("taker")[0]["rating"], "")

    def test_an_alternate_cut_is_refused_across_files(self):
        self.write(self.cache(), {
            "donor": [dict(title="Yhteinen", provider="finnkino", rating="S", len="130")],
            "taker": [dict(title="Yhteinen", provider="riviera", rating="", len="110")],
        })
        self.run_pass()
        self.assertEqual(self.area("taker")[0]["rating"], "")

    def test_a_disagreement_shares_nothing_and_is_named_in_the_log(self):
        self.write(self.cache(), {
            "a": [dict(title="Yhteinen", provider="finnkino", rating="K-12", len="95")],
            "b": [dict(title="Yhteinen", provider="biorex", rating="K-16", len="95")],
            "taker": [dict(title="Yhteinen", provider="riviera", rating="", len="95")],
        })
        log = self.run_pass()
        self.assertEqual(self.area("taker")[0]["rating"], "")
        self.assertIn("rating disagreement", log)
        self.assertIn("K-12=finnkino", log)
        self.assertIn("K-16=biorex", log)

    # -- a second run ---------------------------------------------------------------------------

    def test_a_borrowed_rating_does_not_donate_on_the_next_run(self):
        """The defect. run.py keeps a stale venue's previous data, so the borrowed value
        survives; if it counted as a source, the loan would outlive its donor and then
        lend itself to a third cinema."""
        self.write(self.cache(), {
            "donor": [dict(title="Yhteinen", provider="finnkino", rating="K-7", len="95")],
            "taker": [dict(title="Yhteinen", provider="riviera", rating="", len="95")],
        })
        self.run_pass()
        self.assertEqual(self.area("taker")[0]["rating"], "K-7")

        # The donor leaves the programme. The taker's file is kept as it was written.
        (self.dir / "data" / "area-donor.json").write_text(
            json.dumps({"generated": "2026-09-07T06:00:00+00:00", "shows": []}))
        (self.dir / "data" / "area-third.json").write_text(json.dumps(
            {"generated": "2026-09-07T06:00:00+00:00",
             "shows": [dict(title="Yhteinen", provider="orion", rating="", len="95")]}))
        self.run_pass()
        self.assertEqual(self.area("third")[0]["rating"], "",
                         "a borrowed rating donated itself onward")
        self.assertEqual(self.area("taker")[0]["rating"], "",
                         "the loan outlived the donor that made it")
        self.assertNotIn("rsrc", self.area("taker")[0])

    def test_films_extra_drops_a_shared_value_whose_donor_is_gone(self):
        """`kr` is rewritten from scratch, so a stale one cannot linger. The set is empty
        on the second run, which is exactly when the cleanup has to still happen."""
        self.write(self.cache(), {
            "donor": [dict(title="Yhteinen", provider="finnkino", rating="K-7", len="95")],
            "taker": [dict(title="Yhteinen", provider="riviera", rating="", len="95")],
        })
        self.run_pass()
        self.assertEqual(self.extra()["yhteinen"]["kr"], "K-7")

        (self.dir / "data" / "area-donor.json").write_text(
            json.dumps({"generated": "2026-09-07T06:00:00+00:00", "shows": []}))
        self.run_pass()
        self.assertNotIn("kr", self.extra().get("yhteinen", {}))
        self.assertNotIn("krs", self.extra().get("yhteinen", {}))

    def test_a_loan_is_cleared_when_the_films_cache_entry_is_gone(self):
        """The target's cache entry disappears with the donor: a retitled film, or an entry
        pruned as weakly matched. The pass reaches `continue` on the missing entry, so
        anything that clears after that point never runs and the loan sits there with
        nothing left to justify it."""
        self.write(self.cache(), {
            "donor": [dict(title="Yhteinen", provider="finnkino", rating="K-7", len="95")],
            "taker": [dict(title="Yhteinen", provider="riviera", rating="", len="95")],
        })
        self.run_pass()
        self.assertEqual(self.area("taker")[0]["rating"], "K-7")

        # Donor gone, and the film is no longer in the cache at all.
        (self.dir / "data" / "area-donor.json").write_text(
            json.dumps({"generated": "2026-09-07T06:00:00+00:00", "shows": []}))
        cache = self.cache()
        del cache["yhteinen"]
        (self.dir / "data" / "tmdb-titles.json").write_text(json.dumps(cache))
        self.run_pass()
        got = self.area("taker")[0]
        self.assertEqual(got["rating"], "", "the loan outlived its cache entry")
        self.assertNotIn("rsrc", got)

    def test_a_loan_is_cleared_when_only_the_cache_entry_is_gone(self):
        """The donor is still listing the film; only the cache entry has gone. Nothing can
        re-justify the loan without it, so it goes too."""
        self.write(self.cache(), {
            "donor": [dict(title="Yhteinen", provider="finnkino", rating="K-7", len="95")],
            "taker": [dict(title="Yhteinen", provider="riviera", rating="", len="95")],
        })
        self.run_pass()
        self.assertEqual(self.area("taker")[0]["rating"], "K-7")

        cache = self.cache()
        del cache["yhteinen"]
        (self.dir / "data" / "tmdb-titles.json").write_text(json.dumps(cache))
        self.run_pass()
        self.assertEqual(self.area("taker")[0]["rating"], "")
        self.assertNotIn("kr", self.extra().get("yhteinen", {}))

    def test_a_cinemas_own_rating_survives_a_second_run(self):
        self.write(self.cache(), {
            "donor": [dict(title="Yhteinen", provider="finnkino", rating="K-7", len="95")],
            "own": [dict(title="Yhteinen", provider="biorex", rating="K-7", len="95")],
        })
        self.run_pass()
        self.run_pass()
        got = self.area("own")[0]
        self.assertEqual(got["rating"], "K-7")
        self.assertNotIn("rsrc", got, "a published rating was relabelled as borrowed")

    def test_a_stable_tree_reaches_the_same_answer_twice(self):
        self.write(self.cache(), {
            "donor": [dict(title="Yhteinen", provider="finnkino", rating="K-7", len="95")],
            "taker": [dict(title="Yhteinen", provider="riviera", rating="", len="95")],
        })
        self.run_pass()
        first = (self.area("taker"), self.extra())
        self.run_pass()
        self.assertEqual((self.area("taker"), self.extra()), first)


if __name__ == "__main__":
    unittest.main()
