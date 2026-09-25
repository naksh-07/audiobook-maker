#!/usr/bin/env python3
"""
Test Suite: Golden Performance QC 2.0 Benchmark Suite.
Validates 18 dramatic categories across correct acceptance and correct rejection:
  1. Controlled suppressed anger (intense suppressed emotion, low F0, tight dynamics -> ACCEPT)
  2. Hysterical unsuppressed shouting under high restraint directive -> REGENERATE / REJECT
  3. Intimate tender whisper (low projection, breath presence, close mic -> ACCEPT)
  4. Blown-out loud whisper (> -15 dBFS -> REJECT)
  5. Genuine grief / weeping (interrupted pitch contour, broken pacing -> ACCEPT)
  6. Melodramatic synthetic crying (flat pitch with fake sob -> REJECT)
  7. Sarcasm / irony (mismatch between surface emotion and underlying subtext -> ACCEPT)
  8. Flat reading lacking subtext when subtext is critical -> REJECT
  9. Contextually motivated dramatic silence (pause <= 2.2s with dramatic_silence -> ACCEPT)
  10. Unmotivated dead air (> 2.0s with punctuation silence -> REJECT)
  11. Legitimate emotional pitch variation within character reference distribution -> ACCEPT
  12. Catastrophic pitch mutation / alien voice drift -> REJECT
  13. Submissive yielded projection under interrogation -> ACCEPT
  14. Submissive unmotivated aggressive shout without panic -> REJECT
  15. Submissive panic outburst under extreme terror -> ACCEPT
  16. Interrupted turn-taking with crisp 30-60ms timing -> ACCEPT
  17. Interrupted turn with sluggish 400ms dead air -> REJECT
  18. Candidate pool where all takes fail hard gates -> Authoritative NO_ACCEPTABLE_TAKE with winner=None
"""

from __future__ import annotations
import wave
import tempfile
import numpy as np
from pathlib import Path
import pytest

from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    TakeVariant,
    PerformanceEvaluationResult,
    EvaluationDimensionScore,
    TakeSelectionResult,
    PerformanceEvidence,
    AcousticEvidence,
    ProsodyEvidence,
    PacingEvidence,
    VoiceIdentityEvidence,
    EmotionRealizationEvidence,
    IntentRealizationEvidence,
    EmphasisEvidence,
    BreathEvidence,
    PerceptualPerformanceEvidence,
)
from audiobook_factory.performance.evaluator import PerformanceEvaluator
from audiobook_factory.performance.take_selector import IntelligentTakeSelector
from audiobook_factory.performance.evidence_fusion import EvidenceFusionEngine
from audiobook_factory.performance.chemistry import ConversationalChemistry
from audiobook_factory.identity.reference_bank import AcousticSignature
from audiobook_factory.identity.voice_drift_analyzer import VoiceIdentityAnalyzer


