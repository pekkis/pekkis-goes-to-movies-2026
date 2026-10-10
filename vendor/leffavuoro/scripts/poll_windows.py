#!/usr/bin/env python3
"""When do the cinemas publish? Answered from committed data, no network.

    python3 scripts/poll_windows.py                # every provider
    python3 scripts/poll_windows.py --provider kinoset --provider biorex
    python3 scripts/poll_windows.py --since 2026-09-01
    python3 scripts/poll_windows.py --include-development   # keep the flagged commits

The polling schedule should follow the publication rhythm. This walks every pair of
consecutive data commits and reports when new schedule data first became visible, so the
slots can be set from measurement.

What a timestamp means. `Thu 19h` says the publication happened after the previous
successful observation and no later than this commit. Every row carries `gap`, the
interval back to the previous poll of that provider, which is the width of that window.
With four polls a day it is about six hours, so read the weekday distribution before the
hour.

What counts as new schedule data. Showtimes are keyed on `(venue, title, start, aud)` and
only ones starting after the commit are counted, so a screening scrolling into the past is
not an arrival. Three signals:

    showtimes   future screenings present in this commit and absent in the previous one
    horizon     the furthest future start moved outward
    titles      a title not previously seen for that provider (the weakest: a cinema
                adding next week's dates for a film already showing introduces none)

Not counted: enrichment (`tmdbId`, `tmdb`, `votes`, `tr`, `gids`), poster rewrites
(`img`), synopses, the `generated` stamp, page generation and any other rewrite that
leaves the same screenings in place.

Development is flagged, not counted. An adapter changing between two observations means
the diff may be backfill rather than the cinema publishing; those rows are excluded by
default and `--include-development` puts them back. The first observation of any provider
is always excluded. The Aug 26-30 window is almost entirely this.
"""
import argparse
import collections
import datetime
import json
import pathlib
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Every timestamp is reported in the cinemas' own timezone. Commits arrive in whatever
# offset the committer had -- the local half stamps +03:00 and the runner stamps +00:00 --
# and both the weekday bucket and the printed clock were being taken from that raw offset.
# A cloud commit at 23:30 UTC is 02:30 the next day in Helsinki, so it was being filed
# under the wrong weekday, which is the one thing this script exists to report. Arithmetic
# was never affected; the datetimes are aware and subtract correctly. Display and
# classification were.
FI = ZoneInfo("Europe/Helsinki")

# Only these two messages are the pipeline running unattended. Anything else on a data
# path is someone working, and its diff is not an observation of a cinema.
PIPELINE_MSGS = ("Update cloud provider data", "Update schedule data (local)")

# A change under any of these means a provider's parse may have moved, so a diff across
# it cannot be told apart from the cinema publishing.
ADAPTER_PATHS = ("scripts/providers/", "scripts/fetch_data.py")


def git(*args):
    out = subprocess.run(("git",) + args, cwd=str(ROOT),
                         capture_output=True, text=True)
    out.check_returncode()
    return out.stdout


def commits(ref, since):
    """Data-touching commits, oldest first. -> [(sha, when, subject, touched_adapter)]."""
    rng = ["--since", since] if since else []
    raw = git("log", "--reverse", "--format=%H\t%cI\t%s", *rng, ref, "--", "data/")
    rows = []
    prev = None
    for line in raw.splitlines():
        sha, when, subject = line.split("\t", 2)
        # Whether an adapter moved anywhere in the range since the previous observation,
        # not just in this commit. An adapter commit usually touches no data file at all,
        # so checking `sha` alone missed every one of them -- the Orion parser landing
        # between two cloud runs looked like Cinema Orion publishing 27 screenings.
        touched = bool(git("log", "--format=%H", f"{prev}..{sha}" if prev else sha,
                           "--", *ADAPTER_PATHS).strip())
        rows.append((sha, datetime.datetime.fromisoformat(when).astimezone(FI),
                     subject, touched))
        prev = sha
    return rows


def area_blobs(sha):
    """-> {path: blob sha} for the area files at this commit."""
    out = {}
    for line in git("ls-tree", "-r", sha, "--", "data/").splitlines():
        meta, path = line.split("\t", 1)
        _, typ, blob = meta.split()
        if typ == "blob" and re.fullmatch(r"data/area-.+\.json", path):
            out[path] = blob
    return out


