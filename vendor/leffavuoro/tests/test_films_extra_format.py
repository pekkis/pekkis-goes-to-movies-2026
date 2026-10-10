"""`data/films-extra.json` is written by three passes, and all three emit the same bytes.

The file is one document for the whole run. `synmerge.merge` writes provider synopses into
it per site, `enrich_tmdb.merge_extra` and `merge_shared` write TMDB text, ratings, posters
and the shared classification, and `mirror_posters` rewrites its remote poster URLs to
local paths. Both halves of the pipeline run all of that within the few minutes that
separate their commits.

Emitted on one line it cannot content-merge. A local push landing mid-run fails
`pull --rebase` on this file and fails identically all three attempts, and the cloud run's
whole commit is lost with it. One key per line and `sort_keys` make the diff something git
can reconcile: two halves that added different films touch different lines. The exposure
was measured on 2026-09-19 and no occurrence was found in 27 recorded failures, so this is
a fault closed before it fired rather than one observed.

What matters is that the three agree byte for byte, so two of them are driven for real
here and compared, and the committed file is held to the same output.
"""
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import common
import enrich_tmdb
import synmerge

ROOT = _ctx.ROOT
COMMITTED = ROOT / "data" / "films-extra.json"
WRITERS = ("synmerge.py", "enrich_tmdb.py", "mirror_posters.py")

FI = "Suomenkielinen kuvaus, jossa on ääkkösiä."
EN = "An English description."


def show(title, syn):
    return {"title": title, "start": "2026-09-19T18:00:00+03:00", "_syn": syn}


class EmitterTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)

    def emit(self, doc, name="direct.json"):
        p = self.dir / name
        common.write_films_extra(p, doc)
        return p.read_bytes()

    def test_the_format_is_one_key_per_line_sorted_with_a_final_newline(self):
        doc = {"generated": "2026-09-19",
               "films": {"zeta": {"r": 1}, "alfa": {"r": 2}}}
        text = self.emit(doc).decode("utf-8")
        self.assertTrue(text.endswith("}\n"), "no trailing newline")
        self.assertGreater(len(text.splitlines()), 6, "still emitted on one line")
        self.assertLess(text.index('"alfa"'), text.index('"zeta"'), "keys are not sorted")

    def test_finnish_text_is_not_escaped_into_ascii(self):
        """`ensure_ascii=False` is what keeps the file readable and its size down; it
        comes from write_json and has to survive the move to this emitter."""
        body = self.emit({"films": {"k": {"s": {"fi": FI}}}}).decode("utf-8")
        self.assertIn("ääkkösiä", body)
        self.assertNotIn("\\u00e4", body)

    def test_the_format_is_stated_once_and_is_what_the_emitter_uses(self):
        self.assertEqual(common.FILMS_EXTRA_FORMAT, {"indent": 1, "sort_keys": True})
        doc = {"films": {"b": {"r": 1}, "a": {"r": 2}}}
        expected = json.dumps(doc, ensure_ascii=False,
                              **common.FILMS_EXTRA_FORMAT) + "\n"
        self.assertEqual(self.emit(doc).decode("utf-8"), expected)

    def test_two_documents_that_differ_by_one_film_differ_by_a_few_lines(self):
        """The whole point. On one line the diff is the file; here it is the film."""
        base = {"generated": "2026-09-19", "films": {f"f{i}": {"r": i} for i in range(20)}}
        added = {"generated": "2026-09-19",
                 "films": dict(base["films"], f20={"r": 20})}
        a = self.emit(base, "a.json").decode("utf-8").splitlines()
        b = self.emit(added, "b.json").decode("utf-8").splitlines()
        import difflib
        changed = [x for x in difflib.unified_diff(a, b, n=0) if x[:1] in "+-"
                   and not x.startswith(("+++", "---"))]
        self.assertLessEqual(len(changed), 6, changed)


