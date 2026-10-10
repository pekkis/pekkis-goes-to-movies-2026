"""prices.py: the shared side step that reads a screening's public ticket page (2026-09-13).

One GET per screening key, sequential and paced, at most FETCH_MAX a run, refreshed
after TTL_H, three consecutive failures end the pass, a failed page is not cached, a
page with no usable price is cached as "" for the TTL, the cache is pruned to the
listing and written only when it changed. A failure never touches the rows.
"""
import contextlib
import datetime
import io
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import _ctx                                                # noqa: F401
import prices

PREFIX = "https://tickets.example.fi/show/"
NOW = datetime.datetime(2026, 9, 13, 12, 0, tzinfo=datetime.timezone.utc)


def parse(page):
    """The adapter's parser stand-in: the page is the price."""
    return page.strip()


def show(key, title="A"):
    return {"title": title, "url": PREFIX + key, "price": ""}


class FakeFetch:
    def __init__(self, pages, fail=()):
        self.pages, self.fail, self.gets = pages, set(fail), []

    def __call__(self, url, headers=None, **kw):
        self.gets.append(url)
        key = url.rsplit("/", 1)[1]
        if key in self.fail:
            raise OSError("boom")
        return self.pages[key].encode()


class FormatTest(unittest.TestCase):
    def test_amounts_take_etikettis_shape(self):
        self.assertEqual(prices.fmt("20,00"), "20€")
        self.assertEqual(prices.fmt("12,50"), "12.5€")
        self.assertEqual(prices.fmt("9"), "9€")
        self.assertEqual(prices.fmt("0,00"), "")
        self.assertEqual(prices.fmt("ilmainen"), "")

    def test_one_amount_needs_agreement(self):
        self.assertEqual(prices.one_amount(["20,00", "20.00"]), "20€")
        self.assertEqual(prices.one_amount(["20,00", "22,00"]), "")
        self.assertEqual(prices.one_amount([]), "")

    def test_the_key_is_the_last_path_segment_under_the_prefix(self):
        self.assertEqual(prices.key_of(PREFIX + "982926", PREFIX), "982926")
        self.assertEqual(prices.key_of(PREFIX + "abc/?x=1#t", PREFIX), "abc")
        self.assertEqual(prices.key_of("https://other.fi/show/1", PREFIX), "")
        self.assertEqual(prices.key_of(PREFIX, PREFIX), "")
        self.assertEqual(prices.key_of("", PREFIX), "")


class EnrichTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = pathlib.Path(self.tmp.name) / "prices-x.json"

    def run_it(self, shows, pages, fail=(), now=NOW, limit=None):
        fake = FakeFetch(pages, fail)
        with mock.patch.object(prices, "fetch", fake), mock.patch.object(prices.time, "sleep") as slept:
            st = prices.enrich(shows, provider="x", prefix=PREFIX, parse=parse, path=self.path,
                               now=now, sleep=0.7, limit=limit)
        return st, fake, slept

    def cache(self):
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else None

    def test_each_screening_gets_its_own_price_paced_and_in_order(self):
        shows = [show("1"), show("2")]
        st, fake, slept = self.run_it(shows, {"1": "20€", "2": "22€"})
        self.assertEqual([s["price"] for s in shows], ["20€", "22€"])
        self.assertEqual(fake.gets, [PREFIX + "1", PREFIX + "2"])
        slept.assert_called_once_with(0.7)
        self.assertEqual(st["fetched"], 2)
        self.assertEqual(self.cache()["1"], {"price": "20€", "at": NOW.isoformat()})

    def test_rows_sharing_a_key_are_read_once_and_other_urls_left_alone(self):
        shows = [show("7"), show("7"), {"title": "B", "url": "https://elsewhere.fi/", "price": ""}]
        st, fake, _ = self.run_it(shows, {"7": "18€"})
        self.assertEqual(fake.gets, [PREFIX + "7"])
        self.assertEqual([s["price"] for s in shows], ["18€", "18€", ""])
        self.assertEqual(st["screenings"], 1)

    def test_a_failed_page_is_not_cached_and_the_rows_survive(self):
        shows = [show("1"), show("2")]
        st, fake, _ = self.run_it(shows, {"2": "20€"}, fail=("1",))
        self.assertEqual([s["price"] for s in shows], ["", "20€"])
        self.assertEqual(st["failed"], 1)
        self.assertNotIn("1", self.cache())

    def test_an_unusable_page_is_cached_as_unknown_for_the_ttl(self):
        shows = [show("1")]
        self.run_it(shows, {"1": ""})
        self.assertEqual(self.cache()["1"]["price"], "")
        shows = [show("1")]
        st, fake, _ = self.run_it(shows, {"1": "20€"}, now=NOW + datetime.timedelta(hours=1))
        self.assertEqual((fake.gets, shows[0]["price"], st["unknown"]), ([], "", 1))

    def test_fresh_is_reused_and_expired_is_refreshed(self):
        self.run_it([show("1")], {"1": "20€"})
        shows = [show("1")]
        st, fake, _ = self.run_it(shows, {"1": "25€"}, now=NOW + datetime.timedelta(hours=prices.TTL_H - 1))
        self.assertEqual((fake.gets, shows[0]["price"], st["reused"]), ([], "20€", 1))
        shows = [show("1")]
        st, fake, _ = self.run_it(shows, {"1": "25€"}, now=NOW + datetime.timedelta(hours=prices.TTL_H))
        self.assertEqual((fake.gets, shows[0]["price"]), ([PREFIX + "1"], "25€"))

    def test_keys_off_the_listing_are_pruned(self):
        self.path.write_text(json.dumps({"9": {"price": "20€", "at": NOW.isoformat()}}), encoding="utf-8")
        self.run_it([show("1")], {"1": "20€"})
        self.assertEqual(set(self.cache()), {"1"})

    def test_the_ceiling_defers_the_rest_never_read_first_then_oldest(self):
        old = (NOW - datetime.timedelta(hours=100)).isoformat()
        older = (NOW - datetime.timedelta(hours=200)).isoformat()
        self.path.write_text(json.dumps({"1": {"price": "20€", "at": old},
                                         "2": {"price": "20€", "at": older}}), encoding="utf-8")
        shows = [show("1"), show("2"), show("3")]
        st, fake, _ = self.run_it(shows, {"1": "21€", "2": "22€", "3": "23€"}, limit=2)
        self.assertEqual(fake.gets, [PREFIX + "3", PREFIX + "2"])
        self.assertEqual(st["deferred"], 1)
        self.assertEqual([s["price"] for s in shows], ["20€", "22€", "23€"])

    def test_three_failures_in_a_row_end_the_pass(self):
        shows = [show(str(i)) for i in range(1, 6)]
        st, fake, _ = self.run_it(shows, {"4": "20€", "5": "20€"}, fail=("1", "2", "3"))
        self.assertEqual(len(fake.gets), 3)
        self.assertEqual((st["failed"], st["deferred"]), (3, 2))
        self.assertEqual([s["price"] for s in shows], [""] * 5)

    def test_the_cache_is_written_only_when_it_changed(self):
        self.run_it([show("1")], {"1": "20€"})
        stamp = self.path.stat().st_mtime_ns
        self.run_it([show("1")], {"1": "20€"})
        self.assertEqual(self.path.stat().st_mtime_ns, stamp)

    def test_run_never_raises(self):
        shows = [show("1")]
        with mock.patch.object(prices, "enrich", side_effect=RuntimeError("x")):
            prices.run(shows, provider="x", prefix=PREFIX, parse=parse, path=self.path)
        self.assertEqual(shows[0]["price"], "")


def lang_of(page):
    """A `fields` stand-in: pages read "price|lang"."""
    return {"lang": page.split("|")[1]} if "|" in page else {}


