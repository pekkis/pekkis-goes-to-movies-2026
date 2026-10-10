"""The generated landing pages, as a reader and a crawler receive them (2026-09-02).

The pages under /teatteri/, /kaupunki/, /en/theatre/ and /en/city/ share the app's design:
wordmark, one CTA into the app carrying venue and language, ticket-shaped showtimes, the
app's tokens in both themes. These tests read the pages the real `main()` writes from the
committed data, plus a few synthetic shows for the label rule. They pin:

- the six page families exist in the counts the sitemap advertises, and the legacy
  redirects are byte-identical to the committed ones;
- every canonical page points at itself and carries an hreflang for each language;
- one CTA per page, in the page's language, whose `area` and `lang` are what the
  client's `startupArea()`/`startupLang()` read;
- a theatre page never repeats the cinema inside a showtime; a city page always names it;
  the room is verbatim; empty parts leave no separator behind;
- the intro promises only what the registry's `book` mode offers, and so does the meta
  description, which is one string shared with `og:description` and stays snippet-length;
- the language codes render as words, from a table identical to the client's, and no
  raw code is left on any page built from the committed data;
- the FI · SV · EN selector marks the page's language and links the other two, each
  to the same cinema or city rather than into the app;
- the theme is the app's: the stored `kino-theme` wins before first paint, the OS decides
  otherwise, the toggle writes the same key, and no script renders content;
- the card is the app's: film facts fold first-non-empty across the day's screenings,
  language sits on the card when shared and on the screening when it differs, the price
  sits on its own screening's stub and never on the card,
  the score is the app's ring with an accessible label, prices are labelled the way the
  client labels them, and a city page stacks its stubs the way the combined view does;
- regeneration is deterministic and nothing volatile reaches a page.
"""
import contextlib
import html
import io
import json
import os
import pathlib
import ast
import random
import re
import shutil
import subprocess
import tempfile
import unittest
from datetime import date, datetime, time, timedelta

import _ctx

# film_block takes the year the page is built for. These fixtures publish no
# `oyear`, so the value only has to be a year; the rule itself is covered by
# tests/test_release_year.py.
YEAR_NOW = 2026
import build_pages as bp


ROOT = _ctx.ROOT
REAL_DATA = ROOT / "data"
REDIRECTS = len(bp.LEGACY_VENUE_SLUGS) * len(bp.LANGS)


