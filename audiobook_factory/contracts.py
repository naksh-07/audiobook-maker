#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3: Data Contracts & Strictly Typed Schemas (Pydantic v2).
Defines Layer 1 / Layer 2 / Layer 3 contracts between the Agentic Creative Layer
and the Deterministic Audio Engine with zero heuristics, zero placeholders,
and zero hardcoded character/voice bindings.
"""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, AliasChoices


class ManifestValidationError(ValueError):
    """Raised when a creative manifest or contract violates structural or acoustic constraints."""
    pass


class ProjectConfig(BaseModel):
    """
    Project-level configuration defining metadata, language pairing,
    local asset directories, and broadcast audio compliance targets.
    """
    model_config = ConfigDict(extra="ignore")

    project_id: str = Field(..., description="Unique identifier for the project")
    title: str = Field(..., description="Book/Project title")
    author: str = Field(..., description="Author name")
    source_language: str = Field(..., description="Source text language code (e.g. 'en', 'hi')")
    target_language: str = Field(default="hi-IN", description="Target TTS/audiobook language code")
    assets_dir: str = Field(..., description="Root directory path for all project media assets")
    ebu_r128_lufs: float = Field(default=-19.0, description="EBU R128 integrated loudness target in LUFS")
    true_peak_db: float = Field(default=-1.5, description="Maximum allowable True Peak in dBTP")
    adult_literary_mode: bool = Field(default=True, description="Enables unfiltered Gangs-of-Wasseypur / Manto grade raw adult literary fidelity")

    @field_validator("ebu_r128_lufs")
    @classmethod
    def validate_lufs(cls, v: float) -> float:
        if v > 0.0 or v < -70.0:
            raise ManifestValidationError(f"Invalid EBU R128 target LUFS: {v}. Must be between -70.0 and 0.0 LUFS.")
        return round(v, 2)

    @field_validator("true_peak_db")
    @classmethod
    def validate_true_peak(cls, v: float) -> float:
        if v > 0.0 or v < -20.0:
            raise ManifestValidationError(f"Invalid true peak target dB: {v}. Must be <= 0.0 dBTP.")
        return round(v, 2)


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
    proximity: str = Field(default="normal_room", description="Acoustic proximity zone (e.g. 'close_mic', 'normal_room', 'distant')")


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


class TimelineSegment(BaseModel):
    """
    Sample-accurate audio transcript & millisecond timeline entry (Gate 4.5).
    Formed immediately following speech synthesis to provide an immutable, auditable millisecond map.
    Preserves the full Devanagari/Hindi transcript text without truncation.
    """
    model_config = ConfigDict(extra="ignore")

    uid: Optional[str] = Field(default=None, description="Matching ScreenplaySegment UID")

    segment_index: int = Field(..., ge=1, description="1-indexed sequence number matching ScreenplaySegment")
    speaker: str = Field(..., description="Canonical English character name matching CharacterRoster")
    text: str = Field(..., min_length=1, description="Complete unabridged speech text spoken in this chunk")
    audio_file: str = Field(..., description="Filename or relative path to the generated WAV chunk")
    duration_ms: int = Field(..., ge=0, description="Exact sample duration in milliseconds")
    start_ms: int = Field(..., ge=0, description="Cumulative timeline start timestamp in milliseconds")
    end_ms: int = Field(..., ge=0, description="Cumulative timeline end timestamp in milliseconds")
    pause_after_ms: int = Field(default=400, ge=0, description="Silence gap padding after segment in milliseconds")
    emotion: str = Field(default="neutral", description="Dramatic emotion category")
    delivery_style: str = Field(default="neutral", description="Style of line delivery")
    spatial_pan: float = Field(default=0.0, ge=-1.0, le=1.0, description="Stereo azimuth pan from -1.0 to +1.0")
    acoustic_env: str = Field(default="temple_stone_hall", description="Acoustic room impulse setting")
    sfx_cues: List[str] = Field(default_factory=list, description="Associated physical Foley tags")
    music_mood: str = Field(default="neutral", description="Underlying musical mood")
    pre_roll_breath_ms: int = Field(default=0, ge=0, description="Organic breath intake Foley duration before speech")

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


class TimelineLedger(BaseModel):
    """
    Master Timeline & Audio Transcript Ledger (Gate 4.5).
    Strictly read-only source-of-truth for the Audio Drama Director and Foley Designer agents
    to lock BGM cue timestamps, dynamic ducking envelopes, and tactile SFX placement down to the millisecond.
    """
    model_config = ConfigDict(extra="ignore")

    ledger_version: str = Field(default="2.0", description="Ledger schema specification version")
    project_id: str = Field(default="", description="Associated project identifier")
    chapter_id: str = Field(..., description="Unique chapter identifier (e.g. 'chapter_005')")
    total_segments: int = Field(..., ge=0, description="Total number of speech segments")
    total_dialogue_duration_ms: int = Field(..., ge=0, description="Sum of raw speech audio durations in milliseconds")
    total_timeline_duration_ms: int = Field(..., ge=0, description="Total chapter timeline duration including pauses in milliseconds")
    total_silence_duration_ms: int = Field(default=0, ge=0, description="Sum of dialogue pauses in milliseconds")
    silence_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="Percentage of pause silence in vocal track")
    segments: List[TimelineSegment] = Field(default_factory=list, description="Chronological timeline segments")

    def get_segment(self, index: int) -> Optional[TimelineSegment]:
        """Lookup a segment by 1-based index."""
        for s in self.segments:
            if s.segment_index == index:
                return s
        return None

    def find_segment_at_ms(self, timestamp_ms: int) -> Optional[TimelineSegment]:
        """Find the active speech segment at a given millisecond timestamp."""
        for s in self.segments:
            if s.start_ms <= timestamp_ms <= s.end_ms:
                return s
        return None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TimelineLedger:
        return cls.model_validate(data)

    def to_json(self, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> TimelineLedger:
        return cls.model_validate_json(json_str)

    @classmethod
    def from_file(cls, path: str | Path) -> TimelineLedger:
        with open(path, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())


# Allowable music cue types strictly constrained
MusicCueType = Literal[
    "TRANSITION_BRIDGE",
    "EMOTIONAL_UNDERSCORE",
    "TENSION_RISER",
    "CLIMACTIC_ACTION_CUE",
    "AFTERMATH_FADE",
]


class AcousticMetrics(BaseModel):
    """Physical acoustic invariants extracted via local DSP (zero hallucinations)."""
    model_config = ConfigDict(extra="ignore")

    true_peak_dbtp: float = Field(default=-1.5, description="True peak in dBTP")
    integrated_lufs: float = Field(default=-19.0, description="EBU R128 integrated loudness in LUFS")
    speech_corridor_density: float = Field(default=0.25, ge=0.0, le=1.0, description="Acoustic energy ratio in 300Hz-3.5kHz vocal corridor")
    transient_drops_sec: List[float] = Field(default_factory=list, description="Seconds where major transient drops/crashes occur")
    bpm: float = Field(default=90.0, ge=0.0, le=300.0, description="Detected or canonical Tempo in BPM")
    intro_bed_end_sec: float = Field(default=0.0, ge=0.0, description="Second where subtle intro transitions into main progression")
    vocal_clash_risk: Literal["LOW", "MODERATE", "SEVERE"] = Field(default="LOW", description="Risk of frequency masking in vocal intelligibility range")


class SemanticAnnotations(BaseModel):
    """Dramatic, emotional, and cultural profiling derived via multimodal LLM reasoning."""
    model_config = ConfigDict(extra="ignore")

    valence: float = Field(default=0.0, ge=-1.0, le=1.0, description="Positivity/Negativity from -1.0 (tragic) to +1.0 (joyous)")
    arousal: float = Field(default=0.5, ge=0.0, le=1.0, description="Energy/Intensity from 0.0 (calm/stagnant) to 1.0 (adrenaline frenzy)")
    tension: float = Field(default=0.5, ge=0.0, le=1.0, description="Narrative dread/suspense from 0.0 (resolved) to 1.0 (high dread)")
    narrative_function: Literal[
        "TRANSITION_BRIDGE",
        "EMOTIONAL_UNDERSCORE",
        "TENSION_RISER",
        "CLIMACTIC_ACTION",
        "AFTERMATH_FADE",
        "AMBIENT_BED",
    ] = Field(default="EMOTIONAL_UNDERSCORE", description="Primary structural role in dramatic scoring")
    narrative_archetypes: List[str] = Field(default_factory=list, description="Story archetypes e.g. ['TAVERN_BRAWL', 'MONSTER_HUNT']")
    slavic_instruments: List[str] = Field(default_factory=list, description="Identified lead timbres e.g. ['hurdy-gurdy', 'kemenche']")
    story_triggers: List[str] = Field(default_factory=list, description="Literary action triggers for SQLite FTS5 search")


class SonicGenome(BaseModel):
    """The Complete Sonic Genome for a soundtrack asset or stem."""
    model_config = ConfigDict(extra="ignore")

    version: str = Field(default="1.0", description="Schema version")
    track_id: int = Field(default=0, description="Catalog track ID")
    filename: str = Field(default="", description="Track filename")
    acoustic: AcousticMetrics = Field(default_factory=AcousticMetrics)
    semantic: SemanticAnnotations = Field(default_factory=SemanticAnnotations)
    id3_metadata: Dict[str, Any] = Field(default_factory=dict, description="Embedded ID3 tag dictionary")


class MusicCue(BaseModel):
    """
    Music cue instruction specifying surgical track slice, timing, and dynamic gain.
    """
    model_config = ConfigDict(extra="ignore")

    cue_id: str = Field(..., description="Unique cue identifier (e.g. 'mc_001')")
    cue_type: MusicCueType = Field(..., description="Dramatic categorization of the music cue")
    track_id: int = Field(default=0, ge=0, description="Database asset identifier of the music track")
    track_name: str = Field(..., description="Human-readable track name or title")
    section_name: str = Field(..., description="Sub-track section name (e.g. 'INTRO_BED', 'RISING_TENSION', 'CLIMAX_DROP')")
    section_start_sec: float = Field(default=0.0, ge=0.0, description="Start offset inside source track in seconds")
    start_ms: int = Field(..., ge=0, description="Placement offset on chapter timeline in milliseconds")
    duration_ms: int = Field(..., gt=0, description="Duration of the cue in milliseconds")
    fade_in_ms: int = Field(default=2000, ge=0, description="Fade-in envelope duration in milliseconds")
    fade_out_ms: int = Field(default=3000, ge=0, description="Fade-out envelope duration in milliseconds")
    volume_db: float = Field(default=-18.0, description="Base track attenuation in dB")
    dramatic_justification: str = Field(default="", description="Artistic / narrative rationale for this cue placement")
    leitmotif_ref: Optional[str] = Field(default="", description="Identifier of the leitmotif definition this cue is bound to")
    spectral_notch_needed: bool = Field(default=False, description="Flag indicating if 2.2kHz notch is needed to prevent vocal masking")
    target_valence: Optional[float] = Field(default=None, description="Emotional positivity/negativity (-1.0 to 1.0)")
    target_arousal: Optional[float] = Field(default=None, description="Emotional intensity/adrenaline (0.0 to 1.0)")
    narrative_archetype: Optional[str] = Field(default=None, description="Narrative trope archetype for cue matching")

    @field_validator("cue_type", mode="before")
    @classmethod
    def normalize_cue_type(cls, v: str) -> str:
        """Map legacy or alternate cue type names to standard literal set."""
        mapping = {
            "BGM_MAIN": "EMOTIONAL_UNDERSCORE",
            "BGM": "EMOTIONAL_UNDERSCORE",
            "CLIMACTIC_COMBAT": "CLIMACTIC_ACTION_CUE",
            "COMBAT": "CLIMACTIC_ACTION_CUE",
            "ACTION_TENSION": "CLIMACTIC_ACTION_CUE",
            "UNDERSCORE": "EMOTIONAL_UNDERSCORE",
            "TRANSITION": "TRANSITION_BRIDGE",
        }
        return mapping.get(v, v)

    @property
    def asset_path(self) -> str:
        """Alias for track_name to maintain uniform cue interface across Ambience, Foley, and Music."""
        return self.track_name

    def validate_timeline(self) -> None:
        """Structural validation method for timeline consistency."""
        if self.start_ms < 0:
            raise ManifestValidationError(f"MusicCue {self.cue_id} start_ms cannot be negative: {self.start_ms}")
        if self.duration_ms <= 0:
            raise ManifestValidationError(f"MusicCue {self.cue_id} duration_ms must be positive: {self.duration_ms}")


class FoleyCue(BaseModel):
    """
    Foley / SFX cue instruction anchored to dialogue timestamps with calibrated spatial coordinates.
    """
    model_config = ConfigDict(extra="ignore")

    cue_id: str = Field(..., description="Unique cue identifier (e.g. 'fc_001')")
    segment_index: int = Field(..., ge=0, description="Index of dialogue segment triggering the sound")
    anchor_word: str = Field(..., description="Exact dialogue word triggering the physical sound")
    pre_roll_ms: int = Field(default=100, ge=0, description="Lead-in time before anchor word in milliseconds")
    asset_id: int = Field(default=0, ge=0, description="Database asset identifier of foley sound")
    asset_path: str = Field(default="", description="Filesystem path to sound asset file")
    asset_name: Optional[str] = Field(default="", description="Descriptive asset name")
    gain_dbfs: float = Field(default=-15.0, description="Calibrated True Peak target in dBFS")
    azimuth_pan: float = Field(
        default=0.0,
        ge=-0.8,
        le=0.8,
        description="Stereo panning coordinate (-0.8 = hard left, 0.0 = center, +0.8 = hard right)"
    )
    reverb_send: float = Field(default=0.15, ge=0.0, le=1.0, description="Aux send level to shared convolution reverb (0.0 to 1.0)")
    start_ms: Optional[int] = Field(default=0, ge=0, description="Absolute timeline offset in milliseconds")
    duration_ms: Optional[int] = Field(default=0, ge=0, description="Duration of cue in milliseconds")
    ucs_category: Optional[str] = Field(default="MISCGnl", description="Universal Category System (UCS) 7-character Category ID")
    is_lfe_sub_drop: bool = Field(default=False, description="Triggers 50Hz sub-bass physical impact weight")
    trajectory: Literal["static", "left_to_right", "right_to_left", "center_zoom"] = Field(
        default="static", description="Spatial vector panning trajectory for projectiles or swings"
    )

    @field_validator("azimuth_pan")
    @classmethod
    def validate_azimuth_pan(cls, v: float) -> float:
        if not (-0.8 <= v <= 0.8):
            raise ManifestValidationError(f"azimuth_pan must be within [-0.8, +0.8] range to prevent ear-bleed, got {v}")
        return round(v, 2)


class AmbienceScene(BaseModel):
    """
    Environmental background atmosphere scene spanning continuous time regions.
    """
    model_config = ConfigDict(extra="ignore")

    scene_id: int = Field(..., ge=0, description="Sequential scene index")
    start_ms: int = Field(..., ge=0, description="Start offset on chapter timeline in milliseconds")
    end_ms: int = Field(..., gt=0, description="End offset on chapter timeline in milliseconds")
    asset_path: str = Field(..., description="Filesystem path to ambient bed audio file")
    target_lufs: float = Field(default=-32.0, description="Calibrated ambient background loudness in LUFS")
    reverb_preset: str = Field(default="room", description="Acoustic reverb convolution preset (e.g. 'room', 'wood_hall', 'cave')")
    asset_name: Optional[str] = Field(default="", description="Descriptive asset name")
    acoustic_ir: Optional[Dict[str, Any]] = Field(default=None, description="Impulse response parameters for convolution reverb")

    @model_validator(mode="after")
    def validate_time_bounds(self) -> AmbienceScene:
        if self.end_ms <= self.start_ms:
            raise ManifestValidationError(
                f"Invalid time bounds for AmbienceScene {self.scene_id}: start_ms ({self.start_ms}) must be < end_ms ({self.end_ms})"
            )
        return self


class MasteringConfig(BaseModel):
    """
    Deterministic broadcast mastering chain parameters for multi-bus mixing and sidechain ducking.
    """
    model_config = ConfigDict(extra="ignore")

    target_lufs: float = Field(default=-19.0, description="Final master integrated loudness target in LUFS")
    true_peak_dbtp: float = Field(
        default=-1.5,
        validation_alias=AliasChoices("true_peak_dbtp", "true_peak_db"),
        description="Final master true peak ceiling in dBTP"
    )
    ducking_attenuation_db: float = Field(default=-7.5, description="Music attenuation gain while dialogue speaks in dB")
    ducking_attack_ms: int = Field(default=120, ge=1, le=500, description="Sidechain compressor attack time in milliseconds")
    ducking_release_ms: int = Field(default=750, ge=10, le=2000, description="Sidechain compressor release time in milliseconds")
    spectral_carve_hz: int = Field(default=2200, ge=500, le=8000, description="Center frequency for vocal dialogue spectral notch filter")
    spectral_carve_gain_db: float = Field(default=-5.5, le=0.0, description="Spectral notch filter gain attenuation in dB")
    acoustic_ir: Optional[Dict[str, Any]] = Field(default=None, description="Impulse response parameters for convolution reverb")


MasteringSettings = MasteringConfig


class CreativeManifest(BaseModel):
    """
    Layer 1 / Layer 2 Contract: Full creative and acoustic blueprint for a chapter.
    Enforces the Audio Drama standard mandate of at least 60.0% acoustic silence.
    """
    model_config = ConfigDict(extra="ignore")

    manifest_version: str = Field(
        default="3.0",
        validation_alias=AliasChoices("manifest_version", "version"),
        description="Manifest schema specification version"
    )
    project_id: str = Field(default="", description="Project identifier")
    chapter_id: str = Field(..., description="Unique chapter identifier")
    silence_percentage: float = Field(
        default=100.0,
        description="Percentage of total timeline free of musical underscore (must be >= 60.0%)"
    )
    mastering: MasteringConfig = Field(default_factory=MasteringConfig, description="Mastering bus settings")
    ambience_scenes: List[AmbienceScene] = Field(default_factory=list, description="Environmental ambience scenes")
    scene_acoustics: Optional[Any] = Field(default=None, description="Decoupled 4-stem SceneSoundscapeManifest")
    music_cues: List[MusicCue] = Field(default_factory=list, description="Surgical musical score cues")
    foley_cues: List[FoleyCue] = Field(default_factory=list, description="Physical foley sound cues")
    total_duration_ms: Optional[int] = Field(default=0, ge=0, description="Total chapter duration in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary creative / project metadata")

    @model_validator(mode="before")
    @classmethod
    def handle_silence_percentage(cls, data: Any) -> Any:
        if isinstance(data, dict):
            sp = data.get("silence_percentage")
            if sp is None:
                data["silence_percentage"] = 100.0
        return data

    @model_validator(mode="after")
    def parse_scene_acoustics(self) -> "CreativeManifest":
        """Rehydrate scene_acoustics dictionary into SceneSoundscapeManifest upon JSON load."""
        if isinstance(self.scene_acoustics, dict):
            from audiobook_factory.scene_acoustics import SceneSoundscapeManifest
            self.scene_acoustics = SceneSoundscapeManifest.model_validate(self.scene_acoustics)
        return self

    @field_validator("silence_percentage")
    @classmethod
    def validate_silence_rule(cls, v: float) -> float:
        """Enforce strict 60% minimum acoustic silence mandate for dramatic audiobooks."""
        if v < 60.0:
            raise ManifestValidationError(
                f"Silence violation: Only {v:.1f}% silence. "
                "Audio Drama broadcast standard mandates at least 60.0% acoustic silence to prevent narrative fatigue."
            )
        return round(v, 2)

    def validate_acoustic_rules(self, total_duration_ms: Optional[int] = None) -> None:
        """Validate music cue durations against chapter length to verify silence constraint."""
        dur = total_duration_ms or self.total_duration_ms
        if dur and dur > 0:
            music_ms = sum(c.duration_ms for c in self.music_cues)
            calc_silence = max(0.0, 100.0 * (1.0 - (music_ms / dur)))
            if calc_silence < 60.0:
                raise ManifestValidationError(
                    f"Silence violation: Only {calc_silence:.1f}% silence. "
                    f"Audio Drama standard requires at least 60% silence (music_ms={music_ms}ms, total={dur}ms)."
                )
            self.silence_percentage = round(calc_silence, 2)

    def validate(self, total_duration_ms: Optional[int] = None) -> None:
        """Validate structural and acoustic constraints."""
        dur = total_duration_ms or self.total_duration_ms
        if dur and dur > 0:
            music_ms = sum(c.duration_ms for c in self.music_cues)
            calc_silence = max(0.0, 100.0 * (1.0 - (music_ms / dur)))
            if calc_silence < 60.0:
                raise ManifestValidationError(
                    f"Silence violation: Only {calc_silence:.1f}% silence. "
                    f"Audio Drama standard requires at least 60% silence (music_ms={music_ms}ms, total={dur}ms)."
                )
            self.silence_percentage = round(calc_silence, 2)
        elif self.silence_percentage < 60.0:
            raise ManifestValidationError(
                f"Silence violation: Only {self.silence_percentage:.1f}% silence."
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to serializable Python dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CreativeManifest:
        """Instantiate manifest from Python dictionary with validation."""
        return cls.model_validate(data)

    def to_json(self, indent: int = 2) -> str:
        """Serialize manifest to formatted JSON string."""
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> CreativeManifest:
        """Deserialize and validate manifest from JSON string."""
        return cls.model_validate_json(json_str)

    def save_to_file(self, path: Union[str, Path]) -> None:
        """Serialize and save manifest directly to JSON file."""
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> CreativeManifest:
        """Load and deserialize manifest directly from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_json(f.read())


