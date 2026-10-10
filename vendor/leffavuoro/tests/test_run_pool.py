"""run.py reads unrelated hosts at once and one host's sites one after the other.

Serialising across hosts cost eTiketti about 3.5 minutes of a run. The pool's unit is the
host, not the site: two of Nexxo's sites share kinoaurora.fi and two more share
kinohirvi.fi, and reading either pair concurrently would double the request rate at one
cinema's server. Everything talks to real HTTP servers on localhost, one per host, because
overlap is the property under test.
"""
import contextlib
import http.server
import importlib
import io
import json
import os
import pathlib
import sys
import tempfile
import threading
import time
import unittest

import _ctx                                                # noqa: F401
import _no_sleep as no_sleep
import common
import run
import synmerge


NOW = "2026-08-30T12:00:00+00:00"
DELAY = 0.05          # per request, so overlap is measurable without a slow suite


class Handler(http.server.BaseHTTPRequestHandler):
    """Answers anything, slowly, and records when it started and finished."""
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        started = time.monotonic()
        time.sleep(self.server.delay)
        with self.server.lock:
            self.server.log.append((self.server.netloc, self.path,
                                    started, time.monotonic()))
        body = b"ok"
        self.send_response(200)
        # What every eTiketti and Nexxo origin sends, so `miss` and `nostore`
        # are both exercised and nothing is written to the validator cache.
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class Hosts:
    """A set of local servers, each its own netloc, sharing one request log."""

    def __init__(self, count, delay=DELAY):
        self.log, self.lock, self.servers = [], threading.Lock(), []
        for _ in range(count):
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            srv.daemon_threads = True
            srv.log, srv.lock, srv.delay = self.log, self.lock, delay
            srv.netloc = f"127.0.0.1:{srv.server_address[1]}"
            # serve_forever's default half-second poll is what shutdown() has to wait
            # out, and this file starts and stops a few dozen servers.
            threading.Thread(target=srv.serve_forever, args=(0.01,),
                             daemon=True).start()
            self.servers.append(srv)

    def base(self, n):
        return f"http://{self.servers[n].netloc}"

    def close(self):
        for srv in self.servers:
            srv.shutdown()
            srv.server_close()

    def spans(self, provider):
        """Every request one site made. -> [(start, end)] by wall clock."""
        with self.lock:
            return [(a, b) for _, path, a, b in self.log
                    if path.startswith(f"/{provider}/")]


def overlap(spans_a, spans_b):
    """True if any request of one site was in flight while one of the other was."""
    return any(a0 < b1 and b0 < a1 for a0, a1 in spans_a for b0, b1 in spans_b)


def show(title, start="2026-08-30T18:00:00+03:00", syn=""):
    """A show meeting common.Show, blank where the test does not care; the fake adapter
    stamps `venue` and `provider` the way a real one fills them."""
    s = {k: ("" if t is str else False) for k, t in common.Show.__annotations__.items()}
    s.update(eventId=title.lower().replace(" ", "-"), title=title, start=start,
             url="https://example.test/x")
    if syn:
        s["_syn"] = syn
    return s


def site(provider, base, venues=1, **extra):
    return dict(provider=provider, base=base, label=provider.title(),
                venues=[{"id": f"{provider}-{i}", "name": f"{provider} {i}",
                         "short": f"{provider} {i}", "city": "Espoo"}
                        for i in range(venues)], **extra)


