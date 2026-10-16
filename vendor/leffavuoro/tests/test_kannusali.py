"""The Kannusali reader: the listing's own POST to espoo.fi's events service, paged.

Hits follow the shape read on 2026-10-13, seven of them over two pages of four.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import common
import kannusali as K
import registry
import run


SITE = K.SITES[0]
VENUE = SITE["venues"][0]["id"]
URL = SITE["base"] + SITE["path"]
EVENT = "/fi/tapahtumat/espooevents:"


def hit(hid, title, start, end=None, free=True):
    if end is None:
        two = datetime.datetime.fromisoformat(start) + datetime.timedelta(hours=2)
        end = two.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"id": "event:espooevents:" + hid, "title": title, "path": EVENT + hid,
            "eventStartTime": start, "eventEndTime": end,
            "topics": ["Elokuvat", "Kulttuuritapahtumat"], "isFreeEvent": free,
            "location": "Kannusali", "eventImages": [{"url": "https://example.invalid/i.jpg"}]}


KEVLAR = hit("agqam3geym", "Elokuva: Kevlarsjäl (K12)", "2026-10-21T11:00:00Z")
ISANPAIVA = hit("agqaol4qfu", "Elokuva: Isänpäivä (K7)", "2026-11-08T12:00:00Z")
FLOW_KIDS = hit("agqaw7ipcm", "Lasten viikonloppu, Elokuva: Flow. (K7)", "2026-11-22T12:00:00Z")
FLOW = hit("agqaw5sf2u", "Elokuva: Flow. (K7)", "2026-11-22T12:00:00Z")
FESTIVAL = hit("agqfestiva", "Espoo Ciné Film Festival Kannusalissa 2026",
               "2026-08-21T14:00:00Z", "2026-08-23T15:00:00Z", free=False)
SNOWMAN = hit("agqbi7fj4u", "Lumiukko - Elokuvakonsertti", "2026-12-16T16:00:00Z",
              "2026-12-16T16:30:00Z", free=False)
SNOWMAN2 = hit("agqbi7q5w4", "Lumiukko - Elokuvakonsertti", "2026-12-16T17:30:00Z",
               "2026-12-16T18:00:00Z", free=False)
# The Flow row with the larger id sits on page 1 and its twin on page 2.
HITS = [KEVLAR, FLOW_KIDS, FESTIVAL, ISANPAIVA, FLOW, SNOWMAN, SNOWMAN2]
SWEDISH = "Elokuva on ruotsinkielinen ja siinä on tekstitys suomeksi."
CONCERT = dict(hit("agqconcert", "Megamuskari", "2026-11-03T08:30:00Z", free=False),
               topics=["Kulttuuritapahtumat", "Musiikki"])
LE = K.LE_HOST + K.LE_PATH
PIC = "https://tapahtumasyotto.espoo.fi/media/images/"


def le_event(hid, url=None, licence="event_only", by="", alt="Kuvassa yhtye."):
    """One Linked Events event as the place query answers it, with one picture."""
    return {"id": "espooevents:" + hid, "images": [
        {"url": url or PIC + hid + ".jpg", "license": licence, "photographer_name": by,
         "alt_text": alt, "name": "", "cropping": "286,0,914,628"}]}


class PictureTest(unittest.TestCase):
    def test_a_picture_keeps_its_licence_photographer_and_alt_text(self):
        got = K.picture_of(le_event("agqconcert", by=" Katri Kuusela "))
        self.assertEqual(got, {"img": PIC + "agqconcert.jpg", "imgLic": "event_only",
                               "imgBy": "Katri Kuusela", "imgAlt": "Kuvassa yhtye.",
                               "imgSrc": "Espoon tapahtumarajapinta"})
        self.assertEqual(K.picture_of(le_event("x", licence="cc_by"))["imgLic"], "cc_by")

    def test_a_picture_under_any_other_licence_is_not_published(self):
        for licence in ("cc_by_sa", "", None):
            with self.subTest(licence=licence):
                self.assertIsNone(K.picture_of(le_event("x", licence=licence)))

    def test_only_an_https_picture_is_taken_and_an_odd_alt_text_is_dropped(self):
        ev = le_event("x", alt={"fi": "teksti"})
        ev["images"].insert(0, {"url": "http://example.invalid/a.jpg", "license": "cc_by"})
        self.assertEqual((K.picture_of(ev)["img"], K.picture_of(ev)["imgAlt"]),
                         (PIC + "x.jpg", ""))
        self.assertIsNone(K.picture_of({"id": "espooevents:y", "images": []}))


def page(*paras):
    """An event page as espoo.fi renders it, the description inside `__NEXT_DATA__`."""
    data = {"props": {"graphQLState": {"q": {"data": {"Event": {
        "description": "".join(f"<p>{p}</p>" for p in paras)}}}}}}
    return ('<html><body><main>rendered</main><script id="__NEXT_DATA__" '
            'type="application/json">' + json.dumps(data) + "</script></body></html>")


class LanguageTest(unittest.TestCase):
    def test_the_three_wordings_on_the_film_pages(self):
        for sentence, lang in (
                (SWEDISH, "SV-A, FI-S"),
                ("Elokuva on suomenkielinen ja siinä on ruotsinkielinen tekstitys.", "FI-A, SV-S"),
                ("Elokuva on englanninkielinen ja siinä on tekstitys kielillä suomi ja ruotsi.",
                 "EN-A, FI-S, SV-S"),
                ("Elokuva on suomenkielinen.", "FI-A")):
            with self.subTest(sentence=sentence):
                self.assertEqual(K.lang_of(["Synopsis.", sentence, "K12."]), lang)

    def test_any_other_wording_gives_nothing(self):
        for sentence in ("Elokuvassa ei ole kielellistä dialogia eikä tekstityksiä.",
                         "Elokuva on klingoninkielinen ja siinä on tekstitys suomeksi.",
                         "Elokuva on ruotsinkielinen ja siinä on tekstitys klingoniksi.",
                         SWEDISH + " Mukana myös lyhytelokuva.",
                         "Elokuva on ruotsinkielinen, tekstitys suomeksi."):
            with self.subTest(sentence=sentence):
                self.assertEqual(K.lang_of([sentence]), "")

    def test_the_description_is_read_from_the_page_data_as_plain_paragraphs(self):
        got = K.description(page("Alex &amp; Robin.", "<strong>Elokuva on ruotsinkielinen</strong>"
                                 " ja siinä on tekstitys\u00a0suomeksi."))
        self.assertEqual(got, ["Alex & Robin.", SWEDISH])
        self.assertEqual(K.lang_of(got), "SV-A, FI-S")

    def test_a_page_without_its_data_has_no_description(self):
        self.assertEqual(K.description("<html><p>Elokuva on suomenkielinen.</p></html>"), [])



class RowsTest(unittest.TestCase):
    def rows(self, *hits):
        return K.rows(SITE, list(hits))

    def test_the_utc_instant_is_published_as_helsinki_local_on_both_sides_of_the_change(self):
        shows, _ = self.rows(KEVLAR, ISANPAIVA)
        self.assertEqual([s["start"] for s in shows],
                         ["2026-10-21T14:00:00+03:00", "2026-11-08T14:00:00+02:00"])

    def test_a_span_over_24_hours_is_left_out_and_counted(self):
        shows, report = self.rows(FESTIVAL, KEVLAR)
        self.assertEqual([s["title"] for s in shows], ["Kevlarsjäl"])
        self.assertEqual(report["long"], ["event:espooevents:agqfestiva "
                                          "(Espoo Ciné Film Festival Kannusalissa 2026)"])

    def test_a_span_of_exactly_24_hours_is_kept(self):
        day = hit("agqday", "Elokuva: Päivä", "2026-11-01T10:00:00Z", "2026-11-02T10:00:00Z")
        shows, report = self.rows(day)
        self.assertEqual((len(shows), report["long"]), (1, []))

    def test_a_hit_outside_the_film_topic_is_an_event_labelled_by_its_topics(self):
        dance = dict(hit("agqdance", "Elokuva: Päivätanssit (K7)", "2026-11-12T12:00:00Z"),
                     topics=["Kulttuuritapahtumat", "Liikunta", "Musiikki", "Tanssi"])
        shows, _ = self.rows(KEVLAR, CONCERT, dance)
        self.assertEqual([(s["title"], s["rating"], s["method"], s["price"], s.get("nonFilm"))
                          for s in shows], [
            ("Kevlarsjäl", "K-12", "", "Vapaa pääsy", None),
            ("Megamuskari", "", "Musiikki", "", True),
            ("Elokuva: Päivätanssit (K7)", "", "Liikunta \u00b7 Musiikki \u00b7 Tanssi",
             "Vapaa pääsy", True),
        ])
        common.check_shows({VENUE: shows}, "kannusali", {VENUE})

    def test_a_concert_and_a_film_under_one_title_key_apart(self):
        concert = dict(CONCERT, title="Michael", eventStartTime="2026-12-11T17:00:00Z")
        film = hit("agqaxzismq", "Elokuva: Michael (K12)", "2026-12-10T12:00:00Z")
        shows, _ = self.rows(film, concert)
        self.assertEqual([(s["title"], s["eventId"], s.get("nonFilm")) for s in shows],
                         [("Michael", "michael", None), ("Michael", "tapahtuma-michael", True)])
        common.check_shows({VENUE: shows}, "kannusali", {VENUE})

    def test_a_hit_at_another_place_fails_the_site(self):
        elsewhere = dict(CONCERT, location="Sellosali")
        with self.assertRaises(K.EventRowError) as e:
            self.rows(KEVLAR, elsewhere)
        self.assertIn("Sellosali", str(e.exception))

    def test_a_closing_sold_out_note_leaves_the_title_and_marks_the_row(self):
        sold = [dict(CONCERT, id=f"event:espooevents:agqsold{n}", title=title,
                     eventStartTime=f"2026-11-1{n}T17:00:00Z")
                for n, title in enumerate(("Tuomari Nurmio (LOPPUUNMYYTY)",
                                           "Ykspihlajan Kino-Orkesteri LOPPUUNMYYTY",
                                           "LOPPUUNMYYTY", "Loppuunmyyty ilta"))]
        shows, _ = self.rows(*sold)
        self.assertEqual([(s["title"], s["soldOut"], s["eventId"]) for s in shows], [
            ("Tuomari Nurmio", True, "tapahtuma-tuomari-nurmio"),
            ("Ykspihlajan Kino-Orkesteri", True, "tapahtuma-ykspihlajan-kino-orkesteri"),
            ("LOPPUUNMYYTY", False, "tapahtuma-loppuunmyyty"),
            ("Loppuunmyyty ilta", False, "tapahtuma-loppuunmyyty-ilta"),
        ])

    def test_two_hits_at_one_start_collapse_to_the_smallest_id_in_either_order(self):
        for order in ((FLOW_KIDS, FLOW), (FLOW, FLOW_KIDS)):
            with self.subTest(first=order[0]["id"]):
                shows, report = self.rows(*order)
                self.assertEqual([(s["title"], s["url"]) for s in shows],
                                 [("Flow.", "https://www.espoo.fi" + EVENT + "agqaw5sf2u")])
                self.assertEqual(report["collapsed"], [
                    "event:espooevents:agqaw7ipcm (Lasten viikonloppu, Elokuva: Flow. (K7)), "
                    "same start as event:espooevents:agqaw5sf2u"])

    def test_hits_at_different_minutes_are_all_kept(self):
        shows, report = self.rows(SNOWMAN, SNOWMAN2)
        self.assertEqual([s["start"] for s in shows],
                         ["2026-12-16T18:00:00+02:00", "2026-12-16T19:30:00+02:00"])
        self.assertEqual(report["collapsed"], [])

    def test_a_free_hit_is_free_admission_and_a_paid_one_publishes_no_price(self):
        shows, _ = self.rows(KEVLAR, SNOWMAN)
        self.assertEqual([(s["title"], s["price"]) for s in shows],
                         [("Kevlarsjäl", "Vapaa pääsy"),
                          ("Lumiukko - Elokuvakonsertti", "")])

    def test_the_title_drops_its_prefix_and_its_closing_mark_which_is_the_rating(self):
        allowed = hit("agqsallit", "Elokuva: Muumit (S)", "2026-11-29T12:00:00Z")
        shows, _ = self.rows(KEVLAR, ISANPAIVA, allowed, SNOWMAN)
        self.assertEqual([(s["title"], s["rating"], s["eventId"]) for s in shows], [
            ("Kevlarsjäl", "K-12", "kevlarsjäl"),
            ("Isänpäivä", "K-7", "isänpäivä"),
            ("Muumit", "S", "muumit"),
            ("Lumiukko - Elokuvakonsertti", "", "lumiukko-elokuvakonsertti"),
        ])

    def test_only_a_leading_prefix_and_a_closing_kavi_mark_come_off_the_title(self):
        for title, shown in (("Lasten viikonloppu, Elokuva: Flow. (K7)",
                              "Lasten viikonloppu, Elokuva: Flow."),
                             ("Elokuva: Yö (K13)", "Yö (K13)"),
                             ("Elokuva: Flow. (K7) ja keskustelu", "Flow. (K7) ja keskustelu"),
                             ("Elokuvakonsertti: Lumiukko", "Elokuvakonsertti: Lumiukko"),
                             ("ELOKUVA:Sininen (K16)", "Sininen"),
                             ("Elokuva: (K7)", "Elokuva: (K7)")):
            with self.subTest(title=title):
                self.assertEqual(K.shown_title(title), shown)

    def test_a_mark_that_is_not_a_closing_kavi_class_is_no_rating(self):
        for title in ("Elokuva: Flow. (K7) ja keskustelu", "Elokuva: Yö (K13)",
                      "Elokuva: Sininen (7)", "ELLIMEI S/K18"):
            with self.subTest(title=title):
                self.assertEqual(K.rating_of(title), "")

    def test_the_link_is_the_event_page_and_no_image_is_published(self):
        s = self.rows(KEVLAR)[0][0]
        self.assertEqual(s["url"], "https://www.espoo.fi/fi/tapahtumat/espooevents:agqam3geym")
        self.assertEqual(s["img"], "")

    def test_the_show_shape(self):
        s = self.rows(KEVLAR)[0][0]
        self.assertEqual((s["provider"], s["venue"], s["theatre"], s["aud"], s["lang"],
                          s["method"], s["original"], s["len"], s["genres"], s["soldOut"]),
                         ("kannusali", VENUE, "Kannusali", "", "", "", "", "", "", False))
        self.assertEqual(s["eventId"], "kevlarsjäl")
        self.assertNotIn("nonFilm", s)
        common.check_shows({VENUE: [s]}, "kannusali", {VENUE})

    def test_a_hit_it_cannot_read_fails_the_site(self):
        for field, value in (("title", ""), ("path", None), ("path", "fi/tapahtumat/x"),
                             ("eventStartTime", None), ("eventStartTime", "soon"),
                             ("eventStartTime", "2026-11-04T12:00:00"),
                             ("eventEndTime", "later"), ("topics", None)):
            with self.subTest(field=field, value=value):
                bad = dict(KEVLAR, **{field: value})
                with self.assertRaises(K.EventRowError):
                    self.rows(ISANPAIVA, bad)


class ServiceTest(unittest.TestCase):
    """The service stubbed by URL: it answers slices of `hits` by the body's pagination."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name, value in (("PER_PAGE", 4), ("PAUSE", 0)):
            self.addCleanup(setattr, K, name, getattr(K, name))
            setattr(K, name, value)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._get = K.get_text
        self.addCleanup(lambda: setattr(K, "get_text", self._get))
        self.calls, self.pages, self.le_calls = [], [], []

    def serve(self, hits, total=None, short=False, pages=None, le=None):
        """`pages` maps an event id to its page, or to an exception the read raises. `le` is
        the Linked Events answers in order, each a dict or an exception."""
        answers = list(le or [{"data": [], "meta": {"next": None}}])

        def get_text(url, **kw):
            if url.startswith(LE):
                self.le_calls.append(url)
                answer = answers.pop(0)
                if isinstance(answer, Exception):
                    raise answer
                return json.dumps(answer)
            if url.startswith(SITE["base"] + EVENT):
                self.pages.append(url)
                answer = (pages or {}).get(url.rsplit(":", 1)[1], page("No language here."))
                if isinstance(answer, Exception):
                    raise answer
                return answer
            if url != URL:
                raise AssertionError(f"unexpected request to {url}")
            body = json.loads(kw["data"].decode("utf-8"))
            self.calls.append((body, kw))
            window = body["pagination"]
            got = hits[window["offset"]:window["offset"] + window["perPage"]]
            if short and window["offset"]:
                got = []
            return json.dumps({"total": len(hits) if total is None else total,
                               "hits": [{"_source": h} for h in got], "aggs": {}})
        K.get_text = get_text

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["kannusali", "--half", "all"])
        return code, out.getvalue() + err.getvalue()

    def area(self):
        return json.loads((run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))

    def keep_previous(self):
        kept = {"generated": "2026-10-12T00:00:00+00:00", "dates": ["2026-11-04"],
                "horizon": "2026-11-04",
                "shows": [{"title": "Earlier", "start": "2026-11-04T14:00:00+02:00"}]}
        (run.OUT / f"area-{VENUE}.json").write_text(json.dumps(kept), encoding="utf-8")

    def test_every_page_is_read_until_the_total_is_covered(self):
        self.serve(HITS)
        with contextlib.redirect_stdout(io.StringIO()):
            shows = K.fetch_site(SITE)[VENUE]
        self.assertEqual([c[0]["pagination"] for c in self.calls],
                         [{"offset": 0, "perPage": 4}, {"offset": 4, "perPage": 4}])
        self.assertEqual([(s["start"][:16], s["title"]) for s in shows], [
            ("2026-10-21T14:00", "Kevlarsjäl"),
            ("2026-11-08T14:00", "Isänpäivä"),
            ("2026-11-22T14:00", "Flow."),
            ("2026-12-16T18:00", "Lumiukko - Elokuvakonsertti"),
            ("2026-12-16T19:30", "Lumiukko - Elokuvakonsertti"),
        ])

    def test_the_request_is_the_listing_s_own_filter(self):
        self.serve(HITS)
        with contextlib.redirect_stdout(io.StringIO()):
            K.fetch_site(SITE)
        body, kw = self.calls[0]
        self.assertEqual(body["filters"]["fixedFilters"]["tprId"], "21430")
        self.assertEqual(body["filters"]["topics"], [])
        self.assertEqual((body["langcode"], body["type"], body["showLongLastingEvents"]),
                         ("fi", "event", True))
        self.assertEqual(kw["headers"]["content-type"], "application/json")
        self.assertEqual(kw["headers"]["user-agent"], common.UA)
        self.assertFalse(kw["cache"])

    def test_a_page_with_no_hits_before_the_total_fails(self):
        """It stops at the empty page instead of asking again up to MAX_PAGES times."""
        self.serve(HITS, short=True)
        with self.assertRaisesRegex(RuntimeError, "no hits at offset 4 of a total of 7"):
            K.fetch_site(SITE)
        self.assertEqual(len(self.calls), 2)

    def test_the_run_writes_the_venue_file_and_logs_both_drops(self):
        self.serve(HITS)
        code, log = self.main()
        self.assertEqual(code, 0, log)
        shows = self.area()["shows"]
        self.assertEqual(len(shows), 5)
        self.assertEqual({s["venue"] for s in shows}, {VENUE})
        self.assertEqual([s["rating"] for s in shows], ["K-12", "K-7", "K-7", "", ""])
        self.assertIn("1 hit(s) spanning over 24 h left out: event:espooevents:agqfestiva", log)
        self.assertIn("collapsed event:espooevents:agqaw7ipcm (Lasten viikonloppu, "
                      "Elokuva: Flow. (K7)), same start as event:espooevents:agqaw5sf2u", log)

    def test_zero_hits_fails_the_run_and_keeps_the_previous_file(self):
        self.keep_previous()
        self.serve([])
        with self.assertRaises(RuntimeError) as ctx:
            K.fetch_site(SITE)
        self.assertNotIsInstance(ctx.exception, common.EmptyProgramme)
        code, log = self.main()
        self.assertNotEqual(code, 0, log)
        self.assertIn("no hit for place 21430", log)
        self.assertEqual(self.area()["shows"][0]["title"], "Earlier")

    def test_an_unreadable_hit_fails_the_run_and_keeps_the_previous_file(self):
        self.keep_previous()
        self.serve([KEVLAR, dict(ISANPAIVA, eventStartTime="")])
        code, log = self.main()
        self.assertNotEqual(code, 0, log)
        self.assertEqual(self.area()["shows"][0]["title"], "Earlier")


    def test_one_page_per_film_gives_every_screening_its_languages(self):
        twin = hit("agqam36pti", "Elokuva: Kevlarsjäl (K12)", "2026-10-21T15:00:00Z")
        self.serve(HITS + [twin], pages={"agqam3geym": page("Synopsis.", SWEDISH),
                                         "agqaol4qfu": page("Elokuva on suomenkielinen ja "
                                                            "siinä on ruotsinkielinen tekstitys.")})
        with contextlib.redirect_stdout(io.StringIO()):
            shows = K.fetch_site(SITE)[VENUE]
        self.assertEqual([(s["title"], s["lang"]) for s in shows], [
            ("Kevlarsjäl", "SV-A, FI-S"), ("Kevlarsjäl", "SV-A, FI-S"),
            ("Isänpäivä", "FI-A, SV-S"), ("Flow.", ""),
            ("Lumiukko - Elokuvakonsertti", ""), ("Lumiukko - Elokuvakonsertti", "")])
        self.assertEqual(len(self.pages), 4, self.pages)
        self.assertEqual(sum(p.endswith("agqam3geym") for p in self.pages), 1)

    def test_a_page_that_fails_leaves_its_film_without_languages_and_the_rest_read(self):
        self.serve(HITS, pages={"agqam3geym": OSError("connection reset"),
                                "agqaol4qfu": page(SWEDISH)})
        code, log = self.main()
        self.assertEqual(code, 0, log)
        langs = {s["title"]: s["lang"] for s in self.area()["shows"]}
        self.assertEqual((langs["Kevlarsjäl"], langs["Isänpäivä"]), ("", "SV-A, FI-S"))
        self.assertIn("event page for Kevlarsjäl: OSError: connection reset", log)
        self.assertIn("languages read for 1 of 4 film(s)", log)

    def test_a_concert_is_published_and_its_page_is_not_read(self):
        self.serve(HITS + [CONCERT], pages={"agqconcert": page(SWEDISH)})
        code, log = self.main()
        self.assertEqual(code, 0, log)
        shows = self.area()["shows"]
        concert = next(s for s in shows if s["title"] == "Megamuskari")
        self.assertEqual((concert["nonFilm"], concert["method"], concert["lang"]),
                         (True, "Musiikki", ""))
        self.assertFalse(any(p.endswith("agqconcert") for p in self.pages), self.pages)
        self.assertIn("6 showtimes, 5 of them films", log)

    def test_one_query_gives_each_non_film_event_its_picture_and_no_film_one(self):
        self.serve(HITS + [CONCERT], le=[{"data": [
            le_event("agqconcert", by="Katri Kuusela"), le_event("agqam3geym")],
            "meta": {"next": None}}])
        code, log = self.main()
        self.assertEqual(code, 0, log)
        shows = self.area()["shows"]
        concert = next(s for s in shows if s.get("nonFilm"))
        self.assertEqual({k: concert[k] for k in ("img", "imgLic", "imgBy", "imgSrc")},
                         {"img": PIC + "agqconcert.jpg", "imgLic": "event_only",
                          "imgBy": "Katri Kuusela", "imgSrc": "Espoon tapahtumarajapinta"})
        film = next(s for s in shows if s["title"] == "Kevlarsjäl")
        self.assertEqual((film["img"], film.get("imgLic")), ("", None))
        self.assertEqual(len(self.le_calls), 1)
        self.assertIn("location=tprek:21430", self.le_calls[0])
        self.assertIn("event pictures for 1 of 1 non-film event(s)", log)

    def test_the_next_page_is_asked_of_the_declared_host(self):
        self.serve([CONCERT], le=[
            {"data": [], "meta": {"next": "https://elsewhere.invalid/events/v1/event/?page=2"}},
            {"data": [le_event("agqconcert")], "meta": {"next": None}}])
        with contextlib.redirect_stdout(io.StringIO()):
            shows = K.fetch_site(SITE)[VENUE]
        self.assertEqual(self.le_calls[1], LE + "?page=2")
        self.assertEqual(shows[0]["img"], PIC + "agqconcert.jpg")

    def test_a_failed_or_endless_query_costs_the_pictures_and_nothing_else(self):
        endless = {"data": [], "meta": {"next": LE + "?page=n"}}
        for le, said in (([OSError("connection reset")], "OSError: connection reset"),
                         ([endless] * K.LE_PAGES, "more than 5 pages")):
            with self.subTest(said=said):
                self.le_calls = []
                self.serve(HITS + [CONCERT], le=le)
                code, log = self.main()
                self.assertEqual(code, 0, log)
                self.assertIn(f"event pictures: ", log)
                self.assertIn(said, log)
                concert = next(s for s in self.area()["shows"] if s.get("nonFilm"))
                self.assertEqual((concert["img"], concert.get("imgLic")), ("", None))

class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("kannusali")
        self.assertIsNotNone(p, "no registry entry for kannusali")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Kannusali", "espoo.fi", "list", "kannusali", "cloud"))
        self.assertEqual((p["accent"], p["accentDark"]), ("#00A192", "#81D7B6"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"].upper() == p["accent"].upper()), 1)

    def test_the_venue_is_in_espoo_inside_the_capital_region(self):
        """Its accent is measured against the Espoo view and the Pääkaupunkiseutu row."""
        self.assertEqual({v["city"] for v in SITE["venues"]}, {"Espoo"})
        self.assertIn("Espoo", next(r["cities"] for r in registry.REGIONS
                                    if r["name"] == "Pääkaupunkiseutu"))


class SiteTest(unittest.TestCase):
    def test_the_site_names_the_host_it_is_read_from(self):
        self.assertEqual(SITE["base"], "https://www.espoo.fi")
        self.assertEqual(SITE["reads"], ("api.espoo.fi",))
        self.assertEqual(K.LE_HOST, "https://api.espoo.fi")
        self.assertEqual(SITE["venues"], [{"id": "kannusali-espoo", "name": "Kannusali",
                                           "short": "Kannusali", "city": "Espoo"}])


if __name__ == "__main__":
    unittest.main()
