"""The Johku storefront reader: six cinemas, one front page each.

The fixtures are the front page as the storefronts sent it on 2026-10-09, cut to the
smallest shape that still exercises a rule: the markup draws every programme block as a
loading skeleton, and the `__NUXT_DATA__` payload carries the schedule the page is drawn
from. Two entries minimum everywhere there is a loop, over two days or two blocks.

What they exist to prove:

- **Only a whole schedule is published.** A block whose schedule is absent, failed or
  answered in another shape, and markup drawing a different number of blocks, are read
  again and then fail the site with its previous files standing. Every block answering
  with an empty list is the one empty programme.
- **The page's own rules decide what is a screening**: in the catalogue for the locale,
  not started, not a coming-soon entry, and once per show id across blocks.
- **A hall hire has no canonical name**, so the platform files it under `/fi_FI/products/`.
  Nothing else is left out: a film page with no director, no genre or no answer at all
  costs the row its metadata and never its place.
- **The synopsis carries its own language.** Tammisaari publishes Swedish.
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
import johku as J
import registry
import run


MARILYN = next(s for s in J.SITES if s["provider"] == "biomarilyn")
FORUM = next(s for s in J.SITES if s["provider"] == "bioforum")
NOW = datetime.datetime(2026, 10, 9, 12, 0, tzinfo=J.FI)

SYN_FI = ("Klaus Härön draama kertoo kahden naisen kohtaamisesta keskellä hoitoalan "
          "kriisiä, kun sairaanhoitajat uhkaavat lakolla ja hän joutuu venymään.")
SYN_SV = ("Filmen handlar om en ung kvinna som inte vet att hennes far är tillbaka, och "
          "det som händer efter att hon möter honom i staden.")
# Long enough to be read as a synopsis and carrying no function word of any of the three
# languages. "The Odyssey" at Vihdin Kino was this case on 2026-09-18.
SYN_NO_LANGUAGE = ("Odysseus. Troija, Ithaka, Kirke, Kalypso, Skylla, Kharybdis, Poseidon, "
                   "Penelope, Telemakhos, Polyfemos, Aiolos, Laistrygonit.")


def entry(sid, title, start, minutes=87, loc="Bio Marilyn", product="1038", slug=None,
          rating="K-12", upcoming="0", host="https://biomarilyn.johku.com", path=None,
          catalog="fi_FI", collection="fi_FI"):
    """One schedule entry, with the fields the page's ShowItem draws. `start` is the
    clock the page prints, "2026-10-09 17:30"."""
    slug = slug or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    begin = datetime.datetime.fromisoformat(start)
    return {"id": sid, "shopId": "x", "text": title, "start_date": start,
            "end_date": f"{begin + datetime.timedelta(minutes=minutes):%Y-%m-%d %H:%M}",
            "resource_name": loc, "agelimit": rating, "upcoming": upcoming,
            "storefronturl": host + (path or f"/fi_FI/{slug}"),
            "product": {"id": product, "name": title, "canonical": slug,
                        "enable_catalog": catalog, "enable_collection": collection}}


def devalue(value):
    """`value` in devalue's flat form, as Nuxt writes `__NUXT_DATA__`. A (tag, inner)
    tuple is a typed value."""
    flat = []

    def add(v):
        i = len(flat)
        flat.append(None)
        if isinstance(v, tuple):
            flat[i] = [v[0], add(v[1])]
        elif isinstance(v, dict):
            flat[i] = {k: add(x) for k, x in v.items()}
        elif isinstance(v, list):
            flat[i] = [add(x) for x in v]
        else:
            flat[i] = v
        return i

    add(value)
    return json.dumps(flat, ensure_ascii=False)


# The loading placeholder the markup carries in place of a block's day groups, read
# 2026-10-03 on biomarilyn.com.
SKELETON = ('<div class="product-list-skeleton" role="status" aria-busy="true" '
            'aria-label="Haetaan..."><span class="sr-only">Haetaan...</span>'
            '<div class="showgroup"><h3 class="daytitle" aria-hidden="true">'
            '<span class="sk-line"></span></h3><div class="js-grid">'
            '<div class="js-grid-item js-grid-product in-grid sk-product-card" '
            'aria-hidden="true"></div></div></div></div>')


def front(*blocks, shop="biomarilyn", drawn=None, absent=(), failed=(), answers=None):
    """A front page: `blocks` is (category id, [entry]) per programme block.

    A category in `absent` has no schedule in the payload, one in `failed` has its request
    recorded as failed, and `answers` replaces a category's answer outright. `drawn` is how
    many blocks the markup draws, by default as many as the layout names.
    """
    items = [{"category": {"id": cid, "canonical": f"c{cid}"}, "products": [],
              "view": "showtimes"} for cid, _ in blocks]
    items.append({"category": {"id": 99, "canonical": "lahjakortit"}, "products": [],
                  "view": "default"})
    data = {f"storefront-{shop}-fi_FI": {"carousel": {}, "groups": [
        {"display": "default", "items": items}], "featured": []},
            "listpreview-none-v-0-0-0": False}
    errors = {f"storefront-{shop}-fi_FI": None}
    for cid, entries in blocks:
        key = f"showschedule-fi_FI-f2026-10-09-c{cid}"
        if cid in absent:
            continue
        data[key] = (answers or {}).get(cid, {"data": entries})
        errors[key] = None
        if cid in failed:
            data[key] = None
            errors[key] = ("NuxtError", {"statusCode": 500, "message": "fetch failed"})
    root = ("ShallowReactive", {
        "data": ("ShallowReactive", data), "state": {}, "once": [],
        "_errors": ("ShallowReactive", errors), "serverRendered": True, "path": "/",
        "pinia": {"main": ("Reactive", {"timezone": "Europe/Helsinki", "apiKey": ""})}})
    markup = "".join(f'<div class="js-shows">{SKELETON}</div>'
                     for _ in range(len(blocks) if drawn is None else drawn))
    return ("<html><body><div class='container'>" + markup + "</div>"
            '<script type="application/json" data-nuxt-data="nuxt-app" data-ssr="true" '
            f'id="__NUXT_DATA__">{devalue(root)}</script></body></html>')


def blocks_of(page):
    state, blocks = J.schedule(page)
    assert state == "complete", state
    return blocks


def two_days(loc="Bio Marilyn", host="https://biomarilyn.johku.com"):
    return [entry("1", "Hetki ennen valoa", "2026-10-09 17:30", loc=loc, host=host),
            entry("2", "Filmen", "2026-10-10 19:15", product="1039", loc=loc, host=host)]


def film(kesto="87 min", genres="Draama", original="Hetki ennen valoa", syn=SYN_FI,
         labels=True):
    rows_ = ""
    if labels:
        rows_ = (f'<div class="product-content-inforow">'
                 f'<div class="product-content-infolabel">Kesto</div>'
                 f'<div class="product-content-infovalue text-content">{kesto}</div></div>'
                 f'<div class="product-content-inforow">'
                 f'<div class="product-content-infolabel">Luokittelu</div>'
                 f'<div class="product-content-infovalue text-content">{genres}</div></div>'
                 f'<div class="product-content-inforow">'
                 f'<div class="product-content-infolabel">Alkuperäinen nimi</div>'
                 f'<div class="product-content-infovalue text-content">{original}</div>'
                 f'</div><div class="product-content-inforow">'
                 f'<div class="product-content-infolabel">Ohjaaja</div>'
                 f'<div class="product-content-infovalue text-content">Klaus Härö</div>'
                 f'</div>')
    else:
        rows_ = ('<div class="product-content-inforow">'
                 '<div class="product-content-infolabel">Kesto</div>'
                 '<div class="product-content-infovalue text-content">120 min</div></div>')
    body = (f'<div class="product-description__html"><p>{syn}</p>'
            f'<p>Elokuvateattereissa 4.9.</p></div>' if syn else "")
    return ("<html><body>" + body + '<div class="product-content-infotable">'
            + rows_ + "</div></body></html>")


class PayloadTest(unittest.TestCase):
    def test_references_wrappers_and_undefined_are_revived(self):
        flat = [["ShallowReactive", 1], {"a": 2, "b": 4, "c": -1, "d": 2, "e": 6},
                ["Reactive", 3], {"x": 5}, ["Set", 5], "v", [5, -1]]
        page = (f'<script type="application/json" id="__NUXT_DATA__">{json.dumps(flat)}'
                f"</script>")
        root = J.payload(page)
        self.assertEqual(root["a"], {"x": "v"})
        self.assertIs(root["d"], root["a"], "one index is one value")
        self.assertIsNone(root["c"])
        self.assertIs(root["b"], J.UNREAD, "a type the reader does not know is left unread")
        self.assertEqual(root["e"], ["v", None])

    def test_no_script_or_an_unreadable_one_is_none(self):
        for page in ("<html><body></body></html>",
                     '<script id="__NUXT_DATA__">[{"data": 1},</script>',
                     '<script id="__NUXT_DATA__">"text"</script>',
                     '<script id="__NUXT_DATA__">["text"]</script>'):
            with self.subTest(page=page[-30:]):
                self.assertIsNone(J.payload(page))


class ScheduleTest(unittest.TestCase):
    """The shapes a front page can come in. Only the first is the programme."""
    NOW_ = two_days()
    LATER = [entry("3", "Lapin sota", "2026-10-23 18:00", product="1059"),
             entry("4", "Digger", "2026-10-24 15:00", product="1052")]

    def test_a_skeleton_with_its_whole_schedule_is_complete(self):
        """Bio Marilyn's two blocks, 2026-10-09: both drawn as skeletons, both whole in
        the payload."""
        state, blocks = J.schedule(front((1, self.NOW_), (9, self.LATER)))
        self.assertEqual(state, "complete")
        self.assertEqual([[e["text"] for e in b] for b in blocks],
                         [["Hetki ennen valoa", "Filmen"], ["Lapin sota", "Digger"]])

    def test_no_block_answered_is_loading(self):
        page = front((1, self.NOW_), (9, self.LATER), absent=(1, 9))
        self.assertEqual(J.schedule(page), ("loading", []))

    def test_one_block_answered_beside_one_still_loading_is_loading(self):
        """"nyt ohjelmistossa" whole and "tulossa" not: publishing it would drop every
        screening only the second block lists."""
        for absent in ((9,), (1,)):
            with self.subTest(absent=absent):
                page = front((1, self.NOW_), (9, self.LATER), absent=absent)
                self.assertEqual(J.schedule(page), ("loading", []))

    def test_an_answer_that_is_not_a_list_is_loading(self):
        for answer in (None, {}, {"data": None}, {"data": {"0": "x"}}, ("Set", [1])):
            with self.subTest(answer=answer):
                page = front((1, self.NOW_), (9, self.LATER), answers={9: answer})
                self.assertEqual(J.schedule(page), ("loading", []))

    def test_a_request_the_server_recorded_as_failed_is_an_error(self):
        page = front((1, self.NOW_), (9, self.LATER), failed=(9,))
        self.assertEqual(J.schedule(page), ("error", []))

    def test_markup_drawing_another_number_of_blocks_is_unmatched(self):
        for drawn in (1, 3):
            with self.subTest(drawn=drawn):
                page = front((1, self.NOW_), (9, self.LATER), drawn=drawn)
                self.assertEqual(J.schedule(page), ("unmatched", []))

    def test_two_schedules_for_one_block_are_unmatched(self):
        page = front((1, self.NOW_), (9, self.LATER))
        page = page.replace('"showschedule-fi_FI-f2026-10-09-c9"',
                            '"showschedule-fi_FI-f2026-10-08-c9"').replace(
            '"listpreview-none-v-0-0-0"', '"showschedule-fi_FI-f2026-10-09-c9"')
        self.assertEqual(J.schedule(page), ("unmatched", []))

    def test_no_payload_layout_or_programme_block_is_missing(self):
        whole = front((1, self.NOW_), (9, self.LATER))
        no_layout = whole.replace('"storefront-biomarilyn-fi_FI"', '"storefront-x-sv_SE"')
        no_block = front().replace('<div class="js-shows">', "")
        no_payload = re.sub(r"<script.*</script>", "", whole, flags=re.S)
        for page in (no_payload, no_layout, no_block, "<html><body>Bad gateway</body></html>"):
            with self.subTest(page=page[-50:]):
                self.assertEqual(J.schedule(page), ("missing", []))

    def test_every_block_answering_with_an_empty_list_is_complete_and_empty(self):
        self.assertEqual(J.schedule(front((1, []), (9, []))), ("complete", [[], []]))


class RowsTest(unittest.TestCase):
    def rows(self, *entries, now=NOW):
        return J.rows(MARILYN, blocks_of(front((1, list(entries)))), now)

    def test_the_clock_is_read_as_helsinki_time(self):
        """Summer time ends on 2026-10-25, so the two days take different offsets."""
        listed, _ = self.rows(entry("1", "A", "2026-10-24 18:00"),
                              entry("2", "B", "2026-10-26 18:00"))
        self.assertEqual([r["start"] for r in listed],
                         ["2026-10-24T18:00:00+03:00", "2026-10-26T18:00:00+02:00"])

    def test_a_start_that_is_not_a_local_clock_fails_the_site(self):
        for bad in ("2026-10-24T15:00:00Z", "2026-10-24 18:00+03:00", "24.10.2026 18.00",
                    "", None):
            with self.subTest(bad=bad):
                b = entry("2", "B", "2026-10-24 18:00")
                b["start_date"] = bad
                with self.assertRaises(J.ListingRowError) as e:
                    self.rows(entry("1", "A", "2026-10-24 17:00"), b)
                self.assertIn("not a local clock", str(e.exception))

    def test_a_hall_the_site_does_not_list_fails_the_site(self):
        with self.assertRaises(J.ListingRowError) as e:
            self.rows(entry("1", "A", "2026-10-09 17:30"),
                      entry("2", "B", "2026-10-10 17:30", loc="Kulmasali"))
        self.assertIn("Kulmasali", str(e.exception))

    def test_a_coming_soon_entry_is_counted_and_left_out(self):
        listed, report = self.rows(entry("1", "Heart of Beast", "2026-10-16 00:00",
                                         upcoming="1"),
                                   entry("2", "Digger", "2026-10-23 00:00", upcoming="1"),
                                   entry("3", "Avengers", "2026-10-10 19:20", product="2"))
        self.assertEqual([r["title"] for r in listed], ["Avengers"])
        self.assertEqual(sorted(report["skipped"]), ["Digger", "Heart of Beast"])

    def test_an_entry_out_of_the_catalogue_is_left_out_as_the_page_does(self):
        """Either field may list the locale, or hold 1 for every locale."""
        cases = [("in the catalogue", "fi_FI", None, True),
                 ("in a collection", None, "fi_FI;sv_SE", True),
                 ("in every locale", "1", None, True),
                 ("in Swedish only", "sv_SE", "sv_SE", False),
                 ("in none", None, None, False)]
        listed, report = self.rows(*(entry(str(i), name, f"2026-10-1{i} 18:00", catalog=c,
                                           collection=k)
                                     for i, (name, c, k, _) in enumerate(cases)))
        self.assertEqual([r["title"] for r in listed],
                         [name for name, _, _, shown in cases if shown])
        self.assertEqual(report["unlisted"], 2)

    def test_an_entry_with_no_product_is_left_out(self):
        bare = entry("2", "B", "2026-10-10 18:00")
        del bare["product"]
        listed, report = self.rows(entry("1", "A", "2026-10-09 18:00"), bare)
        self.assertEqual(([r["title"] for r in listed], report["unlisted"]), (["A"], 1))

    def test_a_screening_that_has_started_is_left_out(self):
        listed, report = self.rows(entry("1", "A", "2026-10-09 11:59"),
                                   entry("2", "B", "2026-10-09 12:00"))
        self.assertEqual(([r["title"] for r in listed], report["past"]), (["B"], 1))

    def test_a_screening_in_two_blocks_publishes_once(self):
        """Bio Marilyn, 2026-10-09: four "Kerro Kaikille" screenings in both blocks."""
        kerro = entry("10309", "Kerro Kaikille", "2026-10-10 17:00", product="1056")
        blocks = blocks_of(front((1, [kerro, entry("1", "A", "2026-10-11 18:00")]),
                                 (9, [kerro, entry("2", "B", "2026-10-12 18:00")])))
        listed, report = J.rows(MARILYN, blocks, NOW)
        self.assertEqual([r["title"] for r in listed], ["Kerro Kaikille", "A", "B"])
        self.assertEqual(report["repeated"], 1)

    def test_the_row_carries_rating_runtime_and_the_film_link_as_given(self):
        listed, _ = self.rows(entry("1", "A", "2026-10-09 17:30", minutes=112),
                              entry("2", "B", "2026-10-10 17:30", rating="7", product="2",
                                    path="/fi_FI/b-elokuva"))
        self.assertEqual([(r["rating"], r["len"]) for r in listed],
                         [("K-12", "112"), ("K-7", "87")])
        self.assertEqual([r["url"] for r in listed],
                         ["https://biomarilyn.johku.com/fi_FI/a",
                          "https://biomarilyn.johku.com/fi_FI/b-elokuva"])
        self.assertEqual({r["venue"] for r in listed}, {"biomarilyn-lapua"})

    def test_bio_marilyns_link_is_the_platforms_url_unchanged(self):
        """Bio Marilyn's schedule links every film to biomarilyn.johku.com (45 of 45
        entries, read 2026-10-10). The showtime carries that URL exactly, and the host is
        declared because the film page is read from it."""
        listed, _ = self.rows(entry("1", "Digger", "2026-10-09 17:30",
                                    host="https://biomarilyn.johku.com"))
        self.assertEqual(listed[0]["url"], "https://biomarilyn.johku.com/fi_FI/digger")
        self.assertIn("biomarilyn.johku.com", MARILYN["reads"])

    def test_a_rating_the_page_does_not_badge_is_left_empty(self):
        values = ["S", "K-S", "3", "K16", "18", "-", "unknown", None, 12]
        listed, _ = self.rows(*(entry(str(i), f"F{i}", f"2026-10-1{i} 18:00", rating=v)
                                for i, v in enumerate(values)))
        self.assertEqual([r["rating"] for r in listed],
                         ["S", "S", "S", "K-16", "K-18", "", "", "", ""])

    def test_a_runtime_with_no_end_after_the_start_is_left_empty(self):
        a, b = entry("1", "A", "2026-10-09 17:30"), entry("2", "B", "2026-10-10 17:30")
        a["end_date"], b["end_date"] = "2026-10-09 17:30", None
        self.assertEqual([r["len"] for r in self.rows(a, b)[0]], ["", ""])

    def test_an_entry_with_no_usable_film_link_fails_the_site(self):
        """The link is published as given, so one that is not a full https URL with a film
        path on a host the site reads fails the site and the previous files stand."""
        for link in (None, "", "https://biomarilyn.johku.com/", "/sv_SE/a", "/fi_FI/a",
                     "https://biomarilyn.johku.com/fi_FI/",
                     "http://biomarilyn.johku.com/fi_FI/a",
                     "https://evil.example/fi_FI/a",
                     "https://kinovirta.johku.com/fi_FI/a",
                     "https://biomarilyn.johku.com/fi_FI/a?ref=x"):
            with self.subTest(link=link):
                b = entry("2", "B", "2026-10-10 17:30")
                b["storefronturl"] = link
                with self.assertRaises(J.ListingRowError):
                    self.rows(entry("1", "A", "2026-10-09 17:30"), b)

    def test_the_title_is_published_with_its_spacing_collapsed(self):
        """Bio Marilyn's " PäiväKaffiLeffa:Hetki Ennen Valoa" and "Heart of  the Beast"."""
        listed, _ = self.rows(entry("1", " PäiväKaffiLeffa:Hetki Ennen Valoa",
                                    "2026-10-14 14:00"),
                              entry("2", "Heart of  the Beast ", "2026-10-15 19:15"))
        self.assertEqual([r["title"] for r in listed],
                         ["PäiväKaffiLeffa:Hetki Ennen Valoa", "Heart of the Beast"])

    def test_an_entry_with_no_title_fails_the_site(self):
        with self.assertRaises(J.ListingRowError):
            self.rows(entry("1", "A", "2026-10-09 17:30"), entry("2", " ", "2026-10-10 17:30"))


