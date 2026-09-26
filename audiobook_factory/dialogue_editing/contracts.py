#!/usr/bin/env python3
"""
Audiobook Factory - Dialogue Editorial Layer Contracts (DE-01).
Defines strongly typed Pydantic v2 schemas for editorial decisions:
DialogueEditPlan, EndpointClassification, BreathEditAction, PauseEditClassification,
DialogueEditorialConfig, and DialogueQCReport.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator


EndpointClassification = Literal[
    "NATURAL_SPEECH",
    "NATURAL_BREATH",
    "EMOTIONAL_TAIL",
    "INTENTIONAL_SILENCE",
    "UNWANTED_SILENCE",
    "AUDIO_ARTIFACT",
    "TECHNICAL_BOUNDARY",
]

BreathEditAction = Literal["KEEP", "REDUCE", "REMOVE", "TRIM"]

PauseEditClassification = Literal[
    "NORMAL_TURN",
    "RAPID_TURN",
    "EMOTIONAL_PAUSE",
    "THINKING_PAUSE",
    "SUSPENSE_PAUSE",
    "REACTION_PAUSE",
    "HESITATION",
    "INTERRUPTED_TURN",
]


class DialogueEditorialConfig(BaseModel):
    """
    Isolated and configurable parameters for the Dialogue Editorial Layer.
    Preserves 5.0ms technical de-click by default and avoids fixed 400ms pause defaults.
    """
    model_config = ConfigDict(extra="ignore")

    # Technical de-click: strictly preserve existing 5.0ms baseline
    default_declick_fade_ms: float = Field(default=5.0, description="Baseline technical de-click cosine micro-fade")
    editorial_transition_fade_ms: float = Field(default=15.0, description="Micro-fade used only when editorial transition requires it")

    # Endpoint boundaries & safety buffers
    minimum_speech_boundary_confidence: float = Field(default=0.50, description="Minimum confidence to perform aggressive trimming")
    max_unwanted_silence_head_ms: int = Field(default=80, description="Leading dead air threshold triggering head trim")
    max_unwanted_silence_tail_ms: int = Field(default=120, description="Trailing dead air threshold triggering tail trim")
    head_speech_safety_buffer_ms: int = Field(default=40, description="Minimum buffer before speech onset (never trim into speech)")
    tail_speech_safety_buffer_ms: int = Field(default=60, description="Minimum buffer after speech offset (preserves consonant releases)")
    emotional_tail_release_ms: int = Field(default=180, description="Buffer preserved for emotional vocal resonance and exhales")
    max_endpoint_trim_ms: int = Field(default=1500, description="Maximum allowable trim from head or tail")

    # Breath editing parameters (relative, conservative)
    breath_reduce_attenuation_db: float = Field(default=-6.0, description="Gentle gain reduction applied to exaggerated breaths")
    breath_relative_loudness_margin_db: float = Field(default=4.0, description="Margin within speech RMS to flag breath as disproportionately loud")
    breath_min_confidence_for_removal: float = Field(default=0.75, description="High confidence required before ever removing a breath")

    # Contextual pause realization bounds
    min_pause_ms: int = Field(default=60, description="Hard floor for any non-interrupted pause")
    max_contextual_pause_ms: int = Field(default=2200, description="Hard ceiling for contextual dramatic silence")
    anti_mechanical_jitter_ms: int = Field(default=25, description="Bounded deterministic pseudo-jitter range (±ms)")


class DialogueEditPlan(BaseModel):
    """
    First-Class Editorial Contract (DE-01).
    Captures the complete deterministic editorial treatment for a single dialogue segment.
    Decoupled from PerformanceDirection (intent) and PerformanceEvidence (actual performance).
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    segment_uid: str = Field(default="", description="ScreenplaySegment UID")
    source_take: str = Field(default="", description="Unique take identifier or audio filename stem")
    speech_start_ms: int = Field(default=0, ge=0, description="Detected speech onset in milliseconds")
    speech_end_ms: int = Field(default=0, ge=0, description="Detected speech offset in milliseconds")

    # Endpoint editing decisions
    head_trim_ms: float = Field(default=0.0, ge=0.0, description="Milliseconds trimmed from start")
    tail_trim_ms: float = Field(default=0.0, ge=0.0, description="Milliseconds trimmed from end")
    head_classification: EndpointClassification = Field(default="NATURAL_SPEECH")
    tail_classification: EndpointClassification = Field(default="NATURAL_SPEECH")

    # Breath editing decisions
    pre_breath_action: BreathEditAction = Field(default="KEEP")
    post_breath_action: BreathEditAction = Field(default="KEEP")
    pre_breath_attenuation_db: float = Field(default=0.0, le=0.0, description="Gain adjustment for pre-roll breath")
    post_breath_attenuation_db: float = Field(default=0.0, le=0.0, description="Gain adjustment for post-roll breath")

    # Contextual pause realization (no hardcoded 400ms default; derived from TimingRealizer)
    pause_before_ms: int = Field(default=0, ge=0, description="Silence to precede segment in milliseconds")
    pause_after_ms: Optional[int] = Field(default=None, ge=0, description="Realized contextual silence after segment")
    pause_classification: PauseEditClassification = Field(default="NORMAL_TURN")

    # Boundary micro-fades (preserves 5.0ms technical de-click by default)
    crossfade_in_ms: float = Field(default=5.0, ge=0.0, description="Boundary fade-in duration in milliseconds")
    crossfade_out_ms: float = Field(default=5.0, ge=0.0, description="Boundary fade-out duration in milliseconds")

    # Future / Compatibility extensions
    overlap_ms: int = Field(default=0, ge=0, description="Reserved for DE-05 interruption overlap")
    interruption_mode: str = Field(default="none", description="Interruption transition mode")
    gain_adjustment_db: float = Field(default=0.0, ge=-24.0, le=12.0, description="Editorial level balancing gain")
    room_match_required: bool = Field(default=False, description="Reserved for DE-06 room acoustic matching")
    artifact_repairs: List[str] = Field(default_factory=list, description="Descriptions of surgical artifact repairs")

    # Observability & QC telemetry
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Editorial decision certainty [0.0 - 1.0]")
    decision_reason: str = Field(default="", description="Explainable machine/human-readable rationale for edits")
    diagnostics: List[str] = Field(default_factory=list, description="Diagnostic observations during editorial planning")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary inspectable editorial metadata")


