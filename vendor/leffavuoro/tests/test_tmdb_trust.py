"""Only a trusted TMDB match may supply public film metadata.

Kino Regina's "Naisen kasvot" (1938) matched nothing exactly, and the popularity fallback
was TMDB 4780, De Palma's "Obsession" (1976). The weak flag withheld the `tmdbId`, but the
wrong film's poster, rating, votes, trailer, genre ids and synopses were written onto the
show and into films-extra.json all the same, and run.py carries those fields from the
previous venue file into every later run. An alias corrected that one film; this file
pins the rule for the rest: a weak or unmatched candidate publishes nothing, the cinema's
own fields stay, and what an earlier run published from a weak candidate is taken back
by the next pass.

Same harness as test_tmdb_matching: TMDB is a dispatch on the URL, here with a detail and
a video table as well, so the weak candidate can carry a complete set of attractive
metadata.
"""
import contextlib
import io
import json
import types
import unittest

import _ctx                                                # noqa: F401
import build_pages
import enrich_tmdb
import mirror_posters
from test_tmdb_matching import MainHarness, hit

# The historical mismatch. The production alias for the title is not consulted here: the
# harness points ALIAS_FILE at an empty temporary directory.
OBSESSION = hit(4780, "Obsession", 1976)
WRONG = {"fi": "Väärä elokuva, väärä teksti.", "en": "Wrong film, wrong text.",
         "n": 1200, "r": 7.3, "g": [53], "v": "wrongkey"}
RIGHT = {"fi": "Oikea teksti.", "en": "Right text.", "n": 300, "r": 6.8, "g": [18], "v": "rightkey"}
W342 = "https://image.tmdb.org/t/p/w342"


def mirrored(poster_path):
    """Where mirror_posters puts a TMDB poster, which is how an earlier run left it."""
    return f"data/posters/{mirror_posters.key_for(W342 + poster_path)}.jpg"


def regina(**over):
    """Naisen kasvot as Kino Regina publishes it: every field is the cinema's own."""
    return {"title": "Naisen kasvot", "original": "En kvinnas ansikte", "year": "1938",
            "img": "https://kinoregina.fi/posters/naisen-kasvot.jpg", "rating": "K-12",
            "len": "100", "genres": "Draama", "provider": "regina", "venue": "regina", **over}


class TrustHarness(MainHarness):

    def run_main(self, table, detail=None, videos=None):
        detail, videos = detail or {}, videos or {}

        def fake_get(url, headers, timeout=25):
            if "/genre/movie/list" in url:
                return {"genres": [{"id": 18, "name": "Draama"}, {"id": 53, "name": "Jännitys"}]}
            if "/search/movie" in url:
                import urllib.parse
                q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
                key = (q["query"][0], (q.get("primary_release_year") or [""])[0])
                self.searches.append(key)
                return {"results": table.get(key, [])}
            mid = int(url.split("/movie/")[1].split("/")[0].split("?")[0])
            if url.endswith("/videos"):
                key = videos.get(mid)
                return {"results": [{"site": "YouTube", "type": "Trailer", "official": True,
                                     "key": key}] if key else []}
            d = detail.get(mid) or {}
            lang = "fi" if "language=fi-FI" in url else "en"
            return {"overview": d.get(lang, ""), "vote_count": d.get("n"),
                    "vote_average": d.get("r"), "genres": [{"id": g} for g in d.get("g", [])],
                    "poster_path": d.get("p", f"/{mid}.jpg")}
        real = enrich_tmdb.get
        enrich_tmdb.get = fake_get
        self.addCleanup(lambda: setattr(enrich_tmdb, "get", real))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = enrich_tmdb.main()
        self.assertEqual(code, 0)
        return buf.getvalue()

    def area(self):
        return json.loads((self.dir / "area-zz.json").read_text(encoding="utf-8"))

    def extra(self):
        return json.loads((self.dir / "films-extra.json").read_text(encoding="utf-8"))["films"]

    def extra_write(self, films):
        (self.dir / "films-extra.json").write_text(
            json.dumps({"generated": "2026-09-01", "films": films}), encoding="utf-8")

    def weak_naisen_kasvot(self):
        """The search as it went on 2026-09-13: nothing exact, Obsession as the fallback."""
        self.run_main({("Naisen kasvot", ""): [OBSESSION]},
                      detail={4780: WRONG}, videos={4780: WRONG["v"]})
        e = self.cache()["naisen kasvot"]
        self.assertEqual((e["i"], e["x"]), (4780, False), "the candidate stays weak")
        return e

    def assert_no_tmdb_fields(self, show):
        for field in ("tmdb", "votes", "tr", "gids", "tmdbId"):
            self.assertNotIn(field, show, f"{field} came from the weak candidate")
        self.assertFalse((show.get("img") or "").startswith(W342), "a TMDB poster")
        self.assertNotEqual(show.get("img"), mirrored("/4780.jpg"), "the mirrored TMDB poster")

    def assert_no_tmdb_extra(self, key):
        fx = self.extra().get(key) or {}
        for field in ("r", "tr", "img"):
            self.assertFalse(fx.get(field), f"films-extra {field} came from the weak candidate")
        self.assertFalse((fx.get("s") or {}).get("en"), "the weak candidate's English synopsis")
        return fx


