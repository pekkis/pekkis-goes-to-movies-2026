"""Iso-Hannu: the front page's show table, and the film page behind each row.

The fixtures follow www.isohannu.fi's own markup as read on 2026-09-15: `<div
id="showtable">` holding a `<h3 class="showtable-title">` per day with the year in the
date, then one `div.showtable-container` per hall whose `<td class="showtable-hall">`
names it, and rows that nest the ticket anchor *inside* the title span.

Two days and three halls, not one of each: the parser walks days and halls as nested
loops and a single-item fixture would never enter either. The cases this file exists to
pin are the site's own oddities -- the ticket link written `http://` on a host that
answers `https://`, the age limit written `K12` where every other provider in this repo
publishes `K-12`, and a film page that carries no `Genre:` line at all.
"""
import unittest

import _ctx                                                # noqa: F401
import common
import isohannu

BASE = "https://www.isohannu.fi"
TICKETS = "http://lipunmyynti.isohannu.fi/app/movies"
SITE = isohannu.SITES[0]


def row(fid, time, title, show_id, tags=()):
    """One screening, with the ticket anchor nested inside the title span as the site
    writes it. `tags` are the extra `showtable-tag` spans beside the buy button."""
    extra = "".join(f'<span class="showtable-tag showtable-{k}">{v}</span>' for k, v in tags)
    return (f'<a href="/leffasivu.php?id={fid}">'
            f'<div class="showtable-row">'
            f'<span class="showtable-time">{time}</span>'
            f'<span class="showtable-name">{title}'
            f'<a href="{TICKETS}/{fid}/shows/{show_id}/products/list.html">'
            f'<span class="showtable-tag showtable-tickets">Osta liput &gt;</span></a>'
            f'{extra}</span></div></a>')


def hall(name, *rows):
    return (f'<div class="showtable-container"><table class="showtable">'
            f'<thead><tr><td class="showtable-hall">{name}</td></tr></thead>'
            f'<tbody><tr><td>{"".join(rows)}</td></tr></tbody></table></div>')


def day(title, *halls):
    return f'<h3 class="showtable-title">{title}</h3>{"".join(halls)}'


TARIFF = ("<h2>LIPUT</h2><p>Ma-to 13,50 \u20ac</p><p>Pe-su ja arkipyh\u00e4 14,50 \u20ac</p>"
          "<p>Meill\u00e4 k\u00e4y my\u00f6s Smartum.</p>"
          "<h2>ALENNUKSET</h2><p>Opiskelijat, el\u00e4kel\u00e4iset ja alle 12v lapset "
          "liput 13,50 \u20ac/kpl (korttia n\u00e4ytt\u00e4m\u00e4ll\u00e4).</p>"
          "<p>Tiistaisin liput S-Etukorttia vilauttamalla 10,00 \u20ac saman p\u00e4iv\u00e4n "
          "n\u00e4yt\u00f6ksiin</p>")


def page(*days, tariff=TARIFF):
    """The front page. The tariff block sits below the show table, and the discounts under
    it are the amounts a price reader must not pick up instead."""
    return ('<html><body><div id="showtable">' + "".join(days) +
            "</div>" + (tariff or "") +
            '<div id="footer">Elokuvateatteri Iso-Hannu</div></body></html>')


PAGE = page(
    day("Tiistai 15.09.2026",
        hall("Sali 1",
             row("2190", "18:00", "PRACTICAL MAGIC: LUMOTUT SISARET", "121294"),
             row("2139", "20:20", "THE RIVALS OF AMZIAH KING", "121266")),
        hall("Sali 2",
             row("2140", "18:00", "HETKI ENNEN VALOA", "121274"),
             row("2118", "19:40", "SPIDER-MAN: BRAND NEW DAY", "121298")),
        hall("Sali 3",
             # A dubbed children's screening: the marker is part of the title the cinema
             # publishes, and the strand tag is the site's own word.
             row("2109", "16:00", "TOY STORY 5 (suomeksi puhuttu)", "121369",
                 tags=(("children", "Lapsille"),)))),
    day("Keskiviikko 16.09.2026",
        hall("Sali 1",
             row("2140", "16:00", "HETKI ENNEN VALOA", "121342"),
             # The same film id on a second day: one film, two screenings.
             row("2190", "18:00", "PRACTICAL MAGIC: LUMOTUT SISARET", "121388",
                 tags=(("premiere", "Ensi-ilta"),))),
        hall("Sali 2",
             row("2133", "16:00", "PRESIDENTIN KYYDITYS", "121380"))))


