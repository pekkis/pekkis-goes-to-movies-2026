"""Navettakino: a weekend list in prose, and a shelf of film blocks under it.

The fixtures are the markup as read on 2026-09-19. What they exist to prove:

- **The list is the schedule, the blocks are metadata.** The page carried three blocks and
  two screenings, so a block without a screening publishes nothing and a screening without
  a block publishes anyway, which is the rule that keeps a thinly described film.
- **A film title is the paragraph a figure follows**, because the editor's `<strong>` is
  not reliable: the live page closes one early, "Presidentin kyydity</strong>s".
- **An empty weekend is confirmed, a missing heading is not.** The first is what this
  cinema does most weeks; the second is a template change and raises. So does an empty
  listing on a page that prints a date or time elsewhere: the listing missed it.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import navetta as N
import registry
import run


SITE = N.SITES[0]
PAGE_URL = "https://www.navettakino.fi/"
TODAY = datetime.date(2026, 9, 19)          # a Saturday
INTRO = ("Tervetuloa elokuviin Navettakinoon! Meillä on näytöksiä pääsääntöisesti vain "
         "viikonloppuisin, mutta toiminta on hieman epäsäännöllistä. Esitysajat "
         "ilmestyvät tälle sivulle aina alkuviikosta, mikäli viikonlopulle on näytöksiä "
         "tulossa.")
POSTER = ('<img fetchpriority="high" decoding="async" width="719" height="1024" '
          'src="https://www.navettakino.fi/wp-content/uploads/2026/09/juliste-719x1024.jpg" '
          'alt="" class="wp-image-292" />')
LANDSCAPE = ('<img decoding="async" width="1200" height="800" '
             'src="https://www.navettakino.fi/wp-content/uploads/2026/09/banner.jpg" />')


def p(text):
    return f'<p class="wp-block-paragraph">{text}</p>'


def figure(img=POSTER):
    return f'<figure class="wp-block-image size-large is-resized"><a href="#">{img}</a></figure>'


def block(title, meta="K7, 87 min, liput 10 €", syn="Klaus Härön uutuuselokuva kertoo.",
          img=POSTER, bold=True):
    """`bold="early"` closes the `<strong>` before the title's last letter, which is what
    the live page does to Presidentin kyyditys."""
    if bold == "early":
        head = f"<strong>{title[:-1]}</strong>{title[-1]}"
    else:
        head = f"<strong>{title}</strong>" if bold else title
    out = p(head) + (figure(img) if img else "")
    if syn:
        out += p(syn)
    if meta:
        out += p(meta)
    return out


def screening(title, *lines):
    return p(title + "<br>" + "<br>".join(lines))


def page(listed=(), shelf=(), heading=True, intro=True, blank=True):
    body = (p(INTRO) if intro else "") + p("Navettakinossa onnistuu tilausnäytökset.") + p("<br>")
    if heading:
        body += p("<strong>Tulevan viikolopun näytökset</strong>")
    body += "".join(listed) + (p("<br><br>") if blank else "") + "".join(shelf)
    return ('<html><body><article><header class="entry-header">'
            "<h1 class=\"entry-title\"><span>Elokuvat</span></h1></header>"
            '<div class="entry-content is-layout-constrained has-global-padding">'
            + body + "</div></article></body></html>")


TWO = page(
    listed=[screening("Hetki ennen valoa", "su 20.9 klo 15:00"),
            screening("Presidentin kyyditys", "su 20.9 klo 17:00")],
    shelf=[block("Hetki ennen valoa"),
           block("Presidentin kyyditys", bold="early",
                 meta="Kesto 1 h 27 min, K12, liput 10 €", syn="Tositapahtumien inspiroima."),
           block("Ryhmä Hau: Dinoelokuva", meta="Kesto 1 h 29 min, K7, liput 10 €")])


class RowsTest(unittest.TestCase):
    def rows(self, html, today=None):
        return N.rows(SITE, html, today or TODAY)

    def test_the_weekday_places_a_line_that_prints_no_year(self):
        shows, _ = self.rows(TWO)
        self.assertEqual([s["start"] for s in shows],
                         ["2026-09-20T15:00:00+03:00", "2026-09-20T17:00:00+03:00"])

    def test_a_block_without_a_screening_publishes_nothing(self):
        shows, _ = self.rows(TWO)
        self.assertEqual([s["title"] for s in shows],
                         ["Hetki ennen valoa", "Presidentin kyyditys"])

    def test_a_screening_without_a_block_publishes_anyway(self):
        shows, report = self.rows(page(
            listed=[screening("Hetki ennen valoa", "su 20.9 klo 15:00"),
                    screening("Tuntematon elokuva", "su 20.9 klo 19:00")],
            shelf=[block("Hetki ennen valoa")]))
        self.assertEqual([s["title"] for s in shows],
                         ["Hetki ennen valoa", "Tuntematon elokuva"])
        self.assertEqual([(s["rating"], s["len"], s["price"], s["img"]) for s in shows][1],
                         ("", "", "", ""))
        self.assertEqual(report["no_facts"], {"Tuntematon elokuva"})

    def test_the_title_is_the_whole_paragraph_not_the_bold_run(self):
        """The live page closes one `<strong>` before the title's last letter."""
        shows, _ = self.rows(TWO)
        s = next(x for x in shows if x["title"] == "Presidentin kyyditys")
        self.assertEqual((s["rating"], s["len"]), ("K-12", "87"))

    def test_one_paragraph_can_carry_several_screenings(self):
        shows, _ = self.rows(page(
            listed=[screening("Hetki ennen valoa", "la 19.9 klo 15:00", "su 20.9 klo 17:00")],
            shelf=[block("Hetki ennen valoa")]))
        self.assertEqual([s["start"][:16] for s in shows],
                         ["2026-09-19T15:00", "2026-09-20T17:00"])

    OCT = datetime.date(2026, 10, 9)
    SHELF_OCT = [block("Pirjo i Sverige", syn="", meta="S, 88 min, liput 10 €"),
                 block("Hetki ennen valoa"), block("Presidentin kyyditys")]

    def oct_page(self, *listed):
        """The shape read on 2026-10-10: the first screening shares the heading's paragraph
        and no blank paragraph comes before the film blocks."""
        head = p("<strong>Tulevan viikonlopun näytökset</strong><br>Hetki ennen valoa"
                 "<br>la 10.10 klo 16:00")
        return page(listed=[head, *listed], shelf=self.SHELF_OCT, heading=False, blank=False)

    def test_the_list_ends_at_the_first_film_block_and_starts_in_the_headings_paragraph(self):
        shows, _ = self.rows(self.oct_page(
            screening("Pirjo i Sverige", "la 10.10 klo 18:00", "su 11.10 klo 17:00")),
            today=self.OCT)
        self.assertEqual([(s["title"], s["start"][:16]) for s in shows], [
            ("Hetki ennen valoa", "2026-10-10T16:00"),
            ("Pirjo i Sverige", "2026-10-10T18:00"),
            ("Pirjo i Sverige", "2026-10-11T17:00")])
        self.assertEqual((shows[1]["rating"], shows[1]["len"], shows[1]["price"]),
                         ("S", "88", "10€"))

    def test_an_unreadable_line_still_fails_when_a_film_block_ends_the_list(self):
        with self.assertRaises(N.ListingError):
            self.rows(self.oct_page(screening("Pirjo i Sverige", "lauantaina illalla")),
                      today=self.OCT)

    def test_the_metadata_line_is_read_by_pattern(self):
        for meta, want in (("K7, 87 min, liput 10 €", ("K-7", "87", "10€")),
                           ("Kesto 1 h 29 min, K12, liput 10 €", ("K-12", "89", "10€")),
                           ("Kesto 95 min, S, liput 8 €", ("S", "95", "8€")),
                           ("liput 10 €", ("", "", "10€"))):
            with self.subTest(meta=meta):
                shows, _ = self.rows(page(
                    listed=[screening("A", "su 20.9 klo 15:00")],
                    shelf=[block("A", meta=meta)]))
                s = shows[0]
                self.assertEqual((s["rating"], s["len"], s["price"]), want)

    def test_a_ticket_figure_that_is_not_one_amount_settles_nothing(self):
        shows, report = self.rows(page(
            listed=[screening("A", "su 20.9 klo 15:00"),
                    screening("B", "su 20.9 klo 17:00")],
            shelf=[block("A", meta="K7, 87 min, liput 10/8 €"),
                   block("B", meta="K7, 87 min, liput alk. 8 €")]))
        self.assertEqual([s["price"] for s in shows], ["", ""])
        self.assertEqual(report["no_price"], {"A", "B"})

    def test_the_portrait_poster_publishes_and_a_landscape_image_does_not(self):
        shows, _ = self.rows(page(
            listed=[screening("A", "su 20.9 klo 15:00"), screening("B", "su 20.9 klo 17:00")],
            shelf=[block("A"), block("B", img=LANDSCAPE)]))
        self.assertTrue(shows[0]["img"].endswith("juliste-719x1024.jpg"))
        self.assertEqual(shows[1]["img"], "")

    def test_the_synopsis_is_the_blocks_prose_and_never_its_metadata_line(self):
        shows, _ = self.rows(TWO)
        self.assertEqual(shows[0]["_syn"], "Klaus Härön uutuuselokuva kertoo.")
        self.assertNotIn("liput", shows[0]["_syn"])

    def test_a_line_that_is_no_date_fails_the_site(self):
        with self.assertRaises(N.ListingError):
            self.rows(page(listed=[screening("A", "su 20.9 klo 15:00"),
                                   screening("B", "sunnuntaina iltapäivällä")],
                           shelf=[block("A"), block("B")]))

    def test_a_paragraph_with_no_date_line_fails_the_site(self):
        with self.assertRaises(N.ListingError):
            self.rows(page(listed=[screening("A", "su 20.9 klo 15:00"), p("Hetki ennen valoa")],
                           shelf=[block("A")]))

    def test_a_weekday_no_candidate_year_carries_fails_the_site(self):
        with self.assertRaises(N.ListingError):
            self.rows(page(listed=[screening("A", "ma 20.9 klo 15:00")], shelf=[block("A")]))

    def test_an_impossible_date_fails_the_site(self):
        with self.assertRaises(N.ListingError):
            self.rows(page(listed=[screening("A", "su 20.9 klo 15:00"),
                                   screening("B", "la 31.2 klo 17:00")],
                           shelf=[block("A"), block("B")]))

    def test_a_page_with_no_heading_fails_the_site(self):
        with self.assertRaises(N.ListingError):
            self.rows(page(listed=[], shelf=[block("A")], heading=False))

    def test_an_empty_weekend_parses_to_nothing_without_raising(self):
        shows, _ = self.rows(page(listed=[], shelf=[block("A")]))
        self.assertEqual(shows, [])

    def test_the_show_shape(self):
        shows, _ = self.rows(TWO)
        s = shows[0]
        self.assertEqual((s["provider"], s["venue"], s["theatre"], s["aud"]),
                         ("navettakino", "navettakino-konnevesi", "Navettakino", ""))
        self.assertEqual((s["original"], s["method"], s["genres"], s["lang"], s["soldOut"]),
                         ("", "", "", "", False))
        self.assertEqual(s["url"], PAGE_URL)
        self.assertEqual(s["eventId"], "hetki ennen valoa")
        self.assertEqual(registry.by_id("navettakino")["book"], "door")


