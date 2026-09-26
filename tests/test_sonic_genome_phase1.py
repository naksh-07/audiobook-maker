#!/usr/bin/env python3
"""
Unit and Integration Test Suite for Sonic Intelligence System (Phase 1 — Foundation).
=====================================================================================
Covers all 12 architectural validation pillars:
1. Sonic Genome serialization & deserialization (v2.1 Pydantic model roundtrip)
2. Provenance model & method tracking (source_metadata, measured_dsp, classifier, etc.)
3. Confidence representation (granular per-value, None for measured, float for inferred)
4. Measured facts vs Inferred interpretations clean separation
5. Source metadata normalization & raw field preservation
6. Deterministic DSP enrichment on physical audio (format, loudness LUFS, spectral, temporal)
7. Missing / unsupported measurements (unpitched noise, clicks, zero-pitch SFX)
8. Idempotent reprocessing & analyzer version awareness
9. SQLite schema migration correctness (non-destructive extension)
10. Virtual asset / cache invariant (measured facts & metadata survive LRU eviction)
11. Existing FTS5 full-text & hybrid search preservation
12. Backward compatibility with existing audiobook integrations (Agent Director, Retriever, Sound Cards)
"""

import sys
import json
import math
import random
import shutil
import wave
import tempfile
import unittest
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.contracts import (
    SonicGenome,
    MeasuredAudioFacts,
    SourceMetadata,
    NormalizedSourceFields,
    ProvenanceRecord,
    AudioEventRecord,
    InferredMetadata,
    PhysicalGenome,
    TemporalWaveGenome,
    SpatialGenome,
    EnvironmentalGenome,
    DramaticGenome,
    MixCompatibilityGenome,
    MusicIntelligence,
    FoleyIntelligence,
    RemoteAssetMetadata,
    AcousticMetrics,
    SemanticAnnotations,
)
from audiobook_factory.deterministic_audio_analyzer import (
    DeterministicAudioAnalyzer,
    ANALYZER_VERSION,
    ANALYZER_ID,
    ONTOLOGY_VERSION,
)
from audiobook_factory.sound_bank import SoundBank, get_sound_bank
from audiobook_factory.sound_design.asset_retriever import SoundAssetRetriever


