"""Where the generated pages put the poster, the header and the ticket list, in a real engine.

The suite already checks the pages' markup and the design contract's numbers. Neither
reads a rendered box, so a layout fault ships green: on 2026-09-18 a draft of the phone
change made `.film` a grid at every width with the poster spanning two rows, and a
row-spanning item distributes its height across the rows it spans. On desktop that pushed
the ticket list 28 px down for every film whose `.info` is only a title, 10 of the 83 on
one city page, while the article heights stayed the same. Nothing in the repository could
see it.

Four films, built from a fixture rather than the committed data, so the shapes this is
about cannot quietly leave: one with everything, one with no synopsis, one with no poster,
and one that is a title and nothing else. `test_the_fixture_still_has_all_four_shapes`
fails loudly if that stops being true.

Positions are compared with a tolerance and against each other, never against a pinned
pixel: fonts, the engine and the platform all move a box by a pixel or two, and a hash of
the geometry would go red for reasons that are not faults. What is asserted is the shape
of the layout -- the header beside the poster, the list below it on a phone, and on desktop
a list whose distance from the header does not depend on how tall the poster is.

Run it like the other browser test, from a venv with Playwright:

    .venv/bin/python -m unittest discover -s tests/browser
"""
import base64
import functools
import http.server
import json
import os
import pathlib
import shutil
import sys
import tempfile
import threading
import unittest
from datetime import date

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "out"
sys.path.insert(0, str(ROOT / "scripts"))
import build_pages as bp                                            # noqa: E402

DAY = date(2026, 9, 14)
VENUES = ("tv-1", "tv-2")
SLUG = "testikino-testila"
# A real 1x1 PNG, so the poster is an image the engine decodes rather than a broken one.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
TOL = 3          # px; a box may sit a pixel or two off between engines and platforms
PHONE, TABLET, DESKTOP, WIDEST = 393, 768, 1200, 1600
# 320 is the narrowest phone the design targets, 560 the breakpoint's own edge,
# 768 a tablet, 1600 wider than the 52rem the content column ever uses.
WIDTHS = (320, 375, PHONE, 560, TABLET, DESKTOP, WIDEST)


# The second venue's room is long, so a city page's ticket wraps its facts at 320 and the
# separator test has a line that starts with a fact.
ROOMS = {"tv-1": "Sali 1", "tv-2": "Iso sali Dolby Atmos 2"}


def show(vid, eid, title, clock, price="", img="", rating="", genres="", length="", lang="",
         aud=None):
    return {"eventId": eid, "title": title, "start": f"2026-09-14T{clock}:00+03:00",
            "theatre": "Testikino", "aud": ROOMS[vid] if aud is None else aud,
            "url": "https://example.invalid/t",
            "img": img, "len": length, "rating": rating, "age": None, "genres": genres,
            "gids": [], "lang": lang, "price": price, "provider": "testi", "venue": vid}


# Two screenings each, because a one-stub film never exercises the list's wrapping.
FILMS = {
    "Taysi Elokuva": dict(img=f"data/posters/{'a'*8}.png", rating="K-12", genres="Draama",
                          length="120", lang="fi", syn="Pitka kuvaus tasta elokuvasta, "
                          "jotta rivi rivittyy myos kapealla naytolla ja kortti kasvaa."),
    "Ei Kuvausta": dict(img=f"data/posters/{'b'*8}.png", rating="K-7", genres="Komedia",
                        length="95", lang="fi", syn=""),
    "Ei Julistetta": dict(img="", rating="S", genres="Animaatio", length="88", lang="fi",
                          syn="Tama elokuva ei kanna julistetta lainkaan."),
    "Pelkka Nimi": dict(img="", rating="", genres="", length="", lang="", syn=""),
}


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


