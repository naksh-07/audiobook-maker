#!/usr/bin/env python3
"""
Audiobook Factory - Wave 1 Casting Subsystem Test Suite.
Tests:
1. CharacterCastingProfile creation and derivation from existing entities.
2. VoiceCandidateEngine multi-dimensional scoring, ranking, and explainable breakdowns.
3. VoiceAuditionEngine 10-mode audition generation and synthesis.
4. CastingEvaluator 10-dimensional evaluation and evidence preservation.
5. CastLockManager persistent locking, sync with voice_registry.json, and recasting invalidation.
6. TTSDispatcher integration with CastLockManager.
"""

import json
import tempfile
import unittest
from pathlib import Path

from audiobook_factory.casting import (
    CharacterCastingProfile,
    VoiceCandidateScore,
    AuditionScene,
    AuditionResult,
    CastingEvaluationRecord,
    CastLock,
    VoiceCandidateEngine,
    VoiceAuditionEngine,
    CastingEvaluator,
    CastLockManager,
)
from audiobook_factory.translation.book_bible import BookEntity
from audiobook_factory.translation.character_profile import CharacterLanguageProfile
from audiobook_factory.dramaturgy.contracts import CharacterPerformanceProfile
from audiobook_factory.tts_dispatcher import TTSDispatcher


