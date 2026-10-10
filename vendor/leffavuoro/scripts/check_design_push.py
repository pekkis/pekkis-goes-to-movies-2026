#!/usr/bin/env python3
"""A push that touches DESIGN.md or tests/test_design_contract.py carries an IDEAS.md change.

    python3 scripts/check_design_push.py BEFORE AFTER [--base origin/main] [--repo DIR]

Run by ci.yml with `github.event.before` and `github.sha`. The range is the push's own,
never the tip's parent alone: a push is not one commit, and a design change in an
earlier commit of the same push would slip past `HEAD^..HEAD`.

`before` is not always usable. After a force-push it names the tip the push replaced: a
full clone does not carry it and `git diff` fails with exit 128 (2026-09-13, run
34773073208), and when it *is* readable -- GitHub serves a rewritten SHA for a while --
`before..after` is the difference between two branches rather than the push, so it reports
the files of the commits the push dropped. A branch created by the push reports an
all-zero `before`. The range is recovered in this order:

1. `before` itself, fetched by SHA from origin when the checkout lacks it, and used only
   when it is an ancestor of `after`: that range is exactly the push;
2. otherwise the merge base of the base branch and `after`, which is every commit the
   push put on the branch that main does not have: a superset of the push, never less;
3. otherwise the three states that used to share one error line are told apart, because
   the annotation on a red run is all there is to read (2026-09-15):
   * the base ref does not resolve here, so there is no base branch to recover against;
   * the base branch already holds `after`. For a **created ref** that is benign and
     exits 0: a new ref at a commit the base already has adds no commit anywhere, its
     range against the base is empty, and the push that put the commit on the base
     carried the gate with a readable `before`. This is the branch-then-fast-forward
     delivery routine, where the branch job reads `origin/main` a moment after main has
     advanced to the same commit. For an unreachable `before` it stays exit 2: a push to
     the base branch itself has no range to recover and guessing one would hide a
     contract change;
   * no usable merge base at all, which is exit 2 for the same reason.

The entry has to be in the same commit as the contract change, not merely somewhere in
the range. The merge-base fallback is a superset of the push, and read as one range an
`IDEAS.md` edit in an unrelated earlier commit answers for a later contract-only commit.
Per commit it cannot, and CLAUDE.md asks for the same commit anyway. The net diff still
gates: a push that changes a contract file and takes it back has nothing to explain.

Exit 0 when the contract is untouched, when the IDEAS entry is present, or when a created
ref points at a commit the base branch already holds; 1 on a violation; 2 when the range
cannot be determined.
"""
import argparse
import pathlib
import subprocess
import sys

CONTRACT = ("DESIGN.md", "tests/test_design_contract.py")
ENTRY = "IDEAS.md"
ROOT = pathlib.Path(__file__).resolve().parent.parent


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)


def has_commit(repo, rev):
    return _git(repo, "cat-file", "-e", f"{rev}^{{commit}}").returncode == 0


def is_ancestor(repo, rev, tip):
    return _git(repo, "merge-base", "--is-ancestor", rev, tip).returncode == 0


def push_base(before, after, base_ref, repo, log=print, tag="design"):
    """The commit to diff `after` against -> sha, or None when no range can be found.

    `tag` only names the gate in the log lines. `scripts/check_cache_bump.py` runs the
    same range recovery against the same push and would otherwise print `[design]`.
    """
    if before and set(before) != {"0"}:
        readable = has_commit(repo, before)
        if not readable and _git(repo, "remote", "get-url", "origin").returncode == 0:
            _git(repo, "fetch", "--quiet", "origin", before)
            readable = has_commit(repo, before)
            if readable:
                log(f"[{tag}] before {before[:10]} fetched by sha")
        if readable:
            if is_ancestor(repo, before, after):
                return before
            # Readable but replaced: the range would carry whatever the dropped commits
            # touched, in either direction. It reports a contract change the push does not
            # make, and it accepts an IDEAS entry that only the dropped tip had.
            log(f"[{tag}] before {before[:10]} is not an ancestor of {after[:10]} "
                f"(force-pushed branch)")
        else:
            log(f"[{tag}] before {before[:10]} is not reachable (rewritten branch)")
    else:
        log(f"[{tag}] before is all zeros (created ref)")
    mb = _git(repo, "merge-base", base_ref, after)
    if mb.returncode == 0:
        base = mb.stdout.strip()
        if base and not _git(repo, "rev-parse", "--verify", "--quiet",
                             f"{base}^{{commit}}").returncode and base != _resolve(repo, after):
            log(f"[{tag}] comparing against merge base {base[:10]} with {base_ref}")
            return base
    return None


