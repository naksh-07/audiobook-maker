#!/usr/bin/env python3
"""
Audiobook Factory - Creative Manifest & Audio Cues Contracts.
Defines MusicCue, FoleyCue, AmbienceScene, MasteringConfig, CreativeManifest,
and LegacyCreativeManifestAdapter.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal, Union
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, AliasChoices

from .base import ManifestValidationError, MusicCueType


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

    @model_validator(mode="after")
    def clamp_fade_envelope(self) -> MusicCue:
        total_fade = (self.fade_in_ms or 0) + (self.fade_out_ms or 0)
        if self.duration_ms > 0 and total_fade > self.duration_ms:
            ratio = (self.duration_ms * 0.95) / max(1, total_fade)
            self.fade_in_ms = int(self.fade_in_ms * ratio)
            self.fade_out_ms = int(self.fade_out_ms * ratio)
        return self

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
    is_micro_foley: bool = Field(default=False, description="Whether cue is ambient living-world micro-foley (cups, cloth, chairs)")
    foley_type: str = Field(default="prop", description="Foley sub-type: prop, clothing, tableware, footstep, environmental")

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


class ConvolutionIRConfig(BaseModel):
    """Acoustic convolution impulse response parameters for spatial room staging."""
    model_config = ConfigDict(extra="ignore")

    preset_name: str = Field(default="room", description="Standard IR preset name")
    ir_asset_path: Optional[str] = Field(default=None, description="Filesystem path to WAV impulse response")
    wet_dry_ratio: float = Field(default=0.12, ge=0.0, le=0.50, description="Wet-to-dry mix ratio for dialogue bus (0.10 to 0.15 nominal)")
    early_reflections_decay_ms: int = Field(default=220, description="Early reflection decay time in ms")
    high_cut_hz: Optional[int] = Field(default=8500, description="High frequency damping cutoff")
    enabled: bool = Field(default=True, description="Whether convolution reverb staging is active")


class WallahAutomationPoint(BaseModel):
    """Dynamic speech-reactive crowd murmur / ambient breathing automation point."""
    model_config = ConfigDict(extra="ignore")

    start_ms: int = Field(..., ge=0, description="Start offset on timeline in ms")
    end_ms: int = Field(..., gt=0, description="End offset on timeline in ms")
    target_attenuation_db: float = Field(default=-6.0, description="Attenuation during speech (e.g. -6dB)")
    swell_during_pause_db: float = Field(default=3.0, description="Swell boost during pause >= 1.0s (e.g. +3dB)")
    is_pause_swell: bool = Field(default=False, description="Whether point represents a dramatic pause swell")


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
    ducking_ratio: float = Field(default=3.2, ge=1.0, le=20.0, description="Sidechain compressor ratio")
    ducking_knee: float = Field(default=2.8, ge=0.0, le=10.0, description="Sidechain compressor knee in dB")
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
    acoustic_staging: Dict[str, ConvolutionIRConfig] = Field(default_factory=dict, description="Scene acoustic convolution staging configs")
    wallah_automations: List[WallahAutomationPoint] = Field(default_factory=list, description="Dynamic crowd breathing envelope points")
    scene_intent: Optional[Any] = Field(default=None, description="Stage 11 Scene Mix Intent")
    attention_map: Optional[Any] = Field(default=None, description="Stage 11 Time-aware Listener Attention Map")
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
    def parse_scene_acoustics(self) -> CreativeManifest:
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
                ratio=getattr(legacy.mastering, "ducking_ratio", PROFILE_STANDARD.ratio),
                knee=getattr(legacy.mastering, "ducking_knee", PROFILE_STANDARD.knee),
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
            acoustic_staging=dict(getattr(legacy, "acoustic_staging", {})),
            wallah_automations=list(getattr(legacy, "wallah_automations", [])),
            metadata=dict(legacy.metadata),
        )
