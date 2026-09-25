#!/usr/bin/env python3
"""
Audiobook Factory - Wave 3 Acting Intelligence Test Suite.
Tests:
1. SceneEmotionalVector and SceneEmotionalStateTracker transition smoothing.
2. PerformanceConstraintResolver primary intention, secondary modifiers, and forbidden filtering.
3. GenerationRiskEngine per-segment risk scoring and take policy allocation.
4. PerformanceDirector dynamic risk-based take allocation.
5. GeminiTTSPerformanceAdapter concise style formatting without adjective bloat.
"""

import unittest
from pathlib import Path

from audiobook_factory.performance.scene_emotional_state import (
    SceneEmotionalVector,
    SceneEmotionalStateTracker,
)
from audiobook_factory.performance.constraint_resolver import (
    PerformanceConstraintResolver,
    ResolvedPerformanceConstraints,
)
from audiobook_factory.performance.risk_engine import (
    GenerationRiskEngine,
    GenerationRiskReport,
)
from audiobook_factory.performance.contracts import PerformanceDirection
from audiobook_factory.performance.director import PerformanceDirector
from audiobook_factory.performance.tts_adapter import GeminiTTSPerformanceAdapter
from audiobook_factory.identity.voice_dna import (
    VoiceDNA,
    VoiceDNAIdentityLayer,
    VoiceDNABehaviorLayer,
    VoiceDNAForbiddenLayer,
)


