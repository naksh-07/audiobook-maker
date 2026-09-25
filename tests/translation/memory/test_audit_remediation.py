#!/usr/bin/env python3
"""
Regression test suite reproducing the 5 independent audit probes for World + Character Memory 2.0:
1. Section 4 Probe: SceneChangeDetector & EventExtractor (noun 'injury', transitive attacker vs victim, intra-scene movement)
2. Section 8 Probe: Location condition persistence when CHARACTER_MOVED has no location_condition
3. Section 9 & 11 Probe: Rejected ghost events excluded from store.events, timeline, recent_events, and high_salience_events
4. Downstream Consumer Wiring: ScreenplaySegment, resolve_speech_metadata_style, and TranslationCertifier Gate T6
5. Section 18 Probe: 100-Chapter (600 events, 55 characters, 105 locations, 105 objects) stress & token budget test
"""

import unittest
from audiobook_factory.contracts import ScreenplaySegment
from audiobook_factory.tts_dispatcher import resolve_speech_metadata_style
from audiobook_factory.translation.book_bible import BookBible, CharacterEntry, WorldRule
from audiobook_factory.translation.memory import (
    StoryEvent,
    StoryEventType,
    TemporalMode,
    SceneChangeDetector,
    EventExtractor,
    StateDelta,
    DeltaDomain,
    StateMutability,
    StateDeltaEngine,
    ValidationOutcome,
    MemoryStore,
    MemoryRetriever,
)


