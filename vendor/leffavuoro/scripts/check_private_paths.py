"""Refuse files that would publish a home directory path, and any log at the repo root.

On 2026-08-31 a local run's traceback put an absolute home path, which carries the
account name, into a committed root run.log (8d096921c). The local wrapper redacts its
logs and runs this on the staged files before it commits; the suite runs it on every
tracked file. A hit is reported by file and line, never by the text it found.

    python3 scripts/check_private_paths.py                # every tracked file
    python3 scripts/check_private_paths.py --staged       # what `git commit` would record
    python3 scripts/check_private_paths.py --redact logs  # home directory -> ~, in place
"""
import os
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]

# A home directory at the start of a path token. The look-behind keeps a URL path such as
# https://example.fi/home/x out, and a hosted runner's home is no one's.
HOME_RE = re.compile(r"(?<![\w.-])(?:/Users/|/home/|[A-Za-z]:\\Users\\)(?!runner[/\\])"
                     r"[A-Za-z0-9._-]+")


def home():
    h = os.path.expanduser("~")
    return h if len(h) > 1 else ""


def findings(path, data):
    """-> [(path, line, why)] for one file's bytes."""
    if "/" not in path and path.endswith(".log"):
        return [(path, 0, "a log at the repo root; logs belong in logs/")]
    if b"\0" in data[:8192]:
        return []
    text = data.decode("utf-8", "replace")
    return [(path, n, "a home directory path")
            for n, line in enumerate(text.splitlines(), 1) if HOME_RE.search(line)]


def _git(*args, cwd=REPO):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True).stdout


def check_staged(cwd=REPO):
    names = [n for n in _git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z",
                             cwd=cwd).decode().split("\0") if n]
    return [f for n in names for f in findings(n, _git("show", f":{n}", cwd=cwd))]


def check_tracked(cwd=REPO):
    names = [n for n in _git("ls-files", "-z", cwd=cwd).decode().split("\0") if n]
    out = []
    for n in names:
        p = pathlib.Path(cwd) / n
        if p.is_file():
            out += findings(n, p.read_bytes())
    return out


def redact(dirs, own_home=None):
    """Replace the home directory with ~ in every text file under `dirs`. -> files changed."""
    own = home() if own_home is None else own_home
    changed = 0
    if not own:
        return 0
    for d in dirs:
        for p in sorted(pathlib.Path(d).rglob("*")):
            if not p.is_file():
                continue
            data = p.read_bytes()
            if b"\0" in data[:8192] or own.encode() not in data:
                continue
            p.write_bytes(data.replace(own.encode(), b"~"))
            changed += 1
    return changed


def main(argv):
    if argv[:1] == ["--redact"]:
        print(f"[private-paths] redacted the home directory in {redact(argv[1:])} file(s)")
        return 0
    hits = check_staged() if argv[:1] == ["--staged"] else check_tracked()
    for path, line, why in hits:
        print(f"[private-paths] {path}:{line}: {why}")
    if hits:
        print(f"[private-paths] {len(hits)} finding(s); nothing here may be published")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