def film_page(kesto="130 min", ika="K12", genre="fantasia", kieli="englanti", poster=True):
    img = ('<img src="https://lipunmyynti.isohannu.fi/images/posters/1/8/3/'
           '183f18bc71d4531_medium.jpg">') if poster else ""
    parts = [f"Elokuvan kesto: {kesto}" if kesto else "",
             f"Elokuvan ikäraja: {ika}" if ika else "",
             f"Genre: {genre}" if genre else "",
             f"Puhekieli: {kieli}" if kieli else ""]
    body = " ".join(f"<p>{p}</p>" for p in parts if p)
    return f"<html><body>{img}<div class='info'>{body}</div>Katso traileri</body></html>"


class TableTest(unittest.TestCase):
    def setUp(self):
        self.shows = isohannu.parse(PAGE)

    def test_every_screening_is_read_across_both_days_and_all_halls(self):
        self.assertEqual(len(self.shows), 8)
        self.assertEqual(sorted({s["start"][:10] for s in self.shows}),
                         ["2026-09-15", "2026-09-16"])
        self.assertEqual(sorted({s["aud"] for s in self.shows}),
                         ["Sali 1", "Sali 2", "Sali 3"])

    def test_the_day_heading_supplies_the_date_and_the_row_the_clock(self):
        first = self.shows[0]
        self.assertEqual(first["start"], "2026-09-15T16:00:00+03:00")
        self.assertEqual(first["title"], "TOY STORY 5 (suomeksi puhuttu)")
        self.assertEqual(first["aud"], "Sali 3")

    def test_a_row_belongs_to_the_hall_whose_container_holds_it(self):
        """The bug a flat row scan would cause: every row filed under the day's first
        hall. Checked on the 16th, where Sali 1 and Sali 2 both have rows."""
        by_hall = {}
        for s in self.shows:
            if s["start"][:10] == "2026-09-16":
                by_hall.setdefault(s["aud"], []).append(s["title"])
        self.assertEqual(by_hall["Sali 2"], ["PRESIDENTIN KYYDITYS"])
        self.assertEqual(sorted(by_hall["Sali 1"]),
                         ["HETKI ENNEN VALOA", "PRACTICAL MAGIC: LUMOTUT SISARET"])

    def test_the_event_id_is_the_film_not_the_screening(self):
        """Film 2190 runs on both days; both screenings carry the one id, so the client
        and films-extra.json see one film."""
        runs = [s for s in self.shows if s["eventId"] == "2190"]
        self.assertEqual(len(runs), 2)
        self.assertEqual({s["start"][:10] for s in runs}, {"2026-09-15", "2026-09-16"})

    def test_the_ticket_link_is_per_screening_and_upgraded_to_https(self):
        urls = [s["url"] for s in self.shows]
        self.assertEqual(len(set(urls)), len(urls))
        for u in urls:
            self.assertTrue(u.startswith("https://lipunmyynti.isohannu.fi/app/movies/"), u)
        self.assertNotIn("http://", " ".join(urls))

    def test_the_buy_button_is_not_a_strand_and_the_sites_own_words_are_kept(self):
        strands = {s["title"]: s["method"] for s in self.shows if s["method"]}
        self.assertEqual(strands["TOY STORY 5 (suomeksi puhuttu)"], "Lapsille")
        self.assertIn("Ensi-ilta", strands["PRACTICAL MAGIC: LUMOTUT SISARET"])
        for s in self.shows:
            self.assertNotIn("Osta liput", s["method"])

    def test_every_show_meets_the_contract(self):
        common.check_shows({SITE["venues"][0]["id"]: self.shows}, "isohannu",
                           {v["id"] for v in SITE["venues"]})

    def test_a_repeated_row_is_published_once(self):
        dupe = page(day("Tiistai 15.09.2026",
                        hall("Sali 1",
                             row("2190", "18:00", "PRACTICAL MAGIC", "121294"),
                             row("2190", "18:00", "PRACTICAL MAGIC", "121294"),
                             row("2139", "20:20", "THE RIVALS", "121266"))))
        self.assertEqual(len(isohannu.parse(dupe)), 2)


