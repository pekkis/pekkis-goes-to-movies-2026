"""Savon Kinot reports a room as the venue repeated inside its own room name.

`TAPIO | TAPIO 4` reached the app and the pages verbatim, beside a venue label that
already said Tapio. Verbatim is right for the other eighteen eTiketti sites, so the fix
is a per-site normaliser. On 2026-09-01, 127 of Savon Kinot's 157 showtimes carried a
piped `aud` across 11 values and six venues; every one is exercised here against the
venue `short` the registry gives it. Leffabuumi pipes too (`KINOLINNA | SALI 1`) and
means a real room, so it does not opt in, and a test says so.

Cine is the second site to opt in (2026-09-07), in the unpiped shape: it prints the town
as the place and the cinema again as the room. The gating checks below run over every
opted-in site, so a third opt-in is covered on the day it is added.
"""
import importlib
import json
import unittest

import _ctx                                                # noqa: F401


def load():
    """Import etiketti here rather than at module level, and it matters.

    `etiketti` does `from common import EmptyProgramme`, which captures the class object
    at import time. `tests/test_common_fetch.py` calls `importlib.reload(common)` to get
    fresh throttle counters, and that builds a *new* EmptyProgramme on the same module.
    Any provider module imported before that reload is left holding the old class, and
    `test_empty_programme` then fails to catch what `fetch_site` raises.

    So the suite's result depends on when a provider module is first imported. Importing
    at the top of this file moved etiketti ahead of the reload and turned three unrelated
    tests red -- the first thing a new test file here is likely to trip over. Recorded in
    docs/archive/2026-09-gotchas.md as its own defect; this import keeps the ordering the
    rest of the suite already relies on.
    """
    return importlib.import_module("etiketti")


def optedin_sites():
    """Every site the flag is on for."""
    return [s for s in load().SITES if s.get("aud_repeats_venue")]


def site_of(provider):
    return next(s for s in load().SITES if s["provider"] == provider)

# The 11 distinct values in the committed data, with the venue each belongs to and what
# the page should say. Written out rather than derived, so the intent is reviewable.
EXPECTED = [
    ("TAPIO | TAPIO 1", "Tapio", "Sali Tapio 1"),
    ("TAPIO | TAPIO 2", "Tapio", "Sali Tapio 2"),
    ("TAPIO | TAPIO 3", "Tapio", "Sali Tapio 3"),
    ("TAPIO | TAPIO 4", "Tapio", "Sali Tapio 4"),
    ("MAXIM | MAXIM 1", "Maxim", "Sali Maxim 1"),
    ("MAXIM | MAXIM 2", "Maxim", "Sali Maxim 2"),
    ("MAXIM | MAXIM 3", "Maxim", "Sali Maxim 3"),
    ("KUVALIPAS | KUVALIPAS", "Kuvalipas", ""),
    ("KUVALINNA", "Kuvalinna", ""),
    ("KILLA", "Killa", ""),
    ("KINO-HOVI", "Kino-Hovi", ""),
]

# Cine prints one field where Savon Kinot prints two, and it is the cinema again:
# `KERAVA | CINE KEUDA-TALO` reaches PLACE_RE as place "KERAVA" and aud
# "CINE KEUDA-TALO". Read live from kiertue.cine.fi on 2026-09-07, both venues.
CINE_EXPECTED = [
    ("CINE KEUDA-TALO", "Cine Keuda-Talo", ""),
    ("CINE NIKKIL\u00c4", "Cine Nikkil\u00e4", ""),
]


class NormaliseAudTest(unittest.TestCase):
    def test_every_value_in_the_committed_data_maps_as_intended(self):
        for raw, short, want in EXPECTED:
            with self.subTest(raw=raw):
                self.assertEqual(load().normalise_aud(raw, short), want)

    def test_every_cine_value_in_the_live_read_maps_as_intended(self):
        for raw, short, want in CINE_EXPECTED:
            with self.subTest(raw=raw):
                self.assertEqual(load().normalise_aud(raw, short), want)

    def test_the_reported_case(self):
        self.assertEqual(load().normalise_aud("TAPIO | TAPIO 4", "Tapio"),
                         "Sali Tapio 4")

    def test_none_of_the_shapes_the_report_ruled_out(self):
        """No pipe left in it, no doubled venue, no doubled Sali."""
        for raw, short, _ in EXPECTED:
            got = load().normalise_aud(raw, short)
            with self.subTest(raw=raw):
                self.assertNotIn("|", got)
                self.assertNotIn(f"{short} {short}", got)
                self.assertNotIn("Sali Sali", got)

    def test_a_room_already_called_sali_is_not_prefixed_again(self):
        """`KINOLINNA | SALI 1` is Leffabuumi's shape and does not reach this function,
        but a future site could. Prefixing blindly would read "Sali SALI 1"."""
        self.assertEqual(load().normalise_aud("KINOLINNA | SALI 1", "Kinolinna"),
                         "SALI 1")

    def test_a_room_with_its_own_name_survives(self):
        """Only `VENUE n` is rewritten. Anything else is a real room name and is passed
        through, so an unrecognised room reaches the page looking odd rather than being
        silently dropped."""
        self.assertEqual(load().normalise_aud("TAPIO | VIP", "Tapio"), "VIP")
        self.assertEqual(load().normalise_aud("TAPIO | Parvi", "Tapio"), "Parvi")

    def test_the_casing_comes_from_the_registry(self):
        """`short` is the source of "Tapio", so nothing here has to decide how a Finnish
        name is capitalised. Feeding it a differently-cased short proves the input is not
        being title-cased instead."""
        self.assertEqual(load().normalise_aud("TAPIO | TAPIO 4", "TaPiO"),
                         "Sali TaPiO 4")

    def test_empty_and_whitespace_stay_empty(self):
        self.assertEqual(load().normalise_aud("", "Tapio"), "")
        self.assertEqual(load().normalise_aud("   ", "Tapio"), "")
        self.assertEqual(load().normalise_aud(None, "Tapio"), "")

    def test_an_unpiped_room_that_is_not_the_venue_survives(self):
        """A single-screen house whose room has its own name keeps it; only the room
        that is *just the venue again* is emptied."""
        self.assertEqual(load().normalise_aud("ISO SALI", "Killa"), "ISO SALI")

    def test_a_venue_named_room_is_emptied_whatever_its_case(self):
        self.assertEqual(load().normalise_aud("killa", "Killa"), "")
        self.assertEqual(load().normalise_aud("KILLA", "killa"), "")


