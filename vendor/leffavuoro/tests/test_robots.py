"""robots.txt lets a renderer fetch what the client needs and nothing else under /data/.

Search Console's live test of `/` on 2026-09-13 rendered an empty picker and the
load-failure line, and its resource report listed 14 of 15 requests as blocked by
robots.txt: `Disallow: /data/` covered every JSON the app reads. Googlebot renders the
page before indexing it, so the data files are rendering dependencies, not crawl waste.

The rules are checked with Google's own matching (the robots.txt RFC 9309 semantics
Google documents): a rule is a path prefix, `*` matches any run of characters, `$`
anchors the end, the query string is part of the matched path, the longest matching rule
wins and a tie goes to Allow. Python's urllib.robotparser applies rules in file order,
which is not that, so the matcher lives here. Every URL below is a real file in data/ or
a literal path in index.html or status/index.html, so a renamed file fails the test.
"""
import pathlib
import re
import unittest

import _ctx                                                # noqa: F401

ROOT = _ctx.ROOT
ROBOTS = (ROOT / "robots.txt").read_text(encoding="utf-8")
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
STATUS = (ROOT / "status" / "index.html").read_text(encoding="utf-8")


def rules(text=ROBOTS, agent="*"):
    """(allow, disallow, sitemaps) for one user-agent group."""
    allow, disallow, sitemaps, mine = [], [], [], False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = (x.strip() for x in line.split(":", 1))
        key = key.lower()
        if key == "sitemap":
            sitemaps.append(value)
        elif key == "user-agent":
            mine = value == agent
        elif mine and key == "allow" and value:
            allow.append(value)
        elif mine and key == "disallow" and value:
            disallow.append(value)
    return allow, disallow, sitemaps


def matches(pattern, path):
    rx = "^" + re.escape(pattern).replace(r"\*", ".*")
    if rx.endswith(r"\$"):
        rx = rx[:-2] + "$"
    return re.match(rx, path) is not None


def allowed(path, text=ROBOTS):
    """Google's verdict for a path (with its query string, if any)."""
    allow, disallow, _ = rules(text)
    best_a = max((len(p) for p in allow if matches(p, path)), default=-1)
    best_d = max((len(p) for p in disallow if matches(p, path)), default=-1)
    if best_d < 0:
        return True
    return best_a >= best_d          # longest wins; a tie goes to Allow


# What the client reads. Families are the filename prefixes the pipeline writes; the
# literal files are every static `data/...json` path in the two pages.
CONSUMED = ("providers.json", "regions.json", "areas.json", "films.json",
            "films-extra.json", "tmdb-genres.json")
FAMILIES = ("venues-", "venuelists-", "area-", "posters/")
# Pipeline state nothing public reads. film-lang-: Cinema Orion's per-film language
# cache, written by orion.film_language through prices.enrich (2026-09-23).
INTERNAL = ("tmdb.json", "tmdb-titles.json", "prices-", "film-lang-")


def literal_paths(html):
    return sorted(set(re.findall(r"/?(data/[A-Za-z0-9_.-]+\.json)", html)))


def data_files():
    return sorted(p.name for p in (ROOT / "data").glob("*.json"))


class MatcherTest(unittest.TestCase):
    """The semantics the rest of the file depends on, on a fixed text."""

    TEXT = "User-agent: *\nDisallow: /data/\nAllow: /data/area-\nAllow: /data/x.json\n"

    def test_the_longest_matching_rule_wins(self):
        self.assertTrue(allowed("/data/area-br-tripla.json", self.TEXT))
        self.assertFalse(allowed("/data/other.json", self.TEXT))

    def test_the_query_string_is_part_of_the_path(self):
        self.assertTrue(allowed("/data/x.json?v=3", self.TEXT))
        self.assertFalse(allowed("/data/y.json?v=3", self.TEXT))

    def test_a_tie_goes_to_allow(self):
        self.assertTrue(allowed("/data/", "User-agent: *\nDisallow: /data/\nAllow: /data/\n"))

    def test_a_question_mark_is_a_literal_and_not_a_quantifier(self):
        """Google names two special characters in a path, `*` and a trailing `$`. A `?` is
        an ordinary character, and the query string is part of what a rule is matched
        against, so a rule ending in `?` covers exactly the parameterised forms. Pinned on
        this fixed text rather than on the live file, because it is a property of the
        matcher."""
        text = "User-agent: *\nAllow: /\nDisallow: /a/?\n"
        self.assertTrue(allowed("/a/", text))
        self.assertTrue(allowed("/a/b", text))
        self.assertFalse(allowed("/a/?", text))
        self.assertFalse(allowed("/a/?x=1", text))

    def test_wildcard_and_end_anchor(self):
        text = "User-agent: *\nDisallow: /*.log$\n"
        self.assertFalse(allowed("/run-enrich.log", text))
        self.assertTrue(allowed("/run-enrich.log.txt", text))

    def test_another_agents_group_is_not_ours(self):
        text = "User-agent: other\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
        self.assertTrue(allowed("/data/anything", text))