class EmptyAndBrokenTest(unittest.TestCase):
    def test_an_empty_table_is_a_failure_while_the_empty_state_is_unknown(self):
        """No empty programme of this site has been read, so an empty `showtable` is not
        evidence of one: it is also what a row-markup change inside it produces."""
        with self.assertRaises(RuntimeError) as cm:
            isohannu.parse(page())
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_days_and_halls_whose_rows_the_parser_misses_are_a_failure(self):
        """The table lists two days and three halls, and every row anchor has moved off
        `/leffasivu.php`: the page is full of films and the parse is empty."""
        moved = PAGE.replace('href="/leffasivu.php?id=', 'href="/elokuva.php?id=')
        with self.assertRaises(RuntimeError) as cm:
            isohannu.parse(moved)
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)
        self.assertIn("2 day heading(s)", str(cm.exception))

    def test_no_venue_is_ever_vouched_empty(self):
        """parse() never returns [], so nothing here may tell run.py that an empty venue
        is known empty and have it publish over the previous screenings."""
        self.assertFalse(getattr(isohannu, "EMPTY_VENUES_CONFIRMED", False))

    def test_a_page_without_the_table_is_a_failure_not_an_empty_programme(self):
        """The distinction the run depends on: no container means the template changed,
        and guessing "nothing on" there would age the previous data with no signal."""
        with self.assertRaises(RuntimeError) as cm:
            isohannu.parse("<html><body><p>Tervetuloa</p></body></html>")
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)

    def test_a_row_without_a_readable_clock_is_skipped_not_guessed(self):
        broken = page(day("Tiistai 15.09.2026",
                          hall("Sali 1",
                               row("2190", "kohta", "PRACTICAL MAGIC", "121294"),
                               row("2139", "20:20", "THE RIVALS", "121266"))))
        out = isohannu.parse(broken)
        self.assertEqual([s["title"] for s in out], ["THE RIVALS"])

    def test_an_impossible_date_does_not_abort_the_page(self):
        bad = page(day("Tiistai 31.02.2026", hall("Sali 1", row("1", "18:00", "X", "9"))),
                   day("Keskiviikko 16.09.2026", hall("Sali 1", row("2", "18:00", "Y", "8"))))
        self.assertEqual([s["title"] for s in isohannu.parse(bad)], ["Y"])


