"""common.fetch: retry, Retry-After, the two ceilings, and what a refusal says.

Every test talks to a real HTTP server on localhost rather than a mocked urlopen, because
the behaviour under test is partly urllib's: which exception a 429 raises, what
`e.headers` holds, what survives closing the response.
"""
import contextlib
import email.utils
import datetime
import gc
import http.server
import importlib
import io
import os
import pathlib
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import warnings

import _ctx                                                # noqa: F401
import common
from _http_cache import temp_cache
import _no_sleep as no_sleep

# An adapter binds the exception class at import time (`from common import
# EmptyProgramme`), and a reload below rebinds it to a new class object. An adapter
# imported before the first reload would then raise a class the etiketti tests no longer
# recognise, and four of them go red on an exception that escapes their assertRaises.
# The suite used to be saved from this by accident: the only module that dropped adapters
# from sys.modules did it for its own reasons, and deleting it turned the four red.
EMPTY_PROGRAMME = common.EmptyProgramme

# What `common` reads from the environment at import and these tests override.
LIMITS = ("KINO_RETRY_AFTER_MAX", "KINO_RETRY_AFTER_BUDGET", "KINO_MAX_BODY")


def fresh_common(test, **env):
    """Reload `common` with the limits in env, and undo both when the test ends.

    The reload is in place, so every module holding `fetch` sees the override. The cleanup
    puts the environment back before it reloads: a reload with the override still set
    re-reads it, which left KINO_MAX_BODY=500 in place for tests/test_engel.py. The
    reloaded module reads its cache directory from a private one, put back the same way.
    """
    temp_cache(test)
    saved = {k: os.environ.get(k) for k in LIMITS + tuple(env)}

    def restore():
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        importlib.reload(common).EmptyProgramme = EMPTY_PROGRAMME

    test.addCleanup(restore)
    for k in LIMITS:
        os.environ.pop(k, None)
    os.environ.update({k: str(v) for k, v in env.items()})
    mod = importlib.reload(common)
    # The counters are what this reload is for. The exception type is not: keep the
    # class the adapters already hold, or an `except EmptyProgramme` elsewhere in the
    # suite stops matching what this module now raises.
    mod.EmptyProgramme = EMPTY_PROGRAMME
    return mod


class Handler(http.server.BaseHTTPRequestHandler):
    """Replays a scripted list of responses per path, then repeats the last one."""
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        self.server.hits[self.path] = self.server.hits.get(self.path, 0) + 1
        steps = self.server.script.get(self.path) or [(200, {}, b"ok")]
        status, hdrs, body = steps.pop(0) if len(steps) > 1 else steps[0]
        self.send_response(status)
        for k, v in hdrs.items():
            if k != "X-No-Length":
                self.send_header(k, v)
        if "X-No-Length" in hdrs:
            # No Content-Length at all: the client reads until the connection
            # closes, which is the response shape the streaming cap exists for.
            self.send_header("Connection", "close")
        else:
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def version_string(self):
        """The Server header. BaseHTTPRequestHandler sends one on every response, and
        `send_header` would only append a second that `headers.get` never returns, so a
        test that needs `Server: cloudflare` has to come through here."""
        return getattr(self.server, "banner", "TestHTTP")

    def log_message(self, *a):
        pass


class FetchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.srv.script, cls.srv.hits = {}, {}
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        # shutdown() stops serve_forever; the listening socket is still
        # open until this. test_run_pool.py has always done both.
        cls.srv.server_close()

    def setUp(self):
        self.srv.script.clear()
        self.srv.hits.clear()
        self.srv.banner = "TestHTTP"
        # Every test here that exercises a failure path now makes fetch print one
        # diagnostic line. Swallowed by default so a run stays readable; `refusals`
        # nests its own redirect inside this one for the tests that read them.
        sink = contextlib.redirect_stdout(io.StringIO())
        sink.__enter__()
        self.addCleanup(sink.__exit__, None, None, None)
        temp_cache(self)

    def test_an_error_body_is_thrown_away_unless_the_caller_asks_for_it(self):
        """The default, and the one opt-in. `keep_body_on` exists for Kino Engel, whose
        WordPress began answering 500 with the complete programme on 2026-09-21."""
        self.srv.script["/boom"] = [(500, {}, b"the programme")]
        with self.assertRaises(urllib.error.HTTPError) as cm:
            common.fetch(self.url + "/boom", tries=1)
        self.assertEqual(cm.exception.code, 500)
        self.assertEqual(common.fetch(self.url + "/boom", tries=1, keep_body_on=(500,)),
                         b"the programme")

    def test_only_the_codes_the_caller_names_hand_their_body_back(self):
        self.srv.script["/gone"] = [(404, {}, b"not this one")]
        with self.assertRaises(urllib.error.HTTPError):
            common.fetch(self.url + "/gone", tries=1, keep_body_on=(500,))

    def test_a_kept_error_body_is_never_written_to_the_cache_slot(self):
        """An error response is not a representation to revalidate later."""
        self.srv.script["/boom2"] = [(500, {"ETag": '"v1"'}, b"the programme")]
        common.fetch(self.url + "/boom2", tries=1, cache=True, keep_body_on=(500,))
        self.srv.script["/boom2"] = [(200, {"ETag": '"v1"'}, b"fresh")]
        self.assertEqual(common.fetch(self.url + "/boom2", tries=1, cache=True), b"fresh")

    def refusals(self, fn):
        """Run fn with stdout captured. -> (its return value, the [http] lines)."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            got = fn()
        self.captured = buf.getvalue()
        return got, [l for l in self.captured.splitlines() if l.startswith("[http]")]

    def reload(self, **env):
        """Fresh module so the throttle counters start at zero, with env overrides. Its
        sleeps are recorded in `self.clock.slept` rather than waited."""
        c = fresh_common(self, **env)
        self.clock = no_sleep.patch(self, c)
        return c

    # -- Retry-After is honoured -------------------------------------------------

    def test_429_waits_the_stated_interval_not_the_backoff(self):
        c = self.reload()
        self.srv.script["/a"] = [(429, {"Retry-After": "1"}, b"slow"), (200, {}, b"ok")]
        body = c.fetch(self.url + "/a", backoff=30)
        self.assertEqual(body, b"ok")
        self.assertEqual(self.clock.slept, [1], "the stated 1s, not the 30s backoff")
        self.assertEqual(self.srv.hits["/a"], 2)
        self.assertEqual(c.throttle_stats()["asked"], 1)
        self.assertEqual(c.throttle_stats()["refused"], 0)

    def test_no_sleep_follows_the_final_attempt(self):
        """Three tries sleep twice, whichever way they fail: the last attempt has no retry
        after it, so a sleep there only delays the error. Each branch of the retry loop is
        its own case, the Retry-After wait, the backoff after an HTTP error and the backoff
        after a connection that never opened."""
        c = self.reload()
        self.srv.script["/ra"] = [(429, {"Retry-After": "1"}, b"slow")]
        with self.assertRaises(Exception):
            c.fetch(self.url + "/ra", tries=3, backoff=30)
        self.assertEqual((self.srv.hits["/ra"], self.clock.slept), (3, [1, 1]))

        self.clock.slept.clear()
        self.srv.script["/500"] = [(500, {}, b"down")]
        with self.assertRaises(Exception):
            c.fetch(self.url + "/500", tries=3, backoff=5)
        self.assertEqual((self.srv.hits["/500"], self.clock.slept), (3, [5, 10]))

        self.clock.slept.clear()
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            closed = s.getsockname()[1]
        with self.assertRaises(Exception):
            c.fetch(f"http://127.0.0.1:{closed}/", tries=3, backoff=5)
        self.assertEqual(self.clock.slept, [5, 10])

    def test_503_is_honoured_the_same_way(self):
        c = self.reload()
        self.srv.script["/b"] = [(503, {"Retry-After": "1"}, b"maint"), (200, {}, b"ok")]
        self.assertEqual(c.fetch(self.url + "/b", backoff=30), b"ok")
        self.assertEqual(c.throttle_stats()["asked"], 1)

    def test_http_date_form_is_parsed(self):
        c = self.reload()
        when = email.utils.format_datetime(
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=3))
        self.srv.script["/c"] = [(429, {"Retry-After": when}, b"slow"), (200, {}, b"ok")]
        self.assertEqual(c.fetch(self.url + "/c", backoff=30), b"ok")
        # HTTP-date has whole-second granularity, so "+3s" is 2.0-3.0s away once parsed.
        self.assertEqual(len(self.clock.slept), 1)
        self.assertTrue(1.8 < self.clock.slept[0] <= 3.0, self.clock.slept)

    def test_a_date_already_past_waits_zero_not_a_negative(self):
        c = self.reload()
        past = email.utils.format_datetime(
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1))
        self.srv.script["/d"] = [(429, {"Retry-After": past}, b"slow"), (200, {}, b"ok")]
        self.assertEqual(c.fetch(self.url + "/d", backoff=30), b"ok")
        self.assertEqual(self.clock.slept, [0])

    # -- the ceilings fire ----------------------------------------------

    def test_an_ask_past_the_ceiling_costs_one_request_and_no_sleep(self):
        c = self.reload()
        self.srv.script["/e"] = [(429, {"Retry-After": "9999"}, b"go away")]
        with self.assertRaises(Exception) as cm:
            c.fetch(self.url + "/e", backoff=30)
        self.assertEqual(getattr(cm.exception, "code", None), 429)
        self.assertEqual(self.clock.slept, [])
        self.assertEqual(self.srv.hits["/e"], 1, "kept asking a host that said no")
        self.assertEqual(c.throttle_stats()["refused"], 1)
        self.assertEqual(c.throttle_stats()["waited"], 0)

    def test_the_run_wide_budget_stops_the_second_request(self):
        """Two paths, not one: the budget is per process, so a single request could
        never show that it accumulates across them."""
        c = self.reload(KINO_RETRY_AFTER_BUDGET=3)
        for p in ("/f1", "/f2"):
            self.srv.script[p] = [(429, {"Retry-After": "2"}, b"slow"), (200, {}, b"ok")]
        self.assertEqual(c.fetch(self.url + "/f1", backoff=30), b"ok")
        with self.assertRaises(Exception):
            c.fetch(self.url + "/f2", backoff=30)
        self.assertEqual(self.srv.hits["/f2"], 1)
        self.assertEqual(c.throttle_stats()["waited"], 2)
        self.assertEqual(c.throttle_stats()["refused"], 1)

    def test_per_wait_ceiling_is_the_env_override(self):
        c = self.reload(KINO_RETRY_AFTER_MAX=1)
        self.srv.script["/g"] = [(429, {"Retry-After": "2"}, b"slow"), (200, {}, b"ok")]
        with self.assertRaises(Exception):
            c.fetch(self.url + "/g", backoff=30)
        self.assertEqual(self.srv.hits["/g"], 1)

    # -- nothing else changed ----------------------------------------------------

    def test_429_without_the_header_keeps_the_fixed_backoff_and_try_count(self):
        c = self.reload()
        self.srv.script["/h"] = [(429, {}, b"no header")]
        with self.assertRaises(Exception):
            c.fetch(self.url + "/h", tries=3, backoff=0)
        self.assertEqual(self.srv.hits["/h"], 3)
        self.assertEqual(c.throttle_stats()["asked"], 0)

    def test_unparseable_retry_after_falls_back_rather_than_reading_as_zero(self):
        c = self.reload()
        self.srv.script["/i"] = [(429, {"Retry-After": "soonish"}, b"junk")]
        with self.assertRaises(Exception):
            c.fetch(self.url + "/i", tries=2, backoff=0)
        self.assertEqual(self.srv.hits["/i"], 2)
        self.assertEqual(c.throttle_stats()["asked"], 0)

    def test_a_plain_500_still_takes_its_three_tries(self):
        c = self.reload()
        self.srv.script["/j"] = [(500, {}, b"boom")]
        with self.assertRaises(Exception):
            c.fetch(self.url + "/j", tries=3, backoff=0)
        self.assertEqual(self.srv.hits["/j"], 3)
        self.assertEqual(c.throttle_stats()["asked"], 0)

    # -- the refused response does not sit on its socket -------------------------------

    def test_a_refused_response_comes_back_closed(self):
        """An HTTPError *is* the response. Holding one without closing it keeps the
        socket until the collector happens to run -- 24 ResourceWarnings in a suite run,
        and on a run against a host refusing everything, that many sockets waiting on a
        collection nobody scheduled."""
        c = self.reload()
        self.srv.script["/k1"] = [(429, {"Retry-After": "9999"}, b"go away")]
        with self.assertRaises(urllib.error.HTTPError) as cm:
            c.fetch(self.url + "/k1", backoff=30)
        self.assertTrue(cm.exception.closed)

    def test_the_last_of_several_tries_comes_back_closed_too(self):
        """Three attempts, so three responses. The one that reaches the caller is the
        last, and the two before it are dropped inside the loop -- a fix that only
        closed the raised one would leave those two, which is most of them."""
        c = self.reload()
        self.srv.script["/k2"] = [(500, {}, b"boom")]
        with self.assertRaises(urllib.error.HTTPError) as cm:
            c.fetch(self.url + "/k2", tries=3, backoff=0)
        self.assertEqual(self.srv.hits["/k2"], 3)
        self.assertTrue(cm.exception.closed)

    def test_no_resource_warning_survives_the_retry_loop(self):
        """Stated as the symptom rather than the mechanism, because `closed` is only
        evidence and this is the thing that was wrong. gc.collect() forces the
        collection the warning would otherwise appear at some arbitrary later point."""
        c = self.reload()
        self.srv.script["/k3"] = [(403, {}, b"nope")]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with self.assertRaises(urllib.error.HTTPError):
                c.fetch(self.url + "/k3", tries=3, backoff=0)
            gc.collect()
        leaked = [w for w in caught if issubclass(w.category, ResourceWarning)]
        self.assertEqual(leaked, [], f"{len(leaked)} response(s) left open")

    def test_the_diagnostic_headers_survive_the_close(self):
        """What the close is allowed to cost. `_log_refusal` reads Server and CF-Ray off
        the exception after the fact, so closing the body must not take the headers with
        it -- that line is how a Cloudflare block was told apart from a real 403."""
        c = self.reload()
        self.srv.script["/k4"] = [(403, {"Server": "cloudflare", "CF-Ray": "abc-HEL"},
                                   b"blocked")]
        with self.assertRaises(urllib.error.HTTPError) as cm:
            c.fetch(self.url + "/k4", tries=1, backoff=0)
        e = cm.exception
        self.assertTrue(e.closed)
        self.assertEqual(e.code, 403)
        self.assertEqual(e.headers.get("CF-Ray"), "abc-HEL")
        # The real consumer rather than the header dict: _server_hint is what builds the
        # line, so asserting on it covers the close and the reader together. `Server` is
        # not asserted -- BaseHTTPRequestHandler writes its own banner over the scripted
        # one, which is the harness talking and not the code under test.
        self.assertIn("CF-Ray: abc-HEL", common._server_hint(e))

    def test_a_200_is_untouched(self):
        c = self.reload()
        self.srv.script["/k"] = [(200, {}, b"hello")]
        self.assertEqual(c.fetch(self.url + "/k"), b"hello")
        self.assertEqual(c.throttle_stats()["asked"], 0)

    # -- the body cap ------------------------------------------------------------

    def test_a_declared_oversize_is_refused_from_the_header(self):
        c = self.reload()
        self.srv.script["/big1"] = [(200, {}, b"x" * 2000)]
        with self.assertRaises(c.BodyTooLarge) as cm:
            c.fetch(self.url + "/big1", max_bytes=1000)
        self.assertIn("Content-Length", str(cm.exception))
        self.assertEqual(self.srv.hits["/big1"], 1, "an oversize answer was re-asked")

    def test_an_undeclared_oversize_is_cut_off_while_reading(self):
        """Content-Length is only the origin's claim; a response without one has to be
        stopped by the read loop itself."""
        c = self.reload()
        self.srv.script["/big2"] = [(200, {"X-No-Length": "1"}, b"x" * 200_000)]
        with self.assertRaises(c.BodyTooLarge) as cm:
            c.fetch(self.url + "/big2", max_bytes=1000)
        self.assertNotIn("Content-Length", str(cm.exception))
        self.assertEqual(self.srv.hits["/big2"], 1)

    def test_a_body_at_the_cap_passes(self):
        c = self.reload()
        self.srv.script["/fit"] = [(200, {}, b"x" * 1000)]
        self.assertEqual(len(c.fetch(self.url + "/fit", max_bytes=1000)), 1000)

    def test_the_default_cap_comes_from_the_environment(self):
        c = self.reload(KINO_MAX_BODY=500)
        self.srv.script["/env"] = [(200, {}, b"x" * 501)]
        with self.assertRaises(c.BodyTooLarge):
            c.fetch(self.url + "/env")

    # -- a refusal says which layer refused -------------------------------------

    def test_a_blocked_venue_is_identified_and_a_working_one_stays_silent(self):
        """The Kinoset shape, with the loop in it: one venue refused, one served. The
        committed log said `HTTP Error 403: Forbidden` three times and nothing else,
        which is the same line for an edge block and for an origin throttle."""
        c = self.reload()
        self.srv.banner = "cloudflare"
        self.srv.script["/v1"] = [(403, {"CF-Ray": "8f2a1b3c4d5e6f70-HEL"}, b"blocked")]
        self.srv.script["/v2"] = [(200, {}, b"ok")]

        def loop():
            out = {}
            for venue in ("v1", "v2"):
                try:
                    out[venue] = c.fetch(f"{self.url}/{venue}", tries=2, backoff=0)
                except urllib.error.HTTPError as e:
                    out[venue] = e.code
            return out

        got, lines = self.refusals(loop)
        self.assertEqual(got, {"v1": 403, "v2": b"ok"})
        self.assertEqual(len(lines), 1, f"one line for one refusal, got: {lines}")
        self.assertIn("403", lines[0])
        self.assertIn("Server: cloudflare", lines[0])
        self.assertIn("CF-Ray: 8f2a1b3c4d5e6f70-HEL", lines[0])
        self.assertIn("2 attempt(s)", lines[0])

    def test_an_origin_refusal_does_not_read_as_an_edge_one(self):
        """The distinction the line exists for: no ray means the application said no,
        which clears on its own, rather than an address being blocked, which does not."""
        c = self.reload()
        self.srv.banner = "Apache/2.4.62"
        self.srv.script["/o"] = [(403, {}, b"nope")]

        def call():
            with self.assertRaises(urllib.error.HTTPError):
                c.fetch(self.url + "/o", tries=1, backoff=0)
        _, lines = self.refusals(call)
        self.assertEqual(len(lines), 1)
        self.assertIn("Server: Apache/2.4.62", lines[0])
        self.assertNotIn("CF-Ray", lines[0])

    def test_one_line_per_host_however_many_requests_it_refuses(self):
        """mirror_posters calls fetch once per poster and has had 185 failures against
        one host in a run. A line each would bury the summary the log is read for."""
        c = self.reload()
        self.srv.banner = "cloudflare"
        for n in (1, 2, 3):
            self.srv.script[f"/p{n}"] = [(403, {"CF-Ray": f"ray-{n}"}, b"blocked")]

        def loop():
            for n in (1, 2, 3):
                with self.assertRaises(urllib.error.HTTPError):
                    c.fetch(f"{self.url}/p{n}", tries=1, backoff=0)

        _, lines = self.refusals(loop)
        self.assertEqual(len(lines), 1, f"deduplication is gone: {lines}")
        self.assertIn("ray-1", lines[0])

    def test_the_body_of_a_refusal_is_never_printed(self):
        """run-*.log is committed to a public repo, and a third party's error page carries
        whatever they ship to visitors. That rule cost a history rewrite once already."""
        c = self.reload()
        self.srv.banner = "cloudflare"
        secret = b"<!-- apiKey: AIzaSyTESTONLYNOTREAL -->"
        self.srv.script["/b"] = [(403, {"CF-Ray": "r1"}, secret)]

        def call():
            with self.assertRaises(urllib.error.HTTPError):
                c.fetch(self.url + "/b", tries=1, backoff=0)

        self.refusals(call)
        self.assertNotIn("AIzaSy", self.captured)
        self.assertNotIn("apiKey", self.captured)

    def test_a_response_with_none_of_the_headers_prints_nothing(self):
        """No empty line, and no line saying only the code -- that is what the adapter's
        own FAILED line already says."""
        c = self.reload()
        self.srv.banner = ""
        self.srv.script["/q"] = [(403, {}, b"nope")]

        def call():
            with self.assertRaises(urllib.error.HTTPError):
                c.fetch(self.url + "/q", tries=1, backoff=0)

        _, lines = self.refusals(call)
        self.assertEqual(lines, [])

    def test_a_refused_retry_after_says_what_was_asked_for(self):
        """The ceiling path raises without retrying, and that exit needs the line too:
        `[run] throttled:` counts them but never names the host."""
        c = self.reload()
        self.srv.banner = "cloudflare"
        self.srv.script["/r"] = [(429, {"Retry-After": "9999"}, b"slow")]

        def call():
            with self.assertRaises(urllib.error.HTTPError):
                c.fetch(self.url + "/r", tries=3, backoff=0)

        _, lines = self.refusals(call)
        self.assertEqual(len(lines), 1)
        self.assertIn("Retry-After: 9999", lines[0])
        self.assertIn("1 attempt(s)", lines[0])
        self.assertEqual(self.srv.hits["/r"], 1)


class ServedHeadersTest(unittest.TestCase):
    """`served()` reports Server, CF-Ray and Retry-After beside the size and the title.

    Against a real local server, because what is under test is partly urllib's: which of
    these survive on an `HTTPError`, and what `headers.get` returns for a name the server
    sent. A mock would encode the assumption this is meant to check.

    The nine-host challenge in docs/research/runner-challenges.md had to infer the cause
    from a byte count and a title alone, and two of its fourteen hosts were evidenced by
    nothing at all. These three name it.
    """

    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.srv.script, cls.srv.hits = {}, {}
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        self.srv.script.clear()
        self.srv.hits.clear()
        self.srv.banner = "TestHTTP"
        common._seen.headers = {}
        self.addCleanup(lambda: setattr(common._seen, "headers", {}))

    def get(self, path, tries=1):
        try:
            return common.fetch(self.url + path, tries=tries, backoff=0).decode()
        except Exception:
            return ""

    def test_a_challenge_page_names_the_stack_and_the_front_door(self):
        self.srv.banner = "cloudflare"
        body = b"<html><head><title>Just a moment...</title></head><body></body></html>"
        self.srv.script["/c"] = [(200, {"CF-Ray": "8f2b1c0ddead1234-HEL"}, body)]
        page = self.get("/c")
        note = common.served(page)
        self.assertIn("Just a moment...", note)
        self.assertIn("Server: cloudflare", note)
        self.assertIn("CF-Ray: 8f2b1c0ddead1234-HEL", note)

    def test_a_403_keeps_its_server_header_through_the_httperror(self):
        self.srv.banner = "openresty/1.31.1.1"
        self.srv.script["/f"] = [(403, {}, b"<html><title>Forbidden</title></html>")]
        self.get("/f")
        self.assertIn("Server: openresty/1.31.1.1", common.served(""))

    def test_a_timed_refusal_says_so(self):
        self.srv.script["/r"] = [(503, {"Retry-After": "7"}, b"<html><title>Busy</title></html>")]
        self.get("/r")
        self.assertIn("Retry-After: 7", common.served(""))

    def test_a_response_carrying_none_of_them_reads_as_it_always_did(self):
        """`Server` is sent by every BaseHTTPRequestHandler response, so the one case with
        no note at all is a `served()` call with no fetch behind it."""
        common._seen.headers = {}
        self.assertEqual(common.served("<html><title>Kino</title></html>"),
                         '32 B served, titled "Kino"')
        self.assertEqual(common.served(""), "0 B served, no <title>")

    def test_the_note_describes_the_last_response_and_not_an_older_one(self):
        self.srv.banner = "cloudflare"
        self.srv.script["/a"] = [(200, {"CF-Ray": "aaaa-HEL"}, b"<html><title>A</title></html>")]
        self.get("/a")
        self.assertIn("CF-Ray: aaaa-HEL", common.served(""))
        self.srv.banner = "nginx"
        self.srv.script["/b"] = [(200, {}, b"<html><title>B</title></html>")]
        self.get("/b")
        note = common.served("")
        self.assertIn("Server: nginx", note)
        self.assertNotIn("CF-Ray", note)

    def test_a_response_carrying_none_of_them_clears_the_previous_note(self):
        """The note describes the last response, so an ordinary answer after a challenge
        has to erase the challenge's headers rather than leave them standing over it.
        `banner=""` is how a response with no usable `Server` is produced here, since
        BaseHTTPRequestHandler sends the header on every response."""
        self.srv.banner = "cloudflare"
        self.srv.script["/x"] = [(200, {"CF-Ray": "cccc-HEL"}, b"<html><title>X</title></html>")]
        self.get("/x")
        self.assertIn("CF-Ray: cccc-HEL", common.served(""))
        self.srv.banner = ""
        self.srv.script["/y"] = [(200, {}, b"<html><title>Y</title></html>")]
        self.get("/y")
        self.assertEqual(common.served(""), "0 B served, no <title>")

    def test_no_part_of_the_body_reaches_the_note(self):
        """The rule this whole helper exists under: a third party's page is never kept."""
        self.srv.banner = "cloudflare"
        secret = b"<html><title>Just a moment...</title><body>SECRET-TOKEN-42</body></html>"
        self.srv.script["/s"] = [(200, {"CF-Ray": "bbbb-HEL"}, secret)]
        page = self.get("/s")
        self.assertIn("SECRET-TOKEN-42", page, "the body did arrive")
        self.assertNotIn("SECRET-TOKEN-42", common.served(page))

    def test_a_long_header_value_is_cut(self):
        self.srv.banner = "x" * 200
        self.srv.script["/l"] = [(200, {}, b"<html><title>L</title></html>")]
        self.get("/l")
        note = common.served("")
        self.assertLess(len(note), 120)


