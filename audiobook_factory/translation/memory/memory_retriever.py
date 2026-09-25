#!/usr/bin/env python3
"""
Audiobook Factory - Selective 7-Tier + Narrative Salience Memory Retriever (Memory 2.0).
Retrieves ONLY scene-relevant characters, relationships, epistemic constraints,
location/object states, recent events, high-salience dramatic memories, and open threads.
Prevents prompt bloating by excluding unrelated entities.
"""

from __future__ import annotations
from typing import List, Optional, Set, Dict, Any

from audiobook_factory.translation.book_bible import BookBible
from .events import StoryEvent, SceneChangeDetector, TemporalMode
from .character_memory import CharacterState, CharacterKnowledgeEngine
from .world_memory import ObjectState, NarrativeThreadState
from .memory_store import MemoryStore
from .memory_context import MemoryContext


class _DualRetrieveDescriptor:
    """Allows retrieve_for_scene to be called either as MemoryRetriever.retrieve_for_scene(store, ...)
    or as MemoryRetriever(store).retrieve_for_scene(...)."""

    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner=None):
        cls = owner or type(instance)
        if instance is None:
            def _cls_call(*args, **kwargs):
                return self.func(cls, *args, **kwargs)
            return _cls_call

        def _inst_call(*args, **kwargs):
            if args and isinstance(args[0], MemoryStore):
                return self.func(cls, *args, **kwargs)
            eff_store = kwargs.pop("store", None) or instance.store
            if "book_bible" not in kwargs and instance.book_bible is not None:
                kwargs["book_bible"] = instance.book_bible
            return self.func(cls, eff_store, *args, **kwargs)

        return _inst_call


