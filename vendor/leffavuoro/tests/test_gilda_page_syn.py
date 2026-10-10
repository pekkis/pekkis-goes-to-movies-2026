"""Gilda: a film the feed describes with nothing takes its film page's text.

On 2026-09-27 four films had an empty feed description, Pitchblack Playback's listening
sessions among them, and each film page carried one: a Finnish blurb between an arrival
note and a paragraph of English press quotes.
"""
import io
import json
import unittest
from contextlib import redirect_stdout

import _ctx                                                # noqa: F401
import gilda
from test_gilda_duplicates import SITE, film, payload, show

FI = ("Kuuntele levy alusta loppuun pimeässä salissa, jossa ei ole mitään muuta kuin sinä "
      "ja musiikki, kun kappaleet soivat kovaa.")
QUOTES = ("Sanottua: ”This is the best way to hear a record” — A Critic "
          "”A night to remember for all of us” — Another")
EN = ("The film follows the band on the last night of the tour, and it is a farewell to the "
      "fans who made the music matter.")
PAGE_A = "https://www.gilda.fi/elokuva/levy-a/"
PAGE_B = "https://www.gilda.fi/elokuva/film-b/"


def page(*paras):
    body = "".join(f"<p>{p}</p>\n" for p in paras)
    return (f'<main><div class="single-movie__data"><dl></dl></div>'
            f'<div class="single-movie__description"><h2>Levy A</h2>{body}</div></main>')


class PageSynTest(unittest.TestCase):
    def test_a_mixed_block_keeps_its_finnish_paragraphs(self):
        html = page("<strong>Saavuthan paikalle ajoissa.</strong>", FI, QUOTES, "Lue lisää")
        self.assertEqual(gilda.syn_language(" ".join((FI, QUOTES))), "")
        self.assertEqual(gilda.page_syn(html), {"fi": FI})

    def test_a_block_that_places_is_taken_whole(self):
        self.assertEqual(gilda.page_syn(page(EN, EN)), {"en": EN + " " + EN})

    def test_no_block_no_text(self):
        self.assertEqual(gilda.page_syn("<main><p>" + FI + "</p></main>"), {})


class FeedFirstTest(unittest.TestCase):
    DOC = payload(film(1, "Levy A", [show(1, "Levy A", "2026-09-30T17:00:00+00:00"),
                                     show(1, "Levy A", "2026-10-01T17:00:00+00:00")]),
                  {**film(2, "Film B", [show(2, "Film B", "2026-09-30T15:00:00+00:00")]),
                   "description": f"<p>{EN}</p>"})
    PAGES = {"levy a": PAGE_A, "film b": PAGE_B}

    def test_only_an_undescribed_film_wants_its_page(self):
        self.assertEqual(gilda.undescribed(self.DOC, self.PAGES), [PAGE_A])

    def test_the_page_text_fills_only_an_empty_feed_description(self):
        texts = {PAGE_A: {"fi": FI}, PAGE_B: {"fi": FI}}
        with redirect_stdout(io.StringIO()):
            rows = gilda.parse(self.DOC, SITE, self.PAGES, texts)["gd-gilda"]
        self.assertEqual([(r["title"], r.get("_syn")) for r in rows],
                         [("Levy A", {"fi": FI}), ("Levy A", {"fi": FI}),
                          ("Film B", {"en": EN})])

    def test_fetch_site_reads_the_page(self):
        asked = []

        def fetch(url, **kw):
            asked.append(url)
            if url.endswith("/movies"):
                return json.dumps(self.DOC).encode()
            if "/wp/v2/movies" in url:
                return json.dumps([] if "page=2" in url else
                                  [{"title": {"rendered": "Levy A"}, "link": PAGE_A},
                                   {"title": {"rendered": "Film B"}, "link": PAGE_B}]).encode()
            if url == PAGE_A:
                return page(FI, QUOTES).encode()
            raise AssertionError(url)
        real = gilda.fetch
        gilda.fetch = fetch
        self.addCleanup(lambda: setattr(gilda, "fetch", real))
        with redirect_stdout(io.StringIO()):
            rows = gilda.fetch_site(SITE, sleep=0)["gd-gilda"]
        self.assertEqual({r["title"]: r.get("_syn") for r in rows},
                         {"Levy A": {"fi": FI}, "Film B": {"en": EN}})
        self.assertEqual(asked.count(PAGE_A), 1)


if __name__ == "__main__":
    unittest.main()
