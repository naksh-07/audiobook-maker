#!/usr/bin/env python3
"""
Audiobook Factory - Stage 12: Mastering V2 Contracts.
=====================================================
Defines typed, immutable, and inspectable data contracts for the P0 Mastering Core:
- MasteringProfile: Bounded configuration parameters for broadcast mastering.
- MasteringAnalysisFacts: Ground-truth physical, acoustic, and DSP facts measured from rendered audio.
- MasteringQCResult: Standardized machine-readable QC evaluation (PASS / WARN / FAIL).
- MasteringRequest: Parameterized request for mastering a Stage 11 premaster.
- MasteringResult: Complete output payload including pre/post analysis, QC, and provenance.
- MasteringLedger: Persistent disk artifact (chapter_XXX_mastering_ledger.json).
"""

from __future__ import annotations
import datetime
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal, Union
from pydantic import BaseModel, Field, ConfigDict, model_validator


class MasteringProfile(BaseModel):
    """
    Deterministic broadcast mastering parameters adhering to EBU R128 and Audible/ACX specifications.
    Every parameter is bounded to guarantee transparent, un-distorted audio.
    """
    model_config = ConfigDict(extra="ignore")

    profile_name: str = Field(default="commercial_audiobook_standard", description="Profile identifier")
    target_lufs: float = Field(default=-19.0, ge=-24.0, le=-14.0, description="EBU R128 integrated loudness target in LUFS")
    tolerance_lu: float = Field(default=0.5, ge=0.1, le=2.0, description="Integrated loudness allowable tolerance in LU")
    true_peak_ceiling_dbtp: float = Field(default=-1.5, ge=-3.0, le=-0.5, description="Inter-sample peak ceiling in dBTP")
    target_lra: float = Field(default=8.5, ge=4.0, le=14.0, description="Target loudness range in LU")
    subsonic_highpass_hz: int = Field(default=28, ge=18, le=45, description="Subsonic rumble filter cutoff frequency in Hz")
    enable_dual_pass_linear: bool = Field(default=True, description="Enforce dual-pass linear loudnorm to prevent dynamic pumping")
    limiter_ceiling_db: float = Field(default=-1.6, ge=-3.5, le=-0.8, description="Peak limiter ceiling threshold in dBFS")
    limiter_release_ms: int = Field(default=50, ge=10, le=250, description="Peak limiter release time in milliseconds")
    dither_type: str = Field(default="tpdf", description="Dither algorithm: tpdf, triangular_hp, none")
    output_sample_rate: int = Field(default=48000, description="Standard output sample rate in Hz")
    output_channels: int = Field(default=2, description="Output channel count (2 = stereo)")
    max_retries: int = Field(default=2, ge=0, le=3, description="Hard bound on mastering remediation attempts")
    min_dialogue_to_mix_ratio_db: float = Field(default=0.0, description="Minimum dialogue to mix loudness ratio in dB")


