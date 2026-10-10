"""The ticket's perforation belongs to the price compartment (2026-09-02, revised 2026-09-13).

The last 56 px of a row ticket are the price compartment, with the dashed seam as its left
border and the notches as its own pseudo-elements, so the perforation sits at the price
boundary wherever that lands. Since 2026-09-13 an empty compartment is dropped on the card
and sheet tickets (no seam, no notches, no reserved width); only the Ajat list keeps it,
for its 120 px construction. The combined view's ticket carries the same perforation: the
seam moved there from after the time to before the price. The generated pages keep their
own copy of the row anatomy and are not part of this file's client assertions.

Rendering is measured live; the source is pinned here, in both renderers.
"""
import re
import unittest

import _ctx


HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")
GEN = (_ctx.ROOT / "scripts" / "build_pages.py").read_text(encoding="utf-8")


def rule(css, selector):
    """The body of the rule whose selector list is exactly `selector`, anchored at the
    start of a line: `.stub .price` must not answer for `.stubs.grid .stub .price`."""
    m = re.search(r"(?m)^\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    return m.group(1) if m else None


def num(css_value):
    return float(re.search(r"[\d.]+", css_value).group(0))


class ClientCompactTicketTest(unittest.TestCase):

    def test_the_compartment_is_fixed_and_the_seam_is_its_border(self):
        price = rule(HTML, ".stub .price")
        self.assertIn("flex:0 0 var(--pw)", price)
        self.assertIn("width:var(--pw)", price)
        self.assertIn("border-left:1px dashed var(--line)", price)
        self.assertIn("justify-content:center", price)
        self.assertIn("align-self:stretch", price)
        self.assertIn("--pw:56px", rule(HTML, ".stub"))
        self.assertIn("min-height:40px", rule(HTML, ".stub"))       # 44 until 2026-09-02, judged too heavy a band
        self.assertNotIn("border-left", rule(HTML, ".stub .aud"))          # no second seam after the time

    def test_the_notches_are_the_compartments_own(self):
        """Anchored to the price box, not placed from the ticket edge or a percentage."""
        notch = rule(HTML, ".stub .price::before,.stub .price::after")
        self.assertIn("left:-4px", notch)
        self.assertIn("position:absolute", notch)
        self.assertIn("position:relative", rule(HTML, ".stub .price"))
        self.assertIsNone(rule(HTML, ".stub::before,.stub::after"))
        self.assertNotIn("var(--pw) - 4px", HTML)
        self.assertNotIn("var(--tw) - 4px", HTML)
        self.assertNotIn("--notch:", HTML)

    def test_no_price_means_a_narrow_tail_with_seam_and_notches(self):
        """v153: every ticket is perforated on the right. An empty compartment narrows to
        16 px (--pe) and keeps the seam and notches; v140 to v152 dropped it, which read as
        lost styling, and v102 to v139 kept a blank 56 px box."""
        self.assertIn("--pe:16px", rule(HTML, ".stub"))
        self.assertEqual(rule(HTML, ".stub .price:empty"), "flex:0 0 var(--pe); width:var(--pe); padding:0")
        # The combined ticket's price rule is one class more specific, so the tail width
        # has to be said again at that level or the grid keeps its auto width.
        self.assertEqual(rule(HTML, ".stubs.grid .stub .price:empty"), "width:var(--pe); min-width:var(--pe); padding:0")
        self.assertLess(HTML.index(".stubs.grid .stub .price{"), HTML.index(".stubs.grid .stub .price:empty{"))
        for gone in ("display:none", "border-left:0"):
            self.assertNotIn(gone, rule(HTML, ".stub .price:empty"))
        # the Ajat list keeps the full 56 px compartment: every row ticket 120 px, and its
        # seam and notches with it
        self.assertEqual(rule(HTML, ".trow .stub .price:empty"), "flex:0 0 var(--pw); width:var(--pw)")
        self.assertNotIn(".trow .stub .price:empty::before", HTML)

    def test_the_price_is_ink_and_a_step_below_the_time(self):
        price, time = rule(HTML, ".stub .price"), rule(HTML, ".stub .time")
        self.assertIn("color:var(--ink)", price)
        self.assertIn("font-weight:700", price)
        self.assertIn("white-space:normal", price)                          # "alkaen 10€" wraps
        p_size, t_size = num(re.search(r"font-size:([^;]+)", price).group(1)), num(re.search(r"font-size:([^;]+)", time).group(1))
        self.assertTrue(0.78 <= p_size <= 0.8, p_size)
        self.assertLess(p_size, t_size)
        self.assertLess(700, num(re.search(r"font-weight:([^;]+)", time).group(1)))
        for word in ("background", "border-radius", "var(--accent"):
            self.assertNotIn(word, price)                                   # no badge, pill or accent

    def test_every_renderer_emits_the_compartment_whether_or_not_there_is_a_price(self):
        self.assertEqual(HTML.count('<span class="price">${esc(own_price)}</span>'), 3)
        self.assertNotIn("own_price ? `<span", HTML)
        stubs = re.findall(r'<a class="stub\$\{cls\}.*?</a>', HTML, re.S)
        self.assertEqual(len(stubs), 3)
        for stub in stubs:
            self.assertTrue(stub.rstrip().endswith('<span class="price">${esc(own_price)}</span></a>')
                            or stub.rstrip().endswith('<span class="price">${esc(own_price)}</span>\n                </a>'), stub[-120:])

    def test_the_combined_view_perforates_before_the_price(self):
        grid_price = rule(HTML, ".stubs.grid .stub .price")
        self.assertNotIn("border-left:0", grid_price)           # inherits the row seam
        self.assertIn("color:var(--muted)", grid_price)
        self.assertIn("font-size:.72rem", grid_price)
        self.assertNotIn("border-left", rule(HTML, ".stubs.grid .stub .aud"))   # no seam after the time
        self.assertNotIn(".stubs.grid .stub::before", HTML)
        self.assertIn('grid-template-areas:"time aud price"', rule(HTML, ".stubs.grid .stub"))

    def test_no_film_level_or_sheet_header_price(self):
        self.assertEqual(sorted(re.findall(r"priceLabel\(([^)]*)\)", HTML)), ["[s]", "[s]", "[t]", "rows"])
        self.assertNotIn("sheetPrice", HTML)


class GeneratedCompactTicketTest(unittest.TestCase):

    def block(self, shows, with_venue=False, lang="fi"):
        import build_pages as bp
        return bp.film_block(shows[0]["title"], shows, {}, {}, lang, bp.L[lang], with_venue, set(),
                             current_year=2026)

    @staticmethod
    def show(**kw):
        base = dict(title="The Invite", start="2026-09-02T16:15:00+03:00", price="11\u20ac", aud="",
                    venueLabel="Cinema Niagara", venueProvider="niagara",
                    url="https://cinemaniagara.fi/salikartta?id=53882", lang="EN-A, FI-S, SV-S")
        base.update(kw); return base

    def stubs(self, html):
        return re.findall(r"<li>(<a class=\"stub[^\"]*\" href=\"[^\"]+\" rel=\"nofollow noopener\">.*?</a>)</li>", html, re.S)

    def test_a_priced_ticket_ends_with_the_price_inside_the_anchor(self):
        li = self.stubs(self.block([self.show()]))[0]
        self.assertTrue(li.endswith('<span class="price">11\u00a0\u20ac</span></a>'), li)

    def test_an_unpriced_ticket_has_the_same_anatomy_with_a_blank_compartment(self):
        li = self.stubs(self.block([self.show(price=None)]))[0]
        self.assertTrue(li.endswith('<span class="price"></span></a>'), li)
        priced = self.stubs(self.block([self.show()]))[0]
        self.assertEqual(re.sub(r'<span class="price">[^<]*</span>', "", priced),
                         re.sub(r'<span class="price">[^<]*</span>', "", li))

    def test_room_and_price_both_survive(self):
        li = self.stubs(self.block([self.show(aud="Sali 7", price="13\u20ac")]))[0]
        self.assertIn("<span class=a>Sali 7</span>", li)
        self.assertTrue(li.endswith('<span class="price">13\u00a0\u20ac</span></a>'))

    def test_long_localised_labels_are_kept_whole_in_the_markup(self):
        self.assertIn('<span class="price">alkaen 10\u00a0\u20ac</span>', self.block([self.show(price="alkaen 10\u20ac")]))
        self.assertIn('<span class="price">from 10\u20ac</span>', self.block([self.show(price="alkaen 10\u20ac")], lang="en"))
        self.assertIn("white-space:normal", rule(GEN, ".stub .price"))       # and wrap inside the compartment

    def test_the_compartment_and_its_notches_match_the_client(self):
        price = rule(GEN, ".stub .price")
        for prop in ("flex:0 0 56px", "width:56px", "border-left:1px dashed var(--line)", "justify-content:center",
                     "font-size:.78rem", "font-weight:700", "color:var(--ink)", "align-self:stretch", "position:relative"):
            self.assertIn(prop, price, prop)
        self.assertIn("left:-4px", rule(GEN, ".stub .price::before,.stub .price::after"))
        self.assertIn("min-height:40px", rule(GEN, ".stub"))                 # the row ticket's height, 44 until 2026-09-02
        self.assertIn("min-height:40px", rule(GEN, ".grid .stub"))
        self.assertNotIn("border-left", rule(GEN, ".stub .aud"))
        self.assertIsNone(rule(GEN, ".stub .aud::before,.stub .aud::after"))   # the row's notches moved to the price
        self.assertNotIn(".stub .time + .price", GEN)

    def test_the_generated_tickets_perforate_before_the_price_too(self):
        """Since 2026-09-13 the pages follow the app: the seam and notches are the price
        compartment's in the grid as well, and an empty compartment is a 16 px tail (v153)."""
        self.assertEqual(rule(GEN, ".stub .price:empty"), "flex:0 0 16px;width:16px;padding:0")
        self.assertEqual(rule(GEN, ".grid .stub .price:empty"), "width:16px;min-width:16px;padding:0")
        self.assertLess(GEN.index(".grid .stub .price{"), GEN.index(".grid .stub .price:empty{"))
        self.assertIsNone(rule(GEN, ".grid .stub .price::before,.grid .stub .price::after"))
        self.assertIsNone(rule(GEN, ".grid .stub .aud::before,.grid .stub .aud::after"))
        self.assertNotIn("border-left", rule(GEN, ".grid .stub .aud"))
        grid_price = rule(GEN, ".grid .stub .price")
        self.assertNotIn("border-left:0", grid_price); self.assertIn("color:var(--muted)", grid_price)

    def test_no_film_level_price(self):
        html = self.block([self.show(), self.show(start="2026-09-02T18:00:00+03:00", price="13\u20ac")])
        card = re.search(r"<h3>.*?<ul class=", html, re.S).group(0)
        self.assertNotIn("\u20ac", card)




def render_times_source():
    """The body of renderTimes(), which owns the Ajat list."""
    m = re.search(r"function renderTimes\(\)\{.*?\n  \}\n", HTML, re.S)
    return m.group(0)


class TimeModeTicketTest(unittest.TestCase):
    """The Ajat ticket is time and price (2026-09-03). The room, the venue and the
    screening's age limit sit on the meta line, so every ticket is 120 px by construction
    and the titles share one x."""

    def test_the_time_mode_ticket_is_time_and_price(self):
        src = render_times_source()
        stub = re.search(r'<a class="stub\$\{cls\}\$\{tint\}".*?</a>', src, re.S).group(0)
        self.assertIn('<span class="time">${t}</span>', stub)
        self.assertIn('<span class="price">${esc(own_price)}</span>', stub)
        for gone in ('class="aud"', 'class="loc"', 'glyphRow(', 'ageGlyph('):
            self.assertNotIn(gone, stub)

    def test_the_room_venue_and_age_open_the_meta_line(self):
        src = render_times_source()
        self.assertIn("['theatre-tag', multi ? esc(where) : ''], ['room', esc(s.aud || '')]", src)
        self.assertIn("const sold = s.soldOut && !past ? L[state.lang].soldout : '';", src)
        # Each a fact of its own, drawn by the one builder; the language's parts last.
        self.assertIn("const facts = [...pre, ...langParts(s.lang, !pre.length).map(x => ['', esc(x)])];",
                      src)
        self.assertIn("<small>${factsHtml(facts)}</small>", src)
        head = re.search(r"const pre = \[(.*?)\]\.filter\(x => x\[1\]\);", src, re.S).group(1)
        order = [head.index(x) for x in ("'theatre-tag'", "'room'", "ageGlyph(s)", "esc(sold)",
                                          "esc(s.rating")]
        self.assertEqual(order, sorted(order), head)

    def test_the_ticket_has_no_width_floor_or_cap(self):
        stub = rule(HTML, ".trow .stub")
        self.assertIsNotNone(stub)
        self.assertNotIn("min-width", stub)
        self.assertNotIn("max-width", stub)
        self.assertIsNone(rule(HTML, ".trow .stub .aud"))
        self.assertIn("white-space:nowrap", rule(HTML, ".tinfo small .room"))

    def test_the_card_and_sheet_tickets_keep_the_room(self):
        # The class carries a modifier since v198: a screening's own language line is
        # added to the compartment when a film's screenings disagree. Two ticket builders
        # still, and the room is still in both -- which is what this pins.
        auds = re.findall(r'<span class="aud[^"]*">(.*?)</span><span class="price"',
                          HTML, re.S)
        self.assertEqual(len(auds), 2, "the card ticket and the sheet ticket")
        for body in auds:
            self.assertIn('class="loc"', body)
        self.assertEqual(HTML.count('<span class="price">${esc(own_price)}</span>'), 3)


if __name__ == "__main__":
    unittest.main()