class GetTextTest(unittest.TestCase):
    """`common.get_text`: the body seven adapters had written out identically.

    Against the same local server as the rest of this file, because what it adds to
    `fetch` is a set of defaults and a decode, and both are observable.
    """

    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.srv.script, cls.srv.hits = {}, {}
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        self.srv.script.clear()
        self.srv.hits.clear()
        self.srv.banner = "TestHTTP"
        sink = contextlib.redirect_stdout(io.StringIO())
        sink.__enter__()
        self.addCleanup(sink.__exit__, None, None, None)
        temp_cache(self)          # get_text caches by default

    def test_it_returns_the_page_as_text(self):
        self.srv.script["/p"] = [(200, {}, "<h1>Näytökset</h1>".encode("utf-8"))]
        self.assertEqual(common.get_text(self.url + "/p"), "<h1>Näytökset</h1>")

    def test_one_bad_byte_costs_a_character_and_not_the_page(self):
        self.srv.script["/bad"] = [(200, {}, b"<h1>N\xff\xfeytokset</h1>")]
        got = common.get_text(self.url + "/bad")
        self.assertTrue(got.startswith("<h1>N"))
        self.assertIn("\ufffd", got)

    def test_the_defaults_are_the_ones_the_seven_wrappers_had(self):
        seen = {}
        def fake(url, **kw):
            seen.update(kw)
            return b"ok"
        common.get_text("http://example.invalid/x", fetcher=fake)
        self.assertIs(seen["cache"], True)
        self.assertEqual(seen["timeout"], 30)
        self.assertEqual(seen["headers"], common.TEXT_HEADERS)

    def test_a_caller_can_override_any_of_them(self):
        seen = {}
        def fake(url, **kw):
            seen.update(kw)
            return b"ok"
        common.get_text("http://example.invalid/x", fetcher=fake, cache=False,
                        timeout=45, headers={"accept": "application/json"}, tries=1)
        self.assertEqual((seen["cache"], seen["timeout"], seen["tries"]), (False, 45, 1))
        self.assertEqual(seen["headers"], {"accept": "application/json"})

    def test_the_fetcher_is_the_seam_the_adapter_tests_stub(self):
        """Each adapter passes its own module-level `fetch`, which its tests replace with
        a fixture. Reaching `common.fetch` here would make every one of those a no-op."""
        called = []
        common.get_text("http://example.invalid/x",
                        fetcher=lambda url, **kw: called.append(url) or b"fixture")
        self.assertEqual(called, ["http://example.invalid/x"])

    def test_a_refusal_propagates_rather_than_coming_back_as_an_empty_page(self):
        """The error path, tripped: an adapter that got "" for a 500 would read it as a
        cinema with nothing on."""
        self.srv.script["/gone"] = [(500, {}, b"boom")]
        with self.assertRaises(urllib.error.HTTPError):
            common.get_text(self.url + "/gone", tries=1)

    def test_an_oversize_body_is_refused_here_too(self):
        c = self.reload_common(KINO_MAX_BODY=500)
        self.srv.script["/huge"] = [(200, {}, b"x" * 2000)]
        with self.assertRaises(c.BodyTooLarge):
            c.get_text(self.url + "/huge")

    def reload_common(self, **env):
        return fresh_common(self, **env)


