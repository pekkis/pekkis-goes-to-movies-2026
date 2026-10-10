"""Korjaamo Kino: the unrestricted ticket price from Vista's websales page (2026-09-13).

The "Select tickets" page lists one <li class="ticket-list__item"> per category with a
label and a price. Categories are per screening and carry no fixed ordinary name (a
festival screening sells "HelAFF"), so restricted categories are dropped by name and the
rest must agree. Fixture is that shape with the amount controls left out.
"""
import unittest

import _ctx                                                # noqa: F401
import prices
import vista


def item(label, amount):
    return (f'<li class="ticket-list__item"><div class="grid grid--gutter-small">'
            f'<div class="grid__col grid__col--max"><p class="ticket-list__label bold">{label}</p></div>'
            f'<div class="grid__col grid__col--min"><span class="ticket-list__price">{amount}</span></div>'
            f'<div class="grid__col grid__col--min"><div class="number ticket-list__number">'
            f'<label class="number__label">Amount</label></div></div></div></li>')


def page(*items):
    return ('<html><body><form method="post"><div class="step__content"><h1 class="step__title h2">'
            'Valitse liput</h1><div class="ticket-list step__ticket-list"><ul class="ticket-list__list">'
            + "".join(items) + "</ul></div></div></form></body></html>")


class KorjaamoPriceTest(unittest.TestCase):
    def test_a_single_unrestricted_category_is_the_price(self):
        self.assertEqual(vista.ordinary_price(page(item("HelAFF", "14,00&#xA0;&#x20AC;"))), "14€")

    def test_a_wheelchair_seat_is_ignored_even_when_it_is_the_only_row(self):
        self.assertEqual(vista.ordinary_price(page(item("Py&#xF6;r&#xE4;tuolipaikka", "14,00 €"))), "")
        p = page(item("Pyörätuolipaikka", "10,00 €"), item("Normaali", "14,00 €"))
        self.assertEqual(vista.ordinary_price(p), "14€")

    def test_concessions_do_not_become_the_price(self):
        p = page(item("Opiskelija", "10,00 €"), item("Eläkeläinen", "10,00 €"), item("Normaali", "14,50 €"))
        self.assertEqual(vista.ordinary_price(p), "14.5€")
        # A regular Korjaamo screening as measured on 2026-09-13.
        p = page(item("Normaali lippu", "13,00 €"), item("Eläkeläislippu", "11,00 €"),
                 item("Opiskelijalippu", "11,00 €"), item("Lasten lippu (alle 10v.)", "11,00 €"),
                 item("Pyörätuolipaikka", "11,00 €"))
        self.assertEqual(vista.ordinary_price(p), "13€")

    def test_two_unrestricted_categories_that_disagree_are_unknown(self):
        self.assertEqual(vista.ordinary_price(page(item("HelAFF", "14,00 €"), item("Normaali", "12,00 €"))), "")
        self.assertEqual(vista.ordinary_price(page(item("HelAFF", "14,00 €"), item("Normaali", "14,00 €"))), "14€")

    def test_no_list_or_a_free_row_is_unknown(self):
        self.assertEqual(vista.ordinary_price("<html><body>nothing</body></html>"), "")
        self.assertEqual(vista.ordinary_price(page(item("Normaali", "0,00 €"))), "")

    def test_korjaamos_site_names_its_ticket_pages(self):
        site = vista.SITES[0]
        self.assertEqual(site["tickets"], "https://korjaamokino.fi/websales/show/")
        self.assertEqual(prices.key_of(site["tickets"] + "168040", site["tickets"]), "168040")


if __name__ == "__main__":
    unittest.main()
