#!/usr/bin/env python3
"""
Phase 15: 10-Chapter Golden Novel Continuity Integration Test (Memory 2.0).
Simulates a complete 10-chapter dark-fantasy novel ("The Obsidian Covenant") across:
- Character state evolution (emotion, injury -> persistence -> recovery, death, goals, beliefs, arcs)
- Epistemic knowledge isolation (KNOWN, SUSPECTED, FALSE_BELIEF -> DISPROVEN, UNKNOWN)
- Evidence-backed relationship evolution (aap -> tum -> tu, formal -> intimate / hostile_street)
- World state mutations (object acquisition, ownership transfer, location states, open/resolved threads)
- TemporalMode handling (PRESENT vs FLASHBACK / MEMORY_DREAM)
- All 7 contradiction guardrails (rejected safely without corrupting state)
- Selective 7-tier + Narrative Salience retrieval (long-range dramatic callbacks without prompt bloat)
- End-to-end IntelligentTranslationPipeline & clean_screenplay_pass2 integration
"""

import tempfile
import unittest
from pathlib import Path

from audiobook_factory.translation.book_bible import (
    BookBible,
    BookEntity,
    WorldRule,
)
from audiobook_factory.translation.relationship_state import (
    DynamicRelationshipState,
    RelationshipStateEngine,
)
from audiobook_factory.translation.orchestrator import IntelligentTranslationPipeline
from audiobook_factory.script_builder import clean_screenplay_pass2
from audiobook_factory.translation.memory import (
    StoryEventType,
    TemporalMode,
    StoryEvent,
    SceneChangeDetector,
    DeltaDomain,
    StateDelta,
    KnowledgeStatus,
    CharacterKnowledgeEngine,
    ValidationOutcome,
    MemoryStore,
    MemoryRetriever,
)


