#!/usr/bin/env python3
"""
Audiobook Factory - Selective Scene Memory Context (Memory 2.0).
Packages the 7-tier selective retrieval output + Narrative Salience layer into
a clean prompt context and conservative performance guidance adapter.
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from audiobook_factory.translation.relationship_state import (
    DynamicRelationshipState,
    RelationshipStateEngine,
)
from .events import StoryEvent, TemporalMode
from .character_memory import CharacterState
from .world_memory import LocationState, ObjectState, NarrativeThreadState


class MemoryContext(BaseModel):
    """
    Scene-scoped memory slice assembled by MemoryRetriever.
    Contains ONLY entities, relationships, epistemic constraints, objects,
    recent events, salient dramatic memories, and open threads relevant to the scene.
    """
    chapter: int = 1
    scene_id: str = "scene_01"
    location_name: str = "Unspecified"
    temporal_mode: TemporalMode = TemporalMode.PRESENT

    # Tier 1: Canonical identities & relevant immutable world rules
    canon_identities: List[Dict[str, Any]] = Field(default_factory=list)
    relevant_world_rules: List[str] = Field(default_factory=list)

    # Tier 2: Dynamic states for active characters only
    active_character_states: Dict[str, CharacterState] = Field(default_factory=dict)

    # Tier 3: Active relationships among present characters
    active_relationships: List[DynamicRelationshipState] = Field(default_factory=list)

    # Tier 4: Epistemic isolation matrix per active character
    epistemic_constraints: Dict[str, Dict[str, List[str]]] = Field(default_factory=dict)

    # Tier 5: Active location state and present/owned objects
    location_state: Optional[LocationState] = None
    relevant_objects: List[ObjectState] = Field(default_factory=list)

    # Tier 6: Recent relevant events & Narrative Salience (Dramatic Memory) events
    recent_events: List[StoryEvent] = Field(default_factory=list)
    salient_events: List[StoryEvent] = Field(default_factory=list)

    # Tier 7: Unresolved narrative threads involving active characters/location
    unresolved_threads: List[NarrativeThreadState] = Field(default_factory=list)

    @property
    def high_salience_events(self) -> List[StoryEvent]:
        """Alias for salient_events (Dramatic Memory / Narrative Salience layer)."""
        return self.salient_events

    def to_prompt_block(self) -> str:
        """Alias for get_prompt_context()."""
        return self.get_prompt_context()

    def estimated_tokens(self) -> int:
        """Estimates token count of the rendered prompt block (~4 chars per token)."""
        block = self.get_prompt_context()
        return max(1, len(block) // 4)

    def enforce_token_budget(self, max_token_budget: int = 800) -> "MemoryContext":
        """
        Enforces a strict upper token budget on the rendered MemoryContext prompt block
        by progressively trimming lower-priority items while preserving active character
        states, active relationships, and top salient/recent events.
        """
        if max_token_budget <= 0 or self.estimated_tokens() <= max_token_budget:
            return self

        # Step 1: Trim epistemic constraint buckets to top 2 per category
        for char_name, buckets in self.epistemic_constraints.items():
            for k in list(buckets.keys()):
                buckets[k] = buckets[k][:2]
        if self.estimated_tokens() <= max_token_budget:
            return self

        # Step 2: Trim unresolved threads and relevant objects
        self.unresolved_threads = self.unresolved_threads[:2]
        self.relevant_objects = self.relevant_objects[:3]
        if self.estimated_tokens() <= max_token_budget:
            return self

        # Step 3: Trim epistemic UNKNOWN bucket to top 1 and recent/salient events to top 3
        for char_name, buckets in self.epistemic_constraints.items():
            buckets["UNKNOWN"] = buckets.get("UNKNOWN", [])[:1]
            buckets["KNOWN"] = buckets.get("KNOWN", [])[:2]
        self.recent_events = self.recent_events[-3:]
        self.salient_events = self.salient_events[:3]
        if self.estimated_tokens() <= max_token_budget:
            return self

        # Step 4: Aggressive trim for extreme small budgets
        self.unresolved_threads = self.unresolved_threads[:1]
        self.relevant_objects = self.relevant_objects[:2]
        self.recent_events = self.recent_events[-2:]
        self.salient_events = self.salient_events[:2]
        for char_name, buckets in self.epistemic_constraints.items():
            for k in list(buckets.keys()):
                buckets[k] = buckets[k][:1]
        return self

    def get_character_performance_guidance(
        self,
        speaker: str,
        target: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Computes performance context and constraints for a speaking character
        without blindly overriding screenplay acting intent.
        """
        c_state = self.active_character_states.get(speaker)
        guidance: Dict[str, Any] = {
            "speaker": speaker,
            "physical_condition": c_state.physical_condition if c_state else "healthy",
            "active_injuries": list(c_state.active_injuries) if c_state else [],
            "energy": c_state.energy if c_state else 0.8,
            "baseline_emotion": c_state.current_emotion if c_state else "neutral",
            "emotion_intensity": c_state.emotion_intensity if c_state else 0.3,
            "immediate_goal": c_state.immediate_goal if c_state else "",
            "acoustic_env": self.location_state.acoustic_env if self.location_state else "neutral_room",
            "recommended_pronoun": None,
            "recommended_register": None,
            "vocal_constraints": [],
        }

        if c_state:
            if c_state.physical_condition in ("injured", "critical") or c_state.active_injuries:
                guidance["vocal_constraints"].append("restrained_breath_effort_due_to_injury")
            if c_state.energy <= 0.35 or c_state.physical_condition == "exhausted":
                guidance["vocal_constraints"].append("low_energy_fatigued_projection")

        if target:
            for rel in self.active_relationships:
                if rel.speaker.lower() == speaker.lower() and rel.target.lower() == target.lower():
                    guidance["recommended_pronoun"] = RelationshipStateEngine.resolve_hindi_pronoun(rel)
                    guidance["recommended_register"] = RelationshipStateEngine.resolve_vocabulary_register(rel)
                    break

        return guidance

    def apply_performance_guidance_to_segment(
        self,
        seg_dict: Dict[str, Any],
        target_speaker: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Conservatively enriches a screenplay segment with memory-backed performance context.
        Refinement 2: Respects existing screenplay/acting intent. Never overwrites explicit
        emotion, delivery_style, or vocal tags; only supplies fallback context when neutral/unspecified.
        """
        speaker = str(seg_dict.get("speaker") or "").strip()
        if not speaker or speaker.lower() == "narrator":
            if self.location_state and not seg_dict.get("acoustic_env"):
                seg_dict["acoustic_env"] = self.location_state.acoustic_env
            return seg_dict

        guidance = self.get_character_performance_guidance(speaker, target_speaker)

        # Attach non-destructive metadata context
        if self.location_state and not seg_dict.get("acoustic_env"):
            seg_dict["acoustic_env"] = self.location_state.acoustic_env

        if guidance["recommended_pronoun"] and not seg_dict.get("recommended_pronoun"):
            seg_dict["recommended_pronoun"] = guidance["recommended_pronoun"]
        if guidance["recommended_register"] and not seg_dict.get("recommended_register"):
            seg_dict["recommended_register"] = guidance["recommended_register"]

        # Only suggest emotion or delivery constraint if screenplay left it neutral/empty
        existing_emotion = str(seg_dict.get("emotion") or "neutral").strip().lower()
        acting_obj = seg_dict.get("acting")
        nested_delivery = (
            acting_obj.get("delivery_style")
            if isinstance(acting_obj, dict)
            else getattr(acting_obj, "delivery_style", "")
        )
        existing_delivery = str(
            seg_dict.get("delivery_style") or nested_delivery or seg_dict.get("pace") or ""
        ).strip().lower()
        text_val = str(seg_dict.get("text") or "")
        has_explicit_tag = "[" in text_val and "]" in text_val

        if existing_emotion in ("", "neutral", "standard") and not has_explicit_tag:
            if guidance["physical_condition"] in ("injured", "critical") and guidance["active_injuries"]:
                seg_dict["emotion"] = "strained"
            elif guidance["physical_condition"] == "exhausted" or guidance["energy"] <= 0.3:
                seg_dict["emotion"] = "weary"
            elif guidance["emotion_intensity"] >= 0.75 and guidance["baseline_emotion"] != "neutral":
                seg_dict["emotion"] = guidance["baseline_emotion"]

        if existing_delivery in ("", "normal", "neutral", "standard") and not has_explicit_tag:
            if "restrained_breath_effort_due_to_injury" in guidance["vocal_constraints"]:
                seg_dict["memory_vocal_constraint"] = "strained_breath"
            elif "low_energy_fatigued_projection" in guidance["vocal_constraints"]:
                seg_dict["memory_vocal_constraint"] = "fatigued_low_energy"

        return seg_dict

    def get_prompt_context(self) -> str:
        """
        Renders the selective 7-tier + Narrative Salience memory slice into a compact,
        high-signal prompt block for translation and screenplay generation.
        """
        lines: List[str] = [
            f"=== WORLD & CHARACTER MEMORY 2.0 (Ch {self.chapter}, {self.scene_id} | Mode: {self.temporal_mode.value}) ==="
        ]

        if self.temporal_mode != TemporalMode.PRESENT:
            lines.append(
                f"TEMPORAL NOTE: Scene is in {self.temporal_mode.value} mode. Do not treat past states as overriding present physical survival/location."
            )

        if self.location_state:
            loc = self.location_state
            cond_info = f", conditions={loc.active_conditions}" if loc.active_conditions else ""
            lines.append(
                f"LOCATION: {loc.location_name} [condition={loc.condition}, atmosphere={loc.atmosphere}, acoustics={loc.acoustic_env}{cond_info}]"
            )

        if self.relevant_world_rules:
            lines.append("WORLD RULES: " + " | ".join(self.relevant_world_rules[:4]))

        if self.active_character_states:
            lines.append("ACTIVE CHARACTER STATES (Performance Context & Constraints):")
            for name, st in self.active_character_states.items():
                inj = f", injuries={st.active_injuries}" if st.active_injuries else ""
                goal = f", goal='{st.immediate_goal}'" if st.immediate_goal else ""
                arc = f", arc='{st.arc_state.current_arc_phase}'" if st.arc_state.current_arc_phase else ""
                lines.append(
                    f"  - {name}: alive={st.is_alive}, cond={st.physical_condition}{inj}, "
                    f"emotion={st.current_emotion}({st.emotion_intensity:.1f}), energy={st.energy:.1f}{goal}{arc}"
                )

        if self.active_relationships:
            lines.append("RELATIONSHIP & REGISTER DYNAMICS:")
            for rel in self.active_relationships:
                pronoun = RelationshipStateEngine.resolve_hindi_pronoun(rel)
                reg = RelationshipStateEngine.resolve_vocabulary_register(rel)
                lines.append(
                    f"  - {rel.speaker} -> {rel.target}: pronoun='{pronoun}', register='{reg}' "
                    f"(respect={rel.respect}, trust={rel.trust}, familiarity={rel.familiarity}, tension={rel.tension})"
                )

        if self.epistemic_constraints:
            lines.append("EPISTEMIC ISOLATION (Strict Knowledge Boundaries):")
            for char_name, buckets in self.epistemic_constraints.items():
                known = "; ".join(buckets.get("KNOWN", [])[:3])
                suspected = "; ".join(buckets.get("SUSPECTED", [])[:2])
                false_bel = "; ".join(buckets.get("FALSE_BELIEF", [])[:2])
                unknown = "; ".join(buckets.get("UNKNOWN", [])[:3])
                parts: List[str] = []
                if known:
                    parts.append(f"KNOWS=[{known}]")
                if suspected:
                    parts.append(f"SUSPECTS=[{suspected}]")
                if false_bel:
                    parts.append(f"FALSELY_BELIEVES=[{false_bel}]")
                if unknown:
                    parts.append(f"MUST_NOT_KNOW=[{unknown}]")
                if parts:
                    lines.append(f"  - {char_name}: " + " | ".join(parts))

        if self.relevant_objects:
            obj_strs = [
                f"{o.object_name} (owner={o.current_owner or 'none'}, status={o.status}, loc={o.current_location})"
                for o in self.relevant_objects[:5]
            ]
            lines.append("RELEVANT OBJECTS: " + " | ".join(obj_strs))

        if self.salient_events:
            lines.append("HIGH-SALIENCE DRAMATIC MEMORIES (Unresolved / Turning Points):")
            for ev in self.salient_events[:4]:
                lines.append(
                    f"  - [Ch{ev.chapter} {ev.event_type.value} | salience={ev.salience_score:.2f}] {ev.description}"
                )

        if self.recent_events:
            lines.append("RECENT CONTINUITY EVENTS:")
            for ev in self.recent_events[:4]:
                lines.append(f"  - [Ch{ev.chapter}:{ev.scene}] {ev.description}")

        if self.unresolved_threads:
            lines.append("OPEN NARRATIVE THREADS / PROMISES / SECRETS:")
            for th in self.unresolved_threads[:4]:
                lines.append(f"  - [{th.category.upper()}] {th.summary} (participants={th.participants})")

        return "\n".join(lines)
