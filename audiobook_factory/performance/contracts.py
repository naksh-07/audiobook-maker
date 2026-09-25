#!/usr/bin/env python3
"""
Audiobook Factory - Performance Direction Contracts & Strictly Typed Schemas (Pydantic v2).
Defines contracts for Actor-Level Performance Direction, Multi-Take Banking,
Acoustic-Dramatic Performance Evaluation, and Pre-Mix Performance Fidelity Gates.
"""

from __future__ import annotations
import hashlib
from typing import List, Dict, Any, Optional, Literal
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


class AcousticEvidence(BaseModel):
    """Forensic acoustic waveform telemetry extracted from take."""
    model_config = ConfigDict(extra="ignore")

    peak_amplitude: float = Field(default=0.0, description="Absolute peak sample amplitude [0, 32768]")
    rms_dbfs: float = Field(default=-30.0, description="RMS level in dBFS")
    dc_bias: float = Field(default=0.0, description="Mean offset from zero")
    max_consecutive_clipped_samples: int = Field(default=0, description="Max consecutive samples pinned to digital rail")
    clipping_samples_pinned: int = Field(default=0, description="Max consecutive samples pinned to digital rail")
    spectral_flatness_mean: float = Field(default=0.05, description="Wiener spectral flatness [0.0 = harmonic, 1.0 = noise]")
    hf_ratio_mean: float = Field(default=0.10, description="Energy ratio above 4kHz")
    dead_air_sec: float = Field(default=0.0, description="Measured trailing or unmotivated silence in seconds")
    is_clipped: bool = Field(default=False, description="Whether hard clipping is detected")
    snr_db: float = Field(default=30.0, description="Estimated signal-to-noise ratio in dB")

    @property
    def spectral_flatness(self) -> float:
        return self.spectral_flatness_mean


class ProsodyEvidence(BaseModel):
    """Multidimensional prosodic pitch, energy, and inflection telemetry."""
    model_config = ConfigDict(extra="ignore")

    f0_median_hz: float = Field(default=0.0, description="Median fundamental frequency in Hz")
    f0_iqr_hz: float = Field(default=0.0, description="F0 interquartile range (pitch dispersion/stability)")
    f0_min_hz: float = Field(default=0.0, description="Minimum voiced F0 in Hz")
    f0_max_hz: float = Field(default=0.0, description="Maximum voiced F0 in Hz")
    f0_variance: float = Field(default=0.0, description="F0 standard deviation across voiced frames")
    dynamic_range_db: float = Field(default=0.0, description="Crest factor / peak-to-floor dynamic range in dB")
    energy_variance: float = Field(default=0.0, description="Variance of frame RMS energy")
    is_monotonic_pitch_locked: bool = Field(default=False, description="Whether delivery exhibits unnatural robotic pitch lock")
    has_pitch_rupture: bool = Field(default=False, description="Whether unmotivated octave-jumping pitch glitch occurred")


class PacingEvidence(BaseModel):
    """Syllabic and word delivery timing telemetry."""
    model_config = ConfigDict(extra="ignore")

    words_per_sec: float = Field(default=3.1, description="Measured speaking rate in words/second")
    target_wps: float = Field(default=3.1, description="Dramatically anticipated target speaking rate")
    wps_ratio: float = Field(default=1.0, description="Measured WPS / Target WPS")
    local_rate_variance: float = Field(default=0.0, description="Speech rate acceleration/deceleration variance")
    speech_duration_sec: float = Field(default=0.0, description="Duration of active speech excluding pauses")
    pause_duration_total_ms: int = Field(default=0, description="Total non-speech silence duration in milliseconds")
    pause_count: int = Field(default=0, description="Number of detected pause intervals")
    dramatic_timing_fit: float = Field(default=1.0, ge=0.0, le=1.0, description="Adherence to dramatic timing instructions")

    @property
    def words_per_second(self) -> float:
        return self.words_per_sec


class VoiceIdentityEvidence(BaseModel):
    """Acoustic identity consistency telemetry against character reference signature."""
    model_config = ConfigDict(extra="ignore")

    measured_f0_hz: float = Field(default=0.0)
    baseline_f0_hz: float = Field(default=0.0)
    f0_deviation_pct: float = Field(default=0.0)
    measured_centroid_hz: float = Field(default=0.0)
    baseline_centroid_hz: float = Field(default=0.0)
    similarity_score: float = Field(default=1.0, ge=0.0, le=1.0)
    drift_detected: bool = Field(default=False)
    is_hard_gate_violation: bool = Field(default=False, description="Catastrophic voice drift exceeding hard gate")