def advertised():
    """The figures README states: (pages per language, sitemap URLs). Read rather than
    retyped, so the sentence a reader sees is measured against the committed venues
    below. A venue added without README following fails here."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"(\d+) per language, (\d+) sitemap URLs", readme)
    return int(m.group(1)), int(m.group(2))

CTA_RE = re.compile(r'<a class="cta" href="([^"]+)">(.*?)</a>', re.S)
AUD_RE = re.compile(r'<span class="aud">(.*?)</span><span class="price">', re.S)
LP_RE = re.compile(r'<span class="slang"><span class="lp">(.*?)</span></span>$', re.S)


SR_COMMA = '<span class="sr-only">, </span>'


def split_aud(inner):
    """A stub's label -> (the inline label, its language line or ""). The language is the
    stub's own line, two parts in one `.lp` row (see build_pages.lang_line). Both come back
    in facts notation, see facts_of."""
    i = inner.find('<span class="slang">')
    if i < 0:
        return inner, ""
    lp = LP_RE.search(inner[i:])
    head = inner[:i]
    if head.endswith(SR_COMMA):
        head = head[:-len(SR_COMMA)]
    return head, facts_of(lp.group(1))
CANON_RE = re.compile(r'<link rel="canonical" href="([^"]+)">')
LANGSEG_RE = re.compile(r'<nav class="langseg"[^>]*>(.*?)</nav>', re.S)
RAW_CODE_RE = re.compile(r"\b[A-Z]{2}(?:-[A-Z]{2})?-[AS]\b")
HREFLANG_RE = re.compile(r'<link rel="alternate" hreflang="(fi|sv|en)" href="([^"]+)">')
DESC_RE = re.compile(r'<meta name="description" content="([^"]+)">')
OG_DESC_RE = re.compile(r'<meta property="og:description" content="([^"]+)">')
STUB_RE = re.compile(r'<li><(?:a|span) class="stub[^"]*"[^>]*>(.*?)</li>', re.S)


def text_of(html):
    """What a reader sees: tags and the screen-reader-only text removed."""
    return re.sub(r"<[^>]+>", "", re.sub(r'<span class="sr-only">.*?</span>', "", html))


def facts_of(html):
    """A stub's facts written " \u00b7 "-separated, the notation these tests use. The page
    draws a CSS square between two facts and gives each but the last a hidden comma
    (2026-09-23), so the comma is where a fact ends."""
    return text_of(html.replace(SR_COMMA, " \u00b7 "))


class HostilePosterPathTest(unittest.TestCase):
    """`og:image` carries the first poster path, which is provider text: cinemahouse.py
    unescapes a raw relative `src`, and mirror_posters and run.py pass a non-http value
    through. It went into the attribute unescaped, so a path holding a quote and a
    `</script>` put a script element into the head of the fi, sv and en venue and city
    pages (audit G1, 2026-09-25). Built from the committed data with one city's posters
    replaced."""

    HOSTILE = 'data/posters/x"><script>alert(9)</script><meta x="'

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(cls.tmp.name)
        (root / "data").mkdir()
        for p in REAL_DATA.glob("*.json"):
            shutil.copy2(p, root / "data" / p.name)
        today = bp.recorded_date()
        saved = (bp.ROOT, bp.DATA)
        bp.ROOT, bp.DATA = root, root / "data"
        try:
            by_city = {}
            for v in bp.load_venues():
                by_city.setdefault(bp.city_of(v), []).append(v["id"])
            window = {(today + timedelta(days=i)).isoformat() for i in range(bp.DAYS)}
            cls.city = next(c for c, ids in sorted(by_city.items()) if len(ids) > 1 and all(
                any(s.get("start", "")[:10] in window for s in bp.load_shows(i)) for i in ids))
            for vid in by_city[cls.city]:
                p = root / "data" / f"area-{vid}.json"
                doc = json.loads(p.read_text())
                for sh in doc["shows"]:
                    sh["img"] = cls.HOSTILE
                p.write_text(json.dumps(doc, ensure_ascii=False))
            bp._SHOWS.clear()
            with contextlib.redirect_stdout(io.StringIO()):
                bp.main(today=today)
            cls.pages = {str(p.relative_to(root)): p.read_text(encoding="utf-8")
                         for prefix in bp.PAGE_ROOTS for p in (root / prefix).glob("*/index.html")}
        finally:
            bp.ROOT, bp.DATA = saved
            bp._SHOWS.clear()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_path_is_escaped_in_the_head_of_every_language(self):
        city = bp.slug(self.city)
        hit = {k: v for k, v in self.pages.items() if self.HOSTILE.split('"')[0] in v}
        langs = {("sv" if k.startswith("sv/") else "en" if k.startswith("en/") else "fi")
                 for k in hit}
        self.assertEqual(langs, {"fi", "sv", "en"}, sorted(hit))
        self.assertTrue(any(f"/{city}/" in k for k in hit), "the city page carries it too")
        for k, page in hit.items():
            with self.subTest(page=k):
                head = page[:page.index("</head>")]
                self.assertFalse("<script>alert(9)</script>" in page, "the path ran as markup")
                self.assertIn(f'<meta property="og:image" content="{bp.SITE}/'
                              f'{html.escape(self.HOSTILE, quote=True)}">', head)


class GeneratedPagesTest(unittest.TestCase):
    """Build once from the committed data, then read what came out."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = pathlib.Path(cls.tmp.name)
        (cls.root / "data").mkdir()
        for p in REAL_DATA.glob("*.json"):
            shutil.copy2(p, cls.root / "data" / p.name)
        # The day the committed data was fetched for, read from the real sitemap before
        # ROOT moves: a build for the clock's day against a checkout whose data has aged
        # past it lists no showtimes, and on 2026-09-13 five city pages of a week-old
        # checkout came out empty that way. The same day rules every window below.
        cls.today = bp.recorded_date()
        cls.saved = (bp.ROOT, bp.DATA)
        bp.ROOT, bp.DATA = cls.root, cls.root / "data"
        bp._unmirrored_hosts.clear()
        cls.first_run = cls.run_main()
        cls.pages = {}
        for prefix in bp.PAGE_ROOTS:
            for p in sorted((cls.root / prefix).glob("*/index.html")):
                cls.pages["/" + str(p.relative_to(cls.root).parent) + "/"] = \
                    p.read_text(encoding="utf-8")
        cls.canonical = {k: v for k, v in cls.pages.items() if "noindex" not in v}
        cls.redirects = {k: v for k, v in cls.pages.items() if "noindex" in v}
        cls.providers = {p["id"]: p for p in
                         json.loads((REAL_DATA / "providers.json").read_text())["providers"]}
        # The venue list the way main() sees it: city and label derived, slugs
        # de-duplicated the same way, so the tests address pages by the same names.
        chains = {k: p.get("label", k) for k, p in cls.providers.items()}
        cls.venues, seen = [], set()
        for v in bp.load_venues():
            v["city"] = bp.city_of(v)
            v["label"] = bp.label_of(v, chains)
            v["slug"] = bp.slug(f"{v['label']} {v['city']}")
            if v["slug"] in seen:
                v["slug"] = f"{v['slug']}-{bp.slug(v['id'])}"
            seen.add(v["slug"])
            cls.venues.append(v)
        # One theatre page per venue and one city page per city with more than one venue,
        # in each of bp.LANGS. 75 venues and 10 such cities on 2026-09-02, which is 85.
        by_city = {}
        for v in cls.venues:
            by_city.setdefault(v["city"], []).append(v)
        cls.per_lang = len(cls.venues) + sum(1 for vs in by_city.values() if len(vs) > 1)

    @classmethod
    def tearDownClass(cls):
        bp.ROOT, bp.DATA = cls.saved
        cls.tmp.cleanup()

    @classmethod
    def run_main(cls):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            bp.main(today=cls.today)
        return buf.getvalue()

    def lang_of(self, path):
        """The language a canonical path is published in. Finnish is at the root."""
        return ("sv" if path.startswith("/sv/")
                else "en" if path.startswith("/en/") else "fi")

    def page_for(self, prefix, needle):
        hits = [k for k in self.canonical if k.startswith(prefix) and needle in k]
        self.assertEqual(len(hits), 1, f"{needle!r} under {prefix}: {hits}")
        return hits[0], self.canonical[hits[0]]

    # -- the set ---------------------------------------------------------------------------

    def test_the_six_families_render_in_the_advertised_counts(self):
        by_prefix = {}
        for k in self.canonical:
            for family in bp.PAGE_ROOTS:
                if k.startswith("/" + family + "/"):
                    by_prefix[family] = by_prefix.get(family, 0) + 1
                    break
            else:
                self.fail(f"{k} is under none of {bp.PAGE_ROOTS}")
        for lang, families in (("fi", ("teatteri", "kaupunki")),
                               ("sv", ("sv/teatteri", "sv/kaupunki")),
                               ("en", ("en/theatre", "en/city"))):
            with self.subTest(lang=lang):
                self.assertEqual(sum(by_prefix.get(f, 0) for f in families), self.per_lang)
        self.assertEqual(len(self.redirects), REDIRECTS)
        self.assertEqual(len(self.pages), len(bp.LANGS) * self.per_lang + REDIRECTS)
        for family in bp.PAGE_ROOTS:
            self.assertGreater(by_prefix.get(family, 0), 0, family)

    def test_the_readme_advertises_the_measured_counts(self):
        """`85 per language, 171 sitemap URLs` has to be what the data produces. The
        number was carried over from an older document and wrong five times before the
        rule in CLAUDE.md was written; this makes the sixth impossible to commit."""
        per_lang, urls = advertised()
        self.assertEqual(per_lang, self.per_lang)
        self.assertEqual(urls, len(bp.LANGS) * self.per_lang + 1)

    def test_the_sitemap_lists_exactly_the_canonical_pages(self):
        sm = (self.root / "sitemap.xml").read_text(encoding="utf-8")
        locs = set(re.findall(r"<loc>(.*?)</loc>", sm))
        self.assertEqual(locs, {bp.SITE + "/"} | {bp.SITE + k for k in self.canonical})
        self.assertEqual(len(locs), len(bp.LANGS) * self.per_lang + 1)

    def test_the_legacy_redirects_are_untouched(self):
        for k, text in self.redirects.items():
            with self.subTest(path=k):
                committed = (ROOT / k.strip("/") / "index.html").read_text(encoding="utf-8")
                self.assertEqual(text, committed)
                self.assertNotIn('class="cta"', text)

    def test_every_canonical_page_points_at_itself_and_its_alternates(self):
        for k, text in self.canonical.items():
            with self.subTest(path=k):
                self.assertEqual(CANON_RE.search(text).group(1), bp.SITE + k)
                head = text.split("</head>")[0]
                alts = dict(HREFLANG_RE.findall(head))
                self.assertEqual(set(alts), set(bp.LANGS))
                self.assertEqual(alts[self.lang_of(k)], bp.SITE + k)
                # x-default is the Finnish page: the one a reader with no matching
                # language gets.
                xd = re.search(r'hreflang="x-default" href="([^"]+)"', head)
                self.assertIsNotNone(xd, head)
                self.assertEqual(xd.group(1), alts["fi"])
                self.assertEqual(re.search(r'<html lang="(\w+)">', text).group(1),
                                 self.lang_of(k))

    # -- the language selector ---------------------------------------------------------------

    def test_the_selector_marks_this_language_and_links_the_other_two(self):
        """FI · SV · EN on every page: the page's own language is a non-link marked
        current, and the other two link to the same cinema or city in their language.

        Swedish used to link into the app instead, because it had no page, so choosing SV
        on a city page changed the kind of page as well as the language and choosing EN
        again did not come back. Changing the language changes the language."""
        for k, text in self.canonical.items():
            with self.subTest(path=k):
                segs = LANGSEG_RE.findall(text)
                self.assertEqual(len(segs), 1)
                seg = segs[0]
                items = re.findall(r"<(a|span)([^>]*)>(FI|SV|EN)</(?:a|span)>", seg)
                self.assertEqual([i[2] for i in items], [c.upper() for c in bp.LANGS])
                cur = [i for i in items if 'aria-current="page"' in i[1]]
                self.assertEqual(len(cur), 1)
                self.assertEqual(cur[0][0], "span")
                self.assertEqual(cur[0][2], self.lang_of(k).upper())
                alts = dict(HREFLANG_RE.findall(text.split("</head>")[0]))
                for code in bp.LANGS:
                    if code == self.lang_of(k):
                        continue
                    m = re.search(rf'<a href="([^"]+)" hreflang="{code}">{code.upper()}</a>',
                                  seg)
                    self.assertIsNotNone(m, seg)
                    self.assertEqual(bp.SITE + html.unescape(m.group(1)), alts[code])
                    self.assertIn(html.unescape(m.group(1)), self.canonical,
                                  "the selector links a page this build did not write")

    def test_the_selector_is_a_round_trip_over_the_same_cinema_or_city(self):
        """The requirement the Swedish pages exist for: switching language changes the
        language and nothing else, and switching back comes back.

        Same kind of page, same cinema or city, and the page it lands on links to the one
        it came from. A reader who tries SV and changes their mind is where they started.
        """
        def kind(path):
            return "city" if ("/kaupunki/" in path or "/city/" in path) else "venue"

        for k, text in self.canonical.items():
            with self.subTest(path=k):
                seg = LANGSEG_RE.findall(text)[0]
                for href, code in re.findall(r'<a href="([^"]+)" hreflang="(\w+)">', seg):
                    href = html.unescape(href)
                    self.assertEqual(kind(href), kind(k), (k, href))
                    self.assertEqual(href.rstrip("/").split("/")[-1],
                                     k.rstrip("/").split("/")[-1], (k, href))
                    other = LANGSEG_RE.findall(self.canonical[href])[0]
                    back = re.search(rf'<a href="([^"]+)" hreflang="{self.lang_of(k)}">',
                                     other)
                    self.assertIsNotNone(back, other)
                    self.assertEqual(html.unescape(back.group(1)), k)

    def test_every_cinema_and_city_is_published_in_every_language(self):
        """No page family is short a language, which is what made SV the odd one out."""
        by_slug = {}
        for k in self.canonical:
            by_slug.setdefault((k.rstrip("/").split("/")[-1],
                                "city" if ("/kaupunki/" in k or "/city/" in k) else "venue"),
                               set()).add(self.lang_of(k))
        for key, langs in sorted(by_slug.items()):
            with self.subTest(page=key):
                self.assertEqual(langs, set(bp.LANGS))

    def test_every_day_heading_is_a_weekday_and_a_date(self):
        """Never "Tänään" or "Huomenna": a page is read until the next build, and after
        midnight those named yesterday and today (2026-10-04). Past screenings may still
        show until that build; they are not called today."""
        heads = 0
        for k, text in self.canonical.items():
            t = bp.L[self.lang_of(k)]
            for label in re.findall(r'<h2 class="day">([^<]*)</h2>', text):
                heads += 1
                with self.subTest(page=k, label=label):
                    m = re.fullmatch(r"(\w+) (\d{1,2})\.(\d{1,2})\.", html.unescape(label))
                    self.assertIsNotNone(m)
                    d = self.today.replace(month=int(m.group(3)), day=int(m.group(2)))
                    if d < self.today:
                        d = d.replace(year=d.year + 1)
                    self.assertEqual(m.group(1), t["days"][d.weekday()])
                    for word in ("T\u00e4n\u00e4\u00e4n", "Huomenna", "I dag", "I morgon",
                                 "Today", "Tomorrow"):
                        self.assertNotIn(word, label)
        self.assertGreater(heads, 100, "too few day headings to mean anything")

    def test_today_and_tomorrow_are_labelled_like_any_other_day(self):
        for lang, want in (("fi", ["La 3.10.", "Su 4.10.", "Ma 5.10."]),
                           ("sv", ["L\u00f6r 3.10.", "S\u00f6n 4.10.", "M\u00e5n 5.10."]),
                           ("en", ["Sat 3.10.", "Sun 4.10.", "Mon 5.10."])):
            with self.subTest(lang=lang):
                self.assertEqual([bp.day_label(f"2026-10-0{d}", bp.L[lang]) for d in (3, 4, 5)],
                                 want)

    def test_an_empty_page_offers_the_cinemas_next_known_date(self):
        """The app already answered "nothing today, what about later" and the landing page
        for the same cinema did not. `next_show_day` reads the same committed file the page
        is built from, so the page can say it too."""
        empty = [(k, v) for k, v in self.canonical.items()
                 if bp.L[self.lang_of(k)]["no_shows"] in v]
        self.assertTrue(empty, "no page in this build is empty; the fixture proves nothing")
        offered = 0
        for k, text in empty:
            with self.subTest(path=k):
                t = bp.L[self.lang_of(k)]
                lead = t["next_show"].split("{")[0]
                if lead not in text:
                    continue
                offered += 1
                # No double stop: day_label ends in the date's own.
                m = re.search(re.escape(lead) + r"([^<]*)", text)
                self.assertIsNotNone(m)
                self.assertNotIn("..", m.group(1))
        self.assertGreater(offered, 0,
                           "no empty page named a later date; the committed data has some")

    def test_the_next_date_is_after_the_window_and_the_cinema_really_has_it(self):
        """A one-item check would pass on an empty list, so this runs the helper over two
        shapes: a venue with a screening past the window and one with none at all."""
        today = self.today
        end = today + timedelta(days=bp.DAYS - 1)
        after = [{"start": (end + timedelta(days=2)).isoformat() + "T18:00:00+03:00"},
                 {"start": (end + timedelta(days=5)).isoformat() + "T18:00:00+03:00"}]
        inside = [{"start": today.isoformat() + "T18:00:00+03:00"},
                  {"start": today.isoformat() + "T20:00:00+03:00"}]
        self.assertEqual(bp.next_show_day(after, today, bp.DAYS),
                         (end + timedelta(days=2)).isoformat())
        # The day the window ends and the one after it: the boundary is the whole rule,
        # and a fixture that only uses dates well past it cannot see it move.
        edge = [{"start": end.isoformat() + "T18:00:00+03:00"},
                {"start": (end + timedelta(days=1)).isoformat() + "T18:00:00+03:00"}]
        self.assertEqual(bp.next_show_day(edge, today, bp.DAYS),
                         (end + timedelta(days=1)).isoformat())
        self.assertEqual(bp.next_show_day(inside, today, bp.DAYS), "")
        self.assertEqual(bp.next_show_day([], today, bp.DAYS), "")
        past = [{"start": (today - timedelta(days=3)).isoformat() + "T18:00:00+03:00"},
                {"start": (today - timedelta(days=1)).isoformat() + "T18:00:00+03:00"}]
        self.assertEqual(bp.next_show_day(past, today, bp.DAYS), "")

    def test_every_link_between_pages_stays_in_the_pages_language(self):
        """The cinema links on a city page and the city link on a cinema page. A Swedish
        city page listing Finnish cinema pages would drop the reader out of Swedish on the
        next click, which is the same fault the selector had."""
        for k, text in self.canonical.items():
            with self.subTest(path=k):
                hrefs = [html.unescape(h) for h in
                         re.findall(r'<a class="vchip[^"]*" href="([^"]+)"', text)]
                self.assertTrue(hrefs or "/kaupunki/" not in k and "/city/" not in k, k)
                for href in hrefs:
                    self.assertIn(href, self.canonical, (k, href))
                    self.assertEqual(self.lang_of(href), self.lang_of(k), (k, href))

    def test_the_selector_never_sends_a_reader_into_the_app(self):
        """The fault this replaced: SV was `/?area=...&lang=sv`, a different kind of page
        with a different set of controls and a different span of days."""
        for k, text in self.canonical.items():
            with self.subTest(path=k):
                seg = LANGSEG_RE.findall(text)[0]
                self.assertNotIn("/?area=", html.unescape(seg))

    # -- the CTA ---------------------------------------------------------------------------

    def test_one_cta_per_page_in_the_pages_own_language(self):
        old = "Ajantasaiset ajat, suodattimet ja koko ohjelmisto"
        for k, text in self.canonical.items():
            with self.subTest(path=k):
                ctas = CTA_RE.findall(text)
                self.assertEqual(len(ctas), 1)
                label = " ".join(text_of(ctas[0][1]).replace("\u2192", "").split())
                # One line, one label: the intro already says the app carries the days
                # ahead, so the button does not repeat it.
                self.assertEqual(label, bp.L[self.lang_of(k)]["cta"])
                for gone in (old, "nyt ja tulevina", "upcoming screenings", 'class="more"'):
                    self.assertNotIn(gone, text)

    def test_the_cta_carries_this_pages_venue_or_city_and_its_language(self):
        ids = {v["id"] for v in self.venues}
        by_slug = {v["slug"]: v["id"] for v in self.venues}
        for k, text in self.canonical.items():
            with self.subTest(path=k):
                href = html.unescape(CTA_RE.search(text).group(1))
                m = re.fullmatch(r"/\?area=([^&]+)&lang=(fi|sv|en)", href)
                self.assertIsNotNone(m, href)
                area = bp.urllib.parse.unquote(m.group(1))
                self.assertEqual(m.group(2), self.lang_of(k))
                if "/theatre/" in k or "/teatteri/" in k:
                    self.assertIn(area, ids)
                    self.assertEqual(area, by_slug[k.rstrip("/").split("/")[-1]])
                else:
                    self.assertTrue(area.startswith("city:"), area)
                    self.assertEqual(bp.slug(area[5:]), k.rstrip("/").split("/")[-1])

    def test_the_wordmark_carries_this_pages_language(self):
        """Home from an English page used to open a Finnish app. The wordmark is a link
        out of the page like the CTA, and it says the same thing about the language."""
        for k, text in self.canonical.items():
            with self.subTest(path=k):
                m = re.search(r'<a class="logo" href="([^"]+)"', text)
                self.assertIsNotNone(m, k)
                self.assertEqual(html.unescape(m.group(1)), "/?lang=" + self.lang_of(k))

    def test_the_parameters_are_the_ones_the_client_reads(self):
        """The link is only as good as the code at the other end. Both names are read out
        of index.html rather than assumed, so a rename on either side fails here."""
        client = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn(".get('area')", client)
        self.assertIn(".get('lang')", client)
        self.assertIn("function startupLang(", client)
        for text in self.canonical.values():
            href = html.unescape(CTA_RE.search(text).group(1))
            self.assertTrue(href.startswith("/?area="), href)
            self.assertIn("&lang=", href)

    # -- the showtime label ----------------------------------------------------------------

    def test_a_theatre_page_never_repeats_its_own_cinema_in_a_showtime(self):
        """Data-driven over every venue: each room the data holds appears verbatim, and
        neither the venue's short name nor its label is prepended to it."""
        checked = 0
        for v in self.venues:
            # Only shows inside the page's own window count: a touring cinema can hold
            # shows in its file and none in the next four days, and that page is right
            # to carry no stubs.
            window = bp.group_by_day(bp.load_shows(v["id"]), self.today)
            if not window:
                continue
            k = f"/teatteri/{v['slug']}/"
            text = self.canonical[k]
            stubs = [text_of(m) for m in STUB_RE.findall(text)]
            self.assertTrue(stubs, k)
            checked += 1
            for st in stubs:
                self.assertNotIn(f"{bp.short_of(v)} · ", st, (k, st))
                self.assertNotIn(f"{v['label']} · ", st, (k, st))
            # And the room does appear, verbatim, for every show in the window that has
            # one -- so the assertion above cannot pass on an empty label.
            for day in window.values():
                for shs in day.values():
                    for sh in shs:
                        if sh.get("aud"):
                            self.assertTrue(any(sh["aud"] in st for st in stubs),
                                            (k, sh["aud"]))
        self.assertGreater(checked, 50, "the committed data stopped carrying showtimes")

    def test_tapio_reads_sali_tapio_4_and_none_of_the_bad_forms(self):
        k, text = self.page_for("/teatteri/", "savon-kinot-tapio")
        body = text_of(text)
        self.assertIn("Sali Tapio", body)
        for bad in ("TAPIO | TAPIO", "Tapio Tapio", "Sali Sali", "Tapio · Sali"):
            self.assertNotIn(bad, body, bad)

    # -- language in words -------------------------------------------------------------------

    def test_no_raw_language_code_is_left_on_any_page(self):
        """The storage format stays in the JSON. Every -A/-S tag on every page built from
        the committed data has become words."""
        for k, text in self.canonical.items():
            with self.subTest(path=k):
                for block in re.findall(r'<article class="film">(.*?)</article>', text, re.S):
                    self.assertIsNone(RAW_CODE_RE.search(text_of(block)), text_of(block)[:120])

    def test_every_code_in_the_committed_data_is_known(self):
        """The guarantee behind the test above, stated on the data rather than the output:
        each language code the adapters currently publish has a name in `LN`. A new code
        fails here first, by name. There is no alias layer any more: the TU/MA/XX
        aliases were deleted 2026-09-15 once the data carried none of them. `XX` came back
        on 2026-09-29 with a meaning, "no subtitles", in the subtitle role only."""
        seen = set()
        for p in (REAL_DATA).glob("area-*.json"):
            for s in json.loads(p.read_text(encoding="utf-8")).get("shows", []):
                for raw in (s.get("lang") or "").split(","):
                    c = raw.strip()
                    if not c:
                        continue
                    m = bp.LANG_RE.match(c)
                    self.assertIsNotNone(m, (p.name, c))
                    if c != bp.NO_SUBS + "-S":
                        seen.update(m.group(1).split("-"))
        self.assertTrue(seen)
        self.assertEqual(seen - set(bp.LN["fi"]), set())

    def test_the_name_tables_are_the_clients(self):
        """Read out of index.html rather than retyped: `LN.fi` and `LN.en` there must equal
        the generator's, key for key, so the two cannot drift apart quietly."""
        client = (ROOT / "index.html").read_text(encoding="utf-8")
        block = re.search(r"const LN = \{(.*?)\n  \};", client, re.S).group(1)
        tables = {}
        for lang in ("fi", "en"):
            body = re.search(rf"\b{lang}:\{{(.*?)\}}", block, re.S).group(1)
            tables[lang] = dict(re.findall(r"([A-Z]{2}):'([^']*)'", body))
        self.assertEqual(tables["fi"], bp.LN["fi"])
        self.assertEqual(tables["en"], bp.LN["en"])
        self.assertGreater(len(tables["fi"]), 20)

    def test_the_finnish_subtitle_label_is_the_clients(self):
        """`LW.fi.S` in index.html and the generator's `subs` must render the same words:
        "tekstitys: suomi/ruotsi" on the card and on the page."""
        client = (ROOT / "index.html").read_text(encoding="utf-8")
        word = re.search(r"const LW = \{ fi:\{S:'([^']*)'\}", client).group(1)
        self.assertEqual(f"{word} suomi/ruotsi", bp.L["fi"]["subs"].format("suomi/ruotsi"))
        self.assertTrue(word.endswith(":"), word)

    def test_a_price_appears_only_inside_a_screening_stub(self):
        """Across every generated page: the euro sign occurs only inside a stub's price
        element, never in the card's metadata. The committed Tampere case of 2026-09-02
        is one instance; this holds for whatever the data says today."""
        for k, text in self.canonical.items():
            with self.subTest(path=k):
                body = text.split("<main>")[1].split("</main>")[0]
                metas = re.findall(r'<div class="meta[12]">(.*?)</div>', body)
                self.assertFalse(any("\u20ac" in m for m in metas), k)
                # A synopsis is the cinema's prose and may quote a price ("9€/kpl" in a
                # senior-screening blurb); it is not a label and is left out of the check.
                stripped = re.sub(r'<p class="syn">.*?</p>', "", body, flags=re.S)
                stripped = re.sub(r'<span class="price">[^<]*</span>', "", stripped)
                # The film title is the cinema's own text and is published verbatim, which
                # CLAUDE.md requires because it is the key for normTitle, films-extra and
                # the TMDB aliases. Bio Marilyn Lapua names its cheap screenings
                # "Autot 20v Juhlajulkaisu (5€)" and two others the same way, read
                # 2026-09-18. The label check above still holds.
                stripped = re.sub(r"<h3>.*?</h3>", "", stripped, flags=re.S)
                self.assertNotIn("\u20ac", stripped, k)
                for li in re.findall(r"<li>(.*?)</li>", body, re.S):
                    self.assertLessEqual(li.count('class="price"'), 1)

    def test_a_city_page_stacks_its_stubs_and_a_theatre_page_does_not(self):
        """The app's combined view is a grid of stacked stubs; its single-venue view is a
        row of ticket stubs. A city page is the combined view."""
        for k, text in self.canonical.items():
            with self.subTest(path=k):
                lists = re.findall(r'<ul class="times( grid)?">', text)
                if not lists:
                    continue          # nothing in the window; the count test covers it
                city = "/kaupunki/" in k or "/city/" in k
                self.assertEqual({bool(g) for g in lists}, {city})

    def test_the_price_label_is_the_clients(self):
        """The client's own harness cases, run through both implementations. The case
        table is read out of tests/price_label_harness.js and its answers come from node
        running the shipped priceLabel, so neither side is retyped here."""
        if shutil.which("node") is None:
            self.skipTest("node not installed")
        harness = ROOT / "tests" / "price_label_harness.js"
        out = subprocess.run(["node", str(harness)], capture_output=True, text=True,
                             cwd=str(ROOT), timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        expected = json.loads(out.stdout)
        src = harness.read_text(encoding="utf-8")
        cases = re.findall(r"^\s*\['(\w+)',\s*'(\w+)',\s*\[(.*?)\]\],?\s*$", src, re.M)
        self.assertGreater(len(cases), 15)
        checked = 0
        for name, lang, inner in cases:
            if lang not in ("fi", "en"):
                continue
            prices = ast.literal_eval("[" + inner.replace("null", "None").replace("undefined", "None") + "]")
            with self.subTest(case=name):
                self.assertEqual(bp.price_label([{"price": p} for p in prices], lang), expected[name])
                checked += 1
        self.assertGreater(checked, 12)
        for lang in ("fi", "en"):
            self.assertEqual(expected["__from"][lang], bp.L[lang]["from"])

    def test_a_city_page_names_the_cinema_on_every_showtime(self):
        labels = {v["label"] for v in self.venues}
        by_city = {}
        for v in self.venues:
            by_city.setdefault(bp.slug(bp.city_of(v)), []).append(v)
        checked = 0
        for k, text in self.canonical.items():
            if not (k.startswith("/kaupunki/") or k.startswith("/en/city/")):
                continue
            # Only shows inside the page's own window count, the rule the venue pages
            # above already get. Nurmijärvi's two cinemas had nothing inside CITY_DAYS
            # on 2026-09-19 and its page was right to carry no stubs; asserting per page
            # turned a quiet city into a red suite.
            city = by_city.get(k.rstrip("/").rsplit("/", 1)[-1], [])
            merged = [s for v in city for s in bp.load_shows(v["id"])]
            if not bp.group_by_day(merged, self.today, bp.CITY_DAYS):
                continue
            with self.subTest(path=k):
                stubs = STUB_RE.findall(text)
                self.assertTrue(stubs, k)
                checked += 1
                for st in stubs:
                    m = re.search(r"<span class=v>(.*?)(?:<span class=\"sr-only\">, </span>)?</span>", st)
                    self.assertIsNotNone(m, (k, text_of(st)))
                    self.assertIn(html.unescape(m.group(1)), labels, (k, text_of(st)))
        # So a window that emptied every city page cannot pass this vacuously.
        self.assertGreater(checked, 0)

    def test_no_stub_has_a_leading_trailing_or_doubled_separator(self):
        for k, text in self.canonical.items():
            with self.subTest(path=k):
                for aud in AUD_RE.findall(text):
                    self.assertNotIn("·", text_of(aud), "the separator is a CSS square")
                    plain = facts_of(aud)
                    self.assertFalse(plain.startswith("·") or plain.startswith(" ·"), plain)
                    self.assertFalse(plain.endswith("·") or plain.endswith("· "), plain)
                    self.assertNotIn("· ·", plain)
                    self.assertNotIn("··", plain)
                    self.assertNotRegex(aud, r"<span class=\w+></span>")

    # -- the copy --------------------------------------------------------------------------

    def test_the_intro_promises_what_the_booking_mode_offers(self):
        """Every venue page, against the registry's own `book` field."""
        for v in self.venues:
            k = f"/teatteri/{v['slug']}/"
            prov = self.providers[v["provider"]]
            for lang, path in ((("fi", k)), ("en", "/en/theatre" + k[len("/teatteri"):])):
                with self.subTest(path=path):
                    expected = bp.venue_intro(bp.L[lang], prov.get("book"), prov["host"])
                    self.assertIn(bp.esc(expected), self.canonical[path])

    def test_all_five_booking_modes_have_their_own_sentence(self):
        for lang in ("fi", "en"):
            seen = {bp.venue_intro(bp.L[lang], b, "x.fi")
                    for b in ("buy", "reserve", "list", "door", "admission")}
            self.assertEqual(len(seen), 5, lang)
            self.assertNotIn("x.fi", bp.venue_intro(bp.L[lang], "door", "x.fi"))
            for b in ("buy", "reserve", "list", "admission"):
                self.assertIn("x.fi", bp.venue_intro(bp.L[lang], b, "x.fi"))
            self.assertEqual(bp.venue_intro(bp.L[lang], None, "x.fi"),
                             bp.venue_intro(bp.L[lang], "buy", "x.fi"))

    def test_a_city_intro_does_not_promise_ticket_sales(self):
        for k, text in self.canonical.items():
            if not (k.startswith("/kaupunki/") or k.startswith("/en/city/")):
                continue
            with self.subTest(path=k):
                self.assertNotIn("sivustolla", text_of(text).split("<h2")[0])
                self.assertIn("kun linkki on saatavilla" if k.startswith("/kaupunki/")
                              else "where available", text)

    def test_the_description_is_the_booking_modes_and_sits_in_both_meta_tags(self):
        """One string for `meta name="description"` and `og:description`, built from the
        registry's `book`. A search result is where a promise is quoted, so a door-sales
        venue advertising a ticket link is the fault this pins."""
        for v in self.venues:
            k = f"/teatteri/{v['slug']}/"
            prov = self.providers[v["provider"]]
            for lang, path in (("fi", k), ("en", "/en/theatre" + k[len("/teatteri"):])):
                with self.subTest(path=path):
                    want = bp.esc(bp.venue_desc(bp.L[lang], v["label"], v["city"],
                                                prov.get("book")))
                    text = self.canonical[path]
                    self.assertEqual(DESC_RE.search(text).group(1), want)
                    self.assertEqual(OG_DESC_RE.search(text).group(1), want)

    def test_kino_akseli_offers_no_link_and_kino_hovi_sells_tickets(self):
        """The two ends of the rule by name. Kino Akseli publishes no ticket URL at all
        and sells at the door; Kino-Hovi is a `buy` venue on savonkinot.fi."""
        by_id = {v["id"]: v for v in self.venues}
        cases = {
            # "Samalta sivulta" is the page itself; "teatterin sivulta" is the promise.
            ("ka-nummela", "fi"): (["ovelta"],
                                   ["ostamaan", "varaamaan", "teatterin sivulta"]),
            ("ka-nummela", "en"): (["sold at the cinema"],
                                   ["buy tickets", "reserve seats", "website"]),
            ("sk-kinohovi", "fi"): (["ostamaan liput teatterin sivulta"], ["ovelta"]),
            ("sk-kinohovi", "en"): (["buy tickets"], ["sold at the cinema"]),
        }
        for (vid, lang), (present, absent) in cases.items():
            v = by_id[vid]
            path = (f"/teatteri/{v['slug']}/" if lang == "fi"
                    else f"/en/theatre/{v['slug']}/")
            desc = html.unescape(DESC_RE.search(self.canonical[path]).group(1))
            with self.subTest(path=path):
                for w in present:
                    self.assertIn(w, desc)
                for w in absent:
                    self.assertNotIn(w, desc)

    def test_a_city_description_names_no_cinema(self):
        """The old copy listed every venue, which spent a ten-cinema city's whole snippet
        on names and went stale in the index whenever one was added or renamed."""
        by_city = {}
        for v in self.venues:
            by_city.setdefault(v["city"], []).append(v)
        for c, vs in by_city.items():
            if len(vs) < 2:
                continue
            for lang, path in (("fi", f"/kaupunki/{bp.slug(c)}/"),
                               ("en", f"/en/city/{bp.slug(c)}/")):
                with self.subTest(path=path):
                    text = self.canonical[path]
                    want = bp.esc(bp.city_desc(bp.L[lang], c))
                    self.assertEqual(DESC_RE.search(text).group(1), want)
                    self.assertEqual(OG_DESC_RE.search(text).group(1), want)
                    # Not a second copy of the title either: a snippet that repeats the
                    # heading tells a reader nothing the result already showed.
                    self.assertNotEqual(want, re.search(r"<title>(.*?)</title>",
                                                        text, re.S).group(1))
                    for v in vs:
                        self.assertNotIn(v["label"], html.unescape(want))

    def test_every_description_stays_within_a_snippet_length(self):
        """110-220 characters. Re-measured 2026-09-22 over the committed 134 venues and
        17 multi-venue cities: fi venue 125-170, en venue 140-175, fi city and en city
        both 135-141. The fi opening on its own runs 49 ("Kino Lumo", Salo) to 82
        characters, so an ending dropped from any page falls through the floor here, and
        the longest city name in the data reaches 143, so a city gaining a second venue
        cannot breach the ceiling."""
        for k, text in self.canonical.items():
            with self.subTest(path=k):
                desc = html.unescape(DESC_RE.search(text).group(1))
                self.assertGreaterEqual(len(desc), 110, desc)
                self.assertLessEqual(len(desc), 220, desc)

    # -- stability -------------------------------------------------------------------------

    def test_regenerating_writes_nothing(self):
        out = self.run_main()
        self.assertIn(" 0 files written", out)

    def test_nothing_volatile_reaches_a_page(self):
        """Only a stamp with a time component is evidence. `films-extra.json` writes
        `generated` as a bare date, and every page with a screening that day carries the
        same date inside a JSON-LD `startDate`; on 2026-09-02 that failed 154 pages on a
        legitimate `2026-09-02T18:15:00+03:00`. It had passed only while the date-only
        stamp lagged a day behind the screenings on the page. A build timestamp that
        leaked would carry its time of day, and that is what is searched for."""
        stamps = set()
        for p in (self.root / "data").glob("*.json"):
            d = json.loads(p.read_text(encoding="utf-8"))
            for key in ("generated", "oldest"):
                if isinstance(d, dict) and d.get(key) and "T" in d[key]:
                    stamps.add(d[key])
        self.assertTrue(stamps)
        self.assertTrue(all(len(st) >= len("2026-09-02T05:10") for st in stamps))
        for k, text in self.pages.items():
            with self.subTest(path=k):
                for st in stamps:
                    self.assertNotIn(st, text)
                body_scripts = re.findall(r"<script>(.*?)</script>", text.split("</head>")[1], re.S)
                if k in self.redirects:
                    self.assertEqual(body_scripts, [])
                else:
                    self.assertEqual(len(body_scripts), 1)
                    self.assertIn("kino-theme", body_scripts[0])

    # -- the theme ---------------------------------------------------------------------------

    def test_the_theme_is_read_before_first_paint_from_the_apps_key(self):
        for k, text in self.canonical.items():
            with self.subTest(path=k):
                head = text.split("</head>")[0]
                scripts = re.findall(r"<script>(.*?)</script>", head, re.S)
                self.assertEqual(len(scripts), 1)
                js = scripts[0]
                self.assertIn("localStorage.getItem('kino-theme')", js)
                self.assertIn("prefers-color-scheme: dark", js)
                self.assertIn("setAttribute('data-theme'", js)
                # a stored value the app never writes is treated as absent, not applied
                self.assertIn("k==='dark'||k==='light'", js)
                self.assertLess(head.index("<script>"), head.index("<style>"))

    def test_the_stylesheet_honours_the_stored_theme_and_falls_back_to_the_os(self):
        for k, text in self.canonical.items():
            with self.subTest(path=k):
                css = re.search(r"<style>(.*?)</style>", text, re.S).group(1)
                self.assertIn(":root[data-theme=dark]{--bg:#0D0E12", css)
                self.assertIn("@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0D0E12", css)
                self.assertIn("html:not([data-theme]) #themeToggle{display:none}", css)

    def test_the_toggle_is_the_apps_button_with_a_localised_name(self):
        for k, text in self.canonical.items():
            with self.subTest(path=k):
                m = re.search(r'<button id="themeToggle" type="button" title="([^"]+)" aria-label="([^"]+)">', text)
                self.assertIsNotNone(m)
                self.assertEqual(m.group(2), bp.L[self.lang_of(k)]["a_theme"])
                body_js = re.findall(r"<script>(.*?)</script>", text.split("</head>")[1], re.S)[0]
                self.assertIn("localStorage.setItem('kino-theme',next)", body_js)
                self.assertIn("theme-color", body_js)

    def test_no_script_renders_content(self):
        """The rule the pages keep: what the crawler reads is what the visitor reads. The
        two scripts touch an attribute, a meta and a button, nothing else."""
        for k, text in self.canonical.items():
            with self.subTest(path=k):
                for js in re.findall(r"<script>(.*?)</script>", text, re.S):
                    for banned in ("innerHTML", "document.write", "createElement",
                                   "appendChild", "fetch(", "textContent"):
                        self.assertNotIn(banned, js)

    @unittest.skipIf(shutil.which("node") is None, "node not installed")
    def test_the_inline_scripts_parse(self):
        """The same check `scripts/check_inline_js.py` gives the app, against one page of
        each family; the scripts are constants, so one page each is every page."""
        for prefix in ("/teatteri/", "/kaupunki/", "/en/theatre/", "/en/city/"):
            k = next(p for p in self.canonical if p.startswith(prefix))
            for js in re.findall(r"<script>(.*?)</script>", self.canonical[k], re.S):
                with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
                    f.write(js); name = f.name
                try:
                    r = subprocess.run(["node", "--check", name], capture_output=True, text=True)
                finally:
                    pathlib.Path(name).unlink()
                self.assertEqual(r.returncode, 0, (k, r.stderr))


class LateClockTest(GeneratedPagesTest):
    """Every page assertion above, built with a clock 400 days past the recorded day.

    The build must follow the recorded day, not the clock: on 2026-09-13 a checkout whose
    data ended on 2026-09-12 lost every showtime in five cities when the pages were built
    for the clock's day, and eleven tests failed with nothing wrong in the generator. The
    clock here is far enough out that no data window can reach it, so this class passes
    on any real day with the fix and fails on the city-page content assertions without."""

    @classmethod
    def setUpClass(cls):
        recorded = bp.recorded_date()
        late = datetime.combine(recorded + timedelta(days=400), time(12), tzinfo=bp.FI)

        class LateClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return late if tz is None else late.astimezone(tz)

        cls.saved_clock = bp.datetime
        bp.datetime = LateClock
        try:
            super().setUpClass()
        except BaseException:
            bp.datetime = cls.saved_clock
            raise

    @classmethod
    def tearDownClass(cls):
        bp.datetime = cls.saved_clock
        super().tearDownClass()

    def test_the_clock_is_indeed_later_than_the_recorded_day(self):
        self.assertGreater(bp.datetime.now(bp.FI).date(), self.today)


class DescriptionCopyTest(unittest.TestCase):
    """`venue_desc` and `city_desc` away from the data: one ending per booking mode, a
    neutral ending for a mode the table does not know, and escaping at both meta tags."""

    # What each ending promises, per language. A door, admission or unknown mode must
    # name none of them: the page cannot link a ticket it has no URL for.
    PROMISES = {"fi": ("ostamaan", "varaamaan", "ohjelmisto", "teatterin sivulta"),
                "en": ("buy tickets", "reserve seats", "own programme", "website")}

    def test_each_booking_mode_gets_its_own_ending(self):
        for lang in ("fi", "en"):
            seen = {bp.venue_desc(bp.L[lang], "Kino V", "Kitee", b) for b in bp.DESC_MODES}
            self.assertEqual(len(seen), len(bp.DESC_MODES), lang)
            for d in seen:
                self.assertTrue(d.startswith(
                    bp.L[lang]["venue_desc"].format(venue="Kino V", city="Kitee") + " "), d)

    def test_a_door_or_admission_ending_leads_with_its_claim(self):
        """A snippet is cut long before the ending finishes. Behind the "you can also
        check..." sentence these two claims began past char 120 on all 21 door and
        admission pages, and at or past 155 on six of them, which cut "Liput myydään te".
        The keyword, not the sentence, so a wording edit survives and a reorder does
        not."""
        claims = {("fi", "door"): "ovelta",
                  ("fi", "admission"): "pääsylippuun",
                  ("en", "door"): "sold at the cinema",
                  ("en", "admission"): "included with admission"}
        for (lang, book), word in claims.items():
            with self.subTest(lang=lang, book=book):
                t = bp.L[lang]
                desc = bp.venue_desc(t, "Kino V", "Kitee", book)
                ending = desc[len(t["venue_desc"].format(venue="Kino V", city="Kitee")) + 1:]
                self.assertIn(word, ending.split(". ")[0])

    def test_an_unknown_or_missing_mode_promises_nothing_beyond_the_page(self):
        """venue_intro falls back to `buy`; a description must not. A provider added with
        a mode nobody has written copy for would otherwise advertise a ticket link."""
        for lang in ("fi", "en"):
            t = bp.L[lang]
            want = t["venue_desc"].format(venue="Kino V", city="Kitee") + " " + t["desc_other"]
            for book in (None, "", "gift-card", "BUY", "desc_buy", "other"):
                with self.subTest(lang=lang, book=book):
                    self.assertEqual(bp.venue_desc(t, "Kino V", "Kitee", book), want)

    def test_a_door_admission_or_unknown_venue_never_offers_a_link(self):
        for lang, words in self.PROMISES.items():
            for book in ("door", "admission", None):
                d = bp.venue_desc(bp.L[lang], "Kino V", "Kitee", book)
                for w in words:
                    with self.subTest(lang=lang, book=book, word=w):
                        self.assertNotIn(w, d)

    def test_a_city_description_is_the_citys_and_carries_no_venue_slot(self):
        for lang in ("fi", "en"):
            d = bp.city_desc(bp.L[lang], "Kitee")
            self.assertIn("Kitee", d)
            self.assertNotIn("{", d)

    def test_a_hostile_venue_name_is_escaped_in_both_meta_tags(self):
        """The name is provider text and reaches two attributes. `"` closes an attribute
        and `<` opens a tag, so both are checked on the rendered page rather than on the
        string the builder returned."""
        desc = bp.venue_desc(bp.L["fi"], 'Kino "A" & <b>B</b>', "Kitee", "buy")
        text = bp.page(
            lang="fi", paths={"fi": "/teatteri/x/", "sv": "/sv/teatteri/x/", "en": "/en/theatre/x/"}, title="T",
            desc=desc, h1="H", sub="S", intro="I", days={}, today=date(2026, 9, 21),
            t=bp.L["fi"], extra={}, gmap={}, city="Kitee", with_venue=False, legend="",
            also="", og_image="/icon-512.png", app_href="/?area=x&lang=fi", area="x",
            chain_css="", kind="theatre")
        both = [DESC_RE.search(text).group(1), OG_DESC_RE.search(text).group(1)]
        self.assertEqual(both[0], both[1])
        self.assertEqual(html.unescape(both[0]), desc)
        for raw in ('"A"', "<b>", " & "):
            self.assertNotIn(raw, both[0])
        self.assertIn("&quot;A&quot;", both[0])
        self.assertIn("&lt;b&gt;", both[0])


class StubShapeTest(unittest.TestCase):
    """The label rule on synthetic shows, so it does not depend on what plays this week."""

    T = bp.L["fi"]

    @staticmethod
    def show(**kw):
        base = {"title": "Laula minulle Arja", "start": "2026-09-02T16:00:00+03:00",
                "theatre": "Tapio Joensuu", "aud": "Sali Tapio 4", "lang": "FI-S, SV-S",
                "url": "https://www.savonkinot.fi/salikartta?id=1", "venueLabel": "Savon Kinot Tapio",
                "venueProvider": "savonkinot"}
        base.update(kw)
        return base

    def aud_text(self, s, with_venue, lang="fi"):
        html = bp.film_block(s["title"], [s], {}, {}, lang, bp.L[lang], with_venue, set(),
                             current_year=YEAR_NOW)
        m = AUD_RE.search(html)
        return facts_of(split_aud(m.group(1))[0]) if m else None

    def block(self, shows, with_venue, lang="fi"):
        return bp.film_block(shows[0]["title"], shows, {}, {}, lang, bp.L[lang], with_venue, set(),
                             current_year=YEAR_NOW)

    def meta2_text(self, html):
        m = re.search(r'<div class="meta2">(.*?)</div>', html)
        return [text_of(x) for x in re.findall(r"<span>(.*?)</span>", m.group(1))] if m else []

    def stub_texts(self, html):
        return [facts_of(split_aud(a)[0]) for a in AUD_RE.findall(html)]

    def lang_texts(self, html):
        return [split_aud(a)[1] for a in AUD_RE.findall(html)]

    def test_theatre_shape(self):
        s = self.show(lang="EN-A, FI-S, SV-S")
        self.assertEqual(self.aud_text(s, False), "Sali Tapio 4")
        self.assertEqual(self.lang_texts(self.block([s], False)), ["englanti · tekstitys: suomi/ruotsi"])
        self.assertEqual(self.lang_texts(self.block([s], False, "en")),
                         ["English · Finnish/Swedish subtitles"])

    def test_city_shape(self):
        s = self.show(lang="EN-A, FI-S, SV-S", venueLabel="Finnkino Tennispalatsi", aud="Sali 10")
        self.assertEqual(self.aud_text(s, True), "Finnkino Tennispalatsi · Sali 10")
        self.assertIn('<ul class="times grid">', self.block([s], True))
        self.assertIn('<ul class="times">', self.block([s], False))

    def test_a_shared_language_is_still_on_each_stub_and_never_on_the_card(self):
        """One place for the language on every film (2026-09-23): on the stub, even when
        every screening agrees, so a card never says it and the stubs say it too."""
        shows = [self.show(start="2026-09-02T16:00:00+03:00", aud="Sali Tapio 4"),
                 self.show(start="2026-09-02T19:00:00+03:00", aud="Sali Tapio 1")]
        html = self.block(shows, False)
        self.assertEqual(self.lang_texts(html), ["tekstitys: suomi/ruotsi"] * 2)
        self.assertEqual(self.stub_texts(html), ["Sali Tapio 4", "Sali Tapio 1"])
        self.assertFalse(any("tekstitys" in m for m in self.meta2_text(html)))

    def test_a_differing_language_stays_on_its_screening(self):
        """Never the first screening's language for all of them: a dubbed 16:00 and a
        subtitled 19:00 each say their own, and the card says neither."""
        shows = [self.show(start="2026-09-02T16:00:00+03:00", aud="Sali Tapio 4", lang="FI-A"),
                 self.show(start="2026-09-02T19:00:00+03:00", aud="Sali Tapio 1", lang="EN-A, FI-S, SV-S")]
        html = self.block(shows, False)
        self.assertEqual(self.stub_texts(html), ["Sali Tapio 4", "Sali Tapio 1"])
        self.assertEqual(self.lang_texts(html), ["suomi", "englanti · tekstitys: suomi/ruotsi"])
        self.assertFalse(any("tekstitys" in m or m == "suomi" for m in self.meta2_text(html)))

    def test_a_screening_with_no_language_has_no_language_line(self):
        shows = [self.show(lang=""), self.show(lang="FI-A", start="2026-09-02T19:00:00+03:00")]
        html = self.block(shows, False)
        self.assertEqual(self.lang_texts(html), ["", "suomi"])
        self.assertEqual(html.count('class="slang"'), 1)

    # -- price: the screening's, never the film's (2026-09-02) ----------------------------

    @staticmethod
    def stubs_of(html):
        return re.findall(r"<li>(.*?)</li>", html, re.S)

    def stub_prices(self, html):
        """One entry per stub: the price compartment's text, or None when it is blank.
        The compartment itself is always there (2026-09-02): it is part of the ticket."""
        out = []
        for li in self.stubs_of(html):
            m = re.search(r'<span class="price">(.*?)</span>', li)
            out.append(text_of(m.group(1)) or None if m else None)
        return out

    @staticmethod
    def card_text(html):
        m = re.search(r"<h3>.*?<ul class=", html, re.S)
        return text_of(m.group(0)) if m else ""

    def tampere(self):
        """The committed Autofiktio / Tampere case of 2026-09-02, field for field: Cinema
        Niagara 16:15 at 11€, Finnkino Plevna 17:30 and 20:15 with no published price."""
        base = dict(title="Autofiktio", lang="ES-A, FI-S, SV-S", rating="K-12", len="112",
                    genres="Draama, Komedia", gids=[18, 35], img="", tmdb=6.3, votes=123)
        return [dict(base, start="2026-09-02T16:15:00+03:00", price="11\u20ac", aud="",
                     venueLabel="Cinema Niagara", venueProvider="niagara",
                     url="https://cinemaniagara.fi/salikartta?id=54280"),
                dict(base, start="2026-09-02T17:30:00+03:00", price=None, aud="Sali 7",
                     venueLabel="Finnkino Plevna", venueProvider="finnkino",
                     url="https://www.finnkino.fi/websales/show/302341/"),
                dict(base, start="2026-09-02T20:15:00+03:00", price=None, aud="Sali 7",
                     venueLabel="Finnkino Plevna", venueProvider="finnkino",
                     url="https://www.finnkino.fi/websales/show/302342/")]

    def test_one_priced_screening_among_unpriced_ones_prices_only_itself(self):
        """The defect. price_label over the three skipped the unpriced two and put 11€ on
        the card as if Finnkino charged it."""
        html = self.block(self.tampere(), True)
        self.assertEqual(self.stub_prices(html), ["11\u00a0\u20ac", None, None])
        self.assertNotIn("\u20ac", self.card_text(html))
        self.assertEqual(html.count("11\u00a0\u20ac"), 1)
        niagara = next(li for li in self.stubs_of(html) if "Cinema Niagara" in li)
        self.assertIn('<span class="price">11\u00a0\u20ac</span>', niagara)

    def test_different_prices_stay_with_their_screenings(self):
        shows = [self.show(start="2026-09-02T16:00:00+03:00", price="13\u20ac"),
                 self.show(start="2026-09-02T19:00:00+03:00", price="10\u20ac", aud="Sali Tapio 1")]
        html = self.block(shows, False)
        self.assertEqual(self.stub_prices(html), ["13\u00a0\u20ac", "10\u00a0\u20ac"])
        self.assertNotIn("\u20ac", self.card_text(html))
        self.assertNotIn("alkaen", html)

    def test_the_same_price_everywhere_is_still_each_screenings_own(self):
        shows = [self.show(start=f"2026-09-02T{h}:00:00+03:00", price="13\u20ac", aud=f"Sali {h}")
                 for h in ("14", "17", "20")]
        html = self.block(shows, False)
        self.assertEqual(self.stub_prices(html), ["13\u00a0\u20ac"] * 3)
        self.assertNotIn("\u20ac", self.card_text(html))

    def test_no_prices_means_blank_compartments_and_no_value(self):
        """The compartment stays so the ticket keeps its silhouette; nothing is printed in
        it -- no euro, no dash, no zero, no word."""
        shows = [self.show(start="2026-09-02T16:00:00+03:00", price=None),
                 self.show(start="2026-09-02T19:00:00+03:00", price="", aud="Sali Tapio 1")]
        html = self.block(shows, False)
        self.assertNotIn("\u20ac", html)
        for li in self.stubs_of(html):
            self.assertTrue(li.endswith('<span class="price"></span></a>'), li)
            self.assertEqual(li.count('class="price"'), 1)
        self.assertEqual(self.stub_prices(html), [None, None])

    def test_a_providers_own_floor_survives_on_its_stub(self):
        s = self.show(price="alkaen 10\u20ac")
        self.assertEqual(self.stub_prices(self.block([s], False)), ["alkaen 10\u00a0\u20ac"])
        self.assertEqual(self.stub_prices(self.block([s], False, "en")), ["from 10\u20ac"])
        self.assertNotIn("\u20ac", self.card_text(self.block([s], False)))

    def test_city_and_theatre_pages_both_attach_the_price_to_the_right_stub(self):
        for with_venue in (True, False):
            with self.subTest(with_venue=with_venue):
                html = self.block(self.tampere(), with_venue)
                lis = self.stubs_of(html)
                self.assertEqual(self.stub_prices(html), ["11\u00a0\u20ac", None, None])
                self.assertIn("16:15", lis[0])
                self.assertNotIn("\u20ac", self.card_text(html))

    def test_a_hostile_price_string_cannot_reach_the_page(self):
        """price_label rebuilds the label from the number it finds, so markup in a
        provider's price string never survives it; the leftover letters make it a floor.
        The element is escaped on top of that, asserted at the source."""
        s = self.show(price="13\u20ac<b>x</b>")
        html = self.block([s], False)
        self.assertNotIn("<b>", html)
        self.assertEqual(self.stub_prices(html), ["alkaen 13\u00a0\u20ac"])
        src = (ROOT / "scripts" / "build_pages.py").read_text(encoding="utf-8")
        self.assertIn('<span class="price">{esc(own_price)}</span>', src)

    def test_venue_room_and_links_are_what_they_were(self):
        html = self.block(self.tampere(), True)
        self.assertEqual(re.findall(r'href="([^"]+)"', html),
                         ["https://cinemaniagara.fi/salikartta?id=54280",
                          "https://www.finnkino.fi/websales/show/302341/",
                          "https://www.finnkino.fi/websales/show/302342/"])
        self.assertEqual(self.stub_texts(html),
                         ["Cinema Niagara", "Finnkino Plevna · Sali 7", "Finnkino Plevna · Sali 7"])
        self.assertIn('class="stub chain-niagara"', html)
        self.assertIn('class="stub chain-finnkino"', html)
        self.assertNotIn("sold", html.lower())

    def test_film_facts_fold_first_non_empty_not_first(self):
        shows = [self.show(start="2026-09-02T16:00:00+03:00", rating="", tmdb=None, votes=None),
                 self.show(start="2026-09-02T19:00:00+03:00", rating="K-12", tmdb=7.1, votes=41)]
        html = self.block(shows, False)
        self.assertIn('<span class="rating">K-12</span>', html)
        self.assertIn('aria-label="TMDB-arvio 7,1/10, 41 ääntä"', html)

    def test_the_score_is_the_apps_ring_with_an_accessible_label(self):
        html = self.block([self.show(tmdb=7.1, votes=41)], False)
        self.assertIn('<span class="ring" role="img" style="--v:71" title="TMDB-arvio 7,1/10, 41 ääntä" '
                      'aria-label="TMDB-arvio 7,1/10, 41 ääntä"><b>7.1</b></span><span class="votes">41</span>', html)
        thin = self.block([self.show(tmdb=6.4, votes=12)], False, "en")
        self.assertIn('class="ring thin"', thin)
        self.assertIn("TMDB rating 6.4/10 from 12 votes", thin)
        self.assertIn(">1.2k<", self.block([self.show(tmdb=8.0, votes=1234)], False))
        self.assertNotIn("ring", self.block([self.show(tmdb=None)], False))
        self.assertIn('aria-label="TMDB-arvio 7,1/10"><b>7.1</b></span>', self.block([self.show(tmdb=7.1, votes=None)], False))

    def test_an_empty_room_leaves_no_separator(self):
        shows = [self.show(aud="", lang="FI-A"), self.show(aud="", lang="EN-A", start="2026-09-02T19:00:00+03:00")]
        self.assertEqual(self.stub_texts(self.block(shows, False)), ["", ""])
        self.assertEqual(self.lang_texts(self.block(shows, False)), ["suomi", "englanti"])
        self.assertEqual(self.stub_texts(self.block(shows, True)),
                         ["Savon Kinot Tapio", "Savon Kinot Tapio"])
        self.assertNotIn(" · <span", self.block(shows, True))

    def test_nothing_but_the_time_leaves_no_details_cell(self):
        self.assertIsNone(self.aud_text(self.show(aud="", lang=""), False))

    def test_the_room_is_verbatim_including_leffabuumis_pipe(self):
        s = self.show(aud="KINOLINNA | SALI 1", lang="FI-A", venueLabel="Leffabuumi Kinolinna")
        self.assertEqual(self.aud_text(s, False), "KINOLINNA | SALI 1")
        self.assertEqual(self.aud_text(s, True), "Leffabuumi Kinolinna · KINOLINNA | SALI 1")

    def test_language_words_follow_the_apps_rule(self):
        cases = {
            # role words, and subtitles after the spoken language
            "EN-A, FI-S, SV-S": (["englanti", "tekstitys: suomi/ruotsi"],
                                 ["English", "Finnish/Swedish subtitles"]),
            # a dubbed film: spoken language only
            "FI-A": (["suomi"], ["Finnish"]),
            # subtitles only
            "FI-S, SV-S": (["tekstitys: suomi/ruotsi"], ["Finnish/Swedish subtitles"]),
            # duplicates collapse, source order kept
            "FI-A, FI-S, SV-S, FI-S": (["suomi", "tekstitys: suomi/ruotsi"],
                                      ["Finnish", "Finnish/Swedish subtitles"]),
            # a compound tag is two languages
            "FI-S, FI-SV-A, SV-S": (["suomi/ruotsi", "tekstitys: suomi/ruotsi"],
                                    ["Finnish/Swedish", "Finnish/Swedish subtitles"]),
            # LT is in LN, so it renders as a word like any other code. The TU and MA
            # cases that stood here went with CODE_ALIAS on 2026-09-15 and are now the
            # unmapped case below; the two XX ones went with NO_SUBTITLES, which was a
            # rule of its own, so that case carries the S role now.
            "LT-A, FI-S": (["liettua", "tekstitys: suomi"], ["Lithuanian", "Finnish subtitles"]),
            # a code nobody has mapped stays visible rather than vanishing, in either
            # role. Nothing suppresses a subtitle code any more, so the S half has to
            # be pinned here: it is what the deleted XX cases used to hold.
            "ZZ-A, YY-S": (["ZZ", "tekstitys: YY"], ["ZZ", "YY subtitles"]),
            "": ([], []),
        }
        for codes, (fi, en) in cases.items():
            with self.subTest(codes=codes):
                self.assertEqual(bp.lang_parts(codes, "fi"), fi)
                self.assertEqual(bp.lang_parts(codes, "en"), en)

    def test_the_time_is_the_clock_and_the_stub_is_a_link_when_there_is_a_url(self):
        html = bp.film_block("x", [self.show()], {}, {}, "fi", self.T, False, set(),
                             current_year=YEAR_NOW)
        self.assertIn('<span class="time">16:00</span>', html)
        self.assertIn('<a class="stub" href="https://www.savonkinot.fi/salikartta?id=1" rel="nofollow noopener">', html)
        html = bp.film_block("x", [self.show(url="")], {}, {}, "fi", self.T, False, set(),
                             current_year=YEAR_NOW)
        self.assertIn('<span class="stub">', html)
        self.assertNotIn("<a class=\"stub", html)

    def test_the_order_shows_arrive_in_does_not_change_the_page(self):
        shows = [self.show(start=f"2026-09-02T{h:02d}:00:00+03:00", aud=f"Sali Tapio {i%4+1}",
                           title=("A" if i % 2 else "B")) for i, h in enumerate(range(10, 22))]
        today = date(2026, 9, 2)
        def render(order):
            days = bp.group_by_day(order, today)
            seen = set()
            return "".join(bp.film_block(t_, sh, {}, {}, "fi", self.T, False, seen,
                                          current_year=YEAR_NOW)
                           for iso in sorted(days)
                           for t_, sh in sorted(days[iso].items(),
                                                key=lambda kv: (kv[1][0]["start"], kv[0])))
        ref = render(list(shows))
        rnd = random.Random(7)
        for _ in range(5):
            order = list(shows); rnd.shuffle(order)
            self.assertEqual(render(order), ref)


class SnippetTest(GeneratedPagesTest):
    """What a search engine may quote from a landing page (2026-09-13).

    Google's sitelinks for the theatre pages all opened with the intro sentence and the
    CTA, the same words on 84 pages, and one film after them. The boilerplate carries
    `data-nosnippet`: the header bar, the intro, the CTA and the footer. The heading, the
    subline, the day headings, the films and the showtimes stay quotable. Google honours
    the attribute on div, span and section only, as a boolean.
    """

    @staticmethod
    def split(text):
        """-> (quotable text, [(tag, attrs) of every marked element])."""
        from html.parser import HTMLParser

        class P(HTMLParser):
            def __init__(self):
                super().__init__()
                self.depth, self.out, self.marked = 0, [], []
                self.skip = 0

            def handle_starttag(self, tag, attrs):
                a = dict(attrs)
                if tag in ("script", "style"):
                    self.skip += 1
                if "data-nosnippet" in a:
                    self.marked.append((tag, a))
                    self.depth += 1
                elif self.depth:
                    self.depth += 1

            def handle_endtag(self, tag):
                if tag in ("script", "style"):
                    self.skip -= 1
                if self.depth:
                    self.depth -= 1

            def handle_data(self, data):
                if not self.depth and not self.skip:
                    self.out.append(data)

        p = P()
        p.feed(text)
        return re.sub(r"\s+", " ", "".join(p.out)), p.marked

    def test_the_boilerplate_is_excluded_and_the_schedule_is_not(self):
        for k, text in self.canonical.items():
            quotable, marked = self.split(text)
            lang = "en" if k.startswith("/en/") else "fi"
            t = bp.L[lang]
            for tag, a in marked:
                self.assertIn(tag, ("div", "span", "section"), (k, tag))
                self.assertIsNone(a["data-nosnippet"], (k, tag))
            self.assertNotIn(t["cta"], quotable, k)
            self.assertNotIn(t["sources"][:30], quotable, k)
            self.assertNotIn("Leffavuoro.", quotable, k)          # the wordmark
            intro = re.search(r'<p class="intro">(.*?)</p>', text, re.S).group(1)
            self.assertNotIn(text_of(intro)[:30], quotable, k)
            # `quotable` comes from HTMLParser.handle_data, which resolves entities,
            # while `text_of` only strips tags. So the h1 is unescaped before the
            # comparison, exactly as the film headings below already are. Without it the
            # first venue whose name carries an `&` fails: Julia 1&2 published on
            # 2026-09-15 and its h1 is `Julia 1&amp;2 Julia -- näytösajat` in the markup
            # against `Julia 1&2 Julia -- näytösajat` in the text. The page is right and
            # the comparison was not.
            h1 = html.unescape(text_of(re.search(r"<h1>(.*?)</h1>", text, re.S).group(1)))
            self.assertIn(h1, quotable, k)
            for day in re.findall(r'<h2 class="day">(.*?)</h2>', text, re.S):
                self.assertIn(text_of(day), quotable, k)
            for film in re.findall(r"<h3>(.*?)</h3>", text, re.S)[:3]:
                self.assertIn(html.unescape(text_of(film)), quotable, k)
            for stub in STUB_RE.findall(text)[:3]:
                self.assertIn(re.search(r"\d\d[:.]\d\d", text_of(stub)).group(0), quotable, k)

    def test_the_meta_description_stays(self):
        for k, text in self.canonical.items():
            m = re.search(r'<meta name="description" content="([^"]+)">', text)
            self.assertTrue(m and m.group(1).strip(), k)


class ShowCacheTest(unittest.TestCase):
    """`load_shows` reads each area file once, and never serves a stale one."""

    def setUp(self):
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_pages
        self.B = build_pages
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)
        saved = build_pages.DATA
        build_pages.DATA = self.dir
        self.addCleanup(lambda: setattr(build_pages, "DATA", saved))
        build_pages._SHOWS.clear()

    def write(self, title, generated="2026-09-17"):
        (self.dir / "area-zz.json").write_text(json.dumps({
            "generated": generated,
            "shows": [{"eventId": "1", "title": title, "start": "2026-09-17T18:00:00+03:00"}],
        }))

    def test_the_second_read_of_one_file_does_not_touch_the_disk(self):
        self.write("First")
        reads = []
        real = pathlib.Path.read_text
        pathlib.Path.read_text = lambda s, *a, **k: (reads.append(str(s)), real(s, *a, **k))[1]
        self.addCleanup(lambda: setattr(pathlib.Path, "read_text", real))
        a = self.B.load_shows("zz")
        b = self.B.load_shows("zz")
        self.assertEqual(a, b)
        self.assertEqual(len(reads), 1, "the file was parsed twice")

    def test_a_file_rewritten_between_builds_is_read_again(self):
        """The error this prevents: a cache keyed on the venue id handing a later build
        the earlier one's schedule. The tests rebuild from data they rewrite, and so does
        a regeneration after a run."""
        self.write("First")
        self.assertEqual(self.B.load_shows("zz")[0]["title"], "First")
        self.write("Second", generated="2026-09-18")
        os.utime(self.dir / "area-zz.json", ns=(10 ** 18, 10 ** 18))
        self.assertEqual(self.B.load_shows("zz")[0]["title"], "Second")

    def test_a_missing_file_is_no_shows_and_is_not_cached_as_one(self):
        self.assertEqual(self.B.load_shows("nope"), [])
        self.write("Late")
        self.assertEqual(self.B.load_shows("nope"), [])
        self.assertEqual(self.B.load_shows("zz")[0]["title"], "Late")


