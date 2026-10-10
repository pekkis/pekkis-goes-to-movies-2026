"""Kino Regina: the Peruslippu price from KAVI's shop page (2026-09-13).

The page a showtime links to lists ticket categories as rows, each a <label> and a
schema.org Offer with <span itemprop="price">10,00 €</span> repeated once per
breakpoint. Only "Peruslippu" is the ordinary ticket. Fixture is that shape with the form
fields left out.
"""
import unittest

import _ctx                                                # noqa: F401
import prices
import regina


def row(label, amount, for_id="event_add_form_products_1"):
    return (f'<div><hr></div><div class="row" ><div class="col-sm-8 col-xs-12"><div>'
            f'<label for="{for_id}">{label}</label></div></div>'
            f'<div class="col-sm-2 text-right hidden-xs" itemprop="offers" itemscope '
            f'itemtype="http://schema.org/Offer"><nobr><span itemprop="price">{amount}</span></nobr></div>'
            f'<div class="col-xs-4 visible-xs" itemprop="offers" itemscope '
            f'itemtype="http://schema.org/Offer"><nobr><span itemprop="price">{amount}</span></nobr></div>'
            f'<div class="col-sm-2 col-xs-8 text-right"><select><option value=""></option></select></div></div>')


def page(*rows):
    return ('<html><body><form method="post" action="/fi/events/e/x/cart_op/add_to_cart" '
            'class="jsonformify buybox-form"><div class="margin-bottom"><div class="div margin-top">'
            + "".join(rows) + "</div></div></form></body></html>")


class ReginaPriceTest(unittest.TestCase):
    def test_peruslippu_is_the_price(self):
        self.assertEqual(regina.ordinary_price(page(row("Peruslippu", "10,00 €"))), "10€")

    def test_a_member_ticket_listed_first_is_not_the_price(self):
        p = page(row("KAVI-klubilaisten lippu", "9,00 €", ""), row("Peruslippu", "10,00 €"),
                 row("Lapsi (alle 12-vuotias)", "5,00 €", ""))
        self.assertEqual(regina.ordinary_price(p), "10€")

    def test_no_peruslippu_is_unknown(self):
        self.assertEqual(regina.ordinary_price(page(row("Lapsi", "5,00 €"))), "")
        self.assertEqual(regina.ordinary_price("<html></html>"), "")

    def test_two_peruslippu_rows_that_disagree_are_unknown(self):
        self.assertEqual(regina.ordinary_price(page(row("Peruslippu", "10,00 €"), row("Peruslippu", "12,00 €"))), "")
        self.assertEqual(regina.ordinary_price(page(row("Peruslippu", "10,00 €"), row("Peruslippu", "10,00 €"))), "10€")

    def test_a_free_screening_publishes_no_price(self):
        self.assertEqual(regina.ordinary_price(page(row("Peruslippu", "0,00 €"))), "")

    def test_the_ticket_prefix_matches_the_urls_the_schedule_publishes(self):
        url = "https://kauppa.kavi.fi/fi/events/pwdg/event_buybox/show/6a21c82a6d928abd098b4567"
        self.assertEqual(prices.key_of(url, regina.TICKETS), "6a21c82a6d928abd098b4567")
        self.assertEqual(prices.key_of(regina.BASE + "/elokuva/123/", regina.TICKETS), "")


if __name__ == "__main__":
    unittest.main()