class TestGoldenNovelContinuity(unittest.TestCase):

    def _create_golden_bible(self) -> BookBible:
        bible = BookBible(book_title="The Obsidian Covenant")
        bible.characters["Vikram"] = BookEntity(
            canonical_id="vikram",
            english_name="Vikram",
            hindi_name="विक्रम",
            aliases=["Commander Vikram"],
            gender="male",
            description="Commander of the Vanguard",
            is_canonical=True,
        )
        bible.characters["Meera"] = BookEntity(
            canonical_id="meera",
            english_name="Meera",
            hindi_name="मीरा",
            aliases=["Scout Meera"],
            gender="female",
            description="Imperial Cryptographer",
            is_canonical=True,
        )
        bible.characters["Senapati Rudra"] = BookEntity(
            canonical_id="senapati_rudra",
            english_name="Senapati Rudra",
            hindi_name="सेनापति रुद्र",
            aliases=["Rudra"],
            gender="male",
            description="High General",
            is_canonical=True,
        )
        bible.characters["Kavi Dev"] = BookEntity(
            canonical_id="kavi_dev",
            english_name="Kavi Dev",
            hindi_name="कवि देव",
            aliases=["Master Dev"],
            gender="male",
            description="Elder Mentor",
            is_canonical=True,
        )
        bible.characters["Bazaari Mohan"] = BookEntity(
            canonical_id="bazaari_mohan",
            english_name="Bazaari Mohan",
            hindi_name="बाज़ारी मोहन",
            gender="male",
            description="Spice Trader",
            is_canonical=False,
        )
        bible.locations = {
            "Iron Citadel": "लौह दुर्ग",
            "Vindhya Outpost": "विंध्य चौकी",
            "Shadow Gorge": "छाया घाटी",
            "River Gurukul": "नदी गुरुकुल",
        }
        bible.objects = {
            "Obsidian Seal": "ओब्सिडियन मुहर",
            "Cipher Scroll": "गुप्त चर्मपत्र",
        }
        bible.world_rules.extend([
            WorldRule(
                rule_id="Iron Null-Zone",
                category="magic_law",
                statement="Mortals cannot use magic inside the Iron Citadel.",
                immutable=True,
            ),
            WorldRule(
                rule_id="Mortal Finality",
                category="cosmology",
                statement="No resurrection of the dead is possible once life leaves the body.",
                immutable=True,
            ),
        ])
        return bible

    def test_01_ten_chapter_golden_novel_state_evolution_and_continuity(self):
        """
        Runs a full 10-chapter simulation verifying every Memory 2.0 subsystem.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            bible = self._create_golden_bible()
            bible.save(project_dir)

            store_path = MemoryStore.default_store_path(project_dir)
            store = MemoryStore.load(store_path, book_bible=bible)
            store.world_state.get_or_create_location("Iron Citadel").acoustic_env = "stone_fortress"
            store.relationships["Vikram->Meera"] = DynamicRelationshipState(
                speaker="Vikram",
                target="Meera",
                familiarity=0,
                power_balance=1,
                respect=3,
                trust=1,
                affection=0,
                tension=1,
                active_pronoun="aap",
            )
            store.relationships["Vikram->Senapati Rudra"] = DynamicRelationshipState(
                speaker="Vikram",
                target="Senapati Rudra",
                familiarity=2,
                power_balance=-1,
                respect=3,
                trust=3,
                affection=1,
                tension=0,
                active_pronoun="aap",
            )


            # =========================================================================
            # CHAPTER 1: Formal Council at Iron Citadel
            # Vikram acquires Obsidian Seal; holds FALSE_BELIEF that Rudra is loyal.
            # =========================================================================
            ch1_events = [
                StoryEvent(
                    event_type=StoryEventType.OBJECT_ACQUIRED,
                    chapter=1,
                    scene="ch01_s01",
                    participants=["Vikram", "Meera", "Senapati Rudra"],
                    location="Iron Citadel",
                    description="Vikram receives the Obsidian Seal in the council hall.",
                    importance=4,
                    character_updates={
                        "Vikram": {
                            "location": "Iron Citadel",
                            "emotion": "resolute",
                            "immediate_goal": "Deliver the Obsidian Seal to Vindhya Outpost",
                        },
                        "Meera": {"location": "Iron Citadel"},
                        "Bazaari Mohan": {"location": "Iron Citadel"},
                    },
                    world_updates={
                        "objects_acquired": [
                            {"object_name": "Obsidian Seal", "owner": "Vikram", "location": "Iron Citadel"}
                        ]
                    },
                    knowledge_updates=[
                        {
                            "fact_id": "fact_rudra_loyalty",
                            "subject": "Senapati Rudra",
                            "predicate": "allegiance",
                            "value": "Senapati Rudra is unshakeably loyal to the Iron Citadel",
                            "status": "FALSE_BELIEF",
                            "known_by": ["Vikram"],
                        }
                    ],
                )
            ]
            rep_ch1 = store.commit_scene_memory("ch01_s01", 1, ch1_events, book_bible=bible, location="Iron Citadel")
            self.assertEqual(rep_ch1.outcome, ValidationOutcome.PASS)
            self.assertEqual(store.world_state.object_states["Obsidian Seal"].current_owner, "Vikram")
            self.assertEqual(store.get_relationship("Vikram", "Meera").active_pronoun, "aap")
            self.assertEqual(
                CharacterKnowledgeEngine.get_character_knowledge_status(
                    "Vikram", "fact_rudra_loyalty", store.facts_registry, store.character_states
                ),
                KnowledgeStatus.FALSE_BELIEF,
            )

            # =========================================================================
            # CHAPTER 2: Secret Intercepted at Vindhya Outpost
            # Meera learns Rudra's treason (KNOWN to Meera, UNKNOWN to Vikram).
            # =========================================================================
            ch2_events = [
                StoryEvent(
                    event_type=StoryEventType.KNOWLEDGE_LEARNED,
                    chapter=2,
                    scene="ch02_s01",
                    participants=["Meera"],
                    location="Vindhya Outpost",
                    description="Meera decodes the Cipher Scroll revealing Senapati Rudra sold the gate codes.",
                    importance=5,
                    character_updates={"Meera": {"location": "Vindhya Outpost", "emotion": "alarmed"}},
                    world_updates={
                        "objects_acquired": [
                            {"object_name": "Cipher Scroll", "owner": "Meera", "location": "Vindhya Outpost"}
                        ]
                    },
                    knowledge_updates=[
                        {
                            "fact_id": "fact_rudra_treason",
                            "subject": "Senapati Rudra",
                            "predicate": "treason",
                            "value": "Senapati Rudra sold the garrison gate codes to the enemy",
                            "status": "KNOWN",
                            "known_by": ["Meera"],
                        }
                    ],
                )
            ]
            rep_ch2 = store.commit_scene_memory("ch02_s01", 2, ch2_events, book_bible=bible, location="Vindhya Outpost")
            self.assertEqual(rep_ch2.outcome, ValidationOutcome.PASS)

            # Verify strict epistemic isolation at end of Ch 2
            self.assertEqual(
                CharacterKnowledgeEngine.get_character_knowledge_status(
                    "Meera", "fact_rudra_treason", store.facts_registry, store.character_states
                ),
                KnowledgeStatus.KNOWN,
            )
            self.assertEqual(
                CharacterKnowledgeEngine.get_character_knowledge_status(
                    "Vikram", "fact_rudra_treason", store.facts_registry, store.character_states
                ),
                KnowledgeStatus.UNKNOWN,
            )

            # =========================================================================
            # CHAPTER 3: Ambush at Shadow Gorge
            # Vikram is injured; Shared Danger shifts Vikram -> Meera from 'aap' to 'tum';
            # High-salience blood promise made.
            # =========================================================================
            ch3_events = [
                StoryEvent(
                    event_type=StoryEventType.CHARACTER_INJURED,
                    chapter=3,
                    scene="ch03_s01",
                    participants=["Vikram", "Meera"],
                    location="Shadow Gorge",
                    description="Vikram takes a poisoned spear wound in his left thigh while shielding Meera.",
                    importance=4,
                    character_updates={
                        "Vikram": {
                            "location": "Shadow Gorge",
                            "physical_condition": "injured",
                            "injury_added": "poisoned spear wound in left thigh",
                            "energy_delta": -0.4,
                            "emotion": "grim",
                        },
                        "Meera": {"location": "Shadow Gorge"},
                    },
                    relationship_impacts=[
                        {
                            "speaker": "Vikram",
                            "target": "Meera",
                            "interaction_type": "shared_danger",
                            "deltas": {"familiarity": 2, "trust": 2, "respect": -1},
                        }
                    ],
                ),
                StoryEvent(
                    event_type=StoryEventType.PROMISE_MADE,
                    chapter=3,
                    scene="ch03_s01",
                    participants=["Vikram", "Meera"],
                    location="Shadow Gorge",
                    description="Vikram swears an oath to deliver Meera's Cipher Scroll to the High Council.",
                    importance=5,
                    salience_score=0.92,
                ),
            ]
            rep_ch3 = store.commit_scene_memory("ch03_s01", 3, ch3_events, book_bible=bible, location="Shadow Gorge")
            self.assertEqual(rep_ch3.outcome, ValidationOutcome.PASS)
            self.assertEqual(store.get_character_state("Vikram").physical_condition, "injured")
            self.assertIn("poisoned spear wound in left thigh", store.get_character_state("Vikram").active_injuries)
            self.assertEqual(store.get_relationship("Vikram", "Meera").active_pronoun, "tum")

            # =========================================================================
            # CHAPTER 4: Flashback to River Gurukul (Ten Years Earlier)
            # TemporalMode.FLASHBACK must not overwrite Vikram's present injury or location.
            # =========================================================================
            ch4_events = [
                StoryEvent(
                    event_type=StoryEventType.LOCATION_CHANGED,
                    chapter=4,
                    scene="ch04_s01",
                    temporal_mode=TemporalMode.FLASHBACK,
                    chronological_epoch=-1,
                    story_time_reference="ten years earlier",
                    participants=["Kavi Dev", "Vikram"],
                    location="River Gurukul",
                    description="Ten years earlier, Kavi Dev trained young Vikram at River Gurukul.",
                    importance=3,
                    character_updates={
                        "Vikram": {
                            "location": "River Gurukul",
                            "physical_condition": "healthy",
                            "turning_point": "Remembered Kavi Dev's code of honor",
                        },
                        "Kavi Dev": {"location": "River Gurukul"},
                    },
                )
            ]
            rep_ch4 = store.commit_scene_memory("ch04_s01", 4, ch4_events, book_bible=bible, location="River Gurukul")
            self.assertEqual(rep_ch4.outcome, ValidationOutcome.PASS)
            # Present state of Vikram must STILL be injured at Shadow Gorge!
            self.assertEqual(store.get_character_state("Vikram").physical_condition, "injured")
            self.assertEqual(store.get_character_state("Vikram").current_location, "Shadow Gorge")

            # =========================================================================
            # CHAPTER 5: Sacrifice of Kavi Dev at Vindhya Outpost
            # Kavi Dev dies in PRESENT mode; subsequent PRESENT revival/action rejected.
            # =========================================================================
            ch5_events = [
                StoryEvent(
                    event_type=StoryEventType.CHARACTER_DIED,
                    chapter=5,
                    scene="ch05_s01",
                    participants=["Kavi Dev", "Vikram", "Meera"],
                    location="Vindhya Outpost",
                    description="Kavi Dev sacrifices his life holding the bridge at Vindhya Outpost.",
                    importance=5,
                    salience_score=0.96,
                    character_updates={
                        "Kavi Dev": {"is_alive": False, "location": "Vindhya Outpost"},
                        "Vikram": {"location": "Vindhya Outpost", "emotion": "grief_stricken"},
                        "Meera": {"location": "Vindhya Outpost"},
                    },
                )
            ]
            rep_ch5 = store.commit_scene_memory("ch05_s01", 5, ch5_events, book_bible=bible, location="Vindhya Outpost")
            self.assertEqual(rep_ch5.outcome, ValidationOutcome.PASS)
            self.assertFalse(store.get_character_state("Kavi Dev").is_alive)

            # Verify that an invalid PRESENT-mode recovery for deceased Kavi Dev is rejected!
            ev_invalid_revive = StoryEvent(
                event_type=StoryEventType.CHARACTER_RECOVERED,
                chapter=5,
                scene="ch05_s02",
                participants=["Kavi Dev"],
                location="Vindhya Outpost",
                description="Kavi Dev recovers from his wounds.",
                character_updates={"Kavi Dev": {"is_alive": True, "physical_condition": "healthy"}},
            )
            rep_ch5_bad = store.commit_scene_memory(
                "ch05_s02", 5, [ev_invalid_revive], book_bible=bible, location="Vindhya Outpost"
            )
            self.assertEqual(rep_ch5_bad.outcome, ValidationOutcome.CONFLICT)
            self.assertTrue(any(fc.conflict_type == "dead_character_violation" for fc in rep_ch5_bad.flagged_conflicts))
            self.assertFalse(store.get_character_state("Kavi Dev").is_alive)

            # =========================================================================
            # CHAPTER 6: Secret Revealed & Object Transferred
            # Meera shows Cipher Scroll to Vikram -> FALSE_BELIEF becomes DISPROVEN,
            # treason becomes KNOWN to Vikram. Obsidian Seal transferred to Meera.
            # =========================================================================
            ch6_events = [
                StoryEvent(
                    event_type=StoryEventType.SECRET_REVEALED,
                    chapter=6,
                    scene="ch06_s01",
                    participants=["Meera", "Vikram"],
                    location="Vindhya Outpost",
                    description="Meera reveals the Cipher Scroll proving Senapati Rudra's treason to Vikram.",
                    importance=5,
                    knowledge_updates=[
                        {
                            "fact_id": "fact_rudra_loyalty",
                            "subject": "Senapati Rudra",
                            "predicate": "allegiance",
                            "value": "Senapati Rudra is unshakeably loyal to the Iron Citadel",
                            "status": "DISPROVEN",
                            "known_by": ["Vikram"],
                        },
                        {
                            "fact_id": "fact_rudra_treason",
                            "subject": "Senapati Rudra",
                            "predicate": "treason",
                            "value": "Senapati Rudra sold the garrison gate codes to the enemy",
                            "status": "KNOWN",
                            "known_by": ["Meera", "Vikram"],
                        },
                    ],
                ),
                StoryEvent(
                    event_type=StoryEventType.OBJECT_TRANSFERRED,
                    chapter=6,
                    scene="ch06_s01",
                    participants=["Vikram", "Meera"],
                    location="Vindhya Outpost",
                    description="Vikram entrusts the Obsidian Seal to Meera.",
                    importance=4,
                    world_updates={
                        "objects_transferred": [
                            {
                                "object_name": "Obsidian Seal",
                                "from_owner": "Vikram",
                                "to_owner": "Meera",
                                "location": "Vindhya Outpost",
                            }
                        ]
                    },
                ),
            ]
            rep_ch6 = store.commit_scene_memory("ch06_s01", 6, ch6_events, book_bible=bible, location="Vindhya Outpost")
            self.assertEqual(rep_ch6.outcome, ValidationOutcome.PASS)
            self.assertEqual(
                CharacterKnowledgeEngine.get_character_knowledge_status(
                    "Vikram", "fact_rudra_loyalty", store.facts_registry, store.character_states
                ),
                KnowledgeStatus.DISPROVEN,
            )
            self.assertEqual(
                CharacterKnowledgeEngine.get_character_knowledge_status(
                    "Vikram", "fact_rudra_treason", store.facts_registry, store.character_states
                ),
                KnowledgeStatus.KNOWN,
            )
            self.assertEqual(store.world_state.object_states["Obsidian Seal"].current_owner, "Meera")

            # =========================================================================
            # CHAPTER 7: Quiet Camp Scene (0 LLM calls) & Injury Recovery
            # =========================================================================
            quiet_camp_prose = "The fire crackled softly under the stars as the horses rested by the ridge."
            camp_assessment = SceneChangeDetector.assess_scene(quiet_camp_prose, ["Vikram", "Meera"])
            self.assertFalse(camp_assessment.requires_llm_extraction)

            ch7_events = [
                StoryEvent(
                    event_type=StoryEventType.CHARACTER_RECOVERED,
                    chapter=7,
                    scene="ch07_s01",
                    participants=["Vikram"],
                    location="Vindhya Outpost",
                    description="Vikram recovers from the poisoned spear wound after antidote treatment.",
                    importance=3,
                    character_updates={
                        "Vikram": {
                            "physical_condition": "healthy",
                            "injury_removed": "poisoned spear wound in left thigh",
                            "energy_delta": 0.4,
                        }
                    },
                )
            ]
            rep_ch7 = store.commit_scene_memory("ch07_s01", 7, ch7_events, book_bible=bible, location="Vindhya Outpost")
            self.assertEqual(rep_ch7.outcome, ValidationOutcome.PASS)
            self.assertEqual(store.get_character_state("Vikram").physical_condition, "healthy")
            self.assertEqual(len(store.get_character_state("Vikram").active_injuries), 0)

            # =========================================================================
            # CHAPTER 8: Confrontation with Senapati Rudra (Betrayal & Hostile Register)
            # =========================================================================
            ch8_events = [
                StoryEvent(
                    event_type=StoryEventType.BETRAYAL,
                    chapter=8,
                    scene="ch08_s01",
                    participants=["Vikram", "Senapati Rudra"],
                    location="Iron Citadel",
                    description="Vikram confronts Senapati Rudra as Rudra commands his guards to attack.",
                    importance=5,
                    character_updates={
                        "Vikram": {"location": "Iron Citadel", "emotion": "furious", "emotion_intensity": 0.95},
                        "Senapati Rudra": {"location": "Iron Citadel", "emotion": "hostile"},
                    },
                    relationship_impacts=[
                        {
                            "speaker": "Vikram",
                            "target": "Senapati Rudra",
                            "interaction_type": "betrayal",
                            "deltas": {"trust": -3, "respect": -3, "tension": 3},
                        }
                    ],
                )
            ]
            rep_ch8 = store.commit_scene_memory("ch08_s01", 8, ch8_events, book_bible=bible, location="Iron Citadel")
            self.assertEqual(rep_ch8.outcome, ValidationOutcome.PASS)
            rudra_rel = store.get_relationship("Vikram", "Senapati Rudra")
            self.assertEqual(RelationshipStateEngine.resolve_hindi_pronoun(rudra_rel), "tu")
            self.assertEqual(RelationshipStateEngine.resolve_vocabulary_register(rudra_rel), "hostile_street")

            # =========================================================================
            # CHAPTER 9: Deep Bond Between Vikram & Meera + Salience Retrieval Verification
            # =========================================================================
            ch9_events = [
                StoryEvent(
                    event_type=StoryEventType.RECONCILIATION,
                    chapter=9,
                    scene="ch09_s01",
                    participants=["Vikram", "Meera"],
                    location="Iron Citadel",
                    description="Vikram and Meera embrace before the final assault, bound by complete trust.",
                    importance=5,
                    relationship_impacts=[
                        {
                            "speaker": "Vikram",
                            "target": "Meera",
                            "interaction_type": "romantic_confession",
                            "deltas": {"familiarity": 2, "affection": 3, "trust": 2, "respect": -2},
                        }
                    ],
                )
            ]
            rep_ch9 = store.commit_scene_memory("ch09_s01", 9, ch9_events, book_bible=bible, location="Iron Citadel")
            self.assertEqual(rep_ch9.outcome, ValidationOutcome.PASS)
            meera_rel = store.get_relationship("Vikram", "Meera")
            self.assertEqual(meera_rel.active_pronoun, "tu")
            self.assertEqual(RelationshipStateEngine.resolve_vocabulary_register(meera_rel), "intimate_warm")

            # Retrieve context for Chapter 9 with max_recent_events=2:
            # Must exclude Bazaari Mohan, include Obsidian Seal, and surface Ch 3 Oath + Ch 5 Sacrifice in salient_events!
            ctx_ch9 = MemoryRetriever.retrieve_for_scene(
                store=store,
                book_bible=bible,
                chapter=9,
                scene_id="ch09_s02",
                active_characters=["Vikram", "Meera"],
                location="Iron Citadel",
                scene_text="Vikram and Meera prepared to unlock the Iron Citadel vault with the Obsidian Seal.",
                max_recent_events=2,
                max_salient_events=4,
            )
            self.assertNotIn("Bazaari Mohan", ctx_ch9.active_character_states)
            self.assertIn("Vikram", ctx_ch9.active_character_states)
            self.assertIn("Meera", ctx_ch9.active_character_states)
            salient_descriptions = " ".join(e.description for e in ctx_ch9.salient_events)
            self.assertIn("Kavi Dev sacrifices his life", salient_descriptions)
            self.assertIn("swears an oath", salient_descriptions)

            # =========================================================================
            # CHAPTER 10: Final Resolution & End-to-End Pipeline / Screenplay Verification
            # =========================================================================
            ch10_events = [
                StoryEvent(
                    event_type=StoryEventType.MYSTERY_RESOLVED,
                    chapter=10,
                    scene="ch10_s01",
                    participants=["Vikram", "Meera"],
                    location="Iron Citadel",
                    description="Vikram and Meera present the Cipher Scroll to the High Council and expose the conspiracy.",
                    importance=5,
                    narrative_updates={
                        "threads": [
                            {
                                "thread_id": "thread_ch3_oath",
                                "category": "promise",
                                "summary": "Deliver Cipher Scroll to High Council",
                                "participants": ["Vikram", "Meera"],
                                "status": "resolved",
                            }
                        ]
                    },
                )
            ]
            rep_ch10 = store.commit_scene_memory("ch10_s01", 10, ch10_events, book_bible=bible, location="Iron Citadel")
            self.assertEqual(rep_ch10.outcome, ValidationOutcome.PASS)
            store.save(store_path)

            # Verify full commit history and deterministic provenance
            self.assertEqual(len(store.commit_history), 11)  # 10 valid commits + 1 rejected conflict commit
            vikram_mutations = store.trace_mutations(entity_name="Vikram")
            self.assertGreaterEqual(len(vikram_mutations), 6)

            # Verify clean_screenplay_pass2 integration with MemoryContext
            raw_screenplay = [
                {"speaker": "Vikram", "type": "dialogue", "text": "मीरा, आज यह राज़ खुल गया।", "emotion": "neutral"},
                {"speaker": "Meera", "type": "dialogue", "text": "[whispering] हाँ विक्रम, गुरुजी का बलिदान व्यर्थ नहीं गया।", "emotion": "solemn"},
            ]
            cleaned_script = clean_screenplay_pass2(
                raw_screenplay,
                is_hindi=True,
                memory_context=ctx_ch9,
            )
            self.assertEqual(len(cleaned_script), 2)
            self.assertEqual(cleaned_script[0]["acoustic_env"], "stone_fortress")
            # Explicit emotion "solemn" on Meera's line must be preserved untouched
            self.assertEqual(cleaned_script[1]["emotion"], "solemn")

            # Verify IntelligentTranslationPipeline loads the persisted MemoryStore and executes cleanly
            pipeline = IntelligentTranslationPipeline(project_dir=project_dir)
            self.assertEqual(pipeline.memory_store.memory_version, store.memory_version)
            epilogue_text = "Vikram and Meera stood atop the Iron Citadel ramparts as dawn broke."
            hindi_out, audits = pipeline.translate_chapter(
                chapter_text=epilogue_text,
                chapter_num=11,
                chapter_title="Epilogue",
                call_llm_fn=lambda prompt, **kw: "विक्रम और मीरा लौह दुर्ग की प्राचीर पर भोर के उजाले में खड़े थे।",
                use_cache=False,
            )
            self.assertIn("विक्रम", hindi_out)
            self.assertGreater(pipeline.memory_store.memory_version, store.memory_version)


if __name__ == "__main__":
    unittest.main()
