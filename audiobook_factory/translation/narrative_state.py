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
