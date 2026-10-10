"""scripts/run_tests.py: one process per test file, and a verdict in unittest's own words.

The Checks workflow greps the suite's log for `FAIL:`/`ERROR:` lines, `Ran N tests`,
`OK`/`FAILED` and `skipped=`, and fails on a skip. The parallel runner has to keep every
one of those meaning what it meant. Driven against a temporary directory of small files.
"""
import pathlib
import subprocess
import sys
import tempfile
import unittest

import _ctx                                                # noqa: F401

RUNNER = _ctx.ROOT / "scripts" / "run_tests.py"
PASS = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n    def test_b(self): pass\n"
SKIP = ("import unittest\nclass T(unittest.TestCase):\n"
        "    @unittest.skip('no Pillow')\n    def test_a(self): pass\n")
FAIL = "import unittest\nclass T(unittest.TestCase):\n    def test_red(self): self.fail('red')\n"
BROKEN = "import no_such_module_anywhere\n"


class RunTestsTest(unittest.TestCase):

    def run_on(self, files, *flags):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = pathlib.Path(tmp.name) / "tests"
        d.mkdir()
        for name, body in files.items():
            (d / name).write_text(body, encoding="utf-8")
        r = subprocess.run([sys.executable, str(RUNNER), "--dir", str(d), "--jobs", "3", *flags],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_a_green_suite_is_ok_with_every_test_counted(self):
        code, out = self.run_on({"test_a.py": PASS, "test_b.py": PASS})
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"(?m)^Ran 4 tests in ")
        self.assertRegex(out, r"(?m)^OK$")

    def test_a_failing_file_fails_the_suite_and_keeps_its_fail_line(self):
        code, out = self.run_on({"test_a.py": PASS, "test_red.py": FAIL})
        self.assertEqual(code, 1, out)
        self.assertRegex(out, r"(?m)^FAIL: test_red ")
        self.assertRegex(out, r"(?m)^FAILED \(failures=1\)$")

    def test_a_file_that_will_not_import_fails_the_suite(self):
        code, out = self.run_on({"test_a.py": PASS, "test_broken.py": BROKEN})
        self.assertEqual(code, 1, out)
        self.assertIn("test_broken.py", out.splitlines()[-1])

    def test_a_skip_is_reported_and_fails_only_with_the_flag(self):
        files = {"test_a.py": PASS, "test_skip.py": SKIP}
        code, out = self.run_on(files)
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"(?m)^OK \(skipped=1\)$")
        code, out = self.run_on(files, "--fail-on-skip")
        self.assertEqual(code, 1, out)
        self.assertIn("skipped=", out)


if __name__ == "__main__":
    unittest.main()
