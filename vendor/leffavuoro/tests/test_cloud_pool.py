"""run_cloud.py reads every module's sites through one pool, and publishes them in order.

The cloud half ran `run.py "$m"` once per module, so two modules never overlapped however
many hosts were idle. This is the same host-keyed pool over every module at once, and the
properties it has to keep are the ones the per-module processes gave for free:

- one host is read by one thread, **across modules** as well as inside one;
- `films-extra.json` has one writer and the earlier site in SITES order still wins a
  synopsis, at any pool size;
- each module's committed log holds its own sites, its own counters and its own `exit=N`;
- a module's Retry-After budget is its own, because it was its own process.

Everything that has to overlap or not overlap talks to real HTTP servers on localhost, one
per host, reusing the machinery in `test_run_pool`: overlap is the property under test and
a mock would encode the answer.
"""
import contextlib
import importlib
import io
import json
import pathlib
import re
import tempfile
import threading
import time
import unittest

import _ctx                                                # noqa: F401
import _no_sleep as no_sleep
import common
import registry
import run
import run_cloud
import test_run_pool as P
import venuelists


def module(name, *sites, **kw):
    """A fake adapter module the coordinator can import by name."""
    mod = P.PoolMod(list(sites), **kw)
    mod.__name__ = name
    return mod


def logs_of(directory):
    """-> {log name without run-/.log: its text}."""
    return {p.name[4:-4]: p.read_text(encoding="utf-8")
            for p in pathlib.Path(directory).glob("run-*.log")}


def concurrency(log):
    """The most requests in flight at once, from the servers' own timings. -> int."""
    events = sorted([(a, 1) for _, _, a, _ in log] + [(b, -1) for _, _, _, b in log])
    live = peak = 0
    for _, delta in events:
        live += delta
        peak = max(peak, live)
    return peak


# The two lines that cannot be equal between two runs of the same fixture: durations, and
# the hosts, which here are 127.0.0.1 on whatever ports the servers were given. Both are
# asserted on directly elsewhere in this file rather than being dropped and forgotten.
VARIABLE = ("[run] timing:", "[run] hosts:")


def comparable(text):
    """A module log with those lines removed."""
    return "\n".join(l for l in text.splitlines() if not l.startswith(VARIABLE))


class CloudTestCase(P.PoolTestCase):
    """A temporary data directory, a temporary logs directory, and counters at zero."""

    def setUp(self):
        super().setUp()
        self.logs = self.out / "logs"
        self.logs.mkdir()
        saved = run_cloud.LOGS
        run_cloud.LOGS = self.logs
        self.addCleanup(lambda: setattr(run_cloud, "LOGS", saved))
        common.reset_accounting()
        self.addCleanup(common.reset_accounting)

    def install(self, mods):
        """Make these fake modules importable and registry.modules name them, in order."""
        names = [m.__name__ for m in mods]
        by_name = {m.__name__: m for m in mods}
        real_import, real_modules = importlib.import_module, registry.modules
        importlib.import_module = lambda n: by_name.get(n) or real_import(n)
        registry.modules = lambda where=None: list(names)
        self.addCleanup(lambda: setattr(importlib, "import_module", real_import))
        self.addCleanup(lambda: setattr(registry, "modules", real_modules))
        return names

    def cloud(self, mods, workers=None, half="all"):
        """One whole coordinator run. -> (exit code, {module: log text})."""
        self.install(mods)
        argv = ["--where", half] + (["--workers", str(workers)] if workers else [])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = run_cloud.main(argv)
        return code, logs_of(self.logs)


# --- the courtesy holds across modules as well as inside one ---------------------------

class CrossModuleHostTest(CloudTestCase):
    """The property the whole design turns on, now that two modules can be in flight."""

    def two_modules(self, h):
        # a_shared and b_shared are on one host and in different modules; a_alone and
        # b_alone are on hosts of their own.
        return [module("mod_a", P.site("a_shared", h.base(0)), P.site("a_alone", h.base(1))),
                module("mod_b", P.site("b_shared", h.base(0)), P.site("b_alone", h.base(2)))]

    def test_one_host_is_never_read_by_two_modules_at_once(self):
        h = self.hosts(3)
        self.cloud(self.two_modules(h))
        self.assertFalse(P.overlap(h.spans("a_shared"), h.spans("b_shared")),
                         "two modules read one host at the same time, at twice the rate "
                         "its adapter paces for")

    def test_two_modules_on_different_hosts_do_overlap(self):
        """Otherwise the test above would pass on a coordinator that never pools, and the
        whole change would buy nothing."""
        h = self.hosts(3)
        self.cloud(self.two_modules(h))
        self.assertTrue(P.overlap(h.spans("a_alone"), h.spans("b_alone")),
                        "two modules were still read one after the other")

    def test_a_module_starts_before_the_previous_one_has_finished(self):
        """The plainest statement of the same thing: the per-module processes could not do
        this, because the next one did not exist until the previous had exited."""
        h = self.hosts(3)
        self.cloud(self.two_modules(h))
        first_a = min(s for s, _ in h.spans("a_shared") + h.spans("a_alone"))
        last_a = max(e for _, e in h.spans("a_shared") + h.spans("a_alone"))
        first_b = min(s for s, _ in h.spans("b_alone"))
        self.assertLess(first_b, last_a)
        self.assertGreater(last_a, first_a)

    def test_the_global_ceiling_holds_across_every_module(self):
        """One ceiling for the run, not one per module multiplied by the module count."""
        h = self.hosts(8, delay=0.05)
        mods = [module(f"mod_{i}", *(P.site(f"p{i}{j}", h.base(i * 2 + j))
                                     for j in range(2)))
                for i in range(4)]
        self.cloud(mods, workers=3)
        self.assertLessEqual(concurrency(h.log), 3,
                             "more hosts were read at once than the ceiling allows")

    def test_a_pool_of_one_reads_nothing_at_the_same_time(self):
        h = self.hosts(4, delay=0.02)
        mods = [module("mod_a", P.site("a0", h.base(0)), P.site("a1", h.base(1))),
                module("mod_b", P.site("b0", h.base(2)), P.site("b1", h.base(3)))]
        self.cloud(mods, workers=1)
        self.assertEqual(concurrency(h.log), 1)


