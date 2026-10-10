"""Browser tests for the client: the venue picker and the ticket links, in a real engine.

Separate from the adapter tests on purpose, and outside `discover -s tests` (this
directory is not a package): it needs Playwright and a Chrome, which CI does not
install, and the suite fails on a skipped test. Run it by hand from a venv:

    python3 -m venv .venv && .venv/bin/pip install playwright==1.62.0
    .venv/bin/python -m unittest discover -s tests/browser

`channel="chrome"` drives the Chrome already on the machine, so `playwright install`
and its browser download are not needed. The page is index.html from this checkout;
`data/` is answered from tests/browser/fixture, five files copied from the committed
data on 2026-09-14, and the clock is pinned to 12:00 Helsinki that day, so the
schedule it renders never moves. Every wait is an `expect` condition, none a sleep. A
failing test writes a full-page PNG and a Playwright trace zip into tests/browser/out
(gitignored); open the zip with `playwright show-trace`.

What lives here and not in the node harnesses: focus, inert, Escape, arrow keys and
the on-screen-keyboard rule are DOM and event plumbing, which the extracted pure
functions cannot reach and CLAUDE.md lists as "verified live".
"""
import datetime
import http.server
import json
import os
import pathlib
import re
import threading
import time
import unittest

from playwright.sync_api import expect, sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIXTURE = HERE / "fixture"
OUT = HERE / "out"
FIXED = datetime.datetime(2026, 9, 14, 9, 0, tzinfo=datetime.timezone.utc)   # 12:00 Helsinki
SHOWS = json.loads((FIXTURE / "data/area-or-helsinki.json").read_text(encoding="utf-8"))["shows"]
TODAY_URLS = {s["url"] for s in SHOWS if s["start"].startswith("2026-09-14")}


# 10 s rather than Playwright's 5 s default: the first launch of a freshly installed
# Chromium on a cold runner took the first test past 5 s once in six local runs, and
# every wait here is a condition, so a longer ceiling costs nothing on a green run.
expect.set_options(timeout=10_000)


class Handler(http.server.SimpleHTTPRequestHandler):
    """index.html, sw.js and fonts from the checkout; data/ from the fixture.

    `delay` holds seconds by path suffix: a venue file answered late is how the readiness
    condition below is shown to wait rather than to race the boot.

    `fail` holds path suffixes answered 500, and `body` suffixes answered with the bytes
    given instead of the fixture file. `hold` maps a suffix to two
    `threading.Event`s, `(arrived, release)`: the handler sets the first when the request
    reaches it and answers once the test sets the second. A load that fails, and one left
    in flight for exactly as long as the test needs, with no sleep on either side."""
    delay = {}
    fail = set()
    body = {}
    hold = {}

    def do_GET(self):
        # Logged before the delay below, unlike `served`, which is logged after it. A race
        # test has to know the request is in flight, not that it has finished.
        self.server.requested.append(self.path)
        self.nostore = False
        # A snapshot: the handler runs on the server thread while a test's own thread
        # sets or clears this, and iterating the live dict raised "dictionary changed
        # size during iteration" out of the server loop. The traceback printed, the
        # request still completed and the suite stayed green, so it read as noise.
        for suffix, secs in list(self.delay.items()):
            if self.path.endswith(suffix):
                # A delayed file is also uncacheable, or the browser answers the second
                # request from its own HTTP cache and the delay describes nothing. That is
                # what makes a cold load reproducible here at all.
                self.nostore = True
                time.sleep(secs)
        for suffix, (arrived, release) in list(self.hold.items()):
            if self.path.split("?")[0].endswith(suffix):
                self.nostore = True
                arrived.set()
                release.wait(10)
        if any(self.path.split("?")[0].endswith(x) for x in list(self.fail)):
            self.nostore = True
            self.send_error(500)
            return
        for suffix, data in list(self.body.items()):
            if self.path.split("?")[0].endswith(suffix):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                super().end_headers()
                self.wfile.write(data)
                return
        self.server.served.append((self.path, time.monotonic()))
        super().do_GET()

    def end_headers(self):
        if getattr(self, "nostore", False):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def translate_path(self, path):
        rel = path.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        base = FIXTURE if rel.startswith("data/") else ROOT
        return str(base / rel)

    def log_message(self, *a):
        pass


