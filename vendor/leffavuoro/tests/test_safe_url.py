"""A provider's URL must not be able to become `javascript:` on the way to an href.

`safeUrl` read the scheme off the raw string. A URL parser deletes ASCII tab, LF and CR
anywhere in the URL and strips control characters off its ends, so
`java<LF>script:alert(1)` matched no scheme, was returned as a relative URL and resolved
to javascript:. LF, CR, tab and a leading NUL all got through to booking and trailer hrefs.

The functions are sliced verbatim out of index.html by tests/safe_url_harness.js, and the
harness resolves whatever they accept through a real WHATWG URL parser and reports the
protocol, since the defect was the gap between the tested string and the browser's URL.
"""
import json
import pathlib
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "safe_url_harness.js"

# Every payload that must never come back out of safeUrl, whatever it is dressed as.
HOSTILE = ["js_plain", "js_lf", "js_cr", "js_tab", "js_leading_nul", "js_crlf",
           "js_many_lf", "js_trailing_del", "js_leading_vt", "js_mixed_case",
           "js_upper", "data_html", "vbscript", "file_scheme"]


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class SafeUrlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    # -- the reported bug --------------------------------------------------------------

    def test_a_newline_cannot_hide_the_scheme(self):
        """The exact payload. `java<LF>script:` was accepted and resolved to
        javascript:, because `[a-z0-9+.-]*` stops at the LF and the match fails, which
        the old code read as "no scheme, therefore relative, therefore fine"."""
        self.assertFalse(self.r["js_lf"]["accepted"])

    def test_a_carriage_return_cannot_hide_the_scheme(self):
        self.assertFalse(self.r["js_cr"]["accepted"])

    def test_a_tab_cannot_hide_the_scheme(self):
        self.assertFalse(self.r["js_tab"]["accepted"])

    def test_a_leading_nul_cannot_hide_the_scheme(self):
        """Not in the original report, found while reproducing it. `trim()` removes
        whitespace and NUL is not whitespace, so it survived to the scheme match and
        broke it the same way -- and a parser strips it before reading the scheme."""
        self.assertFalse(self.r["js_leading_nul"]["accepted"])

    def test_the_separator_can_repeat_or_pair_up(self):
        """One check per character class would have passed CRLF and a payload split at
        every letter. Both are the same rule applied more than once."""
        self.assertFalse(self.r["js_crlf"]["accepted"])
        self.assertFalse(self.r["js_many_lf"]["accepted"])

    def test_a_control_character_anywhere_is_enough(self):
        """DEL past the end of an otherwise-plain payload, and a vertical tab in front
        of one. VT is removed by trim(), so this case says the two guards do not
        silently depend on each other."""
        self.assertFalse(self.r["js_trailing_del"]["accepted"])
        self.assertFalse(self.r["js_leading_vt"]["accepted"])

    # -- the invariant, stated against a real URL parser rather than the regex ----------

    def test_nothing_accepted_resolves_to_a_non_http_scheme(self):
        """The property the function exists for. Written against every case in the
        table at once so a payload added later is covered without a test being added:
        whatever comes back out, a browser resolving it lands on http or https."""
        for name, rec in self.r.items():
            if rec["accepted"]:
                self.assertIn(rec["proto"], ("http:", "https:"),
                              f"{name} resolved to {rec['proto']}")

    def test_every_hostile_input_is_refused(self):
        for name in HOSTILE:
            self.assertFalse(self.r[name]["accepted"], f"{name} was accepted")

    # -- schemes that were already refused ---------------------------------------------

    def test_case_does_not_smuggle_a_scheme(self):
        self.assertFalse(self.r["js_mixed_case"]["accepted"])
        self.assertFalse(self.r["js_upper"]["accepted"])

    def test_data_vbscript_and_file_stay_refused(self):
        """These never depended on the control-character hole. They are here so that a
        rewrite of the scheme test cannot quietly drop them."""
        self.assertFalse(self.r["data_html"]["accepted"])
        self.assertFalse(self.r["vbscript"]["accepted"])
        self.assertFalse(self.r["file_scheme"]["accepted"])

    # -- and the links that have to keep working ---------------------------------------

    def test_ordinary_ticket_and_trailer_links_pass(self):
        for name in ("https_plain", "http_plain", "https_upper", "relative_page"):
            self.assertTrue(self.r[name]["accepted"], f"{name} was refused")

    def test_a_trailing_newline_from_an_adapter_still_passes(self):
        """The case that decides reject-over-strip. Adapters do leave a newline on the
        end of a scraped href; `trim()` takes it off before the control check runs, so
        rejecting on a control character costs nothing real. If trim() were ever moved
        after the check, this goes red and the choice has to be made again."""
        self.assertTrue(self.r["https_trailing_lf"]["accepted"])
        self.assertEqual(self.r["https_trailing_lf"]["resolved"], "https://x.fi/a")
        self.assertTrue(self.r["https_surrounding_ws"]["accepted"])

    def test_the_ampersand_survives_as_an_entity(self):
        """esc() runs on the way out, so a query string reaches the attribute as
        `&amp;` and the browser reads back the `&`. Pinned because a showtimeId query
        that lost its second parameter would 404 quietly."""
        self.assertEqual(self.r["https_amp"]["out"], "https://x.fi/a?b=1&amp;c=2")
        self.assertEqual(self.r["https_amp"]["resolved"], "https://x.fi/a?b=1&c=2")

    def test_a_protocol_relative_link_is_allowed(self):
        """Pinned rather than argued: a ticket link is meant to leave this origin, so
        `//host/path` is a working link and not a hole. It is here so that changing the
        answer is a decision someone makes on purpose."""
        self.assertTrue(self.r["protocol_rel"]["accepted"])
        self.assertEqual(self.r["protocol_rel"]["proto"], "https:")

    def test_nothing_in_is_nothing_out(self):
        for name in ("empty", "blank", "null", "undefined"):
            self.assertEqual(self.r[name]["out"], "", name)


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class SafeAssetUrlTest(unittest.TestCase):
    """The poster sink is a different question -- an <img> is a request the browser
    makes on its own, so the README's claim that posters are served from this origin
    rests on this one. It answers with a path allowlist, which a control character
    cannot walk out of, but it shares the guard so that the two sinks cannot drift into
    disagreeing about what a URL is."""

    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    def test_a_mirrored_poster_passes_in_all_three_spellings(self):
        for name in ("asset_ok", "asset_dot_slash", "asset_root_slash"):
            self.assertTrue(self.r[name]["accepted"], f"{name} was refused")
            self.assertTrue(self.r[name]["sameOrigin"], f"{name} left the origin")

    def test_a_third_party_poster_is_refused(self):
        """mirror_posters.py leaves the hot-linked URL in the data when a download
        fails, on purpose, so this is a live case and not a hypothetical."""
        self.assertFalse(self.r["asset_third_party"]["accepted"])
        self.assertFalse(self.r["asset_protocol_rel"]["accepted"])

    def test_a_path_outside_the_mirror_is_refused(self):
        self.assertFalse(self.r["asset_outside_dir"]["accepted"])

    def test_control_characters_are_refused_here_too(self):
        self.assertFalse(self.r["asset_js"]["accepted"])
        self.assertFalse(self.r["asset_js_lf"]["accepted"])
        self.assertFalse(self.r["asset_lf_inside"]["accepted"])
        self.assertFalse(self.r["asset_lf_in_prefix"]["accepted"])

    def test_nothing_in_is_nothing_out(self):
        self.assertEqual(self.r["asset_empty"]["out"], "")


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class SafeUrlRawTest(unittest.TestCase):
    """`safeUrl` rejected bad schemes and HTML-escaped the result in one function. The
    escaping is wrong for the calendar file: `icsFor` wrote into `URL:` and
    `DESCRIPTION:`, where a calendar follows `&amp;` literally, and 21 of 4486 committed
    ticket URLs carry an `&`. `safeUrlRaw` holds the scheme check and `safeUrl` is
    `esc()` over it, so they share one answer about what a URL is."""

    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    def test_it_returns_the_url_unescaped_where_safeurl_escapes(self):
        for raw, html, ch, entity in (("raw_amp", "https_amp", "&", "&amp;"),
                                      ("raw_apostrophe", "https_apostrophe", "'", "&#39;"),
                                      ("raw_quote", "https_quote", '"', "&quot;")):
            self.assertIn(ch, self.r[raw]["out"], raw)
            self.assertNotIn(entity, self.r[raw]["out"], raw)
            self.assertIn(entity, self.r[html]["out"], html)

    def test_an_ordinary_ticket_url_comes_back_byte_for_byte(self):
        self.assertEqual(self.r["raw_plain"]["out"],
                         "https://www.finnkino.fi/liput/valitse-paikat/?showtimeId=1")
        self.assertEqual(self.r["raw_amp"]["out"], "https://x.fi/a?b=1&c=2")

    def test_it_accepts_exactly_what_safeurl_accepts(self):
        """Same rules, so a scheme-less path still passes and every hostile spelling
        still fails. Reversing the scheme-less decision is a separate item."""
        self.assertTrue(self.r["raw_relative"]["accepted"])
        self.assertTrue(self.r["raw_trailing_lf"]["accepted"], "trim() runs first here too")
        for name in ("raw_js", "raw_js_lf", "raw_js_leading_nul", "raw_data_html"):
            self.assertFalse(self.r[name]["accepted"], name)

    def test_nothing_in_is_nothing_out(self):
        self.assertEqual(self.r["raw_empty"]["out"], "")


if __name__ == "__main__":
    unittest.main()
