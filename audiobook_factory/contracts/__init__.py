#!/usr/bin/env python3
"""
Audiobook Factory - Contracts Package.
Standard: v6.0-ENTERPRISE-DAG
Unified Facade exporting all domain schemas, v6.0 contracts, and legacy backward-compatible models.
"""

from __future__ import annotations
from typing import Any

# =============================================================================
# 1. Base & Shared Literals
# =============================================================================
from .base import (
    ContractBaseModel,
    ManifestValidationError,
    ProjectConfig,
    MusicCueType,
    ProvenanceMethod,
)

# =============================================================================
# 2. v6.0-ENTERPRISE-DAG Core Subsystem Contracts
# =============================================================================
# Room 1: Forensic Ingestion
from .ingestion import (
    RawSentenceRecord,
    RawChapterRecord,
    RawBookManifest,
)

# Room 1/3: Lore & Cast Lock
from .lore import (
    CharacterDossier,
    BookBible,
    CastLock,
)

# Room 2: Translation Collective
from .translation import (
    TranslatedSentenceRecord,
    TranslationBeatRecord,
    TranslationManifest,
)

# Room 3: Screenplay & Anti-Swap Attribution
from .screenplay import (
    SegmentProvenance,
    ScreenplaySegment,
    ScreenplayScript,
    # Legacy compatibility re-exports
    CharacterProfile,
    CharacterRoster,
    SceneSource,
    ActingInstructions,
    SpatialCoordinates,
    SegmentMusicParams,
    BatchPlanItem,
    BatchDispatchManifest,
)

# Room 4: Multi-Cast TTS & Dialogue Editorial
from .editorial import (
    SegmentTakeMetadata,
    TimelineCueRecord,
    TimelineLedger,
    ChapterDialogueManifest,
)

# Room 5: Broadcast Mastering & M4B Packaging
from .mastering import (
    LoudnessComplianceReport,
    MasterArtifact,
    ChapterMarker,
    ContainerM4BManifest,
)

# DAG Ledger & Quality Gate Records
from .ledger import (
    ProjectMetadataRecord,
    ChapterStageRecord,
    StageArtifactRecord,
    SegmentTakeCacheRecord,
    GateAuditRecord,
)

# =============================================================================
# 3. Legacy Models for 100% Backward Compatibility with v5.x components
# =============================================================================
from .timeline import (
    TimelineSegment,
)
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
from .manifest import (
    MusicCue,
    FoleyCue,
    AmbienceScene,
    MasteringConfig,
    MasteringSettings,
    CreativeManifest,
    LegacyCreativeManifestAdapter,
)
from .album import (
    BookPackagingSpecs,
    BookChapterMarker,
    BookTableOfContents,
    BookVoiceRoster,
    GlobalLoreBible,
    BookMasterManifest,
)
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
    # v6.0 Base
    "ContractBaseModel",
    "ManifestValidationError",
    "ProjectConfig",
    "MusicCueType",
    "ProvenanceMethod",

    # v6.0 Ingestion
    "RawSentenceRecord",
    "RawChapterRecord",
    "RawBookManifest",

    # v6.0 Lore & Casting
    "CharacterDossier",
    "BookBible",
    "CastLock",

    # v6.0 Translation
    "TranslatedSentenceRecord",
    "TranslationBeatRecord",
    "TranslationManifest",

    # v6.0 Screenplay
    "SegmentProvenance",
    "ScreenplaySegment",
    "ScreenplayScript",
    "CharacterProfile",
    "CharacterRoster",
    "SceneSource",
    "ActingInstructions",
    "SpatialCoordinates",
    "SegmentMusicParams",
    "BatchPlanItem",
    "BatchDispatchManifest",

    # v6.0 Editorial
    "SegmentTakeMetadata",
    "TimelineCueRecord",
    "TimelineLedger",
    "ChapterDialogueManifest",

    # v6.0 Mastering
    "LoudnessComplianceReport",
    "MasterArtifact",
    "ChapterMarker",
    "ContainerM4BManifest",

    # v6.0 DAG Ledger & Gates
    "ProjectMetadataRecord",
    "ChapterStageRecord",
    "StageArtifactRecord",
    "SegmentTakeCacheRecord",
    "GateAuditRecord",

    # Legacy compatibility
    "TimelineSegment",
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
    "MusicCue",
    "FoleyCue",
    "AmbienceScene",
    "MasteringConfig",
    "MasteringSettings",
    "CreativeManifest",
    "LegacyCreativeManifestAdapter",
    "BookPackagingSpecs",
    "BookChapterMarker",
    "BookTableOfContents",
    "BookVoiceRoster",
    "GlobalLoreBible",
    "BookMasterManifest",
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
