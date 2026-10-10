"""Every adapter's page getter asks for a page the same way.

`common.get_text` is that one way: `cache=True`, the Finnish page headers, a 30 s timeout
and a UTF-8 decode with replacement. Commit `4ce7e25e1` folded seven byte-identical
wrappers into it and counted twelve more that differ. Measured again on 2026-09-19, that
count was right about the twelve it looked at and silently untrue of twelve more: nine
wrappers were byte-identical to `get_text` and were never counted, because that pass
grouped on the source text and those nine carry no `(url, tries=3, timeout=30)`
parameters, and three more wrap the same call inside a guard. All twelve are folded now.

**Why this test and not the fold itself.** Folding code that is already identical cannot
be break-verified: re-inserting a byte-identical wrapper is an equivalent mutation and
scores VOID by construction. What can be verified is the property the fold exists to
give, which no test in this repo asserted before: that each adapter reaches its host with
the shared header set and the shared flags. Grepping `tests/*.py` for `accept-language`,
`headers[` and `accept"]` returned nothing outside `tests/browser` and
`test_common_fetch.py`'s check of the constant itself, so a wrapper drifting to a
different Accept-Language went unnoticed by everything.

The deliberate variants are deliberately absent from the table below, and the reason is
recorded per adapter in `docs/research/adapter-http.md`: BioRex and Kino Regina POST,
Johku needs its own opener for the 103 Early Hints its hosts send before the 200, Heureka
sets `cache=False` because its pages answer `If-None-Match` with a full 200, Gilda and
Vista raise the timeout, Nexxo sends a referer, and seven adapters ask for JSON or XML
rather than HTML. Bio Savoy's `sv-AX,sv;q=0.9` and eTiketti's extra `accept` header are
unsettled rather than deliberate; they are left alone and named in that file.
"""
import unittest

import _ctx                                                # noqa: F401
import common


# module, attribute, args. One entry per adapter whose page getter goes through
# `common.get_text`: the nine that already did and the twelve folded on 2026-09-19.
GETTERS = [
    ("hamina", "get", ("https://example.test/a",)),
    ("huvimylly", "get", ("https://example.test/a",)),
    ("kinola", "get", ("https://example.test/a",)),
    ("kinotour", "get", ("https://example.test/a",)),
    ("lieksa", "get", ("https://example.test/a",)),
    ("marita", "get", ("https://example.test/a",)),
    ("navetta", "get", ("https://example.test/a",)),
    ("pallas", "get", ("https://example.test/a",)),
    ("vpk", "get", ("https://example.test/a",)),
    ("biokaari", "get_page", ()),
    ("cinemahouse", "get", ("https://example.test/a",)),
    ("engel", "fetch_page", ()),
    ("isohannu", "get_page", ()),
    ("julia", "get_listing", ()),
    ("kinoakseli", "fetch_page", ()),
    ("kirkkonummi", "get_listing", ()),
    ("kuvakukko", "_get", ("https://example.test/a",)),
    ("orion", "fetch_page", ()),
    ("tapiola", "get_listing", ()),
    ("tmb", "get", ("https://example.test/a",)),
    ("vaakuna", "get_listing", ()),
]

# What `common.get_text` asks `common.fetch` for. Written out rather than read off the
# function, so a change to the shared defaults fails here and has to be made on purpose.
WANT_HEADERS = {"user-agent": "Leffavuoro/1.0 (+https://leffavuoro.fi)",
                "accept-language": "fi-FI,fi;q=0.9"}
WANT_TIMEOUT = 30


class GetTextContractTest(unittest.TestCase):
    """Each getter, with its module's own `fetch` stubbed, and what it asked for."""

    def call(self, name, attr, args):
        """-> the kwargs the module's `fetch` was handed. Raises nothing the caller sees:
        the three guard wrappers parse what comes back and will fail on a stub body, and
        the request is already made by then."""
        mod = __import__(name)
        seen = {}
        real = mod.fetch

        def stub(url, **kw):
            seen["url"] = url
            seen.update(kw)
            return b"<html></html>"

        mod.fetch = stub
        try:
            try:
                getattr(mod, attr)(*args)
            except Exception:                 # a guard or a parser, after the request
                pass
        finally:
            mod.fetch = real
        return seen

    def test_every_page_getter_sends_the_shared_headers(self):
        """The one that matters for a cinema reading its own logs: the same honest
        User-Agent and the same Accept-Language from every adapter."""
        for name, attr, args in GETTERS:
            with self.subTest(module=name):
                seen = self.call(name, attr, args)
                self.assertEqual(seen.get("headers"), WANT_HEADERS)

    def test_every_page_getter_asks_the_same_way_otherwise(self):
        for name, attr, args in GETTERS:
            with self.subTest(module=name):
                seen = self.call(name, attr, args)
                self.assertIs(seen.get("cache"), True)
                self.assertEqual(seen.get("timeout"), WANT_TIMEOUT)

    def test_the_shared_defaults_are_what_this_table_says(self):
        """The counterweight. If `get_text` changes, the two tests above would go on
        passing against whatever it changed to, so the constants are pinned here as well
        as in test_common_fetch.py."""
        self.assertEqual(common.TEXT_HEADERS, WANT_HEADERS)
        seen = {}
        common.get_text("https://example.test/a",
                        fetcher=lambda url, **kw: seen.update(kw) or b"x")
        self.assertEqual((seen["headers"], seen["cache"], seen["timeout"]),
                         (WANT_HEADERS, True, WANT_TIMEOUT))

    def test_the_getter_reaches_the_modules_own_fetch(self):
        """The seam every adapter test relies on. A wrapper that let `get_text` reach
        `common.fetch` directly would turn every one of those stubs into a no-op and the
        adapter tests would quietly start talking to the internet."""
        for name, attr, args in GETTERS:
            with self.subTest(module=name):
                self.assertIn("url", self.call(name, attr, args))


if __name__ == "__main__":
    unittest.main()
