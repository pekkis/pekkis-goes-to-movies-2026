#!/usr/bin/env python3
"""Run the unit suite one process per test file, several files at once. Stdlib only.

    python3 scripts/run_tests.py                     # every tests/test_*.py, one per CPU
    python3 scripts/run_tests.py --jobs 4 --fail-on-skip
    python3 scripts/run_tests.py test_tmdb_matching.py test_synopsis_lang.py

Each file runs as `python -m unittest discover -s tests -p <file>`, the invocation the
mutation checker and a targeted run already use, so a file sees exactly what it sees on its
own. One process per file is also the isolation: nothing a test sets on a module leaks into
another file's tests. The 2026-09-25 audit measured 86 s as one process on 3,346 tests, and
24 s over 4 workers and 13 s over 14 with per-file processes, 0 failures and the tree clean
after each; this runner took 25.7 s over 4 workers on 3,438 tests the same day, 0 skipped.
The bound is the largest file, about 10 s.

The output is every file's own output under a header, then the totals in unittest's own
words (`Ran N tests`, `OK` or `FAILED (failures=.., errors=.., skipped=..)`), so the
lines the Checks workflow greps for mean what they meant. `--fail-on-skip` exits 1 on any
skipped test: every dependency is installed on the runner, so a skip there means one went
missing. Locally the five Pillow tests skip on the system interpreter and pass the plain
run, as before.
"""
import argparse
import concurrent.futures
import os
import pathlib
import re
import subprocess
import sys
import time

TESTS = pathlib.Path(__file__).resolve().parents[1] / "tests"

RAN_RE = re.compile(r"^Ran (\d+) tests? in ", re.M)
TAIL_RE = re.compile(r"^(OK|FAILED)(?: \(([^)]*)\))?\s*$", re.M)


def counts(output):
    """One file's totals from its unittest output. -> {ran, failures, errors, skipped}."""
    out = {"ran": 0, "failures": 0, "errors": 0, "skipped": 0,
           "expected failures": 0, "unexpected successes": 0}
    m = RAN_RE.findall(output)
    if m:
        out["ran"] = int(m[-1])
    tails = TAIL_RE.findall(output)
    if tails:
        for part in (tails[-1][1] or "").split(","):
            key, _, n = part.strip().partition("=")
            if key in out and n.isdigit():
                out[key] = int(n)
    return out


def run_file(name, root, python):
    """-> (name, return code, output, seconds)."""
    t0 = time.monotonic()
    r = subprocess.run([python, "-m", "unittest", "discover", "-s", str(root), "-p", name],
                       capture_output=True, text=True, cwd=root.parent)
    return name, r.returncode, r.stdout + r.stderr, time.monotonic() - t0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="*", help="test file names; default every test_*.py")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1,
                    help="files run at once (default: one per CPU)")
    ap.add_argument("--fail-on-skip", action="store_true",
                    help="exit 1 if any test was skipped")
    ap.add_argument("--dir", default=str(TESTS), help="the test directory")
    args = ap.parse_args(argv)

    root = pathlib.Path(args.dir).resolve()
    names = args.files or [p.name for p in root.glob("test_*.py")]
    # Largest first, a stand-in for longest first: the suite's wall clock is bounded by
    # its slowest file, and starting that one last would leave the other workers idle.
    names.sort(key=lambda n: (-(root / n).stat().st_size, n))
    t0 = time.monotonic()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for got in pool.map(lambda n: run_file(n, root, sys.executable), names):
            results.append(got)
    results.sort(key=lambda r: r[0])

    total = dict.fromkeys(counts("").keys(), 0)
    broken = []
    for name, code, output, secs in results:
        c = counts(output)
        for k in total:
            total[k] += c[k]
        # A file that exits non-zero, or runs nothing at all, is a failure of the suite:
        # a module that will not import reports "NO TESTS RAN" under some Pythons.
        if code != 0 or c["ran"] == 0:
            broken.append(name)
        print(f"==== {name} ({secs:.1f}s, exit {code})")
        print(output.rstrip())
    elapsed = time.monotonic() - t0

    print("-" * 70)
    print(f"Ran {total['ran']} tests in {elapsed:.3f}s ({len(results)} files, "
          f"{args.jobs} at once)")
    notes = [f"{k}={total[k]}" for k in ("failures", "errors", "skipped",
                                         "expected failures", "unexpected successes")
             if total[k]]
    if broken:
        print(f"FAILED ({', '.join(notes) or 'a file failed'})")
        print("files that failed: " + ", ".join(broken))
        return 1
    print("OK" + (f" ({', '.join(notes)})" if notes else ""))
    if args.fail_on_skip and total["skipped"]:
        print(f"{total['skipped']} test(s) skipped, and --fail-on-skip treats a skip as a "
              f"failure")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
