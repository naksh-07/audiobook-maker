#!/usr/bin/env python3
"""
Audiobook Factory - Sound Design Data Contracts (Pydantic v2).
=============================================================
Unified, strictly typed schemas for the 20 Sound Design Capabilities.
Bridges creative dramatic intent and deterministic execution metadata:
- Pure sound design intent, relative intensity, and attention priority.
- Abstract spatial stage geometry and room propagation acoustics.
- Single source of truth: extends existing contracts (FoleyCue, MusicCue,
  AmbienceScene, SceneAcousticProfile, CreativeManifest).
- Complete decision provenance and inspectability.
"""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal, Union, Set
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

# Re-export key existing types to maintain single source of truth
from audiobook_factory.contracts import (
    ScreenplaySegment,
    FoleyCue,
    MusicCue,
    AmbienceScene,
    CreativeManifest,
    TimelineLedger,
    TimelineSegment,
    ManifestValidationError,
)
from audiobook_factory.scene_acoustics import SceneAcousticProfile, AmbienceLayer, SceneSoundscapeManifest
from audiobook_factory.sonic_bible import LeitmotifDefinition, WorldAcousticProfile

# -----------------------------------------------------------------------------
# Common Sound Design Value Types
# -----------------------------------------------------------------------------

RelativeIntensity = Literal[
    "whisper_quiet",      # Barely audible, near threshold of hearing
    "subtle_bed",         # Low background texture, never distracts
    "normal",             # Standard conversational/ambient presence
    "prominent",          # Clear narrative focus, commands listener attention
    "accent",             # Sharp dramatic transient or punctuation
    "explosive_impact",   # Full physical intensity, peak drama
]

AttentionPriority = Literal[
    "CRITICAL",   # High narrative stake (e.g. fatal blow, reveal scream, cue stinger)
    "HIGH",       # Key physical action or dominant emotional motif
    "MEDIUM",     # Standard Foley, dialogue-supporting ambience
    "LOW",        # Background texture, distant sounds
    "TEXTURE",    # Subliminal room tone, micro-textures
]

ProximityZone = Literal[
    "intimate",       # Ear-close / whispered proximity (< 0.5m)
    "close",          # Arm's length physical interaction (0.5m - 1.5m)
    "normal_room",    # Standard acoustic space within the room (1.5m - 4m)
    "mid_distance",   # Across a large hall or courtyard (4m - 12m)
    "distant",        # Horizon, off-stage, or outside the building (> 12m)
    "off_stage",      # Outside immediate listener room/scene boundary
]

SpatialTrajectory = Literal[
    "static",                 # Stationary acoustic source
    "left_to_right",          # Panning from stage left to stage right
    "right_to_left",          # Panning from stage right to stage left
    "approaching",            # Moving from distant/mid to close
    "retreating",             # Moving from close to distant
    "center_zoom",            # Expanding stereo width towards listener
]

OcclusionState = Literal[
    "direct_line_of_sight",   # Unobstructed sound propagation
    "partial_obstruction",    # Soft barrier (curtains, pillar, crowd)
    "behind_closed_door",     # Solid barrier (heavy wooden oak door, shutter)
    "behind_stone_wall",      # Heavy masonry barrier (cellar, crypt)
    "subterranean",           # Deep underground / through earth
]


# -----------------------------------------------------------------------------
# Mix Intent & Spatial Metadata (Abstract, Non-Rendering)
# -----------------------------------------------------------------------------

class MixIntent(BaseModel):
    """
    Directorial mix instructions for downstream Track 11 (Cinematic Mix).
    Does NOT contain hardcoded DSP, volume numbers, or compressor thresholds.
    """
    model_config = ConfigDict(extra="ignore")

    duck_under_dialogue: bool = Field(default=False, description="Whether this sound should duck when dialogue speaks")
    swell_in_dialogue_pauses: bool = Field(default=False, description="Whether this sound should naturally swell during dialogue pauses")
    carve_vocal_presence: bool = Field(default=False, description="Whether downstream mixing should apply spectral pocketing for vocal clarity")
    dry_intelligibility_priority: bool = Field(default=False, description="Whether speech intelligibility takes absolute precedence over wet reverb")
    sidechain_trigger: bool = Field(default=False, description="Whether this sound triggers ducking in other background layers")