class FilmFactsTest(unittest.TestCase):
    def test_the_info_table_and_the_first_long_paragraph(self):
        f = J.film_facts(film())
        self.assertEqual((f["len"], f["genres"], f["original"]),
                         ("87", "Draama", "Hetki ennen valoa"))
        self.assertEqual(f["syn"], SYN_FI)

    def test_hours_and_minutes(self):
        self.assertEqual(J.film_facts(film(kesto="2 h 30 min"))["len"], "150")

    def test_a_page_with_no_director_or_genre_still_yields_what_it_has(self):
        f = J.film_facts(film(labels=False))
        self.assertEqual((f["genres"], f["original"]), ("", ""))
        self.assertEqual(f["len"], "120")

    def test_a_short_paragraph_is_not_a_synopsis(self):
        self.assertEqual(J.film_facts(film(syn="Tervetuloa!"))["syn"], "")


class FilmLanguageTest(unittest.TestCase):
    """The ways a tenant's film page states its language, read 2026-10-04 and 2026-10-05:
    Bio Forum's sentences, Bio Marilyn's labelled paragraphs, Vihdin Kino's "puhumme
    suomea". Nothing looser is read."""

    def lang(self, *paras):
        page = ('<html><body><div class="product-description__html">'
                + "".join(f"<p>{p}</p>" for p in paras) + "</div></body></html>")
        return J.film_facts(page)["lang"]

    def test_bio_forums_sentence(self):
        self.assertEqual(self.lang(SYN_FI, "Elokuva on puhuttu englanniksi ja tekstitys on "
                                           "sekä suomeksi että ruotsiksi."), "EN-A, FI-S, SV-S")
        self.assertEqual(self.lang("Elokuva on puhuttu suomeksi ja tekstitys on ruotsiksi."),
                         "FI-A, SV-S")
        self.assertEqual(self.lang("Tämä elokuva ja näytös on puhuttu englanniksi ja "
                                   "tekstitys on sekä suomeksi että ruotsiksi."),
                         "EN-A, FI-S, SV-S")

    def test_bio_forums_misspelt_subtitle_word(self):
        """Digger, read 2026-10-05. The typo also stopped the spoken-language part from
        matching, so the page got no language at all. The English sentence says the same
        thing and is not read."""
        self.assertEqual(self.lang(SYN_FI, "Elokuva on puhuttu englanniksi ja teksitys on "
                                           "sekä suomeksi että ruotsiksi.", "*",
                                   "The movie is spoken in English with Finnish and Swedish "
                                   "subtitles."), "EN-A, FI-S, SV-S")

    def test_bio_forums_subtitles_then_speech(self):
        """Pirjo i Sverige, read 2026-10-05."""
        self.assertEqual(self.lang(SYN_FI, "Elokuva on tekstitetty ruotsiksi, puhe suomi.", "*",
                                   "This Finnish comedy is spoken in Finnish with Swedish "
                                   "subtitles."), "FI-A, SV-S")
        self.assertEqual(self.lang("Elokuva on tekstitetty englanniksi."), "EN-S")

    def test_bio_forums_dub_and_its_only_subtitles(self):
        """Vaiana, read 2026-10-05. Here the language sentence is the first paragraph."""
        self.assertEqual(self.lang("Tämä elokuvaesitys on dubattu ruotsinkielelle ja "
                                   "tekstitys on vain ruotsiksi.", SYN_FI, "*"),
                         "SV-A, SV-S")

    def test_bio_forums_film_without_subtitles(self):
        """Lilla Spöket, read 2026-10-05. The first sentence is about the character, so it
        is not used as the film's audio language. That was the maintainer's decision."""
        self.assertEqual(self.lang("Pikku Kummitus Lapanen puhuu ruotsia. Elokuva on ilman "
                                   "tekstitystä.", SYN_FI), "XX-S")

    def test_no_subtitles_is_read_only_with_the_film_as_subject(self):
        self.assertEqual(self.lang("Tämä elokuvanäytös on puhuttu ruotsiksi ja se on ilman "
                                   "tekstitystä."), "SV-A")

    def test_bio_marilyns_labelled_paragraphs(self):
        self.assertEqual(self.lang("Kieli : Alkuperäinen", "Tekstitys: Suomi"), "FI-S")
        self.assertEqual(self.lang("Kieli: englanti", "Tekstitys: suomi ja ruotsi"),
                         "EN-A, FI-S, SV-S")

    def test_bio_marilyns_labelled_no_subtitles(self):
        """Baletti: Pähkinänsärkijä, read 2026-10-04. The label is what makes it the
        statement; the same words inside a sentence stay unread, as above."""
        self.assertEqual(self.lang("Kieli:Alkuper\u00e4inen", "Tekstitys: Ei tekstityst\u00e4"),
                         "XX-S")
        self.assertEqual(self.lang("Kieli: englanti", "Tekstitys: Ei tekstityst\u00e4."),
                         "EN-A, XX-S")
        self.assertEqual(self.lang("Kieli: suomi", "Tekstitys: ei tekstityst\u00e4 alussa"),
                         "FI-A")

    def test_vihdin_kinos_we_speak_finnish(self):
        self.assertEqual(self.lang("MLL Vihdin paikallisyhdistys järjestää Toy Story "
                                   "5-elokuvan näytöksen, lipun hinta vain 2€! Esitetään "
                                   "dubattuna versiona eli puhumme suomea."), "FI-A")

    def test_anything_looser_states_nothing(self):
        for p in (SYN_FI, "Elokuva on puhuttu ruotsiksi ja suomeksi tekstitettynä.",
                  "Dubattu versio.", "Pikku Kummitus Lapanen puhuu ruotsia.", "Puhe suomi.",
                  "Elokuva on ilman tekstitystä täysin ymmärrettävä.",
                  "Kieli: Alkuperäinen"):
            with self.subTest(p=p[:30]):
                self.assertEqual(self.lang(p), "")

    def test_the_row_carries_its_film_pages_language(self):
        page = film().replace("<p>Elokuvateattereissa 4.9.</p>",
                              "<p>Elokuva on puhuttu suomeksi ja tekstitys on ruotsiksi.</p>")
        shows, _ = J.parse(MARILYN, blocks_of(front((1, two_days()))),
                           {"1038": page, "1039": film()}, NOW)
        self.assertEqual([s["lang"] for s in shows["biomarilyn-lapua"]], ["FI-A, SV-S", ""])


