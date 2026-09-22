#!/usr/bin/env python3
"""
Unit and Integration Tests for Sonic Genome & Superhuman Music Director Engine.
Verifies Pydantic v2 schemas, SQLite JSON1 virtual columns, search_music_catalog filtering,
and spectral notch pocketing.
"""

import json
import sqlite3
import unittest
from pathlib import Path

from audiobook_factory.contracts import (
    SonicGenome,
    AcousticMetrics,
    SemanticAnnotations,
    MusicCue,
)
from audiobook_factory.sound_bank import SoundBank, get_sound_bank
from audiobook_factory.agent_director import AgentDirector


class TestSonicGenomeEngine(unittest.TestCase):
    def setUp(self):
        self.sound_bank = get_sound_bank()

    def test_01_pydantic_schema_validation(self):
        """Verify SonicGenome Pydantic models validate and serialize correctly."""
        ac = AcousticMetrics(
            true_peak_dbtp=-0.5,
            integrated_lufs=-14.2,
            speech_corridor_density=0.52,
            transient_drops_sec=[1.5, 4.2, 10.0],
            bpm=135.0,
            intro_bed_end_sec=1.5,
            vocal_clash_risk="SEVERE",
        )
        sem = SemanticAnnotations(
            valence=0.6,
            arousal=0.9,
            tension=0.8,
            narrative_function="CLIMACTIC_ACTION",
            narrative_archetypes=["TAVERN_BRAWL", "MONSTER_HUNT"],
            slavic_instruments=["davul_drums", "kemenche"],
            story_triggers=["fisticuffs", "brawl", "punch thrown"],
        )
        genome = SonicGenome(
            track_id=400,
            filename="037 Fists of Fury.mp3",
            acoustic=ac,
            semantic=sem,
            id3_metadata={"title": "Fists of Fury", "artist": "Marcin Przybyłowicz"},
        )
        data = genome.model_dump()
        reconstructed = SonicGenome.model_validate(data)
        self.assertEqual(reconstructed.track_id, 400)
        self.assertEqual(reconstructed.acoustic.vocal_clash_risk, "SEVERE")
        self.assertEqual(reconstructed.semantic.narrative_function, "CLIMACTIC_ACTION")

    def test_02_database_enrichment_coverage(self):
        """Verify all 230 Witcher tracks in sound_bank.db have non-empty sonic_genome."""
        conn = sqlite3.connect(self.sound_bank.db_path)
        c = conn.cursor()
        count = c.execute("SELECT count(*) FROM sound_catalog WHERE sonic_genome != '{}' AND sonic_genome IS NOT NULL").fetchone()[0]
        conn.close()
        self.assertGreaterEqual(count, 230, f"Expected at least 230 enriched tracks, found {count}")

    def test_03_search_music_catalog_with_valence_arousal(self):
        """Verify search_music_catalog filters by emotional valence and arousal."""
        # Query combat brawl with high arousal (> 0.7)
        results = self.sound_bank.search_music_catalog(
            query="fisticuffs brawl",
            target_valence=0.5,
            target_arousal=0.8,
            limit=3,
        )
        self.assertTrue(len(results) > 0, "Expected at least 1 result for brawl query")
        first = results[0]
        self.assertIn("sonic_genome", first)
        self.assertIn("genome_valence", first)
        self.assertIn("genome_arousal", first)
        genome = json.loads(first["sonic_genome"])
        self.assertIn("acoustic", genome)
        self.assertIn("semantic", genome)

    def test_04_music_cue_spectral_notch_flag(self):
        """Verify MusicCue handles spectral_notch_needed and emotional coordinates."""
        cue = MusicCue(
            cue_id="mc_test_01",
            cue_type="CLIMACTIC_ACTION_CUE",
            track_name="037 Fists of Fury.mp3",
            section_name="CLIMAX_DROP",
            section_start_sec=1.75,
            start_ms=1000,
            duration_ms=5000,
            spectral_notch_needed=True,
            target_valence=0.6,
            target_arousal=0.8,
        )
        self.assertTrue(cue.spectral_notch_needed)
        self.assertEqual(cue.target_valence, 0.6)
        self.assertEqual(cue.target_arousal, 0.8)

    def test_05_sound_track_sections_have_real_data(self):
        """Verify sound_track_sections no longer has 0 BPM for enriched tracks."""
        conn = sqlite3.connect(self.sound_bank.db_path)
        c = conn.cursor()
        # Track 400 is Fists of Fury
        row = c.execute("SELECT tempo_bpm, start_sec FROM sound_track_sections WHERE track_id=400 AND section_name='CLIMAX_DROP'").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        bpm, start_sec = row
        self.assertGreater(bpm, 0, f"Expected non-zero BPM, got {bpm}")
        self.assertGreater(start_sec, 0.0, f"Expected measured start_sec > 0.0, got {start_sec}")

    def test_06_agent_director_pass2_sonic_genome_resolution(self):
        """Verify AgentDirector Pass 2 uses Sonic Genome and resolves cues with spectral notch & narrative archetype."""
        director = AgentDirector(sound_bank=self.sound_bank)
        cues_plan = [
            {
                "cue_id": "mc_test_brawl",
                "cue_type": "CLIMACTIC_ACTION_CUE",
                "trigger_segment": 1,
                "narrative_archetype": "TAVERN_BRAWL",
                "valence": 0.5,
                "arousal": 0.8,
                "mood": "combat",
                "tempo": "fast",
                "timbre": "davul drums",
                "energy_section": "CLIMAX_DROP",
                "search_query": "fists brawl",
                "duration_sec": 15.0,
                "fade_in_sec": 2.0,
                "fade_out_sec": 3.0,
                "volume_db": -16.0,
            }
        ]
        seg_starts = {1: 5000}
        total_duration_ms = 60000
        resolved_cues = director._pass2_music_director(cues_plan, seg_starts, total_duration_ms)
        self.assertEqual(len(resolved_cues), 1)
        cue = resolved_cues[0]
        self.assertEqual(cue.narrative_archetype, "TAVERN_BRAWL")
        self.assertEqual(cue.target_valence, 0.5)
        self.assertEqual(cue.target_arousal, 0.8)
        self.assertTrue(bool(cue.track_name))
        self.assertGreater(cue.section_start_sec, 0.0)


if __name__ == "__main__":
    unittest.main()