class GroupingTest(unittest.TestCase):
    """The grouping itself, away from the wire: what lands in a group and in what order."""

    @staticmethod
    def two(*specs):
        """-> work items for modules built from (name, [(provider, base)]) pairs."""
        class M:
            __name__ = "m"
        mods = []
        for order, (name, sites) in enumerate(specs):
            m = run_cloud.Module(order, name)
            m.mod = M
            m.sites = [dict({"provider": p, "venues": []},
                            **({"base": b} if b else {})) for p, b in sites]
            mods.append(m)
        return run_cloud.work_items(mods)

    def test_two_modules_on_one_host_share_a_group_and_keep_module_order(self):
        items = self.two(("a", [("a0", "https://one.test"), ("a1", "https://two.test")]),
                         ("b", [("b0", "https://one.test")]))
        groups = run_cloud.host_groups(items)
        self.assertEqual([[i.label for i in g] for g in groups],
                         [["a0", "b0"], ["a1"]])

    def test_publication_order_is_module_order_then_site_order(self):
        items = self.two(("a", [("a0", "https://one.test"), ("a1", "https://two.test")]),
                         ("b", [("b0", "https://three.test")]))
        self.assertEqual([i.label for i in items], ["a0", "a1", "b0"])
        self.assertEqual([i.order for i in items], [0, 1, 0])
        self.assertEqual([i.index for i in items], [0, 1, 2])

    def test_a_declared_secondary_host_joins_the_sites_that_read_it(self):
        """A differing `base` does not prove two upstreams independent. A site that says
        which other host it reads has to be serialised against whoever else reads it, and
        the groups are the connected components rather than one key per site."""
        items = self.two(("a", [("a0", "https://one.test"), ("a1", "https://two.test")]),
                         ("b", [("b0", "https://three.test")]))
        items[1].site["reads"] = ("three.test",)
        groups = run_cloud.host_groups(items)
        self.assertEqual([[i.label for i in g] for g in groups], [["a0"], ["a1", "b0"]])

    def test_a_secondary_host_may_be_written_as_a_url_or_as_a_bare_host(self):
        for form in ("three.test", "https://three.test/websales/show/"):
            with self.subTest(form=form):
                self.assertIn("three.test",
                              run.hosts_of({"base": "https://two.test", "reads": (form,)}))

    def test_two_declared_hosts_merge_two_groups_that_were_already_apart(self):
        """The case a one-key-per-site grouping cannot express: the joining site arrives
        after both groups exist, so they have to be merged rather than chosen between."""
        at = run.group_indices([("one.test",), ("two.test",), ("one.test", "two.test")])
        self.assertEqual(len(set(at)), 1)
        self.assertEqual(run.group_indices([("one.test",), ("two.test",)]), [0, 1])

    def test_a_site_with_no_base_shares_a_group_rather_than_being_assumed_alone(self):
        """Unknown has to mean "read these one at a time". Treating an unknown host as its
        own would put two requests at one server at once."""
        class M:
            __name__ = "m"
        a = run_cloud.Module(0, "a")
        a.mod = M
        b = run_cloud.Module(1, "b")
        b.mod = M
        a.sites = [{"provider": "a", "venues": []}]
        b.sites = [{"provider": "b", "venues": []}]
        items = run_cloud.work_items([a, b])
        self.assertEqual(len(run_cloud.host_groups(items)), 1)

    def test_a_verified_shared_upstream_puts_two_hosts_in_one_group(self):
        """The mechanism for a conflict that `base` cannot express. Empty in the shipped
        table, so only a fixture reaches it."""
        class M:
            __name__ = "m"
        a = run_cloud.Module(0, "a")
        a.mod = M
        a.sites = [{"provider": "a", "base": "https://one.test", "venues": []},
                   {"provider": "b", "base": "https://two.test", "venues": []}]
        items = run_cloud.work_items([a])
        self.assertEqual(len(run_cloud.host_groups(items)), 2)
        saved = dict(run_cloud.SHARED_UPSTREAMS)
        run_cloud.SHARED_UPSTREAMS["two.test"] = "one.test"
        self.addCleanup(lambda: (run_cloud.SHARED_UPSTREAMS.clear(),
                                 run_cloud.SHARED_UPSTREAMS.update(saved)))
        self.assertEqual(len(run_cloud.host_groups(items)), 1)


class LiveSelectionTest(unittest.TestCase):
    """Asserted against the live registry, like test_run_routing: a fixture cannot go
    stale in the way that matters, which is a new cinema landing on a host or a domain
    another module already reads."""

    def cloud_items(self):
        return run_cloud.work_items(run_cloud.collect(registry.modules("cloud"), "cloud"))

    @staticmethod
    def registrable(host):
        """The last two labels. Approximate -- there is no public-suffix list here -- and
        adequate for the .fi, .com, .org, .info and .ax domains this half reads."""
        parts = host.split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else host

    def test_every_cloud_module_imports_and_selects_sites(self):
        mods = run_cloud.collect(registry.modules("cloud"), "cloud")
        for m in mods:
            with self.subTest(module=m.name):
                self.assertIsNone(m.error)
                self.assertTrue(m.sites, "a cloud module selected no cloud site")

    def test_no_cloud_site_leaves_its_host_inside_the_adapter(self):
        """A site with no `base` shares the conservative group with every other one, which
        would serialise unrelated cinemas across the whole half."""
        missing = [it.label for it in self.cloud_items() if not it.host]
        self.assertEqual(missing, [])

    def test_no_two_modules_read_the_same_registrable_domain(self):
        """What `SHARED_UPSTREAMS` exists for. Two sites of one module sharing a host
        already share a `base` and so a group; two *modules* reaching one operator is the
        case the coordinator introduces, and it must be a decision with evidence rather
        than a side effect of adding a provider. Measured 2026-09-15: none."""
        by_domain = {}
        for it in self.cloud_items():
            by_domain.setdefault(self.registrable(it.host), set()).add(it.module.name)
        shared = {d: sorted(m) for d, m in by_domain.items() if len(m) > 1}
        self.assertEqual(shared, {},
                         "two modules read one registrable domain; verify whether it is "
                         "one upstream and record the answer in run_cloud.SHARED_UPSTREAMS")

    def test_riviera_declares_the_ticket_host_its_price_pass_reads(self):
        """The one secondary host in the registry: prices.run GETs ticket pages on
        tickets.rivieracinemas.fi, which `base` does not name."""
        import riviera
        self.assertIn("tickets.rivieracinemas.fi", run.hosts_of(riviera.SITES[0]))
        self.assertIn("www.rivieracinemas.fi", run.hosts_of(riviera.SITES[0]))

    def test_every_site_that_reads_a_second_host_declares_it(self):
        """The three in the registry, and how each was found: Riviera's ticket host by
        reading the adapter, Kino Regina's by the first run that carried the hosts line
        reporting two where the site declared one, Bio-Kaari's when its ticket pages joined
        the price pass on 2026-10-09."""
        import biokaari
        import regina
        import riviera
        self.assertEqual(sorted(run.hosts_of(riviera.SITES[0])),
                         ["tickets.rivieracinemas.fi", "www.rivieracinemas.fi"])
        self.assertEqual(sorted(run.hosts_of(regina.SITES[0])),
                         ["kauppa.kavi.fi", "kinoregina.fi"])
        self.assertEqual(sorted(run.hosts_of(biokaari.SITES[0])),
                         ["bio-kaari.azurewebsites.net", "www.bio-kaari.fi"])

    def test_every_declared_host_is_one_a_module_could_reach(self):
        """`reads` is a claim about requests, so it may not name a host no adapter uses."""
        for it in self.cloud_items():
            for host in run.hosts_of(it.site):
                with self.subTest(provider=it.label, host=host):
                    self.assertRegex(host, r"^[a-z0-9.-]+$")

    def test_the_two_single_site_modules_name_the_host_they_read(self):
        """BioRex and Cinema Orion carried no `base` until the global pool made every
        base-less site share one group."""
        import biorex
        import orion
        self.assertEqual(run.host_of(biorex.SITES[0]), "biorex.fi")
        self.assertEqual(run.host_of(orion.SITES[0]), "cinemaorion.fi")