class WeakCandidateTest(TrustHarness):

    # 1. a complete set of attractive but wrong metadata contributes nothing
    def test_a_weak_candidate_publishes_nothing(self):
        self.shows(regina())
        self.weak_naisen_kasvot()
        show = self.area()["shows"][0]
        self.assert_no_tmdb_fields(show)
        fx = self.assert_no_tmdb_extra("naisen kasvot")
        self.assertFalse((fx.get("s") or {}).get("fi"), "the weak candidate's Finnish synopsis")

    # 2. the cinema's own fields survive that same case
    def test_provider_fields_survive(self):
        self.shows(regina())
        self.extra_write({"naisen kasvot": {"s": {"fi": "Reginan oma teksti.", "en": ""},
                                            "r": 0, "tr": ""}})
        self.weak_naisen_kasvot()
        show = self.area()["shows"][0]
        for field, value in regina().items():
            self.assertEqual(show.get(field), value, field)
        self.assertEqual(self.extra()["naisen kasvot"]["s"]["fi"], "Reginan oma teksti.")

    # 3. a trusted exact match still enriches
    def test_an_exact_match_enriches_as_before(self):
        self.shows({"title": "Naisen kasvot", "original": "En kvinnas ansikte", "year": "1938"})
        right = hit(76848, "Naisen kasvot", 1938, original="En kvinnas ansikte")
        self.run_main({("Naisen kasvot", "1938"): [right]},
                      detail={76848: RIGHT}, videos={76848: RIGHT["v"]})
        show = self.area()["shows"][0]
        self.assertEqual((show["tmdbId"], show["tmdb"], show["votes"], show["gids"]),
                         (76848, 6.8, 300, [18]))
        self.assertEqual(show["tr"], "https://www.youtube.com/watch?v=rightkey")
        self.assertEqual(show["img"], W342 + "/76848.jpg")
        fx = self.extra()["naisen kasvot"]
        # The pass stops at a Finnish overview and reads the English one only when there
        # is none, so `en` stays empty here.
        self.assertEqual((fx["s"]["fi"], fx["s"]["en"], fx["r"]), ("Oikea teksti.", "", 6.8))
        self.assertEqual((fx["img"], fx["tr"]),
                         (W342 + "/76848.jpg", "https://www.youtube.com/watch?v=rightkey"))

    # 4. a verified alias still enriches
    def test_an_alias_id_enriches_as_before(self):
        self.shows(regina(img=""))
        (self.dir / "tmdb-aliases.json").write_text(json.dumps({"naisen kasvot": "76848"}))
        self.run_main({("Naisen kasvot", ""): [OBSESSION]},
                      detail={76848: RIGHT, 4780: WRONG}, videos={76848: RIGHT["v"]})
        show = self.area()["shows"][0]
        self.assertEqual((show["tmdbId"], show["tmdb"], show["gids"]), (76848, 6.8, [18]))
        self.assertEqual(show["img"], W342 + "/76848.jpg")
        self.assertEqual(self.extra()["naisen kasvot"]["s"]["fi"], "Oikea teksti.")
        self.assertEqual(self.searches, [], "an alias id is not searched")


