#!/usr/bin/env python3
"""
Audiobook Factory - Pure Deterministic State Transition Engine (Memory 2.0).
Applies validated StateDeltas and StoryEvents to CharacterState, DynamicRelationshipState,
KnowledgeFact registry, and WorldState.
Respects TemporalMode so flashbacks, dreams, and historical narrations enrich memory
and knowledge without corrupting present-chronology physical or spatial state.
"""

from __future__ import annotations
from typing import Dict, Any, List

from .events import StoryEvent, StoryEventType, TemporalMode
from .memory_delta import StateDelta, DeltaDomain
from .character_memory import (
    CharacterState,
    KnowledgeFact,
    KnowledgeStatus,
    CharacterKnowledgeEngine,
)
from .world_memory import (
    WorldState,
    NarrativeThreadState,
    TimelinePoint,
)
from audiobook_factory.translation.relationship_state import (
    DynamicRelationshipState,
    RelationshipStateEngine,
)


def apply_character_delta(
    character_states: Dict[str, CharacterState],
    world_state: WorldState,
    delta: StateDelta,
) -> CharacterState:
    """
    Applies a single validated CHARACTER domain delta deterministically.
    """
    char_name = delta.target_entity
    state = character_states.get(char_name)
    if state is None:
        state = CharacterState(character_name=char_name)
        character_states[char_name] = state

    is_present = delta.temporal_mode == TemporalMode.PRESENT
    field = delta.field_name
    op = delta.operation
    val = delta.new_value

    if delta.source_event_id and delta.source_event_id not in state.recent_events:
        state.recent_events.append(delta.source_event_id)
        if len(state.recent_events) > 15:
            state.recent_events = state.recent_events[-15:]

    # In non-present modes (FLASHBACK, MEMORY_DREAM, HISTORICAL_NARRATION), do not overwrite
    # present physical_condition, is_alive, or current_location; only allow arc/belief/turning_point updates.
    if not is_present and field in (
        "current_location",
        "physical_condition",
        "active_injuries",
        "is_alive",
        "energy",
        "current_emotion",
        "emotion_intensity",
    ):
        if delta.rationale and delta.rationale not in state.arc_state.turning_points:
            state.arc_state.turning_points.append(f"[{delta.temporal_mode.value}] {delta.rationale}")
        return state

    if field == "current_location" and val:
        old_loc = state.current_location
        new_loc = str(val)
        state.current_location = new_loc
        if old_loc and old_loc in world_state.location_states:
            pres = world_state.location_states[old_loc].present_characters
            if char_name in pres:
                pres.remove(char_name)
        loc_obj = world_state.get_or_create_location(new_loc)
        if char_name not in loc_obj.present_characters:
            loc_obj.present_characters.append(char_name)
        if delta.source_event_id and delta.source_event_id not in loc_obj.provenance_events:
            loc_obj.provenance_events.append(delta.source_event_id)

    elif field == "current_emotion" and val is not None:
        state.current_emotion = str(val)

    elif field == "emotion_intensity":
        if op == "adjust" and delta.numeric_delta is not None:
            state.emotion_intensity = round(max(0.0, min(1.0, state.emotion_intensity + float(delta.numeric_delta))), 2)
        elif val is not None:
            state.emotion_intensity = round(max(0.0, min(1.0, float(val))), 2)

    elif field == "physical_condition" and val is not None:
        state.physical_condition = str(val)
        if state.physical_condition == "healthy":
            state.active_injuries = []

    elif field == "active_injuries":
        if op == "set" and isinstance(val, list):
            state.active_injuries = [str(x) for x in val]
        elif op == "add" and val:
            inj_str = str(val)
            if inj_str not in state.active_injuries:
                state.active_injuries.append(inj_str)
            if state.physical_condition == "healthy":
                state.physical_condition = "injured"
        elif op == "remove" and val:
            inj_str = str(val)
            if inj_str in state.active_injuries:
                state.active_injuries.remove(inj_str)
            if not state.active_injuries and state.physical_condition == "injured":
                state.physical_condition = "healthy"

    elif field == "energy":
        if op == "adjust" and delta.numeric_delta is not None:
            state.energy = round(max(0.0, min(1.0, state.energy + float(delta.numeric_delta))), 2)
        elif val is not None:
            state.energy = round(max(0.0, min(1.0, float(val))), 2)

    elif field == "is_alive" and val is not None:
        state.is_alive = bool(val)
        if not state.is_alive:
            state.physical_condition = "deceased"
            state.energy = 0.0

    elif field in ("immediate_goal", "goal") and val is not None:
        state.immediate_goal = str(val)
        if not state.arc_state.primary_goal:
            state.arc_state.primary_goal = str(val)
        elif str(val) != state.arc_state.primary_goal and str(val) not in state.arc_state.secondary_goals:
            state.arc_state.secondary_goals.append(str(val))

    elif field in ("current_beliefs", "belief"):
        if op == "set" and isinstance(val, list):
            state.current_beliefs = [str(x) for x in val]
            state.arc_state.belief_state = list(state.current_beliefs)
        elif op == "add" and val:
            b_str = str(val)
            if b_str not in state.current_beliefs:
                state.current_beliefs.append(b_str)
            if b_str not in state.arc_state.belief_state:
                state.arc_state.belief_state.append(b_str)
        elif op == "remove" and val:
            b_str = str(val)
            if b_str in state.current_beliefs:
                state.current_beliefs.remove(b_str)

    elif field == "arc_phase" and val is not None:
        old_phase = state.arc_state.current_arc_phase
        new_phase = str(val)
        if old_phase and old_phase != new_phase and old_phase not in state.arc_state.completed_arcs:
            state.arc_state.completed_arcs.append(old_phase)
        state.arc_state.current_arc_phase = new_phase

    elif field == "turning_point" and val:
        tp_str = str(val)
        if tp_str not in state.arc_state.turning_points:
            state.arc_state.turning_points.append(tp_str)

    elif field == "core_fear" and val is not None:
        state.arc_state.core_fear = str(val)

    elif field == "core_desire" and val is not None:
        state.arc_state.core_desire = str(val)

    elif field == "internal_conflict" and val is not None:
        state.arc_state.internal_conflict = str(val)

    elif field == "unresolved_threads":
        if op == "add" and val:
            if str(val) not in state.arc_state.unresolved_threads:
                state.arc_state.unresolved_threads.append(str(val))
        elif op == "remove" and val:
            if str(val) in state.arc_state.unresolved_threads:
                state.arc_state.unresolved_threads.remove(str(val))

    state.last_updated_chapter = delta.chapter
    state.last_updated_scene = delta.scene
    return state