class SpatialMetadata(BaseModel):
    """
    Abstract stereo stage geometry and spatial sound-design metadata.
    Actual stereo panning and binaural rendering are handled downstream by Track 11.
    """
    model_config = ConfigDict(extra="ignore")

    azimuth_pan: float = Field(
        default=0.0,
        ge=-0.8,
        le=0.8,
        description="Stereo stage azimuth coordinate (-0.8 = stage left, 0.0 = center, +0.8 = stage right)"
    )
    proximity: ProximityZone = Field(default="normal_room", description="Acoustic proximity zone")
    trajectory: SpatialTrajectory = Field(default="static", description="Physical movement vector")
    occlusion: OcclusionState = Field(default="direct_line_of_sight", description="Physical acoustic barrier condition")
    elevation: Optional[Literal["low", "eye_level", "high", "overhead"]] = Field(
        default="eye_level", description="Vertical acoustic placement"
    )

    @field_validator("azimuth_pan")
    @classmethod
    def validate_pan(cls, v: float) -> float:
        return round(max(-0.8, min(0.8, float(v))), 2)


# -----------------------------------------------------------------------------
# 01 — Scene Audio Understanding Contracts
# -----------------------------------------------------------------------------

class ActionCandidate(BaseModel):
    """Physical action parsed from text or screenplay blocking."""
    model_config = ConfigDict(extra="ignore")

    segment_index: int = Field(..., ge=1)
    subject: str = Field(default="Character")
    action_verb: str = Field(..., description="Action verb (e.g. 'draw', 'slam', 'creak', 'step')")
    object_material: str = Field(default="wood", description="Primary physical material involved")
    surface_material: Optional[str] = Field(default=None, description="Ground or contact surface")
    anchor_word: str = Field(default="")
    narrative_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    is_explicit_blocking: bool = Field(default=False)
    manner_of_action: Literal["stealth", "forceful", "hesitant", "casual", "urgent", "normal"] = Field(
        default="normal", description="Manner or style of physical execution"
    )
    intensity_modifier: RelativeIntensity = Field(
        default="normal", description="Acoustic intensity: restrained whisper vs prominent heavy"
    )
    dramatic_purpose: str = Field(default="", description="Narrative intention or dramatic blocking purpose")
    emotional_state: str = Field(default="neutral", description="Actor emotional state during physical movement")
    location_context: Optional[str] = Field(default=None, description="Environmental or ground context")


class SceneAudioUnderstandingResult(BaseModel):
    """
    Structured outcome of the dedicated Scene Audio Analysis stage.
    Extracts all dramatic audio requirements without generating audio assets.
    """
    model_config = ConfigDict(extra="ignore")

    scene_id: str = Field(...)
    chapter_id: str = Field(...)
    environment_type: str = Field(default="room", description="Physical setting type (e.g. 'castle_corridor', 'forest_night')")
    time_and_weather: str = Field(default="indoor_calm", description="Temporal and meteorological context")
    characters_present: List[str] = Field(default_factory=list)
    action_candidates: List[ActionCandidate] = Field(default_factory=list)
    hard_sfx_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    creature_presence: Optional[str] = Field(default=None)
    magical_phenomena: List[str] = Field(default_factory=list)
    requires_walla: bool = Field(default=False)
    walla_description: Optional[str] = Field(default=None)
    music_required: bool = Field(default=True)
    dominant_emotion: str = Field(default="neutral")
    tension_level: float = Field(default=0.5, ge=0.0, le=1.0)
    silence_opportunities: List[str] = Field(default_factory=list)
    sound_continuity_notes: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# 02 — Scene Audio Blueprint Contract
# -----------------------------------------------------------------------------

class SceneAudioBlueprint(BaseModel):
    """
    Persistent Scene-Level Sound Design Plan (Director Instruction Sheet).
    Comprehensive plan for acoustics, staging, layers, cues, and silence.
    """
    model_config = ConfigDict(extra="ignore")

    scene_id: str = Field(...)
    chapter_id: str = Field(...)
    blueprint_version: str = Field(default="1.0")
    location_id: str = Field(default="default_room")
    weather_state: str = Field(default="clear")
    time_context: str = Field(default="day")
    acoustic_profile_id: str = Field(default="indoor_standard")
    characters_staged: Dict[str, SpatialMetadata] = Field(default_factory=dict)
    ambience_layers_planned: List[Dict[str, Any]] = Field(default_factory=list)
    walla_planned: Optional[Dict[str, Any]] = Field(default=None)
    foley_planned: List[Dict[str, Any]] = Field(default_factory=list)
    hard_sfx_planned: List[Dict[str, Any]] = Field(default_factory=list)
    magic_planned: List[Dict[str, Any]] = Field(default_factory=list)
    creatures_planned: List[Dict[str, Any]] = Field(default_factory=list)
    music_motifs_planned: List[Dict[str, Any]] = Field(default_factory=list)
    music_cues_planned: List[Dict[str, Any]] = Field(default_factory=list)
    silence_events_planned: List[Dict[str, Any]] = Field(default_factory=list)
    spatial_sources: List[Dict[str, Any]] = Field(default_factory=list)
    restraint_target: str = Field(default="moderate", description="Restraint policy: 'high', 'moderate', 'dense'")
    provenance_hash: str = Field(default="", description="SHA-256 hash of underlying scene screenplay")
    metadata: Dict[str, Any] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# 03 — Environment / World Sound Profiles
