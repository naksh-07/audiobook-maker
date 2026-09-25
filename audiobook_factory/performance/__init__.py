"""
Audiobook Factory - Performance Realization Layer.
Bridges Stage 3 Dramatic Intelligence to Moment-Level Actor Performance,
Multi-Take Synthesis, Dimensional QC, and Pre-Mix Gatekeeper.
"""

from .contracts import (
    PerformanceDirection,
    PerformanceProvenanceMode,
    PerformancePriority,
    SilenceType,
    InterruptionBehavior,
    TurnTakingBehavior,
    PitchBehavior,
    ResonancePlacement,
    VocalTexture,
    BreathBehavior,
    PowerPosition,
    LeverageLevel,
    IntimacyLevel,
    PhysicalStagingState,
    EvaluationDimensionScore,
    PerformanceEvaluationResult,
    ChemistryEvaluationResult,
    TakeVariant,
    TakeSelectionResult,
    TakeSelectorCalibrationConfig,
    PerformanceFidelityReport,
    TakeSelectionStatus,
    EmotionRealizationEvidence,
    IntentRealizationEvidence,
    EmphasisEvidence,
    BreathEvidence,
    PerceptualPerformanceEvidence,
    EvidenceFusionResult,
    EvidenceFusionCalibrationConfig,
    EvaluatorCalibrationConfig,
    PerformanceEvidence,
)
from .timing_realizer import TimingRealizer
from .director import PerformanceDirector
from .tts_adapter import BaseTTSPerformanceAdapter, GeminiTTSPerformanceAdapter
from .evaluator import PerformanceEvaluator
from .take_bank import TakeBank
from .take_selector import IntelligentTakeSelector, PairwiseTakeJudge
from .chemistry import ConversationalChemistry
from .continuity import PerformanceContinuityTracker, CharacterPerformanceTelemetry
from .gate import PerformanceFidelityGate
from .evidence_fusion import EvidenceFusionEngine
from .perceptual_judge import PerceptualPerformanceJudge, PerceptualJudgeConfig

__all__ = [
    "PerformanceDirection",
    "PerformanceProvenanceMode",
    "PerformancePriority",
    "SilenceType",
    "InterruptionBehavior",
    "TurnTakingBehavior",
    "PitchBehavior",
    "ResonancePlacement",
    "VocalTexture",
    "BreathBehavior",
    "PowerPosition",
    "LeverageLevel",
    "IntimacyLevel",
    "PhysicalStagingState",
    "EvaluationDimensionScore",
    "PerformanceEvaluationResult",
    "ChemistryEvaluationResult",
    "TakeVariant",
    "TakeSelectionResult",
    "TakeSelectionStatus",
    "TakeSelectorCalibrationConfig",
    "PerformanceFidelityReport",
    "EmotionRealizationEvidence",
    "IntentRealizationEvidence",
    "EmphasisEvidence",
    "BreathEvidence",
    "PerceptualPerformanceEvidence",
    "EvidenceFusionResult",
    "EvidenceFusionCalibrationConfig",
    "EvaluatorCalibrationConfig",
    "PerformanceEvidence",
    "TimingRealizer",
    "PerformanceDirector",
    "BaseTTSPerformanceAdapter",
    "GeminiTTSPerformanceAdapter",
    "PerformanceEvaluator",
    "TakeBank",
    "IntelligentTakeSelector",
    "PairwiseTakeJudge",
    "ConversationalChemistry",
    "PerformanceContinuityTracker",
    "CharacterPerformanceTelemetry",
    "PerformanceFidelityGate",
    "EvidenceFusionEngine",
    "PerceptualPerformanceJudge",
    "PerceptualJudgeConfig",
]