class ParseTest(unittest.TestCase):
    def pages(self, **over):
        pages = {"1038": film(), "1039": film(syn=SYN_SV)}
        pages.update(over)
        return pages

    def blocks(self):
        return blocks_of(front((1, two_days())))

    def test_the_synopsis_is_keyed_by_the_language_it_is_written_in(self):
        shows, report = J.parse(MARILYN, self.blocks(), self.pages(), NOW)
        [a, b] = shows["biomarilyn-lapua"]
        self.assertEqual(a["_syn"], {"fi": SYN_FI})
        self.assertEqual(b["_syn"], {"sv": SYN_SV})
        self.assertEqual(report["unplaced"], set())

    def test_a_text_in_no_settled_language_is_withheld_and_counted(self):
        shows, report = J.parse(MARILYN, self.blocks(),
                                self.pages(**{"1039": film(syn=SYN_NO_LANGUAGE)}), NOW)
        self.assertNotIn("_syn", shows["biomarilyn-lapua"][1])
        self.assertEqual(report["unplaced"], {"Filmen"})

    def test_a_row_whose_page_carries_no_director_or_genre_still_publishes(self):
        """A small film that publishes little about itself keeps its place."""
        shows, _ = J.parse(MARILYN, self.blocks(),
                           self.pages(**{"1039": film(labels=False)}), NOW)
        [a, b] = shows["biomarilyn-lapua"]
        self.assertEqual(b["title"], "Filmen")
        self.assertEqual((b["genres"], b["original"]), ("", ""))
        self.assertEqual(b["len"], "87", "the row's own runtime stands")

    def test_a_row_whose_page_was_not_read_publishes_without_its_metadata(self):
        shows, _ = J.parse(MARILYN, self.blocks(), {"1038": film()}, NOW)
        titles = [s["title"] for s in shows["biomarilyn-lapua"]]
        self.assertEqual(titles, ["Hetki ennen valoa", "Filmen"])
        self.assertEqual(shows["biomarilyn-lapua"][1]["genres"], "")
        self.assertNotIn("_syn", shows["biomarilyn-lapua"][1])

    def test_hall_hire_is_left_out_by_its_path(self):
        blocks = blocks_of(front((1, [
            entry("1", "Hetki ennen valoa", "2026-10-09 17:30"),
            entry("2", "Salivaraus", "2026-10-09 19:15", product="94",
                  path="/fi_FI/products/94-kinokulma-salivaraus")])))
        shows, report = J.parse(MARILYN, blocks, self.pages(), NOW)
        self.assertEqual([s["title"] for s in shows["biomarilyn-lapua"]],
                         ["Hetki ennen valoa"])
        self.assertEqual((report["hire"], report["hire_shows"]), ({"Salivaraus"}, 1))

    def test_the_show_shape(self):
        shows, _ = J.parse(MARILYN, self.blocks(), self.pages(), NOW)
        s = shows["biomarilyn-lapua"][0]
        self.assertEqual((s["price"], s["img"], s["soldOut"], s["aud"], s["lang"]),
                         ("", "", False, "", ""))
        self.assertEqual((s["eventId"], s["provider"], s["theatre"]),
                         ("1038", "biomarilyn", "Bio Marilyn"))
        self.assertEqual(s["original"], "Hetki ennen valoa")


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._fetch, self._sleep, self._now = J.fetch, J.time.sleep, J.now
        self.addCleanup(lambda: setattr(J, "fetch", self._fetch))
        self.addCleanup(lambda: setattr(J.time, "sleep", self._sleep))
        self.addCleanup(lambda: setattr(J, "now", self._now))
        J.time.sleep = lambda s: None
        J.now = lambda: NOW
        self.calls = []

    def serve(self, pages):
        def fetch(url, **kw):
            self.calls.append(url)
            body = pages.get(url)
            if isinstance(body, list):
                body = body.pop(0) if len(body) > 1 else body[0]
            if isinstance(body, Exception):
                raise body
            if body is None:
                raise RuntimeError(f"unexpected fetch {url}")
            return body.encode("utf-8")
        J.fetch = fetch

    def main(self, half="all"):
        """`--half all` explicitly, so the run does not depend on where it runs: `half_of`
        reads GITHUB_ACTIONS. The fixture serves every site either way."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["johku", "--half", half])
        return code, out.getvalue() + err.getvalue()

    @staticmethod
    def entries(site, *names, day="2026-10-09"):
        loc = site["venues"][0]["loc"]
        return [entry(f"{site['provider']}-{day}-{i}", n, f"{day} 1{7 + i}:00", loc=loc,
                      product=str(i + 1), host=site["base"])
                for i, n in enumerate(names)]

    def all_sites(self, **over):
        pages = {}
        for site in J.SITES:
            base = site["base"]
            pages[base + "/"] = front((1, self.entries(site, "A", "B")),
                                      shop=site["provider"])
            pages[base + "/fi_FI/a"] = film()
            pages[base + "/fi_FI/b"] = film(syn=SYN_SV)
        pages.update(over)
        return pages

    def keep(self, vid):
        prev = {"generated": "2026-10-01T00:00:00+00:00", "dates": ["2026-10-01"],
                "horizon": "2026-10-01",
                "shows": [{"title": "Old", "start": "2026-10-01T12:00:00+03:00"}]}
        (run.OUT / f"area-{vid}.json").write_text(json.dumps(prev))
        return prev

    def shows(self, vid):
        return json.loads((run.OUT / f"area-{vid}.json").read_text())["shows"]

    def test_all_sites_publish_from_pages_whose_markup_is_a_skeleton(self):
        self.serve(self.all_sites())
        code, log = self.main()
        self.assertEqual(code, 0, log)
        for site in J.SITES:
            shows = self.shows(site["venues"][0]["id"])
            self.assertEqual([s["title"] for s in shows], ["A", "B"], site["provider"])
            self.assertEqual({s["price"] for s in shows}, {""})
        self.assertIn("0 failures", log)

    def marilyn(self, **kw):
        """Bio Marilyn's two blocks, a screening on each of two days."""
        site = MARILYN
        return front((1, self.entries(site, "A", "B")),
                     (9, self.entries(site, "C", day="2026-10-16")), **kw)

    def test_an_incomplete_schedule_is_read_again_until_it_is_whole(self):
        self.serve(self.all_sites(**{"https://www.biomarilyn.com/": [
            self.marilyn(absent=(1, 9)), self.marilyn(absent=(9,)), self.marilyn()]}))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertEqual(self.calls.count("https://www.biomarilyn.com/"), 3)
        self.assertIn("[biomarilyn] the schedule was complete on read 3 of 5", log)
        self.assertEqual([s["title"] for s in self.shows("biomarilyn-lapua")], ["A", "B", "C"])

    def test_an_incomplete_schedule_fails_and_keeps_the_last_good_data(self):
        """Nothing short of the whole schedule replaces the files, and nothing short of
        it is published as an empty programme. The other sites publish."""
        cases = {"fully loading": (self.marilyn(absent=(1, 9)), "loading"),
                 "one block of two": (self.marilyn(absent=(9,)), "loading"),
                 "a failed request": (self.marilyn(failed=(1,)), "error"),
                 "another block count": (self.marilyn(drawn=1), "unmatched"),
                 "no payload": ("<html><body>Bad gateway</body></html>", "missing")}
        for name, (body, state) in cases.items():
            with self.subTest(case=name):
                self.calls = []
                prev = self.keep("biomarilyn-lapua")
                self.serve(self.all_sites(**{"https://www.biomarilyn.com/": [body]}))
                code, log = self.main()
                self.assertEqual(code, 1, log)
                self.assertEqual(self.calls.count("https://www.biomarilyn.com/"),
                                 J.LISTING_TRIES)
                self.assertIn(f"not complete on any of {J.LISTING_TRIES} reads ({state}", log)
                self.assertNotIn("no programme published", log)
                self.assertEqual(json.loads(
                    (run.OUT / "area-biomarilyn-lapua.json").read_text()), prev)
                self.assertEqual(len(self.shows("bioforum-tammisaari")), 2)

    def test_a_plainly_empty_schedule_publishes_the_cinema_empty(self):
        """Every block answered with an empty list: one block at Kinokulma, two at Bio
        Marilyn. Their old screenings leave the page and the run stays green."""
        for vid in ("kinokulma-oulainen", "biomarilyn-lapua"):
            self.keep(vid)
        self.serve(self.all_sites(**{"https://kinokulma.fi/": front((1, []), shop="kinokulma"),
                                     "https://www.biomarilyn.com/": front((1, []), (9, []))}))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertIn("[kinokulma] no programme published", log)
        self.assertIn("[biomarilyn] no programme published", log)
        self.assertEqual(self.shows("kinokulma-oulainen"), [])
        self.assertEqual(self.shows("biomarilyn-lapua"), [])
        self.assertEqual(len(self.shows("bioforum-tammisaari")), 2)

    def test_one_empty_block_beside_a_full_one_is_not_an_empty_programme(self):
        self.serve(self.all_sites(**{"https://www.biomarilyn.com/": front(
            (1, []), (9, self.entries(MARILYN, "A", "B")))}))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertEqual([s["title"] for s in self.shows("biomarilyn-lapua")], ["A", "B"])

    def test_entries_with_no_screening_still_to_come_fail_and_keep_the_file(self):
        """Coming-soon entries and a screening that has started are not an empty
        programme: the page still lists films."""
        prev = self.keep("vihdinkino-vihti")
        site = next(s for s in J.SITES if s["provider"] == "vihdinkino")
        soon, started = self.entries(site, "Soon", "Started")
        soon["upcoming"], started["start_date"] = "1", "2026-10-09 11:00"
        self.serve(self.all_sites(**{"https://vihdinkino.fi/": front(
            (1, [soon, started]), shop="vihdinkino")}))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("2 schedule entries and none a timed screening still to come", log)
        self.assertEqual(json.loads((run.OUT / "area-vihdinkino-vihti.json").read_text()),
                         prev)

    def test_the_reads_are_paced(self):
        waits = []
        J.time.sleep = waits.append
        self.serve(self.all_sites(**{"https://kinokulma.fi/": [
            front((1, []), shop="kinokulma", absent=(1,))]}))
        self.main()
        self.assertEqual(waits.count(J.LISTING_WAIT), J.LISTING_TRIES - 1)

    def test_a_schedule_of_nothing_but_hall_hire_fails_that_site(self):
        self.serve(self.all_sites(**{"https://bioforum.fi/": front((1, [
            entry("1", "Salivaraus", "2026-10-09 17:30", loc="Bio Forum", product="94",
                  path="/fi_FI/products/94-sali", host="https://bioforum.fi"),
            entry("2", "Salivaraus 2", "2026-10-10 19:15", loc="Bio Forum", product="95",
                  path="/fi_FI/products/95-sali", host="https://bioforum.fi")]),
            shop="bioforum")}))
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("template failure", log)
        self.assertFalse((run.OUT / "area-bioforum-tammisaari.json").exists())
        self.assertTrue((run.OUT / "area-vihdinkino-vihti.json").exists())

    def test_a_film_page_that_fails_still_publishes_its_screenings(self):
        """The page carries metadata, not the decision to publish."""
        self.serve(self.all_sites(**{
            "https://vihdinkino.fi/fi_FI/a": RuntimeError("HTTP Error 503")}))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        shows = self.shows("vihdinkino-vihti")
        self.assertEqual([s["title"] for s in shows], ["A", "B"])
        self.assertEqual(shows[0]["genres"], "")

    def test_the_hall_hire_page_is_never_fetched(self):
        """It is dropped before the film pages are chosen, so the request is not made."""
        site = next(s for s in J.SITES if s["provider"] == "kinokulma")
        [a] = self.entries(site, "A")
        self.serve(self.all_sites(**{"https://kinokulma.fi/": front((1, [
            a, entry("9", "Salivaraus", "2026-10-09 20:00", loc="Kulmasali", product="94",
                     host=site["base"], path="/fi_FI/products/94-kinokulma-salivaraus")]),
            shop="kinokulma")}))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertEqual([c for c in self.calls if "/products/" in c], [])
        self.assertIn("hall-hire", log)

    def test_one_film_page_per_distinct_product(self):
        self.serve(self.all_sites())
        self.assertEqual(self.main()[0], 0)
        films = [c for c in self.calls if "/fi_FI/" in c]
        self.assertEqual(sorted(films), sorted(set(films)))
        self.assertEqual(len(films), 12)      # six storefronts, two films each