# -----------------------------------------------------------------------------

class EnvironmentProfile(BaseModel):
    """
    Reusable environment sound profile ensuring consistent acoustic and physical
    identity when a location recurs across multiple scenes or chapters.
    """
    model_config = ConfigDict(extra="ignore")

    env_id: str = Field(..., description="Unique environment slug (e.g. 'castle_great_hall', 'dark_forest')")
    display_name: str = Field(...)
    category: Literal["indoor", "subterranean", "outdoor_nature", "settlement", "travel_vehicle", "supernatural"] = Field(...)
    default_surfaces: List[str] = Field(default_factory=lambda: ["stone", "wood"])
    typical_ambience_layers: List[str] = Field(default_factory=list)
    distant_sounds: List[str] = Field(default_factory=list)
    typical_foley: List[str] = Field(default_factory=list)
    typical_walla: Optional[str] = Field(default=None)
    typical_weather: Optional[str] = Field(default=None)
    typical_creatures: List[str] = Field(default_factory=list)
    estimated_rt60_ms: int = Field(default=1200, ge=50, le=8000)
    occlusion_barrier_hz: int = Field(default=18000, ge=300, le=20000)
    default_absorption: float = Field(default=0.4, ge=0.0, le=1.0)


# -----------------------------------------------------------------------------
# 04, 05 — Ambience Engine & Evolution Continuity
# -----------------------------------------------------------------------------

AmbienceTier = Literal["BASE", "MIDGROUND", "FOREGROUND", "DISTANT", "MICRO_TEXTURE"]

class AmbienceLayerSpec(BaseModel):
    """Specification of an individual layer within the layered Ambience Engine."""
    model_config = ConfigDict(extra="ignore")

    layer_tier: AmbienceTier = Field(...)
    asset_id: Union[int, str] = Field(default="")
    asset_name: str = Field(default="")
    asset_path: str = Field(default="")
    relative_intensity: RelativeIntensity = Field(default="subtle_bed")
    loop: bool = Field(default=True)
    stereo_width: float = Field(default=1.0, ge=0.0, le=2.0)
    spatial: SpatialMetadata = Field(default_factory=SpatialMetadata)
    stochastic_interval_sec: Optional[float] = Field(default=None, ge=1.0, le=300.0)
    mix_intent: MixIntent = Field(default_factory=MixIntent)
    transition_behavior: Literal["crossfade", "cut", "fade_from_silence", "fade_to_silence"] = Field(default="crossfade")


class AmbienceEvolutionState(BaseModel):
    """Tracks persistent acoustic state across scene boundaries."""
    model_config = ConfigDict(extra="ignore")

    active_environment_id: str = Field(...)
    dramatic_mood: str = Field(default="calm")
    tension_level: float = Field(default=0.3, ge=0.0, le=1.0)
    active_layers: List[AmbienceLayerSpec] = Field(default_factory=list)
    accumulated_duration_ms: int = Field(default=0)
    last_scene_id: str = Field(default="")


# -----------------------------------------------------------------------------
# 06 — Walla / Background Human Activity
# -----------------------------------------------------------------------------

WallaActivityType = Literal[
    "tavern_murmur",
    "market_bustle",
    "court_whispers",
    "classroom_mutter",
    "battle_rally",
    "crowd_panic",
    "temple_chanting",
    "festival_cheering",
    "whispers_and_gasps",
    "sparse_patrons",
]

class WallaLayerSpec(BaseModel):
    """Contextual background human activity specification."""
    model_config = ConfigDict(extra="ignore")

    activity_type: WallaActivityType = Field(...)
    density: Literal["sparse", "moderate", "dense", "packed"] = Field(default="moderate")
    distance: ProximityZone = Field(default="mid_distance")
    emotion: str = Field(default="neutral")
    relative_intensity: RelativeIntensity = Field(default="subtle_bed")
    asset_path: str = Field(default="")
    mix_intent: MixIntent = Field(default_factory=lambda: MixIntent(duck_under_dialogue=True))


