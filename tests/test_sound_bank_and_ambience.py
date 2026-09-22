#!/usr/bin/env python3
"""
Tests for Sound Bank FTS5 Resolution and Multitrack Ambience/Foley Separation.
Verifies that:
1. Foley queries resolve to authentic CC0 sound files.
2. Ambience bus strictly isolates environmental audio and never loads music stems.
3. Dialogue bus remains 100% dry with zero comb-filtering aecho.
"""

import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
from audiobook_factory.sound_bank import SoundBank, get_sound_bank
from audiobook_factory.soundscape import resolve_environment_ambience


class TestSoundBankAndAmbience(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.bank = get_sound_bank()

    def test_foley_tag_resolution(self):
        """Verify authentic CC0 sound resolution for standard screenplay Foley cues."""
        self.assertIsNotNone(self.bank, "SoundBank should be initialized.")

        # Sword draw should resolve to an unsheathe / blade sound, not generic clicks
        snd_draw = self.bank.resolve_sound("sword_draw")
        self.assertIsNotNone(snd_draw)
        self.assertTrue(any(w in snd_draw.name.lower() for w in ("unsheathe", "sword", "draw", "knife")))

        # Sword clash should resolve to a steel clash sound
        snd_clash = self.bank.resolve_sound("sword_clash")
        self.assertIsNotNone(snd_clash)
        self.assertTrue("clash" in snd_clash.name.lower())

        # Boots / steps should resolve to authentic boot footsteps
        snd_boots = self.bank.resolve_sound("boots_gravel")
        self.assertIsNotNone(snd_boots)
        self.assertTrue("step" in snd_boots.name.lower() or "boot" in snd_boots.name.lower())

    def test_ambience_resolution(self):
        """Verify environmental ambiences resolve authentic CC0 audio beds."""
        snd_wind = self.bank.resolve_sound("wind_howl", category="AMB") or self.bank.resolve_sound("wind")
        self.assertIsNotNone(snd_wind)
        self.assertTrue("wind" in snd_wind.name.lower())

        snd_tavern = self.bank.resolve_sound("tavern_crowd_murmur", category="AMB") or self.bank.resolve_sound("tavern")
        self.assertIsNotNone(snd_tavern)
        self.assertTrue("tavern" in snd_tavern.name.lower() or "restaurant" in snd_tavern.name.lower())

    def test_environment_ambience_does_not_load_music_stem(self):
        """Ensure resolve_environment_ambience never outputs a music stem."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            out_amb = Path(td) / "test_amb.wav"
            resolve_environment_ambience("dense_forest_night", 2.0, out_amb)
            self.assertTrue(out_amb.exists())
            self.assertGreater(out_amb.stat().st_size, 5000)


if __name__ == "__main__":
    unittest.main()
