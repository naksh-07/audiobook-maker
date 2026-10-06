#!/usr/bin/env python3
"""
Audiobook Factory - Screenplay Contracts (Gate 2).
Defines CharacterProfile, CharacterRoster, SceneSource, ActingInstructions,
SpatialCoordinates, SegmentMusicParams, ScreenplaySegment, BatchPlanItem,
BatchDispatchManifest, and ScreenplayScript.
"""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal, Union
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from .base import ManifestValidationError


class CharacterProfile(BaseModel):
    """
    Individual character voice profile.
    Explicitly decoupled from any hardcoded names to support any novel or cast dynamically.
    """
    model_config = ConfigDict(extra="ignore")

    character_uuid: str = Field(..., description="Unique UUID for character persona")
    display_name: str = Field(..., description="Display name of character in screenplay")
    gender: str = Field(..., description="Gender identifier (e.g., 'male', 'female', 'neutral')")
    assigned_voice_id: str = Field(..., description="Voice model identifier (e.g. 'Charon', 'Aoede', 'Puck')")
    pitch_shift: float = Field(default=0.0, description="Semitone or frequency pitch shift")
    speed_multiplier: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech rate multiplier (0.5 to 2.0)")
    sociolect_trait: Optional[str] = Field(default=None, description="Subtle Desi sociolect trait (e.g. 'COLD_CYNIC', 'CAUSTIC_ARISTOCRAT', 'THARKI_BARD')")


class CharacterRoster(BaseModel):
    """
    Project-wide character voice cast registry.
    Completely zero hardcoded names: characters are loaded and resolved dynamically.
    """
    model_config = ConfigDict(extra="ignore")

    project_id: str = Field(..., description="Associated project identifier")
    characters: List[CharacterProfile] = Field(default_factory=list, description="List of registered character profiles")
    pronunciation_overrides: Dict[str, str] = Field(
        default_factory=dict,
        description="Phonetic Devanagari pronunciation overrides map"
    )

    def add_character(self, profile: CharacterProfile) -> None:
        """Register or update a character profile in the roster."""
        for i, c in enumerate(self.characters):
            if c.character_uuid == profile.character_uuid or c.display_name.strip().lower() == profile.display_name.strip().lower():
                self.characters[i] = profile
                return
        self.characters.append(profile)

    def get_by_id(self, character_uuid: str) -> Optional[CharacterProfile]:
        """Retrieve a character profile by its unique UUID."""
        for c in self.characters:
            if c.character_uuid == character_uuid:
                return c
        return None

    def get_by_name(self, name: str) -> Optional[CharacterProfile]:
        """Retrieve a character profile by display name (case-insensitive)."""
        target = name.strip().lower()
        for c in self.characters:
            if c.display_name.strip().lower() == target:
                return c
        return None

    def get_voice_for_character(self, name: str, fallback_voice: str = "Aoede") -> str:
        """Resolve voice ID for a given character name, returning fallback if unknown."""
        profile = self.get_by_name(name)
        if profile and profile.assigned_voice_id:
            return profile.assigned_voice_id
        return fallback_voice


class SceneSource(BaseModel):
    """
    Source-to-JSON Gate 1: Structured source text and dialogue breakdown for a scene
    before creative soundscape rendering.
    """
    model_config = ConfigDict(extra="ignore")

    scene_id: int = Field(..., ge=0, description="Sequential index of the scene")
    narrative_act: str = Field(..., description="Narrative act identifier (e.g. 'ACT_I_SETUP', 'ACT_II_CONFRONTATION')")
    text_chunks: List[str] = Field(default_factory=list, description="Raw narrative text paragraphs")
    dialogue_lines: List[Dict[str, Any]] = Field(default_factory=list, description="Parsed dialogue lines with speaker and text")
    word_count: int = Field(default=0, ge=0, description="Total word count in scene")
    emotion_tags: List[str] = Field(default_factory=list, description="Dominant scene emotion tags (e.g. ['tense', 'dread'])")
    source_hash: str = Field(..., description="SHA-256 hash of original source text for caching & integrity")

    @classmethod
    def create_with_hash(
        cls,
        scene_id: int,
        narrative_act: str,
        text_chunks: List[str],
        dialogue_lines: List[Dict[str, Any]],
        emotion_tags: List[str],
    ) -> SceneSource:
        """Factory method to construct SceneSource and automatically compute hash and word count."""
        combined_text = " ".join(text_chunks) + " " + " ".join(str(d.get("text", "")) for d in dialogue_lines)
        w_count = len(combined_text.split())
        s_hash = hashlib.sha256(combined_text.encode("utf-8")).hexdigest()
        return cls(
            scene_id=scene_id,
            narrative_act=narrative_act,
            text_chunks=text_chunks,
            dialogue_lines=dialogue_lines,
            word_count=w_count,
            emotion_tags=emotion_tags,
            source_hash=s_hash,
        )