# -----------------------------------------------------------------------------
# 07, 08, 09 — Foley Intelligence, Character & Material
# -----------------------------------------------------------------------------

class CharacterPhysicalProfile(BaseModel):
    """Physical attributes of a character governing movement sound design."""
    model_config = ConfigDict(extra="ignore")

    character_name: str = Field(...)
    body_mass: Literal["imposing_heavy", "average", "lean_agile", "frail_light", "child"] = Field(default="average")
    footwear: Literal["heavy_boots", "light_leather", "hobnailed_clogs", "bare_feet", "sandals", "slippers"] = Field(default="heavy_boots")
    equipment_weight: Literal["full_plate", "chainmail", "leather_gear", "robes", "travel_cloak", "unencumbered"] = Field(default="leather_gear")
    physical_condition: Literal["normal", "injured_limping", "exhausted", "stealthy_stalking", "agitated_fast"] = Field(default="normal")


class FoleyScoredCandidate(BaseModel):
    """
    Foley candidate evaluated with explicit narrative relevance scoring
    and conscious low-value verb rejection.
    """
    model_config = ConfigDict(extra="ignore")

    candidate_id: str = Field(...)
    segment_index: int = Field(..., ge=1)
    subject: str = Field(default="Character")
    action_verb: str = Field(...)
    object_material: str = Field(default="wood")
    surface_material: Optional[str] = Field(default=None)
    anchor_word: str = Field(default="")

    # Scoring Components (0.0 to 1.0)
    narrative_importance: float = Field(default=0.5, ge=0.0, le=1.0)
    dramatic_tension: float = Field(default=0.5, ge=0.0, le=1.0)
    physical_visibility: float = Field(default=0.5, ge=0.0, le=1.0)
    character_relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    timing_necessity: float = Field(default=0.5, ge=0.0, le=1.0)

    # Composite Score
    foley_score: float = Field(default=0.0, ge=0.0, le=1.0)
    status: Literal["ACCEPTED", "REJECTED_RESTRAINT", "REJECTED_TRIVIAL"] = Field(default="ACCEPTED")
    rejection_reason: Optional[str] = Field(default=None)
    provenance_beat_id: Optional[str] = Field(default=None)
    timing_rationale: str = Field(default="")
    dramatic_purpose: str = Field(default="")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    manner_of_action: Optional[str] = Field(default="normal", description="Execution style: stealth, forceful, hesitant, etc.")
    intensity_modifier: RelativeIntensity = Field(default="normal", description="Acoustic intensity modulation")

    def calculate_score(self) -> float:
        """Computes composite Foley score."""
        self.foley_score = round(
            (
                self.narrative_importance * 0.30 +
                self.dramatic_tension * 0.25 +
                self.physical_visibility * 0.20 +
                self.character_relevance * 0.15 +
                self.timing_necessity * 0.10
            ),
            3
        )
        return self.foley_score


# -----------------------------------------------------------------------------
# 10, 11, 12 — Narrative Hard SFX, Magic & Creature Systems
DramaticNarrativePhase = Literal[
    "CALM",
    "UNEASE",
    "TENSION",
    "THREAT",
    "EVENT",
    "AFTERMATH",
    "RECOVERY",
]


class CrossSystemInteraction(BaseModel):
    """Directorial cross-system acoustic reaction between sound design subsystems."""
    model_config = ConfigDict(extra="ignore")

    source_category: str = Field(..., description="Triggering system (e.g. 'MAGIC', 'CREATURE', 'ACTION')")
    target_system: str = Field(..., description="Affected system (e.g. 'AMBIENCE', 'WALLA', 'MUSIC', 'FOLEY')")
    reaction_type: str = Field(..., description="Reaction mode (e.g. 'attenuation', 'subordination', 'thinning', 'pre_reveal_silence')")
    description: str = Field(default="")
    mix_intent_override: Optional[MixIntent] = Field(default=None)