class StartupTest(unittest.TestCase):

    def test_the_page_and_its_shell_are_allowed(self):
        for path in ("/", "/index.html", "/sw.js", "/manifest.webmanifest",
                     "/fonts/", "/icon-192.png"):
            self.assertTrue(allowed(path), path)

    def test_every_literal_data_path_in_the_app_is_allowed(self):
        paths = literal_paths(INDEX)
        self.assertGreaterEqual(len(paths), 6, paths)
        for p in paths:
            self.assertTrue(allowed("/" + p), p)

    def test_every_literal_data_path_on_the_status_page_is_allowed(self):
        paths = literal_paths(STATUS)
        self.assertTrue(paths)
        for p in paths:
            self.assertTrue(allowed("/" + p), p)

    def test_the_startup_files_are_the_ones_the_app_names(self):
        """The list above is not a guess: each consumed file is fetched by index.html."""
        for name in CONSUMED:
            self.assertIn(f"data/{name}", INDEX, name)
            self.assertTrue(allowed(f"/data/{name}"), name)

    def test_no_fetch_carries_a_cache_buster(self):
        """The rules match request URLs; a `?v=` on a fetch would still be covered by a
        prefix rule, but the app sends none, and this pins that."""
        for html in (INDEX, STATUS):
            self.assertNotRegex(html, r"\.json\?")
        self.assertIn("const r = await fetch(path, { signal: ac.signal });", INDEX)


class DataDirectoryTest(unittest.TestCase):
    """Every committed file under data/ is either consumed and allowed or internal and
    blocked. A new family that is neither fails here and has to be classified."""

    def test_every_venue_list_is_allowed(self):
        venues = [f for f in data_files() if f.startswith("venues-")]
        self.assertGreaterEqual(len(venues), 30, "measured 38 on 2026-09-13")
        for f in venues:
            self.assertTrue(allowed(f"/data/{f}"), f)

    def test_every_area_file_is_allowed_across_providers_and_scopes(self):
        areas = [f for f in data_files() if f.startswith("area-")]
        self.assertGreaterEqual(len(areas), 60, "measured 80 on 2026-09-13")
        for f in areas:
            self.assertTrue(allowed(f"/data/{f}"), f)
        # Finnkino's numeric ids, a chain prefix, a single-site module: three shapes.
        for f in ("area-1151.json", "area-br-tripla.json", "area-regina-helsinki.json"):
            self.assertIn(f, areas)

    def test_areas_json_is_not_the_area_family(self):
        """`/data/area-` is a hyphenated prefix and must not be relied on for areas.json."""
        allow, _, _ = rules()
        self.assertIn("/data/areas.json", allow)
        self.assertFalse(matches("/data/area-", "/data/areas.json"))

    def test_posters_are_allowed(self):
        posters = sorted((ROOT / "data" / "posters").glob("*.jpg"))
        self.assertTrue(posters)
        self.assertTrue(allowed(f"/data/posters/{posters[0].name}"))

    def test_internal_caches_and_logs_stay_blocked(self):
        for f in data_files():
            if f.startswith(INTERNAL):
                self.assertFalse(allowed(f"/data/{f}"), f)
        for name in ("tmdb.json", "tmdb-titles.json", "prices-riviera.json"):
            self.assertIn(name, data_files())
        # The logs moved under /logs/ on 2026-09-15. Asserting the old root URLs here
        # would have passed for ever while the real files became crawlable, since a
        # rule that matches nothing still refuses a path nothing serves.
        for path in ("/logs/", "/logs/run.log", "/logs/run-enrich.log",
                     "/logs/run-nexxo.log", "/logs/run-pages-local.log",
                     "/data/", "/data/unknown.json"):
            self.assertFalse(allowed(path), path)

    def test_every_committed_log_is_blocked_at_the_url_it_is_served_from(self):
        """Reads the tree rather than a list, so a log this test never heard of counts."""
        logs = sorted((_ctx.ROOT / "logs").glob("run*.log"))
        self.assertTrue(logs, "no committed run logs to check")
        for p in logs:
            self.assertFalse(allowed(f"/logs/{p.name}"), p.name)

    def test_every_data_file_is_classified(self):
        for f in data_files():
            consumed = f in CONSUMED or f.startswith(FAMILIES)
            internal = f.startswith(INTERNAL)
            self.assertTrue(consumed != internal, f"{f}: classify it")
            self.assertEqual(allowed(f"/data/{f}"), consumed, f)


