"""One film, one card on a city page (2026-09-22).

A city page is the app's combined view rendered ahead of time, so it has to answer "same
film?" the way the app does. Keyed on the published title it did not: the committed
Helsinki page drew "Keltaiset Kirjeet" and "Keltaiset kirjeet" as two films on one day,
and six more pairs sat on the other city pages.

These pin:

- `merge_key` is the client's `mergeKey`: the same four strips over the shared `norm`;
- the union is the client's `mergeIds`: the title key and `tmdb:{tmdbId}`, so chains that
  disagree on the title still merge and chains with no id still do;
- a city page merges and a theatre page does not, because a provider's own "(Dub)" and
  "(Orig)" rows are two cards in the app's single-venue view;
- the heading never advertises one audio version for a card holding two, and never eats a
  word off a title that only differs in case;
- the screening keeps what the card cannot claim for all of it: its cinema, its room, its
  language and its format;
- no committed city page has two cards for one film on one day.
"""
import html
import json
import re
import shutil
import subprocess
import unittest
from datetime import date

import _ctx

import build_pages as bp

ROOT = _ctx.ROOT
TODAY = date(2026, 9, 22)
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")


def show(title, start="2026-09-22T18:00:00+03:00", **kw):
    s = {"title": title, "start": start}
    s.update(kw)
    return s


def days_of(shows, merge):
    return bp.group_by_day(shows, TODAY, 2, merge=merge)


