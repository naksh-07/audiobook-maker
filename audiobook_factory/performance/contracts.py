#!/usr/bin/env python3
"""
Audiobook Factory - Performance Direction Contracts & Strictly Typed Schemas (Pydantic v2).
Defines contracts for Actor-Level Performance Direction, Multi-Take Banking,
Acoustic-Dramatic Performance Evaluation, and Pre-Mix Performance Fidelity Gates.
"""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal, Union
from pydantic import BaseModel, Field, ConfigDict, model_validator


PerformanceProvenanceMode = Literal[
    "SOURCE_DIRECT",
    "DRAMATIC_CANON",
    "INFERRED_PERFORMANCE",
    "DRAMATIC_INTERPRETATION",
]

PerformancePriority = Literal["standard", "focused", "high", "climactic"]

SilenceType = Literal[
    "none",
    "punctuation",
    "breathing",
    "hesitation",
    "dramatic_silence",
    "reaction_silence",
    "conversational_gap",
    "emotional_freeze",
    "interruption_cut",
]

InterruptionBehavior = Literal["none", "abrupt_cut", "overlap_start", "fade_under"]
TurnTakingBehavior = Literal["immediate", "delayed_reaction", "reluctant", "eager_counter", "defensive_parry"]
PitchBehavior = Literal["neutral", "low_resonant", "high_tense", "monotone", "wavering", "dropping", "rising"]
ResonancePlacement = Literal["chest", "throat", "head", "whisper_air"]
VocalTexture = Literal["smooth", "raspy", "brittle", "warm", "gravelly", "harsh"]
BreathBehavior = Literal["steady", "sharp_intake", "labored", "suppressed", "trembling", "exhausted", "holding_breath"]
PowerPosition = Literal["dominant", "submissive", "contested", "neutral"]
LeverageLevel = Literal["commanding", "holding", "equal", "vulnerable", "none"]
IntimacyLevel = Literal["formal", "colleague", "familiar", "intimate", "hostile"]
PhysicalStagingState = Literal["normal", "wounded", "exhausted", "combat_strain", "leaning_in", "withdrawing", "hidden"]


class EvaluationDimensionScore(BaseModel):
    """Evaluation score and qualitative diagnosis for a single performance dimension."""
    model_config = ConfigDict(extra="ignore")

    dimension: str = Field(..., description="Dimension name (e.g. 'intent_match', 'subtext')")
    score: float = Field(..., ge=0.0, le=1.0, description="Normalized score from 0.0 to 1.0")
    rating: Literal["strong", "moderate", "weak", "unacceptable"] = Field(default="strong")
    rationale: str = Field(default="", description="Explainable rationale for this score")


