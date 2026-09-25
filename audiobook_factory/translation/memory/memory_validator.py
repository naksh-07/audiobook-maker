#!/usr/bin/env python3
"""
Audiobook Factory - Memory Validator & Contradiction Engine (Memory 2.0).
Enforces all 7 narrative consistency guardrails before state deltas are committed:
1. canon_contradiction
2. timeline_contradiction (aware of TemporalMode: PRESENT vs FLASHBACK/MEMORY_DREAM/HISTORICAL_NARRATION/NON_LINEAR)
3. knowledge_violation
4. relationship_jump
5. physical_impossibility
6. dead_character_violation
7. world_rule_violation
"""

from __future__ import annotations
from enum import Enum
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field

from audiobook_factory.translation.book_bible import BookBible, FlaggedConflict
from audiobook_factory.translation.relationship_state import DynamicRelationshipState
from .events import StoryEvent, StoryEventType, TemporalMode
from .memory_delta import StateDelta, DeltaDomain, StateMutability
from .character_memory import (
    CharacterState,
    KnowledgeFact,
    KnowledgeStatus,
    CharacterKnowledgeEngine,
)
from .world_memory import WorldState


class ValidationOutcome(str, Enum):
    """Result classification for memory validation."""
    PASS = "PASS"
    WARN = "WARN"
    CONFLICT = "CONFLICT"


class MemoryValidationReport(BaseModel):
    """Detailed validation report returned before committing a scene's deltas."""
    outcome: ValidationOutcome = ValidationOutcome.PASS
    accepted_deltas: List[StateDelta] = Field(default_factory=list)
    rejected_deltas: List[StateDelta] = Field(default_factory=list)
    rejected_event_ids: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    flagged_conflicts: List[FlaggedConflict] = Field(default_factory=list)
    repair_instructions: List[str] = Field(default_factory=list)


