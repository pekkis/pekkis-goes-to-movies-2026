"""Gilda's screening language: `audio_lang`, `subtitle_lang`, and the audio style that can
say a screening has no subtitles."""
import unittest

import _ctx                                                # noqa: F401
import gilda


def lang(audio, subs, style):
    return gilda._lang({"audio_lang": audio, "subtitle_lang": subs,
                        "movie_audio_style_name": style})


class NoSubtitlesTest(unittest.TestCase):
    """Read 2026-10-04: Mandy and Rammstein - Live in Mexico City carry "Ei tekstitystä"
    with subtitles "-"; The Lighthouse carries the same style beside "suomi, ruotsi"."""

    def test_the_style_with_no_subtitle_language_is_xx(self):
        self.assertEqual(lang("EN", "-", "Ei tekstityst\u00e4"), "EN-A, XX-S")
        self.assertEqual(lang("MULTI", "-", "Ei tekstityst\u00e4"), "XX-S")

    def test_named_subtitles_win_over_the_style(self):
        self.assertEqual(lang("EN", "suomi, ruotsi", "Ei tekstityst\u00e4"), "EN-A, FI-S, SV-S")

    def test_no_style_or_another_style_states_nothing(self):
        self.assertEqual(lang("EN", "-", "Tekstitetty"), "EN-A")
        self.assertEqual(lang("EN", "-", ""), "EN-A")
        self.assertEqual(lang("FI", "-", "Dubattu"), "FI-A")


if __name__ == "__main__":
    unittest.main()