class ContaminatedDataTest(TrustHarness):
    """What the runs before this rule left behind, and a normal pass taking it back.

    The films-extra entries record what the pass wrote, `id` and `ts`, since 2026-09-24:
    an English slot with no record is the cinema's, because adapters declare English
    too, so residue is seeded in the shape the pass leaves it."""

    def seed(self, fi="Väärä elokuva, väärä teksti.", img=None):
        # run.py carried these from the previous venue file; the adapter published no
        # poster, so the mirrored TMDB one was carried too.
        self.shows(regina(img=img if img is not None else mirrored("/4780.jpg"),
                          tmdb=7.3, votes=1200, gids=[53], tmdbId=4780,
                          tr="https://www.youtube.com/watch?v=wrongkey"))
        self.extra_write({"naisen kasvot": {
            "s": {"fi": fi, "en": "Wrong film, wrong text."}, "r": 7.3,
            "tr": "https://www.youtube.com/watch?v=wrongkey", "img": mirrored("/4780.jpg"),
            "id": 4780, "ts": ["en"] + (["fi"] if fi == WRONG["fi"] else [])}})
        self.cache_write({"naisen kasvot": {
            "r": 7.3, "n": 1200, "v": "wrongkey", "x": False, "g": [53], "i": 4780,
            "c": "2026-09-12", "a": "2026-09-12", "fi": "Väärä elokuva, väärä teksti.",
            "en": "Wrong film, wrong text.", "p": "/4780.jpg", "o": "", "y": ""}})

    # 5. a normal run corrects previously applied weak-match metadata
    def test_a_normal_run_takes_the_weak_metadata_back(self):
        self.seed()
        self.weak_naisen_kasvot()
        show = self.area()["shows"][0]
        self.assert_no_tmdb_fields(show)
        self.assertNotIn("img", show, "the carried TMDB poster is gone, nothing replaces it")
        fx = self.assert_no_tmdb_extra("naisen kasvot")
        self.assertFalse(fx["s"]["fi"], "the Finnish synopsis was the candidate's own overview")
        for field in ("rating", "len", "genres", "original", "year"):
            self.assertEqual(show[field], regina()[field], field)

    def test_a_synopsis_that_is_not_the_candidates_is_left(self):
        """The slot holds either the cinema's text or a weak candidate's; only text equal
        to the candidate's overview is known to be TMDB's, and nothing else is guessed."""
        self.seed(fi="Reginan oma teksti.")
        self.weak_naisen_kasvot()
        self.assertEqual(self.extra()["naisen kasvot"]["s"]["fi"], "Reginan oma teksti.")

    def test_a_cinemas_own_mirrored_poster_is_not_taken(self):
        self.seed(img="data/posters/0123456789abcdef.jpg")
        self.weak_naisen_kasvot()
        self.assertEqual(self.area()["shows"][0]["img"], "data/posters/0123456789abcdef.jpg")

    def test_a_title_the_cache_no_longer_knows_keeps_no_tmdb_residue(self):
        """A weak entry is dropped as the cache loads; a film that then left the programme
        is searched no more, and its films-extra entry stood with the candidate's fields."""
        self.shows(regina())
        self.extra_write({"paholaiset": {"s": {"fi": "", "en": "Some other film."}, "r": 6.1,
                                         "tr": "https://www.youtube.com/watch?v=x",
                                         "img": "data/posters/fedcba9876543210.jpg",
                                         "id": 4781, "ts": ["en"]}})
        self.weak_naisen_kasvot()
        self.assert_no_tmdb_extra("paholaiset")

    def test_an_unmatched_title_keeps_no_tmdb_residue(self):
        """Here the poster is still the w342 address: the pass wrote it and the mirror
        step failed to download it, so it was carried as it was."""
        self.shows(regina(tmdb=7.3, votes=1200, gids=[53], tr="https://www.youtube.com/watch?v=x",
                          img=W342 + "/4780.jpg"))
        self.extra_write({"naisen kasvot": {"s": {"fi": "Reginan oma teksti.", "en": "Wrong."},
                                            "r": 7.3, "tr": "https://www.youtube.com/watch?v=x",
                                            "id": 4780, "ts": ["en"]}})
        self.run_main({})
        self.assertEqual(self.cache()["naisen kasvot"]["i"], "")
        show = self.area()["shows"][0]
        self.assert_no_tmdb_fields(show)
        self.assertNotIn("img", show)
        fx = self.assert_no_tmdb_extra("naisen kasvot")
        self.assertEqual(fx["s"]["fi"], "Reginan oma teksti.")

    # 8. repeating the pipeline produces the same clean result
    def test_a_second_pass_changes_nothing(self):
        self.seed()
        self.weak_naisen_kasvot()
        first = {p.name: p.read_bytes() for p in sorted(self.dir.glob("*.json"))}
        self.weak_naisen_kasvot()
        second = {p.name: p.read_bytes() for p in sorted(self.dir.glob("*.json"))}
        self.assertEqual(first, second)
        self.assert_no_tmdb_fields(self.area()["shows"][0])


