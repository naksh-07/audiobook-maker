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
    PerformanceFidelityReport,
)
from .timing_realizer import TimingRealizer
from .director import PerformanceDirector
from .tts_adapter import BaseTTSPerformanceAdapter, GeminiTTSPerformanceAdapter
from .evaluator import PerformanceEvaluator
from .take_bank import TakeBank
from .take_selector import IntelligentTakeSelector
from .chemistry import ConversationalChemistry
from .continuity import PerformanceContinuityTracker, CharacterPerformanceTelemetry
from .gate import PerformanceFidelityGate

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
    "PerformanceFidelityReport",
    "TimingRealizer",
    "PerformanceDirector",
    "BaseTTSPerformanceAdapter",
    "GeminiTTSPerformanceAdapter",
    "PerformanceEvaluator",
    "TakeBank",
    "IntelligentTakeSelector",
    "ConversationalChemistry",
    "PerformanceContinuityTracker",
    "CharacterPerformanceTelemetry",
    "PerformanceFidelityGate",
]
