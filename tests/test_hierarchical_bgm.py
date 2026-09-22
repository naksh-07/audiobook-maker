import os
import wave
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from audiobook_factory.sound_bank import SoundBank
from audiobook_factory.soundscape import normalize_to_3level_soundscape, render_hierarchical_soundscape, get_audio_duration
from audiobook_factory.timeline_ledger import build_chapter_timeline_ledger


class TestHierarchicalBGM(unittest.TestCase):
    """Unit and integration test suite for 3-Level Dynamic BGM Architecture."""

    @classmethod
    def setUpClass(cls):
        cls.bank = SoundBank()

    def test_01_fts_search_coverage(self):
        """Verify SQLite FTS5 queries resolve across all 3 levels (Leitmotifs, Chapter Beds, Stems, Stingers)."""
        self.assertTrue(len(self.bank.search("geralt_destiny")) > 0)
        self.assertTrue(len(self.bank.search("gothic_manor")) > 0)
        self.assertTrue(len(self.bank.search("tension_pulse")) > 0)
        self.assertTrue(len(self.bank.search("revelation_sting")) > 0)

    def test_02_sound_bank_hierarchical_resolvers(self):
        """Verify specialized SoundBank resolvers return valid audio paths."""
        lm = self.bank.resolve_leitmotif("geralt_destiny")
        self.assertIsNotNone(lm, "Leitmotif 'geralt_destiny' should resolve")
        self.assertTrue(lm.exists())

        bed = self.bank.resolve_chapter_bed("gothic_manor")
        self.assertIsNotNone(bed, "Chapter Bed 'gothic_manor' should resolve")
        self.assertTrue(bed.exists())

        stem = self.bank.resolve_dynamic_stem("tension_pulse")
        self.assertIsNotNone(stem, "Dynamic Stem 'tension_pulse' should resolve")
        self.assertTrue(stem.exists())

        stinger = self.bank.resolve_stinger("revelation_sting")
        self.assertIsNotNone(stinger, "Stinger 'revelation_sting' should resolve")
        self.assertTrue(stinger.exists())

    def test_03_normalize_to_3level_soundscape(self):
        """Verify legacy 2-tier plans cleanly upgrade to 3-level schema."""
        legacy_plan = {
            "primary_mood": "tense",
            "scenes": [
                {
                    "scene_id": 1,
                    "segment_start": 1,
                    "segment_end": 5,
                    "location": {"environment_type": "stone_crypt"},
                    "emotional_arc": {"intensity": 8, "music_mood": "tense"}
                },
                {
                    "scene_id": 2,
                    "segment_start": 6,
                    "segment_end": 10,
                    "location": {"environment_type": "dense_forest_night"},
                    "emotional_arc": {"intensity": 4, "music_mood": "mysterious"}
                }
            ]
        }

        norm = normalize_to_3level_soundscape(legacy_plan, chapter_num=2)
        self.assertIn("level1_leitmotifs", norm)
        self.assertIn("level2_chapter_bed", norm)
        self.assertIn("level3_scenes", norm)
        self.assertEqual(norm["level2_chapter_bed"]["setting"], "stone_crypt")
        self.assertEqual(norm["level3_scenes"][0]["emotional_arc"]["dynamic_stems"], ["combat_drums"])
        self.assertEqual(norm["level3_scenes"][1]["emotional_arc"]["dynamic_stems"], [])

    def test_04_timeline_ledger_3level_tracking(self):
        """Verify timeline ledger includes hierarchical_score metadata."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            # Create a 1.0s dummy wav
            dummy_wav = tmp_path / "chunk1.wav"
            with wave.open(str(dummy_wav), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(b"\x00\x00" * 24000)

            segments = [
                {"index": 1, "speaker": "Geralt", "type": "dialogue", "text": "Something ends, something begins."}
            ]
            plan = {
                "primary_mood": "tense",
                "level1_leitmotifs": [
                    {"theme": "geralt_destiny", "trigger_segment": 1, "timing": "under", "volume": 0.22}
                ],
                "level2_chapter_bed": {
                    "setting": "dark_forest",
                    "base_volume": 0.16
                },
                "scenes": [
                    {"scene_id": 1, "segment_start": 1, "segment_end": 1, "emotional_arc": {"music_mood": "tense"}}
                ]
            }

            ledger_file = tmp_path / "ledger.json"
            ledger = build_chapter_timeline_ledger(
                chapter_id=4,
                script_segments=segments,
                audio_chunk_paths=[dummy_wav],
                soundscape_plan=plan,
                output_ledger_file=ledger_file
            )

            self.assertIn("hierarchical_score", ledger)
            self.assertEqual(ledger["hierarchical_score"]["level1_leitmotifs"][0]["theme"], "geralt_destiny")
            self.assertEqual(ledger["hierarchical_score"]["level2_chapter_bed"]["setting"], "dark_forest")
            self.assertTrue(ledger_file.exists())

    def test_05_render_hierarchical_soundscape_execution(self):
        """Verify render_hierarchical_soundscape renders multi-level music bus cleanly."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            out_bgm = tmp_path / "composite_bgm.wav"

            plan = {
                "primary_mood": "tense",
                "level1_leitmotifs": [
                    {"theme": "geralt_destiny", "trigger_segment": 1, "timing": "under", "volume": 0.20}
                ],
                "level2_chapter_bed": {
                    "setting": "gothic_manor",
                    "stem": "tense_dark_fog",
                    "base_volume": 0.15
                },
                "scenes": [
                    {
                        "scene_id": 1,
                        "segment_start": 1,
                        "segment_end": 2,
                        "emotional_arc": {
                            "music_mood": "tense",
                            "dynamic_stems": ["tension_pulse"],
                            "stingers": [{"segment": 1, "cue": "revelation_sting", "volume": 0.30}]
                        }
                    }
                ]
            }

            seg_durs = {1: 2.0, 2: 2.0}
            render_hierarchical_soundscape(
                soundscape_plan=plan,
                total_duration=4.5,
                output_audio_file=out_bgm,
                segment_durations=seg_durs,
                pause_ms=300
            )

            self.assertTrue(out_bgm.exists(), "Composite BGM file must be generated")
            self.assertGreater(out_bgm.stat().st_size, 5000, "BGM file must have valid audio data")
            dur = get_audio_duration(out_bgm)
            self.assertGreaterEqual(dur, 4.0, "Rendered BGM duration should match requested duration")

    def test_06_track_sections_seeding(self):
        """Verify sound_track_sections table exists and has indexed sections."""
        stats = self.bank.stats()
        self.assertIn("total_sections", stats)
        self.assertGreaterEqual(stats["total_sections"], 500, "Should have at least 500 track sections indexed")

    def test_07_resolve_track_sections_landmarks(self):
        """Verify landmark section resolution for flagship and general tracks."""
        # Flagship White Wolf Climax Drop
        ww_climax = self.bank.resolve_track_section("001 The White Wolf", section_type="CLIMAX_DROP")
        self.assertIsNotNone(ww_climax)
        self.assertEqual(ww_climax["section_name"], "CLIMAX_DROP")
        self.assertGreater(ww_climax["start_sec"], 0)
        self.assertGreater(ww_climax["end_sec"], ww_climax["start_sec"])
        self.assertGreaterEqual(ww_climax["energy_level"], 8)

        # Flagship Blade of Silver Climax
        blade_climax = self.bank.resolve_track_section("047 A Blade of Silver", section_type="CLIMAX_DROP")
        self.assertIsNotNone(blade_climax)
        self.assertEqual(blade_climax["section_name"], "CLIMAX_DROP")
        self.assertGreaterEqual(blade_climax["energy_level"], 8)

        # Hanged Man's Tree Intro Bed
        hmt_intro = self.bank.resolve_track_section("021 Hanged Man's Tree", section_type="INTRO_BED")
        self.assertIsNotNone(hmt_intro)
        self.assertEqual(hmt_intro["section_name"], "INTRO_BED")
        self.assertLessEqual(hmt_intro["energy_level"], 5)

    def test_08_slice_track_section_non_destructive(self):
        """Verify slice_track_section carves audio without touching original file."""
        ww_climax = self.bank.resolve_track_section("001 The White Wolf", section_type="CLIMAX_DROP")
        self.assertIsNotNone(ww_climax)
        source_path = ww_climax["track_path"]
        orig_size = source_path.stat().st_size
        orig_mtime = source_path.stat().st_mtime

        with tempfile.TemporaryDirectory() as td:
            out_slice = Path(td) / "test_slice.wav"
            res = self.bank.slice_track_section(
                track_path=source_path,
                start_sec=ww_climax["start_sec"],
                target_duration=3.5,
                output_file=out_slice,
                fade_in_sec=0.5,
                fade_out_sec=0.5,
            )
            self.assertTrue(out_slice.exists(), "Sliced WAV must be created")
            self.assertGreater(out_slice.stat().st_size, 10000, "Sliced audio must have substantial size")
            slice_dur = get_audio_duration(out_slice)
            self.assertAlmostEqual(slice_dur, 3.5, delta=0.5)

            # Test safety: original track file MUST remain untouched
            self.assertEqual(source_path.stat().st_size, orig_size, "Original track file size must not change")
            self.assertEqual(source_path.stat().st_mtime, orig_mtime, "Original track mtime must not change")

            # Test safety violation when overwriting source file
            with self.assertRaises(ValueError):
                self.bank.slice_track_section(source_path, 0.0, 2.0, source_path)

    def test_09_timeline_ledger_cue_slice_integration(self):
        """Verify timeline ledger records cue_slice metadata for scenes and leitmotifs."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            dummy_wav = tmp_path / "chunk1.wav"
            with wave.open(str(dummy_wav), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(b"\x00\x00" * 24000)

            plan = {
                "primary_mood": "tense",
                "level1_leitmotifs": [
                    {
                        "theme": "geralt_destiny",
                        "trigger_segment": 1,
                        "timing": "under",
                        "volume": 0.22,
                        "cue_slice": {
                            "section_name": "INTRO_BED",
                            "track_name": "001 The White Wolf.mp3",
                            "start_sec": 0.0,
                            "end_sec": 35.0,
                            "energy_level": 3
                        }
                    }
                ],
                "level2_chapter_bed": {
                    "setting": "dark_forest",
                    "base_volume": 0.16
                },
                "scenes": [
                    {
                        "scene_id": 1,
                        "segment_start": 1,
                        "segment_end": 1,
                        "emotional_arc": {"music_mood": "tense", "intensity": 9},
                        "cue_slice": {
                            "section_name": "CLIMAX_DROP",
                            "track_name": "047 A Blade of Silver.mp3",
                            "start_sec": 35.0,
                            "end_sec": 100.0,
                            "energy_level": 10
                        }
                    }
                ]
            }

            ledger_file = tmp_path / "ledger_sliced.json"
            ledger = build_chapter_timeline_ledger(
                chapter_id=4,
                script_segments=[{"index": 1, "speaker": "Geralt", "type": "dialogue", "text": "Silver is for monsters."}],
                audio_chunk_paths=[dummy_wav],
                soundscape_plan=plan,
                output_ledger_file=ledger_file
            )

            self.assertIn("scenes", ledger)
            self.assertIn("cue_slice", ledger["scenes"][0])
            self.assertEqual(ledger["scenes"][0]["cue_slice"]["section_name"], "CLIMAX_DROP")
            self.assertEqual(ledger["scenes"][0]["cue_slice"]["energy_level"], 10)
            self.assertEqual(ledger["hierarchical_score"]["level1_leitmotifs"][0]["cue_slice"]["section_name"], "INTRO_BED")


if __name__ == "__main__":
    unittest.main()
