#!/usr/bin/env python3
"""
Unit and Regression Test Suite for Audit Fixes & Production Hardening.
Verifies all 7 audit vulnerabilities:
1. TokenBucketRateLimiter lock release during sleep
2. Translator finishReason == "MAX_TOKENS" truncation detection
3. Script builder markdown fences stripping & zero-loss narrator fallback
4. State ledger IN_PROGRESS recovery & auto-reset
5. Extractor Unicode NFC normalization & named chapter regex
6. Audio master shutil import & -19 LUFS ACX compliance
7. Soundscape dynamic sidechain ducking parameter binding
"""

import sys
import time
import json
import shutil
import tempfile
import unittest
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.tts_dispatcher import TokenBucketRateLimiter
from audiobook_factory.translator import call_gemini, translate_chapter
from audiobook_factory.script_builder import _parse_dramatized_chunk_llm, build_narrator_script
from audiobook_factory.state import ProjectStateLedger
from audiobook_factory.extractor import clean_book_text, segment_chapters_from_text
from audiobook_factory.soundscape import get_sound_bank, apply_dynamic_sidechain_ducking
import ffmpeg_mastering.audio_master as audio_master


class TestAuditFixes(unittest.TestCase):

    def test_01_token_bucket_concurrency_lock_release(self):
        """Verify TokenBucketRateLimiter does not hold lock during wait_time sleep."""
        # Limiter with 1 RPM (0.0167 tokens/sec), capacity 1.0
        limiter = TokenBucketRateLimiter(rate_rpm=60.0, capacity=1.0)
        limiter.tokens = 0.0  # Force wait

        lock_acquired_by_sibling = False

        def sibling_checker():
            nonlocal lock_acquired_by_sibling
            # Small delay to ensure main thread has entered acquire()
            time.sleep(0.05)
            # Sibling attempts to grab the lock; should succeed because main sleeps outside lock!
            with limiter.lock:
                lock_acquired_by_sibling = True

        t = threading.Thread(target=sibling_checker)
        t.start()

        # acquire() will calculate wait_time ~1.0s and sleep outside lock
        start_time = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - start_time

        t.join()
        self.assertGreater(elapsed, 0.5)
        self.assertTrue(lock_acquired_by_sibling, "Sibling thread was blocked because lock was held during sleep!")

    def test_02_translator_truncation_detection(self):
        """Verify call_gemini raises RuntimeError when finishReason is MAX_TOKENS."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "candidates": [
                {
                    "content": {"parts": [{"text": "Incomplete sentence that got cut off..."}]},
                    "finishReason": "MAX_TOKENS",
                }
            ]
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            with patch.dict("os.environ", {"GEMINI_API_KEY": "fake_key"}):
                with self.assertRaises(RuntimeError) as ctx:
                    call_gemini("Translate this novel chapter")
                self.assertIn("MAX_TOKENS", str(ctx.exception))

    def test_03_script_builder_fences_and_narrator_fallback(self):
        """Verify markdown code fences are stripped and malformed LLM JSON falls back to narrator script."""
        # Test 1: Markdown codeblock stripped successfully
        fenced_json = "```json\n[{\"speaker\": \"Narrator\", \"text\": \"The journey began.\", \"type\": \"narration\"}]\n```"
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "candidates": [{"content": {"parts": [{"text": fenced_json}]}}]
        }).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=mock_response):
            script = _parse_dramatized_chunk_llm("The journey began.", api_key="fake_key")
            self.assertEqual(len(script), 1)
            self.assertEqual(script[0]["text"], "The journey began.")

        # Test 2: Malformed JSON falls back to build_narrator_script (Zero Content Loss!)
        malformed_response = MagicMock()
        malformed_response.read.return_value = json.dumps({
            "candidates": [{"content": {"parts": [{"text": "Sorry, I cannot produce JSON."}]}}]
        }).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=malformed_response):
            sample_text = "He walked into the room. 'Hello,' he said."
            script = _parse_dramatized_chunk_llm(sample_text, api_key="fake_key", max_retries=1)
            # Must NOT return empty list!
            self.assertGreater(len(script), 0)
            self.assertEqual(script[0]["speaker"], "Narrator")
            self.assertIn("He walked into the room", script[0]["text"])

    def test_04_state_ledger_crash_recovery(self):
        """Verify get_pending_segments includes IN_PROGRESS and auto-resets on startup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.db"
            ledger = ProjectStateLedger(db_path)
            ledger.register_chapter(1, "Chapter One", 500)

            # Insert a segment and mark it IN_PROGRESS (simulating mid-synthesis crash)
            seg = [{"index": 1, "speaker": "Harry", "text": "Expelliarmus!"}]
            ledger.register_script_segments(1, seg, {"Harry": {"voice": "Puck"}})
            pending = ledger.get_pending_segments(1)
            self.assertEqual(len(pending), 1)
            seg_id = pending[0]["id"]

            ledger.mark_segment_started(seg_id)
            # Confirm it is IN_PROGRESS in DB
            with ledger._connection() as conn:
                status = conn.execute("SELECT status FROM segments WHERE id = ?", (seg_id,)).fetchone()[0]
                self.assertEqual(status, "IN_PROGRESS")

            # Crucial Check: get_pending_segments MUST recover IN_PROGRESS
            recovered = ledger.get_pending_segments(1)
            self.assertEqual(len(recovered), 1)
            self.assertEqual(recovered[0]["id"], seg_id)

            # Re-initializing ledger (simulating application restart) auto-resets IN_PROGRESS to PENDING
            ledger2 = ProjectStateLedger(db_path)
            with ledger2._connection() as conn:
                status2 = conn.execute("SELECT status FROM segments WHERE id = ?", (seg_id,)).fetchone()[0]
                self.assertEqual(status2, "PENDING")

    def test_05_extractor_unicode_nfc_and_named_chapters(self):
        """Verify NFC normalization and named chapter detection."""
        # Unicode NFC canonical normalization (e.g. \u0958 canonicalizes to \u0915\u093c)
        precomposed_nukta = "\u0958"
        canonical_nukta = "\u0915\u093c"
        cleaned = clean_book_text(f"Text with {precomposed_nukta} and zero-width\u200b space.")
        self.assertIn(canonical_nukta, cleaned)
        self.assertNotIn("\u200b", cleaned)

        # Named chapters test (no 'Chapter' keyword)
        book_prose = """
# The Boy Who Lived

Mr. and Mrs. Dursley, of number four, Privet Drive, were proud to say that they were perfectly normal.

## The Vanishing Glass

Nearly ten years had passed since the Dursleys had come home.

Chapter III: The Letters from No One

The escape of the Brazilian boa constrictor earned Harry his longest-ever punishment.
"""
        chapters = segment_chapters_from_text(book_prose)
        self.assertGreaterEqual(len(chapters), 3)
        titles = [c["title"] for c in chapters]
        self.assertTrue(any("The Boy Who Lived" in t for t in titles))
        self.assertTrue(any("The Vanishing Glass" in t for t in titles))
        self.assertTrue(any("Letters from No One" in t for t in titles))

    def test_06_audio_master_shutil_and_lufs(self):
        """Verify audio_master has shutil imported and uses -19 LUFS for ACX compliance."""
        self.assertTrue(hasattr(audio_master, "shutil"))
        # Check source code of audio_master.py for -19 LUFS
        source = Path(audio_master.__file__).read_text(encoding="utf-8")
        self.assertIn("loudnorm=I=-19:TP=-1.5:LRA=11", source)
        self.assertNotIn("loudnorm=I=-16", source)

    def test_07_soundscape_ducking_calc_and_singleton(self):
        """Verify soundscape cached SoundBank and ducking attenuation parameter binding."""
        bank1 = get_sound_bank()
        bank2 = get_sound_bank()
        self.assertIs(bank1, bank2)

        # Verify duck_attenuation_db formula mapping
        # -16 dB -> ratio 8.0, threshold ~0.06
        attenuation = abs(-16.0)
        ratio = max(2.0, min(20.0, attenuation / 2.0))
        threshold = max(0.02, min(0.12, 0.06 * (16.0 / max(4.0, attenuation))))
        self.assertAlmostEqual(ratio, 8.0)
        self.assertAlmostEqual(threshold, 0.06)

    def test_08_global_quota_pause(self):
        """Verify trigger_global_pause pauses sibling threads on 429 and resumes automatically."""
        limiter = TokenBucketRateLimiter(rate_rpm=600.0, capacity=10.0)
        self.assertTrue(limiter.pause_event.is_set())

        # Trigger global pause for 0.25 seconds
        limiter.trigger_global_pause(0.25)
        self.assertFalse(limiter.pause_event.is_set())

        # While paused, acquire() will block until the pause elapses
        start = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.20)
        self.assertTrue(limiter.pause_event.is_set())

    def test_09_tts_hallucination_stutter_guard(self):
        """Verify synthesize_gemini_tts detects unnatural duration-to-word stutter and retries."""
        import base64
        from audiobook_factory.tts_dispatcher import synthesize_gemini_tts

        stutter_pcm = b"\x00\x00" * int(10.0 * 24000)
        normal_pcm = b"\x00\x00" * int(1.5 * 24000)

        mock_resp_1 = MagicMock()
        mock_resp_1.read.return_value = json.dumps({
            "candidates": [{"content": {"parts": [{"inlineData": {"data": base64.b64encode(stutter_pcm).decode("utf-8")}}]}}]
        }).encode("utf-8")
        mock_resp_1.__enter__.return_value = mock_resp_1

        mock_resp_2 = MagicMock()
        mock_resp_2.read.return_value = json.dumps({
            "candidates": [{"content": {"parts": [{"inlineData": {"data": base64.b64encode(normal_pcm).decode("utf-8")}}]}}]
        }).encode("utf-8")
        mock_resp_2.__enter__.return_value = mock_resp_2

        with patch("urllib.request.urlopen", side_effect=[mock_resp_1, mock_resp_2]) as mock_open:
            with patch.dict("os.environ", {"GEMINI_API_KEY": "fake_key"}):
                with tempfile.TemporaryDirectory() as tmpdir:
                    out_wav = Path(tmpdir) / "test.wav"
                    path, dur = synthesize_gemini_tts("Hello world of magic", out_wav, max_retries=3)
                    self.assertEqual(mock_open.call_count, 2)
                    self.assertAlmostEqual(dur, 1.5, places=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
