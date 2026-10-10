"""The Kino-Huovi reader: one front page, one blog card per film.

The fixtures are the markup as read on 2026-09-21, cut to the smallest shape that still
exercises a rule. Two cards everywhere there is a loop.

What they exist to prove:

- **A range expands only when the weekdays and the dates agree.** `25.-28.9. PE, LA, SU ja
  MA` is four screenings and the four weekdays are what proves the four days; a card whose
  weekdays do not line up publishes nothing rather than a guess.
- **No date on the page carries a year**, so every screening is placed by
  `common.resolve_year` from the weekday. A page left up past its week selects a year the
  window then refuses.
- **The card's own link is not a film key.** The live card titled `RAKKAUTTA JA
  VIRTAHEPOJA` is served at `/hetki ennen valoa`, so `eventId` is a slug of the title.
- **A ticket line settles a price only when it is one bare amount.**
- **A card with no date publishes nothing**, which is the state `PRESIDENTIN KYYDITYS` was
  in when this cinema was first read.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import kinohuovi as K
import registry
import run


SITE = K.SITES[0]
BASE = SITE["base"]
VENUE = SITE["venues"][0]["id"]
LISTING = BASE + SITE["listing"]
TODAY = datetime.date(2026, 9, 21)
CDN = "https://le-de.cdn-website.com/ba201/dms3rep/multi/opt"


def card(alias="uusi-elokuva", title="PRESIDENTIN KYYDITYS",
         desc="PRESIDENTIN KYYDITYS 21.9. MA klo 18.00 Kestoaika n.1t30min. Liput 12&euro;.",
         img=f"{CDN}/PRESIDENTIN+KYYDITYS-1920w.jpg"):
    """One `postArticle`, in the order the live page renders it."""
    art = (f'<div class="blogImg lazy" data-background-image="{img}">'
           f'<img src="{img}" loading="lazy"/></div>' if img else "")
    return (f'<div style="-ms-grid-column:1" class="postArticle "><div class="inner">'
            f'<a class="blogImgLink" href="/{alias}">{art}</a>'
            f'<div class="postTextContainer"><div class="postText clearfix">'
            f'<div class="postTitle"> <h3> <a href="/{alias}">{title}</a> </h3> </div>'
            f'<div class="authorBar"><span>3. helmikuuta 2026</span></div>'
            f'<div class="postDescription">{desc}</div>'
            f'</div></div></div></div>')


RANGE = card(alias="hetki ennen valoa", title="RAKKAUTTA JA VIRTAHEPOJA",
             desc="RAKKAUTTA JA VIRTAHEPOJA 25.-28.9. PE, LA, SU ja MA klo 18.00 "
                  "Kestoaika n. 1t 40min. Liput 12&euro;.",
             img=f"{CDN}/RAKKAUTTA+JA+VIRTAHEPOJA-1920w.jpg")


def page(*cards):
    return ('<html><body><div class="mainBlog layout4"><div class="inner">'
            + "".join(cards or (card(),)) + "</div></div></body></html>")


class CardTest(unittest.TestCase):
    def rows(self, *cards, today=TODAY):
        return K.rows(SITE, page(*cards), today)

    def test_a_single_date_and_a_range_both_become_rows(self):
        shows, report = self.rows(card(), RANGE)
        self.assertEqual(report["cards"], 2)
        self.assertEqual([(s["title"], s["start"]) for s in shows], [
            ("PRESIDENTIN KYYDITYS", "2026-09-21T18:00:00+03:00"),
            ("RAKKAUTTA JA VIRTAHEPOJA", "2026-09-25T18:00:00+03:00"),
            ("RAKKAUTTA JA VIRTAHEPOJA", "2026-09-26T18:00:00+03:00"),
            ("RAKKAUTTA JA VIRTAHEPOJA", "2026-09-27T18:00:00+03:00"),
            ("RAKKAUTTA JA VIRTAHEPOJA", "2026-09-28T18:00:00+03:00"),
        ])

    def test_the_one_time_on_the_card_applies_to_every_date_of_the_range(self):
        shows, _ = self.rows(RANGE)
        self.assertEqual(sorted({s["start"][11:16] for s in shows}), ["18:00"])

    def test_weekdays_that_do_not_line_up_with_the_dates_publish_nothing(self):
        """25.-28.9.2026 is Friday to Monday. A card claiming otherwise is not expanded."""
        shows, report = self.rows(card(
            desc="X 25.-28.9. MA, TI, KE ja TO klo 18.00 Liput 12&euro;."))
        self.assertEqual((shows, report["mismatch"]), ([], 1))

    def test_a_weekday_count_that_does_not_match_the_day_count_publishes_nothing(self):
        shows, report = self.rows(card(desc="X 25.-28.9. PE ja LA klo 18.00 Liput 12&euro;."))
        self.assertEqual((shows, report["mismatch"]), ([], 1))

    def test_more_weekdays_than_dates_publishes_nothing(self):
        """The count check, not the per-day weekday check, is what refuses this: the first
        four of the five line up, so cycling or truncating them would publish four rows."""
        shows, report = self.rows(card(
            desc="X 25.-28.9. PE, LA, SU, MA ja TI klo 18.00 Liput 12&euro;."))
        self.assertEqual((shows, report["mismatch"]), ([], 1))

    def test_a_card_with_no_date_is_counted_and_left_out(self):
        """The state this cinema's first card was in when it was first read."""
        shows, report = self.rows(card(desc="PRESIDENTIN KYYDITYS Tulossa pian."), RANGE)
        self.assertEqual(report["undated"], 1)
        self.assertEqual({s["title"] for s in shows}, {"RAKKAUTTA JA VIRTAHEPOJA"})

    def test_the_year_comes_from_the_weekday_because_the_page_prints_none(self):
        """21.9. is a Monday in 2026 and a Sunday in 2025, and the card says MA."""
        shows, _ = self.rows(card())
        self.assertEqual(shows[0]["start"], "2026-09-21T18:00:00+03:00")

    def test_a_date_the_window_refuses_is_counted_and_left_out(self):
        shows, report = self.rows(card(desc="X 1.6. TI klo 18.00 Liput 12&euro;."))
        self.assertEqual((shows, report["mismatch"]), ([], 1))

    def test_a_month_out_of_range_is_counted_and_left_out(self):
        shows, report = self.rows(card(desc="X 25.99. PE klo 18.00 Liput 12&euro;."))
        self.assertEqual((shows, report["unreadable"]), ([], 1))

    def test_a_card_stating_no_weekday_still_publishes_and_is_counted(self):
        shows, report = self.rows(card(desc="X 25.9. klo 18.00 Liput 12&euro;."))
        self.assertEqual([s["start"] for s in shows], ["2026-09-25T18:00:00+03:00"])
        self.assertEqual(report["no_weekday"], 1)

    def test_a_card_with_more_times_than_dates_settles_nothing(self):
        shows, report = self.rows(card(
            desc="X 25.9. PE klo 18.00 ja klo 20.15 Liput 12&euro;."))
        self.assertEqual((shows, report["mismatch"]), ([], 1))

    def test_as_many_times_as_dates_pairs_them_in_order(self):
        shows, _ = self.rows(card(
            desc="X 25.-26.9. PE ja LA klo 18.00 klo 20.15 Liput 12&euro;."))
        self.assertEqual([s["start"] for s in shows],
                         ["2026-09-25T18:00:00+03:00", "2026-09-26T20:15:00+03:00"])

    def test_the_title_keys_the_row_and_is_published_verbatim(self):
        """The card's own alias is recycled: this one is served at /hetki ennen valoa."""
        s = self.rows(RANGE)[0][0]
        self.assertEqual(s["eventId"], "rakkautta-ja-virtahepoja")
        self.assertEqual(s["title"], "RAKKAUTTA JA VIRTAHEPOJA")

    def test_an_alias_with_spaces_is_published_as_an_absolute_encoded_url(self):
        s = self.rows(RANGE)[0][0]
        self.assertEqual(s["url"], f"{BASE}/hetki%20ennen%20valoa")

    def test_the_show_shape(self):
        s = self.rows(card())[0][0]
        self.assertEqual((s["provider"], s["venue"], s["aud"], s["lang"], s["method"],
                          s["original"], s["genres"], s["rating"], s["soldOut"]),
                         ("kinohuovi", VENUE, "", "", "", "", "", "", False))
        self.assertEqual(s["theatre"], "Kino-Huovi")
        self.assertEqual((s["len"], s["price"]), ("90", "12€"))

    def test_the_card_image_is_published_as_the_poster(self):
        s = self.rows(card())[0][0]
        self.assertEqual(s["img"], f"{CDN}/PRESIDENTIN+KYYDITYS-1920w.jpg")

    def test_a_card_with_no_image_still_publishes(self):
        shows, _ = self.rows(card(img=""))
        self.assertEqual((len(shows), shows[0]["img"]), (1, ""))


