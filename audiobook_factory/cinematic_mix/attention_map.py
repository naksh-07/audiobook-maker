#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Module: attention_map.py
Defines AttentionEvent and AttentionMap: the time-aware listener attention model.
Represents where listener attention should be directed across the scene timeline.
Attention is decoupled from dialogue: music, FX, silence, ambience, and dialogue
can each take dominant priority depending on narrative intent.
"""

from __future__ import annotations
import hashlib
import json
from typing import Dict, Any, List, Optional, Literal, Union, Tuple, Set
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ConfigDict,
    AliasChoices,
)


AttentionCategory = Literal[
    "dialogue",
    "music",
    "fx",
    "ambience",
    "environment",
    "silence",
    "other",
]


def infer_attention_category(focus_target: str) -> AttentionCategory:
    """Infers attention category from focus target string heuristics."""
    t = (focus_target or "").lower().strip()
    if not t:
        return "other"
    if t in ("silence", "pause", "stillness", "breath_pause", "negative_space"):
        return "silence"
    if any(k in t for k in ("narrator", "dialogue", "whisper", "speech", "shout", "line", "voice", "monologue")):
        return "dialogue"
    if any(k in t for k in ("music", "score", "bgm", "leitmotif", "theme", "orchestra", "melody", "revelation")):
        return "music"
    if any(k in t for k in ("ambience", "room_tone", "weather", "wind", "rain", "storm", "bed", "atmosphere")):
        return "ambience"
    if any(k in t for k in ("door", "sword", "blade", "impact", "crash", "strike", "footstep", "foley", "sfx", "punch", "explosion")):
        return "fx"
    if any(k in t for k in ("environment", "ocean", "forest", "city", "tavern_crowd", "walla")):
        return "environment"
    return "other"


class AttentionEvent(BaseModel):
    """
    An individual timed listener attention event.
    Declares the narrative focus target and attention priority for a specific time window.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    start: float = Field(
        ...,
        ge=0.0,
        validation_alias=AliasChoices("start", "start_sec", "start_time"),
        description="Timeline start offset in seconds (>= 0.0)",
    )
    end: float = Field(
        ...,
        validation_alias=AliasChoices("end", "end_sec", "end_time"),
        description="Timeline end offset in seconds (must be > start)",
    )
    focus_target: str = Field(
        ...,
        description="Target commanding listener attention (e.g. 'narrator', 'door', 'whisper', 'silence', 'music')",
    )
    priority: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Attention priority weight [0.0, 1.0] (0.0 = irrelevant, 1.0 = absolute focus)",
    )
    reason: str = Field(
        default="",
        validation_alias=AliasChoices("reason", "context", "dramatic_reason"),
        description="Narrative rationale or context explaining why attention is focused here",
    )
    category: Optional[AttentionCategory] = Field(
        default=None,
        description="High-level attention category (dialogue, music, fx, ambience, environment, silence, other)",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary event-level metadata",
    )

    @field_validator("focus_target", mode="before")
    @classmethod
    def validate_focus_target(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError(f"focus_target must be a string, got {type(v).__name__}")
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("focus_target cannot be empty")
        return cleaned

    @field_validator("priority", mode="before")
    @classmethod
    def validate_priority(cls, v: Any) -> float:
        try:
            val = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"priority must be numeric, got {v}")
        if not (0.0 <= val <= 1.0):
            raise ValueError(f"priority must be within [0.0, 1.0], got {val}")
        return round(val, 4)

    @field_validator("start", mode="before")
    @classmethod
    def validate_start(cls, v: Any) -> float:
        try:
            val = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"start must be numeric, got {v}")
        if val < 0.0:
            raise ValueError(f"start timestamp cannot be negative, got {val}")
        return round(val, 4)

    @field_validator("end", mode="before")
    @classmethod
    def validate_end(cls, v: Any) -> float:
        try:
            val = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"end must be numeric, got {v}")
        return round(val, 4)

    @model_validator(mode="after")
    def validate_time_bounds_and_category(self) -> AttentionEvent:
        if self.end <= self.start:
            raise ValueError(
                f"end time ({self.end}s) must be strictly greater than start time ({self.start}s)"
            )
        if self.category is None:
            object.__setattr__(self, "category", infer_attention_category(self.focus_target))
        return self

    @property
    def duration_sec(self) -> float:
        """Duration of the attention event in seconds."""
        return round(self.end - self.start, 4)

    @property
    def start_ms(self) -> int:
        """Timeline start in milliseconds."""
        return int(round(self.start * 1000.0))

    @property
    def end_ms(self) -> int:
        """Timeline end in milliseconds."""
        return int(round(self.end * 1000.0))

    @property
    def duration_ms(self) -> int:
        """Timeline duration in milliseconds."""
        return int(round(self.duration_sec * 1000.0))

    def contains(self, timestamp_sec: float) -> bool:
        """Checks if a given timestamp falls within this event window."""
        return self.start <= timestamp_sec <= self.end

    def to_dict(self) -> Dict[str, Any]:
        """Serializes event to dictionary."""
        return self.model_dump(mode="json")


