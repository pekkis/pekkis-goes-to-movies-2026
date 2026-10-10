"""The Kino Kuusamotalo reader: one WordPress posts request, one post per film.

The fixtures are the post shapes as read on 2026-09-20, cut to the smallest that still
exercises a rule. Two posts and two screening lines everywhere there is a loop.

What they exist to prove:

- **`Esitysajat:` is what makes a post a film**, not its category: both notices on the
  site sit in `nykyinen-ohjelmisto` beside the films, and one of them in
  `tuleva-ohjelmisto` as well.
- **No date carries a year**, so the two-letter weekday places it through
  `common.resolve_year`, and a post left up past its run is refused rather than published
  ahead.
- **The clock may have no minutes.** `klo 15` and `klo 13.30` both appear.
- **A day may carry two clocks**, `klo 15 ja 19`, and each is a screening.
- **A line with a date and no clock publishes nothing.** Inventing an hour is the fault.
- **No poster is published.** The site's featured images are 160 px wide against the 342
  the client renders from, and nothing is upscaled.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest

import _ctx                                                # noqa: F401
import kuusamotalo as K
import registry
import run


SITE = K.SITES[0]
BASE = SITE["base"]
VENUE = SITE["venues"][0]["id"]
LISTING = BASE + SITE["listing"]
TODAY = datetime.date(2026, 9, 20)

SYN_FI = ("Klaus Härön uutuuselokuva kertoo kahden naisen kohtaamisesta keskellä "
          "hoitoalan kriisiä, kun sairaanhoitajat suunnittelevat lakkoa ja molemmat "
          "joutuvat tekemään vaikeita valintoja.")


def post(pid=15936, title="Hetki ennen valoa.", rating="-K7-", kesto="Kesto 1h 27min",
         liput="Liput 12€", syn=SYN_FI, times=("Su 20.9. klo 15", "Ti 22.9. klo 19"),
         cats=(3,), marker=True):
    body = "".join(f"<p>{x}</p>" for x in (rating, kesto, liput) if x)
    if syn:
        body += f"<p>{syn}</p>"
    if marker:
        body += "<p>Esitysajat:</p>"
    body += "".join(f"<p>{t}</p>" for t in times)
    return {"id": pid, "link": f"{BASE}/2026/09/20/{pid}/",
            "title": {"rendered": title}, "categories": list(cats),
            "content": {"rendered": body}}


def notice(pid=8996, title="Myymme myös lahjakortteja!"):
    return post(pid=pid, title=title, rating="", kesto="", liput="",
                syn="Myymme 10€ arvoisia lahjakortteja elokuviin.", times=(),
                cats=(3, 4), marker=False)


class PostTest(unittest.TestCase):
    def rows(self, *posts, today=TODAY):
        return K.rows(SITE, list(posts), today)

    def test_every_screening_line_of_every_film_post_becomes_a_row(self):
        shows, report = self.rows(
            post(),
            post(pid=15950, title="Rakkautta ja virtahepoja", rating="-K12-",
                 kesto="Kesto 1h 40min", cats=(3, 4),
                 times=("Pe 25.9. klo 19", "La 26.9. klo 19")))
        self.assertEqual((report["posts"], report["films"], report["notices"]), (2, 2, 0))
        self.assertEqual([(s["title"], s["start"]) for s in shows], [
            ("Hetki ennen valoa.", "2026-09-20T15:00:00+03:00"),
            ("Hetki ennen valoa.", "2026-09-22T19:00:00+03:00"),
            ("Rakkautta ja virtahepoja", "2026-09-25T19:00:00+03:00"),
            ("Rakkautta ja virtahepoja", "2026-09-26T19:00:00+03:00"),
        ])

    def test_a_post_with_no_esitysajat_line_is_counted_and_left_out(self):
        """Category is not the test: this notice sits in the programme category."""
        shows, report = self.rows(post(), notice(), notice(pid=10579, title="Tiedoksi"))
        self.assertEqual((report["films"], report["notices"]), (1, 2))
        self.assertEqual({s["title"] for s in shows}, {"Hetki ennen valoa."})

    def test_the_clock_may_have_no_minutes(self):
        shows, _ = self.rows(post(times=("Su 20.9. klo 15", "Su 27.9. klo 13.30")))
        self.assertEqual([s["start"] for s in shows],
                         ["2026-09-20T15:00:00+03:00", "2026-09-27T13:30:00+03:00"])

    def test_a_day_with_two_clocks_publishes_both(self):
        """The shape read on 2026-10-10, `La 10.10. klo 15 ja 19`."""
        shows, report = self.rows(post(times=(
            "La 26.9. klo 15 ja 19", "Su 27.9. klo 16", "Ke 30.9. klo 15 ja 19.30")))
        self.assertEqual([s["start"] for s in shows], [
            "2026-09-26T15:00:00+03:00", "2026-09-26T19:00:00+03:00",
            "2026-09-27T16:00:00+03:00",
            "2026-09-30T15:00:00+03:00", "2026-09-30T19:30:00+03:00"])
        self.assertEqual(report["no_clock"], 0)

    def test_the_year_comes_from_the_weekday(self):
        """20.9. is a Sunday in 2026 and a Saturday in 2025."""
        shows, _ = self.rows(post(times=("Su 20.9. klo 15",)))
        self.assertEqual(shows[0]["start"][:10], "2026-09-20")

    def test_a_date_the_window_refuses_is_counted_and_left_out(self):
        shows, report = self.rows(post(times=("Su 20.9. klo 15", "Ti 1.6. klo 18")))
        self.assertEqual((len(shows), report["undated"]), (1, 1))

    def test_a_dated_line_with_no_clock_publishes_nothing(self):
        """The coming-soon shape. Reading an hour out of it would be inventing one."""
        shows, report = self.rows(
            post(times=("Su 20.9. klo 15", "Pe 9.10. alkaen.")))
        self.assertEqual((len(shows), report["no_clock"]), (1, 1))

    def test_the_show_shape(self):
        s = self.rows(post())[0][0]
        self.assertEqual((s["provider"], s["venue"], s["aud"], s["img"], s["lang"],
                          s["method"], s["original"], s["soldOut"]),
                         ("kuusamotalo", VENUE, "Oulankasali", "", "", "", "", False))
        self.assertEqual((s["eventId"], s["theatre"], s["rating"], s["len"], s["price"]),
                         ("15936", "Kino Kuusamotalo", "K-7", "87", "12€"))
        self.assertEqual(s["url"], f"{BASE}/2026/09/20/15936/")

    def test_no_poster_is_ever_published_from_this_site(self):
        """160 px wide against the 342 the client renders from, and nothing upscales."""
        shows, _ = self.rows(post(), post(pid=15950, title="Toinen"))
        self.assertEqual({s["img"] for s in shows}, {""})


class FieldTest(unittest.TestCase):
    def test_the_rating_marker_is_read_from_its_dashes(self):
        self.assertEqual(K.rating_of(["-K7-"]), "K-7")
        self.assertEqual(K.rating_of(["-K12-"]), "K-12")
        self.assertEqual(K.rating_of(["-S-"]), "S")

    def test_a_line_that_is_not_a_marker_leaves_the_rating_empty(self):
        self.assertEqual(K.rating_of(["Kesto 1h 27min", "K7", "-K7"]), "")
        self.assertEqual(K.rating_of([]), "")

    def test_the_runtime_counts_the_hours(self):
        self.assertEqual(K.minutes_of(["Kesto 1h 27min"]), "87")
        self.assertEqual(K.minutes_of(["Kesto 1h 40min"]), "100")
        self.assertEqual(K.minutes_of(["Kesto 95 min"]), "95")
        self.assertEqual(K.minutes_of(["Liput 12€"]), "")

    def test_one_bare_amount_is_published_and_anything_else_is_not(self):
        self.assertEqual(K.price_of(["Liput 12€"]), "12€")
        self.assertEqual(K.price_of(["Liput 9,50 €"]), "9,50€")
        for line in ("Liput 12€ / 10€", "Liput 12€ (eläkeläiset 11€)", "Liput"):
            with self.subTest(line=line):
                self.assertEqual(K.price_of([line]), "")

    def test_the_synopsis_is_placed_by_its_language(self):
        shows, report = K.rows(SITE, [post()], TODAY)
        self.assertEqual(shows[0]["_syn"], {"fi": SYN_FI})
        self.assertEqual(report["unplaced_syn"], set())

    def test_a_text_in_no_settled_language_is_withheld_and_counted(self):
        odd = ("Odysseus. Troija, Ithaka, Kirke, Kalypso, Skylla, Kharybdis, Poseidon, "
               "Penelope, Telemakhos, Polyfemos, Aiolos, Laistrygonit, Helios.")
        shows, report = K.rows(SITE, [post(title="The Odyssey", syn=odd)], TODAY)
        self.assertNotIn("_syn", shows[0])
        self.assertEqual(report["unplaced_syn"], {"The Odyssey"})

    def test_a_short_note_is_not_a_synopsis(self):
        shows, report = K.rows(SITE, [post(syn="Tervetuloa!")], TODAY)
        self.assertNotIn("_syn", shows[0])
        self.assertEqual(report["unplaced_syn"], set())


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._out = run.OUT
        run.OUT = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(run, "OUT", self._out))
        self._get = K.get_text
        self.addCleanup(lambda: setattr(K, "get_text", self._get))
        self.calls = []

    def serve(self, pages):
        def get_text(url, **kw):
            self.calls.append(url)
            body = pages.get(url)
            if isinstance(body, Exception):
                raise body
            if body is None:
                raise RuntimeError(f"unexpected fetch {url}")
            return body
        K.get_text = get_text

    def main(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run.main(["kuusamotalo", "--half", "all"])
        return code, out.getvalue() + err.getvalue()

    def kept(self):
        doc = {"generated": "2026-09-19T00:00:00+00:00", "dates": ["2026-09-19"],
               "horizon": "2026-09-19",
               "shows": [{"title": "Yesterday", "start": "2026-09-19T17:00:00+03:00"}]}
        (run.OUT / f"area-{VENUE}.json").write_text(json.dumps(doc), encoding="utf-8")

    def after(self):
        return json.loads((run.OUT / f"area-{VENUE}.json").read_text(encoding="utf-8"))

    def test_the_site_publishes_from_one_request(self):
        self.serve({LISTING: json.dumps(
            [post(), post(pid=15950, title="Rakkautta ja virtahepoja",
                          times=("Pe 25.9. klo 19", "La 26.9. klo 19")), notice()])})
        code, log = self.main()
        self.assertEqual(code, 0, log)
        self.assertEqual(self.calls, [LISTING])
        self.assertEqual(sorted({s["title"] for s in self.after()["shows"]}),
                         ["Hetki ennen valoa.", "Rakkautta ja virtahepoja"])
        self.assertIn("1 post(s) with no Esitysajat line", log)

    def test_a_post_set_with_no_film_fails_and_keeps_the_previous_file(self):
        self.kept()
        self.serve({LISTING: json.dumps([notice(), notice(pid=10579, title="Tiedoksi")])})
        code, log = self.main()
        self.assertNotEqual(code, 0)
        self.assertIn("no post carries a placed screening line", log)
        self.assertEqual(self.after()["shows"][0]["title"], "Yesterday")

    def test_an_answer_that_is_not_json_fails_and_keeps_the_previous_file(self):
        self.kept()
        self.serve({LISTING: "<html>maintenance</html>"})
        code, log = self.main()
        self.assertNotEqual(code, 0)
        self.assertIn("did not answer JSON", log)
        self.assertEqual(self.after()["shows"][0]["title"], "Yesterday")

    def test_an_answer_that_is_not_a_list_fails(self):
        self.kept()
        self.serve({LISTING: json.dumps({"code": "rest_no_route"})})
        code, log = self.main()
        self.assertNotEqual(code, 0)
        self.assertIn("not a list of posts", log)
        self.assertEqual(self.after()["shows"][0]["title"], "Yesterday")

    def test_a_refused_request_keeps_the_previous_file(self):
        self.kept()
        self.serve({LISTING: RuntimeError("503 refused")})
        self.assertNotEqual(self.main()[0], 0)
        self.assertEqual(self.after()["shows"][0]["title"], "Yesterday")


class RegistryTest(unittest.TestCase):
    def test_the_registry_entry(self):
        p = registry.by_id("kuusamotalo")
        self.assertEqual((p["label"], p["host"], p["book"], p["module"], p["where"]),
                         ("Kino Kuusamotalo", "kinokuusamotalo.fi", "door",
                          "kuusamotalo", "cloud"))
        self.assertEqual(sum(1 for q in registry.PROVIDERS
                             if q["accent"] == p["accent"]), 1)

    def test_the_site_is_read_from_the_cinemas_own_host(self):
        """kuusamotalo.fi is the culture house and names no film; the cinema's own site
        is the source and the one this is paced on."""
        self.assertEqual(SITE["base"], "https://kinokuusamotalo.fi")
        self.assertNotIn("reads", SITE)


if __name__ == "__main__":
    unittest.main()
