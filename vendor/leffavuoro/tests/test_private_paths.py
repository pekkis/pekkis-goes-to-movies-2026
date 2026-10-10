"""No tracked file names a home directory, and no log sits at the repo root.

A local traceback published a home path, which carries the account name, in a root
run.log on 2026-08-31 (8d096921c). The fixtures are built from parts: written out whole,
this file would be a tracked file carrying the very string it checks for.
"""
import pathlib
import subprocess
import tempfile
import unittest

import _ctx                                                # noqa: F401
import check_private_paths as cpp

MAC = "/" + "Users" + "/someone"
LINUX = "/" + "home" + "/someone"
WIN = "C:" + "\\" + "Users" + "\\someone"
RUNNER = "/" + "home" + "/runner"
TRACE = f'  File "{MAC}/kino-auth/repo/scripts/fetch_data.py", line 588'.encode()


class FindingsTest(unittest.TestCase):
    def test_a_traceback_path_is_found(self):
        self.assertEqual(cpp.findings("logs/run.log", b"ok\n" + TRACE),
                         [("logs/run.log", 2, "a home directory path")])

    def test_linux_and_windows_homes_are_found(self):
        for home in (LINUX, WIN):
            with self.subTest(home=home):
                self.assertEqual(len(cpp.findings("x.txt", f"at {home}\\x".encode())), 1)

    def test_a_runner_home_and_a_url_path_are_not(self):
        text = f"{RUNNER}/work/kino/kino/run.py\nhttps://example.fi/" + "home" + "/news/"
        self.assertEqual(cpp.findings("logs/run-cloud.log", text.encode()), [])

    def test_a_binary_file_is_not_read_as_text(self):
        self.assertEqual(cpp.findings("data/posters/a.jpg", b"\xff\xd8\0" + TRACE), [])

    def test_a_root_log_is_refused_and_a_logs_one_is_not(self):
        self.assertEqual(cpp.findings("run.log", b"exit=0")[0][0], "run.log")
        self.assertEqual(cpp.findings("logs/run.log", b"exit=0"), [])

    def test_redact_replaces_the_home_directory(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "run.log"
            p.write_bytes(TRACE)
            self.assertEqual(cpp.redact([d], own_home=MAC), 1)
            self.assertNotIn(MAC.encode(), p.read_bytes())
            self.assertIn(b'"~/kino-auth/repo/', p.read_bytes())


class StagedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = pathlib.Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

    def stage(self, name, data):
        (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / name).write_bytes(data)
        subprocess.run(["git", "add", "-f", name], cwd=self.repo, check=True)

    def test_what_is_staged_is_what_is_read(self):
        self.stage("logs/run.log", TRACE)
        (self.repo / "logs/run.log").write_bytes(b"exit=0")      # the working copy is clean
        self.stage("data/a.json", b"{}")
        self.assertEqual(cpp.check_staged(cwd=self.repo),
                         [("logs/run.log", 1, "a home directory path")])

    def test_a_clean_stage_passes(self):
        self.stage("logs/run.log", b"exit=0")
        self.stage("data/a.json", b"{}")
        self.assertEqual(cpp.check_staged(cwd=self.repo), [])


class RepoTest(unittest.TestCase):
    def test_no_tracked_file_names_a_home_directory(self):
        self.assertEqual(cpp.check_tracked(), [])


if __name__ == "__main__":
    unittest.main()