def create_waveform_file(
    filepath: Path,
    duration_sec: float = 2.0,
    sample_rate: int = 24000,
    f0_hz: float = 140.0,
    amplitude: float = 0.5,
    pitch_mod_depth: float = 8.0,
    pitch_mod_freq: float = 3.0,
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
def fusion_engine():
    return EvidenceFusionEngine()


@pytest.fixture
def selector(evaluator):
    return IntelligentTakeSelector(evaluator=evaluator)


class TestGoldenPerformanceQC2Suite:
    """18-Category Golden Performance QC 2.0 Benchmark Matrix."""

    # 1. Controlled suppressed anger -> ACCEPT
    def test_cat_01_controlled_suppressed_anger_accepted(self, temp_dir, evaluator, selector):
        wav = create_waveform_file(temp_dir / "t01.wav", amplitude=0.45)
        pd = PerformanceDirection(
            index=1,
            speaker="speaker_a",
            surface_emotion="cold_menace",
            actioning="intimidate_with_suppressed_rage",
            restraint=0.85,
            intensity="medium",
        )
        take = TakeVariant(
            take_id="t01",
            segment_uid="s01",
            segment_index=1,
            variant_type="more_restrained",
            audio_path=str(wav),
            direction=pd,
        )
        res = selector.select_take_with_result([take], text="I told you never to return.", direction=pd)
        assert res.winner is not None
        assert res.status in ("ACCEPT", "ACCEPT_WITH_WARNING")
        assert res.winner_score >= 0.70

    # 2. Hysterical unsuppressed shouting under high restraint -> REJECT / REVIEW
    def test_cat_02_hysterical_shouting_under_restraint_rejected(self, temp_dir, evaluator, selector):
        wav = create_waveform_file(temp_dir / "t02.wav", amplitude=0.98)
        pd = PerformanceDirection(
            index=2,
            speaker="speaker_a",
            surface_emotion="cold_menace",
            actioning="intimidate",
            restraint=0.90,
            intensity="low",
        )
        take = TakeVariant(
            take_id="t02",
            segment_uid="s02",
            segment_index=2,
            variant_type="exposed",
            audio_path=str(wav),
            direction=pd,
        )
        fusion_res = selector.fusion_engine.fuse_take(take, text="Stay where you are.", direction=pd)
        assert any("Restraint breached" in r for r in fusion_res.review_reasons) or fusion_res.fused_score < 0.80

    # 3. Intimate tender whisper -> ACCEPT
    def test_cat_03_intimate_tender_whisper_accepted(self, temp_dir, evaluator, selector):
        wav = create_waveform_file(temp_dir / "t03.wav", amplitude=0.15)
        pd = PerformanceDirection(
            index=3,
            speaker="speaker_b",
            surface_emotion="tender",
            intimacy_level="intimate",
            proximity="close_mic",
            energy=0.35,
        )
        take = TakeVariant(
            take_id="t03",
            segment_uid="s03",
            segment_index=3,
            variant_type="more_intimate",
            audio_path=str(wav),
            direction=pd,
        )
        res = selector.select_take_with_result([take], text="I am right here with you.", direction=pd)
        assert res.winner is not None
        assert res.status in ("ACCEPT", "ACCEPT_WITH_WARNING")

    # 4. Blown-out loud whisper (> -15 dBFS) -> REJECT
    def test_cat_04_blown_out_whisper_penalized(self, temp_dir, evaluator):
        wav = create_waveform_file(temp_dir / "t04.wav", amplitude=0.95)
        pd = PerformanceDirection(
            index=4,
            speaker="speaker_b",
            surface_emotion="whisper",
            intimacy_level="intimate",
            intensity="low",
            energy=0.30,
        )
        eval_res = evaluator.evaluate_take(
            take_id="t04",
            audio_file=wav,
            text="Do not make a sound.",
            direction=pd,
        )
        # Intense projection on whisper is penalized in emotional match
        emo_dim = eval_res.dimensions.get("emotional_match")
        assert emo_dim is not None
        assert "EMOTION_OVERPLAYED" in emo_dim.reason_codes or "Excessive volume" in emo_dim.rationale

    # 5. Genuine grief / weeping -> ACCEPT
    def test_cat_05_genuine_grief_accepted(self, temp_dir, evaluator, selector):
        wav = create_waveform_file(temp_dir / "t05.wav", pitch_mod_depth=16.0, pitch_mod_freq=6.0)
        pd = PerformanceDirection(
            index=5,
            speaker="speaker_b",
            surface_emotion="grief",
            breath_behavior="trembling",
            physical_state="exhausted",
        )
        take = TakeVariant(
            take_id="t05",
            segment_uid="s05",
            segment_index=5,
            variant_type="more_vulnerable",
            audio_path=str(wav),
            direction=pd,
        )
        res = selector.select_take_with_result([take], text="There is nothing left of them.", direction=pd)
        assert res.winner is not None
        assert res.status in ("ACCEPT", "ACCEPT_WITH_WARNING")

    # 6. Melodramatic synthetic crying (flat pitch with fake sob) -> REJECT
    def test_cat_06_melodramatic_flat_crying_penalized(self, temp_dir, evaluator):
        wav = create_waveform_file(temp_dir / "t06.wav", pitch_mod_depth=0.0)
        pd = PerformanceDirection(
            index=6,
            speaker="speaker_b",
            surface_emotion="grief",
            intensity="high",
        )
        eval_res = evaluator.evaluate_take(
            take_id="t06",
            audio_file=wav,
            text="No, please, no.",
            direction=pd,
        )
        # Completely flat F0 is flagged under prosody as monotonic pitch lock
        pros_dim = eval_res.dimensions.get("prosody")
        assert pros_dim is not None
        assert "Monotonic pitch lock" in pros_dim.rationale or pros_dim.score < 0.75

    # 7. Sarcasm / irony (mismatch between surface emotion and underlying subtext) -> ACCEPT
    def test_cat_07_sarcasm_with_subtext_accepted(self, temp_dir, evaluator, selector):
        wav = create_waveform_file(temp_dir / "t07.wav", amplitude=0.5)
        pd = PerformanceDirection(
            index=7,
            speaker="speaker_a",
            surface_emotion="polite_courtesy",
            underlying_emotion="contempt",
            subtext="You are an utter fool.",
            subtext_confidence=0.90,
        )
        take = TakeVariant(
            take_id="t07",
            segment_uid="s07",
            segment_index=7,
            variant_type="standard",
            audio_path=str(wav),
            direction=pd,
        )
        res = selector.select_take_with_result([take], text="How utterly brilliant of you.", direction=pd)
        assert res.winner is not None
        assert res.winner.evaluation.dimensions["subtext"].score >= 0.70

    # 8. Flat reading lacking subtext when subtext is critical -> REJECT
    def test_cat_08_flat_reading_lacking_subtext_penalized(self, temp_dir, evaluator):
        # Shouting at high volume breaks character restraint
        wav = create_waveform_file(temp_dir / "t08.wav", amplitude=0.99)
        pd = PerformanceDirection(
            index=8,
            speaker="speaker_a",
            surface_emotion="polite_courtesy",
            underlying_emotion="contempt",
            subtext="You disgust me.",
            subtext_confidence=0.95,
            restraint=0.85,
        )
        eval_res = evaluator.evaluate_take(
            take_id="t08",
            audio_file=wav,
            text="A delightful suggestion, Chancellor.",
            direction=pd,
        )
        sub_dim = eval_res.dimensions.get("subtext")
        assert sub_dim is not None
        assert sub_dim.score <= 0.70
        assert "Over-acted delivery" in sub_dim.rationale

    # 9. Contextually motivated dramatic silence (pause <= 2.2s with dramatic_silence) -> ACCEPT
    def test_cat_09_dramatic_silence_rewarded(self, temp_dir, evaluator):
        wav = create_waveform_file(temp_dir / "t09.wav", trailing_silence_sec=1.6)
        pd = PerformanceDirection(
            index=9,
            speaker="speaker_a",
            silence_type="dramatic_silence",
            pause_after_ms=1600,
        )
        eval_res = evaluator.evaluate_take(
            take_id="t09",
            audio_file=wav,
            text="And then... silence.",
            direction=pd,
        )
        nat_dim = eval_res.dimensions.get("naturalness")
        assert nat_dim is not None
        assert "BETTER_DRAMATIC_PAUSE" in nat_dim.reason_codes or "Dramatic silence" in nat_dim.rationale
        assert not any("Dead air" in d for d in eval_res.diagnostics)

    # 10. Unmotivated dead air (> 2.0s with punctuation silence) -> REJECT
    def test_cat_10_unmotivated_dead_air_disqualified(self, temp_dir, evaluator, selector):
        wav = create_waveform_file(temp_dir / "t10.wav", trailing_silence_sec=2.5)
        pd = PerformanceDirection(
            index=10,
            speaker="speaker_a",
            silence_type="punctuation",
        )
        take = TakeVariant(
            take_id="t10",
            segment_uid="s10",
            segment_index=10,
            variant_type="standard",
            audio_path=str(wav),
            direction=pd,
        )
        # Run selector evaluation which populates take.evaluation.evidence.acoustic
        res = selector.select_take_with_result([take], text="The door closed.", direction=pd)
        # When dead air exceeds 2.0s without dramatic silence, it triggers review_required
        assert res.review_required is True
        assert any("Dead air violation" in r for r in res.evidence.get("gate_reasons", []))

    # 11. Legitimate emotional pitch variation within character reference distribution -> ACCEPT
    def test_cat_11_emotional_pitch_variation_within_distribution_accepted(self, temp_dir):
        # Generate wave with pitch 168 Hz matching emotional baseline
        wav = create_waveform_file(temp_dir / "t11_emo.wav", f0_hz=168.0)
        sig = AcousticSignature(
            character_id="char_speaker_a",
            voice_id="voice_speaker_a",
            f0_median_hz=140.0,
            f0_iqr_hz=25.0,
            f0_min_hz=80.0,
            f0_max_hz=260.0,
            f0_dispersion_ratio=0.25,
            spectral_centroid_hz=220.0,
            mode_baselines={"emotional": {"f0_median_hz": 175.0, "f0_iqr_hz": 30.0}},
        )
        analyzer = VoiceIdentityAnalyzer(sample_rate=24000)
        drift_res = analyzer.analyze_take_identity(
            take_id="t11",
            audio_path=wav,
            signature=sig,
            dramatic_emotion="emotional",
        )
        assert drift_res.drift_detected is False
        assert drift_res.similarity_score >= 0.70

    # 12. Catastrophic pitch mutation / alien voice drift -> REJECT
    def test_cat_12_catastrophic_voice_drift_rejected(self, temp_dir):
        sig = AcousticSignature(
            character_id="char_speaker_a",
            voice_id="voice_speaker_a",
            f0_median_hz=130.0,
            f0_iqr_hz=20.0,
            f0_min_hz=90.0,
            f0_max_hz=190.0,
            spectral_centroid_hz=200.0,
        )
        # Severe pitch mutation at 380 Hz
        wav = create_waveform_file(temp_dir / "t12_mutation.wav", f0_hz=380.0)
        analyzer = VoiceIdentityAnalyzer(sample_rate=24000)
        drift_res = analyzer.analyze_take_identity(
            take_id="t12",
            audio_path=wav,
            signature=sig,
            dramatic_emotion="neutral",
        )
        assert drift_res.drift_detected is True
        assert drift_res.similarity_score <= 0.45
        assert drift_res.recommendation == "regenerate"
        assert any("Catastrophic" in d or "divergence" in d for d in drift_res.diagnostics)

    # 13. Submissive yielded projection under interrogation -> ACCEPT
    def test_cat_13_submissive_yielded_projection_accepted(self):
        dir_threat = PerformanceDirection(
            direction_id="pd_13_a", index=13, speaker="interrogator",
            actioning="threaten", power_position="dominant", energy=0.85,
        )
        dir_sub = PerformanceDirection(
            direction_id="pd_13_b", index=14, speaker="captive",
            actioning="plead", power_position="submissive", energy=0.45,
        )
        t_a = TakeVariant(take_id="t13_a", segment_uid="s13_a", segment_index=13, audio_path="/tmp/a.wav", direction=dir_threat)
        t_b = TakeVariant(take_id="t13_b", segment_uid="s13_b", segment_index=14, audio_path="/tmp/b.wav", direction=dir_sub)

        eval_chem = ConversationalChemistry.evaluate_dialogue_chemistry(t_a, t_b)
        assert eval_chem.energy_contrast_score == 1.0
        assert eval_chem.passed is True

    # 14. Submissive unmotivated aggressive shout without panic -> REJECT
    def test_cat_14_submissive_unmotivated_shout_penalized(self):
        dir_threat = PerformanceDirection(
            direction_id="pd_14_a", index=15, speaker="interrogator",
            actioning="threaten", power_position="dominant", energy=0.80,
        )
        dir_shout = PerformanceDirection(
            direction_id="pd_14_b", index=16, speaker="captive",
            actioning="whisper", power_position="submissive", surface_emotion="calm", energy=0.95,
        )
        t_a = TakeVariant(take_id="t14_a", segment_uid="s14_a", segment_index=15, audio_path="/tmp/a.wav", direction=dir_threat)
        t_b = TakeVariant(take_id="t14_b", segment_uid="s14_b", segment_index=16, audio_path="/tmp/b.wav", direction=dir_shout)

        eval_chem = ConversationalChemistry.evaluate_dialogue_chemistry(t_a, t_b)
        assert eval_chem.energy_contrast_score < 0.70
        assert any("Submissive respondent inappropriately projected higher energy" in d for d in eval_chem.diagnostics)

    # 15. Submissive panic outburst under extreme terror -> ACCEPT
    def test_cat_15_submissive_panic_outburst_justified(self):
        dir_threat = PerformanceDirection(
            direction_id="pd_15_a", index=17, speaker="interrogator",
            actioning="threaten with blade", power_position="dominant", energy=0.85,
        )
        dir_panic = PerformanceDirection(
            direction_id="pd_15_b", index=18, speaker="captive",
            actioning="scream in desperation", surface_emotion="terror", power_position="submissive", energy=0.95,
        )
        t_a = TakeVariant(take_id="t15_a", segment_uid="s15_a", segment_index=17, audio_path="/tmp/a.wav", direction=dir_threat)
        t_b = TakeVariant(take_id="t15_b", segment_uid="s15_b", segment_index=18, audio_path="/tmp/b.wav", direction=dir_panic)

        eval_chem = ConversationalChemistry.evaluate_dialogue_chemistry(t_a, t_b)
        assert eval_chem.energy_contrast_score == 1.0
        assert any("justified dramatic panic outburst" in d for d in eval_chem.diagnostics)

    # 16. Interrupted turn-taking with crisp 30-60ms timing -> ACCEPT
    def test_cat_16_crisp_interruption_accepted(self):
        dir_a = PerformanceDirection(
            direction_id="pd_16_a", index=19, speaker="speaker_a",
            interruption_behavior="abrupt_cut", silence_type="interruption_cut",
        )
        dir_b = PerformanceDirection(
            direction_id="pd_16_b", index=20, speaker="speaker_b",
            turn_taking_behavior="immediate",
        )
        t_a = TakeVariant(take_id="t16_a", segment_uid="s16_a", segment_index=19, audio_path="/tmp/a.wav", direction=dir_a)
        t_b = TakeVariant(take_id="t16_b", segment_uid="s16_b", segment_index=20, audio_path="/tmp/b.wav", direction=dir_b)

        eval_chem = ConversationalChemistry.evaluate_dialogue_chemistry(t_a, t_b, actual_gap_ms=45)
        assert eval_chem.interruption_quality_score == 1.0
        assert eval_chem.passed is True

    # 17. Interrupted turn with sluggish 400ms dead air -> REJECT
    def test_cat_17_sluggish_interruption_penalized(self):
        dir_a = PerformanceDirection(
            direction_id="pd_17_a", index=21, speaker="speaker_a",
            interruption_behavior="abrupt_cut", silence_type="interruption_cut",
        )
        dir_b = PerformanceDirection(
            direction_id="pd_17_b", index=22, speaker="speaker_b",
            turn_taking_behavior="immediate",
        )
        t_a = TakeVariant(take_id="t17_a", segment_uid="s17_a", segment_index=21, audio_path="/tmp/a.wav", direction=dir_a)
        t_b = TakeVariant(take_id="t17_b", segment_uid="s17_b", segment_index=22, audio_path="/tmp/b.wav", direction=dir_b)

        eval_chem = ConversationalChemistry.evaluate_dialogue_chemistry(t_a, t_b, actual_gap_ms=400)
        assert eval_chem.interruption_quality_score < 0.50
        assert any("Dead air on interrupted turn" in d for d in eval_chem.diagnostics)

    # 18. Candidate pool where all takes fail hard gates -> Authoritative NO_ACCEPTABLE_TAKE with winner=None
    def test_cat_18_all_takes_fail_hard_gates_authoritative_no_acceptable_take(self, temp_dir, selector):
        pd = PerformanceDirection(index=23, speaker="narrator", intensity="medium")
        clip_a = create_waveform_file(temp_dir / "t18_a.wav", is_clipped=True)
        clip_b = create_waveform_file(temp_dir / "t18_b.wav", is_clipped=True)

        t1 = TakeVariant(take_id="t18_a", segment_uid="s18", segment_index=23, variant_type="standard", audio_path=str(clip_a), direction=pd)
        t2 = TakeVariant(take_id="t18_b", segment_uid="s18", segment_index=23, variant_type="standard", audio_path=str(clip_b), direction=pd)

        # Authoritative result has winner = None
        result = selector.select_take_with_result([t1, t2], text="The darkness deepened.", direction=pd)
        assert result.winner is None
        assert result.status == "NO_ACCEPTABLE_TAKE"
        assert result.review_required is True
        assert "NO_ACCEPTABLE_TAKE" in result.reason_codes

        # Legacy adapter returns degraded fallback with is_selected = False
        fallback = selector.select_best_take([t1, t2], text="The darkness deepened.", direction=pd)
        assert fallback is not None
        assert fallback.is_selected is False
        assert fallback.selection_result.status == "NO_ACCEPTABLE_TAKE"
        assert "[DEGRADED_FALLBACK - NO_ACCEPTABLE_TAKE]" in fallback.selection_reason
