"""scripts/ci_verified.py: when main may skip the heavy Checks for a commit.

Fixtures follow the Actions API's shapes as read on 2026-09-24 for 49120e4bf, a
three-commit fast-forward whose branch run passed. Two runs per case minimum, so the
filter and the ordering are exercised and not only the single-candidate path.
"""
import os
import unittest

import _ctx                                                # noqa: F401
import ci_verified as V

SHA = "49120e4bf4666f8372f9fa3d51c4419c228ba00a"
MAIN_RUN = 36003080437


def run(rid, branch, conclusion="success", status="completed", path=V.WORKFLOW,
        event="push", started="2026-09-24T12:50:00Z"):
    return {"id": rid, "head_branch": branch, "status": status, "conclusion": conclusion,
            "path": path, "event": event, "run_started_at": started,
            "jobs_url": f"https://api.example/runs/{rid}/jobs"}


def job(name, conclusion="success", step="success"):
    first = "Unit suite, with nothing skipped" if name == "check" else "Browser suite"
    return {"name": name, "conclusion": conclusion,
            "steps": [{"name": "Set up job", "conclusion": "success"},
                      {"name": first, "conclusion": step}]}


GREEN = [job("check"), job("browser (chromium)"), job("browser (webkit)")]


def jobs(table):
    return lambda r: table[r["id"]]


class DecideTest(unittest.TestCase):
    def test_a_multi_commit_fast_forward_verified_on_its_branch_skips(self):
        runs = [run(MAIN_RUN, "main", status="in_progress", conclusion=None),
                run(36003080425, "main", path=".github/workflows/logs.yml",
                    conclusion="failure"),
                run(36002584828, "claude/tests-no-real-waits")]
        skip, reason = V.decide(runs, jobs({36002584828: GREEN}), MAIN_RUN)
        self.assertTrue(skip, reason)
        self.assertIn("36002584828", reason)

    def test_a_direct_push_to_main_runs_everything(self):
        runs = [run(MAIN_RUN, "main", status="in_progress", conclusion=None),
                run(35662576203, "main")]
        self.assertEqual(V.decide(runs, jobs({}), MAIN_RUN)[0], False)

    def test_the_current_run_never_vouches_for_itself(self):
        runs = [run(MAIN_RUN, "claude/x"), run(7, "main")]
        self.assertFalse(V.decide(runs, jobs({MAIN_RUN: GREEN}), MAIN_RUN)[0])

    def test_a_newer_failed_branch_run_outweighs_an_older_green_one(self):
        runs = [run(1, "claude/x", started="2026-09-24T10:00:00Z"),
                run(2, "claude/x", conclusion="failure", started="2026-09-24T11:00:00Z")]
        self.assertFalse(V.decide(runs, jobs({1: GREEN, 2: GREEN}), MAIN_RUN)[0])

    def test_a_newer_branch_run_still_running_is_not_an_answer(self):
        runs = [run(1, "claude/x", started="2026-09-24T10:00:00Z"),
                run(2, "claude/y", status="in_progress", conclusion=None,
                    started="2026-09-24T11:00:00Z")]
        self.assertFalse(V.decide(runs, jobs({1: GREEN}), MAIN_RUN)[0])

    def test_a_cancelled_branch_run_is_not_a_pass(self):
        runs = [run(1, "claude/x", conclusion="cancelled"), run(9, "main")]
        self.assertFalse(V.decide(runs, jobs({1: GREEN}), MAIN_RUN)[0])

    def test_each_browser_engine_is_required(self):
        for missing in ("browser (chromium)", "browser (webkit)", "check"):
            with self.subTest(missing=missing):
                table = {1: [j for j in GREEN if j["name"] != missing]}
                runs = [run(1, "claude/x"), run(9, "main")]
                self.assertFalse(V.decide(runs, jobs(table), MAIN_RUN)[0])

    def test_a_run_that_skipped_its_suite_does_not_vouch(self):
        """Should a branch run ever skip the heavy steps itself, it proves nothing."""
        for name in ("check", "browser (webkit)"):
            with self.subTest(job=name):
                table = {1: [job(n, step="skipped" if n == name else "success")
                             for n in ("check", "browser (chromium)", "browser (webkit)")]}
                self.assertFalse(V.decide([run(1, "claude/x"), run(9, "main")],
                                          jobs(table), MAIN_RUN)[0])

    def test_another_workflow_or_event_is_ignored(self):
        runs = [run(1, "claude/x", path=".github/workflows/logs.yml"),
                run(2, "claude/x", event="workflow_dispatch")]
        self.assertFalse(V.decide(runs, jobs({1: GREEN, 2: GREEN}), MAIN_RUN)[0])


class MainTest(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k)
                      for k in ("GITHUB_TOKEN", "GITHUB_REPOSITORY", "GITHUB_OUTPUT")}
        self.addCleanup(self.restore)

    def restore(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_an_unavailable_lookup_writes_false_and_exits_zero(self):
        import tempfile, io, contextlib
        fd, path = tempfile.mkstemp()
        os.close(fd)
        self.addCleanup(os.unlink, path)
        os.environ.pop("GITHUB_TOKEN", None)
        os.environ["GITHUB_REPOSITORY"] = "Shady-Dev/kino"
        os.environ["GITHUB_OUTPUT"] = path
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(V.main(["ci_verified.py", SHA, str(MAIN_RUN)]), 0)
        with open(path, encoding="utf-8") as f:
            self.assertIn("skip=false\n", f.read())

    def test_an_api_error_is_the_full_run(self):
        import io, contextlib, urllib.error
        os.environ.update(GITHUB_TOKEN="t", GITHUB_REPOSITORY="Shady-Dev/kino")
        os.environ.pop("GITHUB_OUTPUT", None)
        real = V._get

        def boom(url, token):
            raise urllib.error.URLError("down")
        V._get = boom
        self.addCleanup(setattr, V, "_get", real)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            V.main(["ci_verified.py", SHA, str(MAIN_RUN)])
        self.assertIn("skip=false", buf.getvalue())
        self.assertIn("lookup unavailable", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
