#!/usr/bin/env python3
"""
Unit Tests for SFX/BGM Library Modernization & Renderer Timing Fixes.
Verifies:
1. Manifest renderer applies `-ss` section seek to music cues.
2. Manifest renderer does not double-subtract pre-roll for foley cues.
3. Agent director music budget is synchronized to 40%.
4. Sound bank resolves Witcher signs (Igni, Aard, Quen, Axii, Yrden).
5. Sound bank resolves monsters (Striga, Ghoul, Wolf) and combat foley.
6. Sound bank resolves fantasy ambiences (Crypt, Castle Hall, Bog Swamp, Blizzard).
7. Harmonized DSP metrics (LUFS, True Peak) are exposed via SoundBank.
8. Music catalog search eliminates duplicate rows via track ID grouping.
"""

import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from audiobook_factory.contracts import (
    MusicCue,
    FoleyCue,
)
from audiobook_factory.sound_bank import SoundBank, get_sound_bank
from audiobook_factory.manifest_renderer import render_music_bus, render_foley_bus


class TestManifestRendererUpgrades(unittest.TestCase):
    """Test renderer timing, section seeking, and pre-roll fixes."""

    @patch("subprocess.run")
    def test_render_music_bus_uses_section_start_sec_seek(self, mock_run):
        """Verify that render_music_bus passes -ss <start_offset_sec> before -i."""
        mock_run.return_value = MagicMock(returncode=0)

        # Create dummy track file
        dummy_track = Path("audiobooks/sound_bank/music/dummy_track.mp3")
        dummy_track.parent.mkdir(parents=True, exist_ok=True)
        dummy_track.touch(exist_ok=True)

        mock_bank = MagicMock(spec=SoundBank)
        mock_bank.resolve_sound.return_value = dummy_track
        mock_bank.resolve_asset_path.return_value = dummy_track

        cue = MusicCue(
            cue_id="mc_001",
            cue_type="CLIMACTIC_ACTION_CUE",
            track_name=str(dummy_track),
            section_name="CLIMAX_DROP",
            section_start_sec=45.5,  # Seek to 45.5s
            start_ms=5000,
            duration_ms=15000,
        )

        out_wav = Path("audiobooks/sound_bank/cache/test_music_bus.wav")
        try:
            render_music_bus(
                music_cues=[cue],
                total_duration_sec=60.0,
                output_bus_file=out_wav,
                sound_bank=mock_bank,
                ffmpeg="ffmpeg",
            )
            self.assertTrue(mock_run.called)
            cmd_args = mock_run.call_args_list[0][0][0]

            # Verify -ss 45.50 precedes -i dummy_track
            self.assertIn("-ss", cmd_args)
            ss_idx = cmd_args.index("-ss")
            self.assertEqual(cmd_args[ss_idx + 1], "45.50")
            i_idx = cmd_args.index("-i", ss_idx)
            self.assertGreater(i_idx, ss_idx)
        finally:
            if dummy_track.exists() and dummy_track.stat().st_size == 0:
                dummy_track.unlink(missing_ok=True)
            if out_wav.exists():
                out_wav.unlink(missing_ok=True)

    @patch("subprocess.run")
    def test_render_foley_bus_no_double_pre_roll(self, mock_run):
        """Verify that render_foley_bus delays by cue.start_ms without double-subtracting pre-roll."""
        mock_run.return_value = MagicMock(returncode=0)

        dummy_sfx = Path("audiobooks/sound_bank/foley/dummy_sfx.wav")
        dummy_sfx.parent.mkdir(parents=True, exist_ok=True)
        dummy_sfx.touch(exist_ok=True)

        mock_bank = MagicMock(spec=SoundBank)
        mock_bank.resolve_asset_path.return_value = dummy_sfx
        mock_bank.resolve_sound.return_value = dummy_sfx

        cue = FoleyCue(
            cue_id="fc_001",
            segment_index=0,
            anchor_word="strike",
            asset_path=str(dummy_sfx),
            start_ms=1200,
            pre_roll_ms=80,  # Should NOT be subtracted again
        )

        out_wav = Path("audiobooks/sound_bank/cache/test_foley_bus.wav")
        try:
            render_foley_bus(
                foley_cues=[cue],
                total_duration_sec=30.0,
                output_bus_file=out_wav,
                sound_bank=mock_bank,
                ffmpeg="ffmpeg",
            )
            self.assertTrue(mock_run.called)
            # Find the FFmpeg call that generates the mix
            found_adelay = False
            for call in mock_run.call_args_list:
                args = call[0][0]
                if "-filter_complex" in args:
                    fc_idx = args.index("-filter_complex")
                    filter_str = args[fc_idx + 1]
                    if "adelay=1200|1200" in filter_str:
                        found_adelay = True
                    self.assertNotIn("adelay=1120|1120", filter_str)
            self.assertTrue(found_adelay, "Did not find expected adelay=1200|1200 in filter_complex")
        finally:
            if dummy_sfx.exists() and dummy_sfx.stat().st_size == 0:
                dummy_sfx.unlink(missing_ok=True)
            if out_wav.exists():
                out_wav.unlink(missing_ok=True)