class KinoHannikainenTest(unittest.TestCase):
    """The sixth storefront, Nurmes, added 2026-09-20.

    Read that day: eight rows over five day groups, every one carrying
    `data-location="Hannikaisen sali"`, which is the hall the registry declares and the
    one the 250-seat auditorium in Nurmes-talo is named. The listing is served from the
    cinema's own domain rather than from `johku.com`, so the site keeps a pacing group of
    its own.
    """

    SITE = next(s for s in J.SITES if s["provider"] == "kinohannikainen")

    def test_the_hall_the_rows_carry_is_the_declared_venue(self):
        host = "https://www.kinohannikainen.net"
        blocks = blocks_of(front((6, [
            entry("1", "Rakkautta ja virtahepoja", "2026-10-09 17:00", minutes=101,
                  loc="Hannikaisen sali", product="1", host=host),
            entry("2", "MYRSKYN IKKUNA", "2026-10-10 19:30", minutes=100,
                  loc="Hannikaisen sali", product="2", host=host)]),
            shop="kinohannikainen"))
        shows, _ = J.parse(self.SITE, blocks, {}, NOW)
        self.assertEqual(list(shows), ["kinohannikainen-nurmes"])
        rows_ = shows["kinohannikainen-nurmes"]
        self.assertEqual([s["title"] for s in rows_],
                         ["Rakkautta ja virtahepoja", "MYRSKYN IKKUNA"])
        self.assertEqual([s["start"] for s in rows_],
                         ["2026-10-09T17:00:00+03:00", "2026-10-10T19:30:00+03:00"])
        self.assertEqual({s["theatre"] for s in rows_}, {"Kino Hannikainen"})
        self.assertTrue(all(s["url"].startswith("https://www.kinohannikainen.net/fi_FI/")
                            for s in rows_))

    def test_the_listing_is_read_from_the_cinemas_own_domain(self):
        """`johku.com` is the platform, not the host any site is read from. A base there
        would share one pacing group with every other site on it."""
        self.assertEqual(self.SITE["base"], "https://www.kinohannikainen.net")
        self.assertNotIn("johku.com", self.SITE["base"])
        self.assertNotIn("reads", self.SITE)