# ==============================================================================
# Macro-Tier Book Level Contracts & Specifications
# ==============================================================================

class BookPackagingSpecs(BaseModel):
    """Macro-tier packaging specifications for final distribution container (e.g. M4B)."""
    model_config = ConfigDict(extra="ignore")

    cover_art_path: Optional[Path] = None
    codec: str = "aac"
    bitrate: str = "192k"
    sample_rate: int = 44100
    faststart: bool = True
    min_cover_resolution: int = 2400


class BookChapterMarker(BaseModel):
    """Sample-accurate chapter marker for publication table of contents."""
    model_config = ConfigDict(extra="ignore")

    chapter_index: int = Field(..., ge=1, description="1-indexed chapter sequence number")
    title: str = Field(..., description="Display title for the chapter")
    start_ms: int = Field(..., ge=0, description="Start offset on book timeline in milliseconds")
    end_ms: int = Field(..., ge=0, description="End offset on book timeline in milliseconds")
    duration_ms: int = Field(..., ge=0, description="Duration in milliseconds")
    integrated_lufs: float = Field(default=-19.0, description="Integrated loudness of chapter audio in LUFS")
    true_peak_dbfs: float = Field(default=-1.5, description="True peak ceiling of chapter audio in dBFS/dBTP")
    audio_file: Optional[Path] = Field(default=None, description="Path to mastered chapter audio file")