class FilmPageTest(unittest.TestCase):
    def test_the_age_limit_is_normalised_to_the_shape_every_provider_publishes(self):
        self.assertEqual(isohannu.details(film_page(ika="K12"))["rating"], "K-12")
        self.assertEqual(isohannu.details(film_page(ika="K7"))["rating"], "K-7")
        self.assertEqual(isohannu.details(film_page(ika="S"))["rating"], "S")

    def test_runtime_genres_language_and_poster_are_read(self):
        d = isohannu.details(film_page(kesto="102 min", genre="Komedia, Kauhu",
                                       kieli="Suomi"))
        self.assertEqual(d["len"], "102")
        self.assertEqual(d["genres"], "komedia, kauhu")
        self.assertEqual(d["lang"], "FI-A")
        self.assertTrue(d["img"].startswith("https://lipunmyynti.isohannu.fi/images/posters/"))

    def test_a_page_without_a_genre_line_yields_no_genre_rather_than_a_guess(self):
        """Film 2109 on 2026-09-15 carries no `Genre:` at all."""
        d = isohannu.details(film_page(genre=""))
        self.assertNotIn("genres", d)
        self.assertEqual(d["rating"], "K-12")

    def test_a_list_of_spoken_languages_is_each_of_them(self):
        """Punainen peto, read 2026-10-04: "Puhekieli: suomi, ruotsi, venäjä"."""
        self.assertEqual(isohannu.details(film_page(kieli="suomi, ruotsi, venäjä"))["lang"],
                         "FI-A, SV-A, RU-A")
        self.assertEqual(isohannu.details(film_page(kieli="englanti ja ranska"))["lang"],
                         "EN-A, FR-A")
        self.assertNotIn("lang", isohannu.details(film_page(kieli="suomi, klingon")))

    def test_an_unknown_spoken_language_yields_no_tag(self):
        self.assertNotIn("lang", isohannu.details(film_page(kieli="klingon")))

    def test_subtitles_are_never_invented(self):
        """The film page carries `Puhekieli` and no `Tekstitys`, so no -S role is emitted."""
        self.assertEqual(isohannu.details(film_page())["lang"], "EN-A")

    def test_details_fold_onto_every_screening_of_the_film(self):
        shows = isohannu.parse(PAGE)
        pages = {"2190": film_page(ika="K12", kesto="130 min"),
                 "2139": film_page(ika="K16", kesto="131 min"),
                 "2140": film_page(ika="K12", kesto="108 min"),
                 "2118": film_page(ika="K12", kesto="120 min"),
                 "2109": film_page(ika="K7", kesto="102 min", genre="", kieli="suomi"),
                 "2133": film_page(ika="K12", kesto="117 min")}
        isohannu.enrich(shows, get=lambda u: pages[u.rsplit("=", 1)[1]], sleep=0)
        runs = [s for s in shows if s["eventId"] == "2190"]
        self.assertEqual(len(runs), 2)
        for s in runs:
            self.assertEqual((s["rating"], s["len"]), ("K-12", "130"))
        toy = [s for s in shows if s["eventId"] == "2109"][0]
        self.assertEqual((toy["rating"], toy["lang"], toy["genres"]), ("K-7", "FI-A", ""))

    def test_a_film_page_that_fails_leaves_the_other_films_enriched(self):
        shows = isohannu.parse(PAGE)

        def get(u):
            if u.endswith("=2190"):
                raise OSError("boom")
            return film_page(ika="K16")

        isohannu.enrich(shows, get=get, sleep=0)
        self.assertEqual([s["rating"] for s in shows if s["eventId"] == "2190"], ["", ""])
        self.assertEqual({s["rating"] for s in shows if s["eventId"] == "2139"}, {"K-16"})


class RegistryTest(unittest.TestCase):
    def test_the_site_names_one_venue_in_rauma_and_the_host_it_reads(self):
        self.assertEqual(SITE["base"], BASE)
        self.assertEqual([v["city"] for v in SITE["venues"]], ["Rauma"])
        self.assertEqual(SITE["provider"], "isohannu")


