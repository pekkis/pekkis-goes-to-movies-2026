"""Bio Savoy, Mariehamn: two halls, ISO instants, and an http-only host.

The fixtures follow `biosavoy.ax` as read on 2026-09-15: one
`block-filmer-schema-block` per hall, each headed `Filmvisningar - Sal N`, holding rows
whose `<span class="date-display-single">` carries the full instant in its `content`
attribute.

Both halls are in the fixture because the hall comes from the block title and nothing on
the row, so a single-block fixture would never show it being lost. The `content` attribute
and the visible clock deliberately disagree in one row: the attribute is the one to read.
"""
import contextlib
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import biosavoy
import common
import enrich_tmdb
import synmerge

BASE = "http://www.biosavoy.ax"


def row(slug, title, content, shown=None):
    shown = shown if shown is not None else content[11:16]
    return ('<div class="views-row"><div class="views-field views-field-title">'
            f'<span class="field-content"><a href="/film/{slug}">'
            f'<span class="date-display-single" property="dc:date" '
            f'datatype="xsd:dateTime" content="{content}">{shown}</span>'
            f' - {title}</a></span></div></div>')


def block(hall, *rows, day="tis 15/09"):
    return (f'<section class="block block-views block-filmer-schema-block">'
            f'<div class="block-inner clearfix">'
            f'<h2 class="block-title">Filmvisningar - {hall}</h2>'
            f'<div class="block-content content"><div class="view view-filmer-schema">'
            f'<div class="view-content"><h3>{day}</h3>' + "".join(rows) +
            '</div></div></div></div></section>')


def page(*blocks, share_row=False):
    """The real page carries a "Dela" block with the same class as the two schedules. It
    holds no screening, so `share_row` puts one in it: only a block whose title actually
    reads "Filmvisningar - ..." may contribute screenings, and that has to be provable."""
    extra = row("shared", "SHARE WIDGET", "2026-09-15T12:00:00+03:00") if share_row else ""
    return ('<html><body><section class="block block-views block-filmer-schema-block">'
            f'<h2 class="block-title">Dela </h2><div>share buttons{extra}</div></section>'
            + "".join(blocks) + "</body></html>")


LISTING = page(
    block("Sal 1",
          row("dog-stars", "THE DOG STARS", "2026-09-15T18:00:00+03:00"),
          row("uprising", "THE UPRISING", "2026-09-15T20:15:00+03:00")),
    block("Sal 2",
          # The visible clock says something else; the attribute is authoritative.
          row("marsupilami", "MARSUPILAMI", "2026-09-15T18:15:00+03:00", shown="18.15"),
          row("spa-weekend", "SPA WEEKEND", "2026-09-16T20:20:00+03:00")),
)


def film_page(price="15 \u20ac", extra=None, field=True, length="2h 7min",
              age="Till\u00e5ten fr\u00e5n 12 \u00e5r", body="Andrew Garfield spelar den "
              "mytomspunne ledaren f\u00f6r det stora upproret."):
    """A `/film/{slug}` page. The price is a labelled Drupal field; `extra` adds a second
    `field-item` under it, which is what makes the page stop saying one thing."""
    items = "".join(f'<li class="field-item even">{v}</li>'
                    for v in ([price] if price is not None else [])
                    + ([extra] if extra is not None else []))
    block = ('<section class="field field-name-field-price field-type-taxonomy-term-reference '
             'field-label-inline clearfix view-mode-full"><h2 class="field-label">Pris:&nbsp;'
             f'</h2><ul class="field-items">{items}</ul></section>') if field else ""
    def sect(name, value, tag="li"):
        if value is None:
            return ""
        return (f'<section class="field field-name-{name} field-label-inline clearfix '
                f'view-mode-full"><ul class="field-items">'
                f'<{tag} class="field-item even">{value}</{tag}></ul></section>')

    return ('<html><body>'
            # A decoy: the genre field wraps its value in `field-item` like every other,
            # so a page-wide read picks it up instead of the field it wants.
            + sect("field-genre", "Drama") + block
            + sect("field-movie-length", length)
            + sect("field-movie-age", age)
            + sect("body", f"<p>{body}</p>" if body else None, tag="div")
            + "</body></html>")


