"""
Tests for Cinematic Audio Drama Upgrade:
- SFX Action-Beat Precision (ScreenplaySegment type='action', silent 48kHz WAV canvas, 50ms transient anchoring)
- BGM 2-Tier Immersion (Musical ducking envelope: 120ms attack, 750ms release, -7.5dB gain; 40% music budget / 60% silence)
"""

import math
import tempfile
import unittest
import wave
from pathlib import Path
from typing import Dict, Any

from audiobook_factory.contracts import (
    ScreenplaySegment,
    MasteringConfig,
    CreativeManifest,
    MusicCue,
    FoleyCue,
    ManifestValidationError,
)
from audiobook_factory.tts_dispatcher import (
    TTSDispatcher,
    synthesize_segment_audio,
)
from audiobook_factory.manifest_renderer import assemble_master_filter_graph
from audiobook_factory.script_builder import clean_screenplay_pass2
from audiobook_factory.sanitizer import sanitize_screenplay_segment
from audiobook_factory.agent_director import AgentDirector
from audiobook_factory.sound_bank import SoundBank


def _create_synthetic_wav(path: Path, duration_sec: float = 1.0, freq: float = 440.0, rate: int = 48000) -> Path:
    """Create a synthetic 16-bit stereo PCM WAV file for acoustic testing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    num_frames = int(round(rate * duration_sec))
    frames = bytearray()
    for i in range(num_frames):
        sample = int(10000 * math.sin(2 * math.pi * freq * (i / rate)))
        sample_bytes = sample.to_bytes(2, byteorder="little", signed=True)
        frames.extend(sample_bytes)  # L
        frames.extend(sample_bytes)  # R
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(bytes(frames))
    return path


class TestActionBeatsAndMusicalDucking(unittest.TestCase):
    """Rigorous test suite for Action Beat Precision and Musical Ducking."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    # =========================================================================
    # CONTRACT TESTS: ScreenplaySegment and MasteringConfig
    # =========================================================================
    def test_screenplay_segment_action_beat_schema(self):
        """Verify ScreenplaySegment accepts type='action' with automatic Foley defaults."""
        # 1. Minimal instantiation: defaults speaker='Foley', text='[ACTION]'
        seg_min = ScreenplaySegment(index=1, type="action")
        self.assertEqual(seg_min.type, "action")
        self.assertEqual(seg_min.speaker, "Foley")
        self.assertEqual(seg_min.text, "[ACTION]")
        self.assertEqual(seg_min.pause_after_ms, 400)

        # 2. Rich instantiation: dedicated combat action beat
        seg_rich = ScreenplaySegment(
            index=2,
            type="action",
            speaker="Foley",
            text="[ACTION]",
            emotion="impact_strike",
            pause_after_ms=600,
            sfx_cues=["sword_draw_steel"],
            acoustic_env="stone_crypt",
        )
        self.assertEqual(seg_rich.type, "action")
        self.assertEqual(seg_rich.emotion, "impact_strike")
        self.assertEqual(seg_rich.pause_after_ms, 600)
        self.assertEqual(seg_rich.sfx_cues, ["sword_draw_steel"])

        # 3. Model validation from dictionary
        data = {
            "index": 3,
            "type": "action",
            "pause_after_ms": 750,
            "sfx_cues": [{"tag": "door_kick_heavy"}],
        }
        seg_dict = ScreenplaySegment.model_validate(data)
        self.assertEqual(seg_dict.speaker, "Foley")
        self.assertEqual(seg_dict.text, "[ACTION]")
        self.assertEqual(seg_dict.pause_after_ms, 750)
        self.assertEqual(seg_dict.sfx_cues, ["door_kick_heavy"])

    def test_screenplay_segment_backward_compatibility(self):
        """Verify standard dialogue, narration, and chapter_header remain strictly valid."""
        seg_diag = ScreenplaySegment(
            index=1,
            type="dialogue",
            speaker="Geralt",
            text="Wind's howling.",
        )
        self.assertEqual(seg_diag.type, "dialogue")
        self.assertEqual(seg_diag.speaker, "Geralt")
        self.assertEqual(seg_diag.text, "Wind's howling.")

        seg_narr = ScreenplaySegment(
            index=2,
            type="narration",
            speaker="Narrator",
            text="The silver blade caught the moonlight.",
        )
        self.assertEqual(seg_narr.type, "narration")

    def test_mastering_config_musical_ducking_calibration(self):
        """Verify calibrated broadcast ducking defaults for smooth musical breathing."""
        m_cfg = MasteringConfig()
        # Calibrated musical ducking envelope
        self.assertEqual(m_cfg.ducking_attenuation_db, -7.5)
        self.assertEqual(m_cfg.ducking_attack_ms, 120)
        self.assertEqual(m_cfg.ducking_release_ms, 750)
        # Standard loudness targets
        self.assertEqual(m_cfg.target_lufs, -19.0)
        self.assertEqual(m_cfg.true_peak_dbtp, -1.5)

        # Custom override maintains full non-destructive flexibility
        m_custom = MasteringConfig(
            ducking_attenuation_db=-10.0,
            ducking_attack_ms=80,
            ducking_release_ms=600,
        )
        self.assertEqual(m_custom.ducking_attenuation_db, -10.0)
        self.assertEqual(m_custom.ducking_attack_ms, 80)
        self.assertEqual(m_custom.ducking_release_ms, 600)

    # =========================================================================
    # TTS DISPATCHER TESTS: Deterministic Silent Canvas Generation
    # =========================================================================
    def test_tts_dispatcher_action_beat_silent_canvas_generation(self):
        """Verify TTSDispatcher generates an exact 48kHz stereo 16-bit silent WAV for action beats."""
        dispatcher = TTSDispatcher(project_dir=self.tmp_path)
        action_seg = {
            "index": 1,
            "type": "action",
            "speaker": "Foley",
            "text": "[ACTION]",
            "pause_after_ms": 500,
        }

        out_file, dur = dispatcher.synthesize_segment(action_seg, chapter_num=1, seg_num=1)
        self.assertTrue(out_file.exists())
        self.assertAlmostEqual(dur, 0.5, places=2)
        self.assertGreater(out_file.stat().st_size, 1000)

        # Verify WAV audio properties: 48kHz, 2 channels (stereo), 16-bit PCM
        with wave.open(str(out_file), "rb") as wf:
            self.assertEqual(wf.getnchannels(), 2)
            self.assertEqual(wf.getsampwidth(), 2)
            self.assertEqual(wf.getframerate(), 48000)
            frames = wf.readframes(wf.getnframes())
            # Must be 100% pure acoustic silence (all zero bytes)
            self.assertEqual(frames, b"\x00" * len(frames))

    def test_synthesize_segment_audio_helper(self):
        """Verify synthesize_segment_audio module-level helper generates silent WAV correctly."""
        action_seg = ScreenplaySegment(
            index=2,
            type="action",
            speaker="Foley",
            text="[ACTION]",
            pause_after_ms=450,
        )
        out_file, dur = synthesize_segment_audio(
            segment=action_seg,
            chapter_num=1,
            seg_num=2,
            audio_dir=self.tmp_path / "audio_chunks",
        )
        self.assertTrue(out_file.exists())
        self.assertAlmostEqual(dur, 0.45, places=2)

        with wave.open(str(out_file), "rb") as wf:
            self.assertEqual(wf.getframerate(), 48000)
            self.assertEqual(wf.getnchannels(), 2)
            frames = wf.readframes(wf.getnframes())
            self.assertEqual(frames, b"\x00" * len(frames))

    # =========================================================================
    # SCRIPT BUILDER & SANITIZER TESTS: Preservation of Action Beats
    # =========================================================================
    def test_sanitizer_preserves_action_segments(self):
        """Verify sanitize_screenplay_segment does not reject or strip action segments."""
        raw_seg = {
            "type": "action",
            "speaker": "Foley",
            "text": "[ACTION]",
            "sfx_cues": ["sword_draw_steel"],
            "pause_after_ms": 600,
        }
        cleaned = sanitize_screenplay_segment(raw_seg, is_hindi=True)
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned["type"], "action")
        self.assertEqual(cleaned["speaker"], "Foley")
        self.assertEqual(cleaned["text"], "[ACTION]")

    def test_clean_screenplay_pass2_preserves_action_beats(self):
        """Verify clean_screenplay_pass2 preserves action beats and Foley speaker."""
        raw_items = [
            {"type": "dialogue", "speaker": "Geralt", "text": "पीछे हटो!"},
            {"type": "action", "speaker": "Foley", "text": "[ACTION]", "sfx_cues": ["sword_draw_steel"], "pause_after_ms": 600},
            {"type": "narration", "speaker": "Narrator", "text": "चांदी की चमक रात में बिखरी।"},
        ]
        roster = {"characters": {"Geralt": {"aliases": ["गेराल्ट"]}}}
        final_script = clean_screenplay_pass2(raw_items, is_hindi=True, character_roster=roster)

        self.assertEqual(len(final_script), 3)
        # Segment 1: Dialogue
        self.assertEqual(final_script[0]["type"], "dialogue")
        self.assertEqual(final_script[0]["speaker"], "Geralt")
        # Segment 2: Action Beat
        self.assertEqual(final_script[1]["type"], "action")
        self.assertEqual(final_script[1]["speaker"], "Foley")
        self.assertEqual(final_script[1]["text"], "[ACTION]")
        self.assertEqual(final_script[1]["pause_after_ms"], 600)
        # Segment 3: Narration
        self.assertEqual(final_script[2]["type"], "narration")
        self.assertEqual(final_script[2]["speaker"], "Narrator")

    # =========================================================================
    # AGENT DIRECTOR TESTS: SFX Action-Beat Anchoring & 2-Tier Score Silence
    # =========================================================================
    def test_pass3_acoustic_foley_anchors_action_beat_directly(self):
        """Verify action beat Foley cues are anchored to seg_start_ms + 50ms without word-ratio offset."""
        from audiobook_factory.sound_bank import get_sound_bank
        sound_bank = get_sound_bank()
        director = AgentDirector(sound_bank=sound_bank)

        # Script with an Action Beat at segment 2
        script_segments = [
            {
                "index": 1,
                "type": "dialogue",
                "speaker": "Geralt",
                "text": "Get ready.",
            },
            {
                "index": 2,
                "type": "action",
                "speaker": "Foley",
                "text": "[ACTION]",
                "sfx_cues": ["sword_draw"],
                "pause_after_ms": 600,
            },
        ]

        # Dialogue ends at 2000ms, pause 400ms -> Action beat starts at 2400ms
        seg_starts_ms = {1: 0, 2: 2400}
        segment_durations_sec = {1: 2.0, 2: 0.6}

        foley_cues = director._pass3_acoustic_foley(
            script_segments=script_segments,
            foley_events_plan=[],  # Empty plan triggers automatic dependency extraction
            seg_starts_ms=seg_starts_ms,
            segment_durations_sec=segment_durations_sec,
        )

        self.assertGreaterEqual(len(foley_cues), 1)
        action_cues = [c for c in foley_cues if c.segment_index == 2]
        self.assertTrue(len(action_cues) >= 1)
        action_cue = action_cues[0]

        # Frame-accurate landing: cue_start_ms MUST be seg_start_ms + 50ms = 2450ms
        self.assertEqual(action_cue.start_ms, 2450)
        self.assertEqual(action_cue.pre_roll_ms, 50)
        self.assertEqual(action_cue.segment_index, 2)

    def test_2_tier_score_architecture_and_silence_budget(self):
        """Verify _enforce_silence_carving enforces up to 40% music budget (>= 60% silence)."""
        from audiobook_factory.sound_bank import get_sound_bank
        director = AgentDirector(sound_bank=get_sound_bank())
        total_duration = 100.0  # 100 seconds

        # Plan with 35 seconds of music (35% music, 65% silence) -> Should NOT be pruned
        plan_35 = {
            "music_cues": [
                {"cue_id": "c1", "duration_sec": 20.0},
                {"cue_id": "c2", "duration_sec": 15.0},
            ]
        }
        res_35 = director._enforce_silence_carving(plan_35, total_duration)
        total_35 = sum(c["duration_sec"] for c in res_35["music_cues"])
        self.assertAlmostEqual(total_35, 35.0, places=1)

        # Plan with 50 seconds of music (exceeds 40% threshold) -> Pruned down to 40 seconds (60% silence)
        plan_50 = {
            "music_cues": [
                {"cue_id": "c1", "duration_sec": 30.0},
                {"cue_id": "c2", "duration_sec": 20.0},
            ]
        }
        res_50 = director._enforce_silence_carving(plan_50, total_duration)
        total_50 = sum(c["duration_sec"] for c in res_50["music_cues"])
        self.assertAlmostEqual(total_50, 40.0, places=1)

        # Validate that CreativeManifest accepts 40% music / 60% silence
        manifest = CreativeManifest(
            chapter_id="chap_2tier",
            total_duration_ms=100000,
            silence_percentage=60.0,
            music_cues=[
                MusicCue(
                    cue_id="mc_bed",
                    cue_type="EMOTIONAL_UNDERSCORE",
                    track_name="low_bed.mp3",
                    section_name="INTRO_BED",
                    start_ms=0,
                    duration_ms=25000,
                    volume_db=-24.0,
                    dramatic_justification="Atmospheric low tension bed",
                ),
                MusicCue(
                    cue_id="mc_peak",
                    cue_type="CLIMACTIC_ACTION_CUE",
                    track_name="peak_drop.mp3",
                    section_name="CLIMAX_DROP",
                    start_ms=30000,
                    duration_ms=15000,
                    volume_db=-18.0,
                    dramatic_justification="Surgical combat drop",
                ),
            ],
        )
        # Must validate without raising ManifestValidationError
        manifest.validate()
        self.assertEqual(manifest.silence_percentage, 60.0)

    # =========================================================================
    # MANIFEST RENDERER & FILTER GRAPH TESTS: 120ms/750ms Musical Ducking
    # =========================================================================
    def test_assemble_master_filter_graph_musical_ducking(self):
        """Verify assemble_master_filter_graph uses 120ms attack, 750ms release, and -7.5dB ratio."""
        # 1. Default graph with Foley
        graph = assemble_master_filter_graph(has_foley=True)
        self.assertIn("attack=120:release=750", graph)
        self.assertIn("sidechaincompress=threshold=0.03:ratio=4.0:attack=120:release=750:knee=2.0", graph)
        self.assertIn("[voc_dry][bgm_ducked][amb_bed][fol_bus][reverb_wet]amix=inputs=5:duration=first:normalize=0", graph)
        self.assertIn("loudnorm=I=-19.0:TP=-1.5:LRA=7.0", graph)

        # 2. Graph without Foley
        graph_no_fol = assemble_master_filter_graph(has_foley=False)
        self.assertIn("attack=120:release=750", graph_no_fol)
        self.assertIn("ratio=4.0", graph_no_fol)
        self.assertIn("[voc_dry][bgm_ducked][amb_bed][reverb_wet]amix=inputs=4:duration=first:normalize=0", graph_no_fol)


if __name__ == "__main__":
    unittest.main()
