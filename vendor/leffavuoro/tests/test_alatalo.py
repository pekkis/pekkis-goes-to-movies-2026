"""Movie Company Alatalo: one hand-typed page, five touring towns.

Fixtures are shapes read on the live page 2026-09-19 and in eleven Wayback captures from
2023-03 to 2026-06. What they prove:

- the venue is keyed on the town name, not on the grey span four of five headings carry;
- an unrecognised heading takes the venue with it, so its rows are withheld rather than
  filed under the town above;
- only a place-name-shaped first word ever reaches the log, never an address;
- the widenings over `huvimylly.py` each read a line that capture carries.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import alatalo as A
import common
import registry
import run


SITE = A.SITES[0]
TODAY = datetime.date(2026, 9, 19)          # a Saturday
FI_LONG = ("Maanantaina", "Tiistaina", "Keskiviikkona", "Torstaina", "Perjantaina",
           "Lauantaina", "Sunnuntaina")
PRICE_LINE = "Liput elokuviin vain10-€ (Käteismaksu)"
# The standing header carries the operator's own address and mobile on the live page. The
# fixture carries their shape so the privacy guard is exercised, not the real values.
ADDRESS = "esimerkki" + "@" + "example.invalid"   # built, so the leak guard in
HEADER = ["Tilaa oma elokuvaesitys", "(Yritys/Kerhot/Yhdistykset/Koulukino)",
          "Alatalon kiertue-elokuvat jo 75 vuotta", ADDRESS, "0400000000"]
# test_contact_address.py does not read this file as carrying one.


def head(d):
    """A date heading with the weekday the date really has."""
    return f"{FI_LONG[d.weekday()]} {d.day}.{d.month}"


def page(*lines, price=True):
    """The programme as this site renders it: `<p>` and `<li>` mixed, entities, nbsp."""
    body = ['<script>domMenu_data.setItem("domMenu_top", "Elokuvaesitykset");</script>']
    if price:
        body.append(f"<p>{PRICE_LINE}</p>")
    body += [f"<p>{x}</p>" for x in HEADER]
    for i, x in enumerate(lines):
        body.append(f"<li>{x}</li>" if i % 2 else f"<p><strong>{x}</strong></p>")
    body.append('<p><img src="/Image/pirjo.jpg" height="326" width="217" /></p>')
    body.append("<p>&nbsp;</p><h2>.</h2>")
    return f'<html><body><div class="main">{"".join(body)}</div>NettiTieto Oy</body></html>'


def soon(days, today=TODAY):
    return today + datetime.timedelta(days=days)


def parse(*lines, today=TODAY, **kw):
    return A.rows(SITE, A.lines(page(*lines, **kw)), today)


def titles(per_venue, vid):
    return [s["title"] for s in per_venue[vid]]


class LinesTest(unittest.TestCase):
    def test_the_navigation_script_is_not_part_of_the_programme(self):
        self.assertNotIn("Elokuvaesitykset", " ".join(A.lines(page("Pudasjärvi Pohjantähti"))))

    def test_a_block_per_line_and_nbsp_collapsed(self):
        got = A.lines('<p>Kiuruvesi&nbsp; Kiurusali</p><li>Klo&nbsp;13.00 Pirjo -s-</li>')
        self.assertEqual(got, ["Kiuruvesi Kiurusali", "Klo 13.00 Pirjo -s-"])

    def test_a_line_of_punctuation_is_dropped(self):
        self.assertEqual(A.lines("<p>.</p><p>&nbsp;-&nbsp;</p><h2>…</h2>"), [])

    def test_a_response_that_is_not_html_raises(self):
        with self.assertRaises(RuntimeError):
            A.lines("One moment, please")


class TownTest(unittest.TestCase):
    def test_the_town_name_switches_the_venue_with_no_styling_to_help(self):
        """Toholampi never carries the grey span in any capture and Haapajärvi lost it
        in 2024-12, so the heading is recognised by its first word alone."""
        d = soon(5)
        out, _ = parse("Toholampi Toholampisali", head(d), "Klo 13.00 Pirjo -s-")
        self.assertEqual(titles(out, "alatalo-toholampi"), ["Pirjo"])

    def test_the_hall_may_be_lowercase_or_missing_or_trailed_by_a_dash(self):
        d = soon(5)
        for heading in ("Kemijärvi kulttuurikeskus", "Kemijärvi",
                        "Kemijärvi Kulttuurikeskus -"):
            with self.subTest(heading=heading):
                out, _ = parse(heading, head(d), "Klo 13.00 Pirjo -s-")
                self.assertEqual(titles(out, "alatalo-kemijarvi"), ["Pirjo"])

    def test_an_all_caps_heading_is_the_same_town(self):
        """The 2023-03 template types every heading in capitals."""
        d = soon(5)
        out, _ = parse("KIURUVESI KIURUSALI", head(d), "Klo 13.00 Pirjo -s-")
        self.assertEqual(titles(out, "alatalo-kiuruvesi"), ["Pirjo"])

    def test_a_date_does_not_carry_across_a_town_heading(self):
        """Kiuruvesi's row is unplaced, so the town is left out rather than confirmed
        empty."""
        d = soon(5)
        out, rep = parse("Pudasjärvi Pohjantähti", head(d), "Klo 13.00 Pirjo -s-",
                         "Kiuruvesi Kiurusali", "Klo 15.00 Vinski 2 -k7/4-")
        self.assertEqual(titles(out, "alatalo-pudasjarvi"), ["Pirjo"])
        self.assertNotIn("alatalo-kiuruvesi", out)
        self.assertEqual(rep["unconfirmed"], ["Kiuruvesi"])

    def test_a_declared_town_with_no_row_publishes_nothing_for_it(self):
        d = soon(5)
        out, _ = parse("Haapajärvi Teatterisali", "Kiuruvesi Kiurusali",
                       head(d), "Klo 13.00 Pirjo -s-")
        self.assertEqual(out["alatalo-haapajarvi"], [])
        self.assertTrue(A.EMPTY_VENUES_CONFIRMED)

    def test_rows_in_a_shape_this_parser_misses_leave_that_town_out(self):
        """Pudasjärvi parses; Kiuruvesi's rows open `Kello`, which no pattern reads. Its
        heading has a date and a time under it, so it is not shown to be empty."""
        a, b = soon(5), soon(6)
        out, rep = parse("Pudasjärvi Pohjantähti", head(a), "Klo 13.00 Pirjo -s-",
                         "Kiuruvesi Kiurusali", head(b), "Kello 15.00 Vinski 2 -k7/4-",
                         "Kello 17.00 Kerro se kaikille -k12/9-")
        self.assertEqual(titles(out, "alatalo-pudasjarvi"), ["Pirjo"])
        self.assertNotIn("alatalo-kiuruvesi", out)
        self.assertEqual(rep["unconfirmed"], ["Kiuruvesi"])

    def test_another_town_s_dates_do_not_vouch_for_this_one(self):
        """The digit check is per town: Kiuruvesi's lone date heading is its own evidence
        of a programme, whatever Pudasjärvi placed."""
        a, b = soon(5), soon(6)
        out, rep = parse("Pudasjärvi Pohjantähti", head(a), "Klo 13.00 Pirjo -s-",
                         "Kiuruvesi Kiurusali", head(b))
        self.assertNotIn("alatalo-kiuruvesi", out)
        self.assertEqual(rep["numbered"]["Kiuruvesi"], 1)
        self.assertEqual(rep["unconfirmed"], ["Kiuruvesi"])

    def test_a_heading_with_only_a_note_under_it_is_still_empty(self):
        """`ELOKUVAT JATKUU SYYSKUUSSA` carries no digit: that town has nothing on."""
        a = soon(5)
        out, rep = parse("Toholampi Toholampisali", "ELOKUVAT JATKUU SYYSKUUSSA",
                         "Kiuruvesi Kiurusali", head(a), "Klo 13.00 Pirjo -s-")
        self.assertEqual(out["alatalo-toholampi"], [])
        self.assertEqual(rep["unconfirmed"], [])

    def test_an_inflected_heading_leaves_every_empty_town_out(self):
        """`Kiuruveden Kiurusali` is not read as Kiuruvesi, so its rows are undeclared.
        Kiuruvesi then looks absent, and any empty town could be the one they belong to."""
        a, b = soon(5), soon(6)
        out, rep = parse("Pudasjärvi Pohjantähti", head(a), "Klo 13.00 Pirjo -s-",
                         "Kiuruveden Kiurusali", head(b), "Klo 15.00 Vinski 2 -k7/4-")
        self.assertEqual(titles(out, "alatalo-pudasjarvi"), ["Pirjo"])
        self.assertEqual(sorted(out), ["alatalo-pudasjarvi"])
        self.assertEqual(rep["undeclared"], {"Kiuruveden": 1})

    def test_a_screening_typed_onto_the_heading_line_leaves_that_town_out(self):
        """The first word makes the line a heading and the rest is never read, so the
        date and time on it are that town's own evidence."""
        a, b = soon(5), soon(6)
        out, rep = parse("Pudasjärvi Pohjantähti", head(a), "Klo 13.00 Pirjo -s-",
                         f"Kiuruvesi {head(b)} klo 15.00 Vinski 2 -k7/4-")
        self.assertNotIn("alatalo-kiuruvesi", out)
        self.assertEqual(rep["unconfirmed"], ["Kiuruvesi"])

    def test_unread_dated_lines_under_an_unrecognised_heading_leave_empty_towns_out(self):
        """No `Klo` line under `Kiuruveden`, so nothing is counted as undeclared; its date
        and its `Kello` row are still lines no declared town owns."""
        a, b = soon(5), soon(6)
        out, rep = parse("Pudasjärvi Pohjantähti", head(a), "Klo 13.00 Pirjo -s-",
                         "Kiuruveden Kiurusali", head(b), "Kello 15.00 Vinski 2 -k7/4-")
        self.assertEqual(rep["undeclared"], {})
        self.assertEqual(sorted(out), ["alatalo-pudasjarvi"])
        self.assertIn("Kiuruvesi", rep["unvouched"])

    def test_an_undeclared_town_listed_first_leaves_empty_towns_out(self):
        """`Haapavesi` above every declared town: its row is undeclared and no line after
        the first declared heading carries a stray digit."""
        a, b = soon(5), soon(6)
        out, rep = parse("Haapavesi RW Sali", head(a), "Klo 15.00 Vinski 2 -k7/4-",
                         "Pudasjärvi Pohjantähti", head(b), "Klo 13.00 Pirjo -s-")
        self.assertEqual(rep["undeclared"], {"Haapavesi": 1})
        self.assertEqual(rep["stray"], 0)
        self.assertEqual(sorted(out), ["alatalo-pudasjarvi"])

    def test_the_page_as_read_on_2026_09_24_keeps_toholampi_empty(self):
        """Four towns with rows, Toholampi not on the page at all, the footer last. The
        page is the operator's whole programme and nothing on it is unaccounted for."""
        a, b, c, d = soon(23), soon(28), soon(29), soon(35)
        out, rep = parse("Pudasjärvi Pohjantähti", head(a), "Klo 16.30 Saapasjalkakissa",
                         "unohdettu saari -k7/4-", "Klo 18.30 Pirjo -k?",
                         "Haapajärvi Teatterisali", head(b),
                         "Klo 16.00 Kerro se kaikille -k12/9-", "KLo 19.30-?",
                         "Kiuruvesi Kiurusali", f"{head(c)} -", "Klo 15.00 Pirjo -s-",
                         "Kemijärvi Kulttuurikeskus", head(d), "Klo 13.00 ?",
                         "Klo 15.00 Lapin Sota k?", "k", "lo")
        self.assertEqual(out["alatalo-toholampi"], [])
        self.assertEqual([len(out[v]) for v in ("alatalo-pudasjarvi", "alatalo-haapajarvi",
                                                "alatalo-kiuruvesi", "alatalo-kemijarvi")],
                         [2, 1, 1, 1])
        self.assertEqual(rep["unconfirmed"] + rep["unvouched"], [])


