"""Finnkino's EiText attribute (OCAPI 0000000060, "ei tekstitystä") is published as XX-S.

`main()` runs with OCAPI stubbed by URL, as in test_finnkino_empty_venue.py.
"""
import contextlib
import io
import json
import os
import pathlib
import tempfile
import types
import unittest

import _ctx                                                # noqa: F401
import fetch_data


SITES = [{"id": 1, "name": {"text": "Tennispalatsi"}}]

ATTRIBUTES = [
    {"id": "0000000066", "shortName": {"text": "FI-A"}},
    {"id": "0000000065", "shortName": {"text": "FI-S"}},
    {"id": "0000000060",
     "shortName": {"text": "EiText", "translations": [{"languageTag": "en", "text": "XX"}]},
     "name": {"text": "ei tekstitystä"}},
    {"id": "0000000099", "shortName": {"text": "Mystery"}},
    {"id": "0000000098",
     "shortName": {"text": "Other", "translations": [{"languageTag": "en", "text": "XX"}]}},
]

# Case name -> attributeIds, in the order OCAPI lists them.
CASES = {
    "eitext": ["0000000060", "0000000066"],
    "absent": ["0000000066"],
    "unknown": ["0000000066", "0000000099"],
    "english_xx": ["0000000066", "0000000098"],
    "named_subs": ["0000000060", "0000000065"],
}


def showtimes_for(date):
    return {
        "relatedData": {
            "films": [{"id": 10, "title": {"text": "Filmi A"},
                       "originalTitle": {"text": "Film A"},
                       "releaseDate": "2026-01-01", "runtimeInMinutes": 100,
                       "genreIds": [], "censorRatingId": 1, "externalIds": {}}],
            "genres": [], "attributes": ATTRIBUTES,
            "screens": [{"id": 5, "name": {"text": "Sali 1"}}],
            "censorRatings": [{"id": 1, "classification": {"text": "S"}}],
        },
        "showtimes": [
            {"id": f"{date}-{name}", "filmId": 10, "siteId": 1, "screenId": 5,
             "attributeIds": ids, "schedule": {"startsAt": f"{date}T{12 + i}:00:00"}}
            for i, (name, ids) in enumerate(CASES.items())
        ],
    }


class NoSubtitlesTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        cwd = os.getcwd()
        os.chdir(root)
        cls.addClassCleanup(os.chdir, cwd)

        saved = {k: os.environ.get(k) for k in ("FINNKINO_TOKEN", "TMDB_TOKEN")}
        os.environ["FINNKINO_TOKEN"] = "stub-token"
        os.environ.pop("TMDB_TOKEN", None)

        def restore_env():
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        cls.addClassCleanup(restore_env)

        def http_get(url, headers, timeout=25):
            if url.endswith("/sites"):
                return json.dumps({"sites": SITES})
            if "/showtimes/by-business-date/" in url:
                date = url.split("/by-business-date/")[1].split("?")[0]
                return json.dumps(showtimes_for(date))
            raise AssertionError(f"unexpected request: {url}")

        real_get, real_time = fetch_data.http_get, fetch_data.time
        fetch_data.http_get = http_get
        fetch_data.time = types.SimpleNamespace(sleep=lambda *_: None)
        cls.addClassCleanup(lambda: setattr(fetch_data, "http_get", real_get))
        cls.addClassCleanup(lambda: setattr(fetch_data, "time", real_time))
        fetch_data._poster_cache.clear()

        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            cls.rc = fetch_data.main()
        cls.stdout = out.getvalue()
        doc = json.loads((root / "data" / "area-1.json").read_text())
        cls.shows = doc["shows"]

    def lang(self, case):
        """The lang of every published row for one case, across the seven dates."""
        langs = {s["lang"] for s in self.shows
                 if s["url"].split("showtimeId=")[1].endswith(f"-{case}")}
        self.assertEqual(len(langs), 1, (case, langs))
        return langs.pop()

    def attrs_line(self):
        lines = [ln for ln in self.stdout.splitlines() if ln.startswith("[attrs]")]
        self.assertEqual(len(lines), 1, self.stdout)
        return lines[0]

    def test_the_run_publishes_every_case_on_every_date(self):
        self.assertEqual(self.rc, 0)
        self.assertEqual(len(self.shows), 7 * len(CASES))

    def test_eitext_follows_the_audio_tag_whatever_the_order(self):
        self.assertEqual(self.lang("eitext"), "FI-A, XX-S")

    def test_eitext_is_not_logged_as_dropped(self):
        self.assertNotIn("EiText", self.attrs_line())

    def test_no_attribute_states_no_subtitle_part(self):
        self.assertEqual(self.lang("absent"), "FI-A")

    def test_an_unknown_attribute_is_still_logged_and_adds_nothing(self):
        self.assertEqual(self.lang("unknown"), "FI-A")
        self.assertIn("Mystery", self.attrs_line())

    def test_an_english_xx_on_another_attribute_is_not_read(self):
        self.assertEqual(self.lang("english_xx"), "FI-A")
        self.assertIn("Other", self.attrs_line())

    def test_a_named_subtitle_language_wins(self):
        self.assertEqual(self.lang("named_subs"), "FI-S")


if __name__ == "__main__":
    unittest.main()
