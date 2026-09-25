#!/usr/bin/env python3
"""
Audiobook Factory - Pronunciation & Spoken Language Domain Contracts (Pydantic v2).
Defines strictly-typed schemas for entity pronunciation identities, language/locale classification,
deterministic resolution records, spoken-text transformations, audio-level verification,
targeted repairs, cross-chapter drift detection, and reproducible provenance.
"""

from __future__ import annotations
import hashlib
from enum import Enum
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator


class PronunciationStatus(str, Enum):
    """
    Meaningful, objective verification states without fabricated numerical precision.
    """
    VERIFIED = "VERIFIED"
    LIKELY = "LIKELY"
    UNCERTAIN = "UNCERTAIN"
    FAILED = "FAILED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class PronunciationSource(str, Enum):
    """
    Deterministic provenance origin of a pronunciation resolution.
    """
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    BOOK_BIBLE = "BOOK_BIBLE"
    CANONICAL_LEXICON = "CANONICAL_LEXICON"
    PREVIOUS_VERIFIED = "PREVIOUS_VERIFIED"
    DETERMINISTIC_RULE = "DETERMINISTIC_RULE"
    MODEL_INFERRED = "MODEL_INFERRED"
    UNRESOLVED = "UNRESOLVED"


class SpokenLanguage(str, Enum):
    """
    Spoken language / dialect classification for audio synthesis.
    """
    HINDI = "hi"
    ENGLISH = "en"
    HINDUSTANI = "hi_latn_mixed"
    SANSKRIT = "sa"
    URDU = "ur"
    FOREIGN = "foreign"
    UNKNOWN = "unknown"


class PronunciationPolicy(str, Enum):
    """
    Governs how a token/entity should be adapted into speech.
    """
    STRICT_CANONICAL = "STRICT_CANONICAL"
    PHONETIC_RESPELLED = "PHONETIC_RESPELLED"
    CODE_SWITCH_NATIVE = "CODE_SWITCH_NATIVE"
    ANGLICIZED = "ANGLICIZED"
    DESI_COLLOQUIAL = "DESI_COLLOQUIAL"


class PronunciationEntry(BaseModel):
    """
    Canonical pronunciation record for a sensitive word, name, or term.
    Integrates directly with BookBible entities while keeping literary display separate from spoken form.
    """
    model_config = ConfigDict(extra="ignore")

    canonical_id: str = Field(..., description="Unique entity key (e.g. 'sherlock_holmes', 'ostrit')")
    canonical_text: str = Field(..., description="Canonical display text in primary script")
    surface_forms: List[str] = Field(default_factory=list, description="Common surface forms observed in text")
    aliases: List[str] = Field(default_factory=list, description="Alternative names / spellings")
    category: str = Field(
        default="character",
        description="Category: character, location, organization, creature, object, title, terminology, acronym, numeral, unit, phrase, foreign"
    )
    expected_language: SpokenLanguage = Field(default=SpokenLanguage.HINDI, description="Intended language or origin")
    pronunciation_hint: str = Field(default="", description="Phonetic respelling or pronunciation guide")
    spoken_form: str = Field(default="", description="Exact token/string sent to TTS for optimal audio pronunciation")
    phonemic_ipa: Optional[str] = Field(default=None, description="Optional IPA representation if verified")
    status: PronunciationStatus = Field(default=PronunciationStatus.LIKELY, description="Current verification state")
    source: PronunciationSource = Field(default=PronunciationSource.CANONICAL_LEXICON, description="Source of pronunciation")
    policy: PronunciationPolicy = Field(default=PronunciationPolicy.STRICT_CANONICAL, description="Spoken adaptation policy")
    notes: str = Field(default="", description="Human notes or phonetic rationale")
    version: int = Field(default=1, description="Version counter incremented on updates")
    occurrence_count: int = Field(default=0, description="Total occurrences observed in project")
    chapter_occurrences: List[int] = Field(default_factory=list, description="Chapters where this entity appears")

    @model_validator(mode="before")
    @classmethod
    def set_canonical_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("canonical_id") and data.get("canonical_text"):
                data["canonical_id"] = str(data["canonical_text"]).strip().lower().replace(" ", "_")
            if not data.get("spoken_form"):
                data["spoken_form"] = data.get("pronunciation_hint") or data.get("canonical_text", "")
        return data


