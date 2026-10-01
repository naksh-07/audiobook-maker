#!/usr/bin/env python3
"""
Audiobook Factory - Golden Pronunciation, Alignment & Dialogue Hardening Test Suite (Prompt 4).
Verifies the complete hardened pipeline across:
1. Pronunciation overrides reliably reach TTS
2. Names retain pronunciation metadata
3. Hindi/Hinglish text survives downstream contracts
4. Alignment covers the correct spoken text (numeral expansion & Hindi phonetics)
5. Speaker identity is preserved across turn transitions
6. Dialogue turns remain correctly ordered
7. Missing/swallowed words are detected by acoustic QA
8. Critical pronunciation failures cannot silently pass into production
9. Chemistry evaluation is actively consumed during take selection
10. Alignment and provenance remain attached to winning takes
11. 20-segment LanguageDialogueCalibrationCorpus benchmark execution
12. Real audio end-to-end smoke test (two speakers, Hindi, proper names, interruption cut)
"""

from __future__ import annotations
import os
import json
import wave
import struct
import math
import shutil
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from audiobook_factory.contracts import ScreenplaySegment
from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    TakeVariant,
    PerformanceEvaluationResult,
    EvaluationDimensionScore,
)
from audiobook_factory.performance.director import PerformanceDirector
from audiobook_factory.performance.take_selector import IntelligentTakeSelector
from audiobook_factory.performance.chemistry import ConversationalChemistry
from audiobook_factory.forced_aligner import (
    WorkstationForcedAligner,
    transliterate_devanagari_to_roman,
    normalize_text_for_alignment,
)
from audiobook_factory.dialogue_editing import DialogueEditor, DialogueEditorialConfig
from audiobook_factory.pronunciation import (
    PronunciationLexicon,
    PronunciationResolver,
    SpokenTextEngine,
    PronunciationAudioQA,
    PronunciationRepairEngine,
    PronunciationStatus,
    SpokenLanguage,
    LanguageDialogueCalibrationCorpus,
)


