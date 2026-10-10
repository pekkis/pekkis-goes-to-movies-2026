"""run.py routes individual sites, not whole adapter modules.

Per-module routing would have put all sixteen eTiketti sites in both halves to make one
of them local, with two writers racing on the same files. Asserted against the live
registry: the halves are disjoint, so every data/venues-{provider}.json has one writer,
and complete, so routing cannot drop a cinema.
"""
import contextlib
import importlib
import io
import os
import unittest

import _ctx                                                # noqa: F401
import registry
import run


class FakeMod:
    __name__ = "fakemod"
    SITES = [
        {"provider": "kotkanleffat", "venues": []},        # cloud in the registry
        {"provider": "joutsankino", "venues": []},         # local in the registry
    ]


class OrphanMod:
    """One site whose provider the registry does not have, beside two it does."""
    __name__ = "orphanmod"
    SITES = FakeMod.SITES + [{"provider": "nosuchprovider", "venues": []}]


def ids(sites):
    return [s["provider"] for s in sites]


class SitesForTest(unittest.TestCase):
    def test_cloud_excludes_a_local_site(self):
        self.assertNotIn("joutsankino", ids(run.sites_for(FakeMod, "cloud")))
        self.assertIn("kotkanleffat", ids(run.sites_for(FakeMod, "cloud")))

    def test_local_takes_the_local_site_and_not_the_cloud_one(self):
        got = ids(run.sites_for(FakeMod, "local"))
        self.assertIn("joutsankino", got)
        self.assertNotIn("kotkanleffat", got)

    def test_all_keeps_every_site(self):
        self.assertEqual(len(run.sites_for(FakeMod, "all")), 2)

    def test_an_unregistered_provider_fails_the_module_and_names_itself(self):
        """Kept on both halves until 2026-09-19, on the argument that
        test_registry_sites.py is where a misconfiguration is reported. It is; what that
        left was the consequence when one gets past the suite, which is the two halves
        writing the same data/venues-{provider}.json in the same run.
        """
        for half in ("cloud", "local"):
            with self.subTest(half=half):
                with self.assertRaises(run.UnregisteredProvider) as cm:
                    run.sites_for(OrphanMod, half)
                self.assertIn("nosuchprovider", str(cm.exception))

    def test_a_site_with_no_provider_id_at_all_is_reported_too(self):
        """`site.get("provider") or ""` reaches registry.by_id("") -> None by the same
        route, and an empty name in the message says nothing."""
        class Nameless:
            __name__ = "nameless"
            SITES = [{"venues": []}, {"provider": "kotkanleffat", "venues": []}]
        with self.assertRaises(run.UnregisteredProvider) as cm:
            run.sites_for(Nameless, "cloud")
        self.assertIn("<no provider id>", str(cm.exception))

    def test_all_does_not_raise_because_there_is_no_second_writer(self):
        """`--where all` is one process fetching everything, which is how an adapter is
        exercised by hand. There is no half for the entry to be in both of, and the
        suite still reports it."""
        self.assertEqual(len(run.sites_for(OrphanMod, "all")), 3)