# --- the committed log is still per module ---------------------------------------------

class PerModuleLogTest(CloudTestCase):
    def run_two(self, **kw):
        h = self.hosts(4, delay=0)
        mods = [module("mod_a", P.site("a0", h.base(0)), P.site("a1", h.base(1)), **kw),
                module("mod_b", P.site("b0", h.base(2)), P.site("b1", h.base(3)), **kw)]
        return h, self.cloud(mods)

    def test_one_log_per_module_plus_the_runs_own(self):
        _, (code, logs) = self.run_two()
        self.assertEqual(code, 0)
        self.assertEqual(sorted(logs), ["cloud", "mod_a", "mod_b"])

    def test_each_log_ends_with_its_own_exit_line(self):
        """`check_runs.py` reads the last `exit=` line of every committed log and nothing
        else; without it a module is reported as having died."""
        _, (_, logs) = self.run_two()
        for name, text in logs.items():
            with self.subTest(log=name):
                self.assertRegex(text, r"(?m)^exit=0\s*$")

    def test_a_modules_log_holds_only_its_own_sites(self):
        _, (_, logs) = self.run_two(chatty=True, requests=2)
        self.assertNotIn("[b0]", logs["mod_a"])
        self.assertNotIn("[b1]", logs["mod_a"])
        self.assertNotIn("[a0]", logs["mod_b"])
        # The worker's own lines, not only the publication step's: those are written
        # straight to the file and would be there even if nothing were ever replayed.
        self.assertIn("[a0] out 0", logs["mod_a"])
        self.assertIn("[a0] err 1", logs["mod_a"])
        self.assertIn("[b1] out 0", logs["mod_b"])

    def test_each_site_is_one_contiguous_block_in_sites_order(self):
        """Sites finish out of order, so a log printed as they go is unreadable. Replayed
        whole, in site order, into its own module's file."""
        h = self.hosts(4, delay=0)
        mods = [module("mod_a", P.site("a0", h.base(0)), P.site("a1", h.base(1)),
                       chatty=True, requests=3, stagger={"a0": 0.03, "a1": 0.0}),
                module("mod_b", P.site("b0", h.base(2)), P.site("b1", h.base(3)),
                       chatty=True, requests=3, stagger={"b0": 0.03, "b1": 0.0})]
        _, logs = self.cloud(mods)
        for name, providers in (("mod_a", ["a0", "a1"]), ("mod_b", ["b0", "b1"])):
            with self.subTest(module=name):
                seen = [t for t in P.blocks(P.tags(logs[name])) if t in providers]
                self.assertEqual(seen, providers)

    def test_the_summary_line_names_only_that_module(self):
        _, (_, logs) = self.run_two()
        self.assertIn("[run] mod_a: 2 venues, 2 showtimes", logs["mod_a"])
        self.assertIn("[run] mod_b: 2 venues, 2 showtimes", logs["mod_b"])

    def test_the_http_counters_are_attributed_to_the_module_that_made_them(self):
        """They were per module when each module was a process, and the committed log
        offers them as evidence for how the pipeline fetched. One pool must not report
        another module's requests."""
        h = self.hosts(4, delay=0)
        mods = [module("mod_a", P.site("a0", h.base(0)), requests=2),
                module("mod_b", P.site("b0", h.base(1)), P.site("b1", h.base(2)),
                       requests=5)]
        _, logs = self.cloud(mods)
        self.assertIn("[run] http: 0 revalidated (304), 2 full", logs["mod_a"])
        self.assertIn("[run] http: 0 revalidated (304), 10 full", logs["mod_b"])
        self.assertEqual(common.cache_stats()["miss"], 12, "the process total is the sum")

    def test_the_timing_line_separates_worker_time_from_wall_clock(self):
        """A sum of overlapping fetches is not elapsed anything, and the line has to say
        which it is quoting."""
        _, (_, logs) = self.run_two()
        line = next(l for l in logs["mod_a"].splitlines() if l.startswith("[run] timing:"))
        self.assertIn("added up across workers that overlap", line)
        self.assertIn("queue wait", line)
        self.assertIn("wall", line)

    def test_each_log_names_the_hosts_that_module_aimed_a_request_at(self):
        """Declared hosts and attempted hosts can differ -- four adapters fetch a URL out of
        a page -- so the log carries what was attempted. Per module, like the counters."""
        h = self.hosts(3, delay=0)
        mods = [module("mod_a", P.site("a0", h.base(0)), requests=1),
                module("mod_b", P.site("b0", h.base(1)), P.site("b1", h.base(2)),
                       requests=1)]
        _, logs = self.cloud(mods)
        line_a = next(l for l in logs["mod_a"].splitlines() if l.startswith("[run] hosts:"))
        line_b = next(l for l in logs["mod_b"].splitlines() if l.startswith("[run] hosts:"))
        self.assertIn("1 attempted", line_a)
        self.assertIn(h.servers[0].netloc, line_a)
        self.assertNotIn(h.servers[1].netloc, line_a)
        self.assertIn("2 attempted", line_b)
        for n in (1, 2):
            self.assertIn(h.servers[n].netloc, line_b)

    def test_the_runs_own_log_accounts_for_what_it_held(self):
        """A global pool fetches ahead of the publication order, so results pile up behind
        the slowest early site. Accounted rather than assumed."""
        _, (_, logs) = self.run_two()
        self.assertRegex(logs["cloud"], r"held at most \d+ fetched site\(s\) and \d+ byte")
        self.assertIn("host group(s), pool of", logs["cloud"])


# --- one site failing is one site failing ----------------------------------------------

