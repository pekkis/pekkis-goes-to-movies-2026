"""The counts are derived, so nothing here transcribes one.

They were hand-kept in IDEAS.md and re-measured twenty-two times; five passes shipped a
wrong number. This file checks the generator against the data by a second route wherever
one exists -- `registry.PROVIDERS` for providers, the venue files for venues, `<loc>` for
the sitemap -- rather than against the generator's own output, which would only assert
that it agrees with itself.

Off-origin references are pinned at 0. That one is an invariant rather than a measurement:
`safeAssetUrl` refuses a poster outside `data/posters/`, and README's "posters are
served from this origin" rests on it. The two figures that do move on a data run --
how many references exist, how many files back them -- are not committed at all;
`--posters` prints them, and this file checks that it prints them and writes nothing.
"""
import contextlib
import io
import json
import re
import unittest

import _ctx                                                 # noqa: F401
import build_counts
import build_pages
import registry


ROOT = build_counts.ROOT
DATA = build_counts.DATA


class FiguresTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.c = build_counts.counts()

    def test_providers_and_local_providers_come_from_the_registry(self):
        self.assertEqual(self.c["providers"], len(registry.PROVIDERS))
        self.assertEqual(self.c["local_providers"],
                         sum(1 for p in registry.PROVIDERS if p.get("where") == "local"))
        self.assertGreater(self.c["local_providers"], 0, "the local half is not empty")

    def test_venues_are_every_committed_venue_file_plus_finnkinos_areas(self):
        """Counted here off the files directly, so a change to load_venues that dropped a
        provider would disagree with this rather than move both numbers together."""
        n = len(json.loads((DATA / "areas.json").read_text(encoding="utf-8"))["areas"])
        for f in sorted(DATA.glob("venues-*.json")):
            n += len(json.loads(f.read_text(encoding="utf-8")).get("venues", []))
        self.assertEqual(self.c["venues"], n)
        local_ids = {p["id"] for p in registry.PROVIDERS if p.get("where") == "local"}
        import build_pages
        self.assertEqual(self.c["local_venues"],
                         sum(1 for v in build_pages.load_venues()
                             if v["provider"] in local_ids))
        self.assertLess(self.c["local_venues"], self.c["venues"])

    def test_every_venue_lands_in_a_city_including_finnkinos(self):
        """Finnkino's areas carry no `city` key -- the city is inside the venue name -- and
        a city count that read the field would silently lose 17 venues. That fault is why
        `city_of` is reused instead of reimplemented."""
        import build_pages
        venues = build_pages.load_venues()
        self.assertTrue(all(build_pages.city_of(v) for v in venues), "a venue with no city")
        finnkino = [v for v in venues if v["provider"] == "finnkino"]
        self.assertTrue(finnkino and all("city" not in v for v in finnkino))
        self.assertTrue(all(build_pages.city_of(v) for v in finnkino))
        self.assertEqual(self.c["cities"], len({build_pages.city_of(v) for v in venues}))
        self.assertLessEqual(self.c["multi_venue_cities"], self.c["cities"])

    def test_the_sitemap_figures_are_the_sitemap(self):
        sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        self.assertEqual(self.c["sitemap_urls"], sitemap.count("<loc>"))
        # Every language carries the same set; the front page belongs to none of them.
        self.assertEqual(self.c["sitemap_urls"],
                         self.c["pages_per_language"] * len(build_pages.LANGS) + 1)
        self.assertEqual(self.c["pages_per_language"],
                         self.c["venues"] + self.c["multi_venue_cities"])

    def test_the_cache_value_is_the_one_in_sw_js(self):
        sw = (ROOT / "sw.js").read_text(encoding="utf-8")
        self.assertIn(f"'{self.c['cache']}'", sw)
        self.assertRegex(self.c["cache"], r"^leffavuoro-v\d+$")

    def test_no_poster_reference_leaves_this_origin(self):
        """An invariant, not a measurement, which is why it sits in the committed block
        and the moving figures do not. Posters served from this origin is the claim README
        makes, and `safeAssetUrl` is what holds it up in the client."""
        self.assertEqual(self.c["poster_refs_off_origin"], 0)

    def test_the_moving_figures_are_not_among_the_committed_ones(self):
        """Committing them would put the drift step in CI at odds with any data run."""
        for key in ("poster_refs", "poster_refs_shows", "poster_refs_extra",
                    "mirrored_posters", "data_generated"):
            self.assertNotIn(key, self.c, key)

    def test_the_largest_adapters_row_is_ordered_and_adds_up(self):
        per = self.c["per_adapter"]
        self.assertEqual([n for _, n in per], sorted((n for _, n in per), reverse=True))
        self.assertEqual(sum(n for _, n in per), self.c["venues"])
        self.assertGreaterEqual(len(per), build_counts.TOP_ADAPTERS)


