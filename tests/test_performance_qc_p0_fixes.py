#!/usr/bin/env python3
"""
Regression test suite for Performance QC 2.0 P0 integration fixes:
1. PerceptualPerformanceJudge wiring into evaluation and EvidenceFusion Layer 8.
2. Authoritative EvidenceFusionEngine in multi-take candidate selection.
3. Single-take status precedence (preventing override of REGENERATE/REVIEW/NO_ACCEPTABLE_TAKE to ACCEPT).
4. Scene-level NO_ACCEPTABLE_TAKE handling (no None appended, safe chemistry & continuity, fail-closed gate).
"""

import math
import struct
import wave
import tempfile
from pathlib import Path
import pytest

from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    TakeVariant,
    PerformanceEvidence,
    PerceptualPerformanceEvidence,
    EvaluationDimensionScore,
    PerformanceEvaluationResult,
    TakeSelectorCalibrationConfig,
    EvidenceFusionCalibrationConfig,
)
from audiobook_factory.performance.perceptual_judge import (
    PerceptualPerformanceJudge,
    PerceptualJudgeConfig,
)
from audiobook_factory.performance.evaluator import PerformanceEvaluator
from audiobook_factory.performance.evidence_fusion import EvidenceFusionEngine
from audiobook_factory.performance.take_selector import IntelligentTakeSelector
from audiobook_factory.performance.gate import PerformanceFidelityGate
from audiobook_factory.performance.continuity import PerformanceContinuityTracker


def _create_synthetic_wav(
    filepath: Path,
    duration_sec: float = 1.0,
    framerate: int = 24000,
    freq: float = 220.0,
    amplitude: float = 12000.0,
) -> Path:
    """Helper to generate a clean mono PCM WAV file."""
    total_frames = int(duration_sec * framerate)
    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        samples = bytearray()
        for i in range(total_frames):
            val = int(amplitude * math.sin(2.0 * math.pi * freq * (i / framerate)))
            val = max(-32768, min(32767, val))
            samples.extend(struct.pack("<h", val))
        wf.writeframes(samples)
    return filepath


