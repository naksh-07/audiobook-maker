#!/usr/bin/env python3
"""
Audiobook Factory - Character State, Epistemic Knowledge Engine & Character Arc Memory (Memory 2.0).
Maintains strict separation between:
- CharacterProfile / BookEntity = WHO THE CHARACTER IS (Hard Canon)
- CharacterLanguageProfile = HOW THE CHARACTER SPEAKS (Linguistic Identity)
- CharacterState = WHAT IS CURRENTLY HAPPENING TO THE CHARACTER (Dynamic State)
- CharacterArcMemory = LONG-TERM NARRATIVE EVOLUTION (Goals, Fears, Turning Points)
- CharacterKnowledgeEngine = WHO KNOWS WHAT (Epistemic Isolation)
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class KnowledgeStatus(str, Enum):
    KNOWN = "KNOWN"
    SUSPECTED = "SUSPECTED"
    FALSE_BELIEF = "FALSE_BELIEF"
    UNKNOWN = "UNKNOWN"
    DISPROVEN = "DISPROVEN"


class KnowledgeFact(BaseModel):
    fact_id: str
    subject: str
    predicate: str
    value: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_event: str
    learned_at: str = "ch001_scene_001"
    known_by: List[str] = Field(default_factory=list)
    status: KnowledgeStatus = KnowledgeStatus.KNOWN
    character_statuses: Dict[str, KnowledgeStatus] = Field(default_factory=dict)

    def get_status_for_character(self, character_name: str) -> KnowledgeStatus:
        """Returns the epistemic status of this fact for a specific character."""
        if character_name in self.character_statuses:
            return self.character_statuses[character_name]
        c_clean = character_name.strip().lower()
        for k, v in self.character_statuses.items():
            if k.strip().lower() == c_clean:
                return v
        if character_name in self.known_by:
            return self.status
        for k in self.known_by:
            if k.strip().lower() == c_clean:
                return self.status
        return KnowledgeStatus.UNKNOWN


class CharacterArcMemory(BaseModel):
    primary_goal: str = ""
    secondary_goals: List[str] = Field(default_factory=list)
    core_fear: str = ""
    core_desire: str = ""
    current_arc_phase: str = "introduction"
    belief_state: List[str] = Field(default_factory=list)
    internal_conflict: str = ""
    unresolved_threads: List[str] = Field(default_factory=list)
    turning_points: List[str] = Field(default_factory=list)
    completed_arcs: List[str] = Field(default_factory=list)


class CharacterState(BaseModel):
    character_name: str
    is_alive: bool = True
    current_location: str = "Unspecified"
    current_emotion: str = "neutral"
    emotion_intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    physical_condition: str = "healthy"
    active_injuries: List[str] = Field(default_factory=list)
    energy: float = Field(default=0.8, ge=0.0, le=1.0)
    immediate_goal: str = ""
    current_beliefs: List[str] = Field(default_factory=list)
    known_facts: List[str] = Field(default_factory=list)
    suspected_facts: List[str] = Field(default_factory=list)
    false_beliefs: List[str] = Field(default_factory=list)
    recent_events: List[str] = Field(default_factory=list)
    arc_state: CharacterArcMemory = Field(default_factory=CharacterArcMemory)
    last_updated_chapter: int = 1
    last_updated_scene: str = "scene_001"


class CharacterKnowledgeEngine:
    """
    Manages character epistemic states and enforces strict knowledge isolation across scenes.
    """

    @staticmethod
    def register_or_update_fact(
        facts_registry: Dict[str, KnowledgeFact],
        character_states: Dict[str, CharacterState],
        fact_id: str,
        subject: str,
        predicate: str,
        value: str,
        source_event: str,
        learned_at: str,
        learners: List[str],
        status: KnowledgeStatus = KnowledgeStatus.KNOWN,
        confidence: float = 1.0,
    ) -> KnowledgeFact:
        existing = facts_registry.get(fact_id)
        if existing is None:
            fact = KnowledgeFact(
                fact_id=fact_id,
                subject=subject,
                predicate=predicate,
                value=value,
                confidence=confidence,
                source_event=source_event,
                learned_at=learned_at,
                known_by=[
                    c for c in dict.fromkeys(learners)
                    if status == KnowledgeStatus.KNOWN
                ],
                status=status,
                character_statuses={c: status for c in learners},
            )
            facts_registry[fact_id] = fact
        else:
            fact = existing
            fact.confidence = confidence
            fact.source_event = source_event
            fact.learned_at = learned_at
            for c in learners:
                fact.character_statuses[c] = status
                if status == KnowledgeStatus.KNOWN:
                    if c not in fact.known_by:
                        fact.known_by.append(c)
                else:
                    if c in fact.known_by:
                        fact.known_by.remove(c)
            if status == KnowledgeStatus.DISPROVEN and (not learners or not fact.known_by):
                fact.status = KnowledgeStatus.DISPROVEN

        # Synchronize character epistemic lists
        for c_name in learners:
            c_state = character_states.get(c_name)
            if c_state is None:
                c_state = CharacterState(character_name=c_name)
                character_states[c_name] = c_state
            CharacterKnowledgeEngine.sync_character_fact_lists(c_state, fact_id, status)

        return fact

    @staticmethod
    def sync_character_fact_lists(
        char_state: CharacterState,
        fact_id: str,
        status: KnowledgeStatus,
    ) -> None:
        for lst in (char_state.known_facts, char_state.suspected_facts, char_state.false_beliefs):
            if fact_id in lst:
                lst.remove(fact_id)

        if status == KnowledgeStatus.KNOWN:
            char_state.known_facts.append(fact_id)
        elif status == KnowledgeStatus.SUSPECTED:
            char_state.suspected_facts.append(fact_id)
        elif status == KnowledgeStatus.FALSE_BELIEF:
            char_state.false_beliefs.append(fact_id)

    @staticmethod
    def get_character_knowledge_status(
        character_name: str,
        fact_id: str,
        facts_registry: Dict[str, KnowledgeFact],
        character_states: Optional[Dict[str, CharacterState]] = None,
    ) -> KnowledgeStatus:
        """Returns the epistemic status (KNOWN, SUSPECTED, FALSE_BELIEF, UNKNOWN, DISPROVEN) of a fact for a character."""
        fact = facts_registry.get(fact_id)
        if fact is not None:
            return fact.get_status_for_character(character_name)
        if character_states and character_name in character_states:
            st = character_states[character_name]
            if fact_id in st.known_facts:
                return KnowledgeStatus.KNOWN
            if fact_id in st.suspected_facts:
                return KnowledgeStatus.SUSPECTED
            if fact_id in st.false_beliefs:
                return KnowledgeStatus.FALSE_BELIEF
        return KnowledgeStatus.UNKNOWN

    @staticmethod
    def build_epistemic_constraints_for_scene(
        active_characters: List[str],
        facts_registry: Dict[str, KnowledgeFact],
        character_states: Optional[Dict[str, CharacterState]] = None,
        max_facts_per_bucket: int = 8,
    ) -> Dict[str, Dict[str, List[str]]]:
        """
        Builds a per-character epistemic matrix mapping each active character to their
        KNOWN, SUSPECTED, FALSE_BELIEF, UNKNOWN, and DISPROVEN facts.
        Prevents omniscient knowledge leakage when Character A knows a secret that Character B does not,
        while prioritizing scene-relevant/recent facts so long-form 100-chapter novels remain bounded.
        """
        matrix: Dict[str, Dict[str, List[str]]] = {}
        for char in active_characters:
            matrix[char] = {
                "KNOWN": [],
                "SUSPECTED": [],
                "FALSE_BELIEF": [],
                "UNKNOWN": [],
                "DISPROVEN": [],
            }

        if not active_characters or not facts_registry:
            return matrix

        active_lower = {c.lower() for c in active_characters}
        all_facts = list(facts_registry.values())

        # Prioritize facts where:
        # (1) at least one active character knows/suspects it (asymmetric scene leakage risk),
        # (2) the fact's subject is an active character,
        # (3) most recently learned facts (reverse order).
        def _fact_priority(idx_and_fact: tuple[int, KnowledgeFact]) -> tuple[int, int, int]:
            idx, f = idx_and_fact
            known_by_active = int(
                any(
                    k.lower() in active_lower
                    for k in list(f.known_by) + list(f.character_statuses.keys())
                )
            )
            subj_is_active = int(f.subject.lower() in active_lower)
            return (known_by_active, subj_is_active, idx)

        ranked_facts = [
            pair[1]
            for pair in sorted(enumerate(all_facts), key=_fact_priority, reverse=True)
        ]

        for fact in ranked_facts:
            fact_desc = f"{fact.subject} ({fact.predicate}): {fact.value}"
            for char in active_characters:
                st = CharacterKnowledgeEngine.get_character_knowledge_status(
                    char, fact.fact_id, facts_registry, character_states
                )
                bucket = matrix[char][st.value]
                if len(bucket) < max_facts_per_bucket:
                    bucket.append(fact_desc)

        return matrix

