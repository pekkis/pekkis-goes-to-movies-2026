"""Provider text inside the JSON-LD block must not be able to close the element.

The HTML parser ends a script element at the first literal "</script>" regardless of its
type attribute, and titles, theatre names and booking URLs are provider text published
verbatim. `ld_json()` therefore \\uXXXX-escapes the HTML-significant characters, which is
equivalent JSON.
"""
import datetime
import json
import unittest

import _ctx                                                # noqa: F401
import build_pages as bp

HOSTILE = "Film </script><script>throw 1</script>"
TODAY = datetime.date(2026, 8, 31)


def days_with(title, theatre="Kino Testi"):
    return {TODAY.isoformat(): {title: [
        {"theatre": theatre, "start": f"{TODAY.isoformat()}T18:00:00",
         "url": "https://example.fi/tickets?a=1&b=2"},
    ]}}


class LdJsonEscapingTest(unittest.TestCase):
    def test_no_html_significant_bytes_survive(self):
        """"</script>" is only reachable through a literal "<", so none may remain --
        in a title, a theatre name, or a URL's query separator."""
        out = bp.ld_json(days_with(HOSTILE, theatre="Kino & <b>"), TODAY,
                         "Helsinki", {})
        for ch in "<>&":
            self.assertNotIn(ch, out)
        self.assertNotIn("</script", out.lower())

    def test_escaping_is_lossless(self):
        """The escapes are alternative JSON spellings, not sanitisation: a crawler
        parsing the block must see the exact provider strings."""
        out = bp.ld_json(days_with(HOSTILE, theatre="Kino & <b>"), TODAY,
                         "Helsinki", {})
        names = {n.get("name") for n in json.loads(out)["@graph"]}
        self.assertIn(HOSTILE, names)
        self.assertIn("Kino & <b>", names)

    def test_js_line_separators_are_escaped(self):
        """U+2028/U+2029 are legal in JSON but not in JavaScript source, and
        ensure_ascii=False would otherwise emit them raw."""
        title = "A\u2028B\u2029C"
        out = bp.ld_json(days_with(title), TODAY, "Helsinki", {})
        self.assertNotIn("\u2028", out)
        self.assertNotIn("\u2029", out)
        names = {n.get("name") for n in json.loads(out)["@graph"]}
        self.assertIn(title, names)

    def test_page_has_exactly_one_script_closer(self):
        """The whole-document property the escaping exists for: the only "</script>"
        closers are the ones page() writes itself -- one per script element it emits,
        the JSON-LD block, the two theme scripts and the pageview.js tag -- and the
        hostile title adds none."""
        html = bp.page(
            lang="fi", paths={"fi": "/teatteri/x/", "sv": "/sv/teatteri/x/",
                              "en": "/en/theatre/x/"},
            title="X", desc="d", h1="h", sub="s", intro="i",
            days=days_with(HOSTILE), today=TODAY, t=bp.L["fi"], extra={},
            gmap={}, city="Helsinki", with_venue=False, legend="", also="",
            og_image="/icon-512.png", app_href="/", area="x", chain_css="", kind="theatre")
        self.assertEqual(html.lower().count("</script>"), html.lower().count("<script"))
        self.assertEqual(html.lower().count("</script>"), 4)


if __name__ == "__main__":
    unittest.main()


def days_priced(*prices):
    return {TODAY.isoformat(): {"Film": [
        {"theatre": "Kino Testi", "start": f"{TODAY.isoformat()}T{18 + i}:00:00",
         "url": f"https://example.fi/tickets?id={i}", "price": p}
        for i, p in enumerate(prices)]}}


class LdJsonOfferTest(unittest.TestCase):
    """Google reads `price: 0` as admission with no payment. Leffabuumi printed "Lippu
    0,00€" on a sold-out premiere without saying whether it was free or by invitation."""

    def events(self, *prices):
        out = bp.ld_json(days_priced(*prices), TODAY, "Helsinki", {})
        return [n for n in json.loads(out)["@graph"] if n["@type"] == "ScreeningEvent"]

    def test_a_zero_price_keeps_the_event_and_its_url_but_no_offer(self):
        for price in ("0€", "0,00€", "0.00€"):
            with self.subTest(price=price):
                (ev,) = self.events(price)
                self.assertEqual(ev["url"], "https://example.fi/tickets?id=0")
                self.assertNotIn("offers", ev)

    def test_a_positive_price_keeps_its_offer(self):
        a, b = self.events("12.5€", "alkaen 10€")
        self.assertEqual(a["offers"], {"@type": "Offer", "url": "https://example.fi/tickets?id=0",
                                       "price": "12.5", "priceCurrency": "EUR"})
        self.assertEqual(b["offers"]["price"], "10")

    def test_a_free_admission_label_is_the_confirmation_a_zero_lacks(self):
        """With the ticket's label, `price: 0` together, as the 2026-09-25 record says."""
        free, member, bare = self.events("Vapaa pääsy", "Vapaa pääsy jäsenille", "Free")
        self.assertEqual((free["offers"]["price"], bare["offers"]["price"]), ("0", "0"))
        self.assertNotIn("offers", member)
