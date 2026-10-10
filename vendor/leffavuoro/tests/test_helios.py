"""The Kino Helios reader: one POST, the whole house's calendar, three fields to filter.

The fixtures are the payload's shape as read on 2026-09-21, cut to the smallest form that
still exercises a rule. Two rows everywhere there is a loop.

What they exist to prove:

- **All three fields are needed to pick this cinema out.** The live answer held 33 rows at
  this location and type: 22 Kino Helios, 8 with a blank subtitle, 2 `Yleison suosikit`
  and 1 **`Doc Helios`**, which is a different strand of the same house.
- **`/Date(ms)/` is a UTC instant**, and the clock the service prints beside it is the same
  moment in Helsinki. A row where the two disagree is refused rather than published three
  hours out.
- **The age limit is a suffix on the title.** It goes to `rating`, and the published title
  is the film's own, because the title is the key the combined city view merges on.
- **`end - start` is a booking slot**, so `len` stays empty whatever the payload says.
- **An empty result is not evidence of an empty programme**, because the service answers
  the whole house.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import helios as H
import registry
import run


SITE = H.SITES[0]
VENUE = SITE["venues"][0]["id"]
URL = SITE["base"] + SITE["path"]
SINGLE = SITE["base"] + H.SINGLE_PATH
HALL = SITE["hall"]
TODAY = datetime.date(2026, 9, 21)
TICKET = "https://www.lippu.fi/event/kino-helios-esittaa-22106493/"


def ms(iso):
    """A Helsinki wall clock -> the service's `/Date(ms)/` string."""
    dt = datetime.datetime.fromisoformat(iso).replace(tzinfo=H.FI)
    return f"/Date({int(dt.timestamp() * 1000)})/"


def span(iso):
    dt = datetime.datetime.fromisoformat(iso)
    return f"{'ma ti ke to pe la su'.split()[dt.weekday()]}  {dt.day}.{dt.month}.{dt.year} klo {dt.hour}.{dt.minute:02d}"


def event(title="Practical Magic: Lumotut sisaret (12)", start="2026-09-23T15:00",
          end="2026-09-23T17:00", location="42", type_="29", subtitle="Kino Helios",
          hall=HALL, ticket=TICKET, description="", span_=None, master="792035"):
    return {
        "title": title, "subtitle": subtitle, "masterID": master,
        "key": "57F8089A89C592CFDB298345F5BABEFF",
        "eventLocation": location, "mainEventType": type_,
        "start": ms(start), "end": ms(end) if end else "None",
        "specificLocation": hall, "ticketLink": ticket,
        "priceinfo": "None", "ticketinfo": "None", "eventChargeable": "308",
        "description": description or "None",
        "timeSpanToShow": span(start) if span_ is None else span_,
    }


class FilterTest(unittest.TestCase):
    def rows(self, *events, today=TODAY):
        return H.rows(SITE, list(events or (event(),)), today)

    def test_every_matching_row_becomes_a_show(self):
        shows, report = self.rows(
            event(), event(title="Myrskyn ikkuna (12)", start="2026-09-23T18:00",
                           end="2026-09-23T20:00", master="792036"))
        self.assertEqual((report["rows"], report["mine"]), (2, 2))
        self.assertEqual([(s["title"], s["start"]) for s in shows], [
            ("Practical Magic: Lumotut sisaret", "2026-09-23T15:00:00+03:00"),
            ("Myrskyn ikkuna", "2026-09-23T18:00:00+03:00"),
        ])

    def test_doc_helios_is_a_different_strand_and_never_publishes(self):
        shows, report = self.rows(event(subtitle="Doc Helios",
                                        title="Kappale kauneinta Suomea"), event())
        self.assertEqual(report["mine"], 1)
        self.assertEqual([s["title"] for s in shows], ["Practical Magic: Lumotut sisaret"])

    def test_a_blank_subtitle_never_publishes(self):
        shows, _ = self.rows(event(subtitle="", title="Syyslomaleffa: Koiramies (7)"))
        self.assertEqual(shows, [])

    def test_another_strand_at_the_same_location_never_publishes(self):
        shows, _ = self.rows(event(subtitle="Yleisön suosikit", title="Sydäntalvi"))
        self.assertEqual(shows, [])

    def test_another_location_or_type_never_publishes(self):
        self.assertEqual(self.rows(event(location="7"))[0], [])
        self.assertEqual(self.rows(event(type_="12"))[0], [])


