"""What the client interpolates into an attribute, and what it writes into a stylesheet.

CLAUDE.md states the rule: escape provider text at every `innerHTML` interpolation. It was
prose alone, and on 2026-09-19 three attribute values were interpolated raw, all of them
derived from provider JSON: `data-goto="${hit.iso}"`, `data-goto="${next}"` and the
premiere chip's `${d}`. None is a live hole -- every one of those values is a date this
repo generated and serves from its own origin -- so this is a rule kept rather than a
breakout closed, and the sweep below is what keeps it kept.

The chain palette is the one interpolation `esc()` cannot help with. It writes into a
`<style>` element, where escaping for HTML does nothing and a stray `}` ends the rule and
starts whatever follows it, so the shape of both halves is checked instead.

The sweep reads `="${...}"` only. A single-quoted attribute holding a nested brace is
beyond a regex, and the one the page has (`data-f='${tile...}'`) builds its value from a
number and a letter class.
"""
import pathlib
import re
import unittest

import _ctx                                                # noqa: F401
import registry

ROOT = _ctx.ROOT
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
ATTR = re.compile(r'=\s*"\$\{([^}]*)\}')

# Wrapped by the rule, or wrapping something themselves.
WRAPPED = ("esc(", "safeUrl(")

# Everything else the page interpolates into an attribute, with why it is not provider
# text. A new name here is a decision: check where the value comes from before adding it,
# because "it is not a string a cinema publishes" is the whole claim this list makes.
INTERNAL = {
    # booleans and language codes the page owns
    "on", "open", "dir", "code", "code === state.lang", "r.current ? 'true' : 'false'",
    # the Ajat floor's reveal, aria-expanded off a boolean this file sets
    "state.showPast",
    # class strings this file builds out of its own literals
    "cls", "stubClass", "stubsCls",
    # generated dates and list indices: 'YYYY-MM-DD' from fiDate, integers from the render
    "iso", "i", "s._i", "hit._i", "el.dataset.i", "el.dataset.pastday", "b.dataset.pastday",
    # a lookup into the page's own table, L[state.lang][...]
    "verb",
    # safeAssetUrl() results, which is the poster check rather than the link one
    "posterUrl", "sheetPoster",
    # safeUrl() result: the stale banner's link to the late provider's own site,
    # built from the registry host in data/providers.json
    "siteHref",
}


def attribute_interpolations():
    """{expression: [line numbers]} for every `="${...}"` in the page."""
    out = {}
    for n, line in enumerate(HTML.split("\n"), 1):
        for m in ATTR.finditer(line):
            out.setdefault(m.group(1).strip(), []).append(n)
    return out


class AttributeInterpolationTest(unittest.TestCase):
    def test_every_attribute_value_is_escaped_or_named_as_the_page_s_own(self):
        found = attribute_interpolations()
        raw = {e: lines for e, lines in found.items()
               if not e.startswith(WRAPPED) and e not in INTERNAL}
        self.assertEqual(raw, {},
                         "an attribute interpolates something that is neither wrapped in "
                         "esc()/safeUrl() nor listed in INTERNAL with its reason")

    def test_the_sweep_actually_reads_the_page(self):
        """A regex that matched nothing would pass the test above in silence."""
        found = attribute_interpolations()
        self.assertGreater(len(found), 25, found)
        self.assertTrue(any(e.startswith("esc(") for e in found))

    def test_the_three_that_shipped_raw_are_wrapped(self):
        for site in ('data-goto="${esc(hit.iso)}"',
                     'data-goto="${esc(next)}"',
                     '${L[state.lang].premiere} ${esc(d)}'):
            with self.subTest(site=site):
                self.assertIn(site, HTML)

    def test_esc_escapes_the_double_quote_so_an_attribute_cannot_be_broken_out_of(self):
        """The rule above is only worth anything if esc() covers the quote that ends an
        attribute value, not just the angle brackets.

        Each pair is pinned whole. Asserting that the body merely contains a `"` and a
        `&quot;` somewhere passed with the mapping for the quote deleted, because the
        character class above it still holds one and the replacement table still holds
        the other.
        """
        body = HTML[HTML.index("const esc = v =>"):]
        body = body[:body.index("const safeUrl")]
        self.assertIn(r"""replace(/[&<>"']/g,""", body)
        for pair in ("'&':'&amp;'", "'<':'&lt;'", "'>':'&gt;'",
                     """'"':'&quot;'""", '''"'":'&#39;\''''):
            with self.subTest(pair=pair):
                self.assertIn(pair, body)


class ChainPaletteTest(unittest.TestCase):
    """`applyProviders` writes `.chain-{id}{--chain:{accent}}` into a <style>."""

    def body(self):
        return HTML[HTML.index("el.textContent = PROVIDERS.filter"):
                    HTML.index(".map(p => `.chain-${p.id}{--chain:${p.accent}}`).join('');")]

    def test_both_halves_of_the_rule_are_shape_checked_before_they_are_written(self):
        body = self.body()
        self.assertIn("/^[a-z0-9-]+$/.test(p.id)", body)
        self.assertIn("/^#[0-9a-f]{6}$/i.test(p.accent)", body)

    def test_a_provider_that_fails_the_shape_is_left_out_and_said_out_loud(self):
        body = self.body()
        self.assertIn("console.warn", body)
        self.assertIn("return false;", body)

    def test_every_provider_in_the_registry_passes_those_shapes(self):
        """The check must not quietly drop a real chain: a provider with no rule in the
        palette loses the one signal a combined city view has besides the venue name."""
        ident, accent = re.compile(r"^[a-z0-9-]+$"), re.compile(r"^#[0-9a-f]{6}$", re.I)
        for p in registry.PROVIDERS:
            with self.subTest(provider=p["id"]):
                self.assertRegex(p["id"], ident)
                self.assertRegex(p["accent"], accent)

    def test_the_committed_fallback_passes_them_too(self):
        """`PROV_FALLBACK` is the list in force when data/providers.json cannot be read,
        so it goes through the same filter."""
        block = HTML.split("/* providers:start */")[1].split("/* providers:end */")[0]
        ids = re.findall(r"id:'([^']*)'", block)
        accents = re.findall(r"accent:'([^']*)'", block)
        self.assertEqual(len(ids), len(registry.PROVIDERS))
        self.assertEqual(len(accents), len(registry.PROVIDERS))
        for i, a in zip(ids, accents):
            with self.subTest(provider=i):
                self.assertRegex(i, r"^[a-z0-9-]+$")
                self.assertRegex(a, r"^#[0-9a-fA-F]{6}$")


if __name__ == "__main__":
    unittest.main()
