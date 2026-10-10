"""The combined venue files: one per half, built from the provider files, one writer each.

`data/venuelists-local.json` and `data/venuelists-cloud.json` carry every provider file of
their half verbatim, so the client makes two requests where it made 82. These pin:

- a half's file holds its own providers and nobody else's, Finnkino in neither;
- a provider file that does not parse is left out, so the client fetches it on its own;
- nothing is written when nothing would change, or when the half has no file yet;
- run.py rewrites the half it fetched for and only that one, a failed run included;
- the committed combined files are what the committed provider files build, which is the
  drift check the Checks workflow also runs through scripts/build_venuelists.py.
"""
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import types
import unittest

import _ctx

import common
import registry
import run
import venuelists

DATA = _ctx.ROOT / "data"
LOCAL, CLOUD = "regina", "biorex"          # one real provider of each half


def provider_file(pid, generated="2026-09-26T06:00:00+00:00"):
    return {"generated": generated, "oldest": generated, "status": "ok", "stale": [],
            "unverified": [], "pending": [], "provider": pid,
            "venues": [{"id": f"{pid}-x", "name": pid, "short": pid, "city": "Espoo"}]}


class BuildTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = pathlib.Path(tmp.name)

    def put(self, pid, doc=None, raw=None):
        (self.out / f"venues-{pid}.json").write_text(
            raw if raw is not None else json.dumps(doc or provider_file(pid)), encoding="utf-8")

    def test_the_registry_splits_the_providers_into_two_halves(self):
        self.assertEqual(registry.by_id(LOCAL)["where"], "local")
        self.assertEqual(registry.by_id(CLOUD)["where"], "cloud")
        both = set(venuelists.providers_of("local")) | set(venuelists.providers_of("cloud"))
        self.assertNotIn("finnkino", both, "its list is areas.json")
        self.assertEqual(set(venuelists.providers_of("local"))
                         & set(venuelists.providers_of("cloud")), set())

    def test_each_half_carries_its_own_providers_verbatim(self):
        self.put(LOCAL); self.put(CLOUD); self.put("not-a-provider")
        local, cloud = venuelists.build(self.out, "local"), venuelists.build(self.out, "cloud")
        self.assertEqual(local, {"half": "local", "providers": {LOCAL: provider_file(LOCAL)}})
        self.assertEqual(cloud, {"half": "cloud", "providers": {CLOUD: provider_file(CLOUD)}})

    def test_a_provider_file_that_does_not_parse_is_left_out(self):
        self.put(LOCAL); self.put("engel", raw='{"generated": "2026-09-26", "venues": [')
        self.assertEqual(list(venuelists.build(self.out, "local")["providers"]), [LOCAL])

    def test_nothing_is_written_for_a_half_with_no_file(self):
        self.put(CLOUD)
        self.assertFalse(venuelists.write(self.out, "local"))
        self.assertFalse(venuelists.path_for(self.out, "local").exists())

    def test_an_unchanged_file_is_not_rewritten(self):
        self.put(CLOUD)
        self.assertTrue(venuelists.write(self.out, "cloud"))
        self.assertFalse(venuelists.write(self.out, "cloud"))
        self.put(CLOUD, provider_file(CLOUD, "2026-09-26T08:00:00+00:00"))
        self.assertTrue(venuelists.write(self.out, "cloud"))
        doc = json.loads(venuelists.path_for(self.out, "cloud").read_text(encoding="utf-8"))
        self.assertEqual(doc["providers"][CLOUD]["generated"], "2026-09-26T08:00:00+00:00")

    def test_a_site_belongs_to_its_providers_half(self):
        self.assertEqual(venuelists.halves_of([{"provider": LOCAL}, {"provider": CLOUD}]),
                         {"local", "cloud"})
        self.assertEqual(venuelists.halves_of([{"provider": "fake"}]), set())


class FakeModule(types.ModuleType):
    """One site of a real provider, fetched without the network."""

    def __init__(self, pid, fail=False):
        super().__init__("venuelists_fake")
        self.pid, self.fail = pid, fail
        self.SITES = [{"provider": pid, "label": pid,
                       "venues": [{"id": f"{pid}-x", "name": pid, "short": pid,
                                   "city": "Espoo"}]}]

    def fetch_site(self, site):
        if self.fail:
            raise RuntimeError("connection reset")
        s = {k: ("" if t is str else False) for k, t in common.Show.__annotations__.items()}
        s.update(eventId="e1", title="Autofiktio", start="2099-01-01T18:00:00+02:00",
                 url="https://example.org/x", provider=self.pid, venue=f"{self.pid}-x",
                 theatre=self.pid)
        return {f"{self.pid}-x": [s]}


class RunWritesItsHalfTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = pathlib.Path(tmp.name)
        saved = run.OUT
        run.OUT = self.out
        self.addCleanup(lambda: setattr(run, "OUT", saved))
        self.addCleanup(lambda: sys.modules.pop("venuelists_fake", None))

    def main(self, mod):
        sys.modules["venuelists_fake"] = mod
        with contextlib.redirect_stdout(io.StringIO()) as out, \
                contextlib.redirect_stderr(io.StringIO()):
            code = run.main(["venuelists_fake", "--half", "all"])
        return code, out.getvalue()

    def test_a_run_rewrites_the_half_it_fetched_for_and_no_other(self):
        (self.out / f"venues-{CLOUD}.json").write_text(json.dumps(provider_file(CLOUD)),
                                                        encoding="utf-8")
        code, log = self.main(FakeModule(LOCAL))
        self.assertEqual(code, 0, log)
        local = json.loads(venuelists.path_for(self.out, "local").read_text(encoding="utf-8"))
        written = json.loads((self.out / f"venues-{LOCAL}.json").read_text(encoding="utf-8"))
        self.assertEqual(local["providers"], {LOCAL: written})
        self.assertFalse(venuelists.path_for(self.out, "cloud").exists(),
                         "the local half wrote the cloud half's file")
        self.assertIn("[run] venuelists-local.json rewritten", log)

    def test_a_failed_site_leaves_the_combined_file_as_its_provider_file_stands(self):
        """The failed fetch keeps the previous provider file, and the combined file is
        rebuilt from it: the two still agree, which is what the drift check reads."""
        prev = provider_file(LOCAL, "2026-09-25T06:00:00+00:00")
        (self.out / f"venues-{LOCAL}.json").write_text(json.dumps(prev), encoding="utf-8")
        code, _ = self.main(FakeModule(LOCAL, fail=True))
        self.assertNotEqual(code, 0)
        local = json.loads(venuelists.path_for(self.out, "local").read_text(encoding="utf-8"))
        self.assertEqual(local["providers"], {LOCAL: prev})


class CommittedFilesTest(unittest.TestCase):
    """The committed combined files are what the committed provider files build."""

    def test_both_combined_files_match_the_provider_files(self):
        for half in venuelists.HALVES:
            with self.subTest(half=half):
                built = venuelists.build(DATA, half)
                committed = venuelists.path_for(DATA, half).read_text(encoding="utf-8")
                self.assertEqual(committed, venuelists.text_of(built),
                                 f"run scripts/build_venuelists.py: {half} drifted")

    def test_together_they_carry_every_provider_but_finnkino(self):
        carried = set()
        for half in venuelists.HALVES:
            doc = json.loads(venuelists.path_for(DATA, half).read_text(encoding="utf-8"))
            carried |= set(doc["providers"])
        expected = {f.stem[len("venues-"):] for f in DATA.glob("venues-*.json")}
        self.assertEqual(carried, expected)


if __name__ == "__main__":
    unittest.main()
