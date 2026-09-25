#!/usr/bin/env python3
"""
Audiobook Factory - Test Suite for Dramatic Performance Realization Layer.
Tests contracts, timing realizer, performance director, TTS adapter,
evaluator, take bank, take selector, conversational chemistry,
continuity tracker, and Gate 2.8 performance fidelity gate.
"""

import os
import wave
import struct
import tempfile
import pytest
from pathlib import Path

from audiobook_factory.contracts import (
    ScreenplaySegment,
    PerformanceDirection,
    TakeVariant,
    PerformanceEvaluationResult,
    PerformanceFidelityReport,
)
from audiobook_factory.performance import (
    TimingRealizer,
    PerformanceDirector,
    GeminiTTSPerformanceAdapter,
    PerformanceEvaluator,
    TakeBank,
    IntelligentTakeSelector,
    ConversationalChemistry,
    PerformanceContinuityTracker,
    PerformanceFidelityGate,
)
from audiobook_factory.dramaturgy.contracts import (
    DramaticPlan,
    DramaticBeat,
    SceneDramaticPlan,
    CharacterDramaticObjective,
    DramaticSilenceIntent,
    ConversationalDynamic,
    PerformanceBible,
)
from audiobook_factory.dramaturgy.performance_bible import PerformanceBibleGenerator
from audiobook_factory.gate_auditor import audit_gate2_8_performance_fidelity, GateAuditError


def create_dummy_wav(path: Path, duration_sec: float = 1.0, sample_rate: int = 24000, amplitude: int = 2000):
    """Creates a clean synthetic mono PCM WAV file for unit tests."""
    import math
    path.parent.mkdir(parents=True, exist_ok=True)
    num_frames = int(sample_rate * duration_sec)
    samples = [int(amplitude * math.sin(2.0 * math.pi * 440.0 * i / sample_rate)) for i in range(num_frames)]
    pcm_bytes = struct.pack(f"<{num_frames}h", *samples)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return path


class TestPerformanceContracts:
    """Test suite for PerformanceDirection and related contracts."""

    def test_performance_direction_defaults_and_validation(self):
        pd = PerformanceDirection(
            index=1,
            speaker="Geralt",
            character_state="grim_focus",
            objective="secure tavern entrance",
            actioning="intimidate",
        )
        assert pd.direction_id.startswith("pd_0001_geralt")
        assert pd.provenance_mode == "SOURCE_DIRECT"
        assert pd.required_takes == 1
        assert pd.pace == 1.0
        assert pd.restraint == 0.5

    def test_priority_based_take_allocation(self):
        pd_climactic = PerformanceDirection(
            index=5,
            speaker="Yennefer",
            performance_priority="climactic",
        )
        assert pd_climactic.required_takes == 3

        pd_focused = PerformanceDirection(
            index=6,
            speaker="Dandelion",
            performance_priority="focused",
        )
        assert pd_focused.required_takes == 2

    def test_json_roundtrip_and_backward_compatibility(self):
        pd = PerformanceDirection(
            index=2,
            speaker="Narrator",
            surface_emotion="grave",
            underlying_emotion="dread",
            subtext="Danger looms ahead",
            subtext_confidence=0.85,
            power_position="dominant",
            pitch_behavior="low_resonant",
            emphasis_words=["never", "return"],
        )
        json_str = pd.model_dump_json()
        rehydrated = PerformanceDirection.model_validate_json(json_str)
        assert rehydrated.speaker == "Narrator"
        assert rehydrated.subtext == "Danger looms ahead"
        assert rehydrated.pitch_behavior == "low_resonant"
        assert rehydrated.emphasis_words == ["never", "return"]


