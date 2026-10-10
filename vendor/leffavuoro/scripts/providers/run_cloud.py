#!/usr/bin/env python3
"""One process, one pool, every module of a half.

    python3 scripts/providers/run_cloud.py --where cloud
    python3 scripts/providers/run_cloud.py --where cloud --workers 1

Writes `logs/run-{module}.log` per module, each with the same site blocks, summary line and
final `exit=N` the per-module `run.py` invocation wrote, plus `logs/run-cloud.log` for the
run as a whole. `scripts/check_runs.py` reads all of them and is unchanged.

## Why this exists

`biorex.yml` ran `run.py "$m"` once per module, one after another, and each of those
processes pooled *its own* sites by host. So two modules never overlapped: the whole of
eTiketti's twenty sites finished before the first BioRex request, however many hosts were
idle in between. This is the same pool, once, over every module's sites at once.

**Not by backgrounding the module commands.** They share `data/films-extra.json`, and the
lock in `synmerge` is a `threading.Lock`: it does nothing across processes, so two runs
merging at once would each write back a document built from what they read and whichever
finished second would drop the other's synopses, silently. Separate processes would also
each hold their own `synmerge` claim table and their own stdout, so the synopsis precedence
and the per-module log would both come apart.

## The shape

1. Modules come from the registry in its own order, and only their sites for this half.
2. A work item keeps its module, the module's position, its position in the module's own
   site list, its provider, and the host it is read from.
3. **Grouped by host, across modules.** One host is read by one thread whether its sites
   belong to one module or two, so the sleep inside an adapter's `fetch_site` still
   describes what that server sees. Independent hosts overlap.
4. One ceiling, `MAX_HOSTS` host groups at a time, shared by every module. There is no
   inner pool to multiply it by: this replaces `run.run_sites` rather than wrapping it.
5. **Workers fetch. The coordinator publishes**, on one thread, in module order and then
   site order, which is the order the per-module processes published in. `run.publish_site`
   is the step: contract check, strand split, synopsis merge, enrichment carry-forward,
   the stale/pending/unverified decision and the file writes. So `films-extra.json` has one
   writer and its precedence -- existing text wins, then the earlier site in SITES order --
   is what it was, at any pool size.
6. `synmerge.reset()` at each module boundary, as `run_sites` does, because a later
   module's site 0 must not outrank an earlier module's site 5.

## What the pool does not change

- Per-host pacing, and every adapter's own sleeps.
- The retry and Retry-After budgets, which were per module when each module was a process.
  `common.accounting` keeps them per module here; see the comment on `common._scopes`.
- The committed log. A site's block is replayed whole, in site order, into its own module's
  file, so a log still reads downwards however long a site took.
"""
import argparse
import concurrent.futures
import datetime
import importlib
import os
import pathlib
import sys
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common              # noqa: E402
import registry            # noqa: E402
import run                 # noqa: E402
import synmerge            # noqa: E402
import venuelists          # noqa: E402

LOGS = pathlib.Path("logs")

# The same ceiling as the single-module path and the same knob, `KINO_MAX_HOSTS`, because
# it means the same thing: how many hosts this end reads at once. Taken from `run` rather
# than read again so the two cannot drift; 1 is the sequential path, which is what the
# equivalence tests run against.
MAX_HOSTS = run.MAX_HOSTS

# One site's fetch, wall clock, before it fails and the rest of the run publishes as it does
# around any failed site. The longest site of 76 pooled runs to 2026-09-25 took 108 s
# (Kinola) and the median slowest module 88 s (BioRex), so 300 s is nearly three times the
# worst seen; the job is capped at 30 minutes and a stalled host used to hold the whole
# run to it, so the commit step never ran (audit C1). `KINO_SITE_DEADLINE` overrides it;
# 0 turns it off.
SITE_DEADLINE = float(os.environ.get("KINO_SITE_DEADLINE") or 300)

# Two hosts verified to be one upstream, mapped onto a shared group key so the sites that
# read them are read one after the other.
#
# Empty, and that is a measurement rather than an assumption: on 2026-09-15 no two cloud
# sites of *different* modules shared a registrable domain, and every same-module pair that
# does (kinoaurora.fi twice, kinohirvi.fi twice) already shares a `base` and so a group.
# `tests/test_cloud_pool.py` asserts that over the live registry, so a provider landing on
# another module's domain fails a test instead of quietly doubling the rate at one server.
#
# An entry here is a finding with a source, never a guess. Two other things carry the rest
# of this question, because a differing `base` does not by itself prove two upstreams
# independent: a site declares every host it knows it reads in `reads`, which
# `run.hosts_of` folds into the grouping, and `common.reading` claims whatever host a fetch
# actually goes to, which is the only thing that can cover a URL read out of a page.
SHARED_UPSTREAMS = {}


