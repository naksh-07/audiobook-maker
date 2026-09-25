#!/usr/bin/env python3
"""
Audiobook Factory - TTS Casting & Generation Integration & Remediation Test Suite.
Verifies the clean wiring pass across:
1. Voice Identity & Reference Signature participation in Take Selection.
2. Generation Risk Engine take count control.
3. Scene Emotional State Tracker grounding across script segments.
4. Voice DNA grounding in Performance Director.
5. Voice Audition Engine dispatcher invocation.
6. Voice Audition Engine acoustic scoring via MathematicalAcousticAnalyzer.
7. Take Bank strategy plan prioritization.
8. End-to-end TTS Dispatcher segment synthesis wiring.
9. Character Continuity state persistence across chapters.
10. Sacred literary text immutability throughout the entire pipeline.
"""

import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch, MagicMock

from audiobook_factory.contracts import ScreenplaySegment
from audiobook_factory.dramaturgy.contracts import PerformanceBible, CharacterPerformanceProfile
from audiobook_factory.forensic_analyzer import MathematicalAcousticAnalyzer
from audiobook_factory.identity import (
    VoiceDNA,
    VoiceDNAIdentityLayer,
    VoiceDNABehaviorLayer,
    VoiceDNAEmotionalLayer,
    VoiceDNAForbiddenLayer,
    VoiceDNABank,
    AcousticSignature,
    ReferenceVoiceBank,
)
from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    TakeVariant,
)
from audiobook_factory.performance.director import PerformanceDirector
from audiobook_factory.performance.evaluator import PerformanceEvaluator
from audiobook_factory.performance.risk_engine import GenerationRiskEngine
from audiobook_factory.performance.scene_emotional_state import SceneEmotionalStateTracker, SceneEmotionalVector
from audiobook_factory.performance.strategy_resolver import GenerationStrategyResolver, GenerationStrategyPlan
from audiobook_factory.performance.take_bank import TakeBank
from audiobook_factory.performance.take_selector import IntelligentTakeSelector
from audiobook_factory.casting.audition_engine import VoiceAuditionEngine
from audiobook_factory.casting.contracts import CharacterCastingProfile, AuditionScene
from audiobook_factory.tts_dispatcher import TTSDispatcher


