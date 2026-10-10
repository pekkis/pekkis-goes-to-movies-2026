"""A changed screening changes its theatre page, and only that page (2026-09-13).

The Checks workflow regenerates the pages and requires a clean tree. That check is only
worth keeping strict if a schedule change actually moves a page: a data commit that
carries new showtimes without the pages built from them must show up as drift. On
2026-09-13 the local half committed schedules alone and every code push on top of it
went red on 48 pages of showtime differences; the wrapper now builds the pages in the
same commit. This pins the property the check relies on, against the committed data.
"""
import contextlib
import io
import json
import pathlib
import re
import shutil
import tempfile
import unittest
from datetime import timedelta

import _ctx
import build_pages as bp


REAL_DATA = _ctx.ROOT / "data"


class PagesFollowDataTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "data").mkdir()
        for p in REAL_DATA.glob("*.json"):
            shutil.copy2(p, self.root / "data" / p.name)
        # The day the committed pages were built for, read from the repo's sitemap before
        # ROOT moves to the temporary tree (which has no sitemap yet).
        self.today = bp.recorded_date()
        for name in ("ROOT", "DATA"):
            self.addCleanup(setattr, bp, name, getattr(bp, name))
        bp.ROOT, bp.DATA = self.root, self.root / "data"
        bp._unmirrored_hosts.clear()

    def build(self):
        with contextlib.redirect_stdout(io.StringIO()):
            bp.main(today=self.today)
        return {p.relative_to(self.root): p.read_bytes()
                for p in self.root.rglob("index.html")} | {
                pathlib.Path("sitemap.xml"): (self.root / "sitemap.xml").read_bytes()}

    def a_show_on_the_day(self):
        """-> (venue id, area path, index of a screening on the build day)."""
        for path in sorted((self.root / "data").glob("area-*.json")):
            d = json.loads(path.read_text(encoding="utf-8"))
            for i, s in enumerate(d.get("shows", [])):
                if (s.get("start") or "")[:10] == self.today.isoformat():
                    return path.name[5:-5], path, i
        self.fail("no screening on the recorded build day in the committed data")

    def test_a_moved_screening_moves_its_theatre_pages_and_nothing_else(self):
        before = self.build()
        vid, path, i = self.a_show_on_the_day()
        d = json.loads(path.read_text(encoding="utf-8"))
        start = d["shows"][i]["start"]
        # Five minutes later, same day: the page's time label changes, the day set does not.
        hh, mm = int(start[11:13]), int(start[14:16])
        mm = (mm + 5) % 60
        d["shows"][i]["start"] = f"{start[:11]}{hh:02d}:{mm:02d}{start[16:]}"
        path.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

        after = self.build()
        changed = sorted(str(k) for k in before if before[k] != after.get(k))
        self.assertTrue(changed, f"moving a screening at {vid} changed no page")
        # Its own theatre pages, one per published language, and possibly its city's.
        own = [k for k in changed if re.search(r"^(sv/)?(teatteri|en/theatre)/", k)]
        self.assertEqual(len(own), len(bp.LANGS), changed)
        city = json.loads(path.read_text(encoding="utf-8"))["shows"][i].get("theatre", "")
        for k in changed:
            self.assertRegex(k, r"^(sv/)?(teatteri|kaupunki|en/theatre|en/city)/",
                             f"{k} moved for a screening at {vid}")
        self.assertEqual(before[pathlib.Path("sitemap.xml")], after[pathlib.Path("sitemap.xml")])
        # Unrelated theatre pages are byte-identical.
        untouched = [k for k in before if str(k).startswith("teatteri/") and str(k) not in changed]
        self.assertGreater(len(untouched), 50)

    def test_the_same_data_rebuilds_byte_identical(self):
        self.assertEqual(self.build(), self.build())


if __name__ == "__main__":
    unittest.main()