class MergeKeyMatchesTheClient(unittest.TestCase):
    """The client's own regexes, read out of index.html. Two copies of a rule drift; this
    fails the day one of them moves without the other."""

    def client_strips(self):
        block = re.search(r"const mergeKey = t => normTitle\(\(t \|\| ''\)(.*?)\);",
                          INDEX, re.S)
        self.assertIsNotNone(block, "mergeKey not found in index.html")
        return re.findall(r"\.replace\(/(.*?)/gi,", block.group(1))

    def test_the_same_four_strips_in_the_same_order(self):
        ours = [rx.pattern for rx in bp._MERGE_STRIP]
        theirs = self.client_strips()
        self.assertEqual(len(theirs), 4)
        self.assertEqual(len(ours), len(theirs))
        for mine, js in zip(ours, theirs):
            # JS needs no escape for `/` inside a literal; Python's re does not either,
            # and neither pattern uses one. Everything else is the same syntax.
            self.assertEqual(mine, js)

    @unittest.skipIf(shutil.which("node") is None, "node not installed")
    def test_the_client_s_own_function_gives_the_same_key(self):
        """The same patterns are not the same function: JavaScript's `\\b` is ASCII and
        Python's was Unicode, so "äsuomeksi" keyed as "ä" in the app and "äsuomeksi" on
        the pages (audit E9). The client's normTitle and mergeKey run in node over the
        hard cases and every title in the committed data."""
        norm_js = re.search(r"^  const normTitle = .*?;\n(?=  //)", INDEX, re.S | re.M).group(0)
        merge_js = re.search(r"^  const mergeKey = .*?\)\);\n", INDEX, re.S | re.M).group(0)
        titles = ["äsuomeksi", "Elokuva äsuomeksi", "Elokuva,\u00a0suomeksi",
                  "Tämä\u2003suomeksi", "Möö3D", "Ö2D elokuva", "Film 3D", "éimax",
                  "IMAXé", "4Kids", "Kissa_suomeksi", "Film (uusi\u00a0kopio)",
                  "Ryhmä Hau: Dinoelokuva (suomeksi)", "Marsupilami, suomeksi",
                  "Spider-Man: Brand New Day 2D", "Ä (Dub)", "x\ufeffsuomeksi"]
        for p in sorted((ROOT / "data").glob("area-*.json")):
            titles += [sh.get("title") or "" for sh in
                       json.loads(p.read_text(encoding="utf-8")).get("shows", [])]
        titles = sorted(set(titles))
        script = (norm_js + merge_js + f"const ts = {json.dumps(titles)};"
                  "console.log(JSON.stringify(ts.map(mergeKey)));")
        out = subprocess.run(["node", "-e", script], capture_output=True, text=True,
                             timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        diff = [(t, bp.merge_key(t), js) for t, js in zip(titles, json.loads(out.stdout))
                if bp.merge_key(t) != js]
        self.assertEqual(diff, [])

    def test_the_client_unions_the_tmdb_id_with_the_title_key(self):
        self.assertIn("union(s.eventId, `tmdb:${s.tmdbId}`)", INDEX)

    def test_case_format_and_dub_markers_fold(self):
        for a, b in (("Keltaiset Kirjeet", "Keltaiset kirjeet"),
                     ("Spider-Man: Brand New Day", "Spider-Man: Brand New Day 2D"),
                     ("Kojootti vs. ACME", "Kojootti vs. ACME (Dub)"),
                     ("Autot", "Autot (uudelleenjulkaisu)")):
            self.assertEqual(bp.merge_key(a), bp.merge_key(b), (a, b))

    def test_a_subtitle_after_a_dash_is_not_stripped(self):
        self.assertNotEqual(bp.merge_key("Mission: Impossible - Dead Reckoning"),
                            bp.merge_key("Mission: Impossible"))


class Grouping(unittest.TestCase):
    def test_a_city_page_folds_a_capitalisation_variant(self):
        # The spelling the other cinemas use is the heading; one cinema's stray capital
        # is what the fold is for.
        d = days_of([show("Keltaiset Kirjeet", theatre="A"),
                     show("Keltaiset kirjeet", start="2026-09-22T19:00:00+03:00",
                          theatre="B"),
                     show("Keltaiset kirjeet", start="2026-09-22T20:00:00+03:00",
                          theatre="C")], merge=True)
        self.assertEqual(list(d["2026-09-22"]), ["Keltaiset kirjeet"])
        self.assertEqual(len(d["2026-09-22"]["Keltaiset kirjeet"]), 3)

    def test_a_theatre_page_does_not(self):
        d = days_of([show("Kojootti vs. ACME (Dub)"),
                     show("Kojootti vs. ACME (Orig)",
                          start="2026-09-22T20:00:00+03:00")], merge=False)
        self.assertEqual(sorted(d["2026-09-22"]),
                         ["Kojootti vs. ACME (Dub)", "Kojootti vs. ACME (Orig)"])

    def test_the_tmdb_id_merges_titles_the_key_cannot(self):
        d = days_of([show("Coyote vs. Acme", tmdbId=1204680),
                     show("Kojootti vs. ACME", tmdbId=1204680,
                          start="2026-09-22T20:00:00+03:00")], merge=True)
        self.assertEqual(len(d["2026-09-22"]), 1)

    def test_a_missing_id_still_merges_on_the_title(self):
        d = days_of([show("Myrskyn ikkuna", tmdbId=1318413),
                     show("Myrskyn Ikkuna", start="2026-09-22T20:00:00+03:00")],
                    merge=True)
        self.assertEqual(len(d["2026-09-22"]), 1)

    def test_two_different_films_stay_apart(self):
        d = days_of([show("Myrskyn ikkuna", tmdbId=1318413),
                     show("Keltaiset kirjeet", tmdbId=1315657,
                          start="2026-09-22T20:00:00+03:00")], merge=True)
        self.assertEqual(len(d["2026-09-22"]), 2)

    def test_one_heading_across_both_days_of_the_window(self):
        d = days_of([show("Myrskyn Ikkuna"), show("Myrskyn Ikkuna"),
                     show("Myrskyn ikkuna", start="2026-09-23T18:00:00+03:00")],
                    merge=True)
        self.assertEqual(list(d["2026-09-22"]), list(d["2026-09-23"]))


class Heading(unittest.TestCase):
    def test_the_spelling_most_screenings_use_wins(self):
        self.assertEqual(bp.merged_title({"Myrskyn Ikkuna": 1, "Myrskyn ikkuna": 4}),
                         "Myrskyn ikkuna")

    def test_ties_go_to_the_shorter_title_then_to_codepoint_order(self):
        self.assertEqual(bp.merged_title({"Autot 2D": 2, "Autot": 2}), "Autot")
        self.assertEqual(bp.merged_title({"Autot b": 1, "Autot a": 1}), "Autot a")

    def test_a_card_holding_both_audio_versions_advertises_neither(self):
        d = days_of([show("Kojootti vs. ACME (suomeksi)", tmdbId=1204680, lang="FI-A"),
                     show("Kojootti vs. ACME (englanniksi)", tmdbId=1204680, lang="EN-A",
                          start="2026-09-22T20:00:00+03:00")], merge=True)
        self.assertEqual(list(d["2026-09-22"]), ["Kojootti vs. ACME"])

    def test_a_shared_opening_never_eats_a_word_off_a_case_variant(self):
        # "Keltaiset Kirjeet" and "Keltaiset kirjeet" share the opening "Keltaiset ", and
        # a card headed "Keltaiset" would be a title no cinema published. They share a
        # title key, so shared_head is never asked.
        self.assertEqual(bp.shared_head(["Keltaiset Kirjeet", "Keltaiset kirjeet"]),
                         "Keltaiset")
        d = days_of([show("Keltaiset Kirjeet"),
                     show("Keltaiset kirjeet", start="2026-09-22T20:00:00+03:00")],
                    merge=True)
        self.assertEqual([t.lower() for t in d["2026-09-22"]], ["keltaiset kirjeet"])

    def test_titles_with_nothing_in_common_fall_back_to_the_count(self):
        self.assertEqual(bp.shared_head(["Coyote vs. Acme", "Kojootti vs. ACME"]), "")

    def test_a_short_shared_opening_is_a_coincidence(self):
        self.assertEqual(bp.shared_head(["Tie taivaaseen", "Tie ja tuuli"]), "")


class WhatTheScreeningKeeps(unittest.TestCase):
    def render(self, shows, with_venue=True):
        return bp.film_block("F", shows, {}, {}, "fi", bp.L["fi"],
                             with_venue=with_venue, syn_seen=set(), current_year=2026)

    def test_the_cinema_and_the_room_stay_on_every_stub(self):
        h = self.render([show("F", venueLabel="Finnkino Itis", aud="LUXE 3"),
                         show("F", venueLabel="Gilda Kamppi", aud="Gilda 1",
                              start="2026-09-22T20:00:00+03:00")])
        for x in ("Finnkino Itis", "LUXE 3", "Gilda Kamppi", "Gilda 1"):
            self.assertIn(x, h)

    def test_a_format_they_all_share_is_not_drawn_at_all(self):
        """It separates nothing, and a card that gained a line would be a design change
        on every city page rather than a fix for the fold."""
        h = self.render([show("F", method="2D · LUXE", aud="Sali 1"),
                         show("F", method="2D · LUXE", aud="Sali 2",
                              start="2026-09-22T20:00:00+03:00")])
        self.assertNotIn("LUXE", h)
        self.assertNotIn("class=f", h)

    def test_a_format_only_one_screening_has_sits_on_that_stub(self):
        h = self.render([show("F", method="Anniskelu", aud="Sali 1"),
                         show("F", aud="Sali 2", start="2026-09-22T20:00:00+03:00")])
        self.assertIn("<span class=f>Anniskelu</span>", h)

    def test_2d_is_not_worth_a_chip_and_a_tag_the_room_already_says_is_not_repeated(self):
        h = self.render([show("F", method="2D", aud="LUXE 3"),
                         show("F", method="LUXE", aud="LUXE 3",
                              start="2026-09-22T20:00:00+03:00")])
        self.assertNotIn("class=f", h)

    def test_a_theatre_page_carries_no_format_part(self):
        h = self.render([show("F", method="Anniskelu", aud="Sali 1"),
                         show("F", aud="Sali 2", start="2026-09-22T20:00:00+03:00")],
                        with_venue=False)
        self.assertNotIn("Anniskelu", h)

    def test_the_languages_split_when_the_merged_screenings_disagree(self):
        h = self.render([show("F", lang="FI-A", aud="Sali 1"),
                         show("F", lang="EN-A, FI-S", aud="Sali 2",
                              start="2026-09-22T20:00:00+03:00")])
        # Each screening keeps its own line on its ticket (2026-09-23).
        self.assertIn('<span class="slang"><span class="lp"><span>suomi</span></span></span>', h)
        self.assertIn('<span class="slang"><span class="lp"><span>englanti'
                      '<span class="sr-only">, </span></span>'
                      '<span>tekstitys: suomi</span></span></span>', h)


class TheCommittedPages(unittest.TestCase):
    """The guarantee stated on what is published, not on the helpers."""

    def test_no_city_page_shows_one_film_twice_on_one_day(self):
        dupes = []
        for p in sorted((ROOT / "kaupunki").glob("*/index.html")):
            page = p.read_text(encoding="utf-8")
            for chunk in re.split(r'<h2 class="day">', page)[1:]:
                day = re.match(r"([^<]*)", chunk).group(1)
                seen = {}
                for raw in re.findall(r"<h3>([^<]*)</h3>", chunk):
                    title = re.sub(r"\s*\(\d{4}\)$", "", html.unescape(raw))
                    seen.setdefault(bp.merge_key(title), []).append(title)
                dupes += [(p.parent.name, day, v) for v in seen.values() if len(v) > 1]
        self.assertEqual(dupes, [])


if __name__ == "__main__":
    unittest.main()