class FieldTest(unittest.TestCase):
    def test_the_runtime_counts_the_hours(self):
        for kesto, want in (("Kestoaika n.1t30min.", "90"),
                            ("Kestoaika n. 1t 40min.", "100"),
                            ("Kestoaika 95 min", "95"), ("", "")):
            with self.subTest(kesto=kesto):
                self.assertEqual(K.minutes_of(kesto), want)

    def test_one_bare_amount_is_published(self):
        for line, want in (("Liput 12€.", "12€"), ("Liput 9,50 €", "9,50€"),
                           ("Kestoaika 95 min. Liput 14€.", "14€")):
            with self.subTest(line=line):
                self.assertEqual(K.price_of(line), want)

    def test_an_amount_with_anything_beside_it_settles_nothing(self):
        for line in ("Liput 12€ / 10€.", "Liput 12€ (lapset 8€).",
                     "Liput ovelta.", "Liput 12€ alkaen jotain", ""):
            with self.subTest(line=line):
                self.assertEqual(K.price_of(line), "")

    def test_the_slug_is_a_stable_key_for_the_published_title(self):
        self.assertEqual(K.slug_of("RAKKAUTTA JA VIRTAHEPOJA"), "rakkautta-ja-virtahepoja")
        self.assertEqual(K.slug_of("Hetki ennen valoa!"), "hetki-ennen-valoa")


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._get = K.get_text
        self.addCleanup(lambda: setattr(K, "get_text", self._get))
        self.calls = []

    def serve(self, pages):
        def get_text(url, **kw):
            self.calls.append(url)
            body = pages.get(url)
            if isinstance(body, Exception):
                raise body
            if body is None:
                raise RuntimeError(f"unexpected fetch {url}")
            return body
        K.get_text = get_text

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["kinohuovi", "--half", "all"])
        return code, out.getvalue() + err.getvalue()

    def test_the_site_publishes_from_one_request(self):
        self.serve({LISTING: page(card(), RANGE)})
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertEqual(self.calls, [LISTING])
        shows = json.loads(
            (run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))["shows"]
        self.assertEqual(sorted({s["title"] for s in shows}),
                         ["PRESIDENTIN KYYDITYS", "RAKKAUTTA JA VIRTAHEPOJA"])

    def test_a_page_with_no_dated_card_fails_and_keeps_the_previous_file(self):
        """No sentence on this site says the programme is empty, so a zero-row parse is a
        broken read rather than evidence of one."""
        kept = {"generated": "2026-09-20T00:00:00+00:00", "dates": ["2026-09-20"],
                "horizon": "2026-09-20",
                "shows": [{"title": "Yesterday", "start": "2026-09-20T17:00:00+03:00"}]}
        (run.OUT / f"area-{VENUE}.json").write_text(json.dumps(kept), encoding="utf-8")
        self.serve({LISTING: page(card(desc="PRESIDENTIN KYYDITYS Tulossa pian."))})
        code, log = self.main()
        self.assertNotEqual(code, 0)
        self.assertIn("no programme card", log)
        after = json.loads((run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))
        self.assertEqual(after["shows"][0]["title"], "Yesterday")

    def test_a_refused_request_keeps_the_previous_file(self):
        kept = {"generated": "2026-09-20T00:00:00+00:00", "dates": [], "horizon": "",
                "shows": [{"title": "Yesterday", "start": "2026-09-20T17:00:00+03:00"}]}
        (run.OUT / f"area-{VENUE}.json").write_text(json.dumps(kept), encoding="utf-8")
        self.serve({LISTING: RuntimeError("503 refused")})
        code, log = self.main()
        self.assertNotEqual(code, 0)
        after = json.loads((run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))
        self.assertEqual(after["shows"][0]["title"], "Yesterday")


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("kinohuovi")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Kino-Huovi", "kinohuovi.fi", "door", "kinohuovi", "local"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"] == p["accent"]), 1)

    def test_the_site_names_the_host_it_is_read_from(self):
        self.assertEqual(SITE["base"], "https://www.kinohuovi.fi")
        self.assertNotIn("reads", SITE)


if __name__ == "__main__":
    unittest.main()
