"""The stale banner says which cinema is late and offers one way to check it (2026-09-20).

Finnkino showed an eight-hour warning during a review and the banner explained the problem
with no way to act on it. Two faults behind that: the text came from a single `generated`,
the oldest part of a combined city, so a second late provider in the same city was never
named; and there was no link, so a reader had nowhere to go but back to the cinema by
memory.

`staleNotice` decides it, from the per-provider timestamps the city fold now returns. One
late provider gets its own site, from the host the registry publishes through
providers.json -- the site root, never a constructed programme path, which is what left
six Nexxo ticket links dead. Two or more get the status page: neither is "the" affected
cinema. A part with no timestamp is never called late.

Sliced verbatim out of index.html by tests/stale_notice_harness.js.
"""
import json
import pathlib
import re
import shutil
import subprocess
import unittest

import _ctx


HARNESS = pathlib.Path(__file__).resolve().parent / "stale_notice_harness.js"
HTML = (_ctx.ROOT / "index.html").read_text(encoding="utf-8")


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class StaleNoticeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                             cwd=str(_ctx.ROOT), timeout=60)
        if out.returncode:
            raise AssertionError(f"harness failed: {out.stderr}")
        cls.r = json.loads(out.stdout)

    def test_no_case_threw(self):
        threw = {k: v for k, v in self.r.items() if isinstance(v, dict) and "threw" in v}
        self.assertEqual(threw, {})

    def test_nothing_is_claimed_when_everything_is_inside_the_window(self):
        for key in ("none_late", "empty_list", "null_list", "undefined_list",
                    "all_unknown", "exactly_at_threshold"):
            with self.subTest(key):
                self.assertIsNone(self.r[key])

    def test_the_threshold_is_strict(self):
        """Exactly STALE_H old is not late; just over it is."""
        self.assertIsNone(self.r["exactly_at_threshold"])
        self.assertIsNotNone(self.r["just_over_threshold"])

    def test_one_late_provider_can_be_sent_to_its_own_site(self):
        for key in ("one_source_late", "one_late_of_three"):
            with self.subTest(key):
                self.assertEqual(self.r[key]["providers"], ["finnkino"])
                self.assertEqual(self.r[key]["only"], "finnkino")
                self.assertEqual(self.r[key]["ageH"], 9)

    def test_a_combined_city_names_every_late_provider(self):
        """Naming only the oldest read as a claim that the rest were current."""
        self.assertEqual(sorted(self.r["two_late"]["providers"]), ["biorex", "finnkino"])
        self.assertEqual(self.r["two_late_order"]["providers"], ["biorex", "finnkino"],
                         "oldest first")

    def test_two_late_providers_offer_no_single_cinema(self):
        for key in ("two_late", "two_late_order"):
            with self.subTest(key):
                self.assertEqual(self.r[key]["only"], "",
                                 "with two, the status page is the honest destination")

    def test_the_age_reported_is_the_oldest(self):
        self.assertEqual(self.r["two_late"]["ageH"], 12)

    def test_a_part_with_no_timestamp_is_never_called_late(self):
        for key in ("missing_generated", "absent_generated",
                    "unparseable_date", "null_member"):
            with self.subTest(key):
                self.assertEqual(self.r[key]["providers"], ["biorex"],
                                 "only the part that actually has an old timestamp")
                self.assertEqual(self.r[key]["only"], "biorex")

    def test_a_blank_provider_id_still_reports(self):
        self.assertEqual(self.r["blank_provider"]["providers"], [""])

    # -- updateState: the warning waits for the worker's check ----------------------

    def test_data_inside_the_window_shows_nothing_while_checking(self):
        for key in ("u_not_late", "u_not_late_while_checking"):
            with self.subTest(key):
                self.assertEqual(self.r[key]["kind"], "none")

    def test_late_data_with_every_check_answered_is_the_warning(self):
        """A failed or offline check is an answer: the worker has nothing newer."""
        self.assertEqual(self.r["u_late_answered"], {"kind": "stale", "waitMs": 0})

    def test_late_data_behind_a_slow_check_reads_as_checking_until_the_cap(self):
        self.assertEqual(self.r["u_late_checking"], {"kind": "checking", "waitMs": 7000})
        self.assertEqual(self.r["u_late_just_under_cap"], {"kind": "checking", "waitMs": 1})

    def test_the_cap_turns_a_check_that_never_answers_into_the_warning(self):
        """An older worker posts no `checked`, and a stalled fetch never answers: past
        8 s the page stops waiting and says what it holds."""
        for key in ("u_late_at_cap", "u_late_past_cap"):
            with self.subTest(key):
                self.assertEqual(self.r[key], {"kind": "stale", "waitMs": 0})

    def test_a_city_waits_on_its_oldest_outstanding_member(self):
        self.assertEqual(self.r["u_city_oldest_sets_cap"], {"kind": "checking", "waitMs": 2000})
        self.assertEqual(self.r["u_city_one_answered"], {"kind": "checking", "waitMs": 7000})

    def test_a_check_for_the_cinema_left_behind_holds_nothing_here(self):
        self.assertEqual(self.r["u_other_cinema_pending"], {"kind": "stale", "waitMs": 0})