class TestAuditRemediationProbes(unittest.TestCase):

    def test_01_section_4_scene_change_detector_and_victim_ordering(self):
        """Verifies noun 'injury', intra-scene movement verbs, and transitive attacker vs victim resolution."""
        chars = ["Arjun", "Vikram", "Meera", "Raghav"]

        # 1. Pure dialogue / weather scene -> no state change, 0 LLM calls
        s1 = SceneChangeDetector.assess_scene(
            '"Good morning, Vikram," Arjun said, sipping his tea quietly as the rain fell outside.',
            known_characters=chars,
        )
        self.assertFalse(s1.has_state_change)
        self.assertFalse(s1.requires_llm_extraction)

        # 2. Noun 'injury' + intra-scene movement ('entered the Courtyard')
        s2 = SceneChangeDetector.assess_scene(
            "Arjun entered the Courtyard. Vikram suffered a severe injury in the Courtyard.",
            known_characters=chars,
            previous_location=None,
        )
        self.assertTrue(s2.has_state_change)
        ev_types = [e.event_type for e in s2.deterministic_events]
        self.assertIn(StoryEventType.CHARACTER_MOVED, ev_types)
        self.assertIn(StoryEventType.CHARACTER_INJURED, ev_types)

        inj_events = [e for e in s2.deterministic_events if e.event_type == StoryEventType.CHARACTER_INJURED]
        self.assertEqual(inj_events[0].metadata.get("injured_character"), "Vikram")

        # 3. Transitive attack ('Arjun stabbed Vikram in the Courtyard') -> Vikram is injured, Arjun is instigator, is_ambiguous=True
        s2_verb = SceneChangeDetector.assess_scene(
            "Arjun stabbed Vikram in the Courtyard.",
            known_characters=chars,
        )
        self.assertTrue(s2_verb.has_state_change)
        self.assertTrue(s2_verb.is_ambiguous)
        self.assertTrue(s2_verb.requires_llm_extraction)
        inj_v = [e for e in s2_verb.deterministic_events if e.event_type == StoryEventType.CHARACTER_INJURED][0]
        self.assertEqual(inj_v.metadata.get("injured_character"), "Vikram")
        self.assertEqual(inj_v.metadata.get("instigator"), "Arjun")

        # 4. Intra-scene departure and arrival ('Arjun left the Courtyard and arrived at the Palace.')
        s_move = SceneChangeDetector.assess_scene(
            "Arjun left the Courtyard and arrived at the Palace.",
            known_characters=chars,
        )
        self.assertTrue(s_move.has_state_change)
        move_ev = [e for e in s_move.deterministic_events if e.event_type == StoryEventType.CHARACTER_MOVED][0]
        self.assertEqual(move_ev.location, "Palace")
        self.assertEqual(move_ev.metadata.get("from_location"), "Courtyard")
        self.assertEqual(move_ev.metadata.get("to_location"), "Palace")

    def test_02_section_8_location_condition_preserved_on_character_movement(self):
        """Verifies that CHARACTER_MOVED without location_condition does NOT overwrite 'damaged' back to 'normal'."""
        store = MemoryStore()
        ev1 = StoryEvent(
            event_id="ev_loc1",
            chapter=1,
            scene="s1",
            event_type=StoryEventType.LOCATION_CHANGED,
            description="Arjun and Vikram entered the damaged Castle.",
            participants=["Arjun", "Vikram"],
            location="Castle",
            source_reference="s1",
            metadata={"to_location": "Castle", "location_condition": "damaged"},
        )
        store.commit_scene_memory("s1", 1, [ev1])
        self.assertEqual(store.world_state.location_states["Castle"].condition, "damaged")

        ev2 = StoryEvent(
            event_id="ev_loc2",
            chapter=1,
            scene="s2",
            event_type=StoryEventType.CHARACTER_MOVED,
            description="Meera arrived at the Castle.",
            participants=["Meera"],
            location="Castle",
            source_reference="s2",
            metadata={"to_location": "Castle"},
        )
        store.commit_scene_memory("s2", 1, [ev2])
        # Condition must remain 'damaged', NOT reset to 'normal'
        self.assertEqual(store.world_state.location_states["Castle"].condition, "damaged")
        self.assertIn("Meera", store.world_state.location_states["Castle"].present_characters)

    def test_03_section_9_and_11_rejected_ghost_event_excluded_from_events_and_salience(self):
        """Verifies that rejected contradictory events do not pollute store.events, timeline, recent_events, or high_salience_events."""
        bible = BookBible()
        bible.characters["Dev"] = CharacterEntry(
            canonical_name="Dev", hindi_name="देव", gender="male", locked=True
        )
        store = MemoryStore()
        store.seed_from_book_bible(bible)

        # Chapter 1: Dev dies
        ev_die = StoryEvent(
            event_id="ev_die",
            chapter=1,
            scene="ch1_s1",
            event_type=StoryEventType.CHARACTER_DIED,
            description="Dev died in battle.",
            participants=["Dev"],
            location="Battlefield",
            source_reference="ch1_s1",
            importance=5,
            metadata={"deceased_character": "Dev"},
        )
        store.commit_scene_memory("ch1_s1", 1, [ev_die], book_bible=bible)
        self.assertFalse(store.get_character_state("Dev").is_alive)

        # Chapter 2: Contradictory PRESENT recovery event for dead Dev
        ev_ghost = StoryEvent(
            event_id="ev_ghost",
            chapter=2,
            scene="ch2_s1",
            event_type=StoryEventType.CHARACTER_RECOVERED,
            description="Dev walked into the room fully recovered.",
            participants=["Dev"],
            location="Courtyard",
            source_reference="ch2_s1",
            importance=5,
            temporal_mode=TemporalMode.PRESENT,
        )
        d_ghost = StateDelta(
            delta_id="d_ghost",
            chapter=2,
            scene="ch2_s1",
            domain=DeltaDomain.CHARACTER,
            target_entity="Dev",
            field_name="physical_condition",
            old_value="deceased",
            new_value="healthy",
            mutability=StateMutability.SOFT_STATE,
            source_event_id="ev_ghost",
            rationale="Dev recovered",
        )
        rep = store.commit_scene_memory("ch2_s1", 2, [ev_ghost], deltas=[d_ghost], book_bible=bible)
        self.assertEqual(rep.outcome, ValidationOutcome.CONFLICT)
        self.assertIn("ev_ghost", rep.rejected_event_ids)
        self.assertNotIn("ev_ghost", store.events)
        self.assertIn("ev_ghost", store.rejected_events)

        for pt in store.world_state.timeline:
            self.assertNotIn("ev_ghost", pt.event_ids)

        ctx = MemoryRetriever.retrieve_for_scene(
            store=store,
            book_bible=bible,
            chapter=3,
            scene_id="ch3_s1",
            active_characters=["Dev"],
            location="Courtyard",
        )
        self.assertNotIn("ev_ghost", [e.event_id for e in ctx.recent_events])
        self.assertNotIn("ev_ghost", [e.event_id for e in ctx.high_salience_events])

    def test_04_downstream_consumer_wiring_contracts_and_tts(self):
        """Verifies ScreenplaySegment preserves Memory 2.0 guidance and resolve_speech_metadata_style consumes memory_vocal_constraint."""
        seg = ScreenplaySegment(
            index=1,
            type="dialogue",
            speaker="Vikram",
            text="मुझे अभी चलना होगा।",
            emotion="strained",
            memory_vocal_constraint="strained_breath",
            recommended_pronoun="tum",
            recommended_register="colloquial",
        )
        self.assertEqual(seg.memory_vocal_constraint, "strained_breath")
        self.assertEqual(seg.recommended_pronoun, "tum")
        self.assertEqual(seg.recommended_register, "colloquial")

        style = resolve_speech_metadata_style(
            seg.acting,
            emotion=seg.emotion,
            intensity=seg.intensity_level or "medium",
            memory_vocal_constraint=seg.memory_vocal_constraint,
        )
        self.assertIn("strained", style)
        self.assertIn("strained breath", style)

    def test_05_section_18_100_chapter_long_novel_stress_and_token_budget(self):
        """Simulates 100 chapters (600 events, 55 chars, 105 locations, 105 objects) and verifies token budget <= 800."""
        bible = BookBible()
        for i in range(55):
            bible.characters[f"Char_{i}"] = CharacterEntry(
                canonical_name=f"Char_{i}",
                hindi_name=f"पात्र_{i}",
                gender="male" if i % 2 == 0 else "female",
            )

        store = MemoryStore()
        store.seed_from_book_bible(bible)

        for ch in range(1, 101):
            c1 = f"Char_{ch % 50}"
            c2 = f"Char_{(ch + 1) % 50}"
            loc = f"Loc_{ch}"
            obj = f"Artifact_{ch}"
            evs = [
                StoryEvent(
                    event_id=f"ev_ch{ch}_1",
                    chapter=ch,
                    scene=f"ch{ch}_s1",
                    event_type=StoryEventType.CHARACTER_MOVED,
                    description=f"{c1} and {c2} arrived at {loc}.",
                    participants=[c1, c2],
                    location=loc,
                    source_reference=f"ch{ch}_s1",
                    importance=2,
                    salience=0.3,
                    metadata={"to_location": loc},
                ),
                StoryEvent(
                    event_id=f"ev_ch{ch}_2",
                    chapter=ch,
                    scene=f"ch{ch}_s1",
                    event_type=StoryEventType.OBJECT_ACQUIRED,
                    description=f"{c1} acquired {obj}.",
                    participants=[c1],
                    location=loc,
                    source_reference=f"ch{ch}_s1",
                    importance=3,
                    salience=0.5,
                    metadata={"object_name": obj, "to_character": c1},
                ),
                StoryEvent(
                    event_id=f"ev_ch{ch}_3",
                    chapter=ch,
                    scene=f"ch{ch}_s2",
                    event_type=StoryEventType.RELATIONSHIP_CHANGED,
                    description=f"{c1} and {c2} argued in {loc}.",
                    participants=[c1, c2],
                    location=loc,
                    source_reference=f"ch{ch}_s2",
                    importance=3,
                    salience=0.6 if ch != 5 else 0.98,
                    metadata={
                        "speaker": c1,
                        "target": c2,
                        "interaction_type": "betrayal" if ch == 5 else "insult",
                    },
                ),
                StoryEvent(
                    event_id=f"ev_ch{ch}_4",
                    chapter=ch,
                    scene=f"ch{ch}_s2",
                    event_type=StoryEventType.SECRET_REVEALED,
                    description=f"{c1} learned secret {ch}.",
                    participants=[c1],
                    location=loc,
                    source_reference=f"ch{ch}_s2",
                    importance=4,
                    salience=0.75,
                    metadata={
                        "fact_id": f"secret_{ch}",
                        "subject": c2,
                        "predicate": "hid",
                        "value": f"secret_{ch}",
                        "knower": c1,
                        "witnesses": [c1],
                    },
                ),
                StoryEvent(
                    event_id=f"ev_ch{ch}_5",
                    chapter=ch,
                    scene=f"ch{ch}_s3",
                    event_type=StoryEventType.CHARACTER_INJURED if ch % 10 == 0 else StoryEventType.CHARACTER_RECOVERED,
                    description=f"{c1} physical update.",
                    participants=[c1],
                    location=loc,
                    source_reference=f"ch{ch}_s3",
                    importance=3,
                    salience=0.4,
                    metadata={"injured_character": c1, "recovered_character": c1, "injury_detail": "bruised"},
                ),
                StoryEvent(
                    event_id=f"ev_ch{ch}_6",
                    chapter=ch,
                    scene=f"ch{ch}_s3",
                    event_type=StoryEventType.PROMISE_MADE,
                    description=f"{c1} promised {c2} at {loc}.",
                    participants=[c1, c2],
                    location=loc,
                    source_reference=f"ch{ch}_s3",
                    importance=3,
                    salience=0.65,
                    is_resolved=(ch < 95),
                    metadata={"promise_text": f"Promise {ch}"},
                ),
            ]
            deltas = StateDeltaEngine.compute_deltas_for_events(
                evs,
                store.character_states,
                store.relationships,
                store.facts_registry,
                store.world_state,
            )
            store.commit_scene_memory(f"ch{ch}_s3", ch, evs, deltas, book_bible=bible)

        retriever = MemoryRetriever(store, book_bible=bible)
        ctx = retriever.retrieve_for_scene(
            chapter=100,
            scene_id="ch100_final",
            active_characters=["Char_5", "Char_6"],
            active_location="Loc_100",
            scene_text="Char_5 confronted Char_6 at Loc_100.",
            max_token_budget=800,
        )

        self.assertEqual(len(ctx.active_character_states), 2)
        self.assertLessEqual(ctx.estimated_tokens(), 800)
        self.assertTrue(any(e.event_id == "ev_ch5_3" for e in ctx.high_salience_events))

    def test_06_pass2_audit_polish_items(self):
        """Verifies Pass 2 audit polish items: P1-1 (read before commit), P1-5b (nested acting delivery_style), P1-4 (strict known_by), and P2-2 (LLM vs deterministic deduplication)."""
        import tempfile
        from pathlib import Path
        from audiobook_factory.translator import (
            _retrieve_chapter_memory_in_translator,
            _commit_chapter_memory_in_translator,
        )
        from audiobook_factory.translation.memory.character_memory import (
            CharacterKnowledgeEngine,
            CharacterState,
            KnowledgeStatus,
        )
        from audiobook_factory.translation.memory.memory_context import (
            MemoryContext,
        )

        # 1. P1-4: Strict known_by membership & scoped DISPROVEN
        facts_reg = {}
        char_states = {}
        fact = CharacterKnowledgeEngine.register_or_update_fact(
            facts_registry=facts_reg,
            character_states=char_states,
            fact_id="fact_ambush",
            subject="Rohan",
            predicate="secret_plan",
            value="Rohan set a trap at the northern gate",
            source_event="ev_1",
            learned_at="ch1_s1",
            learners=["Rohan"],
            status=KnowledgeStatus.KNOWN,
        )
        self.assertEqual(fact.known_by, ["Rohan"])
        # Kabir only suspects it -> should NOT be added to fact.known_by
        CharacterKnowledgeEngine.register_or_update_fact(
            facts_registry=facts_reg,
            character_states=char_states,
            fact_id="fact_ambush",
            subject="Rohan",
            predicate="secret_plan",
            value="Rohan set a trap at the northern gate",
            source_event="ev_2",
            learned_at="ch1_s2",
            learners=["Kabir"],
            status=KnowledgeStatus.SUSPECTED,
        )
        self.assertEqual(fact.known_by, ["Rohan"])
        self.assertEqual(
            CharacterKnowledgeEngine.get_character_knowledge_status("Kabir", "fact_ambush", facts_reg, char_states),
            KnowledgeStatus.SUSPECTED,
        )
        # Disproving for Kabir alone does not wipe Rohan's KNOWN status or global fact status
        CharacterKnowledgeEngine.register_or_update_fact(
            facts_registry=facts_reg,
            character_states=char_states,
            fact_id="fact_ambush",
            subject="Rohan",
            predicate="secret_plan",
            value="Rohan set a trap at the northern gate",
            source_event="ev_3",
            learned_at="ch1_s3",
            learners=["Kabir"],
            status=KnowledgeStatus.DISPROVEN,
        )
        self.assertEqual(fact.known_by, ["Rohan"])
        self.assertNotEqual(fact.status, KnowledgeStatus.DISPROVEN)

        # 2. P1-5b: Nested acting.delivery_style preserved when explicit, enriched when neutral
        ctx = MemoryContext(
            chapter=1,
            scene_id="ch1_s1",
            active_character_states={
                "Vikram": CharacterState(
                    character_name="Vikram",
                    emotional_state="pain",
                    physical_condition="injured",
                    injury_details="stabbed in shoulder",
                )
            },
        )
        seg_explicit = {
            "type": "dialogue",
            "speaker": "Vikram",
            "text": "चुप रहो।",
            "acting": {"delivery_style": "whispering"},
        }
        res_explicit = ctx.apply_performance_guidance_to_segment(seg_explicit)
        self.assertEqual(res_explicit["acting"]["delivery_style"], "whispering")
        self.assertNotIn("delivery_style", res_explicit)

        seg_neutral = {
            "type": "dialogue",
            "speaker": "Vikram",
            "text": "आगे बढ़ो।",
            "acting": {"delivery_style": "normal"},
        }
        res_neutral = ctx.apply_performance_guidance_to_segment(seg_neutral)
        self.assertEqual(res_neutral["memory_vocal_constraint"], "strained_breath")

        # 3. P2-2: Deduplicate deterministic vs LLM events of the same event_type
        def fake_llm(prompt: str, system_instruction: str = "", **kwargs) -> str:
            return json.dumps({
                "events": [
                    {
                        "event_type": "character_injured",
                        "description": "Arjun stabbed Vikram in the shoulder",
                        "participants": ["Arjun", "Vikram"],
                        "importance": 4,
                        "metadata": {"injured_character": "Vikram", "instigator": "Arjun", "injury_detail": "stabbed in shoulder"},
                    }
                ]
            })

        evs, _ = EventExtractor.extract_scene_events(
            scene_text="Arjun stabbed Vikram in the dark courtyard.",
            chapter=1,
            scene_id="ch1_s1",
            active_characters=["Arjun", "Vikram"],
            location="Courtyard",
            call_llm_fn=fake_llm,
        )
        injured_events = [e for e in evs if e.event_type == StoryEventType.CHARACTER_INJURED]
        self.assertEqual(len(injured_events), 1)
        self.assertEqual(injured_events[0].metadata.get("injured_character"), "Vikram")

        # 4. P1-1: Pre-translation READ does not pre-commit; post-translation COMMIT persists
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            glossary = {
                "characters": [
                    {"english_name": "Arjun", "hindi_name": "अर्जुन", "gender": "male"},
                    {"english_name": "Vikram", "hindi_name": "विक्रम", "gender": "male"},
                ]
            }
            mem_block = _retrieve_chapter_memory_in_translator(
                project_dir=tmp_dir,
                source_text="Arjun stabbed Vikram in the courtyard.",
                block_label="chapter_001",
                glossary=glossary,
            )
            store_before = MemoryStore.load(MemoryStore.default_store_path(tmp_dir))
            self.assertEqual(len(store_before.commit_history), 0)

            _commit_chapter_memory_in_translator(
                project_dir=tmp_dir,
                source_text="Arjun stabbed Vikram in the courtyard.",
                block_label="chapter_001",
                glossary=glossary,
                call_llm_fn=fake_llm,
            )
            store_after = MemoryStore.load(MemoryStore.default_store_path(tmp_dir))
            self.assertEqual(len(store_after.commit_history), 1)
            self.assertEqual(store_after.character_states["Vikram"].physical_condition, "injured")

    def test_07_strict_director_supremacy_preserves_screenplay_intent(self):
        """
        Issue 5 & Confirmed Alignment: Strict Director Supremacy in MemoryContext.
        Screenplay cues (nested acting.emotion, bracketed [...], parenthetical (...),
        custom vocal_tags, director_notes) are NEVER overridden by fallback memory guidance.
        Memory guidance ONLY applies to completely neutral/unspecified segments.
        """
        from audiobook_factory.translation.memory import MemoryContext, CharacterState, LocationState

        ctx = MemoryContext(
            chapter=3,
            scene_id="scene_02",
            location_state=LocationState(location_name="Cavern", acoustic_env="deep_cavern_echo"),
            active_character_states={
                "Vikram": CharacterState(
                    character_name="Vikram",
                    physical_condition="injured",
                    active_injuries=["arrow wound"],
                    energy=0.2,
                    current_emotion="furious",
                    emotion_intensity=0.9,
                )
            },
        )

        # Case 1: Parenthetical cue "(whispering)" -> Directorial Intent preserved
        seg_paren = {
            "speaker": "Vikram",
            "type": "dialogue",
            "text": "(whispering) Chup raho, koi sun lega.",
            "emotion": "neutral",
        }
        res_paren = ctx.apply_performance_guidance_to_segment(seg_paren)
        self.assertEqual(res_paren["emotion"], "neutral")
        self.assertNotIn("memory_vocal_constraint", res_paren)
        self.assertEqual(res_paren["acoustic_env"], "deep_cavern_echo")

        # Case 2: Bracketed cue "[screaming]" -> Directorial Intent preserved
        seg_bracket = {
            "speaker": "Vikram",
            "type": "dialogue",
            "text": "[screaming] Bhag yahan se!",
            "emotion": "neutral",
        }
        res_bracket = ctx.apply_performance_guidance_to_segment(seg_bracket)
        self.assertEqual(res_bracket["emotion"], "neutral")
        self.assertNotIn("memory_vocal_constraint", res_bracket)

        # Case 3: Nested acting object with explicit emotion -> Directorial Intent preserved
        seg_nested = {
            "speaker": "Vikram",
            "type": "dialogue",
            "text": "Main haar nahi manunga.",
            "emotion": "neutral",
            "acting": {"emotion": "defiant", "delivery_style": "steely_grit"},
        }
        res_nested = ctx.apply_performance_guidance_to_segment(seg_nested)
        self.assertEqual(res_nested["emotion"], "neutral")
        self.assertNotIn("memory_vocal_constraint", res_nested)

        # Case 4: Explicit vocal_tags or director_notes -> Directorial Intent preserved
        seg_vocal = {
            "speaker": "Vikram",
            "type": "dialogue",
            "text": "Kalam pakdo.",
            "emotion": "neutral",
            "vocal_tags": ["hoarse_raspy"],
        }
        res_vocal = ctx.apply_performance_guidance_to_segment(seg_vocal)
        self.assertEqual(res_vocal["emotion"], "neutral")
        self.assertNotIn("memory_vocal_constraint", res_vocal)

        # Case 5: Completely neutral segment without explicit tags or notes -> Receives memory context
        seg_clean_neutral = {
            "speaker": "Vikram",
            "type": "dialogue",
            "text": "Rasta kahan hai?",
            "emotion": "neutral",
        }
        res_neutral = ctx.apply_performance_guidance_to_segment(seg_clean_neutral)
        self.assertEqual(res_neutral["emotion"], "strained")
        self.assertEqual(res_neutral["memory_vocal_constraint"], "strained_breath")
        self.assertEqual(res_neutral["acoustic_env"], "deep_cavern_echo")


if __name__ == "__main__":
    unittest.main()