class PoolMod:
    """Stands in for an adapter, and fetches: SITES plus fetch_site.

    The requests are what the pool has to keep apart, so they go over the wire. `stagger`
    makes sites finish out of SITES order, which is what a buffered log has to survive.
    """
    __name__ = "poolmod"
    requests = 2
    stagger = {}
    fail = ()
    empty = ()
    syn = False
    shared = False        # True, or the providers that also publish one title in common
    chatty = False

    def __init__(self, sites, **kw):
        self.SITES = sites
        self.__dict__.update(kw)

    def fetch_site(self, site):
        prov = site["provider"]
        for n in range(self.requests):
            if self.chatty:
                print(f"[{prov}] out {n}")
                print(f"[{prov}] err {n}", file=sys.stderr)
            common.fetch(f"{site['base']}/{prov}/p{n}", cache=True)
            time.sleep(self.stagger.get(prov, 0.0))
        if prov in self.fail:
            raise RuntimeError("connection reset")
        if prov in self.empty:
            raise common.EmptyProgramme("the listing renders its empty state")
        out = {v["id"]: [show(f"{prov} film",
                              syn=f"{prov} synopsis" if self.syn else "")]
               for v in site["venues"]}
        if self.shared is True or prov in (self.shared or ()):
            for shows in out.values():
                shows.append(show("Shared Film", syn=f"{prov} synopsis"))
        for vid, shows in out.items():
            for s in shows:
                s.update(venue=vid, provider=prov)
        return out


class PoolTestCase(unittest.TestCase):
    """A temporary data directory, a private validator cache, and counters at zero."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = pathlib.Path(tmp.name)
        for mod, attr, value in ((run, "OUT", self.out),
                                 (common, "CACHE_DIR", self.out / ".http-cache")):
            saved = getattr(mod, attr)
            setattr(mod, attr, value)
            self.addCleanup(lambda m=mod, a=attr, v=saved: setattr(m, a, v))
        self.reset_counters()

    def reset_counters(self):
        with common._lock:
            common._stats.update(hit=0, miss=0, stored=0, nostore=0)
            common._throttle.update(asked=0, waited=0.0, refused=0)
            common._diag_seen.clear()

    def hosts(self, count, delay=DELAY):
        h = Hosts(count, delay)
        self.addCleanup(h.close)
        return h

    def drain(self, mod, workers=None, quiet=True):
        """run_sites to completion. -> ([(label, result, error)], captured output)."""
        buf = io.StringIO()
        sink = (contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf))
        with sink[0], sink[1]:
            got = list(run.run_sites(mod, mod.SITES, NOW, workers=workers))
        if not quiet:
            self.captured = buf.getvalue()
        return got, buf.getvalue()

    def main(self, mod, argv=("poolmod", "--half", "all")):
        """run.main with the fake module importable. -> (exit code, merged output)."""
        real = importlib.import_module
        importlib.import_module = lambda n: mod if n == "poolmod" else real(n)
        self.addCleanup(lambda: setattr(importlib, "import_module", real))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = run.main(list(argv))
        return code, buf.getvalue()


# --- the courtesy: one host is read by one thread ------------------------------------

class HostPacingTest(PoolTestCase):
    def test_two_sites_on_one_host_never_overlap(self):
        """The property the whole design turns on. Keyed on the site instead of the host
        these two would be fetched at once, which is twice the rate the adapter's sleep
        is pacing for, at one cinema's server."""
        h = self.hosts(2)
        mod = PoolMod([site("shared_a", h.base(0)),
                       site("shared_b", h.base(0)),
                       site("alone", h.base(1))])
        self.drain(mod)
        self.assertFalse(overlap(h.spans("shared_a"), h.spans("shared_b")),
                         "two sites on one host were read at the same time")

    def test_a_second_host_is_read_at_the_same_time(self):
        """Otherwise the test above would pass on a pool that never pools."""
        h = self.hosts(2)
        mod = PoolMod([site("shared_a", h.base(0)),
                       site("shared_b", h.base(0)),
                       site("alone", h.base(1))])
        self.drain(mod)
        self.assertTrue(overlap(h.spans("shared_a") + h.spans("shared_b"),
                                h.spans("alone")),
                        "unrelated hosts were still read one after the other")

    def test_the_shared_host_is_still_read_in_sites_order(self):
        """A group is one thread, so its sites keep the order SITES gives them."""
        h = self.hosts(2)
        mod = PoolMod([site("shared_a", h.base(0)),
                       site("shared_b", h.base(0)),
                       site("alone", h.base(1))])
        self.drain(mod)
        self.assertLess(max(e for _, e in h.spans("shared_a")),
                        min(s for s, _ in h.spans("shared_b")))

    def test_the_host_is_where_the_data_comes_from_not_where_a_visitor_is_sent(self):
        """Bio Säde's showtimes come from kinohirvi.fi and its ticket links go to
        biosade.fi. Keyed on `site` the two kinohirvi.fi sites would come apart."""
        h = self.hosts(2)
        mod = PoolMod([site("shared_a", h.base(0), site=h.base(1)),
                       site("shared_b", h.base(0))])
        self.drain(mod)
        self.assertFalse(overlap(h.spans("shared_a"), h.spans("shared_b")))

    def test_a_site_with_no_base_shares_a_group_rather_than_being_assumed_alone(self):
        """Several adapters keep the host inside fetch_site, where host_of cannot read
        it. Unknown has to mean "read these one at a time"."""
        groups = run.host_groups([{"provider": "a", "venues": []},
                                  {"provider": "b", "venues": []}])
        self.assertEqual(len(groups), 1)


