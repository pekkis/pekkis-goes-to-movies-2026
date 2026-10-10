"""check_staleness.py: fail when no run has happened, which check_runs.py cannot see.

`check_runs.py` reads committed logs and answers "did the last run fail"; a log saying
`exit=0` four days ago passes it. A run that never starts produces no log. The staleness
check is a pure function of a file and a clock; when it runs and who it tells live outside
this public repo. The clock is injected so a boundary test asserts something.
"""
import datetime
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

import _ctx
import check_staleness as cs


SCRIPT = _ctx.ROOT / "scripts" / "check_staleness.py"
NOW = datetime.datetime(2026, 9, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
# Distinguishes "no `generated` key" from "`generated` is None", which are different
# failures and would otherwise be the same fixture.
_MISSING = object()
AGE_RE = re.compile(r"(-?[\d.]+) h old")


def hours(n):
    return datetime.timedelta(hours=n)


class StalenessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def write(self, generated, name="areas.json", **extra):
        p = self.dir / name
        doc = {"areas": [{"id": "1", "name": "Tennispalatsi"}]}
        if generated is not _MISSING:
            doc["generated"] = generated
        doc.update(extra)
        p.write_text(json.dumps(doc), encoding="utf-8")
        return p

    def raw(self, text, name="areas.json"):
        p = self.dir / name
        p.write_text(text, encoding="utf-8")
        return p

    def at(self, delta, **kw):
        """A file generated `delta` from the fixed now. -> (ok, message)."""
        return cs.check(self.write((NOW + delta).isoformat()), now=NOW, **kw)

    # -- the age boundary ----------------------------------------------------------------

    def test_a_fresh_file_passes(self):
        ok, msg = self.at(-hours(2))
        self.assertTrue(ok, msg)
        self.assertIn("2.0 h old", msg)
        self.assertIn("limit 8 h", msg)

    def test_exactly_the_threshold_is_not_yet_stale(self):
        """The client reads `ageH > STALE_H`, so eight hours exactly is still fine. If
        this and the banner disagreed, one of them would be announcing a second,
        invisible definition of stale."""
        ok, _ = self.at(-hours(8))
        self.assertTrue(ok)

    def test_a_second_past_the_threshold_is_stale(self):
        """The other side of the same boundary. Without this, a check written as `>=`
        and a check written as `>` both pass."""
        ok, msg = self.at(-hours(8) - datetime.timedelta(seconds=1))
        self.assertFalse(ok)
        self.assertIn("STALE", msg)

    def test_a_file_days_old_is_stale(self):
        ok, msg = self.at(-hours(96))
        self.assertFalse(ok)
        self.assertIn("96.0 h old", msg)

    def test_the_limit_is_adjustable_for_the_caller(self):
        self.assertFalse(self.at(-hours(2), max_age_h=1)[0])
        self.assertTrue(self.at(-hours(2), max_age_h=3)[0])

    # -- offsets, because the timestamp is not always written in UTC ---------------------

    def test_a_positive_offset_is_honoured(self):
        """14:00+03:00 is 11:00 UTC, one hour before the fixed now -- not two hours in
        the future, which is what reading the wall-clock digits would give."""
        p = self.write("2026-09-01T14:00:00+03:00")
        ok, msg = cs.check(p, now=NOW)
        self.assertTrue(ok, msg)
        self.assertIn("1.0 h old", msg)

    def test_a_negative_offset_is_honoured(self):
        """05:00-05:00 is 10:00 UTC, two hours old."""
        ok, msg = cs.check(self.write("2026-09-01T05:00:00-05:00"), now=NOW)
        self.assertTrue(ok, msg)
        self.assertIn("2.0 h old", msg)

    def test_a_z_suffix_is_read_as_utc(self):
        ok, msg = cs.check(self.write("2026-09-01T09:00:00Z"), now=NOW)
        self.assertTrue(ok, msg)
        self.assertIn("3.0 h old", msg)

    def test_a_timestamp_with_no_offset_is_refused(self):
        """Not read as UTC and not read as local. A naive stamp would be three hours out
        here and silently a different answer on another machine."""
        ok, msg = cs.check(self.write("2026-09-01T10:00:00"), now=NOW)
        self.assertFalse(ok)
        self.assertIn("no UTC offset", msg)

    # -- the future, which is the dangerous direction ------------------------------------

    def test_a_few_minutes_ahead_is_ordinary_drift(self):
        """Two machines, two clocks. This must not page anyone."""
        ok, msg = self.at(datetime.timedelta(minutes=2))
        self.assertTrue(ok, msg)
        self.assertIn("0.0 h old", msg)

    def test_a_timestamp_well_into_the_future_fails(self):
        """The failure mode worth naming: a file stamped ahead reads as fresh for as
        long as the skew lasts, so it would silence the monitor rather than trip it."""
        ok, msg = self.at(hours(30))
        self.assertFalse(ok)
        self.assertIn("in the future", msg)
        self.assertIn("clock is wrong", msg)

    def test_the_future_is_never_reported_as_a_negative_age(self):
        """Inside the tolerance the file is accepted, and "-0.1 h old" would be a
        nonsense line for whoever reads the monitor's output."""
        ok, msg = self.at(datetime.timedelta(minutes=4))
        self.assertTrue(ok)
        m = AGE_RE.search(msg)
        self.assertIsNotNone(m, msg)
        self.assertGreaterEqual(float(m.group(1)), 0.0, msg)

    # -- a limit that could not have been meant --------------------------------------

    def test_an_infinite_limit_is_refused(self):
        """`inf` makes every comparison false, so the check passes for ever: a monitor
        that cannot fail, which is worse than none because it looks like one."""
        with self.assertRaises(ValueError):
            self.at(-hours(2), max_age_h=float("inf"))

    def test_a_nan_limit_is_refused(self):
        """The quieter of the two. `nan > x` and `x > nan` are both false, so it also
        never fires, and unlike `inf` it does not even read as suspicious in a log."""
        with self.assertRaises(ValueError):
            self.at(-hours(2), max_age_h=float("nan"))

    def test_a_negative_limit_is_refused_rather_than_read_as_always_stale(self):
        """It is a typo, not an instruction. Reporting it as stale data would send
        somebody to look at a pipeline that is fine."""
        with self.assertRaises(ValueError):
            self.at(-hours(2), max_age_h=-1)

    def test_a_zero_limit_is_allowed(self):
        """Useful, and how the stale branch is exercised without waiting: it asks
        whether the file was written in the last instant."""
        ok, msg = self.at(-hours(2), max_age_h=0)
        self.assertFalse(ok)
        self.assertIn("STALE", msg)

    # -- files that cannot answer the question -------------------------------------------

    def test_a_missing_file_fails(self):
        ok, msg = cs.check(self.dir / "nope.json", now=NOW)
        self.assertFalse(ok)
        self.assertIn("no such file", msg)

    def test_a_file_that_is_not_json_fails(self):
        ok, msg = cs.check(self.raw("<html>404</html>"), now=NOW)
        self.assertFalse(ok)
        self.assertIn("not JSON", msg)

    def test_a_truncated_file_fails(self):
        """What a half-written file looks like. write_json is atomic, so this should be
        impossible -- which is the reason to check rather than assume."""
        ok, msg = cs.check(self.raw('{"generated": "2026-09-01T10:00'), now=NOW)
        self.assertFalse(ok)
        self.assertIn("not JSON", msg)

    def test_a_json_document_that_is_not_an_object_fails(self):
        ok, msg = cs.check(self.raw('["2026-09-01T10:00:00+00:00"]'), now=NOW)
        self.assertFalse(ok)
        self.assertIn("expected an object", msg)

    def test_a_missing_generated_field_fails(self):
        ok, msg = cs.check(self.write(_MISSING), now=NOW)
        self.assertFalse(ok)
        self.assertIn("no `generated` field", msg)

    def test_a_generated_field_of_the_wrong_type_fails(self):
        for bad in (1756728000, None, [], {}, True):
            with self.subTest(bad=bad):
                ok, msg = cs.check(self.write(bad), now=NOW)
                self.assertFalse(ok)

    def test_an_empty_generated_field_fails(self):
        ok, msg = cs.check(self.write("   "), now=NOW)
        self.assertFalse(ok)

    def test_a_generated_field_that_is_not_a_timestamp_fails(self):
        for bad in ("yesterday", "2026-13-45T99:00:00+00:00", "1756728000"):
            with self.subTest(bad=bad):
                ok, msg = cs.check(self.write(bad), now=NOW)
                self.assertFalse(ok)
                self.assertIn("generated", msg)

    def test_an_unreadable_file_never_reports_an_age(self):
        """A broken file is a different answer from an old one, and the message has to
        say which. Reporting "0.0 h old" for a file it could not parse would read as the
        healthiest possible result."""
        for p in (self.dir / "nope.json", self.raw("not json")):
            with self.subTest(path=p.name):
                ok, msg = cs.check(p, now=NOW)
                self.assertFalse(ok)
                self.assertNotIn("h old", msg)

    # -- the file this watches ---------------------------------------------------

    def test_the_repos_own_areas_json_is_readable(self):
        """Against the committed file, not a fixture. This says the format the pipeline
        writes is the format this parses -- the assumption most likely to rot."""
        when = cs.read_generated(_ctx.ROOT / "data" / "areas.json")
        self.assertIsNotNone(when.tzinfo)
        self.assertIsNotNone(when.utcoffset())

    def test_the_default_file_is_the_one_the_backlog_names(self):
        self.assertEqual(str(cs.DEFAULT_FILE), "data/areas.json")

    def test_the_threshold_matches_the_client(self):
        """Read out of index.html rather than copied, so the two cannot drift apart
        without this going red."""
        html = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")
        m = re.search(r"const STALE_H = (\d+);", html)
        self.assertIsNotNone(m, "STALE_H is no longer declared the way this reads it")
        self.assertEqual(cs.MAX_AGE_H, float(m.group(1)))


class CommandLineTest(unittest.TestCase):
    """The half `kino-auth` calls: an exit code and one line."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def run_it(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True, cwd=str(_ctx.ROOT),
                              timeout=60)

    def fresh_file(self):
        """A file stamped now, so the success path does not depend on when the local
        publisher last ran.

        The first version of this ran against the committed `data/areas.json` with no
        arguments, which passes only while that file is under eight hours old. CI runs on
        code pushes, so an unrelated change would have gone red because a laptop had not
        published that morning -- the monitor reaching into the very CI it was written to
        stay out of.
        """
        p = self.dir / "areas.json"
        now = datetime.datetime.now(datetime.timezone.utc)
        p.write_text(json.dumps({"generated": now.isoformat(), "areas": []}),
                     encoding="utf-8")
        return p

    def test_a_fresh_file_passes_with_an_exit_code_of_zero(self):
        out = self.run_it("--file", str(self.fresh_file()))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("fresh", out.stdout)
        self.assertEqual(out.stderr, "")

    def default_path_dir(self, age):
        """A temporary working directory holding data/areas.json at `age`."""
        (self.dir / "data").mkdir(exist_ok=True)
        when = datetime.datetime.now(datetime.timezone.utc) - age
        (self.dir / "data" / "areas.json").write_text(
            json.dumps({"generated": when.isoformat(), "areas": []}), encoding="utf-8")
        return self.dir

    def test_the_default_path_resolves_and_passes(self):
        """The invocation `kino-auth` will make: no arguments at all. Run from
        a temporary working directory so it reads a timestamp this test controls."""
        out = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True,
                             text=True, cwd=str(self.default_path_dir(hours(1))),
                             timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("data/areas.json", out.stdout)
        self.assertIn("1.0 h old", out.stdout)

    def test_the_default_path_reports_a_stale_file(self):
        """The same invocation over data that has stopped moving, which is the whole
        point of the thing.

        Both of these used to be one test run against the committed `data/areas.json`
        with `--hours 0`, on the reasoning that any committed file is older than an
        instant. It is not: a timestamp up to five minutes ahead is deliberately accepted
        and clamped to `0.0 h old`, and `0.0 > 0` is false -- so a publisher clock a few
        minutes fast turned that test red while the script was answering correctly.
        Reproduced by stamping the committed file two minutes ahead."""
        out = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True,
                             text=True, cwd=str(self.default_path_dir(hours(20))),
                             timeout=60)
        self.assertEqual(out.returncode, 1)
        self.assertIn("data/areas.json", out.stderr)
        self.assertIn("STALE", out.stderr)

    def test_a_stale_file_exits_one_and_says_so_on_stderr(self):
        """The split matters to the caller: `2>&1 >/dev/null` keeps the complaint and
        drops the routine line. It is not silence on its own -- cron mails either
        stream -- so this only says the two are separable."""
        out = self.run_it("--file", str(self.fresh_file()), "--hours", "0")
        self.assertEqual(out.returncode, 1)
        self.assertIn("STALE", out.stderr)
        self.assertEqual(out.stdout, "")

    def test_a_missing_file_exits_one(self):
        out = self.run_it("--file", str(self.dir / "nope.json"))
        self.assertEqual(out.returncode, 1)
        self.assertIn("no such file", out.stderr)

    def test_the_line_carries_the_timestamp_the_age_and_the_limit(self):
        out = self.run_it("--file", str(self.fresh_file()))
        line = out.stdout.strip()
        self.assertTrue(line.startswith("[stale] "), line)
        self.assertIn("generated 20", line)
        self.assertIn("h old", line)
        self.assertIn("limit 8 h", line)

    def test_a_limit_that_could_not_have_been_meant_exits_two(self):
        """Two, not one. A caller that cannot tell its own typo from a pipeline outage
        would go looking in the wrong place -- and `nan` and `inf` used to exit 0 and
        report the data fresh for ever."""
        for bad in ("nan", "inf", "-inf", "-1"):
            with self.subTest(hours=bad):
                # `--hours=-inf` rather than `--hours -inf`: argparse reads a bare
                # `-inf` as an option name, because it only treats a leading `-` as part
                # of a value when it matches a number. That refusal is argparse's and
                # exits 2 as well, but it is not the guard under test here.
                out = self.run_it("--file", str(self.fresh_file()), f"--hours={bad}")
                self.assertEqual(out.returncode, 2, out.stderr)
                self.assertNotIn("fresh", out.stdout)
                self.assertIn("limit must", out.stderr)

    def test_a_bare_negative_infinity_is_still_refused(self):
        """The spelling a caller would type. argparse rejects it before the
        validator sees it; what matters is that it does not run the check."""
        out = self.run_it("--hours", "-inf")
        self.assertEqual(out.returncode, 2)
        self.assertNotIn("fresh", out.stdout)

    def test_a_limit_that_is_not_a_number_exits_two(self):
        out = self.run_it("--hours", "soon")
        self.assertEqual(out.returncode, 2)


if __name__ == "__main__":
    unittest.main()
