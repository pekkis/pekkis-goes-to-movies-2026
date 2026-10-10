"""BioRex: the admin-ajax fragment, the film pages, and the guard against another venue's
programme. biorex.py was at 43% coverage with no test file of its own (audit, 2026-09-25);
the parse tests below cover the paths the committed rows exercise, over two venues.

Venue selection is a cookie: POST the location, then ask admin-ajax, which answers
BioRex Verkatehdas's programme whenever the cookie did not take. The guard compared the
data layer's `showCinemaName` with the venue and fell back to the venue's own name when
the field was missing, so with the field gone and the cookie failing, Verkatehdas's
programme would publish under all twelve venues (audit A8, 2026-09-25).

The fixture is the item shape `test_show_contract.sample_biorex` uses, the data layer JSON
attribute-escaped as WordPress prints it.
"""
import contextlib
import html
import io
import json
import unittest
import urllib.parse

import _ctx                                                # noqa: F401
import biorex as B

TRIPLA, VERKA = B.VENUES[0], B.VENUES[2]


def item(show_id, when, cinema, place=True, field=True, title="Autofiktio", fmt="EN"):
    dl = {"movieId": 4711, "movieName": title, "showId": show_id, "showDateTime": when}
    if field:
        dl["showCinemaName"] = cinema
    dl = html.escape(json.dumps(dl), quote=True)
    return ('<div class="showtime-item ">'
            f'<div data-click-data-layer="{dl}"><a\nhref="https://biorex.fi/secure-redirect/{show_id}"\n'
            'class="x">Osta</a></div>'
            + (f'<div class="showtime-item__place__value">{cinema}, Sali 6</div>' if place else "")
            + '<span class="showtime-item__movie-rating">(K-16)</span>'
            f'<span class="showtime-item__format">{fmt}</span>'
            '<a class="showtime-item__movie-name" href="https://biorex.fi/elokuva/autofiktio/">'
            f'{title}</a></div>')


class Upstream:
    """biorex.fi as fetch_venue sees it: a location cookie that takes or not, and one
    admin-ajax answer per location, Verkatehdas's when the cookie did not take."""

    def __init__(self, posts, cookie=True):
        self.posts, self.cookie, self.location = posts, cookie, None

    def fetch(self, url, **kw):
        return b"<html></html>"

    def post(self, op, url, data):
        if url.endswith("/teatterin-valinta/"):
            self.location = data["location"] if self.cookie else None
            return b""
        pid = self.location or VERKA["providerId"]
        return json.dumps({"posts": self.posts.get(pid, "")}).encode()


class GuardTest(unittest.TestCase):
    VENUES = [TRIPLA, VERKA]

    def run_site(self, up):
        saved = (B.fetch, B._post, B.VENUES)
        B.fetch, B._post, B.VENUES = up.fetch, up.post, self.VENUES
        self.addCleanup(lambda: (setattr(B, "fetch", saved[0]), setattr(B, "_post", saved[1]),
                                 setattr(B, "VENUES", saved[2])))
        with contextlib.redirect_stdout(io.StringIO()):
            return B.fetch_site(sleep=0, with_meta=False)

    def posts(self, **kw):
        return {TRIPLA["providerId"]: item(1, "2026-09-26T18:00:00+03:00", TRIPLA["name"], **kw),
                VERKA["providerId"]: item(2, "2026-09-26T19:00:00+03:00", VERKA["name"], **kw)}

    def test_each_venue_publishes_its_own_programme(self):
        out = self.run_site(Upstream(self.posts()))
        self.assertEqual({k: [s["url"][-1] for s in v] for k, v in out.items()},
                         {TRIPLA["id"]: ["1"], VERKA["id"]: ["2"]})

    def test_a_failed_cookie_fails_the_site(self):
        with self.assertRaisesRegex(RuntimeError, "cookie"):
            self.run_site(Upstream(self.posts(), cookie=False))

    def test_the_place_line_still_catches_it_when_the_field_is_gone(self):
        """The case the old guard passed: no `showCinemaName`, so every show named the
        venue it was asked for."""
        with self.assertRaisesRegex(RuntimeError, "cookie"):
            self.run_site(Upstream(self.posts(field=False), cookie=False))

    def test_a_programme_naming_no_cinema_at_all_fails_the_site(self):
        with self.assertRaisesRegex(RuntimeError, "names no cinema"):
            self.run_site(Upstream(self.posts(field=False, place=False)))

    def test_without_the_field_the_place_line_verifies_the_right_venue(self):
        out = self.run_site(Upstream(self.posts(field=False)))
        self.assertEqual(sorted(out), sorted([TRIPLA["id"], VERKA["id"]]))
        self.assertEqual(out[TRIPLA["id"]][0]["theatre"], TRIPLA["name"])


if __name__ == "__main__":
    unittest.main()


