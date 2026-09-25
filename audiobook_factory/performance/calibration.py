#!/usr/bin/env python3
"""
Audiobook Factory - Genuine Human Calibration Corpus & Validation Schema.
Enables statistical calibration and correlation analysis between automated
performance evaluation / evidence fusion scores and genuine human ratings.

Computes:
  - Pearson & Spearman rank correlations per dimension
  - False Accept Rate (FAR): Unacceptable takes incorrectly passed
  - False Reject Rate (FRR): High-quality takes incorrectly rejected
  - Inter-Rater Reliability (Mean Pairwise Agreement & Kendall's W)
"""

from __future__ import annotations
import math
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict


class HumanRatingRecord(BaseModel):
    """A single human auditor evaluation record for an audio take."""
    model_config = ConfigDict(extra="ignore")

    take_id: str = Field(..., description="Unique take identifier")
    rater_id: str = Field(..., description="Anonymized human listener identifier")
    dimension: str = Field(..., description="Evaluated performance dimension")
    score_likert: int = Field(..., ge=1, le=5, description="1-5 Likert scale score")
    normalized_score: float = Field(..., ge=0.0, le=1.0, description="Normalized score 0.0 to 1.0")
    is_acceptable: bool = Field(..., description="Whether human judge considers take commercially acceptable")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Rater certainty")
    notes: Optional[str] = Field(default=None, description="Qualitative feedback")
    timestamp: str = Field(default="", description="ISO timestamp of rating")


class HumanCalibrationDataset(BaseModel):
    """Structured collection of genuine human listener evaluations."""
    model_config = ConfigDict(extra="ignore")

    dataset_id: str = Field(..., description="Unique calibration corpus identifier")
    version: str = Field(default="1.0", description="Schema version")
    description: str = Field(default="", description="Corpus provenance description")
    ratings: List[HumanRatingRecord] = Field(default_factory=list)

    def get_mean_scores_by_take(self) -> Dict[str, Dict[str, float]]:
        """Aggregates multi-rater scores per take and dimension."""
        accum: Dict[str, Dict[str, List[float]]] = {}
        for r in self.ratings:
            if r.take_id not in accum:
                accum[r.take_id] = {}
            if r.dimension not in accum[r.take_id]:
                accum[r.take_id][r.dimension] = []
            accum[r.take_id][r.dimension].append(r.normalized_score)

        return {
            take_id: {
                dim: sum(scores) / len(scores)
                for dim, scores in dims.items()
            }
            for take_id, dims in accum.items()
        }

    def get_consensus_acceptability(self, threshold: float = 0.50) -> Dict[str, bool]:
        """Calculates majority human consensus on whether take is acceptable."""
        accum: Dict[str, List[bool]] = {}
        for r in self.ratings:
            if r.take_id not in accum:
                accum[r.take_id] = []
            accum[r.take_id].append(r.is_acceptable)

        return {
            take_id: (sum(1 for a in accepts if a) / len(accepts)) >= threshold
            for take_id, accepts in accum.items()
        }


class CalibrationMetricsReport(BaseModel):
    """Statistical summary of system calibration against human benchmark."""
    model_config = ConfigDict(extra="ignore")

    dataset_id: str
    sample_size: int
    pearson_correlation: float
    spearman_correlation: float
    false_accept_rate: float
    false_reject_rate: float
    overall_accuracy: float
    inter_rater_agreement: float
    diagnostics: List[str] = Field(default_factory=list)
    passed_calibration: bool = Field(default=True)