class Site:
    """One site of one module, and everything the run learns about it."""

    __slots__ = ("index", "module", "mod", "order", "site", "host", "label",
                 "per_venue", "result", "error", "chunks", "settled", "published",
                 "queued", "started", "finished")

    def __init__(self, index, module, order, site):
        self.index = index          # position in the run's publication order
        self.module = module
        self.mod = module.mod
        self.order = order          # position in this module's selected sites
        self.site = site
        self.host = run.host_of(site)
        self.label = site.get("provider") or self.mod.__name__
        self.per_venue = self.result = self.error = None
        self.chunks = []
        self.settled = self.published = False
        self.queued = self.started = self.finished = None

    @property
    def hosts(self):
        """Every host this site declares, with verified shared upstreams folded in.

        -> (netloc, ...). The grouping is over these, so a site naming two hosts joins
        every site naming either.
        """
        return tuple(SHARED_UPSTREAMS.get(h, h) for h in run.hosts_of(self.site))


class Module:
    """One module's selection, its outcome and its committed log."""

    def __init__(self, order, name):
        self.order, self.name = order, name
        self.mod = None
        self.error = None           # import or configuration failure, kept as a failure
        self.sites = []
        self.items = []
        self.tally = run.Tally([name])
        self.done = False
        self.opened = False         # this run has truncated the log and is writing it

    @property
    def path(self):
        return LOGS / f"run-{self.name}.log"


def collect(names, half):
    """Import each module and select its sites for this half. -> [Module], in order.

    An import or configuration failure is recorded rather than raised: it is that module's
    failure and the rest of the run still publishes, which is what the per-module shell
    loop did with `set +e`.
    """
    mods = []
    for order, name in enumerate(names):
        m = Module(order, name)
        try:
            m.mod = importlib.import_module(name)
            m.mod.SITES        # a module without it is unusable, and says so in its log
            # Inside the try: a SITES entry with no registry entry raises here, and one
            # module's misconfiguration must cost that module's log, not the pool.
            m.sites = run.sites_for(m.mod, half)
        except Exception as e:
            m.error = e
        mods.append(m)
    return mods


def work_items(mods):
    """Every site to fetch, in publication order. -> [Site]."""
    items = []
    for m in mods:
        m.items = [Site(len(items) + k, m, k, site) for k, site in enumerate(m.sites)]
        items.extend(m.items)
    return items


def host_groups(items):
    """Work items grouped so that no two groups declare a host in common, across modules.

    -> [[Site, ...], ...], groups in the order their first member appears and members in
    publication order, so a run reads the same way every time.

    The key is the host and not the site, and not the module either: `kinoaurora.fi` serves
    two of Nexxo's sites today, and if two modules ever reach one server the same rule has
    to hold across them. A site declaring two hosts joins every site declaring either --
    the groups are connected components, see `run.group_indices` -- so `reads` is enough to
    serialise a secondary upstream without inventing a second key for it. A site with no
    `base` answers "" and shares one group with every other such site, which reads them one
    at a time rather than assuming they are different cinemas; there are none in the cloud
    half as of 2026-09-15.
    """
    at = run.group_indices([it.hosts for it in items])
    groups = {}
    for it, g in zip(items, at):
        groups.setdefault(g, []).append(it)
    return [groups[g] for g in sorted(groups)]


def read_host(group, rec, done, fatal):
    """One host's sites, one after the other, on one pool thread.

    The same two-tier handling `run.run_sites` uses and for the same reasons. An ordinary
    failure is caught per site and travels back as that site's error, so one cinema refusing
    takes neither the rest of its host nor the run with it. A `BaseException` -- a
    `SystemExit` out of adapter code -- ended a sequential run and has to end this one, so
    it is recorded and re-raised by the coordinator; left alone the thread would die, the
    future would hold the exception unread, and the run would publish anyway.

    A site is released only once it has an outcome. Releasing it while its thread is being
    unwound would hand the coordinator an empty result before `fatal` was there to be seen.
    """
    try:
        ready = None
        for it in group:
            if ready is not None:
                # A site becomes ready when its host group reaches it, not when the run
                # began. Reported as queue wait, that keeps the number meaning "waited for
                # a pool slot" -- a site behind another on the same host is waiting on the
                # courtesy instead, which is the design and not pressure on the ceiling.
                it.queued = ready
            try:
                it.chunks = rec.capture()
                it.started = time.monotonic()
                # `accounting` charges the requests to this module; `reading` claims every
                # host they turn out to go to, page-derived ones included, and releases
                # them when this site is done; `site_deadline` ends a site that runs past
                # SITE_DEADLINE, and the others publish around it.
                with common.accounting(it.module.name), common.reading(it.label), \
                        common.site_deadline(SITE_DEADLINE):
                    it.per_venue = it.mod.fetch_site(it.site)
                it.settled = True
            except Exception as e:
                it.error = e
                it.settled = True
            finally:
                it.finished = time.monotonic()
                rec.release()
                ready = it.finished
                if it.settled:
                    done[it.index].set()
    except BaseException as e:          # noqa: BLE001 -- forwarded, not handled
        fatal.append(e)
    finally:
        for it in group:
            done[it.index].set()


