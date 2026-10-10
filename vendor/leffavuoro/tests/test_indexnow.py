"""indexnow: announce every kind of page change, including the ones that remove a page.

IndexNow covers added, updated, deleted and moved URLs, and removals matter most: an
engine never told a URL is gone keeps serving it until it recrawls. An earlier version
skipped pages carrying `noindex`, which suppressed exactly those notifications. Also
pinned: a push is not one commit, 202 is success, and 429 is transient.
"""
import json
import pathlib
import subprocess
import tempfile
import unittest

import _ctx                                                # noqa: F401
import indexnow

ROOT = pathlib.Path(__file__).resolve().parents[1]


# Assembled rather than written out: tests/test_contact_address.py fails on any
# email-shaped string in a tracked file, which is the guard that keeps a personal address
# out of this repo. A git identity is needed here only so commits can be made at all.
FAKE_EMAIL = "t" + chr(64) + "example.test"
BOT_EMAIL = "bot" + chr(64) + "example.test"


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          check=True).stdout


class Repo:
    """A throwaway repo, so A/M/D/R are produced by git rather than described to it."""

    def __init__(self, stack):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        stack.addCleanup(lambda: __import__("shutil").rmtree(self.dir, ignore_errors=True))
        git("init", "-q", cwd=self.dir)
        git("config", "user.email", FAKE_EMAIL, cwd=self.dir)
        git("config", "user.name", "t", cwd=self.dir)

    def write(self, rel, body="<html>page</html>"):
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")

    def rm(self, rel):
        (self.dir / rel).unlink()

    def commit(self, msg="c", author=None, when=None):
        git("add", "-A", cwd=self.dir)
        env = []
        if author:
            env = ["-c", f"user.name={author}", "-c", f"user.email={BOT_EMAIL}"]
        args = ["git", *env, "commit", "-q", "--allow-empty", "-m", msg]
        import os, subprocess
        e = dict(os.environ)
        if when:
            e["GIT_AUTHOR_DATE"] = e["GIT_COMMITTER_DATE"] = f"@{when} +0000"
        subprocess.run(args, cwd=self.dir, check=True, capture_output=True, env=e)
        return git("rev-parse", "HEAD", cwd=self.dir).strip()

    def pick(self, head_sha, started_at, ended_at=10**10):
        real = indexnow.ROOT
        indexnow.ROOT = self.dir
        try:
            return indexnow.bot_commit_for_run(head_sha, started_at, ended_at)
        finally:
            indexnow.ROOT = real

    def urls(self, before, after):
        real = indexnow.ROOT
        indexnow.ROOT = self.dir
        try:
            return indexnow.changed_urls(before, after)
        finally:
            indexnow.ROOT = real