class QCDiagnostic(BaseModel):
    """Diagnostic generated during dialogue quality control."""
    model_config = ConfigDict(extra="ignore")

    code: str
    severity: Literal["WARNING", "HARD_FAILURE"]
    message: str
    segment_uid: str = ""
    evidence: Dict[str, Any] = Field(default_factory=dict)


class DialogueQCReport(BaseModel):
    """
    Chapter-level Dialogue Editorial QC Report.
    Summarizes editorial actions, warnings, and hard failures.
    """
    model_config = ConfigDict(extra="ignore")

    chapter_num: int = Field(default=1)
    total_segments: int = Field(default=0, ge=0)
    edited_segments: int = Field(default=0, ge=0)
    breaths_kept: int = Field(default=0, ge=0)
    breaths_reduced: int = Field(default=0, ge=0)
    breaths_removed: int = Field(default=0, ge=0)
    pauses_adjusted: int = Field(default=0, ge=0)
    warnings: List[QCDiagnostic] = Field(default_factory=list)
    hard_failures: List[QCDiagnostic] = Field(default_factory=list)
    passed: bool = Field(default=True)

    @model_validator(mode="after")
    def verify_passed_status(self) -> "DialogueQCReport":
        if self.hard_failures and self.passed:
            object.__setattr__(self, "passed", False)
        return self

    @property
    def has_hard_failures(self) -> bool:
        return len(self.hard_failures) > 0 or not self.passed


