"""Every showtime is the same ticket in every view (2026-09-02).

The combined city view hid the stub's perforation and the generated city pages hid their
notches, so combined stubs read as generic cards. The combined stub is now the row stub
adapted: a fixed time compartment, the details compartment, the price compartment at the
trailing edge with the dashed seam as its left border and the notches as its own
pseudo-elements (moved there from after the time on 2026-09-13). Rendering is measured
live; the source that makes the alignment hold is pinned here, in both renderers.
"""
import re
import unittest

import _ctx


HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")
GEN = (_ctx.ROOT / "scripts" / "build_pages.py").read_text(encoding="utf-8")


def rule(css, selector):
    m = re.search(r"(?m)^\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    return m.group(1) if m else None


class ClientTicketTest(unittest.TestCase):

    def test_the_combined_view_no_longer_hides_the_notches(self):
        self.assertNotRegex(HTML, r"\.stubs\.grid \.stub::before,\s*\.stubs\.grid \.stub::after\s*\{\s*display:\s*none")

    def test_seam_and_notches_belong_to_the_price_compartment(self):
        """The time compartment is `--tw` wide; the seam is the price compartment's dashed
        left border and the notches are its own pseudo-elements, so the perforation sits
        at the price boundary (2026-09-13; until then at --tw, after the time)."""
        grid = rule(HTML, ".stubs.grid .stub")
        self.assertIn("--tw:64px", grid)
        self.assertIn("grid-template-columns:var(--tw) minmax(0,1fr) auto", grid)
        self.assertIn('grid-template-areas:"time aud price"', grid)
        self.assertIn("min-height:40px", grid)
        aud = rule(HTML, ".stubs.grid .stub .aud")
        self.assertNotIn("border-left", aud)
        self.assertIn("flex-wrap:wrap", aud)
        self.assertIn("min-width:0", aud)
        self.assertIn("overflow-wrap:anywhere", rule(HTML, ".stubs.grid .stub .aud .loc"))
        self.assertNotIn("border-left:0", rule(HTML, ".stubs.grid .stub .price"))
        self.assertIn("left:-4px", rule(HTML, ".stub .price::before,.stub .price::after"))
        self.assertNotIn(".stubs.grid .stub::before", HTML)

    def test_the_time_compartment_spans_the_ticket(self):
        self.assertIn("align-items:stretch", rule(HTML, ".stubs.grid .stub"))
        self.assertIn("align-items:center", rule(HTML, ".stubs.grid .stub .time"))

    def test_normal_and_combined_views_share_one_stub_markup(self):
        """The grid is a container class only; every renderer emits the same
        `<a class="stub …">` with time, aud and optional price."""
        self.assertEqual(len(re.findall(r'<a class="stub\$\{cls\}', HTML)), 3)
        self.assertEqual(HTML.count("'stubs grid'"), 2)          # the card and the sheet
        self.assertNotIn('class="ticket', HTML)

    def test_the_price_stays_inside_its_own_stub(self):
        self.assertEqual(sorted(re.findall(r"priceLabel\(([^)]*)\)", HTML)), ["[s]", "[s]", "[t]", "rows"])
        self.assertIn("grid-area:price", rule(HTML, ".stubs.grid .stub .price"))

    def test_a_second_column_needs_a_240px_ticket(self):
        """The film sheet at 375 px is 335 px wide. minmax(168px) gave it two 163 px
        columns, and "Cinema Orion" beside "alkaen 10€" broke letter by letter over nine
        lines; at 520 px three columns left 1 px of details. 240 = 64 of time + 75 of
        floor price + 90 for a cinema name to keep its words, and min(…,100%) keeps the
        one track from overflowing a narrower container. No phone override may lower it."""
        grid = rule(HTML, ".stubs.grid")
        self.assertIn("minmax(min(240px, 100%), 1fr)", grid)
        self.assertNotRegex(HTML, r"\.stubs\.grid\{grid-template-columns:repeat\(auto-fill, minmax\(1[0-9]{2}px")

    def test_the_past_times_control_is_not_a_ticket(self):
        self.assertIn('<button class="pastlink"', HTML)
        self.assertNotRegex(HTML, r"\.pastlink::(before|after)")
        self.assertNotIn('class="stub pastlink', HTML)

    def test_on_the_meta_line_the_past_times_control_is_one_line_tall(self):
        """Reported 2026-09-23: with the -13 px margins the button kept an 18 px box in a
        14 px line, so a card carrying it had its genre row 2 px and its tickets 4 px
        lower than a card without, in both engines. There it gives back all but one line
        height, and the row aligns on the text's baseline."""
        self.assertIn("margin-block:calc((1lh - 44px) / 2)", rule(HTML, ".meta2 .pastlink"))
        self.assertIn("align-items:baseline", rule(HTML, ".meta2"))


class PhoneCardTest(unittest.TestCase):
    """At phone widths the tickets span the card under the poster and the details, as on
    the generated pages (2026-09-23). Measured in Chromium and WebKit at 320, 393, 480
    and 560: the list full width below the poster on every card, the details beside it
    with their desktop spacing, no overlap and no overflow; at 561 the old layout. The
    widest ticket in any view (369 px, Mikkeli) fits beside the poster only from 499 up."""

    def phone(self):
        """The phone block that sizes the card's poster."""
        anchor = HTML.index("    .poster{flex-basis:72px; width:72px; height:104px}")
        start = HTML.rindex("  @media (max-width:560px){", 0, anchor)
        return HTML[start:HTML.index("\n  }\n", start)]

    def test_the_card_becomes_two_columns_with_the_tickets_across_both(self):
        css = self.phone()
        self.assertIn(".movie{display:grid; grid-template-columns:72px minmax(0,1fr);", css)
        self.assertIn("grid-template-rows:auto auto 1fr; gap:0 18px}", css)
        self.assertIn(".movie > .info{display:contents}", css)
        self.assertIn(".movie > .poster{grid-column:1; grid-row:1 / span 3}", css)
        self.assertIn(".movie .title, .movie .meta1, .movie .meta2{grid-column:2; align-self:start}", css)
        self.assertIn(".movie .stubs{grid-column:1 / span 2; margin-top:12px}", css)

    def test_no_negative_grid_line(self):
        """A negative line counts from the explicit grid in WebKit (2026-09-18)."""
        self.assertNotRegex(self.phone(), r"grid-(?:row|column):[^;}]*-\d")

    def test_the_generated_pages_switch_at_the_same_width(self):
        gen = (_ctx.ROOT / "scripts" / "build_pages.py").read_text(encoding="utf-8")
        self.assertRegex(gen, r"@media\(max-width:560px\)\{[^\n]*\.times\{clear:both\}")


class GeneratedTicketTest(unittest.TestCase):

    def test_the_city_page_no_longer_hides_the_notches(self):
        self.assertNotRegex(GEN, r"\.grid \.stub \.aud::before,\.grid \.stub \.aud::after\{display:none\}")

    def test_the_seam_is_the_price_border_and_the_notches_ride_on_it(self):
        """The generator's notches are pseudo-elements of `.price` at left:-4px in both
        tickets, so their centre sits on the price compartment's dashed border; the
        details compartment has no seam of its own (2026-09-13; until then the grid seam
        sat after the time)."""
        self.assertIn("left:-4px", rule(GEN, ".stub .price::before,.stub .price::after"))
        self.assertIsNone(rule(GEN, ".grid .stub .aud::before,.grid .stub .aud::after"))
        grid_aud = rule(GEN, ".grid .stub .aud")
        self.assertNotIn("border-left", grid_aud)
        self.assertIn("flex-wrap:wrap", grid_aud)
        self.assertIn("min-width:0", grid_aud)
        self.assertIn("overflow-wrap:anywhere", grid_aud)
        self.assertEqual(rule(GEN, ".grid .stub .aud .a"), "white-space:normal")
        grid = rule(GEN, ".grid .stub")
        self.assertIn('grid-template-areas:"time aud price"', grid)
        self.assertIn("grid-template-columns:64px minmax(0,1fr) auto", grid)
        self.assertIn("min-height:40px", grid)

    def test_the_city_page_needs_the_same_240px_ticket(self):
        self.assertIn("minmax(min(240px,100%),1fr)", rule(GEN, ".times.grid"))
        self.assertNotRegex(GEN, r"\.times\.grid\{grid-template-columns:repeat\(auto-fill,minmax\(1[0-9]{2}px")

    def test_a_rendered_city_stub_keeps_venue_and_room_on_the_details_side(self):
        import build_pages as bp
        show = {"title": "Autofiktio", "start": "2026-09-02T17:30:00+03:00", "price": None,
                "aud": "Sali 7", "venueLabel": "Finnkino Plevna", "venueProvider": "finnkino",
                "url": "https://www.finnkino.fi/x", "lang": "ES-A, FI-S, SV-S"}
        html = bp.film_block("Autofiktio", [show], {}, {}, "fi", bp.L["fi"], True, set(),
                             current_year=2026)
        li = re.search(r"<li>(.*?)</li>", html, re.S).group(1)
        self.assertRegex(li, r'<span class="time">17:30</span><span class="aud">.*Finnkino Plevna.*Sali 7.*</span><span class="price"></span></a>$')


if __name__ == "__main__":
    unittest.main()