class TestTimingRealizer:
    """Test suite for dynamic pause, breath, and silence realization."""

    def test_punctuation_and_ellipses_hesitation(self):
        timing = TimingRealizer.calculate_performance_timing(
            text="I thought... maybe you knew.",
            speaker="Dandelion",
        )
        assert timing["hesitation_ms"] >= 350
        assert timing["silence_type"] == "hesitation"
        assert timing["turn_taking_behavior"] == "delayed_reaction"

    def test_interruption_cutoff(self):
        timing = TimingRealizer.calculate_performance_timing(
            text="Don't you dare touch that—",
            speaker="Geralt",
            is_interruption=True,
        )
        assert timing["pause_after_ms"] <= 100
        assert timing["silence_type"] == "interruption_cut"
        assert timing["interruption_behavior"] == "abrupt_cut"

    def test_dramatic_silence_intent(self):
        timing = TimingRealizer.calculate_performance_timing(
            text="The King is dead.",
            speaker="Geralt",
            silence_intent="shock",
            tension=0.9,
            restraint=0.8,
        )
        assert timing["pause_after_ms"] >= 1500
        assert timing["silence_type"] == "dramatic_silence"

    def test_respiratory_breath_intake(self):
        # Long combat-strained sentence
        timing = TimingRealizer.calculate_performance_timing(
            text="Hold the line until the silver swords arrive and do not break formation under any circumstances!",
            speaker="Geralt",
            tension=0.85,
            physical_state="combat_strain",
        )
        assert timing["pre_roll_breath_ms"] >= 200
        assert timing["post_roll_breath_ms"] >= 150


class TestPerformanceDirector:
    """Test suite for PerformanceDirector agent logic."""

    @pytest.fixture
    def sample_bible(self, tmp_path):
        roster = {
            "characters": {
                "Geralt": {"assigned_voice_id": "Charon", "sociolect_trait": "COLD_CYNIC"},
                "Dandelion": {"assigned_voice_id": "Puck", "sociolect_trait": "THARKI_BARD"},
            }
        }
        return PerformanceBibleGenerator.generate_bible_for_project(tmp_path, roster_data=roster)

    def test_sociolect_profile_projection(self, sample_bible):
        director = PerformanceDirector(performance_bible=sample_bible)
        seg = {
            "speaker": "Geralt",
            "text": "Move along.",
            "emotion": "anger",
        }
        direction = director.direct_segment(seg)
        # COLD_CYNIC when angry delivers cold_menace with high restraint and low resonant pitch
        assert direction.surface_emotion == "cold_menace"
        assert direction.restraint >= 0.80
        assert direction.pitch_behavior == "low_resonant"
        assert direction.pace <= 0.95

    def test_anti_emotional_teleportation(self, sample_bible):
        director = PerformanceDirector(performance_bible=sample_bible)
        prev = director.direct_segment({
            "speaker": "Geralt",
            "text": "The wind is howling.",
            "emotion": "calm",
        })
        # Next line abruptly leaps to rage without dramatic causal trigger
        curr = director.direct_segment(
            {"speaker": "Geralt", "text": "I'll kill you all!", "emotion": "rage"},
            previous_direction=prev,
        )
        # Director grounds the sudden jump by enforcing suppression rather than hysterical break
        assert "suppressed" in curr.surface_emotion or curr.restraint >= 0.85
        assert curr.pitch_behavior == "low_resonant"

    def test_power_and_leverage_dynamics(self, sample_bible):
        director = PerformanceDirector(performance_bible=sample_bible)
        seg = {
            "speaker": "Dandelion",
            "text": "Please, Geralt, listen to me.",
            "leverage_holder": "Geralt",
        }
        direction = director.direct_segment(seg, target_character="Geralt")
        assert direction.power_position == "submissive"
        assert direction.leverage == "vulnerable"
        assert direction.vulnerability >= 0.50

    def test_subtext_and_social_mask(self, sample_bible):
        director = PerformanceDirector(performance_bible=sample_bible)
        seg = {
            "speaker": "Geralt",
            "text": "I am delighted to meet you, Duke.",
            "surface_emotion": "courtesy",
            "underlying_emotion": "contempt",
            "subtext": "You disgust me",
            "subtext_confidence": 0.90,
        }
        direction = director.direct_segment(seg)
        assert direction.social_mask is not None
        assert "contempt" in direction.social_mask
        assert direction.subtext == "You disgust me"
        assert direction.provenance_mode == "INFERRED_PERFORMANCE"


