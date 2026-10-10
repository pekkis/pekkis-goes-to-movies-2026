"""When a title's TMDB id changes, the old film's metadata goes and the cinema's stays.

films-extra.json filled `s.fi`, `s.en`, `tr`, `img` and `r` only where the slot was empty
and recorded no id, so an alias override, a `reconsider()` re-judge or a weak entry turning
into an alias left the previous film's fields in place: on 2026-09-24 "Ryhmä Hau:
Dinoelokuva" carried the synopsis, trailer and poster of TMDB 893723, the Mighty Movie,
under id 1185806. The show side wrote `tmdb`, `votes`, `tr` and `gids` only when the new
value was truthy, so "Kapina" kept 7.2 from 4929 votes at eight cloud venues after its
entry fell to 14 votes, under the floor.

The rule pinned here: films-extra records the id its TMDB fields came from (`id`) and which
synopsis slots TMDB filled (`ts`). Those fields and slots follow the current trusted entry,
cleared when it changes or has nothing. A slot not in `ts` is the cinema's and is left, in
every language. On a show every field in PUBLISHED follows the entry the same way.
"""
import json
import unittest

import _ctx                                                # noqa: F401
import enrich_tmdb
from test_tmdb_matching import hit
from test_tmdb_trust import TrustHarness, W342, mirrored

YT = "https://www.youtube.com/watch?v="
OLD = {"fi": "Vanhan elokuvan teksti.", "en": "Old film's text.", "n": 4929, "r": 7.2,
       "g": [53], "v": "oldkey", "ry": "1990"}
NEW = {"fi": "Uuden elokuvan teksti.", "en": "", "n": 300, "r": 6.4, "g": [16],
       "v": "newkey"}
CONTROL = {"fi": "Toisen elokuvan teksti.", "en": "", "n": 800, "r": 7.9, "g": [18],
           "v": "ctlkey"}


def entry(mid, meta, title, **over):
    """A settled trusted cache entry: complete, read today, judged on this title."""
    import datetime
    today = datetime.date.today().isoformat()
    return {"r": meta["r"] if meta["n"] >= enrich_tmdb.MIN_VOTES else 0, "n": meta["n"],
            "v": meta["v"], "x": True, "g": meta["g"], "i": mid, "c": today, "a": today,
            "fi": meta["fi"], "en": meta["en"], "p": f"/{mid}.jpg", "o": "", "y": "",
            "ry": meta.get("ry", ""), "q": enrich_tmdb.norm(enrich_tmdb.clean(title)),
            **over}


def published(mid, meta, **over):
    """A show as the pass left it for `mid`, which run.py then carries forward."""
    return {"tmdbId": mid, "tmdb": meta["r"], "votes": meta["n"], "tr": YT + meta["v"],
            "gids": meta["g"], "oyear": meta.get("ry", "1990"), **over}


def extra_of(mid, meta, **over):
    """The films-extra entry the pass wrote for `mid`, in the shape that records it."""
    return {"s": {"fi": meta["fi"], "en": meta["en"]}, "r": meta["r"], "tr": YT + meta["v"],
            "img": mirrored(f"/{mid}.jpg"), "id": mid, "ts": ["en", "fi"], **over}


class IdChangeHarness(TrustHarness):
    """Two films. "Kapina" moves from 111 to 222; "Toinen" stays on 333 throughout, so a
    fix that cleared everything or touched every key shows up on the control."""

    def seed(self, kapina_extra=None, kapina_show=None):
        self.shows({"title": "Kapina", **(kapina_show or published(111, OLD))},
                   {"title": "Toinen", **published(333, CONTROL, oyear="")})
        self.extra_write({"kapina": kapina_extra or extra_of(111, OLD),
                          "toinen": extra_of(333, CONTROL, ts=["fi"])})
        self.cache_write({"kapina": entry(111, OLD, "Kapina"),
                          "toinen": entry(333, CONTROL, "Toinen")})

    def alias_to_222(self):
        (self.dir / "tmdb-aliases.json").write_text(json.dumps({"kapina": "222"}))
        return self.run_main({}, detail={222: NEW}, videos={222: NEW["v"]})

    def assert_control_untouched(self):
        fx = self.extra()["toinen"]
        self.assertEqual((fx["s"]["fi"], fx["tr"], fx["r"], fx["id"]),
                         (CONTROL["fi"], YT + "ctlkey", 7.9, 333))
        show = self.area()["shows"][1]
        self.assertEqual((show["tmdbId"], show["tmdb"], show["votes"], show["tr"]),
                         (333, 7.9, 800, YT + "ctlkey"))