class LanguageAndPagesTest(unittest.TestCase):

    def test_language_variants_and_generated_pages_are_allowed(self):
        for path in ("/?area=regina-helsinki&lang=sv", "/?area=city%3AHelsinki",
                     "/en/", "/en/theatre/kino-regina-helsinki/",
                     "/teatteri/kino-regina-helsinki/", "/kaupunki/helsinki/", "/status/"):
            self.assertTrue(allowed(path), path)

    def test_the_sitemap_declaration_is_intact(self):
        _, _, sitemaps = rules()
        self.assertEqual(sitemaps, ["https://leffavuoro.fi/sitemap.xml"])


# The status page's utility URLs. `build_pages.py` footers one per generated page, carrying
# the reader's selection and language; none is in the sitemap and all of them answer with
# the same page. `Disallow: /status/?` stops the crawl of the parameterised forms and
# leaves the bare page alone. See the note in robots.txt for what that does and does not
# buy.
STATUS_ANCHOR_RE = re.compile(r'href="(/status/[^"]*)"')
PAGE_GLOBS = ("teatteri/*/index.html", "en/theatre/*/index.html",
              "kaupunki/*/index.html", "en/city/*/index.html")


def generated_status_anchors():
    """Every /status/ href in the committed generated pages, read from the tree.

    Derived rather than listed: the count moves with every provider added, and a list
    would pin the day it was written instead of the property.
    """
    import html as html_mod
    out = set()
    for pattern in PAGE_GLOBS:
        for page in ROOT.glob(pattern):
            text = page.read_text(encoding="utf-8")
            out.update(html_mod.unescape(h) for h in STATUS_ANCHOR_RE.findall(text))
    return sorted(out)