class StatusLetterTest(unittest.TestCase):
    def setUp(self):
        self.r = Repo(self)

    def test_an_added_page_is_submitted(self):
        self.r.write("teatteri/a/index.html"); a = self.r.commit()
        self.r.write("teatteri/b/index.html"); b = self.r.commit()
        self.assertEqual(self.r.urls(a, b), ["https://leffavuoro.fi/teatteri/b/"])

    def test_a_modified_page_is_submitted(self):
        self.r.write("teatteri/a/index.html"); a = self.r.commit()
        self.r.write("teatteri/a/index.html", "<html>changed</html>"); b = self.r.commit()
        self.assertEqual(self.r.urls(a, b), ["https://leffavuoro.fi/teatteri/a/"])

    def test_a_deleted_page_is_still_submitted(self):
        """The engine has to be told the URL is gone, or it keeps the old entry."""
        self.r.write("teatteri/a/index.html")
        self.r.write("teatteri/keep/index.html"); a = self.r.commit()
        self.r.rm("teatteri/a/index.html"); b = self.r.commit()
        self.assertEqual(self.r.urls(a, b), ["https://leffavuoro.fi/teatteri/a/"])

    def test_a_renamed_page_submits_both_sides(self):
        """The old URL so it is retired, the new one so it is found."""
        body = "<html>" + "x" * 400 + "</html>"      # similar enough for -M to pair them
        self.r.write("teatteri/old/index.html", body); a = self.r.commit()
        self.r.rm("teatteri/old/index.html")
        self.r.write("teatteri/new/index.html", body); b = self.r.commit()
        self.assertEqual(self.r.urls(a, b),
                         ["https://leffavuoro.fi/teatteri/new/",
                          "https://leffavuoro.fi/teatteri/old/"])

    def test_a_noindex_redirect_is_submitted_not_skipped(self):
        """The regression the review caught. A redirect page carrying noindex is itself
        the indexing change; suppressing it defeats the point of the protocol."""
        self.r.write("teatteri/keep/index.html"); a = self.r.commit()
        self.r.write("teatteri/old/index.html",
                     '<html><meta name="robots" content="noindex,follow">'
                     '<meta http-equiv="refresh" content="0;url=/teatteri/new/"></html>')
        b = self.r.commit()
        self.assertEqual(self.r.urls(a, b), ["https://leffavuoro.fi/teatteri/old/"])

    def test_non_page_files_are_ignored(self):
        self.r.write("teatteri/a/index.html"); a = self.r.commit()
        self.r.write("data/areas.json", "{}")
        self.r.write("logs/run.log", "exit=0")
        self.r.write("scripts/x.py", "x = 1"); b = self.r.commit()
        self.assertEqual(self.r.urls(a, b), [])


class RealHistoryTest(unittest.TestCase):
    """Against this repo, so the fixtures cannot drift from what git records."""

    def urls(self, rev):
        return indexnow.changed_urls(f"{rev}^", rev)

    def test_the_legacy_redirect_commit_yields_all_four_old_urls(self):
        got = self.urls("737bf31")
        self.assertEqual(got, [
            "https://leffavuoro.fi/en/theatre/studio-123-jarvenpaa-studio-123-jarvenpaa/",
            "https://leffavuoro.fi/en/theatre/studio-123-kouvola-studio-123-kouvola/",
            "https://leffavuoro.fi/teatteri/studio-123-jarvenpaa-studio-123-jarvenpaa/",
            "https://leffavuoro.fi/teatteri/studio-123-kouvola-studio-123-kouvola/"])

    def test_the_rename_commit_yields_both_sides(self):
        got = self.urls("1da8dc3")
        for u in ("https://leffavuoro.fi/teatteri/studio-123-kouvola-studio-123-kouvola/",
                  "https://leffavuoro.fi/teatteri/studio-123-kouvola-kouvola/"):
            self.assertIn(u, got)


