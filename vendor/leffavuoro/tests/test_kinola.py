"""Kino Kilta, Kino Laika and Kino Myyri: the policy, the templates, the overrides.

The fixtures are the markup as read on 2026-09-15, reduced to the smallest shape that
still exercises each rule. Two screenings minimum everywhere there is a loop or an index.

What the fixtures exist to prove, each one a rule that reads plausible and is wrong:

- **A runtime and an age classification are not film evidence.** Laika's billed live acts
  carry both: *Arppa* reads "130 min K-18" with no director and no genre. A classifier
  that counted either would publish every gig in Karkkila.
- **A word is never the classifier.** A film whose synopsis says konsertti publishes, and
  a concert film publishes; only the absence of a labelled director or genre withholds.
- **An override decides before the classifier**, in both directions. The exclude direction
  exists precisely because the default can include wrongly, so the redundancy guard must
  not reject an override whose page already classifies as a film.
- **A sold-out row keeps its screening.** Every sold-out row on the live listing that day
  was a live act, so only a fixture can show a sold-out *film* surviving.
- **Myyri's row prints no year**, so the weekday selects it. Its fixtures are built from a
  date, which is what keeps a runner test deterministic across a year boundary.
"""
import contextlib
import datetime
import io
import json
import pathlib
import re
import tempfile
import unittest

import _ctx                                                # noqa: F401
import common
import kinola as K
import registry
import run

KILTA = next(s for s in K.SITES if s["provider"] == "kinokilta")
LAIKA = next(s for s in K.SITES if s["provider"] == "kinolaika")
MYYRI = next(s for s in K.SITES if s["provider"] == "kinomyyri")
FI_WD = ("ma", "ti", "ke", "to", "pe", "la", "su")


# ---------------------------------------------------------------- listing fixtures

def kilta_row(slug, title, date="TI 15.9.2026", time="20:00", subtitle="Kahvikino",
              dur="106 min", checkout="ee317571-a29e-4a11-bdc0-61dadd74822f",
              sold=False):
    ticket = (f'<div class="wp-block-button"><span '
              f'class="kinola-event-tickets-link-sold-out">Loppuunmyyty</span></div>'
              if sold else
              f'<div class="wp-block-button"><a class="kinola-event-tickets-link '
              f'wp-block-button__link" href="https://www.kinokilta.fi/checkout/{checkout}">'
              f'Osta lippu</a></div>')
    return (f'<li class="kinola-event"><div class="movie-info"><div class="time">{time}</div>'
            f'<div class="date-movie"><div class="date">{date}</div>'
            f'<h3><a class="kinola-event-title" '
            f'href="https://www.kinokilta.fi/film/{slug}/">{title}</a></h3>'
            f'<div class="movie-subtitle">{subtitle}</div></div>'
            f'<div class="duration-info">{dur}</div></div>{ticket}</li>')


def laika_row(slug, title, date="16/09/2026 14:00", sold=False,
              checkout="a5e4ff5b-d55b-4c84-bafe-aba007a971fb", poster=True):
    img = (f'<img src="https://media.kinola.ee/storage/laika.kinola.ee/2569/{slug}'
           f'_poster.jpg?width=1000" class="kinola-event-poster"/>' if poster else "")
    ticket = ('<p><span class="kinola-event-tickets-link-sold-out">Loppuunmyyty</span></p>'
              if sold else
              f'<p><a class="kinola-event-tickets-link" '
              f'href="https://www.kinolaika.fi/checkout/{checkout}">Osta lippu</a></p>')
    return (f'<div class="kinola-event" style="padding: 10px 20px;">{img}'
            f'<div class="kinola-event-details"><p>'
            f'<a class="kinola-event-title" href="https://www.kinolaika.fi/film/{slug}/">'
            f'<strong>{title}</strong></a><br>'
            f'<span class="kinola-event-venue">Kino Laika</span><br>'
            f'<span class="kinola-event-date">{date}</span></p>{ticket}</div></div>')


def myyri_row(slug, title, when, time="19:30", sold=False, poster=True,
              checkout="2e4097de-cb51-4d0a-9fc6-28b1fd66ca38", date=None, href=None,
              no_ticket=False):
    """`when` is a date; the row prints its weekday, day and month and no year. `href`
    replaces the ticket anchor's href as printed; `no_ticket` drops the anchor."""
    date = date if date is not None else f"{FI_WD[when.weekday()]} {when.day}.{when.month}. klo {time}"
    img = (f'<img decoding="async" src="https://media.kinola.ee/storage/myyri.kinola.ee/'
           f'3786/{slug}_poster.jpg?width=1000&quality=85" width="100px" height="150px" '
           f'style="float: left;" class="kinola-event-poster"/>' if poster else "")
    ticket = ('<p><span class="kinola-event-tickets-link-sold-out">Loppuunmyyty</span></p>'
              if sold else "" if no_ticket else
              f'<p><a class="kinola-event-tickets-link" '
              f'href="{href or f"https://kinomyyri.fi/checkout/{checkout}"}">Osta lippu</a></p>')
    return (f'<div class="kinola-event" style="padding: 10px 20px;">{img}'
            f'<div class="kinola-event-details"><p>'
            f'<a class="kinola-event-title" href="https://kinomyyri.fi/film/{slug}/">'
            f'<strong>{title}</strong></a><br>'
            f'<span class="kinola-event-venue">Kino Myyri</span><br>'
            f'<span class="kinola-event-date">{date}</span></p>{ticket}</div></div>')


def kilta_row_sold_out_anchor(slug, title):
    """The defensive shape: the sold-out class on the anchor rather than on a span. Not
    observed on either site, which is why only a fixture reaches the guard that refuses to
    publish a checkout href from such a row."""
    return (f'<li class="kinola-event"><div class="movie-info"><div class="time">18:00</div>'
            f'<div class="date-movie"><div class="date">TI 15.9.2026</div>'
            f'<h3><a class="kinola-event-title" '
            f'href="https://www.kinokilta.fi/film/{slug}/">{title}</a></h3>'
            f'<div class="movie-subtitle"></div></div>'
            f'<div class="duration-info">90 min</div></div>'
            f'<div class="wp-block-button"><a class="kinola-event-tickets-link '
            f'kinola-event-tickets-link-sold-out" '
            f'href="https://www.kinokilta.fi/checkout/dead">Loppuunmyyty</a></div></li>')


FILTERS = ('<div class="kinola-filters"><form class="kinola-filters-form"><select '
           'class="js-kinola-film-filter kinola-film-filter"><option value="all">'
           'Kaikki elokuvat</option></select></form></div>')


SHERYL = next(s for s in K.SITES if s["provider"] == "sheryl")
EN_WD = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def sheryl_row(slug, title, when, time="15:00", poster=True, date=None, lang="fi",
               sold=False, no_ticket=False):
    """Sheryl's block is Myyri's with a different date string and a `-buy` ticket class.

    `lang` picks which of the two the site serves: it localises the weekday to whatever
    `accept-language` asks for, and the pipeline always asks for Finnish.
    """
    if date is None:
        wd = (FI_WD if lang == "fi" else EN_WD)[when.weekday()]
        date = f"{wd}, {when.day:02d}.{when.month:02d} {time}"
    img = (f'<a href="https://sheryl.fi/film/{slug}/"><img decoding="async" '
           f'class="kinola-event-poster" src="https://media.kinola.ee/storage/'
           f'sheryl.kinola.ee/891/{slug}_poster.jpg?width=1000&quality=85" /></a>'
           if poster else "")
    return (f'<div class="kinola-event kinola-thumbnail">{img}'
            f'<div class="kinola-event-details">'
            f'<span class="kinola-event-date">{date}</span>'
            f'<a class="kinola-event-title" href="https://sheryl.fi/film/{slug}/">'
            f'{title}</a>'
            + ('<span class="kinola-event-tickets-link-sold-out">Sold out</span>' if sold
               else "" if no_ticket else
               f'<span class="kinola-event-tickets"><a class="kinola-event-tickets-link-buy" '
               f'href="https://sheryl.fi/checkout/0112a866-2646-4310-b698-a6e5b1b84666">'
               f'Buy</a></span>')
            + '</div></div>')


def sheryl_film(director="Wong Kar-wai", rating="K-12", syn=None):
    """Sheryl's film page: Laika's `<strong>Label</strong><br>value` shape with the labels
    in English, which is what the site serves whatever language the listing came back in.
    Read 2026-09-19 on sheryl.fi/film/chungking-express-2/."""
    syn = SYN_EN_TEXT if syn is None else syn
    parts = [f"<p>{syn}</p>", "<strong>Chungking Express</strong><br>"]
    if director:
        parts.append(f"<strong> Director </strong><br> {director} <br><br>")
    parts.append("<strong> Cast </strong><br> Brigitte Lin <br><br>")
    parts.append("<strong> Language </strong><br> Cantonese <br><br>")
    head = f"102 min <br><br> {rating}" if rating else "102 min"
    return ('<html><body><section class="kinola-film-meta">'
            + f'<div class="film-head">{head}</div>' + "".join(parts)
            + "</section></body></html>")


def listing(*rows):
    return ("<html><body>" + FILTERS + '<div class="kinola-events">'
            + "".join(rows) + "</div></body></html>")


def empty_listing():
    """What the platform renders for a tenant with nothing on: the filter widget, **no**
    `kinola-events` container at all, and its own words where the list would be. Read as a
    visitor on kinokonepaja.fi 2026-09-15, the only tenant of the three in that state."""
    return ("<html><body>" + FILTERS
            + "<div> Ei tulevia tapahtumia. </div></body></html>")


def with_classes(row, *extra):
    """The same screening block carrying more classes. Neither live site does this today,
    which is why only a fixture reaches it -- and why an attribute match hid the screening
    with nothing in the log or the omission report to say one had gone."""
    return row.replace('class="kinola-event"',
                       'class="' + " ".join(("wp-block",) + extra + ("kinola-event",))
                       + '"', 1)


UNRELATED_HTML = ("<html><head><title>Kino</title></head><body><h1>Tervetuloa</h1>"
                  "<p>Sivusto uudistuu.</p></body></html>")


# ---------------------------------------------------------------- film-page fixtures

def kilta_film(director="Klaus Härö", genre="Draama", lang="suomi", subs="englanti",
               dur="87 min", rating="K-12", syn=None, year="2026"):
    """Kilta's <dl class='info'> shape, with the rating in an alt attribute."""
    syn = syn or ("Erikoissairaanhoitaja Inka kohtaa vastasyntyneen vanhemmat keskellä "
                  "hoitoalan kriisiä, ja kahden naisen tiet risteytyvät sairaalassa "
                  "tavalla jota kumpikaan ei osannut odottaa etukäteen lainkaan.")
    rows = [("Valmistumisvuosi", year), ("Maat", "Suomi, Liettua")]
    if director:
        rows.append(("Ohjaaja", director))
    if genre:
        rows.append(("Lajityyppi", genre))
    rows += [("Kieli", lang), ("Tekstitys", subs), ("Kesto", dur)]
    info = "".join(f"<div class='info-wrapper'><dt>{k}</dt><dd>{v}</dd></div>"
                   for k, v in rows)
    # The file name disagrees with the alt on purpose: the site serves age-7.svg beside a
    # K-12 alt, so a parser reading the file name publishes the wrong limit.
    badge = (f"<ul class='badges'><li><img data-src='/assets/images/age-7.svg' "
             f"alt='Ikäraja: {rating}' /></li></ul>" if rating else "")
    return (f"<html><head><meta property='og:image' "
            f"content='https://media.kinola.ee/storage/kilta.kinola.ee/1086/poster.jpg'>"
            f"</head><body><main><h1>Elokuva</h1>{badge}"
            f"<dl class='info'>{info}</dl><p>{syn}</p></main></body></html>")


def laika_film(director="Klaus Härö", lang="suomi", subs="", head="87 min <br><br> K-7",
               syn=None):
    """Laika's loose `<strong>Label</strong> <br> value` shape, with the runtime and the
    classification as bare text above the first paragraph."""
    syn = syn or ("Klaus Härön uutuuselokuva kertoo kahden naisen kohtaamisesta keskellä "
                  "hoitoalan kriisiä ja siitä mitä siitä seuraa heille molemmille.")
    parts = [f"<strong>Hetki ennen valoa</strong> <br> Suomi, Liettua <br> {head} <br><br>"]
    if director:
        parts.append(f"<strong>Ohjaus</strong> <br> {director} <br><br>")
    if lang:
        parts.append(f"<strong>Kieli</strong> <br> {lang} <br><br>")
    if subs:
        parts.append(f"<strong>Tekstitys</strong> <br> {subs} <br><br>")
    return ("<html><body><div class='film'>" + "".join(parts) +
            f"<p>{syn}</p></div></body></html>")