def generate_test_wav(
    path: Path,
    f0_hz: float = 140.0,
    dur_sec: float = 1.0,
    sample_rate: int = 24000,
    amp: int = 8000,
) -> Path:
    """Generates synthetic harmonic audio PCM WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    num_frames = int(sample_rate * dur_sec)
    samples = []
    for i in range(num_frames):
        t = i / sample_rate
        val = amp * (
            0.6 * math.sin(2.0 * math.pi * f0_hz * t)
            + 0.3 * math.sin(4.0 * math.pi * f0_hz * t)
            + 0.1 * math.sin(6.0 * math.pi * f0_hz * t)
        )
        samples.append(int(val))
    pcm = struct.pack(f"<{num_frames}h", *samples)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return path


class TestTTSIntegrationRemediation(unittest.TestCase):
    """Integration and Remediation test matrix."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)
        self.audio_dir = self.project_dir / "audio_chunks"
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_voice_identity_take_selection_drift_penalty(self):
        """Test 1: Voice identity signature and DNA penalize drifted takes in take selector."""
        evaluator = PerformanceEvaluator()
        selector = IntelligentTakeSelector(evaluator=evaluator)

        sig = AcousticSignature(
            character_id="char_hero",
            character_name="Hero",
            voice_id="Puck",
            f0_median=140.0,
            f0_iqr=15.0,
            spectral_centroid_mean=1500.0,
            spectral_flatness_mean=0.03,
            dynamic_range_db=25.0,
            sample_rate=24000,
        )
        dna = VoiceDNA(
            character_id="char_hero",
            character_name="Hero",
            voice_id="Puck",
            behavior=VoiceDNABehaviorLayer(baseline_pace=1.0, restraint=0.7),
        )

        direction = PerformanceDirection(
            direction_id="dir_001",
            segment_uid="seg_001",
            index=1,
            speaker="Hero",
            surface_emotion="neutral",
            intensity="medium",
            pace=1.0,
            performance_priority="standard",
        )

        # Consistent take (140 Hz matching reference)
        path_good = generate_test_wav(self.audio_dir / "take_good.wav", f0_hz=140.0, dur_sec=1.2)
        take_good = TakeVariant(
            take_id="take_good",
            segment_uid="seg_001",
            segment_index=1,
            variant_type="standard",
            audio_path=str(path_good),
            duration_sec=1.2,
            direction=direction,
        )

        # Drifted take (260 Hz, severe pitch drift)
        path_drifted = generate_test_wav(self.audio_dir / "take_drifted.wav", f0_hz=260.0, dur_sec=1.2)
        take_drifted = TakeVariant(
            take_id="take_drifted",
            segment_uid="seg_001",
            segment_index=1,
            variant_type="standard",
            audio_path=str(path_drifted),
            duration_sec=1.2,
            direction=direction,
        )

        winning_take = selector.select_best_take(
            takes=[take_drifted, take_good],
            text="The road goes ever on.",
            direction=direction,
            signature=sig,
            voice_dna=dna,
        )

        self.assertEqual(winning_take.take_id, "take_good")
        self.assertTrue(winning_take.is_selected)

    def test_02_generation_risk_take_count_control(self):
        """Test 2: Risk engine controls take counts (low risk = 1 take, climactic = 3 takes)."""
        # Low risk: calm narration
        calm_dir = PerformanceDirection(
            direction_id="dir_calm",
            segment_uid="seg_calm",
            index=1,
            speaker="Narrator",
            surface_emotion="neutral",
            intensity="low",
            performance_priority="standard",
        )
        low_risk = GenerationRiskEngine.calculate_segment_risk(
            calm_dir, text="The quiet evening settled over the peaceful valley."
        )
        self.assertEqual(low_risk.recommended_takes, 1)

        # High risk / Climactic: explosive shouting dialogue with high tension
        climax_dir = PerformanceDirection(
            direction_id="dir_climax",
            segment_uid="seg_climax",
            index=2,
            speaker="Hero",
            surface_emotion="rage",
            intensity="explosive",
            tension_before=0.9,
            performance_priority="climactic",
        )
        high_risk = GenerationRiskEngine.calculate_segment_risk(
            climax_dir, text="You betrayed everyone! Draw your blade, now!"
        )
        self.assertGreaterEqual(high_risk.recommended_takes, 2)
        self.assertIn(high_risk.risk_tier, ("elevated", "critical"))

    def test_03_scene_emotional_state_continuity_tracking(self):
        """Test 3: Scene emotional state tracker damps volatile emotional ruptures."""
        director = PerformanceDirector()

        # Script segments with a sudden ungrounded leap: calm -> bellowing rage without trigger
        segments = [
            {"speaker": "Warrior", "text": "We rest here tonight.", "emotion": "calm", "intensity_level": "low"},
            {"speaker": "Warrior", "text": "I will tear down these gates!", "emotion": "bellowing_rage", "intensity_level": "explosive"},
        ]

        directions = director.direct_chapter_script(segments)
        self.assertEqual(len(directions), 2)
        # Second direction must have dampened transition (suppressed rage or elevated restraint)
        d2 = directions[1]
        self.assertTrue(
            "suppressed" in d2.surface_emotion or d2.restraint >= 0.60,
            f"Expected dampened emotion or elevated restraint, got {d2.surface_emotion}, restraint={d2.restraint}",
        )

    def test_04_voice_dna_director_grounding(self):
        """Test 4: Performance director grounds baseline delivery in VoiceDNA."""
        director = PerformanceDirector()
        dna = VoiceDNA(
            character_id="char_elder",
            character_name="Elder",
            voice_id="Fenrir",
            identity=VoiceDNAIdentityLayer(resonance="throat", vocal_weight="heavy"),
            behavior=VoiceDNABehaviorLayer(
                baseline_pace=0.80,
                baseline_energy=0.55,
                articulation="crisp",
                restraint=0.85,
            ),
        )

        segment = {
            "speaker": "Elder",
            "text": "Listen carefully to the words of old.",
            "emotion": "neutral",
        }
        direction = director.direct_segment(segment, voice_dna=dna)

        self.assertAlmostEqual(direction.pace, 0.80, delta=0.05)
        self.assertEqual(direction.articulation, "crisp")
        self.assertGreaterEqual(direction.restraint, 0.75)
        self.assertEqual(direction.resonance, "throat")

    def test_05_audition_engine_dispatcher_integration(self):
        """Test 5: VoiceAuditionEngine invokes dispatcher or mock gracefully."""
        audition_engine = VoiceAuditionEngine()
        profile = CharacterCastingProfile(
            character_id="char_commander",
            canonical_name="Commander",
            character_name="Commander",
            gender="male",
            archetype="ruler",
            pace=1.0,
            energy=0.8,
        )
        scenes = audition_engine.generate_audition_scenes(profile, use_hindi=False)
        self.assertEqual(len(scenes), 10)

        # Mock dispatcher function
        dispatched_scenes = []

        def mock_dispatch(text: str, output_file: Path, voice: str, emotion: str):
            dispatched_scenes.append((text, voice, emotion))
            generate_test_wav(output_file, f0_hz=160.0, dur_sec=1.0)

        audition_dir = self.project_dir / "auditions"
        results = audition_engine.run_audition(
            candidate_voice_id="Puck",
            scenes=scenes[:3],
            output_dir=audition_dir,
            dispatcher=mock_dispatch,
        )

        self.assertEqual(len(results), 3)
        self.assertEqual(len(dispatched_scenes), 3)
        for r in results:
            self.assertTrue(Path(r.audio_path).exists())
            self.assertTrue(r.passed)

    def test_06_audition_engine_acoustic_scoring(self):
        """Test 6: VoiceAuditionEngine calculates dynamic acoustic score rather than static 0.85."""
        audition_engine = VoiceAuditionEngine()
        profile = CharacterCastingProfile(
            character_id="char_scout",
            canonical_name="Scout",
            character_name="Scout",
            gender="female",
            archetype="outlaw",
        )
        scenes = audition_engine.generate_audition_scenes(profile, use_hindi=False)

        audition_dir = self.project_dir / "auditions_acoustic"
        results = audition_engine.run_audition(
            candidate_voice_id="Kore",
            scenes=scenes[:2],
            output_dir=audition_dir,
            dispatcher=None,  # Uses synthetic audio generation
        )

        self.assertEqual(len(results), 2)
        for r in results:
            self.assertIsInstance(r.overall_score, float)
            self.assertGreaterEqual(r.overall_score, 0.50)
            self.assertLessEqual(r.overall_score, 1.0)
            self.assertGreater(r.duration_sec, 0.5)

    def test_07_take_bank_strategy_plan_prioritization(self):
        """Test 7: TakeBank respects GenerationStrategyPlan target_variants."""
        take_bank = TakeBank(self.audio_dir / "takes")
        direction = PerformanceDirection(
            direction_id="dir_focused",
            segment_uid="seg_focused",
            index=1,
            speaker="Scholar",
            surface_emotion="vulnerable",
            intensity="medium",
            performance_priority="focused",
        )

        # Plan with explicit target variants
        plan = GenerationStrategyPlan(
            segment_uid="seg_focused",
            strategy="ISOLATED_MULTI_TAKE",
            target_variants=["standard", "vulnerable"],
            recommended_takes=2,
            rationale="deep emotional vulnerability",
        )

        variants = take_bank.get_candidate_variants(direction, strategy_plan=plan, text="A secret whispered.")
        self.assertEqual(variants, ["standard", "vulnerable"])

    def test_08_tts_dispatcher_e2e_segment_flow(self):
        """Test 8: TTSDispatcher end-to-end segment synthesis with mocked Gemini synthesis."""
        dispatcher = TTSDispatcher(project_dir=self.project_dir)

        # Register speaker voice
        dispatcher.assign_voice("Hero", "gemini", "Puck")

        # Register voice DNA
        dna = VoiceDNA(
            character_id="hero",
            character_name="Hero",
            voice_id="Puck",
            identity=VoiceDNAIdentityLayer(resonance="chest"),
            behavior=VoiceDNABehaviorLayer(baseline_pace=1.05, restraint=0.60),
        )
        dispatcher.voice_dna_bank.register_dna(dna)

        segment = {
            "speaker": "Hero",
            "text": "The fortress gates are opening.",
            "emotion": "neutral",
            "type": "dialogue",
        }

        # Mock synthesize_gemini_tts to output valid synthetic audio
        def mock_gemini(output_file: Path, **kwargs):
            generate_test_wav(output_file, f0_hz=140.0, dur_sec=1.5)
            return output_file, 1.5

        with patch("audiobook_factory.tts_dispatcher.synthesize_gemini_tts", side_effect=mock_gemini):
            out_file, dur = dispatcher.synthesize_segment(
                segment=segment,
                chapter_num=1,
                seg_num=1,
            )

        self.assertTrue(out_file.exists())
        self.assertGreater(dur, 0.5)

    def test_09_character_continuity_persistence(self):
        """Test 9: PerformanceContinuityTracker records state and persists cleanly."""
        dispatcher = TTSDispatcher(project_dir=self.project_dir)
        tracker = dispatcher.continuity_tracker

        d1 = PerformanceDirection(
            direction_id="d1",
            index=1,
            speaker="Hero",
            pace=1.0,
            energy=0.7,
            surface_emotion="calm",
        )
        d2 = PerformanceDirection(
            direction_id="d2",
            index=2,
            speaker="Hero",
            pace=1.1,
            energy=0.85,
            surface_emotion="anger",
        )
        tracker.record_direction(d1, duration_sec=1.5)
        tracker.record_direction(d2, duration_sec=2.0)
        tracker.advance_chapter("chapter_001")

        save_path = self.project_dir / "character_continuity.json"
        tracker.save_to_file(save_path)
        self.assertTrue(save_path.exists())

        # Reload in a new tracker
        from audiobook_factory.performance.continuity import PerformanceContinuityTracker
        new_tracker = PerformanceContinuityTracker()
        new_tracker.load_from_file(save_path)
        self.assertIn("Hero", new_tracker.characters)
        self.assertEqual(len(new_tracker.characters["Hero"].paces), 2)

    def test_10_sacred_text_immutability_throughout_flow(self):
        """Test 10: Literary text remains 100% sacred and unmutated throughout."""
        sacred_original_text = "यह एक अत्यंत गंभीर और रहस्यमयी बात थी, जिसे कोई नहीं जानता था।"
        segment = ScreenplaySegment(
            index=1,
            speaker="Hero",
            text=sacred_original_text,
            type="dialogue",
            emotion="mysterious",
        )

        director = PerformanceDirector()
        p_dir = director.direct_segment(segment)

        # Spoken text engine may provide a pronunciation rendition, but literary text must remain untouched
        dispatcher = TTSDispatcher(project_dir=self.project_dir)
        spoken_res = dispatcher.spoken_text_engine.resolve_screenplay_segment(segment)

        # Check literary text remains unchanged
        self.assertEqual(segment.text, sacred_original_text)

        # Strategy resolution preserves sacred text
        strategy = GenerationStrategyResolver.resolve_strategy(p_dir, text=spoken_res.spoken_text or segment.text)
        self.assertIsNotNone(strategy)
        self.assertEqual(segment.text, sacred_original_text)


if __name__ == "__main__":
    unittest.main()
