"""Kino Engel: the year a row does not print.

The rows read `La 29.08.` beside `klo 17:30` and carry no year, so the year is selected
from the weekday and then bounded by `common.resolve_year`. Before 2026-09-19 this module
kept a private loop that took the first candidate year inside a window rather than the
nearest one, and a row 46 or more days stale published as next year: `1.8.` read on
2026-09-19 came out as 2027-08-01.

Two rows minimum in every fixture, because the skip is a `continue` inside the loop.
"""
import contextlib
import datetime
import http.client
import http.server
import io
import threading
import unittest
import urllib.error

import _ctx
import _no_sleep as no_sleep
import engel as E


TODAY = datetime.date(2026, 9, 19)          # a Saturday


def row(slug, when, clock, title):
    return (f'<a href="/elokuva/{slug}/"><span>{when}</span><span>klo {clock}</span>'
            f"<h3>{title}</h3>Osta liput</a>")


def parse(page, today=None):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        shows = E.parse(page, today or TODAY)
    return shows, out.getvalue()


def detail(label, value):
    return f"<li><label>{label}</label><span>{value}</span></li>"


class SubtitlesTest(unittest.TestCase):
    """Gråben vs Acme's page, read 2026-09-29: KIELI Ruotsi, TEKSTITYS "Ei tekstitystä".
    Only that explicit statement becomes `XX-S`; an empty or unknown field stays blank."""

    def test_an_explicit_no_subtitles_is_published(self):
        page = detail("KIELI", "Ruotsi") + detail("TEKSTITYS", "Ei tekstitystä")
        self.assertEqual(E.details(page)["lang"], "SV-A, XX-S")

    def test_an_absent_empty_or_unknown_subtitle_field_says_nothing(self):
        for subs in (None, "", "Tulossa", "ei"):
            with self.subTest(subs=subs):
                page = detail("KIELI", "Ruotsi") + ("" if subs is None else detail("TEKSTITYS", subs))
                self.assertEqual(E.details(page)["lang"], "SV-A")

    def test_a_named_subtitle_language_is_published_as_before(self):
        page = detail("KIELI", "Englanti") + detail("TEKSTITYS", "Suomi-Ruotsi")
        self.assertEqual(E.details(page)["lang"], "EN-A, FI-S, SV-S")


class RuntimeTest(unittest.TestCase):
    """Lilla spöket Laban busar vidare, read 2026-10-04: "KESTO 0h 0 min", a field the
    cinema had not filled in, published as "0"."""

    def test_hours_and_minutes_become_minutes(self):
        self.assertEqual(E.details(detail("KESTO", "1h 41 min"))["len"], "101")
        self.assertEqual(E.details(detail("KESTO", "95 min"))["len"], "95")

    def test_a_zero_runtime_publishes_none(self):
        for value in ("0h 0 min", "0 min"):
            with self.subTest(value=value):
                self.assertNotIn("len", E.details(detail("KESTO", value)))


class YearTest(unittest.TestCase):
    def test_the_weekday_places_a_row_that_prints_no_year(self):
        shows, _ = parse(row("autofiktio", "Su 20.09.", "17:30", "Autofiktio")
                         + row("troija", "Ke 30.09.", "19:00", "Troija"))
        self.assertEqual([s["start"] for s in shows],
                         ["2026-09-20T17:30:00+03:00", "2026-09-30T19:00:00+03:00"])

    def test_a_stale_row_is_skipped_and_the_current_one_keeps_its_date(self):
        """`La 1.8.` is 49 days behind: the private loop this replaced published it as
        2027-08-01, a year and a half out."""
        shows, log = parse(row("vanha", "La 01.08.", "18:00", "Vanha")
                           + row("autofiktio", "Su 20.09.", "17:30", "Autofiktio"))
        self.assertEqual([s["title"] for s in shows], ["Autofiktio"])
        self.assertIn("1 row(s) whose weekday matches no candidate year", log)
        self.assertIn("La 01.08.", log)

    def test_a_weekday_that_contradicts_its_own_date_is_skipped(self):
        """20 September 2026 is a Sunday. A row calling it Monday selects 2027, 366 days
        out, which the window refuses."""
        shows, log = parse(row("vaara", "Ma 20.09.", "18:00", "Väärä")
                           + row("autofiktio", "Su 20.09.", "17:30", "Autofiktio"))
        self.assertEqual([s["title"] for s in shows], ["Autofiktio"])
        self.assertIn("Ma 20.09.", log)

    def test_a_row_inside_the_window_behind_today_still_publishes(self):
        """The client hides a past screening; dropping one would lose a same-day row."""
        shows, _ = parse(row("eilen", "Pe 18.09.", "18:00", "Eilen")
                         + row("autofiktio", "Su 20.09.", "17:30", "Autofiktio"))
        self.assertEqual([s["start"][:10] for s in shows], ["2026-09-18", "2026-09-20"])

    def test_the_window_is_the_callers_and_this_one_is_measured(self):
        """The committed programme reached +9 to +15 days on 2026-09-19, so 120 ahead is
        headroom. The weekday is derived here rather than written down, because a calendar
        fact typed by hand is how three of these assertions were wrong first."""
        self.assertEqual(E.WINDOW, (30, 120))
        for days, published in ((100, True), (150, False)):
            with self.subTest(days=days):
                d = TODAY + datetime.timedelta(days=days)
                got = E._iso(d.day, d.month, 18, 0, TODAY, d.weekday())
                self.assertEqual(got[:10], d.isoformat() if published else "")


