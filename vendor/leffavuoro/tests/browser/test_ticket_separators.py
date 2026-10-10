"""The separators between a ticket's facts, in a real engine (2026-09-23).

A ticket's cinema, room, format and the language's two parts are separate elements, and
the separator between two of them is a 3 px CSS square (`.fx`, `.slang .lp`), which
replaced a middle dot. What only a browser can check:

- no visible square opens a line: a fact that wraps takes its square into the clipped
  margin, in the list, the film view and the Ajat meta line, at 320 and 393 px;
- hover and keyboard focus turn the squares and the top, right and bottom edges
  --accent, and the left edge keeps the chain's colour;
- a screen reader hears the facts apart: each fact but the last carries a hidden comma;
- the footer's source, update time and booking line are three spans, and the rating
  ring's label is a phrase in each language;
- none of these views draws a middle dot of the app's own.

The fixture's Orion and Promenadi files carry no rooms or languages, so this file serves
its own Orion and Kinopalatsi (1100, a Helsinki member in the fixture's Finnkino list):
long room names, three-language screenings, format tags and a sold-out screening, which
is what makes the tickets wrap. Everything else comes from tests/browser/fixture.
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


def show(venue, provider, theatre, clock, aud, lang, method, sold=False):
    return {**FILM, "theatre": theatre, "aud": aud, "lang": lang, "method": method,
            "start": f"{DAY}T{clock}:00+03:00", "soldOut": sold, "provider": provider,
            "venue": venue, "url": f"https://example.invalid/{venue}/{clock}"}


AREAS = {
    "or-helsinki": [show("or-helsinki", "orion", "Cinema Orion", "18:00", "Sali 1",
                         "EN-A, FI-S, SV-S", "2D \u00b7 Anniskelu"),
                    show("or-helsinki", "orion", "Cinema Orion", "19:30", "Sali 1",
                         "EN-A, FI-S", "2D", sold=True)],
    "1100": [show("1100", "finnkino", "Kinopalatsi", "18:15", "Sali 10 Dolby Atmos",
                  "ES-A, FI-S, SV-S", "2D \u00b7 Seniorikino"),
             show("1100", "finnkino", "Kinopalatsi", "20:45", "Sali 4", "FI-A", "IMAX")],
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


# Visible squares, and the ones that open a line. A square is the later fact's ::before;
# it is hidden when that fact starts a line, because the fact then sits in the row's
# negative margin, left of the clipping parent's edge.
SQUARES = """(scope) => {
  const root = document.querySelector(scope);
  const R = e => e.getBoundingClientRect();
  const clipOf = e => { let p = e.parentElement;
    while (p && getComputedStyle(p).overflowX === 'visible') p = p.parentElement; return p; };
  let shown = 0, opening = 0;
  for (const row of root.querySelectorAll('.fx:not(.inl), .slang .lp')) {
    if (!row.offsetParent) continue;
    const kids = [...row.children], clip = R(clipOf(row));
    kids.forEach((k, i) => {
      if (!i) return;
      if (R(k).left + 3 < clip.left - 0.5) return;
      shown++;
      const prev = R(kids[i - 1]);
      if (prev.bottom <= R(k).top + 2) opening++;
    });
  }
  return { shown, opening };
}"""


class TicketSeparators(unittest.TestCase):
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

    def open(self, width, view="movies", theme="light"):
        ctx = self.browser.new_context(viewport={"width": width, "height": 900},
                                       timezone_id="Europe/Helsinki", locale="fi-FI",
                                       service_workers="block")
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        page.clock.install(time=base.FIXED)
        page.add_init_script(f"localStorage.setItem('kino-prefs', JSON.stringify({{view:'{view}'}}));"
                             f"localStorage.setItem('kino-theme', '{theme}')")
        page.goto(self.origin + "/index.html?area=city:Helsinki")
        expect(page.locator("#main a.stub").first).to_be_visible()
        return page

    def open_sheet(self, page):
        page.locator("#main h2.title a.tlink").first.click()
        expect(page.locator("#sheet a.stub").first).to_be_visible()

    def test_no_square_opens_a_line(self):
        for width in (320, 393):
            for view in ("movies", "times"):
                with self.subTest(width=width, view=view):
                    page = self.open(width, view)
                    got = page.evaluate(SQUARES, "#main")
                    self.assertGreaterEqual(got["shown"], 3, got)
                    self.assertEqual(got["opening"], 0, got)
                    if view == "movies":
                        self.open_sheet(page)
                        got = page.evaluate(SQUARES, "#sheet")
                        self.assertGreaterEqual(got["shown"], 3, got)
                        self.assertEqual(got["opening"], 0, got)

    def test_the_square_takes_the_width_the_dot_took(self):
        """" \u00b7 " measured 8.66 px at the ticket's .72rem in both engines, so the slot is
        9 px and a ticket wraps where it wrapped before (2026-09-23: every ticket in 80 views
        of the committed data kept its height). Measured between the two facts' text."""
        page = self.open(1200)
        gap = page.locator("#main a.stub", has_text="18:15").evaluate("""e => {
            const [a, b] = e.querySelectorAll('.fx > span');
            const box = n => { const r = document.createRange(); r.selectNodeContents(n.firstChild);
                               return r.getBoundingClientRect(); };
            return box(b).left - box(a).right; }""")
        self.assertAlmostEqual(gap, 9, delta=0.6)

    def test_hover_and_focus_turn_the_squares_and_the_edges_gold(self):
        for theme in ("light", "dark"):
            with self.subTest(theme=theme):
                page = self.open(393, theme=theme)
                probe = """(e) => { const cs = getComputedStyle(e);
                  const sq = e.querySelector('.fx > span + span');
                  return { top: cs.borderTopColor, right: cs.borderRightColor,
                           bottom: cs.borderBottomColor, left: cs.borderLeftColor,
                           seam: getComputedStyle(e.querySelector('.price')).borderLeftColor,
                           square: getComputedStyle(sq, '::before').backgroundColor,
                           outline: cs.outlineStyle,
                           accent: getComputedStyle(document.documentElement)
                                     .getPropertyValue('--accent').trim() }; }"""
                accent = page.evaluate("""() => { const s = document.createElement('i');
                  s.style.color = getComputedStyle(document.documentElement)
                    .getPropertyValue('--accent'); document.body.appendChild(s);
                  const c = getComputedStyle(s).color; s.remove(); return c; }""")
                stubs = page.locator("#main a.stub:not(.sold)")
                rest = stubs.nth(0).evaluate(probe)
                self.assertNotEqual(rest["square"], accent)
                self.assertNotEqual(rest["top"], accent)
                stubs.nth(0).hover()
                # The edges ease in over .15 s; the square has no transition.
                for side in ("top", "right", "bottom"):
                    expect(stubs.nth(0)).to_have_css(f"border-{side}-color", accent)
                hov = stubs.nth(0).evaluate(probe)
                self.assertEqual((hov["top"], hov["right"], hov["bottom"], hov["square"]),
                                 (accent,) * 4)
                self.assertEqual(hov["left"], rest["left"], "the chain's edge is kept")
                self.assertEqual(hov["seam"], rest["seam"], "the seam stays --line")
                page.mouse.move(0, 0)
                page.keyboard.press("Shift")
                stubs.nth(1).focus()
                expect(stubs.nth(1)).to_have_css("border-top-color", accent)
                foc = stubs.nth(1).evaluate(probe)
                self.assertEqual((foc["top"], foc["square"], foc["outline"]),
                                 (accent, accent, "solid"))

    def test_a_screen_reader_hears_the_facts_apart(self):
        page = self.open(393)
        snap = page.locator("#main a.stub", has_text="18:15").aria_snapshot()
        self.assertRegex(snap, r"Kinopalatsi\s*,\s*Sali 10 Dolby Atmos\s*,\s*Seniorikino\s*,\s*"
                               r"espanja\s*,\s*tekstitys: suomi/ruotsi")
        ajat = self.open(393, "times")
        snap = ajat.locator("#main .tinfo").first.aria_snapshot()
        self.assertRegex(snap, r"Cinema Orion\s*,\s*Sali 1\s*,")

    def test_no_middle_dot_of_the_app_s_own_is_drawn(self):
        """The data here carries none, so any on screen is the app's."""
        for view in ("movies", "times"):
            with self.subTest(view=view):
                page = self.open(393, view)
                self.assertNotIn("\u00b7", page.locator("body").inner_text())
                if view == "movies":
                    self.open_sheet(page)
                    self.assertNotIn("\u00b7", page.locator("#sheet").inner_text())


    def test_the_footer_credit_is_three_facts(self):
        page = self.open(393)
        credit = page.locator("#credit > span")
        self.assertEqual(credit.count(), 3)
        self.assertTrue(credit.nth(1).inner_text().startswith("P\u00e4ivitetty 14.9. klo"),
                        credit.nth(1).inner_text())
        # A hidden full stop after the first two, for a screen reader.
        self.assertEqual(page.locator("#credit > span > .sr-only").count(), 2)

    def test_the_rating_says_its_score_and_votes_in_words(self):
        page = self.open(393)
        ring = page.locator("#main .ring").first
        expect(ring).to_have_attribute("aria-label", "TMDB-arvio 7,1/10, 41 \u00e4\u00e4nt\u00e4")
        for code, want in (("sv", "TMDB-betyg 7,1/10, 41 r\u00f6ster"),
                           ("en", "TMDB rating 7.1/10 from 41 votes")):
            page.click(f"button[data-lang={code}]")
            expect(page.locator("#main .ring").first).to_have_attribute("aria-label", want)
            expect(page.locator("#main .ring").first).to_have_attribute("title", want)

    def test_the_anniskelu_glyph_names_itself_in_the_readers_language(self):
        """Its title and accessible name read "Anniskelu" in every language until
        2026-10-04, while the tag key beside the list was translated."""
        page = self.open(393)
        glyph = page.locator("#main a.stub .gl", has_text="A").first
        for code, want in (("fi", "Anniskelu"), ("sv", "Utsk\u00e4nkning"),
                           ("en", "Licensed bar")):
            with self.subTest(lang=code):
                if code != "fi":
                    page.click(f"button[data-lang={code}]")
                expect(glyph).to_have_attribute("aria-label", want)
                expect(glyph).to_have_attribute("title", want)


if __name__ == "__main__":
    unittest.main()