class HeadingShapeTest(unittest.TestCase):
    """Two towns, and a heading typed in a way the town and date rules both missed (audit
    A4, 2026-09-25): `Toholampi/Lestijärvi` reset nothing, so Toholampi's row was filed
    under the town above it and Toholampi was vouched empty; `Lestijärvi 3.10.` passed as
    a date heading, since any six-letter word stood for the weekday, and added a phantom
    screening under that town."""

    def test_a_town_joined_to_another_by_a_slash_is_still_that_town(self):
        d, e = soon(5), soon(6)
        out, _ = parse("Kiuruvesi Kiurusali", head(d), "Klo 13.00 Pirjo -s-",
                       "Toholampi/Lestijärvi", head(e), "Klo 19.00 Vinski 2 -k7/4-")
        self.assertEqual(titles(out, "alatalo-kiuruvesi"), ["Pirjo"])
        self.assertEqual(titles(out, "alatalo-toholampi"), ["Vinski 2"])

    def test_a_place_with_a_date_is_not_a_date_heading(self):
        d = soon(5)
        out, rep = parse("Kiuruvesi Kiurusali", head(d), "Klo 13.00 Pirjo -s-",
                         "Lestijärvi 3.10.", "Klo 15.00 Vinski 2 -k7/4-")
        self.assertEqual([(s["title"], s["start"][:10]) for s in out["alatalo-kiuruvesi"]],
                         [("Pirjo", d.isoformat())])
        self.assertEqual(rep["undeclared"], {"Lestijärvi": 1})
        self.assertNotIn("alatalo-toholampi", out, "an unowned row vouches no town empty")


