"""The analytics privacy contract, checked against index.html and pageview.js rather than
against intent.

pageview.js is the generated city and theatre pages' one hook (2026-10-07): the app's
scrubber, origin guard, DNT/GPC check, pinned bundle and init options, over a table that
allows only $pageview with `generated_city` or `generated_theatre`. The tests below hold the
two files to the same contract.

`analyticsScrub` is posthog-js `before_send`. An event not keyed in PH_ALLOW is dropped;
a property not listed for it is removed, including the 43 the library attaches.

Measured on the wire 2026-09-20, posthog-js 1.434.2, with a title and query planted in the
capture call. `token` and `distinct_id` are mandatory: strip either and posthog-js builds
no request at all. `distinct_id` in cookieless mode is the constant `$posthog_cookieless`.
Full payload in docs/archive/2026-09-app.md.
"""
import json
import pathlib
import re
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "analytics_harness.js"
INDEX = _ctx.ROOT / "index.html"

# The documented allowlist. A change here without a change to the privacy notice is the
# failure this pairing exists to catch.
ALLOWLIST = {
    "$pageview": ["category"],
    "area_opened": ["kind", "area"],
    "cinema_opened": ["venue"],
    "date_changed": ["offset_days"],
    "language_changed": ["lang"],
    "search_used": [],
    "ticket_opened": ["provider"],
}

# Attached by posthog-js before before_send runs, and observed stripped on the wire.
# $current_url is absent here: $pageview carries a synthetic one, asserted separately.
STRIPPED = ["$pathname", "$host", "$referrer", "$referring_domain",
            "$raw_user_agent", "$browser", "$browser_version", "$browser_language",
            "$os", "$os_version", "$device_type", "$device_id", "$screen_height",
            "$screen_width", "$viewport_height", "$viewport_width", "$timezone",
            "$timezone_offset", "$initial_person_info", "$lib", "$lib_version"]

MANDATORY = ["token", "distinct_id"]

CASES = [
    # name, event, properties in, expected properties out (None = event dropped)
    ("allowed_minimal", "cinema_opened", {"venue": "tahtikino-muhos"},
     {"venue": "tahtikino-muhos"}),
    ("strips_a_title", "cinema_opened", {"venue": "v", "title": "Carrie"}, {"venue": "v"}),
    ("strips_a_query", "search_used", {"q": "carrie", "$current_url": "http://a/?q=carrie"},
     {}),
    ("search_carries_nothing", "search_used", {"whatever": 1}, {}),
    ("area_keeps_two", "area_opened", {"kind": "city", "area": "Espoo", "name": "x"},
     {"kind": "city", "area": "Espoo"}),
    # The scrubber builds $current_url from the validated category: all four views, a
    # hostile URL replaced rather than forwarded, and unknown categories dropped.
    ("pv_home", "$pageview", {"category": "home"},
     {"category": "home", "$current_url": "https://leffavuoro.fi/app/home"}),
    ("pv_venue", "$pageview", {"category": "venue"},
     {"category": "venue", "$current_url": "https://leffavuoro.fi/app/venue"}),
    ("pv_city", "$pageview", {"category": "city"},
     {"category": "city", "$current_url": "https://leffavuoro.fi/app/city"}),
    ("pv_region", "$pageview", {"category": "region"},
     {"category": "region", "$current_url": "https://leffavuoro.fi/app/region"}),
    ("pv_hostile_url_replaced", "$pageview",
     {"category": "city", "$current_url": "https://evil.example/?q=carrie&title=Carrie",
      "$pathname": "/?area=city:Espoo&q=carrie", "$host": "evil.example",
      "$referrer": "https://evil.example/ref"},
     {"category": "city", "$current_url": "https://leffavuoro.fi/app/city"}),
    ("pv_real_location_stripped", "$pageview",
     {"category": "home", "$current_url": "https://leffavuoro.fi/?area=city:Espoo&q=x",
      "$raw_user_agent": "Mozilla/5.0", "$screen_width": 1440, "$device_type": "Desktop",
      "$timezone": "Europe/Helsinki"},
     {"category": "home", "$current_url": "https://leffavuoro.fi/app/home"}),
    ("pv_unknown_category", "$pageview", {"category": "admin"}, None),
    ("pv_missing_category", "$pageview", {}, None),
    ("pv_category_not_a_string", "$pageview", {"category": 1}, None),
    ("date_offset_only", "date_changed", {"offset_days": 3, "date": "2026-09-23"},
     {"offset_days": 3}),
    ("lang_only", "language_changed", {"lang": "sv", "$current_url": "http://a/?q=z"},
     {"lang": "sv"}),
    ("ticket_provider_only", "ticket_opened", {"provider": "finnkino", "url": "http://x/?ref=1"},
     {"provider": "finnkino"}),
    ("empty_value_dropped", "cinema_opened", {"venue": ""}, {}),
    # events that must never be sent
    ("drops_autocapture", "$autocapture", {"$el_text": "Buy"}, None),
    ("drops_exception", "$exception", {}, None),
    ("drops_identify", "$identify", {}, None),
    ("drops_unknown", "something_else", {"a": 1}, None),
]


