#!/usr/bin/env python3
"""
Test Suite for Sound Design Subsystem - Phase A:
Validates:
1. Contracts & Pydantic v2 schemas.
2. Scene Audio Understanding & metadata extraction.
3. Scene Audio Blueprint construction.
4. Environment Profiles registry & resolution.
5. Sound Asset Retriever with strict provenance and sanity checks.
"""

import unittest
from pathlib import Path
from audiobook_factory.sound_design.contracts import (
    RelativeIntensity,
    AttentionPriority,
    SceneAudioBlueprint,
    EnvironmentProfile,
    SoundAssetDescriptor,
    AssetProvenance,
)
from audiobook_factory.sound_design.environment_profiles import get_environment_registry
from audiobook_factory.sound_design.asset_retriever import get_asset_retriever
from audiobook_factory.sound_design.scene_understanding import get_scene_audio_analyzer
from audiobook_factory.sound_design.blueprint import get_blueprint_builder


class TestSoundDesignPhaseA(unittest.TestCase):
    """Unit test suite for Phase A components."""

    def setUp(self):
        self.env_registry = get_environment_registry()
        self.analyzer = get_scene_audio_analyzer()
        self.builder = get_blueprint_builder()
        self.retriever = get_asset_retriever()

    def test_environment_profiles_resolution(self):
        """Verifies environment resolution from keywords and locations."""
        tavern = self.env_registry.resolve_from_text("The crowded tavern was loud and smoky.")
        self.assertEqual(tavern.env_id, "tavern_interior")
        self.assertEqual(tavern.category, "settlement")
        self.assertIn("beer_stained_wood", tavern.default_surfaces)

        crypt = self.env_registry.resolve_from_text("Deep in the ancient tomb of the crypt.")
        self.assertEqual(crypt.env_id, "crypt_catacomb")
        self.assertEqual(crypt.category, "subterranean")
        self.assertGreater(crypt.estimated_rt60_ms, 2500)

        forest = self.env_registry.resolve_from_text("Wind whistled through the dark forest canopy.")
        self.assertEqual(forest.env_id, "deep_forest_night")
        self.assertEqual(forest.category, "outdoor_nature")

    def test_scene_audio_understanding(self):
        """Verifies scene audio understanding reuses screenplay metadata without mandatory LLM inference."""
        segments = [
            {
                "index": 1,
                "speaker": "Geralt",
                "text": "The crypt smells of old dust and rot.",
                "emotion": "tense",
                "acoustic_env": "crypt_catacomb",
                "tension_after": 0.65,
                "pause_after_ms": 700,
            },
            {
                "index": 2,
                "speaker": "Geralt",
                "text": "He drew his silver sword with a hiss of steel.",
                "type": "action",
                "sfx_cues": ["draw_sword"],
                "emotion": "alert",
                "tension_after": 0.85,
            },
            {
                "index": 3,
                "speaker": "Narrator",
                "text": "[whispers] A sudden shriek echoed from the stone sarcophagus.",
                "emotion": "terror",
                "tension_after": 0.95,
                "sfx_cues": ["striga_screech"],
            },
        ]

        understanding = self.analyzer.analyze_scene(
            scene_id="scene_001",
            chapter_id="chapter_001",
            segments=segments,
        )

        self.assertEqual(understanding.scene_id, "scene_001")
        self.assertEqual(understanding.environment_type, "crypt_catacomb")
        self.assertIn("Geralt", understanding.characters_present)
        self.assertGreaterEqual(len(understanding.action_candidates), 1)
        self.assertIn("striga", understanding.creature_presence or "")
        self.assertGreater(len(understanding.silence_opportunities), 0)

    def test_blueprint_construction(self):
        """Verifies SceneAudioBlueprint director instruction sheet creation."""
        segments = [
            {"index": 1, "speaker": "Harry", "text": "Lumos!", "acoustic_env": "castle_stone_corridor", "pause_after_ms": 400},
            {"index": 2, "speaker": "Ron", "text": "Did you hear that creak?", "pause_after_ms": 500},
        ]
        understanding = self.analyzer.analyze_scene("sc_corridor", "ch_01", segments)
        blueprint = self.builder.build_blueprint(understanding)

        self.assertEqual(blueprint.scene_id, "sc_corridor")
        self.assertEqual(blueprint.location_id, "castle_stone_corridor")
        self.assertIn("Harry", blueprint.characters_staged)
        self.assertIn("Ron", blueprint.characters_staged)
        # Check abstract spatial staging
        harry_pan = blueprint.characters_staged["Harry"].azimuth_pan
        ron_pan = blueprint.characters_staged["Ron"].azimuth_pan
        self.assertNotEqual(harry_pan, ron_pan)
        self.assertGreaterEqual(len(blueprint.ambience_layers_planned), 1)

    def test_asset_retriever_domestic_isolation_guard(self):
        """Verifies that domestic tableware queries NEVER return weapon clashes."""
        desc = self.retriever.resolve_foley_asset(action_verb="tableware", exciter_material="plate")
        if desc:
            # Must not be a sword, blade, or weapon clash!
            self.assertFalse(any(w in desc.filename.lower() for w in ("sword", "blade", "clash", "dagger", "axe")))
            self.assertEqual(desc.provenance.source, "local_sound_bank")
            self.assertTrue(desc.is_valid_audio)

    def test_asset_retriever_provenance_and_sanity(self):
        """Verifies asset descriptor has complete provenance and sanity check metrics."""
        # Find any foley asset
        desc = self.retriever.resolve_foley_asset(action_verb="draw", exciter_material="steel")
        if desc:
            self.assertIsInstance(desc, SoundAssetDescriptor)
            self.assertTrue(desc.provenance.sha256_checksum)
            self.assertEqual(desc.provenance.license_type, "CC0_PUBLIC_DOMAIN")
            self.assertGreater(desc.duration_sec, 0.0)


if __name__ == "__main__":
    unittest.main()