class ScheduleTest(unittest.TestCase):
    def setUp(self):
        self.shows = biosavoy.parse(LISTING)

    def test_every_row_in_both_blocks_is_read(self):
        self.assertEqual(len(self.shows), 4)
        self.assertEqual(sorted({s["eventId"] for s in self.shows}),
                         ["dog-stars", "marsupilami", "spa-weekend", "uprising"])

    def test_the_hall_comes_from_the_block_title(self):
        by = {s["eventId"]: s["aud"] for s in self.shows}
        self.assertEqual(by["dog-stars"], "Sal 1")
        self.assertEqual(by["marsupilami"], "Sal 2")
        self.assertEqual(sorted({s["aud"] for s in self.shows}), ["Sal 1", "Sal 2"])

    def test_the_share_block_is_not_a_hall_even_when_it_holds_a_row(self):
        """It carries the same block class as the two schedules and only its title tells
        them apart, so a row inside it must not become a screening."""
        self.assertNotIn("Dela", {s["aud"] for s in self.shows})
        out = biosavoy.parse(page(block("Sal 1",
                                        row("a", "A", "2026-09-15T18:00:00+03:00")),
                                  share_row=True))
        self.assertEqual([s["eventId"] for s in out], ["a"])
        self.assertNotIn("SHARE WIDGET", {s["title"] for s in out})

    def test_the_hall_is_the_name_after_the_label_not_the_whole_title(self):
        self.assertEqual(sorted({s["aud"] for s in self.shows}), ["Sal 1", "Sal 2"])
        for s in self.shows:
            self.assertNotIn("Filmvisningar", s["aud"])

    def test_the_instant_comes_from_the_attribute_not_the_visible_clock(self):
        """The attribute carries the date, the clock and the offset. Nothing is inferred
        here: no year to resolve and no timezone to assume."""
        by = {s["eventId"]: s["start"] for s in self.shows}
        self.assertEqual(by["dog-stars"], "2026-09-15T18:00:00+03:00")
        self.assertEqual(by["marsupilami"], "2026-09-15T18:15:00+03:00")
        self.assertEqual(by["spa-weekend"], "2026-09-16T20:20:00+03:00")

    def test_a_row_without_an_offset_is_skipped(self):
        """The offset is what makes the instant unambiguous. A naive datetime would have
        to assume a zone, and this parser assumes none."""
        out = biosavoy.parse(page(block("Sal 1",
                                        row("a", "A", "2026-09-15T18:00:00"),
                                        row("b", "B", "2026-09-15T19:00:00+03:00"))))
        self.assertEqual([s["eventId"] for s in out], ["b"])

    def test_an_unparseable_instant_does_not_abort_the_page(self):
        out = biosavoy.parse(page(block("Sal 1",
                                        row("a", "A", "not-a-date"),
                                        row("b", "B", "2026-09-15T19:00:00+03:00"))))
        self.assertEqual([s["eventId"] for s in out], ["b"])

    def test_the_destination_is_http_because_the_host_has_no_https(self):
        """Port 443 is refused on both biosavoy.ax and www.biosavoy.ax. The verified
        destination is published rather than an https one the host cannot serve."""
        for s in self.shows:
            self.assertTrue(s["url"].startswith("http://www.biosavoy.ax/film/"), s["url"])
            self.assertNotIn("https://", s["url"])

    def test_the_title_is_the_text_after_the_dash(self):
        self.assertIn("THE DOG STARS", {s["title"] for s in self.shows})
        for s in self.shows:
            self.assertNotIn(" - ", s["title"])
            self.assertNotIn(":0", s["title"])

    def test_a_repeated_row_is_published_once(self):
        r = row("a", "A", "2026-09-15T18:00:00+03:00")
        self.assertEqual(len(biosavoy.parse(page(block("Sal 1", r, r)))), 1)

    def test_the_same_minute_in_two_halls_is_two_screenings(self):
        out = biosavoy.parse(page(
            block("Sal 1", row("a", "A", "2026-09-15T18:00:00+03:00")),
            block("Sal 2", row("a", "A", "2026-09-15T18:00:00+03:00"))))
        self.assertEqual(len(out), 2)
        self.assertEqual(sorted(s["aud"] for s in out), ["Sal 1", "Sal 2"])

    def test_every_show_meets_the_contract(self):
        common.check_shows({biosavoy.VENUE["id"]: self.shows}, "biosavoy",
                           {biosavoy.VENUE["id"]})