def resolve_base(before, after, base_ref, repo, tag="design"):
    """`push_base`, plus what the caller returns when it finds nothing -> (base, code).

    Exactly one of the pair is None. A base means the range was recovered; a code is the
    exit status to return, 0 for the benign created ref and 2 for a range that cannot be
    determined. The three states that produce "no base" are told apart here, once, rather
    than in each gate: the annotation on a red run is all there is to read, and a second
    gate restating this is a second place for the three to collapse back into one line.
    """
    base = push_base(before, after, base_ref, repo, tag=tag)
    if base is not None:
        return base, None
    created = not before or set(before) == {"0"}
    contains = base_contains(repo, base_ref, after)
    if contains is None:
        print(f"::error::cannot determine the push range for {after[:10]}: "
              f"{base_ref} does not resolve in this checkout, so there is no base "
              f"branch to recover a range against")
        return None, 2
    if contains:
        if created:
            # A created ref pointing at a commit the base branch already holds adds no
            # commit anywhere, so its range against the base is empty and there is
            # nothing for it to explain. The commit's own arrival on the base branch is
            # what carries the gate, and that push had a readable `before`.
            print(f"{base_ref} already holds {after[:10]}: a created ref at a "
                  f"commit it already has adds nothing to explain")
            return None, 0
        print(f"::error::cannot determine the push range for {after[:10]}: "
              f"before {before[:10]} is unreachable and {base_ref} already holds "
              f"{after[:10]}, so the merge base is the pushed commit itself")
        return None, 2
    print(f"::error::cannot determine the push range for {after[:10]}: "
          f"before {before[:10]} is unreachable and {base_ref} shares no usable "
          f"merge base with it")
    return None, 2


def _resolve(repo, rev):
    r = _git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")
    return r.stdout.strip() if r.returncode == 0 else None


def base_contains(repo, base_ref, rev):
    """Does `base_ref` already hold `rev`? -> True / False, or None when `base_ref` does
    not resolve here, which is a different answer from "no" and used to read as one.

    `push_base` returning None says only that no range was found. Three different states
    produce that, and until 2026-09-15 they shared one error line, so the annotation on a
    red run could not say which had happened. This is what separates them.
    """
    if _resolve(repo, base_ref) is None:
        return None
    return is_ancestor(repo, rev, base_ref)


def entryless_commits(base, after, repo):
    """Commits in base..after that change a contract file and not IDEAS.md. -> [sha]"""
    with_entry = set(_log(base, after, repo, (ENTRY,)))
    return [c for c in _log(base, after, repo, CONTRACT) if c not in with_entry]


def _log(base, after, repo, paths):
    r = _git(repo, "log", "--format=%H", f"{base}..{after}", "--", *paths)
    if r.returncode:
        raise RuntimeError(r.stderr.strip())
    return [line for line in r.stdout.splitlines() if line]


def changed_files(base, after, repo):
    r = _git(repo, "diff", "--name-only", base, after)
    if r.returncode:
        raise RuntimeError(r.stderr.strip())
    return [line for line in r.stdout.splitlines() if line]


def verdict(files, entryless=()):
    """(ok, message) for a push: the files it changed, and the commits in it that changed
    a contract file without touching IDEAS.md."""
    touched = sorted(f for f in files if f in CONTRACT)
    if not touched:
        return True, "design contract untouched"
    if entryless:
        return False, (f"{' and '.join(touched)} changed without an IDEAS.md entry in the "
                       f"same commit ({', '.join(c[:10] for c in entryless)})")
    return True, "design contract change carries an IDEAS entry"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--base", default="origin/main", help="the base branch ref (default origin/main)")
    ap.add_argument("--repo", default=str(ROOT), help="the repository to read (default: this one)")
    args = ap.parse_args(argv)
    repo = pathlib.Path(args.repo)
    base, code = resolve_base(args.before, args.after, args.base, repo)
    if base is None:
        return code
    ok, message = verdict(changed_files(base, args.after, repo),
                          entryless_commits(base, args.after, repo))
    if not ok:
        print(f"::error::{message}")
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
