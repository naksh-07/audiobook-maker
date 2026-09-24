#!/usr/bin/env python3
"""
Audiobook Factory - Literary Intensity Model.
Tracks 7-dimensional intensity vectors and enforces the 'Nothing Above Source' principle.
Note: The ±0.75 threshold is treated as a soft evaluation heuristic (emitting WARN),
reserving hard FAIL only for extreme divergence (> 2.0) like full sanitization or gratuitous inflation.
"""

from typing import Dict, Any, Tuple, List, Optional
from pydantic import BaseModel, Field


class LiteraryIntensityVector(BaseModel):
    profanity: float = Field(default=0.0, ge=0.0, le=5.0)
    sexual_intimacy: float = Field(default=0.0, ge=0.0, le=5.0)
    violence: float = Field(default=0.0, ge=0.0, le=5.0)
    emotional_intensity: float = Field(default=2.0, ge=0.0, le=5.0)
    formality: float = Field(default=2.5, ge=0.0, le=5.0)
    urdu_register: float = Field(default=1.5, ge=0.0, le=5.0)
    colloquiality: float = Field(default=2.0, ge=0.0, le=5.0)


class IntensityEvaluationResult(BaseModel):
    is_valid: bool
    status: str  # PASS, WARN, FAIL
    max_delta: float
    dimension_deltas: Dict[str, float]
    warnings: List[str] = Field(default_factory=list)
    failure_reasons: List[str] = Field(default_factory=list)


class IntensityEvaluator:
    # Heuristic thresholds
    SOFT_HEURISTIC_THRESHOLD = 0.75
    HARD_REJECTION_THRESHOLD = 2.0

    @classmethod
    def compare_vectors(
        cls,
        source_vec: LiteraryIntensityVector,
        target_vec: LiteraryIntensityVector,
    ) -> IntensityEvaluationResult:
        """
        Compares source and target intensity vectors.
        Enforces 'Nothing Above Source' while treating ±0.75 as a soft heuristic.
        """
        source_dict = source_vec.model_dump()
        target_dict = target_vec.model_dump()

        deltas: Dict[str, float] = {}
        warnings: List[str] = []
        failures: List[str] = []

        max_delta = 0.0

        for dim in source_dict.keys():
            s_val = source_dict[dim]
            t_val = target_dict[dim]
            delta = t_val - s_val
            abs_delta = abs(delta)
            deltas[dim] = round(delta, 2)

            if abs_delta > max_delta:
                max_delta = abs_delta

            # Check for hard rejection (> 2.0 divergence)
            if abs_delta > cls.HARD_REJECTION_THRESHOLD:
                if delta < 0:
                    failures.append(
                        f"CRITICAL SANITIZATION on '{dim}': source was {s_val:.1f} but target dropped to {t_val:.1f} (delta: {delta:.2f})"
                    )
                else:
                    failures.append(
                        f"CRITICAL UNJUSTIFIED AMPLIFICATION on '{dim}': source was {s_val:.1f} but target inflated to {t_val:.1f} (delta: {delta:.2f})"
                    )
            # Check for soft warning (0.75 < abs_delta <= 2.0)
            elif abs_delta > cls.SOFT_HEURISTIC_THRESHOLD:
                if delta < 0:
                    warnings.append(
                        f"Mild softening on '{dim}': source {s_val:.1f} -> target {t_val:.1f} (delta: {delta:.2f})"
                    )
                else:
                    warnings.append(
                        f"Mild elevation on '{dim}': source {s_val:.1f} -> target {t_val:.1f} (delta: {delta:.2f})"
                    )

        if failures:
            return IntensityEvaluationResult(
                is_valid=False,
                status="FAIL",
                max_delta=round(max_delta, 2),
                dimension_deltas=deltas,
                warnings=warnings,
                failure_reasons=failures,
            )
        elif warnings:
            return IntensityEvaluationResult(
                is_valid=True,
                status="WARN",
                max_delta=round(max_delta, 2),
                dimension_deltas=deltas,
                warnings=warnings,
                failure_reasons=[],
            )
        else:
            return IntensityEvaluationResult(
                is_valid=True,
                status="PASS",
                max_delta=round(max_delta, 2),
                dimension_deltas=deltas,
                warnings=[],
                failure_reasons=[],
            )