if __name__ == "__main__":
    unittest.main()


class FiveHundredTest(unittest.TestCase):
    """The site answering 500 while still serving the programme.

    Read 2026-09-21: `kinoengel.fi` began returning HTTP 500 on the listing and on every
    film page while the bodies were intact, 126 kB that parses to 25 timed screenings.
    `common.fetch` throws an error response's body away unread and still does; this
    module asks for the 500's body back and then has to earn it. The tests below are the
    three ways it can fail to.
    """

    PAGE = ("<html><body>" + "x" * E.MIN_BYTES
            + row("a", "Ma 21.09.", "18:00", "Alpha")
            + row("b", "Ti 22.09.", "20:15", "Beta") + "</body></html>")

    def setUp(self):
        no_sleep.patch(self, E)                 # the 0.5 s pause before the error body
        self._get = E.get_text
        self.addCleanup(lambda: setattr(E, "get_text", self._get))
        self.calls = []

    def serve(self, *answers):
        """Each call returns the next answer; an Exception is raised instead."""
        seq = list(answers)

        def get_text(url, **kw):
            self.calls.append((url, kw.get("keep_body_on", ())))
            a = seq.pop(0) if len(seq) > 1 else seq[0]
            if isinstance(a, Exception):
                raise a
            return a
        E.get_text = get_text

    def http(self, code):
        """An error response to serve. Closed at the end of the test: HTTPError with no
        `fp` opens a tempfile for the body, and since 3.14 letting that be collected
        raises ResourceWarning. ci.yml greps the suite log for that word and fails the
        build, so five unclosed fixtures here would read as a leak in the pipeline.
        Passing io.BytesIO() instead does not help; the warning is on the object."""
        import urllib.error
        e = urllib.error.HTTPError("https://kinoengel.fi/", code, "err", {}, None)
        self.addCleanup(e.close)
        return e

    def page_with(self, **kw):
        return E.fetch_page()

    def test_a_healthy_page_never_asks_for_an_error_body(self):
        self.serve(self.PAGE)
        with contextlib.redirect_stdout(io.StringIO()):
            shows = E.fetch_page()
        self.assertEqual(len(shows), 2)
        # One listing read and one per film page, none of them asking for an error body.
        self.assertEqual([k for _, k in self.calls], [(), (), ()])

    def test_a_500_whose_body_is_the_programme_publishes_and_says_so(self):
        self.serve(self.http(500), self.PAGE)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            shows = E.fetch_page()
        self.assertEqual(len(shows), 2)
        self.assertEqual(self.calls[1][1], (500,), "the second call asks for the body")
        self.assertIn("answered 500 and served the programme anyway", out.getvalue())

    def test_a_500_with_a_short_body_fails_the_site(self):
        """Short but carrying both markers, so the size floor is what refuses it."""
        self.serve(self.http(500),
                   '<html><a href="/elokuva/a/">Osta liput</a></html>')
        with self.assertRaises(RuntimeError) as cm, contextlib.redirect_stdout(io.StringIO()):
            E.fetch_page()
        self.assertIn("not the programme", str(cm.exception))

    def test_a_500_with_a_long_body_and_no_markers_fails_the_site(self):
        self.serve(self.http(500), "<html>" + "x" * (E.MIN_BYTES + 10) + "</html>")
        with self.assertRaises(RuntimeError) as cm, contextlib.redirect_stdout(io.StringIO()):
            E.fetch_page()
        self.assertIn("not the programme", str(cm.exception))

    def test_a_500_that_looks_right_and_parses_to_nothing_fails_the_site(self):
        """The broken-parse case. An empty programme is not what this proves."""
        body = ("<html>" + "x" * E.MIN_BYTES
                + '<a href="/elokuva/a/">Osta liput</a></html>')
        self.serve(self.http(500), body)
        with self.assertRaises(RuntimeError) as cm, contextlib.redirect_stdout(io.StringIO()):
            E.fetch_page()
        self.assertIn("broken parse", str(cm.exception))
        self.assertIn("markers present", str(cm.exception))

    def test_any_other_status_is_still_an_error(self):
        """The body is served on the second call, so a reader that tolerated the status
        would publish it. Only 500 may reach that second call."""
        for code in (403, 404, 502, 503):
            with self.subTest(code=code):
                self.serve(self.http(code), self.PAGE)
                with self.assertRaises(urllib.error.HTTPError) as cm:
                    E.fetch_page()
                self.assertEqual(cm.exception.code, code)
                self.assertEqual([k for _, k in self.calls], [()],
                                 "only a 500 may have its body asked for")
                self.calls.clear()

    def test_the_markers_are_not_what_the_parse_keys_on(self):
        """A marker the parse used to find rows would prove nothing about the body."""
        self.assertEqual(E.MARKERS, ("/elokuva/", "Osta liput"))
        self.assertNotIn("Osta liput", E.ANCHOR_RE.pattern)

    FILM = ('<html><label>Ikäraja</label><div class="contentratings">'
            '<span class="rating K-12"><span>x</span></span></div>'
            "<label>Kesto</label><span>1 h 47 min</span></html>")

    def test_the_film_pages_go_through_the_same_tolerant_read(self):
        """They answered 500 with their metadata intact on the same day the listing did.
        Without the tolerant read every row publishes unrated."""
        seq = [self.PAGE, self.http(500), self.FILM, self.http(500), self.FILM]

        def get_text(url, **kw):
            self.calls.append((url, kw.get("keep_body_on", ())))
            a = seq.pop(0) if len(seq) > 1 else seq[0]
            if isinstance(a, Exception):
                raise a
            return a
        E.get_text = get_text
        with contextlib.redirect_stdout(io.StringIO()):
            shows = E.fetch_page()
        self.assertEqual(len(shows), 2)
        self.assertEqual(sorted({s["rating"] for s in shows}), ["K-12"])
        self.assertIn((500,), [k for _, k in self.calls],
                      "a film page that 500s is read through it")


