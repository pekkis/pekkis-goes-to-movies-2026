"""Bio Pallas: a Wix front page whose structure is its document order.

The fixtures are the shape read on 2026-09-19. What they exist to prove:

- **The coming-soon block is not the programme.** It renders the same markup for a title
  and a bare date, so every fixture that matters carries one of each, and what excludes it
  is the date standing alone rather than the block's heading.
- **The script blocks are not read.** Wix inlines its own component definitions and they
  carry both shapes this parser looks for, so the page fixture carries one.
- **Nothing is keyed on a component id.** The `comp-` prefixes change on every page edit
  and the `__item-` ids repeat across days, so the fixtures use ids that do neither.
- **One amount settles a price and two do not.** `12€ med kaffeserv./kahvitarjoilulla` is
  one; `22/25€` is two.
- **A poster is checked for shape per row**, because the dimensions travel with the
  reference here and the page's own hero image is landscape.
- **The year comes from the weekday**, and a row no candidate year carries raises.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import pallas as P
import registry
from build_pages import LANG_RE as LANG_CONTRACT
import run


SITE = P.SITES[0]
PAGE_URL = "https://www.biopallas.com/"
TODAY = datetime.date(2026, 9, 19)          # a Saturday
FI_WD = ("Ma", "Ti", "Ke", "To", "Pe", "La", "Su")
SV_WD = ("Må", "Ti", "Ons", "To", "Fre", "Lö", "Sö")
FI_LONG = ("MAANANTAI", "TIISTAI", "KESKIVIIKKO", "TORSTAI", "PERJANTAI", "LAUANTAI",
           "SUNNUNTAI")
SV_LONG = ("MÅNDAG", "TISDAG", "ONSDAG", "TORSDAG", "FREDAG", "LÖRDAG", "SÖNDAG")
POSTER = "61d9eb_ae4470273afe4faabe66039678f65a5c~mv2.jpg"
HERO = "61d9eb_095ddbc9d6eb4fc886d8a0e83d3b5880~mv2.jpeg"


def rich(*paragraphs, item="mtioxnm3"):
    body = "".join(f"<p class=\"font_8\">{p}</p>" for p in paragraphs)
    return (f'<div id="comp-mu29rvaz__item-{item}" class="wixui-rich-text" '
            f'data-testid="richTextElement">{body}</div>')


def image(uri=POSTER, w=1080, h=1920, item="mtioxnm3"):
    info = ('{&quot;containerId&quot;:&quot;comp-mu29rvaj__item-' + item + '&quot;,'
            '&quot;targetWidth&quot;:471,&quot;imageData&quot;:{&quot;width&quot;:'
            + str(w) + ',&quot;height&quot;:' + str(h) + ',&quot;uri&quot;:&quot;'
            + uri + '&quot;}}')
    return (f'<wow-image class="bgImage" data-image-info="{info}" data-has-ssr-src="">'
            f'<img alt="{uri}" width="{w}" height="{h}"></wow-image>')


def trailer(label="TRAILER"):
    return (f'<a data-testid="linkElement" href="https://www.youtube.com/watch?v=x" '
            f'aria-label="{label}">{label}</a>')


def heading(d):
    return rich(f"{SV_LONG[d.weekday()]}/{FI_LONG[d.weekday()]} {d.day}.{d.month}")


def row(d, clock, title, meta="1h 40min -K12-", price="13€", poster=image(),
        marker=None, link="TRAILER"):
    paras = [title] + ([marker] if marker else []) + ([meta] if meta else [])
    prices = price if isinstance(price, (list, tuple)) else [price]
    return (poster + trailer(link) + rich(*paras)
            + rich(f"{FI_WD[d.weekday()]}/{SV_WD[d.weekday()]} {d.day}.{d.month}",
                   f"Klo {clock}")
            + (rich(*prices) if prices and prices[0] else ""))


def coming(title, date="2.10"):
    """The trailing block: a title and a bare date, with no `Klo` line."""
    return image() + trailer() + rich(title) + rich(date)


def page(*blocks, tail=("Varietyn varjo", "Digger")):
    # Wix inlines its own component definitions, and the script carries both shapes this
    # parser looks for as string literals. Reading them would invent a row.
    script = ('<script>window.viewerModel={tpl:'
              + repr(rich("Kummitusjuna") + rich("Ke/Ons 19.9", "Klo 23.00"))
              + ",img:" + repr(image("fake~mv2.jpg", 900, 1600)) + "}</script>")
    return ("<html><head><title>Ohjelmisto/Program | Mysite</title>"
            + script + "</head><body>"
            + image(HERO, 3704, 2248, item="hero")
            + "".join(blocks)
            + rich("Seuraavana ohjelmistossa\nNästa i program")
            + "".join(coming(t) for t in tail)
            + "</body></html>")


SAT, SUN = datetime.date(2026, 9, 19), datetime.date(2026, 9, 20)
TWO = page(heading(SAT),
           row(SAT, "18.00", "Myrskyn ikkuna"),
           row(SAT, "20.00", "Resident Evil", meta="1h 34min -K16-"),
           heading(SUN),
           row(SUN, "15.00", "Presidentin kyyditys", meta="1h 27min -K12-",
               poster=image("61d9eb_4921e460be1345e88c1b6e537a0b7d55~mv2.jpg", 700, 1000)))


class RowsTest(unittest.TestCase):
    def rows(self, html, today=None):
        return P.rows(SITE, html, today or TODAY)

    def test_the_weekday_places_a_row_that_prints_no_year(self):
        shows, _ = self.rows(TWO)
        self.assertEqual([s["start"] for s in shows],
                         ["2026-09-19T18:00:00+03:00", "2026-09-19T20:00:00+03:00",
                          "2026-09-20T15:00:00+03:00"])

    def test_a_row_no_candidate_year_carries_raises(self):
        """The weekday and the date have to agree, or the screening cannot be placed."""
        bad = page(heading(SAT), rich("Kummitusjuna") + rich("Ke/Ons 19.9", "Klo 18.00")
                   + rich("13€"))
        with self.assertRaises(P.ShowRowError) as e:
            self.rows(bad)
        self.assertIn("no candidate year", str(e.exception))

    def test_the_coming_soon_block_is_not_the_programme(self):
        """Its entries carry a title and a bare date and no time, which is what excludes
        them. Naming the block's heading instead would break when the cinema renames it."""
        shows, _ = self.rows(TWO)
        self.assertEqual({s["title"] for s in shows},
                         {"Myrskyn ikkuna", "Resident Evil", "Presidentin kyyditys"})
        self.assertNotIn("Varietyn varjo", {s["title"] for s in shows})

    def test_the_runtime_and_the_rating_come_off_one_line(self):
        shows, _ = self.rows(TWO)
        self.assertEqual([(s["len"], s["rating"]) for s in shows],
                         [("100", "K-12"), ("94", "K-16"), ("87", "K-12")])

    def test_a_row_with_no_meta_line_publishes_neither(self):
        """The concert on 23.9 has no `1h 40min -K12-` line. Dropping a row on a missing
        optional field would lose a film the day the cinema forgets one."""
        shows, _ = self.rows(page(heading(SAT),
                                  row(SAT, "19.00", "Orchestra Nazionale della Luna",
                                      meta=None, price="22/25€", link="LIPUT/ BILJETTER"),
                                  row(SAT, "20.00", "Resident Evil")))
        self.assertEqual(shows[0]["title"], "Orchestra Nazionale della Luna")
        self.assertEqual((shows[0]["len"], shows[0]["rating"]), ("", ""))

    def test_one_amount_settles_the_price_and_two_do_not(self):
        shows, report = self.rows(page(
            heading(SAT),
            row(SAT, "14.00", "Presidentin kyyditys",
                price=["12€ med kaffeserv./", "kahvitarjoilulla"]),
            row(SAT, "19.00", "Orchestra Nazionale della Luna", meta=None, price="22/25€"),
            row(SAT, "20.00", "Resident Evil")))
        self.assertEqual([s["price"] for s in shows], ["12€", "", "13€"])
        self.assertEqual(report["no_price"], ["Orchestra Nazionale della Luna"])

    def test_a_members_amount_leaves_the_public_one(self):
        """Blade Runner at the film club, 30.9.2026: `10€` then `7€ F-Keks jäsenille`."""
        shows, report = self.rows(page(
            heading(SAT),
            row(SAT, "17.00", "Blade Runner", price=["10€", "7€ F-Keks jäsenille"]),
            row(SAT, "19.00", "Kerho", price=["7€ F-Keks jäsenille"]),
            row(SAT, "21.00", "Kaksi", price=["10€", "8€"])))
        self.assertEqual([s["price"] for s in shows], ["10€", "", ""])
        self.assertEqual(report["no_price"], ["Kerho", "Kaksi"])

    def test_only_a_portrait_image_inside_a_row_becomes_a_poster(self):
        """The dimensions travel with the reference here, so the shape is checked per run
        rather than trusted: the page's own hero image is landscape."""
        shows, report = self.rows(page(
            heading(SAT),
            row(SAT, "18.00", "Myrskyn ikkuna"),
            row(SAT, "20.00", "Resident Evil", poster=image(HERO, 3704, 2248)),
            row(SAT, "22.00", "Deep Water", poster=image("x~mv2.jpg", 120, 180))))
        self.assertEqual([s["img"] for s in shows],
                         [P.MEDIA + POSTER, "", ""])
        self.assertEqual(sorted(report["no_poster"]), ["Deep Water", "Resident Evil"])

    def test_a_row_with_no_image_of_its_own_does_not_inherit_the_previous_one(self):
        """The 2026-04-17 capture has a row carrying a trailer link and three text blocks
        and no image at all. The poster is the last image before the row's title, so
        without a reset that row would take the poster of the row above it, which is a
        wrong poster rather than a missing one."""
        shows, report = self.rows(page(
            heading(SAT),
            row(SAT, "18.00", "Myrskyn ikkuna"),
            row(SAT, "20.00", "Regnmannen", poster="")))
        self.assertEqual([s["img"] for s in shows], [P.MEDIA + POSTER, ""])
        self.assertEqual(report["no_poster"], ["Regnmannen"])

    def test_a_day_heading_clears_a_poster_that_belongs_to_no_row(self):
        """The row reset alone is not enough. Today the only image outside a row is the
        page's landscape hero, which the shape filter rejects anyway, so this is a
        portrait one: a closure day illustrated, or the coming-soon block moved above a
        heading, and the first row after it carrying no image of its own. Without the
        heading reset that row takes a poster that was never its own."""
        shows, report = self.rows(page(
            image("61d9eb_stray~mv2.jpg", 700, 1000),
            heading(SAT),
            row(SAT, "18.00", "Regnmannen", poster=""),
            row(SAT, "20.00", "Resident Evil")))
        self.assertEqual(shows[0]["img"], "")
        self.assertEqual(report["no_poster"], ["Regnmannen"])

    def test_only_a_marker_naming_an_audio_language_publishes_one(self):
        """The captures carry a subtitle statement and an `original ... FI/SV` line in the
        same position, and neither names what the audience will hear."""
        shows, _ = self.rows(page(
            heading(SAT),
            row(SAT, "14.00", "Toy Story 5", marker="SUOMEKSI"),
            row(SAT, "16.00", "Toy Story 5", marker="PÅ SVENSKA"),
            row(SAT, "18.00", "Toy Story 5", marker="ORIGINAL version with subtitles FI/SV"),
            row(SAT, "20.00", "Toy Story 5",
                marker="Huom! Ilman suomenkielistä tekstitystä")))
        self.assertEqual([s["lang"] for s in shows], ["FI-A", "SV-A", "", ""])
        for code in ("FI-A", "SV-A"):
            self.assertRegex(code, LANG_CONTRACT, "the form the client and the pages read")

    def test_a_zero_width_space_never_reaches_the_title(self):
        """The site's editor leaves one on many titles. No reader sees it and it would key
        those rows apart from the same film at every other chain."""
        shows, _ = self.rows(page(heading(SAT),
                                  row(SAT, "18.00", "Deep Water​"),
                                  row(SAT, "20.00", "Resident Evil")))
        self.assertEqual(shows[0]["title"], "Deep Water")
        self.assertEqual(shows[0]["eventId"], "deep water")

    def test_a_day_the_page_heads_but_does_not_fill_is_reported_as_closed(self):
        """The cinema writes `STÄNGT/KIINNI` in place of a day's rows, in four spellings
        across the captures, so the closure is read from the day having no row rather than
        from any wording."""
        closed = datetime.date(2026, 9, 22)
        shows, report = self.rows(page(heading(SAT),
                                       row(SAT, "18.00", "Myrskyn ikkuna"),
                                       row(SAT, "20.00", "Resident Evil"),
                                       heading(closed), rich("STÄNGT/KIINNI")))
        self.assertEqual(len(shows), 2)
        self.assertEqual(len(report["closed"]), 1)
        self.assertIn("22.9", report["closed"][0])

    def test_nothing_is_keyed_on_a_component_id(self):
        """They change on every page edit and repeat across days."""
        shifted = TWO.replace("comp-mu29rvaz", "comp-mdyjq4k4").replace(
            "comp-mu29rvaj", "comp-mdyjq4k5")
        self.assertEqual([s["start"] for s in P.rows(SITE, shifted, TODAY)[0]],
                         [s["start"] for s in P.rows(SITE, TWO, TODAY)[0]])

    def test_the_script_blocks_are_not_read(self):
        """Wix inlines its own component definitions, and the fixture's carries both
        shapes this parser looks for. Reading them would invent a row."""
        shows, _ = P.rows(SITE, TWO, TODAY)
        self.assertEqual(len(shows), 3)
        self.assertNotIn("Kummitusjuna", {s["title"] for s in shows})

    def test_a_date_block_with_no_readable_time_is_not_a_row(self):
        """Both halves are required. A date whose second paragraph stops being a time is
        dropped rather than published at midnight, and it is the same requirement that
        keeps the coming-soon entries out."""
        for second in ("Klo?", "Klo 1900", "Loppuunmyyty", ""):
            with self.subTest(second=second):
                shows, _ = self.rows(page(
                    heading(SAT),
                    rich("Kummitusjuna") + rich("La/Lö 19.9", second) + rich("13€"),
                    row(SAT, "20.00", "Resident Evil")))
                self.assertEqual([s["title"] for s in shows], ["Resident Evil"])

    def test_every_screening_links_to_the_page_because_there_is_no_ticket_url(self):
        shows, _ = self.rows(TWO)
        self.assertEqual({s["url"] for s in shows}, {PAGE_URL})
        self.assertEqual(registry.by_id("biopallas")["book"], "door")

    def test_the_show_shape(self):
        shows, _ = self.rows(TWO)
        s = shows[0]
        self.assertEqual((s["provider"], s["venue"], s["theatre"], s["aud"]),
                         ("biopallas", "pallas-karjaa", "Bio Pallas", ""))
        self.assertEqual((s["original"], s["method"], s["genres"], s["soldOut"]),
                         ("", "", "", False))
        self.assertEqual(s["title"], "Myrskyn ikkuna")
        self.assertEqual(s["eventId"], "myrskyn ikkuna")
        self.assertNotIn("_syn", s)


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
        self._fetch = P.fetch
        self.addCleanup(lambda: setattr(P, "fetch", self._fetch))

    def serve(self, body):
        def fetch(url, **kw):
            if isinstance(body, Exception):
                raise body
            return body.encode("utf-8")
        P.fetch = fetch

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            # --half all, the line test_regina.py carries: on Actions run.py derives
            # "cloud" from GITHUB_ACTIONS. This module is cloud today, so it would
            # pass either way, but its routing is explicitly unsettled until the
            # first runner log and a flip to local must not turn these red.
            code = run.main(["pallas", "--half", "all"])
        return code, out.getvalue() + err.getvalue()

    def soon(self, days):
        return datetime.datetime.now(P.FI).date() + datetime.timedelta(days=days)

    def live_page(self):
        a, b = self.soon(1), self.soon(2)
        return page(heading(a), row(a, "18.00", "A"), row(a, "20.00", "B"),
                    heading(b), row(b, "15.00", "C", price="12€"))

    def test_the_site_publishes(self):
        self.serve(self.live_page())
        code, log = self.main()
        self.assertEqual(code, 0, log)
        shows = json.loads((run.OUT / "area-pallas-karjaa.json").read_text())["shows"]
        self.assertEqual(len(shows), 3)
        self.assertEqual({s["price"] for s in shows}, {"12€", "13€"})
        self.assertIn("0 failures", log)

    def test_a_programme_with_no_screening_fails_and_keeps_the_previous_file(self):
        """Six readings over fourteen months every one carried rows, and the site's own
        closure wording is per day and not standardised, so zero rows may not read as a
        confirmed empty programme."""
        (run.OUT / "area-pallas-karjaa.json").write_text(json.dumps(self.PREV))
        self.serve(page(rich("STÄNGT/KIINNI"), tail=()))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("no evidence", log)
        self.assertNotIn("no programme at the moment", log)
        self.assertEqual(json.loads(
            (run.OUT / "area-pallas-karjaa.json").read_text()), self.PREV)

    def test_a_refused_page_keeps_the_previous_file(self):
        (run.OUT / "area-pallas-karjaa.json").write_text(json.dumps(self.PREV))
        self.serve(RuntimeError("HTTP Error 503"))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertEqual(json.loads(
            (run.OUT / "area-pallas-karjaa.json").read_text()), self.PREV)


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("biopallas")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Bio Pallas", "biopallas.com", "door", "pallas", "cloud"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"] == p["accent"]), 1)

    def test_the_site_names_the_host_it_reads(self):
        self.assertEqual([s["base"] for s in P.SITES], ["https://www.biopallas.com"])
        self.assertEqual(len(run.host_groups(P.SITES)), 1)

    def test_the_label_is_the_venue_name(self):
        self.assertEqual(SITE["venues"][0]["name"], registry.by_id("biopallas")["label"])
        self.assertEqual(SITE["venues"][0]["city"], "Karjaa")


if __name__ == "__main__":
    unittest.main()
