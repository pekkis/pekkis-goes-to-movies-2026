"""Room-split venues on one Nexxo locationid: who owns which rows, and what gets loud.

Kino Metso is five towns published as rooms of kinoaurora.fi's locationid 2. A venue
entry with a `rooms` list owns the rows whose roomId is in it; rows nobody owns must
be announced in the log rather than silently unpublished, because that is how a new
town first appears -- Tikkakoski arrived between two probes of the same endpoint.
Matching is on roomId, not roomTitle: the id is what KSEK's own per-town pages filter
on, and a title is one wording change from silently dropping a town.
"""
import contextlib
import io
import unittest

import _ctx                                                # noqa: F401
import common
import nexxo


def row(room_id, room_title, title="Film", start="2026-09-02 18:00:00"):
    return {"movieId": "9", "movieTitle": title, "roomId": room_id,
            "roomTitle": room_title, "startDate": start[:10], "startTime": start,
            "duration": "90", "ageLimit": "7"}


PAYLOAD = {"shows": {"2026-09-02": [
    row(2, "Muurame", "Film A"),
    row(21, "Riihivuori", "Film B"),
    row(4, "Petäjävesi", "Film C"),
    row(12, "Vaajakoski", "Film D"),
    row(19, "Hankasalmi", "Film E"),
    row(19, "Hankasalmi", "Film F", "2026-09-03 18:00:00"),
]}}

SITE = {"provider": "kinometso", "base": "https://api.example",
        "site": "https://pages.example", "programme": "/kino-metso/", "venues": [
            {"id": "km-muurame", "locationid": "2", "rooms": ["2", "21"],
             "page": "/kino-metso/muurame/", "name": "Muurame",
             "short": "Muurame", "city": "Muurame"},
            {"id": "km-petajavesi", "locationid": "2", "rooms": ["4"],
             "page": "/kino-metso/petajavesi/", "name": "Petäjävesi",
             "short": "Petäjävesi", "city": "Petäjävesi"},
        ]}

PLAIN_VENUE = {"id": "x", "locationid": "1", "name": "Kino X",
               "short": "Kino X", "city": "X"}


class RoomSplitTest(unittest.TestCase):
    def test_a_roomed_venue_owns_exactly_its_rooms(self):
        shows = nexxo.parse(PAYLOAD, SITE, SITE["venues"][0])
        self.assertEqual(sorted(s["title"] for s in shows), ["Film A", "Film B"])
        shows = nexxo.parse(PAYLOAD, SITE, SITE["venues"][1])
        self.assertEqual([s["title"] for s in shows], ["Film C"])

    def test_matching_is_on_the_id_not_the_title(self):
        """A retitled room still lands with its venue; a same-titled row under a
        different id does not."""
        p = {"shows": {"d": [row(2, "Muuramesali", "Renamed"),
                             row(99, "Muurame", "Impostor")]}}
        shows = nexxo.parse(p, SITE, SITE["venues"][0])
        self.assertEqual([s["title"] for s in shows], ["Renamed"])

    def test_the_home_room_vanishes_from_aud_and_a_sibling_room_stays(self):
        """"Muurame" repeats the venue and says nothing; "Riihivuori" is a different
        place inside the same venue and the reader needs it."""
        shows = nexxo.parse(PAYLOAD, SITE, SITE["venues"][0])
        by_title = {s["title"]: s for s in shows}
        self.assertEqual(by_title["Film A"]["aud"], "")
        self.assertEqual(by_title["Film B"]["aud"], "Riihivuori")

    def test_a_venue_without_rooms_takes_everything(self):
        shows = nexxo.parse(PAYLOAD, SITE, PLAIN_VENUE)
        self.assertEqual(len(shows), 6)

    def test_a_venue_page_is_the_link_and_carries_no_location_query(self):
        shows = nexxo.parse(PAYLOAD, SITE, SITE["venues"][0])
        self.assertEqual(shows[0]["url"], "https://pages.example/kino-metso/muurame/")

    def test_a_pageless_venue_keeps_the_programme_link(self):
        shows = nexxo.parse(PAYLOAD, SITE, PLAIN_VENUE)
        self.assertEqual(shows[0]["url"], "https://pages.example/kino-metso/?location=1")


class ConfirmedEmptyEvidenceTest(unittest.TestCase):
    """EMPTY_VENUES_CONFIRMED lets run.py read this adapter's [] as a pending
    programme, so [] must only ever mean evidence. Rows that exist but cannot be
    parsed have to raise: a renamed startTime would otherwise wipe every row and the
    wipe would read as a quiet 'no programme yet', forever."""

    def test_rows_with_dead_start_fields_raise_instead_of_reading_empty(self):
        broken = dict(row(2, "Muurame", "Renamed Field"))
        del broken["startTime"]
        p = {"shows": {"d": [broken]}}
        with self.assertRaises(RuntimeError) as cm:
            nexxo.parse(p, SITE, SITE["venues"][0])
        self.assertIn("parser break", str(cm.exception))

    def test_a_malformed_start_raises_too(self):
        bad = dict(row(2, "Muurame"), startTime="26.10.2026 klo 18")
        with self.assertRaises(RuntimeError):
            nexxo.parse({"shows": {"d": [bad]}}, SITE, SITE["venues"][0])

    def test_upcoming_only_rows_are_a_confirmed_empty(self):
        """The payload itself marks a row that legitimately has no scheduled showtime;
        a venue whose whole listing is unscheduled premieres is genuinely not showing
        anything yet."""
        up = dict(row(2, "Muurame"), startTime="", isUpcoming="1")
        up2 = dict(row(2, "Muurame", "Second"), startTime="", isUpcoming="1")
        self.assertEqual(nexxo.parse({"shows": {"d": [up, up2]}},
                                     SITE, SITE["venues"][0]), [])

    def test_a_truly_empty_payload_is_a_confirmed_empty(self):
        self.assertEqual(nexxo.parse({"shows": {}}, SITE, SITE["venues"][0]), [])

    def test_a_room_filtered_venue_with_no_owned_rows_is_a_confirmed_empty(self):
        """Someone else's rows in the payload are not this venue's problem -- the
        Tikkakoski case, where every current row belongs to other towns."""
        p = {"shows": {"d": [row(4, "Petäjävesi"), row(12, "Vaajakoski")]}}
        self.assertEqual(nexxo.parse(p, SITE, SITE["venues"][0]), [])

    def test_one_broken_row_among_parseable_ones_does_not_raise(self):
        """The guard fires on a total wipe, where 'empty' would be a lie. A single
        malformed row in an otherwise live listing is dropped, as before -- killing a
        venue over one bad row would trade a metadata bug for missing showtimes."""
        good = row(2, "Muurame", "Good")
        bad = dict(row(2, "Muurame", "Bad"))
        del bad["startTime"]
        shows = nexxo.parse({"shows": {"d": [good, bad]}}, SITE, SITE["venues"][0])
        self.assertEqual([s["title"] for s in shows], ["Good"])