class FailureTest(CloudTestCase):
    PREV = {"generated": "2026-08-01T00:00:00+00:00", "dates": ["2026-08-02"],
            "horizon": "2026-08-02",
            "shows": [{"title": "Dyyni", "start": "2026-08-02T18:00:00+03:00"}]}

    def test_a_failing_site_keeps_its_files_while_the_other_modules_publish(self):
        (self.out / "area-a0-0.json").write_text(json.dumps(self.PREV), encoding="utf-8")
        h = self.hosts(3, delay=0)
        mods = [module("mod_a", P.site("a0", h.base(0)), fail=("a0",)),
                module("mod_b", P.site("b0", h.base(1)), P.site("b1", h.base(2)))]
        code, logs = self.cloud(mods)
        self.assertEqual(code, 1)
        self.assertIn("[a0] FAILED: connection reset", logs["mod_a"])
        self.assertRegex(logs["mod_a"], r"(?m)^exit=1\s*$")
        self.assertRegex(logs["mod_b"], r"(?m)^exit=0\s*$")
        self.assertEqual(json.loads((self.out / "area-a0-0.json").read_text()), self.PREV)
        self.assertTrue((self.out / "venues-b0.json").exists())
        self.assertTrue((self.out / "venues-b1.json").exists())

    def test_an_empty_programme_is_not_a_failure_and_stays_in_its_own_module(self):
        h = self.hosts(2, delay=0)
        mods = [module("mod_a", P.site("a0", h.base(0)), empty=("a0",)),
                module("mod_b", P.site("b0", h.base(1)))]
        code, logs = self.cloud(mods)
        self.assertEqual(code, 0)
        self.assertIn("[a0] no programme published", logs["mod_a"])
        self.assertIn("1 with no programme, 0 failures", logs["mod_a"])
        self.assertNotIn("no programme published", logs["mod_b"])

    def test_an_empty_programme_clears_the_sites_previous_screenings(self):
        """The coordinator publishes an empty programme as run.run_site does: every venue
        rewritten empty and fresh, all of them pending, and the next site untouched."""
        for i in range(2):
            (self.out / f"area-a0-{i}.json").write_text(json.dumps(self.PREV),
                                                        encoding="utf-8")
        h = self.hosts(2, delay=0)
        mods = [module("mod_a", P.site("a0", h.base(0), venues=2), empty=("a0",)),
                module("mod_b", P.site("b0", h.base(1)))]
        code, logs = self.cloud(mods)
        self.assertEqual(code, 0)
        for i in range(2):
            area = json.loads((self.out / f"area-a0-{i}.json").read_text())
            self.assertEqual(area["shows"], [])
            self.assertNotEqual(area["generated"], self.PREV["generated"])
        doc = json.loads((self.out / "venues-a0.json").read_text())
        self.assertEqual((doc["status"], doc["pending"]), ("ok", ["a0-0", "a0-1"]))
        self.assertIn("[a0] no programme published", logs["mod_a"])
        self.assertEqual(len(json.loads((self.out / "area-b0-0.json").read_text())["shows"]), 1)

    def test_an_empty_programme_that_cannot_be_written_fails_its_site(self):
        real = run.publish_empty
        def boom(*a, **kw):
            raise OSError("disk full")
        run.publish_empty = boom
        self.addCleanup(lambda: setattr(run, "publish_empty", real))
        h = self.hosts(2, delay=0)
        mods = [module("mod_a", P.site("a0", h.base(0)), P.site("a1", h.base(1)),
                       empty=("a0",))]
        code, logs = self.cloud(mods)
        self.assertEqual(code, 1)
        self.assertIn("[a0] FAILED: disk full", logs["mod_a"])
        self.assertNotIn("[a0] no programme published", logs["mod_a"])
        self.assertTrue((self.out / "venues-a1.json").exists())

    def test_a_module_that_cannot_be_imported_fails_in_its_own_log(self):
        """An import or configuration failure is explicit, and the rest of the run still
        publishes -- which is what `set +e` in the shell loop gave."""
        h = self.hosts(1, delay=0)
        good = module("mod_b", P.site("b0", h.base(0)))
        self.install([good])
        real = importlib.import_module
        importlib.import_module = (
            lambda n: good if n == "mod_b" else (_ for _ in ()).throw(
                ImportError("No module named 'mod_gone'")))
        registry.modules = lambda where=None: ["mod_gone", "mod_b"]
        self.addCleanup(lambda: setattr(importlib, "import_module", real))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = run_cloud.main(["--where", "all"])
        logs = logs_of(self.logs)
        self.assertEqual(code, 1)
        self.assertIn("[mod_gone] unusable: No module named 'mod_gone'", logs["mod_gone"])
        self.assertRegex(logs["mod_gone"], r"(?m)^exit=1\s*$")
        self.assertRegex(logs["mod_b"], r"(?m)^exit=0\s*$")

    def test_a_contract_violation_fails_that_site_and_not_the_publication_thread(self):
        """The check moved onto the coordinator thread with the rest of the write phase,
        so a raise there has to stay one site's failure."""
        class Bad(P.PoolMod):
            def fetch_site(self, site):
                out = P.PoolMod.fetch_site(self, site)
                if site["provider"] == "a0":
                    for shows in out.values():
                        for s in shows:
                            del s["rating"]
                return out

        h = self.hosts(2, delay=0)
        a = Bad([P.site("a0", h.base(0))])
        a.__name__ = "mod_a"
        mods = [a, module("mod_b", P.site("b0", h.base(1)))]
        code, logs = self.cloud(mods)
        self.assertEqual(code, 1)
        self.assertIn("[a0] FAILED:", logs["mod_a"])
        self.assertIn("'rating'", logs["mod_a"])
        self.assertRegex(logs["mod_b"], r"(?m)^exit=0\s*$")


