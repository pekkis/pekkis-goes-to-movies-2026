"""Add to calendar: one screening as an .ics file (2026-09-13, v146).

`icsFor` and its helpers are sliced verbatim out of index.html by tests/ics_harness.js and
run on their own with the page's Helsinki formatters and safeUrl. Measured 2026-09-13:
35 of 3561 committed shows have no `len` (booked as 120 minutes, said so), 627 no `aud`
(no hall in LOCATION). The download plumbing and the second menu row are pinned on the
source; the download itself is verified by hand on the platforms named in
docs/archive/2026-09-app.md.
"""
import json
import pathlib
import re
import shutil
import subprocess
import unittest

import _ctx

HARNESS = pathlib.Path(__file__).resolve().parent / "ics_harness.js"
HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")


def unfold(text):
    return text.replace("\r\n ", "")


def prop(text, name):
    """The value of the (unfolded) property `name`, first occurrence inside VEVENT."""
    event = unfold(text).split("BEGIN:VEVENT", 1)[1]
    m = re.search(r"^" + re.escape(name) + r"[;:](.*?)\r\n", event, re.M)
    return m.group(1) if m else None


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class IcsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.o = json.loads(out.stdout)

    def test_the_file_is_a_calendar_with_one_event_in_helsinki_time_and_crlf_ends(self):
        t = self.o["plain"]
        self.assertTrue(t.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"))
        self.assertTrue(t.endswith("END:VEVENT\r\nEND:VCALENDAR\r\n"))
        self.assertNotRegex(t, r"[^\r]\n", "every line end is CRLF")
        self.assertEqual(t.count("BEGIN:VEVENT"), 1)
        self.assertIn("BEGIN:VTIMEZONE\r\nTZID:Europe/Helsinki\r\n", t)
        self.assertIn("RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU", t)
        self.assertIn("RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU", t)
        self.assertEqual(prop(t, "DTSTART"), "TZID=Europe/Helsinki:20260915T163000")
        self.assertEqual(prop(t, "DTEND"), "TZID=Europe/Helsinki:20260915T175800")   # 16:30 + 88 min
        self.assertEqual(prop(t, "DTSTAMP"), "20260913T120000Z")

    def test_summary_is_the_title_verbatim_and_location_is_chain_venue_hall_city(self):
        t = self.o["plain"]
        self.assertEqual(prop(t, "SUMMARY"), "Ryhmä Hau: Dinoelokuva")
        self.assertEqual(prop(t, "LOCATION"), r"Finnkino Promenadi\, Sali 3\, Pori")
        self.assertEqual(prop(t, "URL"), "https://www.finnkino.fi/liput/valitse-paikat/?showtimeId=1004-5281")
        self.assertEqual(prop(t, "DESCRIPTION"), r"2D\nhttps://www.finnkino.fi/liput/valitse-paikat/?showtimeId=1004-5281")

    def test_no_hall_means_venue_and_city_only(self):
        self.assertEqual(prop(self.o["no_hall"], "LOCATION"), r"Kino Regina\, Helsinki")

    def test_a_missing_runtime_books_two_hours_and_says_so_in_the_language(self):
        for case, note in (("no_len_fi", "Kesto arvioitu"), ("no_len_sv", "Längd uppskattad"), ("no_len_en", "Runtime estimated")):
            t = self.o[case]
            self.assertEqual(prop(t, "DTEND"), "TZID=Europe/Helsinki:20260915T183000", case)
            self.assertTrue(prop(t, "DESCRIPTION").endswith(r"\n" + note), (case, prop(t, "DESCRIPTION")))
        self.assertNotIn("Kesto arvioitu", self.o["plain"])

    def test_text_values_escape_backslash_semicolon_comma_and_newline(self):
        t = self.o["punctuation"]
        self.assertEqual(prop(t, "SUMMARY"), r"Mission: Impossible\, Part\; Two\\Three")
        self.assertEqual(prop(t, "LOCATION"), r"BioRex Tripla\, Sali 3\, Helsinki")
        self.assertTrue(prop(t, "DESCRIPTION").startswith(r"IMAX\, dubattu\n"))

    def test_a_lone_carriage_return_is_escaped_and_cannot_open_a_property(self):
        """A CR with no LF reached the file raw until 2026-09-22. The title is provider
        text, so a parser that treats a bare CR as a line break reads a second property."""
        t = self.o["lone_cr"]
        self.assertEqual(prop(t, "SUMMARY"), r"Elokuva\nDESCRIPTION:injected")
        self.assertNotRegex(t, r"\r(?!\n)", "no CR in the file stands on its own")

    def test_the_rest_of_the_c0_range_is_dropped(self):
        """3.3.11 has no escape for these, so they are dropped rather than emitted."""
        t = self.o["c0"]
        self.assertEqual(prop(t, "SUMMARY"), "Elokuvaloppu")
        self.assertEqual(prop(t, "LOCATION"), r"Finnkino Promenadi\, Sali3\, Pori")
        self.assertNotRegex(t, r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]")

    def test_lines_fold_at_75_octets_without_splitting_a_character(self):
        t = self.o["long_title"]
        lines = t.split("\r\n")
        self.assertLessEqual(max(len(l.encode("utf-8")) for l in lines), 75)
        self.assertTrue(any(l.startswith(" ") for l in lines), "the long title was folded")
        self.assertEqual(prop(t, "SUMMARY"), " ".join(["Ääkkösiä"] * 12), "unfolding gives the title back")
        self.assertNotIn("�", t)

    def test_the_ticket_link_goes_through_safeurl(self):
        t = self.o["bad_url"]
        self.assertIsNone(prop(t, "URL"))
        self.assertNotIn("javascript:", t)
        self.assertEqual(prop(t, "DESCRIPTION"), "2D")

    def test_the_ticket_link_reaches_the_calendar_file_unescaped(self):
        """safeUrl HTML-escapes, which an href needs and a calendar file does not: the
        reader's calendar follows `&amp;` literally. icsFor takes safeUrlRaw, writes it
        bare into URL: and through icsText into DESCRIPTION:, which is a TEXT value."""
        amp = "https://www.elavienkuvienteatteri.fi/lipunvaraus/?movieid=1383&date=2026-09-22&time=17:30"
        t = self.o["amp_url"]
        self.assertEqual(prop(t, "URL"), amp, "URL round-trips the input exactly")
        self.assertTrue(prop(t, "DESCRIPTION").endswith(r"\n" + amp))
        self.assertNotIn("&amp;", t)
        apos = "https://x.fi/lippu/o'brien?d=1"
        a = self.o["apostrophe_url"]
        self.assertEqual(prop(a, "URL"), apos)
        self.assertNotIn("&#39;", a)

    def test_the_url_line_carries_a_uri_and_not_escaped_text(self):
        """3.8.4.6 types URL as URI, and the backslash escaping of 3.3.11 is TEXT only,
        so `\\,` in a URI value is two literal characters and a strict reader gets a
        corrupted link. `\\ ; ,` are all legal bare in a URI. Nothing can break the line
        either: safeUrlRaw returns '' for any string holding a control character, so CR
        and LF never reach here. LOCATION and DESCRIPTION are TEXT and keep icsText."""
        self.assertEqual(prop(self.o["comma_url"], "URL"), "https://x.fi/a?list=1,2;3")

    def test_an_iso_start_in_winter_time_is_wall_time(self):
        t = self.o["iso_start"]
        self.assertEqual(prop(t, "DTSTART"), "TZID=Europe/Helsinki:20261101T180000")
        self.assertEqual(prop(t, "DTEND"), "TZID=Europe/Helsinki:20261101T192800")

    def test_the_uid_is_stable_across_calls_and_ours(self):
        a, b = prop(self.o["plain"], "UID"), prop(self.o["same_again"], "UID")
        self.assertEqual(a, b)
        # Written in two halves so the address guard (test_contact_address) sees no address.
        self.assertEqual(a.split("@"), ["6c8421f5-34", "leffavuoro.fi"], "djb2 over venue|start|title, not a clock")
        self.assertNotEqual(a, prop(self.o["no_hall"], "UID"), "another venue is another event")


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class VenuePlaceTest(unittest.TestCase):
    """Two cinemas in one combined view, and a single view: the place comes from the venue
    list, never from the last word of a theatre name a provider chose (Riviera Kallio is in
    Helsinki, Kino Aurora in Jyväskylä: 45 of 65 non-Finnkino venues end in a word that is
    not their city, measured 2026-09-13)."""
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.p = json.loads(out.stdout)["place"]

    def test_a_combined_view_places_each_cinema_by_its_own_id(self):
        self.assertEqual(self.p["combined_riviera"], {"id": "rv-kallio", "label": "Riviera Kallio", "city": "Helsinki"})
        self.assertEqual(self.p["combined_finnkino"], {"id": "1100", "label": "Finnkino Kinopalatsi", "city": "Helsinki"})
        self.assertEqual(self.p["combined_by_venue_only"]["city"], "Helsinki", "the provider's own id is enough")

    def test_a_single_view_places_through_the_venue_on_screen(self):
        self.assertEqual(self.p["single_finnkino"], {"id": "1100", "label": "Finnkino Kinopalatsi", "city": "Helsinki"})
        self.assertEqual(self.p["single_niagara"], {"id": "cn-tampere", "label": "Cinema Niagara", "city": "Tampere"})

    def test_a_show_the_list_cannot_place_falls_back_to_its_theatre_text(self):
        self.assertEqual(self.p["unknown"], {"id": "Plevna Tampere", "label": "Finnkino Plevna", "city": "Tampere"})


class CalendarPlumbingTest(unittest.TestCase):

    def test_the_second_menu_row_and_its_strings(self):
        self.assertIn('<button type="button" role="menuitem" class="mi" data-act="cal"><span>${esc(T.addCalendar)}</span></button>', HTML)
        self.assertIn("if(s && mi.dataset.act === 'cal') calendarScreening(s);", HTML)
        for lang, text in (("fi", "Lisää kalenteriin"), ("sv", "Lägg till i kalendern"), ("en", "Add to calendar")):
            self.assertIn(f"addCalendar:'{text}'", HTML, lang)

    def test_the_download_is_a_blob_on_a_download_anchor(self):
        fn = re.search(r"function calendarScreening\(s\)\{.*?\n  \}\n", HTML, re.S).group(0)
        self.assertIn("icsFor({ ...s, start: s.start }, venueFor(s), state.lang)", fn)
        self.assertIn("new Blob([ics], { type: 'text/calendar;charset=utf-8' })", fn)
        self.assertIn("a.download = `leffavuoro-${fiDate(s.start)}-", fn)
        self.assertIn("a.click();", fn)
        self.assertIn("URL.revokeObjectURL(href)", fn)

    def test_the_caller_hands_venue_place_the_pages_own_index_and_rules(self):
        self.assertIn("const venueFor = s => venuePlace(s, state.area, venueIndex, labelOf, cityOf, venueName);", HTML)
        self.assertIn("_vid: ids[i],", HTML, "the combined loader stamps the venue id on every merged show")

    def test_the_service_worker_moved_with_the_page(self):
        sw = (_ctx.ROOT / "sw.js").read_text(encoding="utf-8")
        self.assertGreaterEqual(int(re.search(r"leffavuoro-v(\d+)", sw).group(1)), 146)


if __name__ == "__main__":
    unittest.main()
