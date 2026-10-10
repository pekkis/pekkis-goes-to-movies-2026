"""The stale banner against the service worker's background refresh, in a real engine.

test_client_browser.py blocks the worker; these tests need it, because what they check is
the order in which the worker answers from its cache, refreshes behind, and messages the
page. Each test seeds the worker with a 24-hour-old copy of Orion's schedule, changes what
the server answers, reloads, and watches #stale: whether the warning or the neutral
"checking" state was ever set, and when. A MutationObserver records it, so a state the page
sets and clears within one frame is still seen; a sampling timer missed those.

`city:Helsinki` is the selection: a combined city's members are known only once the venue
lists arrive, but the boot prefetches them from the ids stored in prefs, so the worker's
refresh can land before the slot exists. Whether it does is a race between the refresh and
the page's boot, so a test that needs it drops Orion's venue list from Cache Storage and
delays it on the server: the fill then waits on the network. In the fixture the city is Orion plus Finnkino
members whose files 404, so the banner turns on Orion's file alone, which the handler
below serves with whatever `generated` the test sets.

Timestamps are relative to the real clock: the worker runs outside the page, where
`page.clock` does not reach.
"""
import datetime
import http.server
import json
import os
import threading
import time
import unittest
import zoneinfo

from playwright.sync_api import expect, sync_playwright

import test_client_browser as base

AREA = json.loads((base.FIXTURE / "data/area-or-helsinki.json").read_text(encoding="utf-8"))
URL = "/index.html?area=city:Helsinki"


def hours_ago(h):
    t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=h)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp(iso):
    """The credit line's time for `iso` as fi-FI draws it: "P\u00e4ivitetty 23.9. klo 14.10"."""
    t = datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc).astimezone(zoneinfo.ZoneInfo("Europe/Helsinki"))
    return f"P\u00e4ivitetty {t.day}.{t.month}. klo {t:%H.%M}"


