#!/usr/bin/env python3
"""
Audiobook Factory - Coordination Contracts & Schema Shield.
Defines strictly typed Pydantic v2 schemas and validation contracts for the
LLM <-> Deterministic Script interface.
Ensures zero markdown leaks, zero unmapped speakers, and fail-closed schema integrity.
"""

from __future__ import annotations
import re
import json
from typing import List, Dict, Any, Optional, Literal, Set, Tuple
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class CoordinationValidationError(ValueError):
    """Raised when an LLM output fails schema validation or coordination bounds."""
    pass


def strip_markdown_fences(raw_text: str) -> str:
    """Strips markdown codeblock fences, JSON prefixes, and explanatory preamble."""
    if not raw_text or not isinstance(raw_text, str):
        return ""
    text = raw_text.strip()
    
    # Extract content between ```json and ``` or ``` and ```
    fence_pattern = r"^```(?:json|JSON)?\s*\n(.*?)\n```"
    match = re.search(fence_pattern, text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # Strip any leading ```json or trailing ```
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
        
    return text.strip()


class RawScreenplaySegmentContract(BaseModel):
    """
    Contract representing a single segment emitted by the LLM screenplay builder.
    Enforces strict typing, speaker string sanitization, and cleans leaked commentary.
    """
    model_config = ConfigDict(extra="ignore")

    index: int = Field(default=1, description="1-based segment sequence index")
    type: Literal["narration", "dialogue", "action"] = Field(
        default="narration",
        description="Structural segment classification"
    )
    speaker: str = Field(..., description="Canonical character name, Narrator, or Foley")
    text: str = Field(..., description="Spoken dialogue or dramatic narration text")
    emotion: Optional[str] = Field(default="neutral", description="Primary emotional delivery")
    actioning: Optional[str] = Field(default=None, description="Transitive dramatic intent verb")
    subtext: Optional[str] = Field(default=None, description="Concealed psychological subtext")
    intensity_level: Literal["low", "medium", "high", "explosive"] = Field(
        default="medium",
        description="Dynamic acoustic headroom"
    )
    acting: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Acting delivery style")
    spatial: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Proximity and pan")
    acoustic_env: Optional[str] = Field(default="domestic_room", description="Scene acoustic environment")
    sfx_cues: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Foley/SFX cues")

    @field_validator("speaker")
    @classmethod
    def sanitize_speaker(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            return "Narrator"
        cleaned = v.strip().strip("\"':()[]{}—–")
        # Disallow raw pronoun leaks as speakers
        lower = cleaned.lower()
        if lower in ("he", "she", "him", "her", "usne", "vah", "वह", "उसने", "someone", "unknown", "voice"):
            return "Narrator"
        return cleaned or "Narrator"

    @field_validator("text")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            return ""
        # Strip markdown header lines or LLM conversational commentary
        cleaned_lines = []
        for line in v.splitlines():
            sline = line.strip()
            if sline.startswith(("#", "```", "Note:", "Note :", "Translation:", "Scene:")):
                continue
            if sline:
                cleaned_lines.append(line)
        result = " ".join(cleaned_lines).strip()
        # Clean double quotes wrapping the entire text
        if result.startswith('"') and result.endswith('"') and len(result) > 1:
            result = result[1:-1].strip()
        return result


class ScreenplayScriptPayload(BaseModel):
    """Container schema for the complete list of screenplay segments."""
    model_config = ConfigDict(extra="ignore")
    segments: List[RawScreenplaySegmentContract] = Field(default_factory=list)

    @classmethod
    def from_raw_json(cls, raw_content: str) -> "ScreenplayScriptPayload":
        """Parses raw LLM string into validated ScreenplayScriptPayload with repair fallback."""
        cleaned = strip_markdown_fences(raw_content)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Attempt to locate JSON array [ ... ]
            m = re.search(r"(\[.*\])", cleaned, flags=re.DOTALL)
            if m:
                data = json.loads(m.group(1))
            else:
                # Attempt to locate JSON object { ... }
                m2 = re.search(r"(\{.*\})", cleaned, flags=re.DOTALL)
                if m2:
                    data = json.loads(m2.group(1))
                else:
                    raise CoordinationValidationError("Could not parse JSON array or object from LLM response")

        if isinstance(data, list):
            return cls(segments=[RawScreenplaySegmentContract.model_validate(item) for item in data])
        elif isinstance(data, dict):
            segs = data.get("segments", data.get("script", []))
            if isinstance(segs, list):
                return cls(segments=[RawScreenplaySegmentContract.model_validate(item) for item in segs])
            raise CoordinationValidationError("Dictionary payload does not contain 'segments' list")
        raise CoordinationValidationError(f"Unexpected top-level JSON type: {type(data)}")


class RawMusicCueContract(BaseModel):
    """Contract for LLM Music Director cue specification."""
    model_config = ConfigDict(extra="ignore")

    cue_id: str = Field(..., description="Unique cue identifier")
    narrative_archetype: Optional[str] = Field(default=None, description="Archetype (e.g., MYSTERY_PROLOGUE)")
    search_query: str = Field(..., description="Keywords for FTS5 catalog matching")
    mood: Optional[str] = Field(default="default", description="Emotional mood")
    timbre: Optional[str] = Field(default=None, description="Instrumentation timbre")
    tempo: Optional[str] = Field(default=None, description="Tempo category (slow, moderate, fast)")
    energy_section: Literal["INTRO_BED", "RISING_TENSION", "CLIMAX_DROP", "OUTRO_TAIL", "FULL_TRACK"] = Field(
        default="INTRO_BED",
        description="Music track structural section"
    )
    trigger_segment: int = Field(default=1, ge=0, description="Segment index where music begins")
    until_segment: Optional[int] = Field(default=None, description="Segment index where music ends")
    duration_sec: float = Field(default=25.0, ge=1.0, le=300.0, description="Desired duration in seconds")
    fade_in_sec: float = Field(default=3.0, ge=0.0, le=15.0, description="Fade in time")
    fade_out_sec: float = Field(default=4.0, ge=0.0, le=15.0, description="Fade out time")
    volume_db: float = Field(default=-18.0, ge=-40.0, le=0.0, description="Target volume in dBFS")
    valence: Optional[float] = Field(default=None, ge=-1.0, le=1.0, description="Emotional positivity")
    arousal: Optional[float] = Field(default=None, ge=-1.0, le=1.0, description="Emotional intensity")
    dramatic_justification: Optional[str] = Field(default="", description="Narrative rationale")

    @field_validator("search_query")
    @classmethod
    def sanitize_search_query(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            return "orchestral drama atmospheric"
        # Strip special punctuation that breaks SQLite FTS5 syntax
        cleaned = re.sub(r"['\":*()^~-]", " ", v).strip()
        tokens = [t for t in cleaned.split() if len(t) > 1]
        return " ".join(tokens) or "orchestral drama"


class RawFoleyEventContract(BaseModel):
    """Contract for LLM Foley Director physical action beat."""
    model_config = ConfigDict(extra="ignore")

    segment_index: int = Field(default=1, ge=0, description="Associated screenplay segment index")
    subject: str = Field(default="Foley", description="Entity initiating the physical action")
    action_verb: str = Field(..., description="Action verb (footstep, door, tableware, impact, rustle)")
    object_material: str = Field(default="wood", description="Material (wood, metal, glass, cloth, stone)")
    anchor_word: str = Field(default="", description="Word in dialogue/narration where sound triggers")
    target_gain_dbfs: float = Field(default=-18.0, ge=-40.0, le=-6.0, description="Volume gain in dBFS")
    azimuth_pan: float = Field(default=0.0, ge=-0.8, le=0.8, description="Stereo panning (-1.0 to +1.0)")
    timing: Literal["before", "under", "after"] = Field(default="under", description="Relative timing to speech")

    @field_validator("action_verb")
    @classmethod
    def sanitize_action_verb(cls, v: str) -> str:
        s = v.strip().lower()
        # Clean verb string
        s = re.sub(r"[^a-z0-9_]", "", s)
        return s or "rustle"


# =========================================================================
# Multi-Expert Architecture Audit & Coordination Contracts
# =========================================================================

class SubsystemEvidenceDossier(BaseModel):
    """
    Forensic dossier containing deterministic factual measurements,
    AST integrity checks, and regex/DSP findings extracted by Python scripts.
    """
    model_config = ConfigDict(extra="ignore")

    subsystem_id: str = Field(..., description="Canonical subsystem ID (e.g. system1_ingestion)")
    expert_role: str = Field(..., description="Designated domain expert auditor title")
    deterministic_score: float = Field(default=100.0, ge=0.0, le=100.0, description="Quantitative score")
    hard_gate_pass: bool = Field(default=True, description="True if all non-negotiable hard gates passed")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Numerical & categorical measurements")
    inspected_files: List[str] = Field(default_factory=list, description="List of audited files")
    raw_excerpts: List[str] = Field(default_factory=list, description="Target excerpts extracted for LLM analysis")
    anomalies: List[str] = Field(default_factory=list, description="Deterministic anomalies or violations found")


class LLMExpertEvaluation(BaseModel):
    """
    Structured qualitative evaluation and critique produced by an LLM Domain Expert
    evaluating the SubsystemEvidenceDossier against formal domain rubrics.
    """
    model_config = ConfigDict(extra="ignore")

    subsystem_id: str = Field(..., description="Canonical subsystem ID")
    expert_role: str = Field(..., description="Domain expert auditor title")
    qualitative_score: float = Field(default=100.0, ge=0.0, le=100.0, description="LLM qualitative score")
    rubric_breakdown: Dict[str, float] = Field(default_factory=dict, description="Individual rubric criterion scores")
    critique: str = Field(default="", description="Deep forensic qualitative critique")
    detected_risks: List[str] = Field(default_factory=list, description="Identified narrative, dramatic or audio risks")
    actionable_recommendations: List[str] = Field(default_factory=list, description="Targeted expert remediation guidance")


class SubsystemAuditVerdict(BaseModel):
    """
    Final composite verdict reconciling deterministic script evidence and LLM expert evaluation.
    """
    model_config = ConfigDict(extra="ignore")

    subsystem_id: str = Field(..., description="Canonical subsystem ID")
    subsystem_name: str = Field(..., description="Human-readable subsystem label")
    expert_role: str = Field(..., description="Designated domain expert title")
    status: Literal["PASS", "WARN", "FAIL"] = Field(..., description="Subsystem certification status")
    composite_score: float = Field(..., ge=0.0, le=100.0, description="Mathematically combined score")
    deterministic_score: float = Field(..., ge=0.0, le=100.0, description="Script quantitative score")
    qualitative_score: float = Field(..., ge=0.0, le=100.0, description="LLM expert qualitative score")
    hard_gate_pass: bool = Field(default=True, description="Fail-closed hard gate status")
    summary_message: str = Field(..., description="One-line diagnostic verdict summary")
    evidence_dossier: SubsystemEvidenceDossier = Field(..., description="Deterministic factual dossier")
    expert_evaluation: Optional[LLMExpertEvaluation] = Field(default=None, description="LLM expert evaluation")
    findings: List[str] = Field(default_factory=list, description="Key forensic findings")
    remediations: List[str] = Field(default_factory=list, description="Actionable recommendations")


class MasterArchitectureAuditReport(BaseModel):
    """
    Master multi-expert audit report spanning all 10 subsystems of the audiobook production platform.
    """
    model_config = ConfigDict(extra="ignore")

    project_name: str = Field(..., description="Name of the audited project")
    project_dir: str = Field(..., description="Absolute path to the book project directory")
    timestamp_utc: str = Field(..., description="ISO 8601 UTC timestamp of audit execution")
    read_only_verified: bool = Field(default=True, description="Confirmation that zero file modifications occurred")
    overall_status: Literal["PASS", "WARN", "FAIL"] = Field(..., description="Overall platform status")
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Master architecture score across all 10 subsystems")
    subsystems_passed: int = Field(default=0, ge=0)
    subsystems_warned: int = Field(default=0, ge=0)
    subsystems_failed: int = Field(default=0, ge=0)
    subsystems: Dict[str, SubsystemAuditVerdict] = Field(default_factory=dict, description="Verdicts per subsystem")
    executive_summary: str = Field(default="", description="High-level architectural evaluation and synthesis")