class EmptyAndBrokenTest(unittest.TestCase):
    def test_blocks_with_no_row_fail_rather_than_empty_the_venue(self):
        """No empty state is recorded for this site. Empty hall blocks are what a changed
        row markup would also produce, so zero rows fails."""
        with self.assertRaises(RuntimeError) as cm:
            biosavoy.parse(page(block("Sal 1"), block("Sal 2")))
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_film_rows_the_parser_cannot_read_fail_the_site(self):
        """Both halls list films, every instant unreadable or its attribute renamed: a
        template change, not a cinema with nothing on."""
        renamed = row("marsupilami", "MARSUPILAMI", "2026-09-15T18:15:00+03:00").replace(
            " content=", " datetime=")
        with self.assertRaises(RuntimeError) as cm:
            biosavoy.parse(page(
                block("Sal 1", row("dog-stars", "THE DOG STARS", "2026-09-15 18:00"),
                      row("uprising", "THE UPRISING", "tis 15/09 20:15")),
                block("Sal 2", renamed)))
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)
        self.assertIn("3 film link", str(cm.exception))

    def test_a_page_without_a_schedule_block_is_a_failure(self):
        with self.assertRaises(RuntimeError) as cm:
            biosavoy.parse("<html><body><p>Välkommen</p></body></html>")
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)


class SiteTest(unittest.TestCase):
    def test_one_venue_on_aland_keyed_under_its_official_name(self):
        """Åland's only official language is Swedish, and `CITY_SV` in index.html cannot
        gain an entry without editing a file this project keeps frozen. Keying the Finnish
        exonym would show it untranslated in the Swedish interface."""
        self.assertEqual([v["city"] for v in biosavoy.SITES[0]["venues"]], ["Mariehamn"])

    def test_the_base_is_http(self):
        self.assertTrue(biosavoy.BASE.startswith("http://"))


class PriceTest(unittest.TestCase):
    """Each film states its own price in a labelled field, so there is nothing to derive.

    Surveyed across all thirteen films on 2026-09-16, not sampled: every one carried the
    field with a single amount, 15 € but 13 € for the two children's films. That says the
    field exists and is single-valued today, not that it always will be, so anything short
    of one readable amount publishes nothing.
    """

    def test_the_labelled_field_is_what_is_read(self):
        self.assertEqual(biosavoy.film_price(film_page("15 \u20ac")), "15\u20ac")
        self.assertEqual(biosavoy.film_price(film_page("13 \u20ac")), "13\u20ac")

    def test_a_page_with_no_price_field_publishes_nothing(self):
        self.assertEqual(biosavoy.film_price(film_page(field=False)), "")

    def test_a_field_with_no_readable_amount_publishes_nothing(self):
        self.assertEqual(biosavoy.film_price(film_page("fri entré")), "")

    def test_two_different_amounts_publish_neither(self):
        """The page has stopped saying one thing, and picking either publishes the doubt."""
        self.assertEqual(biosavoy.film_price(film_page("15 \u20ac", extra="13 \u20ac")), "")

    def test_the_same_amount_twice_is_not_two_things(self):
        self.assertEqual(biosavoy.film_price(film_page("15 \u20ac", extra="15 \u20ac")),
                         "15\u20ac")

    def test_another_field_on_the_page_is_not_the_price(self):
        """`field-name-field-genre` and `-speltid` carry `field-item` too, so the block is
        bounded to the price section rather than searched page-wide."""
        page = film_page(field=False).replace("Drama", "12 \u20ac")
        self.assertEqual(biosavoy.film_price(page), "")

    def test_the_cents_are_dropped_only_when_they_are_zero(self):
        self.assertEqual(biosavoy.film_price(film_page("15,00 \u20ac")), "15\u20ac")
        self.assertEqual(biosavoy.film_price(film_page("13,50 \u20ac")), "13.5\u20ac")