class RenumberedRoomTest(unittest.TestCase):
    """The site-wide verdict, where parse() cannot see the other venues. One town with no
    owned rows while another has some is a town between visits. Rows in the payload that
    no configured room owns at all is the roomIds having moved, and every venue coming
    back [] from that must not read as the site having nothing on."""

    def fetch(self, payload):
        real = nexxo.fetch_payload
        nexxo.fetch_payload = lambda site, loc, **kw: payload
        self.addCleanup(lambda: setattr(nexxo, "fetch_payload", real))
        with contextlib.redirect_stdout(io.StringIO()):
            return nexxo.fetch_site(SITE, sleep=0)

    def test_rows_that_no_configured_room_owns_fail_the_site(self):
        moved = {"shows": {"2026-09-02": [row(102, "Muurame", "Film A"),
                                          row(104, "Petäjävesi", "Film C")]}}
        with self.assertRaises(RuntimeError) as cm:
            self.fetch(moved)
        self.assertNotIsInstance(cm.exception, common.EmptyProgramme)
        self.assertIn("102", str(cm.exception))

    def test_one_town_between_visits_is_a_confirmed_empty_beside_the_other(self):
        out = self.fetch({"shows": {"d": [row(2, "Muurame", "Film A"),
                                          row(21, "Riihivuori", "Film B")]}})
        self.assertEqual(sorted(s["title"] for s in out["km-muurame"]), ["Film A", "Film B"])
        self.assertEqual(out["km-petajavesi"], [])

    def test_a_venue_without_rooms_on_the_locationid_leaves_nothing_orphaned(self):
        """A plain venue takes every row, so no roomId can be orphaned beside it."""
        moved = {"shows": {"d": [row(102, "Muurame"), row(104, "Petäjävesi")]}}
        self.assertEqual(nexxo.orphaned(moved, [PLAIN_VENUE, SITE["venues"][0]]), 0)
        self.assertEqual(nexxo.orphaned(moved, SITE["venues"]), 2)

    def test_an_empty_payload_on_a_room_split_site_is_an_empty_programme(self):
        with self.assertRaises(common.EmptyProgramme):
            self.fetch({"shows": {}})

    def test_a_town_whose_room_alone_moved_is_not_confirmed_empty(self):
        """Muurame still matches and Petäjävesi's rows arrive under room 104. Its []
        would be vouched empty while its screenings sit in the unclaimed line, so it is
        left out and run.py keeps its previous file."""
        out = self.fetch({"shows": {"2026-09-02": [
            row(2, "Muurame", "Film A"), row(21, "Riihivuori", "Film B"),
            row(104, "Petäjävesi", "Film C"), row(104, "Petäjävesi", "Film D")]}})
        self.assertEqual(sorted(s["title"] for s in out["km-muurame"]), ["Film A", "Film B"])
        self.assertNotIn("km-petajavesi", out)

    def test_an_empty_town_beside_rows_nobody_owns_is_not_confirmed_either(self):
        """A new town publishing while a configured one is between visits reads the same
        as a moved room: rows are there that could be this town's."""
        out = self.fetch({"shows": {"d": [row(2, "Muurame", "Film A"),
                                          row(19, "Hankasalmi", "Film E"),
                                          row(19, "Hankasalmi", "Film F")]}})
        self.assertEqual([s["title"] for s in out["km-muurame"]], ["Film A"])
        self.assertNotIn("km-petajavesi", out)


class UnclaimedRoomTest(unittest.TestCase):
    def test_rows_nobody_owns_are_counted_by_room(self):
        got = nexxo.unclaimed(PAYLOAD, SITE["venues"])
        self.assertEqual(got, {("19", "Hankasalmi"): 2, ("12", "Vaajakoski"): 1})

    def test_a_plain_site_reports_nothing(self):
        """One venue that takes everything leaves nothing to claim; the guard exists
        only where rooms partition a location."""
        self.assertEqual(nexxo.unclaimed(PAYLOAD, [PLAIN_VENUE]), {})

    def test_a_fully_claimed_payload_is_quiet(self):
        p = {"shows": {"d": [row(2, "Muurame"), row(4, "Petäjävesi")]}}
        self.assertEqual(nexxo.unclaimed(p, SITE["venues"]), {})


if __name__ == "__main__":
    unittest.main()
