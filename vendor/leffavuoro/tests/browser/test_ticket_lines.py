"""A glyph widens a desktop ticket instead of narrowing its text (2026-10-02).

Reported from the live site with a screenshot at desktop width: on a single cinema's list
the Anniskelu A took its width out of the 200 px the ticket's text had, so "englanti ·
tekstitys: suomi/ruotsi" broke onto two lines on the tickets that carry the glyph and
stayed on one beside them. From 700 px the cap is on the text, 172 px, and the glyph adds
its own width. Phones and the combined grid keep their own layout; this file holds both
halves in a real engine. It serves its own Orion file: one film, the same language on
every screening, the Anniskelu tag on two of three.
"""
import http.server
import json
import os
import threading
import unittest

from playwright.sync_api import expect, sync_playwright

import test_client_browser as base

DAY = "2026-09-14"
FILM = {"eventId": "sama-elokuva", "title": "Sama elokuva", "original": "", "len": "118",
        "rating": "K-12", "age": "", "genres": "Draama", "img": "", "price": "",
        "tmdb": 7.1, "votes": 41}


def show(clock, aud, method):
    return {**FILM, "theatre": "Cinema Orion", "aud": aud, "lang": "EN-A, FI-S, SV-S",
            "method": method, "start": f"{DAY}T{clock}:00+03:00", "soldOut": False,
            "provider": "orion", "venue": "or-helsinki",
            "url": f"https://example.invalid/or-helsinki/{clock}"}


SHOWS = [show("13:20", "Sali 1", "2D · Anniskelu"), show("18:00", "Sali 2", "2D"),
         show("20:40", "Sali 3", "2D · Anniskelu")]


class Handler(base.Handler):
    def do_GET(self):
        if self.path.split("?", 1)[0].endswith("/data/area-or-helsinki.json"):
            body = json.dumps({"generated": "2026-09-14T08:00:00+00:00", "dates": [DAY],
                               "horizon": DAY, "shows": SHOWS}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


# Each language-bearing ticket's glyph count, language lines and height, in document
# order. Text boxes whose tops lie within 4 px are one line.
TICKETS = """(scope) => [...document.querySelectorAll(scope + ' .stub')]
  .filter(s => s.querySelector('.slang')).map(s => {
  const sl = s.querySelector('.slang'), r = document.createRange();
  r.selectNodeContents(sl);
  const tops = [...r.getClientRects()].filter(x => x.width > 0.5).map(x => x.top)
    .sort((a, b) => a - b);
  let lines = 0, last = -1e9;
  for (const t of tops) if (t - last > 4) { lines++; last = t; }
  return { glyphs: s.querySelectorAll('.glyphs > *').length, lines,
           h: Math.round(s.getBoundingClientRect().height),
           cap: getComputedStyle(sl).maxWidth };
})"""


class TicketLines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.srv.served, cls.srv.requested = [], []
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.origin = f"http://127.0.0.1:{cls.srv.server_port}"
        cls.pw = sync_playwright().start()
        engine = os.environ.get("KINO_BROWSER_ENGINE", "chromium")
        channel = os.environ.get("KINO_BROWSER_CHANNEL") if engine == "chromium" else None
        cls.browser = getattr(cls.pw, engine).launch(channel=channel or None, headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.srv.shutdown()

    def open(self, width, area):
        ctx = self.browser.new_context(viewport={"width": width, "height": 900},
                                       timezone_id="Europe/Helsinki", locale="fi-FI",
                                       service_workers="block")
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        page.clock.install(time=base.FIXED)
        page.add_init_script("localStorage.setItem('kino-prefs', JSON.stringify({view:'movies'}));"
                             "localStorage.setItem('kino-theme', 'light')")
        page.goto(self.origin + f"/index.html?area={area}")
        expect(page.locator("#main a.stub").first).to_be_visible()
        return page

    def test_a_glyph_does_not_break_the_language_on_a_desktop_ticket(self):
        for width in (700, 1200):
            page = self.open(width, "or-helsinki")
            page.locator("#main h2.title a.tlink").first.click()
            expect(page.locator("#sheet a.stub").first).to_be_visible()
            for scope in ("#main", "#sheet"):
                with self.subTest(width=width, scope=scope):
                    got = page.evaluate(TICKETS, scope)
                    self.assertEqual([t["glyphs"] > 0 for t in got], [True, False, True], got)
                    self.assertEqual({t["lines"] for t in got}, {1}, got)
                    self.assertEqual(len({t["h"] for t in got}), 1, got)

    def test_phones_and_the_combined_grid_keep_their_layout(self):
        """The rule is scoped to 700 px and up and to a single cinema's list."""
        for width, area in ((393, "or-helsinki"), (699, "or-helsinki"), (1200, "city:Helsinki")):
            with self.subTest(width=width, area=area):
                page = self.open(width, area)
                got = page.evaluate(TICKETS, "#main")
                self.assertTrue(got, "no ticket with a language drawn")
                self.assertEqual({t["cap"] for t in got}, {"none"}, got)


if __name__ == "__main__":
    unittest.main()
