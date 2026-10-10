"""films-extra.json carries TMDB's fields only for a film some area file shows (E10).

Nothing pruned it: 192 of 573 entries named films no area file listed, 26% of the gzipped
file a film sheet downloads, and the client reads it for the film on screen only. The TMDB
pass now projects tmdb-titles.json into it for showing films alone. A dormant entry keeps
every slot not recorded in `ts` byte for byte, the cinema's, a hand correction or text of
unrecorded origin, and its `id`; an entry left with no text goes. tmdb-titles.json stays
whole, so a film that returns gets its fields back from the cache with no request.
Measurements and the options weighed: docs/research/films-extra-retention.md.

TMDB is stubbed on the URL as in test_tmdb_matching, and every film request is recorded.
"""
import contextlib
import datetime
import io
import json
import unittest

import _ctx                                                # noqa: F401
import enrich_tmdb
from test_tmdb_matching import MainHarness

YT = "https://www.youtube.com/watch?v="
W342 = "https://image.tmdb.org/t/p/w342"
CINEMA_FI = "Elokuvateatterin oma synopsis, sellaisenaan."
HAND_SV = "Handrättad svensk text."
TMDB_FI = "TMDB:n suomenkielinen kuvaus."
TMDB_EN = "TMDB's English overview."


def cached(key, mid, fi=TMDB_FI, en=TMDB_EN):
    """A trusted, complete entry read today with a trailer, judged on the search string
    the key gives: neither refresh.due() nor reconsider() sends it back to TMDB."""
    today = datetime.date.today().isoformat()
    return {"i": mid, "x": True, "r": 7.1, "n": 900, "g": [18], "v": f"key{mid}",
            "p": f"/{mid}.jpg", "fi": fi, "en": en, "c": today, "a": today,
            "o": "", "y": "", "ry": "2025", "q": key}


def projected(mid, s, ts):
    """An entry as the pass left it while the film was showing."""
    return {"s": s, "ts": ts, "id": mid, "r": 7.1, "tr": f"{YT}key{mid}",
            "img": f"{W342}/{mid}.jpg"}


