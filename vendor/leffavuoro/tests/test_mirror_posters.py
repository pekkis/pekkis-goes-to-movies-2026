"""mirror_posters: "mirrored everything" and "could not mirror anything" are different exits.

The dependency check returned 0 when Pillow was missing, so a missing Pillow was
indistinguishable from a clean run: nothing rewritten, every reference remote, placeholder
tiles everywhere. It exits CANNOT_RUN now.

The cases that need a real Pillow skip without one, which they do on this repo's system
interpreter; run them with a venv that has it:

    <venv-with-pillow>/bin/python -m unittest discover -s tests -p test_mirror_posters.py

The Pillow-absent cases block the import rather than stub the predicate. The
importable-but-broken case covers an install whose imaging library is incomplete. The
server is a real one on localhost, since the failure path runs through urllib,
common.fetch's retry and Pillow's decoder.
"""
import contextlib
import http.server
import io
import json
import os
import pathlib
import sys
import tempfile
import threading
import unittest

import _ctx
import mirror_posters


def jpeg_bytes(w=800, h=1200):
    """A real JPEG, comfortably over MIN_BYTES and wider than POSTER_W so the resize
    branch is exercised rather than skipped."""
    from PIL import Image
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(0, h, 4):            # enough detail that JPEG cannot squash it to 200 B
        for x in range(0, w, 4):
            px[x, y] = ((x * 7) % 256, (y * 13) % 256, ((x + y) * 3) % 256)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return buf.getvalue()


@contextlib.contextmanager
def pillow_encoder_broken():
    """Pillow imports, but writing a JPEG fails.

    The shape of an install whose imaging library is incomplete -- a wheel built against
    a libjpeg that is no longer there, a half-finished reinstall. OSError is what Pillow
    itself raises when a codec is missing, so that is what this raises.
    """
    from PIL import Image
    original = Image.Image.save

    def boom(self, *a, **kw):
        raise OSError("encoder jpeg not available")

    Image.Image.save = boom
    try:
        yield
    finally:
        Image.Image.save = original


