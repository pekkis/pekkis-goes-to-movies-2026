"""Riviera: every screening links to its own screening, not to the listing.

All 30 committed Kallio showtimes carried `https://www.rivieracinemas.fi/elokuvat/` on
2026-09-13. The parser read the first `href` in the row and kept it only when it started
with `http`, and the listing the adapter reads carries no `href` at all: the action cell
is a `<button class="... show_tickets" data-movieid="983273">`, and the theme's app.js
opens `https://tickets.rivieracinemas.fi/websales/show/983273` from it.

Both link shapes are covered here. An anchor wins when the theme ships one, because it is
the site's own URL for that screening including its query and fragment; the button is what
it ships today. A sold-out row carries a `disabled` button with neither class nor id, and
keeps the listing.
"""
import unittest

import _ctx                                                # noqa: F401
import riviera


BASE = "https://www.rivieracinemas.fi"
LISTING = BASE + "/elokuvat/"
TICKETS = "https://tickets.rivieracinemas.fi/websales/show/"


def item(title, date, time, loc, actions, seats="Varatut paikat: 12/50", before=""):
    """One `<li>` in the shape the ajax endpoint returns."""
    return f"""
<li class="movielist__item single-show flex flex-col md:flex-row ">
  <div class="flex movielist__item__info">
    <div class="movielist__item__date flex flex-col justify-between">
      <span class="date">{date}</span>
      <span class="time">{time}</span>
      <span class="location">{loc}</span>
    </div>
    <div class="movielist__item__details flex flex-col justify-between">
      {before}
      <span class="movielist__item__title title">{title}</span>
      <div class="seats"><div class="seats__txt">{seats}</div></div>
      <span class="length">Kesto:  1 h 48 min</span>
    </div>
  </div>
  <div class="movielist__item__actions flex-grow flex items-center md:justify-end">
    {actions}
  </div>
</li>"""


def button(show_id):
    return (f'<button class="w-full md:w-auto button white smaller show_tickets" '
            f'data-movieid="{show_id}">Valitse näytös</button>')


SOLD_OUT = '<button class="w-full md:w-auto button white smaller" disabled>Valitse näytös</button>'


def listing(*items):
    return '<ul role="list" class="movielist">' + "".join(items) + "</ul>"


def urls(page):
    return [r["url"] for r in riviera.parse(page, LISTING, BASE, TICKETS)]