class PerformanceDirection(BaseModel):
    """
    First-Class Performance Direction Contract.
    Encapsulates exactly how an actor should perform a specific dramatic moment.
    Decouples dramatic intent from provider-specific TTS APIs while maintaining full provenance.
    """
    model_config = ConfigDict(extra="ignore")

    direction_id: str = Field(default="", description="Unique direction identifier (e.g. 'pd_c001_s0001')")
    segment_uid: str = Field(default="", description="Matching ScreenplaySegment UID")
    index: int = Field(..., ge=1, description="1-indexed sequence number in chapter script")
    speaker: str = Field(..., description="Canonical character name delivering line")
    target_character: Optional[str] = Field(default=None, description="Intended character recipient of the dialogue")
    narrative_mode: str = Field(default="direct_dialogue", description="Narrative delivery mode")
    provenance_mode: PerformanceProvenanceMode = Field(
        default="SOURCE_DIRECT",
        description="Fidelity distinction: direct source fact vs dramatic interpretation",
    )

    # 1. Dramatic State
    character_state: str = Field(default="neutral", description="Current psychological / emotional status")
    objective: str = Field(default="", description="Immediate tactical beat objective")
    actioning: str = Field(default="speak", description="Active transitive verb intent (e.g. 'corner', 'reassure')")
    surface_emotion: str = Field(default="neutral", description="Outwardly presented emotion")
    underlying_emotion: Optional[str] = Field(default=None, description="Concealed internal emotion")
    subtext: Optional[str] = Field(default=None, description="Unspoken subtextual reality")
    subtext_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence in inferred subtext")
    intensity: str = Field(default="medium", description="Acoustic headroom: low, medium, high, explosive")
    tension_before: float = Field(default=0.5, ge=0.0, le=1.0, description="Tension entering moment")
    tension_after: float = Field(default=0.5, ge=0.0, le=1.0, description="Tension exiting moment")

    # 2. Relationship & Social Dynamics
    relationship_to_target: Optional[str] = Field(default=None, description="Relational stance toward target")
    power_position: PowerPosition = Field(default="neutral", description="Hierarchical positioning in beat")
    leverage: LeverageLevel = Field(default="equal", description="Tactical leverage level")
    vulnerability: float = Field(default=0.3, ge=0.0, le=1.0, description="Degree of emotional exposure")
    trust_level: float = Field(default=0.5, ge=0.0, le=1.0, description="Interpersonal trust")
    social_mask: Optional[str] = Field(default=None, description="Public persona masking true state")
    intimacy_level: IntimacyLevel = Field(default="formal", description="Social distance / intimacy")

    # 3. Vocal Behavior
    pace: float = Field(default=1.0, ge=0.5, le=2.0, description="Relative speed multiplier")
    energy: float = Field(default=0.7, ge=0.0, le=1.0, description="Vocal projection / adrenaline")
    pitch_behavior: PitchBehavior = Field(default="neutral", description="Pitch contour behavior")
    articulation: str = Field(default="natural", description="Articulation clarity: crisp, colloquial, sluggish, slurred, sharp")
    resonance: ResonancePlacement = Field(default="chest", description="Vocal tract resonance focus")
    breath_behavior: BreathBehavior = Field(default="steady", description="Organic respiratory behavior")
    vocal_texture: VocalTexture = Field(default="smooth", description="Texture timbre")
    restraint: float = Field(default=0.5, ge=0.0, le=1.0, description="Suppression vs explosion (0.0=raw, 1.0=iron)")
    emphasis_words: List[str] = Field(default_factory=list, description="Target words to organically emphasize")
    de_emphasis_words: List[str] = Field(default_factory=list, description="Words to underplay or swallow")

    # 4. Timing & Physical Execution
    pause_before_ms: int = Field(default=0, ge=0, description="Silence before speech starts in milliseconds")
    pause_after_ms: int = Field(default=400, ge=0, description="Silence after speech ends in milliseconds")
    pre_roll_breath_ms: int = Field(default=0, ge=0, description="Breath intake duration before onset")
    post_roll_breath_ms: int = Field(default=0, ge=0, description="Breath release duration after offset")
    hesitation_ms: int = Field(default=0, ge=0, description="Hesitation pause inside or before line")
    silence_type: SilenceType = Field(default="punctuation", description="Qualitative category of silence")
    interruption_behavior: InterruptionBehavior = Field(default="none", description="Interruption dynamics")
    turn_taking_behavior: TurnTakingBehavior = Field(default="immediate", description="Conversational turn latency")

    # 5. Physical & Spatial Staging
    physical_state: PhysicalStagingState = Field(default="normal", description="Physical strain / condition")
    blocking_directive: Optional[str] = Field(default=None, description="Dramatically meaningful physical action")
    spatial_intent: Optional[str] = Field(default=None, description="Staging acoustic intent")
    proximity: str = Field(default="normal_room", description="Microphone proximity zone")
    pan: float = Field(default=0.0, ge=-1.0, le=1.0, description="Stereo azimuth pan")

    # 6. Priority & Take Requirements
    performance_priority: PerformancePriority = Field(default="standard", description="Performance focus priority")
    required_takes: int = Field(default=1, ge=1, le=4, description="Number of candidate takes to generate")
    delivery_intent_summary: str = Field(default="", description="Explainable 1-line actor directive")

    @model_validator(mode="before")
    @classmethod
    def set_deterministic_id(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("direction_id"):
                idx = data.get("index", 1)
                spk = str(data.get("speaker", "narrator")).lower().replace(" ", "_")
                uid = str(data.get("segment_uid", f"seg_{idx}"))
                h = hashlib.sha256(f"{idx}:{spk}:{uid}".encode("utf-8")).hexdigest()[:8]
                data["direction_id"] = f"pd_{idx:04d}_{spk}_{h}"
            if "required_takes" not in data or data.get("required_takes") is None:
                prio = data.get("performance_priority", "standard")
                if prio == "climactic":
                    data["required_takes"] = 3
                elif prio == "high":
                    data["required_takes"] = 2
                elif prio == "focused":
                    data["required_takes"] = 2
                else:
                    data["required_takes"] = 1
        return data


class PerformanceEvaluationResult(BaseModel):
    """
    Comprehensive evaluation of a synthesized audio take against PerformanceDirection.
    Compares 8 distinct dimensions with explainable diagnostics.
    """
    model_config = ConfigDict(extra="ignore")

    take_id: str = Field(..., description="Unique take identifier")
    segment_uid: str = Field(default="", description="Matching segment UID")
    overall_score: float = Field(..., ge=0.0, le=1.0, description="Composite weighted quality score")
    passed: bool = Field(default=True, description="Whether take satisfies performance thresholds")
    dimensions: Dict[str, EvaluationDimensionScore] = Field(
        default_factory=dict,
        description="Individual dimension scores (intent, emotion, prosody, pacing, subtext, character, relationship, naturalness)"
    )
    diagnostics: List[str] = Field(default_factory=list, description="Diagnostic observations and feedback")
    recommendation: Literal["accept", "regenerate", "downgrade"] = Field(default="accept")
    voice_identity_score: Optional[float] = Field(default=None, description="Acoustic similarity score against reference voice bank")
    voice_drift_detected: bool = Field(default=False, description="Whether acoustic drift exceeded calibrated threshold")


class ChemistryEvaluationResult(BaseModel):
    """
    Post-synthesis acoustic and dramatic chemistry evaluation across adjacent dialogue turns.
    Evaluates response latency, interruption sharpness, and dynamic energy contrast.
    """
    model_config = ConfigDict(extra="ignore")

    prev_take_id: str = Field(..., description="Unique take identifier of preceding turn")
    curr_take_id: str = Field(..., description="Unique take identifier of responding turn")
    prev_speaker: str = Field(..., description="Speaker of preceding turn")
    curr_speaker: str = Field(..., description="Speaker of responding turn")
    expected_gap_ms: int = Field(default=400, ge=0, description="Dramatically anticipated gap in milliseconds")
    actual_gap_ms: Optional[int] = Field(default=None, description="Acoustic or assembled gap between turns")
    pause_fidelity_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Turn-taking pause accuracy")
    interruption_quality_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Interruption sharpness score")
    energy_contrast_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Energy dynamic appropriateness")
    composite_chemistry_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Composite conversational chemistry score")
    passed: bool = Field(default=True, description="Whether conversational chemistry passes threshold")
    diagnostics: List[str] = Field(default_factory=list, description="Diagnostic observations")


class TakeVariant(BaseModel):
    """
    Candidate performance take generated for a screenplay segment.
    """
    model_config = ConfigDict(extra="ignore")

    take_id: str = Field(..., description="Unique take identifier (e.g. 'c001_s0001_take_b')")
    segment_uid: str = Field(default="", description="Matching ScreenplaySegment UID")
    segment_index: int = Field(..., ge=1, description="1-indexed sequence number")
    variant_type: Literal[
        "restraint",
        "vulnerable",
        "exposed",
        "standard",
        "alternative_cadence",
        "more_restrained",
        "more_vulnerable",
        "slower_heavier",
        "colder",
        "less_energetic",
        "more_intimate",
        "more_urgent",
    ] = Field(
        default="standard",
        description="Artistic variation avenue"
    )
    audio_path: str = Field(..., description="Filesystem path to generated audio WAV")
    duration_sec: float = Field(default=0.0, ge=0.0, description="Audio duration in seconds")
    direction: PerformanceDirection = Field(..., description="PerformanceDirection guiding this take")
    evaluation: Optional[PerformanceEvaluationResult] = Field(default=None, description="Dimensional evaluation result")
    is_selected: bool = Field(default=False, description="Whether this take was selected for final mix")
    selection_reason: str = Field(default="", description="Explainable reason for selection or rejection")


class PerformanceFidelityReport(BaseModel):
    """
    Pre-Mix Quality Gate Report (Gate 2.8).
    Audits complete chapter performance directions, takes, continuity, and fidelity before audio mastering.
    """
    model_config = ConfigDict(extra="ignore")

    chapter_id: str = Field(..., description="Chapter identifier")
    passed: bool = Field(default=True, description="Whether chapter passed Performance Fidelity Gate")
    total_segments: int = Field(default=0, ge=0)
    total_takes_generated: int = Field(default=0, ge=0)
    avg_evaluation_score: float = Field(default=0.0, ge=0.0, le=1.0)
    dimension_averages: Dict[str, float] = Field(default_factory=dict)
    teleportation_violations: int = Field(default=0, ge=0)
    unresolved_issues: List[str] = Field(default_factory=list)
    created_at: str = Field(default="", description="ISO timestamp of audit")