class WorkerTerminationTest(PoolTestCase):
    """A `SystemExit` out of a worker has to reach the caller.

    `except Exception` per site is the isolation a pool needs. Anything else ended a
    sequential run and has to end this one, and that does not happen by itself: the
    thread dies, ThreadPoolExecutor puts the exception on a future nobody reads, and the
    run carries on and publishes. Recorded and re-raised by the reader instead -- and not
    written into the log as a provider that failed, because it is not one.
    """

    class Exiting(PoolMod):
        """Raises SystemExit for one site, the way `sys.exit()` in adapter code would."""
        exiting = ()

        def fetch_site(self, site):
            if site["provider"] in self.exiting:
                raise SystemExit(3)
            return PoolMod.fetch_site(self, site)

    def test_it_reaches_the_caller_instead_of_a_future_nobody_reads(self):
        h = self.hosts(3, delay=0)
        mod = self.Exiting([site(f"p{i}", h.base(i)) for i in range(3)],
                           requests=1, exiting=("p1",))
        with self.assertRaises(SystemExit) as caught:
            self.main(mod)
        self.assertEqual(caught.exception.code, 3, "a different exception got through")

    def test_it_is_not_written_into_the_log_as_a_provider_failing(self):
        h = self.hosts(3, delay=0)
        mod = self.Exiting([site(f"p{i}", h.base(i)) for i in range(3)],
                           requests=1, exiting=("p1",))
        buf = io.StringIO()
        real = importlib.import_module
        importlib.import_module = lambda n: mod if n == "poolmod" else real(n)
        self.addCleanup(lambda: setattr(importlib, "import_module", real))
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            with self.assertRaises(SystemExit):
                run.main(["poolmod", "--half", "all"])
        self.assertNotIn("FAILED", buf.getvalue())
        self.assertNotIn("not read", buf.getvalue())

    def test_a_host_with_sites_queued_behind_the_dead_one_does_not_hang(self):
        """Two sites on one host share a thread, so the second is only reachable through
        the first, and its reader is waiting on an event that thread will never reach.
        Run on a watchdog, so a regression fails the suite instead of stopping it."""
        h = self.hosts(2, delay=0)
        mod = self.Exiting([site("shared_a", h.base(0)), site("shared_b", h.base(0)),
                            site("alone", h.base(1))],
                           requests=1, exiting=("shared_a",))
        done, box = threading.Event(), {}

        def go():
            try:
                with self.assertRaises(SystemExit):
                    self.main(mod)
                box["ok"] = True
            finally:
                done.set()

        threading.Thread(target=go, daemon=True).start()
        self.assertTrue(done.wait(30), "the run hung on a site nobody released")
        self.assertTrue(box.get("ok"), "SystemExit did not reach the caller")

    def test_an_ordinary_exception_is_still_isolated_and_still_returns(self):
        """The distinction the restructure turns on: one of these ends the run and the
        other is a cinema that could not be fetched."""
        h = self.hosts(2, delay=0)
        mod = self.Exiting([site("p0", h.base(0)), site("p1", h.base(1))],
                           requests=1, fail=("p0",))
        code, text = self.main(mod)
        self.assertEqual(code, 1)
        self.assertIn("[p0] FAILED: connection reset", text)
        self.assertTrue((self.out / "venues-p1.json").exists())


