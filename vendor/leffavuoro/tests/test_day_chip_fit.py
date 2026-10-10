"""The date row must not hand a label a column narrower than the label.

At 402 CSS pixels (iPhone 17) the row showed "Huomen…": six chips at `flex:1 1 0`, a
.66rem "Huomenna" needing 53.43px against a sixth of the row offering 53.00, because the
font-size breakpoint sat at 400px. The arithmetic is checked here with the CSS values read
out of index.html, so moving the breakpoint, gap, paddings or font size re-runs the sum.
Rendering is not checked here: sub-pixel rounding decides the last half-pixel, and that was
verified in the browser and the iOS Simulator at 320, 375, 393, 402 and 430.

The glyph widths were measured once in Chrome against the self-hosted Archivo at the
chips' weight and are stored per 1px of font-size. A test asserts the font stack has not
changed.
"""
import pathlib
import re
import unittest

import _ctx


HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")

# Width of each string per 1px of font-size, Archivo 600 (labels) and 700 (dates).
# Measured 2026-09-01 in Chrome with document.fonts.ready, letter-spacing 0.
LABEL_PER_PX = {
    "Tänään": 3.375, "Huomenna": 5.05906, "Muu": 2.01,          # fi
    "I dag": 2.22102, "I morgon": 4.07602, "Annat": 2.74703,     # sv
    "Today": 2.81406, "Tomorrow": 4.66602, "Other": 2.60305,     # en
}
# Widest weekday abbreviation per language: Ke, Sö, We.
WIDEST_ABBREV = {"fi": 1.21602, "sv": 1.265, "en": 1.465}
# A date is at most six characters in this format ("30.11."); the calendar chip can carry
# one too once a month-picker day is chosen, so the worst case is six of them.
DATE_PER_PX = 3.0

ROW = {  # the six chips, in order, per language
    "fi": ("Tänään", "Huomenna", "Muu"),
    "sv": ("I dag", "I morgon", "Annat"),
    "en": ("Today", "Tomorrow", "Other"),
}
REM = 16.0          # nothing in the page overrides the root font size
BORDER = 1.0        # .day has a 1px border on each side
MAX_ROW = 1100.0    # .days max-width

# Every viewport where the equal sixth has to be enough on its own.
EQUAL_SHARE_WIDTHS = [375, 393, 402, 411, 430, 480, 560, 561, 700, 900, 1100, 1440]
# Narrower than the design's equal-share range; min-width:max-content carries these.
RESCUED_WIDTHS = [320, 360]


def close_at(css, i):
    """-> index just past the `}` that closes the block whose `{` ended at `i`."""
    depth = 1
    while depth:
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
        i += 1
    return i


def media_blocks(css):
    """-> ([(limit_px, body)], css_with_every_at_media_removed).

    By position, not by searching for the opener text. Two blocks in this stylesheet
    share the string `@media (max-width:520px){` and two more share the 560px one, so
    an index() lookup finds the first every time and the later ones survive the strip --
    which is how the base scope first reported a desktop chip padded like a phone.
    """
    blocks, kept, i = [], [], 0
    for m in re.finditer(r"@media[^{]*\{", css):
        if m.start() < i:
            continue                      # already inside a block that was cut
        end = close_at(css, m.end())
        kept.append(css[i:m.start()])
        limit = re.search(r"max-width:\s*(\d+)px", m.group(0))
        if limit:
            blocks.append((int(limit.group(1)), css[m.end():end - 1]))
        i = end
    kept.append(css[i:])
    return blocks, "".join(kept)


def decl(scope, selector, prop):
    """-> the value of `prop` for `selector` within `scope`, or None.

    Every rule whose selector list contains `selector`, last one wins -- the same order
    the cascade uses at equal specificity. Taking the first match instead reads
    `.day b, .day small{overflow:hidden}` and concludes .day small has no font-size.
    """
    found = None
    # No leading anchor: `finditer` cannot overlap, so consuming the previous rule's
    # `}` as this one's delimiter would skip every second rule in the sheet. The
    # selector class already cannot cross `{`, `}` or `;`, which is anchor enough.
    for m in re.finditer(r"([^{};]+)\{([^{}]*)\}", scope, re.S):
        selectors = [x.strip() for x in m.group(1).split(",")]
        if selector not in selectors:
            continue
        d = re.search(r"(?:^|;)\s*" + re.escape(prop) + r"\s*:\s*([^;}]+)", m.group(2))
        if d:
            found = d.group(1).strip()
    return found


