#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Module: perspective.py
Acoustic Perspective: Models believable acoustic geography, distance propagation,
barrier occlusion, and direct vs reverberant sound fields without artificial gimmicks.
"""

from __future__ import annotations
import math
from typing import Dict, Any, List, Optional, Literal, Union, get_args
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from audiobook_factory.cinematic_mix.automation import (
    AutomationEvent,
    AutomationHierarchy,
)


DistanceLevel = Literal["close", "near", "medium", "far"]
OcclusionLevel = Literal["none", "partial", "curtain", "door", "wall"]

DISTANCE_PRESETS: Dict[str, Dict[str, Any]] = {
    "close": {
        "distance_factor": 0.1,
        "direct_energy_db": 0.0,
        "early_reflections_level_db": -18.0,
        "reverb_contribution": 0.05,
        "hf_absorption_hz": 18000,
        "stereo_width": 1.0,
    },
    "near": {
        "distance_factor": 0.3,
        "direct_energy_db": -1.5,
        "early_reflections_level_db": -15.0,
        "reverb_contribution": 0.15,
        "hf_absorption_hz": 16000,
        "stereo_width": 1.05,
    },
    "medium": {
        "distance_factor": 0.6,
        "direct_energy_db": -5.0,
        "early_reflections_level_db": -12.0,
        "reverb_contribution": 0.30,
        "hf_absorption_hz": 11000,
        "stereo_width": 1.15,
    },
    "far": {
        "distance_factor": 0.9,
        "direct_energy_db": -10.0,
        "early_reflections_level_db": -9.0,
        "reverb_contribution": 0.55,
        "hf_absorption_hz": 6500,
        "stereo_width": 1.30,
    },
}

OCCLUSION_PRESETS: Dict[str, Dict[str, Any]] = {
    "none": {
        "occlusion_factor": 0.0,
        "direct_attenuation_db": 0.0,
        "cutoff_hz": 18000,
    },
    "partial": {
        "occlusion_factor": 0.25,
        "direct_attenuation_db": -2.5,
        "cutoff_hz": 9000,
    },
    "curtain": {
        "occlusion_factor": 0.40,
        "direct_attenuation_db": -4.0,
        "cutoff_hz": 5500,
    },
    "door": {
        "occlusion_factor": 0.70,
        "direct_attenuation_db": -9.0,
        "cutoff_hz": 2200,
    },
    "wall": {
        "occlusion_factor": 0.95,
        "direct_attenuation_db": -16.0,
        "cutoff_hz": 1100,
    },
}


class AcousticPerspective(BaseModel):
    """
    Physical acoustic perspective specification for a voice or source sound.
    Separates direct wave energy from diffuse reverberant reflections and barrier absorption.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    distance: Union[DistanceLevel, float] = Field(
        default="near",
        description="Distance category ('close', 'near', 'medium', 'far') or normalized float [0.0, 1.0]",
    )
    occlusion: Union[OcclusionLevel, float] = Field(
        default="none",
        description="Occlusion obstruction ('none', 'partial', 'curtain', 'door', 'wall') or normalized float [0.0, 1.0]",
    )
    direct_energy_db: float = Field(
        default=-1.5,
        ge=-36.0,
        le=3.0,
        description="Direct signal acoustic energy delta in dB",
    )
    early_reflections_level_db: float = Field(
        default=-15.0,
        ge=-36.0,
        le=0.0,
        description="Early room reflection gain in dB",
    )
    reverb_contribution: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Late reverberation ratio / room send contribution [0.0, 1.0]",
    )
    hf_absorption_hz: int = Field(
        default=16000,
        ge=300,
        le=20000,
        description="Air & obstacle high-frequency absorption cutoff frequency in Hz",
    )
    stereo_width: float = Field(
        default=1.05,
        ge=0.0,
        le=2.0,
        description="Perceived spatial stereo spread factor",
    )
    room_profile: Optional[str] = Field(
        default="room",
        description="Associated room acoustic preset (e.g. 'room', 'hall', 'cathedral', 'crypt')",
    )

    @model_validator(mode="before")
    @classmethod
    def apply_presets_if_needed(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values

        dist = values.get("distance", "near")
        occ = values.get("occlusion", "none")

        # Resolve distance preset defaults if direct_energy_db not explicitly provided
        if isinstance(dist, str) and dist.lower() in DISTANCE_PRESETS and "direct_energy_db" not in values:
            p = DISTANCE_PRESETS[dist.lower()]
            values["direct_energy_db"] = p["direct_energy_db"]
            values["early_reflections_level_db"] = p["early_reflections_level_db"]
            values["reverb_contribution"] = p["reverb_contribution"]
            values["hf_absorption_hz"] = p["hf_absorption_hz"]
            values["stereo_width"] = p["stereo_width"]

        # Resolve occlusion preset damping
        if isinstance(occ, str) and occ.lower() in OCCLUSION_PRESETS:
            o_preset = OCCLUSION_PRESETS[occ.lower()]
            if "hf_absorption_hz" not in values:
                values["hf_absorption_hz"] = o_preset["cutoff_hz"]
            else:
                # Occlusion cutoff dominates over open-air distance cutoff
                values["hf_absorption_hz"] = min(values["hf_absorption_hz"], o_preset["cutoff_hz"])
            if o_preset["direct_attenuation_db"] < 0:
                values["direct_energy_db"] = values.get("direct_energy_db", -1.5) + o_preset["direct_attenuation_db"]

        return values


class PerspectiveDirector:
    """
    Directs acoustic geography, distance propagation, and barrier occlusion.
    Translates AcousticPerspective specs into continuous, smoothed automation events.
    """

    def __init__(self, default_transition_sec: float = 0.40):
        self.default_transition_sec = default_transition_sec

    def plan_perspective(
        self,
        perspective: AcousticPerspective,
        start_sec: float,
        end_sec: float,
        target_stem: str = "DX",
        transition_sec: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> List[AutomationEvent]:
        """
        Generates automation events for distance gain, HF absorption lowpass,
        and room reflections for the target stem across [start_sec, end_sec].
        """
        trans = transition_sec if transition_sec is not None else self.default_transition_sec
        r = reason or f"Acoustic perspective: distance={perspective.distance}, occlusion={perspective.occlusion}"

        events: List[AutomationEvent] = []

        # 1. Direct Energy Gain Automation
        # If direct energy is meaningfully different from 0.0 dB
        if abs(perspective.direct_energy_db) > 0.2:
            events.append(
                AutomationEvent(
                    start=round(max(0.0, start_sec), 4),
                    end=round(end_sec, 4),
                    target=target_stem,
                    parameter="gain",
                    value=round(perspective.direct_energy_db, 2),
                    start_value=0.0,
                    curve="smooth",
                    priority=0.75,
                    hierarchy="CINEMATIC_BEHAVIOR",
                    reason=r,
                    metadata={"early_reflections_db": perspective.early_reflections_level_db},
                )
            )

        # 2. High-Frequency Absorption / Occlusion Low-Pass
        # If air damping or obstacle cuts below 16 kHz
        if perspective.hf_absorption_hz < 16000:
            events.append(
                AutomationEvent(
                    start=round(max(0.0, start_sec), 4),
                    end=round(end_sec, 4),
                    target=target_stem,
                    parameter="lowpass_cutoff",
                    value=float(perspective.hf_absorption_hz),
                    start_value=18000.0,
                    curve="smooth",
                    priority=0.75,
                    hierarchy="CINEMATIC_BEHAVIOR",
                    reason=f"{r} (HF damping {perspective.hf_absorption_hz} Hz)",
                    metadata={"occlusion": str(perspective.occlusion)},
                )
            )

        # 3. Stereo Width Modulation
        if abs(perspective.stereo_width - 1.0) > 0.08:
            events.append(
                AutomationEvent(
                    start=round(max(0.0, start_sec), 4),
                    end=round(end_sec, 4),
                    target=target_stem,
                    parameter="stereo_width",
                    value=round(perspective.stereo_width, 2),
                    start_value=1.0,
                    curve="smooth",
                    priority=0.60,
                    hierarchy="CINEMATIC_BEHAVIOR",
                    reason=f"{r} (perceived width {perspective.stereo_width})",
                )
            )

        # 4. Reverb Send Contribution
        if perspective.reverb_contribution > 0.10:
            events.append(
                AutomationEvent(
                    start=round(max(0.0, start_sec), 4),
                    end=round(end_sec, 4),
                    target=target_stem,
                    parameter="reverb_send",
                    value=round(perspective.reverb_contribution, 2),
                    start_value=0.10,
                    curve="smooth",
                    priority=0.65,
                    hierarchy="CINEMATIC_BEHAVIOR",
                    reason=f"{r} (reverb send {perspective.reverb_contribution:.2f})",
                    metadata={"room_profile": perspective.room_profile},
                )
            )

        return events
