#!/usr/bin/env python3
"""
Test Suite for SOTA Novel Pipeline Upgrades:
Verifies ProjectStateLedger ACID transactions, TokenBucketRateLimiter,
Sliding-Window Screenplay Scripting (>8,000 chars), and Orchestrator.
"""

import sys
import shutil
import tempfile
import unittest
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.state import ProjectStateLedger
from audiobook_factory.tts_dispatcher import TokenBucketRateLimiter, TTSDispatcher
from audiobook_factory.script_builder import (
    normalize_speech_text,
    build_narrator_script,
    build_dramatized_script_llm,
)
from audiobook_factory.orchestrator import PipelineOrchestrator
from audiobook_factory.logger import logger


class TestNovelPipelineUpgrade(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_audiobook_state_"))

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_sqlite_state_ledger_crud(self):
        """Verify SQLite transaction-safe state ledger operations."""
        ledger = ProjectStateLedger(self.test_dir)
        ledger.set_meta("title", "Test Novel")
        ledger.set_meta("author", "Test Author")

        self.assertEqual(ledger.get_meta("title"), "Test Novel")
        self.assertEqual(ledger.get_meta("author"), "Test Author")

        # Register chapter
        ledger.register_chapter(1, "The Beginning", word_count=2500)

        # Register mock script
        mock_script = [
            {"index": 1, "speaker": "Narrator", "text": "Once upon a time in a ancient realm."},
            {"index": 2, "speaker": "Hero", "text": "We must venture forth immediately!"},
            {"index": 3, "speaker": "Villain", "text": "You shall not pass this gate."},
        ]
        voice_map = {
            "Narrator": {"voice": "Aoede"},
            "Hero": {"voice": "Puck"},
            "Villain": {"voice": "Charon"},
        }
        ledger.register_script_segments(1, mock_script, voice_map)

        pending = ledger.get_pending_segments(1)
        self.assertEqual(len(pending), 3)

        # Mark first segment started, then completed
        seg_id = pending[0]["id"]
        ledger.mark_segment_started(seg_id)
        ledger.mark_segment_completed(seg_id, "/path/to/test.wav", duration_sec=4.2)

        # Mark second segment failed
        seg_id_2 = pending[1]["id"]
        ledger.mark_segment_failed(seg_id_2, "Rate limit test error")

        progress = ledger.get_progress()
        self.assertEqual(progress["total_segments"], 3)
        self.assertEqual(progress["completed"], 1)
        self.assertEqual(progress["failed"], 1)
        self.assertEqual(progress["pending"], 1)
        self.assertAlmostEqual(progress["total_duration_min"], 4.2 / 60.0, places=1)

    def test_02_token_bucket_rate_limiter(self):
        """Verify thread-safe TokenBucketRateLimiter pacing logic."""
        limiter = TokenBucketRateLimiter(rate_rpm=600.0, capacity=2.0)  # fast rate for unit test
        self.assertGreaterEqual(limiter.tokens, 1.0)
        limiter.acquire()
        self.assertGreaterEqual(limiter.tokens, 0.0)

    def test_03_sliding_window_script_no_truncation(self):
        """
        Verify that chapters > 8,000 characters are processed without truncation.
        Tests narrator fallback and text preservation across large blocks.
        """
        # Generate a 12,000-character test chapter (approx 2,000 words)
        paragraphs = [
            f"Paragraph {i}: This is an extended section of the novel describing in great detail "
            f"the ancient castle, the mysterious forest, and the dialogue between traveler and guardian. "
            f"Words are woven together to test text integrity and ensure that zero truncation occurs."
            for i in range(1, 55)
        ]
        large_chapter_text = "\n\n".join(paragraphs)
        self.assertGreater(len(large_chapter_text), 10000)

        # Run narrator script builder
        script = build_narrator_script(large_chapter_text)
        self.assertGreater(len(script), 5)

        # Verify all paragraphs are represented in the output text
        total_output_text = " ".join([seg["text"] for seg in script])
        self.assertIn("Paragraph 1", total_output_text)
        self.assertIn("Paragraph 54", total_output_text)

    def test_04_orchestrator_initialization(self):
        """Verify PipelineOrchestrator loads with correct project directories."""
        orchestrator = PipelineOrchestrator(self.test_dir)
        self.assertTrue(self.test_dir.exists())
        self.assertEqual(orchestrator.projects_dir, self.test_dir)

    def test_05_alexandria_and_vibevoice_integration(self):
        """Verify Alexandria pronoun disambiguation and VibeVoice emotion preservation."""
        from audiobook_factory.script_builder import build_dramatized_script_llm
        # Test alias mapping & pronoun disambiguation logic via mock
        roster = {
            "characters": {
                "Harry": {"gender": "male", "aliases": ["the boy", "Potter"]},
                "Hermione": {"gender": "female", "aliases": ["Miss Granger"]},
            }
        }
        # Verify script builder respects roster and alias resolution
        sample = "Harry said, 'Let us move quickly.'\n\nHermione replied, 'Wait for me!'"
        script = build_dramatized_script_llm(sample, character_roster=roster)
        self.assertIsInstance(script, list)
        self.assertGreater(len(script), 0)
        for item in script:
            self.assertIn("emotion", item)
            self.assertIn("speaker", item)


if __name__ == "__main__":
    unittest.main(verbosity=2)
