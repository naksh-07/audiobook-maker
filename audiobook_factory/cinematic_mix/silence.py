#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Module: silence.py
Silence Director: Treats silence as an active dramatic narrative instrument.
Supports non-destructive negative sound design, preserved room tone/breath,
and continuous smooth approach/release transitions.
"""

from __future__ import annotations
import math
from typing import Dict, Any, List, Optional, Literal, Union, get_args
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from audiobook_factory.cinematic_mix.automation import (
    AutomationEvent,
    AutomationHierarchy,
)


SilenceType = Literal["NONE", "DRAMATIC", "SUSPENSE", "SHOCK", "EMOTIONAL", "TRANSITION"]
SilenceDepth = Literal["light", "moderate", "deep", "near_black"]

SILENCE_DEPTH_DB: Dict[str, float] = {
    "light": -6.0,
    "moderate": -12.0,
    "deep": -20.0,
    "near_black": -32.0,
}


class SilenceEvent(BaseModel):
    """
    Typed narrative silence event definition.
    Specifies start offset, duration, dramatic role, and preserved acoustic elements.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    start: float = Field(..., ge=0.0, description="Start timestamp in seconds")
    duration: float = Field(..., gt=0.0, description="Hold duration in seconds")
    type: SilenceType = Field(default="DRAMATIC", description="Dramatic nature of the silence")
    depth: Union[SilenceDepth, float] = Field(
        default="deep",
        description="Depth category ('light', 'moderate', 'deep', 'near_black') or negative dB float",
    )
    preserved_elements: List[str] = Field(
        default_factory=lambda: ["room_tone"],
        description="Stems or elements preserved during silence (e.g. 'room_tone', 'breath', 'fx_tail')",
    )
    fade_in: float = Field(
        default=0.25,
        ge=0.02,
        le=5.0,
        description="Approach duration into silence floor in seconds",
    )
    fade_out: float = Field(
        default=0.35,
        ge=0.02,
        le=5.0,
        description="Release recovery duration back to baseline in seconds",
    )
    reason: str = Field(
        default="Dramatic narrative pause",
        description="Inspectable artistic rationale",
    )

    @property
    def end(self) -> float:
        """Total window end including release transition."""
        return round(self.start + self.duration + self.fade_out, 4)

    @property
    def depth_db(self) -> float:
        """Resolves target attenuation depth in dB."""
        if isinstance(self.depth, (int, float)):
            return float(self.depth)
        d_norm = str(self.depth).lower().strip()
        return SILENCE_DEPTH_DB.get(d_norm, -20.0)


