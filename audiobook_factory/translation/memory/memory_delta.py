#!/usr/bin/env python3
"""
Audiobook Factory - Explicit & Auditable State Delta Engine (Memory 2.0).
Translates StoryEvents into typed, provenance-backed StateDelta objects across
Character, Relationship, Knowledge, World, and Narrative domains.
Distinguishes HARD_CANON from SOFT_STATE and preserves temporal_mode so flashback
events do not overwrite present-tense physical/location state.
"""

from __future__ import annotations
import hashlib
from enum import Enum
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field, model_validator

from .events import StoryEvent, StoryEventType, TemporalMode
from audiobook_factory.translation.relationship_state import (
    DynamicRelationshipState,
    RelationshipStateEngine,
)


class DeltaDomain(str, Enum):
    CHARACTER = "CHARACTER"
    RELATIONSHIP = "RELATIONSHIP"
    KNOWLEDGE = "KNOWLEDGE"
    WORLD = "WORLD"
    NARRATIVE = "NARRATIVE"


class StateMutability(str, Enum):
    HARD_CANON = "HARD_CANON"
    SOFT_STATE = "SOFT_STATE"
    DYNAMIC_SCENE = "SOFT_STATE"


class StateDelta(BaseModel):
    delta_id: str = ""
    source_event_id: str
    chapter: int = Field(default=1, ge=1)
    scene: str = "scene_001"
    domain: DeltaDomain
    mutability: StateMutability = StateMutability.SOFT_STATE
    target_entity: str
    field_name: str
    operation: Literal["set", "add", "remove", "adjust"] = "set"
    old_value: Optional[Any] = None
    new_value: Any = None
    numeric_delta: Optional[float] = None
    temporal_mode: TemporalMode = TemporalMode.PRESENT
    rationale: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def ensure_delta_id(self) -> "StateDelta":
        if not self.delta_id or not self.delta_id.strip():
            raw = f"{self.source_event_id}:{self.domain.value}:{self.target_entity}:{self.field_name}:{self.new_value}:{self.numeric_delta}"
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
            self.delta_id = f"dlt_c{self.chapter:03d}_{digest}"
        return self