class WorkflowRunCommitTest(unittest.TestCase):
    """A push made with GITHUB_TOKEN does not fire `on: push`, so the routine data
    commits -- the ones that move the pages -- arrive only through
    workflow_run, and have to be found rather than handed over.

    `workflow_run.head_sha` is where the triggering run *started*, and a queued run
    starts from a base that has since moved. The named range can therefore span an
    earlier run's data commit as well as this one's, which is why the run's start time
    is part of the test and not decoration.
    """

    def setUp(self):
        self.r = Repo(self)

    def test_the_commit_this_run_published_is_selected(self):
        base = self.r.commit("base")
        self.r.write("teatteri/a/index.html")
        want = self.r.commit(indexnow.BOT_SUBJECT, author=indexnow.BOT_NAME, when=2000)
        self.assertEqual(self.r.pick(base, 1000), want)

    def test_an_older_bot_commit_inside_the_range_is_not_resubmitted(self):
        """The queued-run case. The range spans a previous run's data commit; only the
        run's own commit should be announced, and here it produced none."""
        base = self.r.commit("base")
        self.r.write("teatteri/a/index.html")
        self.r.commit(indexnow.BOT_SUBJECT, author=indexnow.BOT_NAME, when=1000)
        self.r.write("scripts/x.py", "x = 1")
        self.r.commit("some human commit", when=3000)
        # this run started after the old bot commit and published nothing of its own
        self.assertIsNone(self.r.pick(base, 2000))

    def test_a_run_that_published_nothing_selects_nothing(self):
        base = self.r.commit("base")
        self.r.write("scripts/x.py", "x = 1")
        self.r.commit("human commit", when=3000)
        self.assertIsNone(self.r.pick(base, 1000))

    def test_a_commit_by_someone_else_is_not_taken_for_the_bot(self):
        base = self.r.commit("base")
        self.r.write("teatteri/a/index.html")
        self.r.commit(indexnow.BOT_SUBJECT, author="someone-else", when=2000)
        self.assertIsNone(self.r.pick(base, 1000))

    def test_a_later_runs_commit_is_not_attributed_to_this_one(self):
        """Run A publishes A and finishes; run B publishes B; only then does A's
        notification job get CPU. Both commits are newer than A's start, so a lower
        bound alone hands A the commit B published -- A never announced, B announced
        twice. A's own window is what separates them."""
        base = self.r.commit("base")
        self.r.write("teatteri/a/index.html")
        a_commit = self.r.commit(indexnow.BOT_SUBJECT, author=indexnow.BOT_NAME, when=2000)
        self.r.write("teatteri/b/index.html")
        self.r.commit(indexnow.BOT_SUBJECT, author=indexnow.BOT_NAME, when=5000)
        # run A: started 1000, finished 3000
        self.assertEqual(self.r.pick(base, 1000, 3000), a_commit)

    def test_a_run_that_published_nothing_is_not_credited_with_a_later_commit(self):
        """The same race, the other way round: A published nothing, B published B. A
        must select nothing rather than claim B's work."""
        base = self.r.commit("base")
        self.r.write("teatteri/b/index.html")
        self.r.commit(indexnow.BOT_SUBJECT, author=indexnow.BOT_NAME, when=5000)
        self.assertIsNone(self.r.pick(base, 1000, 3000))

    def test_a_commit_before_the_run_started_is_not_taken(self):
        base = self.r.commit("base")
        self.r.write("teatteri/a/index.html")
        self.r.commit(indexnow.BOT_SUBJECT, author=indexnow.BOT_NAME, when=500)
        self.assertIsNone(self.r.pick(base, 1000, 3000))

    def test_the_newest_matching_commit_inside_the_window_wins(self):
        base = self.r.commit("base")
        self.r.write("teatteri/a/index.html")
        self.r.commit(indexnow.BOT_SUBJECT, author=indexnow.BOT_NAME, when=2000)
        self.r.write("teatteri/b/index.html")
        newest = self.r.commit(indexnow.BOT_SUBJECT, author=indexnow.BOT_NAME, when=4000)
        self.assertEqual(self.r.pick(base, 1000, 5000), newest)