class ActingInstructions(BaseModel):
    """Voice acting delivery directives for TTS synthesis."""
    model_config = ConfigDict(extra="ignore")
    delivery_style: str = Field(default="neutral", description="Style of line delivery (e.g. 'whispered_threat', 'ironic', 'breathless_exhaustion', 'bellowing_rage', 'combat_strain', 'slow_motion')")
    pacing: float = Field(default=1.0, ge=0.5, le=2.0, description="Speed pacing multiplier")


class SpatialCoordinates(BaseModel):
    """Acoustic spatial placement on the stereo stage."""
    model_config = ConfigDict(extra="ignore")
    pan: float = Field(default=0.0, ge=-1.0, le=1.0, description="Stereo azimuth pan from -1.0 (hard left) to +1.0 (hard right)")
    proximity: str = Field(default="normal_room", description="Acoustic proximity zone (e.g. 'close_mic', 'normal_room', 'distant', 'intimate_close')")
    physical_blocking: Optional[str] = Field(default="standing", description="Physical character posture/choreography: 'sitting', 'standing', 'pacing', 'leaning_close', 'retreating', 'lying_down'")


class SegmentMusicParams(BaseModel):
    """Underlying music atmosphere preference for the segment."""
    model_config = ConfigDict(extra="ignore")
    mood: str = Field(default="neutral", description="Atmospheric musical mood")
    ducking_db: float = Field(default=-16.0, le=0.0, description="Ducking depth when speech is active")


class ScreenplaySegment(BaseModel):
    """
    Standardized Screenplay Segment Contract (Gate 2).
    Enforces canonical character naming, rich acting directives, spatial positioning,
    acoustic environment tagging, and physical Foley cue associations.
    """
    model_config = ConfigDict(extra="ignore")

    uid: str = Field(default="", description="Unique deterministic segment identifier")
    index: int = Field(..., ge=1, description="1-indexed sequence number")
    type: Literal["dialogue", "narration", "chapter_header", "action"] = Field(..., description="Segment narrative type")
    speaker: str = Field(default="Narrator", description="Canonical English character name matching CharacterRoster or 'Foley'")
    text: str = Field(default="", description="Clean localized speech/narration text or '[ACTION]' marker")
    emotion: str = Field(default="neutral", description="Dramatic emotion category")
    pause_after_ms: int = Field(default=400, ge=0, description="Natural silence pause after line in milliseconds")
    acting: ActingInstructions = Field(default_factory=ActingInstructions)
    spatial: SpatialCoordinates = Field(default_factory=SpatialCoordinates)
    acoustic_env: str = Field(default="open_road", description="Acoustic room impulse setting")
    sfx_cues: List[str] = Field(default_factory=list, description="Associated physical Foley tags")
    music: SegmentMusicParams = Field(default_factory=SegmentMusicParams)
    intensity_level: Optional[str] = Field(default="medium", description="Dynamic DSP headroom rating (low, medium, high, explosive)")
    pre_roll_breath_ms: Optional[int] = Field(default=0, description="Organic breath intake Foley duration before speech")
    memory_vocal_constraint: Optional[str] = Field(default=None, description="Conservative physical vocal constraint from Memory 2.0 (e.g. 'strained_breath', 'fatigued_low_energy')")
    recommended_pronoun: Optional[str] = Field(default=None, description="Recommended Hindi pronoun from DynamicRelationshipState ('tu', 'tum', 'aap')")
    recommended_register: Optional[str] = Field(default=None, description="Recommended socio-linguistic register from DynamicRelationshipState")
    spoken_text: Optional[str] = Field(default=None, description="Resolved spoken representation for TTS payload (strictly preserves text as immutable literary prose)")
    pronunciation_metadata: Optional[List[Dict[str, Any]]] = Field(default=None, description="Traceable pronunciation resolution metadata for words and entities in segment")

    # Stage 3: Dramatic Intelligence & Performance Adaptation Extensions (Optional & Defaulted)
    scene_id: Optional[str] = Field(default=None, description="Enclosing dramatic scene identifier")
    beat_id: Optional[str] = Field(default=None, description="Enclosing dramatic beat identifier")
    dramatic_function: Optional[str] = Field(default=None, description="Dramatic beat function")
    character_objective: Optional[str] = Field(default=None, description="Immediate beat objective of speaking character")
    actioning: Optional[str] = Field(default=None, description="Active transitive verb / actioning intent")
    subtext: Optional[str] = Field(default=None, description="Underlying unsaid subtext if justified")
    subtext_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confidence in inferred subtext")
    surface_emotion: Optional[str] = Field(default=None, description="Explicit surface emotional expression")
    underlying_emotion: Optional[str] = Field(default=None, description="Concealed or underlying emotional state")
    tension_before: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Dramatic tension entering segment")
    tension_after: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Dramatic tension exiting segment")
    listener_knowledge_state: Optional[str] = Field(default=None, description="Audience epistemic state (e.g. dramatic irony)")
    performance_priority: Optional[str] = Field(default="standard", description="Performance attention priority")
    dramatic_provenance: Optional[Dict[str, Any]] = Field(default=None, description="Provenance hash linking to dramatic plan")

    # Refined Dramatic Capabilities Extensions (All Optional / Defaulted)
    causal_trigger: Optional[str] = Field(default=None, description="What event or action triggered this beat ('Because of...')")
    consequence: Optional[str] = Field(default=None, description="Direct dramatic consequence leading into subsequent beat ('Therefore...')")
    relationship_shift: Optional[str] = Field(default=None, description="Relational movement occurring in this segment")
    leverage_holder: Optional[str] = Field(default=None, description="Character holding tactical leverage in this beat")
    dramatic_irony: Optional[str] = Field(default=None, description="Specific irony where listener knows truth hidden from character")
    blocking_directive: Optional[str] = Field(default=None, description="Meaningful physical blocking instruction")
    narrative_mode: Optional[str] = Field(default="direct_dialogue", description="Narrative delivery mode (direct_dialogue, internal_monologue, reported_speech, narrator_exposition)")
    narrative_distance: Optional[str] = Field(default=None, description="Psychological distance of narration")
    story_connection: Optional[str] = Field(default=None, description="Long-range narrative connection note")
    conversational_dynamic: Optional[str] = Field(default=None, description="Turn-taking or rhetorical dynamic")
    is_interruption: bool = Field(default=False, description="Whether line abruptly interrupts preceding speaker")
    hesitation_pause_ms: Optional[int] = Field(default=None, description="Hesitation pause duration metadata")
    silence_intent: Optional[str] = Field(default=None, description="Narrative purpose of pause after line")

    @model_validator(mode="before")
    @classmethod
    def set_action_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("type"):
                sp = str(data.get("speaker", "Narrator")).lower()
                if sp in ("narrator", "header", "chapter_header"):
                    data["type"] = "narration"
                elif sp in ("foley", "sfx", "action"):
                    data["type"] = "action"
                else:
                    data["type"] = "dialogue"
            elif data.get("type") == "action":
                if not data.get("speaker"):
                    data["speaker"] = "Foley"
                if not data.get("text"):
                    data["text"] = "[ACTION]"
            if not data.get("uid"):
                idx = data.get("index", 1)
                spk = str(data.get("speaker", "narrator")).lower().replace(" ", "_")
                txt_part = hashlib.sha256(str(data.get("text", "")).encode("utf-8")).hexdigest()[:6]
                data["uid"] = f"s{idx:04d}_{spk}_{txt_part}"
        return data

    @field_validator("sfx_cues", mode="before")
    @classmethod
    def normalize_sfx_cues(cls, v: Any) -> List[str]:
        if not isinstance(v, list):
            return []
        res = []
        for item in v:
            if isinstance(item, dict):
                tag = str(item.get("tag", item.get("name", item.get("sfx", ""))))
                if tag:
                    res.append(tag)
            elif isinstance(item, str) and item.strip():
                res.append(item.strip())
        return res