class HalfOfTest(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.pop("GITHUB_ACTIONS", None)

    def tearDown(self):
        if self._saved is not None:
            os.environ["GITHUB_ACTIONS"] = self._saved

    def test_actions_means_cloud_without_the_workflow_saying_so(self):
        """The cloud workflow calls run.py per module with a bare name. If the half had
        to be passed, this could not have been fixed without editing that file."""
        os.environ["GITHUB_ACTIONS"] = "true"
        self.assertEqual(run.half_of(["etiketti"]), "cloud")

    def test_off_actions_a_bare_module_still_fetches_everything(self):
        """`run.py etiketti` on a laptop is how an adapter gets exercised. Defaulting to
        "local" would quietly fetch one site of sixteen and look like a broken parser."""
        self.assertEqual(run.half_of(["etiketti"]), "all")

    def test_where_selects_the_half_as_well_as_the_modules(self):
        self.assertEqual(run.half_of(["--where", "local"]), "local")

    def test_an_explicit_half_wins_over_the_environment(self):
        os.environ["GITHUB_ACTIONS"] = "true"
        self.assertEqual(run.half_of(["etiketti", "--half", "local"]), "local")


class ArgvTest(unittest.TestCase):
    """A flag's value is not a module name. It was: `run.py etiketti --half local` tried
    to `import local`, logged "[local] unusable", counted a failure and printed the word
    in the run summary -- caught by running it, not by reading it."""

    def test_a_flag_value_is_not_taken_as_a_module(self):
        self.assertEqual(run.module_names(["etiketti", "--half", "local"]), ["etiketti"])

    def test_several_modules_still_come_through(self):
        self.assertEqual(run.module_names(["etiketti", "nexxo"]), ["etiketti", "nexxo"])

    def test_a_trailing_flag_prints_usage_instead_of_an_index_error(self):
        """`--where` with its value lost to a shell variable that expanded to nothing was
        an IndexError and a traceback, which reads as a broken runner rather than as a
        mistyped command."""
        for argv in (["--where"], ["etiketti", "--half"]):
            with self.subTest(argv=argv):
                err = io.StringIO()
                with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
                    run.half_of(argv)
                self.assertEqual(cm.exception.code, 2)
                self.assertIn("usage: run.py", err.getvalue())
                self.assertIn("needs a value", err.getvalue())

    def test_the_two_places_that_print_usage_print_the_same_string(self):
        self.assertIn("--where cloud|local", run.USAGE)
        self.assertEqual(run.USAGE.count("usage: run.py"), 1)


class LiveRegistryTest(unittest.TestCase):
    def test_the_halves_are_disjoint_and_complete(self):
        for name in registry.modules():
            mod = importlib.import_module(name)
            cloud, local = ids(run.sites_for(mod, "cloud")), ids(run.sites_for(mod, "local"))
            with self.subTest(module=name):
                self.assertEqual(set(cloud) & set(local), set(),
                                 "a provider fetched by both halves has two writers "
                                 "on its venues file")
                self.assertEqual(sorted(cloud + local), sorted(ids(mod.SITES)),
                                 "a site in neither half is never fetched")

    def test_joutsan_kino_is_routed_local_and_shares_its_module(self):
        """The case this exists for: a local site inside an otherwise cloud module."""
        p = registry.by_id("joutsankino")
        self.assertIsNotNone(p)
        self.assertEqual(p["where"], "local")
        self.assertEqual(p["module"], "etiketti")
        etiketti = importlib.import_module("etiketti")
        self.assertIn("joutsankino", ids(run.sites_for(etiketti, "local")))
        self.assertGreater(len(run.sites_for(etiketti, "cloud")), 1)

    def test_the_local_etiketti_sites_are_the_four_that_403_a_runner_and_haapamaki(self):
        """Savon Kinot joined the local half on 2026-09-04, Cine and Star on 2026-09-08:
        each sits behind Cloudflare, which answers a datacenter address 403 at the edge
        while an ordinary connection gets 200. Haapamäen Elokuvat came with its move from
        Johku on 2026-09-29, local as it was there until a committed run log shows a
        runner reads it. The list is explicit so a site drifting between halves is a
        failing test and a decision, never a side effect of a registry edit."""
        etiketti = importlib.import_module("etiketti")
        self.assertEqual(ids(run.sites_for(etiketti, "local")),
                         ["savonkinot", "joutsankino", "cine", "star", "haapamaki"])
        for pid in ("savonkinot", "cine", "star"):
            with self.subTest(provider=pid):
                self.assertEqual(registry.by_id(pid)["where"], "local")
                self.assertNotIn(pid, ids(run.sites_for(etiketti, "cloud")))


class HalfValueTest(unittest.TestCase):
    """A half this pipeline does not have is a usage error, not an empty run.

    `run.py biorex --half typo` matched no site's `where`, printed "no sites for the typo
    half" and exited 0. A scheduled caller cannot tell that from a provider that really
    has nothing on this half, so a typo in the wrapper would read as a quiet success
    indefinitely. Reproduced on 2026-09-19 before the check was added.
    """

    def half(self, argv):
        """-> ("value", None) or (None, exit_code), with the usage text swallowed."""
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            try:
                return run.half_of(argv), None, err.getvalue()
            except SystemExit as e:
                return None, e.code, err.getvalue()

    def test_every_real_half_is_accepted(self):
        for value in ("cloud", "local", "all"):
            with self.subTest(value=value):
                got, code, _ = self.half(["biorex", "--half", value])
                self.assertEqual((got, code), (value, None))

    def test_where_accepts_the_two_halves_it_selects_modules_for(self):
        for value in ("cloud", "local"):
            with self.subTest(value=value):
                got, code, _ = self.half(["--where", value])
                self.assertEqual((got, code), (value, None))

    def test_an_unknown_half_is_a_usage_error(self):
        got, code, err = self.half(["biorex", "--half", "typo"])
        self.assertIsNone(got)
        self.assertEqual(code, 2)
        self.assertIn("cloud|local|all", err)
        self.assertIn("typo", err)

    def test_where_rejects_all_because_it_selects_modules(self):
        """USAGE has always said `--where cloud|local`: `registry.modules("all")` matches
        no provider's `where` and would return nothing."""
        got, code, err = self.half(["--where", "all"])
        self.assertIsNone(got)
        self.assertEqual(code, 2)
        self.assertIn("cloud|local", err)

    def test_a_missing_value_is_still_a_usage_error(self):
        for flag in ("--half", "--where"):
            with self.subTest(flag=flag):
                got, code, err = self.half(["biorex", flag])
                self.assertIsNone(got)
                self.assertEqual(code, 2)
                self.assertIn("needs a value", err)

    def test_the_usage_line_names_both_flags_and_their_values(self):
        self.assertIn("--half cloud|local|all", run.USAGE)
        self.assertIn("--where cloud|local", run.USAGE)


if __name__ == "__main__":
    unittest.main()
