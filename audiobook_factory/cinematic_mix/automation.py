#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Module: automation.py
Defines the typed MixAutomation and AutomationEvent data models.
Captures time-varying mixing parameter curves (gain, ducking, pan, stereo_width, eq_depth)
independent of the underlying DSP execution engine.
"""

from __future__ import annotations
import hashlib
import json
from typing import Dict, Any, List, Optional, Literal, Union, get_args
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ConfigDict,
    AliasChoices,
)

from audiobook_factory.cinematic_mix.curves import evaluate_curve, CurveType, ALLOWED_CURVES


StemTarget = Literal["DX", "MX", "FX", "AMB", "ME", "master"]
ALLOWED_TARGETS = set(get_args(StemTarget))

AutomationParameter = Literal[
    "gain",
    "ducking",
    "pan",
    "stereo_width",
    "eq_depth",
    "lowpass_cutoff",
    "reverb_send",
    "room_send",
    "direct_reverb_ratio",
]
ALLOWED_PARAMETERS = set(get_args(AutomationParameter))

AutomationHierarchy = Literal[
    "BASE_SCENE",
    "SCENE_INTENT",
    "ATTENTION_PROTECTION",
    "CINEMATIC_BEHAVIOR",
    "MOMENTARY_EVENT",
    "SAFETY_LIMIT",
]

HIERARCHY_LEVELS: Dict[str, int] = {
    "BASE_SCENE": 10,
    "SCENE_INTENT": 20,
    "ATTENTION_PROTECTION": 30,
    "CINEMATIC_BEHAVIOR": 35,
    "MOMENTARY_EVENT": 40,
    "SAFETY_LIMIT": 50,
}

# Safety Limits
SAFETY_LIMIT_MIN_GAIN_DB = -36.0
SAFETY_LIMIT_MAX_GAIN_DB = 6.0
SAFETY_LIMIT_MAX_NOTCH_DB = -9.0


def normalize_stem_target(target: str) -> StemTarget:
    """Normalizes target string to canonical StemTarget literal."""
    t = (target or "").strip().lower()
    if t in ("dx", "dialogue", "vocal", "speech", "narrator"):
        return "DX"
    if t in ("mx", "music", "score", "bgm", "underscore"):
        return "MX"
    if t in ("fx", "foley", "sfx", "effects", "transient"):
        return "FX"
    if t in ("amb", "ambience", "environment", "room", "bed"):
        return "AMB"
    if t in ("me", "music_and_effects", "submix"):
        return "ME"
    if t in ("master", "premaster", "cinematic_mix_premaster", "full_master"):
        return "master"
    raise ValueError(f"Unknown stem target '{target}'. Allowed: {sorted(ALLOWED_TARGETS)}")


class AutomationEvent(BaseModel):
    """
    An individual mixing automation event representing a continuous parameter change.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    start: float = Field(
        ...,
        ge=0.0,
        validation_alias=AliasChoices("start", "start_sec"),
        description="Timeline start offset in seconds (>= 0.0)",
    )
    end: float = Field(
        ...,
        validation_alias=AliasChoices("end", "end_sec"),
        description="Timeline end offset in seconds (must be > start)",
    )
    target: StemTarget = Field(
        ...,
        description="Target stem: DX, MX, FX, AMB, ME, master",
    )
    parameter: AutomationParameter = Field(
        ...,
        description="Mixing parameter: gain, ducking, pan, stereo_width, eq_depth, reverb_send, direct_reverb_ratio",
    )
    value: float = Field(
        ...,
        description="Target parameter value at the end of the transition (e.g. -6.0 dB gain, 0.0 pan)",
    )
    start_value: Optional[float] = Field(
        default=None,
        description="Value at start of transition; if None, defaults to baseline (0.0 for gain/pan)",
    )
    curve: CurveType = Field(
        default="smooth",
        description="Interpolation curve: linear, ease_in, ease_out, smooth",
    )
    priority: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Priority weight [0.0, 1.0]",
    )
    hierarchy: AutomationHierarchy = Field(
        default="ATTENTION_PROTECTION",
        description="Hierarchy tier: BASE_SCENE, SCENE_INTENT, ATTENTION_PROTECTION, MOMENTARY_EVENT, SAFETY_LIMIT",
    )
    reason: str = Field(
        default="",
        description="Directorial or narrative reason for this automation change",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary automation metadata",
    )

    @field_validator("target", mode="before")
    @classmethod
    def validate_target(cls, v: Any) -> StemTarget:
        if not isinstance(v, str):
            raise ValueError(f"target must be a string, got {type(v).__name__}")
        return normalize_stem_target(v)

    @field_validator("parameter", mode="before")
    @classmethod
    def validate_parameter(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError(f"parameter must be a string, got {type(v).__name__}")
        p = v.strip().lower()
        if p not in ALLOWED_PARAMETERS:
            raise ValueError(f"Invalid parameter '{v}'. Allowed: {sorted(ALLOWED_PARAMETERS)}")
        return p

    @field_validator("curve", mode="before")
    @classmethod
    def validate_curve(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError(f"curve must be a string, got {type(v).__name__}")
        c = v.strip().lower()
        if c not in ALLOWED_CURVES:
            raise ValueError(f"Invalid curve '{v}'. Allowed: {sorted(ALLOWED_CURVES)}")
        return c

    @field_validator("start", mode="before")
    @classmethod
    def validate_start(cls, v: Any) -> float:
        try:
            val = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"start must be numeric, got {v}")
        if val < 0.0:
            raise ValueError(f"start cannot be negative, got {val}")
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
    def validate_event_bounds(self) -> AutomationEvent:
        if self.end <= self.start:
            raise ValueError(f"end ({self.end}s) must be strictly greater than start ({self.start}s)")

        # Clamp parameter-specific physical bounds to prevent renderer clipping/overflow
        if self.parameter in ("gain", "ducking"):
            if self.value < SAFETY_LIMIT_MIN_GAIN_DB or self.value > SAFETY_LIMIT_MAX_GAIN_DB:
                object.__setattr__(self, "value", max(SAFETY_LIMIT_MIN_GAIN_DB, min(SAFETY_LIMIT_MAX_GAIN_DB, self.value)))
        elif self.parameter == "pan":
            if self.value < -0.80 or self.value > 0.80:
                object.__setattr__(self, "value", max(-0.80, min(0.80, self.value)))
        elif self.parameter == "stereo_width":
            if self.value < 0.0 or self.value > 2.0:
                object.__setattr__(self, "value", max(0.0, min(2.0, self.value)))
        elif self.parameter == "eq_depth":
            if self.value < SAFETY_LIMIT_MAX_NOTCH_DB or self.value > 0.0:
                object.__setattr__(self, "value", max(SAFETY_LIMIT_MAX_NOTCH_DB, min(0.0, self.value)))
        elif self.parameter == "lowpass_cutoff":
            if self.value < 200.0 or self.value > 20000.0:
                object.__setattr__(self, "value", max(200.0, min(20000.0, self.value)))
        elif self.parameter in ("reverb_send", "room_send", "direct_reverb_ratio"):
            if self.value < 0.0 or self.value > 1.0:
                object.__setattr__(self, "value", max(0.0, min(1.0, self.value)))
        return self

    @property
    def duration(self) -> float:
        """Alias for duration in seconds."""
        return self.duration_sec

    @property
    def duration_sec(self) -> float:
        """Duration of the automation event in seconds."""
        return round(self.end - self.start, 4)

    @property
    def hierarchy_level(self) -> int:
        """Integer priority level for conflict resolution."""
        return HIERARCHY_LEVELS.get(self.hierarchy, 30)

    def evaluate(self, t: float, baseline: float = 0.0) -> float:
        """
        Evaluates parameter value at time t using the assigned curve.
        """
        st_val = self.start_value if self.start_value is not None else baseline
        return evaluate_curve(self.start, self.end, st_val, self.value, self.curve, t)

    def contains(self, t: float) -> bool:
        """Checks if timestamp t falls inside this event window."""
        return self.start <= t <= self.end

    def to_dict(self) -> Dict[str, Any]:
        """Serializes event to dictionary."""
        return self.model_dump(mode="json")


class MixAutomation(BaseModel):
    """
    Stage 11 Mix Automation Timeline.
    Contains ordered AutomationEvents, conflict resolution rules, and an inspectable decision trace.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    scene_id: Optional[str] = Field(default=None, description="Optional scene identifier")
    chapter_id: Optional[str] = Field(default=None, description="Optional chapter identifier")
    total_duration_sec: Optional[float] = Field(default=None, ge=0.0, description="Total scene duration in seconds")
    events: List[AutomationEvent] = Field(default_factory=list, description="List of automation events")
    decision_trace: List[Dict[str, Any]] = Field(default_factory=list, description="Inspectable decision audit trace")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary automation metadata")

    @property
    def decisions(self) -> List[Dict[str, Any]]:
        """Alias for inspectable decision trace."""
        return self.decision_trace

    @model_validator(mode="after")
    def sort_events_deterministically(self) -> MixAutomation:
        """
        Sorts events deterministically:
        Primary: start time (ascending)
        Secondary: end time (ascending)
        Tertiary: hierarchy level (descending)
        Quaternary: priority (descending)
        Quinary: target + parameter (alphabetical)
        """
        sorted_ev = sorted(
            self.events,
            key=lambda e: (
                round(e.start, 4),
                round(e.end, 4),
                -e.hierarchy_level,
                -round(e.priority, 4),
                e.target,
                e.parameter,
                e.reason,
            ),
        )
        object.__setattr__(self, "events", sorted_ev)
        if self.total_duration_sec is None and self.events:
            object.__setattr__(self, "total_duration_sec", max(e.end for e in self.events))
        return self

    def add_event(self, event: Union[AutomationEvent, Dict[str, Any]]) -> AutomationEvent:
        """Adds an automation event and re-sorts deterministically."""
        if isinstance(event, dict):
            ev = AutomationEvent.model_validate(event)
        elif isinstance(event, AutomationEvent):
            ev = event
        else:
            raise TypeError(f"Expected AutomationEvent or dict, got {type(event).__name__}")

        self.events.append(ev)
        sorted_ev = sorted(
            self.events,
            key=lambda e: (
                round(e.start, 4),
                round(e.end, 4),
                -e.hierarchy_level,
                -round(e.priority, 4),
                e.target,
                e.parameter,
                e.reason,
            ),
        )
        object.__setattr__(self, "events", sorted_ev)
        if self.total_duration_sec is not None:
            object.__setattr__(self, "total_duration_sec", max(self.total_duration_sec, ev.end))
        else:
            object.__setattr__(self, "total_duration_sec", ev.end)
        return ev

    def record_decision(
        self,
        time: float,
        focus: str,
        target: str,
        parameter: str,
        before: float,
        after: float,
        reason: str,
        source: str = "attention_map",
        priority: float = 0.5,
        **extra: Any,
    ) -> None:
        """
        Records an inspectable entry in the Stage 11 decision trace.
        """
        entry = {
            "time": round(float(time), 4),
            "focus": str(focus),
            "target": normalize_stem_target(target),
            "parameter": str(parameter),
            "before": round(float(before), 2),
            "after": round(float(after), 2),
            "reason": str(reason),
            "source": str(source),
            "priority": round(float(priority), 4),
        }
        entry.update(extra)
        self.decision_trace.append(entry)

    def get_events_for_target(
        self, target: str, parameter: Optional[str] = None
    ) -> List[AutomationEvent]:
        """Returns all automation events matching target stem and optional parameter."""
        norm_target = normalize_stem_target(target)
        norm_param = parameter.strip().lower() if parameter else None
        return [
            e for e in self.events
            if e.target == norm_target and (norm_param is None or e.parameter == norm_param)
        ]

    def evaluate_parameter(
        self,
        target: str,
        parameter: str,
        t: float,
        baseline: float = 0.0,
    ) -> float:
        """
        Deterministically evaluates the composite parameter value at time t
        for a specific target stem and parameter, resolving overlapping conflicts
        according to the Section 10/11 Priority Hierarchy Policy.

        Policy:
        - Gain / Ducking:
          When multiple attenuation events overlap, the deepest required attenuation
          dominates, bounded by SAFETY_LIMIT_MIN_GAIN_DB (-36.0 dB).
          A momentary event overrides sustained protection during its duration.
        - EQ Depth:
          Deepest notch wins, bounded by SAFETY_LIMIT_MAX_NOTCH_DB (-9.0 dB).
        - Pan / Stereo Width / Reverb Send:
          Highest hierarchy tier wins; ties broken by highest priority.
        """
        norm_target = normalize_stem_target(target)
        norm_param = parameter.strip().lower()
        active = [
            e for e in self.events
            if e.target == norm_target and e.parameter == norm_param and e.contains(t)
        ]

        if not active:
            return baseline

        # Sort active events by hierarchy level descending, then priority descending
        active.sort(key=lambda e: (-e.hierarchy_level, -e.priority))

        if norm_param in ("gain", "ducking"):
            # Bounded attenuation composition
            eval_values = [e.evaluate(t, baseline=baseline) for e in active]
            # Deepest attenuation wins, protected by safety floor
            min_gain = min(eval_values)
            return round(max(SAFETY_LIMIT_MIN_GAIN_DB, min_gain), 4)

        elif norm_param == "eq_depth":
            # Deepest notch wins, protected by safe maximum notch depth
            eval_values = [e.evaluate(t, baseline=baseline) for e in active]
            min_notch = min(eval_values)
            return round(max(SAFETY_LIMIT_MAX_NOTCH_DB, min_notch), 4)

        elif norm_param == "lowpass_cutoff":
            # Lowest cutoff frequency (most aggressive occlusion/muffling) dominates
            eval_values = [e.evaluate(t, baseline=baseline or 18000.0) for e in active]
            min_cutoff = min(eval_values)
            return round(max(200.0, min_cutoff), 1)

        else:
            # Pan, stereo width, sends: top hierarchy / top priority event determines value
            top_event = active[0]
            return round(top_event.evaluate(t, baseline=baseline), 4)

    def fingerprint(self) -> str:
        """Computes a deterministic SHA-256 fingerprint for this mix automation timeline."""
        payload = self.model_dump_json(indent=None)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Serializes automation to a dictionary."""
        return self.model_dump(mode="json")

    def to_json(self, indent: int = 2) -> str:
        """Serializes automation to JSON deterministically."""
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MixAutomation:
        """Constructs MixAutomation from dictionary."""
        return cls.model_validate(data)

    @classmethod
    def from_json(cls, json_str: str) -> MixAutomation:
        """Constructs MixAutomation from JSON string."""
        return cls.model_validate_json(json_str)