class SiteGatingTest(unittest.TestCase):
    """The blast radius, asserted rather than assumed."""

    def test_only_sites_with_repeated_venue_rooms_opt_in(self):
        optedin = [s["provider"] for s in load().SITES if s.get("aud_repeats_venue")]
        self.assertEqual(optedin, ["savonkinot", "cine"])

    def test_no_opted_in_venue_keeps_its_own_name_as_a_room(self):
        """A room field carrying nothing but the venue name empties, on every site that
        opts in."""
        for site in optedin_sites():
            for v in site["venues"]:
                with self.subTest(provider=site["provider"], venue=v["id"]):
                    self.assertEqual(
                        load().normalise_aud(v["short"].upper(), v["short"]), "")

    def test_leffabuumi_does_not_opt_in(self):
        """It pipes as well, 63 of 78 showtimes, and its right half is a room name
        rather than the venue. Normalising it would drop "KINOLINNA" and leave rooms in
        three different buildings all called SALI 1."""
        lb = site_of("leffabuumi")
        self.assertFalse(lb.get("aud_repeats_venue"))

    def test_every_venue_of_every_opted_in_site_has_a_short(self):
        """normalise_aud takes its casing from `short`; a venue without one would
        produce "Sali None 4"."""
        sites = optedin_sites()
        self.assertTrue(sites, "no site opts in, so this asserts nothing")
        for site in sites:
            for v in site["venues"]:
                with self.subTest(provider=site["provider"], venue=v["id"]):
                    self.assertTrue(v.get("short"), v)

    def test_the_emit_is_gated_on_the_flag(self):
        """Reads the source rather than the behaviour: fetch_site is a network call, so
        what is checkable offline is that the call site is conditional and not blanket."""
        src = (_ctx.ROOT / "scripts" / "providers" / "etiketti.py").read_text(
            encoding="utf-8")
        self.assertIn('site.get("aud_repeats_venue")', src)
        self.assertIn("normalise_aud(r[\"aud\"], venue[\"short\"])", src)


class OtherSitesUnchangedTest(unittest.TestCase):
    """Sites without the normaliser keep their committed auditorium strings."""

    @classmethod
    def setUpClass(cls):
        cls.by_provider = {}
        for f in sorted((_ctx.ROOT / "data").glob("area-*.json")):
            for s in json.loads(f.read_text(encoding="utf-8")).get("shows", []):
                cls.by_provider.setdefault(s.get("provider"), set()).add(s.get("aud"))

    def test_no_other_etiketti_site_would_be_touched(self):
        """The flag is the only route into the normaliser, so this is really a second
        reading of the gating test -- from the data side, naming the providers whose
        auditorium strings have to stay byte-for-byte what they are."""
        others = [s["provider"] for s in load().SITES
                  if not s.get("aud_repeats_venue")]
        # The sixteen from the sweep, Cinema Niagara (2026-09-02), Elokuvateatteri
        # Star (2026-09-07) and Haapamäen Elokuvat (2026-09-29, whose rows print no room).
        # Pinned so a new site lands here as a decision rather than a drift.
        self.assertEqual(len(others), 19)
        for prov in others:
            vals = self.by_provider.get(prov)
            if not vals:
                continue
            with self.subTest(provider=prov):
                self.assertNotIn(None, vals)

    def test_leffabuumis_piped_rooms_are_still_piped_in_the_data(self):
        """If this ever goes red, Leffabuumi changed shape and the reasoning above --
        that its pipe means something different -- needs re-checking before anyone
        extends the flag to it."""
        vals = self.by_provider.get("leffabuumi", set())
        self.assertTrue(any("|" in v for v in vals if v), sorted(vals))


if __name__ == "__main__":
    unittest.main()
