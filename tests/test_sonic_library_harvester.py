#!/usr/bin/env python3
"""
Test Suite: Sonic Intelligence Library Harvesting Subsystem.
============================================================
Validates:
1. Embedded metadata extraction (ID3, Vorbis, BWF, container tags).
2. Universal Category System (UCS) filename grammar parsing.
3. Micro-SFX transient handling and conservative non-tonal guard.
4. Long audio composite sampling and multi-window representation.
5. Strict uncertainty preservation (zero fabricated fields).
6. Idempotent resume and fingerprint skip behavior.
7. Stage-selective harvesting (metadata_dsp vs ai_only vs all).
8. Fault-tolerant error isolation on corrupted files.
9. Epistemic integrity: 7 creative dimensions remain strictly unassigned.
10. End-to-end search retrieval on newly harvested sound assets.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pytest

from audiobook_factory.contracts import AgentSoundCard, SonicGenome
from audiobook_factory.embedded_metadata_harvester import AudioMetadataExtractor
from audiobook_factory.sonic_harvester import SonicLibraryHarvester
from audiobook_factory.sonic_intelligence_engine import SonicIntelligenceEngine
from audiobook_factory.sound_bank import SoundBank

GOLDEN_DIR = Path("tests/fixtures/golden_sound_library").resolve()


class TestSonicLibraryHarvester(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Ensure golden dataset exists
        if not (GOLDEN_DIR / "micro_sfx_transient_01.wav").exists():
            from tests.fixtures.generate_golden_library import generate_golden_dataset
            generate_golden_dataset()

    def setUp(self):
        from audiobook_factory.sonic_model_manager import SonicModelManager
        try:
            SonicModelManager().clear_vram()
        except Exception:
            pass
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="sonic_harvest_test_"))
        self.db_path = self.tmp_dir / "test_sound_bank.db"
        self.bank = SoundBank(db_path=self.db_path, bank_root=self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        from audiobook_factory.sonic_model_manager import SonicModelManager
        try:
            SonicModelManager().clear_vram()
        except Exception:
            pass

    def test_01_embedded_metadata_extraction_id3(self):
        """Verifies embedded container metadata is extracted and raw tags are preserved 100%."""
        target_file = GOLDEN_DIR / "embedded_id3_metadata_sample_01.mp3"
        self.assertTrue(target_file.exists(), f"Missing {target_file}")

        extractor = AudioMetadataExtractor()
        source_meta = extractor.harvest_source_metadata(target_file, root_dir=GOLDEN_DIR)

        norm = source_meta.normalized
        raw = source_meta.raw_metadata

        # Assert normalized fields extracted accurately
        self.assertEqual(norm.title, "Ancient Castle Hall Fireplace")
        self.assertEqual(norm.creator, "Master Sound Designer")
        self.assertEqual(norm.collection, "Cinematic Fantasy Vol 1")
        self.assertIn("flames crackling", norm.description)
        self.assertEqual(norm.category, "AMB")

        # Assert raw metadata preserved uncorrupted
        self.assertIn("title", raw)
        self.assertIn("artist", raw)
        self.assertIn("album", raw)
        self.assertEqual(source_meta.provenance.source_method, "source_metadata")
        self.assertEqual(source_meta.provenance.analyzer_id, "embedded_metadata_harvester")

    def test_02_ucs_filename_parsing(self):
        """Verifies Universal Category System (UCS) grammar parsing without guessing."""
        target_file = GOLDEN_DIR / "DOORWood_Heavy Gate Slam_ST01.wav"
        self.assertTrue(target_file.exists(), f"Missing {target_file}")

        extractor = AudioMetadataExtractor()
        ucs_data = extractor.parse_ucs_naming(target_file.stem)
        self.assertIsNotNone(ucs_data)
        self.assertEqual(ucs_data["ucs_cat_id"], "DOORWOOD")
        self.assertEqual(ucs_data["category"], "FOL")
        self.assertEqual(ucs_data["subcategory"], "Doors / Latches")
        self.assertEqual(ucs_data["fx_name"], "Heavy Gate Slam")
        self.assertEqual(ucs_data["creator"], "ST01")
        self.assertEqual(ucs_data["exciter"], "wood")

        # Non-UCS file returns None
        non_ucs = extractor.parse_ucs_naming("rec_20260927_raw_001")
        self.assertIsNone(non_ucs)

    def test_03_micro_sfx_transient_and_conservative_tonal_guard(self):
        """Verifies micro-SFX (<0.1s) is analyzed without hallucinated pitches or zero-pad distortion."""
        target_file = GOLDEN_DIR / "micro_sfx_transient_01.wav"
        self.assertTrue(target_file.exists())

        harvester = SonicLibraryHarvester(db_path=self.db_path, conn_factory=self.bank._get_conn)
        res = harvester.harvest_single_asset(target_file, root_dir=GOLDEN_DIR, stage="metadata_dsp")

        self.assertEqual(res["status"], "SUCCESS")
        sound_id = res["sound_id"]
        self.assertIsNotNone(sound_id)

        # Inspect database record
        with self.bank._get_conn() as conn:
            row = conn.execute("SELECT * FROM sound_catalog WHERE id = ?", (sound_id,)).fetchone()
            self.assertIsNotNone(row)
            self.assertLess(row["duration_sec"], 0.10)
            self.assertIsNotNone(row["integrated_lufs"])
            self.assertIsNotNone(row["true_peak_db"])

        # Check genome conservative tonal invariants
        genome = self.bank.get_sonic_genome(sound_id)
        self.assertIsNotNone(genome)
        # Conservative tonal guard: Micro SFX must NOT have hallucinated pitch or BPM
        self.assertFalse(genome.measured_facts.tonal.is_tonal)
        self.assertIsNone(genome.measured_facts.tonal.detected_pitch_hz)
        self.assertIsNone(genome.measured_facts.tonal.detected_bpm)

    def test_04_long_ambience_composite_sampling(self):
        """Verifies long audio (>30s) uses composite sampling across start, mid, end."""
        target_file = GOLDEN_DIR / "long_ambience_mountain_wind_01.wav"
        self.assertTrue(target_file.exists())

        harvester = SonicLibraryHarvester(db_path=self.db_path, conn_factory=self.bank._get_conn)
        res = harvester.harvest_single_asset(target_file, root_dir=GOLDEN_DIR, stage="metadata_dsp")

        self.assertEqual(res["status"], "SUCCESS")
        sound_id = res["sound_id"]

        with self.bank._get_conn() as conn:
            row = conn.execute("SELECT * FROM sound_catalog WHERE id = ?", (sound_id,)).fetchone()
            self.assertGreater(row["duration_sec"], 30.0)
            self.assertIsNotNone(row["spectral_centroid_hz"])
            self.assertIsNotNone(row["integrated_lufs"])

    def test_05_unlabeled_raw_recording_uncertainty_preservation(self):
        """Verifies that un-annotated files preserve uncertainty without fabricated metadata."""
        target_file = GOLDEN_DIR / "rec_20260927_raw_001.wav"
        self.assertTrue(target_file.exists())

        extractor = AudioMetadataExtractor()
        source_meta = extractor.harvest_source_metadata(target_file, root_dir=GOLDEN_DIR)

        # Zero fabricated creator, description, or mood
        self.assertEqual(source_meta.normalized.creator, "")
        self.assertEqual(source_meta.normalized.description, "")
        self.assertEqual(source_meta.normalized.mood, "default")
        self.assertEqual(source_meta.normalized.license, "Unknown / Unspecified")

    def test_06_idempotent_harvest_and_resumability(self):
        """Verifies running harvest twice skips all already-analyzed assets instantly."""
        # 1. First run: process all golden assets in metadata_dsp mode
        res1 = self.bank.harvest_library(
            directory=GOLDEN_DIR,
            recursive=True,
            stage="metadata_dsp",
            max_workers=4,
        )
        self.assertEqual(res1["total_discovered"], 16)
        self.assertEqual(res1["processed"], 16)
        self.assertEqual(res1["skipped_valid"], 0)
        self.assertEqual(res1["failed"], 0)

        # 2. Second run: immediate skip
        res2 = self.bank.harvest_library(
            directory=GOLDEN_DIR,
            recursive=True,
            stage="metadata_dsp",
            max_workers=4,
        )
        self.assertEqual(res2["total_discovered"], 16)
        self.assertEqual(res2["processed"], 0)
        self.assertEqual(res2["skipped_valid"], 16)
        self.assertEqual(res2["failed"], 0)
        self.assertLess(res2["elapsed_sec"], 1.0)

    def test_07_stage_selective_harvesting(self):
        """Verifies selective stage execution: metadata_dsp -> ai_only."""
        # Process 1 file in metadata_dsp stage
        target_file = GOLDEN_DIR / "foley_impact_metal_01.wav"
        harvester = SonicLibraryHarvester(db_path=self.db_path, conn_factory=self.bank._get_conn)

        res_dsp = harvester.harvest_single_asset(target_file, root_dir=GOLDEN_DIR, stage="metadata_dsp")
        sound_id = res_dsp["sound_id"]

        with self.bank._get_conn() as conn:
            # DSP columns filled
            row = conn.execute("SELECT integrated_lufs FROM sound_catalog WHERE id = ?", (sound_id,)).fetchone()
            self.assertIsNotNone(row["integrated_lufs"])
            # AI tables still empty
            embed_cnt = conn.execute("SELECT COUNT(*) FROM sound_embeddings WHERE track_id = ?", (sound_id,)).fetchone()[0]
            self.assertEqual(embed_cnt, 0)

        # Now enrich with ai_only stage
        res_ai = harvester.harvest_single_asset(target_file, root_dir=GOLDEN_DIR, stage="ai_only")
        self.assertEqual(res_ai["status"], "SUCCESS")

        with self.bank._get_conn() as conn:
            embed_cnt = conn.execute("SELECT COUNT(*) FROM sound_embeddings WHERE track_id = ?", (sound_id,)).fetchone()[0]
            self.assertEqual(embed_cnt, 1)

    def test_08_crash_safety_and_error_isolation(self):
        """Verifies corrupt audio files are recorded as FAILED without aborting remaining batch."""
        corrupt_dir = self.tmp_dir / "corrupt_test_dir"
        corrupt_dir.mkdir(parents=True, exist_ok=True)

        # 1 valid file
        shutil.copy(GOLDEN_DIR / "foley_cloth_rustle_01.wav", corrupt_dir / "valid_01.wav")
        # 1 corrupt file
        corrupt_file = corrupt_dir / "corrupt_header.wav"
        corrupt_file.write_bytes(b"RIFF\x00\x00\x00\x00WAVEcorruptgarbageheaderdata\x00\x00")
        # 1 more valid file
        shutil.copy(GOLDEN_DIR / "foley_footstep_gravel_01.wav", corrupt_dir / "valid_02.wav")

        harvester = SonicLibraryHarvester(db_path=self.db_path, conn_factory=self.bank._get_conn)
        stats = harvester.harvest_directory(corrupt_dir, stage="metadata_dsp")

        self.assertEqual(stats["total_discovered"], 3)
        self.assertEqual(stats["processed"], 2)
        self.assertEqual(stats["failed"], 1)

        # Assert failed run was recorded in sound_analysis_runs
        with self.bank._get_conn() as conn:
            failed_runs = conn.execute("""
                SELECT error_message FROM sound_analysis_runs WHERE execution_status = 'FAILED'
            """).fetchall()
            self.assertGreaterEqual(len(failed_runs), 1)

    def test_09_epistemic_integrity_zero_creative_hallucinations(self):
        """Verifies harvested sound cards strictly maintain 7 unassigned creative dimensions."""
        harvester = SonicLibraryHarvester(db_path=self.db_path, conn_factory=self.bank._get_conn)
        res = harvester.harvest_single_asset(
            GOLDEN_DIR / "foley_door_creak_slam_01.wav",
            root_dir=GOLDEN_DIR,
            stage="metadata_dsp",
        )
        sound_id = res["sound_id"]

        card = self.bank.get_agent_sound_card_v3(sound_id)
        self.assertIsInstance(card, AgentSoundCard)

        # All 7 creative dimensions must be unassigned
        self.assertEqual(card.dramatic_role, "UNASSIGNED")
        self.assertEqual(card.scene_purpose, "UNASSIGNED")
        self.assertEqual(card.emotional_suitability, "UNINTERPRETED")
        self.assertEqual(card.voice_masking_judgment, "UNASSESSED")
        self.assertIsNone(card.dialogue_ducking_amount_db)
        self.assertEqual(card.placement_usage, "UNASSIGNED")
        self.assertEqual(card.final_taxonomy, "UNASSIGNED")

    def test_10_search_integration_after_harvest(self):
        """Verifies newly harvested assets are immediately searchable via SonicIntelligenceEngine."""
        # Harvest the full golden directory
        self.bank.harvest_library(
            directory=GOLDEN_DIR,
            recursive=True,
            stage="all",
            max_workers=4,
        )

        engine = SonicIntelligenceEngine(sound_bank=self.bank)

        # Search for metal sword impact
        res1 = engine.search_sounds(intent="heavy sword strike metal impact", limit=3)
        self.assertGreater(len(res1.ranked_cards), 0)
        top1_titles = [c.filename for c in res1.ranked_cards]
        self.assertTrue(any("metal" in t for t in top1_titles))

        # Search for door slam
        res2 = engine.search_sounds(intent="heavy door slam shut", limit=3)
        self.assertGreater(len(res2.ranked_cards), 0)
        top2_titles = [c.filename for c in res2.ranked_cards]
        self.assertTrue(any("door" in t.lower() or "gate" in t.lower() for t in top2_titles))


if __name__ == "__main__":
    unittest.main()
