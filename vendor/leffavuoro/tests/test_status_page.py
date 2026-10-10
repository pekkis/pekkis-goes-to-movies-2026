"""The /status/ page as a file: no second health model, no leftover reference content.

status/index.html is a separate document with its own inline script, because there is no
build step and no module system to share one with index.html. The provider health model
moved here with the footer list it fed, so there is one healthState and the app has none;
the first two tests hold that line. STALE_H is still declared in both, because the app
still ages its own schedule banner on it, and that pair is read rather than copied.

The rest is what the handoff calls fictional content: the design reference shipped with
mock scenario controls, invented cinemas and its own timestamps, and none of that may
reach production.
"""
import pathlib
import re
import unittest

import _ctx


ROOT = _ctx.ROOT
STATUS = ROOT / "status" / "index.html"
APP = ROOT / "index.html"

H_START = "// --- healthState: pure, extracted verbatim by tests/health_state_harness.js ---"
H_END = "// --- end healthState ---"


def block(text, start, end):
    a, b = text.index(start), text.index(end)
    return [ln.strip() for ln in text[a:b].splitlines()]


class StatusPageFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.status = STATUS.read_text(encoding="utf-8")
        cls.app = APP.read_text(encoding="utf-8")

    # -- one health model, not two ---------------------------------------------------------

    def test_the_health_model_lives_here_and_only_here(self):
        """The app used to carry healthState for its footer list. That list is this page,
        so the model moved with it. Two copies is the drift this asserts away: the app
        keeping one would let the two answers diverge with both looking right alone."""
        self.assertIn(H_START, self.status)
        self.assertNotIn(H_START, self.app)
        self.assertNotIn("function healthState", self.app)

    def test_the_threshold_matches_the_app(self):
        want = re.search(r"const STALE_H = (\d+);", self.app)
        got = re.search(r"const STALE_H = (\d+);", self.status)
        self.assertIsNotNone(want, "index.html no longer declares STALE_H this way")
        self.assertIsNotNone(got, "status/index.html no longer declares STALE_H this way")
        self.assertEqual(want.group(1), got.group(1))

    def test_the_marker_blocks_the_harness_slices_are_all_present(self):
        for marker in ("// --- status time: pure, extracted verbatim by tests/status_harness.js ---",
                       "// --- end status time ---",
                       "// --- status model: pure, extracted verbatim by tests/status_harness.js ---",
                       "// --- end status model ---",
                       "// --- status store: pure, extracted verbatim by tests/status_store_harness.js ---",
                       "// --- end status store ---"):
            self.assertIn(marker, self.status)

    # -- nothing from the reference ----------------------------------------------------------

    def test_no_reference_controls_survived(self):
        """The handoff's scenario and theme selects, and the block previewing the app
        footer, are review aids. Shipping one would let a reader pick a fake state."""
        for leftover in ("reference-tools", "footer-preview", 'id="scenario"',
                         "Design reference", "omit from production",
                         "omit this block from the status page"):
            self.assertNotIn(leftover, self.status, leftover)

    def test_no_fictional_data_survived(self):
        """Invented cinemas, invented counts and the reference's own clock."""
        for leftover in ("Järvelän Kino", "BioRex Vaasan", "Kino Metso Tikkakosken",
                         "6 tietolähdettä", "klo 12.05", "klo 11.30", "klo 11.45",
                         "11 t sitten", "päivitetty 35 min sitten"):
            self.assertNotIn(leftover, self.status, leftover)

    def test_no_provider_host_is_hardcoded_anywhere(self):
        """Every row's link is built from the registry host in data/providers.json. A host
        written into this file would outlive a registry change and point somewhere the
        registry no longer names."""
        for host in ("cinemaorion.fi", "biorex.fi", "jarvelankino.fi", "ksek.fi",
                     "rivieracinemas.fi", "kinoaurora.fi", "finnkino.fi"):
            self.assertNotIn(host, self.status, host)

    def test_no_provider_name_is_written_into_the_markup_or_the_copy(self):
        """A name in the body or in a translation table would survive the provider being
        removed from the registry. Comments are exempt: the code has to be able to explain
        why Finnkino is read from areas.json instead of a venues file."""
        body = self.status.split("<script>")[0]
        copy = self.status[self.status.index("const L = {"):self.status.index("/* ---------- theme")]
        for name in ("Cinema Orion", "Finnkino", "BioRex", "Kino Metso", "Riviera"):
            self.assertNotIn(name, body, f"{name} in markup")
            self.assertNotIn(name, copy, f"{name} in copy")

    # -- the approved copy ---------------------------------------------------------------------

    def test_the_finnish_title_and_description_are_the_approved_ones(self):
        self.assertIn("Palvelun tila", self.status)
        self.assertIn("Näytösaikojen päivitykset ja tietojen ajantasaisuus.", self.status)

    def test_the_five_row_labels_are_present(self):
        for label in ("Ajan tasalla", "Päivitys viivästynyt", "Osa tiedoista päivittämättä",
                      "Ei julkaistua ohjelmistoa", "Tilaa ei voitu tarkistaa"):
            self.assertIn(label, self.status, label)

    def test_all_three_languages_have_a_copy_block(self):
        for lang in ("fi:", "sv:", "en:"):
            self.assertIn(f"    {lang} {{", self.status, lang)

    def test_help_and_contact_are_markup_rather_than_rendered_from_status_data(self):
        """They have to stay readable when every data request fails, so they cannot be
        built by the same code path that renders the rows."""
        for anchor in ('id="contact"', 'id="helpTitle"', 'id="srcDetails"',
                       "mailto:leffavuoro@gmail.com",
                       "https://github.com/Shady-Dev/kino"):
            self.assertIn(anchor, self.status, anchor)

    # -- reading, refreshing, linking ------------------------------------------------------------

    def test_every_data_request_is_same_origin(self):
        """The page reads this origin's published JSON and calls no cinema."""
        for m in re.finditer(r"readJson\('([^']+)'\)|readJson\(`([^`]+)`\)", self.status):
            path = m.group(1) or m.group(2)
            self.assertTrue(path.startswith("/data/"), path)

    def test_the_refresh_listener_only_answers_the_files_this_page_reads(self):
        """The list, Finnkino's areas.json, a provider's own file, and since 2026-09-26 the
        two combined venue files."""
        self.assertIn(r"/\/data\/(providers|areas|venues-[^/]+|venuelists-[^/]+)\.json$/",
                      self.status)

    def test_the_worker_message_path_and_the_network_path_stay_separate(self):
        """Structural only. What the message path actually does is counted in
        tests/test_status_store.py, because the version of this that read the source text
        passed while the code underneath it looped: the code was legible and the comment
        above it asserted the opposite of what it did."""
        self.assertIn("statusStore.fresh(p)", self.status)
        self.assertIn("document.visibilityState === 'visible') statusStore.load()", self.status)
        a = self.status.index("// --- status store: pure, extracted verbatim")
        b = self.status.index("// --- end status store ---")
        block = self.status[a:b]
        self.assertIn("io.cache(path)", block)
        self.assertIn("io.net(", block)

    def test_a_worker_refresh_does_not_restamp_the_check_time(self):
        """`checkedAt` is when this page last asked the network. The worker refreshing a
        file behind the page is not this page asking, and stamping it would report a check
        that never happened."""
        a = self.status.index("function fresh(path)")
        b = self.status.index("return { load, fresh, state:")
        self.assertNotIn("checkedAt =", self.status[a:b])

    def test_the_saved_favourite_is_read_but_never_written(self):
        """Arriving from a cinema and going back must not promote it to the favourite."""
        self.assertNotIn("prefs.set({ area", self.status)
        self.assertIn("prefs.set({ lang })", self.status)

    def test_the_page_keeps_the_apps_preference_keys(self):
        for key in ("kino-theme", "kino-prefs"):
            self.assertIn(key, self.status, key)

    def test_ticket_and_site_links_go_through_a_scheme_guard(self):
        self.assertIn("const safeUrl", self.status)
        self.assertIn("safeUrl(r.site || 'https://' + r.host", self.status)

    def test_the_control_character_class_is_written_as_escapes(self):
        """A literal control byte in the class silently changes the range, and a NUL in
        the file is not visible in review. This landed once already."""
        self.assertIn("/[\\u0000-\\u001F\\u007F]/", self.status,
                      "the control-character class is not written as escapes")
        self.assertIsNone(re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", self.status),
                          "raw control byte in status/index.html")


class StatusPageWiringTest(unittest.TestCase):
    """The page has to be reachable by the checks that would catch a break in it."""

    def test_the_inline_js_checker_covers_the_page_by_default(self):
        text = (ROOT / "scripts" / "check_inline_js.py").read_text(encoding="utf-8")
        m = re.search(r"DEFAULT = \[(.*?)\]", text, re.S)
        self.assertIsNotNone(m)
        self.assertIn("status/index.html", m.group(1))

    def test_the_checks_workflow_runs_on_changes_to_the_page(self):
        wf = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("'status/**'", wf)

    def test_the_service_worker_version_moved_with_the_client_change(self):
        """The footer moved in index.html, so the cached copy has to be dropped."""
        sw = (ROOT / "sw.js").read_text(encoding="utf-8")
        m = re.search(r"const CACHE = 'leffavuoro-v(\d+)';", sw)
        self.assertIsNotNone(m)
        self.assertGreaterEqual(int(m.group(1)), 122)


if __name__ == "__main__":
    unittest.main()
