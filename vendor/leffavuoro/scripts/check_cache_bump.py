#!/usr/bin/env python3
"""A commit that touches index.html bumps CACHE in sw.js.

    python3 scripts/check_cache_bump.py BEFORE AFTER [--base origin/main] [--repo DIR]

The rule is in CLAUDE.md and was prose alone until 2026-09-19. Two of the 120 most recent
commits touching `index.html` did not carry the bump: `f360a09c0`, where the generated
`PROV_FALLBACK` block moved inside a provider commit, and `3a811db46`, a hand-written
picker change. Neither is rewritten; this gate is for the next one.

What it costs to miss: `sw.js` serves the page network-first, so a visitor online gets the
new `index.html` either way. The old copy stays in the named cache as the offline fallback
until `activate` drops every cache that is not the current `CACHE`, and with the name
unchanged nothing is dropped. The stale page then answers offline, and it reads the same
`data/*.json` the current page does.

The range is the push's own and is recovered by `check_design_push.resolve_base`, which
is where the three unusable-`before` states are told apart. This gate differs only in
what it asks of each commit in that range.

Per commit rather than per push, for the reason the design gate gives: read as one range,
a bump in an unrelated earlier commit of the same push would answer for a later
`index.html` change that shipped without one. The net diff still gates the push as a
whole, so a push that changes `index.html` and takes it back has nothing to bump for.

The constant is read out of `sw.js` at the commit and at its first parent, rather than
asking whether the diff touched `sw.js`: a commit can edit the service worker and leave
the name alone, which is the failure this exists to catch. A commit with no parent, or
one that adds `sw.js`, reads as a bump.

Exit 0 when no commit in the range touches index.html, when every one that does carries
its bump, or when a created ref points at a commit the base branch already holds; 1 on a
violation; 2 when the range cannot be determined.
"""
import argparse
import pathlib
import re
import sys

import check_design_push as cdp

PAGE = "index.html"
WORKER = "sw.js"
ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE_RE = re.compile(r"""^\s*const\s+CACHE\s*=\s*['"]([^'"]+)['"]""", re.M)


def cache_at(repo, rev):
    """The CACHE name in sw.js at `rev` -> str, or None when the file or the constant is
    not there. A missing file and a missing constant are the same answer on purpose: both
    mean "no name to compare", and both differ from any name."""
    r = cdp._git(repo, "show", f"{rev}:{WORKER}")
    if r.returncode:
        return None
    m = CACHE_RE.search(r.stdout)
    return m.group(1) if m else None


def bumpless_commits(base, after, repo):
    """Commits in base..after that touch index.html without changing CACHE. -> [sha]"""
    out = []
    for sha in cdp._log(base, after, repo, (PAGE,)):
        before = cache_at(repo, f"{sha}^")
        now = cache_at(repo, sha)
        if now is None or now == before:
            out.append(sha)
    return out


def verdict(files, bumpless=()):
    """(ok, message) for a push: the files it changed, and the commits in it that touched
    index.html without bumping CACHE."""
    if PAGE not in files:
        return True, f"{PAGE} untouched"
    if bumpless:
        return False, (f"{PAGE} changed without a CACHE bump in {WORKER} in the same "
                       f"commit ({', '.join(c[:10] for c in bumpless)})")
    return True, f"the {PAGE} change carries its CACHE bump"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--base", default="origin/main", help="the base branch ref (default origin/main)")
    ap.add_argument("--repo", default=str(ROOT), help="the repository to read (default: this one)")
    args = ap.parse_args(argv)
    repo = pathlib.Path(args.repo)
    base, code = cdp.resolve_base(args.before, args.after, args.base, repo, tag="cache")
    if base is None:
        return code
    ok, message = verdict(cdp.changed_files(base, args.after, repo),
                          bumpless_commits(base, args.after, repo))
    if not ok:
        print(f"::error::{message}")
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