class MemoryRetriever:
    """
    Selective 7-tier + Narrative Salience retrieval engine.
    Supports both classmethod invocation and instance initialization `MemoryRetriever(store, book_bible)`.
    """

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        book_bible: Optional[BookBible] = None,
    ) -> None:
        self.store = store
        self.book_bible = book_bible

    @classmethod
    def infer_active_entities(
        cls,
        scene_text: str,
        store: MemoryStore,
        book_bible: Optional[BookBible] = None,
        explicit_characters: Optional[List[str]] = None,
        explicit_location: Optional[str] = None,
    ) -> tuple[List[str], str]:
        """
        Determines the canonical active characters and location for a scene
        using explicit scene plan metadata and deterministic text matching.
        """
        active_chars: List[str] = []
        seen_lower: Set[str] = set()

        def _add_char(name: str) -> None:
            if not name or name.lower() in ("narrator", "unknown", "unspecified"):
                return
            canon = store.resolve_canonical_character_name(name, book_bible)
            if canon.lower() not in seen_lower:
                seen_lower.add(canon.lower())
                active_chars.append(canon)

        for c in explicit_characters or []:
            _add_char(c)

        text_lower = (scene_text or "").lower()
        if text_lower and not explicit_characters:
            if book_bible is not None:
                char_iter = (
                    book_bible.characters.values()
                    if isinstance(book_bible.characters, dict)
                    else book_bible.characters
                )
                for entry in char_iter:
                    names_to_check = [entry.canonical_name] + list(entry.aliases)
                    if entry.hindi_name:
                        names_to_check.append(entry.hindi_name)
                    if any(n and len(n) >= 2 and n.lower() in text_lower for n in names_to_check):
                        _add_char(entry.canonical_name)

            for c_name in store.character_states:
                if len(c_name) >= 2 and c_name.lower() in text_lower:
                    _add_char(c_name)

        resolved_location = explicit_location or "Unspecified"
        if resolved_location == "Unspecified" and text_lower:
            if book_bible is not None:
                for loc_key, loc_hi in book_bible.locations.items():
                    p_names = [loc_key, loc_hi]
                    if any(p and len(p) >= 3 and p.lower() in text_lower for p in p_names):
                        resolved_location = loc_key
                        break
            if resolved_location == "Unspecified":
                for loc_name in store.world_state.location_states:
                    if len(loc_name) >= 3 and loc_name.lower() in text_lower:
                        resolved_location = loc_name
                        break

        if resolved_location != "Unspecified" and book_bible is not None:
            p_name = book_bible.find_place(resolved_location)
            if p_name is not None:
                resolved_location = p_name

        return active_chars, resolved_location

    @_DualRetrieveDescriptor
    def retrieve_for_scene(
        cls,
        store: MemoryStore,
        book_bible: Optional[BookBible] = None,
        chapter: int = 1,
        scene_id: str = "scene_01",
        active_characters: Optional[List[str]] = None,
        location: Optional[str] = None,
        active_location: Optional[str] = None,
        scene_text: str = "",
        max_recent_events: int = 5,
        max_salient_events: int = 4,
        max_token_budget: int = 800,
    ) -> MemoryContext:
        """
        Constructs a strictly scoped MemoryContext for the target scene across all 7 tiers
        plus the Narrative Salience (Dramatic Memory) layer.
        """
        if book_bible is not None:
            store.seed_from_book_bible(book_bible)

        eff_location = location or active_location
        resolved_chars, resolved_loc = cls.infer_active_entities(
            scene_text=scene_text,
            store=store,
            book_bible=book_bible,
            explicit_characters=active_characters,
            explicit_location=eff_location,
        )
        active_set_lower: Set[str] = {c.lower() for c in resolved_chars}
        text_lower = (scene_text or "").lower()

        temporal_mode, _, _ = SceneChangeDetector.detect_temporal_mode(scene_text) if scene_text else (TemporalMode.PRESENT, None, None)

        # Tier 1: Canonical identities & relevant world rules
        canon_identities: List[Dict[str, Any]] = []
        relevant_rules: List[str] = []
        if book_bible is not None:
            for c_name in resolved_chars:
                c_entry = book_bible.find_character(c_name)
                lang_prof = book_bible.find_language_profile(c_name)
                if c_entry is not None:
                    canon_identities.append({
                        "canonical_name": c_entry.canonical_name,
                        "gender": c_entry.gender,
                        "role": c_entry.canonical_role,
                        "default_emotion": c_entry.default_emotion,
                        "register": getattr(lang_prof, "vocabulary_register", "literary") if lang_prof else "literary",
                        "default_pronoun": getattr(lang_prof, "honorific_preference", "tum") if lang_prof else "tum",
                    })

            for rule in book_bible.world_rules:
                r_str = f"{rule.rule_name}: {rule.description}"
                if not text_lower or any(tok in text_lower for tok in rule.rule_name.lower().split() if len(tok) >= 3):
                    relevant_rules.append(r_str)
            if not relevant_rules and book_bible.world_rules:
                relevant_rules = [f"{r.rule_name}: {r.description}" for r in book_bible.world_rules[:3]]

        for d_rule in store.world_state.discovered_rules:
            if d_rule not in relevant_rules:
                relevant_rules.append(d_rule)

        # Tier 2: Dynamic Character States (ONLY for active characters)
        active_char_states: Dict[str, CharacterState] = {}
        for c_name in resolved_chars:
            st = store.character_states.get(c_name)
            if st is not None:
                active_char_states[c_name] = st.model_copy(deep=True)
            else:
                active_char_states[c_name] = CharacterState(character_name=c_name)

        # Tier 3: Active Relationships (ONLY between active characters)
        active_rels = []
        for rel in store.relationships.values():
            if rel.speaker.lower() in active_set_lower and rel.target.lower() in active_set_lower:
                active_rels.append(rel.model_copy(deep=True))

        # Tier 4: Epistemic Isolation Matrix (for active characters)
        epistemic_matrix = CharacterKnowledgeEngine.build_epistemic_constraints_for_scene(
            active_characters=resolved_chars,
            facts_registry=store.facts_registry,
            character_states=store.character_states,
        )

        # Tier 5: Active Location State & Relevant Objects
        loc_state = None
        if resolved_loc and resolved_loc != "Unspecified":
            existing_loc = store.world_state.location_states.get(resolved_loc)
            if existing_loc is not None:
                loc_state = existing_loc.model_copy(deep=True)

        relevant_objects: List[ObjectState] = []
        for obj in store.world_state.object_states.values():
            owner_match = bool(obj.current_owner and obj.current_owner.lower() in active_set_lower)
            loc_match = bool(
                resolved_loc != "Unspecified"
                and obj.current_location
                and obj.current_location.lower() == resolved_loc.lower()
            )
            text_match = bool(text_lower and len(obj.object_name) >= 3 and obj.object_name.lower() in text_lower)
            if owner_match or loc_match or text_match:
                relevant_objects.append(obj.model_copy(deep=True))

        # Tier 6: Recent Relevant Events + Narrative Salience (Dramatic Memory) Layer
        all_events = list(store.events.values())
        relevant_all: List[StoryEvent] = []
        for ev in all_events:
            part_overlap = any(p.lower() in active_set_lower for p in ev.participants)
            loc_overlap = (
                resolved_loc != "Unspecified"
                and ev.location
                and ev.location.lower() == resolved_loc.lower()
            )
            if part_overlap or loc_overlap:
                relevant_all.append(ev)

        # Recent events: latest N by commit order / chapter
        recent_slice = relevant_all[-max_recent_events:] if relevant_all else []
        recent_ids = {e.event_id for e in recent_slice}

        # Salient events: past high-salience unresolved events (turning points, betrayals, oaths, deaths, traumas)
        # that occurred earlier and are NOT already in recent_slice
        salient_candidates: List[tuple[float, StoryEvent]] = []
        for ev in relevant_all:
            if ev.event_id in recent_ids:
                continue
            if ev.salience_score >= 0.65 and not ev.is_resolved:
                overlap_count = sum(1 for p in ev.participants if p.lower() in active_set_lower)
                rank_score = ev.salience_score + (0.10 * overlap_count)
                salient_candidates.append((rank_score, ev))

        salient_candidates.sort(key=lambda pair: pair[0], reverse=True)
        salient_slice = [pair[1] for pair in salient_candidates[:max_salient_events]]

        # Tier 7: Unresolved Narrative Threads involving active characters or scene text
        open_threads: List[NarrativeThreadState] = []
        for th in store.world_state.get_open_threads():
            part_match = any(p.lower() in active_set_lower for p in th.participants)
            text_match = bool(text_lower and any(tok in text_lower for tok in th.summary.lower().split() if len(tok) >= 4))
            if part_match or text_match or not active_set_lower:
                open_threads.append(th.model_copy(deep=True))

        ctx = MemoryContext(
            chapter=chapter,
            scene_id=scene_id,
            location_name=resolved_loc,
            temporal_mode=temporal_mode,
            canon_identities=canon_identities,
            relevant_world_rules=relevant_rules,
            active_character_states=active_char_states,
            active_relationships=active_rels,
            epistemic_constraints=epistemic_matrix,
            location_state=loc_state,
            relevant_objects=relevant_objects,
            recent_events=recent_slice,
            salient_events=salient_slice,
            unresolved_threads=open_threads,
        )
        return ctx.enforce_token_budget(max_token_budget)