class SceneAcousticDramaticState(BaseModel):
    """
    Shared Scene-Level Acoustic and Dramatic State.
    Mediates cross-system reactions between Foley, Ambience, Music, SFX, Silence, Walla, Creature, Magic, and Spatial.
    """
    model_config = ConfigDict(extra="ignore")

    scene_id: str = Field(...)
    active_phase: DramaticNarrativePhase = Field(default="CALM")
    environment_id: str = Field(default="indoor_room")
    acoustic_profile_id: str = Field(default="indoor_standard")
    tension_level: float = Field(default=0.5, ge=0.0, le=1.0)
    dominant_emotion: str = Field(default="neutral")
    character_spatial_map: Dict[str, SpatialMetadata] = Field(default_factory=dict)
    active_creature: Optional[str] = Field(default=None)
    creature_proximity: ProximityZone = Field(default="mid_distance")
    active_magic_family: Optional[str] = Field(default=None)
    walla_permitted: bool = Field(default=True)
    walla_attenuation_factor: float = Field(default=1.0, ge=0.0, le=1.0)
    silence_window_active: bool = Field(default=False)
    music_variation: MotifVariationMode = Field(default="MYSTERIOUS")
    foley_prominence: RelativeIntensity = Field(default="normal")
    cross_interactions: List[CrossSystemInteraction] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# 10, 11, 12 — Narrative Hard SFX, Magic & Creature Systems
# -----------------------------------------------------------------------------

class HardSFXEventSpec(BaseModel):
    """Major physical narrative event (impact, crash, explosion, weapon clash)."""
    model_config = ConfigDict(extra="ignore")

    event_id: str = Field(...)
    segment_index: int = Field(..., ge=1)
    sfx_type: Literal[
        "impact_body",
        "impact_weapon",
        "collision_structural",
        "door_gate_slam",
        "fire_combustion",
        "water_splash",
        "explosion_concussive",
        "destruction_crash",
    ] = Field(...)
    description: str = Field(default="")
    start_ms: int = Field(default=0, ge=0)
    relative_intensity: RelativeIntensity = Field(default="prominent")
    priority: AttentionPriority = Field(default="HIGH")
    spatial: SpatialMetadata = Field(default_factory=SpatialMetadata)
    has_lfe_sub_bass: bool = Field(default=False)
    mix_intent: MixIntent = Field(default_factory=lambda: MixIntent(sidechain_trigger=True))
    asset_path: str = Field(default="")
    decision_reason: str = Field(default="")
    timing_rationale: str = Field(default="")
    dramatic_purpose: str = Field(default="")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance_segment_uid: Optional[str] = Field(default=None)
    provenance_beat_id: Optional[str] = Field(default=None)


class MagicalSoundSpec(BaseModel):
    """Coherent supernatural sound vocabulary event."""
    model_config = ConfigDict(extra="ignore")

    event_id: str = Field(...)
    spell_or_artifact_name: str = Field(...)
    stage: Literal[
        "charge_hum",
        "release_burst",
        "projectile_travel",
        "impact_strike",
        "shield_barrier",
        "teleport_displacement",
        "transformation",
        "telekinesis",
        "curse_necrotic",
        "healing_solace",
        "artifact_activation",
    ] = Field(...)
    power_level: Literal["subtle_minor", "standard", "high_potency", "cataclysmic"] = Field(default="standard")
    relative_intensity: RelativeIntensity = Field(default="prominent")
    priority: AttentionPriority = Field(default="HIGH")
    spatial: SpatialMetadata = Field(default_factory=SpatialMetadata)
    asset_path: str = Field(default="")
    sonic_identity_family: str = Field(default="generic_arcane")
    decision_reason: str = Field(default="")
    segment_index: Optional[int] = Field(default=None)
    start_ms: int = Field(default=0, ge=0)
    timing_rationale: str = Field(default="")
    dramatic_purpose: str = Field(default="")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance_segment_uid: Optional[str] = Field(default=None)
    provenance_beat_id: Optional[str] = Field(default=None)


class CreatureSoundSpec(BaseModel):
    """Complete creature sound entity representation."""
    model_config = ConfigDict(extra="ignore")

    event_id: str = Field(...)
    creature_type: str = Field(..., description="Creature slug (e.g. 'striga', 'wolf_pack', 'ghoul')")
    element: Literal["vocalization", "breathing", "locomotion_step", "body_mass_texture", "attack_strike", "injured_reaction"] = Field(...)
    emotional_state: Literal["calm", "alert_curious", "stalking", "aggressive", "injured_pained", "attacking", "retreating"] = Field(default="stalking")
    proximity: ProximityZone = Field(default="mid_distance")
    relative_intensity: RelativeIntensity = Field(default="prominent")
    priority: AttentionPriority = Field(default="HIGH")
    spatial: SpatialMetadata = Field(default_factory=SpatialMetadata)
    asset_path: str = Field(default="")
    decision_reason: str = Field(default="")
    segment_index: Optional[int] = Field(default=None)
    start_ms: int = Field(default=0, ge=0)
    timing_rationale: str = Field(default="")
    dramatic_purpose: str = Field(default="")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance_segment_uid: Optional[str] = Field(default=None)
    provenance_beat_id: Optional[str] = Field(default=None)


