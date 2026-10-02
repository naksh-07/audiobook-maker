#!/usr/bin/env python3
"""
Audiobook Factory - Sonic Genome & Audio Intelligence Contracts (v2.1).
Defines multi-dimensional sonic representation across physical, temporal,
spatial, environmental, dramatic, and epistemic measurement layers.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Literal, Tuple
from pydantic import BaseModel, Field, ConfigDict

from .base import ProvenanceMethod


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
    measurement_method: str = Field(default="ebur128_astats", description="DSP measurement pipeline identifier")
    analyzer_version: str = Field(default="1.0", description="Analyzer version")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Measurement confidence")
    measured_at: Optional[str] = Field(default=None, description="ISO timestamp of measurement")


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
    confidence: float = Field(default=0.85, ge=0.0, le=1.0, description="Inference confidence")
    inference_source: str = Field(default="gemini_flash", description="Model or taxonomy source")


class PhysicalGenome(BaseModel):
    """Physical event, materials, and interaction semantics."""
    model_config = ConfigDict(extra="ignore")

    source_object: str = Field(default="", description="Primary physical object (e.g. 'sword', 'boot', 'door')")
    source_material: str = Field(default="", description="Primary material (e.g. 'steel', 'leather', 'wood')")
    secondary_material: Optional[str] = Field(default=None, description="Secondary contact material (e.g. 'stone', 'chainmail')")
    action_type: str = Field(default="", description="Physical action (e.g. 'clash', 'draw', 'footstep', 'creak', 'pour')")
    interaction_type: str = Field(default="", description="Physical interaction (e.g. 'collision', 'friction', 'fluid', 'aerodynamic')")
    surface_material: Optional[str] = Field(default=None, description="Ground or boundary surface (e.g. 'wet_stone', 'oak_floor')")
    impact_force: Literal["delicate", "light", "medium", "heavy", "violent"] = Field(default="medium")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    knowledge_class: Literal["measured", "inferred", "curated"] = Field(default="inferred")


class TemporalWaveGenome(BaseModel):
    """Temporal evolution and acoustic wave shape characteristics."""
    model_config = ConfigDict(extra="ignore")

    temporal_class: Literal["instant", "transient", "short", "sustained", "evolving", "loopable"] = Field(default="transient")
    wave_style: Literal[
        "transient_percussive",
        "sustained_bed",
        "staccato_hit",
        "textural_drone",
        "harmonic_swell",
        "rhythmic_loop",
        "general"
    ] = Field(default="general")
    energy_envelope: Literal["subtle", "low", "medium", "high", "explosive"] = Field(default="medium")
    texture: Literal["clean", "rough", "grainy", "metallic", "organic", "airy", "dark", "bright"] = Field(default="organic")
    motion: Literal["static", "rising", "falling", "swelling", "pulsing", "chaotic", "rhythmic"] = Field(default="static")
    attack_ms: Optional[float] = None
    decay_ms: Optional[float] = None
    sustain_level: Optional[float] = None
    release_ms: Optional[float] = None
    is_loopable: bool = False


class SpatialGenome(BaseModel):
    """Acoustic environment, perceived distance, and spatial geometry."""
    model_config = ConfigDict(extra="ignore")

    perspective: Literal["intimate", "close", "medium", "distant", "off_stage"] = Field(default="medium")
    room_size: Optional[str] = Field(default=None, description="e.g. 'cathedral', 'large_hall', 'small_chamber', 'outdoor'")
    reverb_character: Optional[str] = Field(default=None, description="e.g. 'dry', 'stone_reverberant', 'wooden_warm', 'subterranean'")
    estimated_rt60_ms: Optional[int] = None
    stereo_width: float = Field(default=1.0, ge=0.0, le=2.0)
    mono_compatible: bool = True


class EnvironmentalGenome(BaseModel):
    """Scene environmental compatibility parameters."""
    model_config = ConfigDict(extra="ignore")

    environment_type: str = Field(default="", description="Setting type (e.g. 'castle_hall', 'dark_forest', 'tavern', 'dungeon')")
    interior_exterior: Literal["interior", "exterior", "subterranean", "indeterminate"] = Field(default="indeterminate")
    weather: Optional[str] = Field(default=None, description="e.g. 'rain', 'wind', 'storm', 'clear'")
    time_of_day: Optional[str] = Field(default=None, description="e.g. 'night', 'day', 'dawn', 'dusk'")
    acoustic_space: Optional[str] = Field(default=None)
    environmental_density: Literal["sparse", "moderate", "dense", "chaotic"] = Field(default="moderate")


class DramaticGenome(BaseModel):
    """Dramatic storytelling intention and narrative impact."""
    model_config = ConfigDict(extra="ignore")

    narrative_function: str = Field(default="AMBIENT_BED")
    dramatic_role: Literal[
        "suspense_builder",
        "action_confirmation",
        "punctuation",
        "emotional_resonance",
        "ambient_grounding",
        "threat_foreshadowing",
        "relief_resolution",
        "general"
    ] = Field(default="general")
    foreground_strength: float = Field(default=0.5, ge=0.0, le=1.0, description="0.0 = subliminal background, 1.0 = dominant hero event")
    attention_demand: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "TEXTURE"] = Field(default="MEDIUM")
    surprise_factor: float = Field(default=0.0, ge=0.0, le=1.0)
    tension_effect: float = Field(default=0.0, ge=-1.0, le=1.0, description="-1.0 = relieves tension, +1.0 = spikes tension")
    scene_roles_allowed: List[str] = Field(default_factory=list)
    scene_roles_forbidden: List[str] = Field(default_factory=list)


class MixCompatibilityGenome(BaseModel):
    """Acoustic interaction constraints with narration, dialogue, and other audio layers."""
    model_config = ConfigDict(extra="ignore")

    voice_masking_risk: Literal["LOW", "MODERATE", "SEVERE"] = Field(default="LOW")
    dialogue_compatibility: float = Field(default=0.8, ge=0.0, le=1.0)
    whisper_compatibility: float = Field(default=0.5, ge=0.0, le=1.0)
    recommended_clearance_ms: int = Field(default=0, ge=0)
    ducking_recommendation_db: float = Field(default=-16.0)
    recommended_gain_range_db: Tuple[float, float] = Field(default=(-24.0, -12.0))
    spectral_vocal_pocket_needed: bool = False


class MusicIntelligence(BaseModel):
    """Specific musical attributes for melodic and underscore assets."""
    model_config = ConfigDict(extra="ignore")

    bpm: float = Field(default=0.0, ge=0.0)
    key_tonality: Optional[str] = Field(default=None, description="e.g. 'D minor', 'C major', 'Atonal'")
    mode: Optional[str] = Field(default=None, description="e.g. 'minor', 'major', 'dorian', 'phrygian'")
    time_signature: str = Field(default="4/4")
    lead_instruments: List[str] = Field(default_factory=list)
    energy_level: int = Field(default=5, ge=1, le=10)
    structure_sections: List[Dict[str, Any]] = Field(default_factory=list)


class FoleyIntelligence(BaseModel):
    """Specific Foley parameters for human or creature physical movement."""
    model_config = ConfigDict(extra="ignore")

    actor_type: str = Field(default="human")
    body_weight: Literal["light", "medium", "heavy", "massive"] = Field(default="medium")
    action: str = Field(default="step")
    surface: str = Field(default="ground")
    footwear: Optional[str] = Field(default=None)
    clothing_texture: Optional[str] = Field(default=None)
    movement_speed: Literal["stealth", "slow", "normal", "brisk", "running", "frantic"] = Field(default="normal")


class RemoteAssetMetadata(BaseModel):
    """Remote virtual asset provenance, mirror links, and availability tracking."""
    model_config = ConfigDict(extra="ignore")

    source_collection: str = Field(default="", description="e.g. 'Incompetech', 'BBC_Sound_Effects', 'Sonniss_GDC', 'Kenney'")
    source_url: str = Field(default="", description="Primary direct download URL")
    mirror_url: Optional[str] = Field(default=None, description="Backup/mirror download URL")
    source_page_url: Optional[str] = Field(default=None, description="Source info / web landing page")
    url_status: Literal["available", "unverified", "broken", "mirrored"] = Field(default="unverified")
    last_verified_at: Optional[str] = None
    license_type: str = Field(default="Royalty-Free")
    creator: Optional[str] = None
    attribution: Optional[str] = None
    sha256_checksum: Optional[str] = None


class ProvenanceRecord(BaseModel):
    """Traceable provenance record for any measurement, inference, or metadata extraction."""
    model_config = ConfigDict(extra="ignore")

    source_method: ProvenanceMethod = Field(..., description="Method used to obtain data")
    analyzer_id: str = Field(..., description="Identifier of analyzer, script, or model")
    analyzer_version: str = Field(default="1.0.0", description="Semantic version of analyzer")
    ontology_version: str = Field(default="sonic_genome_v2.1", description="Taxonomy/ontology version")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_asset_version: Optional[str] = Field(default=None, description="Hash or timestamp of source file")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confidence (None for deterministic physical measurements)")
    processing_version: str = Field(default="phase1_v1.0", description="Pipeline processing stage version")
    notes: Optional[str] = Field(default=None, description="Optional diagnostic notes or execution telemetry")


class NormalizedSourceFields(BaseModel):
    """Normalized representation of third-party source collection metadata."""
    model_config = ConfigDict(extra="ignore")

    title: str = Field(default="")
    description: str = Field(default="")
    tags: List[str] = Field(default_factory=list)
    category: str = Field(default="SFX")
    subcategory: str = Field(default="General")
    creator: str = Field(default="")
    collection: str = Field(default="")
    genre: str = Field(default="")
    mood: str = Field(default="default")
    tempo_bpm: Optional[float] = None
    duration_sec: float = Field(default=0.0, ge=0.0)
    source_url: Optional[str] = None
    license: str = Field(default="Royalty-Free")
    provider_id: str = Field(default="")


class SourceMetadata(BaseModel):
    """Preserved raw source metadata alongside normalized attributes and provenance."""
    model_config = ConfigDict(extra="ignore")

    provider_name: str = Field(default="generic_source")
    raw_metadata: Dict[str, Any] = Field(default_factory=dict, description="Original unparsed provider payload")
    normalized: NormalizedSourceFields = Field(default_factory=NormalizedSourceFields)
    provenance: ProvenanceRecord = Field(
        default_factory=lambda: ProvenanceRecord(
            source_method="source_metadata",
            analyzer_id="source_adapter",
            analyzer_version="1.0.0",
        )
    )


class FormatFacts(BaseModel):
    """Deterministic audio container and codec facts."""
    model_config = ConfigDict(extra="ignore")

    duration_sec: float = Field(default=0.0, ge=0.0)
    sample_rate: int = Field(default=48000, ge=8000)
    channels: int = Field(default=2, ge=1)
    codec: str = Field(default="pcm_s16le")
    container: str = Field(default="wav")
    bit_depth: Optional[int] = Field(default=16)
    file_size_bytes: int = Field(default=0, ge=0)
    bit_rate: int = Field(default=0, ge=0)
    tags: Dict[str, Any] = Field(default_factory=dict, description="Embedded container tags")


class LoudnessFacts(BaseModel):
    """Deterministic EBU R128 loudness and peak dynamics."""
    model_config = ConfigDict(extra="ignore")

    integrated_lufs: Optional[float] = Field(default=None, description="Integrated loudness in LUFS")
    true_peak_dbtp: Optional[float] = Field(default=None, description="True peak in dBTP")
    loudness_range_lu: Optional[float] = Field(default=None, description="EBU R128 Loudness Range in LU")
    rms_level_db: Optional[float] = Field(default=None, description="RMS level in dBFS")
    peak_level_db: Optional[float] = Field(default=None, description="Max sample peak in dBFS")
    dynamic_range_db: Optional[float] = Field(default=None, description="Crest factor / dynamic range in dB")


class SpectralFacts(BaseModel):
    """Deterministic frequency domain spectral descriptors."""
    model_config = ConfigDict(extra="ignore")

    spectral_centroid_hz: Optional[float] = Field(default=None, description="Spectral center of mass (brightness) in Hz")
    spectral_bandwidth_hz: Optional[float] = Field(default=None, description="Spectral spread in Hz")
    spectral_rolloff_hz: Optional[float] = Field(default=None, description="85% energy rolloff frequency in Hz")
    spectral_flatness: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Spectral flatness / noisiness (0.0 to 1.0)")
    zero_crossing_rate: Optional[float] = Field(default=None, ge=0.0, description="Rate of sign-changes along signal")


class TemporalFacts(BaseModel):
    """Deterministic time-domain descriptors and boundaries."""
    model_config = ConfigDict(extra="ignore")

    silence_ratio: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Fraction of frames below -60 dBFS")
    active_duration_sec: Optional[float] = Field(default=None, ge=0.0)
    active_start_sec: Optional[float] = Field(default=None, ge=0.0)
    active_end_sec: Optional[float] = Field(default=None, ge=0.0)
    transient_count: Optional[int] = Field(default=None, ge=0)
    major_transients_sec: List[float] = Field(default_factory=list)
    energy_envelope: Optional[str] = Field(default=None)


class TonalFacts(BaseModel):
    """Tonal and musical facts (strictly None if not technically meaningful for the sound)."""
    model_config = ConfigDict(extra="ignore")

    is_tonal: Optional[bool] = Field(default=None, description="Whether sound exhibits clear pitch/harmonicity")
    detected_pitch_hz: Optional[float] = Field(default=None, description="Fundamental frequency if tonal")
    detected_bpm: Optional[float] = Field(default=None, description="Tempo BPM if rhythmic/musical")
    tuning_hz: Optional[float] = Field(default=None, description="Tuning reference in Hz (e.g. 440.0)")


class MeasuredAudioFacts(BaseModel):
    """Measured physical facts extracted via deterministic local DSP (zero AI hallucinations)."""
    model_config = ConfigDict(extra="ignore")

    format: FormatFacts = Field(default_factory=FormatFacts)
    loudness: LoudnessFacts = Field(default_factory=LoudnessFacts)
    spectral: SpectralFacts = Field(default_factory=SpectralFacts)
    temporal: TemporalFacts = Field(default_factory=TemporalFacts)
    tonal: TonalFacts = Field(default_factory=TonalFacts)
    provenance: ProvenanceRecord = Field(
        default_factory=lambda: ProvenanceRecord(
            source_method="measured_dsp",
            analyzer_id="deterministic_dsp_engine",
            analyzer_version="1.0.0",
            confidence=None,  # Explicitly None for physical measurements
        )
    )


class AudioEventRecord(BaseModel):
    """A timed audio event detected deterministically or inferred."""
    model_config = ConfigDict(extra="ignore")

    event_type: str = Field(
        ...,
        description="e.g. 'transient_onset', 'silence_region', 'active_region', 'classifier_observation_window', 'sed_event', 'analysis_window'"
    )
    start_sec: float = Field(..., ge=0.0)
    end_sec: float = Field(..., ge=0.0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source_method: ProvenanceMethod = Field(default="measured_dsp")
    detector_id: str = Field(default="onset_detector_v1")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentInterpretation(BaseModel):
    """Creative, narrative, or mix interpretation produced by an autonomous agent."""
    model_config = ConfigDict(extra="ignore")

    evaluator_agent: str = Field(..., description="Agent name (e.g. 'SoundDesignDirector', 'MusicCueDirector', 'MixDirector', 'RetrievalAgent')")
    evaluated_at: str = Field(..., description="ISO 8601 timestamp of evaluation")
    scene_context: Optional[str] = Field(default=None, description="Scene ID or dramatic context")

    # Creative / Directorial Decisions (Evaluated at scene/usage time)
    assigned_dramatic_role: Optional[str] = Field(default=None, description="Contextual dramatic role assigned by director")
    scene_purpose: Optional[str] = Field(default=None, description="Specific dramatic purpose in scene")
    emotional_suitability: Optional[str] = Field(default=None, description="Contextual emotional suitability / mood")
    assigned_mood: Optional[str] = Field(default=None, description="Contextual mood (alias to emotional_suitability)")
    voice_masking_judgment: Optional[str] = Field(default=None, description="Voice masking judgment: LOW, MODERATE, SEVERE")
    voice_masking_assessment: Optional[str] = Field(default=None, description="Voice masking assessment (alias to voice_masking_judgment)")
    dialogue_ducking_amount_db: Optional[float] = Field(default=None, description="Target dialogue ducking in dB")
    contextual_ducking_db: Optional[float] = Field(default=None, description="Contextual ducking in dB (alias to dialogue_ducking_amount_db)")
    placement_usage: Optional[str] = Field(default=None, description="Timeline placement and recommended usage in scene")
    final_taxonomy: Optional[str] = Field(default=None, description="Final creative taxonomy when requiring interpretation")

    mix_notes: Optional[str] = Field(default=None, description="Directorial or acoustic mix notes")
    creative_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confidence of the agent's interpretation; None if unprovided")
    conflict_notes: Optional[str] = Field(default=None, description="Explanations of any tension between source tags and classifier evidence")

    def model_post_init(self, __context: Any) -> None:
        # Harmonize aliases
        if self.emotional_suitability is None and self.assigned_mood is not None:
            self.emotional_suitability = self.assigned_mood
        elif self.assigned_mood is None and self.emotional_suitability is not None:
            self.assigned_mood = self.emotional_suitability

        if self.voice_masking_judgment is None and self.voice_masking_assessment is not None:
            self.voice_masking_judgment = self.voice_masking_assessment
        elif self.voice_masking_assessment is None and self.voice_masking_judgment is not None:
            self.voice_masking_assessment = self.voice_masking_judgment

        if self.dialogue_ducking_amount_db is None and self.contextual_ducking_db is not None:
            self.dialogue_ducking_amount_db = self.contextual_ducking_db
        elif self.contextual_ducking_db is None and self.dialogue_ducking_amount_db is not None:
            self.contextual_ducking_db = self.dialogue_ducking_amount_db


class ClassifierPrediction(BaseModel):
    """Individual categorical prediction from an audio classifier with raw model outputs."""
    model_config = ConfigDict(extra="ignore")

    raw_label: str = Field(..., description="Exact raw label from model output vocabulary")
    normalized_label: Optional[str] = Field(default=None, description="Normalized taxonomy label if cleanly mapped")
    raw_score: float = Field(..., description="Raw model confidence (e.g. unthresholded sigmoid/logit)")
    calibrated_score: Optional[float] = Field(default=None, description="Empirically calibrated probability score if calibration exists")
    rank: int = Field(default=1, ge=1, description="Relative confidence rank in inference pass")
    ontology_id: str = Field(default="audioset_527", description="Taxonomy identifier")
    start_sec: Optional[float] = Field(default=None, description="Start time if temporally localized")
    end_sec: Optional[float] = Field(default=None, description="End time if temporally localized")


class ClassifierInferences(BaseModel):
    """Epistemic collection of classifier predictions preserving raw model evidence."""
    model_config = ConfigDict(extra="ignore")

    model_id: str = Field(default="MIT/ast-finetuned-audioset-10-10-0.4593")
    model_version: str = Field(default="1.0.0")
    ontology_id: str = Field(default="audioset_527")
    predictions: List[ClassifierPrediction] = Field(default_factory=list)
    top_labels: List[str] = Field(default_factory=list)
    negative_evidence: List[str] = Field(default_factory=list, description="Classes evaluated with near-zero confidence")
    provenance: ProvenanceRecord = Field(
        default_factory=lambda: ProvenanceRecord(
            source_method="classifier",
            analyzer_id="ast_audioset_classifier",
            analyzer_version="1.0.0",
        )
    )


class SemanticEmbeddingFacts(BaseModel):
    """Open-vocabulary CLAP semantic vector representation."""
    model_config = ConfigDict(extra="ignore")

    model_id: str = Field(default="laion/clap-htsat-unfused")
    model_version: str = Field(default="2023_v1")
    embedding_dim: int = Field(default=512)
    preprocessing_version: str = Field(default="v1_centered_energy_conserving_pad")
    vector: Optional[List[float]] = Field(default=None, description="Normalized float32 vector in memory")
    provenance: ProvenanceRecord = Field(
        default_factory=lambda: ProvenanceRecord(
            source_method="semantic_model",
            analyzer_id="laion_clap_hts_at",
            analyzer_version="1.0.0",
            confidence=None,  # Embeddings are geometric representations, not scalar confidences
        )
    )


class InferredMetadata(BaseModel):
    """Heuristic, rule-based, and keyword-derived taxonomic classifications."""
    model_config = ConfigDict(extra="ignore")

    category: str = Field(default="SFX")
    action_type: str = Field(default="")
    exciter: str = Field(default="")
    resonator: str = Field(default="")
    tags: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    provenance: ProvenanceRecord = Field(
        default_factory=lambda: ProvenanceRecord(
            source_method="keyword_inferred",
            analyzer_id="rule_taxonomy_v1",
            analyzer_version="1.0.0",
            confidence=0.75,
        )
    )


class SonicGenome(BaseModel):
    """The Complete Multi-Dimensional Sonic Genome (v2.1)."""
    model_config = ConfigDict(extra="ignore")

    version: str = Field(default="2.1", description="Schema version")
    track_id: int = Field(default=0, description="Catalog track ID")
    filename: str = Field(default="", description="Track filename")

    # 6 Epistemic Layers
    source_metadata: SourceMetadata = Field(default_factory=SourceMetadata)
    measured_facts: MeasuredAudioFacts = Field(default_factory=MeasuredAudioFacts)
    inferred: InferredMetadata = Field(default_factory=InferredMetadata)
    classifier_inferences: Optional[ClassifierInferences] = Field(default=None, description="Phase 2 audio event/classifier inferences")
    semantic_model_facts: Optional[SemanticEmbeddingFacts] = Field(default=None, description="Phase 2 CLAP semantic vector facts")
    classifier_output: Optional[Dict[str, Any]] = Field(default=None, description="Serialized dictionary representation for legacy callers")
    semantic_model_output: Optional[Dict[str, Any]] = Field(default=None, description="Serialized dictionary representation for legacy callers")
    curated_data: Optional[Dict[str, Any]] = Field(default=None, description="Sound designer overrides")

    # Temporal Events & Full Ledger
    events: List[AudioEventRecord] = Field(default_factory=list)
    provenance_ledger: List[ProvenanceRecord] = Field(default_factory=list)

    # Backward compatible fields (preserved 100% for existing callers)
    acoustic: AcousticMetrics = Field(default_factory=AcousticMetrics)
    semantic: SemanticAnnotations = Field(default_factory=SemanticAnnotations)
    id3_metadata: Dict[str, Any] = Field(default_factory=dict, description="Embedded ID3 tag dictionary")

    # Sonic Genome Extended Dimensions
    physical: PhysicalGenome = Field(default_factory=PhysicalGenome)
    temporal: TemporalWaveGenome = Field(default_factory=TemporalWaveGenome)
    spatial: SpatialGenome = Field(default_factory=SpatialGenome)
    environmental: EnvironmentalGenome = Field(default_factory=EnvironmentalGenome)
    dramatic: DramaticGenome = Field(default_factory=DramaticGenome)
    mix: MixCompatibilityGenome = Field(default_factory=MixCompatibilityGenome)
    music: MusicIntelligence = Field(default_factory=MusicIntelligence)
    foley: FoleyIntelligence = Field(default_factory=FoleyIntelligence)
    remote: RemoteAssetMetadata = Field(default_factory=RemoteAssetMetadata)
    provenance_log: List[Dict[str, Any]] = Field(default_factory=list)

    def sync_measured_to_acoustic(self) -> None:
        """Keep backward-compatible acoustic metrics synchronized with measured_facts."""
        m = self.measured_facts
        if m.loudness.integrated_lufs is not None:
            self.acoustic.integrated_lufs = m.loudness.integrated_lufs
        if m.loudness.true_peak_dbtp is not None:
            self.acoustic.true_peak_dbtp = m.loudness.true_peak_dbtp
        if m.tonal.detected_bpm is not None:
            self.acoustic.bpm = m.tonal.detected_bpm
        if m.temporal.major_transients_sec:
            self.acoustic.transient_drops_sec = m.temporal.major_transients_sec
        if m.spectral.spectral_centroid_hz is not None:
            hz = m.spectral.spectral_centroid_hz
            if 1000.0 <= hz <= 4000.0 and (m.loudness.integrated_lufs or -70) > -25.0:
                self.acoustic.vocal_clash_risk = "MODERATE"
            else:
                self.acoustic.vocal_clash_risk = "LOW"

    def record_ai_inference(
        self,
        classifier: Optional[ClassifierInferences] = None,
        semantic: Optional[SemanticEmbeddingFacts] = None,
        events: Optional[List[AudioEventRecord]] = None,
    ) -> None:
        """Register AI inferences (classifiers, CLAP embeddings, events) into the Sonic Genome with provenance."""
        if classifier is not None:
            self.classifier_inferences = classifier
            self.classifier_output = classifier.model_dump(mode="json")
            if classifier.provenance:
                self.provenance_ledger.append(classifier.provenance)
        if semantic is not None:
            self.semantic_model_facts = semantic
            self.semantic_model_output = semantic.model_dump(mode="json")
            if semantic.provenance:
                self.provenance_ledger.append(semantic.provenance)
        if events:
            for ev in events:
                self.events.append(ev)