class TeardownTest(PoolTestCase):
    def test_abandoning_a_run_stops_it_reading_hosts_it_never_reached(self):
        """A run being torn down -- Ctrl-C, a closed laptop -- should not keep asking
        cinemas for pages nobody is going to read. Three hosts through a pool of one:
        after the first site is drained the generator is closed, and the third host must
        never be reached. The second may already be in flight and is waited for, because
        a thread part-way through writing a venue file has to finish.
        """
        h = self.hosts(3, delay=0.3)
        mod = PoolMod([site(f"p{i}", h.base(i)) for i in range(3)], requests=1)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            gen = run.run_sites(mod, mod.SITES, NOW, workers=1)
            first = next(gen)
            gen.close()
        self.assertEqual(first[0], "p0")
        self.assertEqual(len(h.spans("p0")), 1, "the first host was not read at all")
        self.assertEqual(len(h.spans("p2")), 0,
                         "a host was read after the run had been abandoned")


class HostGroupsAgainstTheRealSitesTest(unittest.TestCase):
    """Asserted against the live SITES rather than a fixture, the way test_run_routing
    checks routing against the live registry: a fixture cannot go stale in the way that
    matters here, which is a new cinema landing on a host another one already uses."""

    def test_no_two_groups_of_a_module_share_a_host(self):
        for name in ("etiketti", "nexxo", "biorex", "gilda", "orion", "riviera",
                     "engel", "kinoakseli"):
            with self.subTest(module=name):
                mod = importlib.import_module(name)
                groups = run.host_groups(mod.SITES)
                hosts = [run.host_of(s) for g in groups for _, s in g[:1]]
                self.assertEqual(len(hosts), len(set(hosts)))

    def test_the_two_nexxo_pairs_that_share_a_host_are_grouped(self):
        """Measured 2026-09-01: eight sites, six hosts. kinoaurora.fi serves kinoaurora
        and kinometso; kinohirvi.fi serves kinohirvi and biosade."""
        nexxo = importlib.import_module("nexxo")
        groups = run.host_groups(nexxo.SITES)
        together = {frozenset(s["provider"] for _, s in g) for g in groups}
        self.assertEqual(len(groups), 6)
        self.assertIn(frozenset({"kinoaurora", "kinometso"}), together)
        self.assertIn(frozenset({"kinohirvi", "biosade"}), together)

    def test_every_etiketti_site_is_its_own_host(self):
        """The property the pool size is argued from: no eTiketti site shares a host
        with another, so the module's sites are all read concurrently. Asserted as
        one group per site rather than against a number, which went stale twice as
        the sweep grew."""
        etiketti = importlib.import_module("etiketti")
        self.assertEqual(len(run.host_groups(etiketti.SITES)), len(etiketti.SITES))


# --- the counters are the committed log's evidence -----------------------------------