class KinoVirtaTest(unittest.TestCase):
    """The seventh storefront, Kalajoki, added 2026-09-20.

    The one site read from `johku.com` itself: the cinema has no storefront domain, and
    virtasali.fi, the municipal hall's own WordPress page, sends every ticket button here.
    Read that day: four rows over two day groups, all `data-location="Virta-sali"`.
    """

    SITE = next(s for s in J.SITES if s["provider"] == "kinovirta")

    def test_the_hall_the_rows_carry_is_the_declared_venue(self):
        host = self.SITE["base"]
        blocks = blocks_of(front((2, [
            entry("1", "Presidentin Kyyditys", "2026-10-09 18:00", loc="Virta-sali",
                  product="1", host=host),
            entry("2", "Resident Evil", "2026-10-09 19:40", loc="Virta-sali",
                  product="2", host=host)]), shop="kinovirta"))
        shows, _ = J.parse(self.SITE, blocks, {}, NOW)
        self.assertEqual(list(shows), ["kinovirta-kalajoki"])
        rows_ = shows["kinovirta-kalajoki"]
        self.assertEqual([s["start"] for s in rows_],
                         ["2026-10-09T18:00:00+03:00", "2026-10-09T19:40:00+03:00"])
        self.assertEqual({s["theatre"] for s in rows_}, {"Kino Virta"})

    def test_it_is_the_only_site_read_from_the_platform_domain(self):
        """Every other storefront answers on the cinema's own host. A second site on
        johku.com would share this one's pacing group, which is correct and has to be
        deliberate rather than a copied base."""
        on_platform = [s["provider"] for s in J.SITES if "johku.com" in s["base"]]
        self.assertEqual(on_platform, ["kinovirta"])
        self.assertEqual(self.SITE["base"], "https://kinovirta.johku.com")