SYN_EN_TEXT = ("A grieving boy seeks God to meet his departed mother, and in finding the "
               "divine, learns to serve humanity with miracles of love and food.")
SYN_FI_TEXT = ("Pedro Almodóvarin melodraama kertoo elokuvantekijästä, joka ammentaa "
               "läheistensä tragedioista, ja siitä mitä hänen ystävilleen tapahtuu.")
# Long enough to be read as a synopsis, and carrying no function word of any of the three
# languages, so `syn_language` refuses it.
SYN_NO_LANGUAGE = ("Hanuman Ansh 2026. Mumbai, Chennai, Kolkata, Delhi, Pune, Jaipur, "
                   "Lucknow, Kanpur, Nagpur, Indore, Bhopal, Patna, Surat, Kochi.")


def myyri_film(director="Vishal Chaturvedi", lang="hindi", subs="englanti",
               rating="K-7", kesto="2 h 30 min", syn=None):
    """Myyri's page: a synopsis paragraph, `<strong>Label</strong><br>value` pairs, and
    the rating and runtime in their own block. `Kesto` prints hours and minutes."""
    syn = SYN_EN_TEXT if syn is None else syn
    parts = ["<strong> Hanuman Ansh </strong><br><em> Hanuman Ansh </em><br> Intia <br>"]
    if director:
        parts.append(f"<strong> Ohjaus </strong><br> {director} <br><br>")
    if lang:
        parts.append(f"<strong> Kieli </strong><br> {lang} <br><br>")
    if subs:
        parts.append(f"<strong> Tekstitys </strong><br> {subs} <br><br>")
    top = (f'<div class="myyri-film-top-meta"><strong>Ikäraja</strong><br> {rating} <br>'
           f'<br><strong>Kesto</strong><br> {kesto} <br></div>' if rating or kesto else "")
    body = f'<p>{syn}</p><br><hr><br>' + "".join(parts) if syn else "".join(parts)
    return ('<html><body><section class="kinola-film-meta">' + body
            + "</section>" + top + "</body></html>")


LIVE_ACT = laika_film(director="", lang="", head="130 min <br><br> K-18",
                      syn=("Arppa - Akustisesti saleissa. Arppa lähtee syksyllä "
                           "konserttisalikiertueelle ennen keväälle ajoittuvaa "
                           "keikkataukoaan, ja lavalla kuullaan tuotantoa kaikilta "
                           "levyiltä."))
SPARSE_FILM = laika_film(director="", lang="", head="76 min <br><br> K-16",
                         syn=("Esitettävänä elokuvana on Mehrdad Oskouen "
                              "dokumenttielokuva A Fox Under A Pink Moon, joka kertoo "
                              "nuoresta afganistanilaisesta kuvanveistäjästä."))
CONCERT_FILM = kilta_film(director="Various", genre="Dokumentti, Musiikki",
                          syn=("Oasis palaa valkokankaalle: konserttielokuva bändin "
                               "vuoden 1996 Knebworth-keikoista ja siitä mitä niiden "
                               "ympärillä tapahtui kaikkien näiden vuosien jälkeen."))
# Conflicting metadata: a page that fills the runtime field and nothing else. A runtime
# is not film evidence, and the labelled shape is the only place a classifier could
# mistake it for some, since Laika writes its runtimes as bare text.
LABELLED_RUNTIME_ONLY = kilta_film(director="", genre="", lang="", subs="",
                                   dur="130 min", rating="K-18",
                                   syn=("Arppa yhtyeineen nousee lavalle akustisella "
                                        "kokoonpanolla, ja illan aikana kuullaan "
                                        "tuotantoa kaikilta levyiltä."))
# A Laika page whose header states no classification, with a decoy inside the synopsis.
RATING_ONLY_IN_THE_SYNOPSIS = laika_film(
    head="87 min", syn=("Elokuva esitettiin aikoinaan K-12 ikärajalla ja se on sittemmin "
                        "luokiteltu uudelleen, mistä kertoo tämä pitkä kuvausteksti."))
# A billed live act whose page fills the generic fields. Nothing at run time can tell it
# from a film, which is the whole reason the policy gives an exclusion precedence over
# generic metadata rather than asking the classifier to be cleverer.
LIVE_ACT_WITH_METADATA = kilta_film(
    director="Arppa", genre="Konsertti", lang="suomi", subs="", dur="130 min",
    rating="K-18",
    syn=("Arppa - Akustisesti saleissa. Arppa lähtee syksyllä konserttisalikiertueelle "
         "ennen keväälle ajoittuvaa keikkataukoaan, ja lavalla kuullaan tuotantoa "
         "kaikilta levyiltä yhtyeen kanssa."))
SYNOPSIS_MENTIONS_CONCERT = kilta_film(
    director="Klaus Härö", genre="Draama",
    syn=("Elokuvan käännekohta on konsertti jossa päähenkilöt kohtaavat, ja siitä "
         "kasvaa tarina kahdesta ihmisestä joiden tiet eivät enää eroa toisistaan."))


# ---------------------------------------------------------------- the templates

class BlocksTest(unittest.TestCase):
    def test_the_class_token_is_not_matched_as_a_prefix(self):
        """Every block contains `kinola-event-title`, `-date`, `-venue` and
        `-tickets-link`, and the container around them is `kinola-events`. A substring
        match would cut each block at its own children and count the container too."""
        page = listing(laika_row("a", "A"), laika_row("b", "B"))
        self.assertEqual(len(K.blocks(page)), 2)
        page = listing(kilta_row("a", "A"), kilta_row("b", "B"))
        self.assertEqual(len(K.blocks(page)), 2)

    def test_a_block_carrying_more_classes_is_still_a_screening(self):
        """A CSS class is a token among others. Matched as the whole attribute, this row
        is invisible: not parsed, not published, not counted as an omission, and with
        every row like it the site reads as a cinema with nothing on."""
        for row in (laika_row, kilta_row):
            with self.subTest(template=row.__name__):
                page = listing(row("a", "A"), with_classes(row("b", "B"), "featured"))
                self.assertEqual(len(K.blocks(page)), 2)

    def test_a_longer_class_name_starting_with_the_token_is_not_a_block(self):
        """`kinola-events` is the container and `kinola-eventti` is not this platform's
        at all. Widening the match to a prefix is the other way to get this wrong."""
        page = listing() + '<div class="kinola-eventti">x</div>'
        self.assertEqual(K.blocks(page), [])

    def test_a_listing_with_no_event_block_yields_none(self):
        self.assertEqual(K.blocks(listing()), [])
        self.assertEqual(K.blocks(empty_listing()), [])


class KiltaListingTest(unittest.TestCase):
    def setUp(self):
        self.rows = K.events_kilta(listing(
            kilta_row("teenage-sex", "Teenage Sex and Death at Camp Miasma",
                      subtitle="Anniskelunäytös K18", dur="106 min"),
            kilta_row("hetki", "Hetki ennen valoa", date="KE 16.9.2026", time="12:30",
                      subtitle="Kahvikino - Leffa&Lounas", dur="87 min")), KILTA)

    def test_both_rows_are_read(self):
        self.assertEqual([r["slug"] for r in self.rows], ["teenage-sex", "hetki"])

    def test_the_date_carries_its_own_year_so_nothing_is_inferred(self):
        self.assertEqual(self.rows[0]["start"], "2026-09-15T20:00:00+03:00")
        self.assertEqual(self.rows[1]["start"], "2026-09-16T12:30:00+03:00")

    def test_a_winter_date_takes_the_winter_offset(self):
        rows = K.events_kilta(listing(kilta_row("x", "X", date="TI 1.12.2026",
                                                time="18:30")), KILTA)
        self.assertEqual(rows[0]["start"], "2026-12-01T18:30:00+02:00")

    def test_the_movie_subtitle_is_the_strand_and_goes_to_method(self):
        self.assertEqual(self.rows[0]["method"], "Anniskelunäytös K18")
        self.assertEqual(self.rows[1]["method"], "Kahvikino - Leffa&Lounas")

    def test_the_duration_comes_from_the_row(self):
        self.assertEqual([r["len"] for r in self.rows], ["106", "87"])

    def test_the_destination_is_the_checkout_anchor_the_row_emits(self):
        self.assertTrue(self.rows[0]["url"].startswith(
            "https://www.kinokilta.fi/checkout/"), self.rows[0]["url"])
        self.assertFalse(self.rows[0]["soldOut"])

    def test_a_row_with_an_impossible_date_fails_the_site_rather_than_being_skipped(self):
        """It used to be skipped, and `b` published alone: a schedule one screening short,
        with nothing in the log and nothing in the omission report to say so. The rest is
        in ListingIntegrityTest."""
        with self.assertRaises(K.ListingRowError):
            K.events_kilta(listing(kilta_row("a", "A", date="TI 31.2.2026"),
                                   kilta_row("b", "B")), KILTA)


class LaikaListingTest(unittest.TestCase):
    def setUp(self):
        self.rows = K.events_laika(listing(
            laika_row("hetki", "Hetki ennen valoa"),
            laika_row("arppa", "Arppa", date="30/10/2026 19:00", sold=True)), LAIKA)

    def test_both_rows_are_read_and_the_date_format_differs_from_kilta(self):
        self.assertEqual([r["slug"] for r in self.rows], ["hetki", "arppa"])
        self.assertEqual(self.rows[0]["start"], "2026-09-16T14:00:00+03:00")
        self.assertEqual(self.rows[1]["start"], "2026-10-30T19:00:00+02:00")

    def test_a_sold_out_row_has_no_anchor_and_falls_back_to_the_film_page(self):
        r = self.rows[1]
        self.assertTrue(r["soldOut"])
        self.assertEqual(r["url"], "https://www.kinolaika.fi/film/arppa/")
        self.assertNotIn("/checkout/", r["url"])

    def test_a_sold_out_marker_on_the_anchor_also_refuses_that_href(self):
        """Defensive: the sold-out class sits on a span on both sites today, so nothing
        live reaches this branch. If the markup ever moves it onto the anchor, the href
        beside it is a dead checkout and must not be published."""
        rows = K.events_kilta(listing(kilta_row_sold_out_anchor("x", "X")), KILTA)
        self.assertIs(rows[0]["soldOut"], True)
        self.assertEqual(rows[0]["url"], "https://www.kinokilta.fi/film/x/")
        self.assertNotIn("/checkout/", rows[0]["url"])

    def test_a_row_on_sale_keeps_its_checkout_link(self):
        self.assertIn("/checkout/", self.rows[0]["url"])
        self.assertFalse(self.rows[0]["soldOut"])

    def test_the_poster_comes_from_the_listing_row(self):
        self.assertTrue(self.rows[0]["img"].startswith("https://media.kinola.ee/"))

    def test_a_row_with_no_poster_publishes_no_image_from_the_listing(self):
        rows = K.events_laika(listing(laika_row("a", "A", poster=False)), LAIKA)
        self.assertEqual(rows[0]["img"], "")


# ---------------------------------------------------------------- listing integrity