class SilenceDirector:
    """
    Directs intentional negative sound design and narrative absence.
    Emits continuous, smooth automation envelopes that preserve room tone and breath.
    """

    def __init__(self, default_fade_in: float = 0.25, default_fade_out: float = 0.35):
        self.default_fade_in = default_fade_in
        self.default_fade_out = default_fade_out

    def plan_silence(
        self,
        event: SilenceEvent,
        total_duration_sec: Optional[float] = None,
    ) -> List[AutomationEvent]:
        """
        Translates a SilenceEvent into discrete stem automation envelopes.
        """
        if event.type == "NONE" or abs(event.depth_db) < 0.2:
            return []

        events: List[AutomationEvent] = []
        base_depth = event.depth_db
        s_type = event.type.upper()
        preserved = {p.lower() for p in event.preserved_elements}

        # Multi-Stem Attenuation Matrix by Silence Type
        if s_type == "DRAMATIC":
            # Dramatic pause: music plunges, FX drops, ambience slightly preserved
            mx_cut = base_depth
            fx_cut = max(-16.0, base_depth + 6.0)
            amb_cut = -5.0 if "room_tone" in preserved else max(-12.0, base_depth + 10.0)
            dx_cut = 0.0 if "breath" in preserved else -12.0

        elif s_type == "SUSPENSE":
            # Suspense: music thins out, ambience lowers, but spot FX remain razor sharp
            mx_cut = max(-18.0, base_depth + 4.0)
            fx_cut = 0.0 if "fx" in preserved or "fx_tail" in preserved else -3.0
            amb_cut = -6.0 if "room_tone" in preserved else -14.0
            dx_cut = 0.0

        elif s_type == "SHOCK":
            # Shock / Ear-ring: everything drops near-black, leaving only ring/tail
            mx_cut = min(-24.0, base_depth - 4.0)
            fx_cut = 0.0 if "fx_tail" in preserved else -18.0
            amb_cut = -12.0 if "room_tone" in preserved else -26.0
            dx_cut = -20.0

        elif s_type == "EMOTIONAL":
            # Emotional moment: gentle dip, intimate breath and room warmth preserved
            mx_cut = max(-12.0, base_depth + 8.0)
            fx_cut = -6.0
            amb_cut = -3.5 if "room_tone" in preserved else -8.0
            dx_cut = 0.0  # Dialogue/breath always pristine

        elif s_type == "TRANSITION":
            # Scene boundary crossfade dip
            mx_cut = base_depth
            fx_cut = base_depth
            amb_cut = max(-10.0, base_depth + 6.0) if "room_tone" in preserved else base_depth
            dx_cut = base_depth

        else:
            mx_cut = base_depth
            fx_cut = base_depth
            amb_cut = -4.0 if "room_tone" in preserved else base_depth
            dx_cut = 0.0

        # Timing envelopes: 3-stage approach -> floor -> release
        t_app_start = max(0.0, event.start - event.fade_in)
        t_app_end = event.start
        t_floor_start = event.start
        t_floor_end = event.start + event.duration
        t_rel_start = t_floor_end
        t_rel_end = t_floor_end + event.fade_out

        targets = [("MX", mx_cut), ("FX", fx_cut), ("AMB", amb_cut)]
        if dx_cut < -0.2:
            targets.append(("DX", dx_cut))

        hier = "MOMENTARY_EVENT" if s_type == "SHOCK" else "CINEMATIC_BEHAVIOR"

        for target_stem, cut_db in targets:
            if cut_db >= -0.2:
                continue

            # Stage 1: Approach (Fade into silence floor)
            if t_app_end > t_app_start:
                events.append(
                    AutomationEvent(
                        start=round(t_app_start, 4),
                        end=round(t_app_end, 4),
                        target=target_stem,
                        parameter="gain",
                        value=round(cut_db, 2),
                        start_value=0.0,
                        curve="smooth",
                        priority=0.88,
                        hierarchy=hier,
                        reason=f"Silence Director ({s_type} Approach): {event.reason} [preserved: {list(preserved)}]",
                        metadata={
                            "silence_type": s_type,
                            "phase": "APPROACH",
                            "preserved_elements": list(preserved),
                            "depth_db": cut_db,
                        },
                    )
                )

            # Stage 2: Floor (Holding silence)
            if t_floor_end > t_floor_start:
                events.append(
                    AutomationEvent(
                        start=round(t_floor_start, 4),
                        end=round(t_floor_end, 4),
                        target=target_stem,
                        parameter="gain",
                        value=round(cut_db, 2),
                        start_value=round(cut_db, 2),
                        curve="linear",
                        priority=0.88,
                        hierarchy=hier,
                        reason=f"Silence Director ({s_type} Floor): {event.reason} [preserved: {list(preserved)}]",
                        metadata={
                            "silence_type": s_type,
                            "phase": "FLOOR",
                            "preserved_elements": list(preserved),
                            "depth_db": cut_db,
                        },
                    )
                )

            # Stage 3: Release (Fading back to baseline)
            if t_rel_end > t_rel_start:
                events.append(
                    AutomationEvent(
                        start=round(t_rel_start, 4),
                        end=round(t_rel_end, 4),
                        target=target_stem,
                        parameter="gain",
                        value=0.0,
                        start_value=round(cut_db, 2),
                        curve="smooth",
                        priority=0.88,
                        hierarchy=hier,
                        reason=f"Silence Director ({s_type} Release): {event.reason} [preserved: {list(preserved)}]",
                        metadata={
                            "silence_type": s_type,
                            "phase": "RELEASE",
                            "preserved_elements": list(preserved),
                            "depth_db": cut_db,
                        },
                    )
                )

        return events