class BatchPlanItem(BaseModel):
    """Execution unit representing one TTS synthesis API call (single or batched)."""
    model_config = ConfigDict(extra="ignore")
    batch_id: str = Field(..., description="Unique batch identifier, e.g. b001_duo_speaker1_speaker2")
    strategy: Literal["multi_speaker_duo", "narrator_chunk", "single_isolated"] = Field(
        ..., description="Batch synthesis strategy"
    )
    uids: List[str] = Field(default_factory=list, description="Ordered list of segment UIDs in this batch")
    speakers: List[str] = Field(default_factory=list, description="Unique speaker names in this batch")
    voice_map: Dict[str, str] = Field(default_factory=dict, description="Speaker to Gemini voice mapping")
    segments: List[ScreenplaySegment] = Field(default_factory=list, description="Constituent screenplay segments")
    total_words: int = Field(default=0, description="Total word count in batch")
    raw_audio_path: Optional[str] = Field(default=None, description="Path to rendered raw multi-speaker WAV")


class BatchDispatchManifest(BaseModel):
    """Complete manifest tracking all synthesis batches for a chapter."""
    model_config = ConfigDict(extra="ignore")
    chapter_id: str = Field(..., description="Chapter identifier, e.g. chapter_001")
    chapter_num: int = Field(default=1, description="1-indexed chapter number")
    total_segments: int = Field(default=0, description="Total input segments")
    total_batches: int = Field(default=0, description="Total planned batches (API calls)")
    quota_savings_ratio: float = Field(default=0.0, description="Estimated API quota savings percentage")
    batches: List[BatchPlanItem] = Field(default_factory=list, description="Planned synthesis batches")


class ScreenplayScript(BaseModel):
    """Full chapter screenplay script collection (Gate 2)."""
    model_config = ConfigDict(extra="ignore")

    segments: List[ScreenplaySegment] = Field(default_factory=list)
    pronunciation_overrides: Dict[str, str] = Field(default_factory=dict, description="Phonetic Devanagari overrides")

    @classmethod
    def from_file(cls, path: str | Path) -> ScreenplayScript:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return cls(segments=[ScreenplaySegment.model_validate(s) for s in data])
        elif isinstance(data, dict) and "segments" in data:
            return cls.model_validate(data)
        raise ValueError(f"Invalid script file format at {path}")
