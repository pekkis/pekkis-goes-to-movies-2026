"""The generated pages' analytics, pageview.js, in a real engine (2026-10-07).

Every page is loaded under https://leffavuoro.fi with each request answered from this
checkout by `page.route`, because pageview.js does nothing on any other origin. PostHog's
two hosts are recorded. Where the loader is meant to run, the bundle is answered with a
stand-in that records the init options and the capture, and runs the page's own
`before_send` over the event with the real URL, a planted query, the title and a referrer
attached, the way posthog-js attaches them. pageview.js is served with its integrity hash
swapped for the stand-in's and nothing else changed; the real bundle on the wire was
checked once by hand, recorded in docs/archive/2026-09-app.md.

No sleeps decide anything: the stand-in's capture is awaited, and the "nothing was
requested" cases wait for the load event, which the loader waits for before it asks for
the bundle, and then for the network to go idle.
"""
import base64
import hashlib
import mimetypes
import os
import pathlib
import re
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
ORIGIN = "https://leffavuoro.fi"
PINNED = "sha384-BmbtQMM1P8wo232drqi6RUQiNd0ZFk56bltD3yk2/94kez4jFURztoW+DlYzT2Ah"
STAND_IN = b"""
window.__ph = { inits: [], captures: [], sent: [] };
window.posthog = {
  init: function(key, cfg){
    window.__ph.inits.push({ key: key, cookieless: cfg.cookieless_mode,
      autocapture: cfg.autocapture, pageview: cfg.capture_pageview,
      scrub: typeof cfg.before_send });
    this.cfg = cfg;
  },
  capture: function(name, props){
    window.__ph.captures.push([name, props]);
    var p = Object.assign({}, props, { $current_url: location.href,
      $pathname: location.pathname, title: document.title, $referrer: document.referrer,
      token: 'phc_test', distinct_id: '$posthog_cookieless' });
    var out = this.cfg.before_send({ event: name, properties: p });
    window.__ph.sent.push(out ? out.properties : null);
  }
};
"""
STAND_IN_SRI = "sha384-" + base64.b64encode(hashlib.sha384(STAND_IN).digest()).decode()
DNT_ON = ("Object.defineProperty(Navigator.prototype, 'doNotTrack', "
          "{get: () => '1', configurable: true});")
GPC_ON = ("Object.defineProperty(Navigator.prototype, 'globalPrivacyControl', "
          "{get: () => true, configurable: true});")
PLANT = "?q=Carrie&utm_source=planted"


def pages():
    """Helsinki's city page and the first theatre page, in all three languages, read off
    the Finnish pages' own hreflang links so a renamed path cannot go stale here."""
    out = []
    theatre = next(d for d in sorted((ROOT / "teatteri").iterdir())
                   if 'http-equiv="refresh"' not in (d / "index.html").read_text(encoding="utf-8"))
    for fi, cat in ((ROOT / "kaupunki" / "helsinki" / "index.html", "generated_city"),
                    (theatre / "index.html", "generated_theatre")):
        text = fi.read_text(encoding="utf-8")
        for lang in ("fi", "sv", "en"):
            href = re.search(rf'hreflang="{lang}" href="{ORIGIN}(/[^"]*)"', text).group(1)
            out.append((lang, href, cat))
    return out