class Browser(unittest.TestCase):
    viewport = {"width": 1200, "height": 900}; touch = False
    tz = "Europe/Helsinki"

    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.srv.served = []
        cls.srv.requested = []
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.origin = f"http://127.0.0.1:{cls.srv.server_port}"
        cls.pw = sync_playwright().start()
        # KINO_BROWSER_ENGINE picks the engine, default chromium, the same way
        # test_pages_layout.py does. Playwright's own pinned build for that engine, the one
        # `playwright install <engine>` fetched for this Playwright version, so what is
        # under test is decided by the pin rather than by the machine.
        # KINO_BROWSER_CHANNEL=chrome drives the Chrome already installed instead, which
        # skips the download for a quick local run; it is a Chromium option and is
        # suppressed outright on any other engine rather than handed to a launcher that
        # would reject it.
        engine = os.environ.get("KINO_BROWSER_ENGINE", "chromium")
        launcher = getattr(cls.pw, engine)
        channel = os.environ.get("KINO_BROWSER_CHANNEL") if engine == "chromium" else None
        cls.browser = launcher.launch(channel=channel or None, headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.srv.shutdown()

    def setUp(self):
        self.ctx = self.browser.new_context(viewport=self.viewport, has_touch=self.touch,
                                            timezone_id=self.tz, locale="fi-FI",
                                            service_workers="block")
        self.ctx.tracing.start(screenshots=True, snapshots=True)
        OUT.mkdir(exist_ok=True)
        self.page = self.ctx.new_page()
        self.page.clock.install(time=FIXED)
        self.page.goto(self.origin + "/index.html")

    def tearDown(self):
        res = getattr(self._outcome, "result", None)
        failed = any(t is self for t, _ in (res.failures + res.errors)) if res else False
        name = OUT / self.id().split(".")[-1]
        if failed:
            self.page.screenshot(path=f"{name}.png", full_page=True)
            self.ctx.tracing.stop(path=f"{name}.zip")
        else:
            self.ctx.tracing.stop()
        self.ctx.close()

    def open_picker(self):
        """Click until the picker opens. `openVenueSheet` returns before the venue lists
        have arrived and the page changes nothing observable when they do (the day chips
        are built before `loadAreas`; the trigger's label and attributes stay as in the
        markup), so the condition is the picker itself: a click that opened it. Each
        attempt waits on the class through `expect`, no fixed sleep, and the loop is
        bounded by the same 10 s the other waits get."""
        deadline = time.monotonic() + 10
        vwrap = self.page.locator("#vwrap")
        while True:
            self.page.locator("#areaSelect").click()
            try:
                expect(vwrap).to_have_class("vwrap open", timeout=250)
                return self.page.locator("#vq")
            except AssertionError:
                if time.monotonic() > deadline:
                    raise

    def pick_orion(self):
        vq = self.open_picker(); vq.fill("orion")
        rows = self.page.locator("#vlist .vrow")
        expect(rows).to_have_count(1)
        expect(rows.first).to_have_attribute("data-id", "or-helsinki")
        vq.press("Enter")
        expect(self.page.locator("#vwrap")).not_to_have_class("vwrap open")
        expect(self.page.locator("#areaSelect")).to_contain_text("Cinema Orion")
        expect(self.page.locator("a.stub").first).to_be_visible()


class Desktop(Browser):
    def test_search_and_select_a_cinema(self):
        self.pick_orion()
        self.assertGreater(self.page.locator("a.stub").count(), 0)

    def test_reopening_marks_the_current_venue(self):
        self.pick_orion()
        self.open_picker()
        cur = self.page.locator('#vlist .vrow[aria-current="true"]')
        expect(cur).to_have_count(1)
        expect(cur).to_have_attribute("data-id", "or-helsinki")
        expect(self.page.locator('#vviews .vv[data-view="cities"]')).to_have_attribute("aria-pressed", "true")
        expect(self.page.locator("#vq")).to_be_focused()          # fine pointer: field takes focus

    def test_keyboard_navigation(self):
        vq = self.open_picker()
        vq.press("ArrowDown")
        expect(self.page.locator("#vlist .vrow").first).to_be_focused()
        self.page.keyboard.press("ArrowUp")
        expect(self.page.locator("#vlist .vrow").first).to_be_focused()   # clamps at the top
        vq.fill("zzz"); expect(self.page.locator("#vnone")).to_have_class("vnone show")
        vq.press("Escape"); expect(vq).to_have_value("")                    # first Escape clears
        expect(self.page.locator("#vwrap")).to_have_class("vwrap open")
        vq.press("Escape")                                                  # second closes
        expect(self.page.locator("#vwrap")).not_to_have_class("vwrap open")
        expect(self.page.locator("#areaSelect")).to_be_focused()

    def test_booking_urls_match_the_fixture(self):
        self.pick_orion()
        hrefs = self.page.locator("a.stub").evaluate_all("as => as.map(a => a.href)")
        self.assertTrue(hrefs)
        self.assertEqual(set(hrefs) - TODAY_URLS, set(), "a rendered link is not a fixture URL for today")
        for h in hrefs:
            self.assertTrue(h.startswith("https://cinemaorion.fi/"), h)
            self.assertNotIn(self.origin, h)


class Mobile(Browser):
    viewport = {"width": 375, "height": 812}; touch = True

    def test_picker_fits_the_viewport_and_focus_avoids_the_keyboard(self):
        self.open_picker()
        sheet = self.page.locator("#vwrap .vsheet").bounding_box()
        self.assertLessEqual(sheet["x"] + sheet["width"], 375.5)
        self.assertLessEqual(sheet["y"] + sheet["height"], 812.5)
        expect(self.page.locator("#vq")).to_be_in_viewport()
        expect(self.page.locator("#vclose")).to_be_in_viewport()
        expect(self.page.locator("#vclose")).to_be_focused()     # coarse pointer: no keyboard pop
        self.assertEqual(self.page.evaluate("document.documentElement.scrollWidth"), 375)

    def test_select_on_mobile_renders_tickets(self):
        self.pick_orion()
        expect(self.page.locator("a.stub").first).to_be_in_viewport()

class DelayedVenues(Browser):
    """The venue file arrives two seconds late: the picker opens on the venue anyway, and
    only after that file was served, so the readiness condition waited for the data and not
    for the page load."""

    def setUp(self):
        Handler.delay = {"/data/venues-orion.json": 2.0}
        self.addCleanup(lambda: setattr(Handler, "delay", {}))
        self.srv.served.clear()
        super().setUp()

    def test_the_picker_opens_only_after_the_late_venue_file(self):
        self.pick_orion()
        opened = time.monotonic()
        served = {path.split("?")[0]: t for path, t in self.srv.served}
        self.assertIn("/data/venues-orion.json", served)
        self.assertGreater(served["/data/venues-orion.json"] - served["/index.html"], 2.0)
        self.assertGreater(opened, served["/data/venues-orion.json"])


class TimeFilterHitTarget(Browser):
    """The Ajat time control has to be clickable, which only a hit test shows.

    v202 shipped it covered: a transparent `.tfield::after` meant to extend the hit area
    sat over the select, so `elementFromPoint` at its centre returned the wrapper and a
    real click did nothing, in Chromium and WebKit alike. Every pre-ship check had set the
    value through `select_option`/`dispatchEvent`, which performs no hit test and so
    passed. This drives the mouse.
    """

    viewport = {"width": 375, "height": 812}
    touch = True

    def open_ajat(self):
        self.pick_orion()
        self.page.locator("#segTimes").click()
        expect(self.page.locator(".trow").first).to_be_visible()

    def test_a_real_click_reaches_the_select(self):
        self.open_ajat()
        # Playwright hit-tests before clicking: an overlay fails this outright.
        self.page.locator("#minTime").click(timeout=5000)
        self.page.keyboard.press("Escape")
        landed = self.page.evaluate("""() => {
            const s = document.querySelector('#minTime');
            const r = s.getBoundingClientRect();
            return document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) === s;
        }""")
        self.assertTrue(landed, "the centre of the control must hit the select itself")

    def test_the_control_is_36_to_the_eye_and_44_to_the_finger(self):
        self.open_ajat()
        box = self.page.evaluate("""() => {
            const s = document.querySelector('#minTime'), f = s.closest('.tfield');
            return {hit: Math.round(s.getBoundingClientRect().height),
                    seen: Math.round(f.getBoundingClientRect().height)};
        }""")
        self.assertEqual(box["seen"], 36)
        self.assertEqual(box["hit"], 44, "Apple's floor, carried by the control itself")

    def test_choosing_a_time_narrows_the_list(self):
        self.open_ajat()
        before = self.page.locator(".trow").count()
        self.page.locator("#minTime").select_option("18:00")
        expect(self.page.locator(".tbar")).to_be_visible()
        times = self.page.evaluate("""() => [...document.querySelectorAll('.trow .time')]
            .map(t => t.textContent.trim())""")
        self.assertTrue(times, "the fixture must keep something at or after 18:00")
        self.assertTrue(all(t >= "18:00" for t in times), times)
        self.assertLess(len(times), before)


class ShareLink(Browser):
    """A `#m=&d=` link marks a ticket. The reader has to be able to see it.

    Short viewport on purpose: the sheet has to overflow before "scrolled to" can mean
    anything. The film picked is the fixture's only one with a day far enough down the
    body to fall outside it -- Hetki ennen valoa, 17.9. and 23.9.
    """

    viewport = {"width": 375, "height": 320}
    touch = True

    def sheet_box(self):
        return self.page.evaluate("""() => {
            const body = document.querySelector('.sheet-body');
            const pick = document.querySelector('.sheet-body .stub.pick');
            if(!body || !pick) return null;
            const b = body.getBoundingClientRect(), p = pick.getBoundingClientRect();
            return {top: b.top, bottom: b.bottom, pickTop: p.top, pickBottom: p.bottom,
                    scrollTop: body.scrollTop, scrollable: body.scrollHeight > body.clientHeight};
        }""")

    def test_a_link_to_a_later_day_leaves_its_ticket_in_view(self):
        self.pick_orion()
        self.page.evaluate("location.hash = 'm=hetki-ennen-valoa&d=2026-09-23'")
        expect(self.page.locator(".sheet-body .stub.pick")).to_have_count(1)
        box = self.sheet_box()
        self.assertTrue(box and box["scrollable"],
                        "the sheet has to overflow or this proves nothing")
        self.assertGreater(box["pickTop"], box["top"] - 1,
                           "the marked ticket sits above the top of the body")
        self.assertLess(box["pickBottom"], box["bottom"],
                        f"the marked ticket is below the body's bottom edge by "
                        f"{box['pickBottom'] - box['bottom']:.0f}px: marked and left off "
                        f"screen, which is what a share link did before this was fixed")

    def test_a_link_to_the_first_day_also_leaves_its_ticket_in_view(self):
        """The counterweight. At this height the synopsis pushes even the first day past
        the fold, so both days need the scroll and neither may end up off screen."""
        self.pick_orion()
        self.page.evaluate("location.hash = 'm=hetki-ennen-valoa&d=2026-09-17'")
        expect(self.page.locator(".sheet-body .stub.pick")).to_have_count(1)
        box = self.sheet_box()
        self.assertGreater(box["pickTop"], box["top"] - 1)
        self.assertLess(box["pickBottom"], box["bottom"] + 1)


class SheetRefresh(Browser):
    """A background refresh redraws an open sheet. It must not move the reader."""

    def open_sheet(self):
        self.pick_orion()
        self.page.evaluate("location.hash = 'm=hetki-ennen-valoa&d=2026-09-17'")
        expect(self.page.locator(".sheet-body .stub.pick")).to_have_count(1)

    def focused(self):
        return self.page.evaluate(
            "() => { const a = document.activeElement;"
            " return a ? (a.className || '') + '|' + (a.dataset.i || '') : ''; }")

    def test_following_a_link_to_another_film_still_focuses_the_close_button(self):
        """The path `keepFocus` must not reach: the reader asked for this sheet, so the
        keyboard goes into it. Only `refreshOpenSheet` passes the flag, and that path is
        driven by a service-worker message this context blocks -- it is covered in
        tests/test_screening_link.py instead, which is stated there rather than implied."""
        self.open_sheet()
        self.page.evaluate("location.hash = 'm=autofiktio'")
        expect(self.page.locator(".sheet-body")).to_be_visible()
        self.assertIn("sheet-close", self.focused())

    def test_opening_the_sheet_still_focuses_the_close_button(self):
        """The counterweight: a sheet the reader opens takes focus, as it always has, or
        the keyboard is left behind the page."""
        self.pick_orion()
        self.page.locator("article.movie").first.click()
        expect(self.page.locator(".sheet-body")).to_be_visible()
        self.assertIn("sheet-close", self.focused())


class SheetTouchDrag(Browser):
    """iOS hands a drag the sheet cannot scroll to the page behind it (2026-09-27). The
    sheet cancels that drag; one the body can scroll goes through."""

    viewport = {"width": 375, "height": 812}
    touch = True
    # WebKit has no Touch constructor, so the events are plain ones carrying `touches`.
    DRAG = """([sel, dy]) => {
        const el = document.querySelector(sel), y = el.getBoundingClientRect().top + 10;
        const touch = (type, at) => {
            const e = new Event(type, {bubbles: true, cancelable: true});
            Object.defineProperty(e, 'touches', {value: [{clientY: at}]});
            el.dispatchEvent(e);
            return e.defaultPrevented;
        };
        touch('touchstart', y);
        return touch('touchmove', y + dy);
    }"""

    def open(self, fid):
        self.pick_orion()
        self.page.evaluate(f"location.hash = 'm={fid}'")
        expect(self.page.locator(".sheet-body")).to_be_visible()

    def cancelled(self, sel, dy):
        return self.page.evaluate(self.DRAG, [sel, dy])

    def test_a_drag_on_a_sheet_that_cannot_scroll_is_cancelled(self):
        self.open("presidentin-kyyditys")
        self.assertFalse(self.page.evaluate(
            "() => { const b = document.querySelector('.sheet-body');"
            " return b.scrollHeight > b.clientHeight; }"), "the body has to fit")
        for sel in (".sheet-body .stub", ".sheet-head", "#overlay"):
            for dy in (-80, 80):
                with self.subTest(sel=sel, dy=dy):
                    self.assertTrue(self.cancelled(sel, dy))

    def test_a_drag_the_body_can_scroll_goes_through(self):
        self.page.set_viewport_size({"width": 375, "height": 320})
        self.open("hetki-ennen-valoa")
        self.page.evaluate("() => { const b = document.querySelector('.sheet-body');"
                           " b.scrollTop = (b.scrollHeight - b.clientHeight) / 2; }")
        for dy in (-40, 40):
            with self.subTest(dy=dy):
                self.assertFalse(self.cancelled(".sheet-body .stub", dy))
        self.page.evaluate("document.querySelector('.sheet-body').scrollTop = 0")
        self.assertTrue(self.cancelled(".sheet-body .stub", 40), "past the top edge")


class SheetHeight(Browser):
    """On a phone a short sheet still rises to 70% of the screen (the maintainer's choice
    C, 2026-09-27); the centred modal keeps its content height."""
    phone = False

    def test_a_short_sheet(self):
        self.pick_orion()
        self.page.evaluate("location.hash = 'm=presidentin-kyyditys'")
        expect(self.page.locator(".sheet-body")).to_be_visible()
        self.page.wait_for_function("() => getComputedStyle(document.querySelector('#sheet'))"
                                    ".transform === 'none' || innerWidth >= 700")
        share = self.page.evaluate("() => document.querySelector('#sheet')"
                                   ".getBoundingClientRect().height / innerHeight")
        if self.phone:
            self.assertAlmostEqual(share, 0.70, delta=0.005)
        else:
            self.assertLess(share, 0.5)


class SheetHeightOnAPhone(SheetHeight):
    viewport = {"width": 375, "height": 812}; touch = True; phone = True


class FreeAdmissionTicket(Browser):
    """A source's "Vapaa pääsy" is drawn in the price compartment, which keeps its 56 px,
    its seam and its notches (audit, 2026-09-27: Kino K13's four screenings drew none)."""

    def setUp(self):
        doc = json.loads((FIXTURE / "data/area-or-helsinki.json").read_text(encoding="utf-8"))
        doc["shows"][0]["price"] = "Vapaa pääsy"
        self.eid = doc["shows"][0]["eventId"]
        Handler.body = {"area-or-helsinki.json": json.dumps(doc).encode("utf-8")}
        self.addCleanup(lambda: setattr(Handler, "body", {}))
        super().setUp()

    def test_the_label_fits_the_compartment(self):
        self.pick_orion()
        for view in ("#segMovies", "#segTimes"):
            with self.subTest(view=view):
                self.page.locator(view).click()
                price = self.page.locator("#main a.stub .price", has_text="Vapaa pääsy").first
                expect(price).to_be_visible()
                box = price.evaluate("""e => { const r = e.getBoundingClientRect(),
                    b = getComputedStyle(e, '::before'), cs = getComputedStyle(e);
                    return {w: r.width, h: r.height, over: e.scrollWidth > e.clientWidth,
                            seam: cs.borderLeftStyle, notch: b.content}; }""")
                self.assertAlmostEqual(box["w"], 56, delta=0.5)
                self.assertGreaterEqual(box["h"], 38)
                self.assertFalse(box["over"])
                self.assertEqual((box["seam"], box["notch"]), ("dashed", '""'))


class FreeAdmissionTicketOnAPhone(FreeAdmissionTicket):
    viewport = {"width": 375, "height": 812}; touch = True


class PremiereBadge(Browser):
    """The badge reads the date off the show. It read films.json, which is fetched only
    in English or for a sheet, so Finnish and Swedish lists had none (prior review #26).
    The fixture serves no films.json at all."""

    def setUp(self):
        doc = json.loads((FIXTURE / "data/area-1004.json").read_text(encoding="utf-8"))
        for sh in doc["shows"]:
            sh["rd"] = "2026-09-18"
        # Itis shows Autofiktio after Orion does, so the city card starts on Orion's show.
        itis = {**doc, "shows": [{**doc["shows"][0], "eventId": "HO9", "title": "Autofiktio",
                                  "theatre": "Itis", "venue": "1162",
                                  "start": "2026-09-14T20:00:00+03:00"}]}
        Handler.body = {"area-1004.json": json.dumps(doc).encode("utf-8"),
                        "area-1162.json": json.dumps(itis).encode("utf-8")}
        self.addCleanup(lambda: setattr(Handler, "body", {}))
        super().setUp()

    def test_the_badge_shows_in_finnish_and_swedish(self):
        for lang, word in (("fi", "Ensi-ilta"), ("sv", "Premiär")):
            with self.subTest(lang=lang):
                self.page.goto(self.origin + f"/index.html?area=1004&lang={lang}")
                badge = self.page.locator("#main .fmt.prem")
                expect(badge).to_have_count(1)
                self.assertEqual(badge.text_content(), f"{word} 18.9.")
        self.assertFalse([p for p in self.srv.requested if "films.json" in p])

    def test_a_city_card_finds_the_date_on_a_later_show(self):
        self.page.goto(self.origin + "/index.html?area=city:Helsinki")
        card = self.page.locator("#main article.movie").filter(has_text="Autofiktio")
        expect(card.locator(".fmt.prem")).to_have_count(1)


class PremiereBadgeOnAPhone(PremiereBadge):
    viewport = {"width": 375, "height": 812}; touch = True


class SheetSynopsisByTmdbId(Browser):
    """Another chain's title reaches Finnkino's text through the TMDB id films.json
    carries, for a slot films-extra leaves empty."""
    FILMS = json.dumps({"films": {
        "HO1": {"t": {"fi": "Presidentin kyyditys"}, "i": 1412214,
                "s": {"fi": "Finnkinon oma teksti.", "en": "Finnkino's own text."}},
        "HO2": {"t": {"fi": "Teenage Sex"}, "i": 1240889,
                "s": {"fi": "Finnkinon toinen teksti.", "en": ""}}}}).encode("utf-8")
    EXTRA = json.dumps({"films": {
        "presidentin kyyditys": {"s": {"en": "The text films-extra holds."}},
        "teenage sex and death at camp miasma": {"s": {"fi": "Films-extran teksti."}}}}
    ).encode("utf-8")

    def setUp(self):
        Handler.body = {"films.json": self.FILMS, "films-extra.json": self.EXTRA}
        self.addCleanup(lambda: setattr(Handler, "body", {}))
        super().setUp()

    def syn(self, lang, fid):
        self.page.goto(self.origin + f"/index.html?area=or-helsinki&lang={lang}")
        expect(self.page.locator("a.stub").first).to_be_visible()
        self.page.evaluate(f"location.hash = 'm={fid}'")
        p = self.page.locator(".sheet-body p.syn")
        expect(p).to_have_count(1)
        return p.text_content()

    def test_finnkino_fills_a_slot_films_extra_leaves_empty(self):
        self.assertEqual(self.syn("fi", "presidentin-kyyditys"), "Finnkinon oma teksti.")

    def test_films_extra_keeps_its_own_slot(self):
        self.assertEqual(self.syn("en", "presidentin-kyyditys"), "The text films-extra holds.")
        self.assertEqual(self.syn("fi", "teenage-sex-and-death-at-camp-miasma"),
                         "Films-extran teksti.")


class SheetDuringARefresh(Browser):
    """A sheet opened while a resume refresh is in flight shows the schedule on screen.

    `refreshAll` emptied the payload cache, then waited on the venue lists (84 requests in
    production) before the schedule; a film tapped in that window drew "Ei näytöksiä
    valitussa teatterissa." with no ticket, and stayed that way after the refresh landed
    (audit K3, 2026-09-25). `areas.json` is held in flight, which is the first thing the
    refresh waits on; it and Orion's file are uncacheable here so the refresh really asks.
    """

    def setUp(self):
        Handler.delay = {"areas.json": 0, "area-or-helsinki.json": 0}   # uncacheable, no wait
        self.addCleanup(lambda: setattr(Handler, "delay", {}))
        self.addCleanup(lambda: setattr(Handler, "hold", {}))
        super().setUp()

    def test_the_sheet_keeps_its_tickets_through_the_refresh(self):
        self.pick_orion()
        asked = lambda: sum(p.split("?")[0].endswith("/data/area-or-helsinki.json")
                            for p in self.srv.requested)
        loads = asked()
        arrived, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        Handler.hold = {"areas.json": (arrived, release)}
        self.page.clock.set_system_time(FIXED + datetime.timedelta(minutes=11))
        self.page.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")
        self.assertTrue(arrived.wait(10), "the refresh never asked for the venue lists")
        self.page.locator("article.movie").first.click()
        stubs = self.page.locator(".sheet-body a.stub")
        # Well inside the handler's own 10 s hold: the refresh is still waiting here.
        expect(stubs.first).to_be_visible(timeout=3000)
        self.assertEqual(self.page.locator("main .reel").count(), 0,
                         "the schedule load had already started")
        before = stubs.count()
        release.set()
        Handler.hold = {}
        # The refresh asks for the schedule again once the lists land; the server's log
        # says when, bounded like every wait.
        deadline = time.monotonic() + 10
        while asked() <= loads:
            self.assertLess(time.monotonic(), deadline, "the refresh served the old copy")
            self.page.wait_for_timeout(50)
        expect(self.page.locator("main a.stub").first).to_be_visible()
        expect(stubs).to_have_count(before)
        self.assertNotIn("Ei näytöksiä", self.page.locator(".sheet-body").text_content())


class SheetDuringARefreshOnAPhone(SheetDuringARefresh):
    viewport = {"width": 375, "height": 812}; touch = True


class HistoryAcrossVenues(Browser):
    """Back and Forward across venues and home, with the movie sheet open.

    The sheet is modal: it marks everything behind it inert. A traversal that changes
    `?area=` and `#m=` in one step fires `popstate` and no `hashchange`, and `hashchange`
    was the only thing that closed the sheet from the URL, so what stayed on screen was
    another cinema's film, with that cinema's ticket links, over a page nothing could
    reach. The fixture carries a second venue for exactly this: Promenadi Pori shows a
    film no other venue in it does.
    """

    def pick_promenadi(self):
        vq = self.open_picker(); vq.fill("promenadi")
        rows = self.page.locator("#vlist .vrow")
        expect(rows).to_have_count(1)
        vq.press("Enter")
        expect(self.page.locator("#areaSelect")).to_contain_text("Promenadi")
        expect(self.page.locator("a.stub").first).to_be_visible()

    def open_first_film(self):
        self.page.locator("article.movie").first.click()
        expect(self.page.locator(".sheet-body")).to_be_visible()

    def state(self):
        return self.page.evaluate("""() => ({
            hidden: document.getElementById('sheet').inert === true,
            behindInert: !!document.querySelector('main').inert
                      || !!document.querySelector('header').inert,
            title: (document.querySelector('#sheetTitle') || {}).textContent || '',
            url: location.search + location.hash,
            venue: document.querySelector('#areaSelect .vlbl').textContent,
            focus: (document.activeElement && document.activeElement.className) || '',
        })""")

    def test_back_across_a_venue_change_closes_the_other_cinema_s_sheet(self):
        self.pick_orion()
        self.pick_promenadi()
        self.open_first_film()
        before = self.state()
        self.assertFalse(before["hidden"], "the sheet should be open at this point")
        self.assertIn("Porin", before["title"])
        self.page.go_back()          # ?area=1004 without the fragment
        self.page.go_back()          # ?area=or-helsinki
        expect(self.page.locator("#areaSelect")).to_contain_text("Cinema Orion")
        after = self.state()
        self.assertTrue(after["hidden"],
                        f"the sheet is still open showing {after['title']!r} while the "
                        f"page shows {after['venue']!r}")
        self.assertFalse(after["behindInert"],
                         "the page behind the sheet is still inert and cannot be used")

    def test_one_traversal_over_both_the_area_and_the_fragment(self):
        """`history.go(-2)` crosses the fragment and the area in a single step, which is
        the case that fires no hashchange at all."""
        self.pick_orion()
        self.pick_promenadi()
        self.open_first_film()
        self.page.evaluate("history.go(-2)")
        expect(self.page.locator("#areaSelect")).to_contain_text("Cinema Orion")
        after = self.state()
        self.assertTrue(after["hidden"], f"sheet still showing {after['title']!r}")
        self.assertFalse(after["behindInert"])
        self.assertEqual(after["url"], "?area=or-helsinki")

    def test_back_to_the_chooser_closes_the_sheet_too(self):
        """Home clears the selection, and `syncSheet` returns early without one, so even
        a later hashchange could not close it."""
        self.pick_orion()
        self.open_first_film()
        self.page.evaluate("history.go(-2)")
        expect(self.page.locator("#homeMore")).to_be_visible()
        after = self.state()
        self.assertTrue(after["hidden"], f"sheet still showing {after['title']!r} on the chooser")
        self.assertFalse(after["behindInert"])

    def test_the_wrong_film_is_gone_before_the_new_schedule_arrives(self):
        """Closing after the load would leave a window where the previous cinema's film
        and its ticket links sit over the incoming venue's page, inert behind them.

        The reload is what makes that window real: a traversal alone refetches nothing,
        because the venue being returned to is already in `jsonCache`. After a reload the
        history is intact and the cache is empty, so Back does fetch -- and the fixture
        answers that one file a second late.
        """
        Handler.delay["area-or-helsinki.json"] = 1.0
        self.addCleanup(Handler.delay.clear)
        self.pick_orion()           # answered late, and uncacheable, from here on
        self.pick_promenadi()
        self.open_first_film()
        self.page.reload()
        expect(self.page.locator("#sheetTitle")).to_have_text("Porin oma elokuva")
        self.page.evaluate("history.go(-2)")
        # Read while Orion's schedule is still in flight: the label changes before the
        # load, so it is no evidence either way, and the file takes a second to answer.
        mid = self.state()
        self.assertIn("Cinema Orion", mid["venue"])
        self.assertTrue(mid["hidden"],
                        f"mid-load the sheet still showed {mid['title']!r}")
        self.assertFalse(mid["behindInert"], "mid-load the page behind was still inert")
        expect(self.page.locator("#areaSelect")).to_contain_text("Cinema Orion")

    def test_forward_into_a_sheet_entry_shows_that_venue_s_film(self):
        """Forward is the same reconciliation the other way: the entry names an area and a
        film, and the film shown has to be that area's."""
        self.pick_orion()
        self.pick_promenadi()
        self.open_first_film()
        self.page.evaluate("history.go(-2)")
        expect(self.page.locator("#areaSelect")).to_contain_text("Cinema Orion")
        self.page.evaluate("history.go(2)")
        expect(self.page.locator("#areaSelect")).to_contain_text("Promenadi")
        after = self.state()
        self.assertFalse(after["hidden"], "the entry names a film; the sheet belongs open")
        self.assertIn("Porin", after["title"])

    def test_closing_the_sheet_puts_focus_back_on_the_card(self):
        """The counterweight to all of the above: an ordinary close still returns the
        keyboard to what opened the sheet, so the traversal fix cannot be a blanket
        hideSheet that drops focus to the document."""
        self.pick_orion()
        self.open_first_film()
        opened = self.state()
        self.assertFalse(opened["hidden"])
        self.page.keyboard.press("Escape")
        closed = self.state()
        self.assertTrue(closed["hidden"], "Escape no longer closes the sheet")
        self.assertFalse(closed["behindInert"])
        self.assertNotEqual(closed["focus"], "",
                            "focus fell to the document instead of the card")


class PickersStayModal(Browser):
    """Three modals drive one `inert` flag on the page behind them.

    The month picker, the venue picker and the movie sheet all call
    `BEHIND().forEach(el => setInert(el, ...))`, so whichever closes last decides what the
    page behind is. `hideSheet` clears that flag whether or not the sheet was the thing
    that set it, and `onPopState` calls `hideSheet` on every traversal, so a Back pressed
    with a picker open left a `role="dialog" aria-modal="true"` over a fully tabbable page
    whose keydown handler still swallowed Escape and the arrows.
    """

    def behind(self):
        return self.page.evaluate("""() => ({
            main: !!document.querySelector('main').inert,
            header: !!document.querySelector('header').inert,
            venueOpen: document.querySelector('#vwrap').classList.contains('open'),
            calOpen: !!document.querySelector('.calwrap, #calwrap'),
        })""")

    def test_back_with_the_venue_picker_open_leaves_it_modal(self):
        self.pick_orion()
        self.open_picker()
        opened = self.behind()
        self.assertTrue(opened["venueOpen"] and opened["main"] and opened["header"],
                        "the picker should be open over an inert page")
        self.page.go_back()
        after = self.behind()
        if after["venueOpen"]:
            self.assertTrue(after["main"] and after["header"],
                            "the picker is still open and the page behind it is not inert")
        else:
            self.assertFalse(after["main"] or after["header"],
                             "the picker closed and left the page inert")

    def test_closing_the_venue_picker_after_a_traversal_still_clears_inert(self):
        """The counterweight: whatever the fix does, the ordinary close must still hand
        the page back."""
        self.pick_orion()
        self.open_picker()
        self.page.go_back()
        self.page.keyboard.press("Escape")
        expect(self.page.locator("#vwrap")).not_to_have_class("vwrap open")
        after = self.behind()
        self.assertFalse(after["main"] or after["header"])

    def test_a_traversal_with_no_modal_open_leaves_the_page_alone(self):
        self.pick_orion()
        self.page.go_back()
        after = self.behind()
        self.assertFalse(after["main"] or after["header"])


if __name__ == "__main__":
    unittest.main()


class AsyncRaces(Browser):
    """Two awaits with no identity guard let a stale reply win.

    `showSheet` awaited `ensureFilms()` and then `extra.ensure()` and checked nothing in
    between, so closing the sheet or opening another film while the metadata loaded let
    the first call run to the end: it reopened a dialog the reader had dismissed, or drew
    film A over film B. `loadSchedule` already numbered its loads; what it did not do was
    read the day it was loading for before the await.

    The server's per-path `delay` is the deferred promise here: `films.json` is fetched
    only by `showSheet`, so delaying it holds both calls open at a point the test controls,
    without a sleep in the page or a stub over the app's own code.
    """

    def slow(self, suffix, secs=1.5):
        self.srv.requested.clear()
        Handler.delay = {suffix: secs}
        self.addCleanup(lambda: setattr(Handler, "delay", {}))

    def wait_in_flight(self, suffix, timeout=10):
        """Block until the delayed request has reached the server. `requested` is logged
        before the sleep, so this is the moment the page is inside the await and the race
        window is open -- a condition, not a guess at how long the page needs."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if any(p.endswith(suffix) for p in self.srv.requested):
                return
            time.sleep(0.02)
        raise AssertionError(f"{suffix} was never requested; the race never opened")

    def sheet_open(self):
        return self.page.evaluate("() => document.body.classList.contains('sheet-open')")

    def test_closing_the_sheet_while_its_metadata_loads_leaves_it_closed(self):
        self.pick_orion()
        self.slow("films.json")
        # Two separate evaluates on purpose. `syncSheet` reads `location.hash` when the
        # event fires, not the value that caused it, so two assignments in one task are
        # both answered with the final hash and the first sheet never opens at all -- the
        # first version of this test raced nothing and passed against the unguarded code.
        self.page.evaluate("() => { location.hash = 'm=autofiktio'; }")
        self.wait_in_flight("films.json")
        self.page.evaluate("() => { location.hash = ''; }")
        self.page.wait_for_timeout(2500)          # past the delay, so the reply has landed
        self.assertFalse(self.sheet_open(), "a dismissed sheet was reopened by a stale load")

    def test_a_slow_venue_load_does_not_render_over_a_newer_pick(self):
        """Promenadi Pori is held open while the reader goes back to Orion, whose payload
        is already in `jsonCache` and renders at once."""
        self.pick_orion()
        first = self.page.locator("a.stub").first.get_attribute("href")
        self.slow("area-1004.json")
        vq = self.open_picker()
        vq.fill("promenadi")
        rows = self.page.locator("#vlist .vrow")
        expect(rows).to_have_count(1)
        vq.press("Enter")
        # Straight back to Orion while Pori is still in flight.
        vq2 = self.open_picker()
        vq2.fill("orion")
        expect(self.page.locator("#vlist .vrow")).to_have_count(1)
        vq2.press("Enter")
        expect(self.page.locator("#areaSelect")).to_contain_text("Cinema Orion")
        self.page.wait_for_timeout(2500)          # Pori's reply lands here
        expect(self.page.locator("#areaSelect")).to_contain_text("Cinema Orion")
        self.assertEqual(self.page.locator("a.stub").first.get_attribute("href"), first,
                         "a stale venue load rendered over the newer pick")

    def test_a_slow_failing_load_does_not_cover_a_newer_selection(self):
        """The failure path needs the same guard: an error screen drawn for an abandoned
        selection replaces a schedule the reader is looking at."""
        self.pick_orion()
        self.slow("area-1004.json")
        vq = self.open_picker()
        vq.fill("promenadi")
        expect(self.page.locator("#vlist .vrow")).to_have_count(1)
        vq.press("Enter")
        vq2 = self.open_picker()
        vq2.fill("orion")
        expect(self.page.locator("#vlist .vrow")).to_have_count(1)
        vq2.press("Enter")
        expect(self.page.locator("a.stub").first).to_be_visible()
        self.page.wait_for_timeout(2500)
        expect(self.page.locator("a.stub").first).to_be_visible()


class LoadLeavesNoOldVenue(Browser):
    """Until a load lands, nothing on the page may come from the venue the reader left.

    `loadSchedule` drew the error or the spinner and left `state` holding the previous
    venue's shows, stamp and sources. A filter tap, a search, a view switch or a language
    switch calls `render()`, which drew Orion's films and ticket links under Promenadi's
    name, and the footer kept Orion's stamp. Promenadi's file fails outright, arrives
    malformed, or is held in flight. The footer is checked empty rather than for Orion's
    name: redrawn from Orion's stamp it names Promenadi's provider, with Orion's time.
    """

    def pick_promenadi(self):
        vq = self.open_picker(); vq.fill("promenadi")
        expect(self.page.locator("#vlist .vrow")).to_have_count(1)
        vq.press("Enter")
        expect(self.page.locator("#areaSelect")).to_contain_text("Promenadi")

    def orion_on_screen(self):
        return self.page.evaluate("""() => ({
            links: [...document.querySelectorAll('main a[href*="cinemaorion.fi"]')].length,
            credit: document.querySelector('#credit').textContent,
            main: document.querySelector('main').textContent,
        })""")

    def assert_no_orion(self, when):
        got = self.orion_on_screen()
        self.assertEqual(got["links"], 0, f"{when}: Orion's ticket links drawn under Promenadi")
        self.assertEqual(got["credit"], "",
                         f"{when}: the footer claims a freshness for data not on screen")

    def test_a_failed_load_leaves_nothing_of_the_last_venue_to_redraw(self):
        self.pick_orion()
        self.assertIn("Orion", self.orion_on_screen()["credit"],
                      "the footer must carry a credit first or this proves nothing")
        Handler.fail = {"area-1004.json"}
        self.addCleanup(lambda: setattr(Handler, "fail", set()))
        self.pick_promenadi()
        err = self.page.locator("main .status", has_text="Näytöstietoja ei juuri nyt saatu")
        expect(err).to_be_visible()
        self.assert_no_orion("after the failure")
        self.page.locator("#chipKids").click()
        self.assert_no_orion("after Lapsille")
        expect(err).to_be_visible()
        self.page.locator("#chipKids").click()
        self.page.locator("#search").fill("a")
        self.assert_no_orion("after a search")
        self.page.locator("#search").fill("")
        self.page.locator("#segTimes").click()
        self.assert_no_orion("after Ajat")
        self.assertEqual(self.page.locator(".trow").count(), 0, "Orion's times drawn in Ajat")
        self.page.locator('#langSeg button[data-lang="sv"]').click()
        expect(self.page.locator("main .status", has_text="Visningstiderna kunde inte")).to_be_visible()
        self.assert_no_orion("after a language switch")

    def test_a_payload_that_throws_after_parsing_leaves_no_stamp(self):
        """Parsed, stamped, and missing `shows`: `state` is part filled when the load
        throws, and a language switch redraws the footer from whatever is left."""
        self.pick_orion()
        Handler.body = {"area-1004.json": b'{"generated": "2026-09-14T08:00:00+00:00"}'}
        self.addCleanup(lambda: setattr(Handler, "body", {}))
        self.pick_promenadi()
        expect(self.page.locator("main .status", has_text="Näytöstietoja ei juuri nyt saatu")).to_be_visible()
        self.page.locator('#langSeg button[data-lang="sv"]').click()
        expect(self.page.locator("main .status", has_text="Visningstiderna kunde inte")).to_be_visible()
        self.assert_no_orion("after a malformed payload and a language switch")

    def test_a_language_switch_while_the_next_venue_loads_draws_none_of_the_last(self):
        self.pick_orion()
        arrived, gate = threading.Event(), threading.Event()
        Handler.hold = {"area-1004.json": (arrived, gate)}
        self.addCleanup(lambda: (gate.set(), setattr(Handler, "hold", {})))
        self.pick_promenadi()
        self.assertTrue(arrived.wait(10), "Promenadi's file was never requested")
        self.page.locator('#langSeg button[data-lang="sv"]').click()
        expect(self.page.locator('#langSeg button[data-lang="sv"]')).to_have_attribute("aria-pressed", "true")
        self.assert_no_orion("mid-load, after a language switch")
        expect(self.page.locator("main .status", has_text="Laddar visningstider")).to_be_visible()
        self.page.locator("#chipKids").click()
        self.assert_no_orion("mid-load, after Lapsille")
        self.page.locator("#chipKids").click()
        gate.set()
        expect(self.page.locator("article.movie", has_text="Porin oma elokuva")).to_be_visible()
        self.assertEqual(self.orion_on_screen()["links"], 0, "Orion's links beside Promenadi's")
        expect(self.page.locator("#credit")).to_contain_text("Finnkino")


class LanguageSwitchKeepsTheDay(Browser):
    """A language switch redraws the day chips and must not move the day under the list.

    `applyLang` rebuilt the chips from the saved day, which `savedDay` drops once it is past
    the venue's horizon, and then called `render()` on the list loaded for the old day. So
    6.10. at Orion, then Promenadi (horizon 17.9.), then a switch to Swedish, highlighted
    today over an empty list saying nothing more was on today, while Promenadi has an 18:00
    today. A second tab writing the saved day did the same with the list of the day before.
    """

    def pick_promenadi(self):
        vq = self.open_picker(); vq.fill("promenadi")
        expect(self.page.locator("#vlist .vrow")).to_have_count(1)
        vq.press("Enter")
        expect(self.page.locator("#areaSelect")).to_contain_text("Promenadi")

    def chips(self):
        return self.page.evaluate("""() => [...document.querySelectorAll('#days .day')].map(b => ({
            text: b.textContent, active: b.classList.contains('active'),
            current: b.getAttribute('aria-current')}))""")

    def test_a_day_past_the_new_venue_s_horizon_survives_a_language_switch(self):
        self.pick_orion()
        self.page.locator('#days .day[aria-haspopup="dialog"]').click()
        self.page.locator('.cal-nav[data-mon="1"]').click()
        self.page.locator('.cal-day[data-day="2026-10-06"]').click()
        expect(self.page.locator("a.stub").first).to_be_visible()
        self.pick_promenadi()
        expect(self.page.locator("main .status",
                                 has_text="ohjelmistoa ei ole vielä julkaistu")).to_be_visible()
        self.page.locator('#langSeg button[data-lang="sv"]').click()
        expect(self.page.locator('#langSeg button[data-lang="sv"]')).to_have_attribute("aria-pressed", "true")
        expect(self.page.locator("main .status",
                                 has_text="har inte publicerats ännu")).to_be_visible()
        active = [c for c in self.chips() if c["active"]]
        self.assertEqual(len(active), 1, active)
        self.assertIn("6.10.", active[0]["text"], "the picked day moved under a language switch")
        self.assertNotIn("Inga fler visningar i dag", self.page.locator("main").text_content())

    def test_a_day_another_tab_saved_does_not_replace_the_one_on_screen(self):
        self.pick_orion()
        today = [c for c in self.chips() if c["active"]]
        self.assertEqual(today[0]["current"], "date")
        self.assertIn("14.9.", today[0]["text"])
        # What another tab's pick leaves behind: the same key, a later day.
        self.page.evaluate("""() => { const p = JSON.parse(localStorage.getItem('kino-prefs') || '{}');
            p.day = '2026-09-23'; localStorage.setItem('kino-prefs', JSON.stringify(p)); }""")
        self.page.locator('#langSeg button[data-lang="en"]').click()
        expect(self.page.locator('#langSeg button[data-lang="en"]')).to_have_attribute("aria-pressed", "true")
        active = [c for c in self.chips() if c["active"]]
        self.assertEqual(len(active), 1, active)
        self.assertIn("14.9.", active[0]["text"], "the chip left the day the list shows")
        hrefs = self.page.locator("a.stub").evaluate_all("as => as.map(a => a.href)")
        self.assertTrue(hrefs)
        self.assertEqual(set(hrefs) - TODAY_URLS, set(), "the list is not today's")

    def test_a_day_that_has_passed_is_reloaded_rather_than_kept(self):
        """Past midnight with no rollover yet: 14.9. is gone, so the switch moves the chips
        to the new today, and the list has to be loaded for it rather than kept."""
        self.pick_orion()
        self.page.clock.set_system_time(FIXED + datetime.timedelta(days=1))
        self.page.locator('#langSeg button[data-lang="en"]').click()
        expect(self.page.locator('#langSeg button[data-lang="en"]')).to_have_attribute("aria-pressed", "true")
        active = [c for c in self.chips() if c["active"]]
        self.assertEqual(len(active), 1, active)
        self.assertNotIn("14.9.", active[0]["text"])
        expect(self.page.locator("a.stub").first).to_be_visible()
        hrefs = self.page.locator("a.stub").evaluate_all("as => as.map(a => a.href)")
        self.assertEqual(set(hrefs) & TODAY_URLS, set(), "14.9.'s list under another day")


class ChooserResumeRollsOver(Browser):
    """A tab resumed on the chooser past midnight builds the new day's chips.

    The resume handler returned on `!state.area` before its rollover check, so a chooser
    left open overnight kept yesterday's chips and `state.dateStr`: picking Orion then drew
    "Tänään" over yesterday's date and a list for a day that had passed (audit K1,
    2026-09-25). The same resume on a venue view already rolled over.
    """

    def chips(self):
        return self.page.evaluate("""() => [...document.querySelectorAll('#days .day')].map(b => ({
            text: b.textContent, active: b.classList.contains('active')}))""")

    def test_resuming_on_the_chooser_after_midnight_moves_the_chips_to_the_new_day(self):
        # Boot builds the chips again once the venue lists land, so the resume has to come
        # after that or boot's own rebuild hides the bug. The picker opening is the only
        # sign the lists are in (see open_picker).
        self.open_picker()
        self.page.keyboard.press("Escape")
        expect(self.page.locator("#vwrap")).not_to_have_class("vwrap open")
        expect(self.page.locator("#days .day").first).to_contain_text("14.9.")
        self.page.clock.set_system_time(FIXED + datetime.timedelta(days=1))
        self.page.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")
        expect(self.page.locator("#days .day").first).to_contain_text("15.9.")
        self.pick_orion()
        chips = self.chips()
        self.assertIn("15.9.", chips[0]["text"], "the first chip is the new today")
        active = [c for c in chips if c["active"]]
        self.assertEqual(len(active), 1, active)
        # Orion may have nothing left on 15.9. at noon, and then the pick moves on to
        # its next day; never back to 14.9.
        self.assertNotIn("14.9.", active[0]["text"])
        hrefs = self.page.locator("a.stub").evaluate_all("as => as.map(a => a.href)")
        self.assertEqual(set(hrefs) & TODAY_URLS, set(), "14.9.'s list after the rollover")


class ChooserResumeRollsOverOnAPhone(ChooserResumeRollsOver):
    """The installed PWA is the case that resumes rather than reloads."""
    viewport = {"width": 375, "height": 812}; touch = True


class VenueListsAfterAFailedBoot(Browser):
    """Venue lists that failed at boot are fetched again on the next resume.

    `areas.json` answering 500 at launch left `allVenues` empty for the life of the tab:
    the picker trigger returned at once and nothing fetched the lists again, and an
    installed PWA has no reload control (audit K2, 2026-09-25).
    """

    def setUp(self):
        Handler.fail = {"areas.json"}
        self.addCleanup(lambda: setattr(Handler, "fail", set()))
        super().setUp()

    def test_the_next_resume_fetches_the_lists_and_the_picker_opens(self):
        # The boot's one request for the list, answered 500. No DOM signal says the boot
        # has given up, so the wait is on the server's own log, bounded like every wait.
        deadline = time.monotonic() + 10
        while not any(p.split("?")[0].endswith("/data/areas.json") for p in self.srv.requested):
            self.assertLess(time.monotonic(), deadline, "areas.json was never requested")
            self.page.wait_for_timeout(50)
        self.page.locator("#areaSelect").click()
        expect(self.page.locator("#vwrap")).not_to_have_class("vwrap open")
        Handler.fail = set()
        self.page.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")
        self.pick_orion()


class VenueListsAfterAFailedBootOnAPhone(VenueListsAfterAFailedBoot):
    viewport = {"width": 375, "height": 812}; touch = True


class ResumeRefresh(Browser):
    """A resume runs one refresh at a time, and a venue list that failed at boot joins a
    closed picker. Two flips inside one refresh each started one, and the lists a resume
    fetched were dropped, so a provider missing at boot stayed missing (prior review #14).
    """

    def setUp(self):
        Handler.fail = {"venues-orion.json"}
        Handler.delay = {"areas.json": 0, "area-1004.json": 0}      # no-store: asked again
        self.addCleanup(lambda: setattr(Handler, "fail", set()))
        self.addCleanup(lambda: setattr(Handler, "delay", {}))
        self.addCleanup(lambda: setattr(Handler, "hold", {}))
        super().setUp()
        self.page.goto(self.origin + "/index.html?area=1004")
        expect(self.page.locator("#main article.movie").first).to_be_visible()

    def resume(self, minutes=11):
        self.page.clock.set_system_time(FIXED + datetime.timedelta(minutes=minutes))
        self.page.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")

    def asked(self, name, since):
        return [p for p in self.srv.requested[since:] if p.split("?")[0].endswith("/data/" + name)]

    def refreshed(self, since):
        """The schedule's refetch is a refresh's last request."""
        deadline = time.monotonic() + 10
        while not self.asked("area-1004.json", since):
            self.assertLess(time.monotonic(), deadline, "the resume refetched nothing")
            self.page.wait_for_timeout(50)

    def orion_rows(self):
        self.open_picker().fill("orion")
        n = self.page.locator("#vlist .vrow").count()
        self.page.locator("#vclose").click()
        return n

    def test_two_resumes_inside_one_refresh_run_it_once(self):
        arrived, gate = threading.Event(), threading.Event()
        Handler.hold = {"areas.json": (arrived, gate)}
        mark = len(self.srv.requested)
        self.resume()
        self.assertTrue(arrived.wait(10), "the resume never asked for the lists")
        self.page.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")
        gate.set()
        self.refreshed(mark)
        self.assertEqual(len(self.asked("areas.json", mark)), 1)

    def test_a_list_that_failed_at_boot_reaches_the_picker(self):
        self.assertEqual(self.orion_rows(), 0)
        Handler.fail = set()
        mark = len(self.srv.requested)
        self.resume()
        self.refreshed(mark)
        self.assertEqual(self.orion_rows(), 1)

    def test_an_open_picker_is_left_alone_and_the_next_resume_repairs(self):
        vq = self.open_picker()
        Handler.fail = set()
        mark = len(self.srv.requested)
        self.resume()
        self.refreshed(mark)
        vq.fill("orion")
        self.assertEqual(self.page.locator("#vlist .vrow").count(), 0)
        self.page.locator("#vclose").click()
        mark = len(self.srv.requested)
        self.resume(minutes=22)
        self.refreshed(mark)
        self.assertEqual(self.orion_rows(), 1)

    def test_a_list_that_fails_on_resume_keeps_its_venues(self):
        """The counterweight: lists that lost a provider the picker holds are not taken,
        or the venue on screen could leave the picker."""
        Handler.body = {"venues-kinoset.json": json.dumps({"venues": [
            {"id": "ks-testi", "name": "Kino Testi", "short": "Kino Testi", "city": "Lahti"}]}
        ).encode("utf-8")}
        self.addCleanup(lambda: setattr(Handler, "body", {}))
        self.page.goto(self.origin + "/index.html?area=1004")
        expect(self.page.locator("#main article.movie").first).to_be_visible()
        Handler.fail = {"venues-kinoset.json"}
        mark = len(self.srv.requested)
        self.resume()
        self.refreshed(mark)
        self.assertEqual(self.orion_rows(), 0)
        self.open_picker().fill("testi")
        self.assertEqual(self.page.locator("#vlist .vrow").count(), 1)


class ResumeRefreshOnAPhone(ResumeRefresh):
    viewport = {"width": 375, "height": 812}; touch = True


class TimesViewChainLegend(Browser):
    """Ajat draws the chain legend whenever it lists more than one chain.

    The chain filter set in Leffat still hid rows in Ajat, but Ajat drew the legend only
    on an empty list, so a city view with Orion isolated showed Orion's rows, no legend
    and no "Kaikki" to undo it (audit K4, 2026-09-25). CLAUDE.md says both combined views
    print one. A second chain comes from Promenadi's fixture file served as Itis Helsinki.
    """

    def setUp(self):
        doc = json.loads((FIXTURE / "data/area-1004.json").read_text(encoding="utf-8"))
        for sh in doc["shows"]:
            sh["venue"] = "1162"
        Handler.body = {"area-1162.json": json.dumps(doc).encode("utf-8")}
        self.addCleanup(lambda: setattr(Handler, "body", {}))
        super().setUp()

    def test_the_legend_is_drawn_and_undoes_the_chain_filter(self):
        self.page.goto(self.origin + "/index.html?area=city:Helsinki")
        expect(self.page.locator("#main a.stub").first).to_be_visible()
        legend = self.page.locator("#main .legend.top .lg-btn:not(.lg-all)")
        expect(legend).to_have_count(2)                      # Leffat, as before
        legend.filter(has_text="Orion").click()
        self.page.locator("#segTimes").click()
        expect(self.page.locator("#main .trow").first).to_be_visible()
        expect(legend).to_have_count(2)
        expect(self.page.locator("#main .legend.top .lg-all")).to_be_visible()
        self.assertEqual(self.page.locator("#main .trow.chain-finnkino, #main .trow .chain-finnkino").count(), 0)
        self.page.locator("#main .legend.top .lg-all").click()
        expect(self.page.locator("#main .legend.top .lg-all")).to_have_count(0)


class TimesViewChainLegendOnAPhone(TimesViewChainLegend):
    viewport = {"width": 375, "height": 812}; touch = True


class ChainFilterEmptiesTheList(Browser):
    """A list the chain filter emptied says so, and keeps its legend in Leffat.

    `emptyMsg` ignored `state.chains`: with Finnkino isolated, 16.9., which only Orion
    plays, read "Valitussa teatterissa ei ole näytöksiä ke 16.9." (prior review #27).
    Leffat's empty list also dropped the legend Ajat's keeps. Promenadi's fixture file is
    served as Itis Helsinki for a second chain, as in TimesViewChainLegend.
    """
    NOMATCH = "Valitulle päivälle ei löytynyt näytöksiä näillä hakuehdoilla."

    def setUp(self):
        doc = json.loads((FIXTURE / "data/area-1004.json").read_text(encoding="utf-8"))
        for sh in doc["shows"]:
            sh["venue"] = "1162"
        Handler.body = {"area-1162.json": json.dumps(doc).encode("utf-8")}
        self.addCleanup(lambda: setattr(Handler, "body", {}))
        super().setUp()

    def status(self):
        return self.page.locator("#main .status").first

    def test_a_day_the_isolated_chain_skips_blames_the_filter(self):
        self.page.goto(self.origin + "/index.html?area=city:Helsinki")
        expect(self.page.locator("#main a.stub").first).to_be_visible()
        self.page.locator("#main .legend.top .lg-btn", has_text="Finnkino").click()
        self.page.locator("#days .day", has_text="16.9.").first.click()
        expect(self.status()).to_contain_text(self.NOMATCH)
        expect(self.status()).to_contain_text("Suodattimet: Finnkino")
        self.assertNotIn("ei ole näytöksiä", self.status().text_content())
        self.page.locator("#segTimes").click()
        expect(self.status()).to_contain_text(self.NOMATCH)

    def test_the_legend_stays_above_an_emptied_list(self):
        self.page.goto(self.origin + "/index.html?area=city:Helsinki")
        expect(self.page.locator("#main a.stub").first).to_be_visible()
        self.page.locator("#main .legend.top .lg-btn", has_text="Orion").click()
        self.page.locator("#search").fill("qqqq")
        expect(self.status()).to_contain_text(self.NOMATCH)
        expect(self.page.locator("#main .legend.top .lg-btn:not(.lg-all)")).to_have_count(2)
        self.page.locator("#main .legend.top .lg-all").click()
        expect(self.page.locator("#main .legend.top .lg-all")).to_have_count(0)
        expect(self.status()).not_to_contain_text("Finnkino")


class ChainFilterEmptiesTheListOnAPhone(ChainFilterEmptiesTheList):
    viewport = {"width": 375, "height": 812}; touch = True


class ChainPickOnAnotherDay(Browser):
    """A chain picked on a day without the isolated one adds to the pick.

    `toggleChain` cleared the filter when the pick's size equalled the day's chain count,
    so with Finnkino isolated, one click on Orion on 16.9. (Orion and Riviera, no Finnkino)
    counted two of two, showed both chains and dropped the Finnkino pick (prior review #27).
    Three Helsinki chains: Promenadi's fixture as Itis, Orion, and Orion's rows as Riviera
    Kallio, whose venue list is served here too.
    """

    def setUp(self):
        itis = json.loads((FIXTURE / "data/area-1004.json").read_text(encoding="utf-8"))
        for sh in itis["shows"]:
            sh["venue"] = "1162"
        riviera = json.loads((FIXTURE / "data/area-or-helsinki.json").read_text(encoding="utf-8"))
        for sh in riviera["shows"]:
            sh.update(provider="riviera", venue="rv-kallio", url=sh["url"] + "&rv=1")
        venues = {"generated": riviera["generated"], "oldest": riviera["generated"],
                  "status": "ok", "stale": [], "unverified": [], "pending": [],
                  "provider": "riviera", "venues": [{"id": "rv-kallio", "name": "Riviera Kallio",
                                                     "short": "Kallio", "city": "Helsinki"}]}
        Handler.body = {"area-1162.json": json.dumps(itis).encode("utf-8"),
                        "area-rv-kallio.json": json.dumps(riviera).encode("utf-8"),
                        "venues-riviera.json": json.dumps(venues).encode("utf-8")}
        self.addCleanup(lambda: setattr(Handler, "body", {}))
        super().setUp()

    def chains_shown(self):
        return sorted(set(self.page.locator("#main a.stub").evaluate_all(
            "els => els.map(a => a.dataset.prov)")))

    def legend(self, name):
        return self.page.locator("#main .legend.top .lg-btn", has_text=name)

    def day(self, dm):
        self.page.locator("#days .day", has_text=dm).first.click()

    def pick_on_another_day(self, view):
        self.page.goto(self.origin + "/index.html?area=city:Helsinki")
        expect(self.page.locator("#main a.stub").first).to_be_visible()
        if view == "times":
            self.page.locator("#segTimes").click()
        self.legend("Finnkino").click()
        self.day("16.9.")
        expect(self.legend("Riviera")).to_have_count(1)
        self.assertEqual(self.chains_shown(), [])
        self.legend("Orion").click()
        expect(self.page.locator("#main a.stub").first).to_be_visible()
        self.assertEqual(self.chains_shown(), ["orion"], "one click showed every chain")
        expect(self.page.locator("#main .legend.top .lg-all")).to_be_visible()
        expect(self.legend("Orion")).to_have_attribute("aria-pressed", "true")
        expect(self.legend("Riviera")).to_have_attribute("aria-pressed", "false")
        self.day("17.9.")
        expect(self.page.locator("#main a.stub").first).to_be_visible()
        self.assertEqual(self.chains_shown(), ["finnkino", "orion"], "the Finnkino pick was dropped")

    def test_leffat(self):
        self.pick_on_another_day("list")

    def test_ajat(self):
        self.pick_on_another_day("times")

    def test_turning_the_days_last_pick_off_clears_the_filter(self):
        """The rule's other half, unchanged: no chain of the day picked means no filter."""
        self.pick_on_another_day("list")
        self.day("16.9.")
        self.legend("Orion").click()
        expect(self.page.locator("#main .legend.top .lg-all")).to_have_count(0)
        self.assertEqual(self.chains_shown(), ["orion", "riviera"])


class ChainPickOnAnotherDayOnAPhone(ChainPickOnAnotherDay):
    viewport = {"width": 375, "height": 812}; touch = True


class EmptyDayNamesItsDay(Browser):
    """The Finnish empty-day line names the selected day by its chip's label.

    `noshows` said "tänään", and `emptyMsg` returns it only for a day that is not today:
    Orion on "Huomenna 15.9." read "Valitussa teatterissa ei ole näytöksiä tänään."
    (audit K5, 2026-09-25). Today keeps its own line, an unpublished day its own, and the
    Swedish and English lines already said "this day" and are unchanged. A language switch
    redraws the line through `applyLang`.
    """

    def status(self):
        return self.page.locator("main .status").first

    def line(self):
        """The message alone, without the next-day link drawn after it."""
        return self.status().evaluate("e => e.firstChild.textContent.trim()")

    def day(self, dm):
        self.page.locator("#days .day", has_text=dm).first.click()

    def test_the_selected_day_is_named_and_the_other_messages_stay_apart(self):
        self.pick_orion()
        self.day("15.9.")
        expect(self.status()).to_contain_text("Valitussa teatterissa ei ole näytöksiä huomenna.")
        self.assertNotIn("tänään", self.status().text_content())
        self.day("18.9.")
        expect(self.status()).to_contain_text("Valitussa teatterissa ei ole näytöksiä pe 18.9.")
        self.assertEqual(self.line(), "Valitussa teatterissa ei ole näytöksiä pe 18.9.",
                         "one full stop, the date's own")
        self.page.locator('#langSeg button[data-lang="sv"]').click()
        expect(self.status()).to_contain_text("Inga visningar denna dag på vald biograf.")
        self.page.locator('#langSeg button[data-lang="en"]').click()
        expect(self.status()).to_contain_text("No shows for this day at the selected theatre.")
        self.page.locator('#langSeg button[data-lang="fi"]').click()
        expect(self.status()).to_contain_text("ei ole näytöksiä pe 18.9.")

    def test_a_day_past_the_horizon_keeps_the_unpublished_line(self):
        """6.10. at Orion, then Promenadi, whose schedule ends 17.9.: the day is not empty,
        it is unpublished, and says so. The path LanguageSwitchKeepsTheDay takes."""
        self.pick_orion()
        self.page.locator('#days .day[aria-haspopup="dialog"]').click()
        self.page.locator('.cal-nav[data-mon="1"]').click()
        self.page.locator('.cal-day[data-day="2026-10-06"]').click()
        expect(self.page.locator("a.stub").first).to_be_visible()
        vq = self.open_picker(); vq.fill("promenadi")
        expect(self.page.locator("#vlist .vrow")).to_have_count(1)
        vq.press("Enter")
        expect(self.status()).to_contain_text("ohjelmistoa ei ole vielä julkaistu")
        self.assertNotIn("ei ole näytöksiä", self.status().text_content())


class EmptyDayNamesItsDayOnAPhone(EmptyDayNamesItsDay):
    viewport = {"width": 375, "height": 812}; touch = True

    def test_the_line_fits_the_phone(self):
        self.pick_orion()
        self.day("18.9.")
        expect(self.status()).to_contain_text("ei ole näytöksiä pe 18.9.")
        box = self.status().bounding_box()
        self.assertLessEqual(box["x"] + box["width"], 375)
        self.assertEqual(self.page.evaluate("document.documentElement.scrollWidth"), 375,
                         "the page scrolls sideways")
        self.page.screenshot(path=str(OUT / "k5-phone-375.png"))


class AutomaticDayJump(Browser):
    """The jump past an empty today moves the list and the chips and saves no day.

    It called `selectDay`, which saves the day in `kino-prefs` and tracks `date_changed`,
    although the reader chose nothing (prior review #28). Orion's fixture is served with
    14.9. removed, so the load moves to 16.9. A reader's chip and calendar picks still
    save the day. `date_changed` is not visible here, since analytics runs on the
    production origin only; `test_widen_load.py` records it.
    """

    def setUp(self):
        doc = json.loads((FIXTURE / "data/area-or-helsinki.json").read_text(encoding="utf-8"))
        doc["shows"] = [s for s in doc["shows"] if not s["start"].startswith("2026-09-14")]
        doc["dates"] = [d for d in doc["dates"] if d != "2026-09-14"]
        Handler.body = {"area-or-helsinki.json": json.dumps(doc).encode("utf-8")}
        self.addCleanup(lambda: setattr(Handler, "body", {}))
        super().setUp()

    def saved_day(self):
        return json.loads(self.page.evaluate("localStorage.getItem('kino-prefs') || '{}'")).get("day")

    def test_the_jump_moves_the_list_and_saves_nothing(self):
        self.page.goto(self.origin + "/index.html?area=or-helsinki")
        expect(self.page.locator("#main a.stub").first).to_be_visible()
        expect(self.page.locator("#days .day.active")).to_contain_text("16.9.")
        hrefs = self.page.locator("#main a.stub").evaluate_all("els => els.map(a => a.href)")
        day = {s["url"] for s in SHOWS if s["start"].startswith("2026-09-16")}
        self.assertTrue(hrefs)
        self.assertEqual(set(hrefs) - day, set(), "the list is not 16.9.'s")
        self.assertIsNone(self.saved_day())

    def test_a_readers_own_chip_and_calendar_pick_are_saved(self):
        self.page.goto(self.origin + "/index.html?area=or-helsinki")
        expect(self.page.locator("#days .day.active")).to_contain_text("16.9.")
        self.page.locator("#days .day", has_text="17.9.").first.click()
        expect(self.page.locator("#days .day.active")).to_contain_text("17.9.")
        self.assertEqual(self.saved_day(), "2026-09-17")
        self.page.locator('#days .day[aria-haspopup="dialog"]').click()
        self.page.locator('.cal-day[data-day="2026-09-23"]').click()
        expect(self.page.locator("#days .day.active")).to_contain_text("23.9.")
        self.assertEqual(self.saved_day(), "2026-09-23")


class AutomaticDayJumpOnAPhone(AutomaticDayJump):
    viewport = {"width": 375, "height": 812}; touch = True


class FilmOrderFollowsTheShownTitle(Browser):
    """Leffat sorts by the title each card shows.

    It sorted by `title`, the Finnish one, while English mode shows the English title
    (prior review #29). films.json gives Orion's "Autofiktio" an English title after
    "Oasis: Don", which has none and keeps its own.
    """
    FILMS = json.dumps({"films": {"autofiktio": {"t": {"en": "Zebra Road"}}}}).encode("utf-8")

    def setUp(self):
        Handler.body = {"films.json": self.FILMS}
        self.addCleanup(lambda: setattr(Handler, "body", {}))
        super().setUp()

    def titles(self):
        return self.page.locator("#main article.movie h2.title").all_text_contents()

    def test_english_titles_are_in_order(self):
        self.page.goto(self.origin + "/index.html?area=or-helsinki&lang=en")
        expect(self.page.locator("#main article.movie h2.title").first).to_have_text("Oasis: Don")
        self.assertEqual(self.titles(), ["Oasis: Don", "Zebra Road"])

    def test_finnish_keeps_the_finnish_order(self):
        self.page.goto(self.origin + "/index.html?area=or-helsinki&lang=en")
        expect(self.page.locator("#main article.movie h2.title", has_text="Zebra Road")).to_have_count(1)
        self.page.locator('#langSeg button[data-lang="fi"]').click()
        expect(self.page.locator("#main article.movie h2.title").first).to_have_text("Autofiktio")
        self.assertEqual(self.titles(), ["Autofiktio", "Oasis: Don"])


class FilmOrderFollowsTheShownTitleOnAPhone(FilmOrderFollowsTheShownTitle):
    viewport = {"width": 375, "height": 812}; touch = True


class GenreSearchInSwedish(Browser):
    """A genre is found by the name its card shows in every language.

    The search haystack held the Finnish and English TMDB genre names only, so in Swedish a
    card labelled "Äventyr" was not found by "äventyr" (audit K8, 2026-09-25). The genre
    names come from the committed `data/tmdb-genres.json`; Orion's fixture carries the ids.
    """

    def setUp(self):
        Handler.body = {"tmdb-genres.json": (ROOT / "data/tmdb-genres.json").read_bytes()}
        self.addCleanup(lambda: setattr(Handler, "body", {}))
        super().setUp()

    def titles(self):
        return self.page.locator("#main article.movie h2.title").all_text_contents()

    def test_a_swedish_genre_name_finds_the_film(self):
        self.pick_orion()
        self.page.locator('#langSeg button[data-lang="sv"]').click()
        expect(self.page.locator("#main article.movie", has_text="Äventyr")).to_have_count(1)
        self.page.locator("#search").fill("äventyr")
        expect(self.page.locator("#main article.movie")).to_have_count(1)
        self.assertIn("Oasis", " ".join(self.titles()))
        self.page.locator("#search").fill("komedi")
        expect(self.page.locator("#main article.movie").first).to_be_visible()
        self.page.locator("#search").fill("adventure")
        expect(self.page.locator("#main article.movie")).to_have_count(1)


class GenreSearchInSwedishOnAPhone(GenreSearchInSwedish):
    viewport = {"width": 375, "height": 812}; touch = True


class ThemeBeforeTheBody(Browser):
    """The stored theme is applied in <head>, before the body's script exists.

    The app set `data-theme` from the script at the end of the body, which runs only once
    the whole document has parsed, so a dark reader saw the light chooser first (audit K9,
    2026-09-25). Here the page is served with every <script> after <body> removed: whatever
    theme is on screen came from <head>. The full page is checked too, for a stored value
    that is neither theme.
    """

    def headless_page(self, stored, scheme):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        head, body = html.split("<body", 1)
        body = re.sub(r"<script\b[^>]*>.*?</script>", "", body, flags=re.S)
        self.page.route("**/index.html*", lambda r: r.fulfill(
            status=200, content_type="text/html; charset=utf-8", body=head + "<body" + body))
        self.page.emulate_media(color_scheme=scheme)
        self.page.evaluate(f"localStorage.setItem('kino-theme', {json.dumps(stored)})")
        self.page.goto(self.origin + "/index.html")

    def theme(self):
        return self.page.evaluate("document.documentElement.getAttribute('data-theme')")

    def background(self):
        return self.page.evaluate("getComputedStyle(document.body).backgroundColor")

    def test_a_stored_dark_theme_is_on_screen_with_no_body_script(self):
        self.headless_page("dark", "light")
        self.assertEqual(self.theme(), "dark")
        self.assertEqual(self.background(), "rgb(13, 14, 18)", "the dark --bg")

    def test_the_os_decides_when_nothing_valid_is_stored(self):
        self.headless_page("bogus", "dark")
        self.assertEqual(self.theme(), "dark")
        self.headless_page("bogus", "light")
        self.assertEqual(self.theme(), "light")

    def test_the_full_page_never_writes_an_unknown_stored_value(self):
        self.page.emulate_media(color_scheme="dark")
        self.page.evaluate("localStorage.setItem('kino-theme', 'sepia')")
        self.page.goto(self.origin + "/index.html")
        expect(self.page.locator("#themeToggle")).to_be_visible()
        self.assertEqual(self.theme(), "dark")


class MalformedStoredPrefs(Browser):
    """A stored preference of the wrong shape costs a prefetch, not the boot.

    `{"fav":"city:Helsinki","cityIds":{"city:Helsinki":{}}}` made boot's prefetch loop
    iterate an object and throw before anything was drawn: the chooser with "Näytöstietoja
    ei juuri nyt saatu ladattua." and no language buttons, on every load (audit K10,
    2026-09-25). A `fav` that is not a string threw the same way. Both now boot to the
    favourite, or to the chooser when there is none to open.
    """

    def boot_with(self, stored):
        self.page.evaluate(f"localStorage.setItem('kino-prefs', {json.dumps(json.dumps(stored))})")
        self.page.goto(self.origin + "/index.html")

    def test_a_city_entry_that_is_not_a_list_still_opens_the_favourite(self):
        self.boot_with({"fav": "city:Helsinki", "cityIds": {"city:Helsinki": {}}})
        expect(self.page.locator("#main a.stub").first).to_be_visible()
        expect(self.page.locator("#langSeg button")).to_have_count(3)
        self.assertNotIn("ei juuri nyt saatu ladattua", self.page.locator("#main").text_content())

    def test_a_list_of_the_wrong_things_still_opens_the_favourite(self):
        self.boot_with({"fav": "city:Helsinki", "cityIds": {"city:Helsinki": [7, None, "1004"]}})
        expect(self.page.locator("#main a.stub").first).to_be_visible()

    def test_a_favourite_that_is_not_a_string_opens_the_chooser(self):
        self.boot_with({"fav": 42})
        expect(self.page.locator("#home")).to_be_visible()
        expect(self.page.locator("#langSeg button")).to_have_count(3)
        self.assertNotIn("ei juuri nyt saatu ladattua", self.page.locator("#main").text_content())


class MalformedStoredPrefsOnAPhone(MalformedStoredPrefs):
    viewport = {"width": 375, "height": 812}; touch = True


class StatusPageStoredNull(Browser):
    """A stored `kino-prefs` of `null` no longer stops the status page.

    Its `prefs.get` returned what `JSON.parse` gave, so `prefs.get().lang` threw at boot and
    the page stayed on "Tarkistetaan…" with no language buttons (prior review #20).
    """

    def test_the_page_draws_its_summary_and_language_buttons(self):
        self.page.evaluate("localStorage.setItem('kino-prefs', 'null')")
        self.page.goto(self.origin + "/status/")
        expect(self.page.locator("#langSeg button")).to_have_count(3)
        expect(self.page.locator("#summaryTitle")).not_to_have_text("Tarkistetaan…")


class StatusPageStoredNullOnAPhone(StatusPageStoredNull):
    viewport = {"width": 375, "height": 812}; touch = True


class MetadataAfterAFailedRead(Browser):
    """A genre or title map that failed to load is read again on the next resume.

    `ensureGenres` stored `{}` on a failed read and `ensureFilms` stored `{}` too, so for the
    life of the tab every card kept the provider's own genre strings and an English reader
    saw every Finnkino film under its Finnish title; films.json was never read again even
    when it had loaded (audit K12, 2026-09-25). The fixture serves neither file at boot. A
    resume past the ten-minute refresh serves both: Orion's "Oasis: Don" publishes no
    genre string and gains TMDB's "Seikkailu", and Promenadi's film its English title.
    """

    GENRES = (ROOT / "data/tmdb-genres.json").read_bytes()
    FILMS = json.dumps({"films": {"promenadi-only-film": {"t": {"en": "Pori's Own Film"}}}}
                       ).encode("utf-8")

    def setUp(self):
        Handler.fail = {"tmdb-genres.json", "films.json"}
        self.addCleanup(lambda: setattr(Handler, "fail", set()))
        self.addCleanup(lambda: setattr(Handler, "body", {}))
        super().setUp()

    def resume(self):
        Handler.fail = set()
        Handler.body = {"tmdb-genres.json": self.GENRES, "films.json": self.FILMS}
        self.page.clock.set_system_time(FIXED + datetime.timedelta(minutes=11))
        self.page.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")

    def test_the_genre_names_arrive_on_the_next_resume(self):
        self.pick_orion()
        oasis = self.page.locator("#main article.movie", has_text="Oasis")
        expect(oasis).to_have_count(1)
        self.assertNotIn("Seikkailu", oasis.text_content())
        self.resume()
        expect(oasis).to_contain_text("Seikkailu")

    def test_the_english_titles_arrive_on_the_next_resume(self):
        self.page.goto(self.origin + "/index.html?area=1004&lang=en")
        film = self.page.locator("#main article.movie h2.title")
        expect(film.first).to_have_text("Porin oma elokuva")
        self.resume()
        expect(film.first).to_have_text("Pori's Own Film")

    def test_a_sheet_opened_later_reads_the_titles_again(self):
        """No resume: the sheet asks for films.json itself, and a failed boot read is no
        longer an answer it accepts."""
        self.page.goto(self.origin + "/index.html?area=1004&lang=en")
        film = self.page.locator("#main article.movie h2.title a")
        expect(film.first).to_have_text("Porin oma elokuva")
        Handler.fail = set()
        Handler.body = {"films.json": self.FILMS}
        film.first.click()
        expect(self.page.locator("#sheetTitle")).to_have_text("Pori's Own Film")

    def test_a_sheet_opened_while_the_titles_still_fail_opens_in_finnish(self):
        """films.json stays unread, so the map is null: the sheet reads it as empty."""
        self.page.goto(self.origin + "/index.html?area=1004&lang=en")
        film = self.page.locator("#main article.movie h2.title a")
        film.first.click()
        expect(self.page.locator("#sheetTitle")).to_have_text("Porin oma elokuva")
        expect(self.page.locator(".sheet-body a.stub").first).to_be_visible()


class MetadataAfterAFailedReadOnAPhone(MetadataAfterAFailedRead):
    viewport = {"width": 375, "height": 812}; touch = True


class CombinedVenueLists(Browser):
    """The venue lists come from the two combined files, one per half.

    The client asked for one `data/venues-{id}.json` per provider on every load (audit K6);
    it now asks for `data/venuelists-local.json` and `data/venuelists-cloud.json` and
    fetches a provider's own file only when neither carries it. The fixture has no combined
    file, so every other test here runs the fallback; these serve them.
    """
    ORION = json.loads((FIXTURE / "data/venues-orion.json").read_text(encoding="utf-8"))

    def serve(self, local, cloud):
        Handler.body = {k: v for k, v in (("venuelists-local.json", local),
                                          ("venuelists-cloud.json", cloud)) if v is not None}
        self.addCleanup(lambda: setattr(Handler, "body", {}))

    def singles(self):
        return [p for p in self.srv.requested if "/data/venues-" in p]

    def setUp(self):
        # Uncacheable, or the browser answers a second request for it from its own cache
        # and "never requested" would pass without the combined file doing anything.
        Handler.delay = {"venues-orion.json": 0}
        self.addCleanup(lambda: setattr(Handler, "delay", {}))
        super().setUp()
        self.srv.requested.clear()

    def test_the_picker_is_built_from_the_combined_files(self):
        self.serve(json.dumps({"half": "local", "providers": {}}).encode(),
                   json.dumps({"half": "cloud", "providers": {"orion": self.ORION}}).encode())
        self.page.goto(self.origin + "/index.html")
        self.srv.requested.clear()
        self.page.goto(self.origin + "/index.html?area=or-helsinki")
        expect(self.page.locator("a.stub").first).to_be_visible()
        self.pick_orion()
        self.assertTrue(any("/data/venuelists-cloud.json" in p for p in self.srv.requested))
        self.assertNotIn("/data/venues-orion.json",
                         [p.split("?")[0] for p in self.singles()])

    def test_a_broken_combined_file_falls_back_to_the_provider_file(self):
        self.serve(b'{"half": "local", "providers": {', None)
        self.page.goto(self.origin + "/index.html")
        self.srv.requested.clear()
        self.page.goto(self.origin + "/index.html?area=or-helsinki")
        expect(self.page.locator("a.stub").first).to_be_visible()
        self.pick_orion()
        self.assertIn("/data/venues-orion.json", [p.split("?")[0] for p in self.singles()])


class CombinedVenueListsOnAPhone(CombinedVenueLists):
    viewport = {"width": 375, "height": 812}; touch = True


class StatusPageCombinedVenueLists(Browser):
    """The status page reads the two combined venue files, like the app.

    It fetched one `venues-{id}.json` per provider for its health table. It now reads the
    combined file of each half and falls back to a provider's own file only when neither
    carries it. Each provider's row has to read exactly as it did from its own file.
    """
    ORION = json.loads((FIXTURE / "data/venues-orion.json").read_text(encoding="utf-8"))

    def setUp(self):
        Handler.delay = {"venues-orion.json": 0}        # never answered from the HTTP cache
        self.addCleanup(lambda: setattr(Handler, "delay", {}))
        self.addCleanup(lambda: setattr(Handler, "body", {}))
        super().setUp()

    def orion_row(self, body):
        Handler.body = body
        self.srv.requested.clear()
        self.page.goto(self.origin + "/status/")
        row = self.page.locator('details.provider[data-id="orion"] summary')
        expect(row).to_be_visible()
        singles = [p.split("?")[0] for p in self.srv.requested if "/data/venues-" in p]
        return row.inner_text(), singles

    def test_the_row_reads_the_same_from_the_combined_file_and_asks_for_no_single_file(self):
        own, own_singles = self.orion_row({})
        self.assertIn("/data/venues-orion.json", own_singles, "the fallback path, for reference")
        combined, singles = self.orion_row({
            "venuelists-cloud.json": json.dumps(
                {"half": "cloud", "providers": {"orion": self.ORION}}).encode()})
        self.assertEqual(combined, own)
        self.assertNotIn("/data/venues-orion.json", singles)

    def test_a_broken_combined_file_falls_back_for_its_half(self):
        own, _ = self.orion_row({})
        broken, singles = self.orion_row({"venuelists-cloud.json": b'{"half": "cloud", "prov',
                                          "venuelists-local.json": json.dumps(
                                              {"half": "local", "providers": {}}).encode()})
        self.assertEqual(broken, own)
        self.assertIn("/data/venues-orion.json", singles)


class StatusPageCombinedVenueListsOnAPhone(StatusPageCombinedVenueLists):
    viewport = {"width": 375, "height": 812}; touch = True


class ChooserNote(Browser):
    """The chooser's note is drawn in the language on screen.

    `showHome` stored the note already translated, so a link naming no known location,
    then EN, drew an English intro over "Linkin teatteria tai kaupunkia ei löytynyt." (audit
    K7, 2026-09-25). The note is now kept as its string's key and `renderHome` translates it.
    """

    def note(self):
        return self.page.locator("#homeNote")

    def switch(self, lang):
        self.page.locator(f'#langSeg button[data-lang="{lang}"]').click()


class ChooserNoteFollowsTheLanguage(ChooserNote):

    def test_the_unknown_location_note_is_redrawn_on_a_language_switch(self):
        self.page.goto(self.origin + "/index.html?area=nope")
        expect(self.note()).to_have_text(
            "Linkin teatteria tai kaupunkia ei löytynyt. Valitse toinen.")
        self.switch("en")
        expect(self.note()).to_have_text(
            "The cinema or city in the link was not found. Choose another.")
        self.switch("sv")
        expect(self.note()).to_have_text(
            "Biografen eller staden i länken hittades inte. Välj en annan.")
        self.switch("fi")
        expect(self.note()).to_contain_text("ei löytynyt")



class ChooserNoteFollowsTheLanguageOnAPhone(ChooserNoteFollowsTheLanguage):
    viewport = {"width": 375, "height": 812}; touch = True


class HomeCityLinks(Browser):
    """A homepage city link is the programme (2026-09-29, the maintainer's instruction): its
    href, once the venue lists are in, names the combined view for a city with two or more
    cinemas and the cinema for one, so a tap, a copied link and a new tab reach the same
    place. The static href is the city page, for a reader without script and a failed boot,
    and the same cities under "Kaupunkisivut" stay links to their pages, the homepage's
    rendered way into them. In the fixture Helsinki has five venues, Jyväskylä one and Forssa
    none."""

    def link(self, city):
        return self.page.locator(f'#home .cities a[data-city="{city}"]')

    def page_link(self, city):
        return self.page.locator(f'#home .cpages a[data-city="{city}"]')

    def lists_in(self):
        expect(self.link("Helsinki")).to_have_attribute("href", "/?area=city%3AHelsinki")

    def test_each_link_names_what_it_opens(self):
        self.lists_in()
        expect(self.link("Espoo")).to_have_attribute("href", "/?area=city%3AEspoo")
        expect(self.link("Jyväskylä")).to_have_attribute("href", "/?area=1095")
        expect(self.link("Forssa")).to_have_attribute("href", "/kaupunki/forssa/")

    def test_a_city_link_opens_the_combined_view_and_back_returns_to_the_chooser(self):
        """In place, as a pick from the picker: the page is not loaded again."""
        self.lists_in()
        self.page.evaluate("window.kinoSamePage = true")
        self.link("Helsinki").click()
        expect(self.page.locator("#areaSelect")).to_contain_text("Helsinki – kaikki teatterit")
        expect(self.page.locator("a.stub").first).to_be_visible()
        self.assertEqual(self.page.evaluate("location.search"), "?area=city%3AHelsinki")
        self.assertTrue(self.page.evaluate("window.kinoSamePage === true"))
        self.page.go_back()
        expect(self.page.locator("#homeMore")).to_be_visible()
        self.assertEqual(self.page.evaluate("location.search"), "")

    def test_a_city_with_one_cinema_opens_that_cinema(self):
        self.lists_in()
        self.link("Jyväskylä").click()
        expect(self.page.locator("#areaSelect")).to_contain_text("Fantasia")
        self.assertEqual(self.page.evaluate("location.search"), "?area=1095")

    def test_the_href_opens_the_same_view_in_a_new_tab(self):
        self.lists_in()
        tab = self.ctx.new_page()
        tab.clock.install(time=FIXED)
        tab.goto(self.origin + self.link("Helsinki").get_attribute("href"))
        expect(tab.locator("#areaSelect")).to_contain_text("Helsinki – kaikki teatterit")

    def test_a_modified_click_is_left_to_the_browser(self):
        self.lists_in()
        prevented = self.page.evaluate("""() => {
            const a = document.querySelector('#home .cities a[data-city="Helsinki"]');
            let seen = null;
            const spy = e => { seen = e.defaultPrevented; e.preventDefault(); };
            document.addEventListener('click', spy);
            a.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, ctrlKey: true}));
            document.removeEventListener('click', spy);
            return seen;
        }""")
        self.assertIs(prevented, False)
        expect(self.page.locator("#homeMore")).to_be_visible()

    def test_a_link_naming_what_the_lists_do_not_know_is_left_to_the_page_load(self):
        """An href from before a refresh of the lists: the load that follows says the
        location was not found, the same as any stale link."""
        self.lists_in()
        self.page.evaluate("document.querySelector('#home .cities a[data-city=\"Helsinki\"]')"
                           ".href = '/index.html?area=city%3ANowhere'")
        self.link("Helsinki").click()
        expect(self.page.locator("#homeNote")).to_have_text(
            "Linkin teatteria tai kaupunkia ei löytynyt. Valitse toinen.")

    def test_the_city_pages_are_one_tap_away(self):
        self.lists_in()
        expect(self.page_link("Helsinki")).to_be_hidden()
        self.page.locator("#home .cpages summary").click()
        expect(self.page_link("Helsinki")).to_be_visible()
        expect(self.page_link("Helsinki")).to_have_attribute("href", "/kaupunki/helsinki/")
        self.assertEqual(self.page.locator("#home .cpages a").count(),
                         self.page.locator("#home .cities a[data-city]").count())
        self.page_link("Helsinki").click()
        self.page.wait_for_url(self.origin + "/kaupunki/helsinki/")

    def test_a_language_switch_relabels_both_lists(self):
        self.lists_in()
        self.page.locator('#langSeg button[data-lang="sv"]').click()
        expect(self.link("Helsinki")).to_have_text("Helsingfors")
        expect(self.link("Helsinki")).to_have_attribute("href", "/?area=city%3AHelsinki")
        expect(self.page.locator("#home .cpages summary")).to_have_text("Stadssidor")
        expect(self.page_link("Helsinki")).to_have_attribute("href", "/sv/kaupunki/helsinki/")
        self.link("Helsinki").click()
        expect(self.page.locator("#areaSelect")).to_contain_text("Helsingfors – alla biografer")

    def test_without_script_both_lists_are_the_city_pages(self):
        ctx = self.browser.new_context(java_script_enabled=False, service_workers="block")
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        page.goto(self.origin + "/index.html")
        expect(page.locator('#home .cities a[data-city="Helsinki"]')).to_have_attribute(
            "href", "/kaupunki/helsinki/")
        page.locator("#home .cpages summary").click()
        expect(page.locator('#home .cpages a[data-city="Helsinki"]')).to_be_visible()
        page.locator('#home .cities a[data-city="Helsinki"]').click()
        page.wait_for_url(self.origin + "/kaupunki/helsinki/")


class HomeCityLinksOnAPhone(HomeCityLinks):
    viewport = {"width": 375, "height": 812}; touch = True


def phone_area(venue, provider, theatre, films):
    """An area file for the phone layout tests: `films` maps a title to its (clock, aud,
    lang) screenings on the fixture's day."""
    shows = [{"eventId": title, "title": title, "original": "", "len": "100", "rating": "",
              "genres": "Draama", "img": "", "method": "", "theatre": theatre, "aud": aud,
              "lang": lang, "start": f"2026-09-14T{clock}:00+03:00", "soldOut": False,
              "price": "10€", "provider": provider, "venue": venue,
              "url": f"https://example.invalid/{venue}/{title}/{clock}"}
             for title, times in films.items() for clock, aud, lang in times]
    return json.dumps({"generated": "2026-09-14T08:00:00+00:00", "dates": ["2026-09-14"],
                       "horizon": "2026-09-14", "shows": shows}).encode()


class PhoneTicketsFillTheCard(Browser):
    """On a phone every film has one layout: poster and details, then its tickets under
    them, each as wide as the card and one per line (the maintainer's instruction,
    2026-09-29). Short tickets such as Kino Kirkkonummi's lone one included; a long room
    and language line keeps its words."""
    viewport = {"width": 375, "height": 812}; touch = True
    LONG = [("18:00", "Sali 10 Dolby Atmos", "ES-A, FI-S, SV-S")]

    def setUp(self):
        Handler.body = {
            "area-or-helsinki.json": phone_area("or-helsinki", "orion", "Cinema Orion", {
                "Yksi lyhyt": [("18:00", "", "")],
                "Kolme lyhyttä": [("18:00", "", ""), ("19:00", "", ""), ("20:00", "", "")],
                "Yksi pitkä": self.LONG}),
            "area-1100.json": phone_area("1100", "finnkino", "Kinopalatsi",
                                         {"Pitkä muualla": self.LONG,
                                          "Kaksi salia": [("17:00", "Sali 4", "FI-A"),
                                                          ("21:00", "Sali 10 Dolby Atmos", "ES-A, FI-S, SV-S")]}),
            **{f"area-{v}.json": phone_area(v, "finnkino", "", {})
               for v in ("1103", "1111", "1162")},
        }
        self.addCleanup(lambda: setattr(Handler, "body", {}))
        super().setUp()

    def geometry(self, area):
        self.page.goto(self.origin + f"/index.html?area={area}")
        expect(self.page.locator("article.movie").first).to_be_visible()
        self.page.evaluate("document.fonts.ready")
        return self.page.evaluate("""() => ({
            overflow: document.documentElement.scrollWidth > innerWidth,
            cards: Object.fromEntries([...document.querySelectorAll('article.movie')].map(c => {
              const cr = c.getBoundingClientRect();
              const ts = [...c.querySelectorAll('.stubs > *')].map(e => e.getBoundingClientRect());
              return [c.querySelector('.title').textContent.trim(), {
                left: ts.map(t => t.left - cr.left), right: ts.map(t => cr.right - t.right),
                gaps: ts.slice(1).map((t, i) => t.top - ts[i].bottom), heights: ts.map(t => t.height),
                price: [...c.querySelectorAll('.stubs > * .price')].map((e, i) => ts[i].right - e.getBoundingClientRect().right),
                cut: [...c.querySelectorAll('.stub .loc, .stub .slang')]
                       .filter(e => e.scrollWidth > e.clientWidth + 1).length}];
            }))})""")

    def check(self, got):
        self.assertFalse(got["overflow"], "the page scrolls sideways")
        for title, c in got["cards"].items():
            with self.subTest(title=title):
                self.assertTrue(all(abs(x) < 0.6 for x in c["left"] + c["right"]), c)
                self.assertTrue(all(abs(g - 8) < 0.6 for g in c["gaps"]), c)
                self.assertTrue(all(h >= 40 for h in c["heights"]), c)
                self.assertTrue(all(x < 2 for x in c["price"]), "the price is not the ticket's end")
                self.assertEqual(c["cut"], 0, c)

    def test_single_cinema_tickets_fill_the_card_one_per_line(self):
        for width in (320, 375, 393):
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": 812})
                got = self.geometry("or-helsinki")
                self.assertEqual(len(got["cards"]["Kolme lyhyttä"]["gaps"]), 2)
                self.check(got)

    def test_combined_tickets_fill_the_card_one_per_line(self):
        for width in (320, 375, 393):
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": 812})
                got = self.geometry("city:Helsinki")
                self.assertEqual(len(got["cards"]["Kaksi salia"]["gaps"]), 1)
                self.check(got)

    def test_a_wide_window_keeps_the_desktop_ticket(self):
        """Above the phone breakpoint a row ticket keeps its own width."""
        self.page.set_viewport_size({"width": 1200, "height": 900})
        got = self.geometry("or-helsinki")
        self.assertGreater(got["cards"]["Yksi lyhyt"]["right"][0], 200, got["cards"]["Yksi lyhyt"])


class LoadFailureNoteFollowsTheLanguage(ChooserNote):
    """A link that asked for a cinema while the venue lists failed: the chooser with the
    load-failure line, which bootFallback now answers as a key. The failure is set before
    the first load, or the browser answers areas.json from its own cache."""

    def setUp(self):
        Handler.fail = {"areas.json"}
        self.addCleanup(lambda: setattr(Handler, "fail", set()))
        super().setUp()

    def test_the_load_failure_note_is_redrawn_too(self):
        self.page.goto(self.origin + "/index.html?area=or-helsinki")
        expect(self.note()).to_have_text("Näytöstietoja ei juuri nyt saatu ladattua.")
        self.switch("en")
        expect(self.note()).to_have_text("Couldn't load the schedule right now.")
        self.switch("sv")
        expect(self.note()).to_have_text("Visningstiderna kunde inte laddas just nu.")


class FooterStampInHelsinki(Browser):
    """The footer's update time is Helsinki time wherever the reader is, like every
    showtime on the page. Orion's fixture was generated 17:16 UTC on 14.9., which is 20.16
    in Helsinki and 18.16 in London; a reader in London saw 18.16 beside showtimes drawn in
    Helsinki time."""
    tz = "Europe/London"

    def test_the_update_time_is_helsinki_time_in_another_zone(self):
        self.pick_orion()
        credit = self.page.locator("#credit")
        expect(credit).to_contain_text("Orion")
        text = credit.text_content()
        self.assertIn("20.16", text, text)
        self.assertNotIn("18.16", text, text)
