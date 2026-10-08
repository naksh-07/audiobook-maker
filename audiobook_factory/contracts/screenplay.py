#!/usr/bin/env python3
"""
Audiobook Factory - Room 3 Screenplay & Dramaturgy Contracts.
Standard: v6.0-ENTERPRISE-DAG
Unified model supporting v6.0-ENTERPRISE-DAG contracts and full backward-compatibility for v5 modules.
"""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from audiobook_factory.contracts.base import ContractBaseModel, ManifestValidationError


# -----------------------------------------------------------------------------
# Legacy Supporting Models (for 100% v5 backward-compatibility)
# -----------------------------------------------------------------------------

class CharacterProfile(BaseModel):
    """Individual character voice profile."""
    model_config = ConfigDict(extra="ignore")

    character_uuid: str = Field(..., description="Unique UUID for character persona")
    display_name: str = Field(..., description="Display name of character in screenplay")
    gender: str = Field(..., description="Gender identifier (e.g., 'male', 'female', 'neutral')")
    assigned_voice_id: str = Field(..., description="Voice model identifier (e.g. 'Charon', 'Aoede', 'Puck')")
    pitch_shift: float = Field(default=0.0, description="Semitone or frequency pitch shift")
    speed_multiplier: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech rate multiplier (0.5 to 2.0)")
    sociolect_trait: Optional[str] = Field(default=None, description="Desi sociolect trait")


class CharacterRoster(BaseModel):
    """Project-wide character voice cast registry."""
    model_config = ConfigDict(extra="ignore")

    project_id: str = Field(..., description="Associated project identifier")
    characters: List[CharacterProfile] = Field(default_factory=list, description="List of registered character profiles")
    pronunciation_overrides: Dict[str, str] = Field(
        default_factory=dict,
        description="Phonetic Devanagari pronunciation overrides map"
    )

    def add_character(self, profile: CharacterProfile) -> None:
        for i, c in enumerate(self.characters):
            if c.character_uuid == profile.character_uuid or c.display_name.strip().lower() == profile.display_name.strip().lower():
                self.characters[i] = profile
                return
        self.characters.append(profile)

    def get_by_id(self, character_uuid: str) -> Optional[CharacterProfile]:
        for c in self.characters:
            if c.character_uuid == character_uuid:
                return c
        return None

    def get_by_name(self, name: str) -> Optional[CharacterProfile]:
        target = name.strip().lower()
        for c in self.characters:
            if c.display_name.strip().lower() == target:
                return c
        return None

    def get_voice_for_character(self, name: str, fallback_voice: str = "Aoede") -> str:
        profile = self.get_by_name(name)
        if profile and profile.assigned_voice_id:
            return profile.assigned_voice_id
        return fallback_voice


class SceneSource(BaseModel):
    """Structured source text and dialogue breakdown for a scene."""
    model_config = ConfigDict(extra="ignore")

    scene_id: int = Field(..., ge=0)
    narrative_act: str = Field(...)
    text_chunks: List[str] = Field(default_factory=list)
    dialogue_lines: List[Dict[str, Any]] = Field(default_factory=list)
    word_count: int = Field(default=0, ge=0)
    emotion_tags: List[str] = Field(default_factory=list)
    source_hash: str = Field(...)


class ActingInstructions(BaseModel):
    """Voice acting delivery directives for TTS synthesis."""
    model_config = ConfigDict(extra="ignore")
    delivery_style: str = Field(default="neutral")
    pacing: float = Field(default=1.0, ge=0.5, le=2.0)


class SpatialCoordinates(BaseModel):
    """Acoustic spatial placement on the stereo stage."""
    model_config = ConfigDict(extra="ignore")
    pan: float = Field(default=0.0, ge=-1.0, le=1.0)
    proximity: str = Field(default="normal_room")
    physical_blocking: Optional[str] = Field(default="standing")


class SegmentMusicParams(BaseModel):
    """Underlying music atmosphere preference for the segment."""
    model_config = ConfigDict(extra="ignore")
    mood: str = Field(default="neutral")
    ducking_db: float = Field(default=-16.0, le=0.0)


# -----------------------------------------------------------------------------
# v6.0-ENTERPRISE-DAG Screenplay Contracts
# -----------------------------------------------------------------------------

