#!/usr/bin/env python3
"""
Audiobook Factory - Generation Risk Engine (Phase 11 & Wave 3).
Calculates per-segment acoustic and dramatic generation risk: R in [0.0, 1.0].
Evaluates emotional intensity, whispering, shouting, crying, laughter, rapid dialogue,
foreign names, interruptions, physical strain, and conflicting subtext.
Dynamically sets candidate take count policy to optimize both quality and API cost.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from .contracts import PerformanceDirection


class GenerationRiskReport(BaseModel):
    """
    Detailed generation risk breakdown for a screenplay segment.
    """
    model_config = ConfigDict(extra="ignore")

    segment_uid: str
    risk_score: float = Field(..., ge=0.0, le=1.0)
    recommended_takes: int = Field(default=1, ge=1, le=4)
    risk_tier: str = Field(default="low", description="low, medium, elevated, critical")
    risk_factors: List[str] = Field(default_factory=list)
    suggested_strategy: str = Field(default="standard")


class GenerationRiskEngine:
    """
    Per-segment generation risk calculator.
    Prevents generating redundant takes on low-risk exposition while allocating
    multi-take banking to dramatic climaxes, whispers, and emotional ruptures.
    """

    @classmethod
    def calculate_segment_risk(
        cls,
        direction: PerformanceDirection,
        text: str = "",
        pronunciation_flags: Optional[List[str]] = None,
    ) -> GenerationRiskReport:
        """
        Computes composite risk score and take allocation for a segment.
        """
        factors: List[str] = []
        raw_score = 0.0

        # Narration is inherently lower risk
        is_narration = direction.speaker in ("Narrator", "Foley") or direction.narrative_mode == "narrator_exposition"
        if is_narration:
            raw_score = 0.05
        else:
            raw_score = 0.15  # Dialogue base risk

        # 1. Emotional Intensity
        if direction.intensity == "explosive":
            raw_score += 0.35
            factors.append("Explosive emotional intensity")
        elif direction.intensity == "high":
            raw_score += 0.20
            factors.append("High emotional headroom")

        # 2. Whisper & Proximity Sensitivity
        text_lower = text.lower()
        if direction.proximity == "close_mic" or direction.intimacy_level == "intimate" or "[whisper" in text_lower:
            raw_score += 0.25
            factors.append("Intimate whisper close-mic delivery")

        # 3. Extreme Physical Delivery (Shout, Cry, Laugh)
        if "[shout" in text_lower or "[screaming" in text_lower or "rage" in direction.surface_emotion.lower():
            raw_score += 0.30
            factors.append("Shout / scream acoustic strain")
        if "[crying" in text_lower or "[weeping" in text_lower or "crying" in direction.surface_emotion.lower() or "sobbing" in direction.surface_emotion.lower():
            raw_score += 0.30
            factors.append("Crying / weeping phonation fragility")
        if "[laugh" in text_lower or "chuckle" in text_lower:
            raw_score += 0.20
            factors.append("Laughter syncopation")

        # 4. Rapid Dialogue Pace
        if direction.pace > 1.20:
            raw_score += 0.15
            factors.append(f"Accelerated pacing ({direction.pace:.2f}x)")
        elif direction.pace < 0.80:
            raw_score += 0.10
            factors.append(f"Unusually slow measured pacing ({direction.pace:.2f}x)")

        # 5. Conversational Interruptions
        if direction.interruption_behavior in ("abrupt_cut", "overlap_start"):
            raw_score += 0.20
            factors.append(f"Turn-taking dynamic: {direction.interruption_behavior}")

        # 6. Physical Staging Strain
        if direction.physical_state in ("wounded", "exhausted", "combat_strain"):
            raw_score += 0.20
            factors.append(f"Physical condition: {direction.physical_state}")

        # 7. Conflicting Subtext & Social Mask
        if direction.social_mask and direction.subtext_confidence >= 0.70:
            raw_score += 0.15
            factors.append("Complex subtextual social mask")

        # 8. Director Performance Priority Elevation
        if direction.performance_priority == "climactic":
            raw_score += 0.40
            factors.append("Climactic scene performance priority")
        elif direction.performance_priority == "high":
            raw_score += 0.25
            factors.append("Elevated dramatic priority")
        elif direction.performance_priority == "focused":
            raw_score += 0.15
            factors.append("Focused dramatic priority")

        # 9. Pronunciation & Loanword Complexity
        if pronunciation_flags and len(pronunciation_flags) > 0:
            raw_score += 0.15
            factors.append(f"Pronunciation alert: {len(pronunciation_flags)} flagged tokens")

        composite_risk = round(max(0.0, min(1.0, raw_score)), 2)

        # Policy Mapping: Risk -> Required Takes
        if composite_risk < 0.25:
            tier = "low"
            takes = 1
            strategy = "chunked_or_single"
        elif composite_risk < 0.50:
            tier = "medium"
            takes = 2
            strategy = "focused_dual_take"
        elif composite_risk < 0.75:
            tier = "elevated"
            takes = 3
            strategy = "isolated_multi_take"
        else:
            tier = "critical"
            takes = 3
            strategy = "critical_scene_ensemble"

        return GenerationRiskReport(
            segment_uid=direction.segment_uid,
            risk_score=composite_risk,
            recommended_takes=takes,
            risk_tier=tier,
            risk_factors=factors,
            suggested_strategy=strategy,
        )