class FilmsExtraIdChangeTest(IdChangeHarness):

    def test_an_alias_replaces_the_previous_films_fields(self):
        self.seed()
        self.alias_to_222()
        fx = self.extra()["kapina"]
        self.assertEqual(fx["id"], 222)
        self.assertEqual(fx["s"]["fi"], NEW["fi"], "the old film's Finnish synopsis stayed")
        self.assertEqual(fx["s"]["en"], "", "the old film's English synopsis stayed")
        self.assertEqual(fx["tr"], YT + "newkey")
        self.assertEqual(fx["img"], W342 + "/222.jpg")
        self.assertEqual(fx["r"], 6.4)
        self.assertEqual(fx["ts"], ["fi"])
        self.assert_control_untouched()

    def test_the_cinemas_slots_survive_the_change(self):
        """Swedish and English declared by an adapter, not in `ts`, stay as they were;
        only the slot TMDB filled is replaced."""
        self.seed(kapina_extra=extra_of(111, OLD, ts=["fi"],
                                        s={"fi": OLD["fi"], "en": "The cinema's own text.",
                                           "sv": "Biografens egen text."}))
        self.alias_to_222()
        s = self.extra()["kapina"]["s"]
        self.assertEqual(s, {"fi": NEW["fi"], "en": "The cinema's own text.",
                             "sv": "Biografens egen text."})
        self.assertEqual(self.extra()["kapina"]["ts"], ["fi"])

    def test_a_re_judge_that_moves_the_id_replaces_the_fields(self):
        """reconsider(): the cinema starts publishing a year, the search lands on another
        film of that title."""
        self.seed()
        self.shows({"title": "Kapina", "year": "2026", **published(111, OLD)},
                   {"title": "Toinen", **published(333, CONTROL, oyear="")})
        self.run_main({("Kapina", "2026"): [hit(222, "Kapina", 2026)]},
                      detail={222: NEW}, videos={222: NEW["v"]})
        self.assertEqual(self.cache()["kapina"]["i"], 222, "the re-judge moved the id")
        fx = self.extra()["kapina"]
        self.assertEqual((fx["id"], fx["s"]["fi"], fx["tr"], fx["img"]),
                         (222, NEW["fi"], YT + "newkey", W342 + "/222.jpg"))
        self.assert_control_untouched()

    def test_an_untrusted_entry_keeps_the_cinemas_english(self):
        """unpublish_extra blanked `en` whatever wrote it; an adapter declaring English is
        the cinema's text, and only the slots in `ts` are TMDB's to take back."""
        self.seed(kapina_extra=extra_of(111, OLD, ts=["fi"],
                                        s={"fi": OLD["fi"], "en": "The cinema's own text."}))
        self.cache_write({"kapina": entry(111, OLD, "Kapina", x=False),
                          "toinen": entry(333, CONTROL, "Toinen")})
        self.run_main({})
        self.assertFalse(enrich_tmdb.trusted(self.cache()["kapina"]), "nothing trusted now")
        fx = self.extra()["kapina"]
        self.assertEqual(fx["s"], {"fi": "", "en": "The cinema's own text."})
        self.assertEqual((fx["r"], fx["tr"]), (0, ""))
        self.assertNotIn("img", fx)
        self.assertNotIn("id", fx)
        self.assertNotIn("ts", fx)

    def test_a_second_pass_changes_nothing(self):
        self.seed()
        self.alias_to_222()
        first = {p.name: p.read_bytes() for p in sorted(self.dir.glob("*.json"))}
        self.alias_to_222()
        self.assertEqual(first, {p.name: p.read_bytes() for p in sorted(self.dir.glob("*.json"))})