class MyyriListingTest(unittest.TestCase):
    """The row prints no year, so the weekday selects it; the listing's checkout href is
    the link, the film page when there is none."""

    TODAY = datetime.date(2026, 9, 18)          # a Friday

    def rows(self, *rows, today=None):
        return K.events_myyri(listing(*rows), MYYRI, today or self.TODAY)

    def test_the_weekday_selects_the_year(self):
        rows = self.rows(
            myyri_row("hanuman", "Hanuman Ansh", datetime.date(2026, 9, 18)),
            myyri_row("father", "Father Mother Sister Brother", datetime.date(2026, 9, 19),
                      time="12:00"))
        self.assertEqual([r["start"] for r in rows],
                         ["2026-09-18T19:30:00+03:00", "2026-09-19T12:00:00+03:00"])

    def test_a_january_row_read_in_december_lands_next_year(self):
        [row] = self.rows(myyri_row("a", "A", None, date="pe 8.1. klo 18:00"),
                          today=datetime.date(2026, 12, 20))
        self.assertEqual(row["start"], "2027-01-08T18:00:00+02:00")

    def test_a_weekday_no_candidate_year_carries_fails_the_site(self):
        """`ma 18.9.` is a Monday on none of the three candidate years."""
        with self.assertRaises(K.ListingRowError) as e:
            self.rows(myyri_row("a", "A", None, date="ma 18.9. klo 19:30"))
        self.assertIn("year the weekday and date agree on", str(e.exception))

    def test_a_date_outside_the_window_fails_the_site(self):
        with self.assertRaises(K.ListingRowError):
            self.rows(myyri_row("a", "A", None, date="ti 1.6. klo 19:30"))

    def test_a_row_on_sale_links_to_the_checkout_href_the_listing_prints(self):
        """Decided 2026-09-26: the listing's own href, copied; nothing is built."""
        rows = self.rows(myyri_row("hanuman", "Hanuman Ansh", self.TODAY, checkout="u-1"),
                         myyri_row("father", "F", self.TODAY, time="12:00", checkout="u-2"))
        self.assertEqual([r["url"] for r in rows],
                         ["https://kinomyyri.fi/checkout/u-1",
                          "https://kinomyyri.fi/checkout/u-2"])
        self.assertEqual([r["soldOut"] for r in rows], [False, False])

    def test_a_relative_href_is_resolved_against_the_site_as_printed(self):
        [row] = self.rows(myyri_row("a", "A", self.TODAY,
                                    href="/checkout/u-3?lang=fi&amp;x=1#tickets"))
        self.assertEqual(row["url"], "https://kinomyyri.fi/checkout/u-3?lang=fi&x=1#tickets")

    def test_a_sold_out_marker_beside_a_live_anchor_still_opens_the_film_page(self):
        """Not seen on the site; the marker anywhere in the block decides, so a checkout
        left beside it is not published."""
        row = myyri_row("father", "F", self.TODAY).replace(
            "</div></div>", '<span class="kinola-event-tickets-link-sold-out">'
                            'Loppuunmyyty</span></div></div>')
        [r] = self.rows(row)
        self.assertEqual((r["url"], r["soldOut"]), ("https://kinomyyri.fi/film/father/", True))

    def test_a_sold_out_row_or_one_with_no_anchor_opens_the_film_page(self):
        rows = self.rows(myyri_row("father", "F", self.TODAY, time="12:00", sold=True),
                         myyri_row("hanuman", "H", self.TODAY, no_ticket=True))
        self.assertEqual([r["url"] for r in rows],
                         ["https://kinomyyri.fi/film/father/",
                          "https://kinomyyri.fi/film/hanuman/"])
        self.assertEqual([r["soldOut"] for r in rows], [True, False])

    def test_the_poster_comes_off_the_row(self):
        [a, b] = self.rows(myyri_row("hanuman", "A", self.TODAY),
                           myyri_row("father", "B", self.TODAY, time="12:00", poster=False))
        self.assertTrue(a["img"].startswith("https://media.kinola.ee/storage/myyri"))
        self.assertEqual(b["img"], "")

    def test_a_row_with_no_readable_date_fails_the_site(self):
        with self.assertRaises(K.ListingRowError):
            self.rows(myyri_row("a", "A", None, date="pian"))


class MinutesTest(unittest.TestCase):
    def test_hours_and_minutes_and_the_bare_form(self):
        for text, want in (("2 h 30 min", "150"), ("1 h 27 min", "87"),
                           ("106 min", "106"), ("Kesto 1 h 0 min", "60"),
                           ("", ""), ("ei tiedossa", "")):
            with self.subTest(text=text):
                self.assertEqual(K._minutes(text), want)


class SynValueTest(unittest.TestCase):
    def test_a_site_that_does_not_declare_keeps_the_bare_string(self):
        self.assertEqual(K.syn_value(LAIKA, SYN_FI_TEXT), SYN_FI_TEXT)

    def test_a_declaring_site_keys_the_text_by_language(self):
        self.assertEqual(K.syn_value(MYYRI, SYN_EN_TEXT), {"en": SYN_EN_TEXT})
        self.assertEqual(K.syn_value(MYYRI, SYN_FI_TEXT), {"fi": SYN_FI_TEXT})

    def test_an_unplaceable_text_is_withheld(self):
        self.assertEqual(K.syn_value(MYYRI, "Hanuman Ansh"), "")


class ListingRowFailureTest(unittest.TestCase):
    """A block the listing marks as a screening yields a row or fails the site.

    Skipping it was silent twice over: the screening left the schedule, and the omission
    report could not name it either, because that report counts what the *classification*
    policy withheld and a row that never parsed was never classified. Parsing failures and
    policy omissions are different claims.
    """

    def kilta(self, *rows):
        return K.events_kilta(listing(*rows), KILTA)

    def laika(self, *rows):
        return K.events_laika(listing(*rows), LAIKA)

    def test_a_block_with_no_title_link_fails(self):
        for reader, row in ((self.kilta, kilta_row), (self.laika, laika_row)):
            with self.subTest(reader=reader.__name__):
                broken = re.sub(r'class="kinola-event-title"', 'class="x"',
                                row("a", "A"))
                with self.assertRaises(K.ListingRowError):
                    reader(broken, row("b", "B"))

    def test_a_block_whose_title_link_is_not_a_film_page_fails(self):
        """The film page carries the classification. A row with no page to read cannot be
        classified at all, so reporting it as `unresolved` would dress a parse failure up
        as a policy omission."""
        for reader, row in ((self.kilta, kilta_row), (self.laika, laika_row)):
            with self.subTest(reader=reader.__name__):
                broken = row("a", "A").replace("/film/a/", "/tapahtuma/a/")
                self.assertNotIn("/film/a/", broken)
                with self.assertRaises(K.ListingRowError):
                    reader(broken, row("b", "B"))

    def test_a_block_with_no_readable_date_fails(self):
        with self.assertRaises(K.ListingRowError):
            self.kilta(kilta_row("a", "A", date="lähiaikoina"), kilta_row("b", "B"))
        with self.assertRaises(K.ListingRowError):
            self.laika(laika_row("a", "A", date="lähiaikoina"), laika_row("b", "B"))

    def test_a_kilta_block_with_no_readable_time_fails(self):
        """Kilta alone splits the two: its date and time are separate elements."""
        with self.assertRaises(K.ListingRowError):
            self.kilta(kilta_row("a", "A", time="illalla"), kilta_row("b", "B"))

    def test_an_impossible_calendar_date_fails_on_both_templates(self):
        with self.assertRaises(K.ListingRowError):
            self.kilta(kilta_row("a", "A", date="TI 31.2.2026"), kilta_row("b", "B"))
        with self.assertRaises(K.ListingRowError):
            self.laika(laika_row("a", "A", date="31/02/2026 14:00"),
                       laika_row("b", "B"))

    def test_one_bad_row_among_good_ones_fails_rather_than_publishing_the_rest(self):
        """The partial-publication case: two readable rows either side of a malformed
        one. Skipping produced a schedule that looked complete."""
        with self.assertRaises(K.ListingRowError):
            self.laika(laika_row("a", "A"),
                       laika_row("b", "B", date="31/02/2026 14:00"),
                       laika_row("c", "C", date="18/09/2026 20:00"))

    def test_the_message_places_the_row_and_names_the_field_without_the_markup(self):
        """The log is committed to a public repo, so it may quote the short field it read
        and never the third party's block. See CLAUDE.md on raw dumps."""
        with self.assertRaises(K.ListingRowError) as caught:
            self.kilta(kilta_row("a", "A"), kilta_row("b", "Beta", date="TI 31.2.2026"))
        msg = str(caught.exception)
        self.assertIn("block 2", msg)
        self.assertIn("kinokilta", msg)
        self.assertIn("Beta", msg)
        self.assertNotIn("<", msg)
        self.assertNotIn("kinola-event", msg)

    def test_it_is_a_runtime_error_so_the_runner_treats_it_as_a_parse_failure(self):
        self.assertTrue(issubclass(K.ListingRowError, RuntimeError))
        self.assertFalse(issubclass(K.ListingRowError, common.EmptyProgramme))


class EmptyProgrammeEvidenceTest(unittest.TestCase):
    """Zero parsed rows is never the evidence: `common.EmptyProgramme` says why, and every
    condition here is something the row parser does not read.

    Measured as a visitor 2026-09-15: kinokilta.fi 57 blocks and kinolaika.fi 47, both
    inside a `kinola-events` container and neither carrying the empty text; kinokonepaja.fi
    zero blocks, no container at all, and "Ei tulevia tapahtumia." after the filter widget.
    """

    def test_the_measured_empty_page_is_evidence(self):
        self.assertEqual(K.empty_programme_evidence(empty_listing()), "")

    def test_an_unrelated_page_is_not(self):
        why = K.empty_programme_evidence(UNRELATED_HTML)
        self.assertIn("not on the page", why)

    def test_a_rendered_container_holding_no_readable_row_is_not(self):
        """The parser-break shape: the widget and its container are both there, so the
        listing rendered and this parser could not read what is in it."""
        why = K.empty_programme_evidence(listing())
        self.assertIn("markup change", why)

    def test_the_empty_text_above_the_widget_is_not(self):
        """Scoped to the page after the filter widget, so a cinema writing the same words
        in its own page copy cannot silence a parse that broke underneath it. The same
        trap `test_empty_programme.py` records for eTiketti's phrase."""
        page = ("<html><body><p>Ei tulevia tapahtumia.</p>" + FILTERS
                + "</body></html>")
        self.assertIn("neither an event list nor its empty state",
                      K.empty_programme_evidence(page))

    def test_a_populated_listing_is_not_evidence_either(self):
        page = listing(laika_row("a", "A"), laika_row("b", "B"))
        self.assertNotEqual(K.empty_programme_evidence(page), "")


# ---------------------------------------------------------------- the classifier

class LabelsTest(unittest.TestCase):
    def test_kiltas_dt_dd_pairs_are_read(self):
        f = K.labels(kilta_film())
        self.assertEqual(f["ohjaaja"], "Klaus Härö")
        self.assertEqual(f["lajityyppi"], "Draama")
        self.assertEqual(f["kesto"], "87 min")

    def test_laikas_strong_pairs_are_read_by_the_same_reader(self):
        """The classifier must not have to know which site it is reading."""
        f = K.labels(laika_film())
        self.assertEqual(f["ohjaus"], "Klaus Härö")
        self.assertEqual(f["kieli"], "suomi")

    def test_a_page_with_no_labels_reads_empty(self):
        self.assertEqual(K.labels("<html><body><p>Arppa</p></body></html>"), {})


