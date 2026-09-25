#!/usr/bin/env python3
"""
Audiobook Factory - Regression Test Suite for Alignment & Take Selection Fixes.
Validates:
1. align_batch_detailed() returns explicit fallback provenance without fake MMS_FA or 0.88 confidence.
2. Evaluator never defaults missing alignment to confidence=1.0 (defaults to None with diagnostic).
3. Real AlignmentResult propagates accurately into PerformanceEvidence.
4. Low alignment confidence (< 0.35) or critical alignment diagnostics fail hard gates.
5. Single candidate take audits ALL 3 hard gates (technical, alignment, voice drift) and evaluation score.
6. Single candidate with any defect is flagged with review_required=True and degraded confidence.
7. Pristine single candidate passes cleanly with review_required=False and confidence=1.0.
8. Take selector automatically aligns unaligned takes when equipped with an aligner.
"""

from __future__ import annotations
import math
import wave
import tempfile
import numpy as np
from pathlib import Path
import pytest

from audiobook_factory.contracts import ScreenplaySegment
from audiobook_factory.alignment_contracts import (
    AlignmentResult,
    WordAlignment,
    SpeechRegion,
    AlignmentDiagnostic,
    AlignmentCalibrationConfig,
)
from audiobook_factory.forced_aligner import WorkstationForcedAligner
from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    TakeVariant,
    TakeSelectionResult,
    TakeSelectorCalibrationConfig,
    PerformanceEvaluationResult,
    EvaluationDimensionScore,
)
from audiobook_factory.performance.evaluator import PerformanceEvaluator
from audiobook_factory.performance.take_selector import IntelligentTakeSelector