class CommittedOutputTest(unittest.TestCase):
    """The committed block is what a reader sees, so it has to agree with the data."""

    def test_the_stable_rows_of_the_committed_block_are_current(self):
        c = build_counts.counts()
        text = build_counts.COUNTS.read_text(encoding="utf-8")
        for row in (f"| providers | {c['providers']} |",
                    f"| venues | {c['venues']} |",
                    f"| cities | {c['cities']} |",
                    f"| generated pages per language | {c['pages_per_language']} |",
                    f"| sitemap URLs | {c['sitemap_urls']} |",
                    f"| off-origin poster references | {c['poster_refs_off_origin']} |",
                    f"| `sw.js` CACHE | `{c['cache']}` |"):
            self.assertIn(row, text, "run scripts/build_counts.py")

    def test_the_committed_block_regenerates_byte_identical(self):
        """What CI's drift step asks. The suite asks whether the file on disk is current;
        this asks whether writing it again changes anything, which is the property that
        lets build_counts.py sit beside the other generators in that step."""
        text = build_counts.COUNTS.read_text(encoding="utf-8")
        self.assertEqual(build_counts.render(text, build_counts.block(build_counts.counts())),
                         text, "run scripts/build_counts.py")

    def test_no_moving_figure_reached_the_committed_file(self):
        text = build_counts.COUNTS.read_text(encoding="utf-8")
        block = text.split(build_counts.START)[1].split(build_counts.END)[0]
        p = build_counts.poster_figures()
        self.assertNotIn("mirrored poster files", block)
        self.assertNotIn("poster references (shows", block)
        self.assertNotIn(p["data_generated"], block, "no data snapshot in the block")
        self.assertNotIn(str(p["mirrored_posters"]), block)

    def test_the_readme_prose_carries_the_same_figures(self):
        readme = build_counts.README.read_text(encoding="utf-8")
        self.assertEqual(build_counts.readme_text(readme, build_counts.counts()), readme,
                         "run scripts/build_counts.py")


class RenderTest(unittest.TestCase):

    def test_a_missing_marker_is_an_error_and_not_a_silent_no_op(self):
        for text in ("no markers here", build_counts.START, build_counts.END,
                     build_counts.END + build_counts.START):
            with self.assertRaises(RuntimeError):
                build_counts.render(text, "x")

    def test_the_block_replaces_only_between_the_markers(self):
        text = f"before{build_counts.START}old{build_counts.END}after"
        out = build_counts.render(text, "new")
        self.assertEqual(out, f"before{build_counts.START}new{build_counts.END}after")