class SegmentProvenance(ContractBaseModel):
    """Provenance tracking for single screenplay segments."""
    origin: str = Field(
        default="AUTO_ATTRIBUTED",
        pattern="^(AUTO_ATTRIBUTED|MANUAL_PATCH|DIRECTOR_LOCK)$",
        description="Source of this segment attribution"
    )
    user_locked: bool = Field(
        default=False,
        description="If true, automatic reconciliation will never overwrite this segment"
    )
    content_hash: str = Field(
        default="",
        description="SHA-256 hash of text + speaker + acting directives"
    )


class ScreenplaySegment(ContractBaseModel):
    """
    Atomic screenplay dialogue or narrative acting line.
    Complies with v6.0-ENTERPRISE-DAG while maintaining backwards compatibility.
    """
    model_config = ConfigDict(
        frozen=False,
        extra="ignore",
        validate_assignment=True,
        populate_by_name=True
    )

    segment_uid: str = Field(default="", description="Deterministic segment ID, e.g., 'ch03_seg045'")
    beat_ref: str = Field(default="b001", description="References TranslationBeatRecord.beat_uid")
    speaker: str = Field(default="Narrator", description="Character name or 'Narrator'")
    voice_id: str = Field(default="Aoede", description="Gemini Flash TTS voice identifier")
    text: str = Field(default="", min_length=1, description="Devanagari text to synthesize")

    # 4D Acoustic Formants
    formant_signature: str = Field(default="p0_t0_eq0", description="Compact formant identifier")
    pitch_shift: float = Field(default=0.0, ge=-12.0, le=12.0, description="Pitch delta percentage")
    speed_multiplier: float = Field(default=1.0, ge=0.85, le=1.15, description="Tempo multiplier")
    eq_curve_filter: Optional[str] = Field(
        default=None,
        description="FFmpeg parametric EQ curve (e.g. 'equalizer=f=320:width_type=o:w=1.2:g=2.5')"
    )

    # Directing Parameters
    temperature: float = Field(default=0.35, ge=0.30, le=0.52, description="Gemini TTS temperature")
    acting_instruction: str = Field(
        default="understated natural dialogue (never theatrical)",
        description="Stanislavski physical vocal anchor"
    )

    # Timing & Editorial Metadata
    pre_speech_pause_ms: int = Field(default=250, ge=0, le=3000, description="Pre-speech latency in ms")
    post_speech_pause_ms: int = Field(default=400, ge=0, le=3000, description="Post-speech pause in ms")

    provenance: SegmentProvenance = Field(
        default_factory=lambda: SegmentProvenance(origin="AUTO_ATTRIBUTED", user_locked=False, content_hash="")
    )

    # Legacy fields for v5 compatibility
    uid: Optional[str] = Field(default=None)
    index: Optional[int] = Field(default=None)
    type: Optional[Literal["dialogue", "narration", "chapter_header", "action"]] = Field(default=None)
    emotion: Optional[str] = Field(default="neutral")
    pause_after_ms: Optional[int] = Field(default=400)
    acting: Optional[ActingInstructions] = Field(default_factory=ActingInstructions)
    spatial: Optional[SpatialCoordinates] = Field(default_factory=SpatialCoordinates)
    acoustic_env: Optional[str] = Field(default="open_road")
    sfx_cues: Optional[List[str]] = Field(default_factory=list)
    music: Optional[SegmentMusicParams] = Field(default_factory=SegmentMusicParams)
    intensity_level: Optional[str] = Field(default="medium")
    pre_roll_breath_ms: Optional[int] = Field(default=0)
    memory_vocal_constraint: Optional[str] = Field(default=None)
    recommended_pronoun: Optional[str] = Field(default=None)
    recommended_register: Optional[str] = Field(default=None)
    spoken_text: Optional[str] = Field(default=None)
    pronunciation_metadata: Optional[List[Dict[str, Any]]] = Field(default=None)

    # Stage 3 Dramatic Intelligence Extensions
    scene_id: Optional[str] = Field(default=None)
    beat_id: Optional[str] = Field(default=None)
    dramatic_function: Optional[str] = Field(default=None)
    character_objective: Optional[str] = Field(default=None)
    actioning: Optional[str] = Field(default=None)
    subtext: Optional[str] = Field(default=None)
    subtext_confidence: Optional[float] = Field(default=None)
    surface_emotion: Optional[str] = Field(default=None)
    underlying_emotion: Optional[str] = Field(default=None)
    tension_before: Optional[float] = Field(default=None)
    tension_after: Optional[float] = Field(default=None)
    listener_knowledge_state: Optional[str] = Field(default=None)
    performance_priority: Optional[str] = Field(default="standard")
    dramatic_provenance: Optional[Dict[str, Any]] = Field(default=None)
    causal_trigger: Optional[str] = Field(default=None)
    consequence: Optional[str] = Field(default=None)
    relationship_shift: Optional[str] = Field(default=None)
    leverage_holder: Optional[str] = Field(default=None)
    dramatic_irony: Optional[str] = Field(default=None)
    blocking_directive: Optional[str] = Field(default=None)
    narrative_mode: Optional[str] = Field(default="direct_dialogue")
    narrative_distance: Optional[str] = Field(default=None)
    story_connection: Optional[str] = Field(default=None)
    conversational_dynamic: Optional[str] = Field(default=None)
    is_interruption: bool = Field(default=False)
    hesitation_pause_ms: Optional[int] = Field(default=None)
    silence_intent: Optional[str] = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def sync_legacy_and_v6_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Sync segment_uid and uid
            if not data.get("segment_uid") and data.get("uid"):
                data["segment_uid"] = data["uid"]
            elif not data.get("uid") and data.get("segment_uid"):
                data["uid"] = data["segment_uid"]
            elif not data.get("segment_uid") and not data.get("uid"):
                idx = data.get("index", 1)
                spk = str(data.get("speaker", "narrator")).lower().replace(" ", "_")
                txt_part = hashlib.sha256(str(data.get("text", "")).encode("utf-8")).hexdigest()[:6]
                uid_val = f"s{idx:04d}_{spk}_{txt_part}"
                data["segment_uid"] = uid_val
                data["uid"] = uid_val

            # Sync voice_id and voice / assigned_voice
            if not data.get("voice_id") and data.get("voice"):
                data["voice_id"] = data["voice"]
            elif not data.get("voice_id") and data.get("assigned_voice_id"):
                data["voice_id"] = data["assigned_voice_id"]

            # Sync type
            if not data.get("type"):
                sp = str(data.get("speaker", "Narrator")).lower()
                if sp in ("narrator", "header", "chapter_header"):
                    data["type"] = "narration"
                elif sp in ("foley", "sfx", "action"):
                    data["type"] = "action"
                else:
                    data["type"] = "dialogue"
        return data