class EventRoutingTest(unittest.TestCase):
    """Which door the range comes through. Without this the workflow_run branch can be
    deleted and every other test still passes -- which is exactly the hole that made the
    feature silent for the only commits that matter."""

    def event(self, payload):
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(payload, f); f.close()
        import os
        old = os.environ.get("GITHUB_EVENT_PATH")
        os.environ["GITHUB_EVENT_PATH"] = f.name
        self.addCleanup(lambda: os.environ.__setitem__("GITHUB_EVENT_PATH", old)
                        if old else os.environ.pop("GITHUB_EVENT_PATH", None))
        self.addCleanup(lambda: pathlib.Path(f.name).unlink(missing_ok=True))

    def pick(self, result):
        real = indexnow.bot_commit_for_run
        indexnow.bot_commit_for_run = lambda head, started, ended, upper="HEAD": result
        self.addCleanup(lambda: setattr(indexnow, "bot_commit_for_run", real))

    def test_a_workflow_run_event_uses_the_bot_commit_it_published(self):
        self.event({"workflow_run": {"head_sha": "aaa", "conclusion": "success",
                                     "run_started_at": "2026-08-31T00:00:00Z",
                                     "updated_at": "2026-08-31T00:09:00Z"}})
        self.pick("deadbeef")
        self.assertEqual(indexnow.event_range(), ("deadbeef^", "deadbeef"))

    def test_a_failed_run_that_published_pages_is_still_announced(self):
        """The fetch workflow commits and pushes before its provider-failure gate, so a
        run can publish live pages and finish red. Those URLs need announcing exactly as
        much as a green run's, so conclusion is never consulted."""
        self.event({"workflow_run": {"head_sha": "aaa", "conclusion": "failure",
                                     "run_started_at": "2026-08-31T00:00:00Z",
                                     "updated_at": "2026-08-31T00:09:00Z"}})
        self.pick("deadbeef")
        self.assertEqual(indexnow.event_range(), ("deadbeef^", "deadbeef"))

    def test_the_run_window_is_passed_to_the_selector(self):
        seen = {}
        real = indexnow.bot_commit_for_run
        indexnow.bot_commit_for_run = lambda h, s, e, upper="HEAD": seen.update(
            start=s, end=e) or "abc"
        self.addCleanup(lambda: setattr(indexnow, "bot_commit_for_run", real))
        self.event({"workflow_run": {"head_sha": "aaa",
                                     "run_started_at": "2026-08-31T00:00:00Z",
                                     "updated_at": "2026-08-31T00:09:00Z"}})
        indexnow.event_range()
        self.assertEqual(seen["end"] - seen["start"], 540, "nine minutes")

    def test_a_workflow_run_that_published_nothing_yields_no_range(self):
        self.event({"workflow_run": {"head_sha": "aaa", "conclusion": "success",
                                     "run_started_at": "2026-08-31T00:00:00Z",
                                     "updated_at": "2026-08-31T00:09:00Z"}})
        self.pick(None)
        self.assertEqual(indexnow.event_range(), (None, None))

    def test_a_push_event_still_uses_the_push_range(self):
        self.event({"before": "aaa111", "after": "bbb222"})
        self.assertEqual(indexnow.event_range(), ("aaa111", "bbb222"))

    def test_main_exits_zero_when_the_run_published_nothing(self):
        self.event({"workflow_run": {"head_sha": "aaa", "conclusion": "success",
                                     "run_started_at": "2026-08-31T00:00:00Z",
                                     "updated_at": "2026-08-31T00:09:00Z"}})
        self.pick(None)
        real = indexnow.submit
        indexnow.submit = lambda *a, **k: self.fail("must not submit without a commit")
        self.addCleanup(lambda: setattr(indexnow, "submit", real))
        self.assertEqual(indexnow.main([]), 0)


class BatchingTest(unittest.TestCase):
    """The protocol caps a POST at 10,000 URLs. This site is far below that, so the
    batching is here to make the limit explicit rather than to be exercised -- a silent
    422 on the day someone regenerates everything is a worse way to find out."""

    def run_main(self, n_urls):
        sent = []
        real_submit, real_changed = indexnow.submit, indexnow.changed_urls
        indexnow.changed_urls = lambda b, a: [f"https://leffavuoro.fi/teatteri/{i}/"
                                              for i in range(n_urls)]
        indexnow.submit = lambda body, **kw: (sent.append(len(body["urlList"])), (200, "ok"))[1]
        self.addCleanup(lambda: setattr(indexnow, "submit", real_submit))
        self.addCleanup(lambda: setattr(indexnow, "changed_urls", real_changed))
        code = indexnow.main(["--after", "HEAD"])
        return code, sent

    def test_a_small_list_is_one_post(self):
        code, sent = self.run_main(5)
        self.assertEqual((code, sent), (0, [5]))

    def test_an_oversized_list_is_split_at_the_ceiling(self):
        code, sent = self.run_main(indexnow.MAX_URLS_PER_POST + 7)
        self.assertEqual(code, 0)
        self.assertEqual(sent, [indexnow.MAX_URLS_PER_POST, 7])
        self.assertTrue(all(n <= indexnow.MAX_URLS_PER_POST for n in sent))


