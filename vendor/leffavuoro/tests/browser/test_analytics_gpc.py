"""Global Privacy Control stops the analytics before anything is sent.

`phDNT` counts `navigator.globalPrivacyControl === true` with Do Not Track, and `phInit`
checks it before the PostHog bundle is requested. Analytics starts only on
https://leffavuoro.fi (`phAllowedOrigin`), so a page served from 127.0.0.1 would pass this
without testing it: the page is loaded under the production origin here, with every
request answered from this checkout by `page.route`, and the PostHog hosts recorded and
refused. The control run, with no signal, must request the bundle, or the GPC run
proves nothing.

The wait is the boot order, not a sleep: `phInit()` runs synchronously after the
regions.json request and before `loadProviders()` asks for providers.json, so once that
request is seen and the network is idle, a script request would already have gone out.
"""
import mimetypes
import os
import pathlib
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = pathlib.Path(__file__).resolve().parent / "fixture"
ORIGIN = "https://leffavuoro.fi"
GPC_ON = ("Object.defineProperty(Navigator.prototype, 'globalPrivacyControl', "
          "{get: () => true, configurable: true});")


class AnalyticsUnderGpc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        engine = os.environ.get("KINO_BROWSER_ENGINE", "chromium")
        channel = os.environ.get("KINO_BROWSER_CHANNEL") if engine == "chromium" else None
        cls.browser = getattr(cls.pw, engine).launch(channel=channel or None, headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()

    def boot(self, gpc):
        ctx = self.browser.new_context(service_workers="block", locale="fi-FI",
                                       timezone_id="Europe/Helsinki")
        self.addCleanup(ctx.close)
        if gpc:
            ctx.add_init_script(GPC_ON)
        posthog, seen = [], []

        def handle(route):
            url = urlsplit(route.request.url)
            if url.hostname and url.hostname.endswith("posthog.com"):
                posthog.append(route.request.url)
                return route.abort()
            if url.hostname != "leffavuoro.fi":
                return route.abort()
            path = url.path.lstrip("/") or "index.html"
            seen.append(path)
            local = FIXTURE / path if (FIXTURE / path).is_file() else ROOT / path
            if not local.is_file():
                return route.fulfill(status=404, body="")
            ctype = mimetypes.guess_type(local.name)[0] or "application/octet-stream"
            return route.fulfill(status=200, body=local.read_bytes(), content_type=ctype)

        ctx.route("**/*", handle)
        page = ctx.new_page()
        with page.expect_request(lambda r: r.url.endswith("/data/providers.json")):
            page.goto(ORIGIN + "/index.html")
        page.wait_for_load_state("networkidle")
        self.assertTrue(page.evaluate("location.origin") == ORIGIN)
        self.assertEqual(page.evaluate("navigator.globalPrivacyControl === true"), gpc)
        return posthog

    def test_without_the_signal_the_bundle_is_requested(self):
        posthog = self.boot(gpc=False)
        self.assertTrue(any("eu-assets.i.posthog.com" in u for u in posthog),
                        f"the control run must reach PostHog or the GPC run proves nothing: "
                        f"{posthog}")

    def test_under_gpc_no_request_reaches_posthog(self):
        posthog = self.boot(gpc=True)
        self.assertEqual(posthog, [], "GPC set: neither the bundle nor an event may be sent")


if __name__ == "__main__":
    unittest.main()