class CounterTest(PoolTestCase):
    """What the `[run] http:` and `[run] throttled:` lines report has to stay exact when
    the requests behind them were made from several threads.

    There is no test here that the lock itself is needed, because on CPython with
    the GIL it is not: eight threads and 1.6 million `_stats["miss"] += 1` lose exactly
    zero, since the eval loop does not offer to switch inside that stretch of bytecode.
    See the comment on common._lock for why it is there anyway. What these two do is pin
    the totals, which is the property the committed log rests on and the one a
    later change to the accounting would break.
    """

    def test_a_pooled_run_counts_every_request_it_made(self):
        """Six sites, six hosts, eight requests each: the `[run] http:` line has to
        report 48, because that line is the pipeline's evidence for how it fetched."""
        h = self.hosts(6, delay=0)
        mod = PoolMod([site(f"p{i}", h.base(i)) for i in range(6)], requests=8)
        self.drain(mod)
        stats = common.cache_stats()
        self.assertEqual(stats["miss"], 48)
        self.assertEqual(stats["nostore"], 48)
        self.assertEqual(len(h.log), 48)

    def test_four_throttled_hosts_report_exactly_what_they_waited(self):
        """Four hosts all answering 429 with `Retry-After: 1`, at once.

        `asked` counts every one of them and `waited` counts only the seconds
        sat out: three attempts per site, of which the last does not sleep because there
        is no retry after it. Two per site, eight in total. Charging the last attempt too
        would report a run as having waited a third longer than it did.
        """
        class Throttling(Handler):
            def do_GET(self):
                with self.server.lock:
                    self.server.log.append((self.server.netloc, self.path, 0.0, 0.0))
                self.send_response(429)
                self.send_header("Retry-After", "1")
                self.send_header("Content-Length", "0")
                self.end_headers()

        h = self.hosts(4, delay=0)
        for srv in h.servers:
            srv.RequestHandlerClass = Throttling
        no_sleep.patch(self, common)            # counted, not sat out
        mod = PoolMod([site(f"p{i}", h.base(i)) for i in range(4)], requests=1)
        got, _ = self.drain(mod)
        self.assertEqual([e is not None for _, _, e in got], [True] * 4)
        t = common.throttle_stats()
        self.assertEqual(t["asked"], 12, "three attempts each, all four sites")
        self.assertEqual(t["waited"], 8.0, "two sleeps a site, not three")
        self.assertEqual(t["refused"], 0)
        self.assertLessEqual(t["waited"], common.RETRY_AFTER_BUDGET)


# --- the committed log is read top to bottom -----------------------------------------

def tags(text):
    """The `[provider]` at the head of every line that has one, in order."""
    out = []
    for line in text.splitlines():
        if line.startswith("[") and "]" in line:
            out.append(line[1:line.index("]")])
    return out


def blocks(tag_list):
    """The tags with runs collapsed: ["a","a","b","a"] -> ["a","b","a"]."""
    out = []
    for t in tag_list:
        if not out or out[-1] != t:
            out.append(t)
    return out


