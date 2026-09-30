#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Module: scene_intent.py
Defines SceneMixIntent, the typed scene-level mixing intent model representing
the director's high-level acoustic and dramatic desires before automation curves
and DSP mixing are executed.
"""

from __future__ import annotations
import hashlib
import json
from typing import Dict, Any, Optional, Literal, Union, get_args
from pydantic import BaseModel, Field, field_validator, ConfigDict


FocusTarget = Literal[
    "dialogue",
    "music",
    "fx",
    "ambience",
    "silence",
    "environment",
]

ALLOWED_FOCUS_TARGETS = set(get_args(FocusTarget))

DynamicRangePreset = Literal[
    "compressed_intimate",
    "natural_dialogue",
    "standard",
    "cinematic_wide",
    "extreme_dynamic",
]

DYNAMIC_RANGE_PRESETS: Dict[str, float] = {
    "compressed_intimate": 0.20,
    "natural_dialogue": 0.50,
    "standard": 0.50,
    "cinematic_wide": 0.80,
    "extreme_dynamic": 1.00,
}

SpatialDepthPreset = Literal[
    "intimate_dry",
    "shallow_room",
    "hall_medium",
    "deep_cavernous",
    "infinite_exterior",
]

SPATIAL_DEPTH_PRESETS: Dict[str, float] = {
    "intimate_dry": 0.10,
    "shallow_room": 0.30,
    "hall_medium": 0.60,
    "deep_cavernous": 0.85,
    "infinite_exterior": 1.00,
}

SilenceIntentPreset = Literal[
    "none",
    "subtle_pause",
    "dramatic_drop",
    "profound_stillness",
]

SILENCE_INTENT_PRESETS: Dict[str, float] = {
    "none": 0.00,
    "subtle_pause": 0.30,
    "dramatic_drop": 0.70,
    "profound_stillness": 1.00,
}

ImpactIntentPreset = Literal[
    "none",
    "light_accent",
    "heavy_strike",
    "cataclysmic_blast",
]

IMPACT_INTENT_PRESETS: Dict[str, float] = {
    "none": 0.00,
    "light_accent": 0.30,
    "heavy_strike": 0.70,
    "cataclysmic_blast": 1.00,
}


class SceneMixIntent(BaseModel):
    """
    Stage 11 Typed Scene Mixing Intent Model.
    Captures narrative and acoustic mixing intent for a scene:
    - Primary listener focus (dialogue, music, fx, ambience, silence, environment)
    - Relative priorities across DME stems
    - Emotional intensity and dynamic range intent
    - Spatial depth, silence intent, and impact punch intent
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    focus: FocusTarget = Field(
        default="dialogue",
        description="Primary narrative focus target: dialogue, music, fx, ambience, silence, environment",
    )
    emotional_intensity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Bounded normalized emotional intensity (0.0 = calm, 1.0 = extreme)",
    )
    dialogue_priority: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Bounded narrative priority for dialogue (0.0 = irrelevant, 1.0 = maximum)",
    )
    music_priority: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Bounded narrative priority for music/score (0.0 = irrelevant, 1.0 = maximum)",
    )
    fx_priority: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Bounded narrative priority for Foley and sound effects (0.0 = irrelevant, 1.0 = maximum)",
    )
    ambience_priority: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description="Bounded narrative priority for environmental background beds (0.0 = irrelevant, 1.0 = maximum)",
    )
    dynamic_range_intent: Union[float, DynamicRangePreset] = Field(
        default=0.50,
        description="Desired scene dynamic range: normalized float [0.0, 1.0] or preset name",
    )
    spatial_depth: Union[float, SpatialDepthPreset] = Field(
        default=0.30,
        description="Acoustic depth perspective intent: normalized float [0.0, 1.0] or preset name",
    )
    silence_intent: Union[float, SilenceIntentPreset] = Field(
        default=0.00,
        description="Intentional negative space/silence intent: normalized float [0.0, 1.0] or preset name",
    )
    impact_intent: Union[float, ImpactIntentPreset] = Field(
        default=0.00,
        description="Visceral impact punch intent: normalized float [0.0, 1.0] or preset name",
    )
    scene_id: Optional[str] = Field(
        default=None,
        description="Optional associated scene identifier",
    )
    chapter_id: Optional[str] = Field(
        default=None,
        description="Optional associated chapter identifier",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary directorial or scene metadata",
    )

    @field_validator("focus", mode="before")
    @classmethod
    def validate_focus(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError(f"Invalid focus: expected string, got {type(v).__name__}")
        norm = v.strip().lower()
        if norm not in ALLOWED_FOCUS_TARGETS:
            raise ValueError(
                f"Invalid focus '{v}'. Must be one of: {sorted(ALLOWED_FOCUS_TARGETS)}"
            )
        return norm

    @field_validator("dynamic_range_intent", mode="before")
    @classmethod
    def validate_dynamic_range(cls, v: Any) -> Union[float, str]:
        if isinstance(v, (int, float)):
            val = float(v)
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"dynamic_range_intent float must be within [0.0, 1.0], got {val}")
            return val
        if isinstance(v, str):
            norm = v.strip().lower()
            if norm not in DYNAMIC_RANGE_PRESETS:
                raise ValueError(
                    f"Invalid dynamic_range_intent preset '{v}'. Must be one of: {sorted(DYNAMIC_RANGE_PRESETS.keys())}"
                )
            return norm
        raise ValueError(f"Invalid dynamic_range_intent type: {type(v).__name__}")

    @field_validator("spatial_depth", mode="before")
    @classmethod
    def validate_spatial_depth(cls, v: Any) -> Union[float, str]:
        if isinstance(v, (int, float)):
            val = float(v)
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"spatial_depth float must be within [0.0, 1.0], got {val}")
            return val
        if isinstance(v, str):
            norm = v.strip().lower()
            if norm not in SPATIAL_DEPTH_PRESETS:
                raise ValueError(
                    f"Invalid spatial_depth preset '{v}'. Must be one of: {sorted(SPATIAL_DEPTH_PRESETS.keys())}"
                )
            return norm
        raise ValueError(f"Invalid spatial_depth type: {type(v).__name__}")

    @field_validator("silence_intent", mode="before")
    @classmethod
    def validate_silence_intent(cls, v: Any) -> Union[float, str]:
        if isinstance(v, (int, float)):
            val = float(v)
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"silence_intent float must be within [0.0, 1.0], got {val}")
            return val
        if isinstance(v, str):
            norm = v.strip().lower()
            if norm not in SILENCE_INTENT_PRESETS:
                raise ValueError(
                    f"Invalid silence_intent preset '{v}'. Must be one of: {sorted(SILENCE_INTENT_PRESETS.keys())}"
                )
            return norm
        raise ValueError(f"Invalid silence_intent type: {type(v).__name__}")

    @field_validator("impact_intent", mode="before")
    @classmethod
    def validate_impact_intent(cls, v: Any) -> Union[float, str]:
        if isinstance(v, (int, float)):
            val = float(v)
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"impact_intent float must be within [0.0, 1.0], got {val}")
            return val
        if isinstance(v, str):
            norm = v.strip().lower()
            if norm not in IMPACT_INTENT_PRESETS:
                raise ValueError(
                    f"Invalid impact_intent preset '{v}'. Must be one of: {sorted(IMPACT_INTENT_PRESETS.keys())}"
                )
            return norm
        raise ValueError(f"Invalid impact_intent type: {type(v).__name__}")

    @property
    def normalized_dynamic_range(self) -> float:
        """Returns the dynamic range intent as a normalized float [0.0, 1.0]."""
        if isinstance(self.dynamic_range_intent, (int, float)):
            return float(self.dynamic_range_intent)
        return DYNAMIC_RANGE_PRESETS.get(str(self.dynamic_range_intent).lower(), 0.50)

    @property
    def normalized_spatial_depth(self) -> float:
        """Returns the spatial depth intent as a normalized float [0.0, 1.0]."""
        if isinstance(self.spatial_depth, (int, float)):
            return float(self.spatial_depth)
        return SPATIAL_DEPTH_PRESETS.get(str(self.spatial_depth).lower(), 0.30)

    @property
    def normalized_silence_intent(self) -> float:
        """Returns the silence intent as a normalized float [0.0, 1.0]."""
        if isinstance(self.silence_intent, (int, float)):
            return float(self.silence_intent)
        return SILENCE_INTENT_PRESETS.get(str(self.silence_intent).lower(), 0.00)

    @property
    def normalized_impact_intent(self) -> float:
        """Returns the impact intent as a normalized float [0.0, 1.0]."""
        if isinstance(self.impact_intent, (int, float)):
            return float(self.impact_intent)
        return IMPACT_INTENT_PRESETS.get(str(self.impact_intent).lower(), 0.00)

    def fingerprint(self) -> str:
        """Computes a deterministic SHA-256 fingerprint for this mixing intent."""
        payload = self.model_dump_json(indent=None)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Serializes intent to a dictionary."""
        return self.model_dump(mode="json")

    def to_json(self, indent: int = 2) -> str:
        """Serializes intent to a JSON string deterministically."""
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SceneMixIntent:
        """Constructs SceneMixIntent from a dictionary."""
        return cls.model_validate(data)

    @classmethod
    def from_json(cls, json_str: str) -> SceneMixIntent:
        """Constructs SceneMixIntent from a JSON string."""
        return cls.model_validate_json(json_str)

    @classmethod
    def from_scene_understanding(cls, understanding: Any) -> SceneMixIntent:
        """
        Constructs SceneMixIntent by adapting Stage 10 SceneAudioUnderstandingResult.
        """
        if hasattr(understanding, "model_dump"):
            u_dict = understanding.model_dump()
        elif isinstance(understanding, dict):
            u_dict = understanding
        else:
            u_dict = getattr(understanding, "__dict__", {})

        tension = float(u_dict.get("tension_level", 0.5) or 0.5)
        emotion = str(u_dict.get("dominant_emotion", "neutral") or "neutral").lower()
        has_music = bool(u_dict.get("music_required", True))
        silence_opps = u_dict.get("silence_opportunities", [])

        # Infer focus target based on scene understanding signals
        if silence_opps and tension < 0.2:
            focus = "silence"
        elif tension > 0.85:
            focus = "fx"
        elif not has_music and tension <= 0.4:
            focus = "dialogue"
        elif "music" in emotion or "revelation" in emotion:
            focus = "music"
        else:
            focus = "dialogue"

        # Determine priorities
        dialogue_prio = 0.90 if focus == "dialogue" else 0.70
        music_prio = (0.75 if focus == "music" else 0.45) if has_music else 0.0
        fx_prio = 0.90 if (focus == "fx" or tension > 0.7) else 0.40
        amb_prio = 0.40 if focus == "environment" else 0.25

        silence_val = 0.60 if silence_opps else 0.00
        impact_val = 0.80 if tension > 0.80 else (0.40 if tension > 0.50 else 0.00)

        dyn_range = 0.85 if tension > 0.75 else (0.30 if "whisper" in emotion or "intimate" in emotion else 0.50)

        return cls(
            scene_id=u_dict.get("scene_id"),
            chapter_id=u_dict.get("chapter_id"),
            focus=focus,
            emotional_intensity=round(tension, 2),
            dialogue_priority=dialogue_prio,
            music_priority=music_prio,
            fx_priority=fx_prio,
            ambience_priority=amb_prio,
            dynamic_range_intent=dyn_range,
            spatial_depth=0.35,
            silence_intent=silence_val,
            impact_intent=impact_val,
            metadata={"source": "SceneAudioUnderstandingResult", "dominant_emotion": emotion},
        )

    @classmethod
    def from_scene_blueprint(cls, blueprint: Any) -> SceneMixIntent:
        """
        Constructs SceneMixIntent by adapting Stage 10 SceneAudioBlueprint.
        """
        if hasattr(blueprint, "model_dump"):
            bp_dict = blueprint.model_dump()
        elif isinstance(blueprint, dict):
            bp_dict = blueprint
        else:
            bp_dict = getattr(blueprint, "__dict__", {})

        restraint = str(bp_dict.get("restraint_target", "moderate") or "moderate").lower()
        silence_events = bp_dict.get("silence_events_planned", [])
        hard_sfx = bp_dict.get("hard_sfx_planned", [])
        music_cues = bp_dict.get("music_cues_planned", [])

        if silence_events and len(silence_events) > 0 and len(music_cues) == 0:
            focus = "silence"
        elif len(hard_sfx) > 2:
            focus = "fx"
        elif len(music_cues) > 0 and restraint == "dense":
            focus = "music"
        else:
            focus = "dialogue"

        silence_val = 0.70 if silence_events else (0.30 if restraint == "high" else 0.00)
        impact_val = 0.85 if len(hard_sfx) > 1 else 0.20

        return cls(
            scene_id=bp_dict.get("scene_id"),
            chapter_id=bp_dict.get("chapter_id"),
            focus=focus,
            emotional_intensity=0.75 if len(hard_sfx) > 0 else 0.40,
            dialogue_priority=0.85,
            music_priority=0.60 if music_cues else 0.10,
            fx_priority=0.80 if hard_sfx else 0.40,
            ambience_priority=0.35,
            dynamic_range_intent="cinematic_wide" if hard_sfx else "natural_dialogue",
            spatial_depth="hall_medium" if "hall" in str(bp_dict.get("acoustic_profile_id", "")) else "shallow_room",
            silence_intent=silence_val,
            impact_intent=impact_val,
            metadata={"source": "SceneAudioBlueprint", "restraint_target": restraint},
        )
