"""One site's fetch has a wall-clock deadline, and a site past it fails alone.

`timeout` bounds one socket operation. A host that answered its listing and then stalled
cost Cinemahouse 105 s per film page (3 x 30 s plus the backoffs), 35 minutes for twenty,
and a cloud run was capped only by the job's 30 minutes, where Actions cancels before the
commit step: no cloud site's data or logs published while the host stayed stalled (audit
C1, 2026-09-25). `common.site_deadline` bounds the fetch and `run_cloud` puts every site
inside one. Real local servers, one that stalls and one that drips its body.
"""
import http.server
import threading
import time
import unittest

import _ctx                                                # noqa: F401
import common
import run_cloud
import test_cloud_pool as C
import test_run_pool as P


class Drip(http.server.BaseHTTPRequestHandler):
    """Headers at once, then the body one byte every 0.1 s: no socket timeout ever fires."""
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", "200")
        self.end_headers()
        try:
            for _ in range(200):
                self.wfile.write(b"x")
                self.wfile.flush()
                time.sleep(0.1)
        except OSError:
            pass

    def log_message(self, *a):
        pass


class FetchTest(unittest.TestCase):

    def serve(self, handler):
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, args=(0.01,), daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_port}"

    def test_a_dripping_body_ends_at_the_deadline(self):
        url = self.serve(Drip) + "/film"
        t0 = time.monotonic()
        with self.assertRaises(common.SiteDeadline):
            with common.site_deadline(0.5):
                common.fetch(url, tries=3, backoff=0)
        self.assertLess(time.monotonic() - t0, 3, "the drip ran on past the deadline")

    def test_a_deadline_the_adapter_swallows_still_ends_the_site(self):
        url = self.serve(Drip) + "/film"
        with self.assertRaises(common.SiteDeadline):
            with common.site_deadline(0.3):
                try:
                    common.fetch(url, tries=1)
                except Exception:
                    pass                     # a page loop that catches and goes on
                return_value = "published"   # noqa: F841 -- the body carried on

    def test_no_deadline_is_no_bound(self):
        h = P.Hosts(1, delay=0.2)
        self.addCleanup(h.close)
        with common.site_deadline(None):
            self.assertEqual(common.fetch(h.base(0) + "/x/p"), b"ok")
        self.assertIsNone(common._deadline_left())


class CloudRunTest(C.CloudTestCase):

    def test_a_stalled_site_fails_and_the_rest_publish(self):
        saved = run_cloud.SITE_DEADLINE
        run_cloud.SITE_DEADLINE = 0.5
        self.addCleanup(lambda: setattr(run_cloud, "SITE_DEADLINE", saved))
        h = self.hosts(2, delay=0)
        h.servers[0].delay = 4                       # answers nothing for four seconds
        mods = [C.module("mod_a", P.site("a0", h.base(0)), requests=3),
                C.module("mod_b", P.site("b0", h.base(1)))]
        t0 = time.monotonic()
        code, logs = self.cloud(mods)
        self.assertLess(time.monotonic() - t0, 3.5, "the run waited out the stalled host")
        self.assertEqual(code, 1)
        self.assertIn("[a0] FAILED:", logs["mod_a"])
        self.assertIn("deadline", logs["mod_a"])
        self.assertRegex(logs["mod_b"], r"(?m)^exit=0\s*$")
        self.assertTrue((self.out / "venues-b0.json").exists())
        self.assertFalse((self.out / "venues-a0.json").exists())


if __name__ == "__main__":
    unittest.main()