class BookTableOfContents(BaseModel):
    """Macro-level table of contents container for entire audiobook."""
    model_config = ConfigDict(extra="ignore")

    chapters: List[BookChapterMarker] = Field(default_factory=list, description="Ordered chapter markers")
    total_duration_ms: int = Field(default=0, ge=0, description="Total book duration in milliseconds")


class BookVoiceRoster(BaseModel):
    """Global cross-chapter voice casting map."""
    model_config = ConfigDict(extra="ignore")

    character_voices: Dict[str, str] = Field(default_factory=dict, description="Character to voice ID mapping")
    narrator_voice: str = Field(default="Charon", description="Global narrator voice ID")


class GlobalLoreBible(BaseModel):
    """Book-level lore, recurring terms, and canonical pronunciation lexicon."""
    model_config = ConfigDict(extra="ignore")

    lexicon: Dict[str, str] = Field(default_factory=dict, description="Canonical proper nouns to phonetic Devanagari spellings")
    series_title: Optional[str] = Field(default=None, description="Book series title")
    book_number: Optional[int] = Field(default=None, description="Volume or book number in series")


class BookMasterManifest(BaseModel):
    """
    Macro-Tier Book Master Manifest aggregating voice roster, lore bible, TOC, and packaging.
    Immutable top-level source of truth for full book packaging and Gate 6 verification.
    """
    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., description="Canonical book title")
    author: str = Field(..., description="Canonical author name")
    narrator: str = Field(default="Charon", description="Lead narrator voice or name")
    translator_credits: Optional[str] = Field(default=None, description="Translator credits or persona")
    series_title: Optional[str] = Field(default=None, description="Series title")
    book_number: Optional[int] = Field(default=None, description="Book number in series")
    total_duration_ms: int = Field(default=0, ge=0, description="Cumulative audiobook duration in milliseconds")
    global_integrated_lufs: float = Field(default=-19.0, description="Target integrated loudness across full book")
    voice_roster: BookVoiceRoster = Field(default_factory=BookVoiceRoster, description="Global character voice casting map")
    lore_bible: GlobalLoreBible = Field(default_factory=GlobalLoreBible, description="Global lore bible and lexicon")
    toc: BookTableOfContents = Field(default_factory=BookTableOfContents, description="Table of contents chapter tree")
    packaging_specs: BookPackagingSpecs = Field(default_factory=BookPackagingSpecs, description="M4B packaging specifications")

    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to JSON-serializable dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BookMasterManifest:
        """Instantiate BookMasterManifest from dictionary."""
        return cls.model_validate(data)

    def to_json(self, indent: int = 2) -> str:
        """Serialize BookMasterManifest to JSON string."""
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> BookMasterManifest:
        """Deserialize BookMasterManifest from JSON string."""
        return cls.model_validate_json(json_str)

    @classmethod
    def from_file(cls, path: str | Path) -> BookMasterManifest:
        """Load BookMasterManifest from file."""
        with open(path, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())