class TestAgentDirectorUpgrades(unittest.TestCase):
    """Test director budget synchronization."""

    def test_music_budget_percentage_is_40_percent(self):
        """Verify that agent_director enforces 40% music budget."""
        from audiobook_factory.agent_director import AgentDirector
        import inspect

        source = inspect.getsource(AgentDirector._pass2_music_director)
        self.assertIn("0.40", source)
        self.assertNotIn("0.35", source)


class TestSoundBankFantasyHydration(unittest.TestCase):
    """Test that all newly added fantasy sound assets resolve to valid on-disk files."""

    def setUp(self):
        self.bank = get_sound_bank()

    def test_resolve_witcher_signs(self):
        """Verify Witcher signs resolve via FTS5."""
        signs = ["igni", "aard", "quen", "axii", "yrden"]
        for sign in signs:
            resolved = self.bank.resolve_sound(sign)
            self.assertIsNotNone(resolved, f"Witcher sign '{sign}' failed to resolve.")
            self.assertTrue(resolved.exists(), f"File for '{sign}' ({resolved}) does not exist on disk.")

    def test_resolve_monsters_and_combat(self):
        """Verify monsters and combat foley resolve via FTS5."""
        cues = [
            ("striga", None),
            ("ghoul", None),
            ("wolf", "SFX"),
            ("sword draw", None),
            ("sword clash", None),
            ("body thud", None),
            ("armor clank", None)
        ]
        for cue, cat in cues:
            resolved = self.bank.resolve_sound(cue, category=cat)
            self.assertIsNotNone(resolved, f"Cue '{cue}' failed to resolve.")
            self.assertTrue(resolved.exists(), f"File for '{cue}' ({resolved}) does not exist on disk.")

    def test_resolve_fantasy_ambiences(self):
        """Verify fantasy environmental ambiences resolve via FTS5."""
        ambs = [
            ("crypt", "AMB"),
            ("castle hall", None),
            ("bog swamp", None),
            ("blizzard", None)
        ]
        for amb, cat in ambs:
            resolved = self.bank.resolve_sound(amb, category=cat)
            self.assertIsNotNone(resolved, f"Ambience '{amb}' failed to resolve.")
            self.assertTrue(resolved.exists(), f"File for '{amb}' ({resolved}) does not exist on disk.")


class TestSoundBankHarmonizationAndDSP(unittest.TestCase):
    """Test schema harmonization and DSP metric querying."""

    def setUp(self):
        self.bank = get_sound_bank()

    def test_search_results_include_dsp_metrics_fields(self):
        """Verify FTS search returns integrated_lufs and true_peak_db fields."""
        results = self.bank.search("igni", limit=1)
        self.assertGreater(len(results), 0, "Search for 'igni' returned no results.")
        res = results[0]
        self.assertIn("integrated_lufs", res)
        self.assertIn("true_peak_db", res)
        self.assertIn("spectral_centroid_hz", res)

    def test_get_asset_metrics(self):
        """Verify get_asset_metrics retrieves valid acoustic data."""
        metrics = self.bank.get_asset_metrics("igni")
        self.assertIsNotNone(metrics, "Failed to get asset metrics for 'igni'")
        self.assertIn("integrated_lufs", metrics)
        self.assertIn("true_peak_db", metrics)
        self.assertIn("sample_rate", metrics)
        self.assertEqual(metrics["sample_rate"], 48000)

    def test_music_catalog_no_duplicate_rows(self):
        """Verify search_music_catalog groups by track ID to avoid duplicates."""
        results = self.bank.search_music_catalog("the", limit=10)
        track_ids = [r["id"] for r in results]
        self.assertEqual(len(track_ids), len(set(track_ids)), "Duplicate tracks found in search_music_catalog!")


if __name__ == "__main__":
    unittest.main()