TakeSelectionStatus = Literal[
    "ACCEPT",
    "ACCEPT_WITH_WARNING",
    "REVIEW",
    "REGENERATE",
    "NO_ACCEPTABLE_TAKE",
]


class EmotionRealizationEvidence(BaseModel):
    """Forensic & dramatic telemetry for emotional realization fidelity."""
    model_config = ConfigDict(extra="ignore")

    intended_emotion: str = Field(default="neutral")
    observed_markers: List[str] = Field(default_factory=list)
    intensity_fit: float = Field(default=1.0, ge=0.0, le=1.0)
    restraint_adherence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_teleportation_violation: bool = Field(default=False)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    diagnostics: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)


class IntentRealizationEvidence(BaseModel):
    """Dramatic communicative actioning and subtext realization telemetry."""
    model_config = ConfigDict(extra="ignore")

    actioning_verb: str = Field(default="speak")
    actioning_communicated: bool = Field(default=True)
    subtext_fit: float = Field(default=1.0, ge=0.0, le=1.0)
    power_leverage_fit: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    diagnostics: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)


class EmphasisEvidence(BaseModel):
    """Forensic acoustic prominence telemetry for targeted emphasis/de-emphasis words."""
    model_config = ConfigDict(extra="ignore")

    target_emphasis_words: List[str] = Field(default_factory=list)
    target_de_emphasis_words: List[str] = Field(default_factory=list)
    detected_prominence: Dict[str, float] = Field(default_factory=dict)
    emphasis_fidelity: float = Field(default=1.0, ge=0.0, le=1.0)
    diagnostics: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)


class BreathEvidence(BaseModel):
    """Forensic respiratory and physical staging acoustic telemetry."""
    model_config = ConfigDict(extra="ignore")

    expected_behavior: BreathBehavior = Field(default="steady")
    physical_state: PhysicalStagingState = Field(default="normal")
    pre_roll_breath_detected: bool = Field(default=False)
    post_roll_breath_detected: bool = Field(default=False)
    physical_strain_match: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    diagnostics: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)

    @property
    def breath_detected(self) -> bool:
        return self.pre_roll_breath_detected or self.post_roll_breath_detected


class EvaluationDimensionScore(BaseModel):
    """Evaluation score and qualitative diagnosis for a single performance dimension."""
    model_config = ConfigDict(extra="ignore")

    dimension: str = Field(..., description="Dimension name (e.g. 'intent_match', 'subtext')")
    score: float = Field(..., ge=0.0, le=1.0, description="Normalized score from 0.0 to 1.0")
    rating: Literal["strong", "moderate", "weak", "unacceptable"] = Field(default="strong")
    rationale: str = Field(default="", description="Explainable rationale for this score")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Measurement certainty [0.0 - 1.0]")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Supporting telemetry and metrics")
    reason_codes: List[str] = Field(default_factory=list, description="Machine-readable diagnostic reason codes")


class PerceptualPerformanceEvidence(BaseModel):
    """Multi-dimensional perceptual acting believability and dramatic fit telemetry."""
    model_config = ConfigDict(extra="ignore")

    dimensions: Dict[str, EvaluationDimensionScore] = Field(default_factory=dict)
    composite_perceptual_score: float = Field(default=1.0, ge=0.0, le=1.0)
    perceptual_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provider: str = Field(default="heuristic", description="Evidence source: heuristic or external_judge")
    diagnostics: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)

    def _get_dim(self, name: str) -> EvaluationDimensionScore:
        if name in self.dimensions:
            return self.dimensions[name]
        return EvaluationDimensionScore(
            dimension=name,
            score=self.composite_perceptual_score,
            confidence=self.perceptual_confidence,
            rating="strong" if self.composite_perceptual_score >= 0.80 else ("moderate" if self.composite_perceptual_score >= 0.65 else "weak"),
            rationale="Default dimension score derived from composite",
            reason_codes=[],
        )

    @property
    def naturalness(self) -> EvaluationDimensionScore:
        return self._get_dim("naturalness")

    @property
    def acting_believability(self) -> EvaluationDimensionScore:
        return self._get_dim("acting_believability")

    @property
    def emotional_fidelity(self) -> EvaluationDimensionScore:
        return self._get_dim("emotional_fidelity")

    @property
    def intent_fidelity(self) -> EvaluationDimensionScore:
        return self._get_dim("intent_fidelity")

    @property
    def subtext_fidelity(self) -> EvaluationDimensionScore:
        return self._get_dim("subtext_fidelity")

    @property
    def prosodic_fit(self) -> EvaluationDimensionScore:
        return self._get_dim("prosodic_fit")

    @property
    def scene_fit(self) -> EvaluationDimensionScore:
        return self._get_dim("scene_fit")

    @property
    def dialogue_reactivity(self) -> EvaluationDimensionScore:
        return self._get_dim("dialogue_reactivity")