class ScreeningLinkTest(unittest.TestCase):

    def test_two_screenings_of_one_film_keep_their_own_ids(self):
        """The defect in one fixture: same film, same venue, two days. One shared link
        would send both readers to whichever screening the site opens by default."""
        page = listing(
            item("The Odyssey", "Ma 14.9.2026", "18:00", "Kallio, Sali 1", button("982926")),
            item("The Odyssey", "Ti 15.9.2026", "18:30", "Punavuori, Sali 2", button("983270")),
        )
        self.assertEqual(urls(page), [TICKETS + "982926", TICKETS + "983270"])

    def test_a_relative_action_link_is_resolved_and_keeps_its_query_and_fragment(self):
        """`/Event/31766/?show=982926#tickets` is the same screening by another route.
        The old rule dropped it for not starting with http."""
        page = listing(
            item("The Odyssey", "Ma 14.9.2026", "18:00", "Kallio, Sali 1",
                 '<a href="/Event/31766/?show=982926&amp;lang=fi#tickets">Valitse näytös</a>'),
            item("The Odyssey", "Ti 15.9.2026", "18:30", "Punavuori, Sali 2",
                 '<a href="/Event/31766/?show=983270#tickets">Valitse näytös</a>'),
        )
        self.assertEqual(urls(page), [
            BASE + "/Event/31766/?show=982926&lang=fi#tickets",
            BASE + "/Event/31766/?show=983270#tickets",
        ])

    def test_an_absolute_action_link_is_published_as_it_stands(self):
        page = listing(
            item("A", "Ma 14.9.2026", "18:00", "Kallio, Sali 1",
                 f'<a href="{BASE}/Event/31766/?show=982926#tickets">Liput</a>'),
            item("B", "Ma 14.9.2026", "20:00", "Kallio, Sali 1",
                 f'<a href="{TICKETS}983270">Liput</a>'),
        )
        self.assertEqual(urls(page), [BASE + "/Event/31766/?show=982926#tickets",
                                      TICKETS + "983270"])

    def test_a_sold_out_row_keeps_the_listing_and_stays_sold_out(self):
        """The `disabled` button carries no class and no id, because there is nothing to
        sell. The fallback is the only thing that names the cinema."""
        page = listing(
            item("Trainspotting (1996)", "Ke 16.9.2026", "20:00", "Kallio, Sali 1",
                 SOLD_OUT, seats="Varatut paikat: 50/50"),
            item("The Odyssey", "Ma 14.9.2026", "18:00", "Kallio, Sali 1", button("982926")),
        )
        rows = riviera.parse(page, LISTING, BASE, TICKETS)
        self.assertEqual([r["url"] for r in rows], [LISTING, TICKETS + "982926"])
        self.assertEqual([r["soldOut"] for r in rows], [True, False])

    def test_the_seat_count_decides_sold_out_where_it_is_printed(self):
        """A disabled button over free seats is not sold out: a sale not yet open looks
        the same. Every seat taken is sold out whatever the button says, and a disabled
        button with no count printed still is."""
        page = listing(
            item("A", "Ti 15.12.2026", "21:00", "Kallio, Sali 1", SOLD_OUT,
                 seats="Varatut paikat: 0/50"),
            item("B", "Ti 15.12.2026", "18:00", "Kallio, Sali 1", button("1"),
                 seats="Varatut paikat: 50/50"),
            item("C", "Ti 15.12.2026", "19:00", "Kallio, Sali 1", SOLD_OUT, seats=""),
            item("D", "Ti 15.12.2026", "20:00", "Kallio, Sali 1", button("2"),
                 seats="Varatut paikat: 49/50"),
        )
        rows = {r["title"]: r["soldOut"] for r in riviera.parse(page, LISTING, BASE, TICKETS)}
        self.assertEqual(rows, {"A": False, "B": True, "C": True, "D": False})

    def test_a_link_outside_the_action_cell_cannot_answer_for_the_screening(self):
        """A film title linked to `/Event/31766/` addresses the film and lands on its
        first screening. Reading the row's first href is what published the listing."""
        page = listing(
            item("The Odyssey", "Ma 14.9.2026", "18:00", "Kallio, Sali 1", button("982926"),
                 before='<a href="/Event/31766/">The Odyssey</a>'),
            item("The Odyssey", "Ti 15.9.2026", "18:30", "Punavuori, Sali 2", button("983270"),
                 before='<a href="/Event/31766/">The Odyssey</a>'),
        )
        self.assertEqual(urls(page), [TICKETS + "982926", TICKETS + "983270"])

    def test_the_rest_of_the_row_is_unchanged(self):
        """Venue split, room, time and sold-out come from the same block, and a link fix
        that moved any of them would be a worse bug than the one it fixes."""
        page = listing(
            item("The Odyssey", "Ma 14.9.2026", "18:00", "Kallio, Sali 1", button("982926")),
            item("Practical Magic: Lumotut sisaret", "Ma 14.9.2026", "17:00",
                 "Punavuori, Sali 1", button("983265")),
        )
        rows = riviera.parse(page, LISTING, BASE, TICKETS)
        self.assertEqual([r["loc"] for r in rows], ["kallio", "punavuori"])
        self.assertEqual([r["aud"] for r in rows], ["Sali 1", "Sali 1"])
        self.assertEqual([r["start"] for r in rows],
                         ["2026-09-14T18:00:00+03:00", "2026-09-14T17:00:00+03:00"])
        self.assertEqual([r["len"] for r in rows], ["108", "108"])

    def test_the_site_names_the_ticket_host(self):
        """`show_url` builds nothing without it, so a site entry that omits it falls back
        rather than inventing a host."""
        self.assertEqual(riviera.SITE["tickets"], TICKETS)
        page = listing(item("A", "Ma 14.9.2026", "18:00", "Kallio, Sali 1", button("982926")),
                       item("B", "Ma 14.9.2026", "20:00", "Kallio, Sali 1", button("983270")))
        self.assertEqual([r["url"] for r in riviera.parse(page, LISTING, BASE, "")],
                         [LISTING, LISTING])


if __name__ == "__main__":
    unittest.main()
