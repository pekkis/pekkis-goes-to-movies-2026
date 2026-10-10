"""Marita: one module on the front page, one block per screening.

The fixtures are the markup as read on 2026-09-19, plus the shapes ten captures of the
same page between 2025-05 and 2026-05 carry. What they exist to prove:

- **The language field is the print being shown.** `Englanti` and the lowercase `saksa`
  are in the captures beside `Suomi` on a dubbed animation, so the value publishes in the
  audio role and anything it cannot place publishes nothing.
- **A content descriptor is not a classification.** The block prints `age-img` and
  `label-img` from one directory, and only the first is a rating.
- **A price belongs to its screening.** `10/8 €` and a missing price element both settle
  nothing, and both occur in the captures.
- **An empty programme is the site's own sentence**, never an empty parse. Each of the
  three conditions is removed on its own and the evidence has to fail.
"""
import contextlib
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import marita as M
import registry
import run


SITE = M.SITES[0]
FILM = "https://elokuvateatterimarita.fi/elokuva/hetki-ennen-valoa/"
OTHER = "https://elokuvateatterimarita.fi/elokuva/presidentin-kyyditys/"
POSTER = ('<img width="421" height="600" '
          'src="https://elokuvateatterimarita.fi/wp-content/uploads/juliste-421x600.jpg" '
          'class="attachment-medium size-medium wp-post-image" />')
LANDSCAPE = ('<img width="1200" height="800" '
             'src="https://elokuvateatterimarita.fi/wp-content/uploads/banner.jpg" />')
LABELS = "wp-content/themes/marita/assets/images/labels"


def labels(age="7", descriptors=("a",)):
    out = ""
    if age:
        out += f'<img class="age-img" src="https://elokuvateatterimarita.fi/{LABELS}/{age}.png">'
    for d in descriptors:
        out += f'<img class="label-img" src="https://elokuvateatterimarita.fi/{LABELS}/{d}.png">'
    return f'<div class="movie-content-labels">{out}</div>'


def row(date, time, title, url=FILM, price="Hinta: 10 €", lang="Kieli: Suomi",
        img=POSTER, age="7", descriptors=("a",)):
    price_cell = f'<div class="movie-info-price">{price}</div>' if price else ""
    lang_cell = f'<div class="movie-info-language">{lang}</div>' if lang else ""
    return (f'<div class="movie-info width-content-narrow grid-x grid-margin-x grid-margin-y">'
            f'<div class="movie-info-image cell small-4"><a href="{url}">{img}</a></div>'
            f'<div class="movie-info-text cell small-8">'
            f'<h3><a href="{url}">{title}</a></h3>'
            f"{price_cell}{lang_cell}{labels(age, descriptors)}</div>"
            f'<div class="movie-info-times text-right cell small-12">'
            f'<div class="movie-info-times-date">{date}</div>'
            f'<div class="movie-info-times-time">klo {time}</div>'
            f"</div></div>")


def page(*rows_, tail=True):
    body = ('<div class="show-times-movies">' + "".join(rows_) + "</div>") if rows_ else ""
    after = ('<div class="page-module page-module-movies movies width-content">'
             "<h2>Ohjelmistossa nyt</h2></div>") if tail else ""
    return ('<html><body><section class="entry-content">'
            '<div class="page-module page-module-news width-content">'
            '<div id="show-times" class="page-module show-times">'
            '<div class="module-title"><H2>Lähipäivien näytökset</H2></div>'
            + body + "</div>" + after + "</section></body></html>")


def empty_page(title=True, sentence=True, container=False):
    body = '<div class="show-times-movies"></div>' if container else ""
    head = '<div class="module-title"><H2>Lähipäivien näytökset</H2></div>' if title else ""
    words = "Ei tulevia näytösaikoja" if sentence else ""
    return ('<html><body><section class="entry-content">'
            '<div class="page-module page-module-news width-content">'
            '<div id="show-times" class="page-module show-times">'
            + head + body + words + "</div>"
            '<div class="page-module page-module-movies movies width-content">'
            "<h2>Ohjelmistossa nyt</h2></div></section></body></html>")


