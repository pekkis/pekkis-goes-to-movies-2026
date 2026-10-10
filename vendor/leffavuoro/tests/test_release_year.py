"""A film's own release year on the card, and the three years that are not it.

"Carrie (1976)" tells a reader the 19:00 showing is a revival. The same suffix on this
week's releases would be noise on almost every card, so it appears only for a film at
least two calendar years old: `oyear < currentYear - 1`, which in 2026 means 2024 and
older while 2025 and 2026 stay bare.

The year has to be the film's own, and three others are within reach of the code that
publishes it. Finnkino's `releaseDate` is the *Finnish* release, so for a reissue it is
this year and would print "Carrie (2026)"; `show["year"]` is whatever the cinema printed,
collected as a search hint and checked against nothing; and the screening's own date is
never the film's. `oyear` is written from an exact TMDB match's `release_date` and from
nothing else, which is what `test_a_reissue_shows_the_original_year_not_the_local_one`
holds.

**One rule, two implementations.** The app renders the card and the sheet, and
`build_pages.film_title` renders the static pages, and a reader who follows a link from
one to the other must not see the film renamed. Both are driven from `CASES` below, so a
change to either that the other does not follow fails here rather than in a screenshot.

The clock is a parameter in both, never `today()`, so these assertions do not change
meaning in January.
"""
import json
import pathlib
import shutil
import subprocess
import unittest

import _ctx
import build_pages


HARNESS = pathlib.Path(__file__).resolve().parent / "film_title_harness.js"
NOW = 2026          # the fixed clock every case is judged against

# name, title, oyear as published, expected output. `now` is NOW unless stated.
CASES = [
    # -- the boundary, stated as the four years around it ------------------------------
    ("current_year", "Presidentin kyyditys", "2026", "Presidentin kyyditys"),
    ("previous_year", "Kuolleet lehdet", "2025", "Kuolleet lehdet"),
    ("two_years_ago", "Tuulen viemää", "2024", "Tuulen viemää (2024)"),
    ("much_older", "Carrie", "1976", "Carrie (1976)"),
    ("the_first_film_year", "Roundhay Garden Scene", "1888",
     "Roundhay Garden Scene (1888)"),
    # -- absent, and everything that has to count as absent ----------------------------
    ("missing_empty", "Hetki ennen valoa", "", "Hetki ennen valoa"),
    ("missing_none", "Hetki ennen valoa", None, "Hetki ennen valoa"),
    ("malformed_letters", "Aavesoturi", "19x6", "Aavesoturi"),
    ("malformed_short", "Aavesoturi", "76", "Aavesoturi"),
    ("malformed_long", "Aavesoturi", "19766", "Aavesoturi"),
    ("malformed_date", "Aavesoturi", "1976-10-01", "Aavesoturi"),
    ("malformed_float", "Aavesoturi", "1976.0", "Aavesoturi"),
    ("malformed_circa", "Aavesoturi", "n. 1976", "Aavesoturi"),
    ("before_cinema", "Ei elokuva", "1492", "Ei elokuva"),
    ("empty_title", "", "1976", ""),
    # -- the reissue, which is the whole point of the field ----------------------------
    ("reissue_original_year", "Varjoja paratiisissa", "1986",
     "Varjoja paratiisissa (1986)"),
    # -- the cinema already printed a year, so it keeps it and gets no second one -------
    ("title_already_dated", "Trainspotting (1996)", "1996", "Trainspotting (1996)"),
    ("title_dated_disagreeing", "Twin Peaks: Kausi 1 (1990)", "1989",
     "Twin Peaks: Kausi 1 (1990)"),
    ("title_dated_with_spaces", "Sex and the City ( 2008 )", "2008",
     "Sex and the City ( 2008 )"),
    ("title_dated_but_year_recent", "Alt Skal Bort (2025)", "2025",
     "Alt Skal Bort (2025)"),
    ("year_in_the_middle_still_appends", "Blade Runner (1982) remaster", "1982",
     "Blade Runner (1982) remaster (1982)"),
]


def js_cases():
    return [{"name": n, "title": t, "oyear": y, "now": NOW} for n, t, y, _ in CASES]


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class ClientFilmTitleTest(unittest.TestCase):
    """index.html's filmTitle(), extracted verbatim."""

    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], input=json.dumps(js_cases()),
                             capture_output=True, text=True, cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stdout}{out.stderr}")
        cls.r = json.loads(out.stdout)
        if "error" in cls.r:
            raise AssertionError(f"harness error: {cls.r['error']}")

    def test_every_case(self):
        for name, title, oyear, want in CASES:
            with self.subTest(case=name):
                self.assertEqual(self.r[name], want)

    def test_the_separator_is_parentheses_and_never_a_middle_dot(self):
        """The stub tags own ` · `, and a year joined with one would read as a format
        tag. Asserted on output rather than on the source, so a helper that builds the
        string some other way is still held to it."""
        shown = self.r["much_older"]
        self.assertEqual(shown, "Carrie (1976)")
        self.assertNotIn("·", shown)
        for name in self.r:
            with self.subTest(case=name):
                self.assertNotIn("·", str(self.r[name]))


