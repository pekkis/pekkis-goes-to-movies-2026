"""`fetch_data.http_get` goes through `common.fetch`, and the proof is behaviour.

The Finnkino half used a bare `urlopen().read()` for the schedule API, the poster
downloads and the TMDB calls: no retry, no body cap, no `Retry-After`, no refusal line.
Asserting that the source now says `common.fetch` would only confirm the source says it,
so these tests drive a real HTTP server on localhost and read what the client does, the
way `tests/test_common_fetch.py` does for the function itself.

`scripts/fetch_data.py` cannot run on a runner: www.finnkino.fi answers a datacenter
address Cloudflare 403 and the token comes from the local wrapper. What runs here is the
one function that talks to a socket.
"""
import contextlib
import http.server
import importlib
import io
import os
import pathlib
import sys
import threading
import unittest

import _ctx                                                # noqa: F401
import _no_sleep as no_sleep
import common
from _http_cache import temp_cache

# An adapter binds `EmptyProgramme` at import time and `importlib.reload(common)` builds a
# new class object, so a module imported earlier stops recognising what the reloaded one
# raises. Ten tests in five other files went red the first time this file reloaded without
# putting the class back. Same trap `tests/test_common_fetch.py` records.
EMPTY_PROGRAMME = common.EmptyProgramme

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import fetch_data                                          # noqa: E402


class Handler(http.server.BaseHTTPRequestHandler):
    """Replays a scripted list of responses per path, then repeats the last one."""
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        self.server.hits[self.path] = self.server.hits.get(self.path, 0) + 1
        steps = self.server.script.get(self.path) or [(200, {}, b"ok")]
        status, hdrs, body = steps.pop(0) if len(steps) > 1 else steps[0]
        self.send_response(status)
        for k, v in hdrs.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class HttpGetTest(unittest.TestCase):
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
        sink = contextlib.redirect_stdout(io.StringIO())
        sink.__enter__()
        self.addCleanup(sink.__exit__, None, None, None)

    def reload(self, **env):
        """A fresh `common` so the throttle budget starts at zero, rebound into
        fetch_data, which holds its own reference to the module."""
        for k in ("KINO_RETRY_AFTER_MAX", "KINO_RETRY_AFTER_BUDGET", "KINO_MAX_BODY"):
            os.environ.pop(k, None)
        os.environ.update({k: str(v) for k, v in env.items()})
        temp_cache(self)
        mod = importlib.reload(common)
        mod.EmptyProgramme = EMPTY_PROGRAMME
        old = fetch_data.common
        fetch_data.common = mod
        self.addCleanup(lambda: setattr(fetch_data, "common", old))
        self.addCleanup(self._restore)
        self.clock = no_sleep.patch(self, mod)  # Retry-After is counted, not sat out
        return mod

    @staticmethod
    def _restore():
        """Back to a module with the counters clear and the class the adapters hold."""
        for k in ("KINO_RETRY_AFTER_MAX", "KINO_RETRY_AFTER_BUDGET", "KINO_MAX_BODY"):
            os.environ.pop(k, None)
        importlib.reload(common).EmptyProgramme = EMPTY_PROGRAMME

    def test_it_returns_the_body(self):
        self.srv.script["/ok"] = [(200, {}, b'{"x": 1}')]
        self.assertEqual(fetch_data.http_get(self.url + "/ok", {"user-agent": "t"}),
                         b'{"x": 1}')

    def test_a_transient_failure_is_retried_instead_of_failing_the_fetch(self):
        """The bare urlopen made one 502 on one business date fail all seven days."""
        self.reload()
        self.srv.script["/flaky"] = [(502, {}, b"nope"), (200, {}, b"good")]
        self.assertEqual(fetch_data.http_get(self.url + "/flaky", {"user-agent": "t"},
                                             backoff=0),
                         b"good")
        self.assertEqual(self.srv.hits["/flaky"], 2)

    def test_a_429_is_waited_out_on_the_interval_the_upstream_names(self):
        mod = self.reload(KINO_RETRY_AFTER_MAX=5, KINO_RETRY_AFTER_BUDGET=30)
        self.srv.script["/throttled"] = [(429, {"Retry-After": "1"}, b"slow down"),
                                         (200, {}, b"good")]
        self.assertEqual(fetch_data.http_get(self.url + "/throttled", {"user-agent": "t"}),
                         b"good")
        self.assertEqual(mod.throttle_stats()["waited"], 1)

    def test_a_429_asking_for_longer_than_the_ceiling_is_not_retried(self):
        mod = self.reload(KINO_RETRY_AFTER_MAX=2, KINO_RETRY_AFTER_BUDGET=30)
        self.srv.script["/forever"] = [(429, {"Retry-After": "9999"}, b"no")]
        with self.assertRaises(Exception):
            fetch_data.http_get(self.url + "/forever", {"user-agent": "t"})
        self.assertEqual(self.srv.hits["/forever"], 1)
        self.assertEqual(mod.throttle_stats()["refused"], 1)

    def test_an_oversize_body_is_refused_rather_than_read(self):
        """A poster download is the one big body this script asks for."""
        mod = self.reload(KINO_MAX_BODY=1000)
        self.srv.script["/huge"] = [(200, {}, b"x" * 5000)]
        with self.assertRaises(mod.BodyTooLarge):
            fetch_data.http_get(self.url + "/huge", {"user-agent": "t"})

    def test_a_gzipped_body_is_still_unpacked_here(self):
        """`common.fetch` returns the body as served; the gunzip is this script's."""
        import gzip as gz
        self.srv.script["/gz"] = [(200, {}, gz.compress(b'{"x": 1}'))]
        self.assertEqual(fetch_data.http_get(self.url + "/gz", {"user-agent": "t"}),
                         b'{"x": 1}')

    def test_the_headers_the_caller_passes_reach_the_server(self):
        """The Finnkino token rides in `authorization`, so it has to survive the move."""
        seen = {}

        class Peek(Handler):
            def do_GET(self):
                seen.update({k.lower(): v for k, v in self.headers.items()})
                Handler.do_GET(self)

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Peek)
        srv.script, srv.hits = {}, {}
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            fetch_data.http_get(f"http://127.0.0.1:{srv.server_address[1]}/x",
                                {"authorization": "Bearer tok", "user-agent": "kino"})
        finally:
            srv.shutdown()
            srv.server_close()
        self.assertEqual(seen.get("authorization"), "Bearer tok")
        self.assertEqual(seen.get("user-agent"), "kino")


if __name__ == "__main__":
    unittest.main()