def film_page(kesto="1 h \t 27 min", genre="Seikkailu , toimintaelokuva",
              kuvaus="Klaus Härön uutuuselokuva kertoo kahden naisen kohtaamisesta."):
    def fact(label, value):
        return (f'<div class="grid-x movies-infos grid-margin-x">'
                f'<div class="cell movies-info-title">\n\t{label}\n</div>\t'
                f'<div class="cell movies-info-text">\n\t{value}\n</div></div>')
    facts = "".join(fact(k, v) for k, v in (("Kesto", kesto), ("Lajityyppi", genre),
                                            ("Ikäraja", "K-7 (4)"),
                                            ("Ohjaaja", "Klaus Härö")) if v)
    syn = f"<h2>Kuvaus</h2>\n<p>{kuvaus}</p>" if kuvaus else ""
    return ('<html><body><section class="entry-content">'
            '<div class="movies-content grid-x width-content">'
            f'<div class="cell movies-description">{syn}{labels()}</div>'
            f'<div class="cell movies-info"><h2>Tiedot</h2>{facts}</div>'
            "</div></section></body></html>")


TWO = page(row("19.09.2026", "17.00", "Hetki ennen valoa"),
           row("20.09.2026", "16.00", "Presidentin kyyditys", url=OTHER, age="12"))


class RowsTest(unittest.TestCase):
    def test_the_date_carries_its_year_and_the_time_is_dotted(self):
        shows, _ = M.rows(SITE, TWO)
        self.assertEqual([s["start"] for s in shows],
                         ["2026-09-19T17:00:00+03:00", "2026-09-20T16:00:00+03:00"])

    def test_a_single_amount_publishes_and_a_band_does_not(self):
        shows, report = M.rows(SITE, page(
            row("19.09.2026", "17.00", "Hetki ennen valoa"),
            row("20.09.2026", "16.00", "Minemare", url=OTHER, price="Hinta: 10/8 €")))
        self.assertEqual([s["price"] for s in shows], ["10€", ""])
        self.assertEqual(report["no_price"], {"Minemare"})

    def test_a_row_with_no_price_element_publishes_no_price(self):
        shows, report = M.rows(SITE, page(
            row("16.05.2026", "17.00", "Michael", price=""),
            row("17.05.2026", "14.00", "Lammasetsivät", url=OTHER)))
        self.assertEqual([s["price"] for s in shows], ["", "10€"])
        self.assertEqual(report["no_price"], {"Michael"})

    def test_the_language_is_the_print_being_shown(self):
        for value, want in (("Kieli: Suomi", "FI-A"), ("Kieli: Englanti", "EN-A"),
                            ("Kieli: saksa", "DE-A")):
            with self.subTest(value=value):
                shows, _ = M.rows(SITE, page(
                    row("19.09.2026", "17.00", "A", lang=value),
                    row("20.09.2026", "17.00", "B", url=OTHER, lang=value)))
                self.assertEqual({s["lang"] for s in shows}, {want})

    def test_a_language_cell_naming_two_or_none_publishes_nothing(self):
        shows, report = M.rows(SITE, page(
            row("19.09.2026", "17.00", "A", lang="Kieli: Suomi ja ruotsi"),
            row("20.09.2026", "17.00", "B", url=OTHER, lang="Kieli: Alkuperäinen"),
            row("21.09.2026", "17.00", "C", url=OTHER, lang="")))
        self.assertEqual([s["lang"] for s in shows], ["", "", ""])
        self.assertEqual(report["no_lang"], {"A", "B", "C"})

    def test_the_rating_is_the_age_image_and_never_a_descriptor(self):
        shows, _ = M.rows(SITE, page(
            row("19.09.2026", "17.00", "A", age="7", descriptors=("v", "a")),
            row("20.09.2026", "17.00", "B", url=OTHER, age="s", descriptors=("a",)),
            row("21.09.2026", "17.00", "C", url=OTHER, age="16", descriptors=("p", "x")),
            row("22.09.2026", "17.00", "D", url=OTHER, age="", descriptors=("a", "v"))))
        self.assertEqual([s["rating"] for s in shows], ["K-7", "S", "K-16", ""])

    def test_the_class_decides_which_image_is_the_classification(self):
        """`s.png` is the S rating here and `x.png` the sex descriptor, so no filename on
        the site collides today. The read is by class all the same: position would make a
        descriptor named like a limit into one."""
        shows, _ = M.rows(SITE, page(
            row("19.09.2026", "17.00", "A", age="", descriptors=("12",)),
            row("20.09.2026", "17.00", "B", url=OTHER, age="", descriptors=("s", "a"))))
        self.assertEqual([s["rating"] for s in shows], ["", ""])

    def test_the_portrait_poster_publishes_and_a_landscape_image_does_not(self):
        shows, _ = M.rows(SITE, page(
            row("19.09.2026", "17.00", "A"),
            row("20.09.2026", "17.00", "B", url=OTHER, img=LANDSCAPE)))
        self.assertTrue(shows[0]["img"].endswith("juliste-421x600.jpg"))
        self.assertEqual(shows[1]["img"], "")

    def test_the_screening_links_to_the_film_page_the_row_names(self):
        shows, _ = M.rows(SITE, TWO)
        self.assertEqual([s["url"] for s in shows], [FILM, OTHER])
        self.assertEqual(registry.by_id("marita")["book"], "door")

    def test_a_block_with_no_readable_date_fails_the_site(self):
        bad = row("pian", "17.00", "Pirjo", url=OTHER)
        with self.assertRaises(M.RowError):
            M.rows(SITE, page(row("19.09.2026", "17.00", "A"), bad))

    def test_a_block_that_names_no_film_fails_the_site(self):
        bad = ('<div class="movie-info width-content-narrow grid-x">'
               '<div class="movie-info-times-date">19.09.2026</div>'
               '<div class="movie-info-times-time">klo 17.00</div></div>')
        with self.assertRaises(M.RowError):
            M.rows(SITE, page(row("19.09.2026", "17.00", "A"), bad))

    def test_an_impossible_date_fails_the_site(self):
        with self.assertRaises(M.RowError):
            M.rows(SITE, page(row("19.09.2026", "17.00", "A"),
                              row("31.02.2026", "17.00", "B", url=OTHER)))

    def test_a_block_outside_the_show_times_module_is_not_a_screening(self):
        """The film pages render the same block, so the parse is scoped to the module."""
        stray = row("25.12.2026", "17.00", "Ei tämä", url=OTHER)
        shows, _ = M.rows(SITE, TWO.replace("</section>", stray + "</section>"))
        self.assertEqual([s["title"] for s in shows],
                         ["Hetki ennen valoa", "Presidentin kyyditys"])

    def test_the_show_shape(self):
        shows, _ = M.rows(SITE, TWO)
        s = shows[0]
        self.assertEqual((s["provider"], s["venue"], s["theatre"], s["aud"]),
                         ("marita", "marita-outokumpu", "Elokuvateatteri Marita", ""))
        self.assertEqual((s["original"], s["method"], s["genres"], s["len"], s["soldOut"]),
                         ("", "", "", "", False))
        self.assertEqual(s["eventId"], "hetki ennen valoa")