class PagesLayoutTest(unittest.TestCase):
    """One build, one server, one browser; each test asks the pages a question."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = pathlib.Path(cls.tmp.name)
        data = cls.root / "data"
        (data / "posters").mkdir(parents=True)
        for f in FILMS.values():
            if f["img"]:
                (cls.root / f["img"]).write_bytes(PNG)

        # Two venues in one city, so the run builds a city page as well as the theatre
        # pages. Both show the same four films, so every shape is on both kinds of page.
        extra = {}
        for vid in VENUES:
            shows = []
            for i, (title, f) in enumerate(FILMS.items()):
                for j, clock in enumerate(("18:00", "20:30")):
                    # The title-only film's unpriced screening has no room either, so a
                    # theatre page carries a ticket that is a time and a tail and nothing
                    # else.
                    bare = title == "Pelkka Nimi" and j == 1
                    # The full film's second venue states no language, so a desktop city
                    # row puts a one-line ticket beside a two-line one.
                    quiet = title == "Taysi Elokuva" and vid == "tv-2"
                    shows.append(show(vid, f"{vid}-{i}-{j}", title, clock,
                                      price="12€" if j == 0 else "",   # one priced, one not
                                      img=f["img"], rating=f["rating"], genres=f["genres"],
                                      length=f["length"], lang="" if quiet else f["lang"],
                                      aud="" if bare else None))
            (data / f"area-{vid}.json").write_text(json.dumps(
                {"generated": "2026-09-14T09:00:00+00:00", "dates": ["2026-09-14"],
                 "horizon": "2026-09-14", "shows": shows}), encoding="utf-8")
        for title, f in FILMS.items():
            if f["syn"]:
                extra[bp.norm(title)] = {"s": {"fi": f["syn"], "en": f["syn"]}}
        (data / "venues-testi.json").write_text(json.dumps(
            {"generated": "2026-09-14T09:00:00+00:00", "oldest": "2026-09-14T09:00:00+00:00",
             "status": "ok", "stale": [], "unverified": [], "provider": "testi",
             "venues": [{"id": "tv-1", "name": "Testikino", "short": "Testikino",
                         "city": "Testila"},
                        {"id": "tv-2", "name": "Testikino Kaksi", "short": "Testikino Kaksi",
                         "city": "Testila"}]}), encoding="utf-8")
        (data / "areas.json").write_text(json.dumps(
            {"generated": "2026-09-14T09:00:00+00:00", "areas": []}), encoding="utf-8")
        (data / "providers.json").write_text(json.dumps({"providers": [
            {"id": "testi", "label": "Testikino", "host": "example.invalid",
             "accent": "#1F7A5C", "book": "buy"}]}), encoding="utf-8")
        (data / "tmdb-genres.json").write_text(json.dumps(
            {"fi": {}, "sv": {}, "en": {}}), encoding="utf-8")
        (data / "films-extra.json").write_text(json.dumps({"films": extra}), encoding="utf-8")
        # The fonts the pages preload, so text metrics are the real ones.
        shutil.copytree(ROOT / "fonts", cls.root / "fonts")

        saved = (bp.ROOT, bp.DATA)
        bp.ROOT, bp.DATA = cls.root, data
        bp._SHOWS.clear(); bp._unmirrored_hosts.clear()
        try:
            bp.main(today=DAY)
        finally:
            bp.ROOT, bp.DATA = saved

        cls.srv = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(Handler, directory=str(cls.root)))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.origin = f"http://127.0.0.1:{cls.srv.server_port}"
        cls.pw = sync_playwright().start()
        # KINO_BROWSER_ENGINE=webkit runs the same checks in WebKit. The layout that
        # shipped on 2026-09-18 was correct in Chromium and wrong in WebKit, because a
        # negative grid line resolves against the explicit grid and there were no explicit
        # rows. One engine is not a check.
        engine = os.environ.get("KINO_BROWSER_ENGINE", "chromium")
        launcher = getattr(cls.pw, engine)
        channel = os.environ.get("KINO_BROWSER_CHANNEL") if engine == "chromium" else None
        cls.browser = launcher.launch(channel=channel or None, headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.srv.shutdown(); cls.tmp.cleanup()

    def geometry(self, width, path=f"/teatteri/{SLUG}/"):
        """-> (rows, overflow). One row per film, every number a rendered box."""
        ctx = self.browser.new_context(viewport={"width": width, "height": 900},
                                       timezone_id="Europe/Helsinki", locale="fi-FI",
                                       service_workers="block")
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        page.goto(self.origin + path)
        page.wait_for_function("document.fonts.ready.then(()=>true)")
        rows = page.evaluate("""() => [...document.querySelectorAll('article.film')].map(f => {
            const r = e => { const b = e.getBoundingClientRect();
                             return {x:b.x, y:b.y, w:b.width, h:b.height, r:b.right, b:b.bottom} };
            // Where the text is drawn, not where its box is. A floated poster leaves the
            // heading box spanning the full width with only its lines beside the float, so
            // a box read says the title is under the poster when a reader sees it beside.
            const t = e => { const rg = document.createRange(); rg.selectNodeContents(e);
                             const cs = [...rg.getClientRects()].filter(c => c.width || c.height);
                             if (!cs.length) return r(e);
                             const x = Math.min(...cs.map(c => c.x)), y = Math.min(...cs.map(c => c.y));
                             const rr = Math.max(...cs.map(c => c.right));
                             const bb = Math.max(...cs.map(c => c.bottom));
                             return {x, y, w: rr - x, h: bb - y, r: rr, b: bb} };
            const info = f.querySelector('.info');
            // Everything above the list, and the part of it that sits beside the poster on
            // a phone: the synopsis drops below the poster there (2026-10-04).
            const above = [...info.children].filter(k => !k.classList.contains('times'));
            const head = above.filter(k => !k.classList.contains('syn'));
            const s = f.querySelector('.syn');
            const syn = s ? {...r(s), lh: parseFloat(getComputedStyle(s).lineHeight),
                             clamp: getComputedStyle(s).webkitLineClamp} : null;
            const times = f.querySelector('.times');
            return {title: f.querySelector('h3').textContent,
                    parts: above.length,
                    poster: r(f.querySelector('.poster')),
                    blank: !!f.querySelector('.poster.blank'),
                    h3: t(f.querySelector('h3')),
                    head: head.map(t),
                    headBottom: above.length ? t(above[above.length-1]).b : r(info).y,
                    titleBlockBottom: head.length ? t(head[head.length-1]).b : r(info).y,
                    headBoxBottom: above.length ? r(above[above.length-1]).b : r(info).y,
                    times: r(times), film: r(f), stubs: times.children.length, syn} })""")
        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth > window.innerWidth")
        return rows, overflow

    # -- the fixture itself ----------------------------------------------------------------

    def test_the_fixture_still_has_all_four_shapes(self):
        """Without this the checks below can pass by having nothing to check."""
        rows, _ = self.geometry(DESKTOP)
        self.assertEqual(len(rows), 4, [r["title"] for r in rows])
        self.assertTrue(any(r["blank"] for r in rows), "no film without a poster")
        self.assertTrue(any(not r["blank"] for r in rows), "no film with a poster")
        self.assertTrue(any(r["parts"] == 1 for r in rows), "no title-only film")
        self.assertTrue(any(r["parts"] >= 3 for r in rows), "no film with a full header")
        self.assertTrue(all(r["stubs"] == 2 for r in rows), "a film lost a screening")

    # -- desktop ---------------------------------------------------------------------------

    def test_desktop_keeps_the_header_beside_the_poster(self):
        rows, _ = self.geometry(DESKTOP)
        for r in rows:
            with self.subTest(film=r["title"]):
                self.assertGreater(r["h3"]["x"], r["poster"]["r"] - TOL)

    def test_desktop_list_sits_the_same_distance_below_the_header_for_every_film(self):
        """The regression this file exists for. A row-spanning poster pushed the list down
        only where the header was short, so the gap stopped being a constant. Compared
        between films rather than against a pinned number, and capped so the check cannot
        be satisfied by every film being equally wrong."""
        rows, _ = self.geometry(DESKTOP)
        gaps = {r["title"]: r["times"]["y"] - r["headBoxBottom"] for r in rows}
        spread = max(gaps.values()) - min(gaps.values())
        self.assertLessEqual(spread, TOL, f"the gap depends on the film: {gaps}")
        self.assertLess(max(gaps.values()), 20, f"the list detached from the header: {gaps}")

    def test_desktop_list_stays_in_the_information_column(self):
        rows, _ = self.geometry(DESKTOP)
        for r in rows:
            with self.subTest(film=r["title"]):
                self.assertGreater(r["times"]["x"], r["poster"]["r"] - TOL)
                self.assertLess(r["times"]["w"], r["film"]["w"] - r["poster"]["w"] + TOL)

    # -- phone -----------------------------------------------------------------------------

    def test_phone_keeps_the_header_beside_the_poster(self):
        rows, _ = self.geometry(PHONE)
        for r in rows:
            with self.subTest(film=r["title"]):
                self.assertGreater(r["h3"]["x"], r["poster"]["r"] - TOL)
                self.assertLess(abs(r["h3"]["y"] - r["poster"]["y"]), 12,
                                "the title left the poster's row")

    def test_phone_keeps_the_whole_header_together_beside_the_poster(self):
        """Not only the title. On a phone `.info` is `display:contents`, so each header
        part is the grid's own item and the poster has to span all of their rows. With the
        poster in row one alone the row inflates to the poster's height and the metadata
        and the synopsis drop underneath it, which the title's own position cannot show.
        The parts flow on their natural margins, 7, 5 and 6 px, so any gap far above those
        is the poster forcing a row open.

        The gaps alone do not settle it. A grid item stretches to its row, so a poster
        left in row one inflates that row and the title's own box grows to fill it: the
        text still sits at the top, the gap to the next part is still 7 px, and the empty
        band is inside the title. That shape survived the gap check and is why the height
        of the title box is asserted too."""
        rows, _ = self.geometry(PHONE)
        for r in rows:
            gaps = [round(b["y"] - a["b"]) for a, b in zip(r["head"], r["head"][1:])]
            with self.subTest(film=r["title"], parts=r["parts"]):
                if gaps:
                    self.assertLess(max(gaps), 12, f"a header part was pushed down: {gaps}")
                if r["parts"] > 1:
                    # The part after the title has to begin while the poster is still
                    # beside it. This is the one that shipped broken: on 2026-09-18 an
                    # iPhone drew the title beside the poster and started the metadata
                    # below it, and every check that read boxes rather than text, or the
                    # title alone, passed.
                    self.assertLess(r["head"][1]["y"], r["poster"]["b"] - TOL,
                                    "the header restarts below the poster")

    def test_phone_puts_the_list_below_the_whole_header_at_full_width(self):
        rows, _ = self.geometry(PHONE)
        for r in rows:
            with self.subTest(film=r["title"]):
                self.assertGreater(r["times"]["y"], r["poster"]["b"] - TOL)
                self.assertGreater(r["times"]["y"], r["headBottom"] - TOL)
                self.assertLess(abs(r["times"]["w"] - r["film"]["w"]), TOL)
                if r["syn"]:
                    self.assertGreater(r["times"]["y"], r["syn"]["b"] - TOL)

    def test_phone_synopsis_is_full_width_below_the_poster_and_clamped(self):
        """The maintainer's decision of 2026-10-04: the clamped synopsis sat beside the
        poster in a narrow column on some cards and under it on others. It now always
        starts below the poster and the title block, at the card's width, three lines."""
        for path in (f"/teatteri/{SLUG}/", "/kaupunki/testila/"):
            for w in (320, 375, PHONE, 430, 560):
                rows, _ = self.geometry(w, path)
                syns = [r for r in rows if r["syn"]]
                self.assertEqual(len(syns), 2, "the fixture lost a synopsis")
                for r in syns:
                    y = r["syn"]
                    with self.subTest(path=path, width=w, film=r["title"]):
                        self.assertGreater(y["y"], r["poster"]["b"] - TOL)
                        self.assertGreater(y["y"], r["titleBlockBottom"] - TOL)
                        self.assertLess(abs(y["w"] - r["film"]["w"]), TOL)
                        self.assertEqual(str(y["clamp"]), "3")
                        self.assertLessEqual(y["h"], 3 * y["lh"] + TOL)

    def test_desktop_synopsis_stays_in_the_information_column(self):
        rows, _ = self.geometry(DESKTOP)
        for r in rows:
            if r["syn"]:
                with self.subTest(film=r["title"]):
                    self.assertGreater(r["syn"]["x"], r["poster"]["r"] - TOL)

    def tickets(self, width, path=f"/teatteri/{SLUG}/"):
        """-> one row per ticket: its box, its film's, its price compartment's, its time's."""
        ctx = self.browser.new_context(viewport={"width": width, "height": 900},
                                       service_workers="block")
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        page.goto(self.origin + path)
        page.wait_for_function("document.fonts.ready.then(()=>true)")
        return page.evaluate("""() => [...document.querySelectorAll('.times .stub')].map(s => {
            const r = e => e.getBoundingClientRect();
            return {w: r(s).width, r: r(s).right, film: r(s.closest('article')).width,
                    info: r(s.closest('.info')).width, priceL: r(s.querySelector('.price')).left,
                    priceR: r(s.querySelector('.price')).right,
                    timeR: r(s.querySelector('.time')).right,
                    bare: !s.querySelector('.aud')} })""")

    def test_phone_tickets_take_the_card_width_one_per_line(self):
        """The app's phone layout since v269: every ticket the card's full width, its price
        or tail at the right edge, on the theatre and the city page alike (2026-10-04)."""
        for path in (f"/teatteri/{SLUG}/", "/kaupunki/testila/"):
            for w in (320, 375, PHONE, 560):
                rows = self.tickets(w, path)
                self.assertTrue(rows)
                for t in rows:
                    with self.subTest(path=path, width=w, ticket=t):
                        self.assertLess(abs(t["w"] - t["film"]), TOL)
                        self.assertLess(abs(t["priceR"] - t["r"]), TOL)
        self.assertTrue(any(t["bare"] for t in self.tickets(375)), "no time-only ticket")

    def test_city_tickets_in_one_row_end_together(self):
        """A grid row is as tall as its tallest ticket and every ticket in it fills that
        height: the 2026-10-04 city pages had 24 rows at 1280 where a one-line ticket ended
        above a two-line one. Each ticket's text stays centred in its own compartment."""
        ctx = self.browser.new_context(viewport={"width": DESKTOP, "height": 900},
                                       service_workers="block")
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        page.goto(self.origin + "/kaupunki/testila/")
        page.wait_for_function("document.fonts.ready.then(()=>true)")
        rows = page.evaluate("""() => { const out = [];
            for (const g of document.querySelectorAll('.times.grid')) { const by = {};
              for (const s of g.querySelectorAll('.stub')) { const b = s.getBoundingClientRect();
                // The text, not the compartment: a stretched compartment is the row's height.
                const rg = document.createRange(); rg.selectNodeContents(s.querySelector('.aud'));
                const cs = [...rg.getClientRects()].filter(c => c.height);
                const top = Math.min(...cs.map(c => c.top)), bot = Math.max(...cs.map(c => c.bottom));
                (by[Math.round(b.top)] = by[Math.round(b.top)] || []).push(
                  {b: b.bottom, h: b.height, mid: (b.top + b.bottom) / 2,
                   audMid: (top + bot) / 2, audH: bot - top}); }
              for (const k in by) if (by[k].length > 1) out.push(by[k]); }
            return out; }""")
        self.assertTrue(rows, "no grid row holds two tickets")
        self.assertTrue(any(max(t["audH"] for t in r) - min(t["audH"] for t in r) > 8
                            for r in rows),
                        "no row mixes a one-line and a two-line ticket; nothing is proved")
        for r in rows:
            with self.subTest(row=r):
                self.assertLess(max(t["b"] for t in r) - min(t["b"] for t in r), 0.5)
                for t in r:
                    self.assertLess(abs(t["audMid"] - t["mid"]), TOL)

    def test_desktop_tickets_keep_their_own_width(self):
        """Above the breakpoint a theatre page's tickets stay as wide as their content: a
        time-only ticket's tail follows its time."""
        rows = self.tickets(DESKTOP)
        for t in rows:
            with self.subTest(ticket=t):
                self.assertLess(t["w"], t["info"] - TOL)
        bare = [t for t in rows if t["bare"]]
        self.assertTrue(bare, "no time-only ticket")
        for t in bare:
            self.assertLess(t["priceL"] - t["timeR"], TOL)

    # -- both ------------------------------------------------------------------------------

    def test_no_width_scrolls_sideways(self):
        for w in WIDTHS:
            with self.subTest(width=w):
                _, overflow = self.geometry(w)
                self.assertFalse(overflow)

    def test_every_width_above_the_breakpoint_keeps_the_desktop_arrangement(self):
        """561 px and up is one layout, so a tablet and a wide desktop answer the same
        way: the list stays in the information column beside the poster, and its distance
        from the header does not depend on the film."""
        for w in (561, TABLET, DESKTOP, WIDEST):
            rows, _ = self.geometry(w)
            gaps = {r["title"]: r["times"]["y"] - r["headBoxBottom"] for r in rows}
            with self.subTest(width=w):
                self.assertLessEqual(max(gaps.values()) - min(gaps.values()), TOL, gaps)
                for r in rows:
                    self.assertGreater(r["times"]["x"], r["poster"]["r"] - TOL, r["title"])

    def test_every_width_below_the_breakpoint_keeps_the_phone_arrangement(self):
        for w in (320, 375, PHONE, 560):
            rows, _ = self.geometry(w)
            with self.subTest(width=w):
                for r in rows:
                    self.assertGreater(r["times"]["y"], r["poster"]["b"] - TOL, r["title"])
                    self.assertLess(abs(r["times"]["w"] - r["film"]["w"]), TOL, r["title"])
                    self.assertGreater(r["h3"]["x"], r["poster"]["r"] - TOL, r["title"])

    def test_the_city_page_follows_the_same_rules(self):
        """A city page is the same generator with the combined ticket, and it is the view
        the phone change was reported against."""
        for w, same_col in ((DESKTOP, True), (PHONE, False)):
            rows, overflow = self.geometry(w, "/kaupunki/testila/")
            self.assertEqual(len(rows), 4, "the city page lost a film")
            self.assertFalse(overflow)
            for r in rows:
                with self.subTest(width=w, film=r["title"]):
                    self.assertGreater(r["h3"]["x"], r["poster"]["r"] - TOL)
                    if same_col:
                        self.assertGreater(r["times"]["x"], r["poster"]["r"] - TOL)
                    else:
                        self.assertLess(abs(r["times"]["w"] - r["film"]["w"]), TOL)

    def test_the_city_page_separates_a_ticket_s_facts_with_squares(self):
        """The cinema and the room are separate facts with a CSS square between them
        (2026-09-23). A fact that starts a line hides its square, and hover turns the
        squares and the top edge --accent while the chain's left edge stays."""
        for w in (320, PHONE):
            ctx = self.browser.new_context(viewport={"width": w, "height": 900})
            self.addCleanup(ctx.close)
            page = ctx.new_page()
            page.goto(self.origin + "/kaupunki/testila/")
            got = page.evaluate("""() => {
              const R = e => e.getBoundingClientRect();
              let shown = 0, opening = 0, wrapped = false;
              for (const row of document.querySelectorAll('.fx')) {
                const kids = [...row.children], clip = R(row.parentElement);
                kids.forEach((k, i) => {
                  if (i && R(kids[i - 1]).bottom <= R(k).top + 2) wrapped = true;
                  if (!i || R(k).left + 3 < clip.left - 0.5) return;
                  shown++;
                  if (R(kids[i - 1]).bottom <= R(k).top + 2) opening++;
                });
              }
              return { shown, opening, wrapped, dots: document.body.innerText.includes('\\u00b7') };
            }""")
            with self.subTest(width=w):
                self.assertGreater(got["shown"], 0, got)
                if w == 320:
                    self.assertTrue(got["wrapped"], "the fixture no longer wraps a ticket")
                self.assertEqual((got["opening"], got["dots"]), (0, False), got)
        stub = page.locator("a.stub").first
        rest_left = stub.evaluate("e => getComputedStyle(e).borderLeftColor")
        accent = page.evaluate("""() => { const i = document.createElement('i');
            i.style.color = getComputedStyle(document.documentElement).getPropertyValue('--accent');
            document.body.appendChild(i); const c = getComputedStyle(i).color; i.remove(); return c; }""")
        stub.hover()
        got = stub.evaluate("""e => [getComputedStyle(e).borderTopColor, getComputedStyle(e).borderLeftColor,
            getComputedStyle(e.querySelector('.fx > span + span'), '::before').backgroundColor]""")
        self.assertEqual(got, [accent, rest_left, accent])


if __name__ == "__main__":
    unittest.main()
