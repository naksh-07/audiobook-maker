#!/usr/bin/env python3
"""
Test Suite: Genuine Human Calibration Corpus Schema & Calibration Harness.
Validates:
1. HumanRatingRecord and HumanCalibrationDataset contracts.
2. Multi-rater consensus and mean score aggregation.
3. Pearson r and Spearman rho correlation calculations.
4. False Accept Rate (FAR) and False Reject Rate (FRR) measurement.
5. Commercial calibration pass and failure detection.
"""

from __future__ import annotations
import pytest
from audiobook_factory.performance.calibration import (
    HumanRatingRecord,
    HumanCalibrationDataset,
    CalibrationMetricCalculator,
    CalibrationMetricsReport,
)


class TestHumanCalibrationSchemaSuite:
    """Test suite for human calibration schema and validation harness."""

    def test_01_human_rating_record_contract(self):
        """Verifies HumanRatingRecord validates fields correctly."""
        rec = HumanRatingRecord(
            take_id="take_001",
            rater_id="rater_auditor_a",
            dimension="acting_believability",
            score_likert=4,
            normalized_score=0.80,
            is_acceptable=True,
            confidence=0.95,
            notes="Natural inflection and convincing delivery",
            timestamp="2026-09-26T00:00:00Z",
        )
        assert rec.take_id == "take_001"
        assert rec.dimension == "acting_believability"
        assert rec.score_likert == 4
        assert rec.normalized_score == 0.80
        assert rec.is_acceptable is True

    def test_02_dataset_aggregation_multi_rater(self):
        """Verifies multi-rater aggregation computes mean scores and consensus acceptability."""
        records = [
            HumanRatingRecord(
                take_id="take_01", rater_id="rater_1", dimension="naturalness",
                score_likert=5, normalized_score=1.0, is_acceptable=True
            ),
            HumanRatingRecord(
                take_id="take_01", rater_id="rater_2", dimension="naturalness",
                score_likert=4, normalized_score=0.8, is_acceptable=True
            ),
            HumanRatingRecord(
                take_id="take_02", rater_id="rater_1", dimension="naturalness",
                score_likert=2, normalized_score=0.4, is_acceptable=False
            ),
            HumanRatingRecord(
                take_id="take_02", rater_id="rater_2", dimension="naturalness",
                score_likert=1, normalized_score=0.2, is_acceptable=False
            ),
        ]
        ds = HumanCalibrationDataset(
            dataset_id="calib_test_v1",
            version="1.0",
            description="Human listening calibration test",
            ratings=records,
        )

        means = ds.get_mean_scores_by_take()
        assert means["take_01"]["naturalness"] == pytest.approx(0.90)
        assert means["take_02"]["naturalness"] == pytest.approx(0.30)

        consensus = ds.get_consensus_acceptability(threshold=0.50)
        assert consensus["take_01"] is True
        assert consensus["take_02"] is False

    def test_03_pearson_and_spearman_calculations(self):
        """Verifies Pearson r and Spearman rho calculations with known series."""
        x = [0.1, 0.3, 0.5, 0.7, 0.9]
        y = [0.15, 0.28, 0.52, 0.68, 0.88]

        pr = CalibrationMetricCalculator.pearson_r(x, y)
        assert pr > 0.98

        sr = CalibrationMetricCalculator.spearman_rho(x, y)
        assert sr == 1.0

    def test_04_calibration_report_clean_pass(self):
        """Verifies system scores well-correlated with human evaluations pass calibration."""
        records = [
            HumanRatingRecord(take_id="t1", rater_id="r1", dimension="acting", score_likert=5, normalized_score=0.95, is_acceptable=True),
            HumanRatingRecord(take_id="t2", rater_id="r1", dimension="acting", score_likert=4, normalized_score=0.82, is_acceptable=True),
            HumanRatingRecord(take_id="t3", rater_id="r1", dimension="acting", score_likert=4, normalized_score=0.78, is_acceptable=True),
            HumanRatingRecord(take_id="t4", rater_id="r1", dimension="acting", score_likert=2, normalized_score=0.40, is_acceptable=False),
            HumanRatingRecord(take_id="t5", rater_id="r1", dimension="acting", score_likert=1, normalized_score=0.20, is_acceptable=False),
        ]
        ds = HumanCalibrationDataset(dataset_id="test_pass", ratings=records)

        system_scores = {"t1": 0.92, "t2": 0.85, "t3": 0.75, "t4": 0.45, "t5": 0.25}
        system_accepts = {"t1": True, "t2": True, "t3": True, "t4": False, "t5": False}

        report = CalibrationMetricCalculator.evaluate_system_calibration(
            human_dataset=ds,
            system_scores=system_scores,
            system_accepts=system_accepts,
            min_pearson_r=0.70,
            max_far=0.10,
            max_frr=0.10,
        )

        assert report.passed_calibration is True
        assert report.pearson_correlation >= 0.90
        assert report.false_accept_rate == 0.0
        assert report.false_reject_rate == 0.0
        assert report.overall_accuracy == 1.0
        assert any("meets commercial audio fidelity targets" in d for d in report.diagnostics)

    def test_05_calibration_report_detects_false_accepts(self):
        """Verifies system with high False Accept Rate fails calibration."""
        records = [
            HumanRatingRecord(take_id="t1", rater_id="r1", dimension="acting", score_likert=1, normalized_score=0.20, is_acceptable=False),
            HumanRatingRecord(take_id="t2", rater_id="r1", dimension="acting", score_likert=1, normalized_score=0.20, is_acceptable=False),
        ]
        ds = HumanCalibrationDataset(dataset_id="test_fail_far", ratings=records)

        # System incorrectly accepted defective takes
        system_scores = {"t1": 0.85, "t2": 0.80}
        system_accepts = {"t1": True, "t2": True}

        report = CalibrationMetricCalculator.evaluate_system_calibration(
            human_dataset=ds,
            system_scores=system_scores,
            system_accepts=system_accepts,
            max_far=0.10,
        )

        assert report.passed_calibration is False
        assert report.false_accept_rate == 1.0
        assert any("False Accept Rate" in d for d in report.diagnostics)