class PronunciationResolutionResult(BaseModel):
    """
    Structured outcome of resolving a specific sensitive token or entity occurrence.
    """
    model_config = ConfigDict(extra="ignore")

    original_token: str = Field(..., description="Raw token as it appears in literary text")
    canonical_id: Optional[str] = Field(default=None, description="Matched canonical entity ID if any")
    resolved_spoken: str = Field(..., description="Spoken representation for TTS payload")
    status: PronunciationStatus = Field(..., description="Verification state")
    source: PronunciationSource = Field(..., description="Provenance origin tier (1 to 7)")
    language: SpokenLanguage = Field(default=SpokenLanguage.HINDI, description="Detected/resolved language")
    transformation_applied: bool = Field(default=False, description="Whether spoken form differs from original token")
    requires_review: bool = Field(default=False, description="Whether human review is required")
    explanation: str = Field(default="", description="Explainable rationale for resolution decision")


class SpokenTextResult(BaseModel):
    """
    First-class result of transforming literary screenplay text into TTS spoken text.
    Maintains complete immutability of the original literary text.
    """
    model_config = ConfigDict(extra="ignore")

    literary_text: str = Field(..., description="Original literary prose (strictly immutable)")
    display_text: str = Field(..., description="Sanitized text suitable for subtitles and display")
    spoken_text: str = Field(..., description="Normalized and phonetically resolved text sent to TTS")
    resolutions: List[PronunciationResolutionResult] = Field(
        default_factory=list,
        description="Individual entity/token pronunciation resolutions"
    )
    has_unresolved_critical: bool = Field(default=False, description="True if any critical entity is UNRESOLVED or FAILED")
    requires_review: bool = Field(default=False, description="True if any resolution requires human review")


class PronunciationAudioQAResult(BaseModel):
    """
    Acoustic verification report comparing generated audio against the pronunciation plan.
    Emits honest failure states (REVIEW_REQUIRED) without false precision.
    """
    model_config = ConfigDict(extra="ignore")

    take_id: str = Field(..., description="Evaluated take identifier")
    segment_uid: str = Field(default="", description="Screenplay segment UID")
    passed: bool = Field(default=True, description="Whether take satisfies pronunciation audio checks")
    status: PronunciationStatus = Field(default=PronunciationStatus.VERIFIED, description="Overall pronunciation status")
    token_alignments: List[Dict[str, Any]] = Field(default_factory=list, description="Aligned tokens with start_ms, end_ms, and duration_ms")
    omissions: List[str] = Field(default_factory=list, description="Expected sensitive tokens that were omitted or swallowed")
    repetitions: List[str] = Field(default_factory=list, description="Tokens exhibiting unnatural stutter or duplication")
    timing_anomalies: List[str] = Field(default_factory=list, description="Tokens with rushed or excessively dragged durations")
    review_reasons: List[str] = Field(default_factory=list, description="Explainable reasons why review or repair is required")
    alignment_method: str = Field(default="mms_fa_ctc", description="Alignment engine used: mms_fa_ctc, energy_valley, or heuristic")


class CrossChapterPronunciationDrift(BaseModel):
    """
    Tracks recurring book entities across chapters and flags unintended phonetic drift.
    """
    model_config = ConfigDict(extra="ignore")

    canonical_id: str = Field(..., description="Canonical entity identifier")
    canonical_text: str = Field(..., description="Canonical name / text")
    occurrences: List[Dict[str, Any]] = Field(default_factory=list, description="List of occurrences across chapters")
    drift_detected: bool = Field(default=False, description="Whether phonetic or spoken representation drifted")
    drift_details: List[str] = Field(default_factory=list, description="Diagnostic descriptions of drift")
    allowed_exception: bool = Field(default=False, description="Whether drift is an intentional, allowed exception")
    exception_reason: str = Field(default="", description="Rationale for allowed exception if applicable")


class PronunciationProvenanceRecord(BaseModel):
    """
    Immutable audit record for every meaningful pronunciation decision.
    """
    model_config = ConfigDict(extra="ignore")

    entity_id: str = Field(..., description="Canonical entity ID")
    occurrence_chapter: int = Field(default=1, description="Chapter index")
    occurrence_segment_uid: str = Field(default="", description="Screenplay segment UID")
    surface_form: str = Field(..., description="Surface form in text")
    resolved_spoken: str = Field(..., description="Resolved spoken representation")
    resolver_source: str = Field(..., description="Resolver tier or lexicon source")
    policy: str = Field(default="STRICT_CANONICAL", description="Pronunciation policy applied")
    tts_model: str = Field(default="gemini-3.8-flash-tts", description="TTS model employed")
    take_id: str = Field(default="", description="Generated take ID")
    qa_status: str = Field(default="UNCHECKED", description="Audio QA verification status")
    repair_attempt: int = Field(default=0, description="Repair iteration count (0 = first try)")
    certified: bool = Field(default=False, description="Whether certified by final production gates")
    timestamp: str = Field(default="", description="ISO timestamp of record creation")
