"""The pages are built for an explicit day, and CI rebuilds for the recorded one.

`build_pages.main()` read the clock, and every page lists a window of days from that day,
so CI's regeneration check went red after midnight with nothing changed. `main(today=None)`
takes the day; `--date YYYY-MM-DD` passes one; `--date recorded` reads it back from the
committed sitemap, whose every `lastmod` is written from that day. Publishing still reads
the clock.

Built against a small synthetic city (two venues in Oulu, one show a day for a week) with
a patched clock, so the day is the only thing that moves between builds.
"""
import contextlib
import io
import json
import pathlib
import re
import shutil
import tempfile
import unittest
from datetime import date, datetime, time, timedelta

import _ctx
import build_pages as bp


D = date(2026, 9, 5)                       # the day the fixture is built for
ROOT = _ctx.ROOT
CI = ROOT / ".github" / "workflows" / "ci.yml"
PUBLISH = ROOT / ".github" / "workflows" / "biorex.yml"


class Clock:
    """Stands in for `datetime` inside build_pages: `now(tz)` is noon on a chosen day."""

    def __init__(self, day):
        self.day = day
        self.asked = []

    def now(self, tz=None):
        self.asked.append(tz)
        return datetime.combine(self.day, time(12, 0), tzinfo=tz)


def show(venue_id, name, day):
    iso = day.isoformat()
    return {"eventId": f"{venue_id}-{iso}", "title": "Testielokuva", "original": "",
            "len": "100", "rating": "K-7", "age": "", "genres": "Draama", "method": "2D",
            "theatre": name, "aud": "Sali 1", "start": f"{iso}T18:00:00+03:00",
            "url": f"https://example.invalid/liput?d={iso}", "img": "", "lang": "FI-A",
            "soldOut": False}


def write_fixture(root):
    data = root / "data"
    data.mkdir()
    venues = [("1001", "Kino Testi Oulu"), ("1002", "Studio Testi Oulu")]
    (data / "providers.json").write_text(json.dumps({"providers": [
        {"id": "finnkino", "label": "Finnkino", "host": "finnkino.fi",
         "accent": "#E4551F", "book": "buy"}]}), encoding="utf-8")
    (data / "tmdb-genres.json").write_text(json.dumps({"fi": {}, "sv": {}, "en": {}}), encoding="utf-8")
    (data / "films-extra.json").write_text(json.dumps({"generated": "2026-09-01", "films": {}}), encoding="utf-8")
    (data / "areas.json").write_text(json.dumps({
        "generated": "2026-09-05T05:00:00+00:00",
        "areas": [{"id": i, "name": n} for i, n in venues]}), encoding="utf-8")
    for vid, name in venues:
        shows = [show(vid, name, D + timedelta(days=k)) for k in range(-1, 6)]
        (data / f"area-{vid}.json").write_text(json.dumps({
            "generated": "2026-09-05T05:00:00+00:00",
            "dates": sorted({s["start"][:10] for s in shows}),
            "shows": shows}), encoding="utf-8")


class BuildDateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        write_fixture(self.root)
        for name in ("ROOT", "DATA", "datetime"):
            self.addCleanup(setattr, bp, name, getattr(bp, name))
        bp.ROOT, bp.DATA = self.root, self.root / "data"
        bp._unmirrored_hosts.clear()

    # -- helpers ---------------------------------------------------------------------------

    def build(self, today=None, clock=None, argv=None):
        """Run the real main() (or cli(argv)) under a clock set to `clock`. -> stdout."""
        self.clock = Clock(clock or D)
        bp.datetime = self.clock
        buf = io.StringIO()
        # stderr too: argparse prints its usage line when a date is refused below.
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            if argv is not None:
                bp.cli(argv)
            else:
                bp.main(today=today)
        return buf.getvalue()

    def snapshot(self):
        """Every generated file, by content. The data is excluded: it is the input."""
        out = {}
        for p in sorted(self.root.rglob("*")):
            if p.is_file() and "data" not in p.relative_to(self.root).parts:
                out[str(p.relative_to(self.root))] = p.read_text(encoding="utf-8")
        return out

    def venue_page(self, snap):
        hits = [k for k in snap if k.startswith("teatteri/") and "kino-testi" in k]
        self.assertEqual(len(hits), 1, hits)
        return snap[hits[0]]

    @staticmethod
    def ld_days(page):
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
        return sorted(set(re.findall(r'"startDate":\s*"(\d{4}-\d{2}-\d{2})', m.group(1))))

    @staticmethod
    def listed_days(page):
        return sorted(set(re.findall(r"liput\?d=(\d{4}-\d{2}-\d{2})", page)))

    # -- the day is explicit ----------------------------------------------------------------

    def test_an_explicit_date_shuts_the_clock_out(self):
        """The same input and the same date on two different days: identical bytes."""
        self.build(today=D, clock=D)
        first = self.snapshot()
        shutil.rmtree(self.root / "teatteri"); shutil.rmtree(self.root / "kaupunki")
        shutil.rmtree(self.root / "en"); (self.root / "sitemap.xml").unlink()
        self.build(today=D, clock=D + timedelta(days=1))
        self.assertTrue(first)
        self.assertEqual(self.snapshot(), first)
        self.assertEqual(self.clock.asked, [], "a dated build has no reason to ask the clock")

    def test_without_a_date_the_clock_decides_in_helsinki_time(self):
        """Publishing is unchanged: no date means today, and today is Europe/Helsinki's."""
        self.build(clock=D + timedelta(days=1))
        self.assertEqual(self.clock.asked, [bp.FI])
        self.assertEqual(self.ld_days(self.venue_page(self.snapshot())),
                         [(D + timedelta(days=1)).isoformat(), (D + timedelta(days=2)).isoformat()])

    def test_a_later_date_advances_the_window_by_that_day(self):
        self.build(today=D)
        page = self.venue_page(self.snapshot())
        days = [(D + timedelta(days=k)).isoformat() for k in range(-1, 6)]
        self.assertEqual(self.listed_days(page), days[1:1 + bp.DAYS], "today plus three")
        self.assertEqual(self.ld_days(page), days[1:1 + bp.LD_DAYS], "today and tomorrow")
        self.build(today=D + timedelta(days=1))
        page = self.venue_page(self.snapshot())
        self.assertEqual(self.listed_days(page), days[2:2 + bp.DAYS])
        self.assertEqual(self.ld_days(page), days[2:2 + bp.LD_DAYS])
        self.assertNotIn(days[1], page, "yesterday's screening is gone from every part of the page")

    # -- the day is recorded and read back ---------------------------------------------------

    def test_the_sitemap_records_the_day_the_pages_were_built_for(self):
        self.build(today=D)
        sm = (self.root / "sitemap.xml").read_text(encoding="utf-8")
        lastmods = set(re.findall(r"<lastmod>([^<]+)</lastmod>", sm))
        self.assertEqual(lastmods, {D.isoformat()})
        self.assertEqual(bp.recorded_date(), D)

    def test_recorded_reproduces_the_committed_build_on_a_later_day(self):
        """The CI scenario: pages built on D, checked on D+1. `--date recorded` rewrites
        nothing; the plain build, which is what CI used to run, rewrites the set."""
        self.build(today=D)
        committed = self.snapshot()
        out = self.build(argv=["--date", "recorded"], clock=D + timedelta(days=1))
        self.assertIn(" 0 files written", out)
        self.assertEqual(self.snapshot(), committed)
        out = self.build(argv=[], clock=D + timedelta(days=1))
        self.assertNotIn(" 0 files written", out)
        self.assertNotEqual(self.snapshot(), committed)

    def test_an_explicit_date_on_the_command_line_is_the_same_as_in_code(self):
        self.build(today=D)
        committed = self.snapshot()
        out = self.build(argv=["--date", D.isoformat()], clock=D + timedelta(days=3))
        self.assertIn(" 0 files written", out)
        self.assertEqual(self.snapshot(), committed)

    def test_a_malformed_date_and_a_missing_record_are_refused(self):
        with self.assertRaises(SystemExit) as cm:
            self.build(argv=["--date", "2026-13-45"])
        self.assertNotEqual(cm.exception.code, 0)
        with self.assertRaises(SystemExit) as cm:
            self.build(argv=["--date", "recorded"])      # nothing built yet: no sitemap
        self.assertNotEqual(cm.exception.code, 0)
        self.assertFalse((self.root / "teatteri").exists(), "a refused build writes nothing")

    # -- the workflows ---------------------------------------------------------------------------

    def test_ci_reproduces_with_the_recorded_date_and_publishing_keeps_the_clock(self):
        """Read rather than retyped, so the wiring cannot drift from the mechanism."""
        ci = CI.read_text(encoding="utf-8")
        step = ci.split("Generated output is reproducible", 1)[1].split("- name:", 1)[0]
        self.assertIn("python3 scripts/build_pages.py --date recorded", step)
        publish = PUBLISH.read_text(encoding="utf-8")
        calls = re.findall(r"python3 scripts/build_pages\.py[^\n]*", publish)
        self.assertEqual(len(calls), 1, calls)
        self.assertNotIn("--date", calls[0])


if __name__ == "__main__":
    unittest.main()