class FatalTest(CloudTestCase):
    """A `SystemExit` out of adapter code ended a sequential run and has to end this one.

    Left alone it would not: the thread dies, the future holds the exception unread, and the
    run publishes anyway. It must also not be written into a log as a provider that failed,
    because it is not one, and it must not leave a worker still asking a cinema for pages.
    """

    class Exiting(P.PoolMod):
        exiting = ()

        def fetch_site(self, site):
            if site["provider"] in self.exiting:
                raise SystemExit(3)
            return P.PoolMod.fetch_site(self, site)

    def build(self, h):
        a = self.Exiting([P.site("a0", h.base(0))], requests=1)
        a.__name__ = "mod_a"
        b = self.Exiting([P.site("b0", h.base(1))], requests=1, exiting=("b0",))
        b.__name__ = "mod_b"
        return [a, b]

    def go(self, mods):
        self.install(mods)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            with self.assertRaises(SystemExit) as caught:
                run_cloud.main(["--where", "all"])
        return caught.exception, logs_of(self.logs)

    def test_it_reaches_the_caller_instead_of_a_future_nobody_reads(self):
        h = self.hosts(2, delay=0)
        exc, _ = self.go(self.build(h))
        self.assertEqual(exc.code, 3)

    def test_every_module_log_still_carries_its_contract_line(self):
        h = self.hosts(2, delay=0)
        _, logs = self.go(self.build(h))
        for name in ("mod_a", "mod_b", "cloud"):
            with self.subTest(log=name):
                self.assertRegex(logs[name], r"(?m)^exit=\d+\s*$")

    def test_the_run_cannot_report_success(self):
        h = self.hosts(2, delay=0)
        _, logs = self.go(self.build(h))
        self.assertRegex(logs["cloud"], r"(?m)^exit=1\s*$")
        self.assertIn("stopped early", logs["cloud"])
        self.assertRegex(logs["mod_b"], r"(?m)^exit=1\s*$")
        self.assertIn("stopped before this module was published", logs["mod_b"])

    def test_it_is_not_written_into_a_log_as_a_provider_failing(self):
        h = self.hosts(2, delay=0)
        _, logs = self.go(self.build(h))
        self.assertNotIn("FAILED", "".join(logs.values()))

    def test_a_module_never_reached_drops_the_previous_runs_log(self):
        """The abort line replaces an unreached module's committed log. Appended, the last
        run's `FAILED` line and `exit=0` stood above it, and check_runs.py named that old
        failure as this run's cause."""
        h = self.hosts(2, delay=0)
        a = self.Exiting([P.site("a0", h.base(0))], requests=1, exiting=("a0",))
        a.__name__ = "mod_a"
        b = self.Exiting([P.site("b0", h.base(1))], requests=1)
        b.__name__ = "mod_b"
        (self.logs / "run-mod_b.log").write_text(
            "[b0] FAILED: HTTP Error 403 from the last run\nexit=0\n", encoding="utf-8")
        _, logs = self.go([a, b])
        self.assertNotIn("from the last run", logs["mod_b"])
        self.assertIn("stopped before this module was published", logs["mod_b"])
        self.assertEqual(re.findall(r"(?m)^exit=\d+$", logs["mod_b"]), ["exit=1"])

    def test_a_module_stopped_part_way_keeps_what_this_run_wrote(self):
        """The other side of the same line: a module whose first site this run published
        and whose second site was fatal keeps the first site's lines above it."""
        class SlowExit(self.Exiting):
            def fetch_site(self, site):
                if site["provider"] in self.exiting:
                    time.sleep(0.3)             # b0 is published before the fatal lands
                return super().fetch_site(site)

        h = self.hosts(2, delay=0)
        a = self.Exiting([P.site("a0", h.base(0))], requests=1)
        a.__name__ = "mod_a"
        b = SlowExit([P.site("b0", h.base(1)), P.site("b1", h.base(1))], requests=1,
                     exiting=("b1",), chatty=True)
        b.__name__ = "mod_b"
        _, logs = self.go([a, b])
        self.assertIn("[b0] out 0", logs["mod_b"])
        self.assertIn("stopped before this module was published", logs["mod_b"])

    def test_a_dying_site_is_released_only_after_its_exception_is_recorded(self):
        """The ordering the whole `settled` flag exists for, asserted directly because the
        pool cannot show it: between releasing the site and recording the exception the
        worker runs a handful of bytecodes, and the coordinator does not get scheduled
        inside them, so a run never reproduces it. What it would do if it did is publish a
        fetch result that does not exist and write the fatal into the log as a provider
        that failed.

        Read as: every time this site was released, the exception was already there to be
        seen. Driven on this thread, so there is nothing to race with.
        """
        fatal = []

        class Watching(threading.Event):
            seen = []

            def set(self):
                self.seen.append(bool(fatal))
                super().set()

        class Dying:
            __name__ = "mod_a"
            SITES = [P.site("a0", "https://one.test")]

            def fetch_site(self, site):
                raise SystemExit(3)

        mod = Dying()
        m = run_cloud.Module(0, "mod_a")
        m.mod = mod
        m.sites = mod.SITES
        items = run_cloud.work_items([m])
        event = Watching()
        run_cloud.read_host(items, run.Recorder(), [event], fatal)
        self.assertEqual([e.code for e in fatal], [3])
        self.assertTrue(event.seen, "the site was never released, so the run would hang")
        self.assertEqual(event.seen, [True] * len(event.seen),
                         "the site was released before the exception was recorded, so the "
                         "coordinator would publish an empty result instead of stopping")

    def test_no_worker_is_left_running(self):
        """`shutdown(wait=True, cancel_futures=True)`: the hosts in flight are waited for
        and the ones not reached are never asked."""
        before = {t.ident for t in threading.enumerate()}
        h = self.hosts(6, delay=0.05)
        a = self.Exiting([P.site(f"a{i}", h.base(i)) for i in range(3)], requests=1)
        a.__name__ = "mod_a"
        b = self.Exiting([P.site(f"b{i}", h.base(i + 3)) for i in range(3)],
                         requests=1, exiting=("a0",))
        b.__name__ = "mod_b"
        b.exiting = ()
        a.exiting = ("a0",)
        self.go([a, b])
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            leftover = [t for t in threading.enumerate()
                        if t.ident not in before and t.is_alive()
                        and t.name.startswith("ThreadPoolExecutor")]
            if not leftover:
                break
            time.sleep(0.05)
        self.assertEqual(leftover, [], "a pool thread outlived the run")


# --- a host nobody declared is still read by one site at a time ------------------------

