#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Module: impact.py
Impact Director: Models visceral cinematic events across 4 distinct phases:
PRE_IMPACT, IMPACT, AFTERMATH, and RECOVERY.
Coordinates temporary focus shifts without destructively mutating the underlying AttentionMap.
"""

from __future__ import annotations
import math
from typing import Dict, Any, List, Optional, Literal, Union, get_args
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from audiobook_factory.cinematic_mix.automation import (
    AutomationEvent,
    AutomationHierarchy,
)
from audiobook_factory.cinematic_mix.attention_map import AttentionMap, AttentionEvent


ImpactPhase = Literal["PRE_IMPACT", "IMPACT", "AFTERMATH", "RECOVERY"]


class ImpactEvent(BaseModel):
    """
    Typed definition of a major cinematic impact or transient event.
    Models the complete physical trajectory from pre-impact tension to aftermath recovery.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    start: float = Field(..., ge=0.0, description="Timestamp of the impact hit transient in seconds")
    pre_impact_duration: float = Field(
        default=0.20,
        ge=0.0,
        le=2.0,
        description="Pre-impact anticipation duration in seconds",
    )
    impact_duration: float = Field(
        default=0.15,
        gt=0.01,
        le=1.5,
        description="Peak transient slam duration in seconds",
    )
    aftermath_duration: float = Field(
        default=0.60,
        ge=0.0,
        le=5.0,
        description="Acoustic aftermath and ring-out duration in seconds",
    )
    recovery_duration: float = Field(
        default=0.80,
        ge=0.05,
        le=10.0,
        description="Gradual return to baseline mix duration in seconds",
    )
    intensity: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Normalized impact intensity [0.0 = subtle, 1.0 = massive explosion]",
    )
    focus_target: str = Field(
        default="fx",
        description="Impact focus cue (e.g. 'door_slam', 'explosion', 'sword_parry')",
    )
    duck_targets: List[str] = Field(
        default_factory=lambda: ["MX", "AMB"],
        description="Competing stems to duck during impact transient",
    )
    preserve_targets: List[str] = Field(
        default_factory=lambda: ["DX"],
        description="Stems protected from impact ducking (e.g. speech)",
    )
    reason: str = Field(
        default="Visceral transient impact",
        description="Inspectable artistic rationale",
    )

    @property
    def total_duration_sec(self) -> float:
        """Total temporal span from pre-impact start to recovery end."""
        return round(
            self.pre_impact_duration + self.impact_duration + self.aftermath_duration + self.recovery_duration,
            4,
        )

    @property
    def pre_impact_start(self) -> float:
        return max(0.0, round(self.start - self.pre_impact_duration, 4))

    @property
    def impact_start(self) -> float:
        return round(self.start, 4)

    @property
    def aftermath_start(self) -> float:
        return round(self.start + self.impact_duration, 4)

    @property
    def recovery_start(self) -> float:
        return round(self.start + self.impact_duration + self.aftermath_duration, 4)

    @property
    def recovery_end(self) -> float:
        return round(self.recovery_start + self.recovery_duration, 4)