def allowlist_entries(html):
    """The PH_ALLOW block with comment lines removed, so a comment mentioning a property
    cannot be mistaken for the property being allowed."""
    block = html[html.index("const PH_ALLOW = {"):]
    block = block[:block.index("};")]
    return "\n".join(l for l in block.splitlines() if not l.strip().startswith("//"))


def js_cases():
    return [{"name": n, "event": e, "properties": p} for n, e, p, _ in CASES]


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class ScrubTest(unittest.TestCase):
    """index.html's analyticsScrub(), extracted verbatim."""

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
        for name, event, props, want in CASES:
            with self.subTest(case=name):
                got = self.r[name]
                if want is None:
                    self.assertIsNone(got, "this event must never be sent")
                else:
                    self.assertIsNotNone(got, "this event must be sent")
                    # The mandatory pair rides along and is asserted separately.
                    self.assertEqual({k: v for k, v in got.items()
                                      if k not in MANDATORY}, want)

    def test_the_library_properties_are_all_stripped(self):
        """The 43 posthog-js attaches, represented by the ones that carry a URL, a user
        agent or a screen size. $current_url is the load-bearing one: the search query
        lives in it."""
        probe = {k: "LEAK-" + k for k in STRIPPED}
        probe["venue"] = "v"
        out = self.r["_stripprobe"]
        self.assertEqual(out and {k: v for k, v in out.items() if k not in MANDATORY},
                         {"venue": "v"})
        for k in STRIPPED:
            with self.subTest(prop=k):
                self.assertNotIn(k, out or {})

    def test_the_two_mandatory_properties_survive(self):
        """Measured: with either stripped, posthog-js builds no request and the event is
        lost silently. They are the reason the scrub is an allowlist plus a fixed pair
        rather than an allowlist alone."""
        out = self.r["_mandatory"]
        self.assertIsNotNone(out)
        for k in MANDATORY:
            with self.subTest(prop=k):
                self.assertIn(k, out)

    def test_person_properties_are_removed(self):
        """$set and $set_once build a person profile. person_profiles:'never' already
        makes them no-ops; emptying them means a later config change cannot start
        building one out of whatever a call site passed."""
        self.assertEqual(self.r["_setprobe"], {"set": None, "set_once": None})