class ClockTest(unittest.TestCase):
    def test_the_utc_instant_is_published_as_helsinki_local(self):
        s = H.rows(SITE, [event()], TODAY)[0][0]
        self.assertEqual(s["start"], "2026-09-23T15:00:00+03:00")

    def test_a_winter_instant_keeps_its_own_offset(self):
        s = H.rows(SITE, [event(start="2026-12-02T17:00", end="2026-12-02T19:00")],
                   TODAY)[0][0]
        self.assertEqual(s["start"], "2026-12-02T17:00:00+02:00")

    def test_a_row_whose_printed_clock_disagrees_is_refused(self):
        """The fault a dropped offset produces: the instant and the clock diverge."""
        shows, report = H.rows(SITE, [event(span_="ke  23.9.2026 klo 12.00"), event()],
                               TODAY)
        self.assertEqual((len(shows), report["clock_clash"]), (1, 1))

    def test_a_row_with_no_printed_clock_is_still_published(self):
        shows, report = H.rows(SITE, [event(span_="")], TODAY)
        self.assertEqual((len(shows), report["clock_clash"]), (1, 0))

    def test_an_unparsable_start_is_counted_and_left_out(self):
        bad = event(); bad["start"] = "soon"
        shows, report = H.rows(SITE, [bad, event()], TODAY)
        self.assertEqual((len(shows), report["unreadable"]), (1, 1))


