"""The Finnkino poster download: a checked id, a decoded body, an atomic write, a retry.

`download_poster` put OCAPI's release id into the path unchecked (`../../escape` wrote two
levels above data/posters), saved whatever came back without decoding it (a body cut short
at 29,126 of 58,252 bytes is not an error from `common.fetch`), wrote it in place, and
returned an existing file on every later run without a request, broken or not (audit E5,
2026-09-25). The ids are the moviexchange release UUIDs; all 84 committed Finnkino posters
are named by one. The body used here is one of those files.
"""
import os
import pathlib
import re
import tempfile
import unittest

import _ctx                                                # noqa: F401
import fetch_data

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.jpg")
REAL = sorted(p for p in (_ctx.ROOT / "data/posters").glob("*.jpg") if UUID.fullmatch(p.name))[0]
GOOD = REAL.read_bytes()
TRUNCATED = GOOD[: len(GOOD) // 2]
RID = "0040c9a4-3ca0-4580-a920-596e67e160ab"


class DownloadPosterTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)
        fetch_data._poster_cache.clear()
        self.addCleanup(fetch_data._poster_cache.clear)
        self.asked, self.body = [], GOOD
        real = fetch_data.http_get

        def http_get(url, headers, timeout=25):
            self.asked.append(url)
            return self.body
        fetch_data.http_get = http_get
        self.addCleanup(lambda: setattr(fetch_data, "http_get", real))

    def poster(self):
        return self.root / f"data/posters/{RID}.jpg"

    def test_a_good_body_is_written_whole_and_leaves_no_temp_file(self):
        self.assertEqual(fetch_data.download_poster(RID), f"data/posters/{RID}.jpg")
        self.assertEqual(self.poster().read_bytes(), GOOD)
        self.assertEqual([p.name for p in self.poster().parent.iterdir()], [self.poster().name])

    def test_an_id_that_is_not_a_release_uuid_is_never_a_path_or_a_request(self):
        for rid in ("../../escape", "a/b", "", "0040c9a4.jpg"):
            with self.subTest(rid=rid):
                self.assertEqual(fetch_data.download_poster(rid), "")
        self.assertEqual(self.asked, [])
        self.assertEqual(sorted(p.name for p in self.root.rglob("*") if p.is_file()), [])

    def test_a_body_that_does_not_decode_is_not_saved(self):
        self.body = TRUNCATED
        self.assertEqual(fetch_data.download_poster(RID), "")
        self.assertFalse(self.poster().exists())

    def test_a_broken_file_already_on_disk_is_fetched_again(self):
        self.poster().parent.mkdir(parents=True)
        self.poster().write_bytes(TRUNCATED)
        self.assertEqual(fetch_data.download_poster(RID), f"data/posters/{RID}.jpg")
        self.assertEqual(len(self.asked), 1)
        self.assertEqual(self.poster().read_bytes(), GOOD)

    def test_a_good_file_already_on_disk_costs_no_request(self):
        self.poster().parent.mkdir(parents=True)
        self.poster().write_bytes(GOOD)
        self.assertEqual(fetch_data.download_poster(RID), f"data/posters/{RID}.jpg")
        self.assertEqual(self.asked, [])


if __name__ == "__main__":
    unittest.main()