class PriceTest(unittest.TestCase):
    """The house tariff, from the front page the adapter already fetches.

    `LIPUT Ma-to 13,50 € Pe-su ja arkipyhä 14,50 €`, read as a visitor 2026-09-16. The
    discounts printed under it all need a card shown at the counter, so the ordinary ticket
    is the one figure that describes what a visitor pays without one -- and they are the
    amounts a careless reader picks up instead.
    """

    def test_the_two_ordinary_amounts_are_read_as_a_pair(self):
        self.assertEqual(isohannu.tariff(page()), (13.5, 14.5))

    def test_the_discount_amounts_below_are_not_the_tariff(self):
        """13,50 appears again under ALENNUKSET and 10,00 for the Tuesday card offer."""
        self.assertEqual(isohannu.tariff(page()), (13.5, 14.5))

    def test_a_page_with_the_discounts_and_no_tariff_block_reads_nothing(self):
        """The anchor is `LIPUT Ma-to ... Pe-su ...` and not "two amounts on the page". A
        reader without it publishes the card-only 13,50 and 10,00 as the house tariff."""
        # Trimmed to the two sentences that matter, so the amounts sit as close together
        # as a loose reader would need them: the point is that no LIPUT block is present.
        discounts = ("<h2>ALENNUKSET</h2><p>Opiskelijat ja el\u00e4kel\u00e4iset 13,50 \u20ac.</p>"
                     "<p>S-Etukortilla 10,00 \u20ac.</p>")
        self.assertEqual(isohannu.tariff(page(tariff=discounts)), (None, None))

    def test_a_page_with_no_tariff_block_publishes_no_price(self):
        one_day = day("Tiistai 15.09.2026",
                      hall("Sali 1", row("2190", "18:00", "HETKI ENNEN VALOA", "121274")))
        self.assertEqual(isohannu.tariff(page(one_day, tariff="")), (None, None))
        shows = isohannu.parse(page(one_day, tariff=""))
        self.assertEqual({s["price"] for s in shows}, {""})

    def test_friday_to_sunday_is_published_and_monday_to_thursday_is_not(self):
        """`Pe-su ja arkipyhä 14,50 €` settles a Friday, Saturday or Sunday screening
        outright. `Ma-to 13,50 €` does not settle a weekday one, because the same line puts
        a weekday public holiday on the dearer tariff and no calendar here knows which days
        those are. 13,50 on such a day would be wrong, and a note saying so is not the same
        as being right."""
        import datetime
        for day_, want in ((14, ""), (15, ""), (16, ""), (17, ""),
                           (18, "14.5\u20ac"), (19, "14.5\u20ac"), (20, "14.5\u20ac")):
            with self.subTest(day=day_):
                when = datetime.datetime(2026, 9, day_, 18, 0, tzinfo=isohannu.FI)
                self.assertEqual(isohannu.price_of(13.5, 14.5, when), want)

    def test_the_cheaper_amount_is_read_and_never_published(self):
        """Read because a block stating one amount cannot say which days it covers;
        unpublished because the days it covers are not all knowable."""
        import datetime
        self.assertEqual(isohannu.tariff(page())[0], 13.5)
        when = datetime.datetime(2026, 9, 16, 18, 0, tzinfo=isohannu.FI)
        self.assertNotIn("13", isohannu.price_of(13.5, 14.5, when))

    def test_no_tariff_means_no_price_rather_than_a_blank_amount(self):
        import datetime
        when = datetime.datetime(2026, 9, 19, 18, 0, tzinfo=isohannu.FI)   # a Saturday
        self.assertEqual(isohannu.price_of(None, None, when), "")

    def test_every_screening_carries_what_its_own_day_settles(self):
        import datetime
        shows = isohannu.parse(PAGE)
        self.assertTrue(shows)
        by_day = {}
        for s in shows:
            by_day.setdefault(s["start"][:10], set()).add(s["price"])
        for iso, prices in by_day.items():
            with self.subTest(day=iso):
                weekday = datetime.date.fromisoformat(iso).weekday()
                self.assertEqual(prices, {"" if weekday <= 3 else "14.5\u20ac"})
        common.check_shows({isohannu.VENUE["id"]: shows}, "isohannu",
                           {isohannu.VENUE["id"]})

    def test_the_cents_are_dropped_only_when_they_are_zero(self):
        import datetime
        when = datetime.datetime(2026, 9, 19, 18, 0, tzinfo=isohannu.FI)   # a Saturday
        self.assertEqual(isohannu.price_of(13.0, 14.0, when), "14\u20ac")
        self.assertEqual(isohannu.price_of(13.5, 14.5, when), "14.5\u20ac")


if __name__ == "__main__":
    unittest.main()
