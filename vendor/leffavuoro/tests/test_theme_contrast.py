"""The accent is two colours, because one cannot meet both contrast rules.

`--accent` is chosen for a 3 px chain border and a focus ring (WCAG 1.4.11, 3:1). Light
theme's #B8860B measures 3.04:1 on `--bg`, which fails the 4.5:1 that 1.4.3 asks of small
text, and eight rules coloured text with it. `--accent-text` is the same hue darkened to
clear 4.5:1 against both surfaces in both themes; `--accent-on-ink` is the selected day
chip's label, painted on `--ink`. The ratios are computed rather than asserted as hex, so
a token may change but not to something unreadable. The pressed favourite star joined the
text rules on 2026-09-02; it measured 3.25:1 on `--surface` before.
"""
import pathlib
import re
import unittest

import _ctx


ROOT = pathlib.Path(_ctx.ROOT)
HTML = (ROOT / "index.html").read_text(encoding="utf-8")

# Every rule that paints text with the accent. Kept as a literal list: the point of the
# test is that this set and the stylesheet agree, so deriving one from the other would
# assert nothing.
TEXT_RULES = (
    ".vrow mark",
    ".fmt.prem",
    ".trailer",
    ".theatre-tag",
    ".tmdb",
    "#statusLink a",
    '.fav[aria-pressed="true"]',
    ".staleact",
)

# Accent as a non-text colour is fine at 3:1 and stays on --accent. The wordmark dot is a
# logotype, which 1.4.3 exempts outright. The open ticket menu's dots are an icon drawn in
# currentColor (1.4.11, 3:1), not text.
ACCENT_TEXT_ALLOWED = (".logo span", ".tk.open .more")

# The favourite button: its glyph is U+2605 / U+2606 at 1.15rem, well under the 24px
# that would make it large text.
FAV = ".fav"
FAV_PRESSED = '.fav[aria-pressed="true"]'

AA_TEXT = 4.5          # 1.4.3, text under 18.66px bold / 24px
AA_NON_TEXT = 3.0      # 1.4.11, borders and focus indicators


def tokens(block_re):
    m = re.search(block_re, HTML, re.S)
    if not m:
        raise AssertionError(f"token block not found: {block_re}")
    return {k: v for k, v in re.findall(r"--([a-z-]+)\s*:\s*(#[0-9A-Fa-f]{6})", m.group(1))}


