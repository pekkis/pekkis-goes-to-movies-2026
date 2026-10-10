"""What a search engine may quote from the app page (2026-09-13).

Google's copy of the front page read "Leffavuoro. EN. Tallenna. Tänään 29.8. Huomenna
30.8. ... Leffat Ajat. Suom. puhe. Lapsille. Aikataulua ei juuri nyt saatu ladattua". The
renderer cannot read data/ (robots.txt disallows it), so what it sees is the chrome and
the load-failure message. `data-nosnippet` marks that chrome so the snippet falls back to
the meta description. It is a boolean attribute valid on div, span and section, must not
be toggled on an existing node from script, and changes nothing a visitor sees.

The film list, the footer sentence and the meta description stay quotable.
"""
import re
import unittest
from html.parser import HTMLParser

import _ctx


CLIENT = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")
SCRIPT = CLIENT[CLIENT.rfind("<script>"):]
STATIC = CLIENT[:CLIENT.rfind("<script>")]


class Marks(HTMLParser):
    """Every element in the static markup, with its attributes, in document order."""

    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def elements():
    p = Marks()
    p.feed(STATIC)
    return p.elements


def marked():
    return [(t, a) for t, a in elements() if "data-nosnippet" in a]


class StaticMarkupTest(unittest.TestCase):
    def test_the_chrome_is_excluded(self):
        keys = {a.get("id") or a.get("class") for _, a in marked()}
        for want in ("bar", "pinned", "stale", "partial", "vwrap", "listStatus", "tagkey",
                     "status"):
            self.assertIn(want, keys)

    def test_only_supported_elements_carry_it(self):
        for tag, _ in marked():
            self.assertIn(tag, ("div", "span", "section"), tag)

    def test_it_is_boolean(self):
        for tag, a in marked():
            self.assertIsNone(a["data-nosnippet"], (tag, a))

    def test_the_footer_and_main_stay_quotable(self):
        for tag, a in elements():
            if tag in ("footer", "main"):
                self.assertNotIn("data-nosnippet", a, tag)
        self.assertIn("Suomalaisten elokuvateatterien näytösajat", STATIC)

    def test_the_description_names_no_number(self):
        m = re.search(r'<meta name="description" content="([^"]*)">', STATIC)
        self.assertTrue(m and m.group(1).strip())
        self.assertNotRegex(m.group(1), r"\d")


class ScriptTest(unittest.TestCase):
    def test_every_status_message_is_created_excluded(self):
        # Loading, load-failure, empty-day and no-more-showtimes messages are the text a
        # renderer without data sees. Each is created with the attribute, which Google
        # allows; a film row is not a status and stays quotable.
        plain = re.findall(r'<div class="status"[^>]*>', SCRIPT)
        self.assertTrue(plain)
        for tag in plain:
            self.assertIn("data-nosnippet", tag, tag)

    def test_the_attribute_is_never_toggled_from_script(self):
        self.assertNotRegex(SCRIPT, r"(setAttribute|removeAttribute|toggleAttribute)\(\s*['\"]data-nosnippet")
        self.assertNotIn("dataset.nosnippet", SCRIPT)


class SiteNameTest(unittest.TestCase):
    """Google reads the site name from `WebSite` structured data on the home page first,
    then og:site_name, the title and the wordmark. The four have to agree."""

    def blocks(self):
        import json
        return [json.loads(b) for b in
                re.findall(r'<script type="application/ld\+json">(.*?)</script>', CLIENT, re.S)]

    def test_one_website_node_on_the_home_page(self):
        sites = [b for b in self.blocks() if b.get("@type") == "WebSite"]
        self.assertEqual(len(sites), 1)
        site = sites[0]
        self.assertEqual(site["@context"], "https://schema.org")
        self.assertEqual(site["name"], "Leffavuoro")
        canonical = re.search(r'<link rel="canonical" href="([^"]+)">', CLIENT).group(1)
        self.assertEqual(site["url"], canonical)
        og = re.search(r'<meta property="og:site_name" content="([^"]+)">', CLIENT).group(1)
        self.assertEqual(site["name"], og)
        self.assertTrue(re.search(r"<title>Leffavuoro\b", CLIENT))


if __name__ == "__main__":
    unittest.main()
