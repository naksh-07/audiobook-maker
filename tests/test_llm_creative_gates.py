#!/usr/bin/env python3
"""
Test Suite: LLM Creative Quality & Audit Gates.
Verifies that rubber-stamp heuristic passes are completely replaced by
fail-closed LLM Judges using dynamic model resolution (TaskType.AUDITING) without hardcoded models.
"""

import os
import pytest
from pathlib import Path
from typing import Dict, Any

from audiobook_factory.gates.contracts import GateAuditError
from audiobook_factory.model_manager import get_model_manager, TaskType
from audiobook_factory.gates.llm_judge import (
    BaseLLMJudge,
    LLMTranslationJudge,
    LLMScreenplayAuditor,
    LLMDramaticCritic,
    LLMPerceptualPerformanceJudge,
    LLMSoundDesignCritic,
    TranslationFidelityVerdict,
    DialogueAttributionVerdict,
    DramaticArcVerdict,
    VocalActingVerdict,
    SoundDesignAtmosphereVerdict,
)
from audiobook_factory.gates.literary import (
    audit_gate0_translation,
    audit_gate1_anticensorship_agent,
)
from audiobook_factory.gates.screenplay import audit_gate2_script


@pytest.fixture(autouse=True)
def setup_mock_env(monkeypatch):
    """Ensure offline mock mode is active for deterministic unit testing."""
    monkeypatch.setenv("MOCK_OFFLINE", "1")


class TestDynamicModelResolution:
    def test_auditing_task_type_has_model_floor(self):
        """Verifies that AUDITING task is registered with minimum Tier 2 capability floor."""
        from audiobook_factory.model_manager import TASK_MINIMUM_TIERS, ModelTier
        assert TaskType.AUDITING in TASK_MINIMUM_TIERS
        assert TASK_MINIMUM_TIERS[TaskType.AUDITING] == ModelTier.TIER_2_BALANCED

    def test_base_judge_resolves_auditing_model_without_hardcode(self):
        """Verifies that BaseLLMJudge resolves model dynamically via ModelManager."""
        mgr = get_model_manager()
        candidates = mgr.get_candidate_models_for_task(TaskType.AUDITING)
        assert len(candidates) > 0
        # No hardcoded model string in judge class definition
        assert not hasattr(BaseLLMJudge, "MODEL_NAME")


class TestLLMTranslationJudge:
    def test_translation_judge_passes_high_fidelity(self):
        source = "Geralt drew his silver sword with deliberate slowness."
        hindi = "गेराल्ट ने सधी हुई गति से अपनी चांदी की तलवार म्यान से बाहर निकाली।"
        verdict = LLMTranslationJudge.audit_translation(source, hindi, strict=True)
        assert isinstance(verdict, TranslationFidelityVerdict)
        assert verdict.status == "PASS"
        assert verdict.score >= 0.80

    def test_translation_judge_fails_closed_on_gibberish(self):
        source = "The striga lunged towards Geralt with bloodthirsty fury."
        hindi = "fail_test: random gibberish that reverses action completely."
        with pytest.raises(GateAuditError) as exc_info:
            LLMTranslationJudge.audit_translation(source, hindi, strict=True)
        assert "LLM Translation Audit FAILED" in str(exc_info.value)


class TestLLMScreenplayAuditor:
    def test_screenplay_auditor_passes_correct_attribution(self):
        source = '“I seek the golden dragon,” Borch said with a calm smile.'
        segments = [
            {"index": 1, "speaker": "Borch", "type": "dialogue", "text": "मैं सुनहरे ड्रैगन की तलाश में हूँ।", "emotion": "calm"}
        ]
        verdict = LLMScreenplayAuditor.audit_screenplay(source, segments, strict=True)
        assert isinstance(verdict, DialogueAttributionVerdict)
        assert verdict.status == "PASS"

    def test_screenplay_auditor_fails_closed_on_misattribution(self):
        source = '“I seek the golden dragon,” Borch said.'
        # Misattributed to Geralt
        segments = [
            {"index": 1, "speaker": "Geralt", "type": "dialogue", "text": "wrong_speaker: I seek the golden dragon.", "emotion": "calm"}
        ]
        with pytest.raises(GateAuditError) as exc_info:
            LLMScreenplayAuditor.audit_screenplay(source, segments, strict=True)
        assert "LLM Screenplay Attribution FAILED" in str(exc_info.value)


