#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3: Data Contracts & Strictly Typed Schemas (Pydantic v2).
Unified Facade exporting all domain schemas, epistemic models, and contracts.
Guarantees 100% backward compatibility for existing callers and tests.
"""

from __future__ import annotations
from typing import Any

# 1. Base & Shared Literals
from .base import (
    ManifestValidationError,
    ProjectConfig,
    MusicCueType,
    ProvenanceMethod,
)

# 2. Screenplay & Casting (Gate 2)
from .screenplay import (
    CharacterProfile,
    CharacterRoster,
    SceneSource,
    ActingInstructions,
    SpatialCoordinates,
    SegmentMusicParams,
    ScreenplaySegment,
    BatchPlanItem,
    BatchDispatchManifest,
    ScreenplayScript,
)

# 3. Timeline & Synchronized Transcripts (Gate 4.5)
from .timeline import (
    TimelineSegment,
    TimelineLedger,
)

# 4. Sonic Genome & Epistemic Measurement Layers (v2.1)
from .sonic_genome import (
    AcousticMetrics,
    SemanticAnnotations,
    PhysicalGenome,
    TemporalWaveGenome,
    SpatialGenome,
    EnvironmentalGenome,
    DramaticGenome,
    MixCompatibilityGenome,
    MusicIntelligence,
    FoleyIntelligence,
    RemoteAssetMetadata,
    ProvenanceRecord,
    NormalizedSourceFields,
    SourceMetadata,
    FormatFacts,
    LoudnessFacts,
    SpectralFacts,
    TemporalFacts,
    TonalFacts,
    MeasuredAudioFacts,
    AudioEventRecord,
    AgentInterpretation,
    ClassifierPrediction,
    ClassifierInferences,
    SemanticEmbeddingFacts,
    InferredMetadata,
    SonicGenome,
)

# 5. Creative Manifest & Audio Cues (Gates 1 & 2)
from .manifest import (
    MusicCue,
    FoleyCue,
    AmbienceScene,
    MasteringConfig,
    MasteringSettings,
    CreativeManifest,
    LegacyCreativeManifestAdapter,
)

# 6. Macro-Tier Book Master & Album Packaging (Gate 6)
from .album import (
    BookPackagingSpecs,
    BookChapterMarker,
    BookTableOfContents,
    BookVoiceRoster,
    GlobalLoreBible,
    BookMasterManifest,
)

# 7. Performance Realization Re-exports
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

# 8. Sonic Intelligence Re-exports (Optional in Vocals-Only Engine)
try:
    from audiobook_factory.sonic_query_planner import (
        SoundIntentType,
        AtomicSoundConcept,
        AcousticConstraints,
        NegativeConstraints,
        SoundQueryPlan,
    )
    from audiobook_factory.sonic_candidate_generators import (
        CandidateEvidence,
        CandidateRecord,
    )
    from audiobook_factory.sonic_hybrid_reranker import (
        RerankingWeights,
        ScoredCandidate,
    )
    from audiobook_factory.agent_sound_card import (
        AgentSoundCard,
    )
    from audiobook_factory.sonic_intelligence_engine import (
        SoundRetrievalResult,
    )
except ImportError:
    SoundIntentType = Any
    AtomicSoundConcept = Any
    AcousticConstraints = Any
    NegativeConstraints = Any
    SoundQueryPlan = Any
    CandidateEvidence = Any
    CandidateRecord = Any
    RerankingWeights = Any
    ScoredCandidate = Any
    AgentSoundCard = Any
    SoundRetrievalResult = Any

# 9. Mastering V2 Re-exports
from audiobook_factory.mastering_contracts import (
    MasteringProfile,
    MasteringAnalysisFacts,
    MasteringQCResult,
    MasteringIssueSeverity,
    MasteringIssue,
    MasteringActionPlan,
    DialogueProtectionReport,
    BookMasterProfile,
    DimensionDeviation,
    ChapterConsistencyAudit,
    BookConsistencyReport,
    PerceptualDimension,
    PerceptualIssueSeverity,
    PerceptualIssue,
    PerceptualEvaluation,
    ReferenceProfile,
    ReferenceComparisonResult,
    SceneMasteringDecision,
    FinalCertificationReport,
    HumanReviewItem,
    MasteringRequest,
    MasteringResult,
    MasteringLedger,
)

__all__ = [
    # Base
    "ManifestValidationError",
    "ProjectConfig",
    "MusicCueType",
    "ProvenanceMethod",
    # Screenplay
    "CharacterProfile",
    "CharacterRoster",
    "SceneSource",
    "ActingInstructions",
    "SpatialCoordinates",
    "SegmentMusicParams",
    "ScreenplaySegment",
    "BatchPlanItem",
    "BatchDispatchManifest",
    "ScreenplayScript",
    # Timeline
    "TimelineSegment",
    "TimelineLedger",
    # Sonic Genome
    "AcousticMetrics",
    "SemanticAnnotations",
    "PhysicalGenome",
    "TemporalWaveGenome",
    "SpatialGenome",
    "EnvironmentalGenome",
    "DramaticGenome",
    "MixCompatibilityGenome",
    "MusicIntelligence",
    "FoleyIntelligence",
    "RemoteAssetMetadata",
    "ProvenanceRecord",
    "NormalizedSourceFields",
    "SourceMetadata",
    "FormatFacts",
    "LoudnessFacts",
    "SpectralFacts",
    "TemporalFacts",
    "TonalFacts",
    "MeasuredAudioFacts",
    "AudioEventRecord",
    "AgentInterpretation",
    "ClassifierPrediction",
    "ClassifierInferences",
    "SemanticEmbeddingFacts",
    "InferredMetadata",
    "SonicGenome",
    # Manifest
    "MusicCue",
    "FoleyCue",
    "AmbienceScene",
    "MasteringConfig",
    "MasteringSettings",
    "CreativeManifest",
    "LegacyCreativeManifestAdapter",
    # Album
    "BookPackagingSpecs",
    "BookChapterMarker",
    "BookTableOfContents",
    "BookVoiceRoster",
    "GlobalLoreBible",
    "BookMasterManifest",
    # Performance
    "PerformanceDirection",
    "PerformanceProvenanceMode",
    "PerformancePriority",
    "SilenceType",
    "InterruptionBehavior",
    "TurnTakingBehavior",
    "EvaluationDimensionScore",
    "PerformanceEvaluationResult",
    "TakeVariant",
    "PerformanceFidelityReport",
    # Sonic Intelligence
    "SoundIntentType",
    "AtomicSoundConcept",
    "AcousticConstraints",
    "NegativeConstraints",
    "SoundQueryPlan",
    "CandidateEvidence",
    "CandidateRecord",
    "RerankingWeights",
    "ScoredCandidate",
    "AgentSoundCard",
    "SoundRetrievalResult",
    # Mastering
    "MasteringProfile",
    "MasteringAnalysisFacts",
    "MasteringQCResult",
    "MasteringIssueSeverity",
    "MasteringIssue",
    "MasteringActionPlan",
    "DialogueProtectionReport",
    "BookMasterProfile",
    "DimensionDeviation",
    "ChapterConsistencyAudit",
    "BookConsistencyReport",
    "PerceptualDimension",
    "PerceptualIssueSeverity",
    "PerceptualIssue",
    "PerceptualEvaluation",
    "ReferenceProfile",
    "ReferenceComparisonResult",
    "SceneMasteringDecision",
    "FinalCertificationReport",
    "HumanReviewItem",
    "MasteringRequest",
    "MasteringResult",
    "MasteringLedger",
]
