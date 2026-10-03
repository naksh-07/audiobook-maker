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
]

# Backward compatibility: include archived modules in package search path
from pathlib import Path
_archive_sd = Path(__file__).resolve().parent.parent.parent / "archive" / "sound_design"
if _archive_sd.exists() and str(_archive_sd) not in __path__:
    __path__.append(str(_archive_sd))