def read_blobs(shas):
    """Batch-read blobs -> {sha: (provider, {(title, aud, epoch)})}.

    `start` is reduced to an epoch second rather than kept as its ISO string, because the
    string form cannot be compared. Showtimes carry a Helsinki offset (+03:00) and commit
    timestamps arrive in whatever offset the committer had, so `"...T17:20:00+03:00" >
    "...T15:16:40+00:00"` is true lexically and false in real time -- 17:20 EEST is 14:20
    UTC, an hour *before* that commit. Every one of the sixteen tiny "arrivals" this
    script first reported for Gilda was that comparison, on two files whose contents were
    byte-identical.

    Deduplicated across commits, which is the whole reason this is fast: most files are
    identical between two runs and the pipeline rewrites only what changed.
    """
    shas = sorted(shas)
    if not shas:
        return {}
    proc = subprocess.run(["git", "cat-file", "--batch"], cwd=str(ROOT),
                          input=("\n".join(shas) + "\n").encode(), capture_output=True)
    out, cache, i = proc.stdout, {}, 0
    while i < len(out):
        nl = out.find(b"\n", i)
        if nl < 0:
            break
        parts = out[i:nl].split()
        if len(parts) != 3:
            break
        sha, size = parts[0].decode(), int(parts[2])
        body = out[nl + 1:nl + 1 + size]
        i = nl + 1 + size + 1
        provider, keys = None, set()
        try:
            for s in json.loads(body).get("shows") or []:
                title = (s.get("title") or "").strip()
                try:
                    when = datetime.datetime.fromisoformat(s.get("start") or "")
                except ValueError:
                    continue
                if not title or when.tzinfo is None:
                    continue          # a naive start cannot be placed on a timeline
                provider = provider or s.get("provider") or "finnkino"
                keys.add((title, (s.get("aud") or "").strip(), int(when.timestamp())))
        except Exception:
            pass
        cache[sha] = (provider, keys)
    return cache


def stamp(epoch):
    return datetime.datetime.fromtimestamp(epoch, FI).strftime("%Y-%m-%d")


def venue_of(path):
    return path[len("data/area-"):-len(".json")]


def venue_providers(trees, cache):
    """venue id -> provider, learned from every blob in the history at once.

    Taken from the shows, because that is where the provider id lives -- but it
    has to be learned globally rather than per commit. A venue whose file is momentarily
    empty carries no show and therefore names no provider, and reading it per commit
    dropped that venue out of the provider's state; every screening then counted as new
    the moment it came back. Two of the arrivals in the first run of this script were
    that bug and not a cinema.
    """
    out = {}
    for tree in trees.values():
        for path, blob in tree.items():
            provider, keys = cache.get(blob, (None, set()))
            if provider:
                out.setdefault(venue_of(path), provider)
    return out


def future(keys, when):
    """Screenings that had not happened yet when the commit was made."""
    cut = when.timestamp()
    return {k for k in keys if k[2] > cut}


def collect(ref, since, wanted):
    """Walk the history and return every arrival. -> (rows, events).

    Separate from `report` so the classification can be tested without parsing printed
    output. Every rule that decides organic-versus-development lives here.
    """
    rows = commits(ref, since)
    if len(rows) < 2:
        return rows, []

    trees = {sha: area_blobs(sha) for sha, *_ in rows}
    cache = read_blobs({b for t in trees.values() for b in t.values()})
    owner = venue_providers(trees, cache)

    seen = {}                                   # provider -> (when, {venue: keys}, horizon)
    titles = collections.defaultdict(set)       # provider -> titles ever seen
    populated = set()                           # venues that have ever carried a show
    events = []

    for sha, when, subject, touched_adapter in rows:
        state = collections.defaultdict(dict)
        horizon = collections.defaultdict(int)
        raw_titles = collections.defaultdict(set)
        for path, blob in trees[sha].items():
            venue = venue_of(path)
            provider, keys = cache.get(blob, (None, set()))
            provider = provider or owner.get(venue)
            if not provider:
                continue                  # a venue that never carried a show, anywhere
            fut = future(keys, when)
            state[provider][venue] = fut
            # Titles come from the future set, not from everything in the file, so the
            # two signals agree: a title whose only screening has already happened is not
            # something the cinema just published. Caught by the DST fixture, where the
            # earlier of two same-wall-clock screenings is already past.
            raw_titles[provider].update(t for t, _, _ in fut)
            for _, _, epoch in keys:
                horizon[provider] = max(horizon[provider], epoch)

        for provider, venues in state.items():
            if wanted and provider not in wanted:
                continue
            reasons = []
            if touched_adapter:
                reasons.append("adapter changed since the previous observation")
            if subject not in PIPELINE_MSGS:
                reasons.append("not an unattended pipeline commit")

            prev = seen.get(provider)
            # A venue's first screenings are backfill, not news: a venue added before its
            # programme is published carries an empty file until it starts producing, and
            # that first population looks exactly like a cinema publishing a season.
            # Tracked per venue rather than per provider, and separately from whether the
            # venue is *present*, because since venues are attributed globally an empty
            # file no longer drops out of state -- which is correct, and which silently
            # stopped this from being flagged the way a missing venue used to be.
            first = sorted(v for v, k in venues.items() if k and v not in populated)
            for v, keys in venues.items():
                if keys:
                    populated.add(v)
            if first:
                reasons.append("first population of " + ", ".join(first))

            if prev is None:
                seen[provider] = (when, venues, horizon[provider])
                titles[provider] |= raw_titles[provider]
                continue

            prev_when, prev_venues, prev_horizon = prev
            new_shows = sum(len(v - prev_venues.get(k, set())) for k, v in venues.items())
            new_venues = sorted(set(venues) - set(prev_venues))
            if new_venues:
                reasons.append("new venue file " + ", ".join(new_venues))
            grew = horizon[provider] > prev_horizon
            new_titles = sorted(raw_titles[provider] - titles[provider])

            if new_shows or grew:
                events.append({
                    "provider": provider, "sha": sha[:8], "subject": subject,
                    "when": when, "prev_when": prev_when,
                    "gap_h": (when - prev_when).total_seconds() / 3600.0,
                    "shows": new_shows,
                    "new_venues": new_venues,
                    "new_titles": new_titles,
                    "horizon": (f"{stamp(prev_horizon)} -> {stamp(horizon[provider])}"
                                if grew else ""),
                    "development": bool(reasons),
                    "reasons": reasons,
                })
            seen[provider] = (when, venues, horizon[provider])
            titles[provider] |= raw_titles[provider]

    return rows, events


