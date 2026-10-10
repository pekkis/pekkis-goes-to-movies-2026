"""check_runs.py: the local half's only failure signal.

A failed cloud provider turns its Actions run red. The local half runs outside this repo,
writes `exit=1` into a log, pushes it and carries on. Both halves commit their logs, so
reading them is the signal. The deciding cases: a log with no exit line, and a stale log
nobody overwrites any more.
"""
import contextlib
import io
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import check_runs


class CheckRunsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def log(self, name, body):
        (self.dir / name).write_text(body, encoding="utf-8")

    def run_check(self):
        return check_runs.main(["--dir", str(self.dir)])

    def test_the_default_dir_finds_the_repos_own_logs(self):
        """Every other test passes --dir, so none of them would notice the logs moving.

        This is the one that goes red on a half-done migration: it asserts the default
        resolves to a directory that actually holds the committed logs, and it does not
        care what the working directory is.
        """
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            check_runs.main([])
        self.assertNotIn("nothing has been committed yet", err.getvalue())
        self.assertRegex(out.getvalue(), r"\[check\] \d+ run log\(s\)")

    def test_a_log_left_at_the_repo_root_fails(self):
        """A writer that was not migrated keeps publishing where nothing reads.

        Without this the check would read the moved copies, find them fine and report
        green while the live half wrote somewhere else entirely.
        """
        self.assertEqual(check_runs.strays(self.dir), [])
        (self.dir / "run-stray.log").write_text("exit=0\n", encoding="utf-8")
        self.assertEqual([p.name for p in check_runs.strays(self.dir)], ["run-stray.log"])

    def test_all_clean_passes(self):
        self.log("run.log", "[run] fine\nexit=0\n")
        self.log("run-biorex.log", "[run] biorex: 12 venues\nexit=0\n")
        self.assertEqual(self.run_check(), 0)

    def test_a_non_zero_exit_fails(self):
        self.log("run.log", "exit=0\n")
        self.log("run-vista.log", "[savonkinot] FAILED: HTTP Error 404: Not Found\nexit=1\n")
        self.assertEqual(self.run_check(), 1)

    def test_a_log_with_no_exit_line_fails(self):
        """Every writer appends one, so its absence means the run died before it could
        or the file was truncated. Treating that as clean is how a half-written log
        passes for a healthy one."""
        self.log("run.log", "[run] started and then nothing\n")
        self.assertEqual(self.run_check(), 1)

    def test_no_logs_at_all_fails(self):
        self.assertEqual(self.run_check(), 1)

    def test_a_stale_log_still_counts(self):
        """run-vista.log sat at exit=1 for hours because its module was retired and
        nothing overwrote it. Age is not a reason to stop reporting."""
        self.log("run.log", "exit=0\n")
        self.log("run-vista.log", "[savonkinot] FAILED: gone\nexit=1\n")
        self.assertEqual(self.run_check(), 1)

    def test_the_cause_line_is_reported_not_just_the_code(self):
        self.log("run-etiketti.log",
                 "[joutsankino] FAILED: HTTP Error 403: Forbidden\n"
                 "[http] 403 from kino.joutsa.fi, gave up after 3 attempt(s)\nexit=1\n")
        ok, code, causes = check_runs.check(self.dir / "run-etiketti.log")
        self.assertFalse(ok)
        self.assertEqual(code, 1)
        self.assertTrue(any("kino.joutsa.fi" in c for c in causes), causes)

    def test_a_clean_log_with_trailing_output_is_still_clean(self):
        """A checker that reads only the final line calls this unreadable and reports a
        healthy run as broken -- which trains people to ignore it, the same failure the
        deleted fetch.yml caused by being permanently red."""
        self.log("run.log", "exit=0\n[run] a note printed after the exit line\n")
        self.assertEqual(self.run_check(), 0)

    def test_the_last_exit_line_wins(self):
        """Each writer appends its own when it finishes, so a later one supersedes an
        earlier one; taking the first would report a run that recovered as failed."""
        self.log("run.log", "exit=1\n[run] second stage\nexit=0\n")
        self.assertEqual(self.run_check(), 0)