@contextlib.contextmanager
def pillow_hidden():
    """Make `from PIL import Image` fail, the way it does on an interpreter without it.

    Blocking the import rather than monkeypatching the predicate keeps the test honest:
    a version that dropped the up-front check and let each download raise ImportError
    would still pass a stubbed one.
    """
    class Blocker:
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "PIL" or fullname.startswith("PIL."):
                raise ImportError("PIL hidden by tests/test_mirror_posters.py")
            return None

    cached = {k: v for k, v in sys.modules.items()
              if k == "PIL" or k.startswith("PIL.")}
    for k in cached:
        del sys.modules[k]
    blocker = Blocker()
    sys.meta_path.insert(0, blocker)
    try:
        yield
    finally:
        sys.meta_path.remove(blocker)
        sys.modules.update(cached)


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        body = self.server.files.get(self.path)
        if body is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class MirrorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.srv.files = {}
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
        self.srv.files.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "data").mkdir()
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.chdir, cwd)
        # Other people's CDNs, but not ours.
        self._pause, mirror_posters.PAUSE = mirror_posters.PAUSE, 0
        self.addCleanup(lambda: setattr(mirror_posters, "PAUSE", self._pause))

    # -- fixture helpers -----------------------------------------------------------

    def write_data(self, *remote_urls):
        """Two venue files and a films-extra, so the rewrite loop runs more than once.

        One file would let a version that stops after the first document pass.
        """
        a, b = remote_urls[0], remote_urls[-1]
        self.area_a = self.root / "data" / "area-fc-a.json"
        self.area_b = self.root / "data" / "area-fc-b.json"
        self.extra = self.root / "data" / "films-extra.json"
        self.area_a.write_text(json.dumps(
            {"generated": "2026-08-30T00:00:00+00:00", "dates": [], "horizon": "",
             "shows": [{"title": "A", "start": "2026-08-30T18:00:00+03:00", "img": a}]}),
            encoding="utf-8")
        self.area_b.write_text(json.dumps(
            {"generated": "2026-08-30T00:00:00+00:00", "dates": [], "horizon": "",
             "shows": [{"title": "B", "start": "2026-08-30T19:00:00+03:00", "img": b}]}),
            encoding="utf-8")
        self.extra.write_text(json.dumps({"films": {"A": {"img": a}}}), encoding="utf-8")

    def snapshot(self):
        return {p.name: p.read_bytes()
                for p in sorted((self.root / "data").glob("*.json"))}

    def run_main(self):
        """-> (exit code, [mirror] log lines)."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = mirror_posters.main()
        self.captured = buf.getvalue()
        return rc, [l for l in self.captured.splitlines() if l.startswith("[mirror]")]

    def img_of(self, path):
        return json.loads(path.read_text(encoding="utf-8"))["shows"][0]["img"]

    # -- 1. Pillow present, mirror succeeds ----------------------------------------

    @unittest.skipUnless(not mirror_posters.pillow_problem(), "Pillow unusable")
    def test_a_successful_mirror_exits_ok_and_rewrites_the_references(self):
        self.srv.files["/one.jpg"] = jpeg_bytes()
        self.srv.files["/two.jpg"] = jpeg_bytes(700, 1000)
        one, two = f"{self.url}/one.jpg", f"{self.url}/two.jpg"
        self.write_data(one, two)

        rc, lines = self.run_main()

        self.assertEqual(rc, mirror_posters.OK)
        self.assertEqual(rc, 0)
        for path in (self.area_a, self.area_b):
            self.assertTrue(self.img_of(path).startswith("data/posters/"),
                            f"{path.name} still points at a remote host")
            self.assertTrue((self.root / self.img_of(path)).exists())
        extra = json.loads(self.extra.read_text(encoding="utf-8"))
        self.assertTrue(extra["films"]["A"]["img"].startswith("data/posters/"))
        self.assertIn("2 downloaded", " ".join(lines))
        self.assertIn("0 failed", " ".join(lines))

    # -- 2. Pillow absent, default invocation --------------------------------------

    def test_a_missing_pillow_is_a_distinct_non_zero_exit(self):
        """The whole point. A caller has to be able to tell this from a clean run, and
        0 made them the same answer."""
        self.write_data(f"{self.url}/one.jpg")
        with pillow_hidden():
            rc, lines = self.run_main()

        self.assertNotEqual(rc, 0, "a missing dependency still reports success")
        self.assertEqual(rc, mirror_posters.CANNOT_RUN)
        self.assertNotEqual(mirror_posters.CANNOT_RUN, 1,
                            "1 is what an uncaught traceback already exits with")

    def test_a_missing_pillow_is_still_one_line_not_one_per_poster(self):
        """The reason the check was added in the first place, and it must survive the
        exit code change: 185 ImportErrors read like the network is down."""
        self.write_data(f"{self.url}/one.jpg", f"{self.url}/two.jpg")
        with pillow_hidden():
            _, lines = self.run_main()

        self.assertEqual(len(lines), 1, f"one explanatory line, got: {lines}")
        self.assertIn("Pillow", lines[0])
        self.assertIn("pip install pillow", lines[0])

    # -- 3. The local path: showtimes still publishable, degradation detectable -----

    def test_a_missing_pillow_leaves_the_fresh_showtimes_untouched(self):
        """There is no --optional mode because neither caller needs one: both commit or
        publish the data before they look at this exit code. What makes that safe is that
        nothing here is half-written -- the check is the first statement in main(), so a
        run that cannot mirror leaves exactly what the fetch wrote."""
        self.write_data(f"{self.url}/one.jpg", f"{self.url}/two.jpg")
        before = self.snapshot()
        with pillow_hidden():
            rc, _ = self.run_main()

        self.assertEqual(rc, mirror_posters.CANNOT_RUN)
        self.assertEqual(self.snapshot(), before,
                         "a run that cannot mirror still rewrote the schedule files")
        self.assertFalse((self.root / "data" / "posters").exists(),
                         "an empty posters directory was created for nothing")

    def test_the_degradation_is_visible_in_the_committed_log_not_only_in_the_code(self):
        """`run-posters*.log` is what gets read, per CLAUDE.md, so the line has to say
        what happened to the posters rather than only naming the missing package."""
        self.write_data(f"{self.url}/one.jpg")
        with pillow_hidden():
            _, lines = self.run_main()
        self.assertRegex(lines[0], r"no poster can be mirrored")
        self.assertRegex(lines[0], r"placeholder")

    @unittest.skipUnless(not mirror_posters.pillow_problem(), "Pillow unusable")
    def test_an_importable_but_broken_pillow_is_cannot_run_too(self):
        """Checking the import was never the question. An install that cannot encode
        passes `from PIL import Image` and then fails once per poster -- exit 0, "N
        failed", and the degradation is silent again one layer in."""
        self.write_data(f"{self.url}/one.jpg", f"{self.url}/two.jpg")
        self.srv.files["/one.jpg"] = jpeg_bytes()
        self.srv.files["/two.jpg"] = jpeg_bytes()
        before = self.snapshot()

        with pillow_encoder_broken():
            rc, lines = self.run_main()

        self.assertEqual(rc, mirror_posters.CANNOT_RUN)
        self.assertEqual(len(lines), 1, f"one line, not one per poster: {lines}")
        self.assertEqual(self.snapshot(), before)

    @unittest.skipUnless(not mirror_posters.pillow_problem(), "Pillow unusable")
    def test_the_two_ways_pillow_can_be_unusable_say_different_things(self):
        """They need different fixes, and telling someone who has Pillow installed to
        install Pillow is worse than saying nothing."""
        with pillow_hidden():
            absent = mirror_posters.pillow_problem()
        with pillow_encoder_broken():
            broken = mirror_posters.pillow_problem()

        self.assertTrue(absent and broken)
        self.assertNotEqual(absent, broken)
        self.assertIn("not installed", absent)
        self.assertNotIn("force-reinstall", absent)
        self.assertIn("cannot encode", broken)
        self.assertIn("force-reinstall", broken)

    def test_a_usable_pillow_reports_no_problem(self):
        """The empty-string contract from the other side. A predicate that always found a
        reason would turn every run into CANNOT_RUN, which is the opposite failure and
        just as quiet -- posters would stop being mirrored and the log would explain why
        every time, four times a day, until someone read it."""
        try:
            import PIL                                          # noqa: F401
        except Exception:
            self.assertIn("not installed", mirror_posters.pillow_problem())
        else:
            self.assertEqual(mirror_posters.pillow_problem(), "")

    # -- 4. A poster that fails to download keeps its old semantics -----------------

    @unittest.skipUnless(not mirror_posters.pillow_problem(), "Pillow unusable")
    def test_a_failed_download_is_logged_left_remote_and_not_fatal(self):
        """kinoakseli.fi challenges datacenter IPs and fails every cloud run by design.
        Making a download failure fatal would hand a third party the ability to fail the
        build, which is why this stays exit 0 while a missing dependency does not."""
        self.srv.files["/one.jpg"] = jpeg_bytes()
        good, bad = f"{self.url}/one.jpg", f"{self.url}/gone.jpg"
        self.write_data(good, bad)

        rc, lines = self.run_main()

        self.assertEqual(rc, mirror_posters.OK)
        self.assertTrue(self.img_of(self.area_a).startswith("data/posters/"))
        self.assertEqual(self.img_of(self.area_b), bad,
                         "a poster that failed must keep its remote address")
        joined = " ".join(lines)
        self.assertIn("1 failed", joined)
        self.assertIn("127.0.0.1", joined)

    @unittest.skipUnless(not mirror_posters.pillow_problem(), "Pillow unusable")
    def test_every_poster_failing_is_still_not_the_same_as_cannot_run(self):
        """The boundary between the two states, from the other side."""
        self.write_data(f"{self.url}/gone-a.jpg", f"{self.url}/gone-b.jpg")
        rc, lines = self.run_main()
        self.assertEqual(rc, mirror_posters.OK)
        self.assertIn("2 failed", " ".join(lines))

    # -- 5. The cloud caller cannot pass silently ----------------------------------

    def test_the_cloud_workflow_gates_on_this_exit_code(self):
        """Requirement five lives in the caller, so it is pinned in the caller. The mirror
        step runs `set +e`, so without both halves of this -- recording $? and comparing it
        -- a non-zero exit here changes nothing at all."""
        wf = (_ctx.ROOT / ".github" / "workflows" / "biorex.yml").read_text(encoding="utf-8")
        self.assertRegex(wf, r'mirror_posters\.py[^\n]*\n\s*code=\$\?',
                         "the mirror step no longer records its exit code")
        self.assertRegex(wf, r'echo "\$code" > "\$RUNNER_TEMP/mirrorfail"')
        self.assertRegex(wf, r'cat "\$RUNNER_TEMP/mirrorfail"\)" = 0 \]',
                         "the failure gate no longer reads mirrorfail")

    def test_pillow_is_installed_by_the_cloud_workflow_so_absence_is_a_real_failure(self):
        """Why the cloud treats CANNOT_RUN as a failure rather than tolerating it: Pillow
        is installed in the job itself, so it is missing only when that install broke."""
        wf = (_ctx.ROOT / ".github" / "workflows" / "biorex.yml").read_text(encoding="utf-8")
        self.assertRegex(wf, r"\n\s*pillow==\d+\.\d+\.\d+ \\\n\s*--hash=sha256:[0-9a-f]{64}",
                         "Pillow is no longer pinned by version and hash in the workflow")
        self.assertRegex(wf, r"pip install[^\n]*--require-hashes",
                         "Pillow is no longer installed with --require-hashes")


if __name__ == "__main__":
    unittest.main()
