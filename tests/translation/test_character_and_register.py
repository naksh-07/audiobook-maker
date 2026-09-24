#!/usr/bin/env python3
"""
Unit tests for Character Language Profiles, Relationship State, and Hindustani Register Engine.
"""

import unittest
from audiobook_factory.translation.character_profile import (
    get_character_profile,
    CharacterLanguageProfile,
)
from audiobook_factory.translation.relationship_state import (
    DynamicRelationshipState,
    RelationshipStateEngine,
)
from audiobook_factory.translation.hindustani_register import (
    HindustaniRegisterEngine,
)


class TestCharacterAndRegister(unittest.TestCase):

    def test_01_character_profiles_distinct_cadence(self):
        from audiobook_factory.translation.character_profile import synthesize_character_profile
        cynic = synthesize_character_profile("Geralt", description="laconic cynic hunter")
        bard = synthesize_character_profile("Dandelion", description="theatrical witty poet singer")
        matriarch = synthesize_character_profile("Nenneke", description="authoritative mother abbess")

        self.assertEqual(cynic.sentence_length_preference, "terse")
        self.assertEqual(cynic.humor_style, "dry_sarcasm")

        self.assertEqual(bard.sentence_length_preference, "theatrical")
        self.assertEqual(bard.humor_style, "theatrical_wit")

        self.assertEqual(matriarch.honorific_preference, "aap")
        self.assertEqual(matriarch.formality_level, 4)

    def test_02_dynamic_relationship_state_pronoun_shifts(self):
        # 1. Close camaraderie -> tum
        rel_friends = DynamicRelationshipState(
            speaker="Geralt",
            target="Dandelion",
            familiarity=4,
            hostility=0,
            respect=3,
        )
        self.assertEqual(RelationshipStateEngine.resolve_pronoun_level(rel_friends), "tum")

        # 2. Hostile confrontation -> tu
        rel_hostile = DynamicRelationshipState(
            speaker="Geralt",
            target="Thug",
            hostility=4,
            authority_differential=2,
        )
        self.assertEqual(RelationshipStateEngine.resolve_pronoun_level(rel_hostile), "tu")

        # 3. Severe intimidation/fear -> aap
        rel_intimidated = DynamicRelationshipState(
            speaker="Thug",
            target="Geralt",
            fear=5,
            authority_differential=-4,
        )
        self.assertEqual(RelationshipStateEngine.resolve_pronoun_level(rel_intimidated), "aap")

    def test_03_hindustani_register_contextual_seasoning(self):
        engine = HindustaniRegisterEngine()
        # Passage seasoned with organic Urdu
        devanagari_prose = (
            "कमरे में अजीब सा सन्नाटा पसरा हुआ था। गेराल्ट ने अपनी तलवार का ख़ंजर निकाला "
            "और ज़ख़्म पर बंधी पट्टी को देखा। बाहर रात के ख़ौफ़ में कोई दस्तक हुई।"
        )
        res = engine.audit_text(devanagari_prose)
        self.assertTrue(res.is_balanced)
        self.assertIn("सन्नाटा", res.detected_seasoning_words)
        self.assertIn("ख़ंजर", res.detected_seasoning_words)
        self.assertIn("ज़ख़्म", res.detected_seasoning_words)
        self.assertIn("ख़ौफ़", res.detected_seasoning_words)
        self.assertIn("दस्तक", res.detected_seasoning_words)


if __name__ == "__main__":
    unittest.main()