class PageDerivedHostTest(CloudTestCase):
    """Four adapters fetch a URL read out of a page and none checks its host.

    BioRex's film pages come from an href in an ajax fragment, Cinemahouse's from a tile
    link, Tapiola's and Kinola's from their listings. Read as a visitor on 2026-09-15 every
    one names the site's own host, but that is markup answering today. While each module was
    its own process only sites of one module could collide; the coordinator overlaps every
    module, so the collision this guards is new.

    `common.reading` claims whatever host a fetch actually goes to, for as long as that site
    keeps reading it. A bound, not a rate limit -- see the ceiling test below.
    """

    class Wandering(P.PoolMod):
        """Fetches its own host, then one neither site declares."""
        elsewhere = ""
        extra = 1
        swallow = False        # catch around the page-derived fetch, as adapters do
        empty = False          # and then find nothing on what it read: EmptyProgramme

        def fetch_site(self, site):
            prov = site["provider"]
            common.fetch(f"{site['base']}/{prov}/own", cache=True)
            for n in range(self.extra):
                try:
                    common.fetch(f"{self.elsewhere}/{prov}/page{n}", cache=True)
                except Exception:
                    if not self.swallow:
                        raise
                    if self.empty:
                        raise common.EmptyProgramme("the page read had no film on it")
            out = {v["id"]: [P.show(f"{prov} film")] for v in site["venues"]}
            for vid, shows in out.items():
                for s in shows:
                    s.update(venue=vid, provider=prov)
            return out

    def spans_on(self, h, index, provider):
        """Every request one site made to one server. -> [(start, end)]."""
        with h.lock:
            return [(a, b) for netloc, path, a, b in h.log
                    if netloc == h.servers[index].netloc
                    and path.startswith(f"/{provider}/")]

    def build(self, h, **kw):
        a = self.Wandering([P.site("a0", h.base(0))], elsewhere=h.base(2), **kw)
        a.__name__ = "mod_a"
        b = self.Wandering([P.site("b0", h.base(1))], elsewhere=h.base(2), **kw)
        b.__name__ = "mod_b"
        return [a, b]

    def test_the_two_modules_do_overlap_on_the_hosts_they_declare(self):
        """The control. Without it the next test would pass on a run that never pools."""
        h = self.hosts(3, delay=0.05)
        self.cloud(self.build(h))
        self.assertTrue(P.overlap(self.spans_on(h, 0, "a0"), self.spans_on(h, 1, "b0")))

    def test_a_host_neither_site_declares_is_still_read_by_one_at_a_time(self):
        h = self.hosts(3, delay=0.05)
        self.cloud(self.build(h))
        self.assertFalse(P.overlap(self.spans_on(h, 2, "a0"), self.spans_on(h, 2, "b0")),
                         "two modules read one undeclared host at the same time")

    PREV = {"generated": "2026-08-01T00:00:00+00:00", "dates": ["2026-08-02"],
            "horizon": "2026-08-02",
            "shows": [{"title": "Dyyni", "start": "2026-08-02T18:00:00+03:00"}]}

    def contended(self, **kw):
        """A run where mod_a reaches the shared host first and holds it.

        mod_a's own host answers at once and mod_b's takes a moment, so a0 claims host 2
        before b0 asks for it; host 2 is slow, so a0 still holds it when b0 does.
        -> (hosts, exit code, logs).
        """
        saved = common.HOST_CLAIM_WAIT
        common.HOST_CLAIM_WAIT = 0.05
        self.addCleanup(lambda: setattr(common, "HOST_CLAIM_WAIT", saved))
        h = self.hosts(3, delay=0)
        h.servers[1].delay = 0.3
        h.servers[2].delay = 0.5
        (self.out / "area-b0-0.json").write_text(json.dumps(self.PREV), encoding="utf-8")
        code, logs = self.cloud(self.build(h, **kw))
        return h, code, logs

    def test_giving_up_on_a_claim_sends_no_request_at_all(self):
        """The property the ceiling exists for. Going ahead after the wait was the first
        answer and it was wrong: it dropped the guarantee exactly when the other site is
        slow, which is when it matters, and a log line does not make two concurrent
        requests at one cinema's server acceptable."""
        h, _, _ = self.contended()
        self.assertEqual(self.spans_on(h, 2, "b0"), [],
                         "a request went to a host another site still held")
        self.assertTrue(self.spans_on(h, 2, "a0"), "the holder never read it either")

    def test_the_site_that_gave_up_fails_and_keeps_its_previous_data(self):
        h, code, logs = self.contended()
        self.assertEqual(code, 1)
        self.assertIn("[b0] FAILED:", logs["mod_b"])
        # The line says what happened -- a request withheld -- and not that two went out.
        self.assertIn("refused to b0", logs["mod_b"])
        self.assertIn("no request was sent", logs["mod_b"])
        self.assertNotIn("at once", logs["mod_b"])
        self.assertIn("`reads`", logs["mod_b"])
        self.assertEqual(json.loads((self.out / "area-b0-0.json").read_text()), self.PREV)
        self.assertFalse((self.out / "venues-b0.json").exists())

    def test_the_site_that_held_the_host_still_publishes(self):
        """One site failing is one site failing, as with any other fetch failure."""
        h, _, logs = self.contended()
        self.assertRegex(logs["mod_a"], r"(?m)^exit=0\s*$")
        self.assertTrue((self.out / "venues-a0.json").exists())

    def test_an_adapter_that_swallows_the_refusal_still_fails_its_site(self):
        """Several adapters catch broadly around their own fetches. Left to them, a
        refused claim would become a partial publish: some pages read, one skipped, no
        error anywhere. The refusal is re-raised when the site's fetch ends."""
        h, code, logs = self.contended(swallow=True)
        self.assertEqual(code, 1)
        self.assertIn("[b0] FAILED:", logs["mod_b"])
        self.assertEqual(self.spans_on(h, 2, "b0"), [])
        self.assertEqual(json.loads((self.out / "area-b0-0.json").read_text()), self.PREV)

    def test_an_empty_programme_raised_after_a_swallowed_refusal_still_fails_the_site(self):
        """`reading` re-raised a swallowed refusal only when the body returned. Any other
        exception took its place, and EmptyProgramme publishes every venue empty and
        pending: an adapter that caught the refused listing and then found no film marker
        in "" would clear its data and exit 0 (audit C3, 2026-09-25). A refusal stays a
        failure whatever the body raised after it."""
        h, code, logs = self.contended(swallow=True, empty=True)
        self.assertEqual(code, 1)
        self.assertIn("[b0] FAILED:", logs["mod_b"])
        self.assertNotIn("no programme published", logs["mod_b"])
        self.assertEqual(json.loads((self.out / "area-b0-0.json").read_text()), self.PREV)

    def test_nothing_waits_for_a_host_no_other_site_holds(self):
        """The uncontended path, which is every host in the half today: claimed, read, and
        released with no waiting at all."""
        h = self.hosts(3, delay=0)
        code, _ = self.cloud(self.build(h))
        self.assertEqual(code, 0)
        self.assertTrue(self.spans_on(h, 2, "a0"))
        self.assertTrue(self.spans_on(h, 2, "b0"))

    def test_every_claim_is_released_when_its_site_finishes(self):
        """Held for the life of one site's fetch and no longer. A claim that outlived its
        site would make every later site wait out the ceiling on that host."""
        h = self.hosts(3, delay=0)
        code, _ = self.cloud(self.build(h))
        self.assertEqual(code, 0)
        self.assertEqual(common._host_owner, {}, "a site kept a host after it finished")

    def test_nothing_is_claimed_outside_a_site_fetch(self):
        """`enrich_tmdb` and `mirror_posters` run in their own processes and an adapter is
        exercised by hand; none of them is a site, and none of them waits for one."""
        h = self.hosts(1, delay=0)
        common.fetch(f"{h.base(0)}/plain/p0", cache=True)
        self.assertEqual(common._host_owner, {})
        self.assertIn(h.servers[0].netloc, common.hosts_attempted())


# --- films-extra.json is one file for the whole run ------------------------------------

