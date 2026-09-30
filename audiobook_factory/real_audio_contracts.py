#!/usr/bin/env python3
"""
Audiobook Factory - Real Audio Validation Contracts.
====================================================
Defines typed, immutable data contracts for Phase 0-15 Real Audio Validation:
- RealAudioFixtureMetadata: Machine-readable provenance and characteristics for real-world audio fixtures.
- AudioMetricDelta: Comparative delta between premaster and master for an individual metric.
- AudioDeltaReport: Full before/after comparison capturing loudness, dynamics, spectral, and stereo deltas.
- ArtifactDetectionResult: Forensic evidence for mastering defects with confidence and severity ratings.
- HumanReviewPackage: Structured bundle for human-listening audits and A/B verification.
- LongFormSceneEvent: Time-stamped scene metrics inside a continuous long-form audio master.
- LongFormReport: Cumulative consistency, transition stability, and fatigue risk report.
- QualityGateEvaluation: Gate results for Technical, Dynamic, Spectral, Dialogue, Artifact, and Consistency gates.
- RealAudioValidationReport: Machine-readable comprehensive validation report.
"""

from __future__ import annotations
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal, Union
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.mastering_contracts import (
    MasteringAnalysisFacts,
    MasteringQCResult,
    FinalArtifactInfo,
    FinalCertificationReport,
    DialogueProtectionReport,
    PerceptualEvaluation,
)


class RealAudioFixtureMetadata(BaseModel):
    """
    Machine-readable metadata contract for real-world audio fixtures.
    Records legal status, provenance, acoustic characteristics, and known risks.
    """
    model_config = ConfigDict(extra="ignore")

    fixture_id: str = Field(..., description="Unique identifier for the fixture")
    source: str = Field(..., description="Origin of audio: repository_test, public_domain, licensed_studio, workstation_synthesis")
    license: str = Field(..., description="License or legal status: MIT, CC0, Project-Owned, Apache-2.0")
    creation_method: str = Field(..., description="Method used to produce audio (e.g. WinRT Speech, Roformer isolation, Studio Foley)")
    language: str = Field(default="en", description="Language code: en, hi, hinglish, code_switching, non_speech")
    scene_type: str = Field(..., description="Canonical category: narration, dialogue, whisper, shouting, emotional, hindi_hinglish, music_heavy, ambience, foley, action, silence, difficult_tts")
    performance_type: str = Field(default="natural", description="Style of performance: formal_narration, intimate, aggressive, conversational, ambient")
    speaker_count: int = Field(default=1, ge=0, description="Number of distinct human or synthesized speakers")
    duration_sec: float = Field(..., ge=0.0, description="Duration in seconds")
    sample_rate: int = Field(default=48000, description="Audio sample rate in Hz")
    channels: int = Field(default=2, description="Channel layout: 1=mono, 2=stereo")
    expected_properties: Dict[str, Any] = Field(default_factory=dict, description="Target acoustic ranges (e.g. expected LUFS, max TP)")
    known_risks: List[str] = Field(default_factory=list, description="Acoustic vulnerabilities to watch for (e.g. sibilance, pumping)")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Detailed creation ledger, hashes, and tools used")


class AudioMetricDelta(BaseModel):
    """Delta measurement for a single acoustic metric with qualitative classification."""
    metric_name: str
    before: Optional[float] = None
    after: Optional[float] = None
    delta: Optional[float] = None
    unit: str = "dB"
    classification: Literal["EXPECTED", "ACCEPTABLE", "SUSPICIOUS", "FAIL"] = "EXPECTED"
    rationale: str = ""


class AudioDeltaReport(BaseModel):
    """
    Comprehensive before/after delta report comparing premaster to master.
    Measures loudness, peak, dynamic range, crest factor, spectral balance, and stereo phase.
    """
    model_config = ConfigDict(extra="ignore")

    fixture_id: str
    premaster_path: str
    master_path: str
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    # Core Metric Deltas
    integrated_lufs: AudioMetricDelta
    true_peak_dbtp: AudioMetricDelta
    loudness_range_lra: AudioMetricDelta
    crest_factor_db: AudioMetricDelta
    spectral_centroid_hz: AudioMetricDelta
    phase_correlation: AudioMetricDelta

    # Band Energy Ratios (Low: <250Hz, Mid: 250Hz-4kHz, High: >4kHz)
    low_band_delta_db: Optional[float] = None
    mid_band_delta_db: Optional[float] = None
    high_band_delta_db: Optional[float] = None

    # Silence & Duration
    silence_ratio_delta: Optional[float] = None
    duration_delta_sec: float = 0.0

    # Dimension Assessments
    dynamic_assessment: Literal["EXPECTED", "ACCEPTABLE", "SUSPICIOUS", "FAIL"] = "ACCEPTABLE"
    spectral_assessment: Literal["EXPECTED", "ACCEPTABLE", "SUSPICIOUS", "FAIL"] = "ACCEPTABLE"
    stereo_assessment: Literal["EXPECTED", "ACCEPTABLE", "SUSPICIOUS", "FAIL"] = "ACCEPTABLE"
    overall_delta_status: Literal["PASS", "WARNING", "REVIEW_REQUIRED", "FAIL"] = "PASS"
    summary_notes: List[str] = Field(default_factory=list)


