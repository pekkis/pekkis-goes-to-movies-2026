"""A combined view names a film by its group, and the name must not depend on file order.

`mergeIds` joins shows by title key and by TMDB id with a union-find, and used the root as
the film's id. The root was the key of whichever show joined last, so on Kotka's data of
2026-09-24 dropping the first day changed the id from "kojootti vs acme englanniksi" to
"kojootti vs acme", and a `#m=` link made the day before opened "Ei näytöksiä". The group
is now named by its sorted-first title key, and `showSheet` resolves a link naming any
member's own key through `sheetId`, so a link made before this change still opens.

Sliced verbatim out of index.html by tests/merge_ids_harness.js.
"""
import json
import pathlib
import re
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "merge_ids_harness.js"
ACME, MUTINY = "kojootti vs acme", "mutiny"


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class MergeIdsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    def test_every_order_gives_every_show_the_same_id(self):
        want = {"1": ACME, "2": ACME, "3": ACME, "4": MUTINY, "5": MUTINY, "6": "autofiktio"}
        for order, got in self.r["orders"].items():
            with self.subTest(order=order):
                self.assertEqual(got["ids"], want)

    def test_a_day_leaving_does_not_rename_the_film(self):
        self.assertEqual(self.r["dropped"], {"2": ACME, "3": ACME, "4": MUTINY,
                                             "5": MUTINY, "6": "autofiktio"})

    def test_each_show_keeps_its_own_key(self):
        for order, got in self.r["orders"].items():
            with self.subTest(order=order):
                self.assertEqual(got["own"]["1"], "kojootti vs acme englanniksi")
                self.assertEqual(got["own"]["4"], "mutiny lavastettu syylliseksi")

    def test_a_link_naming_any_member_opens_the_group(self):
        res = self.r["resolve"]
        self.assertEqual(res["kojootti vs acme englanniksi"], ACME,
                         "the id Kotka's links carried before 2026-09-24")
        self.assertEqual(res[ACME], ACME)
        self.assertEqual(res["mutiny lavastettu syylliseksi"], MUTINY)
        self.assertEqual(res["autofiktio"], "autofiktio")

    def test_a_link_naming_nothing_is_left_as_it_came(self):
        self.assertEqual(self.r["resolve"]["ei tätä elokuvaa"], "ei tätä elokuvaa")
        self.assertEqual(self.r["resolve"][""], "")


class ShowSheetResolvesTest(unittest.TestCase):
    def test_the_sheet_filters_on_the_resolved_id(self):
        """The wiring is outside the sliced block, so it is held here."""
        html = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")
        m = re.search(r"async function showSheet\(fid, want, keepFocus\)\{(.*?)\n  \}\n", html, re.S)
        self.assertIsNotNone(m)
        body = m.group(1)
        at = body.find("fid = sheetId(cached, fid);")
        self.assertGreater(at, -1, "showSheet no longer resolves the link's id")
        self.assertLess(at, body.find(".filter(s => s.eventId === fid)"))


if __name__ == "__main__":
    unittest.main()