class TestTTSPerformanceAdapter:
    """Test suite for GeminiTTSPerformanceAdapter."""

    def test_text_sacredness_and_style_composition(self):
        adapter = GeminiTTSPerformanceAdapter()
        direction = PerformanceDirection(
            index=1,
            speaker="Geralt",
            surface_emotion="cold_menace",
            actioning="threaten",
            restraint=0.85,
            pitch_behavior="low_resonant",
            articulation="clipped",
        )
        original_dialogue = "Step back or face the blade."
        payload = adapter.adapt_direction_to_payload(original_dialogue, direction)

        # Sacred literary dialogue invariance
        assert payload["part_payload"]["text"] == original_dialogue
        # Rich multi-token speechMetadata
        style_desc = payload["part_payload"]["speechMetadata"]["style"]
        assert "cold menace" in style_desc
        assert "threaten" in style_desc
        assert "restraint" in style_desc
        assert "low resonant" in style_desc

    def test_variant_modulation(self):
        adapter = GeminiTTSPerformanceAdapter()
        direction = PerformanceDirection(
            index=2,
            speaker="Yennefer",
            surface_emotion="commanding",
            actioning="order",
        )
        p_restraint = adapter.adapt_direction_to_payload("Obey.", direction, variant_type="restraint")
        p_vulnerable = adapter.adapt_direction_to_payload("Obey.", direction, variant_type="vulnerable")

        assert "suppressed emotion" in p_restraint["style_descriptor"]
        assert "vulnerability" in p_vulnerable["style_descriptor"]
        assert p_restraint["temperature"] < p_vulnerable["temperature"]


class TestPerformanceEvaluator:
    """Test suite for 8-dimension PerformanceEvaluator."""

    def test_evaluate_clean_take(self, tmp_path):
        wav_path = create_dummy_wav(tmp_path / "take1.wav", duration_sec=1.5)
        evaluator = PerformanceEvaluator()
        direction = PerformanceDirection(
            index=1,
            speaker="Geralt",
            surface_emotion="calm",
            pace=1.0,
            restraint=0.8,
        )
        result = evaluator.evaluate_take(
            take_id="take_01",
            audio_file=wav_path,
            text="The path is clear.",
            direction=direction,
        )
        assert result.passed is True
        assert result.overall_score >= 0.70
        assert "naturalness" in result.dimensions
        assert "pacing" in result.dimensions
        assert "subtext" in result.dimensions
        assert result.dimensions["naturalness"].rating == "strong"

    def test_evaluate_missing_file_fails_closed(self, tmp_path):
        evaluator = PerformanceEvaluator()
        direction = PerformanceDirection(index=1, speaker="Geralt")
        result = evaluator.evaluate_take(
            take_id="missing_take",
            audio_file=tmp_path / "does_not_exist.wav",
            text="Hello",
            direction=direction,
        )
        assert result.passed is False
        assert result.recommendation == "regenerate"


class TestTakeBankAndSelector:
    """Test suite for TakeBank and IntelligentTakeSelector."""

    def test_take_bank_priority_allocation(self, tmp_path):
        bank = TakeBank(tmp_path / "takes")
        pd_climactic = PerformanceDirection(index=1, speaker="Geralt", performance_priority="climactic")
        variants = bank.get_candidate_variants(pd_climactic)
        assert len(variants) == 4
        assert variants == ["standard", "restraint", "vulnerable", "exposed"]

    def test_intelligent_take_selection_with_explainability(self, tmp_path):
        bank = TakeBank(tmp_path / "takes")
        evaluator = PerformanceEvaluator()
        selector = IntelligentTakeSelector(evaluator=evaluator)

        direction = PerformanceDirection(
            index=1,
            speaker="Geralt",
            surface_emotion="cold_menace",
            restraint=0.85,
            target_character="Bandit",
        )

        w1 = create_dummy_wav(tmp_path / "take_standard.wav", duration_sec=1.2, amplitude=2000)
        w2 = create_dummy_wav(tmp_path / "take_restraint.wav", duration_sec=1.4, amplitude=1500)

        t1 = bank.create_take("s0001", 1, "standard", w1, direction)
        t2 = bank.create_take("s0001", 1, "restraint", w2, direction)

        chosen = selector.select_best_take([t1, t2], "Step aside.", direction)
        assert chosen.is_selected is True
        assert chosen.selection_reason != ""
        assert "Selected Take" in chosen.selection_reason
        assert any(t.is_selected is False for t in [t1, t2])


