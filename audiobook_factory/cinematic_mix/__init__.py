#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Architecture:
Scene / Existing Mix Inputs
          ↓
    SceneMixIntent
          ↓
     AttentionMap
          ↓
┌────────────────────────────┐
│ Cinematic Behavior Layer    │
│                            │
│ Acoustic Perspective       │
│ Silence Director           │
│ Impact Director             │
└────────────────────────────┘
          ↓
  Automation Planner
          ↓
Mix Automation Timeline
          ↓
    Dynamic Masking
          ↓
  Stem Interaction
          ↓
 Existing Cinema Audio Engine
          ↓
   Cinematic Mix Premaster
          ↓
    Stage 12 Mastering

Stage 11 determines the cinematic mix. Stage 12 performs mastering.
"""

from audiobook_factory.cinematic_mix.scene_intent import (
    SceneMixIntent,
    FocusTarget,
    DynamicRangePreset,
    SpatialDepthPreset,
    SilenceIntentPreset,
    ImpactIntentPreset,
    ALLOWED_FOCUS_TARGETS,
    DYNAMIC_RANGE_PRESETS,
    SPATIAL_DEPTH_PRESETS,
    SILENCE_INTENT_PRESETS,
    IMPACT_INTENT_PRESETS,
)
from audiobook_factory.cinematic_mix.attention_map import (
    AttentionEvent,
    AttentionMap,
    AttentionCategory,
    infer_attention_category,
)
from audiobook_factory.cinematic_mix.curves import (
    CurveType,
    ALLOWED_CURVES,
    SUPPORTED_CURVES,
    evaluate_curve,
    generate_curve_points,
)
from audiobook_factory.cinematic_mix.automation import (
    StemTarget,
    AutomationParameter,
    AutomationHierarchy,
    AutomationEvent,
    MixAutomation,
    normalize_stem_target,
    SAFETY_LIMIT_MIN_GAIN_DB,
    SAFETY_LIMIT_MAX_GAIN_DB,
    SAFETY_LIMIT_MAX_NOTCH_DB,
)
from audiobook_factory.cinematic_mix.masking import (
    MaskingDecision,
    DynamicMaskingAnalyzer,
    MAX_NOTCH_DEPTH_DB,
    SAFE_DMR_CEILING_DB,
)
from audiobook_factory.cinematic_mix.stem_interaction import (
    StemInteractionPlan,
    StemInteractionEngine,
)
from audiobook_factory.cinematic_mix.perspective import (
    AcousticPerspective,
    PerspectiveDirector,
    DistanceLevel,
    OcclusionLevel,
    DISTANCE_PRESETS,
    OCCLUSION_PRESETS,
)
from audiobook_factory.cinematic_mix.silence import (
    SilenceEvent,
    SilenceDirector,
    SilenceType,
    SilenceDepth,
    SILENCE_DEPTH_DB,
)
from audiobook_factory.cinematic_mix.impact import (
    ImpactEvent,
    ImpactDirector,
    ImpactPhase,
)
from audiobook_factory.cinematic_mix.planner import (
    AutomationPlanner,
)
from audiobook_factory.cinematic_mix.engine_adapter import (
    build_stem_filter_chain,
    apply_automation_to_stem,
)
from audiobook_factory.cinematic_mix.judge import (
    JudgeStatus,
    CategoryStatus,
    CategoryResult,
    MixDiagnosis,
    RemixAction,
    RemixPlan,
    MixJudgeResult,
    MixJudge,
)
from audiobook_factory.cinematic_mix.remix_loop import (
    RemixCycleRecord,
    RemixCycleResult,
    RemixController,
)
from audiobook_factory.cinematic_mix.golden_suite import (
    GoldenScenarioContract,
    GoldenSuiteRunner,
    build_golden_scenarios,
    generate_scenario_audio_fixtures,
)

__all__ = [
    # Scene Intent
    "SceneMixIntent",
    "FocusTarget",
    "DynamicRangePreset",
    "SpatialDepthPreset",
    "SilenceIntentPreset",
    "ImpactIntentPreset",
    "ALLOWED_FOCUS_TARGETS",
    "DYNAMIC_RANGE_PRESETS",
    "SPATIAL_DEPTH_PRESETS",
    "SILENCE_INTENT_PRESETS",
    "IMPACT_INTENT_PRESETS",
    # Attention Map
    "AttentionEvent",
    "AttentionMap",
    "AttentionCategory",
    "infer_attention_category",
    # Curves
    "CurveType",
    "ALLOWED_CURVES",
    "SUPPORTED_CURVES",
    "evaluate_curve",
    "generate_curve_points",
    # Automation
    "StemTarget",
    "AutomationParameter",
    "AutomationHierarchy",
    "AutomationEvent",
    "MixAutomation",
    "normalize_stem_target",
    "SAFETY_LIMIT_MIN_GAIN_DB",
    "SAFETY_LIMIT_MAX_GAIN_DB",
    "SAFETY_LIMIT_MAX_NOTCH_DB",
    # Dynamic Masking
    "MaskingDecision",
    "DynamicMaskingAnalyzer",
    "MAX_NOTCH_DEPTH_DB",
    "SAFE_DMR_CEILING_DB",
    # Stem Interaction
    "StemInteractionPlan",
    "StemInteractionEngine",
    # Acoustic Perspective
    "AcousticPerspective",
    "PerspectiveDirector",
    "DistanceLevel",
    "OcclusionLevel",
    "DISTANCE_PRESETS",
    "OCCLUSION_PRESETS",
    # Silence Director
    "SilenceEvent",
    "SilenceDirector",
    "SilenceType",
    "SilenceDepth",
    "SILENCE_DEPTH_DB",
    # Impact Director
    "ImpactEvent",
    "ImpactDirector",
    "ImpactPhase",
    # Planner
    "AutomationPlanner",
    # Engine Adapter
    "build_stem_filter_chain",
    "apply_automation_to_stem",
    # Judge & Diagnosis
    "JudgeStatus",
    "CategoryStatus",
    "CategoryResult",
    "MixDiagnosis",
    "RemixAction",
    "RemixPlan",
    "MixJudgeResult",
    "MixJudge",
    # Remix Loop
    "RemixCycleRecord",
    "RemixCycleResult",
    "RemixController",
    # Golden Suite
    "GoldenScenarioContract",
    "GoldenSuiteRunner",
    "build_golden_scenarios",
    "generate_scenario_audio_fixtures",
]
