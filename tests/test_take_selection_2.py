#!/usr/bin/env python3
"""
Audiobook Factory - Wave C Take Selection 2.0 Test Suite.
Validates:
1. Stage 1-3 Hard Gates: Technical audio integrity (clipping, DC bias, duration, dead air),
   alignment confidence gate, catastrophic voice drift defense.
2. Stage 4 Context-Aware Scoring: Exposition vs Climax vs Whisper weighting.
3. Stage 5 Pairwise Take Judging: Acoustic evidence deliberation for restraint and dramatic pauses.
4. Stage 6 TakeSelectionResult Contract: Explainable reason codes, runner-up provenance, and review flags.
5. Isolated Calibration Configurability: Dynamic threshold overrides.
"""

import math
import wave
import struct
import tempfile
from pathlib import Path
import pytest
import numpy as np

from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    TakeVariant,
    PerformanceEvaluationResult,
    EvaluationDimensionScore,
    TakeSelectionResult,
    TakeSelectorCalibrationConfig,
    PerformanceEvidence,
    AcousticEvidence,
    ProsodyEvidence,
    PacingEvidence,
)
from audiobook_factory.performance.evaluator import PerformanceEvaluator
from audiobook_factory.performance.take_selector import IntelligentTakeSelector, PairwiseTakeJudge
from audiobook_factory.identity.reference_bank import AcousticSignature


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
        raw_samples[:40] = 32767.0  # 40 consecutive pinned samples

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