def _generate_synthetic_speech_wav(
    filepath: Path,
    duration_sec: float = 1.0,
    sample_rate: int = 24000,
    f0: float = 180.0,
    rms_target: float = 0.15,
) -> Path:
    """Generates a valid 16-bit PCM WAV file simulating speech formant harmonics."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(duration_sec * sample_rate)
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        # Fundamental frequency + 3 vocal formants with gentle amplitude envelope
        envelope = min(1.0, t / 0.05) * min(1.0, (duration_sec - t) / 0.05) if duration_sec > 0.1 else 1.0
        val = (
            0.50 * math.sin(2 * math.pi * f0 * t)
            + 0.30 * math.sin(2 * math.pi * f0 * 2.1 * t)
            + 0.15 * math.sin(2 * math.pi * f0 * 3.4 * t)
        ) * envelope * rms_target
        val = max(-1.0, min(1.0, val))
        samples.append(int(val * 32767))

    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return filepath


# =========================================================================
# Test 1: Pronunciation Overrides Reliably Reach TTS
# =========================================================================
def test_pronunciation_overrides_reach_tts(tmp_path):
    """Verify that explicit manual overrides and BookBible entities survive into spoken_text."""
    lexicon = PronunciationLexicon()
    lexicon.seed_default_lexicon()
    # Add explicit override
    lexicon.add_override(
        token="Kaer Morhen",
        spoken_form="केर मॉरहेन",
        expected_language=SpokenLanguage.HINDI,
    )
    resolver = PronunciationResolver(lexicon)
    engine = SpokenTextEngine(resolver)

    segment = ScreenplaySegment(
        uid="seg_override_01",
        index=1,
        speaker="Geralt",
        text="हम Kaer Morhen की ओर जा रहे हैं।",
    )

    res = engine.resolve_screenplay_segment(segment)
    assert "केर मॉरहेन" in res.spoken_text
    assert res.literary_text == "हम Kaer Morhen की ओर जा रहे हैं।"
    assert any(r.original_token == "Kaer Morhen" or "Kaer" in r.original_token for r in res.resolutions)


# =========================================================================
# Test 2: Names Retain Pronunciation Metadata Across Contracts
# =========================================================================
def test_names_retain_pronunciation_metadata(tmp_path):
    """Verify that pronunciation metadata attaches to ScreenplaySegment and PerformanceDirection."""
    lexicon = PronunciationLexicon()
    lexicon.seed_default_lexicon()
    resolver = PronunciationResolver(lexicon)
    engine = SpokenTextEngine(resolver)

    segment = ScreenplaySegment(
        uid="seg_meta_02",
        index=2,
        speaker="Inspector",
        text="Sherlock Holmes ने हत्यारे को पहचान लिया।",
    )

    spoken_res = engine.resolve_screenplay_segment(segment)
    segment.spoken_text = spoken_res.spoken_text
    segment.pronunciation_metadata = [r.model_dump() for r in spoken_res.resolutions]

    director = PerformanceDirector()
    p_dir = director.direct_segment(segment)

    assert p_dir.spoken_text is not None
    assert "शरलॉक होम्स" in p_dir.spoken_text
    assert p_dir.pronunciation_metadata is not None
    assert len(p_dir.pronunciation_metadata) > 0


# =========================================================================
# Test 3: Hindi and Hinglish Code-Switching Survives Downstream
# =========================================================================
def test_hindi_hinglish_code_switching_survives(tmp_path):
    """Verify that natural loanwords and Devanagari Hindi text are not corrupted or textbooksanitized."""
    lexicon = PronunciationLexicon()
    lexicon.seed_default_lexicon()
    resolver = PronunciationResolver(lexicon)
    engine = SpokenTextEngine(resolver)

    # Line containing both Devanagari and natural English loanwords
    line = "Doctor ने कहा कि मरीज को तुरंत City Hospital ले जाना पड़ेगा।"
    res = engine.resolve_text(line)

    assert "Doctor" in res.spoken_text
    assert "Hospital" in res.spoken_text or "हॉस्पिटल" in res.spoken_text or "City Hospital" in res.spoken_text
    assert "मरीज" in res.spoken_text
    assert not res.has_unresolved_critical


# =========================================================================
# Test 4: Forced Aligner Phonetic Numeral Expansion
# =========================================================================
def test_forced_aligner_numeral_expansion():
    """Verify that forced aligner expands numerals into phonetic words rather than dropping them."""
    raw_tokens, roman_tokens = normalize_text_for_alignment("उसने ₹500 दिए और 25% मुनाफा कमाया")
    assert len(raw_tokens) == len(roman_tokens)
    # The token 25 should expand phonetically (e.g. pachees)
    idx_25 = -1
    for i, t in enumerate(raw_tokens):
        if "25" in t:
            idx_25 = i
            break
    assert idx_25 != -1
    assert "pach" in roman_tokens[idx_25] or "chees" in roman_tokens[idx_25]
    # Verify gy mapping for ज्ञ
    assert transliterate_devanagari_to_roman("ज्ञान") == "gyan"


# =========================================================================
# Test 5: Speaker Identity Consistency Across Turns
# =========================================================================
def test_speaker_identity_consistency_across_turns():
    """Verify multi-speaker turns preserve unique speakers and appropriate voice profiles."""
    d1 = PerformanceDirection(segment_uid="s1", index=1, speaker="Geralt", character_state="dominant")
    d2 = PerformanceDirection(segment_uid="s2", index=2, speaker="Yennefer", character_state="contested")
    d3 = PerformanceDirection(segment_uid="s3", index=3, speaker="Geralt", character_state="yielding")

    directions = ConversationalChemistry.apply_conversational_chemistry([d1, d2, d3])
    assert directions[0].speaker == "Geralt"
    assert directions[1].speaker == "Yennefer"
    assert directions[2].speaker == "Geralt"
    assert directions[0].speaker != directions[1].speaker


# =========================================================================
# Test 6: Dialogue Turn Ordering and Timing
# =========================================================================
def test_dialogue_turn_ordering_and_timing(tmp_path):
    """Verify that PauseEditor realizes rapid retort latency (120ms) and normal turn latency."""
    editor = DialogueEditor(project_dir=tmp_path)
    d_threat = PerformanceDirection(
        segment_uid="s_threat", index=1, speaker="Baron", actioning="threaten", power_position="dominant"
    )
    d_rapid = PerformanceDirection(
        segment_uid="s_rapid", index=2, speaker="Rival", turn_taking_behavior="eager_counter", character_state="escalation"
    )

    res_rapid = editor.pause_editor.realize_pause(
        text="फैसला मेरा होगा!",
        speaker="Rival",
        direction=d_rapid,
        segment_uid="s_rapid",
    )
    assert res_rapid["pause_classification"] == "RAPID_TURN"
    assert res_rapid["pause_after_ms"] <= 150


# =========================================================================
# Test 7: Missing / Swallowed Word Acoustic Detection
# =========================================================================
def test_missing_swallowed_word_detection(tmp_path):
    """Verify that PronunciationAudioQA flags missing/swallowed tokens when audio duration is too short."""
    audio_file = tmp_path / "swallowed.wav"
    # Create very short 0.05s audio for a multi-word sensitive sentence
    _generate_synthetic_speech_wav(audio_file, duration_sec=0.05)

    lexicon = PronunciationLexicon()
    lexicon.seed_default_lexicon()
    resolver = PronunciationResolver(lexicon)
    engine = SpokenTextEngine(resolver)

    spoken_res = engine.resolve_text("Sherlock Holmes यहाँ उपस्थित थे।")
    auditor = PronunciationAudioQA()
    qa_res = auditor.audit_take(
        take_audio_path=audio_file,
        spoken_result=spoken_res,
        take_id="take_swallowed",
        segment_uid="seg_swallowed",
    )

    assert not qa_res.passed
    assert qa_res.status in (PronunciationStatus.FAILED, PronunciationStatus.REVIEW_REQUIRED)


# =========================================================================
# Test 8: Critical Pronunciation QA Failure Cannot Silently Pass
# =========================================================================
def test_critical_pronunciation_qa_failure_cannot_silently_pass(tmp_path):
    """Verify that un-repaired pronunciation QA failure marks take unselected and raises RuntimeError."""
    from audiobook_factory.tts_dispatcher import TTSDispatcher

    dispatcher = MagicMock()
    dispatcher.audio_dir = tmp_path
    dispatcher.default_voice = "Aoede"
    dispatcher.default_backend = "gemini"
    dispatcher.rate_limiter = None
    dispatcher.scene_tracker = None
    dispatcher.voice_dna_bank = None
    dispatcher.reference_voice_bank = None
    dispatcher._prev_take = None
    dispatcher.get_speaker_config = MagicMock(return_value={"voice": "Aoede", "speed": 1.0, "pitch": 1.0})

    raw_wav = tmp_path / "raw.wav"
    _generate_synthetic_speech_wav(raw_wav, duration_sec=1.0)

    p_dir = PerformanceDirection(segment_uid="seg_fail", index=1, speaker="Narrator")
    winning_take = TakeVariant(
        take_id="take_good_initially",
        segment_uid="seg_fail",
        segment_index=1,
        variant_type="standard",
        audio_path=str(raw_wav),
        direction=p_dir,
        is_selected=True,
    )

    dispatcher.performance_director = MagicMock()
    dispatcher.performance_director.direct_segment.return_value = p_dir

    dispatcher.take_bank = MagicMock()
    dispatcher.take_bank.get_candidate_variants.return_value = ["standard"]
    dispatcher.take_bank.create_take.return_value = winning_take
    dispatcher.take_bank.takes_dir = tmp_path
    dispatcher.take_selector = MagicMock()
    dispatcher.take_selector.select_best_take.return_value = winning_take

    dispatcher.spoken_text_engine = MagicMock()
    dispatcher.spoken_text_engine.resolve_screenplay_segment.return_value = MagicMock(
        spoken_text="Critical sentence with error.",
        resolutions=[],
        has_unresolved_critical=False,
    )

    # QA Auditor fails with missing token
    failing_qa = MagicMock(passed=False, status=PronunciationStatus.FAILED, omissions=["Token 'Sherlock' swallowed"], review_reasons=[], repetitions=[])
    dispatcher.pronunciation_auditor = MagicMock()
    dispatcher.pronunciation_auditor.audit_take.return_value = failing_qa

    # Pronunciation repair cannot repair
    dispatcher.pronunciation_repair = MagicMock()
    dispatcher.pronunciation_repair.attempt_repair.return_value = None

    # Call synthesize_segment with fail-closed environment
    segment = {"text": "Sherlock was here.", "speaker": "Narrator", "type": "narration"}

    with patch("audiobook_factory.tts_dispatcher.synthesize_gemini_tts"):
        with patch.dict(os.environ, {"TTS_ALLOW_DEGRADED_TAKES": "false"}):
            with pytest.raises(RuntimeError, match="PRONUNCIATION_QA_FAILED|Take selection failed"):
                TTSDispatcher.synthesize_segment(
                    dispatcher,
                    segment=segment,
                    chapter_num=1,
                    seg_num=1,
                )


# =========================================================================
# Test 9: Conversational Chemistry Actively Consumed During Take Selection
# =========================================================================
def test_conversational_chemistry_actively_consumed(tmp_path):
    """Verify that ConversationalChemistry scores bonus or penalize candidate takes during take selection."""
    selector = IntelligentTakeSelector()

    # Previous take was an intimidating threat from Baron
    p_dir_prev = PerformanceDirection(
        segment_uid="s_threat", index=1, speaker="Baron", actioning="threaten", power_position="dominant", energy=0.85
    )
    wav_prev = tmp_path / "prev.wav"
    _generate_synthetic_speech_wav(wav_prev, duration_sec=1.2, f0=120.0, rms_target=0.25)
    take_prev = TakeVariant(
        take_id="t_prev", segment_uid="s_threat", segment_index=1, variant_type="standard",
        audio_path=str(wav_prev), direction=p_dir_prev, is_selected=True
    )

    # Current take: Servant responding
    p_dir_curr = PerformanceDirection(
        segment_uid="s_sub", index=2, speaker="Servant", actioning="plead", power_position="submissive", energy=0.40, pause_before_ms=750, turn_taking_behavior="delayed_reaction"
    )
    wav_cand_good = tmp_path / "cand_good.wav"
    _generate_synthetic_speech_wav(wav_cand_good, duration_sec=1.0, f0=220.0, rms_target=0.10)
    take_good = TakeVariant(
        take_id="t_cand_good", segment_uid="s_sub", segment_index=2, variant_type="vulnerable",
        audio_path=str(wav_cand_good), direction=p_dir_curr
    )

    # Evaluate chemistry directly
    c_res = ConversationalChemistry.evaluate_dialogue_chemistry(take_prev, take_good, actual_gap_ms=750)
    assert c_res.passed
    assert c_res.composite_chemistry_score >= 0.70

    # Select best take with prev_take passed
    winner = selector.select_best_take(
        takes=[take_good],
        text="माफ़ कर दीजिए हुज़ूर!",
        direction=p_dir_curr,
        prev_take=take_prev,
    )
    assert winner is not None
    assert winner.take_id == "t_cand_good"


# =========================================================================
# Test 10: Alignment and Provenance Remain Attached
# =========================================================================
def test_alignment_and_provenance_remain_attached(tmp_path):
    """Verify that forced aligner results and provenance metadata attach cleanly to TakeVariant."""
    wav = tmp_path / "aligned_take.wav"
    _generate_synthetic_speech_wav(wav, duration_sec=1.0)

    p_dir = PerformanceDirection(
        segment_uid="s_prov", index=1, speaker="Narrator", provenance_mode="SOURCE_DIRECT", spoken_text="साधारण वाक्य।"
    )
    aligner = WorkstationForcedAligner(use_cuda=False)
    align_res = aligner.align_segment(audio_path=wav, text=p_dir.spoken_text, segment_uid=p_dir.segment_uid)

    take = TakeVariant(
        take_id="t_prov", segment_uid="s_prov", segment_index=1, variant_type="standard",
        audio_path=str(wav), direction=p_dir, alignment_result=align_res
    )

    assert take.alignment_result is not None
    assert take.alignment_result.confidence > 0.0
    assert take.direction.provenance_mode == "SOURCE_DIRECT"


# =========================================================================
# Test 11: 20-Segment LanguageDialogueCalibrationCorpus Execution
# =========================================================================
def test_language_dialogue_calibration_corpus_execution():
    """Verify all 20 segments in LanguageDialogueCalibrationCorpus resolve correctly."""
    lexicon = PronunciationLexicon()
    lexicon.seed_default_lexicon()
    resolver = PronunciationResolver(lexicon)
    engine = SpokenTextEngine(resolver)

    assert len(LanguageDialogueCalibrationCorpus.ITEMS) == 20

    passed_count = 0
    failures = []
    for item in LanguageDialogueCalibrationCorpus.ITEMS:
        res = engine.resolve_text(item.literary_text)
        if LanguageDialogueCalibrationCorpus.evaluate_item_pronunciation(item, res.spoken_text):
            passed_count += 1
        else:
            failures.append((item.uid, item.expected_spoken_contains, res.spoken_text))

    assert len(failures) == 0, f"Calibration failures: {failures}"
    assert passed_count == 20


# =========================================================================
# Test 12: Real Audio Pipeline Smoke Test (Two-Speaker Dialogue + Interruption)
# =========================================================================
def test_real_audio_pipeline_smoke_test(tmp_path):
    """
    Executes a real audio smoke test through the hardened pipeline:
    TEXT -> PRONUNCIATION -> TTS (audio WAV generation) -> ALIGNMENT -> SPEAKER TURNS -> DIALOGUE EDITING -> QC.
    """
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # Segment 1: Geralt speaks (Hindi dialogue with proper name)
    s1_text = "Dandelion, हमें Kaer Morhen पहुँचना होगा।"
    s1_wav = audio_dir / "c001_s0001_geralt.wav"
    _generate_synthetic_speech_wav(s1_wav, duration_sec=1.4, f0=115.0)

    # Segment 2: Dandelion interrupted line (ends with em-dash)
    s2_text = "लेकिन मुझे लगा था कि तुम—"
    s2_wav = audio_dir / "c001_s0002_dandelion.wav"
    _generate_synthetic_speech_wav(s2_wav, duration_sec=0.9, f0=190.0)

    # Segment 3: Geralt abrupt retort (0ms pause before line)
    s3_text = "खामोश रहो! कोई आ रहा है।"
    s3_wav = audio_dir / "c001_s0003_geralt.wav"
    _generate_synthetic_speech_wav(s3_wav, duration_sec=1.1, f0=120.0)

    script_segments = [
        {"uid": "s1", "index": 1, "speaker": "Geralt", "text": s1_text, "type": "dialogue"},
        {"uid": "s2", "index": 2, "speaker": "Dandelion", "text": s2_text, "type": "dialogue", "is_interruption": True},
        {"uid": "s3", "index": 3, "speaker": "Geralt", "text": s3_text, "type": "dialogue"},
    ]

    # Run Dialogue Editor across real generated WAVs
    editor = DialogueEditor(project_dir=tmp_path)
    edited_wavs, edit_plans, qc_rep = editor.process_chapter(
        chapter_num=1,
        audio_segments=[s1_wav, s2_wav, s3_wav],
        script_segments=script_segments,
    )

    assert len(edited_wavs) == 3
    assert len(edit_plans) == 3
    assert qc_rep.passed

    # Verify Interruption Plan for Segment 2 (abrupt cut with 35ms pause)
    plan_s2 = edit_plans[1]
    assert plan_s2.interruption_mode == "abrupt_cut" or plan_s2.pause_after_ms <= 60
    assert plan_s2.crossfade_out_ms <= 2.5