# protocol, hostname, allowed. Analytics runs on the production origin only, so a
# preview deploy or a dev server cannot reach the project's data.
ORIGINS = [
    ("prod_https", True), ("prod_http", False),
    ("localhost_http", False), ("localhost_https", False),
    ("loopback_v4", False), ("loopback_v6", False),
    ("file_url", False), ("gh_pages", False), ("gh_preview", False),
    ("www_prefix", False), ("suffix_attack", False), ("prefix_attack", False),
    ("unrelated", False), ("empty_host", False),
]


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class OriginGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], input=json.dumps(js_cases()),
                             capture_output=True, text=True, cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stdout}{out.stderr}")
        cls.r = json.loads(out.stdout)
        cls.html = INDEX.read_text(encoding="utf-8")

    def test_only_the_production_https_origin_is_allowed(self):
        got = self.r["_origins"]
        for name, want in ORIGINS:
            with self.subTest(origin=name):
                self.assertEqual(got[name], want)

    def test_the_bundle_is_not_fetched_off_production(self):
        """The guard runs before the script element is created, so a rejected origin
        makes no request at all, not even for the bundle."""
        init = self.html[self.html.index("function phInit(){"):]
        init = init[:init.index("document.head.appendChild")]
        self.assertIn("if(phDNT() || !phHere()) return;", init)
        self.assertLess(init.index("phHere()"), init.index("createElement"))

    def test_nothing_is_queued_or_captured_off_production(self):
        """Both entry points are gated, so a rejected origin cannot fill the queue that
        a later init would flush."""
        for fn in ("function track(name, props){", "function trackTicket(provider){"):
            with self.subTest(fn=fn):
                body = self.html[self.html.index(fn):]
                body = body[:body.index("\n  }")]
                self.assertIn("phDNT() || !phHere()", body)
                self.assertLess(body.index("phHere()"), body.index("phQueue.push"))

    def test_the_hostname_match_is_exact(self):
        block = self.html[self.html.index("function phAllowedOrigin"):]
        block = block[:block.index("\n  }")]
        self.assertIn("hostname === 'leffavuoro.fi'", block)
        for loose in ("endsWith", "includes", "indexOf", "startsWith", "RegExp", "match("):
            with self.subTest(op=loose):
                self.assertNotIn(loose, block)

    def test_do_not_track_is_still_checked(self):
        self.assertIn("phDNT()", self.html)
        block = self.html[self.html.index("const phDNT"):]
        block = block[:block.index("function phInit")]
        for sig in ("navigator.doNotTrack", "globalPrivacyControl"):
            with self.subTest(signal=sig):
                self.assertIn(sig, block)


class SyntheticUrlTest(unittest.TestCase):
    """$pageview is the one event carrying a URL, and it is built from the category."""

    @classmethod
    def setUpClass(cls):
        cls.html = INDEX.read_text(encoding="utf-8")

    def test_the_scrubber_builds_the_url_and_the_caller_cannot(self):
        """$current_url is not in the allowlist, so it cannot be forwarded; it is
        constructed from the validated category instead."""
        self.assertNotIn("$current_url", allowlist_entries(self.html))
        self.assertIn("out.$current_url = PH_APP_BASE + out.category;", self.html)
        self.assertIn("if(PH_CATEGORIES.indexOf(out.category) === -1) return null;",
                      self.html)

    def test_the_call_site_passes_only_the_category(self):
        self.assertIn("track('$pageview', { category: phCategory() });", self.html)

    def test_the_four_categories_are_the_only_ones(self):
        self.assertIn("const PH_CATEGORIES = ['home', 'venue', 'city', 'region'];",
                      self.html)
        self.assertIn("const PH_APP_BASE = 'https://leffavuoro.fi/app/';", self.html)

    def test_no_real_location_is_read_for_analytics(self):
        block = self.html[self.html.index("/* ---------- analytics ---------- */"):]
        block = block[:block.index("const FI_TZ")]
        for bad in ("location.href", "location.search", "location.pathname",
                    "document.referrer", "document.URL"):
            with self.subTest(source=bad):
                self.assertNotIn(bad, block)

    def test_only_pageview_may_carry_a_url(self):
        self.assertNotIn("$current_url", allowlist_entries(self.html),
                         "no event may forward a URL; $pageview's is constructed")


class VersionPinTest(unittest.TestCase):
    """The bundle is pinned, so a PostHog default change cannot move the measured
    contract underneath it."""

    @classmethod
    def setUpClass(cls):
        cls.html = INDEX.read_text(encoding="utf-8")

    def test_the_version_is_pinned_and_used_in_the_src(self):
        self.assertIn("const PH_VERSION = '1.434.2';", self.html)
        self.assertIn("'/static/' + PH_VERSION + '/array.js'", self.html)

    def test_the_unpinned_path_is_not_used(self):
        self.assertNotIn("'/static/array.js'", self.html)

    def test_the_bundle_is_pinned_by_its_bytes_and_not_only_its_url(self):
        """The version pins the URL. Without integrity, whoever can change what that URL
        returns has script execution here, and analyticsScrub cannot help: before_send
        belongs to the library being replaced. Measured from the 1.434.2 bundle on
        2026-09-22; re-measure in the same commit as any PH_VERSION bump."""
        self.assertIn("sc.integrity = 'sha384-BmbtQMM1P8wo232drqi6RUQiNd0Z"
                      "Fk56bltD3yk2/94kez4jFURztoW+DlYzT2Ah';", self.html)
        # SRI on a cross-origin script is only enforced when the fetch is a CORS one.
        self.assertIn("sc.crossOrigin = 'anonymous';", self.html)
        i, c = self.html.index("sc.integrity ="), self.html.index("sc.crossOrigin =")
        self.assertLess(abs(self.html.count("\n", min(i, c), max(i, c))), 3,
                        "the two sit together on the one script element")


