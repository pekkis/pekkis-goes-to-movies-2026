"""Venue URLs that were public before a naming fix keep resolving.

A slug is built from the chain label and the city, so correcting a label moves the URL.
Fixing Studio 123's doubled names on 2026-08-30 retired four indexed paths; they are
redirect pages now. Pinned: the table pointing at a venue that no longer exists, and the
redirect page losing one of the four things it has to say.
"""
import json
import pathlib
import re
import unittest

import _ctx                                                # noqa: F401
import build_pages as bp

ROOT = pathlib.Path(__file__).resolve().parents[1]


def live_venue_ids():
    ids = set()
    for f in (ROOT / "data").glob("venues-*.json"):
        for v in json.loads(f.read_text(encoding="utf-8"))["venues"]:
            ids.add(v["id"])
    return ids


class LegacyTableTest(unittest.TestCase):
    def test_every_alias_points_at_a_venue_that_still_exists(self):
        """A table entry for a removed venue writes a redirect to a 404, which is worse
        than the 404 it was added to prevent."""
        ids = live_venue_ids()
        for old, vid in bp.LEGACY_VENUE_SLUGS.items():
            with self.subTest(old=old):
                self.assertIn(vid, ids)

    def test_each_alias_is_the_slug_the_old_label_produced(self):
        """Why each entry exists, rather than a string someone typed. The old label
        repeated the chain name; the slug is built from label plus city."""
        cases = [("Studio 123 Kouvola Studio 123", "Kouvola",
                  "studio-123-kouvola-studio-123-kouvola"),
                 ("Studio 123 Järvenpää Studio 123", "Järvenpää",
                  "studio-123-jarvenpaa-studio-123-jarvenpaa"),
                 ("Elokuvateatteri Elo Elo", "Heinola", "elokuvateatteri-elo-elo-heinola"),
                 ("Julia 1&2 Julia", "Hyvinkää", "julia-1-2-julia-hyvinkaa")]
        for label, city, expected in cases:
            with self.subTest(label=label):
                self.assertEqual(bp.slug(f"{label} {city}"), expected)
                self.assertIn(expected, bp.LEGACY_VENUE_SLUGS)

    def test_no_label_prints_its_chain_name_twice(self):
        """A `short` already inside the chain label rendered twice: Studio 123 until
        2026-08-30, Elokuvateatteri Elo and Julia 1&2 until 2026-10-04."""
        chains = {p["id"]: p.get("label", p["id"]) for p in
                  json.loads((ROOT / "data" / "providers.json").read_text())["providers"]}
        for f in sorted((ROOT / "data").glob("venues-*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            for v in d["venues"]:
                vv = {**v, "provider": d["provider"]}
                label, short = bp.label_of(vv, chains), bp.short_of(vv)
                with self.subTest(venue=v["id"], label=label):
                    if label != short:
                        self.assertNotRegex(chains[d["provider"]],
                                            r"(?:^|\s)" + re.escape(short) + r"(?:\s|$)")

    def test_no_alias_shadows_a_current_slug(self):
        """If a live venue ever slugs to a legacy key, the redirect would take
        precedence over a real page and hide it."""
        current = set()
        chains = {p["id"]: p.get("label", p["id"]) for p in
                  json.loads((ROOT / "data" / "providers.json").read_text())["providers"]}
        for f in (ROOT / "data").glob("venues-*.json"):
            d = json.loads(f.read_text(encoding="utf-8"))
            for v in d["venues"]:
                vv = {**v, "provider": d["provider"]}
                current.add(bp.slug(f"{bp.label_of(vv, chains)} {bp.city_of(vv)}"))
        for old in bp.LEGACY_VENUE_SLUGS:
            with self.subTest(old=old):
                self.assertNotIn(old, current)


class RedirectPageTest(unittest.TestCase):
    FI = "/teatteri/studio-123-kouvola-kouvola/"
    EN = "/en/theatre/studio-123-kouvola-kouvola/"

    def test_it_carries_all_four_signals(self):
        html = bp.redirect_page("fi", self.FI, "Studio 123 Kouvola")
        self.assertIn(f'<link rel="canonical" href="{bp.SITE}{self.FI}">', html)
        self.assertIn('name="robots" content="noindex,follow"', html)
        self.assertIn(f'content="0;url={self.FI}"', html)
        self.assertIn(f'<a href="{self.FI}">', html)

    def test_the_language_matches_its_destination(self):
        self.assertIn('<html lang="en">', bp.redirect_page("en", self.EN, "X"))
        self.assertIn('<html lang="fi">', bp.redirect_page("fi", self.FI, "X"))

    def test_it_does_not_duplicate_the_venue_content(self):
        """A copy under both URLs is what canonical exists to prevent, and its schedule
        would then age in a second place nothing updates."""
        html = bp.redirect_page("fi", self.FI, "Studio 123 Kouvola")
        self.assertNotIn("application/ld+json", html)
        self.assertLess(len(html), 1200, "a redirect should not carry a programme")

    def test_it_holds_nothing_volatile(self):
        """write_if_changed is what stops these four files appearing in every diff."""
        a = bp.redirect_page("fi", self.FI, "Studio 123 Kouvola")
        b = bp.redirect_page("fi", self.FI, "Studio 123 Kouvola")
        self.assertEqual(a, b)
        self.assertNotRegex(a, r"\d{4}-\d{2}-\d{2}")

    def test_the_label_is_escaped(self):
        html = bp.redirect_page("fi", self.FI, 'Kino "X" & <b>')
        self.assertNotIn("<b>", html)
        self.assertIn("&amp;", html)


class SitemapTest(unittest.TestCase):
    def test_the_sitemap_advertises_canonical_urls_only(self):
        sm = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        for old in bp.LEGACY_VENUE_SLUGS:
            with self.subTest(old=old):
                self.assertNotIn(old, sm)

    def test_the_corrected_urls_are_in_the_sitemap(self):
        sm = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        for path in ("/teatteri/studio-123-kouvola-kouvola/",
                     "/en/theatre/studio-123-kouvola-kouvola/",
                     "/teatteri/studio-123-jarvenpaa-jarvenpaa/",
                     "/en/theatre/studio-123-jarvenpaa-jarvenpaa/",
                     "/teatteri/elokuvateatteri-elo-heinola/",
                     "/sv/teatteri/elokuvateatteri-elo-heinola/",
                     "/en/theatre/elokuvateatteri-elo-heinola/",
                     "/teatteri/julia-1-2-hyvinkaa/",
                     "/sv/teatteri/julia-1-2-hyvinkaa/",
                     "/en/theatre/julia-1-2-hyvinkaa/"):
            with self.subTest(path=path):
                self.assertIn(f"<loc>{bp.SITE}{path}</loc>", sm)


if __name__ == "__main__":
    unittest.main()