class Css:
    """The handful of declarations the date row's width arithmetic depends on,
    resolved for a viewport width the way the cascade would resolve them."""

    def __init__(self, html):
        start = html.index("<style>") + len("<style>")
        self.raw = html[start:html.index("</style>", start)]
        # Comments out first. This stylesheet explains itself at length, and a comment
        # sitting between `}` and the next selector is otherwise read as part of that
        # selector -- which made the parser skip `.days` entirely and report no padding
        # at all rather than the wrong padding.
        self.css = re.sub(r"/\*.*?\*/", "", self.raw, flags=re.S)
        self.media, self.base = media_blocks(self.css)
        assert self.media, "no max-width media blocks found; the parse is wrong"

    def scopes(self, vw):
        """Base first, then every matching max-width block in source order."""
        yield self.base
        for limit, body in self.media:
            if vw <= limit:
                yield body

    def value(self, vw, selector, prop):
        found = None
        for scope in self.scopes(vw):
            v = decl(scope, selector, prop)
            if v is not None:
                found = v
        return found

    @staticmethod
    def _len(token):
        m = re.fullmatch(r"(-?[\d.]+)(px|rem)?", token)
        assert m, f"not a length: {token!r}"
        return float(m.group(1)) * (REM if m.group(2) == "rem" else 1.0)

    def px(self, vw, selector, prop):
        v = self.value(vw, selector, prop)
        assert v is not None, f"{selector} {{{prop}}} not found at {vw}px"
        return self._len(v.split()[0])

    def pad_x(self, vw, selector):
        """The horizontal half of a padding shorthand, however many values it has.

        Written out rather than indexed off a regex: `padding:0 14px 8px` has an
        unitless first value, so a findall for lengths-with-units silently returns the
        bottom padding as if it were the side.
        """
        v = self.value(vw, selector, "padding")
        assert v is not None, f"{selector} {{padding}} not found at {vw}px"
        parts = [self._len(t) for t in v.split()]
        return {1: parts[0], 2: parts[1], 3: parts[1],
                4: parts[1]}[len(parts)]

    # -- the pieces of the row -------------------------------------------------------

    def row_pad_x(self, vw):
        return self.pad_x(vw, ".days")

    def gap(self, vw):
        return self.px(vw, ".days", "gap")

    def chip_pad_x(self, vw):
        return self.pad_x(vw, ".day")

    def label_px(self, vw):
        return self.px(vw, ".day small", "font-size")

    def date_px(self, vw):
        return self.px(vw, ".day b", "font-size")

    def min_width(self, vw):
        return self.value(vw, ".day", "min-width")

    def min_height(self, vw):
        return self.px(vw, ".day", "min-height")

    # -- and the geometry it produces ------------------------------------------------

    def row_content(self, vw):
        return min(vw, MAX_ROW) - 2 * self.row_pad_x(vw) - 5 * self.gap(vw)

    def label_space(self, vw):
        """Width left for the label inside one chip of an equal-sixth row."""
        return self.row_content(vw) / 6 - 2 * self.chip_pad_x(vw) - 2 * BORDER

    def widest_label(self, vw, lang):
        today, tomorrow, other = ROW[lang]
        return max(LABEL_PER_PX[today], LABEL_PER_PX[tomorrow],
                   LABEL_PER_PX[other], WIDEST_ABBREV[lang]) * self.label_px(vw)

    def max_content_row(self, vw, lang):
        """Total width the six chips demand when each is sized to its own content."""
        today, tomorrow, other = ROW[lang]
        date = DATE_PER_PX * self.date_px(vw)
        label = self.label_px(vw)
        chips = [max(LABEL_PER_PX[today] * label, date),
                 max(LABEL_PER_PX[tomorrow] * label, date),
                 *[max(WIDEST_ABBREV[lang] * label, date)] * 3,
                 max(LABEL_PER_PX[other] * label, date)]
        return sum(c + 2 * self.chip_pad_x(vw) + 2 * BORDER for c in chips)


CSS = Css(HTML)


