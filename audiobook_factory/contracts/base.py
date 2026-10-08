#!/usr/bin/env python3
"""
Audiobook Factory - Contracts Base: ContractBaseModel with deterministic SHA-256 serialization.
Standard: v6.0-ENTERPRISE-DAG
"""

from __future__ import annotations
import hashlib
import json
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ManifestValidationError(ValueError):
    """Raised when a creative manifest or contract violates structural or acoustic constraints."""
    pass


class ContractBaseModel(BaseModel):
    """Base model for all v6.0-ENTERPRISE-DAG data contracts."""
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        populate_by_name=True
    )

    schema_version: str = Field(
        default="2.0",
        description="Contract schema version identifier"
    )

    def compute_sha256_hash(self) -> str:
        """Computes deterministic SHA-256 hash of the model data using canonical JSON."""
        data_dict = self.model_dump(mode="json", exclude={"schema_version"})
        serialized = json.dumps(
            data_dict,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_canonical_json(self, indent: Optional[int] = 2) -> str:
        """Serializes model to human-readable or compact canonical UTF-8 JSON."""
        data_dict = self.model_dump(mode="json")
        if indent is not None:
            return json.dumps(data_dict, indent=indent, ensure_ascii=False)
        return json.dumps(data_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class ProjectConfig(BaseModel):
    """
    Legacy Project-level configuration defining metadata, language pairing,
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
    adult_literary_mode: bool = Field(default=True, description="Enables raw adult literary fidelity")

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


# Allowable music cue types strictly constrained (Legacy)
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