class FieldsTest(EnrichTest):
    """`fields`: more facts off the same page, never at the price's expense (2026-09-23).

    Every EnrichTest case runs again here with `fields` on, so the price behaviour is
    shown not to change; the one that pins the cache entry's exact shape is restated."""

    def run_it(self, shows, pages, fail=(), now=NOW, limit=None, fields=lang_of):
        fake = FakeFetch(pages, fail)
        with mock.patch.object(prices, "fetch", fake), mock.patch.object(prices.time, "sleep") as slept:
            st = prices.enrich(shows, provider="x", prefix=PREFIX,
                               parse=lambda p: p.split("|")[0], path=self.path,
                               now=now, sleep=0.7, limit=limit, fields=fields)
        return st, fake, slept

    def test_each_screening_gets_its_own_price_paced_and_in_order(self):
        shows = [show("1"), show("2")]
        st, fake, slept = self.run_it(shows, {"1": "20€", "2": "22€"})
        self.assertEqual([s["price"] for s in shows], ["20€", "22€"])
        self.assertEqual(fake.gets, [PREFIX + "1", PREFIX + "2"])
        slept.assert_called_once_with(0.7)
        self.assertEqual(self.cache()["1"], {"price": "20€", "at": NOW.isoformat(), "fields": {}})

    def test_the_fields_reach_the_rows_and_the_cache_beside_the_price(self):
        shows = [show("1"), show("1")]
        st, _, _ = self.run_it(shows, {"1": "20€|EN-A, FI-S"})
        self.assertEqual([(s["price"], s["lang"]) for s in shows], [("20€", "EN-A, FI-S")] * 2)
        self.assertEqual(self.cache()["1"],
                         {"price": "20€", "at": NOW.isoformat(), "fields": {"lang": "EN-A, FI-S"}})
        self.assertEqual(st["with_fields"], 1)

    def test_an_entry_cached_before_fields_is_read_once_more(self):
        self.path.write_text(json.dumps({"1": {"price": "20€", "at": NOW.isoformat()}}),
                             encoding="utf-8")
        shows = [show("1")]
        _, fake, _ = self.run_it(shows, {"1": "20€|FI-A"})
        self.assertEqual((fake.gets, shows[0]["lang"]), ([PREFIX + "1"], "FI-A"))
        shows = [show("1")]
        _, fake, _ = self.run_it(shows, {"1": "20€|FI-A"})
        self.assertEqual((fake.gets, shows[0]["lang"]), ([], "FI-A"))   # then it is fresh

    def test_a_failed_re_read_keeps_the_cached_price(self):
        self.path.write_text(json.dumps({"1": {"price": "20€", "at": NOW.isoformat()}}),
                             encoding="utf-8")
        shows = [show("1")]
        st, _, _ = self.run_it(shows, {}, fail=("1",))
        self.assertEqual((shows[0]["price"], shows[0].get("lang")), ("20€", None))
        self.assertEqual(self.cache(), {"1": {"price": "20€", "at": NOW.isoformat()}})
        self.assertEqual(st["failed"], 1)

    def test_fields_that_raise_leave_the_price_and_the_row(self):
        def broken(page):
            raise ValueError("unreadable")
        shows = [show("1")]
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.run_it(shows, {"1": "20€|FI-A"}, fields=broken)
        self.assertEqual((shows[0]["price"], shows[0].get("lang")), ("20€", None))
        self.assertEqual(self.cache()["1"]["fields"], {})
        self.assertIn("page fields 1: ValueError", out.getvalue())

    def test_a_row_s_own_value_is_not_overwritten(self):
        shows = [dict(show("1"), lang="SV-A")]
        self.run_it(shows, {"1": "20€|EN-A"})
        self.assertEqual(shows[0]["lang"], "SV-A")

    def test_never_read_first_then_the_entries_without_fields_then_the_oldest(self):
        fresh = NOW.isoformat()
        old = (NOW - datetime.timedelta(hours=prices.TTL_H + 1)).isoformat()
        self.path.write_text(json.dumps({
            "1": {"price": "20€", "at": fresh},                       # lacks fields
            "2": {"price": "20€", "at": old, "fields": {}},           # expired
            "4": {"price": "20€", "at": fresh, "fields": {}}}),       # fresh, complete
            encoding="utf-8")
        shows = [show("1"), show("2"), show("3"), show("4")]
        st, fake, _ = self.run_it(shows, {k: "21€|FI-A" for k in "1234"}, limit=2)
        self.assertEqual(fake.gets, [PREFIX + "3", PREFIX + "1"])
        self.assertEqual((st["deferred"], shows[1]["price"], shows[3]["price"]), (1, "20€", "20€"))


if __name__ == "__main__":
    unittest.main()