class DroppedConnectionTest(unittest.TestCase):
    """The site's other failure since 2026-09-21: the connection closes with no response.

    `http.client` raises RemoteDisconnected and `common.fetch` retries it like any other
    exception, three attempts 5 s and 10 s apart. Four runs between 2026-09-22 and
    2026-09-23 had all three fall inside one bad window, and the whole site failed.

    There is no body to rescue the way the 500's body is rescued, so the only answer is to
    wait longer, and the only question worth pinning is which errors get that patience and
    which still fail at once.

    The classification is partly urllib's, so the last two tests talk to a real socket: a
    server that accepts and closes is the only honest way to produce the exception this is
    about, and a stub would encode the assumption under test.
    """

    def test_a_closed_connection_is_recognised_raw_and_wrapped(self):
        raw = http.client.RemoteDisconnected("Remote end closed connection without response")
        self.assertTrue(E.dropped(raw))
        self.assertTrue(E.dropped(urllib.error.URLError(raw)))
        self.assertTrue(E.dropped(ConnectionResetError(54, "Connection reset by peer")))
        self.assertTrue(E.dropped(urllib.error.URLError(ConnectionResetError(54, "reset"))))

    def test_an_answer_is_never_a_dropped_connection(self):
        """An HTTPError is a URLError too, and it is the 500 path's business, not this."""
        e = urllib.error.HTTPError("https://kinoengel.fi/", 500, "err", {}, None)
        self.addCleanup(e.close)
        self.assertFalse(E.dropped(e))
        self.assertFalse(E.dropped(urllib.error.URLError(TimeoutError("timed out"))))
        self.assertFalse(E.dropped(RuntimeError("something else")))
        # An HTTPError's `reason` is its status message, so the URLError branch below
        # would read one. The guard is first for that reason, and this is the input that
        # tells the two orderings apart: a 500 whose message is itself a socket error is
        # still an answer, and still the 500 path's business.
        odd = urllib.error.HTTPError("https://kinoengel.fi/", 500,
                                     ConnectionResetError(54, "reset"), {}, None)
        self.addCleanup(odd.close)
        self.assertFalse(E.dropped(odd))

    def test_the_patience_is_the_listings_and_not_the_film_pages(self):
        """`enrich()` already counts a film-page failure and moves on, so a cinema showing
        thirty films is not made to wait a minute a page for metadata it can do without."""
        src = (_ctx.ROOT / "scripts" / "providers" / "engel.py").read_text(encoding="utf-8")
        self.assertIn("page = patient_get(URL)", src)
        self.assertEqual(src.count("patient_get("), 2, "one definition, one call site")
        body = src[src.index("def tolerant_get"):src.index("def usable")]
        self.assertNotIn("patient_get", body, "the film pages take the fast path")