class LogOrderTest(PoolTestCase):
    SITES_ORDER = ["p0", "p1", "p2", "p3"]

    def chatty_mod(self, h):
        # p0 is the slowest, so completion order is the reverse of SITES order and a log
        # printed as sites finish would come out backwards as well as interleaved.
        return PoolMod([site(f"p{i}", h.base(i)) for i in range(4)],
                       chatty=True, requests=3,
                       stagger={"p0": 0.03, "p1": 0.02, "p2": 0.01, "p3": 0.0})

    def test_each_site_is_one_contiguous_block_in_sites_order(self):
        h = self.hosts(4, delay=0)
        _, text = self.drain(self.chatty_mod(h))
        seen = [t for t in blocks(tags(text)) if t in self.SITES_ORDER]
        self.assertEqual(seen, self.SITES_ORDER)

    def test_stderr_lines_stay_inside_their_own_site(self):
        """The workflow merges the two streams (`> run-$m.log 2>&1`), so a buffer that
        took only stdout would move half the lines. Captured into one buffer here for the
        same reason, and asserted on the slice between a site's first and last line: a
        site's own lines being in order proves nothing on its own, since one site is one
        thread either way. What has to hold is that nobody else's line is in among them.
        """
        h = self.hosts(4, delay=0)
        _, text = self.drain(self.chatty_mod(h))
        lines = [l for l in text.splitlines() if l.startswith("[p")]
        for prov in self.SITES_ORDER:
            mine = [i for i, l in enumerate(lines) if l.startswith(f"[{prov}]")]
            block = lines[mine[0]:mine[-1] + 1]
            self.assertEqual(len(block), len(mine),
                             f"another site's output landed inside {prov}'s block")
            self.assertEqual(block[:6], [f"[{prov}] out 0", f"[{prov}] err 0",
                                         f"[{prov}] out 1", f"[{prov}] err 1",
                                         f"[{prov}] out 2", f"[{prov}] err 2"])

    def test_the_merged_log_is_ordered_by_the_writes_and_not_by_the_buffers(self):
        """`> run-$m.log 2>&1` hands the two streams one file description between them,
        and Python line-buffers stderr while block-buffering a redirected stdout. So a
        stderr line written last can land first in the file, which is why the committed
        run-nexxo.log opens with an empty-venue notice printed by the eighth site of
        eight. Reproduced with a dup'd descriptor, which is what the shell does, rather
        than with two StringIOs, where flushing is a no-op and the bug cannot appear.
        """
        h = self.hosts(4, delay=0)
        path = self.out / "merged.log"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        out = os.fdopen(fd, "w", buffering=8192)
        err = os.fdopen(os.dup(fd), "w", buffering=1)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                mod = self.chatty_mod(h)
                list(run.run_sites(mod, mod.SITES, NOW))
        finally:
            out.flush()
            err.flush()
            out.close()
            err.close()
        lines = [l for l in path.read_text(encoding="utf-8").splitlines()
                 if l.startswith("[p")]
        self.assertEqual(lines[:6], ["[p0] out 0", "[p0] err 0", "[p0] out 1",
                                     "[p0] err 1", "[p0] out 2", "[p0] err 2"])
        self.assertEqual([t for t in blocks(tags("\n".join(lines)))],
                         self.SITES_ORDER)

    def test_the_runs_own_lines_still_land_inside_the_site_they_are_about(self):
        """`[label] no programme published` and `[label] FAILED` are printed by main
        after the site's own output has been replayed, not after the whole pool."""
        h = self.hosts(3, delay=0)
        mod = PoolMod([site(f"p{i}", h.base(i)) for i in range(3)],
                      chatty=True, requests=1, empty=("p1",),
                      stagger={"p0": 0.02, "p1": 0.0, "p2": 0.0})
        _, text = self.main(mod)
        seen = blocks([t for t in tags(text) if t in ("p0", "p1", "p2")])
        self.assertEqual(seen, ["p0", "p1", "p2"])
        self.assertIn("[p1] no programme published:", text)


# --- one site failing is one failure -------------------------------------------------

class FailureAccountingTest(PoolTestCase):
    def test_a_failing_site_does_not_take_the_others_down(self):
        h = self.hosts(4, delay=0)
        mod = PoolMod([site(f"p{i}", h.base(i)) for i in range(4)],
                      requests=1, fail=("p1",))
        code, text = self.main(mod)
        self.assertEqual(code, 1)
        self.assertIn("[p1] FAILED: connection reset", text)
        self.assertIn("3 venues, 3 showtimes", text)
        self.assertIn("1 failures", text)
        for prov in ("p0", "p2", "p3"):
            self.assertTrue((self.out / f"venues-{prov}.json").exists())

    def test_two_sites_on_one_host_both_run_when_the_first_fails(self):
        """They share a thread, so a raise that escaped the worker would silently drop
        every site queued behind it."""
        h = self.hosts(2, delay=0)
        mod = PoolMod([site("shared_a", h.base(0)), site("shared_b", h.base(0)),
                       site("alone", h.base(1))], requests=1, fail=("shared_a",))
        code, text = self.main(mod)
        self.assertEqual(code, 1)
        self.assertIn("1 failures", text)
        self.assertTrue((self.out / "venues-shared_b.json").exists())

    def test_an_empty_programme_is_empty_and_not_a_failure(self):
        h = self.hosts(3, delay=0)
        mod = PoolMod([site(f"p{i}", h.base(i)) for i in range(3)],
                      requests=1, empty=("p2",))
        code, text = self.main(mod)
        self.assertEqual(code, 0)
        self.assertIn("1 with no programme, 0 failures", text)

    def test_a_site_that_wrote_nothing_is_still_one_failure_not_two(self):
        """`not v` and a raise are two different routes to the same count, and a pool
        that reported both would double it."""
        h = self.hosts(2, delay=0)
        mod = PoolMod([site("p0", h.base(0)), site("p1", h.base(1))],
                      requests=1, fail=("p1",))
        _, text = self.main(mod)
        self.assertIn("1 failures", text)