if __name__ == "__main__":
    unittest.main()


class FailingSiteHistoryTest(unittest.TestCase):
    """Every failing site is named and marked new or carried, from git history alone.

    Nineteen of twenty cloud runs up to 2026-09-25 were red from Kinotour's HTTP 500, so a
    second site failing read exactly like the first (audit, cloud verdict). The run stays
    red; the report says which failure is which. No state file: the committed logs are the
    record, read with `git log` and `git show`.
    """

    OK = "[x] X: 3 showtimes\nexit=0\n"

    @staticmethod
    def failed(*sites):
        return "".join(f"[{s}] FAILED: HTTP Error 500\n" for s in sites) + "exit=1\n"

    def setUp(self):
        import subprocess
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = pathlib.Path(self.tmp.name)
        self.logs = self.repo / "logs"
        self.logs.mkdir()
        self.git = lambda *a: subprocess.run(["git", "-C", str(self.repo), *a], check=True,
                                             capture_output=True, text=True)
        self.git("init", "-q")
        self.git("config", "user.name", "t")
        self.git("config", "user.email", "t" + "@" + "example.invalid")
        self.day = 0

    def commit(self, body, name="run-mod.log"):
        import os
        self.day += 1
        (self.logs / name).write_text(body, encoding="utf-8")
        self.git("add", "-A")
        when = f"2026-09-{10 + self.day:02d}T12:00:00+00:00"
        import subprocess
        subprocess.run(["git", "-C", str(self.repo), "commit", "-q", "-m", "run"], check=True,
                       env=dict(os.environ, GIT_COMMITTER_DATE=when, GIT_AUTHOR_DATE=when))

    def report(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = check_runs.main(["--dir", str(self.logs)])
        return code, err.getvalue()

    def test_a_site_failing_for_the_first_time_is_new(self):
        self.commit(self.OK)
        self.commit(self.failed("alpha"))
        code, err = self.report()
        self.assertEqual(code, 1, "the run stays red")
        self.assertIn("    alpha: new", err)

    def test_a_site_failing_run_after_run_is_carried_since_its_first_failure(self):
        self.commit(self.OK)
        self.commit(self.failed("alpha"))            # 2026-09-12
        self.commit(self.failed("alpha") + "\n")     # 2026-09-13, a later run
        self.commit(self.failed("alpha"))            # 2026-09-14
        code, err = self.report()
        self.assertEqual(code, 1)
        self.assertIn("    alpha: carried since 2026-09-12 (3 runs)", err)

    def test_a_new_site_beside_a_carried_one_is_told_apart(self):
        self.commit(self.OK)
        self.commit(self.failed("alpha"))
        self.commit(self.failed("alpha", "beta"))
        _, err = self.report()
        self.assertIn("    alpha: carried since 2026-09-12 (2 runs)", err)
        self.assertIn("    beta: new", err)

    def test_the_file_on_disk_ahead_of_its_commit_is_the_run_being_judged(self):
        """The fetch workflow writes the log and checks before it commits."""
        self.commit(self.OK)
        self.commit(self.failed("alpha"))
        (self.logs / "run-mod.log").write_text(self.failed("alpha") + "\n", encoding="utf-8")
        _, err = self.report()
        self.assertIn("    alpha: carried since 2026-09-12 (2 runs)", err)

    def test_the_coordinator_log_names_the_module(self):
        self.commit("[cloud] a: exit=0\n[cloud] kinotour: exit=1\nexit=1\n", "run-cloud.log")
        _, err = self.report()
        self.assertIn("    kinotour: new", err)

    def test_a_streak_reaching_the_history_limit_is_at_least_that_old(self):
        for _ in range(3):
            self.commit(self.failed("alpha") + "x" * self.day)
        saved = check_runs.HISTORY_LIMIT
        check_runs.HISTORY_LIMIT = 2
        self.addCleanup(lambda: setattr(check_runs, "HISTORY_LIMIT", saved))
        _, err = self.report()
        self.assertIn("    alpha: carried since at least 2026-09-12 (2 runs read)", err)