class ArtifactDetectionResult(BaseModel):
    """
    Forensic defect detection result with clear empirical rationale, confidence, and severity.
    Zero hallucinated certainty from weak heuristics.
    """
    artifact_type: Literal[
        "CLIPPING",
        "EXCESSIVE_LIMITING",
        "PUMPING",
        "SPECTRAL_HARSHNESS",
        "BASS_OVERLOAD",
        "NOISE_FLOOR_AMPLIFICATION",
        "STEREO_DEGRADATION",
        "TRANSIENT_DESTRUCTION",
        "BREATH_DESTRUCTION"
    ]
    detected: bool = False
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    threshold_rationale: str = ""
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence score [0.0 - 1.0]")
    severity: Literal["INFO", "WARNING", "REVIEW_REQUIRED", "FAIL"] = "INFO"
    evidence: Dict[str, Any] = Field(default_factory=dict)


class HumanReviewPackage(BaseModel):
    """
    A/B audit bundle facilitating direct human verification of mastered audio against premaster.
    """
    fixture_id: str
    premaster_path: str
    master_path: str
    delta_report: AudioDeltaReport
    qc_passed: bool
    qc_failures: List[str] = Field(default_factory=list)
    perceptual_score: float = 1.0
    flagged_artifacts: List[ArtifactDetectionResult] = Field(default_factory=list)
    review_status: Literal["CLEAR", "HUMAN_AUDIT_RECOMMENDED", "MANDATORY_REVIEW"] = "CLEAR"
    listening_notes: str = ""


class LongFormSceneEvent(BaseModel):
    """Time-stamped scene metrics inside a continuous long-form audio master."""
    scene_id: str
    scene_type: str
    start_sec: float
    end_sec: float
    integrated_lufs: float
    true_peak_dbtp: float
    loudness_range_lra: float
    spectral_centroid_hz: float
    dialogue_ratio_db: Optional[float] = None
    limiter_active: bool = False


class LongFormReport(BaseModel):
    """
    Multi-scene continuous playback stress test report.
    Evaluates cumulative consistency, chapter drift, limiter behavior, and auditory fatigue.
    """
    total_duration_sec: float
    scene_count: int
    overall_lufs: float
    overall_lra: float
    max_true_peak_dbtp: float
    lufs_drift_max_db: float
    spectral_drift_hz: float
    repeated_limiter_occurrences: int = 0
    fatigue_risk_index: float = Field(default=0.0, ge=0.0, le=1.0)
    scene_timeline: List[LongFormSceneEvent] = Field(default_factory=list)
    outlier_scenes: List[str] = Field(default_factory=list)
    status: Literal["PASS", "REVIEW_REQUIRED", "FAIL"] = "PASS"
    notes: List[str] = Field(default_factory=list)


class QualityGateEvaluation(BaseModel):
    """Evaluation result for one of the 6 core quality gates."""
    gate_name: Literal[
        "TECHNICAL_GATE",
        "DYNAMIC_GATE",
        "SPECTRAL_GATE",
        "DIALOGUE_GATE",
        "ARTIFACT_GATE",
        "CONSISTENCY_GATE"
    ]
    status: Literal["PASS", "WARNING", "REVIEW_REQUIRED", "FAIL"] = "PASS"
    score: float = 1.0
    reasons: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)


class RealAudioValidationReport(BaseModel):
    """
    Top-level machine-readable report for Real Audio Validation.
    """
    report_version: str = "1.0.0"
    engine_version: str = "2.1.0"
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    fixtures_evaluated: int
    passed_count: int
    warning_count: int
    review_required_count: int
    failed_count: int

    category_results: Dict[str, Literal["PASS", "WARNING", "REVIEW_REQUIRED", "FAIL"]]
    quality_gates: Dict[str, QualityGateEvaluation]
    long_form_evaluation: LongFormReport
    overall_status: Literal["PASS", "WARNING", "REVIEW_REQUIRED", "FAIL"]
    review_packages: List[HumanReviewPackage] = Field(default_factory=list)
    executive_summary: str = ""