class FieldTest(unittest.TestCase):
    def test_the_age_suffix_becomes_the_rating_and_leaves_the_title(self):
        for title, want in (("Hetki ennen valoa (7)", ("Hetki ennen valoa", "K-7")),
                            ("Myrskyn ikkuna (12)", ("Myrskyn ikkuna", "K-12")),
                            ("Unohdettu saari (S)", ("Unohdettu saari", "S")),
                            ("Heart of the Beast", ("Heart of the Beast", ""))):
            with self.subTest(title=title):
                self.assertEqual(H.split_title(title), want)

    def test_a_title_that_is_only_a_bracket_is_left_alone(self):
        self.assertEqual(H.split_title("(12)"), ("(12)", ""))

    def test_the_title_merges_with_the_same_film_at_other_chains(self):
        """The combined city view keys on the title, and Iso-Hannu publishes this film as
        `Practical Magic: Lumotut sisaret`. A title carrying `(12)` would be a second
        film."""
        s = H.rows(SITE, [event()], TODAY)[0][0]
        self.assertEqual(s["title"], "Practical Magic: Lumotut sisaret")
        self.assertEqual(s["rating"], "K-12")

    def test_the_booking_slot_never_becomes_a_runtime(self):
        """Twenty-one of the 22 live rows measured 120 minutes and one 300."""
        s = H.rows(SITE, [event()], TODAY)[0][0]
        self.assertEqual(s["len"], "")

    def test_the_house_tariff_is_not_a_per_screening_price(self):
        s = H.rows(SITE, [event()], TODAY)[0][0]
        self.assertEqual(s["price"], "")

    def test_the_services_literal_none_never_reaches_a_field(self):
        s = H.rows(SITE, [event(ticket="None", description="None")], TODAY)[0][0]
        self.assertEqual(s["url"], "")
        self.assertNotIn("_syn", s)

    def test_the_hall_is_published_as_the_room(self):
        s = H.rows(SITE, [event()], TODAY)[0][0]
        self.assertEqual(s["aud"], HALL)

    def test_a_row_in_another_hall_still_publishes_and_is_counted(self):
        """The filter is the three fields, not the hall: a rename must not empty the site."""
        shows, report = H.rows(SITE, [event(hall="Malmitalon Sali")], TODAY)
        self.assertEqual((len(shows), report["other_hall"]), (1, 1))
        self.assertEqual(shows[0]["aud"], "Malmitalon Sali")

    def test_a_finnish_blurb_is_declared_finnish(self):
        s = H.rows(SITE, [event(description=(
            "Sandra Bullockin ja Nicole Kidmanin tähdittämä elokuva vie "
            "kuutamon valaisemien kepposten ja esiäitien taikuuden sävyttämään "
            "maailmaan, jossa siskokset kohtaavat menneisyytensä."))], TODAY)[0][0]
        self.assertEqual(list(s["_syn"]), ["fi"])

    def test_the_show_shape(self):
        s = H.rows(SITE, [event()], TODAY)[0][0]
        self.assertEqual((s["provider"], s["venue"], s["lang"], s["method"],
                          s["original"], s["genres"], s["img"], s["soldOut"]),
                         ("helios", VENUE, "", "", "", "", "", False))
        self.assertEqual((s["theatre"], s["eventId"], s["url"]),
                         ("Kino Helios", "792035", TICKET))


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._get = H.get_text
        self.addCleanup(lambda: setattr(H, "get_text", self._get))
        self.calls = []

    def serve(self, events, record=None):
        """`events` answers the calendar; `record` answers each screening's own record."""
        def get_text(url, **kw):
            self.calls.append((url, json.loads(kw["data"].decode())))
            if url == SINGLE:
                return json.dumps({"EventData": json.dumps(record or {"breadtext": "None"})})
            if isinstance(events, Exception):
                raise events
            return json.dumps({"EventData": json.dumps(events)})
        H.get_text = get_text

    def calendar_calls(self):
        return [c for c in self.calls if c[0] == URL]

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["helios", "--half", "all"])
        return code, out.getvalue() + err.getvalue()

    def test_the_site_publishes_from_one_post(self):
        self.serve([event(), event(subtitle="Doc Helios"),
                    event(title="Myrskyn ikkuna (12)", start="2026-09-24T15:00",
                          end="2026-09-24T17:00", master="792036")])
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertEqual(len(self.calendar_calls()), 1)
        url, body = self.calls[0]
        self.assertEqual(url, URL)
        self.assertEqual(body["Language"], "fi")
        self.assertEqual(body["StartTime"], datetime.datetime.now(H.FI).date().isoformat())
        shows = json.loads(
            (run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))["shows"]
        self.assertEqual(sorted({s["title"] for s in shows}),
                         ["Myrskyn ikkuna", "Practical Magic: Lumotut sisaret"])

    def test_the_window_asked_for_is_the_declared_horizon(self):
        self.serve([event()])
        self.main()
        _, body = self.calls[0]
        start = datetime.date.fromisoformat(body["StartTime"])
        end = datetime.date.fromisoformat(body["EndTime"])
        self.assertEqual((end - start).days, H.HORIZON)

    def test_a_payload_with_no_row_of_this_cinema_fails_and_keeps_the_previous_file(self):
        """The service answers the whole house, so this is not evidence of a dark week."""
        kept = {"generated": "2026-09-20T00:00:00+00:00", "dates": ["2026-09-20"],
                "horizon": "2026-09-20",
                "shows": [{"title": "Yesterday", "start": "2026-09-20T17:00:00+03:00"}]}
        (run.OUT / f"area-{VENUE}.json").write_text(json.dumps(kept), encoding="utf-8")
        self.serve([event(subtitle="Doc Helios"), event(subtitle="")])
        code, log = self.main()
        self.assertNotEqual(code, 0)
        self.assertIn("no Kino Helios row", log)
        after = json.loads((run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))
        self.assertEqual(after["shows"][0]["title"], "Yesterday")

    def test_a_clock_clash_on_every_row_fails_the_site(self):
        """What a dropped offset looks like: every instant three hours off its printed
        clock. Each row is left out, nothing is left, and the site fails with the
        previous file kept, instead of publishing every screening at the wrong time."""
        self.serve([event(span_="ke  23.9.2026 klo 12.00"),
                    event(start="2026-09-24T15:00", end="2026-09-24T17:00",
                          span_="to  24.9.2026 klo 12.00")])
        code, log = self.main()
        self.assertNotEqual(code, 0)
        self.assertFalse((run.OUT / f"area-{VENUE}.json").exists())

    def test_a_refused_request_keeps_the_previous_file(self):
        kept = {"generated": "2026-09-20T00:00:00+00:00", "dates": [], "horizon": "",
                "shows": [{"title": "Yesterday", "start": "2026-09-20T17:00:00+03:00"}]}
        (run.OUT / f"area-{VENUE}.json").write_text(json.dumps(kept), encoding="utf-8")
        self.serve(RuntimeError("502 refused"))
        code, log = self.main()
        self.assertNotEqual(code, 0)
        after = json.loads((run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))
        self.assertEqual(after["shows"][0]["title"], "Yesterday")


