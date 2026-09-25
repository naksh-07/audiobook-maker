#!/usr/bin/env python3
"""
Unit tests for Audio-Level Pronunciation QA, Targeted Repair Engine, and Cross-Chapter Consistency.
"""

import unittest
import tempfile
import wave
import json
from pathlib import Path

from audiobook_factory.pronunciation.contracts import (
    SpokenTextResult,
    PronunciationResolutionResult,
    PronunciationStatus,
    PronunciationSource,
)
from audiobook_factory.pronunciation.auditor import PronunciationAudioQA
from audiobook_factory.pronunciation.repair import PronunciationRepairEngine
from audiobook_factory.pronunciation.consistency import CrossChapterConsistencyAuditor


def create_mock_wav(path: Path, duration_sec: float = 2.0, sample_rate: int = 24000):
    """Creates a mock 24kHz mono PCM WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    num_frames = int(sample_rate * duration_sec)
    # Generate low-amplitude noise / tone bytes so RMS > 0
    import struct
    samples = [int(1000 * (i % 20 - 10)) for i in range(num_frames)]
    pcm = struct.pack(f"<{num_frames}h", *samples)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)


class TestAudioQARepairAndConsistency(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_audio_qa_valid_take(self):
        wav_path = self.output_dir / "valid_take.wav"
        create_mock_wav(wav_path, duration_sec=3.0)

        spoken_res = SpokenTextResult(
            literary_text="Sherlock Holmes यहाँ आया था।",
            display_text="Sherlock Holmes यहाँ आया था।",
            spoken_text="शरलॉक होम्स यहाँ आया था।",
            resolutions=[
                PronunciationResolutionResult(
                    original_token="Sherlock Holmes",
                    canonical_id="sherlock_holmes",
                    resolved_spoken="शरलॉक होम्स",
                    status=PronunciationStatus.VERIFIED,
                    source=PronunciationSource.CANONICAL_LEXICON,
                    transformation_applied=True,
                )
            ]
        )

        auditor = PronunciationAudioQA(forced_aligner=None)
        qa_res = auditor.audit_take(wav_path, spoken_res, take_id="take_01", segment_uid="s0001")

        self.assertTrue(qa_res.passed)
        self.assertEqual(qa_res.status, PronunciationStatus.VERIFIED)
        self.assertEqual(len(qa_res.omissions), 0)

    def test_02_audio_qa_missing_or_corrupted_file(self):
        auditor = PronunciationAudioQA(forced_aligner=None)
        missing_path = self.output_dir / "nonexistent.wav"

        spoken_res = SpokenTextResult(
            literary_text="test",
            display_text="test",
            spoken_text="test",
        )
        qa_res = auditor.audit_take(missing_path, spoken_res)
        self.assertFalse(qa_res.passed)
        self.assertEqual(qa_res.status, PronunciationStatus.FAILED)

    def test_03_repair_engine_text_mutation(self):
        repair_engine = PronunciationRepairEngine()
        from audiobook_factory.pronunciation.contracts import PronunciationAudioQAResult
        mock_qa = PronunciationAudioQAResult(
            take_id="take_01",
            segment_uid="s0001",
            passed=False,
            status=PronunciationStatus.FAILED,
            omissions=["Token 'शरलॉक' suspiciously truncated"],
        )

        original_spoken = "उसने कहा शरलॉक यहाँ आया था।"
        repaired = repair_engine.generate_repaired_spoken_text(original_spoken, mock_qa)

        # Token should be wrapped with breathing commas
        self.assertIn(", शरलॉक ,", repaired)

    def test_04_cross_chapter_consistency_detection(self):
        scripts_dir = self.output_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        # Chapter 1 script with 'ओस्ट्रिट'
        ch1_script = [
            {
                "index": 1,
                "chapter_num": 1,
                "speaker": "Narrator",
                "text": "Ostrit ने देखा।",
                "pronunciation_metadata": [
                    {"canonical_id": "ostrit", "original_token": "Ostrit", "resolved_spoken": "ओस्ट्रिट", "status": "VERIFIED"}
                ]
            }
        ]
        with open(scripts_dir / "chapter_001_script.json", "w", encoding="utf-8") as f:
            json.dump(ch1_script, f)

        # Chapter 2 script with drifted 'ऑस्ट्रिट'
        ch2_script = [
            {
                "index": 1,
                "chapter_num": 2,
                "speaker": "Narrator",
                "text": "Ostrit आगे बढ़ा।",
                "pronunciation_metadata": [
                    {"canonical_id": "ostrit", "original_token": "Ostrit", "resolved_spoken": "ऑस्ट्रिट", "status": "VERIFIED"}
                ]
            }
        ]
        with open(scripts_dir / "chapter_002_script.json", "w", encoding="utf-8") as f:
            json.dump(ch2_script, f)

        auditor = CrossChapterConsistencyAuditor()
        drifts = auditor.audit_project(self.output_dir)

        self.assertEqual(len(drifts), 1)
        self.assertEqual(drifts[0].canonical_id, "ostrit")
        self.assertTrue(drifts[0].drift_detected)
        self.assertFalse(drifts[0].allowed_exception)

        # Now test with allowed exception
        auditor_with_exc = CrossChapterConsistencyAuditor(allowed_exceptions={"ostrit": "Accent shift in foreign province"})
        drifts_exc = auditor_with_exc.audit_project(self.output_dir)
        self.assertEqual(len(drifts_exc), 1)
        self.assertTrue(drifts_exc[0].allowed_exception)


if __name__ == "__main__":
    unittest.main()