class ClassifyTest(unittest.TestCase):
    def one(self, page):
        """-> (publish, state), dropping the default the caller does not need here."""
        publish, state, _ = K.classify("kinolaika", "s", K.film_facts(page), {})
        return publish, state

    def test_a_labelled_director_is_film_evidence(self):
        self.assertEqual(self.one(laika_film(director="Klaus Härö")), (True, K.FILM))

    def test_a_labelled_genre_is_film_evidence(self):
        self.assertEqual(self.one(kilta_film(director="", genre="Draama")),
                         (True, K.FILM))

    def test_a_runtime_and_a_classification_are_not_film_evidence(self):
        """The trap the policy was corrected for. Arppa is 130 min and K-18 with no
        director: counted as evidence, every gig in Karkkila would publish."""
        facts = K.film_facts(LIVE_ACT)
        self.assertEqual(facts["len"], "130")
        self.assertEqual(facts["rating"], "K-18")
        self.assertEqual(K.classify("kinolaika", "arppa", facts, {})[:2],
                         (False, K.UNRESOLVED))

    def test_a_film_whose_page_fills_no_field_is_unresolved_not_a_non_film(self):
        self.assertEqual(self.one(SPARSE_FILM), (False, K.UNRESOLVED))

    def test_a_labelled_runtime_on_its_own_is_still_not_film_evidence(self):
        """Conflicting metadata, and the shape a classifier could most easily get wrong:
        the runtime in a real `<dt>Kesto</dt>` field with no director and no genre beside
        it. Laika writes its runtimes as bare text, so only this fixture reaches the
        case."""
        facts = K.film_facts(LABELLED_RUNTIME_ONLY)
        self.assertEqual(facts["labels"].get("kesto"), "130 min")
        self.assertEqual(facts["rating"], "K-18")
        self.assertEqual(K.classify("kinokilta", "x", facts, {})[:2],
                         (False, K.UNRESOLVED))

    def test_a_concert_film_publishes(self):
        self.assertEqual(self.one(CONCERT_FILM), (True, K.FILM))

    def test_a_synopsis_mentioning_a_concert_does_not_withhold_the_film(self):
        self.assertEqual(self.one(SYNOPSIS_MENTIONS_CONCERT), (True, K.FILM))

    def test_a_billed_live_act_that_fills_the_generic_fields_publishes_by_default(self):
        """The standing limitation, kept executable rather than only written down.

        Nothing at run time separates this page from a film: it names a director and a
        genre like any other. So a live act of this shape with **no** recorded exclusion
        publishes, and the next test shows an exclusion is what withholds it. Precedence
        is not detection, and the pair of tests proves the first and not the second. The
        only alternative would be reading a word out of a title or a synopsis, which the
        policy forbids and which would misfile every concert film.
        """
        facts = K.film_facts(LIVE_ACT_WITH_METADATA)
        self.assertEqual(facts["labels"].get("ohjaaja"), "Arppa")
        self.assertEqual(facts["genres"], "Konsertti")
        self.assertEqual(K.default_state(facts), K.FILM)
        self.assertEqual(self.one(LIVE_ACT_WITH_METADATA), (True, K.FILM))

    def test_an_exclusion_beats_the_generic_metadata_on_that_same_page(self):
        """The adopted precedence: explicit event-level evidence of a live act prevents
        automatic inclusion even where generic metadata is present."""
        o = {("kinolaika", "arppa"): {"action": "exclude"}}
        publish, state, default = K.classify("kinolaika", "arppa",
                                             K.film_facts(LIVE_ACT_WITH_METADATA), o)
        self.assertFalse(publish)
        self.assertEqual(state, K.NON_FILM)
        self.assertEqual(default, K.FILM, "the classifier would have published it")

    def test_a_concert_film_is_not_touched_by_that_precedence(self):
        """The exclusion is scoped to one page. A concert film keeps publishing, and so
        does a film whose synopsis mentions a concert, because neither is named."""
        o = {("kinolaika", "arppa"): {"action": "exclude"}}
        for slug, page in (("oasis", CONCERT_FILM),
                           ("hetki", SYNOPSIS_MENTIONS_CONCERT)):
            with self.subTest(slug=slug):
                publish, state, _ = K.classify("kinolaika", slug, K.film_facts(page), o)
                self.assertTrue(publish)
                self.assertEqual(state, K.FILM)

    def test_the_classifier_never_returns_non_film_on_its_own(self):
        """`non-film` is an assertion a person makes on evidence. Nothing on these pages
        lets the runtime make it, and a word in a title or synopsis must not."""
        for page in (LIVE_ACT, LIVE_ACT_WITH_METADATA, SPARSE_FILM, CONCERT_FILM,
                     LABELLED_RUNTIME_ONLY, SYNOPSIS_MENTIONS_CONCERT):
            self.assertIn(K.default_state(K.film_facts(page)),
                          (K.FILM, K.UNRESOLVED))
            self.assertNotEqual(K.default_state(K.film_facts(page)), K.NON_FILM)

    def test_the_word_konsertti_in_a_live_acts_page_is_not_what_withholds_it(self):
        """Proof that no keyword is doing the work: strip every mention and the verdict
        is unchanged, because the absence of a labelled field is the whole rule."""
        page = LIVE_ACT.replace("konserttisalikiertueelle", "kiertueelle")
        self.assertEqual(self.one(page), (False, K.UNRESOLVED))


class FilmFactsTest(unittest.TestCase):
    def test_kiltas_og_image_is_a_still_and_is_not_published(self):
        """All 40 Kilta films read 2026-10-04 carried a landscape still there. Myyri's and
        Sheryl's are portrait posters and stay."""
        self.assertIn("og:image", kilta_film())
        self.assertEqual(K.film_facts(kilta_film(), "kilta")["img"], "")
        og = "<head><meta property='og:image' content='https://media.kinola.ee/p.jpg'></head>"
        page = myyri_film().replace("<html>", "<html>" + og)
        self.assertEqual(K.film_facts(page, "myyri")["img"], "https://media.kinola.ee/p.jpg")

    def test_kiltas_rating_comes_from_the_alt_and_not_the_file_name(self):
        """The site serves age-7.svg beside a K-12 alt."""
        page = kilta_film(rating="K-12")
        self.assertIn("age-7.svg", page)
        self.assertEqual(K.film_facts(page)["rating"], "K-12")

    def test_sallittu_kaikille_is_s(self):
        self.assertEqual(K.film_facts(kilta_film(rating="sallittu kaikille"))["rating"],
                         "S")

    def test_a_page_with_no_classification_publishes_no_rating(self):
        """Blank is filled by the shared classification pass from another chain."""
        self.assertEqual(K.film_facts(kilta_film(rating=""))["rating"], "")

    def test_laikas_rating_is_read_from_the_header_and_not_from_the_synopsis(self):
        """A K-12 inside a blurb is not this film's own limit. The header states no
        classification at all here, so an unbounded search would publish the decoy: a
        fixture whose header also carries a rating proves nothing, because the header's
        value comes first either way."""
        f = K.film_facts(RATING_ONLY_IN_THE_SYNOPSIS)
        self.assertIn("K-12", RATING_ONLY_IN_THE_SYNOPSIS)
        self.assertEqual(f["rating"], "")
        self.assertEqual(f["len"], "87")

    def test_the_header_region_stops_at_the_first_paragraph(self):
        self.assertNotIn("K-12", K._head(RATING_ONLY_IN_THE_SYNOPSIS))
        self.assertIn("87 min", K._head(RATING_ONLY_IN_THE_SYNOPSIS))

    def test_a_header_rating_is_still_read_when_there_is_one(self):
        self.assertEqual(K.film_facts(laika_film(head="87 min <br><br> K-7"))["rating"],
                         "K-7")

    def test_the_language_tags_come_from_the_finnish_names(self):
        f = K.film_facts(kilta_film(lang="suomi", subs="englanti"))
        self.assertEqual(f["lang"], "FI-A, EN-S")

    def test_two_subtitle_languages_split_on_the_conjunction(self):
        f = K.film_facts(kilta_film(lang="englanti", subs="suomi ja ruotsi"))
        self.assertEqual(f["lang"], "EN-A, FI-S, SV-S")

    def test_the_tables_are_shared_with_the_other_reader_of_this_vocabulary(self):
        import gilda
        self.assertIs(K.LANG, gilda.LANG)

    def test_the_genre_is_published_and_the_synopsis_is_the_long_paragraph(self):
        f = K.film_facts(kilta_film(genre="Draama"))
        self.assertEqual(f["genres"], "Draama")
        self.assertGreater(len(f["syn"]), 120)


class LanguageNamesTest(unittest.TestCase):
    """Every language name the four tenants' film pages used, read 2026-10-03 over all
    their listed films. Until then `_lang` knew Gilda's Finnish names alone and dropped the
    rest one by one, so "suomi, persia" published as Finnish only and Sheryl's English
    labels published nothing."""

    MEASURED = {
        "suomi, persia": "FI-A, FA-A", "tanska": "DA-A",
        "englanti, ranska, hollanti, saksa": "EN-A, FR-A, NL-A, DE-A",
        "ruotsi, turkki, persia": "SV-A, TR-A, FA-A", "Farsi": "FA-A",
        "mandariinikiina, Taiwan": "ZH-A", "heprea, englanti, ranska, saksa":
        "HE-A, EN-A, FR-A, DE-A", "hindi": "HI-A", "English": "EN-A",
        "Dari, Pa\u0161tu, englanti": "FA-A, PS-A, EN-A", "Dubattu englanniksi": "EN-A",
        "japani, korea": "JA-A, KO-A", "islanti": "IS-A", "kreikka": "EL-A",
        "kiillottaa": "PL-A", "englanti, heprea": "EN-A, HE-A",
        "englanti, norja, romanialainen": "EN-A, NO-A, RO-A",
        "englanti, hindi, nepalilainen": "EN-A, HI-A, NE-A", "tamili": "TA-A",
        "italialainen": "IT-A", "englanti, liettualainen": "EN-A, LT-A",
        "Cantonese, Spanish, English, Mandarin": "ZH-A, ES-A, EN-A",
        "Polish, German, Yiddish, Russian": "PL-A, DE-A, YI-A, RU-A", "Spanish": "ES-A"}

    @staticmethod
    def sheryl_langs(language, subtitles):
        """Sheryl's labels as served on sheryl.fi/film/verityn-varjo/, 2026-10-03."""
        return ("<html><body><section class='kinola-film-meta'>"
                " <strong>Director</strong> <br> Michael Showalter <br><br>"
                f" <strong>Language</strong> <br> {language} <br><br>"
                f" <strong>Subtitles</strong> <br> {subtitles} <br><br>"
                "</section></body></html>")

    def test_every_measured_value_reads_whole(self):
        for value, want in self.MEASURED.items():
            with self.subTest(value=value):
                self.assertEqual(K._lang({"kieli": value}), (want, []))

    def test_sheryl_s_english_labels(self):
        for language, subtitles, want in (
                ("English", "Finnish, Swedish", "EN-A, FI-S, SV-S"),
                ("Cantonese, Mandarin", "English", "ZH-A, EN-S")):
            with self.subTest(language=language):
                f = K.film_facts(self.sheryl_langs(language, subtitles), "sheryl")
                self.assertEqual((f["lang"], f["lang_unread"]), (want, []))

    def test_a_role_with_an_unknown_name_publishes_nothing_for_that_role(self):
        f = K.film_facts(kilta_film(lang="suomi, klingon", subs="englanti"))
        self.assertEqual((f["lang"], f["lang_unread"]), ("EN-S", ["klingon"]))
        f = K.film_facts(kilta_film(lang="suomi", subs="Ei teksityst\u00e4"))
        self.assertEqual((f["lang"], f["lang_unread"]), ("FI-A", ["Ei teksityst\u00e4"]))

    def test_the_run_names_the_films_whose_language_was_not_read(self):
        page = listing(laika_row("hetki", "Hetki ennen valoa"),
                       laika_row("fox", "A Fox Under a Pink Moon", date="24/09/2026 18:00"))
        pages = {"hetki": laika_film(lang="suomi, klingon"), "fox": laika_film(lang="ruotsi")}
        per, om = K.parse(LAIKA, page, pages, {})
        self.assertEqual(om["lang_unread"], {"Hetki ennen valoa (klingon)"})
        self.assertEqual({s["title"]: s["lang"] for s in per["laika-karkkila"]},
                         {"Hetki ennen valoa": "", "A Fox Under a Pink Moon": "SV-A"})

    def test_every_code_the_names_give_has_a_name_on_the_pages_and_in_the_app(self):
        """The app's table is held identical to this one in test_lang_normalization."""
        import build_pages as bp
        for lang in ("fi", "sv", "en"):
            with self.subTest(lang=lang):
                self.assertEqual(set(K.NAMES.values()) - set(bp.LN[lang]), set())