def rich_item(show_id, when, cinema, room, formats, rating="(K-12)", title="Autofiktio"):
    """An item with everything the committed rows carry: several format spans, the rating,
    a room that may state a door limit, a srcset and the film link."""
    dl = html.escape(json.dumps({"movieId": 4711, "movieName": title, "showId": show_id,
                                 "showCinemaName": cinema, "showDateTime": when}), quote=True)
    spans = "".join(f'<span class="showtime-item__format">{f}</span>' for f in formats)
    return ('<div class="showtime-item ">'
            f'<div data-click-data-layer="{dl}"><a\nhref="https://biorex.fi/secure-redirect/{show_id}"\n'
            'class="x">Osta</a></div>'
            f'<div class="showtime-item__place__value">{cinema}, {room}</div>'
            f'<span class="showtime-item__movie-rating">{rating}</span>{spans}'
            '<img data-srcset="https://biorex.fi/p/a-200.jpg 200w, https://biorex.fi/p/a-600.jpg 600w,'
            ' https://biorex.fi/p/a-400.jpg 400w">'
            '<a class="showtime-item__movie-name" href="https://biorex.fi/elokuva/autofiktio/">'
            f'{title}</a></div>')


SEINAJOKI = next(v for v in B.VENUES if v["id"] == "br-seinajoki")


class ParseTest(unittest.TestCase):
    """The parse paths the committed BioRex rows exercise (2026-09-25): tags ahead of the
    language codes ("Anniskelu · Plus", "EN-A, FI-S, SV-S" on 634 rows), a door limit in the
    room name ("2 REX (K-18)" on 31 rows), the rating in brackets, and the widest poster."""

    def test_tags_come_before_the_language_codes(self):
        s = B.parse(rich_item(1, "2026-09-26T18:00:00+03:00", TRIPLA["name"], "Sali 3",
                              ["Anniskelu", "Plus", "EN", "FI&SV"]), TRIPLA)[0]
        self.assertEqual((s["method"], s["lang"]), ("Anniskelu · Plus", "EN-A, FI-S, SV-S"))
        self.assertEqual((s["rating"], s["age"], s["aud"]), ("K-12", "", "Sali 3"))

    def test_a_door_limit_in_the_room_is_the_screenings_age_and_leaves_the_room(self):
        s = B.parse(rich_item(2, "2026-09-26T21:00:00+03:00", SEINAJOKI["name"],
                              "2 REX (K-18)", ["FI"]), SEINAJOKI)[0]
        self.assertEqual((s["age"], s["aud"], s["lang"], s["method"]),
                         ("K-18", "2 REX", "FI-A", ""))

    def test_the_rest_of_the_row(self):
        s = B.parse(rich_item(3, "2026-09-26T18:00:00+03:00", TRIPLA["name"], "Sali 1",
                              ["FI"], rating=""), TRIPLA)[0]
        self.assertEqual(s["rating"], "")
        self.assertEqual(s["img"], "https://biorex.fi/p/a-600.jpg", "the widest candidate")
        self.assertEqual(s["url"], "https://biorex.fi/secure-redirect/3")
        self.assertEqual(s["movieUrl"], "https://biorex.fi/elokuva/autofiktio/")
        self.assertEqual((s["theatre"], s["venue"], s["provider"], s["eventId"]),
                         (TRIPLA["name"], TRIPLA["id"], "biorex", "4711"))

    def test_an_item_with_no_start_or_an_unreadable_data_layer_is_skipped(self):
        broken = item(4, "", TRIPLA["name"]) + item(5, "2026-09-26T18:00:00+03:00",
                                                     TRIPLA["name"]).replace(
            'data-click-data-layer="', 'data-click-data-layer="{')
        self.assertEqual(B.parse(broken, TRIPLA), [])


FILM_PAGE = ('<div class="movie-description__synopsis x">Pedro Almodóvarin <b>melodraama</b>.</div>'
             '<span>Kesto:</span> 1 h 52 m <span>Genre:</span> Draama, Komedia <')


class FilmMetaTest(unittest.TestCase):

    def test_the_film_page_supplies_synopsis_runtime_and_genres(self):
        saved = B.fetch
        B.fetch = lambda url, **kw: FILM_PAGE.encode()
        self.addCleanup(lambda: setattr(B, "fetch", saved))
        self.assertEqual(B.film_meta("https://biorex.fi/elokuva/autofiktio/"),
                         {"syn": "Pedro Almodóvarin melodraama .", "len": "112",
                          "genres": "Draama, Komedia"})

    def test_the_metadata_reaches_every_screening_at_both_venues(self):
        up = Upstream({TRIPLA["providerId"]: rich_item(1, "2026-09-26T18:00:00+03:00",
                                                       TRIPLA["name"], "Sali 1", ["FI"]),
                       VERKA["providerId"]: rich_item(2, "2026-09-27T18:00:00+03:00",
                                                      VERKA["name"], "Sali 2", ["FI"])})
        pages = []

        def fetch(url, **kw):
            if "/elokuva/" in url:
                pages.append(url)
                return FILM_PAGE.encode()
            return up.fetch(url)
        saved = (B.fetch, B._post, B.VENUES)
        B.fetch, B._post, B.VENUES = fetch, up.post, [TRIPLA, VERKA]
        self.addCleanup(lambda: (setattr(B, "fetch", saved[0]), setattr(B, "_post", saved[1]),
                                 setattr(B, "VENUES", saved[2])))
        with contextlib.redirect_stdout(io.StringIO()):
            out = B.fetch_site(sleep=0)
        self.assertEqual(len(pages), 1, "one film page per film, not per screening")
        for vid in (TRIPLA["id"], VERKA["id"]):
            s = out[vid][0]
            self.assertEqual((s["len"], s["genres"], s["_syn"]),
                             ("112", "Draama, Komedia", "Pedro Almodóvarin melodraama ."))
