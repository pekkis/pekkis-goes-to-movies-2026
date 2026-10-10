"""Kino Juha publishes two screening spaces on one listing (2026-09-14).

"KINO JUHA" is Keskustie 7 and "VIP-SALI" is Pratikankuja 3, both in Nurmijärvi, and the
listing distinguishes them only by the place line. VIP-Sali was unregistered, so its rows
matched no venue and were dropped: 6 of the site's 13 screenings, on every run since the
site was added. The place is the whole of the evidence here, so these fixtures are the
Kotka template with the place line and no room, which is what this site prints.
"""
import io
import unittest
from contextlib import redirect_stdout

import _ctx                                                # noqa: F401
import build_pages as bp
from test_etiketti_templates import Stubbed, listing, load, site as site_of

CHAINS = {"kinojuha": "Kino Juha"}


def site():
    return site_of("kinojuha")


def item(day, hhmm, place, sid):
    """One screening block. This site prints the place and no room, so `aud` stays empty."""
    return (f'<div class="item nurmijarvi date-{day}.9.2026"> <div> <p> <strong><span>'
            f"MA {day}.9. klo {hhmm}</span></strong> </p> <p> {place}<br /> "
            "Lippu 13,50&euro;<br /> Vapaat paikat 40/120 </p> </div> <div> "
            f'<a class="button-screening" href="/salikartta?id={sid}"> Osta tai varaa </a>'
            " </div> </div>")


def film(title, *items):
    return (f"<main><h1>{title}</h1><h2>Näytökset</h2>"
            f'<div class="screenings">{"".join(items)}</div></main>')


# The shape of the live read of 2026-09-14: 13 screenings over several films, 7 printing
# KINO JUHA and 6 printing VIP-SALI, ticket ids contiguous across both.
MAIN_A = film("Hetki ennen valoa", item(15, "18.00", "KINO JUHA", 53592),
              item(16, "20.15", "KINO JUHA", 53595), item(24, "14.00", "KINO JUHA", 53598))
MAIN_B = film("Autofiktio", item(15, "20.15", "KINO JUHA", 53593),
              item(17, "14.00", "KINO JUHA", 53596))
MAIN_C = film("Presidentin kyyditys", item(16, "18.00", "KINO JUHA", 53594),
              item(17, "17.15", "KINO JUHA", 53597))
VIP_A = film("Practical Magic: Lumotut sisaret", item(15, "18.00", "VIP-SALI", 53599),
             item(16, "18.00", "VIP-SALI", 53601))
VIP_B = film("Mutiny - Lavastettu syylliseksi", item(15, "20.45", "VIP-SALI", 53600),
             item(17, "20.30", "VIP-SALI", 53604))
VIP_C = film("The Dog Stars", item(17, "18.00", "VIP-SALI", 53603),
             item(16, "20.45", "VIP-SALI", 53602))
PAGES = {"/elokuvat/17/hetki": MAIN_A, "/elokuvat/22/autofiktio": MAIN_B,
         "/elokuvat/16/presidentin": MAIN_C, "/elokuvat/40/practical": VIP_A,
         "/elokuvat/38/mutiny": VIP_B, "/elokuvat/39/dog-stars": VIP_C}
FULL = dict(PAGES, **{"/elokuvat/ohjelmistossa": listing(*PAGES)})


class VenueSplitTest(Stubbed):

    def read(self, mapping=None):
        return self.stub(mapping or FULL).fetch_site(site(), sleep=0)

    def read_logged(self, mapping):
        buf = io.StringIO()
        with redirect_stdout(buf):
            out = self.read(mapping)
        return out, buf.getvalue()

    def sids(self, rows):
        return sorted(r["url"].rsplit("=", 1)[1] for r in rows)

    def test_the_two_places_split_into_their_own_venues(self):
        out = self.read()
        self.assertEqual(sorted(out), ["kj-nurmijarvi", "kj-vipsali"])
        self.assertEqual(len(out["kj-nurmijarvi"]), 7)
        self.assertEqual(len(out["kj-vipsali"]), 6)
        self.assertEqual({r["theatre"] for r in out["kj-nurmijarvi"]}, {"Kino Juha"})
        self.assertEqual({r["theatre"] for r in out["kj-vipsali"]}, {"VIP-Sali"})
        # The place is the venue here, so the room field stays empty on both.
        self.assertEqual({r["aud"] for shows in out.values() for r in shows}, {""})

    def test_neither_venue_takes_the_other_s_screenings(self):
        out = self.read()
        main = self.sids(out["kj-nurmijarvi"])
        vip = self.sids(out["kj-vipsali"])
        self.assertEqual(main, ["53592", "53593", "53594", "53595", "53596", "53597", "53598"])
        self.assertEqual(vip, ["53599", "53600", "53601", "53602", "53603", "53604"])
        self.assertEqual(set(main) & set(vip), set())

    def test_every_screening_is_published_once(self):
        out = self.read()
        urls = [r["url"] for shows in out.values() for r in shows]
        self.assertEqual(len(urls), 13)
        self.assertEqual(len(set(urls)), 13)

    def test_one_screening_listed_under_two_films_is_published_once(self):
        """The ticket id is the key, not the film page it was read from: a listing that
        links the same screening twice must not give VIP-Sali the row twice."""
        pages = dict(PAGES, **{"/elokuvat/41/practical-ennakko": film(
            "Practical Magic: ennakko", item(15, "18.00", "VIP-SALI", 53599))})
        out = self.read(dict(pages, **{"/elokuvat/ohjelmistossa": listing(*pages)}))
        self.assertEqual(len(out["kj-vipsali"]), 6)
        self.assertEqual(sum(len(v) for v in out.values()), 13)

    def test_a_third_place_nobody_registered_is_still_unclaimed(self):
        """The operator runs Taaborin kesäteatteri too. Registering VIP-Sali must not turn
        the guard into "anything on this host belongs to one of these two"."""
        pages = dict(PAGES, **{"/elokuvat/9/kesa": film(
            "Kesäkomedia", item(18, "19.00", "TAABORIN KESÄTEATTERI", 53700),
            item(19, "19.00", "TAABORIN KESÄTEATTERI", 53701))})
        out, log = self.read_logged(dict(pages, **{"/elokuvat/ohjelmistossa": listing(*pages)}))
        self.assertEqual(len(out["kj-nurmijarvi"]), 7)
        self.assertEqual(len(out["kj-vipsali"]), 6)
        self.assertNotIn("53700", " ".join(r["url"] for s in out.values() for r in s))
        self.assertIn("TAABORIN KESÄTEATTERI", log)

    def test_each_venue_keeps_its_own_label_and_page_slug(self):
        """A shared slug would silently drop one venue's page, and the calendar's LOCATION
        is built from the same label and city."""
        labels, slugs = [], []
        for v in site()["venues"]:
            d = dict(v, provider="kinojuha")
            labels.append(bp.label_of(d, CHAINS))
            slugs.append(bp.slug(f"{labels[-1]} {d['city']}"))
        self.assertEqual(labels, ["Kino Juha", "Kino Juha VIP-Sali"])
        self.assertEqual(slugs, ["kino-juha-nurmijarvi", "kino-juha-vip-sali-nurmijarvi"])


if __name__ == "__main__":
    unittest.main()
