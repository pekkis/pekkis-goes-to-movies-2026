"""Every icon, manifest and preload a published page links to exists in the checkout.

The status page and the privacy page linked `/favicon.svg`, a file this repository never
held, so every load of either answered a 404. Both now name `icon-192.png`, as the app
and the generated pages do. Covers every tracked page, generated ones included.
"""
import re
import subprocess
import unittest
import urllib.parse

import _ctx

LINK = re.compile(r"<link\b[^>]*>", re.I)
ATTR = re.compile(r'\b(rel|href)="([^"]*)"', re.I)
ASSET_RELS = {"icon", "apple-touch-icon", "manifest", "preload"}


def pages():
    out = subprocess.run(["git", "ls-files", "*.html"], cwd=_ctx.ROOT, capture_output=True,
                         text=True, check=True).stdout.split()
    return [_ctx.ROOT / p for p in out]


def asset_links(html):
    for tag in LINK.findall(html):
        a = {k.lower(): v for k, v in ATTR.findall(tag)}
        if set(a.get("rel", "").lower().split()) & ASSET_RELS and "href" in a:
            yield a["href"]


class PageAssetTest(unittest.TestCase):

    def test_the_hand_written_pages_are_covered(self):
        names = {str(p.relative_to(_ctx.ROOT)) for p in pages()}
        for page in ("index.html", "status/index.html", "tietosuoja/index.html"):
            self.assertIn(page, names)

    def test_every_linked_icon_manifest_and_preload_exists(self):
        checked = 0
        for page in pages():
            for href in asset_links(page.read_text(encoding="utf-8")):
                u = urllib.parse.urlsplit(href)
                if u.scheme or u.netloc:
                    continue                      # another origin: not this checkout's file
                path = u.path
                target = (_ctx.ROOT / path.lstrip("/")) if path.startswith("/") \
                    else (page.parent / path)
                checked += 1
                with self.subTest(page=str(page.relative_to(_ctx.ROOT)), href=href):
                    self.assertTrue(target.is_file(), target)
        self.assertGreater(checked, 3)


if __name__ == "__main__":
    unittest.main()