class SynopsisTest(CloudTestCase):
    def three_modules(self, h):
        """Every site publishes "Shared Film" with its own blurb, module A's first site
        slowest so completion order and publication order disagree."""
        h.servers[0].delay = 0.25
        h.servers[1].delay = 0.05
        return [module("mod_a", P.site("a0", h.base(0)), P.site("a1", h.base(1)),
                       requests=2, syn=True, shared=True),
                module("mod_b", P.site("b0", h.base(2)), requests=2, syn=True,
                       shared=True)]

    def films(self):
        return json.loads((self.out / "films-extra.json").read_text())["films"]

    def test_the_earliest_site_of_the_earliest_module_wins(self):
        """Fill-if-empty makes the winner "whichever host answered first", which with a
        pool is a property of the network. It has to be the publication order instead, at
        any pool size."""
        h = self.hosts(3, delay=0)
        mods = self.three_modules(h)
        self.cloud(mods, workers=8)
        finished = sorted(("a0", "a1", "b0"), key=lambda p: max(e for _, e in h.spans(p)))
        self.assertEqual(finished[-1], "a0",
                         "a0 did not finish last, so this fixture is not exercising the "
                         "race it exists for")
        self.assertEqual(self.films()["shared film"]["s"]["fi"], "a0 synopsis")

    def test_a_later_module_does_not_outrank_an_earlier_one(self):
        """`synmerge.reset()` at each module boundary. Without it module B's site 0
        outranks module A's site 1 and takes a slot that is already settled."""
        h = self.hosts(3, delay=0)
        mods = [module("mod_a", P.site("a0", h.base(0)), P.site("a1", h.base(1)),
                       requests=1, syn=True, shared=("a1",)),
                module("mod_b", P.site("b0", h.base(2)), requests=1, syn=True,
                       shared=("b0",))]
        self.cloud(mods)
        self.assertEqual(self.films()["shared film"]["s"]["fi"], "a1 synopsis")

    def test_no_sites_synopses_are_lost(self):
        """One file, one writer: the merge runs on the publication thread, so there is no
        read-modify-write to lose."""
        h = self.hosts(6, delay=0)
        mods = [module(f"mod_{i}", P.site(f"p{i}a", h.base(i * 2)),
                       P.site(f"p{i}b", h.base(i * 2 + 1)), requests=1, syn=True)
                for i in range(3)]
        self.cloud(mods)
        films = self.films()
        self.assertEqual(len(films), 6)
        for i in range(3):
            for half in ("a", "b"):
                self.assertEqual(films[f"p{i}{half} film"]["s"]["fi"],
                                 f"p{i}{half} synopsis")


# --- one worker and eight publish the same thing ---------------------------------------

