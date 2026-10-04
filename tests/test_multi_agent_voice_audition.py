#!/usr/bin/env python3
"""
Test Suite: Room 4 - Voice Performance & Multi-Take Audition.
Verifies the TakeAuditionCritic for comparative take selection on high-stakes climaxes.
"""

import unittest
from unittest.mock import MagicMock

from audiobook_factory.performance.take_critic import TakeAuditionCritic


class TestMultiAgentVoiceAudition(unittest.TestCase):

    def test_single_candidate_default(self):
        """Verifies TakeAuditionCritic returns 0 without calling LLM when only 1 candidate exists."""
        critic = TakeAuditionCritic(model="mock-model")
        idx, reason = critic.select_best_take_audition(
            text="I will not let you die.",
            speaker="Geralt",
            subtext="Desperate protective vow",
            emotion="urgency",
            intensity="high",
            candidates=[{"variant": "standard", "duration_sec": 2.1}],
        )
        self.assertEqual(idx, 0)
        self.assertIn("Single candidate", reason)

    def test_multi_take_audition_selection(self):
        """Verifies TakeAuditionCritic compares candidate takes and selects superior take."""
        critic = TakeAuditionCritic(model="mock-model")

        mock_critic_response = {
            "winner_index": 1,
            "justification": "Take 1 has authentic vocal strain and breath tremor matching the desperate subtext.",
        }
        mock_llm = MagicMock(return_value=mock_critic_response)

        candidates = [
            {"variant": "standard", "duration_sec": 2.2, "pitch_variance": 0.12},
            {"variant": "more_vulnerable", "duration_sec": 2.5, "pitch_variance": 0.28},
        ]

        idx, reason = critic.select_best_take_audition(
            text="I will not let you die.",
            speaker="Geralt",
            subtext="Desperate protective vow",
            emotion="urgency",
            intensity="high",
            candidates=candidates,
            call_llm_fn=mock_llm,
        )

        self.assertEqual(idx, 1)
        self.assertIn("vocal strain", reason)
        mock_llm.assert_called_once()

    def test_audition_fallback_on_error(self):
        """Verifies TakeAuditionCritic safely falls back to candidate 0 if LLM fails."""
        critic = TakeAuditionCritic(model="mock-model")
        mock_llm = MagicMock(side_effect=RuntimeError("API error"))

        candidates = [
            {"variant": "standard", "duration_sec": 2.2},
            {"variant": "more_urgent", "duration_sec": 2.0},
        ]

        idx, reason = critic.select_best_take_audition(
            text="Run!",
            speaker="Yennefer",
            subtext="Absolute terror",
            emotion="panic",
            intensity="explosive",
            candidates=candidates,
            call_llm_fn=mock_llm,
        )

        self.assertEqual(idx, 0)
        self.assertIn("fallback", reason.lower())


if __name__ == "__main__":
    unittest.main()