class PushRangeTest(unittest.TestCase):
    """A push is not one commit."""

    def event(self, payload):
        import os
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(payload, f); f.close()
        old = os.environ.get("GITHUB_EVENT_PATH")
        os.environ["GITHUB_EVENT_PATH"] = f.name
        self.addCleanup(lambda: os.environ.__setitem__("GITHUB_EVENT_PATH", old)
                        if old else os.environ.pop("GITHUB_EVENT_PATH", None))
        self.addCleanup(lambda: pathlib.Path(f.name).unlink(missing_ok=True))

    def test_the_range_comes_from_the_push_event(self):
        self.event({"before": "aaa111", "after": "bbb222"})
        self.assertEqual(indexnow.push_range(), ("aaa111", "bbb222"))

    def test_an_all_zero_before_falls_back_to_the_tip_parent(self):
        """Branch creation. Diffing the empty tree would announce every page on the
        site; the tip's parent announces what the push did."""
        self.event({"before": "0" * 40, "after": "HEAD"})
        before, after = indexnow.push_range()
        self.assertEqual((before, after), ("HEAD^", "HEAD"))

    def test_without_an_event_it_falls_back_to_the_tip_parent(self):
        import os
        os.environ.pop("GITHUB_EVENT_PATH", None)
        self.assertEqual(indexnow.push_range(), ("HEAD^", "HEAD"))


class ResponseMatrixTest(unittest.TestCase):
    def run_submit(self, responses):
        """responses: list of (status, detail, retry_after) returned in order."""
        seq = list(responses)
        calls = {"n": 0, "slept": []}
        real = indexnow._post
        def fake(body, timeout):
            calls["n"] += 1
            return seq[min(calls["n"] - 1, len(seq) - 1)]
        indexnow._post = fake
        self.addCleanup(lambda: setattr(indexnow, "_post", real))
        status, detail = indexnow.submit({}, sleep=calls["slept"].append)
        return status, calls

    def test_200_and_202_are_success_without_retry(self):
        for code in (200, 202):
            with self.subTest(code=code):
                status, calls = self.run_submit([(code, "ok", None)])
                self.assertEqual(status, code)
                self.assertEqual(calls["n"], 1)

    def test_hard_failures_are_not_retried(self):
        for code in (400, 403, 422):
            with self.subTest(code=code):
                status, calls = self.run_submit([(code, "bad", None)])
                self.assertEqual(status, code)
                self.assertEqual(calls["n"], 1, "retrying our own bug just repeats it")

    def test_429_is_retried_a_bounded_number_of_times(self):
        status, calls = self.run_submit([(429, "slow down", None)])
        self.assertEqual(status, 429)
        self.assertEqual(calls["n"], indexnow.RETRY_TRIES)
        self.assertEqual(len(calls["slept"]), indexnow.RETRY_TRIES - 1)

    def test_429_then_success_succeeds(self):
        status, calls = self.run_submit([(429, "slow", None), (200, "ok", None)])
        self.assertEqual(status, 200)
        self.assertEqual(calls["n"], 2)

    def test_a_dead_socket_is_retried_then_reported(self):
        status, calls = self.run_submit([(None, "timed out", None)])
        self.assertIsNone(status)
        self.assertEqual(calls["n"], indexnow.RETRY_TRIES)

    def test_a_server_error_is_retried(self):
        status, calls = self.run_submit([(503, "unavailable", None)])
        self.assertEqual(calls["n"], indexnow.RETRY_TRIES)

    def test_retry_after_is_honoured_but_capped(self):
        _, calls = self.run_submit([(429, "slow", 9999)])
        self.assertTrue(calls["slept"])
        self.assertTrue(all(w <= indexnow.RETRY_AFTER_MAX for w in calls["slept"]),
                        "a stranger must not be able to stall the job")

    def test_retry_after_is_used_when_reasonable(self):
        _, calls = self.run_submit([(429, "slow", 7)])
        self.assertEqual(calls["slept"][0], 7)