class ConfigTest(unittest.TestCase):
    """The init options, read out of index.html."""

    @classmethod
    def setUpClass(cls):
        cls.html = INDEX.read_text(encoding="utf-8")
        i = cls.html.index("posthog.init(PH_KEY")
        cls.cfg = cls.html[i:cls.html.index("});", i)]

    def test_the_privacy_options(self):
        for frag in ("cookieless_mode: 'always'",
                     "person_profiles: 'never'",
                     "persistence: 'memory'",
                     "disable_persistence: true",
                     "respect_dnt: true",
                     "autocapture: false",
                     "capture_pageview: false",
                     "capture_pageleave: false",
                     "capture_dead_clicks: false",
                     "capture_heatmaps: false",
                     "capture_performance: false",
                     "capture_exceptions: false",
                     "disable_session_recording: true",
                     "disable_surveys: true",
                     "enable_recording_console_log: false",
                     "advanced_disable_decide: true",
                     "advanced_disable_feature_flags: true",
                     "before_send: analyticsScrub"):
            with self.subTest(option=frag):
                self.assertIn(frag, self.cfg)

    def test_the_endpoint_is_the_eu_cloud(self):
        self.assertIn("https://eu.i.posthog.com", self.html)
        self.assertNotIn("us.i.posthog.com", self.html)
        # PostHog's own snippet derives the bundle host from the API host this way.
        self.assertIn(".replace('.i.posthog.com', '-assets.i.posthog.com')", self.html)

    def test_do_not_track_stops_the_request_before_it_is_made(self):
        """respect_dnt is the library's answer; this one is ours, and it means a reader
        with DNT set causes no request to posthog at all, not even the bundle."""
        block = self.html[self.html.index("const phDNT"):]
        block = block[:block.index("function phInit")]
        for sig in ("navigator.doNotTrack", "window.doNotTrack",
                    "navigator.msDoNotTrack", "globalPrivacyControl"):
            with self.subTest(signal=sig):
                self.assertIn(sig, block)
        init = self.html[self.html.index("function phInit()"):]
        self.assertIn("if(phDNT() || !phHere()) return;",
                      init[:init.index("document.head.appendChild")])

    def test_identify_and_the_other_person_calls_are_never_used(self):
        for call in ("posthog.identify(", ".identify(", "posthog.alias(",
                     "setPersonProperties", "createPersonProfile", "opt_in_capturing"):
            with self.subTest(call=call):
                self.assertNotIn(call, self.html)

    def test_no_browser_storage_is_used_for_analytics(self):
        """The app's own two keys stay; nothing analytics-related may be added."""
        keys = set(re.findall(r"(?:localStorage|sessionStorage)\.(?:get|set|remove)Item\('([^']+)'",
                              self.html))
        self.assertTrue(keys <= {"kino-prefs", "kino-theme"}, keys)

    def test_the_allowlist_matches_the_documented_one(self):
        block = allowlist_entries(self.html)
        for event, props in ALLOWLIST.items():
            with self.subTest(event=event):
                self.assertRegex(block, rf"{re.escape(event)}:\s*\[")
        found = set(re.findall(r"^\s{4}(\$?\w+):\s*\[", block, re.M))
        self.assertEqual(found, set(ALLOWLIST), "the allowlist changed; the notice must too")


