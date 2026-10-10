"""The privacy page in the reader's language (2026-09-22).

`/tietosuoja/` is one document with a section per language and three anchor links between
them. The app linked to it as a bare `/tietosuoja/`, so an English reader arrived at the
Finnish heading and the Finnish introduction, and every link out of the page was a bare
`/`, so they left in whatever language they had stored (docs/research/flow-review.md, 2026-09-22).

These pin the two halves: the app names the section and passes the way back, and the page
rebuilds its three links out of what it was given.

The page's script is checked for syntax by `scripts/check_inline_js.py`, which now covers
this file; what it does to the DOM stays verified live.
"""
import json
import pathlib
import re
import shutil
import subprocess
import unittest

import _ctx


ROOT = _ctx.ROOT
APP = (ROOT / "index.html").read_text(encoding="utf-8")
PRIVACY = (ROOT / "tietosuoja" / "index.html").read_text(encoding="utf-8")
LANGS = ("fi", "sv", "en")


class TheAppsHalfTest(unittest.TestCase):
    def test_the_link_names_the_section_and_carries_the_way_back(self):
        m = re.search(r"function privacyHref\(\)\{(.*?)\n  \}", APP, re.S)
        self.assertIsNotNone(m, "privacyHref not found in index.html")
        body = m.group(1)
        self.assertIn("q.set('area', state.area)", body)
        self.assertIn("q.set('lang', state.lang)", body)
        self.assertIn("/tietosuoja/?${q}#${state.lang}", body)

    def test_the_footer_link_is_built_through_it(self):
        self.assertIn("pv.href = privacyHref();", APP)

    def test_the_static_href_is_still_usable_without_javascript(self):
        """The markup keeps a plain link, as the status link does, so a script that never
        ran still leaves a page a reader can reach."""
        self.assertIn('<div id="privacyLink"><a href="/tietosuoja/">', APP)