class Handler(base.Handler):
    """base.Handler, with Orion's schedule file answered from `server.cfg`: its
    `generated`, its status and a delay. Nothing may be answered from the browser's HTTP
    cache, so the worker's Cache Storage is the only copy in play."""

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        cfg = self.server.cfg
        if path.endswith("/data/area-or-helsinki.json"):
            self.server.requested.append(path)
            time.sleep(cfg["area_delay"])
            cfg["answered"] = time.monotonic()
            if cfg["area_drop"]:
                # No response at all: the worker's fetch rejects, as it does offline.
                self.close_connection = True
                return
            if cfg["area_status"] != 200:
                self.send_error(cfg["area_status"])
                return
            body = json.dumps({**AREA, "generated": cfg["generated"]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path.endswith("/data/venues-orion.json"):
            time.sleep(cfg["venues_delay"])
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        http.server.SimpleHTTPRequestHandler.end_headers(self)


class UpdateCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.srv.served, cls.srv.requested = [], []
        cls.srv.cfg = {}
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.origin = f"http://127.0.0.1:{cls.srv.server_port}"
        cls.pw = sync_playwright().start()
        engine = os.environ.get("KINO_BROWSER_ENGINE", "chromium")
        channel = os.environ.get("KINO_BROWSER_CHANNEL") if engine == "chromium" else None
        cls.browser = getattr(cls.pw, engine).launch(channel=channel or None, headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.srv.shutdown()

    def setUp(self):
        self.srv.cfg.update(generated=hours_ago(24), area_status=200, area_delay=0,
                            area_drop=False, venues_delay=0)
        self.ctx = self.browser.new_context(timezone_id="Europe/Helsinki", locale="fi-FI",
                                            service_workers="allow")
        self.ctx.tracing.start(screenshots=True, snapshots=True)
        base.OUT.mkdir(exist_ok=True)
        self.page = self.ctx.new_page()
        self.stale = self.page.locator("#stale")
        self.credit = self.page.locator("#credit")
        # First load installs the worker and stores the city's member ids in prefs; the
        # second, controlled, puts the 24-hour-old copy in Cache Storage. The banner is
        # then true on both sides: the server has nothing newer yet.
        self.page.goto(self.origin + URL)
        self.page.wait_for_function("navigator.serviceWorker.controller !== null")
        self.page.reload()
        expect(self.stale).to_contain_text("\u26a0")
        expect(self.credit).to_contain_text(stamp(self.srv.cfg["generated"]))

    def watch(self):
        """From the next navigation on, record whether #stale ever showed the warning or
        the checking state, and when the warning first appeared (ms since navigation)."""
        self.page.add_init_script("""
            window.__seen = { warn: false, checking: false, warnAt: null };
            document.addEventListener('DOMContentLoaded', () => {
              const e = document.getElementById('stale');
              const look = () => {
                if (e.style.display !== 'block') return;
                if (e.classList.contains('checking')) __seen.checking = true;
                else if (e.textContent.includes('\\u26a0')) {
                  if (!__seen.warn) __seen.warnAt = performance.now();
                  __seen.warn = true;
                }
              };
              new MutationObserver(look).observe(e, { attributes: true, childList: true,
                                                      subtree: true, characterData: true });
            });""")

    def seen(self):
        return self.page.evaluate("() => window.__seen")

    def warned_at(self, timeout=10_000):
        """ms since navigation when the sampler first saw the warning."""
        self.page.wait_for_function("() => window.__seen && window.__seen.warn", timeout=timeout)
        return self.seen()["warnAt"]

    def pick(self, query):
        deadline = time.monotonic() + 10
        while True:
            self.page.locator("#areaSelect").click()
            try:
                expect(self.page.locator("#vwrap")).to_have_class("vwrap open", timeout=250)
                break
            except AssertionError:
                if time.monotonic() > deadline:
                    raise
        vq = self.page.locator("#vq")
        vq.fill(query)
        expect(self.page.locator("#vlist .vrow").first).to_be_visible()
        vq.press("Enter")

    def uncache(self, fragment):
        """Drop every Cache Storage entry whose URL contains `fragment`."""
        self.page.evaluate("""async f => {
            for (const k of await caches.keys()) {
                const c = await caches.open(k);
                for (const r of await c.keys()) if (r.url.includes(f)) await c.delete(r);
            }
        }""", fragment)

    def tearDown(self):
        res = getattr(self._outcome, "result", None)
        failed = any(t is self for t, _ in (res.failures + res.errors)) if res else False
        name = base.OUT / self.id().split(".")[-1]
        if failed:
            self.page.screenshot(path=f"{name}.png", full_page=True)
            self.ctx.tracing.stop(path=f"{name}.zip")
        else:
            self.ctx.tracing.stop()
        self.ctx.close()

    def test_a_refresh_that_lands_before_the_city_is_drawn_is_applied(self):
        """The server now has an hour-old copy, and the venue lists take 2 s. The worker's
        refresh lands long before the city's slot exists; the slot is filled with the
        24-hour-old copy the prefetch was handed, and the replay must replace it without
        a reload. Until 2026-09-23 the message was dropped and the warning stayed."""
        self.srv.cfg.update(generated=hours_ago(1), venues_delay=2.0)
        self.uncache("/data/venues-orion.json")
        self.watch()
        self.page.reload()
        # The credit line is the schedule on screen: until it names the new copy, a hidden
        # banner only means nothing has been drawn yet.
        expect(self.credit).to_contain_text(stamp(self.srv.cfg["generated"]), timeout=8_000)
        expect(self.stale).to_be_hidden()
        self.assertFalse(self.seen()["warn"], "the warning flashed before the replay landed")

    def test_a_slow_check_shows_checking_and_never_the_warning(self):
        """The server has an hour-old copy but takes 3 s to answer the worker. The 24-hour
        copy is drawn at once, under the neutral state; the warning never appears."""
        self.srv.cfg.update(generated=hours_ago(1), area_delay=3.0)
        self.watch()
        self.page.reload()
        expect(self.stale).to_have_class("checking")
        expect(self.stale).to_have_text("Tarkistetaan p\u00e4ivityksi\u00e4\u2026")
        expect(self.credit).to_contain_text(stamp(self.srv.cfg["generated"]), timeout=8_000)
        expect(self.stale).to_be_hidden()
        self.assertEqual(self.seen()["warn"], False)

    def test_a_failed_check_shows_the_warning_without_the_wait(self):
        """A 500 behind the cached copy: the worker has nothing newer and says so, so the
        late copy gets its warning at once rather than at the 8 s cap."""
        self.srv.cfg.update(area_status=500)
        self.watch()
        self.page.reload()
        self.assertLess(self.warned_at(), 3000)
        expect(self.credit).to_contain_text(stamp(self.srv.cfg["generated"]))

    def test_a_check_that_cannot_connect_shows_the_warning_without_the_wait(self):
        """Offline, as the worker sees it: its fetch rejects. Modelled by a connection
        closed with no response, because WebKit's reload under `set_offline` fails
        inside the engine ("WebKit encountered an internal error")."""
        self.srv.cfg.update(area_drop=True)
        self.watch()
        self.page.reload()
        self.assertLess(self.warned_at(), 3000)
        expect(self.credit).to_contain_text(stamp(self.srv.cfg["generated"]))

    def test_a_check_that_never_answers_gives_the_warning_at_the_cap(self):
        """The worker's fetch takes 12 s. The page stops waiting at FETCH_MS, 8 s, and says
        what it holds; the late answer then still replaces it."""
        self.srv.cfg.update(generated=hours_ago(1), area_delay=12.0)
        self.watch()
        self.page.reload()
        expect(self.stale).to_have_class("checking")
        at = self.warned_at(timeout=11_000)
        self.assertGreater(at, 7500)
        self.assertLess(at, 11000)
        expect(self.credit).to_contain_text(stamp(self.srv.cfg["generated"]), timeout=8_000)
        expect(self.stale).to_be_hidden()

    def test_switching_cinemas_during_a_check(self):
        """Orion's check is slow; the reader moves to Promenadi Pori, whose file is late on
        the server too and answers at once. Pori gets its own warning, not Orion's pending
        state, and Orion's late answer repaints nothing on Pori. Back on the city, its slot
        already holds the newer copy."""
        self.srv.cfg.update(generated=hours_ago(1), area_delay=6.0, answered=None)
        self.page.reload()
        expect(self.stale).to_have_class("checking")
        self.pick("promenadi")
        # Pori's schedule is drawn; read its banner once, without retrying, while Orion's
        # check is still out. A retrying expect would pass once Orion answered.
        expect(self.credit).to_contain_text(stamp("2026-09-14T17:20:00Z"))
        cls, text = self.stale.get_attribute("class") or "", self.stale.inner_text()
        self.assertIsNone(self.srv.cfg["answered"], "Orion answered before Pori was drawn")
        self.assertNotIn("checking", cls)
        self.assertIn("Finnkino", text)
        self.page.wait_for_timeout(6500)                  # Orion's answer lands here
        expect(self.page.locator("#areaSelect")).to_contain_text("Promenadi")
        expect(self.stale).to_contain_text("Finnkino")
        self.pick("helsinki")
        expect(self.credit).to_contain_text(stamp(self.srv.cfg["generated"]))
        expect(self.stale).to_be_hidden()


if __name__ == "__main__":
    unittest.main()