class StatusQueryTest(unittest.TestCase):
    """`Disallow: /status/?`, added 2026-09-20."""

    def test_the_bare_status_page_stays_crawlable(self):
        """The rule needs a literal `?` where the bare path has nothing, so it does not
        match. The page keeps the directives that make it worth crawling."""
        self.assertTrue(allowed("/status/"))
        self.assertIn('<meta name="robots" content="index,follow">', STATUS)
        self.assertIn('<link rel="canonical" href="https://leffavuoro.fi/status/">', STATUS)

    def test_every_parameter_shape_the_app_can_emit_is_blocked(self):
        """The vocabulary is `area`, `lang` and `report`, in two orders: the footer and
        `statusHref()` write area first, `reportScreening()` writes report first. An
        unknown parameter and an empty query are covered by the same prefix."""
        for path in ("/status/?area=br-vaasa",
                     "/status/?lang=en",
                     "/status/?area=br-vaasa&lang=en",
                     "/status/?lang=en&area=br-vaasa",
                     "/status/?area=regina-helsinki&lang=sv",
                     "/status/?report=Kino%20Regina",
                     "/status/?report=Kino%20Regina&lang=en",
                     "/status/?unknown=1",
                     "/status/?"):
            with self.subTest(path=path):
                self.assertFalse(allowed(path), path)

    def test_an_encoded_value_does_not_bypass_the_rule(self):
        """A regression pin, not a proof about encoding: the rule stops at the `?`, so
        whatever follows is never examined. City areas carry `city:` as `city%3A` and
        Finnish names carry their own escapes."""
        for path in ("/status/?area=city%3AVaasa&lang=fi",
                     "/status/?area=city%3AHyvink%C3%A4%C3%A4&lang=en",
                     "/status/?report=Rakkautta%20ja%20virtahepoja%0AKino%20Virta"):
            with self.subTest(path=path):
                self.assertFalse(allowed(path), path)

    def test_every_generated_parameterised_status_anchor_is_blocked(self):
        """Read off the tree, so a provider added tomorrow is covered without an edit."""
        anchors = generated_status_anchors()
        self.assertGreaterEqual(len(anchors), 200, "measured 294 on 2026-09-20")
        parameterised = [a for a in anchors if "?" in a]
        self.assertEqual(len(parameterised), len(anchors),
                         "a generated footer link with no query would be a template change")
        for a in parameterised:
            self.assertFalse(allowed(a), a)

    def test_the_generator_writes_the_shape_the_rule_covers(self):
        """The committed pages can lag the generator, so the template is pinned too: a
        shape change would otherwise ship escaping URLs with this suite green."""
        pages = (ROOT / "scripts" / "build_pages.py").read_text(encoding="utf-8")
        self.assertIn('<a href="/status/?area=', pages)

    def test_the_report_fragment_is_appended_after_the_query(self):
        """`reportScreening()` navigates to `/status/?...#contact`. A fragment is not sent
        to the server, so what a crawler would fetch is the part before it, and that part
        is what the rule matches. Pinning the order in the source is the half this tree
        controls."""
        self.assertIn("location.href = `/status/?${q}#contact`;", INDEX)
        self.assertFalse(allowed("/status/?report=x&lang=en"))

    def test_the_runtime_link_is_bare_until_something_is_selected(self):
        """`statusHref()` omits the query when no area is chosen and the language is
        Finnish, which is the state a renderer boots into, so the crawlable link on `/`
        is the bare one."""
        self.assertIn("return `/status/${qs ? '?' + qs : ''}`;", INDEX)
        self.assertIn('<div id="statusLink"><a href="/status/">', INDEX)

    def test_the_shapes_left_outside_the_rule_have_no_producer(self):
        """`/status?...` and `/status/index.html?...` are not covered, deliberately: the
        rule is as narrow as the links that exist. That is safe only while nothing writes
        them, so the absence is asserted rather than assumed. If this fails, the rule is
        what has to change, not this test."""
        self.assertTrue(allowed("/status?area=x"))
        self.assertTrue(allowed("/status/index.html?area=x"))
        sources = [INDEX, STATUS, (ROOT / "scripts" / "build_pages.py").read_text(
            encoding="utf-8")]
        sources += [p.read_text(encoding="utf-8")
                    for pattern in PAGE_GLOBS for p in ROOT.glob(pattern)]
        for text in sources:
            self.assertNotIn("status/index.html?", text)
            self.assertNotRegex(text, r'["\'(]/status\?')

    def test_the_other_restrictions_and_the_sitemap_survive(self):
        """The new line sits in the same group as the rest; nothing else moved."""
        allow, disallow, sitemaps = rules()
        self.assertIn("/status/?", disallow)
        self.assertIn("/data/", disallow)
        self.assertIn("/logs/", disallow)
        self.assertIn("/", allow)
        self.assertEqual(sitemaps, ["https://leffavuoro.fi/sitemap.xml"])
        for path in ("/data/tmdb.json", "/logs/run.log"):
            self.assertFalse(allowed(path), path)
        for path in ("/data/providers.json", "/data/posters/x.jpg"):
            self.assertTrue(allowed(path), path)


class CrawlableSurfaceTest(unittest.TestCase):
    """The two invariants that catch the next robots rule as well as this one."""

    def test_every_sitemap_url_is_allowed(self):
        xml = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        locs = re.findall(r"<loc>(.*?)</loc>", xml)
        self.assertGreaterEqual(len(locs), 200, "measured 295 on 2026-09-20")
        for loc in locs:
            path = re.sub(r"^https?://[^/]+", "", loc)
            self.assertTrue(allowed(path), loc)

    def test_no_sitemap_url_is_a_status_url(self):
        xml = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        self.assertNotIn("/status", xml)

    def test_every_url_indexnow_would_submit_is_allowed(self):
        """`indexnow.py` pushes changed pages under its own PAGE_DIRS. Submitting a URL
        this file blocks would be asking Google to fetch what it is told not to."""
        import indexnow
        self.assertTrue(indexnow.PAGE_DIRS)
        seen = 0
        for d in indexnow.PAGE_DIRS:
            for page in ROOT.glob(f"{d}*/index.html"):
                seen += 1
                self.assertTrue(allowed("/" + str(page.relative_to(ROOT).parent) + "/"),
                                str(page))
        self.assertGreaterEqual(seen, 200, "measured 298 on 2026-09-20")


if __name__ == "__main__":
    unittest.main()
