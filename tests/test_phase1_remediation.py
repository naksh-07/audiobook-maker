#!/usr/bin/env python3
"""
Test Suite: Phase 1 Audio Timing & State Integrity Remediation.
Verifies the 5 forensic fixes:
1. Action beat silent canvas format matches Gemini TTS exactly (24kHz, 1-ch mono).
2. Timeline ledger stitching safely normalizes format mismatches without 4x time distortion.
3. State ledger auto-heals desynced segment IDs via c{ch}_s{seg} composite key extraction.
4. Screenplay Pass 2 preserves newly introduced characters without "Narrator Fallback" erasure.
5. Screenplay Pass 2 preserves intensity_level and pre_roll_breath_ms dynamics attributes.
6. TTS dispatcher cleanly propagates AllKeysExhaustedTodayError for stealth pause.
"""

import sys
import wave
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.tts_dispatcher import (
    TTSDispatcher,
    AllKeysExhaustedTodayError,
)
from audiobook_factory.state import ProjectStateLedger
from audiobook_factory.script_builder import clean_screenplay_pass2
from audiobook_factory.timeline_ledger import (
    stitch_dialogue_track_from_ledger,
    TimelineLedger,
    TimelineSegment,
)


class TestPhase1Remediation(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_action_beat_silent_canvas_format(self):
        """Action beat canvas must be 24000Hz, 1 channel mono, 16-bit PCM, matching speech."""
        audio_dir = self.project_dir / "audio"
        dispatcher = TTSDispatcher(project_dir=self.project_dir, audio_dir=audio_dir)

        action_segment = {
            "type": "action",
            "speaker": "Foley",
            "text": "[ACTION] Sword clashing",
            "pause_after_ms": 1500,
        }

        wav_path, dur = dispatcher.synthesize_segment(action_segment, chapter_num=1, seg_num=3)
        self.assertTrue(wav_path.exists())
        self.assertEqual(dur, 1.5)

        with wave.open(str(wav_path), "rb") as wf:
            self.assertEqual(wf.getnchannels(), 1, "Must be 1-channel mono, not stereo")
            self.assertEqual(wf.getframerate(), 24000, "Must be 24000Hz, not 48000Hz")
            self.assertEqual(wf.getsampwidth(), 2, "Must be 16-bit PCM (2 bytes/sample)")
            expected_frames = int(24000 * 1.5)
            self.assertEqual(wf.getnframes(), expected_frames)

    def test_02_stitch_dialogue_normalizes_heterogeneous_chunks(self):
        """Stitching must normalize non-standard chunks (e.g. 48kHz stereo) to 24kHz mono without stretching."""
        audio_dir = self.project_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        # Chunk 1: standard 24kHz mono (1.0s)
        chunk1 = audio_dir / "c001_s0001_aaa.wav"
        with wave.open(str(chunk1), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(b"\x00\x00" * 24000)  # 1 second silence

        # Chunk 2: legacy/external 48kHz stereo (1.0s = 48000 frames = 192000 bytes)
        chunk2 = audio_dir / "c001_s0002_bbb.wav"
        with wave.open(str(chunk2), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(b"\x00\x00\x00\x00" * 48000)  # 1 second silence in 48kHz stereo

        seg1 = TimelineSegment(
            segment_index=1,
            speaker="Narrator",
            text="Hello world.",
            audio_file="c001_s0001_aaa.wav",
            duration_ms=1000,
            start_ms=0,
            end_ms=1000,
            pause_after_ms=500,
        )
        seg2 = TimelineSegment(
            segment_index=2,
            speaker="Foley",
            text="[ACTION]",
            audio_file="c001_s0002_bbb.wav",
            duration_ms=1000,
            start_ms=1500,
            end_ms=2500,
            pause_after_ms=0,
        )

        ledger = TimelineLedger(
            chapter_id="1",
            total_segments=2,
            total_timeline_duration_ms=2500,
            total_dialogue_duration_ms=2000,
            total_silence_duration_ms=500,
            silence_percentage=20.0,
            segments=[seg1, seg2],
        )

        out_wav = self.project_dir / "master_dialogue.wav"
        res_path = stitch_dialogue_track_from_ledger(ledger, audio_dir, out_wav, sample_rate=24000)
        self.assertTrue(res_path.exists())

        with wave.open(str(res_path), "rb") as wf:
            self.assertEqual(wf.getnchannels(), 1)
            self.assertEqual(wf.getframerate(), 24000)
            total_frames = wf.getnframes()
            dur_sec = total_frames / 24000.0
            # Total expected: 1.0s + 0.5s pause + 1.0s = 2.5 seconds
            # Previously with 48kHz stereo, chunk 2 would blow out to 4.0s!
            self.assertAlmostEqual(dur_sec, 2.5, delta=0.05)

    def test_03_state_ledger_composite_key_and_hash_desync(self):
        """State ledger must complete segments using composite key or regex extraction when hash desync occurs."""
        ledger = ProjectStateLedger(self.project_dir)
        script = [
            {"index": 1, "speaker": "Geralt", "text": "Hmm."},
            {"index": 2, "speaker": "Yennefer", "text": "Geralt, listen."},
        ]
        ledger.register_script_segments(chapter_num=1, script=script, voice_map={}, default_voice="Puck")

        pending = ledger.get_pending_segments(1)
        self.assertEqual(len(pending), 2)
        initial_id = pending[0]["id"]

        # 1. Test auto-extraction of c001_s0001 from a desynced segment_id without explicit chapter/seg
        desynced_id_1 = "c001_s0001_99999999"
        ledger.mark_segment_started(desynced_id_1)
        segs = ledger.get_chapter_segments(1)
        self.assertEqual(segs[0]["status"], "IN_PROGRESS", "Must match by extracted c001_s0001")

        # 2. Test completion with explicit chapter_num and seg_num even if ID has arbitrary suffix
        desynced_id_2 = "c001_s0001_calibrated_eq_audio"
        ledger.mark_segment_completed(
            segment_id=desynced_id_2,
            audio_path="/path/to/c001_s0001.wav",
            duration_sec=1.45,
            chapter_num=1,
            seg_num=1,
        )
        segs = ledger.get_chapter_segments(1)
        self.assertEqual(segs[0]["status"], "COMPLETED")
        self.assertEqual(segs[0]["duration_sec"], 1.45)
        self.assertEqual(segs[0]["audio_path"], "/path/to/c001_s0001.wav")

        # 3. Test failure marking with extracted regex
        desynced_id_fail = "c001_s0002_randomhash"
        ledger.mark_segment_failed(desynced_id_fail, "Simulated network timeout")
        segs = ledger.get_chapter_segments(1)
        self.assertEqual(segs[1]["status"], "FAILED")
        self.assertEqual(segs[1]["error_message"], "Simulated network timeout")

    def test_04_script_builder_preserves_new_characters(self):
        """clean_screenplay_pass2 must not erase newly introduced characters to 'Narrator'."""
        roster_ch1 = {
            "characters": {
                "Harry": {"gender": "male", "aliases": ["harry potter", "the boy"]},
            }
        }
        raw_items = [
            {"speaker": "Harry", "text": "Hello there.", "type": "dialogue"},
            {"speaker": "Dumbledore", "text": "Welcome to Hogwarts, Harry.", "type": "dialogue"},
            {"speaker": "King Foltest", "text": "Who enters my throne room?", "type": "dialogue"},
            {"speaker": "Pavetta", "text": "Mother, please!", "type": "dialogue"},
        ]

        cleaned = clean_screenplay_pass2(raw_items, character_roster=roster_ch1, is_hindi=False)

        speakers = [item["speaker"] for item in cleaned]
        self.assertEqual(speakers[0], "Harry")
        self.assertEqual(speakers[1], "Dumbledore", "Dumbledore must not be downgraded to Narrator!")
        self.assertEqual(speakers[2], "King Foltest", "King Foltest must not be downgraded to Narrator!")
        self.assertEqual(speakers[3], "Pavetta", "Pavetta must not be downgraded to Narrator!")

    def test_05_script_builder_preserves_breath_and_intensity_dynamics(self):
        """clean_screenplay_pass2 must preserve pre_roll_breath_ms and intensity_level attributes."""
        raw_items = [
            {
                "speaker": "Geralt",
                "text": "Quiet... something is in the shadows.",
                "type": "dialogue",
                "intensity_level": "explosive",
                "pre_roll_breath_ms": 220,
                "pause_after_ms": 800,
            }
        ]

        cleaned = clean_screenplay_pass2(raw_items, character_roster=None, is_hindi=False)
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["intensity_level"], "explosive")
        self.assertEqual(cleaned[0]["pre_roll_breath_ms"], 220)

    def test_06_tts_dispatcher_reraises_quota_error(self):
        """TTSDispatcher must re-raise AllKeysExhaustedTodayError to allow orchestrator stealth pause."""
        import json
        dispatcher = TTSDispatcher(project_dir=self.project_dir)
        script_file = self.project_dir / "chapter_001.json"
        script_data = [
            {"index": 1, "speaker": "Narrator", "text": "Chapter one began in silence."},
        ]
        with open(script_file, "w", encoding="utf-8") as f:
            json.dump(script_data, f)

        with patch.object(dispatcher, "synthesize_segment", side_effect=AllKeysExhaustedTodayError("RPD quota exhausted")):
            with self.assertRaises(AllKeysExhaustedTodayError):
                dispatcher.synthesize_chapter_script(script_file, chapter_num=1)


if __name__ == "__main__":
    unittest.main()