class SynopsisParagraphTest(unittest.TestCase):
    """The synopsis is the film's own long paragraph, read from `<p>` elements only.

    Read live 2026-09-24. Kilta's film pages open with an SVG logo whose `<path d=...>`
    elements matched `<p[^>]*>`, so the "paragraph" ran from the logo through the site menu
    and both titles to the first `</p>`: 39 films-extra entries carried Kilta's menu as
    their Finnish synopsis, and Sheryl's menu was read the same way. Strand films put the
    strand's notice paragraphs first (KAVI's aluesarja, "Kultti Kilta"), and Laika puts a
    ticket notice first, so the first paragraph over 120 characters is not the synopsis
    either."""

    SYN = ("Elokuvan alkuperaista nimea myotaillen agentti paasee irti ja valloilleen, kun "
           "kansainvalinen juoni vie hanet Brasiliaan etsimaan kadonnutta mikrofilmia, ja "
           "matkan varrella han kohtaa niin natseja, hippeja kuin paikallisen poliisinkin.")
    NOTICE = ("<strong>Syyssarja 2026</strong> starttaa minä muunakaan päivänä kuin "
              "<strong>Kino Killan 2-vuotissyntymäpäivänä</strong> 28.9. ja jatkuu "
              "marraskuun viimeiselle viikolle.")

    def kilta_live(self, syn):
        logo = ("<svg viewBox='0 0 120 120'><path d='M71.5 46.9C64.1 46.9 58.1 52.9 58.1 "
                "60.3'></path><path d='M49.6 73.7H53.2'></path></svg>")
        menu = ("<nav class='main-menu' role='navigation'><ul id='menu-primary-navigation-fi'>"
                + "".join(f"<li><a href='/x/'>{w}</a></li>" for w in
                          ("Etusivu", "Näytökset", "Yhteystiedot ja aukioloajat",
                           "Saapuminen ja saavutettavuus", "Info", "Tilavuokraus",
                           "Lahjakortit", "Sarjaliput", "Erikoistapahtumat",
                           "Tukijat ja kumppanit", "Tietosuojaseloste", "English"))
                + "</ul></nav>")
        return (f"<html><body><header>{logo}{menu}</header><main><article>"
                f"<div class='page-title'><h1>Agentti O.S.S. 117 iskee</h1>"
                f"<em>OSS 117 se déchaîne</em></div>"
                f"<p><strong>KUVIn aluesarja tekee paluun kevään mittaisen tauon jälkeen!</strong></p>"
                f"<p>{self.NOTICE}</p><p>{syn}</p></article></main></body></html>")

    def test_an_svg_path_is_not_a_paragraph(self):
        f = K.film_facts(self.kilta_live(self.SYN))
        self.assertNotIn("Etusivu", f["syn"])
        self.assertNotIn("Tietosuojaseloste", f["syn"])

    def test_a_strand_notice_before_the_synopsis_is_passed_over(self):
        self.assertEqual(K.film_facts(self.kilta_live(self.SYN))["syn"], self.SYN)

    def test_a_ticket_notice_before_the_synopsis_is_passed_over(self):
        notice = ("Kino Iglu! Liput 10€ / 7€ (lapset ja nuoret, opiskelijat, työttömät, "
                  "varusmiehet ja eläkeläiset). Näytös alkaa tasan, ovet aukeavat puoli "
                  "tuntia ennen.")
        page = f"<html><body><main><p>{notice}</p><p>{self.SYN}</p></main></body></html>"
        self.assertGreater(len(notice), 120)
        self.assertEqual(K.film_facts(page)["syn"], self.SYN)

    def test_a_page_with_no_long_paragraph_has_no_synopsis(self):
        page = "<html><body><main><p>Lyhyt teksti.</p><p>Toinen.</p></main></body></html>"
        self.assertEqual(K.film_facts(page)["syn"], "")


def kilta_page(title, original, body):
    """Kilta's film-page shape as read 2026-09-24: the SVG logo (whose `<path>` once read
    as a paragraph), the menu, the title block, the description, then the info block."""
    logo = "<svg viewBox='0 0 9 9'><path d='M71.5 46.9C64.1 46.9 58.1 52.9'></path></svg>"
    menu = ("<nav><ul>" + "".join(f"<li><a href='/x/'>{w}</a></li>"
                                   for w in ("Etusivu", "Näytökset", "Tietosuojaseloste"))
            + "</ul></nav>")
    return (f"<html><body><header>{logo}{menu}</header><main><article>"
            f"<div class='page-title'><h1>{title}</h1><em>{original}</em></div>{body}"
            f"<div class='hide-for-l-up'><div class='movie-info'><dl class='info'>"
            f"<div class='info-wrapper'><dt>Kieli</dt><dd>ruotsi</dd></div></dl></div></div>"
            f"</article></main></body></html>")


class KiltaSynopsisTest(unittest.TestCase):
    """Kilta's description is split into sections, each kept whole and placed by
    `common.syn_language`. Longest-paragraph selection filed the Swedish paragraph of two
    Nordic films as Finnish on 2026-09-24: Kilta writes the Finnish synopsis in two
    paragraphs and the Swedish in one longer one, after a `---` line."""

    FI_A = ("Ane ja Thomas ovat keski-ikäiset kahden kouluikäisen lapsen vanhemmat, jotka "
            "ovat päättäneet erota, mutta eivät ole vielä kertoneet siitä lapsilleen.")
    FI_B = ("Suunnitelmat menevät uusiksi, kun Ane saa yllättäen aivoinfarktin. Thomas jää "
            "hoitamaan häntä, ja vanha arki palaa hetkeksi, vaikka kumpikaan ei tiedä, mitä "
            "he oikeastaan haluavat.")
    FI_C = "Elokuva sai ensi-iltansa Berliinin elokuvajuhlien Panorama-sarjassa."
    SV = ("Ane och Thomas är båda inställda på skilsmässa, och Thomas har redan köpt en "
          "lägenhet tillsammans med sin nya partner. Ändå kommer de sig inte för att berätta "
          "för barnen, och huset ska säljas. Så länge lunkar vardagen på, tills Ane får en "
          "stroke och tillvaron för alla vänds upp och ner.")

    def test_begyndelser_keeps_the_whole_finnish_synopsis_and_files_the_swedish_as_sv(self):
        page = kilta_page("Begyndelser", "Begyndelser",
                          f"<p><strong>Lokakuun Kuukauden pohjoismainen elokuva</strong></p>"
                          f"<p>{self.FI_A}</p><p>{self.FI_B}</p><p>{self.FI_C}</p>"
                          f"<p>---</p><p>{self.SV}</p>")
        self.assertGreater(len(self.SV), len(self.FI_B))
        f = K.film_facts(page, "kilta")
        self.assertEqual(f["syn"], {"fi": f"{self.FI_A} {self.FI_B} {self.FI_C}",
                                    "sv": self.SV})
        self.assertEqual(f["syn_withheld"], 0)

    def test_knyckertz_drops_the_credits_and_files_both_sections(self):
        fi = ("Vorosen perheen hyppysiä syyhyttää, kun kaupungin museoon on tulossa "
              "arvokas näyttely. Samaan aikaan poliisilla on selvittelyn alla kadonnut koira, "
              "ja jäljet johtavat Vorosen perheeseen, joka joutuu valitsemaan.")
        sv = ("Familjen Knyckertz brinner av iver när stadens museum ska få en värdefull "
              "utställning. Samtidigt utreder polisen en försvunnen hund, och spåren leder "
              "till familjen, som måste välja om de ska lämna tillbaka den eller inte.")
        page = kilta_page("Vorosen perhe ja kyttäjahti", "Knyckertz &amp; snutjakten",
                          f"<p><strong>Marraskuun Kuukauden pohjoismainen elokuva</strong></p>"
                          f"<p>{fi}</p><p>Lähde: Espoo Ciné</p><p>---</p><p>{sv}</p>"
                          f"<p>Källa: Walhalla</p>")
        self.assertEqual(K.film_facts(page, "kilta")["syn"], {"fi": fi, "sv": sv})

    def test_a_strand_film_loses_its_notices_and_keeps_its_synopsis(self):
        syn = ("Elokuvan alkuperäistä nimeä myötäillen <strong>O.S.S. 117</strong> pääsee "
               "irti, kun kansainvälinen juoni vie agentin Brasiliaan etsimään kadonnutta "
               "mikrofilmiä, ja matkan varrella hän kohtaa niin natseja kuin hippejäkin.")
        page = kilta_page(
            "Agentti O.S.S. 117 iskee", "OSS 117 se déchaîne",
            "<p><strong>KUVIn aluesarja tekee paluun kevään tauon jälkeen!</strong></p>"
            "<p><strong>Syyssarja 2026</strong> alkaa Kino Killan syntymäpäivänä 28.9. ja "
            "jatkuu marraskuun viimeiselle viikolle.</p>"
            "<p><strong>Maanantaisin klo 19.30 arkiston aarteita, liput 9/5€.</strong></p>"
            "<p><strong>Tutustu aluesarjoihin täältä</strong>: "
            "<a href='https://kavi.fi/aluesarjat/'>https://kavi.fi/aluesarjat/</a></p>"
            f"<p>{syn}</p>")
        self.assertEqual(K.film_facts(page, "kilta")["syn"], {"fi": K._txt(syn)})

    def test_notices_before_asterisks_go_and_a_bold_opening_sentence_stays(self):
        """Kinokopla's pages put the ticket notices before `***`; Kolme väriä opens its
        synopsis with the title in bold, which is the film's own sentence."""
        first = ("<strong><em>Kolme väriä: Sininen</em></strong> on Krzysztof Kieślowskin "
                 "väritrilogian ensimmäinen osa.")
        rest = ("Auto suistuu tieltä, ja kaksi sen kolmesta matkustajasta kuolee. Julie "
                "menettää onnettomuudessa miehensä ja tyttärensä, ja hän yrittää aloittaa "
                "elämänsä alusta ilman muistoja, joita hän ei halua kantaa mukanaan.")
        page = kilta_page("Kolme väriä: Sininen", "Trois couleurs: Bleu",
                          "<h3><strong>Kuukauden klassikko!</strong></h3>"
                          "<p>Yksittäisliput opiskelijoille 7€ ja muille 8 €.</p><p>***</p>"
                          f"<p>{first}</p><p>{rest}</p>"
                          "<p>Liput maksavat 9 € ja opiskelijoille 7 €, ja näytökseen mahtuu "
                          "vain rajallinen määrä katsojia, joten paikat kannattaa varata.</p>")
        f = K.film_facts(page, "kilta")
        self.assertEqual(f["syn"], {"fi": f"{K._txt(first)} {rest}"})
        self.assertEqual(f["syn_withheld"], 0)

    def test_a_section_no_language_settles_is_withheld_and_counted(self):
        page = kilta_page("Nimetön", "Untitled",
                          f"<p>{self.FI_A} {self.FI_B}</p><p>---</p>"
                          f"<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do "
                          f"eiusmod tempor incididunt ut labore et dolore magna aliqua.</p>")
        f = K.film_facts(page, "kilta")
        self.assertEqual(f["syn"], {"fi": f"{self.FI_A} {self.FI_B}"})
        self.assertEqual(f["syn_withheld"], 1)

    def test_kilta_publishes_the_placed_value_unchanged(self):
        """Kilta sets no `declare_syn`, so `syn_value` hands the placed dict on as is."""
        placed = {"fi": self.FI_A, "sv": self.SV}
        self.assertIs(K.syn_value(KILTA, placed), placed)


def sheryl_page(synopsis_html, facts):
    """Sheryl's film-page shape as read 2026-09-24: the meta block with its bold labels,
    the synopsis, then one <hr> and the title block that carries the runtime."""
    return ("<html><body><section class='kinola-film-meta'><img alt='Film poster' src='x'>"
            " Hong Kong <br> <strong>Rating</strong> <br> K-12 <br><br>"
            " <strong>Classifications</strong> <br> <br><br>"
            f"{synopsis_html} <br><hr><br> {facts}"
            " <strong>Director</strong> <br> Wong Kar-Wai <br><br>"
            " <strong>Language</strong> <br> Cantonese <br><br></section></body></html>")


class SherylRuntimeTest(unittest.TestCase):
    """Sheryl publishes the runtime in its title block after the page's <hr>. The text
    before the first <p> reached it only where the synopsis was not in <p> elements, so
    Chungking Express and Happy Together had none and three films had it by accident."""

    def test_a_synopsis_in_paragraphs_still_yields_the_runtime(self):
        page = sheryl_page("<p>Two melancholic policemen stumble into romance.</p>",
                           "<strong>Chungking Express</strong> <br> <em>Chungking Express</em>"
                           " <br> Hong Kong <br> 102 min <br><br>")
        self.assertEqual(K.film_facts(page, "sheryl")["len"], "102")

    def test_a_dated_runtime_is_read_and_a_minute_count_in_the_synopsis_is_not(self):
        """The Resident Evil shape: the synopsis as bare text, and the block's runtime
        after a release date. A "15 min" in the synopsis is the film's story, not its
        length, and it comes first on the page."""
        page = sheryl_page("A courier has 15 min to cross the city before the night"
                           " collapses around him.",
                           "<strong>Resident Evil</strong> <br> <em>Resident Evil</em> <br>"
                           " United States <br> 2026-09-18, 94 min <br><br>")
        self.assertEqual(K.film_facts(page, "sheryl")["len"], "94")

    def test_a_page_without_the_title_block_has_no_runtime(self):
        """No block, no runtime: the "15 min" before the first <p> is what the old scan
        would have published."""
        page = sheryl_page("A courier has 15 min to cross the city. <p>More to come.</p>", "")
        page = page.replace("<hr>", "")
        self.assertEqual(K.film_facts(page, "sheryl")["len"], "")

    def test_minutes_after_the_title_block_are_not_its_runtime(self):
        """A title block with no runtime reads as none, whatever a later block says."""
        page = sheryl_page("<p>A restored print.</p>",
                           "<strong>Short Films</strong> <br> <em>Short Films</em> <br>"
                           " Finland <br><br> <strong>Notes</strong> <br> Intermission 20 min <br><br>")
        self.assertEqual(K.film_facts(page, "sheryl")["len"], "")

    def test_the_other_templates_keep_their_own_rule(self):
        """Laika's bare runtime above the first paragraph is still read as before."""
        self.assertEqual(K.film_facts(laika_film(head="87 min <br><br> K-7"))["len"], "87")


