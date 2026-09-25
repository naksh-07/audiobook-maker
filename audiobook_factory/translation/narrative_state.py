#!/usr/bin/env python3
"""
Audiobook Factory - Narrative Continuity State Engine.
Maintains structured story memory across scenes and chapters, replacing the fragile
trailing 500-character string as the primary continuity mechanism.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class NarrativeContinuityState(BaseModel):
    active_characters: List[str] = Field(default_factory=list)
    current_location: str = "Unknown"
    current_time: str = "Unknown"
    recent_events: List[str] = Field(default_factory=list)
    current_objectives: List[str] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)
    character_injuries: Dict[str, str] = Field(default_factory=dict)
    prevailing_emotional_tone: str = "grim dramatic focus"
    newly_decided_terms: Dict[str, str] = Field(default_factory=dict)

    def get_prompt_context(self) -> str:
        """Formats the structured narrative continuity context for translation prompts."""
        chars = ", ".join(self.active_characters) if self.active_characters else "None"
        events = "; ".join(self.recent_events[-3:]) if self.recent_events else "None recorded"
        terms = ", ".join(f"{k} -> {v}" for k, v in list(self.newly_decided_terms.items())[-4:]) if self.newly_decided_terms else "None"

        return (
            "STRUCTURED NARRATIVE CONTINUITY STATE:\n"
            f"- Current Location & Atmosphere: {self.current_location} ({self.prevailing_emotional_tone})\n"
            f"- Present Characters: {chars}\n"
            f"- Recent Preceding Events: {events}\n"
            f"- Active Terminology Decisions: {terms}"
        )


class NarrativeStateEngine:
    @staticmethod
    def update_from_scene_completion(
        current_state: NarrativeContinuityState,
        scene_summary: str,
        active_characters: List[str],
        location: str,
        new_terms: Optional[Dict[str, str]] = None
    ) -> NarrativeContinuityState:
        """Updates story state upon the successful certified completion of a scene."""
        updated = current_state.model_copy(deep=True)
        if scene_summary:
            updated.recent_events.append(scene_summary)
            # Retain only last 5 key events to prevent unbounded growth
            if len(updated.recent_events) > 5:
                updated.recent_events = updated.recent_events[-5:]

        updated.active_characters = list(set(active_characters))
        if location and location != "Unspecified":
            updated.current_location = location

        if new_terms:
            updated.newly_decided_terms.update(new_terms)

        return updated

    @staticmethod
    def sync_from_memory_store(
        current_state: NarrativeContinuityState,
        memory_store: Optional[Any] = None,
        scene_plan: Optional[Any] = None,
        character_states: Optional[Dict[str, Any]] = None,
        world_state: Optional[Any] = None,
        recent_events: Optional[List[Any]] = None,
        active_characters: Optional[List[str]] = None,
        location: Optional[str] = None,
    ) -> NarrativeContinuityState:
        """
        Projects rich MemoryStore state into NarrativeContinuityState so legacy callers
        automatically receive updated character injuries, active objectives, and unresolved threads.
        """
        updated = current_state.model_copy(deep=True)

        # Sync character injuries and objectives
        char_states = character_states if character_states is not None else getattr(memory_store, "character_states", {})
        injuries: Dict[str, str] = {}
        objectives: List[str] = []
        for cname, cstate in char_states.items():
            if not getattr(cstate, "is_alive", True):
                injuries[cname] = "deceased"
            elif getattr(cstate, "active_injuries", []):
                injuries[cname] = ", ".join(cstate.active_injuries)
            elif getattr(cstate, "physical_condition", "healthy") != "healthy":
                injuries[cname] = cstate.physical_condition

            goal = getattr(cstate, "immediate_goal", "") or getattr(getattr(cstate, "arc_state", None), "primary_goal", "")
            if goal:
                objectives.append(f"{cname}: {goal}")

        updated.character_injuries = injuries
        if objectives:
            updated.current_objectives = objectives[:8]

        # Sync unresolved narrative threads
        eff_world_state = world_state if world_state is not None else getattr(memory_store, "world_state", None)
        if eff_world_state and hasattr(eff_world_state, "narrative_threads"):
            open_threads = [
                t.summary for t in eff_world_state.narrative_threads.values()
                if getattr(t, "status", "open") == "open"
            ]
            updated.unresolved_questions = open_threads[:8]

        # Sync recent events
        if recent_events is not None:
            recent_descs = [
                getattr(e, "description", str(e))
                for e in recent_events[-5:]
            ]
            if recent_descs:
                updated.recent_events = recent_descs
        elif memory_store is not None:
            events_map = getattr(memory_store, "events", {})
            if events_map:
                recent_descs = [ev.description for ev in list(events_map.values())[-5:]]
                if recent_descs:
                    updated.recent_events = recent_descs

        if active_characters is not None:
            updated.active_characters = list(active_characters)
        if location and location != "Unspecified":
            updated.current_location = location

        if scene_plan is not None:
            if getattr(scene_plan, "active_characters", None):
                updated.active_characters = list(scene_plan.active_characters)
            if getattr(scene_plan, "location", "Unspecified") != "Unspecified":
                updated.current_location = scene_plan.location
            if getattr(scene_plan, "time", "Unspecified") != "Unspecified":
                updated.current_time = scene_plan.time
            if getattr(scene_plan, "emotional_state", ""):
                updated.prevailing_emotional_tone = scene_plan.emotional_state

        return updated

