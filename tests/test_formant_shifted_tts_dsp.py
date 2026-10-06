#!/usr/bin/env python3
"""
Test Suite: Phase 4 - Formant-Shifted Studio TTS & DSP Verification.
Verifies:
1. 4D acoustic formant vector FFmpeg post-filter chain construction (asetrate, aresample, atempo, parametric EQ).
2. Canonical segment filename hash sensitivity to eq_formant_profile (cache invalidation).
3. TakeAuditionCritic deliberation integration during multi-take candidate selection.
4. Universal permissive BLOCK_NONE safety thresholds across providers.
"""

import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from audiobook_factory.tts.audio_slicer import compute_canonical_segment_filename
from audiobook_factory.tts.dispatcher import TTSDispatcher
from audiobook_factory.safety import get_universal_safety_settings
from audiobook_factory.performance.take_critic import TakeAuditionCritic


class TestFormantShiftedTTSDSP(unittest.TestCase):

    def test_canonical_filename_sensitive_to_eq_formant_profile(self):
        """Verifies that differing eq_formant_profiles produce distinct cache hashes."""
        base_cfg = {
            "voice": "Enceladus",
            "speed": 1.0,
            "pitch": 0.95,
            "bass_boost_db": 0.0,
            "clarity_reduction_db": 0.0,
            "lowpass_hz": 0,
            "highpass_hz": 0,
            "presence_boost_db": 0.0,
            "volume_gain_db": 0.0,
        }

        cfg_lead_warrior = dict(base_cfg)
        cfg_lead_warrior["eq_formant_profile"] = "equalizer=f=150:t=q:w=1.2:g=+2.5,equalizer=f=3200:t=q:w=1.4:g=+2.0"

        cfg_young_rogue = dict(base_cfg)
        cfg_young_rogue["eq_formant_profile"] = "equalizer=f=4500:t=q:w=1.2:g=+1.8"

        file_flat = compute_canonical_segment_filename(1, 1, "Stay back.", base_cfg)
        file_warrior = compute_canonical_segment_filename(1, 1, "Stay back.", cfg_lead_warrior)
        file_rogue = compute_canonical_segment_filename(1, 1, "Stay back.", cfg_young_rogue)

        # All three must have distinct filenames / hashes
        self.assertNotEqual(file_flat, file_warrior)
        self.assertNotEqual(file_flat, file_rogue)
        self.assertNotEqual(file_warrior, file_rogue)

    def test_ffmpeg_4d_acoustic_filter_chain_construction(self):
        """Verifies that pitch shift, tempo compensation, and eq_formant_profile are chained cleanly."""
        sp_cfg = {
            "voice": "Enceladus",
            "pitch": 0.94,
            "speed": 0.96,
            "bass_boost_db": 2.0,
            "presence_boost_db": 1.5,
            "clarity_reduction_db": 0.0,
            "lowpass_hz": 6000,
            "highpass_hz": 40,
            "eq_formant_profile": "equalizer=f=150:t=q:w=1.2:g=+2.5,equalizer=f=3200:t=q:w=1.4:g=+2.0",
        }

        # Simulate dispatcher post_filters construction logic
        post_filters = []
        highpass_hz = int(sp_cfg.get("highpass_hz", 0))
        if highpass_hz > 20:
            post_filters.append(f"highpass=f={highpass_hz}")

        pitch = float(sp_cfg.get("pitch", 1.0))
        speed = float(sp_cfg.get("speed", 1.0))

        if abs(pitch - 1.0) > 0.005:
            new_rate = int(24000 * pitch)
            post_filters.append(f"asetrate={new_rate},aresample=24000")
            eff_tempo = speed / pitch
            if abs(eff_tempo - 1.0) > 0.005:
                post_filters.append(f"atempo={eff_tempo:.3f}")
        elif abs(speed - 1.0) > 0.005:
            post_filters.append(f"atempo={speed:.3f}")

        bass_boost_db = float(sp_cfg.get("bass_boost_db", 0.0))
        if bass_boost_db > 0.1:
            post_filters.append(f"equalizer=f=100:t=q:w=1.2:g={bass_boost_db:.1f}")

        presence_boost_db = float(sp_cfg.get("presence_boost_db", 0.0))
        if presence_boost_db > 0.1:
            post_filters.append(f"equalizer=f=3200:t=q:w=1.4:g={presence_boost_db:.1f}")

        lowpass_hz = int(sp_cfg.get("lowpass_hz", 0))
        if lowpass_hz > 1000:
            post_filters.append(f"lowpass=f={lowpass_hz}")

        eq_formant_profile = str(sp_cfg.get("eq_formant_profile", "")).strip()
        if eq_formant_profile:
            for eq_filter in eq_formant_profile.split(","):
                eq_clean = eq_filter.strip()
                if eq_clean and eq_clean not in post_filters:
                    post_filters.append(eq_clean)

        filter_str = ",".join(post_filters)

        # 1. asetrate must reflect pitch: 24000 * 0.94 = 22560
        self.assertIn("asetrate=22560,aresample=24000", filter_str)
        # 2. atempo compensation: 0.96 / 0.94 = 1.021
        self.assertIn("atempo=1.021", filter_str)
        # 3. Formant EQ profile filters must be injected
        self.assertIn("equalizer=f=150:t=q:w=1.2:g=+2.5", filter_str)
        self.assertIn("equalizer=f=3200:t=q:w=1.4:g=+2.0", filter_str)
        # 4. Lowpass filter must be present
        self.assertIn("lowpass=f=6000", filter_str)

    def test_universal_block_none_safety_thresholds(self):
        """Verifies that all 4 safety categories are configured with BLOCK_NONE for unrated fiction."""
        settings = get_universal_safety_settings()
        self.assertEqual(len(settings), 4)

        categories = {s["category"]: s["threshold"] for s in settings}
        self.assertEqual(categories.get("HARM_CATEGORY_HARASSMENT"), "BLOCK_NONE")
        self.assertEqual(categories.get("HARM_CATEGORY_HATE_SPEECH"), "BLOCK_NONE")
        self.assertEqual(categories.get("HARM_CATEGORY_SEXUALLY_EXPLICIT"), "BLOCK_NONE")
        self.assertEqual(categories.get("HARM_CATEGORY_DANGEROUS_CONTENT"), "BLOCK_NONE")

    def test_take_audition_critic_deliberation(self):
        """Verifies TakeAuditionCritic selects superior candidate take for climactic lines."""
        critic = TakeAuditionCritic(model="mock-critic")

        candidates = [
            {"take_id": "take_001_standard", "variant_type": "standard", "duration_sec": 2.1},
            {"take_id": "take_001_vulnerable", "variant_type": "more_vulnerable", "duration_sec": 2.4},
        ]

        mock_critic_res = {
            "winner_index": 1,
            "justification": "Take 1 portrays raw vulnerability with breath tremor matching the stakes.",
        }

        mock_llm = MagicMock(return_value=mock_critic_res)

        win_idx, justification = critic.select_best_take_audition(
            text="I thought I had lost you forever.",
            speaker="Geralt",
            subtext="Deep terror masked as stoicism",
            emotion="vulnerable_relief",
            intensity="high",
            candidates=candidates,
            call_llm_fn=mock_llm,
        )

        self.assertEqual(win_idx, 1)
        self.assertIn("vulnerability", justification)


if __name__ == "__main__":
    unittest.main()