class BatchPlanItem(BaseModel):
    """Execution unit representing one TTS synthesis API call (v5 legacy compatibility)."""
    model_config = ConfigDict(extra="ignore")
    batch_id: str = Field(..., description="Unique batch identifier")
    strategy: Literal["multi_speaker_duo", "narrator_chunk", "single_isolated"] = Field(
        ..., description="Batch synthesis strategy"
    )
    uids: List[str] = Field(default_factory=list)
    speakers: List[str] = Field(default_factory=list)
    voice_map: Dict[str, str] = Field(default_factory=dict)
    segments: List[ScreenplaySegment] = Field(default_factory=list)
    total_words: int = Field(default=0)
    raw_audio_path: Optional[str] = Field(default=None)


class BatchDispatchManifest(BaseModel):
    """Complete manifest tracking all synthesis batches for a chapter (v5 legacy compatibility)."""
    model_config = ConfigDict(extra="ignore")
    chapter_id: str = Field(..., description="Chapter identifier")
    chapter_num: int = Field(default=1)
    total_segments: int = Field(default=0)
    total_batches: int = Field(default=0)
    quota_savings_ratio: float = Field(default=0.0)
    batches: List[BatchPlanItem] = Field(default_factory=list)


class ScreenplayScript(ContractBaseModel):
    """Manifest emitted by Room 3 Screenplay & Dramaturgy for synthesis."""
    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
        populate_by_name=True
    )

    chapter_id: int = Field(default=1, ge=1, description="Chapter index")
    translation_hash: str = Field(default="", description="SHA-256 checksum of source TranslationManifest")
    segments: List[ScreenplaySegment] = Field(
        default_factory=list,
        description="Ordered sequence of screenplay segments"
    )
    pronunciation_overrides: Dict[str, str] = Field(
        default_factory=dict,
        description="Phonetic Devanagari overrides"
    )

    @classmethod
    def from_file(cls, path: str | Path) -> ScreenplayScript:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return cls(segments=[ScreenplaySegment.model_validate(s) for s in data])
        elif isinstance(data, dict) and "segments" in data:
            return cls.model_validate(data)
        raise ValueError(f"Invalid script file format at {path}")
