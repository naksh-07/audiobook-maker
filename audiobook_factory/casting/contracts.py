#!/usr/bin/env python3
"""
Audiobook Factory - Casting Contracts & Data Models (Pydantic v2).
Defines schemas for Character Casting Profiles, Voice Candidate Scoring,
Voice Audition Scenes, Multi-Dimensional Casting Evaluation, and Cast Locks.
"""

from __future__ import annotations
import json
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


CastingGender = Literal["male", "female", "neutral"]
PerceivedAgeCategory = Literal[
    "child",
    "youth",
    "young_adult",
    "prime_adult",
    "mature_adult",
    "elder",
]
VocalWeight = Literal["light", "medium", "heavy"]
TimbreType = Literal["gravelly", "smooth", "raspy", "warm", "sharp", "resonant", "brittle", "textured"]
PitchBand = Literal["low", "medium_low", "medium", "medium_high", "high"]
BrightnessLevel = Literal["dark", "neutral", "bright"]
ProjectionLevel = Literal["intimate", "conversational", "projected", "bellowing"]

AuditionDramaticMode = Literal[
    "neutral",
    "conversational",
    "authority",
    "anger",
    "vulnerability",
    "fear",
    "whisper",
    "humor",
    "action",
    "transition",
]


class CharacterCastingProfile(BaseModel):
    """
    Unified Casting Profile derived from canonical character identity,
    linguistic profile, and dramaturgy performance profile.
    """
    model_config = ConfigDict(extra="ignore")

    character_id: str = Field(..., description="Unique character identifier (e.g. 'char_hero')")
    canonical_name: str = Field(..., description="Canonical character display name")
    gender: CastingGender = Field(default="neutral", description="Biological / dramatic vocal gender")
    perceived_age: PerceivedAgeCategory = Field(default="prime_adult", description="Perceived acoustic age band")
    sociolect_archetype: str = Field(default="NEUTRAL", description="Sociolect archetype from book bible")

    # 1. Personality Traits (0.0 to 1.0)
    warmth: float = Field(default=0.5, ge=0.0, le=1.0)
    aggression: float = Field(default=0.5, ge=0.0, le=1.0)
    restraint: float = Field(default=0.5, ge=0.0, le=1.0)
    authority: float = Field(default=0.5, ge=0.0, le=1.0)
    vulnerability: float = Field(default=0.3, ge=0.0, le=1.0)
    humor: float = Field(default=0.2, ge=0.0, le=1.0)
    seriousness: float = Field(default=0.8, ge=0.0, le=1.0)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)

    # 2. Speech Dynamics
    pace: float = Field(default=1.0, ge=0.5, le=2.0)
    articulation: str = Field(default="natural", description="Speech clarity: crisp, natural, colloquial, sluggish, sharp")
    formality: int = Field(default=2, ge=0, le=5)
    verbosity: str = Field(default="balanced", description="terse, balanced, elaborate, theatrical")
    rhythm: str = Field(default="steady", description="staccato, steady, fluid, syncopated, halting")
    sentence_style: str = Field(default="balanced")

    # 3. Dramatic Range Demands (0.0 to 1.0)
    range_anger: float = Field(default=0.5, ge=0.0, le=1.0)
    range_fear: float = Field(default=0.3, ge=0.0, le=1.0)
    range_grief: float = Field(default=0.3, ge=0.0, le=1.0)
    range_joy: float = Field(default=0.3, ge=0.0, le=1.0)
    range_intimacy: float = Field(default=0.3, ge=0.0, le=1.0)
    range_tension: float = Field(default=0.6, ge=0.0, le=1.0)
    range_action: float = Field(default=0.5, ge=0.0, le=1.0)

    # 4. Vocal Weight & Acoustic Preferences
    vocal_weight: VocalWeight = Field(default="medium")
    timbre_preference: TimbreType = Field(default="resonant")
    pitch_preference: PitchBand = Field(default="medium")
    brightness: BrightnessLevel = Field(default="neutral")
    projection: ProjectionLevel = Field(default="conversational")

    # 5. Delivery Styles
    required_styles: List[str] = Field(default_factory=list)
    forbidden_styles: List[str] = Field(default_factory=list)

    @classmethod
    def from_entities(
        cls,
        character_id: str,
        canonical_name: str,
        entity: Optional[Any] = None,
        language_profile: Optional[Any] = None,
        performance_profile: Optional[Any] = None,
    ) -> CharacterCastingProfile:
        """
        Synthesizes a unified CharacterCastingProfile by inspecting existing
        BookEntity, CharacterLanguageProfile, and CharacterPerformanceProfile.
        Zero duplication of domain knowledge.
        """
        gender: CastingGender = "neutral"
        if entity:
            ent_gender = getattr(entity, "gender", None) or (entity.get("gender") if isinstance(entity, dict) else None)
            if ent_gender:
                g_str = str(ent_gender).lower()
                if "female" in g_str:
                    gender = "female"
                elif "male" in g_str:
                    gender = "male"

        archetype = "NEUTRAL"
        if entity:
            archetype = getattr(entity, "sociolect_archetype", None) or (entity.get("sociolect_archetype") if isinstance(entity, dict) else "NEUTRAL") or "NEUTRAL"

        base_pace = 1.0
        base_energy = 0.75
        articulation = "natural"
        restraint = 0.50
        req_styles: List[str] = []
        forbid_styles: List[str] = []

        if performance_profile:
            base_pace = getattr(performance_profile, "baseline_pace", 1.0)
            base_energy = getattr(performance_profile, "baseline_energy", 0.75)
            articulation = getattr(performance_profile, "articulation", "natural")
            restraint = getattr(performance_profile, "restraint_level", 0.50)
            emo_beh = getattr(performance_profile, "emotional_behaviors", {})
            if isinstance(emo_beh, dict):
                req_styles.extend(list(emo_beh.values()))

        formality = 2
        verbosity = "balanced"
        if language_profile:
            formality = getattr(language_profile, "formality_level", 2)
            verbosity = getattr(language_profile, "sentence_length_preference", "balanced")
            forbid = getattr(language_profile, "prohibited_registers", [])
            if isinstance(forbid, list):
                forbid_styles.extend([str(x) for x in forbid])

        # Infer acoustic weight & authority from archetype and restraint
        authority = 0.7 if "COMMANDER" in archetype or "ARISTOCRAT" in archetype or "MATRIARCH" in archetype else 0.5
        vocal_weight: VocalWeight = "heavy" if (base_energy > 0.85 or authority > 0.65) else ("light" if base_energy < 0.60 else "medium")
        timbre_pref: TimbreType = "gravelly" if "CYNIC" in archetype or "SURVIVOR" in archetype else ("sharp" if "ARISTOCRAT" in archetype else "resonant")
        pitch_pref: PitchBand = "low" if (gender == "male" and authority >= 0.6) else ("medium_low" if gender == "female" and authority >= 0.6 else "medium")

        return cls(
            character_id=character_id,
            canonical_name=canonical_name,
            gender=gender,
            sociolect_archetype=archetype,
            authority=authority,
            restraint=restraint,
            pace=base_pace,
            articulation=articulation,
            formality=formality,
            verbosity=verbosity,
            vocal_weight=vocal_weight,
            timbre_preference=timbre_pref,
            pitch_preference=pitch_pref,
            required_styles=req_styles,
            forbidden_styles=forbid_styles,
        )