class TestConversationalChemistry:
    """Test suite for ConversationalChemistry."""

    def test_interruption_coupling(self):
        d1 = PerformanceDirection(
            index=1,
            speaker="Dandelion",
            text="I was only trying to—",
            interruption_behavior="abrupt_cut",
            silence_type="interruption_cut",
        )
        d2 = PerformanceDirection(
            index=2,
            speaker="Geralt",
            text="Be silent.",
            pause_before_ms=400,
        )
        coupled = ConversationalChemistry.apply_conversational_chemistry([d1, d2])
        # Speaker B cuts in immediately with zero onset delay
        assert coupled[1].pause_before_ms == 0
        assert coupled[1].turn_taking_behavior == "immediate"

    def test_threat_reaction_coupling(self):
        d1 = PerformanceDirection(
            index=1,
            speaker="Geralt",
            actioning="threaten",
            power_position="dominant",
        )
        d2 = PerformanceDirection(
            index=2,
            speaker="Merchant",
            power_position="submissive",
        )
        coupled = ConversationalChemistry.apply_conversational_chemistry([d1, d2])
        assert coupled[1].turn_taking_behavior == "delayed_reaction"
        assert coupled[1].pause_before_ms >= 600


class TestPerformanceContinuityTracker:
    """Test suite for PerformanceContinuityTracker."""

    def test_tracking_and_drift_detection(self):
        tracker = PerformanceContinuityTracker()
        # Seed 5 established baseline directions
        for _ in range(5):
            tracker.record_direction(PerformanceDirection(index=1, speaker="Geralt", pace=1.0, energy=0.75))

        assert tracker.characters["Geralt"].average_pace == 1.0

        # Scene with drastic 40% pace drift
        drift_directions = [
            PerformanceDirection(index=6, speaker="Geralt", pace=1.45),
            PerformanceDirection(index=7, speaker="Geralt", pace=1.40),
        ]
        warnings = tracker.audit_scene_continuity(drift_directions)
        assert len(warnings) >= 1
        assert "Performance Drift Alert" in warnings[0]


class TestPerformanceFidelityGate:
    """Test suite for Gate 2.8 Pre-Mix Performance Fidelity Gate."""

    def test_gate_passes_clean_report(self, tmp_path):
        w = create_dummy_wav(tmp_path / "t1.wav")
        d1 = PerformanceDirection(index=1, speaker="Geralt", surface_emotion="calm")
        t1 = TakeVariant(
            take_id="t1",
            segment_uid=d1.segment_uid,
            segment_index=1,
            audio_path=str(w),
            direction=d1,
            is_selected=True,
            selection_reason="Optimal delivery",
        )
        evaluator = PerformanceEvaluator()
        t1.evaluation = evaluator.evaluate_take("t1", w, "Clear path.", d1)

        res = audit_gate2_8_performance_fidelity(
            chapter_id="chapter_001",
            directions=[d1],
            selected_takes=[t1],
        )
        assert res["status"] == "PASS"
        assert res["total_segments"] == 1
        assert res["violations"] == 0

    def test_gate_fails_closed_on_teleportation(self, tmp_path):
        w = create_dummy_wav(tmp_path / "t1.wav")
        d1 = PerformanceDirection(index=1, speaker="Geralt", surface_emotion="calm")
        d2 = PerformanceDirection(index=2, speaker="Geralt", surface_emotion="bellowing_rage")
        t1 = TakeVariant(take_id="t1", segment_uid=d1.segment_uid, segment_index=1, audio_path=str(w), direction=d1, is_selected=True)
        t2 = TakeVariant(take_id="t2", segment_uid=d2.segment_uid, segment_index=2, audio_path=str(w), direction=d2, is_selected=True)

        with pytest.raises(GateAuditError, match="Gate 2.8 Performance Fidelity Failed"):
            audit_gate2_8_performance_fidelity(
                chapter_id="chapter_001",
                directions=[d1, d2],
                selected_takes=[t1, t2],
            )