# ==============================================================================
# Next-Gen Cinema Architecture Adapter Bridge
# ==============================================================================

class LegacyCreativeManifestAdapter:
    """
    Adapter bridging Legacy CreativeManifest (v3.0) to Next-Gen CinemaAudioManifest (v4.0).
    Guarantees 100% backward compatibility for Chapters 4, 5, 6, 7 and certified productions
    without modifying legacy JSON structures or breaking old tests.
    """

    @staticmethod
    def lift_legacy_manifest_to_cinema(legacy: CreativeManifest) -> Any:
        """
        Lifts flat legacy manifest into modular cinema structures:
        - Converts legacy AmbienceScene list into SceneSoundscapeManifest.
        - Converts legacy mastering settings into calibrated DuckingProfile.
        - Transfers MusicCue and FoleyCue collections with zero loss.
        """
        from audiobook_factory.scene_acoustics import SceneSoundscapeManifest, SceneAcousticProfile, AmbienceLayer
        from audiobook_factory.acoustic_bus_matrix import DuckingProfile, PROFILE_STANDARD
        from audiobook_factory.cinema_audio_engine import CinemaAudioManifest

        # Prefer existing 4-stem decoupled scene acoustics manifest if present
        scene_manifest = getattr(legacy, "scene_acoustics", None)
        if not scene_manifest and legacy.ambience_scenes:
            scenes: List[SceneAcousticProfile] = []
            for s in legacy.ambience_scenes:
                layer = AmbienceLayer(
                    layer_type="base_room_tone",
                    asset_path=s.asset_path or s.asset_name or "wind_howl.ogg",
                    target_lufs=s.target_lufs,
                )
                sc_prof = SceneAcousticProfile(
                    scene_id=f"scene_{s.scene_id:03d}",
                    start_ms=s.start_ms,
                    end_ms=s.end_ms,
                    ir_preset=s.reverb_preset or "room",
                    layers=[layer],
                )
                scenes.append(sc_prof)

            scene_manifest = SceneSoundscapeManifest(
                chapter_id=legacy.chapter_id,
                scenes=scenes,
                metadata={"source": "lifted_from_legacy_manifest"},
            ) if scenes else None

        # Resolve ducking profile from mastering settings or default
        ducking_policy = PROFILE_STANDARD
        if legacy.mastering:
            ducking_policy = DuckingProfile(
                profile_name="standard_speech",
                attenuation_db=legacy.mastering.ducking_attenuation_db,
                attack_ms=legacy.mastering.ducking_attack_ms,
                release_ms=legacy.mastering.ducking_release_ms,
                spectral_carve_hz=legacy.mastering.spectral_carve_hz,
                spectral_carve_depth_db=legacy.mastering.spectral_carve_gain_db,
            )

        total_sec = float(legacy.total_duration_ms) / 1000.0 if legacy.total_duration_ms else 0.0

        return CinemaAudioManifest(
            manifest_version="4.0",
            chapter_id=legacy.chapter_id,
            project_id=legacy.project_id,
            scene_acoustics=scene_manifest,
            music_cues=list(legacy.music_cues),
            foley_cues=list(legacy.foley_cues),
            ducking_policy=ducking_policy,
            total_duration_sec=total_sec,
            silence_percentage=legacy.silence_percentage,
            metadata=dict(legacy.metadata),
        )


# ==============================================================================
# Performance Realization Re-exports
# ==============================================================================
from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    PerformanceProvenanceMode,
    PerformancePriority,
    SilenceType,
    InterruptionBehavior,
    TurnTakingBehavior,
    EvaluationDimensionScore,
    PerformanceEvaluationResult,
    TakeVariant,
    PerformanceFidelityReport,
)