class StaleBannerWiringTest(unittest.TestCase):
    """What the banner does with that decision, read off the source."""

    def test_the_fold_returns_a_timestamp_per_provider(self):
        self.assertIn("const sources = [...srcAge].map(([provider, generated]) "
                      "=> ({ provider, generated }));", HTML)
        self.assertIn("sources,", HTML)

    def test_a_single_venue_synthesises_its_own_source(self):
        self.assertIn("state.sources = Array.isArray(cache.sources) ? cache.sources", HTML)

    def test_the_link_is_the_registry_host_and_never_a_built_path(self):
        self.assertIn("safeUrl(site || 'https://' + host + '/')", HTML)
        self.assertNotRegex(HTML, r"'https://' \+ host \+ '/\w")

    def test_the_fallback_is_the_status_page_with_the_selection(self):
        self.assertIn("function statusHref()", HTML)
        self.assertIn("esc(statusHref())", HTML)
        self.assertEqual(len(re.findall(r"`/status/\$\{qs \? '\?' \+ qs : ''\}`", HTML)), 1,
                         "one builder, shared by the footer link and the banner")

    def test_the_action_never_tells_anyone_to_reload(self):
        """A refresh re-reads this origin's files and starts no collection at a cinema."""
        for lang, label in (("fi", "Tarkista ohjelmisto: {host}"),
                            ("sv", "Kontrollera programmet: {host}"),
                            ("en", "Check the programme: {host}")):
            with self.subTest(lang):
                self.assertIn(f"staleSite:'{label}'", HTML)
        for bad in ("Lataa sivu uudelleen", "Reload", "Uppdatera sidan", "Refresh the page"):
            self.assertNotIn(f"staleSite:'{bad}", HTML)

    def test_all_three_interface_languages_have_both_labels(self):
        self.assertEqual(len(re.findall(r"staleSite:'", HTML)), 3)
        self.assertEqual(len(re.findall(r"staleStatus:'", HTML)), 3)
        self.assertEqual(len(re.findall(r"checking:'", HTML)), 3)

    def test_the_checking_state_is_capped_at_the_fetch_timeout(self):
        """The harness's 8 s is the page's FETCH_MS: a check is given as long as the page
        gives its own fetch before it gives up."""
        self.assertIn("const FETCH_MS = 8000;", HTML)
        self.assertRegex(HTML, r"updateState\(!!notice, [^;]*checking,\s*Date\.now\(\), FETCH_MS\)")

    def test_the_action_is_a_real_link_and_focusable(self):
        """A keyboard reaches an <a href>; a click handler on a span it does not."""
        self.assertIn('<a class="staleact" href=', HTML)
        self.assertIn(".staleact:focus-visible{outline:2px solid var(--accent)", HTML)

    def test_the_action_reaches_the_tap_floor(self):
        floor = re.search(r"tap\.floor\s*=\s*(\d+)px",
                          (_ctx.ROOT / "DESIGN.md").read_text(encoding="utf-8")).group(1)
        rule = re.search(r"\.staleact\{(.*?)\}", HTML, re.S).group(1)
        self.assertIn(f"min-height:{floor}px", rule.replace(" ", ""))


if __name__ == "__main__":
    unittest.main()
