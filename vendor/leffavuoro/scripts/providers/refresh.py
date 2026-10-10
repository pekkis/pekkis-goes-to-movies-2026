"""When a cached TMDB rating is due to be read again. Pure; no I/O.

Two caches hold ratings: `data/tmdb.json`, keyed by Finnkino filmId and written by
scripts/fetch_data.py, and `data/tmdb-titles.json`, keyed by normalised title and written
by providers/enrich_tmdb.py. Both decide "read again?" here, so the rule cannot drift
between them. They differ only in what a complete entry looks like, which each passes in
as `complete`: the Finnkino cache carries no synopsis or poster, because Finnkino
publishes both itself.

The rule:

  * Refresh complete entries once `c` is `max_age` days old, even when a trailer is
    cached. Before, a cached trailer stopped an entry from ever being re-read and its
    rating froze.
  * `c` is when TMDB last answered with a usable rating and vote count, not when it was
    last asked. A failed detail request keeps the old date, so the entry stays due.
  * `a` is when a refresh was last attempted, and the queue sorts on it: least recently
    attempted first, never attempted ahead of all. Sorting on `c` would let an id that
    can never be read hold the whole budget for ever.
  * `budget` bounds the catch-up. Without it the first run after a rule change re-reads
    the whole backlog at once, and it all comes due together again.

`a` is not part of any `complete` predicate. It is scheduling bookkeeping, and absence
means "never attempted", which sorts first.
"""
import datetime
import os

# How long a cached rating may stand, and how many stale ones one pass re-reads. In the
# steady state ~96 entries at seven days come due at about fourteen a day, two per run;
# the budget only bounds the catch-up. Overridable like KINO_PAGE_BUDGET.
RATING_MAX_AGE = int(os.environ.get("KINO_TMDB_MAX_AGE") or 7)
REFRESH_BUDGET = int(os.environ.get("KINO_TMDB_REFRESH") or 12)


def numeric(v):
    """A usable number from a TMDB field. -> the value, or None.

    Zero is a value: an unvoted film has `vote_count` 0 and `vote_average` 0.0. Absent,
    null or a string is not, and must not overwrite a real rating with zero.
    """
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def age_days(entry, today, field="c"):
    """Days since one of this entry's dates. -> int, or None if the field is missing.

    None differs from zero. No `c` means an entry from an older shape, the oldest there
    is; no `a` means never attempted, the head of the queue.
    """
    try:
        return (datetime.date.fromisoformat(today)
                - datetime.date.fromisoformat(entry.get(field) or "")).days
    except (TypeError, ValueError):
        return None


def due(keys, cache, today, complete, max_age=None, budget=None):
    """Which cached entries a pass should fetch. -> (keys, refreshes, deferred).

    `keys` is what the pass has work for; `complete` says what a fully-formed entry looks
    like in that cache. `refreshes` is returned as keys so the caller can report which
    detail requests failed. `deferred` is what the budget left for the next run.

    Four states:

      * not cached: fetched.
      * cached in an older shape, missing a field: fetched, so a new field costs one pass
        rather than a cache wipe.
      * complete with no trailer: once a day, in case a trailer has appeared.
      * complete with a trailer: re-read once `c` is `max_age` days old, at most `budget`
        a run, least recently attempted first.
    """
    max_age = RATING_MAX_AGE if max_age is None else max_age
    budget = REFRESH_BUDGET if budget is None else budget
    work, stale = set(), []
    for k in keys:
        c = cache.get(k)
        if not complete(c):
            work.add(k)
            continue
        age = age_days(c, today)
        if not c.get("v"):
            # Read today already is the only reason to skip.
            if age != 0:
                work.add(k)
            continue
        if age is None or age >= max_age:
            stale.append((age, age_days(c, today, "a"), k))
    # Never attempted first, then longest since the last attempt, then oldest data, then
    # the key, so the order is deterministic.
    stale.sort(key=lambda p: (0 if p[1] is None else 1, -(p[1] or 0),
                              0 if p[0] is None else 1, -(p[0] or 0), p[2]))
    refresh = {k for _, _, k in stale[:budget]}
    return work | refresh, refresh, len(stale) - len(refresh)


def report(scheduled, settled, deferred, budget=None):
    """The one line a pass prints about its rating refreshes. -> str, or "" if silent.

    Printed after the loop, since whether a refresh re-read anything is only known then.
    A failed refresh keeps its figures and comes round again, but a run where every
    refresh failed must not read like one where every refresh worked.
    """
    if not scheduled and not deferred:
        return ""
    budget = REFRESH_BUDGET if budget is None else budget
    return (f"rating refresh: {scheduled} scheduled, {settled} re-read, "
            f"{scheduled - settled} failed and still due, {deferred} deferred "
            f"(budget {budget})")