class TestWave3ActingIntelligence(unittest.TestCase):

    def test_01_scene_emotional_state_smoothing(self):
        """Verifies SceneEmotionalStateTracker smooths volatile leaps without causal triggers."""
        tracker = SceneEmotionalStateTracker(scene_id="scene_001")

        # Initial calm line
        v1 = tracker.update_state(1, "SpeakerA", "calm", intensity="low")
        self.assertLess(v1.energy, 0.6)
        self.assertLess(v1.arousal, 0.5)

        # Abrupt ungrounded jump to explosive rage
        v2 = tracker.update_state(2, "SpeakerA", "explosive_rage", intensity="explosive", causal_trigger=None)

        # Should be smoothed / damped rather than instantaneously jumping
        self.assertLess(v2.energy, 0.98)
        self.assertGreater(v2.restraint, 0.50)  # Tense suppression applied

        # Causal trigger allows sharp legitimate jump
        v3 = tracker.update_state(3, "SpeakerA", "explosive_rage", intensity="explosive", causal_trigger="attacked")
        self.assertGreaterEqual(v3.energy, 0.95)

    def test_02_performance_constraint_resolver_clean_directives(self):
        """Verifies PerformanceConstraintResolver outputs clean, prioritized directives."""
        pd = PerformanceDirection(
            index=1,
            speaker="Inquisitor",
            actioning="corner_and_interrogate",
            surface_emotion="suppressed_menace",
            restraint=0.85,
            pitch_behavior="low_resonant",
            physical_state="wounded",
            proximity="close_mic",
        )
        dna = VoiceDNA(
            character_id="inquisitor",
            character_name="Inquisitor",
            voice_id="fenrir",
            forbidden=VoiceDNAForbiddenLayer(forbidden_behaviors=["screaming", "shrill panic"]),
        )

        resolved = PerformanceConstraintResolver.resolve_constraints(pd, voice_dna=dna)

        # Primary intention must be clean and lead
        self.assertIn("suppressed menace", resolved.primary_intention)
        self.assertIn("corner and interrogate", resolved.primary_intention)

        # Secondary modifiers limited to at most 3
        self.assertLessEqual(len(resolved.secondary_modifiers), 3)
        self.assertIn("iron restraint", resolved.secondary_modifiers)

        # Forbidden behaviors must be collected
        self.assertIn("screaming", resolved.forbidden_behaviors)

        # Clean style descriptor should not contain forbidden words or comma bloat
        self.assertNotIn("screaming", resolved.clean_style_descriptor)
        self.assertLess(len(resolved.clean_style_descriptor.split(",")), 6)

    def test_03_generation_risk_engine_policy(self):
        """Verifies GenerationRiskEngine allocates takes accurately according to dramatic risk."""
        # 1. Routine narration -> Low risk, exactly 1 take
        pd_narr = PerformanceDirection(
            index=1,
            speaker="Narrator",
            narrative_mode="narrator_exposition",
            surface_emotion="neutral",
            intensity="medium",
        )
        rep_narr = GenerationRiskEngine.calculate_segment_risk(pd_narr, text="The ancient forest stretched for leagues.")
        self.assertLess(rep_narr.risk_score, 0.25)
        self.assertEqual(rep_narr.recommended_takes, 1)

        # 2. Explosive shout / screaming combat line -> High risk, 3 takes
        pd_combat = PerformanceDirection(
            index=2,
            speaker="Warrior",
            surface_emotion="rage",
            intensity="explosive",
            pace=1.3,
            physical_state="combat_strain",
        )
        rep_combat = GenerationRiskEngine.calculate_segment_risk(pd_combat, text="[shouting] Fall back! Protect the gates!")
        self.assertGreaterEqual(rep_combat.risk_score, 0.70)
        self.assertGreaterEqual(rep_combat.recommended_takes, 3)

        # 3. Fragile whisper with subtext -> Elevated risk, 2-3 takes
        pd_whisper = PerformanceDirection(
            index=3,
            speaker="Spy",
            proximity="close_mic",
            intimacy_level="intimate",
            surface_emotion="fear",
            social_mask="masking_terror",
            subtext_confidence=0.85,
        )
        rep_whisper = GenerationRiskEngine.calculate_segment_risk(pd_whisper, text="[whispering] They know we are here.")
        self.assertGreaterEqual(rep_whisper.risk_score, 0.50)
        self.assertGreaterEqual(rep_whisper.recommended_takes, 2)

    def test_04_director_dynamic_risk_calibration(self):
        """Verifies PerformanceDirector automatically upgrades takes on high-risk lines."""
        director = PerformanceDirector()

        # Simple segment
        simple_seg = {
            "uid": "seg_01",
            "index": 1,
            "speaker": "Guard",
            "text": "The gate is locked for the night.",
            "emotion": "neutral",
            "intensity_level": "medium",
            "performance_priority": "standard",
        }
        pd_simple = director.direct_segment(simple_seg)
        self.assertEqual(pd_simple.required_takes, 1)

        # High-risk screaming/wounded line
        risk_seg = {
            "uid": "seg_02",
            "index": 2,
            "speaker": "Guard",
            "text": "[shouting] Help me! The gates are falling!",
            "emotion": "rage",
            "intensity_level": "explosive",
            "blocking_directive": "wounded, bleeding heavily",
            "performance_priority": "standard",  # Not manually set to climactic
        }
        pd_risk = director.direct_segment(risk_seg)
        # Risk engine should dynamically elevate takes
        self.assertGreaterEqual(pd_risk.required_takes, 2)

    def test_05_tts_adapter_context_awareness(self):
        """Verifies GeminiTTSPerformanceAdapter generates concise payload without modifying text."""
        adapter = GeminiTTSPerformanceAdapter()
        pd = PerformanceDirection(
            index=10,
            speaker="Sorcerer",
            surface_emotion="cold_threat",
            actioning="intimidate",
            restraint=0.8,
            proximity="close_mic",
        )
        text = "Speak one more word, and you will turn to ash."
        payload = adapter.adapt_direction_to_payload(text, pd, variant_type="restraint")

        # Sacred text invariant
        self.assertEqual(payload["part_payload"]["text"], text)
        # Speech style descriptor present
        style = payload["part_payload"]["speechMetadata"]["style"]
        self.assertTrue(len(style) > 0)
        # Restraint temperature calibration
        self.assertLessEqual(payload["temperature"], 0.68)


if __name__ == "__main__":
    unittest.main()