class DedupTest(unittest.TestCase):
    def test_track_dedupes_on_the_property_signature(self):
        html = INDEX.read_text(encoding="utf-8")
        block = html[html.index("function track(name, props)"):]
        block = block[:block.index("\n  }")]
        self.assertIn("phSeen[name] === sig", block)
        self.assertIn("return;", block)

    def test_the_page_view_fires_once_a_load(self):
        html = INDEX.read_text(encoding="utf-8")
        block = html[html.index("function phPageView()"):]
        block = block[:block.index("\n  }")]
        self.assertIn("if(phBooted) return;", block)
        self.assertIn("phBooted = true;", block)


# ---------------------------------------------------------------- generated pages

PAGEVIEW = _ctx.ROOT / "pageview.js"
PAGE_CATEGORIES = ["generated_city", "generated_theatre"]
PAGE_URL_BASE = "https://leffavuoro.fi/pages/"
# Every generated root and the category its pages send. Redirect pages under them send
# nothing: they forward at once, and the page they forward to counts the view.
PAGE_ROOTS = {"kaupunki": "generated_city", "sv/kaupunki": "generated_city",
              "en/city": "generated_city", "teatteri": "generated_theatre",
              "sv/teatteri": "generated_theatre", "en/theatre": "generated_theatre"}
TAG_RE = re.compile(r'<script src="/pageview\.js" data-category="([a-z_]+)" async></script>')

PAGE_CASES = [
    ("pv_city", "$pageview", {"category": "generated_city"},
     {"category": "generated_city", "$current_url": PAGE_URL_BASE + "generated_city"}),
    ("pv_theatre", "$pageview", {"category": "generated_theatre"},
     {"category": "generated_theatre", "$current_url": PAGE_URL_BASE + "generated_theatre"}),
    # What the library would attach on a real page, planted: the real path and a query,
    # the cinema's name in the title, a referrer. Only the category and the synthetic URL
    # may come out.
    ("pv_planted", "$pageview",
     {"category": "generated_theatre",
      "$current_url": "https://leffavuoro.fi/teatteri/kino-x/?q=Carrie&utm_source=x",
      "$pathname": "/teatteri/kino-x/", "$host": "leffavuoro.fi",
      "title": "Carrie | Kino X, Kitee", "$title": "Kino X",
      "$referrer": "https://example.com/?q=Carrie", "$referring_domain": "example.com",
      "city": "Kitee", "venue": "kino-x", "film": "Carrie"},
     {"category": "generated_theatre", "$current_url": PAGE_URL_BASE + "generated_theatre"}),
    # The app's own categories are not the pages' to send.
    ("pv_app_home", "$pageview", {"category": "home"}, None),
    ("pv_app_city", "$pageview", {"category": "city"}, None),
    ("pv_unknown", "$pageview", {"category": "generated_status"}, None),
    ("pv_missing", "$pageview", {}, None),
    # Every other event, the app's included, is dropped.
    ("cinema", "cinema_opened", {"venue": "v"}, None),
    ("area", "area_opened", {"kind": "city", "area": "Espoo"}, None),
    ("search", "search_used", {}, None),
    ("ticket", "ticket_opened", {"provider": "finnkino"}, None),
    ("date", "date_changed", {"offset_days": 1}, None),
    ("lang", "language_changed", {"lang": "sv"}, None),
    ("autocapture", "$autocapture", {"$el_text": "Osta"}, None),
    ("pageleave", "$pageleave", {}, None),
    ("identify", "$identify", {}, None),
]