class FilmsExtraLegacyTest(IdChangeHarness):
    """An entry written before `id` existed. The TMDB-only fields are rebuilt from the
    trusted entry; a slot equal to the entry's own text is recorded as TMDB's; any other
    text is the cinema's as far as the pass can tell, and stays."""

    def test_tmdb_only_fields_follow_the_current_entry(self):
        legacy = {"s": {"fi": "Joku teksti.", "en": OLD["en"]}, "r": 7.2,
                  "tr": YT + "oldkey", "img": mirrored("/111.jpg")}
        self.seed(kapina_extra=legacy)
        self.cache_write({"kapina": entry(222, NEW, "Kapina"),
                          "toinen": entry(333, CONTROL, "Toinen")})
        self.run_main({})
        fx = self.extra()["kapina"]
        self.assertEqual((fx["id"], fx["tr"], fx["img"], fx["r"]),
                         (222, YT + "newkey", W342 + "/222.jpg", 6.4))
        self.assertEqual(fx["s"]["fi"], "Joku teksti.", "unknown provenance is the cinema's")
        self.assertEqual(fx["s"]["en"], OLD["en"])
        self.assertNotIn("fi", fx.get("ts", []))

    def test_a_slot_equal_to_the_entrys_text_is_adopted(self):
        legacy = {"s": {"fi": NEW["fi"], "en": ""}, "r": 0, "tr": ""}
        self.seed(kapina_extra=legacy)
        self.cache_write({"kapina": entry(222, NEW, "Kapina"),
                          "toinen": entry(333, CONTROL, "Toinen")})
        self.run_main({})
        self.assertEqual(self.extra()["kapina"]["ts"], ["fi"])


class EmptiedValueTest(IdChangeHarness):
    """Same id, a value gone: TMDB withdrew the trailer, the votes fell under the floor."""

    def test_a_rating_under_the_floor_and_a_withdrawn_trailer_come_off(self):
        self.seed()
        self.cache_write({"kapina": entry(111, {**OLD, "n": 14, "v": ""}, "Kapina"),
                          "toinen": entry(333, CONTROL, "Toinen")})
        self.run_main({})
        show = self.area()["shows"][0]
        for field in ("tmdb", "votes", "tr"):
            self.assertNotIn(field, show, f"{field} outlived the entry's value")
        self.assertEqual(show["tmdbId"], 111)
        fx = self.extra()["kapina"]
        self.assertEqual((fx["r"], fx["tr"]), (0, ""))
        self.assert_control_untouched()

    def test_an_entry_left_with_nothing_still_clears_its_key(self):
        """No synopsis, trailer or rating at all: the key exists, so it is still brought
        into line rather than skipped as having nothing to add. Only the Finnish slot
        is left of what the pass wrote, so `ts` alone marks the key as holding any."""
        self.seed(kapina_extra=extra_of(111, OLD, r=0, tr="", img=None, ts=["fi"],
                                        s={"fi": OLD["fi"], "en": ""}))
        self.cache_write({"kapina": entry(111, {**OLD, "fi": "", "en": "", "n": 14, "v": ""},
                                          "Kapina"),
                          "toinen": entry(333, CONTROL, "Toinen")})
        self.run_main({})
        fx = self.extra()["kapina"]
        self.assertEqual((fx["s"], fx["r"], fx["tr"]), ({"fi": "", "en": ""}, 0, ""))
        self.assertNotIn("ts", fx)
        self.assert_control_untouched()


class ShowIdChangeTest(IdChangeHarness):

    def test_every_published_field_follows_the_new_id(self):
        self.seed()
        (self.dir / "tmdb-aliases.json").write_text(json.dumps({"kapina": "222"}))
        self.run_main({}, detail={222: {**NEW, "n": 14, "g": []}}, videos={})
        show = self.area()["shows"][0]
        self.assertEqual(show["tmdbId"], 222)
        for field in ("tmdb", "votes", "tr", "gids", "oyear"):
            self.assertNotIn(field, show, f"{field} is the old film's")
        self.assert_control_untouched()

    def test_new_values_replace_old_ones(self):
        self.seed()
        self.alias_to_222()
        show = self.area()["shows"][0]
        self.assertEqual((show["tmdbId"], show["tmdb"], show["votes"], show["tr"],
                          show["gids"]), (222, 6.4, 300, YT + "newkey", [16]))


if __name__ == "__main__":
    unittest.main()