class ExitCodeTest(unittest.TestCase):
    def patch(self, result):
        real_submit, real_changed = indexnow.submit, indexnow.changed_urls
        indexnow.submit = lambda body, **kw: result
        indexnow.changed_urls = lambda before, after: ["https://leffavuoro.fi/teatteri/a/"]
        self.addCleanup(lambda: setattr(indexnow, "submit", real_submit))
        self.addCleanup(lambda: setattr(indexnow, "changed_urls", real_changed))

    def test_200_and_202_exit_zero(self):
        for code in (200, 202):
            with self.subTest(code=code):
                self.patch((code, "ok"))
                self.assertEqual(indexnow.main(["--after", "HEAD"]), 0)

    def test_persistent_failure_is_surfaced(self):
        """This workflow cannot block publication, so a submission that keeps failing
        should show as failing rather than stay green forever."""
        for result in ((400, "bad"), (403, "key"), (422, "host"), (429, "rate"),
                       (None, "timed out")):
            with self.subTest(result=result):
                self.patch(result)
                self.assertEqual(indexnow.main(["--after", "HEAD"]), 1)

    def test_nothing_changed_exits_zero_without_submitting(self):
        real_changed, real_submit = indexnow.changed_urls, indexnow.submit
        indexnow.changed_urls = lambda before, after: []
        indexnow.submit = lambda *a, **k: self.fail("must not submit an empty list")
        self.addCleanup(lambda: setattr(indexnow, "changed_urls", real_changed))
        self.addCleanup(lambda: setattr(indexnow, "submit", real_submit))
        self.assertEqual(indexnow.main(["--after", "HEAD"]), 0)


class KeyFileTest(unittest.TestCase):
    def test_the_repo_has_exactly_one_valid_key_file(self):
        key, name = indexnow.key_file()
        self.assertEqual(name, f"{key}.txt")
        self.assertEqual(len(key), 32)

    def test_it_is_reachable_by_robots(self):
        robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
        _, name = indexnow.key_file()
        for line in robots.splitlines():
            if line.lower().startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path and path != "/":
                    self.assertFalse(f"/{name}".startswith(path), f"blocked by {line!r}")

    def use(self, mapping):
        d = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        for name, body in mapping.items():
            (d / name).write_text(body, encoding="utf-8")
        real = indexnow.ROOT
        indexnow.ROOT = d
        self.addCleanup(lambda: setattr(indexnow, "ROOT", real))

    def test_contents_must_equal_the_filename(self):
        self.use({"a" * 32 + ".txt": "something-else"})
        with self.assertRaises(SystemExit):
            indexnow.key_file()

    def test_a_trailing_newline_is_tolerated(self):
        self.use({"b" * 32 + ".txt": "b" * 32 + "\n"})
        self.assertEqual(indexnow.key_file()[0], "b" * 32)

    def test_two_key_files_are_refused(self):
        self.use({"c" * 32 + ".txt": "c" * 32, "d" * 32 + ".txt": "d" * 32})
        with self.assertRaises(SystemExit):
            indexnow.key_file()

    def test_no_key_file_is_refused(self):
        self.use({})
        with self.assertRaises(SystemExit):
            indexnow.key_file()


class PayloadTest(unittest.TestCase):
    def test_it_matches_the_documented_shape(self):
        body = indexnow.payload(["https://leffavuoro.fi/x/"], "abc", "abc.txt")
        self.assertEqual(sorted(body), ["host", "key", "keyLocation", "urlList"])
        self.assertEqual(body["keyLocation"], "https://leffavuoro.fi/abc.txt")
        json.dumps(body)

    def test_the_host_matches_the_cname(self):
        body = indexnow.payload([], "k", "k.txt")
        self.assertEqual(body["host"], (ROOT / "CNAME").read_text(encoding="utf-8").strip())
        self.assertNotIn("/", body["host"])


if __name__ == "__main__":
    unittest.main()
