#!/usr/bin/env python3
"""
Test Suite: Pre-TTS Smart Batch Dispatch Planner, UID Tracking,
Acoustic De-Clicking, and Workstation Forced Alignment (ADR-024).
"""

import wave
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from audiobook_factory.contracts import (
    ScreenplaySegment,
    ActingInstructions,
    SpatialCoordinates,
    BatchPlanItem,
    BatchDispatchManifest,
)
from audiobook_factory.batch_planner import BatchDispatchPlanner
from audiobook_factory.forced_aligner import (
    WorkstationForcedAligner,
    transliterate_devanagari_to_roman,
)
from audiobook_factory.tts_dispatcher import (
    resolve_speech_metadata_style,
    slice_and_declick_batch,
)


def create_dummy_wav(path: Path, duration_sec: float = 2.0, sample_rate: int = 24000):
    """Creates a temporary valid 24kHz mono PCM WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    num_frames = int(sample_rate * duration_sec)
    silence = b"\x00" * (num_frames * 2)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(silence)


class TestUIDAndContracts:
    def test_uid_auto_generation(self):
        seg = ScreenplaySegment(
            index=1,
            type="dialogue",
            speaker="Geralt",
            text="यह रास्ता बहुत खतरनाक है।",
        )
        assert seg.uid != ""
        assert seg.uid.startswith("s0001_geralt_")

    def test_uid_preservation(self):
        seg = ScreenplaySegment(
            uid="custom_unique_id_999",
            index=5,
            type="dialogue",
            speaker="Dandelion",
            text="मैं तुम्हारे साथ चलूँगा।",
        )
        assert seg.uid == "custom_unique_id_999"


class TestBatchDispatchPlanner:
    def test_planner_intimate_isolation(self):
        planner = BatchDispatchPlanner(enabled=True)
        seg = ScreenplaySegment(
            index=1,
            type="dialogue",
            speaker="Yennefer",
            text="पास आओ...",
            spatial=SpatialCoordinates(proximity="intimate_close"),
            pre_roll_breath_ms=250,
        )
        classification = planner.classify_segment(seg)
        assert classification == "isolated_intimate"

    def test_planner_combat_isolation(self):
        planner = BatchDispatchPlanner(enabled=True)
        seg_action = ScreenplaySegment(
            index=2,
            type="action",
            speaker="Foley",
            text="[ACTION]",
            sfx_cues=["sword_clash"],
        )
        assert planner.classify_segment(seg_action) == "isolated_combat"

        seg_combat = ScreenplaySegment(
            index=3,
            type="dialogue",
            speaker="Geralt",
            text="[combat roar] वार करो!",
            intensity_level="explosive",
        )
        assert planner.classify_segment(seg_combat) == "isolated_combat"

    def test_planner_stereo_panned_dialogue_batches(self):
        """Validates that regular dialogue with stereo spatial panning is batched rather than trapped in combat."""
        planner = BatchDispatchPlanner(enabled=True, max_words_per_batch=500)
        segments = [
            ScreenplaySegment(index=1, type="dialogue", speaker="Geralt", text="नमस्ते दोस्त", spatial=SpatialCoordinates(pan=-0.4)),
            ScreenplaySegment(index=2, type="dialogue", speaker="Dandelion", text="हाँ बिलकुल", spatial=SpatialCoordinates(pan=0.4)),
        ]
        manifest = planner.plan_chapter_batches(segments)
        assert manifest.total_batches == 1
        assert manifest.batches[0].strategy == "multi_speaker_duo"

    def test_batch_id_character_token_sanitization(self):
        """Validates that character names with spaces or apostrophes produce sanitized batch IDs."""
        planner = BatchDispatchPlanner(enabled=True)
        segments = [
            ScreenplaySegment(index=1, type="dialogue", speaker="Tavern Thug", text="यहाँ से निकलो!"),
            ScreenplaySegment(index=2, type="dialogue", speaker="Innkeeper's Wife", text="रुकिए, झगड़ा मत करो!"),
        ]
        manifest = planner.plan_chapter_batches(segments)
        assert manifest.total_batches == 1
        b_id = manifest.batches[0].batch_id
        assert " " not in b_id
        assert "'" not in b_id
        assert "tavern_thug" in b_id
        assert "innkeeper_s_wife" in b_id

    def test_planner_2_speaker_dialogue_batching(self):
        planner = BatchDispatchPlanner(enabled=True, max_words_per_batch=500)
        segments = [
            ScreenplaySegment(index=1, type="dialogue", speaker="Geralt", text="तुम यहाँ क्या कर रहे हो?"),
            ScreenplaySegment(index=2, type="dialogue", speaker="Dandelion", text="मैं तुम्हारा इंतज़ार कर रहा था।"),
            ScreenplaySegment(index=3, type="dialogue", speaker="Geralt", text="हमें तुरंत निकलना होगा।"),
            ScreenplaySegment(index=4, type="dialogue", speaker="Dandelion", text="चलो फिर, देर किस बात की!"),
        ]
        manifest = planner.plan_chapter_batches(segments, chapter_id="chapter_001", chapter_num=1)
        assert manifest.total_segments == 4
        assert manifest.total_batches == 1
        batch = manifest.batches[0]
        assert batch.strategy == "multi_speaker_duo"
        assert set(batch.speakers) == {"Geralt", "Dandelion"}
        assert len(batch.segments) == 4
        assert manifest.quota_savings_ratio == 75.0

    def test_planner_3_speaker_sliding_window(self):
        planner = BatchDispatchPlanner(enabled=True, max_words_per_batch=500)
        segments = [
            ScreenplaySegment(index=1, type="dialogue", speaker="Geralt", text="पहला संवाद।"),
            ScreenplaySegment(index=2, type="dialogue", speaker="Dandelion", text="दूसरा संवाद।"),
            ScreenplaySegment(index=3, type="dialogue", speaker="Yennefer", text="तीसरा पात्र आ गया!"),
            ScreenplaySegment(index=4, type="dialogue", speaker="Geralt", text="चौथा संवाद।"),
        ]
        manifest = planner.plan_chapter_batches(segments, chapter_id="chapter_001", chapter_num=1)
        # Should split across speaker transitions to never exceed 2 speakers in multi_speaker_duo
        for b in manifest.batches:
            if b.strategy == "multi_speaker_duo":
                assert len(b.speakers) == 2


class TestSpeechMetadataAndStyle:
    def test_resolve_speech_metadata_style(self):
        acting = ActingInstructions(delivery_style="whispered_threat")
        style = resolve_speech_metadata_style(acting, emotion="menacing", intensity="explosive")
        assert "whispered threat" in style
        assert "menacing" in style
        assert "extreme intensity" in style

    def test_resolve_neutral_style(self):
        acting = ActingInstructions(delivery_style="neutral")
        style = resolve_speech_metadata_style(acting, emotion="neutral", intensity="medium")
        assert style == "neutral"


class TestWorkstationForcedAligner:
    def test_transliterate_devanagari_to_roman(self):
        text = "[whispers] यह रास्ता बहुत खतरनाक है!"
        roman = transliterate_devanagari_to_roman(text)
        assert "whispers" not in roman  # bracketed tag stripped
        assert "rasta" in roman
        assert "khtrnak" in roman

    def test_energy_fallback_alignment(self, tmp_path):
        wav_file = tmp_path / "test_batch.wav"
        create_dummy_wav(wav_file, duration_sec=4.0)

        aligner = WorkstationForcedAligner(use_cuda=False)
        segments = [
            ScreenplaySegment(index=1, type="dialogue", speaker="Geralt", text="चार शब्द यहाँ हैं"),
            ScreenplaySegment(index=2, type="dialogue", speaker="Dandelion", text="चार शब्द यहाँ भी"),
        ]
        boundaries = aligner._align_with_energy_fallback(wav_file, segments)
        assert len(boundaries) == 2
        assert boundaries[0][0] == 0
        assert boundaries[1][1] == 4000
        assert boundaries[0][1] == boundaries[1][0]


class TestSliceAndDeclick:
    def test_slice_and_declick_batch(self, tmp_path):
        raw_wav = tmp_path / "raw_batch.wav"
        create_dummy_wav(raw_wav, duration_sec=4.0)

        batch_plan = BatchPlanItem(
            batch_id="b001_duo",
            strategy="multi_speaker_duo",
            uids=["s0001", "s0002"],
            speakers=["Geralt", "Dandelion"],
            voice_map={"Geralt": "Charon", "Dandelion": "Puck"},
            segments=[
                ScreenplaySegment(index=1, type="dialogue", speaker="Geralt", text="नमस्ते दोस्त"),
                ScreenplaySegment(index=2, type="dialogue", speaker="Dandelion", text="हाँ दोस्त"),
            ],
            total_words=4,
        )

        out_dir = tmp_path / "slices"
        out_dir.mkdir(parents=True, exist_ok=True)

        sliced = slice_and_declick_batch(
            raw_audio=raw_wav,
            batch=batch_plan,
            chapter_num=1,
            output_dir=out_dir,
            declick_fade_ms=5.0,
        )

        assert len(sliced) == 2
        for s_path, s_dur in sliced:
            assert s_path.exists()
            assert s_dur > 0.0
            with wave.open(str(s_path), "rb") as wf:
                assert wf.getframerate() == 24000
                assert wf.getnchannels() == 1

    def test_gpu_mms_fa_live_execution(self, tmp_path):
        """Validates that MMS_FA loads and executes on CUDA or CPU without throwing backend exceptions."""
        wav_file = tmp_path / "test_mms_fa.wav"
        create_dummy_wav(wav_file, duration_sec=3.0, sample_rate=24000)

        aligner = WorkstationForcedAligner(use_cuda=True)
        segments = [
            ScreenplaySegment(index=1, type="dialogue", speaker="Geralt", text="नमस्ते दोस्त"),
            ScreenplaySegment(index=2, type="dialogue", speaker="Dandelion", text="हाँ बिलकुल"),
        ]
        boundaries = aligner.align_batch(wav_file, segments)
        assert len(boundaries) == 2
        assert boundaries[0][0] == 0
        assert boundaries[1][1] == 3000
        assert boundaries[0][1] <= boundaries[1][0]


class TestDispatcherBatchIntegration:
    def test_synthesize_chapter_script_batch_e2e(self, tmp_path):
        """End-to-end integration test verifying zero redundant single calls when batching succeeds."""
        import json
        from audiobook_factory.tts_dispatcher import TTSDispatcher

        audio_dir = tmp_path / "audio_chunks"
        audio_dir.mkdir(parents=True)

        script_file = tmp_path / "chapter_001_script.json"
        script_data = {
            "script_version": "2.0",
            "segments": [
                {"index": 1, "type": "dialogue", "speaker": "Geralt", "text": "नमस्ते दोस्त"},
                {"index": 2, "type": "dialogue", "speaker": "Dandelion", "text": "हाँ बिलकुल"},
            ]
        }
        script_file.write_text(json.dumps(script_data), encoding="utf-8")

        roster_file = tmp_path / "character_roster.json"
        roster_file.write_text(json.dumps({
            "characters": {
                "Geralt": {"gender": "male", "aliases": []},
                "Dandelion": {"gender": "male", "aliases": []}
            }
        }), encoding="utf-8")

        reg_file = tmp_path / "voice_registry.json"
        reg_file.write_text(json.dumps({
            "Narrator": {"backend": "gemini_tts", "voice": "Aoede"},
            "Geralt": {"backend": "gemini_tts", "voice": "Charon"},
            "Dandelion": {"backend": "gemini_tts", "voice": "Puck"}
        }), encoding="utf-8")

        dispatcher = TTSDispatcher(project_dir=tmp_path, audio_dir=audio_dir, strict_speakers=False)
        calls = {"batch": 0, "single": 0}

        def fake_multispeaker(batch, output_file, voice_map, rate_limiter=None):
            calls["batch"] += 1
            create_dummy_wav(output_file, duration_sec=3.0, sample_rate=24000)
            return output_file, 3.0

        def fake_single(text, output_file, voice="Aoede", model="m", emotion="neutral", max_retries=4, rate_limiter=None):
            calls["single"] += 1
            create_dummy_wav(output_file, duration_sec=1.5, sample_rate=24000)
            return output_file, 1.5

        with patch("audiobook_factory.tts_dispatcher.synthesize_gemini_multispeaker_batch", side_effect=fake_multispeaker), \
             patch("audiobook_factory.tts_dispatcher.synthesize_gemini_tts", side_effect=fake_single):
            results = dispatcher.synthesize_chapter_script(script_file, chapter_num=1)

        assert calls["batch"] == 1
        assert calls["single"] == 0
        assert len(results) == 2
        for r in results:
            assert r.exists()
            assert r.stat().st_size > 1000

        # Test resume (should make 0 batch calls and 0 single calls)
        calls["batch"] = 0
        calls["single"] = 0
        with patch("audiobook_factory.tts_dispatcher.synthesize_gemini_multispeaker_batch", side_effect=fake_multispeaker), \
             patch("audiobook_factory.tts_dispatcher.synthesize_gemini_tts", side_effect=fake_single):
            resume_results = dispatcher.synthesize_chapter_script(script_file, chapter_num=1)

        assert calls["batch"] == 0
        assert calls["single"] == 0
        assert len(resume_results) == 2
