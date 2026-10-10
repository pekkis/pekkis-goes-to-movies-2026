#!/usr/bin/env python3
"""Tell IndexNow which generated pages a push added, changed, deleted or moved.

    python3 scripts/indexnow.py            # range from the push event, else HEAD^..HEAD
    python3 scripts/indexnow.py --dry-run  # print what would be sent, send nothing
    python3 scripts/indexnow.py --before X --after Y

IndexNow reaches Bing, Yandex, Seznam, Naver and Yep; Google does not use it. Showtimes
are perishable and git records exactly which pages moved, which is what the protocol asks
for.

The URL list comes from the commit range, not from the generator: `build_pages.py` stays
offline and deterministic, and the submission stays out of the fetch workflow, which has
an unmerged branch against it.

Every kind of change is a notification, including the ones that remove a page: an engine
never told a URL is gone keeps the old entry until it recrawls. An earlier version filtered
out pages carrying `noindex` and stayed silent about exactly those changes.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://leffavuoro.fi"
HOST = "leffavuoro.fi"
ENDPOINT = "https://api.indexnow.org/IndexNow"
UA = "Leffavuoro/1.0 (+https://leffavuoro.fi)"
# Only generated pages. data/ is the machine payload, the logs are build output, and
# neither is a page a search engine should be told about.
PAGE_DIRS = ("teatteri/", "kaupunki/", "sv/teatteri/", "sv/kaupunki/",
             "en/theatre/", "en/city/")
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"   # git's canonical empty tree
ZERO = "0" * 40

# 200 is accepted, 202 means accepted-but-the-key-is-still-being-validated, which is the
# normal answer for a key nobody has checked yet. Treating it as failure would make the
# very first submission red.
OK_STATUS = (200, 202)
# The key, the host or the payload is wrong. Ours to fix, and retrying cannot help.
HARD_STATUS = (400, 403, 422)
RETRY_TRIES = 3
RETRY_BACKOFF = 5
# A stranger naming its own delay must not be able to stall the job indefinitely, the
# same ceiling common.fetch applies for the same reason.
RETRY_AFTER_MAX = 60
# The protocol's ceiling for one POST. This site is two orders of magnitude below it, so
# the batching exists to make the limit explicit rather than to be exercised -- a silent
# 422 on the day someone regenerates every page is a worse way to learn it.
MAX_URLS_PER_POST = 10000
# The cloud workflow commits as this identity. A push made with GITHUB_TOKEN does not
# trigger `on: push` -- GitHub suppresses it to stop workflows recursing -- so the
# routine data commits, which are the ones that move the pages, arrive only
# through workflow_run and have to be found by looking for them.
BOT_NAME = "kino-bot"
BOT_SUBJECT = "Update cloud provider data"


def key_file():
    """-> (key, filename).

    The 32-hex file at the root is a **public IndexNow ownership token, not a secret
    credential**: it is served openly so the protocol can confirm who controls the
    domain, which is why committing it is correct. Possession cannot modify the site or
    authenticate another host, but it would let someone submit same-host notifications
    and generate crawl noise, so it is not nothing either.
    """
    files = sorted(ROOT.glob("[0-9a-f]" * 32 + ".txt"))
    if len(files) != 1:
        raise SystemExit(f"[indexnow] expected exactly one key file at the root, "
                         f"found {[f.name for f in files]}")
    key = files[0].read_text(encoding="utf-8").strip()
    if key != files[0].stem:
        raise SystemExit(f"[indexnow] {files[0].name} does not contain its own name, "
                         f"which is what the protocol checks")
    return key, files[0].name


def _event():
    ev = os.environ.get("GITHUB_EVENT_PATH")
    if not ev or not pathlib.Path(ev).exists():
        return {}
    try:
        return json.loads(pathlib.Path(ev).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _iso_epoch(text):
    try:
        from datetime import datetime
        return int(datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").timestamp())
    except Exception:
        return None


def event_range():
    """The commit range to announce -> (before, after), or (None, None) for nothing.

    Two shapes arrive here, because the commits worth announcing come through two doors:

      push          a person pushed generated pages by hand
      workflow_run  the cloud workflow published its data commit

    The second exists because a push made with GITHUB_TOKEN does not trigger `on: push`
    at all -- GitHub suppresses it so workflows cannot recurse. Without this path the
    trigger would fire only for hand commits and stay silent for the routine data runs,
    which is where the theatre and city pages change. That is most of the
    feature, quietly missing.
    """
    ev = _event()
    run = ev.get("workflow_run")
    if run:
        # Deliberately not gated on conclusion. The fetch workflow commits and pushes
        # *before* its provider-failure gate, so a run can publish changed pages and
        # still finish red -- and those pages are live and need announcing exactly as
        # much as a green run's. Whether a commit exists is the only question that
        # matters, and looking for it answers it.
        #
        # `updated_at` on a completed run is when it finished, which closes the window a
        # later run's commit would otherwise fall into. If it is ever absent, now is a
        # sound upper bound: this job is running, so nothing committed after now can
        # belong to the run that triggered it.
        ended = _iso_epoch(run.get("updated_at") or "") or int(time.time())
        sha = bot_commit_for_run(run.get("head_sha"),
                                 _iso_epoch(run.get("run_started_at") or ""), ended)
        if not sha:
            return None, None
        return f"{sha}^", sha
    return push_range()


def push_range():
    """The commit range this push covers -> (before, after).

    A push is not one commit. Taking `HEAD^..HEAD` drops every page change in every
    earlier commit of the same push, which is silent and looks like nothing happened.
    GitHub names the real range on the event payload.

    An all-zero `before` means the ref was created by this push. Diffing against the
    empty tree would then announce every page on the site; falling back to the tip's
    parent announces what that push did, which is the useful answer and the
    quieter one. Only if there is no parent either does the empty tree apply.
    """
    ev = os.environ.get("GITHUB_EVENT_PATH")
    before = after = None
    if ev and pathlib.Path(ev).exists():
        try:
            data = json.loads(pathlib.Path(ev).read_text(encoding="utf-8"))
            before, after = data.get("before"), data.get("after")
        except (OSError, ValueError):
            before = after = None
    after = after or "HEAD"
    if not before or set(before) == {"0"}:
        before = f"{after}^" if _has_parent(after) else EMPTY_TREE
    return before, after


def _has_parent(rev):
    return subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{rev}^"],
                          cwd=ROOT, capture_output=True).returncode == 0


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout


def bot_commit_for_run(head_sha, started_at, ended_at, upper="HEAD"):
    """The data commit *this* cloud run published -> sha, or None.

    `workflow_run.head_sha` is the commit the triggering run started from, and a queued
    run starts from a base that has since moved -- so the range it names can span an
    earlier run's data commit as well as this one's.

    A lower time bound alone is not enough, and the failure is not hypothetical: run A
    publishes commit A and finishes, run B publishes commit B, and only then does A's
    notification job get CPU. Both commits are newer than A's start, so "newest wins"
    hands A the commit B published -- A is never announced, B is announced twice, and if
    A published nothing at all it is credited with B's work. The run's own window is what
    separates them, so the commit must fall **between the run starting and finishing**.

    Nothing found means the run published nothing, which is a normal answer.
    """
    if not head_sha or started_at is None or ended_at is None:
        return None
    out = _git("log", "--format=%H%x1f%ct%x1f%an%x1f%s", f"{head_sha}..{upper}")
    for line in out.splitlines():                 # newest first
        parts = line.split("\x1f")
        if len(parts) != 4:
            continue
        sha, ct, author, subject = parts
        if author != BOT_NAME or subject != BOT_SUBJECT:
            continue
        if started_at <= int(ct) <= ended_at:
            return sha
    return None


def changed_urls(before, after):
    """Page URLs a range added, modified, deleted or moved -> sorted list.

    Every status letter is a notification, and the ones that remove a URL matter most:

      A/M  the page exists now              -> submit it
      D    the page is gone                 -> submit it, so the engine drops it
      R    the page moved                   -> submit *both* sides, so the old entry is
                                               retired and the new one is found

    Nothing here reads the file. A deleted page cannot be read at all, and what a page
    now contains -- `noindex`, a redirect, anything -- is a reason to announce it rather
    than to stay quiet.
    """
    out = subprocess.run(["git", "diff", "--name-status", "-M", before, after],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    paths = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        if status.startswith("R") and len(parts) >= 3:
            paths += [parts[1], parts[2]]         # old and new
        elif status[:1] in ("A", "M", "D"):
            paths.append(parts[1])
    return sorted({f"{SITE}/{p[:-len('index.html')]}" for p in paths
                   if p.endswith("/index.html") and p.startswith(PAGE_DIRS)})


def payload(urls, key, key_name):
    return {"host": HOST, "key": key,
            "keyLocation": f"{SITE}/{key_name}",
            "urlList": urls}


def _post(body, timeout):
    """-> (status, detail, retry_after). status is None when nothing answered."""
    req = urllib.request.Request(
        ENDPOINT, method="POST",
        data=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json; charset=utf-8", "user-agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, "ok", None
    except urllib.error.HTTPError as e:
        after = None
        try:
            raw = (e.headers or {}).get("Retry-After")
            after = int(raw) if raw and raw.strip().isdigit() else None
        except Exception:
            after = None
        return e.code, (e.reason or ""), after
    except Exception as e:                # DNS, TLS, timeout, reset
        return None, str(e), None


def submit(body, tries=RETRY_TRIES, timeout=30, sleep=time.sleep):
    """-> (status, detail). Bounded retry only; never loops without a limit.

    429 is rate limiting and 5xx or a dead socket is the far end having a bad minute --
    both transient, both worth a few attempts. 400/403/422 are this repo's mistake and
    retrying them just repeats it.
    """
    status = detail = None
    for attempt in range(1, tries + 1):
        status, detail, retry_after = _post(body, timeout)
        if status in OK_STATUS or status in HARD_STATUS:
            return status, detail
        if attempt == tries:
            break
        wait = retry_after if retry_after is not None else RETRY_BACKOFF * attempt
        wait = min(wait, RETRY_AFTER_MAX)
        print(f"[indexnow] {status or 'no response'} ({detail}), "
              f"retrying in {wait}s ({attempt}/{tries - 1})", file=sys.stderr)
        sleep(wait)
    return status, detail


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--before")
    ap.add_argument("--after")
    args = ap.parse_args(argv)

    key, key_name = key_file()
    if args.before or args.after:
        before = args.before or f"{args.after}^"
        after = args.after or "HEAD"
    else:
        before, after = event_range()
    if before is None:
        print("[indexnow] the triggering run published no data commit")
        return 0
    urls = changed_urls(before, after)
    if not urls:
        print(f"[indexnow] no generated pages changed in {before}..{after}")
        return 0
    print(f"[indexnow] {len(urls)} changed page(s) in {before}..{after}")
    if args.dry_run:
        body = payload(urls, key, key_name)
        print(json.dumps({**body, "key": "<redacted for the dry run>"}, indent=1))
        return 0

    batches = [urls[i:i + MAX_URLS_PER_POST]
               for i in range(0, len(urls), MAX_URLS_PER_POST)]
    if len(batches) > 1:
        print(f"[indexnow] {len(urls)} urls exceeds the {MAX_URLS_PER_POST} per-POST "
              f"ceiling, sending {len(batches)} batches")
    for n, batch in enumerate(batches, 1):
        status, detail = submit(payload(batch, key, key_name))
        if status not in OK_STATUS:
            break
        print(f"[indexnow] submitted {len(batch)} url(s), {status}"
              + (f" (batch {n}/{len(batches)})" if len(batches) > 1 else ""))
    if status in OK_STATUS:
        return 0
    # Everything else is worth seeing. This workflow cannot block publication -- the
    # pages are already live and the sitemap still advertises them -- so a submission
    # that keeps failing should show as failing rather than stay green forever.
    print(f"[indexnow] gave up after {RETRY_TRIES} attempt(s): "
          f"{status or 'no response'} ({detail})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
