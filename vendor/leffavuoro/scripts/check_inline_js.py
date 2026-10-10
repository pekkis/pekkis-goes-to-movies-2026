#!/usr/bin/env python3
"""Syntax-check the client's JavaScript. -> 0 clean, 1 something is broken.

    python3 scripts/check_inline_js.py              # index.html, status/index.html,
                                                   # tietosuoja/index.html, sw.js
    python3 scripts/check_inline_js.py FILE [FILE]  # any .html or .js

There is no build step, so nothing parses `index.html`'s script block before a browser
does; a syntax error ships and the service worker keeps serving the last good copy to
whoever pushed it. Line numbers are reported against the HTML file, not the extracted
fragment.

A `<script>` with a `src` is skipped. A `<script type="application/ld+json">` is parsed
as JSON, because a broken one silently removes the page from rich results. An HTML file
with no inline script is a failure: each file this checks has exactly one, so zero means
the tag shape changed.

`node --check` parses; it does not run. A regular expression literal with a broken
character class is valid syntax and throws only when the engine builds it, which is how
a status/index.html class written with literal control bytes passed here and died in the
browser. Anything that has to be constructed at runtime needs a test, not this.
"""
import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPT_RE = re.compile(r"<script([^>]*)>(.*?)</script>", re.S | re.I)
DEFAULT = ["index.html", "status/index.html", "tietosuoja/index.html", "sw.js",
           "pageview.js"]


def blocks(html):
    """-> [(kind, first_line, source)] for every inline <script> in `html`.

    `first_line` is 1-based and points at the line the block's content starts on, so a
    node error can be reported against the original file.
    """
    out = []
    for m in SCRIPT_RE.finditer(html):
        attrs, body = m.group(1), m.group(2)
        if re.search(r"\bsrc\s*=", attrs, re.I):
            continue
        kind = "json" if "ld+json" in attrs.lower() else "js"
        out.append((kind, html.count("\n", 0, m.start(2)) + 1, body))
    return out


def check_js(source, label, first_line=1):
    """node --check one fragment. -> [] or a list of complaints."""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as f:
        # node reports `file:line`, and the fragment starts partway down the HTML, so
        # push it down by the offset before handing it over. Blank lines cost nothing
        # and mean the number node prints is the number to open the editor at.
        f.write("\n" * (first_line - 1) + source)
        tmp = f.name
    try:
        r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
        if r.returncode == 0:
            return []
        return [ln.replace(tmp, label) for ln in r.stderr.strip().splitlines()[:6]]
    finally:
        pathlib.Path(tmp).unlink(missing_ok=True)


def check_file(path):
    """-> (checked_count, [complaints]) for one file."""
    if not path.exists():
        return 0, [f"{path}: no such file"]
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".js":
        return 1, check_js(text, str(path))

    found = blocks(text)
    if not found:
        return 0, [f"{path}: no inline <script> found -- the tag shape changed, and "
                   f"this check has been passing on nothing"]
    bad, n = [], 0
    for kind, line, body in found:
        n += 1
        if kind == "json":
            try:
                json.loads(body)
            except Exception as e:
                bad.append(f"{path}:{line}: invalid JSON-LD: {e}")
        else:
            bad += check_js(body, str(path), line)
    return n, bad


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="*", default=DEFAULT,
                    help="files to check (default: index.html sw.js)")
    args = ap.parse_args(argv)

    if shutil.which("node") is None:
        # Not a skip. The whole point of this file is that a workflow can enforce the
        # check, and a checker that passes when its checker is missing enforces nothing.
        print("[js] node is not installed -- cannot check anything", file=sys.stderr)
        return 1

    total, bad = 0, []
    for name in (args.files or DEFAULT):
        n, complaints = check_file(pathlib.Path(name))
        total += n
        bad += complaints

    for line in bad:
        print(f"[js] {line}", file=sys.stderr)
    print(f"[js] {total} script(s) checked, {len(bad)} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