class UndeclaredTownTest(unittest.TestCase):
    def test_its_rows_are_withheld_and_counted_under_its_own_name(self):
        """`Haapavesi RW Sali` ran in both 2024 captures and in none of the five since."""
        d = soon(5)
        out, rep = parse("Pudasjärvi Pohjantähti", head(d), "Klo 13.00 Pirjo -s-",
                         "Haapavesi RW Sali", head(d), "Klo 15.00 Vinski 2 -k7/4-",
                         "Klo 17.00 Kerro se kaikille -k12/9-")
        self.assertEqual(titles(out, "alatalo-pudasjarvi"), ["Pirjo"])
        self.assertEqual(rep["undeclared"], {"Haapavesi": 2})
        self.assertEqual(sum(len(v) for v in out.values()), 1)

    def test_an_unrecognised_heading_with_no_row_is_not_named(self):
        """`ELOKUVAT JATKUU SYYSKUUSSA` stands under every town in the 2025-08 capture."""
        d = soon(5)
        out, rep = parse("Pudasjärvi Pohjantähti", head(d), "Klo 13.00 Pirjo -s-",
                         "Elokuvat jatkuu syyskuussa", "Kiuruvesi Kiurusali")
        self.assertEqual(rep["undeclared"], {})
        self.assertEqual(titles(out, "alatalo-pudasjarvi"), ["Pirjo"])

    def test_an_address_or_a_number_is_never_a_heading(self):
        for line in (ADDRESS, "0400000000", "Liput 2 kpl",
                     "kiertue jatkuu", "Nyt", "Näillä elokuvilla aloitetaan nyt heti"):
            with self.subTest(line=line):
                self.assertEqual(A._heading_candidate(line), "")

    def test_a_place_name_shaped_word_is_one(self):
        self.assertEqual(A._heading_candidate("Haapavesi RW Sali"), "Haapavesi")
        self.assertEqual(A._heading_candidate("YLIVIESKA AKUSTIIKKA"), "YLIVIESKA")