class PropagationTest(TrustHarness):
    """Weak metadata must not reach other screenings through the shared film record."""

    # 6. shared film records, poster fallbacks, title-based sharing
    def test_a_weak_poster_does_not_reach_a_show_without_one(self):
        self.shows(regina(), regina(img="", provider="orion", venue="orion"))
        self.weak_naisen_kasvot()
        shows = self.area()["shows"]
        self.assertEqual(shows[0]["img"], regina()["img"])
        self.assertFalse(shows[1].get("img"))
        self.assertNotIn("img", self.extra().get("naisen kasvot") or {},
                         "the sheet's poster fallback")

    def test_a_weak_match_neither_donates_nor_receives_a_classification(self):
        self.shows(regina(), regina(rating="", provider="orion", venue="orion"))
        self.weak_naisen_kasvot()
        shows = self.area()["shows"]
        self.assertEqual(shows[0]["rating"], "K-12")
        self.assertEqual(shows[1].get("rating", ""), "")
        self.assertNotIn("rsrc", shows[1])

    def test_a_weak_match_does_not_merge_two_films_into_one(self):
        self.shows(regina(), regina(provider="orion", venue="orion"))
        self.weak_naisen_kasvot()
        self.assertTrue(all("tmdbId" not in s for s in self.area()["shows"]))


