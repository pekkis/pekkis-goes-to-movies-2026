"""The Ajat ticket's width, in a real engine (2026-10-04).

DESIGN.md: every ticket in the Ajat list is 120 px, the time's 62 and the price's 56 plus
the borders, so the titles share one x; a chain tint adds 2. WebKit sized the ticket from
the time's text instead of its 62 px basis, drew it 111.84 px wide and clipped the price's
sign: "14,95 €" lost its "€" on every iPhone (measured 2026-10-04). Chromium drew 120,
so only a run in WebKit shows it, which is why CI runs this file in both engines.

Served data: Orion and Kinopalatsi in Helsinki with a two-decimal price, a whole one and
none, so the city view tints its tickets and Orion alone does not.
"""
import http.server
import json
import os
import threading
import unittest

from playwright.sync_api import expect, sync_playwright

import test_client_browser as base

DAY = "2026-09-14"
FILM = {"original": "", "len": "118", "rating": "K-12", "genres": "Draama", "img": "",
        "lang": "", "method": "", "aud": "", "soldOut": False}


def show(venue, provider, theatre, clock, title, price):
    return {**FILM, "eventId": title.lower(), "title": title, "theatre": theatre,
            "price": price, "start": f"{DAY}T{clock}:00+03:00", "provider": provider,
            "venue": venue, "url": f"https://example.invalid/{venue}/{clock}"}


AREAS = {
    "or-helsinki": [show("or-helsinki", "orion", "Cinema Orion", "18:00", "Kerro kaikille", "14.95€"),
                    show("or-helsinki", "orion", "Cinema Orion", "19:30", "Digger", "9€"),
                    show("or-helsinki", "orion", "Cinema Orion", "21:00", "Rose", "")],
    "1100": [show("1100", "finnkino", "Kinopalatsi", "18:15", "Verityn varjo", "14.95€"),
             show("1100", "finnkino", "Kinopalatsi", "20:45", "Hetki ennen valoa", "")],
}


class Handler(base.Handler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        for vid, shows in AREAS.items():
            if path.endswith(f"/data/area-{vid}.json"):
                body = json.dumps({"generated": "2026-09-14T08:00:00+00:00", "dates": [DAY],
                                   "horizon": DAY, "shows": shows}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
        super().do_GET()


# Per ticket: its width, whether a chain tint is on it, whether anything inside it runs
# past its own box, and where the title beside it starts.
MEASURE = """() => [...document.querySelectorAll('#main .trow')].map(row => {
  const stub = row.querySelector('.stub'), price = stub.querySelector('.price');
  return { w: stub.getBoundingClientRect().width,
           tinted: /\\bchain-/.test(stub.className),
           over: stub.scrollWidth - stub.clientWidth,
           priceOver: price.scrollWidth - price.clientWidth,
           price: price.textContent,
           x: row.querySelector('.tinfo').getBoundingClientRect().left };
})"""


class AjatTicketWidth(unittest.TestCase):
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

    def rows(self, width, area, lang):
        ctx = self.browser.new_context(viewport={"width": width, "height": 900},
                                       timezone_id="Europe/Helsinki", locale="fi-FI",
                                       service_workers="block")
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        page.clock.install(time=base.FIXED)
        page.add_init_script("localStorage.setItem('kino-prefs', JSON.stringify({view:'times'}))")
        page.goto(f"{self.origin}/index.html?area={area}&lang={lang}")
        expect(page.locator("#main .trow .stub").first).to_be_visible()
        return page.evaluate(MEASURE)

    def check(self, rows, tinted):
        self.assertGreaterEqual(len(rows), 3, rows)
        self.assertTrue(any(r["price"] for r in rows) and any(not r["price"] for r in rows))
        for r in rows:
            self.assertEqual(r["tinted"], tinted, r)
            self.assertAlmostEqual(r["w"], 122 if tinted else 120, delta=0.01, msg=r)
            self.assertLessEqual(r["over"], 0, r)
            self.assertLessEqual(r["priceOver"], 0, r)
        self.assertLess(max(r["x"] for r in rows) - min(r["x"] for r in rows), 0.01, rows)

    def test_every_ticket_is_120_px_and_its_price_fits(self):
        for lang in ("fi", "sv", "en"):
            for width in (320, 375, 430, 1280):
                with self.subTest(lang=lang, width=width):
                    self.check(self.rows(width, "city:Helsinki", lang), tinted=True)
            for width in (320, 1280):
                with self.subTest(lang=lang, width=width, venue="or-helsinki"):
                    self.check(self.rows(width, "or-helsinki", lang), tinted=False)

    def test_the_two_decimal_price_is_drawn_whole(self):
        want = {"fi": "14,95 €", "sv": "14.95€", "en": "14.95€"}
        for lang, text in want.items():
            with self.subTest(lang=lang):
                self.assertIn(text, [r["price"] for r in self.rows(375, "city:Helsinki", lang)])


if __name__ == "__main__":
    unittest.main()
