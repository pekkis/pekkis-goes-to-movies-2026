"""The privacy page's events table on a phone and on a desktop, in a real engine.

At 320 to 430 px the table is wider than the screen and scrolls in its own focusable box.
The event names (`language_changed`) were unbreakable and held the first column at 159 px;
since 2026-10-04 each breaks after its underscore on a phone and nowhere else, and stays on
one line on a desktop. Run with KINO_BROWSER_ENGINE=webkit as well as the default.
"""
import functools
import http.server
import os
import pathlib
import threading
import unittest

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


NAMES = """() => [...document.querySelectorAll('.tablewrap tr td:first-child code')].map(c => {
    const tops = [], rg = document.createRange();
    for (const n of c.childNodes) { if (n.nodeType !== 3) continue;
      for (let i = 0; i < n.length; i++) { rg.setStart(n, i); rg.setEnd(n, i + 1);
        const r = rg.getClientRects()[0]; if (r) tops.push([n.data[i], Math.round(r.top)]); } }
    const after = []; for (let i = 1; i < tops.length; i++)
      if (tops[i][1] !== tops[i - 1][1]) after.push(tops[i - 1][0]);
    return {name: c.textContent, after}; })"""


class PrivacyTableTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(Handler, directory=str(ROOT)))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.origin = f"http://127.0.0.1:{cls.srv.server_port}"
        cls.pw = sync_playwright().start()
        engine = os.environ.get("KINO_BROWSER_ENGINE", "chromium")
        channel = os.environ.get("KINO_BROWSER_CHANNEL") if engine == "chromium" else None
        cls.browser = getattr(cls.pw, engine).launch(channel=channel or None, headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.srv.shutdown()

    def open(self, width):
        ctx = self.browser.new_context(viewport={"width": width, "height": 900},
                                       service_workers="block")
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        page.goto(self.origin + "/tietosuoja/")
        page.wait_for_function("document.fonts.ready.then(()=>true)")
        return page

    def test_a_phone_breaks_an_event_name_only_after_its_underscore(self):
        for w in (320, 375, 430):
            names = self.open(w).evaluate(NAMES)
            self.assertGreaterEqual(sum("_" in n["name"] for n in names), 6)
            with self.subTest(width=w):
                self.assertTrue(any(n["after"] for n in names), "no event name wrapped")
                for n in names:
                    self.assertTrue(set(n["after"]) <= {"_"}, n)

    def test_a_desktop_keeps_every_event_name_on_one_line(self):
        for n in self.open(1200).evaluate(NAMES):
            with self.subTest(name=n["name"]):
                self.assertEqual(n["after"], [])

    def test_every_column_is_reached_in_the_focusable_scroller(self):
        """The scroller takes focus, so the arrow keys move it, and scrolled to its end it
        shows the last column whole. The key presses themselves were checked by hand in
        both engines on 2026-10-04: WebKit animates each and drops one sent mid-scroll, so
        a scripted press needs a fixed wait this suite does not use."""
        for w in (320, 375, 430):
            page = self.open(w)
            page.locator(".tablewrap").focus()
            got = page.evaluate("""() => { const w = document.querySelector('.tablewrap');
                const focused = document.activeElement === w;
                w.scrollLeft = w.scrollWidth;
                const b = w.getBoundingClientRect();
                const whole = [...w.querySelectorAll('tr')].every(r => {
                  const c = r.cells[2].getBoundingClientRect();
                  return c.right <= b.right + 1 && c.left >= b.left - 1; });
                return {focused, scrolls: w.scrollWidth > w.clientWidth, whole,
                        page: document.documentElement.scrollWidth > innerWidth}; }""")
            with self.subTest(width=w):
                self.assertEqual(got, {"focused": True, "scrolls": True, "whole": True,
                                       "page": False})

if __name__ == "__main__":
    unittest.main()