class FailedRejudgeTest(TrustHarness):
    """A re-judge whose search fails must not unpublish the film for the run.

    `reconsider()` deletes an entry before re-searching it, so the search cannot read the
    judgement it is replacing. If that search raises -- a TMDB 429, a timeout -- the key is
    simply gone, and an absent key is not neutral: `trusted(None)` is False, so every
    showtime of that film loses its id, poster, rating and trailer and renders an initials
    tile until a later run succeeds. The hole predates the `q` trigger; `q` widened it,
    because a strand addition now puts titles through the same window.
    """

    def seeded(self):
        """A published exact match, then shows carrying evidence that differs from it."""
        self.shows(regina(year="", original=""))
        self.run_main({("Naisen kasvot", ""): [hit(76848, "Naisen kasvot", 1938)]},
                      detail={76848: RIGHT}, videos={76848: RIGHT["v"]})
        e = self.cache()["naisen kasvot"]
        self.assertEqual((e["i"], e["x"]), (76848, True), "seeded as a published match")
        self.shows(regina())          # the cinema now publishes an original and a year
        return e

    def run_failing(self):
        """Every search raises; detail requests still answer."""
        def fake_get(url, headers, timeout=25):
            if "/genre/movie/list" in url:
                return {"genres": [{"id": 18, "name": "Draama"}]}
            if "/search/movie" in url:
                raise RuntimeError("HTTP Error 429: Too Many Requests")
            if url.endswith("/videos"):
                return {"results": []}
            return {"overview": "x", "vote_count": 300, "vote_average": 6.8,
                    "genres": [{"id": 18}], "poster_path": "/76848.jpg"}
        real = enrich_tmdb.get
        enrich_tmdb.get = fake_get
        self.addCleanup(lambda: setattr(enrich_tmdb, "get", real))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(enrich_tmdb.main(), 0)
        return buf.getvalue()

    def test_a_failed_re_search_keeps_the_entry_and_the_film_published(self):
        before = self.seeded()
        self.run_failing()
        self.assertEqual(self.cache().get("naisen kasvot"), before,
                         "the old judgement is put back verbatim")
        self.assertEqual(self.area()["shows"][0]["tmdbId"], 76848,
                         "the film is still published")

    def test_the_entry_is_re_judged_again_on_the_next_run(self):
        """Restoring must not settle it: the evidence still differs, so the next run
        tries again rather than keeping a judgement made without it."""
        self.seeded()
        self.run_failing()
        cache = self.cache()
        facts = enrich_tmdb.gather([regina()])
        self.assertEqual(enrich_tmdb.reconsider(facts, cache, {}), (["naisen kasvot"], 0))


    def test_a_raise_after_the_write_does_not_put_the_old_entry_back(self):
        """The `replaced` guard. The search succeeds and the new judgement is written,
        then something after the write raises; the restore must not overwrite a good
        entry with the one it replaced."""
        self.seeded()
        boom = types.SimpleNamespace(sleep=lambda *_: (_ for _ in ()).throw(
            RuntimeError("after the write")))
        real_time = enrich_tmdb.time
        enrich_tmdb.time = boom
        self.addCleanup(lambda: setattr(enrich_tmdb, "time", real_time))
        self.run_main({("Naisen kasvot", "1938"): [hit(76848, "Naisen kasvot", 1938)],
                       ("En kvinnas ansikte", "1938"): [hit(76848, "Naisen kasvot", 1938)]},
                      detail={76848: RIGHT}, videos={76848: RIGHT["v"]})
        e = self.cache()["naisen kasvot"]
        self.assertEqual((e["i"], e["x"]), (76848, True))
        self.assertEqual(e["y"], "1938", "the new judgement stands, not the restored one")

    def test_an_alias_override_whose_lookup_fails_is_not_put_back(self):
        """The distinction the restore is scoped on. An exact entry an alias id
        supersedes is *known wrong*; republishing it after a failed lookup would put the
        wrong film on the row for a run, so that drop site is deliberately not restored.

        An id alias skips the search, so the failure is the video request. A weak entry
        an alias supersedes publishes nothing and is put back: test_tmdb_weak_retry."""
        self.shows(regina(year="", original=""))
        self.run_main({("Naisen kasvot", ""): [hit(4780, "Naisen kasvot", 1976)]},
                      detail={4780: WRONG}, videos={4780: WRONG["v"]})
        self.assertEqual((self.cache()["naisen kasvot"]["i"],
                          self.cache()["naisen kasvot"]["x"]), (4780, True))
        (self.dir / "tmdb-aliases.json").write_text(
            json.dumps({"naisen kasvot": "76848"}), encoding="utf-8")

        def fake_get(url, headers, timeout=25):
            if "/genre/movie/list" in url:
                return {"genres": [{"id": 18, "name": "Draama"}]}
            if url.endswith("/videos"):
                raise RuntimeError("HTTP Error 429: Too Many Requests")
            return {"overview": "x", "vote_count": 300, "vote_average": 6.8,
                    "genres": [{"id": 18}], "poster_path": "/76848.jpg"}
        real = enrich_tmdb.get
        enrich_tmdb.get = fake_get
        self.addCleanup(lambda: setattr(enrich_tmdb, "get", real))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(enrich_tmdb.main(), 0)
        self.assertNotIn("naisen kasvot", self.cache(), "the wrong id does not come back")
        self.assertNotIn("tmdbId", self.area()["shows"][0],
                         "unpublished rather than republished wrong")