class RowTest(unittest.TestCase):
    def test_a_bare_k_question_mark_closes_the_title(self):
        """`Klo 15.00 Lapin Sota k?` on the live page: no dash, and two of its thirteen
        rows turn on it."""
        d = soon(5)
        out, _ = parse("Kemijärvi Kulttuurikeskus", head(d),
                       "Klo 15.00 Lapin Sota k?", "Klo 18.00 Lapin Sota k?- -")
        self.assertEqual(titles(out, "alatalo-kemijarvi"), ["Lapin Sota", "Lapin Sota"])
        self.assertEqual({s["rating"] for s in out["alatalo-kemijarvi"]}, {""})

    def test_a_code_outside_the_legal_classes_is_no_rating(self):
        """`Klo 18.00 Lapin Sota -k6/13` on the live page, 2026-09-25: a typo for 16/13,
        since the law's classes are S, 7, 12, 16 and 18. It closes the title and states
        no rating; K-6 went out and was lent to four chains."""
        d = soon(5)
        out, _ = parse("Kiuruvesi Kiurusali", head(d), "Klo 18.00 Lapin Sota -k6/13",
                       "Klo 20.00 Kolme kovaa -k16/13")
        self.assertEqual(titles(out, "alatalo-kiuruvesi"), ["Lapin Sota", "Kolme kovaa"])
        self.assertEqual([s["rating"] for s in out["alatalo-kiuruvesi"]], ["", "K-16"])

    def test_a_leading_time_with_a_marker_is_a_row(self):
        """`16.30 Kero se kaikille -k12/9-` on the live page, with the `Klo` left off."""
        d = soon(5)
        out, _ = parse("Kiuruvesi Kiurusali", head(d), "16.30 Kero se kaikille -k12/9-")
        self.assertEqual(titles(out, "alatalo-kiuruvesi"), ["Kero se kaikille"])

    def test_a_leading_time_with_no_marker_is_not_a_row(self):
        """A bare date carries no marker, which is what makes the rule above safe."""
        d = soon(5)
        out, rep = parse("Kiuruvesi Kiurusali", head(d), "12.10", "Klo 13.00 Pirjo -s-")
        self.assertEqual(titles(out, "alatalo-kiuruvesi"), ["Pirjo"])
        self.assertEqual(rep["unplaceable"], 0)

    def test_kl_reads_as_klo(self):
        """`Kl 19.00 Vonkka originaaliversio` twice in the 2023-12 capture."""
        d = soon(5)
        out, _ = parse("Kiuruvesi Kiurusali", head(d), "Kl 19.00 Vonkka -k7/4-")
        self.assertEqual(titles(out, "alatalo-kiuruvesi"), ["Vonkka"])

    def test_a_word_beginning_kl_is_not_a_screening(self):
        d = soon(5)
        out, rep = parse("Kiuruvesi Kiurusali", head(d),
                         "Klovnit tulevat kaupunkiin ensi viikolla -s-",
                         "Klo 13.00 Pirjo -s-")
        self.assertEqual(titles(out, "alatalo-kiuruvesi"), ["Pirjo"])
        self.assertEqual(rep["unplaceable"], 0)

    def test_a_title_may_run_across_two_lines(self):
        d = soon(5)
        out, _ = parse("Kiuruvesi Kiurusali", head(d), "Klo 17.00 Taru Sormustenherrasta",
                       "Rohrrimin sota -k12/9-")
        self.assertEqual(titles(out, "alatalo-kiuruvesi"),
                         ["Taru Sormustenherrasta Rohrrimin sota"])

    def test_a_town_heading_is_never_swallowed_as_a_continuation(self):
        """No capture ends a heading in a marker, so the tail here is constructed. The
        guard is one call and what it prevents is severe: the heading would join the
        film title above it and the town's own screenings would go unread."""
        d = soon(5)
        out, rep = parse("Pudasjärvi Pohjantähti", head(d), "Klo 13.00 Pirjo -s-",
                         "Klo 17.00 Vonkka", "Kiuruvesi Kiurusali -s-",
                         head(d), "Klo 19.00 Vinski 2 -k7/4-")
        self.assertEqual(titles(out, "alatalo-pudasjarvi"), ["Pirjo"])
        self.assertEqual(titles(out, "alatalo-kiuruvesi"), ["Vinski 2"])
        self.assertEqual(rep["unplaceable"], 1)

    def test_one_line_may_hold_two_times(self):
        d = soon(5)
        out, _ = parse("Kiuruvesi Kiurusali", head(d),
                       "Klo 14.00 ja 19.00 Myrskyluodon Maija -k12/9-")
        self.assertEqual([s["start"][11:16] for s in out["alatalo-kiuruvesi"]],
                         ["14:00", "19:00"])

    def test_consecutive_date_headings_share_the_rows_that_follow(self):
        a, b = soon(5), soon(6)
        out, _ = parse("Kemijärvi Kulttuurikeskus", head(a), head(b),
                       "Klo 17.00 Vonkka -k7/4-")
        self.assertEqual([s["start"][:10] for s in out["alatalo-kemijarvi"]],
                         [a.isoformat(), b.isoformat()])

    def test_a_placeholder_row_is_counted_and_left_out(self):
        """`Klo 13.00 ?` and `KLo 19.30-?` are both on the live page."""
        d = soon(5)
        out, rep = parse("Kemijärvi Kulttuurikeskus", head(d), "Klo 13.00 ?",
                         "KLo 19.30-?", "Klo 15.00 Lapin Sota k?",
                         "Klo 18.00 Pirjo -s-")
        self.assertEqual(len(out["alatalo-kemijarvi"]), 2)
        self.assertEqual(rep["unplaceable"], 2)

    def test_a_row_with_no_date_heading_is_counted_not_raised(self):
        """2024-08 heads Pudasjärvi `Maanantaina 9.` with the month left off; raising
        would cost the other four towns their schedule."""
        d = soon(5)
        out, rep = parse("Pudasjärvi Pohjantähti", "Maanantaina 9.",
                         "Klo 16.00 Itse ilkimys 4 -k7/4-",
                         "Kiuruvesi Kiurusali", head(d), "Klo 13.00 Pirjo -s-")
        self.assertNotIn("alatalo-pudasjarvi", out, "a row is there, so not confirmed empty")
        self.assertEqual(rep["unconfirmed"], ["Pudasjärvi"])
        self.assertEqual(titles(out, "alatalo-kiuruvesi"), ["Pirjo"])
        self.assertEqual(rep["unplaceable"], 1)

    def test_more_lines_unplaceable_than_placed_raises(self):
        d = soon(5)
        with self.assertRaises(A.ShowRowError) as cm:
            parse("Kemijärvi Kulttuurikeskus", head(d), "Klo 13.00 ?", "Klo 14.00 ?",
                  "Klo 15.00 Pirjo -s-")
        self.assertIn("template has moved", str(cm.exception))

    def test_no_poster_is_published(self):
        d = soon(5)
        out, _ = parse("Kiuruvesi Kiurusali", head(d), "Klo 13.00 Pirjo -s-")
        self.assertEqual({s["img"] for s in out["alatalo-kiuruvesi"]}, {""})