class RegistryTest(unittest.TestCase):
    def test_the_cloud_registry_entries(self):
        for pid, label, host, city in (
                ("biomarilyn", "Bio Marilyn", "biomarilyn.com", "Lapua"),
                ("vihdinkino", "Vihdin Kino", "vihdinkino.fi", "Vihti"),
                ("bioforum", "Bio Forum", "bioforum.fi", "Tammisaari"),
                ("kinokulma", "Kinokulma", "kinokulma.fi", "Oulainen"),
                ("kinohannikainen", "Kino Hannikainen", "kinohannikainen.net", "Nurmes"),
                ("kinovirta", "Kino Virta", "kinovirta.johku.com", "Kalajoki")):
            with self.subTest(provider=pid):
                p = registry.by_id(pid)
                self.assertEqual((p["label"], p["host"], p["book"], p["module"],
                                  p["where"]), (label, host, "buy", "johku", "cloud"))
                self.assertEqual(sum(1 for q in registry.PROVIDERS
                                     if q["accent"] == p["accent"]), 1)
                site = next(s for s in J.SITES if s["provider"] == pid)
                self.assertEqual(site["venues"][0]["city"], city)

    def test_the_venue_name_matches_the_chain_label(self):
        """`build_pages.label_of` concatenates the two when the venue name does not start
        with the chain word, which put the town in the page slug twice."""
        for site in J.SITES:
            with self.subTest(provider=site["provider"]):
                label = registry.by_id(site["provider"])["label"]
                self.assertTrue(site["venues"][0]["name"].startswith(label))

    def test_bio_marilyn_and_kino_marilyn_are_two_cinemas(self):
        """Loviisa's is on its own site and its own module."""
        self.assertNotEqual(registry.by_id("biomarilyn")["host"],
                            registry.by_id("kinomarilyn")["host"])
        self.assertNotEqual(registry.by_id("biomarilyn")["module"],
                            registry.by_id("kinomarilyn")["module"])

    def test_each_site_names_the_host_it_reads_and_they_are_paced_apart(self):
        self.assertEqual([s["base"] for s in J.SITES],
                         ["https://www.biomarilyn.com", "https://vihdinkino.fi",
                          "https://bioforum.fi", "https://kinokulma.fi",
                          "https://www.kinohannikainen.net",
                          "https://kinovirta.johku.com"])
        self.assertEqual(len(run.host_groups(J.SITES)), 6)

    def test_kino_engel_and_kino_tapiola_stay_on_their_own_modules(self):
        """The widget is not the storefront; those two keep their own parsers."""
        self.assertEqual(registry.by_id("engel")["module"], "engel")
        self.assertEqual(registry.by_id("tapiola")["module"], "tapiola")


if __name__ == "__main__":
    unittest.main()
