#!/usr/bin/env python3
"""
Audiobook Factory - Dynamic World State Engine (Memory 2.0).
Separates canonical world definitions (BookBible) from dynamic, evolving world state
(object ownership & locations, location states, organization states, active conditions,
discovered world rules, narrative threads, and dual narrative/chronological timeline).
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field

from .events import TemporalMode


class ObjectState(BaseModel):
    object_name: str
    current_owner: Optional[str] = None
    current_location: str = "Unspecified"
    condition: str = "intact"
    status: Literal["owned", "present", "lost", "destroyed"] = "present"
    provenance_events: List[str] = Field(default_factory=list)
    last_updated_chapter: int = 1
    last_updated_scene: str = "scene_001"


class LocationState(BaseModel):
    location_name: str
    condition: str = "normal"
    atmosphere: str = "neutral"
    acoustic_env: str = "open_road"
    present_characters: List[str] = Field(default_factory=list)
    active_conditions: List[str] = Field(default_factory=list)
    provenance_events: List[str] = Field(default_factory=list)
    last_updated_chapter: int = 1
    last_updated_scene: str = "scene_001"


class OrganizationState(BaseModel):
    organization_name: str
    status: str = "active"
    disposition: str = "neutral"
    leader: Optional[str] = None
    allegiances: List[str] = Field(default_factory=list)
    provenance_events: List[str] = Field(default_factory=list)
    last_updated_chapter: int = 1
    last_updated_scene: str = "scene_001"


class NarrativeThreadState(BaseModel):
    thread_id: str
    category: Literal["secret", "promise", "mystery", "unresolved_thread"] = "unresolved_thread"
    summary: str
    participants: List[str] = Field(default_factory=list)
    status: Literal["open", "resolved", "broken"] = "open"
    source_event_id: str = ""
    resolution_event_id: Optional[str] = None
    chapter_created: int = 1
    scene_created: str = "scene_001"


class TimelinePoint(BaseModel):
    """
    Records a scene/event point along both narrative presentation order and in-universe story chronology.
    """
    sequence_index: int
    chapter: int
    scene: str
    time_marker: str = "Unspecified"
    location: str = "Unspecified"
    temporal_mode: TemporalMode = TemporalMode.PRESENT
    chronological_epoch: Optional[int] = None
    story_time_reference: str = ""
    event_ids: List[str] = Field(default_factory=list)


class WorldState(BaseModel):
    location_states: Dict[str, LocationState] = Field(default_factory=dict)
    object_states: Dict[str, ObjectState] = Field(default_factory=dict)
    organization_states: Dict[str, OrganizationState] = Field(default_factory=dict)
    active_world_conditions: List[str] = Field(default_factory=list)
    discovered_rules: List[str] = Field(default_factory=list)
    historical_events: List[str] = Field(default_factory=list)
    timeline: List[TimelinePoint] = Field(default_factory=list)
    narrative_threads: Dict[str, NarrativeThreadState] = Field(default_factory=dict)

    def get_or_create_location(self, location_name: str) -> LocationState:
        if location_name not in self.location_states:
            self.location_states[location_name] = LocationState(location_name=location_name)
        return self.location_states[location_name]

    def get_or_create_object(self, object_name: str) -> ObjectState:
        if object_name not in self.object_states:
            self.object_states[object_name] = ObjectState(object_name=object_name)
        return self.object_states[object_name]

    def get_or_create_organization(self, org_name: str) -> OrganizationState:
        if org_name not in self.organization_states:
            self.organization_states[org_name] = OrganizationState(organization_name=org_name)
        return self.organization_states[org_name]

    def get_open_threads(self) -> List[NarrativeThreadState]:
        """Returns all currently open narrative threads (secrets, promises, mysteries)."""
        return [t for t in self.narrative_threads.values() if t.status == "open"]