class TestEndToEndPerformancePipeline:
    """Full lifecycle integration test: ScreenplaySegment -> Direction -> Multi-Take -> QC -> Gate 2.8 -> Cinema Stems."""

    def test_end_to_end_performance_lifecycle(self, tmp_path):
        from audiobook_factory.contracts import LegacyCreativeManifestAdapter, CreativeManifest, AmbienceScene
        from audiobook_factory.cinema_audio_engine import CinemaAudioManifest

        # 1. Screenplay segments
        segments = [
            ScreenplaySegment(
                index=1,
                speaker="Geralt",
                text="Put the steel down.",
                emotion="anger",
                character_objective="disarm threat",
                actioning="intimidate",
                subtext="I don't want to slaughter you all",
                subtext_confidence=0.88,
                performance_priority="climactic",
            ),
            ScreenplaySegment(
                index=2,
                speaker="Bandit",
                text="We outnumber you, witcher—",
                emotion="defiance",
                is_interruption=True,
                performance_priority="focused",
            ),
        ]

        # 2. Performance Director
        roster = {"characters": {"Geralt": {"sociolect_trait": "COLD_CYNIC"}}}
        pb = PerformanceBibleGenerator.generate_bible_for_project(tmp_path, roster_data=roster)
        director = PerformanceDirector(performance_bible=pb)
        directions = director.direct_chapter_script([s.model_dump() for s in segments])
        directions = ConversationalChemistry.apply_conversational_chemistry(directions)

        assert len(directions) == 2
        assert directions[0].surface_emotion == "cold_menace"
        assert directions[0].required_takes == 3  # climactic
        assert directions[1].silence_type == "interruption_cut"

        # 3. Take Bank & Synthetic Audio Generation
        bank = TakeBank(tmp_path / "takes")
        evaluator = PerformanceEvaluator()
        selector = IntelligentTakeSelector(evaluator=evaluator)

        selected_takes = []
        for d, s in zip(directions, segments):
            variants = bank.get_candidate_variants(d)
            cand_takes = []
            for v in variants:
                wav_file = create_dummy_wav(tmp_path / f"take_{d.index}_{v}.wav", duration_sec=1.2)
                t = bank.create_take(d.segment_uid, d.index, v, wav_file, d)
                cand_takes.append(t)
            winning = selector.select_best_take(cand_takes, s.text, d)
            selected_takes.append(winning)

        assert len(selected_takes) == 2
        assert all(t.is_selected for t in selected_takes)

        # 4. Gate 2.8 Audit
        gate_res = audit_gate2_8_performance_fidelity(
            chapter_id="chapter_001",
            directions=directions,
            selected_takes=selected_takes,
        )
        assert gate_res["status"] == "PASS"
        assert gate_res["violations"] == 0

        # 5. Cinema Audio Engine Compatibility
        legacy_manifest = CreativeManifest(
            chapter_id="chapter_001",
            silence_percentage=80.0,
            ambience_scenes=[
                AmbienceScene(
                    scene_id=1,
                    start_ms=0,
                    end_ms=5000,
                    asset_path="wind_howl.ogg",
                )
            ],
        )
        cinema_man = LegacyCreativeManifestAdapter.lift_legacy_manifest_to_cinema(legacy_manifest)
        assert isinstance(cinema_man, CinemaAudioManifest)
        assert cinema_man.chapter_id == "chapter_001"