# --- films-extra.json is one file for the whole run ----------------------------------

class SynopsisMergeTest(PoolTestCase):
    def slow_merge_writes(self):
        """Widen the read-modify-write window merge() holds the lock across.

        Without it the race is real but occasional; with it, every site reads the file
        before any site has written it, so an unserialised merge loses all but the last
        synopsis every time. The delay is on the write of films-extra.json alone -- the
        per-venue writes are single-writer and are not what is under test.
        """
        real = common.write_json

        def slow(path, obj, **kw):
            if pathlib.Path(path).name == "films-extra.json":
                time.sleep(0.05)
            return real(path, obj, **kw)

        common.write_json = slow
        self.addCleanup(lambda: setattr(common, "write_json", real))

    def shared_run(self, workers):
        """One film published by all three sites with three different blurbs, the first
        site slowest so it finishes last. -> (the parsed document, completion order)."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = pathlib.Path(tmp.name)
        h = self.hosts(3, delay=0)
        h.servers[0].delay = 0.25          # SITES order and completion order disagree
        h.servers[1].delay = 0.05
        mod = PoolMod([site(f"p{i}", h.base(i)) for i in range(3)],
                      requests=2, syn=True, shared=True)
        saved = run.OUT
        run.OUT = out
        try:
            self.drain(mod, workers=workers)
        finally:
            run.OUT = saved
        finished = sorted(("p0", "p1", "p2"),
                          key=lambda p: max(e for _, e in h.spans(p)))
        return json.loads((out / "films-extra.json").read_text()), finished

    def test_the_same_film_from_two_sites_takes_the_earlier_site_s_synopsis(self):
        """Two chains showing one film, each with its own Finnish blurb.

        Fill-if-empty makes the winner "whichever host answered first", which with a pool
        is a property of the network rather than of the data. Measured 2026-09-01 with
        one slow site and one fast one: `workers=1` published the first site's synopsis
        and `workers=2` published the second's, from identical input. The winner has to
        be SITES order, which is what the sequential loop produced, at any pool size.
        """
        one, order_one = self.shared_run(1)
        self.reset_counters()
        many, order_many = self.shared_run(8)
        self.assertEqual(order_many[-1], "p0",
                         "the pooled run did not finish out of SITES order, so this "
                         "fixture is not exercising the race it exists for")
        self.assertEqual(one["films"]["shared film"]["s"]["fi"], "p0 synopsis")
        self.assertEqual(many["films"]["shared film"]["s"]["fi"], "p0 synopsis")
        # Compared as documents. Every value is identical at either pool size; what a
        # pool still decides is the position a film seen for the first time on this run
        # takes among the other new ones, which JSON object order does not carry meaning
        # for and which no consumer reads.
        self.assertEqual(one, many, "the published document depends on the pool size")

    def test_a_later_module_does_not_outrank_an_earlier_one(self):
        """Modules are fetched one after the other, so `reset()` drops a module's claims
        when it is done. Without it the second module's site 0 outranks the first
        module's site 1 and takes a slot that is already settled -- the file's text is no
        longer "the first provider in SITES order" but "the lowest index of any module".
        """
        h = self.hosts(3, delay=0)
        first = PoolMod([site("a0", h.base(0)), site("a1", h.base(1))],
                        requests=1, syn=True, shared=("a1",))
        second = PoolMod([site("b0", h.base(2))],
                         requests=1, syn=True, shared=("b0",))
        self.drain(first)
        self.drain(second)
        films = json.loads((self.out / "films-extra.json").read_text())["films"]
        self.assertEqual(films["shared film"]["s"]["fi"], "a1 synopsis")

    def test_every_site_keeps_its_synopses(self):
        self.slow_merge_writes()
        h = self.hosts(6, delay=0)
        mod = PoolMod([site(f"p{i}", h.base(i)) for i in range(6)],
                      requests=1, syn=True)
        self.drain(mod)
        films = json.loads((self.out / "films-extra.json").read_text())["films"]
        self.assertEqual(len(films), 6, "a site's synopses were overwritten")
        for i in range(6):
            self.assertEqual(films[synmerge.norm(f"p{i} film")]["s"]["fi"],
                             f"p{i} synopsis")


# --- the sequential path is still there ----------------------------------------------

class PoolOfOneTest(PoolTestCase):
    @contextlib.contextmanager
    def frozen_now(self):
        """main() stamps datetime.now() into every file it writes, so two runs are only
        comparable with the clock held still."""
        real = run.datetime

        class Frozen:
            timezone = real.timezone

            class datetime:
                @staticmethod
                def now(tz=None):
                    return real.datetime(2026, 8, 30, 12, 0, 0, tzinfo=tz)

        run.datetime = Frozen
        try:
            yield
        finally:
            run.datetime = real

    def run_with(self, workers):
        """One whole run at this pool size, into its own data directory.

        -> ({filename: contents}, the summary line, everything it printed).
        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = pathlib.Path(tmp.name)
        h = self.hosts(3, delay=0)
        mod = PoolMod([site("shared_a", h.base(0)), site("shared_b", h.base(0)),
                       site("p2", h.base(1)), site("p3", h.base(2))],
                      requests=2, syn=True)
        saved_out, saved_hosts = run.OUT, run.MAX_HOSTS
        run.OUT, run.MAX_HOSTS = out, workers
        try:
            with self.frozen_now():
                _, text = self.main(mod)
        finally:
            run.OUT, run.MAX_HOSTS = saved_out, saved_hosts
        files = {f.name: f.read_text(encoding="utf-8")
                 for f in sorted(out.glob("*.json"))}
        summary = next(l for l in text.splitlines() if l.startswith("[run] poolmod:"))
        return files, summary, text

    def test_a_pool_of_one_writes_the_same_files_and_says_the_same_thing(self):
        one_files, one_summary, one_text = self.run_with(1)
        self.reset_counters()
        many_files, many_summary, many_text = self.run_with(8)
        self.assertEqual(one_summary, many_summary)
        self.assertEqual(sorted(one_files), sorted(many_files))
        self.assertEqual(tags(one_text), tags(many_text))
        for name in one_files:
            if name == "films-extra.json":
                # The one file several sites write, so the order its *new* keys land in
                # follows which site finished first. Keys already in the file keep their
                # place -- setdefault does not move them -- so this is a handful of new
                # films appearing in a different order among themselves on the run that
                # first sees them, and nothing at all on every run after. Compared as a
                # document rather than as bytes for exactly that much difference.
                self.assertEqual(json.loads(one_files[name]),
                                 json.loads(many_files[name]), name)
            else:
                self.assertEqual(one_files[name], many_files[name], name)

    def test_the_pool_size_comes_from_the_environment(self):
        """KINO_MAX_HOSTS, in the style of KINO_PAGE_BUDGET: forcing it to 1 is how the
        sequential path stays reachable without an edit."""
        saved = os.environ.get("KINO_MAX_HOSTS")
        os.environ["KINO_MAX_HOSTS"] = "3"
        self.addCleanup(lambda: (os.environ.__setitem__("KINO_MAX_HOSTS", saved)
                                 if saved is not None
                                 else os.environ.pop("KINO_MAX_HOSTS", None)))
        try:
            self.assertEqual(importlib.reload(run).MAX_HOSTS, 3)
        finally:
            os.environ.pop("KINO_MAX_HOSTS", None)
            importlib.reload(run)


if __name__ == "__main__":
    unittest.main()