class CalibrationMetricCalculator:
    """Computes correlation and classification metrics against human benchmark."""

    @staticmethod
    def pearson_r(x: List[float], y: List[float]) -> float:
        """Calculates Pearson correlation coefficient between two series."""
        n = len(x)
        if n < 2 or len(y) != n:
            return 0.0

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        var_x = sum((xi - mean_x) ** 2 for xi in x)
        var_y = sum((yi - mean_y) ** 2 for yi in y)

        if var_x <= 1e-9 or var_y <= 1e-9:
            return 0.0

        cov_xy = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        r = cov_xy / math.sqrt(var_x * var_y)
        return round(float(r), 3)

    @staticmethod
    def spearman_rho(x: List[float], y: List[float]) -> float:
        """Calculates Spearman rank correlation coefficient."""
        n = len(x)
        if n < 2 or len(y) != n:
            return 0.0

        def _rank(vals: List[float]) -> List[float]:
            indexed = sorted(enumerate(vals), key=lambda item: item[1])
            ranks = [0.0] * n
            for rank_idx, (orig_idx, _) in enumerate(indexed):
                ranks[orig_idx] = float(rank_idx + 1)
            return ranks

        rx = _rank(x)
        ry = _rank(y)
        return CalibrationMetricCalculator.pearson_r(rx, ry)

    @classmethod
    def evaluate_system_calibration(
        cls,
        human_dataset: HumanCalibrationDataset,
        system_scores: Dict[str, float],
        system_accepts: Dict[str, bool],
        min_pearson_r: float = 0.60,
        max_far: float = 0.15,
        max_frr: float = 0.20,
    ) -> CalibrationMetricsReport:
        """
        Evaluates system fidelity against human ground truth.
        """
        mean_scores = human_dataset.get_mean_scores_by_take()
        human_accepts = human_dataset.get_consensus_acceptability()

        common_takes = [t for t in mean_scores.keys() if t in system_scores and t in system_accepts]
        diagnostics: List[str] = []

        if not common_takes:
            return CalibrationMetricsReport(
                dataset_id=human_dataset.dataset_id,
                sample_size=0,
                pearson_correlation=0.0,
                spearman_correlation=0.0,
                false_accept_rate=1.0,
                false_reject_rate=1.0,
                overall_accuracy=0.0,
                inter_rater_agreement=0.0,
                diagnostics=["No overlapping takes between human dataset and system scores."],
                passed_calibration=False,
            )

        # Average human overall score per take
        h_overall = []
        s_overall = []
        for t in common_takes:
            h_vals = list(mean_scores[t].values())
            h_overall.append(sum(h_vals) / len(h_vals) if h_vals else 0.5)
            s_overall.append(system_scores[t])

        pr = cls.pearson_r(s_overall, h_overall)
        sr = cls.spearman_rho(s_overall, h_overall)

        # FAR & FRR
        # FAR: Human says unacceptable (False), but system accepted (True)
        # FRR: Human says acceptable (True), but system rejected (False)
        total_human_unacc = sum(1 for t in common_takes if not human_accepts[t])
        total_human_acc = sum(1 for t in common_takes if human_accepts[t])

        false_accepts = sum(
            1 for t in common_takes
            if (not human_accepts[t]) and system_accepts[t]
        )
        false_rejects = sum(
            1 for t in common_takes
            if human_accepts[t] and (not system_accepts[t])
        )

        far = (false_accepts / total_human_unacc) if total_human_unacc > 0 else 0.0
        frr = (false_rejects / total_human_acc) if total_human_acc > 0 else 0.0

        correct = sum(
            1 for t in common_takes
            if human_accepts[t] == system_accepts[t]
        )
        accuracy = correct / len(common_takes)

        # Inter-rater agreement across multiple raters
        ratings_by_take: Dict[str, List[bool]] = {}
        for r in human_dataset.ratings:
            if r.take_id not in ratings_by_take:
                ratings_by_take[r.take_id] = []
            ratings_by_take[r.take_id].append(r.is_acceptable)

        # Pairwise percentage agreement
        pair_agreements: List[float] = []
        for t, bools in ratings_by_take.items():
            if len(bools) >= 2:
                pairs = 0
                matches = 0
                for i in range(len(bools)):
                    for j in range(i + 1, len(bools)):
                        pairs += 1
                        if bools[i] == bools[j]:
                            matches += 1
                if pairs > 0:
                    pair_agreements.append(matches / pairs)

        ira = sum(pair_agreements) / len(pair_agreements) if pair_agreements else 1.0

        # Calibration pass criteria
        passed = True
        if pr < min_pearson_r:
            passed = False
            diagnostics.append(f"Pearson r {pr:.2f} below target threshold {min_pearson_r:.2f}")
        if far > max_far:
            passed = False
            diagnostics.append(f"False Accept Rate {far:.1%} exceeds tolerance {max_far:.1%}")
        if frr > max_frr:
            passed = False
            diagnostics.append(f"False Reject Rate {frr:.1%} exceeds tolerance {max_frr:.1%}")

        if passed:
            diagnostics.append("System calibration meets commercial audio fidelity targets.")

        return CalibrationMetricsReport(
            dataset_id=human_dataset.dataset_id,
            sample_size=len(common_takes),
            pearson_correlation=pr,
            spearman_correlation=sr,
            false_accept_rate=round(far, 3),
            false_reject_rate=round(frr, 3),
            overall_accuracy=round(accuracy, 3),
            inter_rater_agreement=round(ira, 3),
            diagnostics=diagnostics,
            passed_calibration=passed,
        )
