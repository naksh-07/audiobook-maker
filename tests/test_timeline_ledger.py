#!/usr/bin/env python3
"""
Unit tests for Gate 4.5: Master Timeline & Audio Transcript Ledger.
Tests contracts, sample-accurate duration math, 100% text preservation, and gate auditing.
"""

import os
import wave
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from audiobook_factory.contracts import (
    TimelineSegment,
    TimelineLedger,
    ScreenplaySegment,
    ScreenplayScript,
)
from audiobook_factory.timeline_ledger import (
    build_audio_transcript_ledger,
    stitch_dialogue_track_from_ledger,
    get_wav_duration_ms,
)
from audiobook_factory.gate_auditor import audit_gate4_ledger, GateAuditError


def create_dummy_wav(path: Path, duration_sec: float = 1.0, sample_rate: int = 24000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(duration_sec * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # 16-bit PCM silent or small tone bytes
        wf.writeframes(b"\x10\x00" * num_samples)
    return path


class TestTimelineLedger(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_timeline_ledger_"))
        self.scripts_dir = self.test_dir / "scripts"
        self.audio_dir = self.test_dir / "audio_chunks"
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_timeline_segment_and_ledger_contracts(self):
        """Test strict validation, serialization and query methods of Timeline contracts."""
        seg1 = TimelineSegment(
            segment_index=1,
            speaker="Narrator",
            text="यह पहला वाक्य है।",
            audio_file="c001_s0001_a1b2c3d4.wav",
            duration_ms=2000,
            start_ms=0,
            end_ms=2000,
            pause_after_ms=500,
        )
        seg2 = TimelineSegment(
            segment_index=2,
            speaker="Geralt",
            text="यह गेराल्ट का संवाद है।",
            audio_file="c001_s0002_e5f6g7h8.wav",
            duration_ms=3000,
            start_ms=2500,
            end_ms=5500,
            pause_after_ms=600,
        )

        ledger = TimelineLedger(
            ledger_version="2.0",
            chapter_id="chapter_001",
            total_segments=2,
            total_dialogue_duration_ms=5000,
            total_timeline_duration_ms=5500,
            total_silence_duration_ms=500,
            silence_percentage=9.09,
            segments=[seg1, seg2],
        )

        # JSON Roundtrip
        raw_json = ledger.to_json()
        loaded = TimelineLedger.from_json(raw_json)
        self.assertEqual(loaded.total_segments, 2)
        self.assertEqual(loaded.segments[0].text, "यह पहला वाक्य है।")

        # Queries
        self.assertEqual(ledger.get_segment(1).speaker, "Narrator")
        self.assertEqual(ledger.get_segment(2).speaker, "Geralt")
        self.assertIsNone(ledger.get_segment(3))

        # Timestamp search
        found = ledger.find_segment_at_ms(1500)
        self.assertIsNotNone(found)
        self.assertEqual(found.segment_index, 1)

        # During pause
        in_pause = ledger.find_segment_at_ms(2200)
        self.assertIsNone(in_pause)

        found2 = ledger.find_segment_at_ms(3000)
        self.assertIsNotNone(found2)
        self.assertEqual(found2.segment_index, 2)

    def test_build_audio_transcript_ledger_and_audit(self):
        """Test build_audio_transcript_ledger generates valid ledger and passes Gate 4.5 audit."""
        script_path = self.scripts_dir / "chapter_001_hi_script.json"
        script_data = [
            {
                "index": 1,
                "type": "narration",
                "speaker": "Narrator",
                "text": "काउण्ट फालविक और युवा नाइट ताइलेस मंदिर के हॉल में दाखिल हुए।",
                "emotion": "neutral",
                "pause_after_ms": 400,
                "acoustic_env": "temple_stone_hall",
            },
            {
                "index": 2,
                "type": "dialogue",
                "speaker": "Falwick",
                "text": "नेनेके, हम ड्यूक हियरवर्ड का शाही फरमान लेकर आए हैं।",
                "emotion": "cold",
                "pause_after_ms": 500,
                "acoustic_env": "temple_stone_hall",
            }
        ]
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script_data, f, ensure_ascii=False)

        # Create matching audio chunks
        chunk1 = self.audio_dir / "c001_s0001_1111aaaa.wav"
        chunk2 = self.audio_dir / "c001_s0002_2222bbbb.wav"
        create_dummy_wav(chunk1, duration_sec=2.0)  # 2000 ms
        create_dummy_wav(chunk2, duration_sec=3.0)  # 3000 ms

        output_ledger_file = self.scripts_dir / "chapter_001_timeline_ledger.json"

        ledger = build_audio_transcript_ledger(
            project_dir=self.test_dir,
            chapter_num=1,
            script_file=script_path,
            audio_dir=self.audio_dir,
            output_ledger_file=output_ledger_file,
        )

        self.assertEqual(ledger.total_segments, 2)
        self.assertEqual(ledger.segments[0].start_ms, 0)
        self.assertEqual(ledger.segments[0].end_ms, 2000)
        # Second chunk starts at 2000 + 400 = 2400 ms
        self.assertEqual(ledger.segments[1].start_ms, 2400)
        self.assertEqual(ledger.segments[1].end_ms, 5400)
        # Total timeline = 5400 ms
        self.assertEqual(ledger.total_timeline_duration_ms, 5400)
        self.assertEqual(ledger.total_dialogue_duration_ms, 5000)

        # 100% text preservation check
        self.assertEqual(ledger.segments[0].text, script_data[0]["text"])
        self.assertEqual(ledger.segments[1].text, script_data[1]["text"])

        # Audit Gate 4.5
        audit_res = audit_gate4_ledger(output_ledger_file, script_path, self.audio_dir)
        self.assertEqual(audit_res["status"], "PASS")
        self.assertEqual(audit_res["total_segments"], 2)

    def test_audit_gate4_detects_truncation_or_corruption(self):
        """Test audit_gate4_ledger raises GateAuditError on text truncation or missing chunks."""
        script_path = self.scripts_dir / "chapter_002_hi_script.json"
        script_data = [
            {
                "index": 1,
                "type": "narration",
                "speaker": "Narrator",
                "text": "यह एक बहुत लम्बा वाक्य है जिसे कभी भी काटा या ट्रंकेट नहीं किया जाना चाहिए।",
                "emotion": "neutral",
                "pause_after_ms": 400,
            }
        ]
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script_data, f, ensure_ascii=False)

        chunk1 = self.audio_dir / "c002_s0001_hash1234.wav"
        create_dummy_wav(chunk1, duration_sec=1.5)

        # Create a ledger with truncated text to simulate old bug
        bad_ledger = TimelineLedger(
            ledger_version="2.0",
            chapter_id="chapter_002",
            total_segments=1,
            total_dialogue_duration_ms=1500,
            total_timeline_duration_ms=1500,
            segments=[
                TimelineSegment(
                    segment_index=1,
                    speaker="Narrator",
                    text="यह एक बहुत लम्बा...",  # Truncated!
                    audio_file=chunk1.name,
                    duration_ms=1500,
                    start_ms=0,
                    end_ms=1500,
                )
            ]
        )
        bad_ledger_file = self.scripts_dir / "chapter_002_bad_ledger.json"
        with open(bad_ledger_file, "w", encoding="utf-8") as f:
            f.write(bad_ledger.to_json())

        with self.assertRaises(GateAuditError) as ctx:
            audit_gate4_ledger(bad_ledger_file, script_path, self.audio_dir)
        self.assertIn("Text divergence", str(ctx.exception))

    def test_stitch_dialogue_track_from_ledger(self):
        """Test stitching vocal track produces sample-accurate duration."""
        chunk1 = self.audio_dir / "c003_s0001_aaaa.wav"
        chunk2 = self.audio_dir / "c003_s0002_bbbb.wav"
        create_dummy_wav(chunk1, duration_sec=1.0)  # 1000 ms
        create_dummy_wav(chunk2, duration_sec=2.0)  # 2000 ms

        ledger = TimelineLedger(
            ledger_version="2.0",
            chapter_id="chapter_003",
            total_segments=2,
            total_dialogue_duration_ms=3000,
            total_timeline_duration_ms=3500,
            segments=[
                TimelineSegment(
                    segment_index=1,
                    speaker="Narrator",
                    text="Chunk 1",
                    audio_file=chunk1.name,
                    duration_ms=1000,
                    start_ms=0,
                    end_ms=1000,
                    pause_after_ms=500,
                ),
                TimelineSegment(
                    segment_index=2,
                    speaker="Geralt",
                    text="Chunk 2",
                    audio_file=chunk2.name,
                    duration_ms=2000,
                    start_ms=1500,
                    end_ms=3500,
                    pause_after_ms=400,
                ),
            ]
        )

        out_vocal = self.test_dir / "chapter_003_dialogue.wav"
        stitch_dialogue_track_from_ledger(ledger, self.audio_dir, out_vocal)

        self.assertTrue(out_vocal.exists())
        # Expected duration = 1.0s + 0.5s pause + 2.0s = 3.5s = 3500 ms
        dur_ms = get_wav_duration_ms(out_vocal)
        self.assertEqual(dur_ms, 3500)


if __name__ == "__main__":
    unittest.main()
