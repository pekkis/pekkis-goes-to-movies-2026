"""Riviera: a screening's price comes from its own public ticket page (2026-09-13).

The fetch, cache and pacing live in prices.py since the same day (shared with Regina and
Korjaamo) and are pinned in tests/test_prices.py; these tests run the whole adapter
through fetch_site() so the wiring is covered too.

The listing carries no price. `tickets.rivieracinemas.fi/websales/show/{id}` prints a
`table.showPrices-table`, one row per ticket category; the ordinary seat is "Sohvapaikka
tai Nojatuolipaikka" and only that row counts. Fixtures here are the table's shape with
its tokens and form fields left out.

The enrichment is a bounded, cached side step after the schedule: one GET per screening
id, sequential, refreshed after PRICE_TTL_H, at most PRICE_FETCH_MAX pages a run, three
consecutive failures end the pass. A failure leaves the price "" and never touches the
showtimes.
"""
import datetime
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import _ctx                                                # noqa: F401
import build_pages as bp
import prices
import riviera
from test_riviera_links import BASE, LISTING, TICKETS, SOLD_OUT, button, item, listing


def price_page(rows, title="Rivierakallio - Elokuva"):
    """A ticket page carrying `rows` of (category, amount) in the site's table."""
    trs = "".join(
        f'<tr><td class="col-xs-5 showPrices-table-ticketCategory"><h4 class="no-margin">'
        f'{cat}</h4></td><td class="col-xs-3 showPrices-table-price no-wrap"><span>'
        f'{amount}</span><input type="hidden"><input type="hidden"></td>'
        f'<td class="col-xs-4 showPrices-table-Amount"><select><option>0</option></select>'
        f'</td></tr>' for cat, amount in rows)
    return (f"<html><head><title>{title}</title></head><body><h3>Lipun hinta</h3>"
            f'<form><table class="table showPrices-table">{trs}<tfoot><tr><td></td></tr>'
            f"</tfoot></table></form></body></html>")


ORDINARY = "Sohvapaikka tai Nojatuolipaikka"
NOW = datetime.datetime(2026, 9, 13, 12, 0, tzinfo=datetime.timezone.utc)


class OrdinaryPriceTest(unittest.TestCase):
    def test_the_ordinary_seat_is_the_price(self):
        self.assertEqual(riviera.ordinary_price(price_page([(ORDINARY, "20,00 €")])), "20€")

    def test_a_decimal_comma_survives_into_the_display_format(self):
        p = riviera.ordinary_price(price_page([(ORDINARY, "12,50 €")]))
        self.assertEqual(p, "12.5€")
        self.assertEqual(bp.price_label([{"price": p}], "fi"), "12,50 €")
        self.assertEqual(bp.price_label([{"price": p}], "en"), "12.50€")
        self.assertEqual(bp.price_label([{"price": "22€"}], "fi"), "22 €")

    def test_a_restricted_category_listed_first_is_not_the_price(self):
        page = price_page([("Pyörätuolipaikka", "10,00 €"), ("Opiskelija", "15,00 €"),
                           (ORDINARY, "20,00 €")])
        self.assertEqual(riviera.ordinary_price(page), "20€")

    def test_no_ordinary_row_is_unknown_not_the_cheapest(self):
        page = price_page([("Pyörätuolipaikka", "10,00 €"), ("Opiskelija", "15,00 €")])
        self.assertEqual(riviera.ordinary_price(page), "")
        self.assertEqual(riviera.ordinary_price("<html><body>ei taulukkoa</body></html>"), "")

    def test_two_ordinary_rows_with_different_amounts_are_ambiguous(self):
        page = price_page([(ORDINARY, "20,00 €"), (ORDINARY, "22,00 €")])
        self.assertEqual(riviera.ordinary_price(page), "")
        same = price_page([(ORDINARY, "20,00 €"), (ORDINARY, "20,00 €")])
        self.assertEqual(riviera.ordinary_price(same), "20€")

    def test_zero_and_a_missing_amount_stay_unknown(self):
        self.assertEqual(riviera.ordinary_price(price_page([(ORDINARY, "0,00 €")])), "")
        self.assertEqual(riviera.ordinary_price(price_page([(ORDINARY, "ilmainen")])), "")

    def test_the_entity_and_a_nonbreaking_space_are_read(self):
        self.assertEqual(riviera.ordinary_price(price_page([(ORDINARY, "20,00&nbsp;&euro;")])), "20€")


