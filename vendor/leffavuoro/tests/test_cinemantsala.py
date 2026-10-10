"""Cine Mäntsälä: the seven-day cap, the window cover, and UTC that means UTC.

Fixtures are the `/webservices/show_times/` envelopes as read on 2026-09-15:
`{"resultCode": 0, "data": [...]}` for both `getShowDates` and `getShowTimesDays`.

Three things the fixtures exist to prove, each of which cost a design decision:

- **`number_of_days` is a cap of 7, not a request.** Asked for 7, 14 and 120 the endpoint
  returned the same six days, so the date list has to be walked and covered. Every window
  fixture here holds at least two windows: a one-window fixture would never enter the
  paced loop, which is how a missing import once passed a whole suite.
- **`show_date` and `show_time` are real UTC instants.** Local midnight arrives as the
  preceding 21:00Z in summer and 22:00Z in winter, so the DST fixtures are a September
  row and a December row and the assertions are on the offset as well as the clock.
- **Windows overlap.** The cover is minimal but two adjacent programme dates can still be
  returned twice, so a repeated `show_time_id` is one screening.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import cinemantsala as cm
import common
import registry
import run

BASE = "https://mantsala.cine.fi"
API = BASE + "/webservices/show_times"
D = datetime.date


def dates_doc(*iso):
    return {"resultCode": 0, "data": [{"show_date": d} for d in iso]}


def show(sid, start, mid=981, title="Hetki ennen valoa", screen="Sali 1",
         rating="K7", audio="FI", subs="Suomeksi ja ruotsiksi", ext=None,
         runtime=87, genre="Draama", poster="p.jpeg", sold=0, style="Original language",
         **over):
    row = {
        "show_time_id": sid, "show_time": start, "movie_id": mid, "title": title,
        "short_desc": title, "screen_name": screen, "rating_name": rating,
        "audio_lang": audio, "subtitle_lang": subs, "title_extension": ext,
        "running_time": runtime, "genre": genre, "movie_poster": poster,
        "sold_out": sold, "movie_audio_style_name": style,
        "business_date": start[:10] + "T00:00:00.000Z",
        "version_digital": 1, "bookable": 1, "allow_purchases": 1,
    }
    row.update(over)
    return row


def times_doc(*rows):
    return {"resultCode": 0, "data": list(rows)}


def dates_url():
    return API + "/getShowDates?cinema_id=1"


def window_url(day):
    return f"{API}/getShowTimesDays?cinema_id=1&date={day}&number_of_days=7"


# Local midnight as this API writes it: the preceding 21:00Z on +03:00 dates and
# 22:00Z on +02:00 dates. 2026-09-15 and 2026-09-22 are a fortnight apart in windows,
# 2026-12-01 and 2026-12-05 share one, and 2026-12-09 needs its own.
SEPT = "2026-09-14T21:00:00.000Z"          # -> 2026-09-15 local
SEPT2 = "2026-09-21T21:00:00.000Z"         # -> 2026-09-22 local
DEC = "2026-11-30T22:00:00.000Z"           # -> 2026-12-01 local
DEC2 = "2026-12-04T22:00:00.000Z"          # -> 2026-12-05 local


class WindowCoverTest(unittest.TestCase):
    """`windows` is the whole cap strategy and is pure, so it is tested on its own."""

    def test_six_consecutive_days_are_one_window(self):
        days = [D(2026, 9, 15) + datetime.timedelta(days=i) for i in range(6)]
        self.assertEqual(cm.windows(days), [D(2026, 9, 15)])

    def test_the_seventh_day_is_the_last_one_a_window_reaches(self):
        self.assertEqual(cm.windows([D(2026, 9, 15), D(2026, 9, 21)]),
                         [D(2026, 9, 15)])

    def test_the_eighth_day_starts_a_second_window(self):
        """The cap boundary. 09-15 covers through 09-21, so 09-22 cannot ride it."""
        self.assertEqual(cm.windows([D(2026, 9, 15), D(2026, 9, 22)]),
                         [D(2026, 9, 15), D(2026, 9, 22)])

    def test_a_gap_between_programme_dates_costs_one_window_not_the_gap(self):
        """A fortnight of nothing is two requests, not fifteen."""
        self.assertEqual(cm.windows([D(2026, 9, 15), D(2026, 9, 29)]),
                         [D(2026, 9, 15), D(2026, 9, 29)])

    def test_a_date_inside_a_later_window_adds_no_request(self):
        self.assertEqual(cm.windows([D(2026, 12, 1), D(2026, 12, 5)]),
                         [D(2026, 12, 1)])
        self.assertEqual(cm.windows([D(2026, 12, 1), D(2026, 12, 5), D(2026, 12, 9)]),
                         [D(2026, 12, 1), D(2026, 12, 9)])

    def test_the_real_seventeen_dates_cover_in_nine_windows(self):
        """The programme as it stood on 2026-09-15: 17 dates to 2026-12-22."""
        days = [D(2026, 9, d) for d in (15, 16, 17, 18, 19, 20, 22, 23)]
        days += [D(2026, 10, 6), D(2026, 10, 20), D(2026, 11, 3), D(2026, 11, 17)]
        days += [D(2026, 12, d) for d in (1, 5, 9, 15, 22)]
        starts = cm.windows(days)
        self.assertEqual(len(starts), 9)
        for day in days:
            self.assertTrue(any(0 <= (day - s).days < cm.WINDOW_DAYS for s in starts),
                            f"{day} is in no window")

    def test_unsorted_and_repeated_dates_give_the_same_cover(self):
        days = [D(2026, 9, 22), D(2026, 9, 15), D(2026, 9, 15), D(2026, 9, 16)]
        self.assertEqual(cm.windows(days), [D(2026, 9, 15), D(2026, 9, 22)])

    def test_no_date_is_no_window(self):
        self.assertEqual(cm.windows([]), [])


class DateListTest(unittest.TestCase):
    def read(self, doc):
        cm_get = cm.get
        cm.get = lambda url, **kw: doc
        self.addCleanup(lambda: setattr(cm, "get", cm_get))
        return cm.show_dates(cm.SITES[0])

    def test_local_midnight_is_converted_not_sliced(self):
        """21:00Z is the day *after* the Z date in Helsinki. Slicing the string would
        publish every programme date one day early."""
        self.assertEqual(self.read(dates_doc(SEPT)), [D(2026, 9, 15)])

    def test_the_winter_offset_is_an_hour_different_and_still_lands_on_midnight(self):
        self.assertEqual(self.read(dates_doc(DEC)), [D(2026, 12, 1)])

    def test_both_sides_of_the_dst_change_read_correctly_together(self):
        self.assertEqual(self.read(dates_doc(SEPT, DEC, SEPT2)),
                         [D(2026, 9, 15), D(2026, 9, 22), D(2026, 12, 1)])

    def test_a_naive_show_date_fails_the_list_rather_than_being_assumed(self):
        """A naive timestamp is what the JSON-LD feed publishes, three hours early. No
        zone is assumed for one here, and it is not dropped either: a listed date the
        parser cannot read is a shape change, and dropping it loses that date's window.

        Asserted as raise against no raise, so the guard is tested on a Helsinki machine
        too, where `astimezone` on a naive datetime silently assumes local time."""
        with self.assertRaises(RuntimeError) as cm_:
            self.read(dates_doc("2026-10-05T00:00:00", SEPT))
        self.assertNotIsInstance(cm_.exception, common.EmptyProgramme)
        self.assertIn("no UTC offset", str(cm_.exception))

    def test_an_unparseable_or_blank_show_date_fails_the_list(self):
        for bad in ("not-a-date", ""):
            with self.subTest(show_date=bad):
                with self.assertRaises(RuntimeError) as cm_:
                    self.read(dates_doc(bad, SEPT))
                self.assertNotIsInstance(cm_.exception, common.EmptyProgramme)

    def test_a_data_field_that_is_not_a_list_is_a_failure(self):
        """`[]` is the empty collection this envelope carries; `null` or an object is not
        that statement."""
        for data in (None, {}):
            with self.subTest(data=data):
                with self.assertRaises(RuntimeError) as cm_:
                    self.read({"resultCode": 0, "data": data})
                self.assertNotIsInstance(cm_.exception, common.EmptyProgramme)

    def test_an_empty_list_is_no_dates(self):
        self.assertEqual(self.read(dates_doc()), [])

    def test_an_envelope_without_data_is_a_failure(self):
        with self.assertRaises(RuntimeError) as cm_:
            self.read({"resultCode": 0})
        self.assertIn("envelope", str(cm_.exception))

    def test_a_non_zero_result_code_is_a_failure(self):
        with self.assertRaises(RuntimeError) as cm_:
            self.read({"resultCode": 7, "data": []})
        self.assertIn("resultCode", str(cm_.exception))


class ParseTest(unittest.TestCase):
    def setUp(self):
        # Deliberately out of order, the way the endpoint returns them: read live on
        # 2026-09-15 the four rows for that day arrived 13:45, 15:45, 16:00, 14:00. A
        # fixture already sorted made the sort a no-op and the mutation that deletes it
        # turned nothing red.
        self.rows = cm.parse([
            show(13233, "2026-12-01T16:30:00.000Z", mid=1003, title="Hamnet",
                 rating="K16", audio="EN", subs="Suomeksi ja ruotsiksi"),
            show(13391, "2026-09-15T14:00:00.000Z", mid=1013,
                 title="Presidentin kyyditys", screen="Sali 2", rating="K12"),
            show(13394, "2026-09-15T13:45:00.000Z"),
        ])[cm.VENUE["id"]]

    def test_the_utc_instant_becomes_the_local_clock_the_site_prints(self):
        """13:45Z is the 16.45 screening on the cinema's own booking page."""
        self.assertEqual(self.rows[0]["start"], "2026-09-15T16:45:00+03:00")

    def test_the_earliest_screening_is_first_whatever_order_the_rows_arrive_in(self):
        self.assertEqual([r["title"] for r in self.rows],
                         ["Hetki ennen valoa", "Presidentin kyyditys", "Hamnet"])

    def test_a_december_screening_carries_the_winter_offset(self):
        """Same conversion, an hour less: EET rather than EEST. A fixed +03:00 would
        publish every winter screening an hour late."""
        dec = [r for r in self.rows if r["title"] == "Hamnet"][0]
        self.assertEqual(dec["start"], "2026-12-01T18:30:00+02:00")

    def test_rows_are_sorted_by_start(self):
        self.assertEqual([r["start"] for r in self.rows],
                         sorted(r["start"] for r in self.rows))

    def test_a_repeated_show_time_id_across_overlapping_windows_is_one_screening(self):
        """Two windows can both reach a date. The screening is the id, not the row."""
        with contextlib.redirect_stdout(io.StringIO()):
            out = cm.parse([show(13394, "2026-09-15T13:45:00.000Z"),
                            show(13394, "2026-09-15T13:45:00.000Z"),
                            show(13395, "2026-09-15T15:45:00.000Z")])
        self.assertEqual([r["url"].rsplit("/", 1)[1] for r in out[cm.VENUE["id"]]],
                         ["13394", "13395"])

    def test_the_duplicate_is_named_in_the_log(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cm.parse([show(13394, "2026-09-15T13:45:00.000Z"),
                      show(13394, "2026-09-15T13:45:00.000Z")])
        self.assertIn("dropped 1 showtime", out.getvalue())

    def test_the_same_minute_on_two_screens_is_two_screenings(self):
        out = cm.parse([show(1, "2026-09-15T13:45:00.000Z", screen="Sali 1"),
                        show(2, "2026-09-15T13:45:00.000Z", screen="Sali 2")])
        rows = out[cm.VENUE["id"]]
        self.assertEqual(len(rows), 2)
        self.assertEqual(sorted(r["aud"] for r in rows), ["Sali 1", "Sali 2"])

    def test_a_naive_show_time_is_skipped(self):
        out = cm.parse([show(1, "2026-09-15T13:45:00"),
                        show(2, "2026-09-15T15:45:00.000Z")])
        self.assertEqual([r["url"].rsplit("/", 1)[1] for r in out[cm.VENUE["id"]]], ["2"])

    def test_an_unparseable_show_time_is_skipped(self):
        out = cm.parse([show(1, "soon"), show(2, "2026-09-15T15:45:00.000Z")])
        self.assertEqual([r["url"].rsplit("/", 1)[1] for r in out[cm.VENUE["id"]]], ["2"])

    def test_the_ticket_url_is_the_anchor_the_programme_emits(self):
        """On 2026-09-15 the ids the rendered programme emitted were exactly the
        show_time_id values the window returned, as sets, for the current week and for
        2026-12-15. The id is read from the source, not minted here."""
        self.assertEqual(self.rows[0]["url"], "https://mantsala.cine.fi/#/book/13394")

    def test_the_poster_is_the_platform_path_at_the_one_large_width(self):
        """Only 216 and 1080 exist; 300, 500, 720, 1024 and 2048 all answer 404."""
        self.assertEqual(self.rows[0]["img"],
                         "https://mantsala.cine.fi/media/posters/981/1080/p.jpeg")

    def test_a_row_with_no_poster_publishes_no_image(self):
        out = cm.parse([show(1, "2026-09-15T13:45:00.000Z", poster="")])
        self.assertEqual(out[cm.VENUE["id"]][0]["img"], "")

    def test_every_show_meets_the_contract(self):
        common.check_shows({cm.VENUE["id"]: self.rows}, "cinemantsala",
                           {cm.VENUE["id"]})


class FieldTest(unittest.TestCase):
    def one(self, **over):
        return cm.parse([show(1, "2026-09-15T13:45:00.000Z", **over)])[cm.VENUE["id"]][0]

    def test_the_finnish_rating_strings_become_the_client_tags(self):
        for raw, want in (("K7", "K-7"), ("K12", "K-12"), ("K16", "K-16"),
                          ("K18", "K-18"), ("Sallittu kaikenikäisille", "S")):
            with self.subTest(rating=raw):
                self.assertEqual(self.one(rating=raw)["rating"], want)

    def test_a_pending_or_unclassified_rating_publishes_nothing(self):
        """No tag is honest; a guessed one is not."""
        for raw in ("Ikäraja tulossa!", "Luokittelematon", ""):
            with self.subTest(rating=raw):
                self.assertEqual(self.one(rating=raw)["rating"], "")

    def test_the_subtitle_phrase_is_split_on_the_finnish_conjunction(self):
        self.assertEqual(self.one(audio="FI", subs="Suomeksi ja ruotsiksi")["lang"],
                         "FI-A, FI-S, SV-S")

    def test_a_single_subtitle_language_and_a_lower_case_one(self):
        self.assertEqual(self.one(audio="EN", subs="Ruotsiksi")["lang"], "EN-A, SV-S")
        self.assertEqual(self.one(audio="EN", subs="suomeksi")["lang"], "EN-A, FI-S")

    def test_ei_means_no_subtitles_rather_than_an_unknown_language(self):
        self.assertEqual(self.one(audio="FI", subs="Ei")["lang"], "FI-A")

    def test_the_swedish_audio_code_is_se_on_this_platform(self):
        self.assertEqual(self.one(audio="SE", subs="Ei")["lang"], "SV-A")

    def test_an_unknown_subtitle_word_is_dropped_rather_than_published(self):
        self.assertEqual(self.one(audio="FI", subs="Klingoniksi")["lang"], "FI-A")

    def test_an_unknown_audio_code_publishes_no_audio_tag(self):
        self.assertEqual(self.one(audio="ZZ", subs="Ei")["lang"], "")

    def test_the_strand_arrives_in_its_own_field_and_goes_to_method(self):
        """`strands.py` puts a strand in `method`. Here it never touches the title, so
        nothing is added to EVENT_PREFIXES and the title stays the TMDB key."""
        r = self.one(ext="Cine Matinea", title="Lex Julia")
        self.assertEqual(r["method"], "Cine Matinea")
        self.assertEqual(r["title"], "Lex Julia")

    def test_no_strand_is_an_empty_method_not_a_format_pill(self):
        """version_digital is set on every row and FORMATS omits it on purpose."""
        self.assertEqual(self.one(ext=None)["method"], "")

    def test_a_real_format_flag_still_becomes_a_pill(self):
        self.assertEqual(self.one(version_3d=1)["method"], "3D")
        self.assertEqual(self.one(version_3d=1, ext="Ennakkonäytös!")["method"],
                         "3D · Ennakkonäytös!",
                         "two tags, on the separator the client splits on")

    def test_the_dub_label_is_not_published_because_the_audio_code_says_it(self):
        """All five dubbed rows measured were Finnish children's films whose audio_lang
        is already FI, so a "Dubbed" pill would repeat what `lang` states."""
        r = self.one(style="Dubbed", audio="FI", subs="Ei")
        self.assertEqual(r["method"], "")
        self.assertEqual(r["lang"], "FI-A")

    def test_the_screen_is_published_verbatim(self):
        self.assertEqual(self.one(screen="Sali 2")["aud"], "Sali 2")

    def test_a_screen_named_after_the_venue_renders_blank(self):
        """A single-screen house whose screen repeats the venue name would otherwise
        read "Cine Mäntsälä · Cine Mäntsälä" on the stub."""
        self.assertEqual(self.one(screen="Cine Mäntsälä")["aud"], "")

    def test_the_film_id_and_the_plain_fields(self):
        r = self.one(mid=1003, runtime=104, genre="Komedia, Draama")
        self.assertEqual((r["eventId"], r["len"], r["genres"]),
                         ("1003", "104", "Komedia, Draama"))
        self.assertEqual((r["original"], r["price"]), ("", ""))
        self.assertEqual((r["provider"], r["venue"], r["theatre"]),
                         ("cinemantsala", "cm-mantsala", "Cine Mäntsälä"))

    def test_sold_out_is_read_from_the_row(self):
        self.assertIs(self.one(sold=0)["soldOut"], False)
        self.assertIs(self.one(sold=1)["soldOut"], True)


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._fetch, self._sleep = cm.fetch, cm.time.sleep
        self.addCleanup(lambda: setattr(cm, "fetch", self._fetch))
        self.addCleanup(lambda: setattr(cm.time, "sleep", self._sleep))
        cm.time.sleep = lambda s: None
        self.calls = []

    def serve(self, docs):
        def fetch(url, **kw):
            self.calls.append(url)
            body = docs.get(url)
            if isinstance(body, Exception):
                raise body
            if body is None:
                raise RuntimeError(f"unexpected fetch {url}")
            return json.dumps(body).encode("utf-8")
        cm.fetch = fetch

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["cinemantsala"])
        return code, out.getvalue() + err.getvalue()

    def two_windows(self, **over):
        """A September week and a December week: two windows, both sides of the DST
        change, so the paced loop is entered and the conversion is exercised twice."""
        docs = {
            dates_url(): dates_doc(SEPT, SEPT2, DEC, DEC2),
            window_url("2026-09-15"): times_doc(
                show(13394, "2026-09-15T13:45:00.000Z"),
                show(13391, "2026-09-15T14:00:00.000Z", mid=1013,
                     title="Presidentin kyyditys", screen="Sali 2")),
            window_url("2026-09-22"): times_doc(
                show(13420, "2026-09-22T15:30:00.000Z", mid=1034, title="Kapina")),
            window_url("2026-12-01"): times_doc(
                show(13233, "2026-12-01T16:30:00.000Z", mid=1003, title="Hamnet"),
                show(13330, "2026-12-05T12:30:00.000Z", mid=1004,
                     title="Andre Rieu's 2026 Christmas Concert")),
        }
        docs.update(over)
        return docs

    def test_a_full_run_publishes_the_venue_and_every_window(self):
        self.serve(self.two_windows())
        code, log = self.main()
        self.assertEqual(code, 0, log)
        doc = json.loads((run.OUT / "area-cm-mantsala.json").read_text())
        self.assertEqual(len(doc["shows"]), 5)
        venues = json.loads((run.OUT / "venues-cinemantsala.json").read_text())
        self.assertEqual(venues["venues"], [dict(cm.VENUE)])
        self.assertEqual((venues["status"], venues["stale"], venues["pending"]),
                         ("ok", [], []))
        self.assertIn("1 venues, 5 showtimes", log)
        self.assertIn("0 failures", log)

    def test_three_windows_are_requested_and_each_asks_for_seven_days(self):
        self.serve(self.two_windows())
        self.assertEqual(self.main()[0], 0)
        windows = [c for c in self.calls if "getShowTimesDays" in c]
        self.assertEqual(windows, [window_url("2026-09-15"), window_url("2026-09-22"),
                                   window_url("2026-12-01")])
        for c in windows:
            self.assertIn("number_of_days=7", c)

    def test_the_date_list_is_read_once_and_nothing_else_is(self):
        """No JSON-LD feed, no booking flow, no getShowTimes: three kinds of request
        this adapter must never make."""
        self.serve(self.two_windows())
        self.assertEqual(self.main()[0], 0)
        self.assertEqual([c for c in self.calls if "getShowDates" in c], [dates_url()])
        for c in self.calls:
            self.assertNotIn("structured_data", c)
            self.assertNotIn("/#/book/", c)
            self.assertNotIn("getShowTimes?", c)

    def test_the_published_times_are_local_on_both_sides_of_the_dst_change(self):
        self.serve(self.two_windows())
        self.assertEqual(self.main()[0], 0)
        shows = json.loads((run.OUT / "area-cm-mantsala.json").read_text())["shows"]
        by = {s["title"]: s["start"] for s in shows}
        self.assertEqual(by["Hetki ennen valoa"], "2026-09-15T16:45:00+03:00")
        self.assertEqual(by["Hamnet"], "2026-12-01T18:30:00+02:00")

    def test_an_empty_date_list_is_an_empty_programme_and_stays_green(self):
        """The cinema's own statement that it has nothing on. What run.py then writes for
        the venue is run.py's decision and is pinned in its own tests."""
        self.serve({dates_url(): dates_doc()})
        with self.assertRaises(common.EmptyProgramme):
            cm.fetch_site(cm.SITES[0], sleep=0)
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertIn("no programme published", log)
        self.assertNotIn("FAILED", log)
        self.assertEqual([c for c in self.calls if "getShowTimesDays" in c], [])

    def test_dates_listed_with_no_screening_fails_instead_of_publishing_nothing(self):
        """The date list is derived from the screenings, so dates beside an empty parse
        is the contradiction CLAUDE.md calls the broken case."""
        prev = {"generated": "2026-09-01T00:00:00+00:00", "dates": [], "horizon": "",
                "shows": [{"title": "Old", "start": "2026-09-01T12:00:00+03:00"}]}
        (run.OUT / "area-cm-mantsala.json").write_text(json.dumps(prev))
        self.serve({dates_url(): dates_doc(SEPT, SEPT2),
                    window_url("2026-09-15"): times_doc(),
                    window_url("2026-09-22"): times_doc()})
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", log)
        self.assertEqual(json.loads((run.OUT / "area-cm-mantsala.json").read_text()), prev)
        self.assertFalse((run.OUT / "venues-cinemantsala.json").exists())

    def test_dates_listed_in_a_shape_the_parser_misses_fail_the_site(self):
        """Every date listed and none readable: the list is not empty, the parse is, and
        reading that as `EmptyProgramme` would publish the venue empty."""
        prev = {"generated": "2026-09-01T00:00:00+00:00", "dates": [], "horizon": "",
                "shows": [{"title": "Old", "start": "2026-09-01T12:00:00+03:00"}]}
        (run.OUT / "area-cm-mantsala.json").write_text(json.dumps(prev))
        self.serve({dates_url(): dates_doc("2026-09-15T00:00:00", "2026-09-22T00:00:00")})
        code, log = self.main()
        self.assertEqual(code, 1, log)
        self.assertIn("FAILED", log)
        self.assertNotIn("no programme published", log)
        self.assertEqual(json.loads((run.OUT / "area-cm-mantsala.json").read_text()), prev)
        self.assertFalse((run.OUT / "venues-cinemantsala.json").exists())

    def test_a_refused_later_window_fails_the_site_and_keeps_the_previous_file(self):
        """A partial fetch would publish part of a programme, and run.py keeping the
        previous file lets the health line age honestly instead."""
        prev = {"generated": "2026-09-01T00:00:00+00:00", "dates": ["2026-09-01"],
                "horizon": "2026-09-01",
                "shows": [{"title": "Old", "start": "2026-09-01T12:00:00+03:00"}]}
        (run.OUT / "area-cm-mantsala.json").write_text(json.dumps(prev))
        self.serve(self.two_windows(**{
            window_url("2026-12-01"): RuntimeError("HTTP Error 502: Bad Gateway")}))
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", log)
        self.assertEqual(json.loads((run.OUT / "area-cm-mantsala.json").read_text()), prev)
        self.assertFalse((run.OUT / "venues-cinemantsala.json").exists())

    def test_a_refused_first_window_fails_the_site(self):
        self.serve(self.two_windows(**{
            window_url("2026-09-15"): RuntimeError("HTTP Error 403: Forbidden")}))
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", log)
        self.assertFalse((run.OUT / "area-cm-mantsala.json").exists())

    def test_a_refused_date_list_fails_the_site(self):
        self.serve({dates_url(): RuntimeError("HTTP Error 403: Forbidden")})
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", log)
        self.assertFalse((run.OUT / "area-cm-mantsala.json").exists())

    def test_a_date_list_spanning_years_is_refused_by_the_budget(self):
        """The window count comes from the cinema's list, so nothing else bounds it."""
        far = [f"2026-09-{d:02d}T21:00:00.000Z" for d in (14,)]
        far += [f"20{y}-06-0{d}T22:00:00.000Z"
                for y in range(27, 47) for d in (1, 9)]
        self.serve({dates_url(): dates_doc(*far)})
        code, log = self.main()
        self.assertEqual(code, 1)
        self.assertIn("budget", log)
        self.assertFalse((run.OUT / "area-cm-mantsala.json").exists())


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("cinemantsala")
        self.assertEqual((p["label"], p["host"], p["accent"], p["book"], p["module"],
                          p["where"]),
                         ("Cine Mäntsälä", "mantsala.cine.fi", "#5B21B6", "buy",
                          "cinemantsala", "cloud"))

    def test_the_accent_is_not_shared_with_another_chain(self):
        self.assertEqual(sum(1 for q in registry.PROVIDERS if q["accent"] == "#5B21B6"), 1)

    def test_it_is_a_separate_provider_from_the_cine_touring_entry(self):
        """Same brand, different deployment, different host, different half of the
        pipeline: `cine` is kiertue.cine.fi and runs locally."""
        cine = registry.by_id("cine")
        self.assertEqual(cine["where"], "local")
        self.assertNotEqual(cine["host"], registry.by_id("cinemantsala")["host"])
        self.assertNotEqual(cine["module"], registry.by_id("cinemantsala")["module"])

    def test_the_one_venue(self):
        site = cm.SITES[0]
        self.assertEqual([v["id"] for v in site["venues"]], ["cm-mantsala"])
        self.assertEqual((cm.VENUE["name"], cm.VENUE["short"], cm.VENUE["city"]),
                         ("Cine Mäntsälä", "Cine Mäntsälä", "Mäntsälä"))

    def test_the_site_names_the_host_it_reads(self):
        """`base` is run.py's pacing key, so a site without one shares a group with
        every other base-less site instead of being read on its own host."""
        self.assertEqual([s["base"] for s in cm.SITES], [BASE])
        self.assertEqual(len(run.host_groups(cm.SITES)), 1)
        self.assertEqual(run.host_of(cm.SITES[0]), "mantsala.cine.fi")

    def test_the_platform_tables_are_shared_with_the_other_mycloudcinema_adapter(self):
        """The row shape is the platform's. `FORMATS` and `LANG` are imported rather than
        copied so a format or a language code cannot drift between the two readers."""
        import gilda
        self.assertIs(cm.FORMATS, gilda.FORMATS)
        self.assertIs(cm.LANG, gilda.LANG)
        self.assertNotIn("version_digital", cm.FORMATS)


if __name__ == "__main__":
    unittest.main()