class MasteringAnalysisFacts(BaseModel):
    """
    Physical, measurable acoustic facts probed directly from rendered audio.
    Strictly zero hallucinated or estimated figures.
    """
    model_config = ConfigDict(extra="ignore")

    filepath: str = Field(..., description="Absolute path to analyzed audio file")
    duration_sec: float = Field(default=0.0, ge=0.0, description="Duration in seconds")
    sample_rate: int = Field(default=48000, description="Audio sample rate in Hz")
    channels: int = Field(default=2, description="Channel count")
    integrated_lufs: float = Field(default=-70.0, description="EBU R128 Integrated Loudness in LUFS")
    short_term_max_lufs: Optional[float] = Field(default=None, description="Maximum short-term (3s window) loudness in LUFS")
    momentary_max_lufs: Optional[float] = Field(default=None, description="Maximum momentary (400ms window) loudness in LUFS")
    loudness_range_lra: Optional[float] = Field(default=None, description="Loudness range (LRA) in LU")
    true_peak_dbtp: Optional[float] = Field(default=None, description="True peak level in dBTP")
    sample_peak_dbfs: Optional[float] = Field(default=None, description="Peak sample level in dBFS")
    rms_level_dbfs: Optional[float] = Field(default=None, description="Root-mean-square energy level in dBFS")
    dynamic_range_db: Optional[float] = Field(default=None, description="Dynamic range (Sample Peak - RMS) in dB")
    crest_factor_db: Optional[float] = Field(default=None, description="Crest factor ratio in dB")
    spectral_centroid_hz: Optional[float] = Field(default=None, description="Spectral brightness center in Hz")
    spectral_rolloff_hz: Optional[float] = Field(default=None, description="85% energy rolloff frequency in Hz")
    spectral_flatness: Optional[float] = Field(default=None, description="Spectral flatness measure (0.0 to 1.0)")
    phase_correlation: float = Field(default=1.0, ge=-1.0, le=1.0, description="Stereo phase correlation coefficient r")
    mono_compatible: bool = Field(default=True, description="Whether phase correlation r >= 0.20")
    silence_ratio: Optional[float] = Field(default=None, description="Fraction of frames below -60 dBFS")
    dead_air_sec: float = Field(default=0.0, ge=0.0, description="Total dead-air silence duration (>2.0s below -50dB)")
    transient_count: Optional[int] = Field(default=None, description="Detected transient peak count")
    clipping_detected: bool = Field(default=False, description="Flag indicating true-peak overshoots > 0.0 dBTP")
    is_valid_audio: bool = Field(default=True, description="File integrity check (non-empty, non-corrupt)")


class MasteringQCResult(BaseModel):
    """
    Machine-readable Quality Certification for a mastered audio deliverable.
    Enforces fail-closed safety: critical failures block pipeline signoff.
    """
    model_config = ConfigDict(extra="ignore")

    status: Literal["PASS", "WARN", "FAIL"] = Field(default="PASS", description="Mastering certification status")
    passed: bool = Field(default=True, description="Whether mastering passed all critical requirements")
    checks: Dict[str, str] = Field(default_factory=dict, description="Individual test verdicts (PASS/WARN/FAIL)")
    failures: List[str] = Field(default_factory=list, description="Critical blocking defect codes")
    warnings: List[str] = Field(default_factory=list, description="Non-blocking acoustic warnings")
    details: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic evidence ledger")


MasteringIssueSeverity = Literal["CRITICAL", "MAJOR", "MINOR", "INFO"]


class MasteringIssue(BaseModel):
    """
    Standardized, inspectable mastering issue identified by MasteringJudge.
    Every issue must be supported by empirical acoustic evidence.
    """
    model_config = ConfigDict(extra="ignore")

    issue_type: str = Field(..., description="Machine-readable issue category")
    severity: MasteringIssueSeverity = Field(default="MINOR", description="Impact severity")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Measurement confidence")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Objective measurement evidence")
    recommended_action: str = Field(..., description="Actionable correction recommendation")
    bounded_parameters: Dict[str, Any] = Field(default_factory=dict, description="DSP adjustment suggestions within safety bounds")


class MasteringActionPlan(BaseModel):
    """
    Bounded action plan generated by MasteringJudge before deterministic rendering.
    Enforces that all recommendations are clamped within strict safety envelopes.
    """
    model_config = ConfigDict(extra="ignore")

    chapter_id: str = Field(..., description="Chapter identifier")
    issues: List[MasteringIssue] = Field(default_factory=list, description="Prioritized detected issues")
    overall_verdict: Literal["PASS", "ADJUST", "REJECT"] = Field(default="PASS", description="Mastering judge decision")
    adjusted_profile: Optional[MasteringProfile] = Field(default=None, description="Bounded profile override if ADJUST")
    explanation: str = Field(default="", description="Summary of reasoning")