class PriceThroughFetchTest(unittest.TestCase):
    """One request per distinct film, paced, and a failure costing that film alone."""

    def serve(self, pages):
        self.calls = []

        def get(url):
            self.calls.append(url)
            body = pages.get(url)
            if isinstance(body, Exception):
                raise body
            if body is None:
                raise RuntimeError(f"unexpected fetch {url}")
            return body
        self.slept = []
        real_get, real_sleep = biosavoy.get, biosavoy.time.sleep
        biosavoy.get = get
        biosavoy.time.sleep = self.slept.append
        self.addCleanup(lambda: setattr(biosavoy, "get", real_get))
        self.addCleanup(lambda: setattr(biosavoy.time, "sleep", real_sleep))

    # One film with two screenings, so "once per distinct film" is not the same number as
    # "once per screening". LISTING has four rows and four films; this has five and four.
    LISTING_REPEAT = page(
        block("Sal 1",
              row("dog-stars", "THE DOG STARS", "2026-09-15T18:00:00+03:00"),
              row("uprising", "THE UPRISING", "2026-09-15T20:15:00+03:00")),
        block("Sal 2",
              row("marsupilami", "MARSUPILAMI", "2026-09-15T18:15:00+03:00"),
              row("spa-weekend", "SPA WEEKEND", "2026-09-16T20:20:00+03:00"),
              row("marsupilami", "MARSUPILAMI", "2026-09-17T16:00:00+03:00")),
    )

    def run_site(self, **over):
        pages = {f"{BASE}/": self.LISTING_REPEAT,
                 f"{BASE}/film/dog-stars": film_page("15 \u20ac"),
                 f"{BASE}/film/uprising": film_page("15 \u20ac"),
                 f"{BASE}/film/marsupilami": film_page("13 \u20ac"),
                 f"{BASE}/film/spa-weekend": film_page("15 \u20ac")}
        pages.update(over)
        self.serve(pages)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            data = biosavoy.fetch_site()
        return data["savoy-mariehamn"], out.getvalue() + err.getvalue()

    def test_one_request_per_distinct_film_and_none_repeated(self):
        """Five screenings over four films, so reading per screening is one request more
        and asks a cinema twice for a page it already answered."""
        shows, log = self.run_site()
        films = [c for c in self.calls if "/film/" in c]
        self.assertEqual(len(shows), 5)
        self.assertEqual(len({s["eventId"] for s in shows}), 4)
        self.assertEqual(sorted(films), sorted(set(films)), "a film page was read twice")
        self.assertEqual(len(films), 4)
        self.assertEqual(self.calls[0], f"{BASE}/")

    def test_the_film_pages_are_paced_one_sleep_apart(self):
        """What a cinema's server experiences between two of its pages. Four films, so
        three waits: the first page is not made to wait for nothing."""
        self.run_site()
        self.assertEqual(len([c for c in self.calls if "/film/" in c]), 4)
        self.assertEqual(len(self.slept), 3)
        self.assertTrue(all(s > 0 for s in self.slept), self.slept)

    def test_every_screening_carries_its_own_films_price(self):
        shows, log = self.run_site()
        got = {s["title"]: s["price"] for s in shows}
        self.assertEqual(got["MARSUPILAMI"], "13\u20ac")
        self.assertEqual(got["THE DOG STARS"], "15\u20ac")
        self.assertIn("5 priced", log)
        common.check_shows({"savoy-mariehamn": shows}, "biosavoy", {"savoy-mariehamn"})

    def test_a_film_page_that_refuses_costs_that_film_and_not_the_schedule(self):
        """The schedule is already parsed by the time the pages are read. A cinema's whole
        programme must not go stale because one film page 500s."""
        shows, log = self.run_site(**{
            f"{BASE}/film/marsupilami": RuntimeError("HTTP Error 500")})
        got = {s["title"]: s["price"] for s in shows}
        self.assertEqual(got["MARSUPILAMI"], "")
        self.assertEqual(got["THE DOG STARS"], "15\u20ac")
        self.assertEqual(len(shows), 5)
        self.assertIn("film page marsupilami", log)

    def test_a_film_whose_page_says_nothing_publishes_nothing(self):
        shows, _ = self.run_site(**{f"{BASE}/film/uprising": film_page(field=False)})
        got = {s["title"]: s["price"] for s in shows}
        self.assertEqual(got["THE UPRISING"], "")
        self.assertEqual(got["THE DOG STARS"], "15\u20ac")

    def test_the_film_pages_are_bounded_by_the_shared_budget(self):
        """`capped`, not `budget_or_raise`: these pages carry no showtime, so a film past
        the cap loses its price and keeps its screenings."""
        saved = common.PAGE_BUDGET
        common.PAGE_BUDGET = 2
        self.addCleanup(lambda: setattr(common, "PAGE_BUDGET", saved))
        shows, log = self.run_site()
        self.assertEqual(len([c for c in self.calls if "/film/" in c]), 2)
        self.assertEqual(len(shows), 5, "the schedule is untouched by the cap")
        self.assertIn("page budget", log)
        # The two films the cap reached, in slug order: dog-stars once and marsupilami
        # twice. The two it did not keep their screenings and lose only the amount.
        self.assertEqual(sum(1 for s in shows if s["price"]), 3)
        self.assertEqual({s["title"] for s in shows if not s["price"]},
                         {"SPA WEEKEND", "THE UPRISING"})


