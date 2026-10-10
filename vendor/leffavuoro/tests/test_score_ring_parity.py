"""The pages' score ring prints what the app's prints.

`score_ring` in build_pages.py is the app's `scoreRing` as static markup, and until
2026-09-25 the two disagreed on the text: the pages wrote `str(tmdb)`, so 8.0 read "8.0"
where the app reads "8" (786 rings in 171 committed pages), and Python rounds a tie to
even where `toFixed` rounds it up, so 1250 votes read "1.2k" against the app's "1.3k".

The client's own `shortVotes` is read out of index.html and run in node over every vote
count up to 20,000 and a set above, so the two copies cannot drift apart unseen.
"""
import json
import re
import shutil
import subprocess
import unittest

import _ctx

import build_pages as bp

INDEX = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")
VOTES = list(range(0, 20001)) + [25000, 99950, 125000, 999500, 1250000]
SCORES = [0.1, 1.0, 5.5, 6.05, 7.0, 7.25, 7.5, 8.0, 8.35, 9.9, 10.0]


def client_short_votes():
    m = re.search(r"^\s*const shortVotes = (n => .*?);$", INDEX, re.M)
    if not m:
        raise AssertionError("shortVotes not found in index.html")
    return m.group(1)


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class ScoreRingParityTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        script = (f"const shortVotes = {client_short_votes()};"
                  f"const votes = {json.dumps(VOTES)}, scores = {json.dumps(SCORES)};"
                  "console.log(JSON.stringify({votes: votes.map(shortVotes),"
                  " scores: scores.map(String)}));")
        out = subprocess.run(["node", "-e", script], capture_output=True, text=True,
                             timeout=60)
        if out.returncode:
            raise AssertionError(f"node failed: {out.stderr}")
        cls.js = json.loads(out.stdout)

    def test_every_vote_count_is_shortened_as_the_app_does(self):
        ours = [bp.short_votes(n) for n in VOTES]
        diff = [(n, a, b) for n, a, b in zip(VOTES, ours, self.js["votes"]) if a != b]
        self.assertEqual(diff, [], "pages and app disagree on these vote counts")

    def test_a_score_is_printed_as_the_app_prints_it(self):
        self.assertEqual([bp.js_number(v) for v in SCORES], self.js["scores"])

    def test_the_ring_and_its_label_carry_the_same_number(self):
        t = {"rtg": "TMDB {v}/10", "rtg1": "{v} 1", "rtgN": "TMDB {v}/10, {n}", "dec": ","}
        ring = bp.score_ring(8.0, 1250, t)
        self.assertIn("<b>8</b>", ring)
        self.assertIn('aria-label="TMDB 8/10, 1250"', ring)
        self.assertIn('<span class="votes">1.3k</span>', ring)


if __name__ == "__main__":
    unittest.main()