class EvidenceFusionResult(BaseModel):
    """8-Layer Hierarchical Evidence Fusion Decision."""
    model_config = ConfigDict(extra="ignore")

    layer_passed: Dict[str, bool] = Field(default_factory=dict)
    hard_gate_reasons: List[str] = Field(default_factory=list)
    fused_score: float = Field(default=0.0, ge=0.0, le=1.0)
    fused_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    status: TakeSelectionStatus = Field(default="ACCEPT")
    review_reasons: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)


class EvidenceFusionCalibrationConfig(BaseModel):
    """
    Isolated and configurable calibration parameters for hierarchical evidence fusion.
    These values are baseline hypotheses and are validated against golden benchmarks and human calibration data.
    """
    model_config = ConfigDict(extra="ignore")

    min_accept_score: float = Field(default=0.70, description="Minimum fused score for ACCEPT")
    high_quality_threshold: float = Field(default=0.75, description="High quality threshold")
    min_accept_confidence: float = Field(default=0.50, description="Minimum confidence for clean ACCEPT")
    low_confidence_review_threshold: float = Field(default=0.45, description="Confidence threshold triggering REVIEW")
    critical_defect_score: float = Field(default=0.55, description="Score threshold below which take triggers REGENERATE/REJECT")
    catastrophic_voice_drift_similarity: float = Field(default=0.45)
    alignment_confidence_hard_gate: float = Field(default=0.35)


class PerformanceEvidence(BaseModel):
    """
    First-Class Performance Evidence Model.
    Aggregates all measurable acoustic, prosodic, pacing, alignment, emotion, intent, emphasis, breath, and identity signals.
    """
    model_config = ConfigDict(extra="ignore")

    acoustic: AcousticEvidence = Field(default_factory=AcousticEvidence)
    prosody: ProsodyEvidence = Field(default_factory=ProsodyEvidence)
    pacing: PacingEvidence = Field(default_factory=PacingEvidence)
    voice_identity: Optional[VoiceIdentityEvidence] = None
    alignment_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    alignment_diagnostics: List[str] = Field(default_factory=list)
    emotion: Optional[EmotionRealizationEvidence] = None
    intent: Optional[IntentRealizationEvidence] = None
    emphasis: Optional[EmphasisEvidence] = None
    breath: Optional[BreathEvidence] = None
    perceptual: Optional[PerceptualPerformanceEvidence] = None


class EvaluatorCalibrationConfig(BaseModel):
    """
    Isolated and configurable initial calibration parameters for performance evaluation.
    These values are baseline hypotheses and are validated against golden benchmarks and human calibration data.
    """
    model_config = ConfigDict(extra="ignore")

    base_neutral_score: float = Field(default=0.75, description="Neutral evidence baseline")
    target_wps_nominal: float = Field(default=3.1, description="Nominal conversational words per second")
    clipping_pinned_threshold: int = Field(default=6, description="Consecutive pinned samples triggering clipping penalty")
    dc_bias_threshold: float = Field(default=1200.0, description="DC offset penalty threshold")
    dead_air_threshold_sec: float = Field(default=1.5, description="Trailing silence penalty threshold")
    vocoder_flatness_threshold: float = Field(default=0.40, description="White noise vocoder static threshold")
    monotonic_f0_var_threshold: float = Field(default=5.0, description="F0 variance threshold below which voice is robotic")
    explosive_min_rms_dbfs: float = Field(default=-24.0, description="Minimum RMS dBFS for explosive projection")
    intimate_max_rms_dbfs: float = Field(default=-18.0, description="Maximum RMS dBFS for intimate whisper")
    restraint_overacting_peak: float = Field(default=31000.0, description="Peak amplitude threshold indicating shouting")
    restraint_overacting_rms: float = Field(default=-15.0, description="RMS dBFS threshold indicating unsuppressed shouting")
    catastrophic_drift_similarity: float = Field(default=0.45, description="Similarity threshold for catastrophic voice drift hard gate")
    catastrophic_f0_dev_pct: float = Field(default=60.0, description="Pitch deviation percentage (e.g. 60.0%) triggering catastrophic voice drift hard gate")


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
    evidence: Optional[PerformanceEvidence] = Field(default=None, description="Forensic acoustic, prosodic, and pacing evidence")


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
    alignment_result: Optional[Any] = Field(default=None, repr=False, description="Detailed alignment result for this take")
    is_selected: bool = Field(default=False, description="Whether this take was selected for final mix")
    selection_reason: str = Field(default="", description="Explainable reason for selection or rejection")
    selection_result: Optional[Any] = Field(default=None, repr=False, description="Detailed selection outcome and provenance")