# ---------------------------------------------------------------- overrides

class OverrideTest(unittest.TestCase):
    def facts(self, page):
        return K.film_facts(page)

    def test_an_include_override_publishes_a_film_the_classifier_leaves_unresolved(self):
        o = {("kinolaika", "fox"): {"action": "include"}}
        publish, state, default = K.classify("kinolaika", "fox",
                                             self.facts(SPARSE_FILM), o)
        self.assertEqual((publish, state, default), (True, K.FILM, K.UNRESOLVED))

    def test_an_exclude_override_withholds_an_event_the_classifier_would_publish(self):
        """The direction the proposed guard would have forbidden: an override is needed
        precisely because the default includes wrongly."""
        o = {("kinokilta", "gig"): {"action": "exclude"}}
        publish, state, default = K.classify("kinokilta", "gig",
                                             self.facts(kilta_film()), o)
        self.assertEqual((publish, state, default), (False, K.NON_FILM, K.FILM))

    def test_the_override_is_consulted_before_the_classifier(self):
        """Both directions disagree with the default, so neither verdict can come from
        the classifier having run first."""
        o = {("kinolaika", "a"): {"action": "include"},
             ("kinolaika", "b"): {"action": "exclude"}}
        self.assertTrue(K.classify("kinolaika", "a", self.facts(LIVE_ACT), o)[0])
        self.assertFalse(K.classify("kinolaika", "b", self.facts(kilta_film()), o)[0])

    def test_an_override_is_scoped_to_its_provider(self):
        o = {("kinolaika", "fox"): {"action": "include"}}
        self.assertFalse(K.classify("kinokilta", "fox", self.facts(SPARSE_FILM), o)[0])

    def test_an_unknown_action_is_not_loaded(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"overrides": [
                {"provider": "kinolaika", "slug": "a", "action": "maybe"},
                {"provider": "kinolaika", "slug": "b", "action": "include"}]}, fh)
        self.addCleanup(lambda: pathlib.Path(fh.name).unlink())
        self.assertEqual(sorted(K.load_overrides(fh.name)),
                         [("kinolaika", "b")])

    def test_a_missing_file_is_no_overrides_rather_than_an_error(self):
        self.assertEqual(K.load_overrides("/nonexistent/kinola-overrides.json"), {})


class ShippedOverridesTest(unittest.TestCase):
    """The committed file, held to the shape the policy requires."""

    def setUp(self):
        self.doc = json.loads(K.OVERRIDE_FILE.read_text(encoding="utf-8"))

    def test_every_entry_carries_its_action_reason_evidence_and_verification_date(self):
        for row in self.doc["overrides"]:
            with self.subTest(slug=row.get("slug")):
                for key in ("provider", "slug", "action", "reason", "evidence",
                            "verified"):
                    self.assertTrue(str(row.get(key, "")).strip(), key)
                self.assertIn(row["action"], ("include", "exclude"))
                self.assertRegex(row["verified"], r"^\d{4}-\d{2}-\d{2}$")

    def test_every_entry_names_a_provider_this_module_serves(self):
        served = {s["provider"] for s in K.SITES}
        for row in self.doc["overrides"]:
            self.assertIn(row["provider"], served)

    def test_no_entry_is_a_title_keyword(self):
        """Scoped to the site's own /film/{slug}/ identifier. A keyword would put the
        classification rule the policy forbids back in through the override file."""
        for row in self.doc["overrides"]:
            self.assertRegex(row["slug"], r"^[a-z0-9][a-z0-9-]*$")
            self.assertNotIn(" ", row["slug"])

    def test_the_fox_entry_is_the_recorded_inclusion_candidate(self):
        entry = next(r for r in self.doc["overrides"]
                     if r["slug"] == "a-fox-under-a-pink-moon")
        self.assertEqual((entry["provider"], entry["action"]),
                         ("kinolaika", "include"))
        self.assertIn("dokumenttielokuva", entry["evidence"])

    def test_the_dubbed_print_is_the_second_inclusion(self):
        """Kino Myyri publishes the dub and the original from one listing, and only the
        original fills a labelled field."""
        entry = next(r for r in self.doc["overrides"]
                     if r["slug"] == "kojootti-vs-acme-dub")
        self.assertEqual((entry["provider"], entry["action"]),
                         ("kinomyyri", "include"))
        self.assertIn("kojootti-vs-acme", entry["evidence"])

    def test_whether_an_entry_is_still_needed_is_not_asserted_here(self):
        """Deliberately absent. Whether a shipped override still changes the decision
        depends on the source page as it stands, which only a run can see, so
        `override_state` scores it there and the log carries the answer. A fixture
        standing in for the page would prove the fixture, not the entry."""
        self.assertTrue(hasattr(K, "override_state"))


class OverrideRevalidationTest(unittest.TestCase):
    """`override_state` is the revalidation, and it runs in the adapter rather than here.

    The helper this replaced lived in the test file and re-stated the rule it was meant to
    check, so it could only prove decision semantics. This scores an entry against the
    page as it stands, which is the question that matters as the source changes: is this
    override still doing anything.
    """

    FILM_PAGE = K.film_facts(kilta_film())
    SPARSE_PAGE = K.film_facts(SPARSE_FILM)
    GIG_PAGE = K.film_facts(LIVE_ACT_WITH_METADATA)

    def state(self, action, facts, listed=True, read=True):
        return K.override_state({"action": action},
                                K.default_state(facts) if facts else K.UNRESOLVED,
                                listed, read)

    def test_an_include_is_active_while_the_page_fills_no_field(self):
        self.assertEqual(self.state("include", self.SPARSE_PAGE), K.ACTIVE)

    def test_an_include_turns_redundant_once_the_page_names_a_director(self):
        """The case the policy wants surfaced: the cinema filled the field in, so the
        entry is no longer carrying the decision."""
        self.assertEqual(self.state("include", self.FILM_PAGE), K.REDUNDANT)

    def test_an_exclude_is_active_while_the_page_still_classifies_as_a_film(self):
        """A billed gig that fills the generic fields. The exclusion is the only thing
        withholding it, so it is doing all the work."""
        self.assertEqual(self.state("exclude", self.GIG_PAGE), K.ACTIVE)
        self.assertEqual(K.default_state(self.GIG_PAGE), K.FILM)

    def test_an_exclude_turns_redundant_once_the_page_stops_classifying(self):
        self.assertEqual(self.state("exclude", self.SPARSE_PAGE), K.REDUNDANT)

    def test_an_event_absent_from_the_listing_is_unavailable_not_redundant(self):
        """A film off programme proves nothing about whether its override is needed.
        Treating that as redundancy would delete a still-needed entry."""
        for action in ("include", "exclude"):
            with self.subTest(action=action):
                self.assertEqual(self.state(action, None, listed=False, read=False),
                                 K.UNAVAILABLE)

    def test_a_page_that_was_not_read_is_unavailable_even_when_the_event_is_listed(self):
        self.assertEqual(self.state("include", None, listed=True, read=False),
                         K.UNAVAILABLE)

    def test_an_unlisted_event_is_unavailable_even_when_its_page_was_read(self):
        """The mirror of the case above, and the reason `listed` is a parameter rather
        than an inference from the page. Inside `parse` the two always move together,
        because pages come from the listing's own slugs, so only this reaches it: a
        cached or separately supplied page does not make a vanished event current."""
        self.assertEqual(self.state("include", self.SPARSE_PAGE, listed=False,
                                    read=True), K.UNAVAILABLE)
        self.assertEqual(self.state("exclude", self.GIG_PAGE, listed=False,
                                    read=True), K.UNAVAILABLE)

    def test_unavailable_is_never_confused_with_either_verdict(self):
        self.assertNotIn(K.UNAVAILABLE, (K.ACTIVE, K.REDUNDANT))

    def test_every_entry_in_the_file_is_scored_even_when_its_film_is_gone(self):
        """Scored from the override file, not from the listing, so an entry whose event
        has left the programme is reported rather than quietly skipped."""
        page = listing(laika_row("hetki", "Hetki ennen valoa"),
                       laika_row("hetki", "Hetki ennen valoa", date="17/09/2026 16:00"))
        _, om = K.parse(LAIKA, page, {"hetki": laika_film()},
                        {("kinolaika", "gone"): {"action": "include"},
                         ("kinolaika", "hetki"): {"action": "include"}})
        self.assertEqual(om["overrides"],
                         {"gone": K.UNAVAILABLE, "hetki": K.REDUNDANT})

    def test_an_override_for_another_provider_is_not_scored_here(self):
        page = listing(laika_row("hetki", "Hetki ennen valoa"),
                       laika_row("oasis", "Oasis", date="18/09/2026 20:00"))
        _, om = K.parse(LAIKA, page,
                        {"hetki": laika_film(), "oasis": CONCERT_FILM},
                        {("kinokilta", "hetki"): {"action": "exclude"}})
        self.assertEqual(om["overrides"], {})


# ---------------------------------------------------------------- parse and omissions

class ParseTest(unittest.TestCase):
    def run_parse(self, overrides=None):
        page = listing(
            laika_row("hetki", "Hetki ennen valoa"),
            laika_row("hetki", "Hetki ennen valoa", date="17/09/2026 16:00"),
            laika_row("fox", "A Fox Under a Pink Moon", date="24/09/2026 18:00"),
            laika_row("arppa", "Arppa", date="30/10/2026 19:00", sold=True),
            laika_row("arppa", "Arppa", date="31/10/2026 19:00"),
            laika_row("oasis", "Oasis: Don't Look Back in Anger",
                      date="18/09/2026 20:00", sold=True))
        pages = {"hetki": laika_film(), "fox": SPARSE_FILM, "arppa": LIVE_ACT,
                 "oasis": CONCERT_FILM}
        return K.parse(LAIKA, page, pages,
                       {("kinolaika", "fox"): {"action": "include"}}
                       if overrides is None else overrides)

    def test_films_publish_and_the_live_act_does_not(self):
        per, om = self.run_parse()
        titles = sorted({s["title"] for s in per["laika-karkkila"]})
        self.assertEqual(titles, ["A Fox Under a Pink Moon", "Hetki ennen valoa",
                                  "Oasis: Don't Look Back in Anger"])
        self.assertNotIn("Arppa", titles)

    def test_a_sold_out_film_is_preserved_with_the_film_page_as_its_destination(self):
        """No sold-out film was on the live listing that day; only a fixture shows it."""
        per, _ = self.run_parse()
        oasis = [s for s in per["laika-karkkila"] if s["title"].startswith("Oasis")]
        self.assertEqual(len(oasis), 1)
        self.assertIs(oasis[0]["soldOut"], True)
        self.assertEqual(oasis[0]["url"], "https://www.kinolaika.fi/film/oasis/")

    def test_the_omission_count_is_unique_films_and_screenings_split_by_state(self):
        _, om = self.run_parse()
        self.assertEqual(om["unresolved_films"], {"Arppa"})
        self.assertEqual(om["unresolved_shows"], 2)
        self.assertEqual(om["non_film_films"], set())
        self.assertEqual(om["non_film_shows"], 0)

    def test_a_confirmed_non_film_is_counted_apart_from_an_unresolved_entry(self):
        """Two different claims. Only the first says a person judged it not a film."""
        _, om = self.run_parse({("kinolaika", "oasis"): {"action": "exclude"}})
        self.assertEqual(om["non_film_films"], {"Oasis: Don't Look Back in Anger"})
        self.assertEqual(om["non_film_shows"], 1)
        self.assertEqual(om["unresolved_films"], {"Arppa", "A Fox Under a Pink Moon"})
        self.assertEqual(om["unresolved_shows"], 3)

    def test_an_excluded_live_act_with_metadata_is_a_confirmed_non_film(self):
        """The precedence through parse: the page would classify as a film, the exclusion
        withholds it, and the report says confirmed rather than unresolved."""
        page = listing(laika_row("arppa", "Arppa"),
                       laika_row("arppa", "Arppa", date="31/10/2026 19:00"),
                       laika_row("hetki", "Hetki ennen valoa", date="17/09/2026 16:00"))
        per, om = K.parse(LAIKA, page,
                          {"arppa": LIVE_ACT_WITH_METADATA, "hetki": laika_film()},
                          {("kinolaika", "arppa"): {"action": "exclude"}})
        self.assertEqual([s["title"] for s in per["laika-karkkila"]],
                         ["Hetki ennen valoa"])
        self.assertEqual(om["non_film_films"], {"Arppa"})
        self.assertEqual(om["non_film_shows"], 2)
        self.assertEqual(om["unresolved_films"], set())
        self.assertEqual(om["overrides"], {"arppa": K.ACTIVE})

    def test_the_same_film_at_the_same_minute_twice_is_one_row(self):
        """The listing has repeated a row before; the screening is the film and the
        minute, not the block."""
        row = laika_row("hetki", "Hetki ennen valoa")
        per, _ = K.parse(LAIKA, listing(row, row), {"hetki": laika_film()})
        self.assertEqual(len(per["laika-karkkila"]), 1)

    def test_two_screenings_of_one_film_are_two_rows(self):
        per, _ = self.run_parse()
        hetki = [s for s in per["laika-karkkila"] if s["title"] == "Hetki ennen valoa"]
        self.assertEqual(len(hetki), 2)
        self.assertEqual(sorted(s["start"][:10] for s in hetki),
                         ["2026-09-16", "2026-09-17"])

    def test_rows_are_sorted_by_start(self):
        per, _ = self.run_parse()
        starts = [s["start"] for s in per["laika-karkkila"]]
        self.assertEqual(starts, sorted(starts))

    def test_every_show_meets_the_contract(self):
        per, _ = self.run_parse()
        common.check_shows(per, "kinolaika", {"laika-karkkila"})

    def test_a_kilta_parse_carries_the_row_duration_and_the_page_metadata(self):
        page = listing(kilta_row("hetki", "Hetki ennen valoa"),
                       kilta_row("oasis", "Oasis", date="KE 16.9.2026", time="19:00"))
        per, om = K.parse(KILTA, page, {"hetki": kilta_film(), "oasis": CONCERT_FILM})
        rows = per["kilta-turku"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["len"], "106")          # the row, not the page's 87
        self.assertEqual(rows[0]["rating"], "K-12")
        self.assertEqual(rows[0]["genres"], "Draama")
        self.assertEqual(rows[0]["method"], "Kahvikino")
        self.assertEqual(om["unresolved_shows"], 0)
        common.check_shows(per, "kinokilta", {"kilta-turku"})