class ThePagesHalfTest(unittest.TestCase):
    def test_every_section_the_app_links_to_exists(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                self.assertRegex(PRIVACY, rf'<h[12] id="{lang}">')

    def test_the_three_links_out_have_ids_to_rewrite(self):
        for el in ("homeLink", "backLink", "footShowtimes", "footStatus"):
            with self.subTest(el=el):
                self.assertIn(f'id="{el}"', PRIVACY)

    def test_each_link_out_still_works_with_no_script(self):
        self.assertIn('<a class="logo" href="/" id="homeLink">', PRIVACY)
        self.assertIn('<a class="back" href="/" id="backLink">', PRIVACY)

    def test_the_language_precedence_is_the_apps(self):
        """Query, then the stored choice, then Finnish: the same order `startupLang()` and
        the status page use, and the same storage key."""
        self.assertIn("param.get('lang')", PRIVACY)
        self.assertIn("kino-prefs", PRIVACY)
        self.assertIn("LANGS.indexOf(stored) >= 0 ? stored : LANGS[0]", PRIVACY)

    def test_the_document_language_is_not_rewritten(self):
        """The page holds all three sections at once, so `<html lang>` describes the first
        one a reader without JavaScript lands on and the script leaves it alone."""
        self.assertIn('<html lang="fi">', PRIVACY)
        self.assertNotIn("documentElement.lang", PRIVACY)

    def test_each_translated_section_declares_its_language(self):
        """Assistive technology picks pronunciation from the nearest `lang`, and with only
        the root's `fi` the Swedish and English sections were marked Finnish (live audit,
        2026-10-10). Every piece of text from a section's heading to the next one sits under
        that section's language. In the Finnish section the two link labels naming the
        other languages carry their own."""
        from html.parser import HTMLParser

        class Langs(HTMLParser):
            VOID = {"br", "img", "meta", "link", "input", "hr", "wbr", "source"}

            def __init__(self):
                super().__init__()
                self.stack, self.section, self.text = [], None, []

            def handle_starttag(self, tag, attrs):
                a = dict(attrs)
                if tag in ("h1", "h2") and a.get("id") in LANGS:
                    self.section = a["id"]
                if tag == "footer":
                    self.section = None
                if tag not in self.VOID:
                    self.stack.append((tag, a.get("lang")))

            def handle_endtag(self, tag):
                for i in range(len(self.stack) - 1, -1, -1):
                    if self.stack[i][0] == tag:
                        del self.stack[i:]
                        break

            def handle_data(self, data):
                if self.section and data.strip():
                    lang = next((l for _, l in reversed(self.stack) if l), None)
                    self.text.append((self.section, data.strip(), lang))

        p = Langs()
        p.feed(PRIVACY)
        named = {"P\u00e5 svenska": "sv", "In English": "en"}
        for section in LANGS:
            pieces = [x for x in p.text if x[0] == section]
            self.assertGreater(len(pieces), 10, section)
            for _, text, lang in pieces:
                with self.subTest(section=section, text=text[:40]):
                    self.assertEqual(lang, named.get(text, section))

    def test_the_back_label_exists_in_all_three_languages(self):
        m = re.search(r"var BACK = \{(.*?)\};", PRIVACY, re.S)
        self.assertIsNotNone(m)
        for lang in LANGS:
            with self.subTest(lang=lang):
                self.assertIn(f"{lang}:", m.group(1))

    def test_the_page_is_covered_by_the_inline_js_check(self):
        import check_inline_js as chk
        self.assertIn("tietosuoja/index.html", chk.DEFAULT)


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class TheScriptRunsTest(unittest.TestCase):
    """The real script, against a stub DOM. Two languages and two areas, so no loop is
    entered once."""

    CASES = (
        ("?lang=en&area=engel-helsinki", "", "/?area=engel-helsinki&lang=en", "To showtimes"),
        ("?lang=sv&area=city%3AHelsinki", "", "/?area=city%3AHelsinki&lang=sv",
         "Till visningstiderna"),
        ("", "en", "/?lang=en", "To showtimes"),
        ("", "", "/?lang=fi", "Näytösaikoihin"),
        ("?lang=de", "sv", "/?lang=sv", "Till visningstiderna"),
    )

    @classmethod
    def setUpClass(cls):
        script = re.search(r"<script>\n(/\* The way back.*?)\n</script>", PRIVACY, re.S)
        if not script:
            raise AssertionError("the privacy page's script was not found")
        cls.src = script.group(1)

    def run_case(self, search, stored):
        driver = """
        const src = %s;
        const els = {};
        for (const id of ['homeLink','backLink','footShowtimes','footStatus'])
          els[id] = { href:'/', text:'', setAttribute(k,v){ this[k]=v; },
                      set textContent(t){ this.text = t; }, get textContent(){ return this.text; } };
        const sandbox = {
          location: { search: %s },
          document: { getElementById: id => els[id] || null },
          localStorage: { getItem: () => JSON.stringify({ lang: %s }) },
          URLSearchParams, JSON,
        };
        const vm = require('vm');
        vm.createContext(sandbox);
        vm.runInContext(src, sandbox, { filename: 'privacy' });
        process.stdout.write(JSON.stringify(
          Object.fromEntries(Object.entries(els).map(([k,v]) => [k, { href:v.href, text:v.text }]))));
        """ % (json.dumps(self.src), json.dumps(search), json.dumps(stored))
        out = subprocess.run(["node", "-e", driver], capture_output=True, text=True)
        if out.returncode != 0:
            raise AssertionError(f"driver failed: {out.stderr}")
        return json.loads(out.stdout)

    def test_every_link_out_carries_the_language_and_the_area(self):
        for search, stored, want, label in self.CASES:
            with self.subTest(search=search, stored=stored):
                got = self.run_case(search, stored)
                self.assertEqual(got["homeLink"]["href"], want)
                self.assertEqual(got["backLink"]["href"], want)
                self.assertEqual(got["footShowtimes"]["href"], want)
                self.assertEqual(got["footStatus"]["href"], "/status/" + want[1:])
                self.assertIn(label, got["backLink"]["text"])

    def test_nothing_it_writes_can_leave_this_origin(self):
        for search, stored, _, _ in self.CASES:
            with self.subTest(search=search):
                for el in self.run_case(search, stored).values():
                    self.assertTrue(el["href"].startswith("/"), el)
                    self.assertFalse(el["href"].startswith("//"), el)


if __name__ == "__main__":
    unittest.main()