class FilmFactsTest(unittest.TestCase):
    """The runtime, the age limit and the Swedish synopsis, off the page fetched anyway."""

    def facts(self, **kw):
        return biosavoy.film_facts(film_page(**kw))

    def test_the_runtime_becomes_minutes(self):
        self.assertEqual(self.facts(length="2h 7min")["len"], "127")
        self.assertEqual(self.facts(length="01h 58min")["len"], "118")
        self.assertEqual(self.facts(length="1h 30min")["len"], "90")

    def test_a_placeholder_runtime_publishes_nothing(self):
        """`one-night-only` published `XXh 00min` on 2026-09-16: the cinema had not filled
        it in. A card reading 0 min states a fact that is not one."""
        self.assertEqual(self.facts(length="XXh 00min")["len"], "")

    def test_a_missing_runtime_field_publishes_nothing(self):
        self.assertEqual(self.facts(length=None)["len"], "")

    def test_the_age_limit_is_read_from_the_cinemas_own_wording(self):
        for text, want in (("Till\u00e5ten fr\u00e5n 7 \u00e5r", "K-7"),
                           ("Till\u00e5ten fr\u00e5n 12 \u00e5r", "K-12"),
                           ("Till\u00e5ten fr\u00e5n 16 \u00e5r", "K-16")):
            with self.subTest(text=text):
                self.assertEqual(self.facts(age=text)["rating"], want)

    def test_any_other_age_wording_publishes_nothing_rather_than_a_guess(self):
        """The rule tmb.py already follows for its age images: a classification inferred
        from a shape is worse than none, and the shared pass can still fill a blank."""
        for text in ("Barntillåten", "Till\u00e5ten f\u00f6r alla", "", None,
                     # A bare number, and a label without the statement: the wording is
                     # what says this is an age limit, and a digit on its own does not.
                     "12", "\u00c5ldersgr\u00e4ns 12",
                     # Defensive: not a wording this site uses, and the one that would cost
                     # most if `från N` alone were the rule. A recommendation is not a limit.
                     "Rekommenderas fr\u00e5n 7 \u00e5r"):
            with self.subTest(text=text):
                self.assertEqual(self.facts(age=text)["rating"], "")

    def test_the_synopsis_is_the_body_field_and_not_another_one(self):
        f = self.facts(body="En mening p\u00e5 svenska om filmen.")
        self.assertEqual(f["syn"], "En mening p\u00e5 svenska om filmen.")
        self.assertNotIn("Drama", f["syn"])

    def test_a_page_with_no_body_publishes_no_synopsis(self):
        self.assertEqual(self.facts(body=None)["syn"], "")

    def test_svenskt_tal_is_the_spoken_language(self):
        """Marsupilami and Gr\u00e5ben vs ACME, read 2026-10-04: a body paragraph of its
        own. The words inside a sentence state nothing."""
        self.assertEqual(self.facts(body="Om Marsupilami.</p>\n<p>SVENSKT TAL!</p>\n"
                                         "<p>PREMI\u00c4R 21.8 2026")["lang"], "SV-A")
        self.assertEqual(self.facts(body="Filmen visas med svenskt tal och text.")["lang"], "")
        self.assertEqual(self.facts()["lang"], "")

    def test_the_body_ends_where_the_genre_field_begins(self):
        """The page's own order, read on /film/digger 2026-10-04: the body is a `<div>`
        and the genre section follows it. Its items ended 15 Swedish synopses."""
        body = ('<div class="field field-name-body field-type-text-with-summary '
                'field-label-hidden view-mode-full"><div class="field-items">'
                '<div class="field-item even" property="content:encoded">'
                '<p>Digger är en svart katastrofkomedi.</p>\n'
                '<p>PREMIÄR:<br />\n2.10 2026</p>\n</div></div></div>')
        genre = ('<section class="field field-name-field-movie-genre field-label-inline '
                 'clearfix view-mode-full"><h2 class="field-label">Genre:&nbsp;</h2>'
                 '<ul class="field-items"><li class="field-item even">Drama</li>'
                 '<li class="field-item odd">Komedi</li></ul></section>')
        f = biosavoy.film_facts("<html><body>" + body + genre
                                + film_page(body=None)[len("<html><body>"):])
        self.assertEqual(f["syn"], "Digger är en svart katastrofkomedi.")
        self.assertEqual((f["len"], f["rating"], f["price"]), ("127", "K-12", "15€"))

    def test_the_screening_paragraphs_leave_the_synopsis(self):
        """Marsupilami and Digger, read 2026-10-04. Only a whole paragraph goes: the words
        inside a sentence are the film's."""
        f = self.facts(body="Om Marsupilami.</p>\n<p>SVENSKT TAL!</p>\n<p>PREMI\u00c4R 21.8 2026<br />\n ")
        self.assertEqual((f["syn"], f["lang"]), ("Om Marsupilami.", "SV-A"))
        f = self.facts(body="Om Digger.</p>\n<p>PREMI\u00c4R:<br />\n2.10 2026")
        self.assertEqual(f["syn"], "Om Digger.")
        for kept in ("Filmen hade premi\u00e4r 2.10 2026 i Cannes.",
                     "Svenskt tal och finsk text p\u00e5 alla visningar.",
                     "Svenskt tal! Filmen dubbades i Stockholm.",
                     "Premi\u00e4r 2.10 2026 i hela Norden."):
            with self.subTest(kept=kept):
                self.assertEqual(self.facts(body=kept)["syn"], kept)

    def test_each_field_is_read_from_its_own_section(self):
        """Every Drupal field wraps its value in `field-item`, so a page-wide read of any
        one of them finds whichever field happens to come first."""
        f = self.facts(length="2h 7min", age="Till\u00e5ten fr\u00e5n 16 \u00e5r")
        self.assertEqual((f["len"], f["rating"], f["price"]), ("127", "K-16", "15\u20ac"))