class RunnerTest(unittest.TestCase):
    PREV = {"generated": "2026-09-01T00:00:00+00:00", "dates": ["2026-09-01"],
            "horizon": "2026-09-01",
            "shows": [{"title": "Old", "start": "2026-09-01T12:00:00+03:00"}]}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._fetch = N.fetch
        self.addCleanup(lambda: setattr(N, "fetch", self._fetch))

    def serve(self, body):
        def fetch(url, **kw):
            if isinstance(body, Exception):
                raise body
            return body.encode("utf-8")
        N.fetch = fetch

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["navetta"])
        return code, out.getvalue() + err.getvalue()

    def soon(self, days):
        return datetime.datetime.now(N.FI).date() + datetime.timedelta(days=days)

    def live_page(self):
        def row(d, clock):
            wd = ("ma", "ti", "ke", "to", "pe", "la", "su")[d.weekday()]
            return f"{wd} {d.day}.{d.month} klo {clock}"
        return page(listed=[screening("A", row(self.soon(1), "15:00")),
                            screening("B", row(self.soon(2), "17:00"))],
                    shelf=[block("A"), block("B", meta="Kesto 1 h 29 min, K12, liput 8 €")])

    def test_the_site_publishes(self):
        self.serve(self.live_page())
        code, log = self.main()
        self.assertEqual(code, 0, log)
        shows = json.loads(
            (run.OUT / "area-navettakino-konnevesi.json").read_text())["shows"]
        self.assertEqual(len(shows), 2)
        self.assertEqual([s["price"] for s in shows], ["10€", "8€"])
        self.assertIn("0 failures", log)

    def test_an_empty_weekend_writes_a_fresh_empty_file(self):
        (run.OUT / "area-navettakino-konnevesi.json").write_text(json.dumps(self.PREV))
        self.serve(page(listed=[], shelf=[block("A")]))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertIn("no programme at the moment", log)
        body = json.loads((run.OUT / "area-navettakino-konnevesi.json").read_text())
        self.assertEqual(body["shows"], [])
        self.assertNotEqual(body["generated"], self.PREV["generated"])

    def test_an_empty_weekend_without_the_pages_own_sentence_fails(self):
        (run.OUT / "area-navettakino-konnevesi.json").write_text(json.dumps(self.PREV))
        self.serve(page(listed=[], shelf=[block("A")], intro=False))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("does not carry its own", log)
        self.assertEqual(json.loads(
            (run.OUT / "area-navettakino-konnevesi.json").read_text()), self.PREV)

    def test_times_the_listing_misses_fail_and_keep_the_previous_file(self):
        """The heading, then screenings the listing never reaches: a blank line left under
        the heading, or the weekend typed as a list block. The page prints times, so zero
        rows is the parser missing them, not a quiet weekend. The list blocks print a date
        without a clock and a clock without a short weekday, one each."""
        shelf = [block("Hetki ennen valoa"), block("Presidentin kyyditys")]
        for name, listed in (
                ("blank under the heading",
                 [p("<br>"), screening("Hetki ennen valoa", "su 20.9 klo 15:00"),
                  screening("Presidentin kyyditys", "su 20.9 klo 17:00")]),
                ("a list block, date only",
                 ['<ul class="wp-block-list"><li>Hetki ennen valoa<br>su 20.9 15.00</li>'
                  '<li>Presidentin kyyditys<br>su 20.9 17.00</li></ul>']),
                ("a list block, clock only",
                 ['<ul class="wp-block-list"><li>Hetki ennen valoa<br>sunnuntaina klo 15:00</li>'
                  '<li>Presidentin kyyditys<br>sunnuntaina klo 17:00</li></ul>'])):
            with self.subTest(name):
                html = page(listed=listed, shelf=shelf)
                self.assertEqual(N.rows(SITE, html, TODAY)[0], [])
                (run.OUT / "area-navettakino-konnevesi.json").write_text(json.dumps(self.PREV))
                self.serve(html)
                code, log = self.main()
                self.assertEqual(code, 1, log)
                self.assertIn("prints a date or time elsewhere", log)
                self.assertNotIn("no programme at the moment", log)
                self.assertEqual(json.loads(
                    (run.OUT / "area-navettakino-konnevesi.json").read_text()), self.PREV)

    def test_a_page_with_no_heading_fails_and_keeps_the_previous_file(self):
        (run.OUT / "area-navettakino-konnevesi.json").write_text(json.dumps(self.PREV))
        self.serve(page(listed=[], shelf=[block("A")], heading=False))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertEqual(json.loads(
            (run.OUT / "area-navettakino-konnevesi.json").read_text()), self.PREV)

    def test_a_refused_page_keeps_the_previous_file(self):
        (run.OUT / "area-navettakino-konnevesi.json").write_text(json.dumps(self.PREV))
        self.serve(RuntimeError("HTTP Error 503"))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertEqual(json.loads(
            (run.OUT / "area-navettakino-konnevesi.json").read_text()), self.PREV)


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        prov = registry.by_id("navettakino")
        self.assertEqual((prov["label"], prov["host"], prov["book"], prov["module"],
                          prov["where"]),
                         ("Navettakino", "navettakino.fi", "door", "navetta", "cloud"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"] == prov["accent"]), 1)

    def test_the_site_names_the_host_it_reads(self):
        self.assertEqual([s["base"] for s in N.SITES], ["https://www.navettakino.fi"])
        self.assertEqual(len(run.host_groups(N.SITES)), 1)

    def test_the_label_is_the_venue_name(self):
        self.assertEqual(SITE["venues"][0]["name"], registry.by_id("navettakino")["label"])
        self.assertEqual(SITE["venues"][0]["city"], "Konnevesi")


if __name__ == "__main__":
    unittest.main()