class EmptyProgrammeTest(unittest.TestCase):
    def test_the_three_conditions_together_are_the_evidence(self):
        self.assertTrue(M.empty_programme_evidence(empty_page()))

    def test_each_condition_alone_is_not(self):
        self.assertFalse(M.empty_programme_evidence(empty_page(title=False)))
        self.assertFalse(M.empty_programme_evidence(empty_page(sentence=False)))
        self.assertFalse(M.empty_programme_evidence(empty_page(container=True)))
        self.assertFalse(M.empty_programme_evidence("<html><body>nothing</body></html>"))

    def test_a_page_with_screenings_is_not_empty(self):
        self.assertFalse(M.empty_programme_evidence(TWO))

    def test_the_sentence_outside_the_module_does_not_confirm_anything(self):
        """A cinema writing the same words in its news column cannot silence a broken parse."""
        page_ = empty_page(sentence=False).replace(
            "<h2>Ohjelmistossa nyt</h2>", "<h2>Ei tulevia näytösaikoja</h2>")
        self.assertFalse(M.empty_programme_evidence(page_))


class FilmPageTest(unittest.TestCase):
    def test_the_runtime_reads_hours_and_minutes(self):
        for kesto, want in (("1 h \t 27 min", "87"), ("2 h 25 min", "145"),
                            ("95 min", "95"), ("", "")):
            with self.subTest(kesto=kesto):
                self.assertEqual(M.film_facts(film_page(kesto=kesto))["len"], want)

    def test_the_genre_list_is_tidied_and_capitalised(self):
        self.assertEqual(M.film_facts(film_page())["genres"],
                         "Seikkailu, Toimintaelokuva")
        self.assertEqual(M.film_facts(film_page(genre=""))["genres"], "")

    def test_the_synopsis_is_the_kuvaus_paragraph(self):
        facts = M.film_facts(film_page())
        self.assertTrue(facts["syn"].startswith("Klaus Härön uutuuselokuva"))
        self.assertNotIn("Ikäraja", facts["syn"])
        self.assertEqual(M.film_facts(film_page(kuvaus=""))["syn"], "")

    def test_one_page_per_distinct_film_and_it_fills_the_rows(self):
        shows, _ = M.rows(SITE, page(
            row("19.09.2026", "17.00", "Hetki ennen valoa"),
            row("20.09.2026", "14.00", "Hetki ennen valoa"),
            row("20.09.2026", "16.00", "Presidentin kyyditys", url=OTHER)))
        asked = []

        def fake(url):
            asked.append(url)
            return film_page(kuvaus=f"Kuvaus {url[-12:]}")
        self.assertEqual(M.enrich(shows, sleep=0, fetch_page=fake), 2)
        self.assertEqual(sorted(asked), sorted({FILM, OTHER}))
        self.assertEqual([s["len"] for s in shows], ["87", "87", "87"])
        self.assertEqual({s["genres"] for s in shows}, {"Seikkailu, Toimintaelokuva"})
        self.assertEqual(len({s["_syn"] for s in shows}), 2)

    def test_a_film_page_that_will_not_answer_costs_that_film_its_metadata_only(self):
        shows, _ = M.rows(SITE, TWO)

        def fake(url):
            if url == OTHER:
                raise RuntimeError("HTTP Error 500")
            return film_page()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(M.enrich(shows, sleep=0, fetch_page=fake), 1)
        self.assertEqual([s["len"] for s in shows], ["87", ""])
        self.assertIn("_syn", shows[0])
        self.assertNotIn("_syn", shows[1])


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
        self._fetch, self._sleep = M.fetch, M.SLEEP
        M.SLEEP = 0
        self.addCleanup(lambda: setattr(M, "fetch", self._fetch))
        self.addCleanup(lambda: setattr(M, "SLEEP", self._sleep))

    def serve(self, listing, films=True):
        def fetch(url, **kw):
            if isinstance(listing, Exception):
                raise listing
            body = film_page() if "/elokuva/" in url else listing
            return body.encode("utf-8")
        M.fetch = fetch

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["marita"])
        return code, out.getvalue() + err.getvalue()

    def test_the_site_publishes(self):
        self.serve(TWO)
        code, log = self.main()
        self.assertEqual(code, 0, log)
        shows = json.loads((run.OUT / "area-marita-outokumpu.json").read_text())["shows"]
        self.assertEqual(len(shows), 2)
        self.assertEqual([s["price"] for s in shows], ["10€", "10€"])
        self.assertEqual([s["len"] for s in shows], ["87", "87"])
        self.assertIn("0 failures", log)

    def test_the_sites_own_sentence_writes_a_fresh_empty_file(self):
        (run.OUT / "area-marita-outokumpu.json").write_text(json.dumps(self.PREV))
        self.serve(empty_page())
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertIn("no programme at the moment", log)
        body = json.loads((run.OUT / "area-marita-outokumpu.json").read_text())
        self.assertEqual(body["shows"], [])
        self.assertNotEqual(body["generated"], self.PREV["generated"])

    def test_zero_rows_without_the_sentence_fails_and_keeps_the_previous_file(self):
        (run.OUT / "area-marita-outokumpu.json").write_text(json.dumps(self.PREV))
        self.serve(page(tail=True))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("does not say it has nothing on", log)
        self.assertEqual(json.loads(
            (run.OUT / "area-marita-outokumpu.json").read_text()), self.PREV)

    def test_a_refused_page_keeps_the_previous_file(self):
        (run.OUT / "area-marita-outokumpu.json").write_text(json.dumps(self.PREV))
        self.serve(RuntimeError("HTTP Error 503"))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertEqual(json.loads(
            (run.OUT / "area-marita-outokumpu.json").read_text()), self.PREV)


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("marita")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Elokuvateatteri Marita", "elokuvateatterimarita.fi", "door",
                          "marita", "cloud"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"] == p["accent"]), 1)

    def test_the_site_names_the_host_it_reads(self):
        self.assertEqual([s["base"] for s in M.SITES],
                         ["https://elokuvateatterimarita.fi"])
        self.assertEqual(len(run.host_groups(M.SITES)), 1)

    def test_the_label_is_the_venue_name_so_the_page_slug_does_not_double_it(self):
        self.assertEqual(SITE["venues"][0]["name"], registry.by_id("marita")["label"])
        self.assertEqual(SITE["venues"][0]["city"], "Outokumpu")


if __name__ == "__main__":
    unittest.main()
