"""`common.syn_language`: which language a synopsis is in, and when it refuses to say.

The slot in films-extra.json is keyed by normalised title and read by every chain showing
the film, so a misfiled text is served under the wrong language everywhere. A refusal costs
a reader one paragraph, which is why the thresholds are set to refuse rather than guess.

The texts are the shapes that break a naive detector: a Finnish blurb quoting an English
title, an English blurb quoting Finnish names, and a line of proper nouns with no function
word at all.
"""
import unittest

import _ctx                                                # noqa: F401
import common
import synmerge


FI = ("Klaus Härön draama kertoo kahden naisen kohtaamisesta keskellä hoitoalan kriisiä, "
      "kun sairaanhoitajat uhkaavat lakolla ja hän joutuu venymään.")
SV = ("Filmen handlar om en ung kvinna som inte vet att hennes far är tillbaka, och det "
      "som händer efter att hon möter honom.")
EN = ("A grieving boy seeks God to meet his departed mother, and in finding the divine, "
      "learns to serve humanity with miracles of love and food.")
FI_WITH_ENGLISH_TITLE = ("Elokuva The Salt Path kertoo pariskunnasta, joka lähtee "
                         "vaeltamaan Englannin rannikolle, ja siitä mitä matkalla "
                         "tapahtuu heille.")
EN_WITH_FINNISH_NAMES = ("The film follows Klaus Härö and Laura Birn in a hospital that "
                         "is running out of time, and the choices they are left with.")
NO_FUNCTION_WORDS = ("Hanuman Ansh 2026. Mumbai, Chennai, Kolkata, Delhi, Pune, Jaipur, "
                     "Lucknow, Kanpur, Nagpur, Indore, Bhopal, Patna, Surat, Kochi.")
# Finnish that uses none of the marker words. Read on biomarilyn.com 2026-09-18.
FI_BY_ENDINGS = ("Kilpa-auto Salama McQueen on matkalla Kaliforniaan ottamaan osaa "
                 "suureen Piston Cup -kisaan. Se eksyy valtatie 66:n varrella olevaan "
                 "uinuvaan Syylari Cityyn.")


class SynLanguageTest(unittest.TestCase):
    def test_the_three_languages_are_placed(self):
        for text, want in ((FI, "fi"), (SV, "sv"), (EN, "en")):
            with self.subTest(want=want):
                self.assertEqual(common.syn_language(text), want)

    def test_a_quoted_title_or_name_does_not_move_the_verdict(self):
        self.assertEqual(common.syn_language(FI_WITH_ENGLISH_TITLE), "fi")
        self.assertEqual(common.syn_language(EN_WITH_FINNISH_NAMES), "en")

    def test_too_little_evidence_is_refused(self):
        for text in ("", None, "Hetki ennen valoa", NO_FUNCTION_WORDS):
            with self.subTest(text=(text or "")[:20]):
                self.assertEqual(common.syn_language(text), "")

    def test_an_even_mix_is_refused_and_a_dominant_one_wins(self):
        """Half and half settles nothing. A text that is mostly one language is filed
        under it, which is what `margin` is for."""
        self.assertEqual(common.syn_language("Ja kun hän the and of"), "")
        self.assertEqual(common.syn_language(EN + " Ja kun."), "en")

    def test_finnish_case_endings_carry_a_text_with_no_marker_word(self):
        """Three quarters of one cinema's blurbs were refused on markers alone."""
        self.assertEqual(common.syn_language(FI_BY_ENDINGS), "fi")

    def test_a_short_word_with_the_same_ending_does_not_count(self):
        """vista, pasta and villa end like a Finnish case and are not evidence of one."""
        self.assertEqual(common.syn_language("Vista pasta villa. Vista pasta villa."), "")

    def test_one_or_two_endings_are_not_enough(self):
        self.assertEqual(common.syn_language("Kaliforniaan. Kunnioittamaan."), "")

    def test_one_swedish_or_english_marker_closes_the_endings_route(self):
        """The fallback is for a text with no function word of either, which no real
        sentence in them is."""
        self.assertEqual(common.syn_language(FI_BY_ENDINGS + " and"), "")
        self.assertEqual(common.syn_language(FI_BY_ENDINGS + " och"), "")

    def test_the_thresholds_are_the_caller_s_to_set(self):
        self.assertEqual(common.syn_language("Ei ja tai", least=3, margin=2), "fi")
        self.assertEqual(common.syn_language("Ei ja tai", least=4, margin=2), "")

    def test_it_names_only_a_language_the_client_offers(self):
        self.assertEqual(set(common.SYN_LANGS), set(synmerge.LANGS))
        for text in (FI, SV, EN, "", NO_FUNCTION_WORDS):
            self.assertIn(common.syn_language(text), ("",) + common.SYN_LANGS)

    def test_the_marker_lists_share_no_word(self):
        """A word in two lists scores both and cancels itself out of the margin."""
        seen = {}
        for lang, words in common.SYN_MARKERS.items():
            for w in words:
                self.assertNotIn(w, seen, f"{w!r} is in {lang} and {seen.get(w)}")
                seen[w] = lang


if __name__ == "__main__":
    unittest.main()