class DateChipFitTest(unittest.TestCase):
    """The reported bug, as arithmetic."""

    def test_the_widest_label_fits_its_sixth_at_every_ordinary_width(self):
        """One pixel of margin, not zero. The failing case cleared the column by
        -0.43px, so a test demanding only "fits" would have passed a layout that was
        already inside the rounding noise."""
        for vw in EQUAL_SHARE_WIDTHS:
            for lang in ROW:
                with self.subTest(vw=vw, lang=lang):
                    need = CSS.widest_label(vw, lang)
                    have = CSS.label_space(vw)
                    self.assertGreaterEqual(
                        have, need + 1.0,
                        f"{lang} at {vw}px: widest label needs {need:.2f}px, "
                        f"a sixth of the row leaves {have:.2f}px")

    def test_402_is_the_case_that_was_reported(self):
        """Named on its own because it is the one an iPhone 17 renders."""
        need = CSS.widest_label(402, "fi")
        have = CSS.label_space(402)
        self.assertGreaterEqual(have, need + 1.0,
                                f"needs {need:.2f}px, has {have:.2f}px")

    def test_the_step_up_in_label_size_never_outruns_the_column(self):
        """The shape of the defect: a breakpoint that grows the font faster than it
        grows the chip. Walk the boundary of every max-width block and check the width
        just above it, which is where the larger size first applies."""
        for limit, _ in CSS.media:
            vw = limit + 1
            if vw < min(EQUAL_SHARE_WIDTHS):
                continue
            for lang in ROW:
                with self.subTest(justAbove=limit, lang=lang):
                    self.assertGreaterEqual(
                        CSS.label_space(vw), CSS.widest_label(vw, lang) + 1.0,
                        f"{lang} at {vw}px, one pixel above the {limit}px breakpoint")

    # -- the narrow end, where an equal sixth is not enough -------------------------------

    def test_below_the_equal_share_range_the_chips_may_size_to_content(self):
        """320px cannot give "Huomenna" a sixth of the row at any size the rest of the
        design uses, so `min-width:max-content` is what carries it: the one chip that
        needs more takes it and the other five share the rest."""
        for vw in RESCUED_WIDTHS:
            with self.subTest(vw=vw):
                self.assertEqual(CSS.min_width(vw), "max-content")
                for lang in ROW:
                    self.assertLessEqual(
                        CSS.max_content_row(vw, lang), CSS.row_content(vw),
                        f"{lang} at {vw}px: the six chips want more than the row has")

    def test_min_width_is_max_content_everywhere_it_is_declared(self):
        """A flex item defaults to min-width:auto and this row used to set it to 0,
        which is what let a chip be squeezed under its own content."""
        self.assertEqual(CSS.min_width(320), "max-content")
        self.assertEqual(CSS.min_width(1440), "max-content")

    def test_the_chip_is_at_least_a_44px_tap_target(self):
        """Two lines of small type and the padding come to 42.5px on a phone, which is
        under the 44px floor. `min-height` carries the last 1.5px; a button centres its
        own content, so the extra is split evenly and nothing moves.

        Declared, because the rendered height is font metrics plus line-height plus
        padding and modelling that in Python would be guesswork. The box was measured at
        44.00px at 320, 375, 393, 402 and 430 in Chrome and on an iPhone 17 simulator,
        and 47px on desktop where it was already over."""
        for vw in [320, 375, 393, 402, 430] + EQUAL_SHARE_WIDTHS:
            with self.subTest(vw=vw):
                self.assertGreaterEqual(CSS.min_height(vw), 44.0)

    def test_the_ellipsis_backstop_is_still_there(self):
        """Below 320px the row does run out, and an ellipsis says the label continues
        where a hard clip mid-glyph said nothing. It is the last resort, not the fix."""
        # On the chip's own two lines, not merely somewhere in the sheet -- five other
        # rules use an ellipsis and a bare substring check passes while the date row
        # has none.
        self.assertEqual(decl(CSS.css, ".day small", "text-overflow"), "ellipsis")
        self.assertEqual(decl(CSS.css, ".day b", "text-overflow"), "ellipsis")

    # -- the measurements this file is built on -------------------------------------------

    def test_the_font_the_widths_were_measured_against_is_still_the_font(self):
        """Every number in LABEL_PER_PX is Archivo. If the stack changes they are
        fiction, and this test is the only thing that would say so."""
        flat = CSS.raw.replace(" ", "").replace("\n", "")
        self.assertIn("font-family:'Archivo',system-ui,sans-serif", flat)
        self.assertIn("@font-face", CSS.raw)
        # Self-hosted, so the metrics cannot change because a CDN swapped a file. The
        # comment-stripped copy, because a comment still records that it used to be
        # fetched from Google and why it stopped being.
        self.assertNotIn("fonts.googleapis.com", CSS.css)
        self.assertIn("src:url(fonts/archivo-latin.woff2)", CSS.css.replace(" ", ""))

    def test_the_parse_found_real_values(self):
        """A regex that quietly matches nothing would make every assertion above
        vacuous. These are the values the arithmetic is built from."""
        self.assertEqual(CSS.chip_pad_x(402), 1.0)
        self.assertEqual(CSS.chip_pad_x(1440), 2.0)
        self.assertEqual(CSS.row_pad_x(402), 14.0)
        self.assertEqual(CSS.row_pad_x(1440), 20.0)
        self.assertEqual(CSS.gap(402), 5.0)
        self.assertEqual(CSS.gap(430), 6.0)
        self.assertAlmostEqual(CSS.label_px(402), 9.6, places=2)
        self.assertAlmostEqual(CSS.label_px(430), 10.56, places=2)
        self.assertAlmostEqual(CSS.label_px(1440), 11.84, places=2)


if __name__ == "__main__":
    unittest.main()