class FakeFetch:
    """The two requests fetch_site makes: the listing POST and ticket-page GETs."""

    def __init__(self, page, pages, fail=()):
        self.page, self.pages, self.fail = page, pages, set(fail)
        self.gets = []

    def __call__(self, url, headers=None, data=None, **kw):
        if data is not None:
            return json.dumps({"success": True, "data": {"movies": self.page}}).encode()
        self.gets.append(url)
        sid = url.rsplit("/", 1)[1]
        if sid in self.fail:
            raise OSError("boom")
        return price_page(self.pages[sid]).encode()


def rows(*items):
    return listing(*items)


class EnrichmentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.tmp.name) / "prices-riviera.json"
        self.addCleanup(self.tmp.cleanup)

    def run_site(self, page, pages, fail=(), now=NOW, limit=None):
        fake = FakeFetch(page, pages, fail)
        with mock.patch.object(riviera, "fetch", fake), mock.patch.object(prices, "fetch", fake), \
             mock.patch.object(prices.time, "sleep") as slept:
            if limit is not None:
                with mock.patch.object(prices, "FETCH_MAX", limit):
                    out = riviera.fetch_site(riviera.SITE, price_sleep=0.7,
                                             prices_path=self.path, now=now)
            else:
                out = riviera.fetch_site(riviera.SITE, price_sleep=0.7, prices_path=self.path,
                                         now=now)
        shows = [s for v in out.values() for s in v]
        return shows, fake, slept

    def cache(self):
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else None

    def test_two_screenings_of_one_film_carry_their_own_prices(self):
        page = rows(item("Odyssey", "Ma 14.9.2026", "18:00", "Kallio, Sali 1", button(1)),
                    item("Odyssey", "Ti 15.9.2026", "20:00", "Kallio, Sali 1", button(2)))
        shows, fake, slept = self.run_site(page, {"1": [(ORDINARY, "20,00 €")],
                                                  "2": [(ORDINARY, "22,00 €")]})
        self.assertEqual([(s["url"], s["price"]) for s in shows],
                         [(TICKETS + "1", "20€"), (TICKETS + "2", "22€")])
        self.assertEqual(fake.gets, [TICKETS + "1", TICKETS + "2"])
        slept.assert_called_once_with(0.7)                 # sequential, paced between pages
        self.assertEqual(self.cache()["1"], {"price": "20€", "at": mock.ANY, "fields": {}})

    def test_one_id_shared_by_two_rows_is_read_once(self):
        page = rows(item("A", "Ma 14.9.2026", "18:00", "Kallio, Sali 1", button(7)),
                    item("A", "Ma 14.9.2026", "18:00", "Punavuori, Sali 2", button(7)))
        shows, fake, _ = self.run_site(page, {"7": [(ORDINARY, "18,00 €")]})
        self.assertEqual(fake.gets, [TICKETS + "7"])
        self.assertEqual([s["price"] for s in shows], ["18€", "18€"])

    def test_a_sold_out_row_keeps_the_listing_and_asks_nothing(self):
        page = rows(item("A", "Ma 14.9.2026", "18:00", "Kallio, Sali 1", SOLD_OUT,
                         seats="Varatut paikat: 50/50"),
                    item("B", "Ma 14.9.2026", "20:00", "Kallio, Sali 1", button(3)))
        shows, fake, _ = self.run_site(page, {"3": [(ORDINARY, "20,00 €")]})
        self.assertEqual(fake.gets, [TICKETS + "3"])
        sold = next(s for s in shows if s["title"] == "A")
        self.assertEqual((sold["url"], sold["price"], sold["soldOut"]), (LISTING, "", True))

    def test_a_failed_page_leaves_its_price_unknown_and_the_schedule_whole(self):
        page = rows(item("A", "Ma 14.9.2026", "18:00", "Kallio, Sali 1", button(1)),
                    item("B", "Ma 14.9.2026", "20:00", "Kallio, Sali 1", button(2)))
        shows, fake, _ = self.run_site(page, {"2": [(ORDINARY, "20,00 €")]}, fail=("1",))
        self.assertEqual(len(shows), 2)
        self.assertEqual({s["title"]: s["price"] for s in shows}, {"A": "", "B": "20€"})
        self.assertNotIn("1", self.cache())                 # retried next run, not memoised

    def test_a_page_without_an_ordinary_seat_is_cached_as_unknown(self):
        page = rows(item("A", "Ma 14.9.2026", "18:00", "Kallio, Sali 1", button(1)))
        shows, fake, _ = self.run_site(page, {"1": [("Pyörätuolipaikka", "10,00 €")]})
        self.assertEqual(shows[0]["price"], "")
        self.assertEqual(self.cache()["1"]["price"], "")
        shows, fake, _ = self.run_site(page, {"1": [(ORDINARY, "20,00 €")]},
                                       now=NOW + datetime.timedelta(hours=1))
        self.assertEqual(fake.gets, [])                     # not asked again inside the TTL
        self.assertEqual(shows[0]["price"], "")

    def test_a_fresh_cache_is_reused_and_an_expired_one_is_refreshed(self):
        page = rows(item("A", "Ma 14.9.2026", "18:00", "Kallio, Sali 1", button(1)))
        self.run_site(page, {"1": [(ORDINARY, "20,00 €")]})
        shows, fake, _ = self.run_site(page, {"1": [(ORDINARY, "25,00 €")]})
        self.assertEqual((fake.gets, shows[0]["price"]), ([], "20€"))
        stale = self.cache()
        stale["1"]["at"] = (NOW - datetime.timedelta(hours=prices.TTL_H + 1)).isoformat()
        self.path.write_text(json.dumps(stale), encoding="utf-8")
        shows, fake, _ = self.run_site(page, {"1": [(ORDINARY, "25,00 €")]})
        self.assertEqual((fake.gets, shows[0]["price"]), ([TICKETS + "1"], "25€"))

    def test_an_id_that_left_the_listing_leaves_the_cache(self):
        self.path.write_text(json.dumps({"9": {"price": "20€", "at": NOW.isoformat()}}),
                             encoding="utf-8")
        page = rows(item("A", "Ma 14.9.2026", "18:00", "Kallio, Sali 1", button(1)))
        self.run_site(page, {"1": [(ORDINARY, "20,00 €")]})
        self.assertEqual(set(self.cache()), {"1"})

    def test_the_per_run_ceiling_defers_the_rest(self):
        page = rows(item("A", "Ma 14.9.2026", "18:00", "Kallio, Sali 1", button(1)),
                    item("B", "Ma 14.9.2026", "20:00", "Kallio, Sali 1", button(2)))
        shows, fake, _ = self.run_site(page, {"1": [(ORDINARY, "20,00 €")],
                                              "2": [(ORDINARY, "22,00 €")]}, limit=1)
        self.assertEqual(len(fake.gets), 1)
        self.assertEqual(sorted(s["price"] for s in shows), ["", "20€"])

    def test_three_failures_in_a_row_end_the_pass(self):
        page = rows(*[item(str(i), "Ma 14.9.2026", f"1{i}:00", "Kallio, Sali 1", button(i))
                      for i in range(1, 6)])
        shows, fake, _ = self.run_site(page, {"4": [(ORDINARY, "20,00 €")],
                                              "5": [(ORDINARY, "20,00 €")]},
                                       fail=("1", "2", "3"))
        self.assertEqual(fake.gets, [TICKETS + "1", TICKETS + "2", TICKETS + "3"])
        self.assertEqual([s["price"] for s in shows], [""] * 5)

    def test_the_cache_is_written_only_when_it_changed(self):
        page = rows(item("A", "Ma 14.9.2026", "18:00", "Kallio, Sali 1", button(1)))
        self.run_site(page, {"1": [(ORDINARY, "20,00 €")]})
        stamp = self.path.stat().st_mtime_ns
        self.run_site(page, {"1": [(ORDINARY, "20,00 €")]})
        self.assertEqual(self.path.stat().st_mtime_ns, stamp)


if __name__ == "__main__":
    unittest.main()