class StaleEmptyPageTest(unittest.TestCase):
    """An empty page says nothing is published only while the run behind it is recent.

    On 2026-10-10 Navettakino's pages said no showtimes were published while its run had
    failed for four days and the cinema's own page listed three. Built here from the
    committed data with two venues and two cities emptied: in each pair one provider file
    is dated two days before the build day and the other on the build day."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(cls.tmp.name)
        data = root / "data"
        data.mkdir()
        for p in REAL_DATA.glob("*.json"):
            shutil.copy2(p, data / p.name)
        cls.today = today = bp.recorded_date()
        cls.saved = (bp.ROOT, bp.DATA)
        bp.ROOT, bp.DATA = root, data
        try:
            chains = {p["id"]: p.get("label", p["id"]) for p in
                      json.loads((data / "providers.json").read_text())["providers"]}
            venues, seen = [], set()
            for v in bp.load_venues():
                v["city"], v["label"] = bp.city_of(v), bp.label_of(v, chains)
                v["slug"] = bp.slug(f"{v['label']} {v['city']}")
                if v["slug"] in seen:
                    v["slug"] = f"{v['slug']}-{bp.slug(v['id'])}"
                seen.add(v["slug"])
                venues.append(v)
            by_prov, by_city = {}, {}
            for v in venues:
                by_prov.setdefault(v["provider"], []).append(v)
                by_city.setdefault(v["city"], []).append(v)
            multi = {c: vs for c, vs in by_city.items() if len(vs) > 1}
            single = sorted(p for p, vs in by_prov.items()
                            if p != "finnkino" and len(vs) == 1 and vs[0]["city"] not in multi)
            cls.v_old, cls.v_new = by_prov[single[0]][0], by_prov[single[1]][0]
            used, cities = set(single[:2]), []
            for c in sorted(multi):
                provs = {v["provider"] for v in multi[c]}
                if "finnkino" in provs or provs & used:
                    continue
                cities.append(c)
                used |= provs
                if len(cities) == 2:
                    break
            cls.c_old, cls.c_new = cities
            old = datetime.combine(today - timedelta(days=2), time(12), tzinfo=bp.FI)
            new = datetime.combine(today, time(6), tzinfo=bp.FI)

            def stamp(prov, when):
                f = data / f"venues-{prov}.json"
                d = json.loads(f.read_text())
                d["generated"] = when.isoformat()
                f.write_text(json.dumps(d))

            def empty(vid):
                f = data / f"area-{vid}.json"
                d = json.loads(f.read_text()) if f.exists() else {}
                d["shows"] = []
                f.write_text(json.dumps(d))

            stamp(cls.v_old["provider"], old)
            stamp(cls.v_new["provider"], new)
            for c in cities:
                for v in multi[c]:
                    empty(v["id"])
            for v in (cls.v_old, cls.v_new):
                empty(v["id"])
            provs_old = sorted({v["provider"] for v in multi[cls.c_old]})
            stamp(provs_old[0], old)
            for p in provs_old[1:] + sorted({v["provider"] for v in multi[cls.c_new]}):
                stamp(p, new)
            bp._unmirrored_hosts.clear()
            with contextlib.redirect_stdout(io.StringIO()):
                bp.main(today=today)
            cls.root = root
        except BaseException:
            bp.ROOT, bp.DATA = cls.saved
            cls.tmp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        bp.ROOT, bp.DATA = cls.saved
        cls.tmp.cleanup()

    def read(self, path):
        return (self.root / path.strip("/") / "index.html").read_text(encoding="utf-8")

    def says(self, path, key, lang):
        """The page's empty line is `key` in `lang`, and the other one is absent."""
        lines = [html.unescape(x) for x in re.findall(
            r'<p class="intro"><span data-nosnippet>([^<]*)</span>', self.read(path))]
        other = "no_shows" if key == "no_shows_unchecked" else "no_shows_unchecked"
        self.assertIn(bp.L[lang][key], lines, path)
        self.assertNotIn(bp.L[lang][other], lines, path)

    def test_a_venue_whose_run_is_old_says_it_could_not_be_checked(self):
        for lang, prefix in (("fi", "teatteri"), ("sv", "sv/teatteri"), ("en", "en/theatre")):
            with self.subTest(lang=lang):
                self.says(f"/{prefix}/{self.v_old['slug']}/", "no_shows_unchecked", lang)
                self.says(f"/{prefix}/{self.v_new['slug']}/", "no_shows", lang)

    def test_a_city_with_one_old_run_says_it_could_not_be_checked(self):
        for lang, prefix in (("fi", "kaupunki"), ("sv", "sv/kaupunki"), ("en", "en/city")):
            with self.subTest(lang=lang):
                self.says(f"/{prefix}/{bp.slug(self.c_old)}/", "no_shows_unchecked", lang)
                self.says(f"/{prefix}/{bp.slug(self.c_new)}/", "no_shows", lang)

    def test_the_day_counts_in_helsinki_and_an_unknown_stamp_is_not_old(self):
        today = date(2026, 10, 10)
        for fetched, want in (("2026-10-09T05:00:00+03:00", False),
                              ("2026-10-08T21:30:00+00:00", False),   # 10-09 00:30 here
                              ("2026-10-08T20:30:00+00:00", True),    # 10-08 23:30 here
                              ("2026-10-06T05:14:35+00:00", True),
                              ("", False), (None, False), ("not a date", False)):
            with self.subTest(fetched=fetched):
                self.assertIs(bp.unchecked(fetched, today), want)