class CreatureSonicIdentity(BaseModel):
    """
    Persistent acoustic signature for a recurring creature entity.
    Maintains recognizable acoustic character across scenes and chapters.
    """
    model_config = ConfigDict(extra="ignore")

    creature_type: str = Field(...)
    display_name: str = Field(...)
    vocal_timbre: str = Field(default="guttural_resonant", description="Acoustic description of vocal timbre")
    breathing_cadence: str = Field(default="labored_wheeze", description="Respiration texture and pace")
    locomotion_weight: str = Field(default="heavy_quadruped", description="Footstep or locomotion physics")
    body_texture: str = Field(default="chitin_clicking", description="Surface texture: fur, scales, chitin, wet_flesh")
    preferred_reverb: str = Field(default="hall", description="Acoustic space signature")
    default_proximity: ProximityZone = Field(default="mid_distance")
    signature_motifs: List[str] = Field(default_factory=list)


class MagicalSonicIdentity(BaseModel):
    """
    Persistent sonic signature for a recurring spell, rune, or magical artifact.
    Preserves supernatural identity across multiple invocations.
    """
    model_config = ConfigDict(extra="ignore")

    spell_or_artifact_name: str = Field(...)
    family: str = Field(default="generic_arcane", description="Spell school or aesthetic lineage")
    charge_timbre: str = Field(default="crystalline_frequency_rise", description="Acoustic character of the charge hum")
    release_timbre: str = Field(default="concussive_burst", description="Acoustic character of spell release")
    impact_timbre: str = Field(default="resonant_energy_dispersion", description="Acoustic character of impact/barrier")
    harmonic_root: Optional[str] = Field(default=None, description="Tonal/musical anchor note or pitch")
    default_power_level: Literal["subtle_minor", "standard", "high_potency", "cataclysmic"] = Field(default="standard")
    associated_color_tone: Optional[str] = Field(default=None)


# -----------------------------------------------------------------------------
# 13, 14, 15 — Music Motif System, Variation & Cue Director
# -----------------------------------------------------------------------------

MotifVariationMode = Literal[
    "INTIMATE",       # Solo instrument, dry, delicate
    "MYSTERIOUS",     # Dissonant pads, high fragile tones, low drone
    "TRAGIC",         # Minor key, slow, sustained strings
    "TENSE",          # Tremolo strings, muted ostinato pulse
    "CLIMAX",         # Full arrangement, driving rhythm, brass accents
    "AFTERMATH",      # Sparse resolution, warm ambient tail
]

class MusicCueSpec(BaseModel):
    """Scene-level musical cue instruction with adaptive density."""
    model_config = ConfigDict(extra="ignore")

    cue_id: str = Field(...)
    motif_id: Optional[str] = Field(default=None)
    variation_mode: MotifVariationMode = Field(default="MYSTERIOUS")
    cue_type: Literal["TRANSITION_BRIDGE", "EMOTIONAL_UNDERSCORE", "TENSION_RISER", "CLIMACTIC_ACTION_CUE", "AFTERMATH_FADE"] = Field(...)
    start_ms: int = Field(..., ge=0)
    duration_ms: int = Field(..., gt=0)
    fade_in_ms: int = Field(default=2000, ge=0)
    fade_out_ms: int = Field(default=3000, ge=0)
    relative_intensity: RelativeIntensity = Field(default="subtle_bed")
    priority: AttentionPriority = Field(default="MEDIUM")
    track_name: str = Field(default="")
    track_id: Union[int, str] = Field(default=0)
    dramatic_justification: str = Field(default="")
    mix_intent: MixIntent = Field(default_factory=lambda: MixIntent(duck_under_dialogue=True, carve_vocal_presence=True))
    trigger_beat: Optional[str] = Field(default=None, description="Narrative beat trigger (revelation, discovery, turn, climax)")
    trigger_segment_index: Optional[int] = Field(default=None, description="Screenplay segment anchoring the cue")
    pre_roll_ms: int = Field(default=500, ge=0, description="Lead time before narrative peak or dialogue delivery")
    entry_type: Literal["fade_in", "sudden_hit", "pre_roll_swell", "subtle_drift"] = Field(default="fade_in")
    development_arc: Literal["steady_bed", "tension_riser", "emotional_swell", "driving_rhythm", "subdued_tail"] = Field(default="steady_bed")
    peak_ms: Optional[int] = Field(default=None, description="Timestamp of cue musical or dramatic peak")
    release_type: Literal["fade_out", "sharp_cutoff", "reverb_spill", "ringout"] = Field(default="fade_out")
    narrative_rationale: str = Field(default="", description="Narrative justification for music presence")