class GeneratedPageAnalytics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        engine = os.environ.get("KINO_BROWSER_ENGINE", "chromium")
        channel = os.environ.get("KINO_BROWSER_CHANNEL") if engine == "chromium" else None
        cls.browser = getattr(cls.pw, engine).launch(channel=channel or None, headless=True)
        js = (ROOT / "pageview.js").read_text(encoding="utf-8")
        assert js.count(PINNED) == 1, "the pinned hash moved; this test swaps it by value"
        cls.loader = js.replace(PINNED, STAND_IN_SRI).encode()
        cls.pages = pages()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()

    def context(self, *, init=(), posthog="stand-in", origin=ORIGIN):
        """-> (context, posthog request log). `posthog` is "stand-in", "abort" or "hang"."""
        ctx = self.browser.new_context(service_workers="block", locale="fi-FI",
                                       timezone_id="Europe/Helsinki",
                                       viewport={"width": 375, "height": 812})
        self.addCleanup(ctx.close)
        for script in init:
            ctx.add_init_script(script)
        log, held = [], []
        host = urlsplit(origin).hostname

        def handle(route):
            url = urlsplit(route.request.url)
            if url.hostname and url.hostname.endswith("posthog.com"):
                log.append(route.request.url)
                if posthog == "hang":
                    held.append(route)           # never answered
                    return None
                if posthog == "stand-in" and url.hostname == "eu-assets.i.posthog.com":
                    return route.fulfill(status=200, body=STAND_IN,
                                         content_type="application/javascript",
                                         headers={"access-control-allow-origin": "*"})
                return route.abort()
            if url.hostname != host:
                return route.abort()
            path = url.path.lstrip("/")
            local = ROOT / path
            if not path or path.endswith("/") or local.is_dir():
                local = local / "index.html"
            if path == "pageview.js":
                return route.fulfill(status=200, body=self.loader,
                                     content_type="application/javascript")
            if not local.is_file():
                return route.fulfill(status=404, body="")
            ctype = mimetypes.guess_type(local.name)[0] or "application/octet-stream"
            return route.fulfill(status=200, body=local.read_bytes(), content_type=ctype)

        ctx.route("**/*", handle)
        # Runs before the context closes: a held request is let go, not left pending.
        self.addCleanup(lambda: [r.abort() for r in held])
        return ctx, log

    def settle(self, page):
        page.wait_for_load_state("load")
        page.wait_for_load_state("networkidle")

    # -- one page view per load ------------------------------------------------------

    def test_each_page_sends_one_pageview_with_its_category_only(self):
        for lang, path, cat in self.pages:
            with self.subTest(page=path):
                ctx, log = self.context()
                page = ctx.new_page()
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(ORIGIN + path + PLANT, referer="https://example.com/?q=Carrie")
                page.wait_for_function("window.__ph && window.__ph.sent.length > 0")
                self.settle(page)
                ph = page.evaluate("window.__ph")
                self.assertEqual(len(ph["inits"]), 1)
                self.assertEqual(ph["inits"][0]["cookieless"], "always")
                self.assertIs(ph["inits"][0]["autocapture"], False)
                self.assertIs(ph["inits"][0]["pageview"], False)
                self.assertEqual(ph["inits"][0]["scrub"], "function")
                self.assertEqual(ph["captures"], [["$pageview", {"category": cat}]])
                self.assertEqual(ph["sent"], [{
                    "category": cat, "$current_url": "https://leffavuoro.fi/pages/" + cat,
                    "token": "phc_test", "distinct_id": "$posthog_cookieless"}])
                self.assertEqual([u for u in log if "eu-assets" in u],
                                 ["https://eu-assets.i.posthog.com/static/1.434.2/array.js"])
                self.assertEqual(errors, [])

    def test_a_reload_is_one_more_view_and_never_two(self):
        lang, path, cat = self.pages[0]
        ctx, log = self.context()
        page = ctx.new_page()
        for _ in range(2):
            page.goto(ORIGIN + path)
            page.wait_for_function("window.__ph && window.__ph.sent.length > 0")
            self.settle(page)
            self.assertEqual(page.evaluate("window.__ph.captures.length"), 1)

    # -- where nothing may be requested ----------------------------------------------

    def assert_silent(self, *, init=(), origin=ORIGIN, path=None):
        path = path or self.pages[3][1]
        ctx, log = self.context(init=init, origin=origin)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(origin + path)
        self.settle(page)
        self.assertEqual(log, [], "neither the bundle nor an event may be requested")
        self.assertEqual(page.evaluate("typeof window.posthog"), "undefined")
        self.assertTrue(page.locator("h1").is_visible())
        self.assertEqual(errors, [])

    def test_a_local_server_or_a_preview_requests_nothing(self):
        for origin in ("http://localhost:8000", "http://127.0.0.1:8000",
                       "https://shady-dev.github.io", "https://www.leffavuoro.fi",
                       "http://leffavuoro.fi"):
            with self.subTest(origin=origin):
                self.assert_silent(origin=origin)

    def test_do_not_track_requests_nothing(self):
        self.assert_silent(init=(DNT_ON,))

    def test_global_privacy_control_requests_nothing(self):
        self.assert_silent(init=(GPC_ON,))

    def test_status_and_privacy_pages_request_nothing(self):
        for path in ("/status/", "/tietosuoja/"):
            with self.subTest(page=path):
                ctx, log = self.context()
                page = ctx.new_page()
                page.goto(ORIGIN + path)
                self.settle(page)
                self.assertEqual(log, [])

    # -- a blocked or unanswered PostHog -----------------------------------------------

    def assert_usable(self, page):
        self.assertTrue(page.locator("h1").is_visible())
        before = page.evaluate("document.documentElement.getAttribute('data-theme')")
        page.locator("#themeToggle").click()
        after = page.evaluate("document.documentElement.getAttribute('data-theme')")
        self.assertNotEqual(before, after, "the theme toggle still works")

    def test_a_blocked_posthog_leaves_the_page_usable(self):
        ctx, log = self.context(posthog="abort")
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(ORIGIN + self.pages[3][1])
        self.settle(page)
        self.assertTrue(any("eu-assets" in u for u in log), "the bundle was asked for")
        self.assertEqual(page.evaluate("typeof window.posthog"), "undefined")
        self.assert_usable(page)
        self.assertEqual(errors, [])

    def test_an_unanswered_posthog_does_not_hold_up_the_load_event(self):
        """The bundle is requested only after the load event, so a PostHog that never
        answers cannot delay it. The request has to have been made, or this proves
        nothing."""
        ctx, log = self.context(posthog="hang")
        page = ctx.new_page()
        with page.expect_request(lambda r: "eu-assets.i.posthog.com" in r.url, timeout=15000):
            page.goto(ORIGIN + self.pages[0][1], wait_until="load", timeout=15000)
        nav = page.evaluate("performance.getEntriesByType('navigation')[0].loadEventEnd")
        self.assertGreater(nav, 0, "the load event fired while the bundle was unanswered")
        self.assertEqual(page.evaluate("document.readyState"), "complete")
        self.assertEqual(page.evaluate("typeof window.posthog"), "undefined")
        self.assert_usable(page)


if __name__ == "__main__":
    unittest.main()
