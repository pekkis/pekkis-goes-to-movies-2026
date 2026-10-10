"""poll_windows: the classification has to be right before its output guides a schedule.

The first three runs reported 125, 20 and 4 arrivals over the same history; the difference
was the analyser's own bugs, each pinned here. Git traversal is the implementation, so the
fixtures build small throwaway repositories with controlled commit timestamps rather than
mocking git. Timestamps mix `+03:00` and `+00:00` on purpose: the local half commits in
Helsinki time and the runner in UTC, and both serious bugs came from comparing them.
"""
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import _ctx                                                # noqa: F401
import poll_windows


PIPELINE = "Update cloud provider data"


def show(title, start, aud="", provider="fakechain", **extra):
    d = {"title": title, "start": start, "aud": aud, "provider": provider,
         "url": "https://example.test/x"}
    d.update(extra)
    return d


def area(*shows, **extra):
    doc = {"generated": "2026-08-30T00:00:00+00:00", "dates": [], "horizon": "",
           "shows": list(shows)}
    doc.update(extra)
    return doc


@unittest.skipIf(shutil.which("git") is None, "git not installed")
class PollWindowsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.git("init", "-q")
        self.git("symbolic-ref", "HEAD", "refs/heads/main")
        self.git("config", "user.name", "fixture")
        # No dot after the @, so this is not an address shape and the contact-address
        # leak guard in test_contact_address.py stays a guard rather than growing an
        # allowlist entry. It caught the first version of this line, which is the point
        # of it -- a tracked file in a public repo has exactly one address in it.
        self.git("config", "user.email", "fixture@localhost")
        saved = poll_windows.ROOT
        poll_windows.ROOT = self.root
        self.addCleanup(lambda: setattr(poll_windows, "ROOT", saved))

    def git(self, *args):
        out = subprocess.run(("git",) + args, cwd=str(self.root),
                             capture_output=True, text=True, env=self.env)
        out.check_returncode()
        return out.stdout

    env = None

    def commit(self, when, message, files):
        """One commit at an exact timestamp. `files` maps path -> dict | str | None."""
        for rel, content in files.items():
            p = self.root / rel
            if content is None:
                if p.exists():
                    p.unlink()
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content if isinstance(content, str)
                         else json.dumps(content), encoding="utf-8")
        self.git("add", "-A")
        self.env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
        try:
            self.git("commit", "-q", "--allow-empty", "-m", message)
        finally:
            self.env = None

    def events(self, provider=None):
        _, evs = poll_windows.collect("main", "", {provider} if provider else set())
        return evs

    def only(self):
        evs = self.events()
        self.assertEqual(len(evs), 1, f"expected exactly one arrival, got {evs}")
        return evs[0]

    # -- 1. timezone normalisation -------------------------------------------------

    def test_a_past_screening_is_not_an_arrival_across_mixed_offsets(self):
        """The false Gilda arrivals, reproduced exactly.

        Two consecutive observations three minutes apart whose area files are byte
        identical. The screening at 17:20+03:00 is 14:20 UTC, already past at both. The
        first version compared ISO strings, so "...T17:20:00+03:00" sorted above
        "...T15:16:40+00:00" and the screening read as future at the second commit only --
        sixteen arrivals invented out of files that never changed.
        """
        doc = area(show("Autofiktio", "2026-08-29T17:20:00+03:00", "Gilda 2"),
                   show("The Dog Stars", "2026-08-30T20:00:00+03:00", "Gilda 1"))
        self.commit("2026-08-29T18:13:35+03:00", PIPELINE, {"data/area-fc-a.json": doc})
        self.commit("2026-08-29T15:16:40+00:00", PIPELINE, {"data/area-fc-a.json": doc})
        self.assertEqual(self.events(), [],
                         "identical files across two offsets produced arrivals")

    def test_starts_are_compared_chronologically_not_by_wall_clock(self):
        """Two screenings at the same wall clock, an hour apart in real time.

        Finland repeats 03:00-04:00 on the last Sunday of October, so `+03:00` and
        `+02:00` starts genuinely coexist in one venue file across that night. Naive or
        lexical comparison calls them equal; only one of them is still in the future when
        this observation is made. The identical-files test above cannot catch this on its
        own -- normalising commit stamps to Helsinki happens to rescue a naive comparison
        whenever every start shares the local offset, which is every other night of the
        year -- so this is the case that pins the arithmetic itself.
        """
        far = show("Far", "2026-12-01T18:00:00+02:00")
        self.commit("2026-10-25T03:00:00+03:00", PIPELINE,       # 00:00 UTC
                    {"data/area-fc-a.json": area(far)})
        self.commit("2026-10-25T04:00:00+03:00", PIPELINE, {     # 01:00 UTC
            "data/area-fc-a.json": area(
                far,
                show("Before", "2026-10-25T03:30:00+03:00"),     # 00:30 UTC, past
                show("After", "2026-10-25T03:30:00+02:00"))})    # 01:30 UTC, future
        e = self.only()
        self.assertEqual(e["shows"], 1,
                         "both DST-hour screenings were treated as the same instant")
        self.assertEqual(e["new_titles"], ["After"])

    def test_the_weekday_is_the_cinemas_weekday_not_the_committers(self):
        """A runner commits in UTC. 23:30 UTC on Thursday is 02:30 Friday in Helsinki,
        and the weekday is the entire output of this tool."""
        base = area(show("A", "2026-09-10T18:00:00+03:00"))
        self.commit("2026-09-03T20:00:00+03:00", PIPELINE, {"data/area-fc-a.json": base})
        self.commit("2026-09-03T23:30:00+00:00", PIPELINE, {"data/area-fc-a.json":
                    area(show("A", "2026-09-10T18:00:00+03:00"),
                         show("B", "2026-09-11T18:00:00+03:00"))})
        e = self.only()
        # 2026-09-03 is a Thursday; 23:30 UTC that day is Friday 02:30 in Helsinki.
        self.assertEqual(poll_windows.WD[e["when"].weekday()], "Fri")
        self.assertEqual(e["when"].strftime("%H:%M"), "02:30")

    # -- 2 & 10. everything that is not a screening --------------------------------

    def test_enrichment_poster_and_generated_churn_produce_no_arrival(self):
        """A cloud run rewrites every venue file, stamps a new `generated`, adds TMDB
        fields, rewrites posters same-origin and regenerates pages and logs. None of that
        is a cinema publishing anything."""
        plain = area(show("A", "2026-09-10T18:00:00+03:00", img="https://cdn.test/a.jpg"))
        enriched = area(show("A", "2026-09-10T18:00:00+03:00",
                             img="data/posters/deadbeef.jpg", tmdbId=603, tmdb=8.7,
                             votes=2000, tr="abc123", gids=[28, 878],
                             s={"fi": "Synopsis"}),
                        generated="2026-08-30T12:00:00+00:00")
        self.commit("2026-09-03T08:10:00+03:00", PIPELINE, {
            "data/area-fc-a.json": plain,
            "data/films-extra.json": {"films": {"A": {"img": "https://cdn.test/a.jpg"}}},
            "run-fake.log": "exit=0\n",
            "teatteri/x/index.html": "<html>old</html>",
        })
        self.commit("2026-09-03T12:10:00+03:00", PIPELINE, {
            "data/area-fc-a.json": enriched,
            "data/films-extra.json": {"films": {"A": {"img": "data/posters/deadbeef.jpg",
                                                      "tr": "abc123"}}},
            "data/tmdb-genres.json": {"fi": {"28": "Toiminta"}},
            "run-fake.log": "exit=0\nmore\n",
            "teatteri/x/index.html": "<html>new</html>",
        })
        self.assertEqual(self.events(), [])

    # -- 3. empty venue ------------------------------------------------------------

    def test_an_empty_venue_keeps_its_provider_and_the_window_stays_honest(self):
        """A venue whose file is momentarily empty names no provider, because the provider
        id lives on the shows. Reading it per commit dropped the venue out of the
        provider's state and stopped `seen` advancing, so the next arrival was measured
        against a stale observation and reported a window that never happened."""
        shows = area(show("A", "2026-09-10T18:00:00+03:00"),
                     show("B", "2026-09-11T18:00:00+03:00"))
        self.commit("2026-09-03T08:10:00+03:00", PIPELINE, {"data/area-fc-a.json": shows})
        self.commit("2026-09-03T14:10:00+03:00", PIPELINE, {"data/area-fc-a.json": area()})
        self.commit("2026-09-03T20:10:00+03:00", PIPELINE, {"data/area-fc-a.json": shows})
        e = self.only()
        self.assertEqual(e["provider"], "fakechain")
        self.assertAlmostEqual(e["gap_h"], 6.0, places=2,
                               msg="window measured from before the empty observation")
        self.assertEqual(e["prev_when"].strftime("%H:%M"), "14:10")

    def test_the_first_population_of_a_venue_is_flagged_as_backfill(self):
        """A venue added before its programme is published carries an empty file until it
        starts producing, and that first population looks exactly like a cinema
        publishing a season. Flagged per venue -- and it stopped being flagged for free
        once empty files kept their identity, because the venue was no longer *missing*."""
        a = show("A", "2026-09-10T18:00:00+03:00")
        self.commit("2026-09-03T08:10:00+03:00", PIPELINE, {
            "data/area-fc-a.json": area(a), "data/area-fc-b.json": area()})
        self.commit("2026-09-03T14:10:00+03:00", PIPELINE, {
            "data/area-fc-a.json": area(a),
            "data/area-fc-b.json": area(show("C", "2026-09-12T18:00:00+03:00"))})
        e = self.only()
        self.assertTrue(e["development"])
        self.assertTrue(any("first population of fc-b" in r for r in e["reasons"]),
                        f"reasons did not name the venue: {e['reasons']}")

    # -- 4. adapter introduction / backfill ----------------------------------------

    def test_an_adapter_commit_touching_no_data_flags_the_next_arrival(self):
        """The one that mattered. An adapter commit usually touches no data file at all,
        so inspecting the data commit alone missed every one of them: the Cinema Orion
        parser landing between two cloud runs read as Orion publishing 27 screenings."""
        self.commit("2026-09-03T08:10:00+03:00", PIPELINE,
                    {"data/area-fc-a.json": area(show("A", "2026-09-10T18:00:00+03:00"))})
        self.commit("2026-09-03T10:00:00+03:00", "fakechain: parse the second screen",
                    {"scripts/providers/fake.py": "# adapter\n"})
        self.commit("2026-09-03T14:10:00+03:00", PIPELINE,
                    {"data/area-fc-a.json": area(show("A", "2026-09-10T18:00:00+03:00"),
                                                 show("B", "2026-09-11T18:00:00+03:00"))})
        e = self.only()
        self.assertTrue(e["development"])
        self.assertTrue(any("adapter" in r for r in e["reasons"]), e["reasons"])

    def test_the_same_arrival_is_organic_without_the_adapter_commit(self):
        """The control. Without it the flag would be meaningless -- something that fires
        on everything is not a classifier."""
        self.commit("2026-09-03T08:10:00+03:00", PIPELINE,
                    {"data/area-fc-a.json": area(show("A", "2026-09-10T18:00:00+03:00"))})
        self.commit("2026-09-03T14:10:00+03:00", PIPELINE,
                    {"data/area-fc-a.json": area(show("A", "2026-09-10T18:00:00+03:00"),
                                                 show("B", "2026-09-11T18:00:00+03:00"))})
        e = self.only()
        self.assertFalse(e["development"], e["reasons"])

    def test_a_hand_made_commit_is_flagged_even_with_no_adapter_change(self):
        """Only the two unattended pipeline messages are observations of a cinema."""
        self.commit("2026-09-03T08:10:00+03:00", PIPELINE,
                    {"data/area-fc-a.json": area(show("A", "2026-09-10T18:00:00+03:00"))})
        self.commit("2026-09-03T14:10:00+03:00", "fix a bad start time by hand",
                    {"data/area-fc-a.json": area(show("A", "2026-09-10T18:00:00+03:00"),
                                                 show("B", "2026-09-11T18:00:00+03:00"))})
        self.assertTrue(self.only()["development"])

    # -- 5. future filtering -------------------------------------------------------

    def test_a_screening_already_past_at_observation_is_not_an_arrival(self):
        """Backfilled history is not news, and a cinema correcting yesterday is not
        publishing tomorrow."""
        self.commit("2026-09-03T08:10:00+03:00", PIPELINE,
                    {"data/area-fc-a.json": area(show("A", "2026-09-10T18:00:00+03:00"))})
        self.commit("2026-09-03T14:10:00+03:00", PIPELINE,
                    {"data/area-fc-a.json": area(show("A", "2026-09-10T18:00:00+03:00"),
                                                 show("Old", "2026-09-01T18:00:00+03:00"))})
        self.assertEqual(self.events(), [])

    # -- 6. showtime identity ------------------------------------------------------

    def base_then(self, *added):
        first = show("A", "2026-09-10T18:00:00+03:00", "Sali 1")
        self.commit("2026-09-03T08:10:00+03:00", PIPELINE,
                    {"data/area-fc-a.json": area(first)})
        self.commit("2026-09-03T14:10:00+03:00", PIPELINE,
                    {"data/area-fc-a.json": area(*added)})

    def test_same_title_new_date_is_an_arrival(self):
        self.base_then(show("A", "2026-09-10T18:00:00+03:00", "Sali 1"),
                       show("A", "2026-09-11T18:00:00+03:00", "Sali 1"))
        self.assertEqual(self.only()["shows"], 1)

    def test_same_start_different_auditorium_is_an_arrival(self):
        """A second screen opening for the same film at the same minute is a real extra
        screening, and dropping `aud` from the key would hide it."""
        self.base_then(show("A", "2026-09-10T18:00:00+03:00", "Sali 1"),
                       show("A", "2026-09-10T18:00:00+03:00", "Sali 2"))
        self.assertEqual(self.only()["shows"], 1)

    def test_a_moved_screening_time_counts_once(self):
        """The old key disappears and a new one arrives; only arrivals are counted, so a
        move is one, not two and not zero."""
        self.base_then(show("A", "2026-09-10T19:30:00+03:00", "Sali 1"))
        self.assertEqual(self.only()["shows"], 1)

    def test_duplicate_records_are_counted_once(self):
        """Providers repeat rows. A duplicate is not a new screening."""
        dup = show("A", "2026-09-10T18:00:00+03:00", "Sali 1")
        self.base_then(dup, dict(dup), dict(dup))
        self.assertEqual(self.events(), [])

    # -- 7 & 8. horizon, and titles as the weaker signal ---------------------------

    def test_a_horizon_extension_is_reported_with_no_new_title(self):
        """The case first-seen titles cannot see at all: a cinema opening next week's
        dates for films already showing publishes real news and introduces no title."""
        a = show("A", "2026-09-10T18:00:00+03:00")
        self.commit("2026-09-03T08:10:00+03:00", PIPELINE,
                    {"data/area-fc-a.json": area(a)})
        self.commit("2026-09-03T14:10:00+03:00", PIPELINE,
                    {"data/area-fc-a.json": area(a, show("A", "2026-09-17T18:00:00+03:00"))})
        e = self.only()
        self.assertEqual(e["new_titles"], [], "no title is new here, which is the point")
        self.assertEqual(e["shows"], 1)
        self.assertIn("2026-09-10 -> 2026-09-17", e["horizon"])

    def test_a_new_title_is_recorded_but_does_not_gate_the_arrival(self):
        a = show("A", "2026-09-10T18:00:00+03:00")
        self.commit("2026-09-03T08:10:00+03:00", PIPELINE,
                    {"data/area-fc-a.json": area(a)})
        self.commit("2026-09-03T14:10:00+03:00", PIPELINE,
                    {"data/area-fc-a.json": area(a, show("B", "2026-09-09T18:00:00+03:00"))})
        e = self.only()
        self.assertEqual(e["new_titles"], ["B"])
        self.assertEqual(e["shows"], 1)
        self.assertEqual(e["horizon"], "", "B is nearer than A; the horizon did not move")

    # -- 9. the observation window -------------------------------------------------

    def test_every_arrival_carries_the_window_it_was_observed_in(self):
        self.commit("2026-09-03T08:10:00+03:00", PIPELINE,
                    {"data/area-fc-a.json": area(show("A", "2026-09-10T18:00:00+03:00"))})
        self.commit("2026-09-03T14:10:00+03:00", PIPELINE,
                    {"data/area-fc-a.json": area(show("A", "2026-09-10T18:00:00+03:00"),
                                                 show("B", "2026-09-11T18:00:00+03:00"))})
        e = self.only()
        self.assertAlmostEqual(e["gap_h"], 6.0, places=2)
        self.assertEqual((e["when"] - e["prev_when"]).total_seconds() / 3600.0, e["gap_h"])
        self.assertLess(e["prev_when"], e["when"])

    def test_the_report_says_the_window_is_not_a_publication_time(self):
        """The whole risk of this script is someone reading `Thu 19h` as a fact about a
        cinema. That caveat is output, not a docstring, so it is tested like output."""
        import contextlib, io
        self.commit("2026-09-03T08:10:00+03:00", PIPELINE,
                    {"data/area-fc-a.json": area(show("A", "2026-09-10T18:00:00+03:00"))})
        self.commit("2026-09-03T14:10:00+03:00", PIPELINE,
                    {"data/area-fc-a.json": area(show("A", "2026-09-10T18:00:00+03:00"),
                                                 show("B", "2026-09-11T18:00:00+03:00"))})
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            poll_windows.analyse("main", "", set(), False)
        text = buf.getvalue()
        self.assertIn("not a publication time", text)
        self.assertIn("AFTER the previous observation", text)
        self.assertIn("Europe/Helsinki", text)


if __name__ == "__main__":
    unittest.main()