class PosterProvenanceTest(TrustHarness):
    """A poster the pass wrote, or run.py carried from the previous file for a show whose
    adapter published none, is marked `isrc: "tmdb"`. The mark is what lets the pass
    correct a poster from an earlier candidate: "Naisen kasvot" was aliased to 76848 and
    went on showing Obsession's mirrored poster, because only a blank was ever filled."""

    def alias(self):
        (self.dir / "tmdb-aliases.json").write_text(json.dumps({"naisen kasvot": "76848"}))

    def test_a_trusted_entry_replaces_a_marked_stale_poster(self):
        self.shows(regina(img=mirrored("/4780.jpg"), isrc="tmdb"))
        self.alias()
        self.run_main({}, detail={76848: RIGHT})
        show = self.area()["shows"][0]
        self.assertEqual((show["img"], show["isrc"]), (W342 + "/76848.jpg", "tmdb"))

    def test_a_trusted_entry_leaves_an_unmarked_mirrored_poster_alone(self):
        """Unmarked and mirrored is a cinema's own poster as far as the pass can tell."""
        self.shows(regina(img="data/posters/0123456789abcdef.jpg"))
        self.alias()
        self.run_main({}, detail={76848: RIGHT})
        show = self.area()["shows"][0]
        self.assertEqual(show["img"], "data/posters/0123456789abcdef.jpg")
        self.assertNotIn("isrc", show)

    def test_a_marked_poster_a_trusted_entry_cannot_replace_comes_off(self):
        self.shows(regina(img=mirrored("/4780.jpg"), isrc="tmdb"))
        self.alias()
        self.run_main({}, detail={76848: {**RIGHT, "p": None}})
        show = self.area()["shows"][0]
        self.assertNotIn("img", show)
        self.assertNotIn("isrc", show)
        self.assertEqual(show["tmdbId"], 76848, "the rest of the trusted entry still lands")

    def test_an_untrusted_entry_drops_a_marked_poster_whatever_its_path(self):
        self.shows(regina(img="data/posters/0123456789abcdef.jpg", isrc="tmdb"))
        self.weak_naisen_kasvot()
        show = self.area()["shows"][0]
        self.assertNotIn("img", show)
        self.assertNotIn("isrc", show)

    def test_the_pass_marks_the_poster_it_writes(self):
        self.shows(regina(img=""))
        self.alias()
        self.run_main({}, detail={76848: RIGHT})
        show = self.area()["shows"][0]
        self.assertEqual((show["img"], show["isrc"]), (W342 + "/76848.jpg", "tmdb"))

    def test_a_cinemas_own_poster_is_never_replaced(self):
        self.shows(regina())
        self.alias()
        self.run_main({}, detail={76848: RIGHT})
        show = self.area()["shows"][0]
        self.assertEqual(show["img"], regina()["img"])
        self.assertNotIn("isrc", show)


class PlaceholderTest(TrustHarness):

    # 7. no reliable poster: the page uses the existing blank tile
    def test_a_film_without_a_reliable_poster_gets_the_blank_tile(self):
        self.shows(regina(img=""))
        self.weak_naisen_kasvot()
        show = self.area()["shows"][0]
        html = build_pages.film_block(show["title"], [show], self.extra(), {"fi": {}}, "fi",
                                      build_pages.L["fi"], False, set(), current_year=2026)
        self.assertIn('<div class="poster blank" aria-hidden="true"></div>', html)
        self.assertNotIn("<img", html)
        self.assertNotIn("4780", html)
        self.assertNotIn("Väärä", html)


class ShortTitleTest(TrustHarness):
    """A title of two letters or fewer has no search candidate, since queries() drops
    them. The en-US step took the first candidate of an empty list, so the title raised
    IndexError, got no cache entry, and was retried and unpublished on every run."""

    def test_it_is_cached_as_no_match_and_the_next_title_still_matches(self):
        self.shows(regina(title="Up", original="", year=""),
                   regina(title="Autofiktio", original="", year=""))
        out = self.run_main({("Autofiktio", ""): [hit(5, "Autofiktio", "2025-01-01")]},
                            detail={5: {"fi": "Teksti."}})
        self.assertNotIn("index out of range", out)
        self.assertIn("up", self.cache(), "no cache entry, so it is searched every run")
        self.assertFalse(self.cache()["up"].get("i"))
        self.assertEqual(self.cache()["autofiktio"]["i"], 5)
        self.assertEqual({q for q, *_ in self.searches}, {"Autofiktio"},
                         "Up has nothing to search for, not even an empty string")
        self.assertNotIn("en-US second search", out, "no en-US request was sent for Up")


class FinnkinoFilesTest(TrustHarness):
    """The pass leaves Finnkino's numeric area files to fetch_data.py, and only those. A
    prefix of "area-1" also skipped any other venue whose id began with a 1."""

    def write(self, vid, title):
        (self.dir / f"area-{vid}.json").write_text(json.dumps({
            "generated": self.today, "dates": [], "horizon": "",
            "shows": [regina(title=title, original="", year="", venue=vid)]}),
            encoding="utf-8")

    def test_a_numeric_id_is_skipped_and_a_slug_starting_with_1_is_not(self):
        self.write("1004", "Finnkinon elokuva")
        self.write("1kino-x", "Autofiktio")
        self.run_main({("Autofiktio", ""): [hit(5, "Autofiktio", "2025-01-01")]})
        asked = {q for q, *_ in self.searches}
        self.assertIn("Autofiktio", asked)
        self.assertNotIn("Finnkinon elokuva", asked)


if __name__ == "__main__":
    unittest.main()