def apply_relationship_delta(
    relationships: Dict[str, DynamicRelationshipState],
    delta: StateDelta,
) -> DynamicRelationshipState:
    """
    Applies a validated RELATIONSHIP domain delta via RelationshipStateEngine.
    """
    rel_key = delta.target_entity
    meta = delta.metadata or {}
    if "->" in rel_key:
        sp, tgt = [x.strip() for x in rel_key.split("->", 1)]
    else:
        sp = meta.get("speaker", rel_key)
        tgt = meta.get("target", "Unknown")
        rel_key = f"{sp}->{tgt}"

    existing = relationships.get(rel_key)
    if existing is None:
        existing = DynamicRelationshipState(speaker=sp, target=tgt)

    dim = delta.field_name
    if delta.operation == "adjust" and delta.numeric_delta is not None:
        step = int(round(delta.numeric_delta))
    elif delta.new_value is not None and hasattr(existing, dim):
        step = int(delta.new_value) - int(getattr(existing, dim))
    else:
        step = 0

    updated = RelationshipStateEngine.apply_relationship_mutation(
        rel=existing,
        deltas={dim: step},
        event_id=delta.source_event_id,
        chapter=delta.chapter,
        scene=delta.scene,
        notes=delta.rationale,
    )
    relationships[rel_key] = updated
    return updated