class WritersAgreeTest(unittest.TestCase):
    """Two of the three writers, driven for real against the same starting document."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)
        synmerge.reset()
        self.addCleanup(synmerge.reset)
        self.extra = self.dir / "films-extra.json"
        saved = enrich_tmdb.EXTRA
        enrich_tmdb.EXTRA = self.extra
        self.addCleanup(lambda: setattr(enrich_tmdb, "EXTRA", saved))

    def bytes_of(self):
        return self.extra.read_bytes()

    def reemit(self):
        """The same content through the emitter, into a different file. -> bytes."""
        twin = self.dir / "twin.json"
        common.write_films_extra(twin, json.loads(self.extra.read_text(encoding="utf-8")))
        return twin.read_bytes()

    def test_synmerge_writes_exactly_what_the_emitter_produces(self):
        synmerge.merge(self.dir, {"v": [show("Hetki ennen valoa", FI),
                                        show("Autofiktio", FI)]}, "p", 0)
        self.assertEqual(self.bytes_of(), self.reemit())

    def test_enrich_tmdb_writes_exactly_what_the_emitter_produces(self):
        key = synmerge.norm("The Uprising")
        enrich_tmdb.merge_extra({key: {"fi": FI, "en": EN, "p": "/p.jpg", "n": "n",
                                       "x": True, "i": 1, "g": [], "r": 7}},
                                "2026-09-19")
        self.assertEqual(self.bytes_of(), self.reemit())

    def test_the_second_enrich_pass_agrees_with_the_first(self):
        """merge_shared is the other write in that module and had its own call."""
        key = synmerge.norm("The Uprising")
        enrich_tmdb.merge_extra({key: {"fi": FI, "en": EN, "p": "", "n": "n",
                                       "x": True, "i": 1, "g": [], "r": 7}},
                                "2026-09-19")
        enrich_tmdb.merge_shared({key: {"kr": "K-12", "krs": ["a", "b"]}}, "2026-09-19")
        self.assertEqual(self.bytes_of(), self.reemit())

    def test_the_two_passes_over_one_document_leave_one_format(self):
        """Two different writers, one after the other, on the same file: the bytes are
        the emitter's either way, which is the property that makes a rebase work."""
        synmerge.merge(self.dir, {"v": [show("Autofiktio", FI)]}, "p", 0)
        after_syn = self.bytes_of()
        enrich_tmdb.merge_extra({synmerge.norm("Autofiktio"):
                                 {"fi": "", "en": EN, "p": "", "n": "n",
                                  "x": True, "i": 1, "g": [], "r": 7}},
                                "2026-09-19")
        after_tmdb = self.bytes_of()
        self.assertNotEqual(after_syn, after_tmdb, "the second pass wrote nothing")
        self.assertEqual(after_tmdb, self.reemit())
        for blob in (after_syn, after_tmdb):
            self.assertTrue(blob.endswith(b"}\n"))


class NoOtherWriterTest(unittest.TestCase):
    """mirror_posters needs Pillow and a server to drive, so its call is read instead.
    The committed file below is what catches a writer that bypasses the emitter."""

    def source(self, name):
        return (ROOT / "scripts" / "providers" / name).read_text(encoding="utf-8")

    def test_each_writer_names_the_shared_emitter(self):
        for name in WRITERS:
            with self.subTest(module=name):
                self.assertIn("common.write_films_extra(", self.source(name))

    def test_no_writer_still_emits_that_file_through_write_json(self):
        for name in WRITERS:
            body = self.source(name)
            for n, line in enumerate(body.split("\n"), 1):
                if "common.write_json(" not in line:
                    continue
                with self.subTest(module=name, line=n):
                    self.assertNotIn("EXTRA", line)
                    self.assertNotIn("extra", line)


class CommittedFileTest(unittest.TestCase):
    def test_the_committed_file_is_in_the_format_its_writers_emit(self):
        """The drift gate, and the one check that covers all three writers: whatever last
        wrote this file, re-emitting its own content has to reproduce it byte for byte. A
        pass that bypassed the emitter, or a hand edit, fails here after the next run."""
        raw = COMMITTED.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
        expected = (json.dumps(doc, ensure_ascii=False,
                               **common.FILMS_EXTRA_FORMAT) + "\n").encode("utf-8")
        self.assertEqual(raw, expected,
                         "data/films-extra.json is not in the format its three writers "
                         "emit: re-emit it, or find the writer that bypassed "
                         "common.write_films_extra")

    def test_the_file_is_not_one_line(self):
        """Stated separately from the comparison above, because that one would also pass
        on a one-line file if the format constant were changed back."""
        self.assertGreater(len(COMMITTED.read_text(encoding="utf-8").splitlines()), 1000)


if __name__ == "__main__":
    unittest.main()