class DroppedConnectionSocketTest(unittest.TestCase):
    """Against a real server, because which exception urllib raises is urllib's answer."""

    PAGE = ("<html><body>" + "x" * E.MIN_BYTES
            + row("a", "Ma 21.09.", "18:00", "Alpha")
            + row("b", "Ti 22.09.", "20:15", "Beta") + "</body></html>").encode()

    def serve(self, drops):
        """A server that closes the connection on the first `drops` requests, then serves
        the page. -> base url. Two rows in the page, as every fixture here has."""
        page = self.PAGE
        state = {"n": 0}

        class H(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def do_GET(self):
                state["n"] += 1
                if state["n"] <= drops:
                    self.close_connection = True
                    try:
                        self.connection.close()
                    except OSError:
                        pass
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)

            def log_message(self, *a):
                pass

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        # Both, in this order: shutdown() stops the loop and server_close() releases the
        # listening socket. Without the second the socket is collected later and raises
        # ResourceWarning, which ci.yml greps the suite log for and fails the build on.
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        self.state = state
        return f"http://127.0.0.1:{srv.server_address[1]}/"

    def setUp(self):
        no_sleep.patch(self, E)                 # the 0.5 s pause before the error body
        # The real schedule is 20 s and 40 s; the rule under test is that there is a
        # second round at all, not how long it waits, and the suite must not sleep a
        # minute to see it.
        for name, value in (("PATIENT_BACKOFF", 0), ("PATIENT_TRIES", 3)):
            saved = getattr(E, name)
            setattr(E, name, value)
            self.addCleanup(lambda n=name, v=saved: setattr(E, n, v))

    def test_a_closed_connection_raises_what_dropped_recognises(self):
        """The whole chain in one: a real socket close, through common.fetch, classified."""
        url = self.serve(drops=99)
        with self.assertRaises(Exception) as cm:
            E.get_text(url, fetcher=E.fetch, tries=1, cache=False)
        self.assertTrue(E.dropped(cm.exception),
                        f"dropped() does not recognise {cm.exception!r}")

    def test_a_short_window_is_ridden_out(self):
        """Three attempts inside common.fetch, then three more: a window that swallows the
        first round is survived by the second, which is the run that used to fail."""
        url = self.serve(drops=4)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            page = E.patient_get(url, tries=3, backoff=0, cache=False)
        self.assertIn("Osta liput", page)
        self.assertEqual(self.state["n"], 5, "four refusals and one page")
        self.assertIn("the connection was closed without a response", out.getvalue())

    def test_a_site_that_is_really_gone_still_fails_closed(self):
        """The patience is a longer wait, not a way to publish nothing."""
        url = self.serve(drops=99)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(Exception) as cm:
            E.patient_get(url, tries=3, backoff=0, cache=False)
        self.assertTrue(E.dropped(cm.exception))
        self.assertEqual(self.state["n"], 6, "three attempts, then three more, then out")

    def test_an_answer_gets_no_second_round(self):
        """A page on the first attempt is one request, and nothing is retried."""
        url = self.serve(drops=0)
        with contextlib.redirect_stdout(io.StringIO()):
            page = E.patient_get(url, tries=3, backoff=0, cache=False)
        self.assertIn("Osta liput", page)
        self.assertEqual(self.state["n"], 1)