def apply_knowledge_delta(
    facts_registry: Dict[str, KnowledgeFact],
    character_states: Dict[str, CharacterState],
    delta: StateDelta,
) -> KnowledgeFact:
    """
    Applies a validated KNOWLEDGE domain delta via CharacterKnowledgeEngine.
    """
    payload = delta.new_value if isinstance(delta.new_value, dict) else {}
    fact_id = payload.get("fact_id") or delta.target_entity
    raw_status = str(payload.get("status", "KNOWN")).upper()
    status = KnowledgeStatus(raw_status) if raw_status in KnowledgeStatus.__members__ else KnowledgeStatus.KNOWN
    learners = [str(c) for c in payload.get("known_by", []) if c]

    return CharacterKnowledgeEngine.register_or_update_fact(
        facts_registry=facts_registry,
        character_states=character_states,
        fact_id=fact_id,
        subject=str(payload.get("subject", "world")),
        predicate=str(payload.get("predicate", "fact")),
        value=str(payload.get("value", delta.rationale)),
        source_event=delta.source_event_id,
        learned_at=str(payload.get("learned_at") or f"ch{delta.chapter:03d}_{delta.scene}"),
        learners=learners,
        status=status,
        confidence=float(payload.get("confidence", 1.0)),
    )


def apply_world_or_narrative_delta(
    world_state: WorldState,
    character_states: Dict[str, CharacterState],
    delta: StateDelta,
) -> None:
    """
    Applies a validated WORLD or NARRATIVE domain delta to WorldState.
    """
    is_present = delta.temporal_mode == TemporalMode.PRESENT
    field = delta.field_name
    target = delta.target_entity
    val = delta.new_value
    meta = delta.metadata or {}

    if delta.domain == DeltaDomain.WORLD:
        if field == "object_owner":
            if not is_present:
                return
            obj = world_state.get_or_create_object(target)
            obj.current_owner = str(val) if val is not None else None
            if meta.get("location") and meta["location"] != "Unspecified":
                obj.current_location = str(meta["location"])
            elif obj.current_owner and obj.current_owner in character_states:
                char_loc = character_states[obj.current_owner].current_location
                if char_loc and char_loc != "Unspecified":
                    obj.current_location = char_loc
            obj.status = "lost" if obj.current_owner is None and meta.get("status") == "lost" else ("owned" if obj.current_owner else "present")
            if delta.source_event_id and delta.source_event_id not in obj.provenance_events:
                obj.provenance_events.append(delta.source_event_id)
            obj.last_updated_chapter = delta.chapter
            obj.last_updated_scene = delta.scene

        elif field == "object_location":
            if not is_present:
                return
            obj = world_state.get_or_create_object(target)
            if val:
                obj.current_location = str(val)
            if delta.source_event_id and delta.source_event_id not in obj.provenance_events:
                obj.provenance_events.append(delta.source_event_id)
            obj.last_updated_chapter = delta.chapter
            obj.last_updated_scene = delta.scene

        elif field == "location_state":
            if not is_present:
                return
            loc = world_state.get_or_create_location(target)
            if isinstance(val, dict):
                if val.get("condition"):
                    loc.condition = str(val["condition"])
                if val.get("atmosphere"):
                    loc.atmosphere = str(val["atmosphere"])
                if val.get("acoustic_env"):
                    loc.acoustic_env = str(val["acoustic_env"])
                if "present_characters" in val and isinstance(val["present_characters"], list):
                    for c in val["present_characters"]:
                        if c not in loc.present_characters:
                            loc.present_characters.append(str(c))
                if "active_conditions" in val and isinstance(val["active_conditions"], list):
                    for cond in val["active_conditions"]:
                        if cond not in loc.active_conditions:
                            loc.active_conditions.append(str(cond))
            elif isinstance(val, str):
                loc.condition = val
            if delta.source_event_id and delta.source_event_id not in loc.provenance_events:
                loc.provenance_events.append(delta.source_event_id)
            loc.last_updated_chapter = delta.chapter
            loc.last_updated_scene = delta.scene

        elif field == "organization_state":
            org = world_state.get_or_create_organization(target)
            if isinstance(val, dict):
                if "status" in val:
                    org.status = str(val["status"])
                if "disposition" in val:
                    org.disposition = str(val["disposition"])
                if "leader" in val:
                    org.leader = str(val["leader"]) if val["leader"] else None
            elif isinstance(val, str):
                org.status = val
            if delta.source_event_id and delta.source_event_id not in org.provenance_events:
                org.provenance_events.append(delta.source_event_id)
            org.last_updated_chapter = delta.chapter
            org.last_updated_scene = delta.scene

        elif field == "discovered_rule" and val:
            rule_str = str(val)
            if rule_str not in world_state.discovered_rules:
                world_state.discovered_rules.append(rule_str)

        elif field == "active_world_condition" and val:
            cond_str = str(val)
            if delta.operation == "remove":
                if cond_str in world_state.active_world_conditions:
                    world_state.active_world_conditions.remove(cond_str)
            elif cond_str not in world_state.active_world_conditions:
                world_state.active_world_conditions.append(cond_str)

    elif delta.domain == DeltaDomain.NARRATIVE:
        payload = val if isinstance(val, dict) else {"summary": str(val or delta.rationale)}
        cat_map = {
            "secret_revealed": "secret",
            "promise_created": "promise",
            "promise_broken": "promise",
            "mystery_created": "mystery",
            "mystery_resolved": "mystery",
            "unresolved_thread": "unresolved_thread",
        }
        category = payload.get("category") or cat_map.get(field, "unresolved_thread")
        status = payload.get("status")
        if not status:
            if field in ("promise_broken",):
                status = "broken"
            elif field in ("mystery_resolved", "thread_resolved"):
                status = "resolved"
            else:
                status = "open"

        existing_thread = world_state.narrative_threads.get(target)
        participants = [str(p) for p in payload.get("participants", []) if p]
        if existing_thread is None:
            thread = NarrativeThreadState(
                thread_id=target,
                category=category,
                summary=str(payload.get("summary") or delta.rationale),
                participants=participants,
                status=status,
                source_event_id=delta.source_event_id,
                resolution_event_id=delta.source_event_id if status in ("resolved", "broken") else None,
                chapter_created=delta.chapter,
                scene_created=delta.scene,
            )
            world_state.narrative_threads[target] = thread
        else:
            existing_thread.status = status
            if status in ("resolved", "broken"):
                existing_thread.resolution_event_id = delta.source_event_id
            for p in participants:
                if p not in existing_thread.participants:
                    existing_thread.participants.append(p)

        # Sync participant character arc unresolved_threads
        for p in participants:
            c_state = character_states.get(p)
            if c_state:
                if status == "open" and target not in c_state.arc_state.unresolved_threads:
                    c_state.arc_state.unresolved_threads.append(target)
                elif status in ("resolved", "broken") and target in c_state.arc_state.unresolved_threads:
                    c_state.arc_state.unresolved_threads.remove(target)