class StateDeltaEngine:
    """
    Deterministically computes structured StateDeltas from a StoryEvent.
    """

    @classmethod
    def derive_deltas_from_event(
        cls,
        event: StoryEvent,
        existing_relationships: Optional[Dict[str, DynamicRelationshipState]] = None,
    ) -> List[StateDelta]:
        deltas: List[StateDelta] = []
        meta = event.metadata or {}
        et = event.event_type

        # 1. CHARACTER_MOVED / LOCATION_CHANGED
        if et in (StoryEventType.CHARACTER_MOVED, StoryEventType.LOCATION_CHANGED):
            new_loc = meta.get("to_location") or event.location
            if new_loc and new_loc != "Unspecified":
                char_delta_meta: Dict[str, Any] = {}
                if meta.get("allow_intra_scene_travel"):
                    char_delta_meta["allow_intra_scene_travel"] = True
                for p in event.participants:
                    deltas.append(
                        StateDelta(
                            source_event_id=event.event_id,
                            chapter=event.chapter,
                            scene=event.scene,
                            domain=DeltaDomain.CHARACTER,
                            mutability=StateMutability.SOFT_STATE,
                            target_entity=p,
                            field_name="current_location",
                            operation="set",
                            old_value=meta.get("from_location"),
                            new_value=new_loc,
                            temporal_mode=event.temporal_mode,
                            rationale=event.description,
                            metadata=char_delta_meta,
                        )
                    )
                loc_payload: Dict[str, Any] = {
                    "present_characters": list(event.participants),
                }
                if meta.get("location_condition"):
                    loc_payload["condition"] = str(meta["location_condition"])
                if meta.get("atmosphere"):
                    loc_payload["atmosphere"] = str(meta["atmosphere"])
                if meta.get("acoustic_env"):
                    loc_payload["acoustic_env"] = str(meta["acoustic_env"])
                deltas.append(
                    StateDelta(
                        source_event_id=event.event_id,
                        chapter=event.chapter,
                        scene=event.scene,
                        domain=DeltaDomain.WORLD,
                        mutability=StateMutability.SOFT_STATE,
                        target_entity=new_loc,
                        field_name="location_state",
                        operation="set",
                        new_value=loc_payload,
                        temporal_mode=event.temporal_mode,
                        rationale=event.description,
                    )
                )

        # 2. CHARACTER_INJURED
        elif et == StoryEventType.CHARACTER_INJURED:
            target = meta.get("injured_character") or (event.participants[0] if event.participants else "")
            injury_desc = meta.get("injury_detail") or event.description
            if target:
                deltas.append(
                    StateDelta(
                        source_event_id=event.event_id,
                        chapter=event.chapter,
                        scene=event.scene,
                        domain=DeltaDomain.CHARACTER,
                        mutability=StateMutability.SOFT_STATE,
                        target_entity=target,
                        field_name="physical_condition",
                        operation="set",
                        new_value="injured",
                        temporal_mode=event.temporal_mode,
                        rationale=event.description,
                        metadata={"injury_detail": injury_desc},
                    )
                )
                deltas.append(
                    StateDelta(
                        source_event_id=event.event_id,
                        chapter=event.chapter,
                        scene=event.scene,
                        domain=DeltaDomain.CHARACTER,
                        mutability=StateMutability.SOFT_STATE,
                        target_entity=target,
                        field_name="active_injuries",
                        operation="add",
                        new_value=injury_desc,
                        temporal_mode=event.temporal_mode,
                        rationale=event.description,
                    )
                )
                deltas.append(
                    StateDelta(
                        source_event_id=event.event_id,
                        chapter=event.chapter,
                        scene=event.scene,
                        domain=DeltaDomain.CHARACTER,
                        mutability=StateMutability.SOFT_STATE,
                        target_entity=target,
                        field_name="energy",
                        operation="adjust",
                        numeric_delta=-0.3,
                        temporal_mode=event.temporal_mode,
                        rationale="Energy reduced due to physical injury",
                    )
                )

        # 3. CHARACTER_RECOVERED
        elif et == StoryEventType.CHARACTER_RECOVERED:
            target = meta.get("recovered_character") or (event.participants[0] if event.participants else "")
            if target:
                deltas.append(
                    StateDelta(
                        source_event_id=event.event_id,
                        chapter=event.chapter,
                        scene=event.scene,
                        domain=DeltaDomain.CHARACTER,
                        mutability=StateMutability.SOFT_STATE,
                        target_entity=target,
                        field_name="physical_condition",
                        operation="set",
                        new_value="healthy",
                        temporal_mode=event.temporal_mode,
                        rationale=event.description,
                    )
                )
                deltas.append(
                    StateDelta(
                        source_event_id=event.event_id,
                        chapter=event.chapter,
                        scene=event.scene,
                        domain=DeltaDomain.CHARACTER,
                        mutability=StateMutability.SOFT_STATE,
                        target_entity=target,
                        field_name="active_injuries",
                        operation="set",
                        new_value=[],
                        temporal_mode=event.temporal_mode,
                        rationale=event.description,
                    )
                )
                deltas.append(
                    StateDelta(
                        source_event_id=event.event_id,
                        chapter=event.chapter,
                        scene=event.scene,
                        domain=DeltaDomain.CHARACTER,
                        mutability=StateMutability.SOFT_STATE,
                        target_entity=target,
                        field_name="energy",
                        operation="adjust",
                        numeric_delta=0.4,
                        temporal_mode=event.temporal_mode,
                        rationale="Energy restored upon recovery",
                    )
                )

        # 4. CHARACTER_DIED
        elif et == StoryEventType.CHARACTER_DIED:
            target = meta.get("deceased_character") or (event.participants[0] if event.participants else "")
            if target:
                deltas.append(
                    StateDelta(
                        source_event_id=event.event_id,
                        chapter=event.chapter,
                        scene=event.scene,
                        domain=DeltaDomain.CHARACTER,
                        mutability=StateMutability.SOFT_STATE,
                        target_entity=target,
                        field_name="is_alive",
                        operation="set",
                        new_value=False,
                        temporal_mode=event.temporal_mode,
                        rationale=event.description,
                    )
                )
                deltas.append(
                    StateDelta(
                        source_event_id=event.event_id,
                        chapter=event.chapter,
                        scene=event.scene,
                        domain=DeltaDomain.CHARACTER,
                        mutability=StateMutability.SOFT_STATE,
                        target_entity=target,
                        field_name="physical_condition",
                        operation="set",
                        new_value="deceased",
                        temporal_mode=event.temporal_mode,
                        rationale=event.description,
                    )
                )

        # 5. SECRET_REVEALED / FACT_LEARNED / FACT_DISPROVEN
        elif et in (StoryEventType.SECRET_REVEALED, StoryEventType.FACT_LEARNED, StoryEventType.FACT_DISPROVEN):
            knower = meta.get("knower") or (event.participants[0] if event.participants else "")
            witnesses = meta.get("witnesses") or list(event.participants)
            if knower and knower not in witnesses:
                witnesses.append(knower)
            fact_id = meta.get("fact_id") or f"fact_{event.event_id}"
            subject = meta.get("subject") or (event.participants[0] if event.participants else "world")
            predicate = meta.get("predicate") or ("secret" if et == StoryEventType.SECRET_REVEALED else "fact")
            val = meta.get("fact_summary") or meta.get("value") or event.description
            status = "DISPROVEN" if et == StoryEventType.FACT_DISPROVEN else meta.get("epistemic_status", "KNOWN")

            deltas.append(
                StateDelta(
                    source_event_id=event.event_id,
                    chapter=event.chapter,
                    scene=event.scene,
                    domain=DeltaDomain.KNOWLEDGE,
                    mutability=StateMutability.SOFT_STATE,
                    target_entity=fact_id,
                    field_name="knowledge_fact",
                    operation="set",
                    new_value={
                        "fact_id": fact_id,
                        "subject": subject,
                        "predicate": predicate,
                        "value": val,
                        "confidence": float(meta.get("confidence", 1.0)),
                        "source_event": event.event_id,
                        "learned_at": f"ch{event.chapter:03d}_{event.scene}",
                        "known_by": witnesses,
                        "status": status,
                    },
                    temporal_mode=event.temporal_mode,
                    rationale=event.description,
                )
            )
            if et == StoryEventType.SECRET_REVEALED:
                deltas.append(
                    StateDelta(
                        source_event_id=event.event_id,
                        chapter=event.chapter,
                        scene=event.scene,
                        domain=DeltaDomain.NARRATIVE,
                        mutability=StateMutability.SOFT_STATE,
                        target_entity=meta.get("thread_id", f"thread_{event.event_id}"),
                        field_name="secret_revealed",
                        operation="set",
                        new_value={
                            "summary": val,
                            "participants": witnesses,
                            "status": "resolved" if meta.get("resolves_secret", False) else "open",
                        },
                        temporal_mode=event.temporal_mode,
                        rationale=event.description,
                    )
                )

        # 6. RELATIONSHIP_CHANGED / BETRAYAL / RECONCILIATION / ROMANTIC_CONFESSION / SHARED_DANGER / THREAT_ISSUED
        elif et in (
            StoryEventType.RELATIONSHIP_CHANGED,
            StoryEventType.BETRAYAL,
            StoryEventType.RECONCILIATION,
            StoryEventType.ROMANTIC_CONFESSION,
            StoryEventType.SHARED_DANGER,
            StoryEventType.THREAT_ISSUED,
        ):
            speaker = meta.get("speaker") or (event.participants[0] if len(event.participants) >= 1 else "")
            target = meta.get("target") or (event.participants[1] if len(event.participants) >= 2 else "")
            if speaker and target:
                rel_key = f"{speaker}->{target}"
                existing_rel = (existing_relationships or {}).get(rel_key) or DynamicRelationshipState(
                    speaker=speaker,
                    target=target,
                )
                default_int_map = {
                    StoryEventType.BETRAYAL: "betrayal",
                    StoryEventType.RECONCILIATION: "reconciliation",
                    StoryEventType.ROMANTIC_CONFESSION: "romantic_confession",
                    StoryEventType.SHARED_DANGER: "shared_danger",
                    StoryEventType.THREAT_ISSUED: "threat",
                }
                interaction_type = meta.get("interaction_type") or default_int_map.get(et, "other")
                explicit_deltas = meta.get("deltas") if isinstance(meta.get("deltas"), dict) else None
                computed_priors = RelationshipStateEngine.compute_contextual_prior_deltas(
                    rel=existing_rel,
                    interaction_type=interaction_type,
                    importance=event.importance,
                    explicit_overrides=explicit_deltas,
                )
                for dim, d_val in computed_priors.items():
                    deltas.append(
                        StateDelta(
                            source_event_id=event.event_id,
                            chapter=event.chapter,
                            scene=event.scene,
                            domain=DeltaDomain.RELATIONSHIP,
                            mutability=StateMutability.SOFT_STATE,
                            target_entity=rel_key,
                            field_name=dim,
                            operation="adjust",
                            numeric_delta=float(d_val),
                            temporal_mode=event.temporal_mode,
                            rationale=event.description,
                            metadata={"speaker": speaker, "target": target, "interaction_type": interaction_type, "importance": event.importance},
                        )
                    )
                # Also emit emotional delta on participants if specified in metadata
                if "emotion" in meta:
                    deltas.append(
                        StateDelta(
                            source_event_id=event.event_id,
                            chapter=event.chapter,
                            scene=event.scene,
                            domain=DeltaDomain.CHARACTER,
                            mutability=StateMutability.SOFT_STATE,
                            target_entity=speaker,
                            field_name="current_emotion",
                            operation="set",
                            new_value=str(meta["emotion"]),
                            temporal_mode=event.temporal_mode,
                            rationale=event.description,
                        )
                    )

        # 7. OBJECT_ACQUIRED / OBJECT_TRANSFERRED / OBJECT_LOST
        elif et in (StoryEventType.OBJECT_ACQUIRED, StoryEventType.OBJECT_TRANSFERRED, StoryEventType.OBJECT_LOST):
            obj_name = meta.get("object_name") or (event.dramatic_tags[1] if len(event.dramatic_tags) > 1 else "UnknownObject")
            new_owner = None if et == StoryEventType.OBJECT_LOST else (
                meta.get("to_character") or (event.participants[-1] if event.participants else None)
            )
            old_owner = meta.get("from_character")
            deltas.append(
                StateDelta(
                    source_event_id=event.event_id,
                    chapter=event.chapter,
                    scene=event.scene,
                    domain=DeltaDomain.WORLD,
                    mutability=StateMutability.SOFT_STATE,
                    target_entity=obj_name,
                    field_name="object_owner",
                    operation="set",
                    old_value=old_owner,
                    new_value=new_owner,
                    temporal_mode=event.temporal_mode,
                    rationale=event.description,
                    metadata={
                        "location": event.location,
                        "previous_owner": old_owner,
                        "status": "lost" if et == StoryEventType.OBJECT_LOST else "owned",
                    },
                )
            )
            if event.location and event.location != "Unspecified":
                deltas.append(
                    StateDelta(
                        source_event_id=event.event_id,
                        chapter=event.chapter,
                        scene=event.scene,
                        domain=DeltaDomain.WORLD,
                        mutability=StateMutability.SOFT_STATE,
                        target_entity=obj_name,
                        field_name="object_location",
                        operation="set",
                        new_value=event.location,
                        temporal_mode=event.temporal_mode,
                        rationale=event.description,
                    )
                )

        # 8. PROMISE_CREATED / PROMISE_BROKEN
        elif et in (StoryEventType.PROMISE_CREATED, StoryEventType.PROMISE_BROKEN):
            thread_id = meta.get("thread_id") or f"promise_{event.event_id}"
            deltas.append(
                StateDelta(
                    source_event_id=event.event_id,
                    chapter=event.chapter,
                    scene=event.scene,
                    domain=DeltaDomain.NARRATIVE,
                    mutability=StateMutability.SOFT_STATE,
                    target_entity=thread_id,
                    field_name="promise_broken" if et == StoryEventType.PROMISE_BROKEN else "promise_created",
                    operation="set",
                    new_value={
                        "thread_id": thread_id,
                        "category": "promise",
                        "summary": meta.get("promise_text") or event.description,
                        "participants": list(event.participants),
                        "status": "broken" if et == StoryEventType.PROMISE_BROKEN else "open",
                    },
                    temporal_mode=event.temporal_mode,
                    rationale=event.description,
                )
            )

        # 9. GOAL_CHANGED / BELIEF_CHANGED
        elif et in (StoryEventType.GOAL_CHANGED, StoryEventType.BELIEF_CHANGED):
            target = meta.get("character") or (event.participants[0] if event.participants else "")
            if target:
                field = "immediate_goal" if et == StoryEventType.GOAL_CHANGED else "current_beliefs"
                op = "set" if et == StoryEventType.GOAL_CHANGED else "add"
                val = meta.get("new_goal") or meta.get("new_belief") or event.description
                deltas.append(
                    StateDelta(
                        source_event_id=event.event_id,
                        chapter=event.chapter,
                        scene=event.scene,
                        domain=DeltaDomain.CHARACTER,
                        mutability=StateMutability.SOFT_STATE,
                        target_entity=target,
                        field_name=field,
                        operation=op,
                        new_value=val,
                        temporal_mode=event.temporal_mode,
                        rationale=event.description,
                        metadata=meta,
                    )
                )

        # 10. WORLD_STATE_CHANGED
        elif et == StoryEventType.WORLD_STATE_CHANGED:
            target = meta.get("target_entity") or event.location or "world"
            field = meta.get("field_name") or "active_world_condition"
            val = meta.get("new_value") or event.description
            deltas.append(
                StateDelta(
                    source_event_id=event.event_id,
                    chapter=event.chapter,
                    scene=event.scene,
                    domain=DeltaDomain.WORLD,
                    mutability=StateMutability.SOFT_STATE,
                    target_entity=target,
                    field_name=field,
                    operation=meta.get("operation", "add" if field in ("active_world_condition", "discovered_rule") else "set"),
                    new_value=val,
                    temporal_mode=event.temporal_mode,
                    rationale=event.description,
                )
            )

        return deltas

    @classmethod
    def compute_deltas_for_events(
        cls,
        events: List[StoryEvent],
        character_states: Optional[Dict[str, Any]] = None,
        relationships: Optional[Dict[str, DynamicRelationshipState]] = None,
        facts_registry: Optional[Dict[str, Any]] = None,
        world_state: Optional[Any] = None,
    ) -> List[StateDelta]:
        """
        Computes all StateDeltas across a batch of StoryEvents, combining explicit structured
        update payloads (character_updates, relationship_impacts, knowledge_updates, world_updates,
        narrative_updates) with event-type heuristic deltas for any domain not explicitly specified.
        """
        all_deltas: List[StateDelta] = []
        for event in events:
            explicit_domains = set()
            event_deltas: List[StateDelta] = []

            # 1. Explicit character_updates
            if event.character_updates:
                explicit_domains.add(DeltaDomain.CHARACTER)
                for char_name, updates in event.character_updates.items():
                    if not isinstance(updates, dict):
                        continue
                    # Process location & non-death fields before is_alive so location updates precede death state
                    ordered_keys = sorted(updates.keys(), key=lambda k: 1 if k == "is_alive" else 0)
                    for k in ordered_keys:
                        val = updates[k]
                        if k in ("location", "current_location"):
                            event_deltas.append(
                                StateDelta(
                                    source_event_id=event.event_id,
                                    chapter=event.chapter,
                                    scene=event.scene,
                                    domain=DeltaDomain.CHARACTER,
                                    mutability=StateMutability.SOFT_STATE,
                                    target_entity=char_name,
                                    field_name="current_location",
                                    operation="set",
                                    new_value=val,
                                    temporal_mode=event.temporal_mode,
                                    rationale=event.description,
                                )
                            )
                        elif k in ("emotion", "current_emotion"):
                            event_deltas.append(
                                StateDelta(
                                    source_event_id=event.event_id,
                                    chapter=event.chapter,
                                    scene=event.scene,
                                    domain=DeltaDomain.CHARACTER,
                                    mutability=StateMutability.SOFT_STATE,
                                    target_entity=char_name,
                                    field_name="current_emotion",
                                    operation="set",
                                    new_value=val,
                                    temporal_mode=event.temporal_mode,
                                    rationale=event.description,
                                )
                            )
                        elif k == "emotion_intensity":
                            event_deltas.append(
                                StateDelta(
                                    source_event_id=event.event_id,
                                    chapter=event.chapter,
                                    scene=event.scene,
                                    domain=DeltaDomain.CHARACTER,
                                    mutability=StateMutability.SOFT_STATE,
                                    target_entity=char_name,
                                    field_name="emotion_intensity",
                                    operation="set",
                                    new_value=float(val),
                                    temporal_mode=event.temporal_mode,
                                    rationale=event.description,
                                )
                            )
                        elif k == "physical_condition":
                            event_deltas.append(
                                StateDelta(
                                    source_event_id=event.event_id,
                                    chapter=event.chapter,
                                    scene=event.scene,
                                    domain=DeltaDomain.CHARACTER,
                                    mutability=StateMutability.SOFT_STATE,
                                    target_entity=char_name,
                                    field_name="physical_condition",
                                    operation="set",
                                    new_value=val,
                                    temporal_mode=event.temporal_mode,
                                    rationale=event.description,
                                )
                            )
                        elif k == "injury_added":
                            event_deltas.append(
                                StateDelta(
                                    source_event_id=event.event_id,
                                    chapter=event.chapter,
                                    scene=event.scene,
                                    domain=DeltaDomain.CHARACTER,
                                    mutability=StateMutability.SOFT_STATE,
                                    target_entity=char_name,
                                    field_name="active_injuries",
                                    operation="add",
                                    new_value=val,
                                    temporal_mode=event.temporal_mode,
                                    rationale=event.description,
                                )
                            )
                        elif k == "injury_removed":
                            event_deltas.append(
                                StateDelta(
                                    source_event_id=event.event_id,
                                    chapter=event.chapter,
                                    scene=event.scene,
                                    domain=DeltaDomain.CHARACTER,
                                    mutability=StateMutability.SOFT_STATE,
                                    target_entity=char_name,
                                    field_name="active_injuries",
                                    operation="remove",
                                    new_value=val,
                                    temporal_mode=event.temporal_mode,
                                    rationale=event.description,
                                )
                            )
                        elif k == "energy_delta":
                            event_deltas.append(
                                StateDelta(
                                    source_event_id=event.event_id,
                                    chapter=event.chapter,
                                    scene=event.scene,
                                    domain=DeltaDomain.CHARACTER,
                                    mutability=StateMutability.SOFT_STATE,
                                    target_entity=char_name,
                                    field_name="energy",
                                    operation="adjust",
                                    numeric_delta=float(val),
                                    temporal_mode=event.temporal_mode,
                                    rationale=event.description,
                                )
                            )
                        elif k == "is_alive":
                            event_deltas.append(
                                StateDelta(
                                    source_event_id=event.event_id,
                                    chapter=event.chapter,
                                    scene=event.scene,
                                    domain=DeltaDomain.CHARACTER,
                                    mutability=StateMutability.SOFT_STATE,
                                    target_entity=char_name,
                                    field_name="is_alive",
                                    operation="set",
                                    new_value=bool(val),
                                    temporal_mode=event.temporal_mode,
                                    rationale=event.description,
                                )
                            )
                        elif k in ("immediate_goal", "goal"):
                            event_deltas.append(
                                StateDelta(
                                    source_event_id=event.event_id,
                                    chapter=event.chapter,
                                    scene=event.scene,
                                    domain=DeltaDomain.CHARACTER,
                                    mutability=StateMutability.SOFT_STATE,
                                    target_entity=char_name,
                                    field_name="immediate_goal",
                                    operation="set",
                                    new_value=val,
                                    temporal_mode=event.temporal_mode,
                                    rationale=event.description,
                                )
                            )
                        elif k == "belief_added":
                            event_deltas.append(
                                StateDelta(
                                    source_event_id=event.event_id,
                                    chapter=event.chapter,
                                    scene=event.scene,
                                    domain=DeltaDomain.CHARACTER,
                                    mutability=StateMutability.SOFT_STATE,
                                    target_entity=char_name,
                                    field_name="current_beliefs",
                                    operation="add",
                                    new_value=val,
                                    temporal_mode=event.temporal_mode,
                                    rationale=event.description,
                                )
                            )
                        elif k in ("turning_point", "arc_phase", "core_fear", "core_desire", "internal_conflict"):
                            event_deltas.append(
                                StateDelta(
                                    source_event_id=event.event_id,
                                    chapter=event.chapter,
                                    scene=event.scene,
                                    domain=DeltaDomain.CHARACTER,
                                    mutability=StateMutability.SOFT_STATE,
                                    target_entity=char_name,
                                    field_name=k,
                                    operation="add" if k == "turning_point" else "set",
                                    new_value=val,
                                    temporal_mode=event.temporal_mode,
                                    rationale=event.description,
                                )
                            )
                        else:
                            event_deltas.append(
                                StateDelta(
                                    source_event_id=event.event_id,
                                    chapter=event.chapter,
                                    scene=event.scene,
                                    domain=DeltaDomain.CHARACTER,
                                    mutability=StateMutability.SOFT_STATE,
                                    target_entity=char_name,
                                    field_name=k,
                                    operation="set",
                                    new_value=val,
                                    temporal_mode=event.temporal_mode,
                                    rationale=event.description,
                                )
                            )

            # 2. Explicit relationship_impacts
            if event.relationship_impacts:
                explicit_domains.add(DeltaDomain.RELATIONSHIP)
                for imp in event.relationship_impacts:
                    speaker = imp.get("speaker", "")
                    target = imp.get("target", "")
                    if not speaker or not target:
                        continue
                    rel_key = f"{speaker}->{target}"
                    existing_rel = (relationships or {}).get(rel_key) or DynamicRelationshipState(
                        speaker=speaker, target=target
                    )
                    interaction_type = imp.get("interaction_type", "other")
                    explicit_overrides = imp.get("deltas") if isinstance(imp.get("deltas"), dict) else None
                    computed = RelationshipStateEngine.compute_contextual_prior_deltas(
                        rel=existing_rel,
                        interaction_type=interaction_type,
                        importance=event.importance,
                        explicit_overrides=explicit_overrides,
                    )
                    for dim, d_val in computed.items():
                        event_deltas.append(
                            StateDelta(
                                source_event_id=event.event_id,
                                chapter=event.chapter,
                                scene=event.scene,
                                domain=DeltaDomain.RELATIONSHIP,
                                mutability=StateMutability.SOFT_STATE,
                                target_entity=rel_key,
                                field_name=dim,
                                operation="adjust",
                                numeric_delta=float(d_val),
                                temporal_mode=event.temporal_mode,
                                rationale=event.description,
                                metadata={
                                    "speaker": speaker,
                                    "target": target,
                                    "interaction_type": interaction_type,
                                    "importance": event.importance,
                                },
                            )
                        )

            # 3. Explicit knowledge_updates
            if event.knowledge_updates:
                explicit_domains.add(DeltaDomain.KNOWLEDGE)
                for ku in event.knowledge_updates:
                    fact_id = ku.get("fact_id") or f"fact_{event.event_id}"
                    event_deltas.append(
                        StateDelta(
                            source_event_id=event.event_id,
                            chapter=event.chapter,
                            scene=event.scene,
                            domain=DeltaDomain.KNOWLEDGE,
                            mutability=StateMutability.SOFT_STATE,
                            target_entity=fact_id,
                            field_name="knowledge_fact",
                            operation="set",
                            new_value={
                                "fact_id": fact_id,
                                "subject": ku.get("subject", "world"),
                                "predicate": ku.get("predicate", "fact"),
                                "value": ku.get("value", event.description),
                                "confidence": float(ku.get("confidence", 1.0)),
                                "source_event": event.event_id,
                                "learned_at": ku.get("learned_at") or f"ch{event.chapter:03d}_{event.scene}",
                                "known_by": list(ku.get("known_by", event.participants)),
                                "status": ku.get("status", "KNOWN"),
                            },
                            temporal_mode=event.temporal_mode,
                            rationale=event.description,
                        )
                    )

            # 4. Explicit world_updates
            if event.world_updates:
                explicit_domains.add(DeltaDomain.WORLD)
                wu = event.world_updates
                for obj_acq in wu.get("objects_acquired", []):
                    obj_name = obj_acq.get("object_name", "UnknownObject")
                    owner = obj_acq.get("owner")
                    loc = obj_acq.get("location") or event.location
                    event_deltas.append(
                        StateDelta(
                            source_event_id=event.event_id,
                            chapter=event.chapter,
                            scene=event.scene,
                            domain=DeltaDomain.WORLD,
                            mutability=StateMutability.SOFT_STATE,
                            target_entity=obj_name,
                            field_name="object_owner",
                            operation="set",
                            new_value=owner,
                            temporal_mode=event.temporal_mode,
                            rationale=event.description,
                            metadata={"location": loc, "status": "owned"},
                        )
                    )
                for obj_tr in wu.get("objects_transferred", []):
                    obj_name = obj_tr.get("object_name", "UnknownObject")
                    from_owner = obj_tr.get("from_owner") or obj_tr.get("from_character")
                    to_owner = obj_tr.get("to_owner") or obj_tr.get("to_character")
                    loc = obj_tr.get("location") or event.location
                    event_deltas.append(
                        StateDelta(
                            source_event_id=event.event_id,
                            chapter=event.chapter,
                            scene=event.scene,
                            domain=DeltaDomain.WORLD,
                            mutability=StateMutability.SOFT_STATE,
                            target_entity=obj_name,
                            field_name="object_owner",
                            operation="set",
                            old_value=from_owner,
                            new_value=to_owner,
                            temporal_mode=event.temporal_mode,
                            rationale=event.description,
                            metadata={"previous_owner": from_owner, "location": loc, "status": "owned"},
                        )
                    )
                for obj_lost in wu.get("objects_lost", []):
                    obj_name = obj_lost.get("object_name", "UnknownObject")
                    loc = obj_lost.get("location") or event.location
                    event_deltas.append(
                        StateDelta(
                            source_event_id=event.event_id,
                            chapter=event.chapter,
                            scene=event.scene,
                            domain=DeltaDomain.WORLD,
                            mutability=StateMutability.SOFT_STATE,
                            target_entity=obj_name,
                            field_name="object_owner",
                            operation="set",
                            new_value=None,
                            temporal_mode=event.temporal_mode,
                            rationale=event.description,
                            metadata={"location": loc, "status": "lost"},
                        )
                    )
                for loc_name, loc_data in wu.get("location_states", {}).items():
                    event_deltas.append(
                        StateDelta(
                            source_event_id=event.event_id,
                            chapter=event.chapter,
                            scene=event.scene,
                            domain=DeltaDomain.WORLD,
                            mutability=StateMutability.SOFT_STATE,
                            target_entity=loc_name,
                            field_name="location_state",
                            operation="set",
                            new_value=loc_data,
                            temporal_mode=event.temporal_mode,
                            rationale=event.description,
                        )
                    )
                for org_name, org_data in wu.get("organization_states", {}).items():
                    event_deltas.append(
                        StateDelta(
                            source_event_id=event.event_id,
                            chapter=event.chapter,
                            scene=event.scene,
                            domain=DeltaDomain.WORLD,
                            mutability=StateMutability.SOFT_STATE,
                            target_entity=org_name,
                            field_name="organization_state",
                            operation="set",
                            new_value=org_data,
                            temporal_mode=event.temporal_mode,
                            rationale=event.description,
                        )
                    )
                for rule_str in wu.get("discovered_rules", []):
                    event_deltas.append(
                        StateDelta(
                            source_event_id=event.event_id,
                            chapter=event.chapter,
                            scene=event.scene,
                            domain=DeltaDomain.WORLD,
                            mutability=StateMutability.SOFT_STATE,
                            target_entity="world",
                            field_name="discovered_rule",
                            operation="add",
                            new_value=rule_str,
                            temporal_mode=event.temporal_mode,
                            rationale=event.description,
                        )
                    )

            # 5. Explicit narrative_updates
            if event.narrative_updates:
                explicit_domains.add(DeltaDomain.NARRATIVE)
                for th in event.narrative_updates.get("threads", []):
                    th_id = th.get("thread_id") or f"thread_{event.event_id}"
                    event_deltas.append(
                        StateDelta(
                            source_event_id=event.event_id,
                            chapter=event.chapter,
                            scene=event.scene,
                            domain=DeltaDomain.NARRATIVE,
                            mutability=StateMutability.SOFT_STATE,
                            target_entity=th_id,
                            field_name="unresolved_thread",
                            operation="set",
                            new_value=th,
                            temporal_mode=event.temporal_mode,
                            rationale=event.description,
                        )
                    )

            # Combine with heuristic event deltas for any domains not explicitly provided
            heuristic_deltas = cls.derive_deltas_from_event(event, existing_relationships=relationships)
            for hd in heuristic_deltas:
                if hd.domain not in explicit_domains:
                    event_deltas.append(hd)

            all_deltas.extend(event_deltas)

        return all_deltas