def harness(src, cases):
    out = subprocess.run(["node", str(HARNESS), src], input=json.dumps(cases),
                         capture_output=True, text=True, cwd=str(_ctx.ROOT), timeout=60)
    if out.returncode:
        raise AssertionError(f"harness failed on {src}: {out.stdout}{out.stderr}")
    r = json.loads(out.stdout)
    if "error" in r:
        raise AssertionError(f"harness error on {src}: {r['error']}")
    return r


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class PageScrubTest(unittest.TestCase):
    """pageview.js's analyticsScrub(), extracted verbatim and run on the same probes."""

    @classmethod
    def setUpClass(cls):
        cls.r = harness("pageview.js", [{"name": n, "event": e, "properties": p}
                                        for n, e, p, _ in PAGE_CASES])

    def test_every_case(self):
        for name, event, props, want in PAGE_CASES:
            with self.subTest(case=name):
                got = self.r[name]
                if want is None:
                    self.assertIsNone(got, "this event must never be sent from a page")
                else:
                    self.assertEqual({k: v for k, v in got.items() if k not in MANDATORY},
                                     want)

    def test_the_table_is_one_event_with_two_categories(self):
        self.assertEqual(self.r["_allow"], ["$pageview"])
        self.assertEqual(self.r["_categories"], PAGE_CATEGORIES)

    def test_every_library_property_and_the_planted_ones_are_stripped(self):
        out = self.r["_pvstripprobe"]
        self.assertEqual(out, {"category": "generated_city",
                               "$current_url": PAGE_URL_BASE + "generated_city"})
        flat = json.dumps(out)
        for planted in ("LEAK-", "Carrie", "?q=", "kino-x", "example.com", "teatteri"):
            with self.subTest(planted=planted):
                self.assertNotIn(planted, flat)

    def test_the_two_mandatory_properties_survive(self):
        for k in MANDATORY:
            with self.subTest(prop=k):
                self.assertIn(k, self.r["_pvmandatory"] or {})

    def test_person_properties_are_removed(self):
        self.assertEqual(self.r["_setprobe"], {"set": None, "set_once": None})

    def test_only_the_production_https_origin_is_allowed(self):
        for name, want in ORIGINS:
            with self.subTest(origin=name):
                self.assertEqual(self.r["_origins"][name], want)


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class AppPlantedPageviewTest(unittest.TestCase):
    """The app's scrubber on the same planted $pageview probe, so both files are shown to
    replace a real URL with their synthetic one."""

    def test_the_planted_url_title_and_query_do_not_survive(self):
        out = harness("index.html", [])["_pvstripprobe"]
        self.assertEqual(out, {"category": "home",
                               "$current_url": "https://leffavuoro.fi/app/home"})


def between(text, start, end):
    i = text.index(start)
    return text[i:text.index(end, i)]


def init_options(text):
    """The posthog.init option lines, comments dropped, as {name: value}."""
    block = between(text, "posthog.init(PH_KEY", "});")
    opts = {}
    for line in block.splitlines():
        m = re.match(r"\s*(\w+):\s*(.+?),\s*(?://.*)?$", line)
        if m:
            opts[m.group(1)] = m.group(2)
    return opts