class TestWave1CastingSubsystem(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)
        self.scripts_dir = self.project_dir / "scripts"
        self.audio_dir = self.project_dir / "audio_chunks"
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_character_casting_profile_derivation(self):
        """Verifies CharacterCastingProfile derives cleanly from existing entities without duplication."""
        entity = BookEntity(
            canonical_id="hero_commander",
            english_name="Commander Valen",
            gender="male",
            sociolect_archetype="MILITARY_COMMANDER",
        )
        lang_profile = CharacterLanguageProfile(
            english_name="Commander Valen",
            hindi_name="सेनापति वालेन",
            formality_level=4,
            sentence_length_preference="staccato",
            prohibited_registers=["poetic florid prose", "hesitant whining"],
        )
        perf_profile = CharacterPerformanceProfile(
            character_name="Commander Valen",
            baseline_pace=0.95,
            baseline_energy=0.88,
            articulation="crisp",
            restraint_level=0.75,
            emotional_behaviors={"anger": "cold_menace"},
        )

        profile = CharacterCastingProfile.from_entities(
            character_id="hero_commander",
            canonical_name="Commander Valen",
            entity=entity,
            language_profile=lang_profile,
            performance_profile=perf_profile,
        )

        self.assertEqual(profile.character_id, "hero_commander")
        self.assertEqual(profile.gender, "male")
        self.assertEqual(profile.pace, 0.95)
        self.assertEqual(profile.articulation, "crisp")
        self.assertEqual(profile.restraint, 0.75)
        self.assertEqual(profile.vocal_weight, "heavy")
        self.assertIn("cold_menace", profile.required_styles)
        self.assertIn("poetic florid prose", profile.forbidden_styles)

    def test_02_voice_candidate_engine_ranking_and_explainability(self):
        """Verifies VoiceCandidateEngine ranks catalog voices and produces explainable breakdowns."""
        engine = VoiceCandidateEngine()
        profile = CharacterCastingProfile(
            character_id="veteran_hunter",
            canonical_name="Old Hunter",
            gender="male",
            perceived_age="mature_adult",
            sociolect_archetype="COLD_CYNIC",
            authority=0.8,
            restraint=0.75,
            vocal_weight="heavy",
            timbre_preference="gravelly",
            pitch_preference="low",
            required_styles=["cold suppressed menace", "gravelly battle roar"],
            forbidden_styles=["cartoon panic", "high-pitched bubbly youth"],
        )

        candidates = engine.rank_candidates(profile, top_n=5)
        self.assertTrue(len(candidates) >= 3)

        top_cand = candidates[0]
        # Algenib, Fenrir, or Charon should rank near the top for a mature gritty male
        self.assertIn(top_cand.voice_id.lower(), ["algenib", "fenrir", "charon"])
        self.assertGreaterEqual(top_cand.overall_score, 0.75)
        self.assertTrue(len(top_cand.strengths) > 0)
        self.assertIn("gender_fit", top_cand.score_breakdown)
        self.assertIn("timbre_fit", top_cand.score_breakdown)
        self.assertIn("personality_fit", top_cand.score_breakdown)

        # Distinctiveness test: if candidate voice is already assigned, score drops
        ensemble = {"Companion": top_cand.voice_id}
        re_ranked = engine.rank_candidates(profile, ensemble_voices=ensemble, top_n=5)
        found_penalized = [c for c in re_ranked if c.voice_id == top_cand.voice_id]
        if found_penalized:
            self.assertEqual(found_penalized[0].score_breakdown["distinctiveness"], 0.15)

    def test_03_voice_audition_engine_10_modes(self):
        """Verifies VoiceAuditionEngine generates all 10 required audition modes and audio."""
        audition_engine = VoiceAuditionEngine()
        profile = CharacterCastingProfile(
            character_id="hero_protagonist",
            canonical_name="Protagonist",
            gender="female",
            perceived_age="prime_adult",
        )

        scenes = audition_engine.generate_audition_scenes(profile, use_hindi=True)
        self.assertEqual(len(scenes), 10)
        modes = {s.dramatic_mode for s in scenes}
        expected_modes = {
            "neutral", "conversational", "authority", "anger",
            "vulnerability", "fear", "whisper", "humor", "action", "transition"
        }
        self.assertEqual(modes, expected_modes)

        # Run mock audition synthesis
        out_dir = self.project_dir / "auditions" / profile.character_id
        results = audition_engine.run_audition("kore", scenes, out_dir)
        self.assertEqual(len(results), 10)
        for res in results:
            self.assertTrue(Path(res.audio_path).exists())
            self.assertGreater(Path(res.audio_path).stat().st_size, 100)
            self.assertTrue(res.passed)

    def test_04_casting_evaluator_dimensions_and_evidence(self):
        """Verifies CastingEvaluator evaluates 10 dimensions and preserves evidence."""
        evaluator = CastingEvaluator()
        profile = CharacterCastingProfile(
            character_id="advisor_sorceress",
            canonical_name="Sorceress Advisor",
            gender="female",
            perceived_age="prime_adult",
            sociolect_archetype="RAZOR_ARISTOCRAT",
            authority=0.8,
            timbre_preference="sharp",
        )
        cand_score = VoiceCandidateScore(
            voice_id="kore",
            display_name="Kore",
            overall_score=0.88,
            strengths=["Crisp commanding articulation", "Authoritative presence"],
            risks=[],
            score_breakdown={
                "gender_fit": 1.0,
                "archetype_fit": 0.9,
                "personality_fit": 0.85,
                "timbre_fit": 0.9,
                "range_fit": 0.85,
                "distinctiveness": 1.0,
            },
        )

        # Generate mock audition files
        audition_engine = VoiceAuditionEngine()
        scenes = audition_engine.generate_audition_scenes(profile)
        aud_dir = self.project_dir / "auditions" / "test_kore"
        aud_results = audition_engine.run_audition("kore", scenes, aud_dir)

        record = evaluator.evaluate_candidate_audition(profile, cand_score, aud_results)

        self.assertEqual(record.candidate_voice_id, "kore")
        self.assertTrue(record.passed_audition)
        self.assertGreaterEqual(record.overall_fit_score, 0.70)
        self.assertIn("naturalness", record.dimension_scores)
        self.assertIn("authority", record.dimension_scores)
        self.assertIn("vulnerability", record.dimension_scores)
        self.assertIn("whisper_quality", record.dimension_scores)
        self.assertIn("high_intensity_quality", record.dimension_scores)
        self.assertEqual(len(record.audition_results), 10)

    def test_05_cast_lock_manager_persistence_and_recast_invalidation(self):
        """Verifies CastLockManager locks voices, syncs voice_registry.json, and recasts with invalidation."""
        mgr = CastLockManager(self.project_dir)

        # Lock character
        lock = mgr.lock_character(
            character_id="captain_guard",
            character_name="Captain of the Guard",
            voice_id="fenrir",
            selection_rationale="Unanimous audition winner for commanding authority",
            calibration_overrides={"speed": 0.95, "pitch": 0.98},
        )

        self.assertTrue(mgr.is_locked("Captain of the Guard"))
        self.assertTrue(mgr.is_locked("captain_guard"))
        self.assertEqual(lock.voice_id, "fenrir")

        # Verify cast_lock.json exists and is valid
        lock_file = self.project_dir / "cast_lock.json"
        self.assertTrue(lock_file.exists())
        with open(lock_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("captain_guard", data["locks"])

        # Verify voice_registry.json was synchronized automatically
        reg_file = self.project_dir / "voice_registry.json"
        self.assertTrue(reg_file.exists())
        with open(reg_file, "r", encoding="utf-8") as f:
            reg_data = json.load(f)
        self.assertIn("Captain of the Guard", reg_data)
        self.assertEqual(reg_data["Captain of the Guard"]["voice"], "fenrir")
        self.assertTrue(reg_data["Captain of the Guard"]["cast_locked"])

        # Create dummy audio chunk for this character to test recast invalidation
        dummy_chunk = self.audio_dir / "c001_s0015_fenrir_hash1234.wav"
        dummy_chunk.write_text("synthetic audio bytes")

        # Mock script segment
        script_file = self.scripts_dir / "chapter_001_hi_script.json"
        script_content = [
            {"index": 15, "speaker": "Captain of the Guard", "text": "Halt!"}
        ]
        with open(script_file, "w", encoding="utf-8") as f:
            json.dump(script_content, f)

        # Recast character
        recast_lock = mgr.recast_character(
            character_name_or_id="Captain of the Guard",
            new_voice_id="charon",
            reason="Creative redirection toward understated stoicism",
        )

        self.assertEqual(recast_lock.voice_id, "charon")
        self.assertEqual(len(mgr.manifest.recast_history), 1)

        # Verify old audio chunk was archived/invalidated
        self.assertFalse(dummy_chunk.exists())
        archived = list((self.audio_dir / "recast_archive").glob("*.wav"))
        self.assertEqual(len(archived), 1)

    def test_06_tts_dispatcher_respects_cast_lock(self):
        """Verifies TTSDispatcher prioritizes CastLock over legacy voice_registry.json."""
        # 1. Write legacy voice registry pointing to old voice
        legacy_reg = {
            "Narrator": {"backend": "gemini_tts", "voice": "Aoede"},
            "Chief_Engineer": {"backend": "gemini_tts", "voice": "Puck", "speed": 1.0},
        }
        with open(self.project_dir / "voice_registry.json", "w", encoding="utf-8") as f:
            json.dump(legacy_reg, f)

        # 2. Write formal cast lock pointing to new authoritative voice
        mgr = CastLockManager(self.project_dir)
        mgr.lock_character(
            character_id="chief_engineer",
            character_name="Chief_Engineer",
            voice_id="alnilam",
            calibration_overrides={"speed": 0.92, "pitch": 0.95},
        )

        # 3. Initialize TTSDispatcher
        dispatcher = TTSDispatcher(project_dir=self.project_dir, strict_speakers=True)
        cfg = dispatcher.get_speaker_config("Chief_Engineer", seg_type="dialogue")

        # Must return locked voice 'alnilam', NOT legacy 'Puck'
        self.assertEqual(cfg["voice"], "alnilam")
        self.assertEqual(cfg["speed"], 0.92)
        self.assertTrue(cfg.get("cast_locked"))


if __name__ == "__main__":
    unittest.main()
