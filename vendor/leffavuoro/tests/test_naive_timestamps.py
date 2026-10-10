"""A timestamp with no offset is read in Helsinki, never in the host machine's zone.

Gilda's `show_time` and Local Hub's event `start` were parsed with `fromisoformat` and
then `astimezone(FI)`, which reads a naive value in the zone of whatever machine runs it:
"2026-09-26T15:00:00" became 18:00 on a UTC runner and 15:00 on the Helsinki laptop, so a
hand run and a cloud run published the same screening three hours apart (audit A7, prior
review #31, 2026-09-25). The tests pin the process to UTC, where the old reading is wrong,
and to Helsinki, where it happens to be right.
"""
import os
import time
import unittest

import _ctx                                                # noqa: F401
import gilda
import localhub


class NaiveIsHelsinkiTest(unittest.TestCase):

    def zone(self, tz):
        saved = os.environ.get("TZ")
        os.environ["TZ"] = tz
        time.tzset()

        def restore():
            if saved is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = saved
            time.tzset()
        self.addCleanup(restore)

    def test_gilda_reads_a_naive_show_time_in_helsinki_on_a_utc_host(self):
        for tz in ("UTC", "Europe/Helsinki"):
            with self.subTest(tz=tz):
                self.zone(tz)
                self.assertEqual(gilda._start({"show_time": "2026-09-26T15:00:00"}),
                                 "2026-09-26T15:00:00+03:00")

    def test_localhub_reads_a_naive_start_in_helsinki_on_a_utc_host(self):
        for tz in ("UTC", "Europe/Helsinki"):
            with self.subTest(tz=tz):
                self.zone(tz)
                self.assertEqual(localhub.instant("2026-11-26T15:00:00").isoformat(),
                                 "2026-11-26T15:00:00+02:00")

    def test_an_offset_is_still_honoured_by_both(self):
        self.zone("UTC")
        self.assertEqual(gilda._start({"show_time": "2026-09-26T12:00:00Z"}),
                         "2026-09-26T15:00:00+03:00")
        self.assertEqual(localhub.instant("2026-09-26T12:00:00.000Z").isoformat(),
                         "2026-09-26T15:00:00+03:00")


if __name__ == "__main__":
    unittest.main()