# -----------------------------------------------------------------------------
# 16 — Silence / Negative Sound Design
# -----------------------------------------------------------------------------

SilencePurpose = Literal[
    "ambient_drop_suspense",
    "foley_suppression_stealth",
    "walla_drop_arrival",
    "music_drop_impact",
    "aftermath_contemplation",
    "reveal_breath",
    "profound_stillness",
]

class SilenceEventSpec(BaseModel):
    """First-class negative sound design event."""
    model_config = ConfigDict(extra="ignore")

    silence_id: str = Field(...)
    start_ms: int = Field(..., ge=0)
    duration_ms: int = Field(..., gt=0)
    purpose: SilencePurpose = Field(...)
    affected_buses: List[Literal["AMBIENCE", "WALLA", "FOLEY", "MUSIC", "ALL"]] = Field(default_factory=lambda: ["MUSIC"])
    dramatic_rationale: str = Field(default="")
    listening_focus: Literal["dialogue_whisper", "room_acoustics", "subtext_digestion", "breath"] = Field(default="dialogue_whisper")


# -----------------------------------------------------------------------------
# 17, 18 — Acoustic Environment & Spatial Geography
# -----------------------------------------------------------------------------

class AcousticProfileSpec(BaseModel):
    """Abstract room acoustic parameters for scene sound propagation."""
    model_config = ConfigDict(extra="ignore")

    profile_id: str = Field(...)
    room_type: str = Field(default="indoor_room")
    estimated_rt60_ms: int = Field(default=800, ge=50, le=8000)
    early_reflections_intent: Literal["dry", "subtle", "prominent"] = Field(default="subtle")
    late_reverb_intent: Literal["none", "short_decay", "medium_tail", "cavernous"] = Field(default="short_decay")
    high_frequency_absorption: float = Field(default=0.4, ge=0.0, le=1.0)
    occlusion_state: OcclusionState = Field(default="direct_line_of_sight")


class SpatialSourceSpec(BaseModel):
    """Acoustic source staged on the persistent scene geography."""
    model_config = ConfigDict(extra="ignore")

    source_id: str = Field(...)
    entity_name: str = Field(...)
    role: Literal["narrator", "character", "prop_object", "creature", "environment_element"] = Field(...)
    spatial: SpatialMetadata = Field(default_factory=SpatialMetadata)
    is_active: bool = Field(default=True)


# -----------------------------------------------------------------------------
# 19 — Sound Retrieval + Asset Intelligence
# -----------------------------------------------------------------------------

class AssetProvenance(BaseModel):
    """Strict asset provenance tracking."""
    model_config = ConfigDict(extra="ignore")

    asset_id: Union[int, str] = Field(...)
    filepath: str = Field(...)
    source: Literal["local_sound_bank", "approved_provider", "generated_synthesizer"] = Field(default="local_sound_bank")
    license_type: str = Field(default="CC0_PUBLIC_DOMAIN")
    sha256_checksum: Optional[str] = Field(default=None)
    creator_attribution: Optional[str] = Field(default=None)


class SoundAssetDescriptor(BaseModel):
    """Complete semantic sound asset metadata descriptor."""
    model_config = ConfigDict(extra="ignore")

    asset_id: Union[int, str] = Field(...)
    filename: str = Field(...)
    filepath: str = Field(...)
    category: Literal["FOL", "SFX", "AMB", "MUS", "WALLA", "MAGC", "CREA"] = Field(...)
    subcategory: str = Field(default="General")
    ucs_category: str = Field(default="MISCGnl")
    semantic_tags: List[str] = Field(default_factory=list)
    action_type: Optional[str] = Field(default=None)
    exciter_material: Optional[str] = Field(default=None)
    resonator_surface: Optional[str] = Field(default=None)
    duration_sec: float = Field(default=0.0, ge=0.0)
    loopable: bool = Field(default=False)
    # DSP Sanity Metrics (Suitability signals only, NOT primary search key)
    integrated_lufs: float = Field(default=-23.0)
    true_peak_db: float = Field(default=-1.5)
    spectral_centroid_hz: float = Field(default=0.0)
    is_valid_audio: bool = Field(default=True)
    provenance: AssetProvenance = Field(...)


