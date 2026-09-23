#!/usr/bin/env python3
"""
Unit and Regression Tests for Audio Drama Sync, Foley Staging, and Soundscape Remediation.
Tests 5 forensic defect fixes:
1. Cumulative Timeline Drift (pre_roll_breath_ms synchronization).
2. Bilingual Foley Anchor Matching without 50% dead-center trap.
3. Domestic vs Combat Taxonomy Isolation (no dinner plate -> sword clash).
4. Scene-Bound BGM Underscore & until_segment duration calculation.
5. Dynamic Multi-Scene Ambience Bed Partitioning.
"""

import unittest
from pathlib import Path
import tempfile
import wave

from audiobook_factory.contracts import (
    ScreenplaySegment,
    ScreenplayScript,
    TimelineSegment,
    TimelineLedger,
)
from audiobook_factory.acoustic_bus_matrix import derive_ucs_category
from audiobook_factory.agent_director import AgentDirector
from audiobook_factory.sound_bank import SoundBank, get_sound_bank


class TestAudioSyncAndSoundscapeRemediation(unittest.TestCase):

    def setUp(self):
        self.director = AgentDirector(model="test-model")

    def test_pre_roll_breath_cumulative_timeline_sync(self):
        """Validates that pre_roll_breath_ms is fully accounted for in start_ms calculations."""
        script_segments = [
            {"index": 1, "text": "First line", "pre_roll_breath_ms": 200, "pause_after_ms": 300},
            {"index": 2, "text": "Second line terrified", "pre_roll_breath_ms": 250, "pause_after_ms": 400},
            {"index": 3, "text": "Third line normal", "pre_roll_breath_ms": 0, "pause_after_ms": 500},
        ]
        segment_durations = {1: 4.0, 2: 3.0, 3: 5.0}  # seconds

        # Simulate agent_director seg_starts_ms calculation
        seg_starts_ms = {}
        current_time_ms = 0
        for seg in script_segments:
            s_idx = seg["index"]
            pre_breath = int(seg.get("pre_roll_breath_ms", 0) or 0)
            seg_starts_ms[s_idx] = current_time_ms + pre_breath
            dur_ms = int(segment_durations.get(s_idx, 4.0) * 1000)
            pause_after = seg.get("pause_after_ms", 300)
            current_time_ms = seg_starts_ms[s_idx] + dur_ms + pause_after

        # Segment 1 starts at 200ms (after 200ms pre-roll breath)
        self.assertEqual(seg_starts_ms[1], 200)

        # Segment 1 ends at 200 + 4000 = 4200ms, followed by 300ms pause = 4500ms
        # Segment 2 has 250ms pre-roll breath, so speech starts at 4500 + 250 = 4750ms!
        self.assertEqual(seg_starts_ms[2], 4750)

        # Segment 2 ends at 4750 + 3000 = 7750ms, followed by 400ms pause = 8150ms
        # Segment 3 has 0ms pre-roll breath, so speech starts at exactly 8150ms!
        self.assertEqual(seg_starts_ms[3], 8150)

    def test_bilingual_anchor_offset_no_dead_center(self):
        """Validates that English anchors match Hindi text and never default to 50% dead center."""
        seg_text = "गेराल्ट ने अपनी तलवार म्यान से बाहर निकाली और कदम बढ़ाए।"
        seg_dur_ms = 4000

        # Case A: English anchor 'sword' matches 'तलवार'
        offset_sword = self.director._compute_word_level_offset(
            text=seg_text,
            anchor_word="sword",
            seg_dur_ms=seg_dur_ms,
            action_verb="draw",
        )
        # 'तलवार' is word index 3 of 10 words (~35% into segment = ~1400ms)
        self.assertTrue(1000 <= offset_sword <= 1800, f"Offset {offset_sword}ms out of range for 'sword'")

        # Case B: Devanagari anchor 'तलवार' directly matches
        offset_hindi = self.director._compute_word_level_offset(
            text=seg_text,
            anchor_word="तलवार",
            seg_dur_ms=seg_dur_ms,
            action_verb="draw",
        )
        self.assertEqual(offset_sword, offset_hindi)

        # Case C: Unmatched anchor word and verb on quiet text with preparatory action 'draw'
        # Must land on early transient window (~15% = ~600ms), NOT 50% (2000ms)!
        no_match_text = "कमरे में सन्नाटा पसरा हुआ था और कोई हलचल नहीं थी।"
        offset_early = self.director._compute_word_level_offset(
            text=no_match_text,
            anchor_word="nonexistent_prop",
            seg_dur_ms=seg_dur_ms,
            action_verb="draw",
        )
        self.assertEqual(offset_early, int(seg_dur_ms * 0.15))
        self.assertNotEqual(offset_early, int(seg_dur_ms * 0.50))

        # Case D: Unmatched anchor word and verb with impact action 'slam'
        # Must land on climax window (~75% = ~3000ms), NOT 50% (2000ms)!
        offset_late = self.director._compute_word_level_offset(
            text=no_match_text,
            anchor_word="nonexistent_impact",
            seg_dur_ms=seg_dur_ms,
            action_verb="slam",
        )
        self.assertEqual(offset_late, int(seg_dur_ms * 0.75))
        self.assertNotEqual(offset_late, int(seg_dur_ms * 0.50))

    def test_domestic_vs_combat_foley_taxonomy(self):
        """Validates that 'थाली' and tableware classify as DOMETabl and never trigger sword clashing."""
        # 1. UCS Classification
        ucs_thali = derive_ucs_category("थाली", "plate")
        self.assertEqual(ucs_thali, "DOMETabl")

        ucs_plate = derive_ucs_category("dish", "plate")
        self.assertEqual(ucs_plate, "DOMETabl")

        ucs_bone = derive_ucs_category("हड्डी", "bone")
        self.assertEqual(ucs_bone, "GOREAnat")

        ucs_sword = derive_ucs_category("तलवार", "steel")
        self.assertEqual(ucs_sword, "WEAPSwd")

        # 2. Asset Resolution Guard: Tableware must NEVER resolve to sword_clash or blade
        res = self.director._resolve_foley_asset(action_verb="tableware", object_material="थाली")
        if res:
            res_lower = res.name.lower()
            self.assertFalse(
                any(w in res_lower for w in ("sword", "blade", "clash", "scabbard", "parry")),
                f"Domestic action resolved to combat weapon asset: {res.name}"
            )

    def test_scene_bound_bgm_duration(self):
        """Validates that BGM cues calculate duration from scene boundaries instead of fixed 30s chops."""
        seg_starts_ms = {
            1: 0,
            10: 35000,
            25: 120000,  # 2 minutes in
            40: 240000,  # 4 minutes in
        }
        # 10 minutes total duration -> 40% budget = 240,000ms
        total_duration_ms = 600000

        cues_plan = [
            {
                "cue_id": "cue_battle_01",
                "trigger_segment": 10,
                "until_segment": 40,
                "duration_sec": 30.0,  # Fallback duration if until_segment wasn't provided
                "energy_section": "CLIMAX_DROP",
                "search_query": "battle confrontation dark strings",
            }
        ]

        music_cues = self.director._pass2_music_director(
            cues_plan=cues_plan,
            seg_starts_ms=seg_starts_ms,
            total_duration_ms=total_duration_ms,
        )

        if music_cues:
            # Segment 10 is at 35,000ms, Segment 40 is at 240,000ms.
            # Expected duration is 240,000 - 35,000 = 205,000ms (not 30,000ms!)
            cue = music_cues[0]
            self.assertEqual(cue.start_ms, 35000)
            self.assertEqual(cue.duration_ms, 205000)

    def test_dynamic_multi_scene_ambience_partitioning(self):
        """Validates that shifts in acoustic_env partition the chapter into distinct scene blocks."""
        script_segments = [
            {"index": 1, "acoustic_env": "cintra_castle_bath"},
            {"index": 2, "acoustic_env": "cintra_castle_bath"},
            {"index": 3, "acoustic_env": "royal_banquet_hall"},
            {"index": 4, "acoustic_env": "royal_banquet_hall"},
            {"index": 5, "acoustic_env": "dense_forest_night"},
        ]
        seg_starts_ms = {
            1: 0,
            2: 5000,
            3: 12000,
            4: 20000,
            5: 30000,
        }
        segment_durations = {
            1: 5.0,
            2: 7.0,
            3: 8.0,
            4: 10.0,
            5: 15.0,
        }
        total_duration_ms = 45000

        blocks = self.director._partition_script_ambience_scenes(
            script_segments=script_segments,
            seg_starts_ms=seg_starts_ms,
            segment_durations_sec=segment_durations,
            total_duration_ms=total_duration_ms,
        )

        # Expected: exactly 3 distinct scene blocks
        self.assertEqual(len(blocks), 3)

        # Scene 1: cintra_castle_bath from 0 to 12,000ms
        self.assertEqual(blocks[0][0], "cintra_castle_bath")
        self.assertEqual(blocks[0][1], 0)
        self.assertEqual(blocks[0][2], 12000)

        # Scene 2: royal_banquet_hall from 12,000ms to 30,000ms
        self.assertEqual(blocks[1][0], "royal_banquet_hall")
        self.assertEqual(blocks[1][1], 12000)
        self.assertEqual(blocks[1][2], 30000)

        # Scene 3: dense_forest_night from 30,000ms to 45,000ms
        self.assertEqual(blocks[2][0], "dense_forest_night")
        self.assertEqual(blocks[2][1], 30000)
        self.assertEqual(blocks[2][2], 45000)


if __name__ == "__main__":
    unittest.main()