class PagesFilmTitleTest(unittest.TestCase):
    """build_pages.film_title(), over the same table."""

    def test_every_case(self):
        for name, title, oyear, want in CASES:
            with self.subTest(case=name):
                shows = [{"oyear": oyear}] if oyear is not None else [{}]
                self.assertEqual(build_pages.film_title(title, shows, NOW), want)

    def test_the_year_folds_across_the_days_screenings(self):
        """`first()` is how every other film fact folds, so a chain that publishes no
        year cannot blank a heading another chain's row filled."""
        shows = [{"oyear": ""}, {"oyear": "1976"}]
        self.assertEqual(build_pages.film_title("Carrie", shows, NOW), "Carrie (1976)")


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class OneRuleTwoImplementationsTest(unittest.TestCase):
    """The app and the generated pages must not disagree about a film's name."""

    def test_the_client_and_build_pages_agree_on_every_case(self):
        out = subprocess.run(["node", str(HARNESS)], input=json.dumps(js_cases()),
                             capture_output=True, text=True, cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stdout}{out.stderr}")
        client = json.loads(out.stdout)
        self.assertNotIn("error", client)
        for name, title, oyear, _ in CASES:
            with self.subTest(case=name):
                shows = [{"oyear": oyear}] if oyear is not None else [{}]
                self.assertEqual(client[name], build_pages.film_title(title, shows, NOW))


class TheYearSourceTest(unittest.TestCase):
    """Which year reaches `oyear`, which is the part a display test cannot see."""

    def test_a_reissue_shows_the_original_year_not_the_local_one(self):
        """The failure this field exists to avoid. A 1986 film reissued in 2026 carries
        a provider `year` and, at Finnkino, a `releaseDate` of this year. Neither is read
        by the heading; only `oyear` is, so the card says 1986."""
        show = {"oyear": "1986", "year": "2026", "rd": "2026-09-04",
                "start": "2026-09-20T19:00:00+03:00"}
        self.assertEqual(build_pages.film_title("Varjoja paratiisissa", [show], NOW),
                         "Varjoja paratiisissa (1986)")

    def test_a_provider_year_alone_prints_nothing(self):
        """`show["year"]` is the year the cinema published, collected as a TMDB search
        hint and verified against nothing. It is not promoted to a display year, so a row
        carrying only that prints a bare title."""
        self.assertEqual(build_pages.film_title("Carrie", [{"year": "1976"}], NOW),
                         "Carrie")

    def test_finnkinos_local_release_date_is_not_a_year_source(self):
        """`rd` is the Finnish release date. For a reissue it is this year."""
        self.assertEqual(build_pages.film_title("Carrie", [{"rd": "2026-09-04"}], NOW),
                         "Carrie")

    def test_the_screening_date_is_not_a_year_source(self):
        self.assertEqual(
            build_pages.film_title("Carrie", [{"start": "2024-09-20T19:00:00+03:00"}], NOW),
            "Carrie")

    def test_oyear_is_published_only_from_a_trusted_entry(self):
        """A weak candidate's year belongs to a different film, so `oyear` sits behind
        the same gate as `tmdbId` and is listed in PUBLISHED, which is what takes it back
        off a row whose entry stops being trusted."""
        import enrich_tmdb
        self.assertIn("oyear", enrich_tmdb.PUBLISHED)
        show = {"title": "x", "oyear": "1976", "tmdbId": 1, "tmdb": 7.0}
        enrich_tmdb.unpublish(show, {"x": False, "i": "", "p": ""})
        self.assertNotIn("oyear", show)

    def test_a_weak_entry_never_writes_a_year(self):
        """The other direction: an entry that is not trusted supplies nothing."""
        import enrich_tmdb
        self.assertFalse(enrich_tmdb.trusted({"x": False, "i": "123", "ry": "1976"}))
        self.assertFalse(enrich_tmdb.trusted({"x": True, "i": "", "ry": "1976"}))
        self.assertTrue(enrich_tmdb.trusted({"x": True, "i": "123", "ry": "1976"}))


class NoYearInImagesTest(unittest.TestCase):
    """A poster and a title card carry no year: they are images, and a year baked into
    one cannot be corrected or localised and would go stale in the file."""

    def test_the_title_card_generator_sets_the_published_title_only(self):
        import make_cards
        for card in make_cards.CARDS:
            with self.subTest(card=card["slug"]):
                self.assertNotIn("(", card["title"])
                self.assertNotRegex(card["title"], r"\b(18|19|20)\d{2}\b")

    def test_the_cards_initials_fallback_reads_the_bare_title(self):
        """index.html derives a blank tile's two letters from `title`, not from the
        string the heading shows, so "Carrie (1976)" cannot tile as "C1"."""
        html = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")
        start = html.index("const card = m => {")
        card = html[start:html.index("</article>", start)]
        # The tile's letters come off `title`, the heading off `cardTitle`. If the tile
        # ever read the formatted string, "Carrie (1976)" would tile as "C1".
        # Since 2026-09-20 the two letters are derived by tileInitials(), which takes the
        # festival prefix off them and nothing else. What this pins is unchanged: the
        # argument is `title`, never `cardTitle`.
        self.assertIn("const initials = tileInitials(title);", card)
        self.assertNotIn("tileInitials(cardTitle)", card)
        self.assertIn("const cardTitle = filmTitle(title, m.oyear, fiYear());", card)
        self.assertIn("${esc(cardTitle)}", card)
        self.assertNotIn("cardTitle.match(", card)
        self.assertNotIn("${esc(title)}", card)


if __name__ == "__main__":
    unittest.main()
