"""The footer must not call a provider healthy while one of its cinemas did not refresh.

The classifier was age alone, so a provider with one failed venue read as healthy while
the expanded row beside it said (1/12). `healthState` is sliced verbatim out of index.html
by tests/health_state_harness.js; it takes provider metadata and an age and returns a
string.
"""
import json
import pathlib
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "health_state_harness.js"


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class HealthStateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    # -- the reported bug ----------------------------------------------------------

    def test_partial_two_hours_old_is_not_healthy(self):
        """status partial, one stale venue, data two hours old. The exact case: well
        inside STALE_H, so age alone called it fine."""
        self.assertEqual(self.r["partial_recent"], "partial")
        self.assertNotEqual(self.r["partial_recent"], "ok")

    def test_the_status_flag_alone_is_enough(self):
        """A provider can be partial with an empty stale list -- everything it kept back
        was unverified rather than stale -- so the flag has to count on its own."""
        self.assertEqual(self.r["partial_flag_only"], "partial")

    def test_a_stale_count_alone_is_enough(self):
        """Guards a file written before `status` existed."""
        self.assertEqual(self.r["stale_count_only"], "partial")

    def test_an_unverified_venue_stays_partial(self):
        """run.py cannot tell "added before its programme is published" from "a parse
        that has never worked" -- its own comment says so -- and the ambiguous case must
        stay visibly degraded. The first version of the pending state quieted these too,
        which would have read a rotted venue match as a calm "no programme yet"."""
        self.assertEqual(self.r["unverified_only"], "partial")

    def test_the_unverified_count_alone_is_enough(self):
        """Without a `status` field, so only the unverified term can catch it. The first
        version of this file set status:'partial' here too, which meant the term could be
        deleted with every test still green -- found by deleting it."""
        self.assertEqual(self.r["unverified_count_only"], "partial")

    def test_a_stale_venue_and_an_unverified_one_read_partial(self):
        self.assertEqual(self.r["stale_and_unverified"], "partial")

    def test_age_outranks_unverified(self):
        self.assertEqual(self.r["unverified_but_old"], "behind")

    # -- pending: the adapter vouched the venue is empty ----------------------------

    def test_a_confirmed_empty_venue_is_pending_not_partial(self):
        """Kino Metso Tikkakoski publishes into late October from day one. run.py grants
        pending only when the adapter set EMPTY_VENUES_CONFIRMED and reported the venue
        explicitly, so this quiet state never covers a parse that silently broke."""
        self.assertEqual(self.r["pending_only"], "pending")

    def test_the_pending_count_alone_is_enough(self):
        self.assertEqual(self.r["pending_count_only"], "pending")

    def test_a_stale_venue_outranks_a_pending_one(self):
        self.assertEqual(self.r["pending_and_stale"], "partial")

    def test_an_unverified_venue_outranks_a_pending_one(self):
        self.assertEqual(self.r["pending_and_unverified"], "partial")

    def test_age_outranks_pending(self):
        self.assertEqual(self.r["pending_but_old"], "behind")

    # -- nothing else moved --------------------------------------------------------

    def test_a_fully_fresh_provider_is_still_ok(self):
        self.assertEqual(self.r["fresh_ok"], "ok")

    def test_a_file_from_before_these_fields_is_still_ok(self):
        """Additive schema: no status, no unverified, nothing stale -> healthy."""
        self.assertEqual(self.r["legacy_no_status"], "ok")

    def test_old_data_is_behind(self):
        self.assertEqual(self.r["too_old"], "behind")

    def test_exactly_at_the_threshold_is_not_yet_behind(self):
        self.assertEqual(self.r["exactly_at_threshold"], "ok")

    def test_an_unreadable_timestamp_is_behind(self):
        self.assertEqual(self.r["invalid_timestamp"], "behind")

    # -- severity order ------------------------------------------------------------

    def test_behind_outranks_partial(self):
        """A provider that is both has the worse problem, and the summary line has room
        for one phrase."""
        self.assertEqual(self.r["too_old_and_partial"], "behind")

    def test_gone_outranks_everything(self):
        self.assertEqual(self.r["gone"], "gone")
        self.assertEqual(self.r["gone_but_fresh_age"], "gone")

    def test_absent_metadata_is_gone_not_healthy(self):
        self.assertEqual(self.r["missing_meta"], "gone")


if __name__ == "__main__":
    unittest.main()