def publish(it, now):
    """Run one site's write phase on the coordinator thread.

    A contract violation raises here rather than in the worker, which is the same site
    failure it always was: the files are left as they were and the log names the key.
    """
    if isinstance(it.error, common.EmptyProgramme):
        # Published like run.run_site does it, then still recorded as the empty programme
        # it was. A write that fails here replaces the error and fails the site.
        try:
            run.publish_empty(it.mod, it.site, now, it.order)
        except Exception as e:
            it.error = e
        return
    if it.error is not None:
        return
    try:
        it.result = run.publish_site(it.mod, it.site, it.per_venue, now, it.order)
    except Exception as e:
        it.error = e
    finally:
        it.per_venue = None         # published or failed; nothing else reads it


def timing_line(m):
    """One module's timing, or None when it fetched nothing.

    Three different numbers, kept apart on purpose. The sum of the fetches is **worker
    time**, and the workers overlap, so it is not elapsed anything; the span is the only
    wall-clock figure here; the wait is how long a site sat in the queue before a worker
    took it, which is what a ceiling that is too low looks like.
    """
    spans = [(it.started, it.finished) for it in m.items
             if it.started is not None and it.finished is not None]
    if not spans:
        return None
    # From when its host group reached it, so this is time spent waiting for a pool
    # slot rather than time spent behind another site on the same server.
    waits = [it.started - it.queued for it in m.items if it.started is not None]
    return (f"[run] timing: {len(spans)} site(s), "
            f"{sum(b - a for a, b in spans):.1f}s of fetching added up across workers "
            f"that overlap, longest site {max(b - a for a, b in spans):.1f}s, "
            f"longest queue wait {max(waits):.1f}s, "
            f"{max(b for _, b in spans) - min(a for a, _ in spans):.1f}s wall from this "
            f"module's first fetch starting to its last ending")


def run_module(m, rec, fh, done, fatal, now, half, peak):
    """Drain one module's sites in order, publish them, and close its log.

    Everything printed inside here -- the worker's replayed block, the publish step's own
    lines, the summary -- goes to this module's file and nowhere else.
    """
    with rec.sink(fh):
        if m.error is not None:
            m.tally.unusable(m.name, m.error)
        elif not m.sites:
            m.tally.no_sites(m.name, half)
        else:
            # Per module, exactly as run_sites does it: a later module's site 0 must not
            # outrank an earlier module's site 5 for a synopsis slot.
            synmerge.reset()
            for it in m.items:
                done[it.index].wait()
                if fatal:
                    # Raised on this thread, which is where a sequential run would have
                    # raised it. The caller's `finally` stops the pool and closes the logs.
                    raise fatal[0]
                peak(it)
                rec.replay_into(it.chunks, fh)
                it.chunks = []
                publish(it, now)
                it.published = True
                m.tally.site(it.mod, m.sites, it.label, it.result, it.error)
        m.tally.report(common.cache_stats(m.name), common.throttle_stats(m.name),
                       common.hosts_attempted(m.name))
        line = timing_line(m)
        if line:
            print(line)
    fh.write(f"exit={m.tally.code()}\n")
    fh.flush()
    m.done = True