class EquivalenceTest(CloudTestCase):
    @contextlib.contextmanager
    def frozen_now(self):
        """Every file carries datetime.now(), so two runs are only comparable with the
        clock held still."""
        real = run_cloud.datetime

        class Frozen:
            timezone = real.timezone

            class datetime:
                @staticmethod
                def now(tz=None):
                    return real.datetime(2026, 8, 30, 12, 0, 0, tzinfo=tz)

        run_cloud.datetime = Frozen
        try:
            yield
        finally:
            run_cloud.datetime = real

    def run_with(self, workers):
        """One whole coordinator run into its own directories.

        -> ({filename: contents}, {module: log without its timing line}, the raw logs).
        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = pathlib.Path(tmp.name)
        logs = out / "logs"
        logs.mkdir()
        h = self.hosts(4, delay=0)
        mods = [module("mod_a", P.site("shared_a", h.base(0)),
                       P.site("shared_b", h.base(0)), P.site("a2", h.base(1)),
                       requests=2, syn=True, shared=True),
                module("mod_b", P.site("b0", h.base(2)), P.site("b1", h.base(3)),
                       requests=2, syn=True, shared=True)]
        saved_out, saved_logs = run.OUT, run_cloud.LOGS
        run.OUT, run_cloud.LOGS = out, logs
        try:
            with self.frozen_now():
                self.cloud(mods, workers=workers)
        finally:
            run.OUT, run_cloud.LOGS = saved_out, saved_logs
        files = {f.name: f.read_text(encoding="utf-8") for f in sorted(out.glob("*.json"))}
        raw = logs_of(logs)
        return files, {k: comparable(v) for k, v in raw.items()}, raw

    def test_one_worker_and_eight_write_the_same_files_and_say_the_same_thing(self):
        one_files, one_logs, _ = self.run_with(1)
        common.reset_accounting()
        self.reset_counters()
        many_files, many_logs, _ = self.run_with(8)
        self.assertEqual(sorted(one_files), sorted(many_files))
        for name in one_files:
            if name == "films-extra.json":
                # The one file several sites write, so the order its *new* keys land in
                # follows which site was published first among the films seen for the
                # first time on this run. Compared as a document for exactly that much
                # difference; every value is identical.
                self.assertEqual(json.loads(one_files[name]),
                                 json.loads(many_files[name]), name)
            else:
                self.assertEqual(one_files[name], many_files[name], name)
        for name in ("mod_a", "mod_b"):
            self.assertEqual(one_logs[name], many_logs[name], name)

    def test_the_timing_line_is_the_only_difference_and_it_is_there(self):
        _, one_logs, raw = self.run_with(1)
        self.assertNotIn("timing", one_logs["mod_a"])
        self.assertIn("[run] timing:", raw["mod_a"])
        self.assertIn("added up across workers that overlap", raw["mod_a"])


# --- the budgets were per module because each module was a process ---------------------

class BudgetTest(CloudTestCase):
    def setUp(self):
        super().setUp()
        # The waits are counted, which is what these read; sitting them out is not.
        no_sleep.patch(self, common)

    def throttling(self, h, seconds="1"):
        class Throttling(P.Handler):
            def do_GET(self):
                with self.server.lock:
                    self.server.log.append((self.server.netloc, self.path, 0.0, 0.0))
                self.send_response(429)
                self.send_header("Retry-After", seconds)
                self.send_header("Content-Length", "0")
                self.end_headers()
        for srv in h.servers:
            srv.RequestHandlerClass = Throttling

    def test_one_module_throttled_does_not_spend_another_modules_budget(self):
        """RETRY_AFTER_BUDGET bounds a run, and a run was one module. A coordinator that
        charged every module to one budget would let the first host to answer 429 stop the
        other nineteen modules retrying at all."""
        h = self.hosts(2, delay=0)
        self.throttling(h)
        saved = common.RETRY_AFTER_BUDGET
        common.RETRY_AFTER_BUDGET = 3
        self.addCleanup(lambda: setattr(common, "RETRY_AFTER_BUDGET", saved))
        mods = [module("mod_a", P.site("a0", h.base(0)), requests=1),
                module("mod_b", P.site("b0", h.base(1)), requests=1)]
        _, logs = self.cloud(mods, workers=1)
        for name in ("mod_a", "mod_b"):
            with self.subTest(module=name):
                self.assertIn("[run] throttled: 3 Retry-After responses, 2s waited, "
                              "0 not retried", logs[name])
        self.assertEqual(common.throttle_stats()["asked"], 6)

    def test_a_modules_own_counters_are_what_its_log_reports(self):
        h = self.hosts(2, delay=0)
        self.throttling(h)
        mods = [module("mod_a", P.site("a0", h.base(0)), requests=1),
                module("mod_b", P.site("b0", h.base(1)), requests=1)]
        self.cloud(mods, workers=1)
        self.assertEqual(common.throttle_stats("mod_a")["asked"], 3)
        self.assertEqual(common.throttle_stats("mod_b")["asked"], 3)


class CaptureBoundTest(CloudTestCase):
    def test_a_sites_captured_output_is_bounded_and_says_when_it_trims(self):
        """A pool holds every unreplayed site's block at once, so a chatty adapter would
        otherwise decide how much memory a run takes. Nothing real comes near the cap."""
        class Loud(P.PoolMod):
            def fetch_site(self, site):
                print("[" + site["provider"] + "] " + "x" * 500)
                return P.PoolMod.fetch_site(self, site)

        saved = run.MAX_CAPTURE
        run.MAX_CAPTURE = 200
        self.addCleanup(lambda: setattr(run, "MAX_CAPTURE", saved))
        h = self.hosts(1, delay=0)
        mod = Loud([P.site("a0", h.base(0))], requests=1)
        mod.__name__ = "mod_a"
        _, logs = self.cloud([mod])
        self.assertIn("past the 200-byte capture cap", logs["mod_a"])
        self.assertNotIn("x" * 500, logs["mod_a"])


# --- the single-module and local paths are untouched ------------------------------------

class RoutingTest(CloudTestCase):
    def test_the_half_selects_the_sites_the_way_run_py_does(self):
        """Site-level routing, not per module: the coordinator reuses run.sites_for, so a
        local site inside a cloud module stays out of the cloud half."""
        class FakeMod:
            __name__ = "fakemod"
            SITES = [{"provider": "kotkanleffat", "venues": []},   # cloud in the registry
                     {"provider": "joutsankino", "venues": []}]    # local in the registry

        real = importlib.import_module
        importlib.import_module = lambda n: FakeMod if n == "fakemod" else real(n)
        self.addCleanup(lambda: setattr(importlib, "import_module", real))
        cloud = run_cloud.collect(["fakemod"], "cloud")[0]
        local = run_cloud.collect(["fakemod"], "local")[0]
        self.assertEqual([s["provider"] for s in cloud.sites], ["kotkanleffat"])
        self.assertEqual([s["provider"] for s in local.sites], ["joutsankino"])

    def test_a_site_with_no_registry_entry_costs_its_module_and_not_the_pool(self):
        """`run.sites_for` raises for a provider the registry does not have, so that a
        misconfiguration cannot be fetched by both halves onto one venue file. It is
        called inside collect()'s try, which keeps the blast radius at one module: that
        module carries the error into its own log and into the run's exit code, and every
        other module still fetches."""
        class Orphan:
            __name__ = "orphanmod"
            SITES = [{"provider": "nosuchprovider", "venues": []}]

        class Fine:
            __name__ = "finemod"
            SITES = [{"provider": "kotkanleffat", "venues": []}]   # cloud in the registry

        mods = {"orphanmod": Orphan, "finemod": Fine}
        real = importlib.import_module
        importlib.import_module = lambda n: mods.get(n) or real(n)
        self.addCleanup(lambda: setattr(importlib, "import_module", real))
        bad, good = run_cloud.collect(["orphanmod", "finemod"], "cloud")
        self.assertIsInstance(bad.error, run.UnregisteredProvider)
        self.assertIn("nosuchprovider", str(bad.error))
        self.assertEqual(bad.sites, [])
        self.assertEqual([s["provider"] for s in good.sites], ["kotkanleffat"])

    def test_run_py_reports_the_same_misconfiguration_instead_of_a_traceback(self):
        """The other caller. `poolmod`'s fake providers have no registry entry, so any
        half but "all" reaches the same raise, and main() has to count it as an unusable
        module rather than die with it."""
        h = self.hosts(1, delay=0)
        mod = P.PoolMod([P.site("p0", h.base(0))], requests=1)
        code, text = self.main(mod, argv=("poolmod", "--half", "cloud"))
        self.assertEqual(code, 1)
        self.assertIn("[poolmod] unusable:", text)
        self.assertIn("no entry in registry.py", text)
        self.assertFalse((self.out / "venues-p0.json").exists())

    def test_run_py_still_runs_one_module_on_its_own(self):
        """The single-module CLI is what exercises an adapter by hand and what the local
        wrapper calls. The split into fetch and publish must not have moved it."""
        h = self.hosts(2, delay=0)
        mod = P.PoolMod([P.site("p0", h.base(0)), P.site("p1", h.base(1))], requests=1)
        code, text = self.main(mod)
        self.assertEqual(code, 0)
        self.assertIn("[run] poolmod: 2 venues, 2 showtimes", text)
        self.assertTrue((self.out / "venues-p0.json").exists())

    def test_the_default_ceiling_is_the_one_run_py_uses(self):
        self.assertEqual(run_cloud.MAX_HOSTS, run.MAX_HOSTS)


class VenueListsTest(CloudTestCase):
    """The cloud half rewrites its combined venue file after the run, aborted or not.

    A real cloud provider's id on a fake module, so the registry puts it in the cloud half.
    `biorex` here is a name, not the adapter: the fetch is the pool's own stub."""

    def combined(self, half):
        p = venuelists.path_for(self.out, half)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def test_the_run_writes_the_cloud_file_from_what_it_published(self):
        h = self.hosts(1, delay=0)
        code, logs = self.cloud([module("mod_v", P.site("biorex", h.base(0)))])
        self.assertEqual(code, 0, logs)
        written = json.loads((self.out / "venues-biorex.json").read_text(encoding="utf-8"))
        self.assertEqual(self.combined("cloud")["providers"], {"biorex": written})
        self.assertIsNone(self.combined("local"), "the cloud half wrote the local file")
        self.assertIn("venuelists-cloud.json rewritten", logs["cloud"])

    def test_an_aborted_run_still_rebuilds_it_from_the_files_as_they_stand(self):
        prev = {"generated": "2026-09-25T06:00:00+00:00", "venues": [{"id": "x", "name": "x"}],
                "provider": "biorex"}
        (self.out / "venues-biorex.json").write_text(json.dumps(prev), encoding="utf-8")
        h = self.hosts(1, delay=0)
        exiting = FatalTest.Exiting([P.site("biorex", h.base(0))], requests=1,
                                    exiting=("biorex",))
        exiting.__name__ = "mod_v"
        self.install([exiting])
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                run_cloud.main(["--where", "all"])
        self.assertEqual(self.combined("cloud")["providers"], {"biorex": prev})


if __name__ == "__main__":
    unittest.main()