class TestTakeSelection2Suite:
    """Comprehensive test matrix for Wave C Take Selection 2.0."""

    @pytest.fixture(autouse=True)
    def setup_suite(self, tmp_path):
        self.tmp_dir = tmp_path
        self.takes_dir = self.tmp_dir / "takes"
        self.takes_dir.mkdir(parents=True, exist_ok=True)
        self.evaluator = PerformanceEvaluator()
        self.selector = IntelligentTakeSelector(evaluator=self.evaluator)

    def test_01_technical_hard_gate_rejects_clipping(self):
        """Verifies candidate with pinned clipping >= 12 samples is disqualified by hard gate."""
        pd = PerformanceDirection(
            index=1,
            speaker="Narrator",
            intensity="medium",
            surface_emotion="neutral",
        )

        clean_wav = create_waveform_file(self.takes_dir / "t1_clean.wav", duration_sec=1.5, is_clipped=False)
        clipped_wav = create_waveform_file(self.takes_dir / "t1_clipped.wav", duration_sec=1.5, is_clipped=True)

        take_clean = TakeVariant(
            take_id="t1_clean",
            segment_uid="seg_01",
            segment_index=1,
            variant_type="standard",
            audio_path=str(clean_wav),
            direction=pd,
        )
        take_clipped = TakeVariant(
            take_id="t1_clipped",
            segment_uid="seg_01",
            segment_index=1,
            variant_type="standard",
            audio_path=str(clipped_wav),
            direction=pd,
        )

        result = self.selector.select_take_with_result(
            takes=[take_clipped, take_clean],
            text="The forest was still.",
            direction=pd,
        )

        assert result.winner.take_id == "t1_clean"
        assert result.winner.is_selected is True
        assert take_clipped.is_selected is False
        assert "Disqualified by Hard Gate" in take_clipped.selection_reason
        assert "Audible clipping" in take_clipped.selection_reason
        assert result.evidence["disqualified_count"] == 1

    def test_02_technical_hard_gate_rejects_dead_air(self):
        """Verifies candidate with dead air > 2.0s is disqualified by technical hard gate."""
        pd = PerformanceDirection(
            index=2,
            speaker="Narrator",
            intensity="medium",
            surface_emotion="neutral",
        )

        normal_wav = create_waveform_file(self.takes_dir / "t2_normal.wav", duration_sec=1.2, trailing_silence_sec=0.2)
        dead_air_wav = create_waveform_file(self.takes_dir / "t2_dead.wav", duration_sec=1.2, trailing_silence_sec=2.5)

        t_normal = TakeVariant(
            take_id="t2_normal",
            segment_uid="seg_02",
            segment_index=2,
            variant_type="standard",
            audio_path=str(normal_wav),
            direction=pd,
        )
        t_dead = TakeVariant(
            take_id="t2_dead",
            segment_uid="seg_02",
            segment_index=2,
            variant_type="standard",
            audio_path=str(dead_air_wav),
            direction=pd,
        )

        result = self.selector.select_take_with_result(
            takes=[t_dead, t_normal],
            text="He looked around slowly.",
            direction=pd,
        )

        assert result.winner.take_id == "t2_normal"
        assert t_dead.is_selected is False
        assert "Dead air violation" in t_dead.selection_reason

    def test_03_technical_hard_gate_rejects_dc_bias_and_truncation(self):
        """Verifies candidates with DC bias > 1500 or duration < 0.25s are rejected."""
        pd = PerformanceDirection(
            index=3,
            speaker="Narrator",
            intensity="medium",
        )

        good_wav = create_waveform_file(self.takes_dir / "t3_good.wav", duration_sec=1.2)
        dc_wav = create_waveform_file(self.takes_dir / "t3_dc.wav", duration_sec=1.2, dc_bias=2000.0)
        trunc_wav = create_waveform_file(self.takes_dir / "t3_trunc.wav", duration_sec=0.15)

        t_good = TakeVariant(take_id="t3_good", segment_uid="s3", segment_index=3, variant_type="standard", audio_path=str(good_wav), direction=pd)
        t_dc = TakeVariant(take_id="t3_dc", segment_uid="s3", segment_index=3, variant_type="standard", audio_path=str(dc_wav), direction=pd)
        t_trunc = TakeVariant(take_id="t3_trunc", segment_uid="s3", segment_index=3, variant_type="standard", audio_path=str(trunc_wav), direction=pd)

        result = self.selector.select_take_with_result([t_dc, t_trunc, t_good], text="Shadows lengthened.", direction=pd)
        assert result.winner.take_id == "t3_good"
        assert t_dc.is_selected is False
        assert t_trunc.is_selected is False
        assert "Truncated audio" in t_trunc.selection_reason

    def test_04_alignment_hard_gate_rejects_low_confidence(self):
        """Verifies candidate with alignment confidence < 0.35 is disqualified."""
        pd = PerformanceDirection(
            index=4,
            speaker="Hero",
            intensity="medium",
        )

        wav_a = create_waveform_file(self.takes_dir / "t4_a.wav", duration_sec=1.5)
        wav_b = create_waveform_file(self.takes_dir / "t4_b.wav", duration_sec=1.5)

        t_a = TakeVariant(
            take_id="t4_a",
            segment_uid="s4",
            segment_index=4,
            variant_type="standard",
            audio_path=str(wav_a),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="t4_a",
                overall_score=0.88,
                passed=True,
                evidence=PerformanceEvidence(
                    acoustic=AcousticEvidence(),
                    prosody=ProsodyEvidence(),
                    pacing=PacingEvidence(),
                    alignment_confidence=0.25,  # Low alignment confidence
                ),
            ),
        )
        t_b = TakeVariant(
            take_id="t4_b",
            segment_uid="s4",
            segment_index=4,
            variant_type="standard",
            audio_path=str(wav_b),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="t4_b",
                overall_score=0.82,
                passed=True,
                evidence=PerformanceEvidence(
                    acoustic=AcousticEvidence(),
                    prosody=ProsodyEvidence(),
                    pacing=PacingEvidence(),
                    alignment_confidence=0.92,
                ),
            ),
        )

        result = self.selector.select_take_with_result([t_a, t_b], text="We cannot remain here.", direction=pd)
        assert result.winner.take_id == "t4_b"
        assert t_a.is_selected is False
        assert "Alignment failure" in t_a.selection_reason

    def test_05_voice_identity_hard_gate_rejects_catastrophic_drift(self):
        """Verifies catastrophic voice drift (similarity < 0.45) triggers hard gate disqualification."""
        pd = PerformanceDirection(
            index=5,
            speaker="Hero",
            surface_emotion="neutral",
        )

        wav_good = create_waveform_file(self.takes_dir / "t5_good.wav", duration_sec=1.2, f0_hz=140.0)
        wav_drift = create_waveform_file(self.takes_dir / "t5_drift.wav", duration_sec=1.2, f0_hz=280.0)

        t_good = TakeVariant(
            take_id="t5_good",
            segment_uid="s5",
            segment_index=5,
            variant_type="standard",
            audio_path=str(wav_good),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="t5_good",
                overall_score=0.80,
                passed=True,
                voice_identity_score=0.92,
                voice_drift_detected=False,
            ),
        )
        t_catastrophic = TakeVariant(
            take_id="t5_catastrophic",
            segment_uid="s5",
            segment_index=5,
            variant_type="standard",
            audio_path=str(wav_drift),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="t5_catastrophic",
                overall_score=0.86,
                passed=False,
                voice_identity_score=0.35,  # Catastrophic drift
                voice_drift_detected=True,
            ),
        )

        result = self.selector.select_take_with_result([t_catastrophic, t_good], text="Listen to me.", direction=pd)
        assert result.winner.take_id == "t5_good"
        assert t_catastrophic.is_selected is False
        assert "Catastrophic voice drift" in t_catastrophic.selection_reason

    def test_06_all_takes_fail_hard_gates_failsafe_with_review_flag(self):
        """Verifies that if ALL takes violate hard gates, the engine does not crash but flags review_required."""
        pd = PerformanceDirection(
            index=6,
            speaker="Narrator",
            intensity="medium",
        )

        clip1 = create_waveform_file(self.takes_dir / "t6_c1.wav", duration_sec=1.2, is_clipped=True)
        clip2 = create_waveform_file(self.takes_dir / "t6_c2.wav", duration_sec=1.2, is_clipped=True)

        t1 = TakeVariant(take_id="t6_c1", segment_uid="s6", segment_index=6, variant_type="standard", audio_path=str(clip1), direction=pd)
        t2 = TakeVariant(take_id="t6_c2", segment_uid="s6", segment_index=6, variant_type="standard", audio_path=str(clip2), direction=pd)

        result = self.selector.select_take_with_result([t1, t2], text="Silence fell.", direction=pd)
        assert result.winner is None
        assert result.status == "NO_ACCEPTABLE_TAKE"
        assert result.review_required is True
        assert result.evidence["all_violated"] is True
        assert "NO_ACCEPTABLE_TAKE" in result.reason_codes

        # Legacy adapter returns degraded fallback marked is_selected=False
        best = self.selector.select_best_take([t1, t2], text="Silence fell.", direction=pd)
        assert best is not None
        assert best.is_selected is False
        assert best.selection_result.review_required is True
        assert best.selection_result.status == "NO_ACCEPTABLE_TAKE"
        assert "[DEGRADED_FALLBACK - NO_ACCEPTABLE_TAKE]" in best.selection_reason

    def test_07_context_aware_mode_scoring_exposition_vs_climax_vs_whisper(self):
        """Verifies context-aware weight allocation across Exposition, Climax, and Whisper modes."""
        # 1. Exposition: Naturalness dominates
        pd_expo = PerformanceDirection(index=7, speaker="Narrator", narrative_mode="narrator_exposition")
        w_expo = create_waveform_file(self.takes_dir / "t7_expo.wav")
        t_high_nat = TakeVariant(
            take_id="t_nat", segment_uid="s7", segment_index=7, variant_type="standard", audio_path=str(w_expo), direction=pd_expo,
            evaluation=PerformanceEvaluationResult(
                take_id="t_nat", overall_score=0.80, passed=True,
                dimensions={"naturalness": EvaluationDimensionScore(dimension="naturalness", score=0.92)}
            )
        )
        t_low_nat = TakeVariant(
            take_id="t_low_nat", segment_uid="s7", segment_index=7, variant_type="standard", audio_path=str(w_expo), direction=pd_expo,
            evaluation=PerformanceEvaluationResult(
                take_id="t_low_nat", overall_score=0.81, passed=True,
                dimensions={"naturalness": EvaluationDimensionScore(dimension="naturalness", score=0.65)}
            )
        )
        res_expo = self.selector.select_take_with_result([t_low_nat, t_high_nat], text="The road was long.", direction=pd_expo)
        assert res_expo.winner.take_id == "t_nat"

        # 2. Climax: Emotional match & subtext dominate
        pd_climax = PerformanceDirection(index=8, speaker="Hero", intensity="explosive", performance_priority="climactic")
        t_climax_emo = TakeVariant(
            take_id="t_emo", segment_uid="s8", segment_index=8, variant_type="more_restrained", audio_path=str(w_expo), direction=pd_climax,
            evaluation=PerformanceEvaluationResult(
                take_id="t_emo", overall_score=0.82, passed=True,
                dimensions={
                    "emotional_match": EvaluationDimensionScore(dimension="emotional_match", score=0.90),
                    "subtext": EvaluationDimensionScore(dimension="subtext", score=0.88),
                    "naturalness": EvaluationDimensionScore(dimension="naturalness", score=0.80),
                }
            )
        )
        t_climax_flat = TakeVariant(
            take_id="t_flat", segment_uid="s8", segment_index=8, variant_type="standard", audio_path=str(w_expo), direction=pd_climax,
            evaluation=PerformanceEvaluationResult(
                take_id="t_flat", overall_score=0.83, passed=True,
                dimensions={
                    "emotional_match": EvaluationDimensionScore(dimension="emotional_match", score=0.70),
                    "subtext": EvaluationDimensionScore(dimension="subtext", score=0.70),
                    "naturalness": EvaluationDimensionScore(dimension="naturalness", score=0.85),
                }
            )
        )
        res_climax = self.selector.select_take_with_result([t_climax_flat, t_climax_emo], text="This ends now!", direction=pd_climax)
        assert res_climax.winner.take_id == "t_emo"

    def test_08_pairwise_deliberation_restraint_beats_shouting(self):
        """Verifies PairwiseTakeJudge awards victory to restraint over unmotivated shouting."""
        pd = PerformanceDirection(
            index=9,
            speaker="Hero",
            restraint=0.85,
            surface_emotion="cold_menace",
            actioning="intimidate_with_silence",
        )

        w1 = create_waveform_file(self.takes_dir / "t9_restrained.wav", duration_sec=1.5, amplitude=0.35)
        w2 = create_waveform_file(self.takes_dir / "t9_shout.wav", duration_sec=1.5, amplitude=0.95)

        t_restraint = TakeVariant(
            take_id="t9_restrained",
            segment_uid="s9",
            segment_index=9,
            variant_type="more_restrained",
            audio_path=str(w1),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="t9_restrained",
                overall_score=0.84,
                passed=True,
                dimensions={
                    "subtext": EvaluationDimensionScore(dimension="subtext", score=0.92),
                    "naturalness": EvaluationDimensionScore(dimension="naturalness", score=0.88),
                    "emotional_match": EvaluationDimensionScore(dimension="emotional_match", score=0.86),
                },
                evidence=PerformanceEvidence(
                    acoustic=AcousticEvidence(rms_dbfs=-22.0, clipping_samples_pinned=0),
                    prosody=ProsodyEvidence(dynamic_range_db=18.0),
                    pacing=PacingEvidence(),
                ),
            ),
        )

        t_shout = TakeVariant(
            take_id="t9_shout",
            segment_uid="s9",
            segment_index=9,
            variant_type="exposed",
            audio_path=str(w2),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="t9_shout",
                overall_score=0.85,
                passed=True,
                dimensions={
                    "subtext": EvaluationDimensionScore(dimension="subtext", score=0.68),
                    "naturalness": EvaluationDimensionScore(dimension="naturalness", score=0.78),
                    "emotional_match": EvaluationDimensionScore(dimension="emotional_match", score=0.88),
                },
                evidence=PerformanceEvidence(
                    acoustic=AcousticEvidence(rms_dbfs=-14.0, clipping_samples_pinned=4),
                    prosody=ProsodyEvidence(dynamic_range_db=10.0),
                    pacing=PacingEvidence(),
                ),
            ),
        )

        result = self.selector.select_take_with_result([t_shout, t_restraint], text="Do not take another step.", direction=pd)
        assert result.winner.take_id == "t9_restrained"
        assert "BETTER_RESTRAINT" in result.reason_codes
        assert "more_restrained" in result.winner.selection_reason

    def test_09_pairwise_deliberation_dramatic_pause_beats_dead_air(self):
        """Verifies PairwiseTakeJudge differentiates intentional dramatic pauses from unmotivated dead air."""
        pd = PerformanceDirection(
            index=10,
            speaker="Hero",
            surface_emotion="grief",
            restraint=0.70,
        )

        w1 = create_waveform_file(self.takes_dir / "t10_timing.wav", duration_sec=1.5)
        w2 = create_waveform_file(self.takes_dir / "t10_dead.wav", duration_sec=1.5)

        t_dramatic = TakeVariant(
            take_id="t10_dramatic",
            segment_uid="s10",
            segment_index=10,
            variant_type="vulnerable",
            audio_path=str(w1),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="t10_dramatic",
                overall_score=0.83,
                passed=True,
                dimensions={"subtext": EvaluationDimensionScore(dimension="subtext", score=0.86)},
                evidence=PerformanceEvidence(
                    acoustic=AcousticEvidence(dead_air_sec=0.4),
                    prosody=ProsodyEvidence(),
                    pacing=PacingEvidence(dramatic_timing_fit=0.92),
                ),
            ),
        )

        t_dead_air = TakeVariant(
            take_id="t10_dead",
            segment_uid="s10",
            segment_index=10,
            variant_type="standard",
            audio_path=str(w2),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="t10_dead",
                overall_score=0.84,
                passed=True,
                dimensions={"subtext": EvaluationDimensionScore(dimension="subtext", score=0.80)},
                evidence=PerformanceEvidence(
                    acoustic=AcousticEvidence(dead_air_sec=1.8),
                    prosody=ProsodyEvidence(),
                    pacing=PacingEvidence(dramatic_timing_fit=0.50),
                ),
            ),
        )

        result = self.selector.select_take_with_result([t_dead_air, t_dramatic], text="She... is gone.", direction=pd)
        assert result.winner.take_id == "t10_dramatic"
        assert "BETTER_DRAMATIC_PAUSE" in result.reason_codes

    def test_10_selection_result_contract_fields_and_explainability(self):
        """Verifies TakeSelectionResult contract adheres strictly to specification."""
        pd = PerformanceDirection(index=11, speaker="Hero")
        w1 = create_waveform_file(self.takes_dir / "t11_a.wav")
        w2 = create_waveform_file(self.takes_dir / "t11_b.wav")

        t1 = TakeVariant(take_id="t11_a", segment_uid="s11", segment_index=11, variant_type="more_restrained", audio_path=str(w1), direction=pd)
        t2 = TakeVariant(take_id="t11_b", segment_uid="s11", segment_index=11, variant_type="standard", audio_path=str(w2), direction=pd)

        res = self.selector.select_take_with_result([t1, t2], text="Stay close.", direction=pd)
        assert isinstance(res, TakeSelectionResult)
        assert res.winner.take_id in ("t11_a", "t11_b")
        assert res.runner_up is not None
        assert res.margin >= 0.0
        assert 0.0 <= res.confidence <= 1.0
        assert isinstance(res.reason_codes, list)
        assert res.winner.selection_result is res
        assert "Selected Take" in res.winner.selection_reason

    def test_11_calibration_configurability(self):
        """Verifies TakeSelectorCalibrationConfig isolates all thresholds and can be reconfigured."""
        custom_cfg = TakeSelectorCalibrationConfig(
            clipping_pinned_hard_gate=5,  # Stricter clipping threshold
            pairwise_margin_threshold=0.10,
            voice_drift_penalty=0.60,
        )
        custom_selector = IntelligentTakeSelector(evaluator=self.evaluator, config=custom_cfg)
        assert custom_selector.config.clipping_pinned_hard_gate == 5
        assert custom_selector.config.pairwise_margin_threshold == 0.10
        assert custom_selector.config.voice_drift_penalty == 0.60