class SwedishSynopsisTest(unittest.TestCase):
    """Åland's only official language is Swedish, and the slot is shared across chains."""

    def run_site(self, **over):
        pages = {f"{BASE}/": PriceThroughFetchTest.LISTING_REPEAT,
                 f"{BASE}/film/dog-stars": film_page(body="Om h\u00f6sten och hundarna."),
                 f"{BASE}/film/uprising": film_page(body="Om upproret."),
                 f"{BASE}/film/marsupilami": film_page(body=None),
                 f"{BASE}/film/spa-weekend": film_page(body="Om en spahelg.")}
        pages.update(over)
        calls = []

        def get(url):
            calls.append(url)
            body = pages.get(url)
            if isinstance(body, Exception):
                raise body
            if body is None:
                raise RuntimeError(f"unexpected fetch {url}")
            return body
        real_get, real_sleep = biosavoy.get, biosavoy.time.sleep
        biosavoy.get, biosavoy.time.sleep = get, lambda s: None
        self.addCleanup(lambda: setattr(biosavoy, "get", real_get))
        self.addCleanup(lambda: setattr(biosavoy.time, "sleep", real_sleep))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            data = biosavoy.fetch_site()
        return data["savoy-mariehamn"], out.getvalue() + err.getvalue()

    def test_the_synopsis_is_published_declared_as_swedish(self):
        """A bare string would be filed as Finnish by synmerge and served as Finnish to
        every chain showing the same film."""
        shows, log = self.run_site()
        syn = {s["title"]: s.get("_syn") for s in shows}
        self.assertEqual(syn["THE DOG STARS"], {"sv": "Om h\u00f6sten och hundarna."})
        self.assertIn("Swedish synopsis", log)

    def test_the_spoken_language_reaches_that_films_screenings_only(self):
        shows, _ = self.run_site(**{f"{BASE}/film/marsupilami": film_page(
            body="Om Marsupilami.</p><p>SVENSKT TAL!")})
        got = {s["title"]: s["lang"] for s in shows}
        self.assertEqual(got["MARSUPILAMI"], "SV-A")
        self.assertEqual({v for k, v in got.items() if k != "MARSUPILAMI"}, {""})

    def test_the_runtime_and_the_age_limit_reach_every_screening(self):
        """Not only the price: the same page carries both, and both are per film, so every
        screening of a film gets the same pair."""
        shows, log = self.run_site()
        got = {}
        for s in shows:
            got.setdefault(s["title"], set()).add((s["len"], s["rating"]))
        for title, pairs in got.items():
            with self.subTest(title=title):
                self.assertEqual(pairs, {("127", "K-12")})
        self.assertIn("timed", log)
        self.assertIn("rated", log)

    def test_a_film_with_no_body_carries_no_synopsis_key_at_all(self):
        shows, _ = self.run_site()
        marsu = next(s for s in shows if s["title"] == "MARSUPILAMI")
        self.assertNotIn("_syn", marsu)

    def test_what_synmerge_does_with_it_lands_in_the_swedish_slot(self):
        """The end of the path, through the real helper rather than a restatement."""
        shows, _ = self.run_site()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = pathlib.Path(tmp.name)
        synmerge.reset()
        self.addCleanup(synmerge.reset)
        with contextlib.redirect_stdout(io.StringIO()):
            synmerge.merge(out, {"savoy-mariehamn": shows}, "biosavoy", 0)
        films = json.loads((out / "films-extra.json").read_text())["films"]
        entry = films[synmerge.norm("THE DOG STARS")]["s"]
        self.assertEqual(entry["sv"], "Om h\u00f6sten och hundarna.")
        self.assertEqual(entry["fi"], "")

    def test_every_show_still_meets_the_contract_with_the_helper_stripped(self):
        shows, _ = self.run_site()
        synmerge.strip_helpers(shows)
        common.check_shows({"savoy-mariehamn": shows}, "biosavoy", {"savoy-mariehamn"})