def luminance(hex_colour):
    r, g, b = (int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


LIGHT = tokens(r":root\{(.*?)\}")
DARK = tokens(r'\[data-theme="dark"\]\{(.*?)\}')


class TokenContrastTest(unittest.TestCase):

    def test_the_light_theme_parsed_at_all(self):
        """Guards the two tests below against a regex that silently matched nothing."""
        for name in ("bg", "surface", "ink", "accent", "accent-text", "accent-on-ink"):
            self.assertIn(name, LIGHT, f"--{name} missing from :root")
            self.assertIn(name, DARK, f"--{name} missing from [data-theme=dark]")

    def test_accent_text_is_readable_on_both_surfaces_in_both_themes(self):
        """The defect this token exists for. Text sits on --bg or on --surface; both have
        to clear 4.5:1, in the theme the reader is using."""
        for theme, t in (("light", LIGHT), ("dark", DARK)):
            for surface in ("bg", "surface"):
                with self.subTest(theme=theme, surface=surface):
                    ratio = contrast(t["accent-text"], t[surface])
                    # Raw, never rounded: round(4.495, 2) is 4.5, and a token that misses
                    # the bar by three thousandths misses it.
                    self.assertGreaterEqual(
                        ratio, AA_TEXT,
                        f"--accent-text {t['accent-text']} on --{surface} {t[surface]} "
                        f"is {ratio:.3f}:1")

    def test_the_selected_day_label_is_readable_on_the_ink_chip(self):
        """`.day.active` paints --ink, so this label inverts with the theme while
        --accent does not. Dark theme measured 1.57:1 before this token existed."""
        for theme, t in (("light", LIGHT), ("dark", DARK)):
            with self.subTest(theme=theme):
                ratio = contrast(t["accent-on-ink"], t["ink"])
                self.assertGreaterEqual(
                    ratio, AA_TEXT,
                    f"--accent-on-ink {t['accent-on-ink']} on --ink {t['ink']} "
                    f"is {ratio:.3f}:1")

    def test_the_light_chip_label_is_unchanged(self):
        """The fix is dark-theme-only by construction: light already measured 5.46:1 and
        the point was not to redesign it."""
        self.assertEqual(LIGHT["accent-on-ink"], "#B8860B")

    def test_the_plain_accent_still_carries_a_border_and_a_ring(self):
        """--accent keeps its own job. If a later edit darkens it into --accent-text,
        the focus ring quietly drops under 3:1 and nothing else would notice."""
        for theme, t in (("light", LIGHT), ("dark", DARK)):
            for surface in ("bg", "surface"):
                with self.subTest(theme=theme, surface=surface):
                    ratio = contrast(t["accent"], t[surface])
                    self.assertGreaterEqual(ratio, AA_NON_TEXT,
                                            f"--accent on --{surface} is {ratio:.3f}:1")


class TokenRoutingTest(unittest.TestCase):
    """Contrast of a token nothing uses proves nothing. These pin the wiring."""

    def test_every_named_text_rule_uses_the_text_token(self):
        for rule in TEXT_RULES:
            with self.subTest(rule=rule):
                pattern = re.escape(rule) + r"\s*\{[^}]*color:var\(--accent-text\)"
                self.assertRegex(HTML, pattern)

    def test_no_other_rule_uses_the_text_token(self):
        """Keeps the token from spreading into borders and backgrounds, where it is too
        dark and where --accent was already correct."""
        found = re.findall(r"\n\s*([^\n{]+?)\{[^}]*var\(--accent-text\)", HTML)
        self.assertEqual(sorted(s.strip() for s in found), sorted(TEXT_RULES))

    def test_accent_is_no_longer_used_as_text_except_where_it_is_allowed(self):
        """`border-color` and `border-top-color` end in the same eight characters, so the
        lookbehind is what keeps this from passing on a rule it never checked."""
        found = re.findall(r"\n\s*([^\n{]+?)\{[^}]*(?<![-\w])color:var\(--accent\)", HTML)
        self.assertEqual(sorted(s.strip() for s in found), sorted(ACCENT_TEXT_ALLOWED))

    def test_the_selected_day_label_uses_the_ink_token(self):
        self.assertRegex(HTML, r"\.day\.active small\{color:var\(--accent-on-ink\)\}")


def rule_token(selector, prop):
    """The token `prop` resolves to in the last rule for exactly `selector` that sets it.

    Exactly: `.fav` must not match `.fav[aria-pressed="true"]`, `.fav.labelled` or
    `.fav:hover`, so the selector has to be followed by `{`. Two `.fav{` rules exist (the
    base one and a media-query override that sets only flex and padding), and taking the
    last body that names the property is what the cascade does for equal specificity.
    The lookbehind keeps `border-color` from answering for `color`."""
    bodies = re.findall(re.escape(selector) + r"\s*\{([^}]*)\}", HTML)
    if not bodies:
        raise AssertionError(f"no rule for {selector}")
    pattern = r"(?<![-\w])" + re.escape(prop) + r"\s*:\s*var\(--([a-z-]+)\)"
    hits = [m.group(1) for b in bodies for m in [re.search(pattern, b)] if m]
    if not hits:
        raise AssertionError(f"{selector} sets no {prop} from a token")
    return hits[-1]


class FavouriteStarTest(unittest.TestCase):
    """The star is the one control whose colour changes with state, so each state is
    measured on the surface the button paints, in the theme the reader is in.
    Light theme pressed measured 3.25:1 before the fix; every other cell already passed."""

    def test_the_pressed_star_paints_its_glyph_with_the_text_token(self):
        self.assertEqual(rule_token(FAV_PRESSED, "color"), "accent-text")

    def test_the_pressed_star_is_readable_on_its_own_surface_in_both_themes(self):
        """Resolves whatever token the rule names, so a later retune of `--accent-text`
        or of `--surface` is measured rather than trusted."""
        fg, bg = rule_token(FAV_PRESSED, "color"), rule_token(FAV, "background")
        for theme, t in (("light", LIGHT), ("dark", DARK)):
            with self.subTest(theme=theme):
                ratio = contrast(t[fg], t[bg])
                self.assertGreaterEqual(
                    ratio, AA_TEXT,
                    f"pressed star --{fg} {t[fg]} on --{bg} {t[bg]} is {ratio:.3f}:1")

    def test_the_unpressed_star_is_readable_in_both_themes(self):
        """`--muted` on `--surface`. Unchanged by the fix and measured so that it stays
        that way: 5.98:1 light, 5.73:1 dark on 2026-09-02."""
        fg, bg = rule_token(FAV, "color"), rule_token(FAV, "background")
        for theme, t in (("light", LIGHT), ("dark", DARK)):
            with self.subTest(theme=theme):
                ratio = contrast(t[fg], t[bg])
                self.assertGreaterEqual(
                    ratio, AA_TEXT,
                    f"unpressed star --{fg} {t[fg]} on --{bg} {t[bg]} is {ratio:.3f}:1")

    def test_the_pressed_border_keeps_the_accent_and_its_own_bar(self):
        """The border is the 1.4.11 case `--accent` was tuned for. Moving it to the text
        token would darken it for no reader's benefit."""
        self.assertEqual(rule_token(FAV_PRESSED, "border-color"), "accent")
        bg = rule_token(FAV, "background")
        for theme, t in (("light", LIGHT), ("dark", DARK)):
            with self.subTest(theme=theme):
                ratio = contrast(t["accent"], t[bg])
                self.assertGreaterEqual(ratio, AA_NON_TEXT,
                                        f"pressed border on --{bg} is {ratio:.3f}:1")


class SearchHighlightTest(unittest.TestCase):
    """The picker's search hit (`.vrow mark`) is measured on the grounds it actually
    sits on: the sheet's --bg at rest and --accent-soft on a hovered row. --accent-text
    on --accent-soft measured 4.41:1 in the light theme on 2026-09-13, so the hovered
    hit paints --ink. The rest state keeps the accent. Both pairs are measured through
    the tokens the rules name, so a retune of either token is measured, never pinned."""

    def test_the_hit_at_rest_keeps_the_text_token_and_is_readable(self):
        fg, bg = rule_token(".vrow mark", "color"), rule_token(".vsheet", "background")
        self.assertEqual(fg, "accent-text")
        for theme, t in (("light", LIGHT), ("dark", DARK)):
            with self.subTest(theme=theme):
                ratio = contrast(t[fg], t[bg])
                self.assertGreaterEqual(ratio, AA_TEXT,
                                        f"search hit --{fg} on --{bg} is {ratio:.3f}:1")

    def test_the_hovered_hit_is_readable_on_the_hover_ground(self):
        fg, bg = rule_token(".vrow:hover mark", "color"), rule_token(".vrow:hover", "background")
        for theme, t in (("light", LIGHT), ("dark", DARK)):
            with self.subTest(theme=theme):
                ratio = contrast(t[fg], t[bg])
                self.assertGreaterEqual(ratio, AA_TEXT,
                                        f"hovered hit --{fg} on --{bg} is {ratio:.3f}:1")


if __name__ == "__main__":
    unittest.main()
