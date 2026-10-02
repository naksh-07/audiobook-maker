#!/usr/bin/env python3
"""
Audiobook Factory - Contracts Base: Shared exceptions, configurations, and type literals.
"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


class ManifestValidationError(ValueError):
    """Raised when a creative manifest or contract violates structural or acoustic constraints."""
    pass


class ProjectConfig(BaseModel):
    """
    Project-level configuration defining metadata, language pairing,
    local asset directories, and broadcast audio compliance targets.
    """
    model_config = ConfigDict(extra="ignore")

    project_id: str = Field(..., description="Unique identifier for the project")
    title: str = Field(..., description="Book/Project title")
    author: str = Field(..., description="Author name")
    source_language: str = Field(..., description="Source text language code (e.g. 'en', 'hi')")
    target_language: str = Field(default="hi-IN", description="Target TTS/audiobook language code")
    assets_dir: str = Field(..., description="Root directory path for all project media assets")
    ebu_r128_lufs: float = Field(default=-19.0, description="EBU R128 integrated loudness target in LUFS")
    true_peak_db: float = Field(default=-1.5, description="Maximum allowable True Peak in dBTP")
    adult_literary_mode: bool = Field(default=True, description="Enables unfiltered Gangs-of-Wasseypur / Manto grade raw adult literary fidelity")

    @field_validator("ebu_r128_lufs")
    @classmethod
    def validate_lufs(cls, v: float) -> float:
        if v > 0.0 or v < -70.0:
            raise ManifestValidationError(f"Invalid EBU R128 target LUFS: {v}. Must be between -70.0 and 0.0 LUFS.")
        return round(v, 2)

    @field_validator("true_peak_db")
    @classmethod
    def validate_true_peak(cls, v: float) -> float:
        if v > 0.0 or v < -20.0:
            raise ManifestValidationError(f"Invalid true peak target dB: {v}. Must be <= 0.0 dBTP.")
        return round(v, 2)


# Allowable music cue types strictly constrained
MusicCueType = Literal[
    "TRANSITION_BRIDGE",
    "EMOTIONAL_UNDERSCORE",
    "TENSION_RISER",
    "CLIMACTIC_ACTION_CUE",
    "AFTERMATH_FADE",
]

ProvenanceMethod = Literal[
    "source_metadata",
    "measured_dsp",
    "classifier",
    "semantic_model",
    "llm_inferred",
    "keyword_inferred",
    "curated",
]