class TestLLMDramaticCritic:
    def test_dramatic_critic_passes_grounded_arc(self):
        segments = [
            {"index": 1, "speaker": "Geralt", "emotion": "calm", "type": "dialogue", "text": "रुको।"},
            {"index": 2, "speaker": "Geralt", "emotion": "tense", "type": "dialogue", "text": "कोई आ रहा है।"},
        ]
        verdict = LLMDramaticCritic.audit_dramatic_arc(segments, strict=True)
        assert isinstance(verdict, DramaticArcVerdict)
        assert verdict.status == "PASS"
        assert not verdict.emotional_teleportation_detected

    def test_dramatic_critic_fails_closed_on_teleportation(self):
        segments = [
            {"index": 1, "speaker": "Geralt", "emotion": "simulate_teleportation", "type": "dialogue", "text": "झटका।"},
        ]
        with pytest.raises(GateAuditError) as exc_info:
            LLMDramaticCritic.audit_dramatic_arc(segments, strict=True)
        assert "LLM Dramatic Fidelity FAILED" in str(exc_info.value)


class TestLLMPerceptualPerformanceJudge:
    def test_performance_judge_critiques_acting(self):
        direction = {
            "speaker": "Geralt",
            "surface_emotion": "cold_menace",
            "intensity": "high",
            "actioning": "threaten",
            "subtext": "You will die if you take another step",
            "restraint": 0.85,
        }
        dsp_metrics = {"peak_amplitude": 25000, "rms_dbfs": -19.5, "is_clipped": False}
        verdict = LLMPerceptualPerformanceJudge.critique_performance(
            direction=direction,
            acoustic_metrics=dsp_metrics,
            text="एक कदम और बढ़ाया तो तुम्हारी गर्दन नहीं बचेगी।",
            strict=False,
        )
        assert isinstance(verdict, VocalActingVerdict)
        assert verdict.status == "PASS"
        assert verdict.overall_acting_score >= 0.80

    def test_performance_judge_fails_closed_on_bad_acting(self):
        direction = {
            "speaker": "Geralt",
            "surface_emotion": "grief",
            "intensity": "high",
            "actioning": "weep",
            "subtext": "Unbearable loss",
            "restraint": 0.3,
        }
        dsp_metrics = {"peak_amplitude": 12000, "rms_dbfs": -35.0, "is_clipped": False}
        with pytest.raises(GateAuditError) as exc_info:
            LLMPerceptualPerformanceJudge.critique_performance(
                direction=direction,
                acoustic_metrics=dsp_metrics,
                text="bad_acting: flat_robotic reading without emotion.",
                strict=True,
            )
        assert "LLM Vocal Performance Audit FAILED" in str(exc_info.value)


class TestLLMSoundDesignCritic:
    def test_sound_design_critic_passes_authentic_atmosphere(self):
        scene_text = "The cold drizzle tapped relentlessly on the sodden straw roofs of Blaviken."
        manifest_summary = {
            "ambience": "rain_on_thatch_roof.wav",
            "bgm": "somber_medieval_fiddle.wav",
            "foley": ["mud_footstep.wav"],
        }
        verdict = LLMSoundDesignCritic.audit_soundscape(
            scene_text=scene_text,
            manifest_summary=manifest_summary,
            active_env="tavern_village_rain",
            strict=True,
        )
        assert isinstance(verdict, SoundDesignAtmosphereVerdict)
        assert verdict.status == "PASS"
        assert verdict.ambience_scene_fitness
        assert verdict.music_mood_aligned

    def test_sound_design_critic_fails_closed_on_clashing_audio(self):
        scene_text = "Geralt stood over the slaughtered bodies in the grim tavern."
        manifest_summary = {
            "ambience": "modern_leak_car_highway.wav",
            "bgm": "clashing_audio_upbeat_circus.wav",
        }
        with pytest.raises(GateAuditError) as exc_info:
            LLMSoundDesignCritic.audit_soundscape(
                scene_text=scene_text,
                manifest_summary=manifest_summary,
                strict=True,
            )
        assert "LLM Sound Design Audit FAILED" in str(exc_info.value)


class TestGate0AndGate1Upgrades:
    def test_gate0_invokes_llm_judge(self, tmp_path):
        src_file = tmp_path / "chapter_001.md"
        trans_file = tmp_path / "chapter_001_hi.md"
        src_file.write_text("Long source text with proper paragraphs " * 20, encoding="utf-8")
        trans_file.write_text("उचित अनुच्छेदों के साथ लंबा स्रोत पाठ " * 20, encoding="utf-8")

        res = audit_gate0_translation(src_file, trans_file, enable_llm_judge=True, strict=True)
        assert res["status"] == "PASS"
        assert "fidelity_score" in res
        assert res["fidelity_score"] >= 0.80

    def test_gate1_anticensorship_fails_on_diluted_curses(self):
        english = "You filthy bastard, die like a dog!"
        # Diluted with polite serial word 'दुष्ट' instead of 'हरामी'
        diluted_hindi = "तुम गंदे दुष्ट, कुत्ते की मौत मरो!"
        with pytest.raises(GateAuditError) as exc_info:
            audit_gate1_anticensorship_agent(english, diluted_hindi, strict=True)
        assert "Gate 1 Anti-Censorship Failed" in str(exc_info.value)
