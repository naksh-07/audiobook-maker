#!/usr/bin/env python3
"""
Audiobook Factory - Sound Design Subsystem
==========================================
Unified cinematic audio drama sound design engine.
Covers all 20 sound design capabilities:
- Scene Audio Understanding & Blueprint
- Layered Ambience, Continuity & Walla
- Intelligent Foley, Physical Characters & Material Matrix
- Narrative Hard SFX, Magic Language & Creatures
- Persistent Motifs, Variation Engine & Scene Cue Director
- First-Class Silence & Abstract Spatial Acoustics
- Verified Asset Intelligence & Multi-Signal QC
"""

from audiobook_factory.sound_design.contracts import (
    RelativeIntensity,
    AttentionPriority,
    ProximityZone,
    SpatialTrajectory,
    OcclusionState,
    MixIntent,
    SpatialMetadata,
    ActionCandidate,
    SceneAudioUnderstandingResult,
    SceneAudioBlueprint,
    EnvironmentProfile,
    AmbienceTier,
    AmbienceLayerSpec,
    AmbienceEvolutionState,
    WallaActivityType,
    WallaLayerSpec,
    CharacterPhysicalProfile,
    FoleyScoredCandidate,
    HardSFXEventSpec,
    MagicalSoundSpec,
    CreatureSoundSpec,
    MotifVariationMode,
    MusicCueSpec,
    SilencePurpose,
    SilenceEventSpec,
    AcousticProfileSpec,
    SpatialSourceSpec,
    AssetProvenance,
    SoundAssetDescriptor,
    SoundTimelineEvent,
    SoundTimeline,
    SoundDesignQCReport,
)
from audiobook_factory.sound_design.environment_profiles import (
    EnvironmentRegistry,
    get_environment_registry,
)
from audiobook_factory.sound_design.asset_retriever import (
    AssetRetriever,
    get_asset_retriever,
)
from audiobook_factory.sound_design.scene_understanding import (
    SceneAudioUnderstandingEngine,
    get_scene_understanding_engine,
)
from audiobook_factory.sound_design.blueprint import (
    BlueprintBuilder,
    get_blueprint_builder,
)
from audiobook_factory.sound_design.ambience_engine import (
    AmbienceEngine,
    get_ambience_engine,
)
from audiobook_factory.sound_design.walla_engine import (
    WallaEngine,
    get_walla_engine,
)
from audiobook_factory.sound_design.silence_engine import (
    SilenceEngine,
    get_silence_engine,
)
from audiobook_factory.sound_design.foley_engine import (
    FoleyEngine,
    get_foley_engine,
)
from audiobook_factory.sound_design.foley_character_material import (
    MaterialMatrixEngine,
    CharacterFoleyRegistry,
    get_character_foley_registry,
)
from audiobook_factory.sound_design.narrative_sfx import (
    HardSFXEngine,
    get_hard_sfx_engine,
    CreatureSoundEngine,
    get_creature_engine,
)
from audiobook_factory.sound_design.magical_sound import (
    MagicalSoundEngine,
    get_magical_sound_engine,
)
from audiobook_factory.sound_design.music_motif_director import (
    MotifVariationEngine,
    MusicCueDirector,
    get_music_cue_director,
)
from audiobook_factory.sound_design.spatial_acoustics import (
    SpatialAcousticsEngine,
    get_spatial_acoustics_engine,
    SpatialGeographyEngine,
    get_spatial_geography_engine,
)
from audiobook_factory.sound_design.sound_director import (
    SoundDesignDirector,
    get_sound_design_director,
)
from audiobook_factory.sound_design.qc import (
    SoundDesignQCAuditor,
    get_sound_design_qc_auditor,
)
from audiobook_factory.sound_design.adapter import (
    SoundDesignAdapter,
    get_sound_design_adapter,
)
from audiobook_factory.sound_design.golden_benchmarks import (
    GOLDEN_BENCHMARK_SCENARIOS,
)

__all__ = [





    "RelativeIntensity",
    "AttentionPriority",
    "ProximityZone",
    "SpatialTrajectory",
    "OcclusionState",
    "MixIntent",
    "SpatialMetadata",
    "ActionCandidate",
    "SceneAudioUnderstandingResult",
    "SceneAudioBlueprint",
    "EnvironmentProfile",
    "AmbienceTier",
    "AmbienceLayerSpec",
    "AmbienceEvolutionState",
    "WallaActivityType",
    "WallaLayerSpec",
    "CharacterPhysicalProfile",
    "FoleyScoredCandidate",
    "HardSFXEventSpec",
    "MagicalSoundSpec",
    "CreatureSoundSpec",
    "MotifVariationMode",
    "MusicCueSpec",
    "SilencePurpose",
    "SilenceEventSpec",
    "AcousticProfileSpec",
    "SpatialSourceSpec",
    "AssetProvenance",
    "SoundAssetDescriptor",
    "SoundTimelineEvent",
    "SoundTimeline",
    "SoundDesignQCReport",
    "EnvironmentRegistry",
    "get_environment_registry",
    "AssetRetriever",
    "get_asset_retriever",
    "SceneAudioUnderstandingEngine",
    "get_scene_understanding_engine",
    "BlueprintBuilder",
    "get_blueprint_builder",
    "AmbienceEngine",
    "get_ambience_engine",
    "WallaEngine",
    "get_walla_engine",
    "SilenceEngine",
    "get_silence_engine",
    "FoleyEngine",
    "get_foley_engine",
    "MaterialMatrixEngine",
    "CharacterFoleyRegistry",
    "get_character_foley_registry",
    "HardSFXEngine",
    "get_hard_sfx_engine",
    "CreatureSoundEngine",
    "get_creature_engine",
    "MagicalSoundEngine",
    "get_magical_sound_engine",
    "MotifVariationEngine",
    "MusicCueDirector",
    "get_music_cue_director",
    "SpatialAcousticsEngine",
    "get_spatial_acoustics_engine",
    "SpatialGeographyEngine",
    "get_spatial_geography_engine",
    "SoundDesignDirector",
    "get_sound_design_director",
    "SoundDesignQCAuditor",
    "get_sound_design_qc_auditor",
    "SoundDesignAdapter",
    "get_sound_design_adapter",
    "GOLDEN_BENCHMARK_SCENARIOS",
]