# ---------------------------------------------------------------- the runner

class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._fetch, self._sleep = K.fetch, K.time.sleep
        self.addCleanup(lambda: setattr(K, "fetch", self._fetch))
        self.addCleanup(lambda: setattr(K.time, "sleep", self._sleep))
        K.time.sleep = lambda s: None
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
        K.fetch = fetch

    def main(self, which="kinola", half="cloud"):
        """`--half cloud` by default: the three tenants these tests were written for are
        cloud and Cinema Sheryl is local, so without it every test here would also fetch
        sheryl.fi and the stub would raise on a URL it was never given. Explicit rather
        than inherited from the environment, which decides the half differently on Actions
        than on a laptop."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main([which, "--half", half])
        return code, out.getvalue() + err.getvalue()

    def both(self, **over):
        pages = {
            "https://www.kinokilta.fi/naytokset/": listing(
                kilta_row("hetki", "Hetki ennen valoa"),
                kilta_row("oasis", "Oasis", date="KE 16.9.2026", time="19:00")),
            "https://www.kinokilta.fi/film/hetki/": kilta_film(),
            "https://www.kinokilta.fi/film/oasis/": CONCERT_FILM,
            "https://www.kinolaika.fi/ohjelmisto/": listing(
                laika_row("hetki", "Hetki ennen valoa"),
                laika_row("arppa", "Arppa", date="30/10/2026 19:00", sold=True)),
            "https://www.kinolaika.fi/film/hetki/": laika_film(),
            "https://www.kinolaika.fi/film/arppa/": LIVE_ACT,
            "https://kinomyyri.fi/ohjelmisto/": listing(
                myyri_row("hanuman", "Hanuman Ansh", self.soon(1)),
                myyri_row("autofiktio", "Autofiktio", self.soon(2), time="17:00")),
            "https://kinomyyri.fi/film/hanuman/": myyri_film(),
            "https://kinomyyri.fi/film/autofiktio/": myyri_film(syn=SYN_FI_TEXT),
        }
        pages.update(over)
        return pages

    @staticmethod
    def soon(days):
        """A date inside Myyri's window, so its rows place against the real clock."""
        return datetime.datetime.now(K.FI).date() + datetime.timedelta(days=days)

    def test_a_full_run_publishes_both_venues_and_omits_the_live_act(self):
        self.serve(self.both())
        code, log = self.main()
        self.assertEqual(code, 0, log)
        kilta = json.loads((run.OUT / "area-kilta-turku.json").read_text())["shows"]
        laika = json.loads((run.OUT / "area-laika-karkkila.json").read_text())["shows"]
        self.assertEqual(len(kilta), 2)
        self.assertEqual([s["title"] for s in laika], ["Hetki ennen valoa"])
        self.assertIn("0 confirmed non-film(s)", log)
        self.assertIn("1 unresolved over 1", log)
        self.assertIn("unresolved: Arppa", log)
        self.assertIn("0 failures", log)
        for pid in ("kinokilta", "kinolaika"):
            v = json.loads((run.OUT / f"venues-{pid}.json").read_text())
            self.assertEqual((v["status"], v["stale"], v["pending"]), ("ok", [], []))

    def test_one_film_page_is_read_per_distinct_film(self):
        self.serve(self.both())
        self.assertEqual(self.main()[0], 0)
        films = [c for c in self.calls if "/film/" in c]
        self.assertEqual(sorted(films), sorted(set(films)))
        self.assertEqual(len(films), 6)

    PREV = {"generated": "2026-09-01T00:00:00+00:00", "dates": ["2026-09-01"],
            "horizon": "2026-09-01",
            "shows": [{"title": "Old", "start": "2026-09-01T12:00:00+03:00"}]}

    def with_previous(self, venue="laika-karkkila"):
        """A venue that already published, so what happens to its file is observable."""
        (run.OUT / f"area-{venue}.json").write_text(json.dumps(self.PREV))

    def unchanged(self, venue="laika-karkkila"):
        self.assertEqual(
            json.loads((run.OUT / f"area-{venue}.json").read_text()), self.PREV,
            "the previous file did not survive")

    def laika(self, page):
        return self.both(**{"https://www.kinolaika.fi/ohjelmisto/": page})

    def cleared(self, venue, provider):
        """The previous screenings are gone and the provider file names the venue pending."""
        area = json.loads((run.OUT / f"area-{venue}.json").read_text())
        self.assertEqual(area["shows"], [])
        self.assertNotEqual(area["generated"], self.PREV["generated"])
        doc = json.loads((run.OUT / f"venues-{provider}.json").read_text())
        self.assertEqual((doc["status"], doc["pending"]), ("ok", [venue]))

    def test_a_listing_with_no_screening_clears_the_previous_file_and_stays_green(self):
        """The platform's own empty state, as read on kinokonepaja.fi."""
        self.with_previous()
        self.serve(self.laika(empty_listing()))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.cleared("laika-karkkila", "kinolaika")
        self.assertIn("no programme published", log)
        self.assertIn("empty state", log)
        self.assertTrue((run.OUT / "area-kilta-turku.json").exists())

    def test_an_unrelated_page_fails_that_site_instead_of_reading_as_empty(self):
        """It exited 0 and aged the data quietly: zero parsed rows was the whole test, and
        an unrelated page parses to zero rows exactly like an empty listing does."""
        self.with_previous()
        self.serve(self.laika(UNRELATED_HTML))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("FAILED", log)
        self.assertIn("no evidence of an empty programme", log)
        self.assertNotIn("no programme published", log)
        self.unchanged()
        self.assertTrue((run.OUT / "area-kilta-turku.json").exists())

    def test_a_rendered_container_with_no_readable_row_fails_that_site(self):
        """The row class changing upstream: the listing is there and nothing in it parses.
        Reading that as a quiet week is the regression the whole rule exists to catch."""
        self.with_previous()
        self.serve(self.laika(listing()))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("markup change", log)
        self.unchanged()

    def test_a_listing_whose_every_row_is_malformed_fails_instead_of_reading_as_empty(self):
        """Every row skipped left zero rows, which the old rule called an empty programme:
        exit 0, stale data preserved, and no line anywhere saying a screening was lost."""
        self.with_previous()
        self.serve(self.laika(listing(
            laika_row("a", "A", date="31/02/2026 14:00"),
            laika_row("b", "B", date="31/02/2026 16:00"))))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("FAILED", log)
        self.assertNotIn("no programme published", log)
        self.unchanged()
        self.assertTrue((run.OUT / "area-kilta-turku.json").exists())

    def test_one_malformed_row_fails_rather_than_publishing_a_partial_schedule(self):
        """One good row and one bad one published the good one, exit 0, and the dropped
        screening appeared in neither the schedule nor the omission report."""
        self.with_previous()
        self.serve(self.laika(listing(
            laika_row("hetki", "Hetki ennen valoa"),
            laika_row("bad", "Bad", date="31/02/2026 16:00"))))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("block 2", log)
        self.unchanged()

    def test_the_other_cinema_still_publishes_when_one_listing_fails(self):
        """One site failing is one failure. Kilta's own files are written and fresh."""
        self.serve(self.laika(UNRELATED_HTML))
        self.assertEqual(self.main()[0], 1)
        shows = json.loads((run.OUT / "area-kilta-turku.json").read_text())["shows"]
        self.assertEqual(len(shows), 2)
        self.assertTrue((run.OUT / "venues-kinokilta.json").exists())
        self.assertFalse((run.OUT / "venues-kinolaika.json").exists())

    def test_a_row_carrying_extra_classes_still_publishes(self):
        """An attribute match hid it: not parsed, not published, not counted, and with
        every row like it the site read as a cinema with nothing on."""
        self.serve(self.laika(listing(
            laika_row("hetki", "Hetki ennen valoa"),
            with_classes(laika_row("hetki", "Hetki ennen valoa",
                                   date="17/09/2026 16:00"), "featured"))))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        shows = json.loads((run.OUT / "area-laika-karkkila.json").read_text())["shows"]
        self.assertEqual(len(shows), 2)
        self.assertIn("2 screening(s) listed", log)

    def test_a_listing_whose_rows_all_fail_to_classify_fails_the_site(self):
        """Blocks present and nothing published is a template or classification failure,
        not a cinema with nothing on."""
        self.serve(self.both(**{
            "https://www.kinolaika.fi/ohjelmisto/": listing(
                laika_row("arppa", "Arppa"),
                laika_row("arppa", "Arppa", date="31/10/2026 19:00"))}))
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", log)
        self.assertFalse((run.OUT / "area-laika-karkkila.json").exists())
        self.assertTrue((run.OUT / "area-kilta-turku.json").exists())

    def test_a_film_page_that_cannot_be_read_fails_that_site_only(self):
        """The page carries the classification, so a missing one would omit its
        screenings silently. A second film publishes from the same listing, so swallowing
        the failure would exit 0 with a partial schedule rather than fail: that is what
        this asserts against, not merely a non-zero exit."""
        self.serve(self.both(**{
            "https://www.kinolaika.fi/ohjelmisto/": listing(
                laika_row("hetki", "Hetki ennen valoa"),
                laika_row("oasis", "Oasis", date="18/09/2026 20:00")),
            "https://www.kinolaika.fi/film/hetki/": RuntimeError("HTTP Error 503"),
            "https://www.kinolaika.fi/film/oasis/": CONCERT_FILM}))
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", log)
        self.assertIn("classification", log)
        self.assertFalse((run.OUT / "area-laika-karkkila.json").exists())
        self.assertTrue((run.OUT / "area-kilta-turku.json").exists())

    def test_a_refused_listing_fails_that_site_only(self):
        self.serve(self.both(**{
            "https://www.kinokilta.fi/naytokset/": RuntimeError("HTTP Error 403")}))
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", log)
        self.assertFalse((run.OUT / "area-kilta-turku.json").exists())
        self.assertTrue((run.OUT / "area-laika-karkkila.json").exists())

    def test_a_listing_over_the_film_page_budget_is_refused(self):
        rows = [laika_row(f"f{n}", f"Film {n}", date=f"{(n % 28) + 1:02d}/09/2026 14:00")
                for n in range(common.PAGE_BUDGET + 2)]
        self.serve(self.both(**{
            "https://www.kinolaika.fi/ohjelmisto/": listing(*rows)}))
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("over the", log)
        self.assertIn("partial schedule", log)
        # Refused before the loop, not trimmed inside it: a cap would fetch the first
        # 120 pages and publish what they classified.
        self.assertEqual([c for c in self.calls if "kinolaika.fi/film/" in c], [])
        self.assertFalse((run.OUT / "area-laika-karkkila.json").exists())

    def myyri(self, page):
        return self.both(**{"https://kinomyyri.fi/ohjelmisto/": page})

    def test_myyri_publishes_the_listings_checkout_link_and_never_requests_it(self):
        self.serve(self.both())
        code, log = self.main()
        self.assertEqual(code, 0, log)
        shows = json.loads((run.OUT / "area-myyri-vantaa.json").read_text())["shows"]
        self.assertEqual([s["title"] for s in shows], ["Hanuman Ansh", "Autofiktio"])
        self.assertTrue(all(s["url"].startswith("https://kinomyyri.fi/checkout/")
                            for s in shows), [s["url"] for s in shows])
        self.assertEqual({s["price"] for s in shows}, {""})
        self.assertEqual({s["len"] for s in shows}, {"150"})
        self.assertTrue(all(s["img"].startswith("https://media.kinola.ee/")
                            for s in shows))
        self.assertEqual([c for c in self.calls if "checkout" in c], [])

    def test_sheryl_publishes_on_the_local_half(self):
        """The fourth tenant is the only local one, so it is the half these three are not
        run on. `--half local` is what the wrapper outside this repository passes."""
        pages = {
            "https://sheryl.fi/": listing(
                sheryl_row("chungking", "Chungking Express", self.soon(1)),
                sheryl_row("resident-evil", "Resident Evil", self.soon(2), time="19:00")),
            "https://sheryl.fi/film/chungking/": sheryl_film(),
            "https://sheryl.fi/film/resident-evil/": sheryl_film(director="Zach Cregger"),
        }
        self.serve(pages)
        code, log = self.main(half="local")
        self.assertEqual(code, 0, log)
        shows = json.loads((run.OUT / "area-sheryl-espoo.json").read_text())["shows"]
        self.assertEqual([s["title"] for s in shows],
                         ["Chungking Express", "Resident Evil"])
        self.assertEqual([s["url"] for s in shows],
                         ["https://sheryl.fi/checkout/0112a866-2646-4310-b698-a6e5b1b84666"] * 2)
        self.assertEqual([c for c in self.calls if "checkout" in c], [])
        self.assertNotIn("kinokilta.fi", " ".join(self.calls))

    def test_the_synopsis_is_published_under_the_language_it_is_written_in(self):
        self.serve(self.both())
        self.assertEqual(self.main()[0], 0)
        films = json.loads((run.OUT / "films-extra.json").read_text())["films"]
        self.assertEqual(films["hanuman ansh"]["s"].get("en"), SYN_EN_TEXT)
        self.assertEqual(films["hanuman ansh"]["s"].get("fi", ""), "")
        self.assertEqual(films["autofiktio"]["s"].get("fi"), SYN_FI_TEXT)

    def test_a_synopsis_in_no_settled_language_is_withheld_and_counted(self):
        self.serve(self.both(**{
            "https://kinomyyri.fi/film/hanuman/": myyri_film(syn=SYN_NO_LANGUAGE)}))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertIn("synopsis/synopses withheld", log)
        shows = json.loads((run.OUT / "area-myyri-vantaa.json").read_text())["shows"]
        self.assertEqual(len(shows), 2)

    def test_myyri_empty_listing_clears_the_previous_file_and_stays_green(self):
        self.with_previous("myyri-vantaa")
        self.serve(self.myyri(empty_listing()))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.cleared("myyri-vantaa", "kinomyyri")
        self.assertIn("no programme published", log)

    def test_a_myyri_row_that_cannot_be_placed_fails_that_site_only(self):
        self.with_previous("myyri-vantaa")
        self.serve(self.myyri(listing(
            myyri_row("hanuman", "Hanuman Ansh", self.soon(1)),
            myyri_row("a", "A", None, date="ma 18.9. klo 19:30"))))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("block 2", log)
        self.unchanged("myyri-vantaa")
        self.assertTrue((run.OUT / "area-kilta-turku.json").exists())