class OverrideScopeTest(unittest.TestCase):
    """An override ends with the test that set it, whichever file runs next.

    Each helper runs inside a throwaway test here, so the check does not depend on the
    order files are loaded in.
    """

    def test_an_override_is_gone_once_its_test_ends(self):
        before = (os.environ.get("KINO_MAX_BODY"), common.MAX_BODY)
        for helper in (FetchTest.reload, GetTextTest.reload_common):
            with self.subTest(helper=helper.__qualname__):
                class Inner(unittest.TestCase):
                    def runTest(inner):
                        inner.assertEqual(helper(inner, KINO_MAX_BODY=500).MAX_BODY, 500)
                result = unittest.TestResult()
                Inner().run(result)
                self.assertEqual(result.errors + result.failures, [])
                self.assertEqual((os.environ.get("KINO_MAX_BODY"), common.MAX_BODY), before)


class CacheIsolationTest(unittest.TestCase):
    """A test that caches brings its own directory, whichever test ran before it.

    The caching tests run here inside throwaway suites, each alone and then all of them
    forwards and backwards, with KINO_HTTP_CACHE unset and `common` pointed at a sentinel
    that stands in for the real `.http-cache`: the state a test is in when nothing ran
    before it.
    """

    def cases(self):
        return ([FetchTest("test_a_kept_error_body_is_never_written_to_the_cache_slot")]
                + list(unittest.defaultTestLoader.loadTestsFromTestCase(GetTextTest)))

    def test_caching_tests_pass_in_any_order_and_leave_the_real_cache_alone(self):
        saved_env, saved_dir = os.environ.pop("KINO_HTTP_CACHE", None), common.CACHE_DIR
        self.addCleanup(setattr, common, "CACHE_DIR", saved_dir)
        if saved_env is not None:
            self.addCleanup(os.environ.__setitem__, "KINO_HTTP_CACHE", saved_env)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        sentinel = common.CACHE_DIR = pathlib.Path(tmp.name) / "real-http-cache"
        n = len(self.cases())
        orders = [[i] for i in range(n)] + [list(range(n)), list(range(n))[::-1]]
        for order in orders:
            with self.subTest(order=order):
                cases = self.cases()
                result = unittest.TestResult()
                unittest.TestSuite([cases[i] for i in order]).run(result)
                self.assertEqual(result.errors + result.failures, [])
                self.assertEqual(result.testsRun, len(order))
                self.assertFalse(sentinel.exists(), "a caching test wrote the real cache")
                self.assertNotIn("KINO_HTTP_CACHE", os.environ)
                self.assertEqual(common.CACHE_DIR, sentinel)


if __name__ == "__main__":
    unittest.main()
