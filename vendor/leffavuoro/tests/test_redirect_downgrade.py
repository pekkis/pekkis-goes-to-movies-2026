"""The shared fetch never follows a redirect from https to http.

urllib's default redirect handler follows one, so a WordPress site whose `siteurl` is
http:// answering 301 would have its programme read over cleartext with nothing logged,
against CLAUDE.md's rule never to follow an `https:` -> `http:` redirect (audit C7,
2026-09-25). `common.NoDowngradeRedirect` refuses it and the request fails at once, not
after the retries: asking again gets the same redirect. A plain-HTTP site the rule allows
(Bio Savoy, Alatalo) and every upgrade are followed as before.
"""
import email.message
import http.server
import io
import threading
import unittest
import urllib.request

import _ctx                                                # noqa: F401
import biorex
import common
import johku


def redirect(frm, to, code=301):
    h = common.NoDowngradeRedirect()
    hdrs = email.message.Message()
    hdrs["Location"] = to
    return h.redirect_request(urllib.request.Request(frm), io.BytesIO(b""), code, "Moved",
                              hdrs, to)


class HandlerTest(unittest.TestCase):

    def test_https_to_http_is_refused(self):
        with self.assertRaises(common.DowngradeRefused) as ctx:
            redirect("https://kino.test/elokuvat/", "http://kino.test/elokuvat/")
        self.assertIn("http://kino.test/elokuvat/", str(ctx.exception))

    def test_the_scheme_is_compared_without_regard_to_case(self):
        with self.assertRaises(common.DowngradeRefused):
            redirect("HTTPS://kino.test/", "Http://kino.test/")

    def test_every_other_redirect_is_followed_as_before(self):
        for frm, to in (("https://kino.test/a", "https://www.kino.test/a"),
                        ("http://kino.test/a", "https://kino.test/a"),
                        ("http://kino.test/a", "http://kino.test/b")):
            with self.subTest(frm=frm, to=to):
                self.assertEqual(redirect(frm, to).full_url, to)

    def test_the_shared_opener_and_the_adapters_own_carry_it_and_no_plain_handler(self):
        for name, op in (("common", common._OPENER), ("biorex", biorex._opener()),
                         ("johku", johku.OPENER)):
            with self.subTest(opener=name):
                kinds = [type(h) for h in op.handlers]
                self.assertIn(common.NoDowngradeRedirect, kinds)
                self.assertNotIn(urllib.request.HTTPRedirectHandler, kinds)


class Redirecting(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/old":
            self.send_response(301)
            self.send_header("Location", "/new")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


class FetchTest(unittest.TestCase):

    def test_a_plain_http_redirect_is_still_followed_through_fetch(self):
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Redirecting)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        self.assertEqual(common.fetch(f"http://127.0.0.1:{srv.server_port}/old", tries=1), b"ok")

    def test_a_refused_downgrade_fails_the_request_without_retrying(self):
        calls = []

        class Refusing:
            def open(self, req, timeout=None):
                calls.append(req.full_url)
                raise common.DowngradeRefused("refused a redirect from https to http")
        saved = common._OPENER
        common._OPENER = Refusing()
        self.addCleanup(lambda: setattr(common, "_OPENER", saved))
        with self.assertRaises(common.DowngradeRefused):
            common.fetch("https://kino.test/elokuvat/", tries=3, backoff=0)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