# ---------------------------------------------------------------- registry and sites

class RegistryTest(unittest.TestCase):
    def test_the_three_registry_entries(self):
        for pid, label, host, accent, venue, city in (
                ("kinokilta", "Kino Kilta", "kinokilta.fi", "#1D6F8B", "kilta-turku",
                 "Turku"),
                ("kinolaika", "Kino Laika", "kinolaika.fi", "#9A3412", "laika-karkkila",
                 "Karkkila"),
                ("kinomyyri", "Kino Myyri", "kinomyyri.fi", "#807CFC", "myyri-vantaa",
                 "Vantaa")):
            with self.subTest(provider=pid):
                p = registry.by_id(pid)
                self.assertEqual((p["label"], p["host"], p["accent"], p["book"],
                                  p["module"], p["where"]),
                                 (label, host, accent, "buy", "kinola", "cloud"))
                self.assertEqual(sum(1 for q in registry.PROVIDERS
                                     if q["accent"] == p["accent"]), 1)
                site = next(s for s in K.SITES if s["provider"] == pid)
                v = site["venues"][0]
                self.assertEqual((v["id"], v["name"], v["short"], v["city"]),
                                 (venue, label, label, city))

    def test_konepaja_has_no_entry_until_it_lists_a_screening(self):
        """Re-read 2026-09-15: its event list still says "Ei tulevia tapahtumia."."""
        self.assertIsNone(registry.by_id("kinokonepaja"))
        self.assertNotIn("konepaja", {s["provider"] for s in K.SITES})
        self.assertNotIn("kinokonepaja.fi", {s["base"] for s in K.SITES})

    def test_each_site_names_the_host_it_reads_and_they_are_paced_apart(self):
        self.assertEqual([s["base"] for s in K.SITES],
                         ["https://www.kinokilta.fi", "https://www.kinolaika.fi",
                          "https://kinomyyri.fi", "https://sheryl.fi"])
        # Four hosts, four groups: every tenant is its own WordPress, so nothing here
        # shares a server and the pacing is per site.
        self.assertEqual(len(run.host_groups(K.SITES)), 4)

    def test_orion_still_reads_the_third_template_and_is_untouched(self):
        """One platform, two modules. Orion's own table is not this module's business."""
        import orion
        self.assertEqual(registry.by_id("orion")["module"], "orion")
        self.assertEqual(orion.parse(listing(kilta_row("a", "A"))), [])

    def test_all_three_providers_share_the_one_module(self):
        mods = {registry.by_id(p)["module"]
                for p in ("kinokilta", "kinolaika", "kinomyyri")}
        self.assertEqual(mods, {"kinola"})


class SherylTemplateTest(unittest.TestCase):
    """The fourth tenant: the same block as Myyri, a different date string, and a film
    page whose labels are in English.

    The site localises its listing to whatever `accept-language` asks for. Read
    2026-09-19: the Finnish header `common.TEXT_HEADERS` always sends gives `su, 20.09
    15:00`, no header gives `Sun, 20.09 15:00`. The pipeline only ever sees the first; the
    second is read too, and both are pinned here because both were served.
    """

    TODAY = datetime.date(2026, 9, 19)

    def rows(self, *rows, today=None):
        return K.events_sheryl(listing(*rows), SHERYL, today or self.TODAY)

    def test_the_finnish_weekday_the_pipeline_asks_for_places_the_row(self):
        [row] = self.rows(sheryl_row("chungking", "Chungking Express",
                                     datetime.date(2026, 9, 20)))
        self.assertEqual(row["start"], "2026-09-20T15:00:00+03:00")
        self.assertEqual(row["title"], "Chungking Express")

    def test_the_english_weekday_places_the_same_row(self):
        [row] = self.rows(sheryl_row("chungking", "Chungking Express",
                                     datetime.date(2026, 9, 20), lang="en"))
        self.assertEqual(row["start"], "2026-09-20T15:00:00+03:00")

    def test_every_weekday_of_the_week_resolves_in_both_languages(self):
        """`weekday_index` answers for `su` and `ti` whichever language they came from and
        None for the other five English ones, which is what the English map is for."""
        for i in range(7):
            when = datetime.date(2026, 9, 21) + datetime.timedelta(days=i)
            for lang in ("fi", "en"):
                with self.subTest(day=when.isoformat(), lang=lang):
                    [row] = self.rows(sheryl_row("a", "A", when, lang=lang),
                                      today=datetime.date(2026, 9, 19))
                    self.assertEqual(row["start"][:10], when.isoformat())

    def test_an_english_weekday_is_read_and_not_merely_ignored(self):
        """The fallback has to be doing work, not sitting unused beside dates the nearest
        occurrence would have placed anyway.

        `01.01` read on 2026-09-19 has exactly one candidate inside the window, 2027-01-01,
        a Friday 104 days out. `Sat` belongs to 2028, 469 days out and outside it, so a
        parser that reads the English name raises and one that drops it to None takes the
        nearest occurrence and publishes the wrong year. `Fri` is the control.
        """
        [row] = self.rows(sheryl_row("a", "A", None, date="Fri, 01.01 18:00"))
        self.assertEqual(row["start"][:10], "2027-01-01")
        with self.assertRaises(K.ListingRowError):
            self.rows(sheryl_row("a", "A", None, date="Sat, 01.01 18:00"))

    def test_a_weekday_that_fits_no_candidate_year_raises(self):
        with self.assertRaises(K.ListingRowError):
            self.rows(sheryl_row("a", "A", None, date="ma, 20.09 15:00"))

    def test_a_date_this_parser_cannot_read_raises_rather_than_dropping_a_screening(self):
        with self.assertRaises(K.ListingRowError):
            self.rows(sheryl_row("a", "A", None, date="joskus ensi viikolla"))

    def test_the_showtime_links_to_the_listings_checkout_href(self):
        """Sheryl's anchor class is `kinola-event-tickets-link-buy`; its href is copied."""
        [row] = self.rows(sheryl_row("chungking", "C", datetime.date(2026, 9, 20)))
        self.assertEqual(row["url"],
                         "https://sheryl.fi/checkout/0112a866-2646-4310-b698-a6e5b1b84666")

    def test_a_sold_out_row_or_one_with_no_anchor_opens_the_film_page(self):
        rows = self.rows(sheryl_row("chungking", "C", datetime.date(2026, 9, 20), sold=True),
                         sheryl_row("evil", "E", datetime.date(2026, 9, 20), time="19:00",
                                    no_ticket=True))
        self.assertEqual([(r["url"], r["soldOut"]) for r in rows],
                         [("https://sheryl.fi/film/chungking/", True),
                          ("https://sheryl.fi/film/evil/", False)])

    def test_the_listing_poster_is_read(self):
        [a, b] = self.rows(sheryl_row("a", "A", datetime.date(2026, 9, 20)),
                           sheryl_row("b", "B", datetime.date(2026, 9, 20), time="17:00",
                                      poster=False))
        self.assertTrue(a["img"].startswith("https://media.kinola.ee/storage/sheryl"))
        self.assertEqual(b["img"], "")


class SherylClassifierTest(unittest.TestCase):
    """An English `Director` is the same evidence as a Finnish `Ohjaus`."""

    def test_an_english_director_label_classifies_the_page_as_a_film(self):
        facts = K.film_facts(sheryl_film())
        self.assertEqual(K.default_state(facts), K.FILM)

    def test_a_page_with_no_director_or_genre_stays_unresolved(self):
        """Never `non-film`: this module does not identify a live act by itself."""
        facts = K.film_facts(sheryl_film(director=""))
        self.assertEqual(K.default_state(facts), K.UNRESOLVED)

    def test_the_finnish_vocabulary_still_classifies(self):
        self.assertEqual(K.default_state(K.film_facts(laika_film())), K.FILM)


if __name__ == "__main__":
    unittest.main()
