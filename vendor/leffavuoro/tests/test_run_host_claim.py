"""run.py publishes a site only after its host claims are released and checked.

`run.run_sites` wrapped the whole of `run_site`, fetch and publish, in `common.reading`, so
a `HostBusy` an adapter swallowed was re-raised only after the site's files were written:
its area file and `venues-{p}.json` (`status: ok`) went live while the log said FAILED
(audit C2, 2026-09-25). `run_cloud` already fetched inside the claim and published outside
it. The host here is held by another site beforehand, so nothing is sent anywhere.
"""
import contextlib
import io
import pathlib
import sys
import tempfile
import types
import unittest

import _ctx                                                # noqa: F401
import common
import run
from test_run_partial import show


def module(name):
    mod = types.ModuleType(name)
    mod.SITES = [{"provider": "zzclaim", "label": "Claim", "base": "https://own.zzclaim.test",
                  "venues": [{"id": "zzclaim-v", "name": "Claim", "short": "Claim",
                              "city": "Espoo"}]}]

    def fetch_site(site):
        try:
            common.fetch("https://held.zzclaim.test/film/1")
        except common.HostBusy:
            pass                                 # an adapter catching around a film page
        return {"zzclaim-v": [dict(show("Film", "2027-01-09T18:00:00+02:00"),
                                   venue="zzclaim-v", provider="zzclaim")]}
    mod.fetch_site = fetch_site
    return mod


class SwallowedRefusalTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = pathlib.Path(tmp.name)
        saved = run.OUT, common.HOST_CLAIM_WAIT
        run.OUT, common.HOST_CLAIM_WAIT = self.out, 0.05
        self.addCleanup(lambda: (setattr(run, "OUT", saved[0]),
                                 setattr(common, "HOST_CLAIM_WAIT", saved[1])))
        with common._host_cv:
            common._host_owner["held.zzclaim.test"] = "another-site"
        self.addCleanup(lambda: common._host_owner.pop("held.zzclaim.test", None))

    def test_the_site_fails_and_writes_nothing(self):
        mod = module("zz_claim_mod")
        sys.modules[mod.__name__] = mod
        self.addCleanup(sys.modules.pop, mod.__name__, None)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = run.main([mod.__name__, "--half", "all"])
        self.assertEqual(code, 1, out.getvalue())
        self.assertIn("[zzclaim] FAILED:", out.getvalue())
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), [],
                         "a file went live for a site that failed")


if __name__ == "__main__":
    unittest.main()
