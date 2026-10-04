#!/usr/bin/env python3
"""
Test Suite: Room 3 - Screenplay Dramaturgy & Spatial Staging Agents.
Verifies the 4-agent collaborative screenplay architecture:
1. DialogueTurnIsolator: Dialogue isolation and speaker attribution.
2. StanislavskiSubtextDirector: Transitive actioning, subtext & intensity headroom.
3. PhysicalBlockingDirector: Actor physical posture, proximity & azimuth staging.
4. DramaturgyConsistencyJudge: Narrator centering, azimuth smoothing & intensity calibration.
5. ScreenplayDramaturgyRoom: Full pipeline coordination.
"""

import unittest
from unittest.mock import MagicMock, patch

from audiobook_factory.script.agents import (
    DialogueTurnIsolator,
    StanislavskiSubtextDirector,
    PhysicalBlockingDirector,
    DramaturgyConsistencyJudge,
    ScreenplayDramaturgyRoom,
    get_screenplay_room,
)
from audiobook_factory.contracts import SpatialCoordinates, ScreenplaySegment


class TestMultiAgentScreenplay(unittest.TestCase):

    def setUp(self):
        self.sample_turns = [
            {
                "index": 1,
                "type": "narration",
                "speaker": "Narrator",
                "text": "The tavern was thick with the scent of roasted meat and wet wool.",
                "emotion": "neutral",
            },
            {
                "index": 2,
                "type": "dialogue",
                "speaker": "Geralt",
                "text": "Sit down. We need to talk.",
                "emotion": "serious",
            },
            {
                "index": 3,
                "type": "dialogue",
                "speaker": "Dandelion",
                "text": "I would rather stand, my friend. My legs are cramped.",
                "emotion": "nervous",
            },
        ]

    def test_spatial_coordinates_contract_supports_physical_blocking(self):
        """Verifies SpatialCoordinates contract contains physical_blocking field."""
        sc = SpatialCoordinates(pan=-0.35, proximity="normal_room", physical_blocking="sitting")
        self.assertEqual(sc.pan, -0.35)
        self.assertEqual(sc.proximity, "normal_room")
        self.assertEqual(sc.physical_blocking, "sitting")

    def test_stanislavski_subtext_director(self):
        """Verifies StanislavskiSubtextDirector injects actioning, subtext, and delivery style."""
        director = StanislavskiSubtextDirector(model="mock-model")

        mock_enrichment = [
            {
                "index": 2,
                "actioning": "command",
                "subtext": "You are not safe until you hear what I have to say.",
                "underlying_emotion": "protective urgency",
                "intensity_level": "medium",
                "acting": {"delivery_style": "calm_authoritative", "pacing": 0.95},
            },
            {
                "index": 3,
                "actioning": "deflect",
                "subtext": "I know what you are going to say, and I am terrified.",
                "underlying_emotion": "concealed fear",
                "intensity_level": "medium",
                "acting": {"delivery_style": "breathless_exhaustion", "pacing": 1.1},
            },
        ]
        mock_llm = MagicMock(return_value=mock_enrichment)

        enriched = director.direct_subtext(
            segments=self.sample_turns,
            dramatic_context="A tense reunion in an inn.",
            call_llm_fn=mock_llm,
        )

        # Segment 2 should have actioning and subtext
        seg2 = next(s for s in enriched if s["index"] == 2)
        self.assertEqual(seg2.get("actioning"), "command")
        self.assertIn("protective urgency", seg2.get("underlying_emotion", ""))
        self.assertEqual(seg2.get("acting", {}).get("delivery_style"), "calm_authoritative")

    def test_physical_blocking_director(self):
        """Verifies PhysicalBlockingDirector sets posture, proximity, and stereo pan coordinates."""
        blocking_director = PhysicalBlockingDirector(model="mock-model")

        mock_staging = [
            {
                "index": 1,
                "physical_blocking": "standing",
                "spatial": {"proximity": "normal_room", "azimuth_pan": 0.0},
                "acoustic_env": "tavern_hearth",
            },
            {
                "index": 2,
                "physical_blocking": "sitting",
                "spatial": {"proximity": "normal_room", "azimuth_pan": -0.35},
                "acoustic_env": "tavern_hearth",
            },
            {
                "index": 3,
                "physical_blocking": "pacing",
                "spatial": {"proximity": "normal_room", "azimuth_pan": 0.35},
                "acoustic_env": "tavern_hearth",
            },
        ]
        mock_llm = MagicMock(return_value=mock_staging)

        staged = blocking_director.direct_blocking(
            segments=self.sample_turns,
            dramatic_context="Tavern corner.",
            call_llm_fn=mock_llm,
        )

        seg2 = next(s for s in staged if s["index"] == 2)
        self.assertEqual(seg2.get("physical_blocking"), "sitting")
        self.assertEqual(seg2.get("spatial", {}).get("pan"), -0.35)

        seg3 = next(s for s in staged if s["index"] == 3)
        self.assertEqual(seg3.get("physical_blocking"), "pacing")
        self.assertEqual(seg3.get("spatial", {}).get("pan"), 0.35)

    def test_dramaturgy_consistency_judge_narrator_and_whisper_rules(self):
        """Verifies DramaturgyConsistencyJudge clamps narrator to center and calibrates whisper intensity."""
        judge = DramaturgyConsistencyJudge()

        raw_segments = [
            # Flawed narrator with off-center pan
            {
                "index": 1,
                "type": "narration",
                "speaker": "Narrator",
                "text": "The wind howled.",
                "spatial": {"pan": -0.7, "proximity": "distant"},
            },
            # Whispered dialogue with incorrect high intensity
            {
                "index": 2,
                "type": "dialogue",
                "speaker": "Yennefer",
                "text": "Listen closely...",
                "intensity_level": "high",
                "acting": {"delivery_style": "whispering_fear"},
                "spatial": {"pan": 0.3, "proximity": "normal_room"},
            },
            # Clamping test: extreme pan > 0.8
            {
                "index": 3,
                "type": "dialogue",
                "speaker": "Geralt",
                "text": "I hear it.",
                "spatial": {"pan": 0.95, "proximity": "normal_room"},
            },
        ]

        certified, report = judge.audit_and_certify(raw_segments, chunk_title="Test Chunk")

        # 1. Narrator must be clamped to 0.0 and normal_room
        seg1 = certified[0]
        self.assertEqual(seg1["spatial"]["pan"], 0.0)
        self.assertEqual(seg1["spatial"]["proximity"], "normal_room")

        # 2. Whisper must be low intensity and intimate_close proximity
        seg2 = certified[1]
        self.assertEqual(seg2["intensity_level"], "low")
        self.assertEqual(seg2["spatial"]["proximity"], "intimate_close")

        # 3. Pan 0.95 must be clamped to 0.8
        seg3 = certified[2]
        self.assertLessEqual(seg3["spatial"]["pan"], 0.8)
        self.assertEqual(report["status"], "CERTIFIED")

    def test_screenplay_dramaturgy_room_end_to_end(self):
        """Verifies ScreenplayDramaturgyRoom coordinates all 4 passes end-to-end."""
        room = ScreenplayDramaturgyRoom(model="mock-model")

        mock_turns = [
            {"index": 1, "type": "narration", "speaker": "Narrator", "text": "He spoke."},
            {"index": 2, "type": "dialogue", "speaker": "Geralt", "text": "Stay back."},
        ]

        with patch.object(room.isolator, "isolate_turns", return_value=mock_turns), \
             patch.object(room.stanislavski, "direct_subtext", side_effect=lambda segments, **kw: segments), \
             patch.object(room.blocking_director, "direct_blocking", side_effect=lambda segments, **kw: segments):

            result = room.process_chunk(
                chunk_text="He spoke. 'Stay back.'",
                dramatic_context="A confrontational moment.",
            )

            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["speaker"], "Narrator")
            self.assertEqual(result[0]["spatial"]["pan"], 0.0)


if __name__ == "__main__":
    unittest.main()
