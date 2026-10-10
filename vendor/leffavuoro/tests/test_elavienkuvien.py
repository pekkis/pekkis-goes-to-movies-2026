"""Forssan Elävienkuvien teatteri: a listing of films, a page of screenings each.

The fixtures are the shapes read on the live site on 2026-09-19. What they exist to prove:

- **The sub-navigation shares the film links' path space.** `ohjelmisto/` holds
  `erikoisnaytokset/`, `esityskalenteri/` and `mykkaelokuvafestivaalit/` as well as twelve
  films, and only the films sit inside `movielifts`.
- **The poster is the listing's, not the film page's.** Both exist; measured that day,
  `{slug}-list.jpg` is 316x474 and `{slug}.jpg` is an 835x369 banner.
- **A date with no clock time is left out and counted**, never invented and never fatal.
- **The rating is the age image's file name**, the only signal the page carries for it.
- **Two amounts settle nothing**, so no price is published.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import _no_sleep as no_sleep
import elavienkuvien as E
import registry
import run


SITE = E.SITES[0]
BASE = "https://www.elavienkuvienteatteri.fi"


def lift(slug, title, poster=True):
    img = (f'<div class="lift_image"><a href="ohjelmisto/{slug}/">'
           f'<img src="client/ekt/userfiles/{slug}-list.jpg" alt="{title}" /></a></div>'
           if poster else "")
    return (f'<div class="lift">{img}<div class="lift_text"><h2>'
            f'<a href="ohjelmisto/{slug}/">{title}</a></h2>'
            f'<p>Kesto 1 h 27 min | <img src="includes/img/agelimits/agelimit_12.png" '
            f'class="age" /> </p><p>Seuraava näytös<br />Tänään klo 17:00</p>'
            f'<p><a href="ohjelmisto/{slug}/" class="button">Info ja näytökset</a></p>'
            f'</div><div class="multifooter">&nbsp;</div></div>')


SUBNAV = ('<div class="sub_navigation"><ul>'
          '<li><a href="ohjelmisto/erikoisnaytokset/">Erikoisnäytökset</a></li>'
          '<li><a href="ohjelmisto/esityskalenteri/">Esityskalenteri</a></li>'
          '<li><a href="ohjelmisto/mykkaelokuvafestivaalit/">Mykkäelokuvafestivaalit</a>'
          '</li></ul></div>')


def listing(*lifts):
    return ('<html><body>' + SUBNAV + '<div class="container" id="foxy-target-content">'
            '<div id="foxyedit-3"><h1>Ohjelmisto</h1><div class="movielifts">'
            + "".join(lifts) + '</div></div></div></body></html>')


def screening(day, month, year, time="17:00", movieid="1360", buy=True):
    a = (f'<a href="lipunvaraus/?movieid={movieid}&date={year}-{month:02d}-{day:02d}'
         f'&time={time}">Osta liput <i class="fa fa-shopping-cart"></i></a> | 13€ / 11€'
         if buy else "13€ / 11€")
    return f'su {day}.{month}.{year} klo {time} | {a}'


def film_page(title="Presidentin kyyditys", age="12", kesto="1 h 27 min",
              genres="draama, komedia", rows=("su 20.9.2026 klo 17:00 | "
                                              "<a href=\"lipunvaraus/?movieid=1360&"
                                              "date=2026-09-20&time=17:00\">Osta liput</a>"
                                              " | 13€ / 11€",)):
    age_img = (f'<img src="includes/img/agelimits/agelimit_{age}.png" class="age" />'
               if age else "")
    body = "<br />".join(rows)
    screenings = f'<div class="screenings"><p>{body}</p></div>' if rows else ""
    return ('<html><body><div class="movielifts"><div class="contents_thin">'
            f'<h2>{title}</h2>'
            f'<p><img src="client/ekt/userfiles/x.jpg" alt="{title}" /></p>'
            f'<p class="movielength">Kesto {kesto} | {age_img}<br />{genres}</p>'
            f'{screenings}'
            '<p><strong>Ohjaus:</strong><br />Samuli Valkama<p>'
            '</div></div></body></html>')


class ListingTest(unittest.TestCase):
    def test_only_the_films_are_read_and_the_subnavigation_is_not(self):
        got = E.films(listing(lift("presidentin-kyyditys", "Presidentin kyyditys"),
                              lift("myrskyn-ikkuna", "Myrskyn ikkuna")), BASE)
        self.assertEqual([f["slug"] for f in got],
                         ["ohjelmisto/presidentin-kyyditys/", "ohjelmisto/myrskyn-ikkuna/"])
        self.assertNotIn("ohjelmisto/esityskalenteri/", [f["slug"] for f in got])

    def test_the_poster_is_the_listings_portrait_one(self):
        [f] = E.films(listing(lift("digger", "Digger")), BASE)
        self.assertTrue(f["img"].endswith("/client/ekt/userfiles/digger-list.jpg"), f["img"])

    def test_a_film_with_no_image_still_reads(self):
        [f] = E.films(listing(lift("digger", "Digger", poster=False)), BASE)
        self.assertEqual(f["img"], "")
        self.assertTrue(f["url"].endswith("/ohjelmisto/digger/"))

    def test_a_page_that_is_not_the_listing_raises(self):
        with self.assertRaises(E.ListingError):
            E.films("<html><body>" + SUBNAV + "</body></html>", BASE)


class FilmPageTest(unittest.TestCase):
    FILM = {"slug": "ohjelmisto/x/", "url": f"{BASE}/ohjelmisto/x/", "img": "poster.jpg"}

    def rows(self, page, report=None):
        return E.shows_of(SITE, self.FILM, page, report)

    def test_a_screening_carries_its_own_year_so_nothing_is_resolved(self):
        [s] = self.rows(film_page())
        self.assertEqual(s["start"], "2026-09-20T17:00:00+03:00")
        self.assertEqual(s["title"], "Presidentin kyyditys")

    def test_the_rating_comes_from_the_age_image_file_name(self):
        for age, want in (("12", "K-12"), ("7", "K-7"), ("16", "K-16"), ("s", "S")):
            with self.subTest(age=age):
                [s] = self.rows(film_page(age=age))
                self.assertEqual(s["rating"], want)

    def test_the_sites_own_no_rating_marker_produces_none(self):
        [s] = self.rows(film_page(age="notset"))
        self.assertEqual(s["rating"], "")

    def test_the_runtime_counts_the_hours(self):
        self.assertEqual(self.rows(film_page(kesto="1 h 27 min"))[0]["len"], "87")
        self.assertEqual(self.rows(film_page(kesto="97 min"))[0]["len"], "97")
        self.assertEqual(self.rows(film_page(kesto="2 h 10 min"))[0]["len"], "130")

    def test_the_genres_are_the_line_after_the_age_image(self):
        [s] = self.rows(film_page(genres="draama, komedia"))
        self.assertEqual(s["genres"], "draama, komedia")

    def test_the_ticket_link_is_the_rows_own_seat_picker(self):
        [s] = self.rows(film_page())
        self.assertTrue(s["url"].endswith(
            "/lipunvaraus/?movieid=1360&date=2026-09-20&time=17:00"), s["url"])

    def test_a_row_without_a_link_falls_back_to_the_film_page(self):
        [s] = self.rows(film_page(rows=("su 20.9.2026 klo 17:00 | 13€ / 11€",)))
        self.assertEqual(s["url"], self.FILM["url"])

    def test_two_amounts_settle_nothing_so_no_price_is_published(self):
        [s] = self.rows(film_page())
        self.assertEqual(s["price"], "")

    def test_a_date_with_no_clock_time_is_counted_and_left_out(self):
        report = {"no_time": 0}
        got = self.rows(film_page(rows=("pe 2.10.2026",)), report)
        self.assertEqual(got, [])
        self.assertEqual(report["no_time"], 1)

    def test_a_timeless_row_beside_a_real_one_costs_only_itself(self):
        report = {"no_time": 0}
        got = self.rows(film_page(rows=("su 20.9.2026 klo 17:00 | 13€ / 11€",
                                        "pe 2.10.2026")), report)
        self.assertEqual(len(got), 1)
        self.assertEqual(report["no_time"], 1)

    def test_a_line_with_no_date_at_all_raises(self):
        with self.assertRaises(E.ListingError):
            self.rows(film_page(rows=("ensi viikolla, aika tarkentuu",)))

    def test_an_impossible_calendar_date_raises(self):
        with self.assertRaises(E.ListingError):
            self.rows(film_page(rows=("su 31.2.2026 klo 17:00",)))

    def test_a_film_page_with_no_title_raises(self):
        with self.assertRaises(E.ListingError):
            self.rows(film_page().replace("<h2>Presidentin kyyditys</h2>", ""))

    def test_a_film_with_no_screenings_block_is_not_an_error(self):
        self.assertEqual(self.rows(film_page(rows=())), [])


class RunnerTest(unittest.TestCase):
    def setUp(self):
        no_sleep.patch(self, E)                 # the 1.2 s pause between film pages
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._fetch = E.fetch
        self.addCleanup(lambda: setattr(E, "fetch", self._fetch))
        self.calls = []

    def serve(self, pages):
        def fetch(url, **kw):
            self.calls.append(url)
            body = pages.get(url)
            if isinstance(body, Exception):
                raise body
            if body is None:
                raise RuntimeError(f"unexpected fetch {url}")
            return body.encode("utf-8")
        E.fetch = fetch

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["elavienkuvien", "--half", "all"])
        return code, out.getvalue() + err.getvalue()

    def pages(self, **over):
        p = {
            f"{BASE}/ohjelmisto/": listing(lift("a", "Film A"), lift("b", "Film B")),
            f"{BASE}/ohjelmisto/a/": film_page(title="Film A"),
            f"{BASE}/ohjelmisto/b/": film_page(
                title="Film B", age="7",
                rows=("ti 22.9.2026 klo 19:30 | 13€ / 11€", "pe 2.10.2026")),
        }
        p.update(over)
        return p

    def test_the_site_publishes_and_names_what_it_left_out(self):
        self.serve(self.pages())
        code, log = self.main()
        self.assertEqual(code, 0, log)
        shows = json.loads(
            (run.OUT / "area-ekt-forssa.json").read_text(encoding="utf-8"))["shows"]
        self.assertEqual([s["title"] for s in shows], ["Film A", "Film B"])
        self.assertEqual([s["rating"] for s in shows], ["K-12", "K-7"])
        self.assertIn("1 row(s) announced for a day with no clock time yet", log)
        self.assertIn("0 failures", log)

    def test_the_subnavigation_pages_are_never_fetched(self):
        self.serve(self.pages())
        self.main()
        for nav in ("erikoisnaytokset", "esityskalenteri", "mykkaelokuvafestivaalit"):
            self.assertEqual([c for c in self.calls if nav in c], [], nav)

    def test_a_listing_with_no_film_fails_and_keeps_the_previous_file(self):
        prev = {"generated": "2026-09-01T00:00:00+00:00", "dates": ["2026-09-01"],
                "horizon": "2026-09-01", "shows": [{"title": "Old"}]}
        (run.OUT / "area-ekt-forssa.json").write_text(json.dumps(prev), encoding="utf-8")
        self.serve({f"{BASE}/ohjelmisto/": listing()})
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertEqual(json.loads(
            (run.OUT / "area-ekt-forssa.json").read_text(encoding="utf-8")), prev)

    def test_films_listed_with_no_screening_at_all_fails(self):
        """Twelve films and no screening on any of them is a template change, not a
        cinema with nothing on: this site publishes no empty-state text."""
        self.serve(self.pages(**{
            f"{BASE}/ohjelmisto/a/": film_page(title="A", rows=()),
            f"{BASE}/ohjelmisto/b/": film_page(title="B", rows=())}))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("template change", log)


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("elavienkuvien")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Elävienkuvien teatteri", "elavienkuvienteatteri.fi", "buy",
                          "elavienkuvien", "local"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"] == p["accent"]), 1)

    def test_the_site_names_the_one_host_it_reads(self):
        self.assertEqual([s["base"] for s in E.SITES], [BASE])
        self.assertEqual(len(run.host_groups(E.SITES)), 1)

    def test_forssa_now_holds_two_chains(self):
        """Bio-Kaari was alone there, so this creates the combined city view and the
        accent has to clear the floor against it."""
        import accent_check as A
        a = registry.by_id("elavienkuvien")["accent"]
        b = registry.by_id("biokaari")["accent"]
        self.assertGreater(A.separation_labs(A.labs_for(a), A.labs_for(b)), A.FLOOR)


if __name__ == "__main__":
    unittest.main()
