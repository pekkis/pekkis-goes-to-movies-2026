"""One title key, and the four places that have to produce it.

`enrich_tmdb.norm`, `synmerge.norm` and `normTitle()` in `index.html` are pinned against
each other elsewhere. `scripts/fetch_data.py` carried a fourth, `_tnorm`, whose docstring
said it "must behave like enrich_tmdb.norm()" and which did not: it left the underscore
in, because Python's `\\w` counts it as a word character while the client's `\\p{L}\\p{N}`
does not. `Dyyni: Osa_kolme` keyed as `dyyni osa_kolme` in the Finnkino pass and
`dyyni osa kolme` in every other, so an alias or a cache entry written by one was
unreachable from the other.

Measured on 2026-09-19 before the change: `data/tmdb.json` 72 keys and
`data/tmdb-titles.json` 517, none with an underscore, and of the 11 underscored keys in
`scripts/providers/tmdb-aliases.json` all 11 are `_comment*` documentation that the
loader drops with `startswith("_")`. So nothing was unreachable in practice and no rekey
was needed: a latent divergence closed before it fired.
"""
import pathlib
import sys
import unittest

import _ctx                                                # noqa: F401
import enrich_tmdb
import synmerge

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import fetch_data                                          # noqa: E402


CASES = [
    "Dyyni: Osa_kolme",
    "Dyyni: Osa kolme",
    "_alaviiva_alussa_",
    "Spider-Man: Brand New Day",
    "Kojootti vs. ACME (suomeksi)",
    "Ryhmä Hau: Dinoelokuva",
    "Hetki  ennen   valoa",
    "",
]


class TitleKeyTest(unittest.TestCase):
    def test_the_finnkino_pass_uses_the_same_key_as_the_others(self):
        for t in CASES:
            with self.subTest(title=t):
                self.assertEqual(fetch_data._tnorm(t), enrich_tmdb.norm(t))
                self.assertEqual(fetch_data._tnorm(t), synmerge.norm(t))

    def test_the_underscore_is_the_case_that_diverged(self):
        self.assertEqual(fetch_data._tnorm("Dyyni: Osa_kolme"), "dyyni osa kolme")
        self.assertEqual(fetch_data._tnorm("Dyyni: Osa_kolme"),
                         fetch_data._tnorm("Dyyni: Osa kolme"))

    def test_it_is_the_same_function_rather_than_a_copy_that_agrees_today(self):
        """A copy drifts. This one is the import."""
        self.assertIs(fetch_data._tnorm, enrich_tmdb.norm)

    def test_no_committed_key_needs_rekeying(self):
        """If this ever fails, a key written under the old rule is unreachable and has to
        be migrated in the same commit as whatever wrote it."""
        import json
        root = pathlib.Path(__file__).resolve().parents[1]
        for name in ("data/tmdb.json", "data/tmdb-titles.json"):
            f = root / name
            if not f.exists():
                continue
            keys = json.loads(f.read_text())
            with self.subTest(file=name):
                self.assertEqual([k for k in keys if "_" in k], [])
        aliases = json.loads((root / "scripts/providers/tmdb-aliases.json").read_text())
        self.assertEqual([k for k in aliases if "_" in k and not k.startswith("_")], [])


if __name__ == "__main__":
    unittest.main()