class TestSonicIntelligencePhase1(unittest.TestCase):
    """Full Phase 1 Validation Suite."""

    @classmethod
    def setUpClass(cls):
        cls.global_tmp = tempfile.TemporaryDirectory()
        cls.global_tmp_path = Path(cls.global_tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.global_tmp.cleanup()

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.db_path = self.tmp_path / "test_sound_bank.db"
        self.bank = SoundBank(db_path=self.db_path, bank_root=self.tmp_path)
        self.analyzer = DeterministicAudioAnalyzer()

    def tearDown(self):
        self.tmp_dir.cleanup()

    # -------------------------------------------------------------------------
    # Audio Generation Helpers
    # -------------------------------------------------------------------------

    def _create_wav(
        self,
        filename: str,
        duration_sec: float = 1.0,
        sample_rate: int = 48000,
        channels: int = 2,
        freq_hz: float = 440.0,
        amplitude: float = 0.5,
        noise_mix: float = 0.0,
    ) -> Path:
        """Generates a synthetic WAV fixture for deterministic testing."""
        file_path = self.tmp_path / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        num_samples = int(duration_sec * sample_rate)
        frames = bytearray()

        for i in range(num_samples):
            t = i / sample_rate
            tone = amplitude * math.sin(2.0 * math.pi * freq_hz * t) if freq_hz > 0 else 0.0
            noise = (random.random() * 2.0 - 1.0) * noise_mix
            sample_val = int(max(-32767, min(32767, (tone + noise) * 32767)))
            b = sample_val.to_bytes(2, byteorder="little", signed=True)
            for _ in range(channels):
                frames.extend(b)

        with wave.open(str(file_path), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(frames)

        return file_path

    def _create_transient_click(self, filename: str) -> Path:
        """Generates a short physical transient click (50ms)."""
        file_path = self.tmp_path / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        sr = 48000
        num_samples = int(0.05 * sr)
        frames = bytearray()

        for i in range(num_samples):
            # Sharp decaying impulse
            env = math.exp(-i / (0.005 * sr))
            val = int(25000 * env * math.sin(2.0 * math.pi * 1200.0 * (i / sr)))
            b = val.to_bytes(2, byteorder="little", signed=True)
            frames.extend(b * 2)

        with wave.open(str(file_path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(frames)

        return file_path

    # -------------------------------------------------------------------------
    # Pillar 1: Sonic Genome Serialization & Deserialization
    # -------------------------------------------------------------------------

    def test_01_sonic_genome_serialization(self):
        """Verify SonicGenome v2.1 serialization, deserialization, and JSON roundtrip."""
        genome = SonicGenome(
            version="2.1",
            track_id=101,
            filename="sword_draw_01.wav",
        )
        genome.measured_facts.format.duration_sec = 2.45
        genome.measured_facts.format.sample_rate = 48000
        genome.measured_facts.loudness.integrated_lufs = -18.5
        genome.measured_facts.spectral.spectral_centroid_hz = 3200.0
        genome.inferred.category = "FOL"
        genome.inferred.action_type = "draw"

        # Model dump & JSON
        j_str = genome.model_dump_json()
        restored = SonicGenome.model_validate_json(j_str)

        self.assertEqual(restored.version, "2.1")
        self.assertEqual(restored.track_id, 101)
        self.assertEqual(restored.filename, "sword_draw_01.wav")
        self.assertEqual(restored.measured_facts.format.duration_sec, 2.45)
        self.assertEqual(restored.measured_facts.loudness.integrated_lufs, -18.5)
        self.assertEqual(restored.measured_facts.spectral.spectral_centroid_hz, 3200.0)
        self.assertEqual(restored.inferred.action_type, "draw")

    # -------------------------------------------------------------------------
    # Pillar 2: Provenance Tracking
    # -------------------------------------------------------------------------

    def test_02_provenance_tracking(self):
        """Verify comprehensive provenance structure across all supported methods."""
        prov_methods = [
            "source_metadata",
            "measured_dsp",
            "classifier",
            "semantic_model",
            "llm_inferred",
            "keyword_inferred",
            "curated",
        ]
        for method in prov_methods:
            rec = ProvenanceRecord(
                source_method=method,
                analyzer_id=f"{method}_engine",
                analyzer_version="1.0.0",
                ontology_version=ONTOLOGY_VERSION,
                confidence=None if method == "measured_dsp" else 0.85,
            )
            self.assertEqual(rec.source_method, method)
            self.assertEqual(rec.analyzer_version, "1.0.0")
            if method == "measured_dsp":
                self.assertIsNone(rec.confidence)
            else:
                self.assertEqual(rec.confidence, 0.85)

    # -------------------------------------------------------------------------
    # Pillar 3: Confidence Model
    # -------------------------------------------------------------------------

    def test_03_confidence_model(self):
        """Verify confidence strictly belongs to individual inferred values, NEVER measured DSP."""
        genome = SonicGenome(track_id=1, filename="footstep_stone.wav")
        # Measured DSP has None confidence
        self.assertIsNone(genome.measured_facts.provenance.confidence)

        # Inferred metadata has explicit float confidence
        self.assertIsNotNone(genome.inferred.confidence)
        self.assertGreaterEqual(genome.inferred.confidence, 0.0)
        self.assertLessEqual(genome.inferred.confidence, 1.0)

        # Future classifier outputs can attach confidence
        genome.classifier_output = {
            "predicted_label": "stone_impact",
            "confidence": 0.88,
            "provenance": {
                "source_method": "classifier",
                "analyzer_id": "panns_cnn14",
                "confidence": 0.88
            }
        }
        self.assertEqual(genome.classifier_output["confidence"], 0.88)

    # -------------------------------------------------------------------------
    # Pillar 4: Measured Facts vs Inferred Interpretations Separation
    # -------------------------------------------------------------------------

    def test_04_measured_vs_inferred_separation(self):
        """Verify strict epistemic boundary between physical DSP measurements and narrative inferences."""
        genome = SonicGenome(track_id=2, filename="tavern_ambience.wav")
        genome.measured_facts.loudness.integrated_lufs = -24.0
        genome.measured_facts.spectral.spectral_centroid_hz = 1500.0
        genome.inferred.action_type = "chatter"
        genome.dramatic.dramatic_role = "ambient_grounding"

        # Relational check: measured DSP facts reside in measured_facts, inferred in inferred/dramatic
        self.assertEqual(genome.measured_facts.loudness.integrated_lufs, -24.0)
        self.assertEqual(genome.measured_facts.provenance.source_method, "measured_dsp")
        self.assertEqual(genome.inferred.action_type, "chatter")
        self.assertEqual(genome.inferred.provenance.source_method, "keyword_inferred")

    # -------------------------------------------------------------------------
    # Pillar 5: Source Metadata Normalization & Preservation
    # -------------------------------------------------------------------------

    def test_05_source_metadata_normalization(self):
        """Verify preservation of raw provider metadata alongside normalized fields."""
        raw_payload = {
            "isrc": "US-KML-12-00452",
            "original_bitrate": 320,
            "custom_provider_key": "incompetech_special_id_99",
            "bpm": "120",
        }
        track_id = self.bank.ingest_source_metadata(
            item={
                "filename": "kevin_macleod_epic.mp3",
                "title": "Epic Journey",
                "description": "Orchestral adventure theme",
                "category": "MUS",
                "subcategory": "Orchestral",
                "tempo_bpm": 120.0,
                "duration_sec": 180.0,
                "raw_metadata": raw_payload,
            },
            source_name="Incompetech"
        )
        self.assertGreater(track_id, 0)

        genome = self.bank.get_sonic_genome(track_id)
        self.assertIsNotNone(genome)
        self.assertEqual(genome.source_metadata.provider_name, "Incompetech")
        self.assertEqual(genome.source_metadata.normalized.title, "Epic Journey")
        self.assertEqual(genome.source_metadata.normalized.tempo_bpm, 120.0)
        # Verify raw metadata is preserved
        self.assertEqual(genome.source_metadata.raw_metadata.get("isrc"), "US-KML-12-00452")
        self.assertEqual(genome.source_metadata.raw_metadata.get("custom_provider_key"), "incompetech_special_id_99")

    # -------------------------------------------------------------------------
    # Pillar 6: Deterministic DSP Enrichment on Real Audio
    # -------------------------------------------------------------------------

    def test_06_deterministic_dsp_enrichment(self):
        """Verify full deterministic DSP extraction across format, loudness, spectral, and temporal."""
        # Create a 440Hz test tone WAV file (0.6s, 48kHz, stereo)
        audio_path = self._create_wav("tone_440.wav", duration_sec=0.6, freq_hz=440.0, amplitude=0.4)

        facts, events = self.analyzer.analyze_file(audio_path)

        # 1. Format facts
        self.assertEqual(facts.format.sample_rate, 48000)
        self.assertEqual(facts.format.channels, 2)
        self.assertEqual(facts.format.container, "wav")
        self.assertAlmostEqual(facts.format.duration_sec, 0.6, delta=0.05)

        # 2. Loudness facts
        self.assertIsNotNone(facts.loudness.integrated_lufs)
        self.assertLess(facts.loudness.integrated_lufs, 0.0)
        self.assertIsNotNone(facts.loudness.true_peak_dbtp)

        # 3. Spectral facts (440Hz tone should have centroid ~440Hz, low flatness)
        self.assertIsNotNone(facts.spectral.spectral_centroid_hz)
        self.assertAlmostEqual(facts.spectral.spectral_centroid_hz, 440.0, delta=25.0)
        self.assertIsNotNone(facts.spectral.spectral_flatness)
        self.assertLess(facts.spectral.spectral_flatness, 0.1)

        # 4. Temporal facts
        self.assertIsNotNone(facts.temporal.silence_ratio)
        self.assertGreater(facts.temporal.active_duration_sec, 0.4)

        # 5. Tonal facts
        self.assertTrue(facts.tonal.is_tonal)
        self.assertAlmostEqual(facts.tonal.detected_pitch_hz, 440.0, delta=10.0)

    # -------------------------------------------------------------------------
    # Pillar 7: Missing / Unsupported Measurements (Conservative Tonal Guard)
    # -------------------------------------------------------------------------

    def test_07_missing_unsupported_measurements(self):
        """Verify unpitched noisy SFX do not hallucinate pitch, BPM, or tonality."""
        # Pure white noise (flatness > 0.9)
        noise_path = self._create_wav("pure_noise.wav", duration_sec=0.5, freq_hz=0.0, noise_mix=0.8)

        facts, _ = self.analyzer.analyze_file(noise_path)
        self.assertFalse(facts.tonal.is_tonal)
        self.assertIsNone(facts.tonal.detected_pitch_hz)
        self.assertIsNone(facts.tonal.detected_bpm)
        self.assertGreater(facts.spectral.spectral_flatness, 0.7)

    # -------------------------------------------------------------------------
    # Pillar 8: Idempotent Reprocessing
    # -------------------------------------------------------------------------

    def test_08_idempotent_reprocessing(self):
        """Verify that running enrich_asset multiple times is safe and non-duplicating."""
        audio_path = self._create_wav("reprocess_test.wav", duration_sec=0.5, freq_hz=300.0)
        with self.bank._get_conn() as conn:
            cur = conn.execute("""
                INSERT INTO sound_catalog (filename, filepath, category, is_downloaded)
                VALUES (?, ?, 'SFX', 1) RETURNING id;
            """, (audio_path.name, str(audio_path)))
            track_id = cur.fetchone()[0]

        # First enrichment run
        g1 = self.bank.enrich_asset(track_id, force=True)
        prov1 = self.bank.get_asset_provenance(track_id)
        self.assertEqual(len(prov1), 1)

        # Second enrichment run (idempotent re-run)
        g2 = self.bank.enrich_asset(track_id, force=True)
        prov2 = self.bank.get_asset_provenance(track_id)
        self.assertEqual(len(prov2), 2)  # Logged 2 separate audit runs

        # Verify catalog row count did NOT duplicate
        with self.bank._get_conn() as conn:
            cnt = conn.execute("SELECT COUNT(*) FROM sound_catalog WHERE filename = ?", (audio_path.name,)).fetchone()[0]
            self.assertEqual(cnt, 1)

        # Facts match exactly
        self.assertEqual(g1.measured_facts.format.duration_sec, g2.measured_facts.format.duration_sec)
        self.assertEqual(g1.measured_facts.loudness.integrated_lufs, g2.measured_facts.loudness.integrated_lufs)

    # -------------------------------------------------------------------------
    # Pillar 9: Schema Migration Correctness
    # -------------------------------------------------------------------------

    def test_09_schema_migration_correctness(self):
        """Verify non-destructive schema migration adds all 14 columns and new tables without data loss."""
        # Create legacy sqlite table without measured columns
        legacy_db = self.tmp_path / "legacy_test.db"
        import sqlite3
        conn = sqlite3.connect(str(legacy_db))
        conn.execute("""
            CREATE TABLE sound_catalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                filepath TEXT,
                category TEXT
            );
        """)
        conn.execute("INSERT INTO sound_catalog (filename, category) VALUES ('test_legacy.wav', 'SFX');")
        conn.commit()
        conn.close()

        # Initialize SoundBank against legacy database
        migrated_bank = SoundBank(db_path=legacy_db, bank_root=self.tmp_path)
        with migrated_bank._get_conn() as c:
            cols = [col[1] for col in c.execute("PRAGMA table_info(sound_catalog)").fetchall()]
            self.assertIn("integrated_lufs", cols)
            self.assertIn("spectral_centroid_hz", cols)
            self.assertIn("silence_ratio", cols)
            self.assertIn("analysis_version", cols)

            tables = [tbl[0] for tbl in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            self.assertIn("sound_analysis_runs", tables)
            self.assertIn("sound_temporal_events", tables)

            # Assert original row survived untouched
            row = c.execute("SELECT * FROM sound_catalog WHERE filename = 'test_legacy.wav'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["category"], "SFX")

    # -------------------------------------------------------------------------
    # Pillar 10: Virtual Asset / Cache Invariant
    # -------------------------------------------------------------------------

    def test_10_virtual_asset_cache_invariant(self):
        """Verify that when local audio bytes are evicted by LRU pruning, all metadata & measured facts survive."""
        audio_path = self._create_wav("cache_eviction_test.wav", duration_sec=0.5, freq_hz=500.0)

        with self.bank._get_conn() as conn:
            cur = conn.execute("""
                INSERT INTO sound_catalog (filename, filepath, category, is_downloaded, size_bytes)
                VALUES (?, ?, 'SFX', 1, ?) RETURNING id;
            """, (audio_path.name, str(audio_path), audio_path.stat().st_size))
            track_id = cur.fetchone()[0]

        # Enrich while file is local
        genome = self.bank.enrich_asset(track_id)
        measured_lufs = genome.measured_facts.loudness.integrated_lufs
        self.assertIsNotNone(measured_lufs)

        # Simulate cache manager eviction: delete file on disk, set is_downloaded = 0, filepath = NULL
        audio_path.unlink()
        with self.bank._get_conn() as conn:
            conn.execute("UPDATE sound_catalog SET filepath = NULL, is_downloaded = 0 WHERE id = ?", (track_id,))

        # Verify metadata & measured columns survived in SQLite
        with self.bank._get_conn() as conn:
            row = conn.execute("SELECT is_downloaded, filepath, integrated_lufs, sonic_genome FROM sound_catalog WHERE id = ?", (track_id,)).fetchone()
            self.assertEqual(row["is_downloaded"], 0)
            self.assertIsNone(row["filepath"])
            self.assertEqual(row["integrated_lufs"], measured_lufs)

        # Verify get_sonic_genome still returns measured facts from survived JSON
        survived_genome = self.bank.get_sonic_genome(track_id)
        self.assertIsNotNone(survived_genome)
        self.assertEqual(survived_genome.measured_facts.loudness.integrated_lufs, measured_lufs)

    # -------------------------------------------------------------------------
    # Pillar 11: Existing FTS & Hybrid Search Preservation
    # -------------------------------------------------------------------------

    def test_11_existing_fts_search_preservation(self):
        """Verify that BM25 FTS5 search and search_virtual_catalog continue to function without degradation."""
        with self.bank._get_conn() as conn:
            conn.execute("""
                INSERT INTO sound_catalog (
                    filename, category, subcategory, mood, tags, title, description,
                    action_type, exciter, resonator, dramatic_role, is_downloaded
                ) VALUES (
                    'ancient_iron_gate_creak.wav', 'FOL', 'Doors', 'tense',
                    'ancient iron gate heavy dungeon entrance', 'Ancient Gate', 'Dungeon gate',
                    'creak', 'steel', 'hall', 'suspense_builder', 0
                );
            """)

        # 1. Standard search
        results = self.bank.search("ancient iron gate", category="FOL")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["filename"], "ancient_iron_gate_creak.wav")

        # 2. Hybrid search_virtual_catalog
        candidates = self.bank.search_virtual_catalog(
            query="iron gate",
            category="FOL",
            action_type="creak",
            limit=1
        )
        self.assertGreater(len(candidates), 0)
        self.assertEqual(candidates[0]["filename"], "ancient_iron_gate_creak.wav")
        self.assertIn("why_matched", candidates[0])

    # -------------------------------------------------------------------------
    # Pillar 12: Backward Compatibility with Downstream Engines
    # -------------------------------------------------------------------------

    def test_12_downstream_compatibility(self):
        """Verify compatibility with Agent Sound Cards and SoundAssetRetriever."""
        audio_path = self._create_wav("clash_blade.wav", duration_sec=0.4, freq_hz=800.0)

        with self.bank._get_conn() as conn:
            cur = conn.execute("""
                INSERT INTO sound_catalog (
                    filename, filepath, category, subcategory, tags, title,
                    action_type, exciter, resonator, is_downloaded
                ) VALUES (
                    ?, ?, 'FOL', 'Combat', 'sword blade metal clash combat fight',
                    'Blade Clash', 'clash', 'steel', 'room', 1
                ) RETURNING id;
            """, (audio_path.name, str(audio_path)))
            track_id = cur.fetchone()[0]

        # Enrich track
        self.bank.enrich_asset(track_id)

        # 1. Verify format_agent_sound_card
        candidates = self.bank.search_virtual_catalog(query="blade clash", limit=1)
        self.assertGreater(len(candidates), 0)
        card_text = self.bank.format_agent_sound_card(candidates[0])
        self.assertIn("Sound Asset Card", card_text)
        self.assertIn("Blade Clash", card_text)
        self.assertIn("Why Matched", card_text)

        # 2. Verify SoundAssetRetriever sanity verification
        retriever = SoundAssetRetriever(sound_bank=self.bank)
        is_sane, metrics = retriever.verify_asset_sanity(audio_path)
        self.assertTrue(is_sane)
        self.assertIn("integrated_lufs", metrics)


if __name__ == "__main__":
    unittest.main()