class HomeLinkVenuesTest(unittest.TestCase):
    """main() checks the homepage's city links against the venue list it already holds.

    `sync_home` called `home_cities()` with no argument, so the last step of a build that
    had every venue in memory reloaded them from disk: `data/areas.json` and 55
    `venues-*.json` on 2026-09-17. `--home` still reads them, because it runs on its own
    with nothing loaded.

    No speedup is claimed. The whole build is about 0.19 s and this is a fraction of it.
    The second read is waste, and that is the reason it is gone, the same reason given for
    the area-file cache above.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = pathlib.Path(self.tmp.name)
        (root / "data").mkdir()
        for f in REAL_DATA.glob("*.json"):
            shutil.copy2(f, root / "data" / f.name)
        # Read before ROOT moves: the day the committed data was built for lives in the
        # real sitemap, and the temp root has none until this build writes one.
        self.today = bp.recorded_date()
        saved = (bp.ROOT, bp.DATA)
        bp.ROOT, bp.DATA = root, root / "data"
        self.addCleanup(lambda: setattr(bp, "DATA", saved[1]))
        self.addCleanup(lambda: setattr(bp, "ROOT", saved[0]))
        bp._SHOWS.clear()
        bp._unmirrored_hosts.clear()

    def counted(self):
        """-> the list of calls, with `load_venues` wrapped to append to it."""
        calls = []
        real = bp.load_venues

        def wrapper():
            calls.append(1)
            return real()

        bp.load_venues = wrapper
        self.addCleanup(lambda: setattr(bp, "load_venues", real))
        return calls

    def test_a_whole_build_loads_the_venues_once(self):
        calls = self.counted()
        with contextlib.redirect_stdout(io.StringIO()):
            bp.main(today=self.today)
        self.assertEqual(len(calls), 1,
                         "the venue files were read again for the city-link check")

    def test_home_on_its_own_still_loads_them(self):
        """`--home` is a separate invocation with nothing in memory, so it must read."""
        calls = self.counted()
        bp.sync_home(write=False)
        self.assertEqual(len(calls), 1)

    def test_the_list_main_holds_names_the_same_cities_as_a_fresh_read(self):
        """main() fills `city` on every venue before the check, and `city_of` returns that
        key once it is set, so reading a venue's city a second time gives what the first
        reading wrote. That is what lets main hand its own list over.
        """
        fresh = bp.home_cities(bp.load_venues())
        as_main_sees_it = bp.load_venues()
        for v in as_main_sees_it:
            v["city"] = bp.city_of(v)
        self.assertEqual(bp.home_cities(as_main_sees_it), fresh)
        self.assertTrue(fresh, "the committed data has no multi-venue city to compare")


class ReadmeCountsTest(unittest.TestCase):
    """The three counts README's first paragraph states, measured rather than trusted.

    CLAUDE.md names the city count among the figures that have been wrong before, and it
    was wrong again on 2026-09-16: the opening line said 69 cities and the paragraph about
    the picker still said 62, a number true some days earlier. `advertised()` above pins
    the page and sitemap figures and nothing pinned these, which is why only one of the two
    copies moved.
    """

    README = (ROOT / "README.md").read_text(encoding="utf-8")

    def measured(self):
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        sys.path.insert(0, str(ROOT / "scripts" / "providers"))
        import build_pages
        import registry
        venues = build_pages.load_venues()
        cities = {build_pages.city_of(v) for v in venues}
        return len(registry.PROVIDERS), len(venues), len(cities)

    def test_the_opening_line_counts_the_committed_venues(self):
        providers, venues, cities = self.measured()
        m = re.search(r"Showtimes for (\d+) venues in (\d+) cities across (\d+) providers",
                      self.README)
        self.assertTrue(m, "README's opening sentence changed shape")
        self.assertEqual((int(m.group(1)), int(m.group(2)), int(m.group(3))),
                         (venues, cities, providers))

    def test_the_picker_paragraph_states_the_same_city_count(self):
        """The second copy is the one that went stale. It describes the picker, which
        lists every city with a venue, so it is the same number as the opening line."""
        _, _, cities = self.measured()
        m = re.search(r"the picker switches between\s+its (\d+) cities", self.README)
        self.assertTrue(m, "README's picker sentence changed shape")
        self.assertEqual(int(m.group(1)), cities)

    def adapter_table(self):
        """The rows of README's adapter table, as (label, providers, venues)."""
        body = self.README.split("| Adapter | Providers | Venues | Auth | Runs |")[1]
        body = body.split("\n\n")[0]
        rows = []
        for line in body.strip().split("\n")[1:]:
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.split("|")[1:-1]]
            rows.append((cells[0], int(cells[1]), int(cells[2]), cells[4]))
        return rows

    def test_the_adapter_table_adds_up_to_the_registry(self):
        """Nothing pinned this table, and it drifted: Elävienkuvien teatteri was named in
        the prose from the day it was built and never given a row, so the table stood at
        35 rows and 74 providers against 36 and 75 (found 2026-09-20). The opening line
        was right the whole time, because that one *is* pinned, three tests above."""
        import sys
        sys.path.insert(0, str(ROOT / "scripts" / "providers"))
        import registry
        rows = self.adapter_table()
        providers, venues, _ = self.measured()
        self.assertEqual(sum(r[1] for r in rows), providers,
                         "the Providers column must add up to the registry")
        self.assertEqual(sum(r[2] for r in rows), venues,
                         "the Venues column must add up to the committed venues")
        modules = {(p.get("module") or p.get("id")) for p in registry.PROVIDERS}
        self.assertEqual(len(rows), len(modules),
                         "one row per adapter module, so a new adapter cannot be omitted")

    def test_every_local_adapter_says_so_in_the_runs_column(self):
        """`where="local"` is the routing a reader needs: those cinemas ride on one
        machine. A row that runs partly local names which site."""
        import sys
        sys.path.insert(0, str(ROOT / "scripts" / "providers"))
        import registry
        local = {(p.get("module") or p.get("id")) for p in registry.PROVIDERS
                 if p.get("where") == "local"}
        said = sum(1 for r in self.adapter_table() if "local" in r[3].lower())
        self.assertEqual(said, len(local),
                         f"{len(local)} adapter modules have a local site; "
                         f"{said} rows say so")

    def test_the_region_count_matches_the_registry(self):
        import sys
        sys.path.insert(0, str(ROOT / "scripts" / "providers"))
        import registry
        for m in re.finditer(r"(\d+) regions", self.README):
            with self.subTest(said=m.group(1)):
                self.assertEqual(int(m.group(1)), len(registry.REGIONS))


if __name__ == "__main__":
    unittest.main()