# Rakkautta ja virtahepoja's own record, read 2026-09-29: the film's facts end `breadtext`.
RECORD = {"title": "Rakkautta ja virtahepoja (12)", "breadtext":
          "Dome Karukosken romanttinen draamaelokuva.<br />\r\n<br />\r\nIk\u00e4raja:12<br />\r\n"
          "Kesto: 102 min<br />\r\nEnsi-ilta: 25.09.2026<br />\r\nKieli: suomi<br />\r\n"
          "Tekstitys: suomi<br />\r\n"}


def answer(record):
    return json.dumps({"EventData": json.dumps(record)})


class EventLanguageTest(unittest.TestCase):
    def test_the_record_names_the_audio_and_the_subtitles(self):
        self.assertEqual(H.event_language(answer(RECORD)), {"lang": "FI-A, FI-S"})
        other = dict(RECORD, breadtext="Kieli: englanti<br />Tekstitys: suomi, ruotsi<br />")
        self.assertEqual(H.event_language(answer(other)), {"lang": "EN-A, FI-S, SV-S"})

    def test_a_dubbed_film_says_spoken_in_finnish(self):
        # Ryhmä Hau: Dinoelokuva and Unohdettu saari, 2026-09-29.
        dub = dict(RECORD, breadtext="Kesto: 89 min<br />\r\nKieli: puhuttu suomeksi<br />\r\n")
        self.assertEqual(H.event_language(answer(dub)), {"lang": "FI-A"})

    def test_what_the_record_does_not_state_plainly_is_left_out(self):
        for text in ("Kesto: 102 min<br />", "Kieli: dari<br />", "None"):
            with self.subTest(text=text):
                self.assertEqual(H.event_language(answer(dict(RECORD, breadtext=text))), {})


class ScreeningLanguageTest(RunnerTest):
    def test_each_screening_takes_the_language_its_own_record_states(self):
        self.serve([event()], record=RECORD)
        code, log = self.main()
        self.assertEqual(code, 0, log)
        (url, body), = [c for c in self.calls if c[0] == SINGLE]
        self.assertEqual(body, {"Key": "57F8089A89C592CFDB298345F5BABEFF", "Language": "fi"})
        (show,) = json.loads((run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))["shows"]
        self.assertEqual(show["lang"], "FI-A, FI-S")
        self.assertNotIn("_event", show)

    def test_a_cached_record_is_not_read_again(self):
        self.serve([event()], record=RECORD)
        self.main()
        self.calls.clear()
        self.main()
        self.assertEqual([c for c in self.calls if c[0] == SINGLE], [])

    def test_a_record_that_fails_leaves_the_screening_published_without_a_language(self):
        self.serve([event()], record=RECORD)
        real = H.get_text
        def failing(url, **kw):
            if url == SINGLE:
                raise RuntimeError("502")
            return real(url, **kw)
        H.get_text = failing
        code, log = self.main()
        self.assertEqual(code, 0, log)
        (show,) = json.loads((run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))["shows"]
        self.assertEqual(show["lang"], "")


    def test_a_language_pass_that_breaks_leaves_the_programme_published(self):
        self.serve([event()], record=RECORD)
        real = H.prices.enrich
        def broken(*a, **kw):
            raise OSError("disk full")
        H.prices.enrich = broken
        self.addCleanup(lambda: setattr(H.prices, "enrich", real))
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertIn("languages skipped", log)
        (show,) = json.loads((run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))["shows"]
        self.assertEqual(show["lang"], "")


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("helios")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Kino Helios", "malmitalo.fi", "buy", "helios", "cloud"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"] == p["accent"]), 1)

    def test_the_site_names_the_host_it_is_read_from(self):
        self.assertEqual(SITE["base"], "https://www.malmitalo.fi")
        self.assertNotIn("reads", SITE)

    def test_the_three_filter_fields_are_declared(self):
        self.assertEqual((SITE["location"], SITE["type"], SITE["subtitle"]),
                         ("42", "29", "Kino Helios"))


if __name__ == "__main__":
    unittest.main()