class TestPerformanceQCP0Fixes:

    def test_fix1_perceptual_judge_wired_into_evaluator_and_fusion(self, tmp_path):
        """Fix 1: Evaluator populates evidence.perceptual, properties work, and Fusion consumes Layer 8."""
        wav_path = _create_synthetic_wav(tmp_path / "test_fix1.wav", duration_sec=1.0)
        direction = PerformanceDirection(
            speaker="Alice",
            index=1,
            surface_emotion="fear",
            intensity="explosive",
            actioning="threaten",
            restraint=0.3,
        )
        text = "Get back right now!"

        evaluator = PerformanceEvaluator(sample_rate=24000)
        assert evaluator.perceptual_judge is not None

        eval_res = evaluator.evaluate_take(
            take_id="take_f1",
            audio_file=wav_path,
            text=text,
            direction=direction,
        )

        assert eval_res.evidence is not None
        assert eval_res.evidence.perceptual is not None
        perceptual = eval_res.evidence.perceptual
        assert isinstance(perceptual, PerceptualPerformanceEvidence)

        # Check that all 8 dimension properties exist and return EvaluationDimensionScore
        assert isinstance(perceptual.naturalness, EvaluationDimensionScore)
        assert isinstance(perceptual.acting_believability, EvaluationDimensionScore)
        assert isinstance(perceptual.emotional_fidelity, EvaluationDimensionScore)
        assert isinstance(perceptual.intent_fidelity, EvaluationDimensionScore)
        assert isinstance(perceptual.subtext_fidelity, EvaluationDimensionScore)
        assert isinstance(perceptual.prosodic_fit, EvaluationDimensionScore)
        assert isinstance(perceptual.scene_fit, EvaluationDimensionScore)
        assert isinstance(perceptual.dialogue_reactivity, EvaluationDimensionScore)

        # Check Layer 8 evaluation consumes it without error
        take = TakeVariant(
            take_id="take_f1",
            segment_uid="seg_001",
            segment_index=1,
            variant_type="standard",
            audio_path=str(wav_path),
            duration_sec=1.0,
            evaluation=eval_res,
            direction=direction,
        )

        fusion_engine = EvidenceFusionEngine()
        l8_passed, l8_score, l8_conf, l8_reasons, l8_codes = fusion_engine.evaluate_layer8_perceptual(take)
        assert 0.0 <= l8_score <= 1.0
        assert 0.0 <= l8_conf <= 1.0

        fusion_res = fusion_engine.fuse_take(take, text, direction)
        assert "layer8_perceptual" in fusion_res.layer_passed
        assert fusion_res.fused_score > 0.0

    def test_fix2_authoritative_evidence_fusion_in_candidate_selection(self, tmp_path):
        """Fix 2: fuse_candidate_pool drives candidate qualification and authoritative status."""
        good_wav = _create_synthetic_wav(tmp_path / "good.wav", duration_sec=1.2, amplitude=15000.0)
        # Create a clipped corrupt wav that fails Layer 1 technical gate
        clipped_wav = tmp_path / "clipped.wav"
        with wave.open(str(clipped_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            # 100 pinned clipped samples
            samples = bytearray()
            for _ in range(24000):
                samples.extend(struct.pack("<h", 32767))
            wf.writeframes(samples)

        direction = PerformanceDirection(speaker="Bob", index=2, surface_emotion="neutral")
        text = "Hello there."

        evaluator = PerformanceEvaluator(sample_rate=24000)
        ev_good = evaluator.evaluate_take("take_good", good_wav, text, direction)
        ev_bad = evaluator.evaluate_take("take_bad", clipped_wav, text, direction)

        take_good = TakeVariant(
            take_id="take_good",
            segment_uid="seg_002",
            segment_index=2,
            variant_type="standard",
            audio_path=str(good_wav),
            duration_sec=1.2,
            evaluation=ev_good,
            direction=direction,
        )
        take_bad = TakeVariant(
            take_id="take_bad",
            segment_uid="seg_002",
            segment_index=2,
            variant_type="alternative_cadence",
            audio_path=str(clipped_wav),
            duration_sec=1.0,
            evaluation=ev_bad,
            direction=direction,
        )

        selector = IntelligentTakeSelector(evaluator=evaluator)
        result = selector.select_take_with_result(
            takes=[take_bad, take_good],
            text=text,
            direction=direction,
        )

        assert result.winner is not None
        assert result.winner.take_id == "take_good"
        assert result.status in ("ACCEPT", "ACCEPT_WITH_WARNING")
        # take_bad must be disqualified by EvidenceFusion hard gate
        assert take_bad.is_selected is False
        assert "Disqualified by Hard Gate" in take_bad.selection_reason

    def test_fix3_single_take_status_precedence(self, tmp_path):
        """Fix 3: When EvidenceFusion returns REGENERATE or REVIEW, single-take selector must not override to ACCEPT."""
        clipped_wav = tmp_path / "single_clipped.wav"
        with wave.open(str(clipped_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            samples = bytearray()
            for _ in range(24000):
                samples.extend(struct.pack("<h", 32767))
            wf.writeframes(samples)

        direction = PerformanceDirection(speaker="Charlie", index=3, surface_emotion="neutral")
        text = "Testing single take clipping."

        evaluator = PerformanceEvaluator(sample_rate=24000)
        ev_clipped = evaluator.evaluate_take("take_single_bad", clipped_wav, text, direction)

        take_single = TakeVariant(
            take_id="take_single_bad",
            segment_uid="seg_003",
            segment_index=3,
            variant_type="standard",
            audio_path=str(clipped_wav),
            duration_sec=1.0,
            evaluation=ev_clipped,
            direction=direction,
        )

        selector = IntelligentTakeSelector(evaluator=evaluator)
        result = selector.select_take_with_result(
            takes=[take_single],
            text=text,
            direction=direction,
        )

        # Precedence check: must NOT be ACCEPT!
        assert result.status != "ACCEPT"
        assert result.status in ("REGENERATE", "REVIEW", "NO_ACCEPTABLE_TAKE")
        assert result.review_required is True
        assert take_single.is_selected is False
        assert "HARD GATE FAILURE" in take_single.selection_reason

    def test_fix4_scene_level_no_acceptable_take_handling(self, tmp_path):
        """Fix 4: Scene selection never appends None, protects chemistry & continuity, and fails gate closed."""
        clipped_wav = tmp_path / "scene_clipped.wav"
        with wave.open(str(clipped_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            samples = bytearray()
            for _ in range(24000):
                samples.extend(struct.pack("<h", 32767))
            wf.writeframes(samples)

        good_wav = _create_synthetic_wav(tmp_path / "scene_good.wav", duration_sec=1.5)

        dir_1 = PerformanceDirection(speaker="Hero", index=1, surface_emotion="neutral", energy=0.7)
        dir_2 = PerformanceDirection(speaker="Villain", index=2, surface_emotion="menacing", energy=0.85)

        evaluator = PerformanceEvaluator(sample_rate=24000)
        ev_clipped = evaluator.evaluate_take("take_fail", clipped_wav, "Defective line", dir_1)
        ev_good = evaluator.evaluate_take("take_ok", good_wav, "Good response", dir_2)

        take_failing_cand = TakeVariant(
            take_id="take_fail",
            segment_uid="seg_001",
            segment_index=1,
            variant_type="standard",
            audio_path=str(clipped_wav),
            duration_sec=1.0,
            evaluation=ev_clipped,
            direction=dir_1,
        )
        take_good_cand = TakeVariant(
            take_id="take_ok",
            segment_uid="seg_002",
            segment_index=2,
            variant_type="standard",
            audio_path=str(good_wav),
            duration_sec=1.5,
            evaluation=ev_good,
            direction=dir_2,
        )

        selector = IntelligentTakeSelector(
            evaluator=evaluator,
            config=TakeSelectorCalibrationConfig(allow_degraded_winner=False),
        )
        continuity = PerformanceContinuityTracker()

        scene_takes = [
            [take_failing_cand],  # Segment 1 will result in NO_ACCEPTABLE_TAKE
            [take_good_cand],     # Segment 2 is normal
        ]
        directions = [dir_1, dir_2]
        texts = ["Defective line", "Good response"]

        # Crucial test: select_scene_takes must NOT raise AttributeError or append None!
        selected = selector.select_scene_takes(
            scene_takes=scene_takes,
            directions=directions,
            texts=texts,
            continuity_tracker=continuity,
        )

        assert len(selected) == 2
        assert None not in selected
        assert selected[0] is not None
        assert selected[0].is_selected is False  # Degraded fallback explicitly unselected
        assert selected[0].selection_result.status in ("NO_ACCEPTABLE_TAKE", "REGENERATE", "REVIEW")
        assert selected[1] is not None
        assert selected[1].is_selected is True

        # Pre-mix Fidelity Gate test: Gate must fail closed and identify the unselected take
        gate_report = PerformanceFidelityGate.audit_chapter_performance(
            chapter_id="c001",
            directions=directions,
            selected_takes=selected,
        )
        assert gate_report.passed is False
        assert any("NO ACCEPTABLE TAKE" in issue or "Critical defect" in issue or "No selected take" in issue for issue in gate_report.unresolved_issues)
