#!/usr/bin/env python3
"""
Test Suite: Combat & Action Audio Drama Fidelity (Hollywood / AAA-Game Standard)
==============================================================================
Validates:
1. FoleyCue combat contracts: is_lfe_sub_drop and vector trajectory.
2. ScreenplaySegment action-beat splitting, dual-perspective panning (-0.6/+0.6),
   and explosive intensity headroom.
3. Acoustic Bus Matrix: PROFILE_COMBAT_SHOCK (-24 dB, 4000ms release) and combat ducking resolution.
4. Linguistic Sanitizer: Combat vocal tags ([bellowing battlecry], [combat strain],
   [guttural grunt on blade deflect], [spits blood], [choked gasp], [slow motion]) retention.
5. UCS Combat Taxonomy mappings (WEAPMtl, WEAPBlun, WEAPBow, GOREAnat, LFEDrop, VOXExrt).
"""

import unittest
from audiobook_factory.contracts import (
    FoleyCue,
    ActingInstructions,
    SpatialCoordinates,
    ScreenplaySegment,
    ManifestValidationError,
)
from audiobook_factory.acoustic_bus_matrix import (
    get_ducking_profile,
    derive_ucs_category,
    PROFILE_COMBAT,
    PROFILE_COMBAT_SHOCK,
)
from audiobook_factory.sanitizer import (
    sanitize_screenplay_segment,
    validate_and_sanitize_translation,
    filter_bracketed_tags,
)


class TestCombatAudioDramaFidelity(unittest.TestCase):
    """Rigorous contract and behavior validation for combat and action audio drama engine."""

    def test_foley_cue_combat_fields(self):
        """Asserts that FoleyCue accepts is_lfe_sub_drop and vector trajectory fields."""
        cue = FoleyCue(
            cue_id="fc_combat_001",
            segment_index=12,
            anchor_word="वार",
            is_lfe_sub_drop=True,
            trajectory="left_to_right",
            azimuth_pan=-0.6,
        )
        self.assertTrue(cue.is_lfe_sub_drop)
        self.assertEqual(cue.trajectory, "left_to_right")
        self.assertEqual(cue.azimuth_pan, -0.6)

        # Default trajectory and is_lfe_sub_drop
        default_cue = FoleyCue(
            cue_id="fc_default_002",
            segment_index=1,
            anchor_word="तलवार",
        )
        self.assertFalse(default_cue.is_lfe_sub_drop)
        self.assertEqual(default_cue.trajectory, "static")

        # Invalid trajectory should raise validation error
        with self.assertRaises(Exception):
            FoleyCue(
                cue_id="fc_invalid",
                segment_index=1,
                anchor_word="वार",
                trajectory="diagonal_warp",  # type: ignore
            )

    def test_acting_instructions_combat_styles(self):
        """Validates that ActingInstructions supports combat delivery styles."""
        acting = ActingInstructions(delivery_style="combat_strain", pacing=1.1)
        self.assertEqual(acting.delivery_style, "combat_strain")
        self.assertEqual(acting.pacing, 1.1)

        acting_slowmo = ActingInstructions(delivery_style="slow_motion", pacing=0.5)
        self.assertEqual(acting_slowmo.delivery_style, "slow_motion")

    def test_screenplay_action_beat_contracts(self):
        """Validates action-beat splitting and dual-perspective panning (-0.6 vs +0.6)."""
        # Attacker action beat
        attacker_beat = ScreenplaySegment(
            index=1,
            type="action",
            speaker="Foley",
            text="[ACTION]",
            pause_after_ms=1200,
            intensity_level="explosive",
            spatial=SpatialCoordinates(pan=-0.6),
            sfx_cues=["sword_slash", "mud_slide"],
        )
        self.assertEqual(attacker_beat.type, "action")
        self.assertEqual(attacker_beat.speaker, "Foley")
        self.assertEqual(attacker_beat.pause_after_ms, 1200)
        self.assertEqual(attacker_beat.intensity_level, "explosive")
        self.assertEqual(attacker_beat.spatial.pan, -0.6)

        # Defender parry beat
        defender_beat = ScreenplaySegment(
            index=2,
            type="dialogue",
            speaker="Defender",
            text="[combat strain] तेरी मां की... गिर साले!",
            pause_after_ms=800,
            spatial=SpatialCoordinates(pan=0.6),
        )
        self.assertEqual(defender_beat.spatial.pan, 0.6)

    def test_ducking_profile_combat_shock(self):
        """Validates PROFILE_COMBAT_SHOCK resolution and calibrated values."""
        shock_profile = get_ducking_profile("tinnitus concussion shock")
        self.assertEqual(shock_profile.profile_name, "combat_shock")
        self.assertEqual(shock_profile.attenuation_db, -24.0)
        self.assertEqual(shock_profile.release_ms, 4000)

        combat_profile = get_ducking_profile("intense sword combat")
        self.assertEqual(combat_profile.profile_name, "combat_shouting")
        self.assertEqual(combat_profile.attenuation_db, -22.0)
        self.assertEqual(combat_profile.release_ms, 250)

    def test_sanitizer_combat_vocal_tags(self):
        """Asserts that linguistic sanitizer preserves all combat vocal tags and raw battle profanity."""
        test_text = "[bellowing battlecry] काट के फेंक दूंगा भोसड़ीके! [spits blood]"
        seg = {
            "index": 1,
            "type": "dialogue",
            "speaker": "Warrior",
            "text": test_text,
            "pause_after_ms": 1000,
        }
        sanitized = sanitize_screenplay_segment(seg)
        self.assertIn("[bellowing battlecry]", sanitized["text"])
        self.assertIn("[spits blood]", sanitized["text"])
        self.assertIn("काट के फेंक दूंगा भोसड़ीके!", sanitized["text"])

        # Test additional tags
        tags = [
            "[combat strain]",
            "[diaphragm strain]",
            "[choked gasp]",
            "[guttural grunt on blade deflect]",
            "[ragged heaving pant]",
            "[slow motion]",
        ]
        for tag in tags:
            tag_seg = {
                "index": 2,
                "type": "dialogue",
                "speaker": "Fighter",
                "text": f"{tag} संभल के!",
            }
            res = sanitize_screenplay_segment(tag_seg)
            self.assertIn(tag, res["text"], f"Tag {tag} was unexpectedly stripped!")

    def test_ucs_combat_taxonomy_mapping(self):
        """Validates that UCS rules correctly classify diverse combat cues."""
        self.assertEqual(derive_ucs_category("steel plate armor dent"), "WEAPMtl")
        self.assertEqual(derive_ucs_category("heavy warhammer club smash"), "WEAPBlun")
        self.assertEqual(derive_ucs_category("arrow whipcrack flyby"), "WEAPBow")
        self.assertEqual(derive_ucs_category("bone snap and cartilage crunch"), "GOREAnat")
        self.assertEqual(derive_ucs_category("solar plexus lfe sub drop"), "LFEDrop")
        self.assertEqual(derive_ucs_category("battlecry and guttural grunt"), "VOXExrt")


if __name__ == "__main__":
    unittest.main()