class AttentionMap(BaseModel):
    """
    Time-aware listener attention map for a scene or chapter.
    Holds chronologically and priority-ordered AttentionEvents with deterministic resolution.
    Supports overlapping events and resolves dominant focus deterministically.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    scene_id: Optional[str] = Field(default=None, description="Associated scene identifier")
    chapter_id: Optional[str] = Field(default=None, description="Associated chapter identifier")
    total_duration_sec: Optional[float] = Field(default=None, ge=0.0, description="Total scene duration in seconds")
    events: List[AttentionEvent] = Field(default_factory=list, description="Ordered timed attention events")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary attention metadata")

    @model_validator(mode="after")
    def sort_events_deterministically(self) -> AttentionMap:
        """
        Guarantees deterministic event ordering:
        Primary: start time (ascending)
        Secondary: end time (ascending)
        Tertiary: priority (descending, so highest priority is inspected first)
        Quaternary: focus_target (alphabetical)
        Quinary: reason (alphabetical)
        """
        sorted_ev = sorted(
            self.events,
            key=lambda e: (e.start, e.end, -e.priority, e.focus_target, e.reason),
        )
        object.__setattr__(self, "events", sorted_ev)
        if self.total_duration_sec is None and self.events:
            object.__setattr__(self, "total_duration_sec", max(e.end for e in self.events))
        return self

    def add_event(self, event: Union[AttentionEvent, Dict[str, Any]]) -> AttentionEvent:
        """Adds an event and re-sorts deterministically."""
        if isinstance(event, dict):
            ev = AttentionEvent.model_validate(event)
        elif isinstance(event, AttentionEvent):
            ev = event
        else:
            raise TypeError(f"Expected AttentionEvent or dict, got {type(event).__name__}")

        self.events.append(ev)
        self.events = sorted(
            self.events,
            key=lambda e: (e.start, e.end, -e.priority, e.focus_target, e.reason),
        )
        if self.total_duration_sec is not None:
            self.total_duration_sec = max(self.total_duration_sec, ev.end)
        else:
            self.total_duration_sec = ev.end
        return ev

    def get_active_events(self, timestamp_sec: float) -> List[AttentionEvent]:
        """
        Returns all attention events active at timestamp_sec.
        Ordered by priority descending (highest priority first).
        """
        t = round(float(timestamp_sec), 4)
        active = [e for e in self.events if e.start <= t <= e.end]
        return sorted(
            active,
            key=lambda e: (-e.priority, -e.start, e.duration_sec, e.focus_target),
        )

    def get_dominant_event(self, timestamp_sec: float) -> Optional[AttentionEvent]:
        """
        Deterministically resolves the single dominant attention event at timestamp_sec.
        Tie-breaking rule:
        1. Priority (highest)
        2. Start time (most recent event captures attention)
        3. Duration (shorter transient focus takes precedence over long bed)
        4. Focus target (alphabetical for strict determinism)
        """
        active = self.get_active_events(timestamp_sec)
        if not active:
            return None
        return active[0]

    def get_dominant_target_at(self, timestamp_sec: float) -> Optional[str]:
        """Convenience method returning the dominant focus target name at timestamp_sec."""
        dom = self.get_dominant_event(timestamp_sec)
        return dom.focus_target if dom else None

    def resolve_windows(self) -> List[Tuple[float, float, AttentionEvent]]:
        """
        Resolves the continuous timeline into discrete non-overlapping windows
        with their dominant AttentionEvent.
        """
        if not self.events:
            return []

        # Collect all critical boundary timestamps
        timestamps: Set[float] = set()
        for e in self.events:
            timestamps.add(e.start)
            timestamps.add(e.end)
        sorted_times = sorted(timestamps)

        windows: List[Tuple[float, float, AttentionEvent]] = []
        for i in range(len(sorted_times) - 1):
            t_start = sorted_times[i]
            t_end = sorted_times[i + 1]
            if t_end <= t_start:
                continue
            # Sample midpoint
            t_mid = (t_start + t_end) / 2.0
            dom = self.get_dominant_event(t_mid)
            if dom is not None:
                # Merge consecutive windows with same dominant event
                if windows and windows[-1][2] == dom and abs(windows[-1][1] - t_start) < 1e-4:
                    prev_s, _, prev_ev = windows[-1]
                    windows[-1] = (prev_s, t_end, prev_ev)
                else:
                    windows.append((t_start, t_end, dom))
        return windows

    def fingerprint(self) -> str:
        """Deterministic SHA-256 fingerprint of the attention map."""
        payload = self.model_dump_json(indent=None)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Serializes AttentionMap to dictionary."""
        return self.model_dump(mode="json")

    def to_json(self, indent: int = 2) -> str:
        """Serializes AttentionMap to JSON string deterministically."""
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AttentionMap:
        """Constructs AttentionMap from dictionary."""
        return cls.model_validate(data)

    @classmethod
    def from_json(cls, json_str: str) -> AttentionMap:
        """Constructs AttentionMap from JSON string."""
        return cls.model_validate_json(json_str)

    @classmethod
    def from_events(
        cls,
        events: List[Union[AttentionEvent, Dict[str, Any]]],
        scene_id: Optional[str] = None,
        chapter_id: Optional[str] = None,
        total_duration_sec: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AttentionMap:
        """Factory method to construct AttentionMap from a list of events."""
        parsed_events: List[AttentionEvent] = []
        for e in events:
            if isinstance(e, dict):
                parsed_events.append(AttentionEvent.model_validate(e))
            elif isinstance(e, AttentionEvent):
                parsed_events.append(e)
            else:
                raise TypeError(f"Invalid event element: {type(e).__name__}")

        return cls(
            scene_id=scene_id,
            chapter_id=chapter_id,
            total_duration_sec=total_duration_sec,
            events=parsed_events,
            metadata=metadata or {},
        )

    @classmethod
    def from_sound_timeline(cls, timeline: Any, scene_id: Optional[str] = None) -> AttentionMap:
        """
        Adapts a Stage 10 SoundTimeline into a Stage 11 AttentionMap.
        Maps priority keywords (CRITICAL, HIGH, MEDIUM, LOW, TEXTURE) to normalized floats.
        """
        if hasattr(timeline, "model_dump"):
            tl_dict = timeline.model_dump()
        elif isinstance(timeline, dict):
            tl_dict = timeline
        else:
            tl_dict = getattr(timeline, "__dict__", {})

        prio_map = {
            "CRITICAL": 1.00,
            "HIGH": 0.85,
            "MEDIUM": 0.60,
            "LOW": 0.35,
            "TEXTURE": 0.15,
        }

        raw_events = tl_dict.get("events", [])
        att_events: List[AttentionEvent] = []

        for rev in raw_events:
            s_ms = float(rev.get("start_ms", 0) or 0)
            d_ms = float(rev.get("duration_ms", 0) or 0)
            if d_ms <= 0:
                d_ms = 500.0  # Safe minimum transient duration
            s_sec = round(s_ms / 1000.0, 4)
            e_sec = round((s_ms + d_ms) / 1000.0, 4)
            cat = str(rev.get("category", "other"))
            raw_prio = rev.get("priority", "MEDIUM")
            prio = prio_map.get(raw_prio, 0.60) if isinstance(raw_prio, str) else float(raw_prio)

            target = rev.get("asset_name") or cat.lower()
            reason = rev.get("decision_reason") or rev.get("dramatic_purpose") or f"{cat} cue"

            att_events.append(
                AttentionEvent(
                    start=s_sec,
                    end=e_sec,
                    focus_target=str(target),
                    priority=prio,
                    reason=str(reason),
                    metadata={"source_event_id": rev.get("event_id")},
                )
            )

        tot_dur = float(tl_dict.get("total_duration_ms", 0) or 0) / 1000.0
        return cls(
            scene_id=scene_id or tl_dict.get("scene_id"),
            chapter_id=tl_dict.get("chapter_id"),
            total_duration_sec=tot_dur if tot_dur > 0 else None,
            events=att_events,
            metadata={"source": "SoundTimeline"},
        )