class DateTest(unittest.TestCase):
    def test_a_year_may_be_glued_on_with_a_dot_or_follow_a_space(self):
        """`Tiistaina 2.1.2024` and `Maanantaina 8.1 2024` in one capture."""
        for heading, want in (("Tiistaina 2.1.2027", "2027-01-02"),
                              ("Maanantaina 4.1 2027", "2027-01-04")):
            with self.subTest(heading=heading):
                out, _ = parse("Kiuruvesi Kiurusali", heading, "Klo 13.00 Pirjo -s-")
                self.assertEqual([s["start"][:10] for s in out["alatalo-kiuruvesi"]],
                                 [want])

    def test_a_year_typed_onto_the_month_is_refused_as_a_heading(self):
        """`Sunnuntaina 7.12024-` leaves digits no reading of this pattern can take."""
        d = soon(5)
        out, rep = parse("Kiuruvesi Kiurusali", "Sunnuntaina 7.12024-",
                         "Klo 13.00 Pirjo -s-", head(d),
                         "Klo 15.00 Vinski 2 -k7/4-")
        self.assertEqual(titles(out, "alatalo-kiuruvesi"), ["Vinski 2"])
        self.assertEqual(rep["unplaceable"], 1)

    def test_a_misspelled_weekday_still_places_the_date(self):
        """`Maanantana`, `Luantaina` and `Sununtaina` are all in the captures."""
        d = soon(5)
        bad = FI_LONG[d.weekday()][:2] + "xxxxxx"
        out, _ = parse("Kiuruvesi Kiurusali", f"{bad} {d.day}.{d.month}",
                       "Klo 13.00 Pirjo -s-")
        self.assertEqual([s["start"][:10] for s in out["alatalo-kiuruvesi"]],
                         [d.isoformat()])

    def test_a_weekday_that_fits_no_year_in_the_window_raises(self):
        d = soon(5)
        wrong = FI_LONG[(d.weekday() + 1) % 7]
        with self.assertRaises(A.ShowRowError) as cm:
            parse("Kiuruvesi Kiurusali", f"{wrong} {d.day}.{d.month}",
                  "Klo 13.00 Pirjo -s-")
        self.assertIn("cannot be placed", str(cm.exception))


