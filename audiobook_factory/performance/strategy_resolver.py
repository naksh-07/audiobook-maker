#!/usr/bin/env python3
"""
Audiobook Factory - Generation Strategy Resolver (Phase 12 & Wave 4).
Selects the optimal synthesis execution strategy per segment:
1. CHUNKED_NARRATION: High-efficiency chunked synthesis for routine narration.
2. MULTI_SPEAKER_BATCH: 2-speaker multiSpeakerVoiceConfig batch synthesis for natural dialogue banter.
3. ISOLATED_SINGLE_TAKE: Isolated single-line synthesis for standard character lines.
4. ISOLATED_MULTI_TAKE: Multi-take candidate banking for elevated dramatic uncertainty.
5. CRITICAL_SCENE_TAKE: Maximum-fidelity multi-take generation for climaxes, screams, and whispers.
Balances acoustic quality with API / cost efficiency.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

from .contracts import PerformanceDirection
from .risk_engine import GenerationRiskEngine, GenerationRiskReport


GenerationStrategy = Literal[
    "CHUNKED_NARRATION",
    "MULTI_SPEAKER_BATCH",
    "ISOLATED_SINGLE_TAKE",
    "ISOLATED_MULTI_TAKE",
    "CRITICAL_SCENE_TAKE",
]


class GenerationStrategyPlan(BaseModel):
    """
    Resolved generation strategy and take banking roadmap for a screenplay segment.
    """
    model_config = ConfigDict(extra="ignore")

    segment_uid: str
    strategy: GenerationStrategy
    recommended_takes: int = Field(default=1, ge=1, le=4)
    target_variants: List[str] = Field(default_factory=lambda: ["standard"])
    rationale: str = ""


class GenerationStrategyResolver:
    """
    Cost-aware, quality-maximizing generation strategy resolver.
    """

    @classmethod
    def resolve_strategy(
        cls,
        direction: PerformanceDirection,
        text: str = "",
        risk_report: Optional[GenerationRiskReport] = None,
        is_multispeaker_eligible: bool = False,
    ) -> GenerationStrategyPlan:
        """
        Calculates the optimal generation strategy and target take variants.
        """
        rep = risk_report or GenerationRiskEngine.calculate_segment_risk(direction, text=text)
        is_narr = direction.speaker in ("Narrator", "Foley") or direction.narrative_mode == "narrator_exposition"

        # 1. Routine Narration
        if is_narr and rep.risk_score < 0.30:
            return GenerationStrategyPlan(
                segment_uid=direction.segment_uid,
                strategy="CHUNKED_NARRATION",
                recommended_takes=1,
                target_variants=["standard"],
                rationale="Routine exposition: chunked single-take synthesis for maximum efficiency",
            )

        # 2. Critical Scene Climax / Fragile Whisper / Screaming Rupture
        if rep.risk_score >= 0.75:
            variants = ["standard"]
            if direction.restraint >= 0.65:
                variants.extend(["more_restrained", "colder"])
            elif direction.intensity == "explosive":
                variants.extend(["exposed", "more_urgent"])
            elif direction.proximity == "close_mic":
                variants.extend(["more_intimate", "more_vulnerable"])
            else:
                variants.extend(["more_vulnerable", "more_urgent"])

            return GenerationStrategyPlan(
                segment_uid=direction.segment_uid,
                strategy="CRITICAL_SCENE_TAKE",
                recommended_takes=len(variants[:3]),
                target_variants=variants[:3],
                rationale=f"Critical dramatic risk ({rep.risk_score:.2f}): multi-take adaptive generation ({', '.join(variants[:3])})",
            )

        # 3. High-Risk Isolated Dialogue
        if rep.risk_score >= 0.50:
            variants = ["standard"]
            if direction.restraint >= 0.60:
                variants.append("more_restrained")
            elif direction.intensity in ("high", "explosive"):
                variants.append("more_urgent")
            else:
                variants.append("more_vulnerable")

            return GenerationStrategyPlan(
                segment_uid=direction.segment_uid,
                strategy="ISOLATED_MULTI_TAKE",
                recommended_takes=len(variants),
                target_variants=variants,
                rationale=f"Elevated dramatic risk ({rep.risk_score:.2f}): dual-take banking ({', '.join(variants)})",
            )

        # 4. Multi-Speaker Batch Dialogue
        if is_multispeaker_eligible and rep.risk_score < 0.45:
            return GenerationStrategyPlan(
                segment_uid=direction.segment_uid,
                strategy="MULTI_SPEAKER_BATCH",
                recommended_takes=1,
                target_variants=["standard"],
                rationale="Standard conversational turn: multiSpeakerVoiceConfig batch synthesis",
            )

        # 5. Standard Isolated Single Line
        return GenerationStrategyPlan(
            segment_uid=direction.segment_uid,
            strategy="ISOLATED_SINGLE_TAKE",
            recommended_takes=1,
            target_variants=["standard"],
            rationale="Standard character line: isolated single-take synthesis",
        )