class MemoryValidator:
    """
    Validates proposed StateDeltas and StoryEvents against Hard Canon (BookBible)
    and Dynamic Memory (CharacterState, DynamicRelationshipState, KnowledgeFact, WorldState).
    """

    HARD_CANON_PROTECTED_FIELDS: Set[str] = {
        "canonical_name",
        "immutable_name",
        "gender",
        "canonical_role",
        "voice_id",
        "locked_pronoun",
        "locked_register",
    }

    @classmethod
    def _allows_resurrection(cls, book_bible: Optional[BookBible]) -> bool:
        """Checks whether the BookBible explicitly defines a resurrection/revival world rule."""
        if book_bible is None:
            return False
        for rule in book_bible.world_rules:
            combined = f"{rule.rule_name} {rule.description} {rule.category}".lower()
            if any(k in combined for k in ("resurrection", "revival", "undead", "reincarnation", "immortal", "necromancy")):
                return True
        return False

    @classmethod
    def _violates_world_rule(
        cls,
        delta: StateDelta,
        book_bible: Optional[BookBible],
    ) -> Optional[str]:
        """Checks if a delta explicitly or semantically violates an immutable BookBible WorldRule."""
        if delta.metadata.get("violates_world_rule"):
            return str(delta.metadata["violates_world_rule"])

        if book_bible is None or not book_bible.world_rules:
            return None

        candidate_text = f"{delta.field_name} {delta.new_value} {delta.rationale}".lower()
        for rule in book_bible.world_rules:
            rule_desc = rule.description.lower()
            rule_name = rule.rule_name.lower()
            # Check explicit negation patterns against established rules
            if "cannot " in rule_desc or "impossible" in rule_desc or "forbidden" in rule_desc or "never " in rule_desc:
                # Extract key tokens from rule name and description
                if rule_name and rule_name in candidate_text:
                    if any(trigger in candidate_text for trigger in ("violate", "break", "bypass", "ignore", "override")):
                        return f"Violates immutable WorldRule '{rule.rule_name}': {rule.description}"
                # Check if rule forbids magic/action that delta claims
                if "cannot use magic" in rule_desc and "uses magic" in candidate_text:
                    return f"Violates immutable WorldRule '{rule.rule_name}': {rule.description}"
                if "no resurrection" in rule_desc and delta.field_name == "is_alive" and delta.new_value is True:
                    return f"Violates immutable WorldRule '{rule.rule_name}': {rule.description}"
        return None

    @classmethod
    def validate_deltas(
        cls,
        deltas: List[StateDelta],
        book_bible: Optional[BookBible],
        character_states: Dict[str, CharacterState],
        relationships: Dict[str, DynamicRelationshipState],
        facts_registry: Dict[str, KnowledgeFact],
        world_state: WorldState,
        events_by_id: Optional[Dict[str, StoryEvent]] = None,
    ) -> MemoryValidationReport:
        """
        Validates a batch of proposed StateDeltas for a scene.
        Rejects any delta that triggers a hard contradiction, logs a FlaggedConflict,
        and generates actionable repair instructions.
        """
        report = MemoryValidationReport()
        events_map = events_by_id or {}

        # Track locations assigned within the same scene in PRESENT mode to catch simultaneous bi-location
        scene_present_locations: Dict[tuple, str] = {}

        for delta in deltas:
            conflict_found = False
            source_event = events_map.get(delta.source_event_id) if delta.source_event_id else None
            effective_mode = source_event.temporal_mode if source_event else delta.temporal_mode

            def _record_conflict(conflict_type: str, canonical_val: str, candidate_val: str, repair: str) -> None:
                nonlocal conflict_found
                conflict_found = True
                fc = FlaggedConflict(
                    entity_name=delta.target_entity,
                    conflict_type=conflict_type,
                    chapter=delta.chapter,
                    scene_id=delta.scene,
                    event_id=delta.source_event_id,
                    severity="CONFLICT",
                    existing_canonical=canonical_val,
                    candidate_conflict=candidate_val,
                    candidate_data=delta.model_dump(),
                    resolution_notes=repair,
                )
                report.flagged_conflicts.append(fc)
                report.rejected_deltas.append(delta)
                report.repair_instructions.append(repair)
                if book_bible is not None:
                    book_bible.flagged_conflicts.append(fc)

            # 1. CANON CONTRADICTION CHECK
            if delta.mutability == StateMutability.HARD_CANON or delta.field_name in cls.HARD_CANON_PROTECTED_FIELDS:
                _record_conflict(
                    conflict_type="canon_contradiction",
                    canonical_val=f"Protected hard-canon attribute '{delta.field_name}' on '{delta.target_entity}'",
                    candidate_val=f"Attempted mutation to '{delta.new_value}'",
                    repair=f"Do not mutate hard-canon field '{delta.field_name}' for '{delta.target_entity}'. Keep canonical BookBible identity.",
                )
                continue

            if book_bible is not None and delta.domain == DeltaDomain.CHARACTER:
                canon_char = book_bible.find_character(delta.target_entity)
                if canon_char is not None and canon_char.locked and delta.field_name in ("voice_id", "gender", "canonical_role"):
                    _record_conflict(
                        conflict_type="canon_contradiction",
                        canonical_val=f"Locked BookBible character '{canon_char.canonical_name}' ({delta.field_name})",
                        candidate_val=str(delta.new_value),
                        repair=f"Character '{canon_char.canonical_name}' is locked in BookBible; reject override of '{delta.field_name}'.",
                    )
                    continue

            # 2. WORLD RULE VIOLATION CHECK
            rule_violation = cls._violates_world_rule(delta, book_bible)
            if rule_violation:
                _record_conflict(
                    conflict_type="world_rule_violation",
                    canonical_val=rule_violation,
                    candidate_val=f"{delta.target_entity}.{delta.field_name} = {delta.new_value}",
                    repair=f"Remove or rewrite scene mutation for '{delta.target_entity}' because it violates established world law: {rule_violation}",
                )
                continue

            # 3. TIMELINE CONTRADICTION CHECK (TemporalMode-aware)
            if effective_mode == TemporalMode.PRESENT:
                # If an event explicitly marks chronological_epoch < 0 while claiming PRESENT mode, flag timeline conflict
                if source_event is not None and source_event.chronological_epoch is not None and source_event.chronological_epoch < 0:
                    _record_conflict(
                        conflict_type="timeline_contradiction",
                        canonical_val="TemporalMode.PRESENT requires non-negative story chronology",
                        candidate_val=f"chronological_epoch={source_event.chronological_epoch} in PRESENT mode",
                        repair="Mark past-epoch memories or flashbacks with TemporalMode.FLASHBACK or HISTORICAL_NARRATION instead of PRESENT.",
                    )
                    continue

                # Check monotonic chapter progression against last PRESENT timeline point
                present_points = [pt for pt in world_state.timeline if pt.temporal_mode == TemporalMode.PRESENT]
                if present_points and delta.chapter > 0:
                    max_present_chapter = max(pt.chapter for pt in present_points)
                    if delta.chapter < max_present_chapter and not delta.metadata.get("allow_retroactive_commit"):
                        _record_conflict(
                            conflict_type="timeline_contradiction",
                            canonical_val=f"Current PRESENT story timeline is at chapter {max_present_chapter}",
                            candidate_val=f"Attempted PRESENT state mutation at earlier chapter {delta.chapter}",
                            repair=f"Scene at chapter {delta.chapter} occurs before current PRESENT chapter {max_present_chapter}; set TemporalMode.FLASHBACK or NON_LINEAR.",
                        )
                        continue

            # 4. DEAD CHARACTER VIOLATION CHECK
            if delta.domain == DeltaDomain.CHARACTER:
                existing_char = character_states.get(delta.target_entity)
                if existing_char is not None and not existing_char.is_alive:
                    # In FLASHBACK, MEMORY_DREAM, or HISTORICAL_NARRATION, deceased characters can appear/speak
                    if effective_mode in (
                        TemporalMode.FLASHBACK,
                        TemporalMode.MEMORY_DREAM,
                        TemporalMode.HISTORICAL_NARRATION,
                    ):
                        report.warnings.append(
                            f"Deceased character '{delta.target_entity}' referenced in {effective_mode.value} mode (allowed)."
                        )
                    else:
                        # In PRESENT mode, a dead character cannot act, move, or recover unless resurrection is explicitly allowed
                        if delta.field_name == "is_alive" and delta.new_value is True:
                            resurrection_allowed = (
                                cls._allows_resurrection(book_bible)
                                or bool(delta.metadata.get("explicit_resurrection"))
                            )
                            is_ordinary_recovery = (
                                source_event is not None
                                and source_event.event_type == StoryEventType.CHARACTER_RECOVERED
                            )
                            if is_ordinary_recovery or not resurrection_allowed:
                                _record_conflict(
                                    conflict_type="dead_character_violation",
                                    canonical_val=f"Character '{delta.target_entity}' is deceased (is_alive=False)",
                                    candidate_val=f"Attempted revival via {source_event.event_type.value if source_event else 'delta'}",
                                    repair=f"Character '{delta.target_entity}' is dead and cannot be revived without an explicit resurrection WorldRule.",
                                )
                                continue
                        elif delta.field_name in (
                            "current_location",
                            "current_emotion",
                            "immediate_goal",
                            "physical_condition",
                            "active_injuries",
                            "energy",
                        ):
                            _record_conflict(
                                conflict_type="dead_character_violation",
                                canonical_val=f"Character '{delta.target_entity}' is deceased (is_alive=False)",
                                candidate_val=f"Attempted PRESENT-mode update to '{delta.field_name}' = '{delta.new_value}'",
                                repair=f"Deceased character '{delta.target_entity}' cannot act or change state in PRESENT chronology. Use FLASHBACK/MEMORY_DREAM if this is a memory.",
                            )
                            continue

            # 5. PHYSICAL IMPOSSIBILITY CHECK
            if delta.domain == DeltaDomain.CHARACTER and delta.field_name == "current_location" and effective_mode == TemporalMode.PRESENT:
                loc_key = (delta.target_entity, delta.chapter, delta.scene)
                new_loc = str(delta.new_value)
                prev_scene_loc = scene_present_locations.get(loc_key)
                if prev_scene_loc is not None and prev_scene_loc != new_loc and not delta.metadata.get("allow_intra_scene_travel"):
                    _record_conflict(
                        conflict_type="physical_impossibility",
                        canonical_val=f"Character '{delta.target_entity}' already placed at '{prev_scene_loc}' in scene '{delta.scene}'",
                        candidate_val=f"Simultaneous placement at '{new_loc}' in same scene '{delta.scene}'",
                        repair=f"Split scene '{delta.scene}' or mark travel explicitly; '{delta.target_entity}' cannot be in '{prev_scene_loc}' and '{new_loc}' simultaneously.",
                    )
                    continue
                scene_present_locations[loc_key] = new_loc

            if delta.domain == DeltaDomain.WORLD and delta.field_name == "object_owner" and effective_mode == TemporalMode.PRESENT:
                obj_name = delta.target_entity
                existing_obj = world_state.object_states.get(obj_name)
                claimed_prev_owner = delta.metadata.get("previous_owner")
                if (
                    existing_obj is not None
                    and existing_obj.current_owner
                    and claimed_prev_owner
                    and existing_obj.current_owner != claimed_prev_owner
                ):
                    _record_conflict(
                        conflict_type="physical_impossibility",
                        canonical_val=f"Object '{obj_name}' is currently owned by '{existing_obj.current_owner}'",
                        candidate_val=f"Transfer claims previous owner was '{claimed_prev_owner}' -> '{delta.new_value}'",
                        repair=f"Object '{obj_name}' cannot be transferred from '{claimed_prev_owner}' because it is held by '{existing_obj.current_owner}'.",
                    )
                    continue
                if existing_obj is not None and existing_obj.status == "destroyed" and delta.new_value is not None:
                    _record_conflict(
                        conflict_type="physical_impossibility",
                        canonical_val=f"Object '{obj_name}' is destroyed",
                        candidate_val=f"Attempted ownership transfer to '{delta.new_value}'",
                        repair=f"Destroyed object '{obj_name}' cannot be transferred to '{delta.new_value}'.",
                    )
                    continue

            # 6. RELATIONSHIP JUMP CHECK (Rule 12: Evidence-Backed Relationship Evolution)
            if delta.domain == DeltaDomain.RELATIONSHIP:
                if not delta.source_event_id:
                    _record_conflict(
                        conflict_type="relationship_jump",
                        canonical_val=f"Relationship '{delta.target_entity}' requires event provenance",
                        candidate_val=f"Silent mutation on '{delta.field_name}' without source_event_id",
                        repair=f"Attach a valid StoryEvent ID to relationship mutation on '{delta.target_entity}.{delta.field_name}'.",
                    )
                    continue

                # Check magnitude of jump
                jump_val = abs(float(delta.numeric_delta)) if delta.numeric_delta is not None else 0.0
                if jump_val == 0.0 and delta.new_value is not None and delta.old_value is not None:
                    try:
                        jump_val = abs(float(delta.new_value) - float(delta.old_value))
                    except (TypeError, ValueError):
                        jump_val = 0.0

                event_importance = source_event.importance if source_event is not None else int(delta.metadata.get("importance", 3))
                if jump_val > 2.0 and event_importance < 4:
                    _record_conflict(
                        conflict_type="relationship_jump",
                        canonical_val=f"Max single-scene relationship delta is <= 2 for standard events (importance={event_importance})",
                        candidate_val=f"Jump of {jump_val} on '{delta.target_entity}.{delta.field_name}'",
                        repair=f"Clamp relationship delta on '{delta.target_entity}.{delta.field_name}' to [-2, +2] or link a high-importance (importance >= 4) turning-point event.",
                    )
                    continue
                elif jump_val > 3.0:
                    _record_conflict(
                        conflict_type="relationship_jump",
                        canonical_val="Single-scene relationship jump cannot exceed 3 points even on major events",
                        candidate_val=f"Extreme jump of {jump_val} on '{delta.target_entity}.{delta.field_name}'",
                        repair=f"Bound single-scene relationship delta on '{delta.target_entity}.{delta.field_name}' to <= 3.",
                    )
                    continue

            # 7. KNOWLEDGE VIOLATION CHECK (Rule 13: Epistemic Isolation)
            # Check 7A: Actions across ANY domain requiring prior knowledge
            req_fact = delta.metadata.get("requires_knowledge")
            if req_fact:
                acting_char = delta.metadata.get("acted_upon_by") or (
                    delta.target_entity if delta.domain == DeltaDomain.CHARACTER else None
                )
                if acting_char:
                    status = CharacterKnowledgeEngine.get_character_knowledge_status(
                        acting_char, str(req_fact), facts_registry, character_states
                    )
                    if status != KnowledgeStatus.KNOWN:
                        _record_conflict(
                            conflict_type="knowledge_violation",
                            canonical_val=f"Fact '{req_fact}' is {status.value} to '{acting_char}'",
                            candidate_val=f"Character '{acting_char}' attempted action requiring unpossessed fact '{req_fact}'",
                            repair=f"Character '{acting_char}' cannot perform action requiring '{req_fact}' because their epistemic status is {status.value}.",
                        )
                        continue

            # Check 7B: Explicit Knowledge Domain deltas (Using / Transmitting vs Receiving)
            if delta.domain == DeltaDomain.KNOWLEDGE:
                payload = delta.new_value if isinstance(delta.new_value, dict) else {}
                fact_id = str(payload.get("fact_id") or delta.target_entity)

                # Transmitting / Revealing knowledge: Revealer MUST possess the knowledge (status == KNOWN)
                revealer = (
                    delta.metadata.get("revealed_by")
                    or delta.metadata.get("transmitted_by")
                    or payload.get("revealed_by")
                    or (
                        (
                            source_event.metadata.get("knower")
                            or source_event.metadata.get("revealer")
                            or source_event.metadata.get("revealed_by")
                            or source_event.metadata.get("speaker")
                            or (source_event.participants[0] if source_event.participants else None)
                        )
                        if (source_event and source_event.event_type == StoryEventType.SECRET_REVEALED)
                        else None
                    )
                )
                is_disproving = (
                    str(payload.get("status", "")).upper() in ("DISPROVEN", KnowledgeStatus.DISPROVEN.value)
                    or delta.field_name == "belief_disproven"
                    or (source_event and source_event.event_type == StoryEventType.FACT_DISPROVEN)
                )
                if revealer and not is_disproving:
                    r_status = CharacterKnowledgeEngine.get_character_knowledge_status(
                        str(revealer), fact_id, facts_registry, character_states
                    )
                    if r_status != KnowledgeStatus.KNOWN:
                        _record_conflict(
                            conflict_type="knowledge_violation",
                            canonical_val=f"Fact '{fact_id}' is {r_status.value} to revealer '{revealer}'",
                            candidate_val=f"Character '{revealer}' attempted to reveal or transmit unpossessed secret '{fact_id}'",
                            repair=f"Character '{revealer}' cannot reveal secret '{fact_id}' because they do not know it (prior status: {r_status.value}).",
                        )
                        continue

                # Using / Acting upon knowledge: Actor MUST possess the knowledge (status == KNOWN)
                if payload.get("acted_upon_by"):
                    actor = str(payload["acted_upon_by"])
                    a_status = CharacterKnowledgeEngine.get_character_knowledge_status(
                        actor, fact_id, facts_registry, character_states
                    )
                    if a_status != KnowledgeStatus.KNOWN:
                        _record_conflict(
                            conflict_type="knowledge_violation",
                            canonical_val=f"Fact '{fact_id}' is {a_status.value} to '{actor}'",
                            candidate_val=f"Character '{actor}' acted upon unlearned/unpossessed fact '{fact_id}'",
                            repair=f"Prevent '{actor}' from referencing or acting on '{fact_id}' until a valid KNOWLEDGE_LEARNED or SECRET_REVEALED event occurs.",
                        )
                        continue

                # Receiving knowledge: Characters in known_by are transitioning UNKNOWN -> KNOWN through valid event
                # (Receiving is explicitly allowed; no conflict is raised for learners)

            if not conflict_found:
                report.accepted_deltas.append(delta)

        # Strict Event Atomicity: If an event has any rejected delta, companion deltas
        # for that same event are purged to prevent partial/ghost event mutations.
        rejected_eids = {d.source_event_id for d in report.rejected_deltas if d.source_event_id}
        if rejected_eids:
            purged_accepted = []
            for d in report.accepted_deltas:
                if d.source_event_id in rejected_eids:
                    report.rejected_deltas.append(d)
                else:
                    purged_accepted.append(d)
            report.accepted_deltas = purged_accepted

        report.rejected_event_ids = sorted(rejected_eids)

        if report.flagged_conflicts:
            report.outcome = ValidationOutcome.CONFLICT
        elif report.warnings:
            report.outcome = ValidationOutcome.WARN
        else:
            report.outcome = ValidationOutcome.PASS

        return report