def analyse(ref, since, wanted, include_dev):
    rows, events = collect(ref, since, wanted)
    if len(rows) < 2:
        print("not enough data commits to compare", file=sys.stderr)
        return 1
    report(events, include_dev, rows)
    return 0


def report(events, include_dev, rows):
    kept = [e for e in events if include_dev or not e["development"]]
    dropped = len(events) - len(kept)
    span = (rows[-1][1] - rows[0][1]).total_seconds() / 86400.0

    print(f"{len(rows)} data commits over {span:.1f} days, "
          f"{rows[0][1]:%Y-%m-%d} to {rows[-1][1]:%Y-%m-%d}, "
          f"times in Europe/Helsinki")
    print(f"{len(events)} arrival events, {dropped} flagged as development/backfill "
          f"and excluded" + (" (shown anyway)" if include_dev else ""))
    print()
    print("Each row is an observation window, not a publication time. It says the "
          "provider")
    print("published sometime AFTER the previous observation and no later than this "
          "one;")
    print("the window is printed in full, and it can never be narrower than the polling")
    print("interval that produced it.")
    print()

    if not kept:
        print("Nothing organic to report, which with this much history is the honest")
        print("answer rather than a rhythm.")
        return

    by = collections.defaultdict(list)
    for e in kept:
        by[e["provider"]].append(e)

    for provider in sorted(by):
        es = sorted(by[provider], key=lambda e: e["when"])
        print(f"--- {provider}  ({len(es)} arrivals)")
        for e in es:
            bits = []
            if e["horizon"]:
                bits.append(f"horizon {e['horizon']}")
            if e["new_titles"]:
                bits.append(f"{len(e['new_titles'])} new title(s)")
            if e["new_venues"]:
                bits.append("+venues " + ",".join(e["new_venues"]))
            if e["development"]:
                bits.append("DEV: " + "; ".join(e["reasons"]))
            print(f"    {WD[e['when'].weekday()]} "
                  f"({e['prev_when']:%m-%d %H:%M} -> {e['when']:%m-%d %H:%M}]  "
                  f"{e['gap_h']:5.1f}h window  "
                  f"+{e['shows']:4d} future showtimes"
                  + ("  " + "  ".join(bits) if bits else ""))
        wd = collections.Counter(WD[e["when"].weekday()] for e in es)
        print("    weekday: " + ", ".join(f"{d} x{wd[d]}" for d in WD if wd[d]))
        print()

    print("=== all providers, arrivals by weekday ===")
    wd = collections.Counter(WD[e["when"].weekday()] for e in kept)
    for d in WD:
        if wd[d]:
            print(f"  {d}  x{wd[d]}")
    widest = max(e["gap_h"] for e in kept)
    print(f"\nWidest observation window here: {widest:.1f}h. Nothing about a publication")
    print("*hour* is available at finer resolution than that, so read the weekday first.")


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--since", default="")
    ap.add_argument("--provider", action="append", default=[])
    ap.add_argument("--include-development", action="store_true")
    a = ap.parse_args(argv)
    return analyse(a.ref, a.since, set(a.provider), a.include_development)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