class PageContractTest(unittest.TestCase):
    """pageview.js against index.html: the same contract, read out of both files."""

    @classmethod
    def setUpClass(cls):
        cls.app = INDEX.read_text(encoding="utf-8")
        cls.js = PAGEVIEW.read_text(encoding="utf-8")

    def test_the_same_project_host_and_pinned_bundle(self):
        for line in ("const PH_KEY  = 'phc_zTiDPrATqb3MbLoYZ25XKhkNpdR7GsdeofZL6rnd5GzV';",
                     "const PH_HOST = 'https://eu.i.posthog.com';",
                     "const PH_VERSION = '1.434.2';",
                     "sc.integrity = 'sha384-BmbtQMM1P8wo232drqi6RUQiNd0ZFk56bltD3yk2/94kez4"
                     "jFURztoW+DlYzT2Ah';",
                     "sc.crossOrigin = 'anonymous';",
                     "+ '/static/' + PH_VERSION + '/array.js';",
                     ".replace('.i.posthog.com', '-assets.i.posthog.com')"):
            with self.subTest(line=line[:40]):
                self.assertIn(line, self.app)
                self.assertIn(line, self.js)

    def test_the_same_init_options(self):
        app, js = init_options(self.app), init_options(self.js)
        self.assertGreaterEqual(len(app), 18)
        self.assertEqual(js, app)

    def test_the_same_scrubber_body(self):
        """Only the table differs. The function is the app's, so a fix to one that misses
        the other turns this red."""
        fn = lambda t: between(t, "function analyticsScrub(event){", "// --- end analyticsScrub")
        self.assertEqual(fn(self.js).replace("PH_URL_BASE", "PH_APP_BASE"), fn(self.app))

    def test_the_same_origin_guard_and_dnt_check(self):
        guard = lambda t: between(t, "function phAllowedOrigin", "// --- end phAllowedOrigin")
        self.assertEqual(guard(self.js).strip(), guard(self.app).strip())
        dnt = lambda t: " ".join(between(t, "const phDNT", ";\n").split())
        self.assertEqual(dnt(self.js), dnt(self.app))

    def test_every_check_runs_before_the_bundle_is_requested(self):
        """A bad category, another origin, DNT or GPC returns before phInit can exist."""
        js = self.js
        create = js.index("document.createElement('script')")
        for check in ("PH_CATEGORIES.indexOf(category) === -1) return;",
                      "if(phDNT() || !phAllowedOrigin(location.protocol, location.hostname)) "
                      "return;"):
            with self.subTest(check=check[:30]):
                self.assertIn(check, js)
                self.assertLess(js.index(check), js.index("function phInit(){"))
        self.assertLess(js.index("function phInit(){"), create)

    def test_the_bundle_waits_for_the_load_event(self):
        self.assertIn("if(document.readyState === 'complete') phInit();", self.js)
        self.assertIn("else window.addEventListener('load', phInit, { once: true });", self.js)
        self.assertEqual(self.js.count("phInit();"), 1, "called from one place only")

    def test_one_capture_carrying_only_the_category(self):
        self.assertEqual(self.js.count(".capture("), 1)
        self.assertIn("window.posthog.capture('$pageview', { category: category });", self.js)

    def test_nothing_about_the_page_is_read(self):
        for bad in ("location.href", "location.search", "location.pathname", "location.hash",
                    "document.referrer", "document.title", "document.URL", "innerText",
                    "textContent", "querySelector"):
            with self.subTest(source=bad):
                self.assertNotIn(bad, self.js)

    def test_no_storage_and_no_person_calls(self):
        # Code only: the init options carry the app's comment naming the two storages.
        code = "\n".join(l.split("//")[0] for l in self.js.splitlines())
        for bad in ("localStorage", "sessionStorage", "document.cookie", "indexedDB",
                    ".identify(", ".alias(", "setPersonProperties", "opt_in_capturing",
                    "startSessionRecording", "loadToolbar"):
            with self.subTest(call=bad):
                self.assertNotIn(bad, code)


class GeneratedPagesTagTest(unittest.TestCase):
    """Every generated city and theatre page loads pageview.js once, with its own category;
    the redirect pages, /status/ and /tietosuoja/ load nothing that reaches PostHog."""

    def test_every_page_carries_one_tag_with_its_category(self):
        counts = {}
        for root, want in PAGE_ROOTS.items():
            for f in sorted((_ctx.ROOT / root).glob("*/index.html")):
                text = f.read_text(encoding="utf-8")
                tags = TAG_RE.findall(text)
                with self.subTest(page=str(f.relative_to(_ctx.ROOT))):
                    if 'http-equiv="refresh"' in text:
                        self.assertEqual(tags, [], "a redirect page must not count a view")
                    else:
                        self.assertEqual(tags, [want])
                        counts[want] = counts.get(want, 0) + 1
                    self.assertEqual(text.count("pageview.js"), len(tags))
                    self.assertNotIn("posthog", text.lower())
        # Without this the loop passes on an empty checkout.
        self.assertGreater(counts.get("generated_city", 0), 30)
        self.assertGreater(counts.get("generated_theatre", 0), 300)

    def test_the_generator_knows_two_kinds_and_no_other(self):
        import build_pages as bp
        self.assertEqual(bp.PAGEVIEW_KINDS, {"city": "generated_city",
                                             "theatre": "generated_theatre"})
        self.assertEqual(sorted(bp.PAGEVIEW_KINDS.values()), PAGE_CATEGORIES)
        with self.assertRaises(KeyError):
            bp.pageview_tag("status")

    def test_status_and_privacy_pages_load_no_analytics(self):
        for page in ("status/index.html", "tietosuoja/index.html"):
            text = (_ctx.ROOT / page).read_text(encoding="utf-8")
            with self.subTest(page=page):
                self.assertNotIn("pageview.js", text)
                for attrs, body in re.findall(r"<script([^>]*)>(.*?)</script>", text, re.S):
                    self.assertNotIn("posthog", (attrs + body).lower())


if __name__ == "__main__":
    unittest.main()