class PriceTest(unittest.TestCase):
    def test_the_standing_line_settles_every_row(self):
        d = soon(5)
        out, rep = parse("Kiuruvesi Kiurusali", head(d), "Klo 13.00 Pirjo -s-")
        self.assertEqual({s["price"] for s in out["alatalo-kiuruvesi"]}, {"10€"})
        self.assertEqual(rep["no_price"], 0)

    def test_a_page_without_the_line_publishes_no_price(self):
        """The 2024-05 and 2024-08 captures carry none, which a hardcoded amount would
        have got wrong."""
        d = soon(5)
        out, rep = parse("Kiuruvesi Kiurusali", head(d), "Klo 13.00 Pirjo -s-",
                         price=False)
        self.assertEqual({s["price"] for s in out["alatalo-kiuruvesi"]}, {""})
        self.assertEqual(rep["no_price"], 1)

    def test_the_price_line_is_never_read_as_a_screening(self):
        d = soon(5)
        _, rep = parse("Kiuruvesi Kiurusali", head(d), "Klo 13.00 Pirjo -s-")
        self.assertEqual(rep["unplaceable"], 0)


class RunnerTest(unittest.TestCase):
    # A day ahead of the real clock: run.main publishes empty a kept file whose every day
    # has passed, and these tests are about a file that is still worth keeping.
    AHEAD = (datetime.datetime.now(A.FI).date() + datetime.timedelta(days=30)).isoformat()
    PREV = {"generated": "2026-09-01T00:00:00+00:00", "dates": [AHEAD],
            "horizon": AHEAD,
            "shows": [{"title": "Old", "start": f"{AHEAD}T12:00:00+03:00"}]}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._fetch = A.fetch
        self.addCleanup(lambda: setattr(A, "fetch", self._fetch))

    def serve(self, body):
        def fetch(url, **kw):
            if isinstance(body, Exception):
                raise body
            return body.encode("utf-8")
        A.fetch = fetch

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["alatalo", "--half", "all"])
        return code, out.getvalue() + err.getvalue()

    def live(self):
        today = datetime.datetime.now(A.FI).date()
        a, b = soon(5, today), soon(6, today)
        return page("Pudasjärvi Pohjantähti", head(a),
                    "Klo 16.30 Saapasjalkakissa", "unohdettu saari -k7/4-",
                    "Kiuruvesi Kiurusali", head(b), "Klo 13.00 Pirjo -s-")

    def test_the_site_publishes_each_town_into_its_own_file(self):
        self.serve(self.live())
        code, log = self.main()
        self.assertEqual(code, 0, log)
        a = json.loads((run.OUT / "area-alatalo-pudasjarvi.json").read_text())["shows"]
        b = json.loads((run.OUT / "area-alatalo-kiuruvesi.json").read_text())["shows"]
        self.assertEqual([len(a), len(b)], [1, 1])
        self.assertEqual({s["price"] for s in a + b}, {"10€"})
        self.assertIn("0 failures", log)

    def test_towns_and_no_screening_anywhere_is_an_empty_programme(self):
        """The 2025-08 capture lists all five towns under `ELOKUVAT JATKUU SYYSKUUSSA`."""
        self.serve(page("Pudasjärvi Pohjantähti", "ELOKUVAT JATKUU SYYSKUUSSA",
                        "Kiuruvesi Kiurusali", "ELOKUVAT JATKUU SYYSKUUSSA"))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertIn("no programme published", log)

    def test_towns_listed_with_nothing_under_them_is_an_empty_programme(self):
        """The 2025-04 capture lists all five towns one after another and nothing else."""
        self.serve(page("Nyt Kiertueella", "Pudasjärvi Pohjantähti", "Kiuruvesi Kiurusali",
                        "Toholampi Toholampisali", "Haapajärvi Teatterisali",
                        "Kemijärvi kulttuurikeskus"))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertIn("no programme published", log)

    def test_dated_lines_under_an_unrecognised_heading_are_not_an_empty_programme(self):
        """Every declared town listed with nothing under it, and `Kiuruveden` carrying a
        date and a `Kello` row: no declared town has a digit, the page still does."""
        (run.OUT / "area-alatalo-kiuruvesi.json").write_text(json.dumps(self.PREV))
        d = soon(5, datetime.datetime.now(A.FI).date())
        self.serve(page("Pudasjärvi Pohjantähti", "Toholampi Toholampisali",
                        "Kiuruveden Kiurusali", head(d), "Kello 13.00 Vinski 2 -k7/4-"))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertNotIn("no programme published", log)
        self.assertEqual(json.loads(
            (run.OUT / "area-alatalo-kiuruvesi.json").read_text()), self.PREV)

    def test_dated_rows_in_a_shape_this_parser_misses_are_not_an_empty_programme(self):
        """Town headings, date headings and a film per town, with no `Klo` line for the
        parser to match. A row it cannot read is not the page saying nothing is on."""
        (run.OUT / "area-alatalo-kiuruvesi.json").write_text(json.dumps(self.PREV))
        today = datetime.datetime.now(A.FI).date()
        a, b = soon(5, today), soon(6, today)
        self.serve(page("Pudasjärvi Pohjantähti", head(a), "Kello 16.30 Pirjo -s-",
                        "Kiuruvesi Kiurusali", head(b), "Kello 13.00 Vinski 2 -k7/4-"))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertNotIn("no programme published", log)
        self.assertEqual(json.loads(
            (run.OUT / "area-alatalo-kiuruvesi.json").read_text()), self.PREV)

    def test_rows_only_under_unrecognised_headings_fail_and_keep_the_previous_file(self):
        """Every heading in a form `_town_of` does not read, `Pudasjärven` for
        `Pudasjärvi`: each row is withheld as undeclared, and no declared town is shown
        to be empty by that."""
        (run.OUT / "area-alatalo-pudasjarvi.json").write_text(json.dumps(self.PREV))
        today = datetime.datetime.now(A.FI).date()
        a, b = soon(5, today), soon(6, today)
        self.serve(page("Pudasjärven Pohjantähti", head(a), "Klo 16.30 Pirjo -s-",
                        "Kiuruveden Kiurusali", head(b), "Klo 13.00 Vinski 2 -k7/4-"))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("Kiuruveden (1), Pudasjärven (1)", log)
        self.assertEqual(json.loads(
            (run.OUT / "area-alatalo-pudasjarvi.json").read_text()), self.PREV)

    def test_a_town_whose_rows_could_not_be_placed_keeps_its_previous_file(self):
        """2024-08 heads Pudasjärvi `Maanantaina 9.` with no month. Its row is there and
        unplaced, which is not the town having nothing on, so its file is not emptied
        while Kiuruvesi still publishes."""
        (run.OUT / "area-alatalo-pudasjarvi.json").write_text(json.dumps(self.PREV))
        today = datetime.datetime.now(A.FI).date()
        a, b = soon(5, today), soon(6, today)
        self.serve(page("Pudasjärvi Pohjantähti", "Maanantaina 9.",
                        "Klo 16.00 Itse ilkimys 4 -k7/4-",
                        "Kiuruvesi Kiurusali", head(a), "Klo 13.00 Pirjo -s-",
                        head(b), "Klo 15.00 Vinski 2 -k7/4-"))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertEqual(json.loads(
            (run.OUT / "area-alatalo-pudasjarvi.json").read_text()), self.PREV)
        b_ = json.loads((run.OUT / "area-alatalo-kiuruvesi.json").read_text())["shows"]
        self.assertEqual(len(b_), 2)

    def test_a_town_whose_rows_changed_shape_keeps_its_previous_file(self):
        """Kiuruvesi's rows open `Kello` while Pudasjärvi parses. Its file stands and
        Toholampi, absent with nothing unaccounted for, is published empty."""
        (run.OUT / "area-alatalo-kiuruvesi.json").write_text(json.dumps(self.PREV))
        today = datetime.datetime.now(A.FI).date()
        a, b = soon(5, today), soon(6, today)
        self.serve(page("Pudasjärvi Pohjantähti", head(a), "Klo 13.00 Pirjo -s-",
                        "Kiuruvesi Kiurusali", head(b), "Kello 15.00 Vinski 2 -k7/4-"))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertEqual(json.loads(
            (run.OUT / "area-alatalo-kiuruvesi.json").read_text()), self.PREV)
        self.assertEqual(json.loads(
            (run.OUT / "area-alatalo-toholampi.json").read_text())["shows"], [])
        self.assertIn("Kiuruvesi: a date or a time under its heading", log)

    def test_no_town_heading_at_all_fails_and_keeps_the_previous_file(self):
        (run.OUT / "area-alatalo-kiuruvesi.json").write_text(json.dumps(self.PREV))
        self.serve(page("Tervetuloa laatuelokuvien pariin"))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("template having moved", log)
        self.assertEqual(json.loads(
            (run.OUT / "area-alatalo-kiuruvesi.json").read_text()), self.PREV)

    def test_a_refused_page_keeps_the_previous_file(self):
        (run.OUT / "area-alatalo-kiuruvesi.json").write_text(json.dumps(self.PREV))
        self.serve(RuntimeError("HTTP Error 403"))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertEqual(json.loads(
            (run.OUT / "area-alatalo-kiuruvesi.json").read_text()), self.PREV)

    def test_the_log_names_an_undeclared_town_and_nothing_else(self):
        today = datetime.datetime.now(A.FI).date()
        d = soon(5, today)
        self.serve(page("Kiuruvesi Kiurusali", head(d), "Klo 13.00 Pirjo -s-",
                        "Haapavesi RW Sali", head(d), "Klo 15.00 Vinski 2 -k7/4-"))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertIn("Haapavesi (1)", log)
        self.assertNotIn(ADDRESS, log)
        self.assertNotIn("0400000000", log)


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("alatalo")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Movie Company Alatalo", "moviecompanyalatalo.fi", "door",
                          "alatalo", "cloud"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"] == p["accent"]), 1)

    def test_the_site_names_the_one_host_it_reads(self):
        self.assertEqual([s["base"] for s in A.SITES],
                         ["http://www.moviecompanyalatalo.fi"])
        self.assertEqual(len(run.host_groups(A.SITES)), 1)

    def test_every_declared_town_has_a_venue_of_its_own(self):
        towns = [v["town"] for v in SITE["venues"]]
        self.assertEqual(len(towns), len(set(towns)))
        self.assertEqual([v["city"] for v in SITE["venues"]], towns)

    def test_the_grammar_is_shared_with_huvimylly(self):
        """Both pages are typed by the same person, so the shapes they agree on are read
        by one pattern rather than two that can drift."""
        import huvimylly
        self.assertIs(A.RATING_RE, huvimylly.RATING_RE)
        self.assertIs(A.TIME_RE, huvimylly.TIME_RE)


if __name__ == "__main__":
    unittest.main()