class TakeSelectorCalibrationConfig(BaseModel):
    """
    Isolated and configurable initial calibration parameters for take selection.
    These values are baseline hypotheses and are validated against golden benchmarks.
    """
    model_config = ConfigDict(extra="ignore")

    pairwise_margin_threshold: float = Field(default=0.05, description="Margin threshold triggering pairwise judging")
    clipping_pinned_hard_gate: int = Field(default=12, description="Pinned clipped samples triggering hard gate rejection")
    dc_bias_hard_gate: float = Field(default=1500.0, description="DC offset threshold triggering hard gate rejection")
    dead_air_hard_gate_sec: float = Field(default=2.0, description="Trailing silence seconds triggering hard gate rejection")
    min_duration_sec: float = Field(default=0.25, description="Minimum duration in seconds for valid take")
    max_duration_multiplier: float = Field(default=3.5, description="Maximum duration multiplier over expected target")
    alignment_confidence_hard_gate: float = Field(default=0.35, description="Minimum alignment confidence threshold")
    max_word_omission_pct: float = Field(default=50.0, description="Maximum word omission percentage threshold")
    voice_drift_penalty: float = Field(default=0.40, description="Score penalty for detected voice drift")
    voice_match_bonus: float = Field(default=0.05, description="Bonus for rock-solid signature match")
    unnaturalness_penalty: float = Field(default=0.15, description="Score penalty for unnaturalness (< threshold)")
    unnaturalness_threshold: float = Field(default=0.70, description="Naturalness threshold triggering penalty")
    min_confidence_review_threshold: float = Field(default=0.40, description="Confidence threshold triggering human review flag")
    chemistry_weight: float = Field(default=0.15, description="Weight multiplier for conversational chemistry bonus/penalty")
    continuity_weight: float = Field(default=0.05, description="Weight multiplier for performance continuity bonus/penalty")
    allow_degraded_winner: bool = Field(default=False, description="When False, returns winner=None with status NO_ACCEPTABLE_TAKE when all takes fail hard gates; when True, falls back to best degraded take.")



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


class TakeSelectionResult(BaseModel):
    """
    First-Class Take Selection Result Contract.
    Captures the winning take (or None if NO_ACCEPTABLE_TAKE), runner up, margin, confidence,
    status, and explainable reason codes.
    """
    model_config = ConfigDict(extra="ignore")

    winner: Optional[TakeVariant] = Field(default=None, description="The chosen winning take, or None if NO_ACCEPTABLE_TAKE")
    runner_up: Optional[TakeVariant] = Field(default=None, description="The closest competing candidate take")
    winner_score: float = Field(default=0.0, ge=0.0, le=1.0)
    runner_up_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    margin: float = Field(default=0.0, description="Score delta between winner and runner-up")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Selection certainty [0.0 - 1.0]")
    status: TakeSelectionStatus = Field(default="ACCEPT", description="Granular selection outcome")
    reason_codes: List[str] = Field(default_factory=list, description="Machine-readable selection reason codes")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Supporting acoustic and performance evidence")
    fusion_result: Optional[EvidenceFusionResult] = Field(default=None, description="Hierarchical evidence fusion outcome")
    review_required: bool = Field(default=False, description="Flagged for human audio engineer review")