class ReadmeRulesTest(unittest.TestCase):
    """Four numbers in flowing prose, each anchored on the words around it."""

    PROSE = ("Showtimes for 1 venues in 2 cities across 3 providers: Finnkino.\n"
             "The picker switches between its 2 cities and those regions.\n"
             "4 per language, 5 sitemap URLs: 1 venues plus the seventeen cities with "
             "more than one venue.\n"
             "Schedule data belongs to the respective cinemas, the 3 providers listed at "
             "the top of this page.\n")

    C = {"venues": 134, "cities": 96, "providers": 83, "pages_per_language": 151,
         "sitemap_urls": 454, "multi_venue_cities": 17}

    def test_every_site_is_rewritten(self):
        out = build_counts.readme_text(self.PROSE, self.C)
        self.assertIn("Showtimes for 134 venues in 96 cities across 83 providers", out)
        self.assertIn("its 96 cities and those regions", out)
        self.assertIn("151 per language, 454 sitemap URLs: 134 venues plus the "
                      "seventeen cities", out)
        self.assertIn("the 83 providers listed at the", out)
        self.assertEqual(out.count("\n"), self.PROSE.count("\n"))

    def test_the_multi_venue_city_count_is_written_as_a_word(self):
        out = build_counts.readme_text(self.PROSE, {**self.C, "multi_venue_cities": 20})
        self.assertIn("134 venues plus the twenty cities", out)
        out = build_counts.readme_text(self.PROSE, {**self.C, "multi_venue_cities": 31})
        self.assertIn("134 venues plus the 31 cities", out, "no word for it, so the digit")

    def test_a_reworded_anchor_is_reported_rather_than_skipped(self):
        """The failure this generator exists to prevent is a number nobody noticed going
        stale. An anchor that stops matching has to be loud."""
        broken = self.PROSE.replace("Showtimes for", "Showtimes covering")
        with self.assertRaises(RuntimeError) as e:
            build_counts.readme_text(broken, self.C)
        self.assertIn("matched 0 times", str(e.exception))

    def test_a_duplicated_anchor_is_reported_too(self):
        with self.assertRaises(RuntimeError) as e:
            build_counts.readme_text(self.PROSE * 2, self.C)
        self.assertIn("matched 2 times", str(e.exception))

    def test_an_unchanged_prose_round_trips(self):
        once = build_counts.readme_text(self.PROSE, self.C)
        self.assertEqual(build_counts.readme_text(once, self.C), once)


class BlockTest(unittest.TestCase):

    def test_the_block_names_every_figure_it_was_asked_for(self):
        c = build_counts.counts()
        body = build_counts.block(c)
        for label in ("providers", "venues", "cities", "local providers (venues)",
                      "venues per adapter", "generated pages per language",
                      "sitemap URLs", "off-origin poster references", "`sw.js` CACHE"):
            self.assertIn(label, body, label)

    def test_the_largest_row_holds_the_top_adapters_in_order(self):
        c = build_counts.counts()
        named = re.search(r"venues per adapter, largest \d+ \| (.+?) \|",
                          build_counts.block(c)).group(1)
        top = c["per_adapter"][:build_counts.TOP_ADAPTERS]
        # "largest few" is a presentation choice, so the count is not pinned to 5. The
        # floor is: more than one, or the row shows no shape at all.
        self.assertGreaterEqual(len(top), 3)
        self.assertEqual(named, ", ".join(f"`{name}` {n}" for name, n in top))


class PosterFiguresTest(unittest.TestCase):
    """The two figures that move, printed on demand and never written down."""

    def test_they_are_measured_off_the_data(self):
        p = build_counts.poster_figures()
        self.assertEqual(p["poster_refs"],
                         p["poster_refs_shows"] + p["poster_refs_extra"])
        self.assertGreater(p["poster_refs_shows"], 0)
        self.assertGreater(p["poster_refs_extra"], 0, "films-extra carries some too")
        on_disk = sum(1 for f in (DATA / "posters").iterdir() if f.is_file())
        self.assertEqual(p["mirrored_posters"], on_disk)
        self.assertEqual(p["data_generated"], json.loads(
            (DATA / "areas.json").read_text(encoding="utf-8"))["generated"])

    def test_the_flag_prints_both_figures(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = build_counts.main(["--posters"])
        text = out.getvalue()
        self.assertEqual(rc, 0)
        p = build_counts.poster_figures()
        self.assertIn(str(p["poster_refs"]), text)
        self.assertIn(str(p["poster_refs_shows"]), text)
        self.assertIn(str(p["poster_refs_extra"]), text)
        self.assertIn(str(p["mirrored_posters"]), text)
        self.assertIn(p["data_generated"], text)

    def test_the_flag_writes_nothing(self):
        """A reporting flag that rewrote the file would put the drift step and a data run
        back in conflict, which is the whole reason these two are not committed."""
        before = {f: f.read_bytes() for f in (build_counts.COUNTS, build_counts.README)}
        with contextlib.redirect_stdout(io.StringIO()):
            build_counts.main(["--posters"])
        for f, body in before.items():
            self.assertEqual(f.read_bytes(), body, f.name)

    def test_the_flag_skips_the_stale_report_entirely(self):
        """It reports on the data, not on whether the file is current, so it must not
        print a stale line a reader would act on."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            build_counts.main(["--posters"])
        self.assertNotIn("docs/counts.md", out.getvalue())
        self.assertNotIn("stale", out.getvalue())


if __name__ == "__main__":
    unittest.main()
