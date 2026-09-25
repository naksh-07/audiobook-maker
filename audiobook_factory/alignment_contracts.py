#!/usr/bin/env python3
"""
Audiobook Factory - Alignment 2.0 Contracts & Calibration Configuration.
Defines production-grade typed schemas for word-level speech alignment,
pause intelligence, acoustic diagnostics, and multi-signal confidence metrics.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator


AlignmentDiagnosticCode = Literal[
    "ALIGNMENT_OK",
    "LOW_WORD_CONFIDENCE",
    "TEXT_AUDIO_MISMATCH",
    "UNEXPECTED_LONG_SILENCE",
    "UNSTABLE_BOUNDARY",
    "INSUFFICIENT_SPEECH",
    "PHONETIC_AMBIGUITY",
    "FOREIGN_NAME_UNCERTAINTY",
    "NORMALIZATION_UNCERTAINTY",
    "FALLBACK_ALIGNMENT",
    "IMPOSSIBLE_WORD_DURATION",
    "AUDIO_FILE_DEFECT",
]

AlignmentDiagnosticSeverity = Literal["INFO", "WARNING", "CRITICAL"]

PauseClassification = Literal[
    "natural_pause",
    "dramatic_pause",
    "hesitation",
    "interruption_gap",
    "emotional_pause",
    "breath_pause",
    "dead_air",
    "synthetic_gap",
]

PronunciationAlignmentStatus = Literal["aligned", "uncertain", "mismatch", "fallback"]

AlignmentMethod = Literal["mms_fa_ctc", "energy_fallback", "proportional_fallback"]

AlignmentConfidenceCategory = Literal["HIGH", "MEDIUM", "LOW", "FAILED_REVIEW_REQUIRED"]


class AlignmentCalibrationConfig(BaseModel):
    """
    Isolated and configurable initial calibration parameters for speech alignment.
    These values are baseline hypotheses and are validated against golden benchmarks.
    """
    model_config = ConfigDict(extra="ignore")

    # Pause & silence duration thresholds (milliseconds)
    min_pause_ms: int = Field(default=60, description="Minimum acoustic dip to be classified as a pause")
    natural_pause_min_ms: int = Field(default=150, description="Typical lower bound for grammatical pause")
    natural_pause_max_ms: int = Field(default=650, description="Typical upper bound for grammatical pause")
    dramatic_pause_min_ms: int = Field(default=650, description="Intentional dramatic silence lower bound")
    dramatic_pause_max_ms: int = Field(default=1800, description="Intentional dramatic silence upper bound")
    dead_air_min_ms: int = Field(default=1800, description="Unmotivated trailing or intra-line silence")
    breath_pause_max_ms: int = Field(default=350, description="Pre-speech respiratory intake window")
    synthetic_gap_rms_dbfs: float = Field(default=-65.0, description="Digital zero dropout threshold")

    # Word plausibility thresholds (milliseconds)
    min_word_duration_ms: int = Field(default=40, description="Minimum plausible spoken word duration")
    max_word_duration_ms: int = Field(default=2500, description="Maximum plausible isolated word duration")
    suspicious_word_gap_ms: int = Field(default=800, description="Unexpected inter-word gap without punctuation")

    # Multi-signal confidence weighting (sum to 1.0)
    weight_phonetic: float = Field(default=0.35, description="CTC posterior emission confidence weight")
    weight_coverage: float = Field(default=0.25, description="Aligned word count vs text word count ratio")
    weight_timing: float = Field(default=0.20, description="Word duration plausibility ratio")
    weight_speech_activity: float = Field(default=0.10, description="Audio energy activity ratio")
    weight_boundary: float = Field(default=0.10, description="Boundary continuity and non-overlap stability")

    # Categorization thresholds
    high_confidence_threshold: float = Field(default=0.85, description="Threshold for HIGH confidence")
    medium_confidence_threshold: float = Field(default=0.65, description="Threshold for MEDIUM confidence")
    low_confidence_threshold: float = Field(default=0.40, description="Threshold for LOW confidence")

    # Fallback calibration penalty
    fallback_confidence_penalty: float = Field(default=0.45, description="Score cap when energy fallback is used")


class AlignmentDiagnostic(BaseModel):
    """Actionable diagnostic observation generated during alignment."""
    model_config = ConfigDict(extra="ignore")

    code: AlignmentDiagnosticCode
    severity: AlignmentDiagnosticSeverity = "INFO"
    message: str
    evidence: Dict[str, Any] = Field(default_factory=dict)


class SpeechRegion(BaseModel):
    """Active voiced/unvoiced acoustic speech interval."""
    model_config = ConfigDict(extra="ignore")

    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


class PauseInterval(BaseModel):
    """Classified silence or non-speech interval within or flanking dialogue."""
    model_config = ConfigDict(extra="ignore")

    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=0)
    duration_ms: int = Field(..., ge=0)
    classification: PauseClassification = "natural_pause"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def calculate_duration(cls, data: Any) -> Any:
        if isinstance(data, dict):
            s = data.get("start_ms", 0)
            e = data.get("end_ms", 0)
            if "duration_ms" not in data or data.get("duration_ms") is None:
                data["duration_ms"] = max(0, e - s)
        return data


class WordAlignment(BaseModel):
    """Millisecond-accurate token alignment span with phonetic confidence."""
    model_config = ConfigDict(extra="ignore")

    token: str = Field(..., description="Original source text token")
    normalized_token: str = Field(..., description="Phonetically cleaned token aligned via CTC")
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    pronunciation_status: PronunciationAlignmentStatus = "aligned"
    source: str = Field(default="mms_fa_ctc")

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


class AlignmentResult(BaseModel):
    """
    First-Class Alignment Contract.
    Captures complete word timing, pauses, speech regions, calibrated confidence,
    and structured diagnostics for a speech segment.
    """
    model_config = ConfigDict(extra="ignore")

    segment_uid: str = Field(default="", description="Unique identifier for segment")
    words: List[WordAlignment] = Field(default_factory=list)
    pauses: List[PauseInterval] = Field(default_factory=list)
    speech_regions: List[SpeechRegion] = Field(default_factory=list)
    start_ms: int = Field(default=0, ge=0)
    end_ms: int = Field(default=0, ge=0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence_category: AlignmentConfidenceCategory = Field(default="HIGH")
    method: AlignmentMethod = Field(default="mms_fa_ctc")
    diagnostics: List[AlignmentDiagnostic] = Field(default_factory=list)
    language: str = Field(default="unknown")

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)

    @property
    def total_speech_duration_ms(self) -> int:
        return sum(w.duration_ms for w in self.words)

    @property
    def total_pause_duration_ms(self) -> int:
        return sum(p.duration_ms for p in self.pauses)

    @property
    def word_count(self) -> int:
        return len(self.words)

    @property
    def has_critical_failure(self) -> bool:
        return any(d.severity == "CRITICAL" for d in self.diagnostics) or self.confidence_category == "FAILED_REVIEW_REQUIRED"

    def get_diagnostic_codes(self) -> List[AlignmentDiagnosticCode]:
        return [d.code for d in self.diagnostics]