class Held:
    """How much a run holds while it waits for an earlier site to be published.

    A global pool fetches ahead of the publication order, so results and captured log text
    pile up behind the slowest early module. The shape of the worst case is every site
    fetched and none published, which is the whole half at once; nothing in the code makes
    it smaller, because blocking a worker until a permit frees can deadlock -- the site the
    coordinator is waiting for may be the one that cannot get a permit.

    **So this is a measurement, not a bound.** At the programme of 2026-09-15 the 48 cloud
    sites' committed schedules are 1.83 MB of JSON over 71 venue files and 3,312 showtimes;
    held as the Python dicts a fetch returns that is 5.45 MB, plus at most 1.72 MB of `_syn`
    that `strip_helpers` drops at publication and about as much again in duplication across
    venues, so under 10 MB against a runner's 16 GB. It scales with the cinemas and with the
    length of their programmes, and both grow. Captured log text is the part that is
    actually bounded, per site, by `run.MAX_CAPTURE`.

    Which is why this is sampled at every publication, when the queue is longest, and
    reported in `logs/run-cloud.log`: the figure is re-measured on every run rather than
    asserted once from one day's data.
    """

    def __init__(self, items):
        self.items = items
        self.sites = self.bytes = 0

    def __call__(self, _it):
        waiting = [i for i in self.items if i.finished is not None and not i.published]
        self.sites = max(self.sites, len(waiting))
        self.bytes = max(self.bytes, sum(len(t) for i in waiting for _, t in i.chunks))


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--where", required=True, choices=("cloud", "local", "all"),
                    help="which half to read; the cloud workflow passes cloud")
    ap.add_argument("--workers", type=int, default=None,
                    help=f"host groups read at once (default {MAX_HOSTS}; 1 is sequential)")
    ap.add_argument("--logs", default=None, help="where the per-module logs are written")
    args = ap.parse_args(argv)

    global LOGS
    if args.logs:
        LOGS = pathlib.Path(args.logs)
    workers = MAX_HOSTS if args.workers is None else args.workers

    half = args.where
    names = registry.modules(None if half == "all" else half)
    LOGS.mkdir(parents=True, exist_ok=True)
    run.OUT.mkdir(exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    mods = collect(names, half)
    items = work_items(mods)
    groups = host_groups(items)
    done = [threading.Event() for _ in items]
    fatal = []
    held = Held(items)
    rec = run.Recorder()

    started = time.monotonic()
    for it in items:
        it.queued = started

    aborted = None
    # The streams are swapped and the pool is created only once there is a file to report
    # into: a run that cannot open its own log must not leave sys.stdout replaced, because
    # the failure would then be unreadable.
    with open(LOGS / "run-cloud.log", "w", encoding="utf-8") as top:
        rec.install()
        pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, min(workers, len(groups) or 1)))
        try:
            for group in groups:
                pool.submit(read_host, group, rec, done, fatal)
            for m in mods:
                with open(m.path, "w", encoding="utf-8") as fh:
                    m.opened = True
                    run_module(m, rec, fh, done, fatal, now, half, held)
        except BaseException as e:          # noqa: BLE001 -- recorded, then re-raised
            aborted = e
            raise
        finally:
            # cancel_futures, so a run being torn down -- Ctrl-C, a closed laptop, a
            # fatal out of an adapter -- stops asking hosts it has not reached yet. The
            # hosts already in flight are waited for: a thread part-way through writing a
            # venue file has to finish, and wait=True is what makes the atomic write mean
            # something.
            pool.shutdown(wait=True, cancel_futures=True)
            rec.remove()
            for m in mods:
                if not m.done:
                    # A module the run never reached still gets its contract line, and it
                    # is a failure: the alternative is its previous committed log standing
                    # at exit=0 and the run reading as a success. The line replaces that
                    # log rather than joining it, or check_runs.py would read the last
                    # run's failures as this run's cause (audit C4). A module stopped
                    # part-way keeps what this run wrote into it.
                    with open(m.path, "a" if m.opened else "w", encoding="utf-8") as fh:
                        fh.write(f"[run] {m.name}: the run stopped before this module was "
                                 f"published: {aborted!r}\nexit=1\n")
            # The cloud half's combined venue file, from the provider files as they now
            # stand, whatever this run managed to publish, an aborted run included.
            run.write_venuelists(run.OUT, venuelists.halves_of([it.site for it in items]),
                                 stream=top)
            report(top, mods, items, groups, workers, started, held, aborted)
    return 0 if all(m.tally.code() == 0 for m in mods) else 1


def report(top, mods, items, groups, workers, started, held, aborted):
    """The run's own log: what it read, what each module exited with, and what it held."""
    elapsed = time.monotonic() - started
    fetched = [it for it in items if it.started is not None and it.finished is not None]
    print(f"[cloud] {len(mods)} module(s), {len(items)} site(s), {len(groups)} host "
          f"group(s), pool of {min(workers, len(groups) or 1)}", file=top)
    for m in mods:
        print(f"[cloud] {m.name}: exit={m.tally.code() if m.done else 1}", file=top)
    print(f"[cloud] {elapsed:.1f}s wall, "
          f"{sum(it.finished - it.started for it in fetched):.1f}s of fetching added up "
          f"across workers that overlap, {len(fetched)} site(s) fetched", file=top)
    print(f"[cloud] held at most {held.sites} fetched site(s) and {held.bytes} byte(s) of "
          f"captured log waiting for publication", file=top)
    if aborted is not None:
        print(f"[cloud] stopped early: {aborted!r}", file=top)
    code = 1 if aborted is not None else (0 if all(m.tally.code() == 0 for m in mods) else 1)
    print(f"exit={code}", file=top)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