# -----------------------------------------------------------------------------
# 20 — Sound Timeline, Sound Director & Sound Design QC
# -----------------------------------------------------------------------------

class SoundTimelineEvent(BaseModel):
    """An individual timed event on the unified scene sound timeline."""
    model_config = ConfigDict(extra="ignore")

    event_id: str = Field(...)
    category: Literal["DX", "FOLEY", "HARD_SFX", "MAGIC", "CREATURE", "AMBIENCE", "WALLA", "MUSIC", "SILENCE"] = Field(...)
    start_ms: int = Field(..., ge=0)
    duration_ms: int = Field(..., ge=0)
    relative_intensity: RelativeIntensity = Field(default="normal")
    priority: AttentionPriority = Field(default="MEDIUM")
    asset_path: str = Field(default="")
    asset_name: Optional[str] = Field(default=None)
    spatial: SpatialMetadata = Field(default_factory=SpatialMetadata)
    mix_intent: MixIntent = Field(default_factory=MixIntent)
    decision_reason: str = Field(default="", description="Why this sound was chosen at this exact moment")
    provenance_segment_uid: Optional[str] = Field(default=None)
    provenance_beat_id: Optional[str] = Field(default=None)
    source_segment_index: Optional[int] = Field(default=None)
    timing_rationale: str = Field(default="")
    dramatic_purpose: str = Field(default="")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_resolved: bool = Field(default=True)
    unresolved_reason: Optional[str] = Field(default=None)
    resolved_asset: Optional[SoundAssetDescriptor] = Field(default=None)


class SoundTimeline(BaseModel):
    """Chronological ledger of all sound events planned for a scene or chapter."""
    model_config = ConfigDict(extra="ignore")

    timeline_id: str = Field(...)
    chapter_id: str = Field(...)
    scene_id: Optional[str] = Field(default=None)
    total_duration_ms: int = Field(..., ge=0)
    events: List[SoundTimelineEvent] = Field(default_factory=list)

    def events_in_window(self, start_ms: int, end_ms: int) -> List[SoundTimelineEvent]:
        """Returns all events active within a specific time window."""
        return [
            e for e in self.events
            if not (e.start_ms + e.duration_ms <= start_ms or e.start_ms >= end_ms)
        ]


class QCViolationRecord(BaseModel):
    """
    Forensic record of a sound design quality rule violation.
    Provides complete inspectability: scene, event, rule, severity, and exact contrast
    between expected and actual behavior.
    """
    model_config = ConfigDict(extra="ignore")

    scene_id: str = Field(...)
    event_id: Optional[str] = Field(default=None)
    category: str = Field(..., description="Affected category: FOLEY, AMBIENCE, WALLA, MUSIC, SFX, SPATIAL, etc.")
    rule_id: str = Field(..., description="QC rule identifier (e.g. TABLEWARE_COLLISION, NO_FAKE_PATHS, BOUNDS_OVERFLOW)")
    severity: Literal["ERROR", "WARNING"] = Field(default="ERROR")
    reason: str = Field(..., description="Human-readable root cause explanation")
    expected_behavior: str = Field(..., description="What the cinematic audio standard expected")
    actual_behavior: str = Field(..., description="What was actually found on the timeline or blueprint")


class SoundDesignQCReport(BaseModel):
    """
    Independent Multi-Signal Sound Design Quality Control Report.
    Audits narrative justification, restraint adherence, continuity, and mix readiness.
    """
    model_config = ConfigDict(extra="ignore")

    report_id: str = Field(...)
    scene_or_chapter_id: str = Field(...)
    status: Literal["PASS", "WARN", "FAIL"] = Field(default="PASS")
    restraint_score: float = Field(default=1.0, ge=0.0, le=1.0, description="1.0 = perfect restraint adherence")
    foley_evaluated_count: int = Field(default=0)
    foley_accepted_count: int = Field(default=0)
    foley_rejected_count: int = Field(default=0)
    ambience_continuity_verified: bool = Field(default=True)
    walla_subordination_verified: bool = Field(default=True)
    hard_sfx_collision_free: bool = Field(default=True)
    music_motif_valid: bool = Field(default=True)
    intentional_silence_preserved: bool = Field(default=True)
    spatial_stage_valid: bool = Field(default=True)
    asset_provenance_verified: bool = Field(default=True)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    violations: List[QCViolationRecord] = Field(default_factory=list)
    telemetry: Dict[str, Any] = Field(default_factory=dict)