class ProjectionTest(MainHarness):

    def setUp(self):
        super().setUp()
        self.requests = []
        # A cinema's Finnish text beside TMDB's English, one entry of TMDB text alone, a
        # hand-corrected Swedish slot, and pre-`ts` text equal to TMDB's own overview.
        self.cache_write({k: cached(k, mid) for k, mid in (
            ("lahtenyt", 11), ("vain tmdb", 12), ("kasin", 13), ("vanha", 14), ("elava", 15))})
        self.films = {
            "lahtenyt": projected(11, {"fi": CINEMA_FI, "en": TMDB_EN}, ["en"]),
            "vain tmdb": projected(12, {"fi": TMDB_FI, "en": ""}, ["fi"]),
            "kasin": projected(13, {"fi": TMDB_FI, "en": TMDB_EN, "sv": HAND_SV}, ["en", "fi"]),
            "vanha": {"s": {"fi": TMDB_FI, "en": ""}, "r": 0, "tr": ""},
        }
        self.extra_write(self.films)
        self.showing()

    def showing(self, *titles, name="area-zz.json"):
        base = {"start": "2026-09-26T18:30:00+03:00", "provider": "zz", "venue": "zz"}
        rows = [{"title": t, **base} for t in ("Elava",) + titles]
        (self.dir / name).write_text(json.dumps({"generated": self.today, "dates": [],
                                                 "horizon": "", "shows": rows}),
                                     encoding="utf-8")

    def extra_write(self, films):
        (self.dir / "films-extra.json").write_text(
            json.dumps({"generated": "2026-09-26", "films": films}), encoding="utf-8")

    def extra(self):
        return json.loads((self.dir / "films-extra.json").read_text(encoding="utf-8"))["films"]

    def extra_bytes(self):
        return (self.dir / "films-extra.json").read_bytes()

    def run_pass(self):
        def fake_get(url, headers, timeout=25):
            if "/genre/movie/list" in url:
                return {"genres": [{"id": 18, "name": "Draama"}]}
            self.requests.append(url)
            if "/search/movie" in url:
                return {"results": []}
            if url.endswith("/videos"):
                return {"results": []}
            return {"overview": "", "vote_count": 900, "vote_average": 7.1, "genres": []}
        real = enrich_tmdb.get
        enrich_tmdb.get = fake_get
        self.addCleanup(lambda: setattr(enrich_tmdb, "get", real))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(enrich_tmdb.main(), 0)

    # -- a film no area file shows ---------------------------------------------------------

    def test_a_dormant_entry_keeps_its_text_byte_for_byte_and_loses_tmdbs_fields(self):
        self.run_pass()
        e = self.extra()["lahtenyt"]
        self.assertEqual(e["s"], {"fi": CINEMA_FI, "en": ""})
        self.assertEqual((e["r"], e["tr"]), (0, ""))
        self.assertNotIn("img", e)
        self.assertNotIn("ts", e)
        self.assertEqual(e["id"], 11, "kept as the record that the text is not TMDB's")

    def test_a_hand_corrected_slot_stays_and_tmdbs_slots_go(self):
        self.run_pass()
        self.assertEqual(self.extra()["kasin"]["s"], {"fi": "", "en": "", "sv": HAND_SV})

    def test_text_of_unrecorded_origin_is_kept(self):
        """Written before `ts` and equal to TMDB's overview: it may be TMDB's, and it may
        be a cinema's copy of the same distributor text. Nothing says, so it stays."""
        self.run_pass()
        self.assertEqual(self.extra()["vanha"]["s"]["fi"], TMDB_FI)

    def test_an_entry_holding_only_tmdbs_text_goes(self):
        self.run_pass()
        self.assertNotIn("vain tmdb", self.extra())

    def test_tmdb_titles_is_kept_whole(self):
        before = self.cache()
        self.run_pass()
        self.assertEqual(self.cache(), before)
        self.assertEqual(self.requests, [], "a dormant film costs no request")

    def test_the_next_pass_repopulates_nothing_and_writes_the_same_bytes(self):
        self.run_pass()
        first = self.extra_bytes()
        self.run_pass()
        self.assertEqual(self.extra_bytes(), first)
        self.assertNotIn("img", self.extra()["lahtenyt"])

    # -- the film comes back ---------------------------------------------------------------

    def test_a_returning_film_regains_its_fields_from_the_cache_with_no_request(self):
        self.run_pass()
        self.showing("Lahtenyt")
        self.run_pass()
        e = self.extra()["lahtenyt"]
        self.assertEqual(self.requests, [], "restoring the projection looked nothing up")
        self.assertEqual(e["s"], {"fi": CINEMA_FI, "en": TMDB_EN})
        self.assertEqual(e["ts"], ["en"], "the cinema's Finnish is still the cinema's")
        self.assertEqual((e["id"], e["r"], e["tr"], e["img"]),
                         (11, 7.1, f"{YT}key11", f"{W342}/11.jpg"))

    def test_a_removed_entry_comes_back_whole(self):
        self.run_pass()
        self.showing("Vain TMDB")
        self.run_pass()
        e = self.extra()["vain tmdb"]
        self.assertEqual(self.requests, [])
        self.assertEqual((e["s"]["fi"], e["s"]["en"]), (TMDB_FI, TMDB_EN))
        self.assertEqual(e["ts"], ["en", "fi"])

    def test_a_kept_slot_equal_to_tmdbs_text_stays_the_cinemas_across_a_return(self):
        """The reason `id` stays. Without it the return would take the pre-`ts` rule and
        record a cinema's slot equal to TMDB's overview as TMDB's, and the next dormancy
        would delete it."""
        self.films["lahtenyt"]["s"]["fi"] = TMDB_FI      # the distributor's text, both ways
        self.extra_write(self.films)
        self.run_pass()
        self.showing("Lahtenyt")
        self.run_pass()
        self.assertEqual(self.extra()["lahtenyt"]["ts"], ["en"])
        self.showing()
        self.run_pass()
        self.assertEqual(self.extra()["lahtenyt"]["s"]["fi"], TMDB_FI)

    # -- what counts as showing ------------------------------------------------------------

    def test_a_finnkino_title_counts_as_showing(self):
        """The pass skips Finnkino's files for its own lookups, but the client shows those
        films too."""
        self.showing("Lahtenyt", name="area-1004.json")
        self.run_pass()
        self.assertEqual(self.extra()["lahtenyt"]["img"], f"{W342}/11.jpg")

    def test_an_unreadable_area_file_strips_nothing(self):
        (self.dir / "area-broken.json").write_text("{ not json", encoding="utf-8")
        self.run_pass()
        self.assertEqual(self.extra()["lahtenyt"]["img"], f"{W342}/11.jpg")
        self.assertIn("vain tmdb", self.extra())


if __name__ == "__main__":
    unittest.main()