class VoiceCandidateScore(BaseModel):
    """
    Explainable candidate evaluation output from VoiceCandidateEngine.
    """
    model_config = ConfigDict(extra="ignore")

    voice_id: str
    display_name: str
    overall_score: float = Field(..., ge=0.0, le=1.0)
    strengths: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    recommendation_summary: str = ""


class AuditionScene(BaseModel):
    """
    Single standardized dramatic audition scene.
    """
    model_config = ConfigDict(extra="ignore")

    scene_id: str
    dramatic_mode: AuditionDramaticMode
    line_text: str
    delivery_directive: str
    target_emotion: str
    suggested_pace: float = 1.0


class AuditionResult(BaseModel):
    """
    Audio generation result for a single audition scene.
    """
    model_config = ConfigDict(extra="ignore")

    candidate_voice_id: str
    scene_id: str
    dramatic_mode: AuditionDramaticMode
    audio_path: str
    duration_sec: float = 0.0
    passed: bool = True
    overall_score: float = 0.0
    dimension_scores: Dict[str, float] = Field(default_factory=dict)
    diagnostics: List[str] = Field(default_factory=list)


class CastingEvaluationRecord(BaseModel):
    """
    Comprehensive audition and metadata evaluation of a candidate voice.
    Preserves audit evidence for winning and losing candidates alike.
    """
    model_config = ConfigDict(extra="ignore")

    candidate_voice_id: str
    character_id: str
    overall_fit_score: float = Field(..., ge=0.0, le=1.0)
    rank: int = 1
    passed_audition: bool = True
    dimension_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="character_fit, timbre_fit, emotional_range, naturalness, authority, vulnerability, whisper_quality, high_intensity_quality, long_form_suitability, ensemble_distinctiveness"
    )
    strengths: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    audition_results: List[AuditionResult] = Field(default_factory=list)
    evaluation_summary: str = ""


class CastLock(BaseModel):
    """
    Persistent, formal Cast Lock contract.
    Guarantees stable character-to-voice attribution across the entire novel.
    Recasting requires explicit invalidation and causes downstream regeneration.
    """
    model_config = ConfigDict(extra="ignore")

    character_id: str
    character_name: str
    voice_id: str
    casting_version: str = "1.0.0"
    locked: bool = True
    locked_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    locked_by: str = "Director"
    selection_rank: int = 1
    selection_rationale: str = ""
    casting_evidence: Dict[str, Any] = Field(default_factory=dict)
    calibration_overrides: Dict[str, Any] = Field(default_factory=dict)


class CastLockManifest(BaseModel):
    """
    Project-level manifest storing all locked character voices (cast_lock.json).
    """
    model_config = ConfigDict(extra="ignore")

    project_slug: str
    version: str = "1.0.0"
    locks: Dict[str, CastLock] = Field(default_factory=dict)
    recast_history: List[Dict[str, Any]] = Field(default_factory=list)
    updated_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())

    def get_lock(self, character_name_or_id: str) -> Optional[CastLock]:
        """Case-insensitive character lookup in cast locks."""
        clean = character_name_or_id.strip().lower()
        clean_norm = clean.replace("_", " ")
        for cid, lock in self.locks.items():
            if cid.lower() == clean or lock.character_name.lower() == clean:
                return lock
            if cid.lower().replace("_", " ") == clean_norm or lock.character_name.lower().replace("_", " ") == clean_norm:
                return lock
        return None