def create_waveform_file(
    filepath: Path,
    duration_sec: float = 2.0,
    sample_rate: int = 24000,
    f0_hz: float = 150.0,
    amplitude: float = 0.5,
    pitch_mod_depth: float = 10.0,
    pitch_mod_freq: float = 4.0,
    is_clipped: bool = False,
    dc_bias: float = 0.0,
    trailing_silence_sec: float = 0.0,
) -> Path:
    """Creates deterministic test audio WAV with configurable parameters."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    num_speech_samples = int(sample_rate * duration_sec)
    t = np.arange(num_speech_samples) / float(sample_rate)

    instantaneous_f0 = f0_hz + pitch_mod_depth * np.sin(2 * np.pi * pitch_mod_freq * t)
    phase = 2 * np.pi * np.cumsum(instantaneous_f0) / sample_rate
    signal = np.sin(phase) + 0.3 * np.sin(2 * phase)

    raw_samples = (signal * amplitude * 28000.0) + dc_bias
    if is_clipped:
        raw_samples[:40] = 32767.0

    speech_samples = raw_samples.clip(-32767, 32767).astype(np.int16)

    if trailing_silence_sec > 0:
        silence_samples = np.zeros(int(sample_rate * trailing_silence_sec), dtype=np.int16)
        samples = np.concatenate([speech_samples, silence_samples])
    else:
        samples = speech_samples

    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())

    return filepath


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def evaluator():
    return PerformanceEvaluator(sample_rate=24000)


@pytest.fixture
def selector(evaluator):
    return IntelligentTakeSelector(evaluator=evaluator)


class TestAlignmentAndTakeSelectionFixes:

    # 1. Fallback honesty in align_batch_detailed()
    def test_01_align_batch_detailed_fallback_provenance(self, temp_dir):
        """align_batch_detailed() must return honest fallback without fake 0.88 or fake mms_fa_ctc."""
        wav = create_waveform_file(temp_dir / "batch_test.wav", duration_sec=3.0)
        aligner = WorkstationForcedAligner(use_cuda=False)
        aligner._lazy_init = lambda: False  # Force energy fallback mode

        segments = [
            ScreenplaySegment(index=1, text="The moonlight filtered through ancient pines."),
            ScreenplaySegment(index=2, text="A cold wind stirred the embers."),
        ]

        results = aligner.align_batch_detailed(wav, segments)
        assert len(results) == 2

        for res in results:
            # Fallback must be explicit
            assert res.method == "energy_fallback"
            assert res.confidence <= 0.50
            assert res.confidence != 0.88  # Never fabricate 0.88
            assert res.confidence_category == "LOW"
            assert any(d.code == "FALLBACK_ALIGNMENT" for d in res.diagnostics)

            # Words must have fallback provenance
            assert len(res.words) > 0
            for w in res.words:
                assert w.source == "energy_proportional"
                assert w.source != "mms_fa_ctc"
                assert w.confidence <= 0.50
                assert w.pronunciation_status == "fallback"

    def test_01b_align_batch_detailed_mms_when_available(self, temp_dir):
        """align_batch_detailed() with real MMS_FA must extract real word token spans and not fake 0.88."""
        wav = create_waveform_file(temp_dir / "batch_mms.wav", duration_sec=3.0)
        aligner = WorkstationForcedAligner(use_cuda=False)
        if not aligner._lazy_init():
            pytest.skip("TorchAudio MMS_FA not available in environment")

        segments = [
            ScreenplaySegment(index=1, text="The moonlight filtered through ancient pines."),
            ScreenplaySegment(index=2, text="A cold wind stirred the embers."),
        ]

        results = aligner.align_batch_detailed(wav, segments)
        assert len(results) == 2
        for res in results:
            assert res.method == "mms_fa_ctc"
            assert len(res.words) > 0
            for w in res.words:
                assert w.source == "mms_fa_ctc"
                assert w.start_ms >= 0
                assert w.end_ms > w.start_ms

    # 2. Never default missing alignment to confidence=1.0
    def test_02_missing_alignment_not_defaulted_to_perfect(self, temp_dir, evaluator):
        """Evaluator without alignment_result must set alignment_confidence to None and record unverified diagnostic."""
        wav = create_waveform_file(temp_dir / "eval_no_align.wav", duration_sec=2.0)
        pd = PerformanceDirection(index=1, speaker="Narrator", surface_emotion="neutral")

        res = evaluator.evaluate_take(
            take_id="take_no_align",
            audio_file=wav,
            text="The mist shrouded the distant valley.",
            direction=pd,
            alignment_result=None,
        )

        assert res.evidence is not None
        assert res.evidence.alignment_confidence is None  # NEVER 1.0
        assert any("unverified" in d.lower() for d in res.evidence.alignment_diagnostics)
        assert any("[ALIGNMENT]" in d for d in res.diagnostics)

    # 3. Real AlignmentResult propagates accurately to evidence
    def test_03_alignment_result_propagates_to_evidence(self, temp_dir, evaluator):
        """Passing real AlignmentResult properly populates alignment_confidence and diagnostics in evidence."""
        wav = create_waveform_file(temp_dir / "eval_real_align.wav", duration_sec=2.0)
        pd = PerformanceDirection(index=1, speaker="Narrator", surface_emotion="neutral")

        align_res = AlignmentResult(
            segment_uid="seg_01",
            confidence=0.92,
            confidence_category="HIGH",
            method="mms_fa_ctc",
            diagnostics=[
                AlignmentDiagnostic(code="ALIGNMENT_OK", severity="INFO", message="High-quality phonetic alignment")
            ],
        )

        res = evaluator.evaluate_take(
            take_id="take_real_align",
            audio_file=wav,
            text="The mist shrouded the distant valley.",
            direction=pd,
            alignment_result=align_res,
        )

        assert res.evidence is not None
        assert res.evidence.alignment_confidence == 0.92
        assert "High-quality phonetic alignment" in res.evidence.alignment_diagnostics

    # 4. Low alignment confidence fails evaluation and hard gate
    def test_04_low_confidence_alignment_fails_gate_and_disqualifies(self, temp_dir, evaluator, selector):
        """Take with alignment confidence < 0.35 fails hard gate and is disqualified against good candidate."""
        wav_bad = create_waveform_file(temp_dir / "take_bad_align.wav", duration_sec=2.0)
        wav_good = create_waveform_file(temp_dir / "take_good_align.wav", duration_sec=2.0)
        pd = PerformanceDirection(index=1, speaker="SpeakerA", surface_emotion="neutral")

        bad_align = AlignmentResult(
            segment_uid="seg_01",
            confidence=0.22,  # Below 0.35 hard gate
            confidence_category="FAILED_REVIEW_REQUIRED",
            method="mms_fa_ctc",
            diagnostics=[
                AlignmentDiagnostic(code="INSUFFICIENT_SPEECH", severity="CRITICAL", message="Muffled audio with dropped tokens")
            ],
        )
        good_align = AlignmentResult(
            segment_uid="seg_01",
            confidence=0.88,
            confidence_category="HIGH",
            method="mms_fa_ctc",
            diagnostics=[
                AlignmentDiagnostic(code="ALIGNMENT_OK", severity="INFO", message="Acoustic alignment verified")
            ],
        )

        t_bad = TakeVariant(
            take_id="take_bad",
            segment_uid="seg_01",
            segment_index=1,
            variant_type="standard",
            audio_path=str(wav_bad),
            duration_sec=2.0,
            direction=pd,
            alignment_result=bad_align,
        )
        t_good = TakeVariant(
            take_id="take_good",
            segment_uid="seg_01",
            segment_index=1,
            variant_type="vulnerable",
            audio_path=str(wav_good),
            duration_sec=2.0,
            direction=pd,
            alignment_result=good_align,
        )

        result = selector.select_take_with_result(
            takes=[t_bad, t_good],
            text="Step forward into the light.",
            direction=pd,
        )

        assert result.winner.take_id == "take_good"
        assert t_bad.is_selected is False
        assert "Disqualified by Hard Gate" in t_bad.selection_reason
        assert "Alignment failure" in t_bad.selection_reason

    # 5. Single take with alignment failure flags review_required
    def test_05_single_take_with_alignment_failure_flags_review_required(self, temp_dir, selector):
        """Solitary take with failing alignment confidence fails hard gate, flags review_required=True, and drops confidence."""
        wav = create_waveform_file(temp_dir / "single_bad_align.wav", duration_sec=2.0)
        pd = PerformanceDirection(index=1, speaker="SpeakerA", surface_emotion="neutral")

        bad_align = AlignmentResult(
            segment_uid="seg_single",
            confidence=0.20,
            confidence_category="FAILED_REVIEW_REQUIRED",
            method="mms_fa_ctc",
            diagnostics=[
                AlignmentDiagnostic(code="TEXT_AUDIO_MISMATCH", severity="CRITICAL", message="Phonetic token loss")
            ],
        )

        sole_take = TakeVariant(
            take_id="take_sole_bad",
            segment_uid="seg_single",
            segment_index=1,
            variant_type="standard",
            audio_path=str(wav),
            duration_sec=2.0,
            direction=pd,
            alignment_result=bad_align,
        )

        result = selector.select_take_with_result(
            takes=[sole_take],
            text="Do not look back.",
            direction=pd,
        )

        assert result.winner.take_id == "take_sole_bad"
        assert result.review_required is True
        assert result.confidence <= 0.35
        assert result.evidence["gate_passed"] is False
        assert any("Alignment failure" in r or "Critical alignment failure" in r for r in result.evidence["gate_reasons"])
        assert "HARD GATE FAILURE" in result.winner.selection_reason

    # 6. Single take with voice drift flags review_required
    def test_06_single_take_with_voice_drift_flags_review_required(self, temp_dir, selector):
        """Solitary take with catastrophic voice drift fails voice hard gate, flags review_required=True, and drops confidence."""
        wav = create_waveform_file(temp_dir / "single_drift.wav", duration_sec=2.0)
        pd = PerformanceDirection(index=1, speaker="SpeakerA", surface_emotion="neutral")

        dim_strong = EvaluationDimensionScore(dimension="naturalness", score=0.85, rating="strong", rationale="Clean audio")
        eval_drift = PerformanceEvaluationResult(
            take_id="take_drift",
            segment_uid="seg_drift",
            overall_score=0.45,
            passed=False,
            dimensions={"naturalness": dim_strong},
            diagnostics=["Catastrophic timbre divergence"],
            recommendation="regenerate",
            voice_identity_score=0.30,
            voice_drift_detected=True,
        )

        sole_take = TakeVariant(
            take_id="take_drift",
            segment_uid="seg_drift",
            segment_index=1,
            variant_type="standard",
            audio_path=str(wav),
            duration_sec=2.0,
            direction=pd,
            evaluation=eval_drift,
        )

        result = selector.select_take_with_result(
            takes=[sole_take],
            text="The shadows were creeping closer.",
            direction=pd,
        )

        assert result.winner.take_id == "take_drift"
        assert result.review_required is True
        assert result.confidence <= 0.35
        assert result.evidence["gate_passed"] is False
        assert any("voice drift" in r.lower() for r in result.evidence["gate_reasons"])

    # 7. Single take with poor performance score flags review_required
    def test_07_single_take_with_poor_performance_flags_review_required(self, temp_dir, selector):
        """Solitary take that passes technical gates but fails performance evaluation flags review_required=True."""
        wav = create_waveform_file(temp_dir / "single_poor_perf.wav", duration_sec=2.0)
        pd = PerformanceDirection(index=1, speaker="SpeakerA", surface_emotion="neutral")

        dim_weak = EvaluationDimensionScore(dimension="naturalness", score=0.50, rating="weak", rationale="Robotic vocoder artifacts")
        eval_poor = PerformanceEvaluationResult(
            take_id="take_poor",
            segment_uid="seg_poor",
            overall_score=0.55,
            passed=False,  # Failed evaluation standards
            dimensions={"naturalness": dim_weak},
            diagnostics=["[NATURALNESS] Robotic vocoder artifacts"],
            recommendation="regenerate",
        )

        sole_take = TakeVariant(
            take_id="take_poor",
            segment_uid="seg_poor",
            segment_index=1,
            variant_type="standard",
            audio_path=str(wav),
            duration_sec=2.0,
            direction=pd,
            evaluation=eval_poor,
        )

        result = selector.select_take_with_result(
            takes=[sole_take],
            text="We must make camp before nightfall.",
            direction=pd,
        )

        assert result.winner.take_id == "take_poor"
        assert result.review_required is True
        assert result.confidence <= 0.35
        assert result.evidence["eval_passed"] is False
        assert "EVALUATION DEFECTS" in result.winner.selection_reason

    # 8. Pristine single take passes cleanly
    def test_08_single_take_pristine_passes_cleanly(self, temp_dir, evaluator, selector):
        """Pristine single candidate with verified alignment and high score passes cleanly without review required."""
        wav = create_waveform_file(temp_dir / "single_pristine.wav", duration_sec=2.0)
        pd = PerformanceDirection(index=1, speaker="SpeakerA", surface_emotion="neutral")

        pristine_align = AlignmentResult(
            segment_uid="seg_clean",
            confidence=0.90,
            confidence_category="HIGH",
            method="mms_fa_ctc",
            diagnostics=[
                AlignmentDiagnostic(code="ALIGNMENT_OK", severity="INFO", message="Clean alignment")
            ],
        )

        sole_take = TakeVariant(
            take_id="take_clean",
            segment_uid="seg_clean",
            segment_index=1,
            variant_type="standard",
            audio_path=str(wav),
            duration_sec=2.0,
            direction=pd,
            alignment_result=pristine_align,
        )

        result = selector.select_take_with_result(
            takes=[sole_take],
            text="The sky was clear and full of stars.",
            direction=pd,
        )

        assert result.winner.take_id == "take_clean"
        assert result.review_required is False
        assert result.confidence == 1.0
        assert result.evidence["gate_passed"] is True
        assert result.evidence["eval_passed"] is True
        assert "satisfies performance and technical standards" in result.winner.selection_reason

    # 9. Take selector auto-aligns unaligned takes
    def test_09_take_selector_auto_aligns_unaligned_takes(self, temp_dir, evaluator):
        """IntelligentTakeSelector equipped with aligner automatically aligns takes lacking alignment results."""
        wav = create_waveform_file(temp_dir / "auto_align.wav", duration_sec=2.0)
        pd = PerformanceDirection(index=1, speaker="SpeakerA", surface_emotion="neutral")

        aligner = WorkstationForcedAligner(use_cuda=False)
        aligner._lazy_init = lambda: False  # Use acoustic fallback

        selector = IntelligentTakeSelector(evaluator=evaluator, aligner=aligner)

        take = TakeVariant(
            take_id="take_auto",
            segment_uid="seg_auto",
            segment_index=1,
            variant_type="standard",
            audio_path=str(wav),
            duration_sec=2.0,
            direction=pd,
            alignment_result=None,  # Not aligned yet
        )

        result = selector.select_take_with_result(
            takes=[take],
            text="There is nothing to fear.",
            direction=pd,
        )

        # Take must have been automatically aligned
        assert take.alignment_result is not None
        assert take.evaluation is not None
        assert take.evaluation.evidence.alignment_confidence is not None
        assert take.alignment_result.method == "energy_fallback"