class ImpactDirector:
    """
    Directs cinematic impact behavior across 4 phases.
    Ducks competing beds, protects dialogue, and manages smooth acoustic recovery.
    """

    def __init__(self, max_duck_db: float = -14.0):
        self.max_duck_db = max_duck_db

    def plan_impact(
        self,
        event: ImpactEvent,
        total_duration_sec: Optional[float] = None,
    ) -> List[AutomationEvent]:
        """
        Translates an ImpactEvent into 4-phase automation events for competing stems.
        """
        if event.intensity <= 0.05:
            return []

        events: List[AutomationEvent] = []
        i = event.intensity

        # Compute dynamic ducking depths based on intensity
        # Peak impact attenuation: e.g. -6 dB (mild) up to -14 dB (extreme)
        peak_duck_db = round(self.max_duck_db * i, 2)
        # Pre-impact anticipation dip: subtle (-1.5 to -3.5 dB)
        pre_duck_db = round(-3.5 * i, 2)
        # Aftermath tail attenuation: half of peak (-3 to -7 dB)
        aftermath_duck_db = round(peak_duck_db * 0.5, 2)

        # 1. Pre-Impact Phase (Anticipation)
        if event.pre_impact_duration > 0.05:
            for stem in event.duck_targets:
                events.append(
                    AutomationEvent(
                        start=event.pre_impact_start,
                        end=event.impact_start,
                        target=stem,
                        parameter="gain",
                        value=pre_duck_db,
                        start_value=0.0,
                        curve="smooth",
                        priority=0.82,
                        hierarchy="CINEMATIC_BEHAVIOR",
                        reason=f"Impact Pre-Anticipation: {event.reason}",
                        metadata={"phase": "PRE_IMPACT", "intensity": i},
                    )
                )

        # 2. Impact Phase (Peak Transient Slam)
        for stem in event.duck_targets:
            events.append(
                AutomationEvent(
                    start=event.impact_start,
                    end=event.aftermath_start,
                    target=stem,
                    parameter="gain",
                    value=peak_duck_db,
                    start_value=pre_duck_db if event.pre_impact_duration > 0.05 else 0.0,
                    curve="smooth",
                    priority=0.92,
                    hierarchy="MOMENTARY_EVENT",
                    reason=f"Impact Transient Slam: {event.reason} ({event.focus_target})",
                    metadata={"phase": "IMPACT", "intensity": i, "focus": event.focus_target},
                )
            )

        # 3. Aftermath Phase (Ring-Out & Room Decay)
        if event.aftermath_duration > 0.05:
            for stem in event.duck_targets:
                events.append(
                    AutomationEvent(
                        start=event.aftermath_start,
                        end=event.recovery_start,
                        target=stem,
                        parameter="gain",
                        value=aftermath_duck_db,
                        start_value=peak_duck_db,
                        curve="smooth",
                        priority=0.80,
                        hierarchy="CINEMATIC_BEHAVIOR",
                        reason=f"Impact Aftermath: {event.reason}",
                        metadata={"phase": "AFTERMATH", "intensity": i},
                    )
                )

        # 4. Recovery Phase (Gradual Return to Baseline)
        for stem in event.duck_targets:
            events.append(
                AutomationEvent(
                    start=event.recovery_start,
                    end=event.recovery_end,
                    target=stem,
                    parameter="gain",
                    value=0.0,
                    start_value=aftermath_duck_db if event.aftermath_duration > 0.05 else peak_duck_db,
                    curve="smooth",
                    priority=0.75,
                    hierarchy="CINEMATIC_BEHAVIOR",
                    reason=f"Impact Recovery to Baseline: {event.reason}",
                    metadata={"phase": "RECOVERY", "intensity": i},
                )
            )

        return events

    def derive_attention_shift(
        self,
        base_attention: AttentionMap,
        impact_events: List[ImpactEvent],
    ) -> AttentionMap:
        """
        Derives a non-destructive attention overlay incorporating impact transients.
        The original AttentionMap is NOT mutated.
        """
        derived_events = list(base_attention.events)
        for imp in impact_events:
            if imp.intensity > 0.20:
                # Add temporary dominant attention window during impact transient
                derived_events.append(
                    AttentionEvent(
                        start=imp.impact_start,
                        end=imp.aftermath_start,
                        focus_target=imp.focus_target,
                        priority=min(1.0, 0.70 + (imp.intensity * 0.30)),
                        reason=f"Impact Focus Shift: {imp.reason}",
                    )
                )
        return AttentionMap(
            chapter_id=base_attention.chapter_id,
            scene_id=base_attention.scene_id,
            total_duration_sec=base_attention.total_duration_sec,
            events=derived_events,
            metadata=dict(base_attention.metadata),
        )