class RatingPrecedenceTest(unittest.TestCase):
    """The cinema's own age limit outranks the shared classification pass.

    That pass fills a blank rating from another chain showing the same film. Bio Savoy now
    states its own, and a borrowed one must not replace it -- the two disagree in the normal
    case, because one is the Åland cinema's and the other is whatever chain matched first.
    """

    TABLE = {7: {"rating": "K-16", "runtimes": {127}}}

    def test_a_rating_the_cinema_published_is_never_replaced(self):
        show = {"rating": "K-12", "tmdbId": 7, "len": "127"}
        self.assertIsNone(enrich_tmdb.borrowed_rating(show, self.TABLE))

    def test_a_blank_rating_may_still_be_filled(self):
        show = {"rating": "", "tmdbId": 7, "len": "127"}
        self.assertEqual(enrich_tmdb.borrowed_rating(show, self.TABLE), "K-16")

    def test_bio_savoy_now_publishes_one_so_the_pass_has_nothing_to_do(self):
        shows = [dict(s) for s in biosavoy.parse(LISTING)]
        for s in shows:
            s["rating"] = "K-12"
            with self.subTest(title=s["title"]):
                self.assertIsNone(enrich_tmdb.borrowed_rating({**s, "tmdbId": 7},
                                                              self.TABLE))


if __name__ == "__main__":
    unittest.main()
