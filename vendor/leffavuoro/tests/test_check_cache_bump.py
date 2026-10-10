"""A commit that touches index.html bumps CACHE in sw.js, and the gate reads the constant.

Two of the 120 most recent commits touching `index.html` shipped without the bump,
`f360a09c0` and `3a811db46`, while the rule was prose in CLAUDE.md alone. These tests
build small repositories with real git, the way `tests/test_check_design_push.py` does for
its neighbour, so the log walk and the blob lookups are git's own.
"""
import contextlib
import io
import pathlib
import re
import subprocess
import tempfile
import unittest

import _ctx
import check_cache_bump as ccb
import check_design_push as cdp

MISSING = "d" * 40


def git(repo, *args):
    r = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(f"git {' '.join(args)}: {r.stderr}")
    return r.stdout.strip()


def commit(repo, message, **files):
    for name, text in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git(repo, "add", name)
    git(repo, "-c", "user.name=t", "-c", "user.email=t@localhost", "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def worker(version):
    """sw.js as this repo writes it: a comment, then the constant."""
    return f"// Bump on every index.html change.\nconst CACHE = 'leffavuoro-v{version}';\n"


class CheckCacheBumpTest(unittest.TestCase):
    """main: A (v1). branch: B (index.html + the bump), C (index.html, no bump)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = pathlib.Path(self.tmp.name)
        git(self.repo, "init", "-q", "-b", "main")
        self.a = commit(self.repo, "A", **{"index.html": "x\n", "sw.js": worker(1),
                                           "IDEAS.md": "notes\n"})
        git(self.repo, "checkout", "-q", "-b", "feature")
        self.b = commit(self.repo, "B", **{"index.html": "y\n", "sw.js": worker(2)})
        self.c = commit(self.repo, "C", **{"index.html": "z\n"})
        self.log = []

    def run_check(self, before, after):
        return ccb.main([before, after, "--base", "main", "--repo", str(self.repo)])

    def out(self, before, after):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = ccb.main([before, after, "--base", "main", "--repo", str(self.repo)])
        return code, buf.getvalue()

    # -- the rule ------------------------------------------------------------------------

    def test_a_change_with_the_bump_passes_and_one_without_it_fails(self):
        self.assertEqual(self.run_check(self.a, self.b), 0, "B bumps v1 to v2")
        code, text = self.out(self.b, self.c)
        self.assertEqual(code, 1, text)
        self.assertIn(self.c[:10], text)
        self.assertIn("::error::", text)

    def test_a_bump_in_an_earlier_commit_of_the_push_does_not_answer_for_a_later_one(self):
        """Read as one range, B's bump covers C. The rule is per commit, as it is for the
        IDEAS entry next door and for the same reason."""
        self.assertEqual(self.run_check(self.a, self.c), 1)
        self.assertEqual(ccb.bumpless_commits(self.a, self.c, self.repo), [self.c])

    def test_a_push_that_touches_no_page_is_not_asked_for_a_bump(self):
        d = commit(self.repo, "D", **{"IDEAS.md": "notes\nmore\n"})
        code, text = self.out(self.c, d)
        self.assertEqual(code, 0, text)
        self.assertIn("index.html untouched", text)

    def test_editing_the_worker_without_renaming_the_cache_is_not_a_bump(self):
        """Why the constant is read rather than the diff: `git show --stat` says sw.js
        moved, and the old page still answers offline because the cache keeps its name."""
        d = commit(self.repo, "D", **{"index.html": "w\n",
                                      "sw.js": worker(2) + "// a comment\n"})
        self.assertEqual(ccb.bumpless_commits(self.c, d, self.repo), [d])
        self.assertEqual(self.run_check(self.c, d), 1)

    def test_deleting_the_worker_while_changing_the_page_is_not_a_bump(self):
        git(self.repo, "rm", "-q", "sw.js")
        (self.repo / "index.html").write_text("gone\n", encoding="utf-8")
        git(self.repo, "add", "index.html")
        git(self.repo, "-c", "user.name=t", "-c", "user.email=t@localhost",
            "commit", "-q", "-m", "D")
        d = git(self.repo, "rev-parse", "HEAD")
        self.assertIsNone(ccb.cache_at(self.repo, d))
        self.assertEqual(ccb.bumpless_commits(self.c, d, self.repo), [d])

    def test_a_worker_that_arrives_with_the_page_reads_as_a_bump(self):
        """`A^` does not resolve, and a commit that adds sw.js has no earlier name to
        differ from. Neither may be reported as a missed bump."""
        self.assertIsNone(ccb.cache_at(self.repo, f"{self.a}^"))
        git(self.repo, "checkout", "-q", "-B", "fresh", self.a)
        git(self.repo, "rm", "-q", "sw.js")
        git(self.repo, "-c", "user.name=t", "-c", "user.email=t@localhost",
            "commit", "-q", "-m", "no worker")
        gone = git(self.repo, "rev-parse", "HEAD")
        added = commit(self.repo, "the worker arrives",
                       **{"index.html": "n\n", "sw.js": worker(9)})
        self.assertEqual(ccb.bumpless_commits(gone, added, self.repo), [])

    # -- the range is the design gate's, and says which gate is speaking ------------------

    def test_an_unreachable_before_falls_back_to_the_merge_base_and_still_catches_it(self):
        base = cdp.push_base(MISSING, self.c, "main", self.repo, self.log.append, tag="cache")
        self.assertEqual(base, self.a)
        self.assertTrue(any("not reachable" in m for m in self.log), self.log)
        self.assertEqual(self.run_check(MISSING, self.c), 1)

    def test_the_log_lines_name_this_gate_rather_than_the_design_one(self):
        """Through `main`, because the tag is an argument it passes: asserting on
        `push_base` directly left that argument untested and a mutation of it scored
        VOID while this file still read OK."""
        cdp.push_base(MISSING, self.c, "main", self.repo, self.log.append, tag="cache")
        self.assertTrue(all(m.startswith("[cache]") for m in self.log), self.log)
        _, text = self.out(MISSING, self.c)
        self.assertIn("[cache] before", text)
        self.assertNotIn("[design]", text)

    def test_a_range_that_cannot_be_determined_is_exit_2_not_a_pass(self):
        git(self.repo, "checkout", "-q", "main")
        code, text = self.out(MISSING, self.a)
        self.assertEqual(code, 2, text)
        self.assertIn("cannot determine the push range", text)

    def test_a_created_ref_at_a_commit_the_base_already_holds_passes(self):
        """The 2026-09-15 case the design gate records: the branch job reads origin/main
        after main has already fast-forwarded to the same commit."""
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "merge", "-q", "--ff-only", "feature")
        code, text = self.out("0" * 40, self.c)
        self.assertEqual(code, 0, text)
        self.assertIn("already holds", text)

    # -- the verdict, and the constant in this repo ---------------------------------------

    def test_the_verdict_names_the_file_and_the_commit_without_the_bump(self):
        ok, msg = ccb.verdict(["index.html", "scripts/x.py"], ["0123456789abcdef"])
        self.assertFalse(ok)
        self.assertIn("index.html changed without a CACHE bump in sw.js in the same commit",
                      msg)
        self.assertIn("0123456789", msg)
        self.assertEqual(ccb.verdict(["index.html", "sw.js"]),
                         (True, "the index.html change carries its CACHE bump"))
        self.assertEqual(ccb.verdict(["sw.js"], ["0123456789abcdef"]),
                         (True, "index.html untouched"),
                         "a push that takes its own page change back has nothing to bump for")

    def test_the_constant_is_read_out_of_this_repo_as_written(self):
        """A regex that stops matching makes every page commit red, which is loud. One
        that matches the wrong thing is quiet, so it is pinned against the real file.

        At HEAD rather than in the working tree: a commit being written has the bump on
        disk and not yet in history, and this test is not about that difference.
        """
        head = ccb.cache_at(_ctx.ROOT, "HEAD")
        self.assertRegex(head, r"^leffavuoro-v\d+$")
        committed = subprocess.run(["git", "show", "HEAD:sw.js"], cwd=str(_ctx.ROOT),
                                   capture_output=True, text=True).stdout
        self.assertEqual(re.search(r"leffavuoro-v\d+", committed).group(0), head,
                         "the regex reads the constant, not some other version string")


class WorkflowWiringTest(unittest.TestCase):
    CI = (_ctx.ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    def test_ci_runs_the_gate_with_the_event_range(self):
        self.assertIn('python3 scripts/check_cache_bump.py "${{ github.event.before }}" '
                      '"${{ github.sha }}"', self.CI)

    def test_it_runs_on_a_push_like_the_gate_beside_it(self):
        step = self.CI.split("An index.html change carries its CACHE bump")[1]
        self.assertIn("if: github.event_name == 'push'", step.split("run:")[0])


if __name__ == "__main__":
    unittest.main()