class DialogueProtectionReport(BaseModel):
    """
    Forensic dialogue protection audit report evaluating speech intelligibility,
    masking ratios, and dramatic dynamic contrast.
    """
    model_config = ConfigDict(extra="ignore")

    chapter_id: str = Field(..., description="Chapter identifier")
    dialogue_lufs: float = Field(default=-70.0, description="Measured dialogue stem integrated loudness")
    mix_lufs: float = Field(default=-70.0, description="Measured mix integrated loudness")
    dialogue_anchor_ratio_db: float = Field(default=0.0, description="Ratio (DX_LUFS - Mix_LUFS)")
    masking_risk: Literal["NONE", "LOW", "MODERATE", "SEVERE"] = Field(default="NONE", description="Risk of speech masking")
    clarity_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Speech clarity score")
    dynamic_contrast_preserved: bool = Field(default=True, description="Whether whispers/emotional dynamics are preserved")
    recommended_adjustments: Dict[str, Any] = Field(default_factory=dict, description="Recommended safe adjustments")
    status: Literal["PASS", "WARN", "FAIL"] = Field(default="PASS", description="Dialogue protection status")


class BookMasterProfile(BaseModel):
    """
    Book-level acoustic profile capturing what 'belongs to this audiobook'.
    Derived via robust outlier-resistant statistics across representative chapters.
    """
    model_config = ConfigDict(extra="ignore")

    version: str = Field(default="1.0.0", description="Book profile schema version")
    book_id: str = Field(..., description="Book identifier")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence based on sample count")
    sample_count: int = Field(default=0, ge=0, description="Number of analyzed chapters")
    source_chapters: List[str] = Field(default_factory=list, description="List of source chapter IDs")
    target_lufs_median: float = Field(default=-19.0, description="Robust median integrated loudness")
    target_lufs_iqr: float = Field(default=0.5, description="Interquartile range for LUFS")
    true_peak_median_dbtp: float = Field(default=-1.5, description="Robust median true peak")
    dynamic_range_median_db: float = Field(default=6.0, description="Robust median dynamic range")
    crest_factor_median_db: float = Field(default=8.0, description="Robust median crest factor")
    lra_median: float = Field(default=8.5, description="Robust median loudness range")
    spectral_centroid_median_hz: float = Field(default=1200.0, description="Robust median spectral centroid")
    dialogue_anchor_median_db: float = Field(default=0.0, description="Robust median dialogue anchor ratio")
    phase_correlation_median: float = Field(default=0.95, description="Robust median stereo phase correlation")
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata and statistics distributions")

    def save_to_disk(self, target_path: Union[str, Path]) -> Path:
        p = Path(target_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return p

    @classmethod
    def load_from_disk(cls, target_path: Union[str, Path]) -> BookMasterProfile:
        p = Path(target_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Book master profile not found: {p}")
        return cls.model_validate(json.loads(p.read_text(encoding="utf-8")))


class DimensionDeviation(BaseModel):
    """Deviation of a single acoustic dimension from the BookMasterProfile."""
    model_config = ConfigDict(extra="ignore")

    metric: str = Field(..., description="Audited dimension name")
    measured_value: float = Field(..., description="Measured value in chapter")
    expected_value: float = Field(..., description="Book profile median value")
    delta: float = Field(..., description="Deviation delta (measured - expected)")
    tolerance: float = Field(..., description="Allowable tolerance band")
    status: Literal["PASS", "WARN", "FAIL"] = Field(default="PASS", description="Dimension status")
    is_intentional: bool = Field(default=False, description="Whether deviation is justified by dramatic scene intent")
    rationale: Optional[str] = Field(default=None, description="Justification or warning rationale")


class ChapterConsistencyAudit(BaseModel):
    """
    Chapter-level consistency evaluation comparing chapter metrics to the BookMasterProfile.
    Distinguishes intentional dramatic variation from accidental inconsistency.
    """
    model_config = ConfigDict(extra="ignore")

    chapter_id: str = Field(..., description="Chapter identifier")
    overall_status: Literal["PASS", "WARN", "REVIEW"] = Field(default="PASS", description="Consistency verdict")
    deviations: Dict[str, DimensionDeviation] = Field(default_factory=dict, description="Per-dimension deviation breakdown")
    is_intentional_variation: bool = Field(default=False, description="Whether variations are intentional")
    intentional_intent: Optional[str] = Field(default=None, description="Dramatic intent category, e.g. combat, whisper")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Consistency audit confidence")
    review_priority: Literal["NONE", "LOW", "MEDIUM", "HIGH"] = Field(default="NONE", description="Manual review urgency")
    details: Dict[str, Any] = Field(default_factory=dict, description="Audit telemetry")


class BookConsistencyReport(BaseModel):
    """Aggregated book-level consistency report across all mastered chapters."""
    model_config = ConfigDict(extra="ignore")

    book_id: str = Field(..., description="Book identifier")
    profile_version: str = Field(default="1.0.0", description="Book profile version used")
    total_chapters: int = Field(default=0, ge=0)
    passed_count: int = Field(default=0, ge=0)
    warn_count: int = Field(default=0, ge=0)
    review_count: int = Field(default=0, ge=0)
    chapter_audits: Dict[str, ChapterConsistencyAudit] = Field(default_factory=dict)
    summary_markdown: str = Field(default="")

    def save_to_disk(self, target_path: Union[str, Path]) -> Path:
        p = Path(target_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return p

    @classmethod
    def load_from_disk(cls, target_path: Union[str, Path]) -> BookConsistencyReport:
        p = Path(target_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Book consistency report not found: {p}")
        return cls.model_validate(json.loads(p.read_text(encoding="utf-8")))


PerceptualDimension = Literal[
    "intelligibility",
    "naturalness",
    "tonal_balance",
    "dynamic_integrity",
    "emotional_preservation",
    "spatial_coherence",
    "fatigue_risk",
]

PerceptualIssueSeverity = Literal["CRITICAL", "MAJOR", "MINOR", "INFO"]


class PerceptualIssue(BaseModel):
    """Specific perceptual issue detected with empirical evidence."""
    model_config = ConfigDict(extra="ignore")

    dimension: str = Field(..., description="Audited perceptual dimension")
    severity: PerceptualIssueSeverity = Field(default="MINOR", description="Perceptual issue severity")
    description: str = Field(..., description="Explainable description of perceptual concern")
    evidence: List[str] = Field(default_factory=list, description="Empirical evidence supporting this finding")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Perceptual critic confidence")
    recommended_action: Optional[str] = Field(default=None, description="Conservative recommendation")


class PerceptualEvaluation(BaseModel):
    """
    Structured perceptual evaluation of mastered audio as an experience.
    Evaluates 7 core acoustic/aesthetic dimensions with measurable evidence.
    """
    model_config = ConfigDict(extra="ignore")

    overall: Literal["PASS", "WARN", "REVIEW"] = Field(default="PASS", description="Perceptual evaluation status")
    scores: Dict[str, float] = Field(default_factory=dict, description="0.0 to 1.0 scores per perceptual dimension")
    issues: List[PerceptualIssue] = Field(default_factory=list, description="Detailed perceptual issues")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Overall evaluation confidence")
    evidence: List[str] = Field(default_factory=list, description="Consolidated evidence ledger")
    critic_version: str = Field(default="1.0.0", description="Perceptual critic version")


class ReferenceProfile(BaseModel):
    """
    Normalized acoustic/perceptual reference profile for genre or scene style benchmarking.
    Never used as absolute truth; provides context-aware baseline.
    """
    model_config = ConfigDict(extra="ignore")

    reference_id: str = Field(..., description="Reference profile identifier")
    reference_type: Literal[
        "narration",
        "dialogue",
        "intimate",
        "emotional",
        "action",
        "quiet",
        "music_heavy",
    ] = Field(..., description="Acoustic scenario type")
    version: str = Field(default="1.0.0", description="Reference profile version")
    target_lufs: float = Field(..., description="Reference integrated loudness in LUFS")
    dynamic_range_db: float = Field(..., description="Reference dynamic range in dB")
    crest_factor_db: float = Field(..., description="Reference crest factor in dB")
    spectral_centroid_hz: float = Field(..., description="Reference spectral centroid in Hz")
    dialogue_anchor_ratio_db: Optional[float] = Field(default=None, description="Reference vocal anchor ratio")
    phase_correlation: float = Field(default=1.0, description="Reference stereo correlation")
    tolerance_lufs: float = Field(default=1.5, description="Allowable LUFS tolerance")
    tolerance_crest: float = Field(default=3.0, description="Allowable crest factor tolerance")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Reference provenance and source notes")


class ReferenceComparisonResult(BaseModel):
    """Contextual comparison between mastered chapter and reference profile."""
    model_config = ConfigDict(extra="ignore")

    reference_id: str = Field(..., description="Target reference profile ID")
    reference_type: str = Field(..., description="Target reference type")
    comparison_status: Literal[
        "MATCH",
        "MILD_DEVIATION",
        "SIGNIFICANT_DEVIATION",
        "INAPPROPRIATE_COMPARISON",
    ] = Field(default="MATCH", description="Comparison outcome")
    is_appropriate: bool = Field(default=True, description="Whether reference is appropriate for this scene")
    deviations: Dict[str, float] = Field(default_factory=dict, description="Deviation deltas")
    notes: List[str] = Field(default_factory=list, description="Diagnostic notes")


class SceneMasteringDecision(BaseModel):
    """
    Structured scene-aware mastering decision preserving dramatic and narrative identity.
    Enforces that quiet != bad and action transients are preserved.
    """
    model_config = ConfigDict(extra="ignore")

    scene_type: Literal[
        "INTIMATE",
        "QUIET",
        "NORMAL",
        "EMOTIONAL",
        "TENSION",
        "ACTION",
        "MUSIC_HEAVY",
        "AMBIENCE_HEAVY",
        "DIALOGUE_HEAVY",
    ] = Field(default="NORMAL", description="Classified scene profile")
    primary_element: str = Field(default="dialogue", description="Primary narrative focus")
    context_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Scene understanding confidence")
    perceptual_findings: List[str] = Field(default_factory=list, description="Perceptual observations")
    recommended_action: Optional[str] = Field(default=None, description="Recommended mastering adjustment")
    risk: str = Field(default="NONE", description="Risk assessment if adjustment applied")
    expected_effect: str = Field(default="Transparent broadcast delivery", description="Expected aesthetic impact")
    requires_review: bool = Field(default=False, description="Whether human review is suggested")
    bounded_adjustments: Dict[str, Any] = Field(default_factory=dict, description="Concrete bounded DSP parameters")


class FinalCertificationReport(BaseModel):
    """
    Authoritative final certification gate combining technical, mechanical,
    dialogue protection, book consistency, and perceptual evidence.
    """
    model_config = ConfigDict(extra="ignore")

    certification: Literal["CERTIFIED", "WARNINGS", "REVIEW_REQUIRED", "REJECTED"] = Field(
        ..., description="Final production certification state"
    )
    chapter_id: str = Field(..., description="Chapter identifier")
    technical_qc: Dict[str, Any] = Field(default_factory=dict, description="P0 Technical QC evaluation")
    mechanical_mastering: Dict[str, Any] = Field(default_factory=dict, description="Mechanical mastering verification")
    dialogue_protection: Dict[str, Any] = Field(default_factory=dict, description="P1 Dialogue protection evaluation")
    book_consistency: Dict[str, Any] = Field(default_factory=dict, description="P1 Book consistency evaluation")
    perceptual_evaluation: Dict[str, Any] = Field(default_factory=dict, description="P4 Perceptual critic evaluation")
    reference_comparison: Optional[Dict[str, Any]] = Field(default=None, description="P4 Reference comparison")
    warnings: List[str] = Field(default_factory=list, description="Non-blocking warning notices")
    review_items: List[Dict[str, Any]] = Field(default_factory=list, description="Items requiring human review")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Traceability provenance")
    certified_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class HumanReviewItem(BaseModel):
    """Targeted human review recommendation for uncertain cases."""
    model_config = ConfigDict(extra="ignore")

    issue_code: str
    category: str
    severity: str
    chapter_id: str
    evidence: str
    suggested_action: str
    confidence: float


class MasteringRequest(BaseModel):
    """
    Typed request triggering Stage 12 mastering on a Stage 11 premaster.
    """
    model_config = ConfigDict(extra="ignore")

    chapter_id: str = Field(..., description="Unique chapter identifier")
    premaster_path: str = Field(..., description="Path to Stage 11 premaster WAV file")
    output_master_path: Optional[str] = Field(default=None, description="Target path for mastered WAV file")
    dialogue_stem_path: Optional[str] = Field(default=None, description="Optional dialogue stem path for vocal protection")
    profile: MasteringProfile = Field(default_factory=MasteringProfile, description="Mastering configuration profile")
    book_profile: Optional[BookMasterProfile] = Field(default=None, description="Optional book master profile")
    reference_profile: Optional[ReferenceProfile] = Field(default=None, description="Optional reference profile")
    scene_intent: Optional[Any] = Field(default=None, description="Optional scene mix intent for dramatic context")
    allow_perceptual_multipass: bool = Field(default=True, description="Whether to allow bounded multi-pass perceptual review")
    mastering_version: str = Field(default="2.2.0", description="Mastering engine version")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Downstream pipeline metadata")
    is_premaster: bool = Field(default=True, description="Enforces input must be a fresh premaster, preventing double-mastering")

    @model_validator(mode="after")
    def validate_request(self) -> MasteringRequest:
        p = Path(self.premaster_path)
        if not p.exists():
            raise FileNotFoundError(f"Premaster file does not exist: {self.premaster_path}")
        if not self.is_premaster:
            raise ValueError(f"Double-master protection: input {self.premaster_path} is flagged as already mastered.")
        return self


class MasteringResult(BaseModel):
    """
    Complete output deliverable from Stage 12 Mastering.
    Includes input identity, post-master metrics, closed-loop QC verdict, and provenance.
    """
    model_config = ConfigDict(extra="ignore")

    status: Literal["SUCCESS", "FAILED", "RETRY_EXHAUSTED"] = Field(..., description="Mastering execution outcome")
    chapter_id: str = Field(..., description="Chapter identifier")
    premaster_path: str = Field(..., description="Input premaster file path")
    master_path: str = Field(..., description="Final certified master file path")
    profile: MasteringProfile = Field(..., description="Mastering profile used")
    analysis_before: MasteringAnalysisFacts = Field(..., description="Pre-master analysis facts")
    analysis_after: Optional[MasteringAnalysisFacts] = Field(default=None, description="Post-master analysis facts")
    qc_result: MasteringQCResult = Field(..., description="Mastering QC certification")
    action_plan: Optional[MasteringActionPlan] = Field(default=None, description="Mastering judge action plan")
    dialogue_protection: Optional[DialogueProtectionReport] = Field(default=None, description="Dialogue protection audit")
    consistency_audit: Optional[ChapterConsistencyAudit] = Field(default=None, description="Chapter consistency audit")
    perceptual_evaluation: Optional[PerceptualEvaluation] = Field(default=None, description="Perceptual evaluation result")
    scene_decision: Optional[SceneMasteringDecision] = Field(default=None, description="Scene-aware mastering decision")
    reference_comparison: Optional[ReferenceComparisonResult] = Field(default=None, description="Reference comparison result")
    certification_report: Optional[FinalCertificationReport] = Field(default=None, description="Final certification report")
    iteration_count: int = Field(default=1, ge=1, description="Number of mastering passes executed")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Cryptographic hashes, versions, and timestamp")
    error_message: Optional[str] = Field(default=None, description="Error diagnostics if mastering failed")


class MasteringLedger(BaseModel):
    """
    Persistent audit ledger for Stage 12 Mastering.
    Persisted to `chapter_XXX_mastering_ledger.json`.
    """
    model_config = ConfigDict(extra="ignore")

    chapter_id: str
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    request: MasteringRequest
    result: MasteringResult
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def save_to_disk(self, target_path: Union[str, Path]) -> Path:
        """Persists ledger to disk as formatted JSON."""
        p = Path(target_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return p

    @classmethod
    def load_from_disk(cls, target_path: Union[str, Path]) -> MasteringLedger:
        """Loads mastering ledger from disk."""
        p = Path(target_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Mastering ledger not found: {p}")
        return cls.model_validate(json.loads(p.read_text(encoding="utf-8")))