def record_events_on_timeline(
    world_state: WorldState,
    events: List[StoryEvent],
    chapter: int,
    scene: str,
    location: str = "Unspecified",
    time_marker: str = "Unspecified",
) -> None:
    """
    Appends or updates a TimelinePoint for the scene, distinguishing PRESENT story
    chronology from FLASHBACK / HISTORICAL_NARRATION / MEMORY_DREAM events.
    """
    if not events:
        return

    modes = [e.temporal_mode for e in events]
    dominant_mode = modes[0] if modes else TemporalMode.PRESENT
    event_ids = [e.event_id for e in events]

    for e in events:
        if e.temporal_mode == TemporalMode.HISTORICAL_NARRATION:
            if e.description not in world_state.historical_events:
                world_state.historical_events.append(e.description)

    existing_pt = None
    for pt in world_state.timeline:
        if pt.chapter == chapter and pt.scene == scene:
            existing_pt = pt
            break

    if existing_pt is not None:
        for eid in event_ids:
            if eid not in existing_pt.event_ids:
                existing_pt.event_ids.append(eid)
    else:
        world_state.timeline.append(
            TimelinePoint(
                sequence_index=len(world_state.timeline) + 1,
                chapter=chapter,
                scene=scene,
                time_marker=time_marker,
                location=location,
                temporal_mode=dominant_mode,
                chronological_epoch=events[0].chronological_epoch,
                story_time_reference=events[0].story_time_reference,
                event_ids=event_ids,
            )
        )
