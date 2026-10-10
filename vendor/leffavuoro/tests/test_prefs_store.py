"""A stored `kino-prefs` that is valid JSON but not an object must not break the app.

`prefs.get` returned `JSON.parse` of whatever was stored, so `null` came back as null and
boot's `prefs.get().lang` threw before anything was drawn, on every load. `prefs.set`
could not repair it: `Object.assign(null, ...)` throws inside its own try, so the bad
value stayed stored for good. Anything that is not a plain object now reads as `{}`, and
the next `set` overwrites it. The key is unchanged: renaming `kino-prefs` would wipe
every reader's saved venue, star and view.

Sliced verbatim out of index.html by tests/prefs_harness.js. The status page reads the
same key with the same guard: without it a stored `null` left that page on its checking
state with no language buttons (prior review #20).
"""
import json
import pathlib
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "prefs_harness.js"


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class PrefsStoreTest(unittest.TestCase):
    PAGE = "index.html"

    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS), cls.PAGE], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    NOT_OBJECTS = ("null_json", "number", "string", "boolean", "array")

    def test_a_stored_value_that_is_not_an_object_reads_as_empty(self):
        for k in self.NOT_OBJECTS:
            with self.subTest(stored=k):
                self.assertNotIn("threw", self.r[k])
                self.assertEqual(self.r[k]["get"], {})
                self.assertFalse(self.r[k]["getIsArray"])
                self.assertIsNone(self.r[k]["lang"])

    def test_the_next_set_repairs_it(self):
        """The value was stuck: set() could not write over it."""
        for k in self.NOT_OBJECTS:
            with self.subTest(stored=k):
                self.assertNotIn("setThrew", self.r[k])
                self.assertEqual(json.loads(self.r[k]["after"]), {"lang": "sv"})

    def test_saved_prefs_are_read_and_kept(self):
        """The counterweight: a real saved object loses nothing to the guard."""
        s = self.r["saved"]
        self.assertEqual(s["get"], {"fav": "1103", "view": "times", "lang": "en"})
        self.assertEqual(json.loads(s["after"]), {"fav": "1103", "view": "times", "lang": "sv"})

    def test_missing_and_torn_still_read_as_empty(self):
        for k in ("missing", "empty_obj", "torn"):
            with self.subTest(stored=k):
                self.assertEqual(self.r[k]["get"], {})
                self.assertEqual(json.loads(self.r[k]["after"]), {"lang": "sv"})

    def test_the_key_is_not_renamed(self):
        for k, v in self.r.items():
            with self.subTest(stored=k):
                self.assertEqual(v["keys"], ["kino-prefs"])


class StatusPagePrefsStoreTest(PrefsStoreTest):
    PAGE = "status/index.html"


if __name__ == "__main__":
    unittest.main()
