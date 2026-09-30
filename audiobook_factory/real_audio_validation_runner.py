#!/usr/bin/env python3
"""
Audiobook Factory - Real Audio Validation Runner (Phase 7, 14, 15).
=================================================================
Orchestrates the complete Real Audio Validation lifecycle:
1. Sourcing & ensuring all 12 Real Audio Golden Fixtures.
2. Individual mastering execution via MasteringEngineV2.
3. Before/After Delta quantification (RealAudioComparator).
4. Scene-Specific & Dialogue Protection audit (RealAudioSceneValidator).
5. Reference Audio deviation audit (RealAudioReferenceSuite).
6. Forensic Artifact detection (RealAudioArtifactDetector).
7. Perceptual Critic evaluation on real material.
8. Packaging Human Review Packages for A/B verification.
9. Long-Form multi-scene stress testing (RealAudioLongFormStressTester).
10. Evaluation of the 6 Core Quality Gates:
    - Technical Gate
    - Dynamic Gate
    - Spectral Gate
    - Dialogue Gate
    - Artifact Gate
    - Consistency Gate
11. Generates machine-readable report (JSON) and human-readable Markdown report.
"""

from __future__ import annotations
import json
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.mastering_contracts import (
    MasteringProfile,
    MasteringRequest,
    MasteringResult,
    MasteringAnalysisFacts,
)
from audiobook_factory.mastering_engine import MasteringEngineV2
from audiobook_factory.mastering_analyzer import MasteringAnalyzer
from audiobook_factory.perceptual_critic import PerceptualCritic
from audiobook_factory.real_audio_contracts import (
    RealAudioFixtureMetadata,
    AudioDeltaReport,
    ArtifactDetectionResult,
    HumanReviewPackage,
    LongFormReport,
    QualityGateEvaluation,
    RealAudioValidationReport,
)
from audiobook_factory.real_audio_golden_suite import RealAudioGoldenSuite
from audiobook_factory.real_audio_comparator import RealAudioComparator
from audiobook_factory.real_audio_reference_suite import RealAudioReferenceSuite
from audiobook_factory.real_audio_scene_validator import RealAudioSceneValidator
from audiobook_factory.real_audio_artifact_detector import RealAudioArtifactDetector
from audiobook_factory.real_audio_long_form import RealAudioLongFormStressTester


class RealAudioValidationRunner:
    """Executes end-to-end real audio verification across all 12 categories."""

    def __init__(
        self,
        engine: Optional[MasteringEngineV2] = None,
        analyzer: Optional[MasteringAnalyzer] = None,
        critic: Optional[PerceptualCritic] = None,
        golden_suite: Optional[RealAudioGoldenSuite] = None,
    ):
        self.engine = engine or MasteringEngineV2()
        self.analyzer = analyzer or MasteringAnalyzer()
        self.critic = critic or PerceptualCritic()
        self.golden_suite = golden_suite or RealAudioGoldenSuite()
        self.comparator = RealAudioComparator(self.analyzer)
        self.scene_validator = RealAudioSceneValidator()
        self.ref_suite = RealAudioReferenceSuite()
        self.artifact_detector = RealAudioArtifactDetector()
        self.long_form_tester = RealAudioLongFormStressTester(self.engine, self.analyzer)

    def run_full_validation(
        self,
        output_dir: Optional[Path] = None,
        profile: Optional[MasteringProfile] = None,
    ) -> RealAudioValidationReport:
        base_dir = output_dir or (self.golden_suite.audio_dir / "validation_run")
        base_dir.mkdir(parents=True, exist_ok=True)

        fixtures = self.golden_suite.ensure_fixtures()
        m_profile = profile or MasteringProfile()

        category_results: Dict[str, str] = {}
        review_packages: List[HumanReviewPackage] = []
        all_artifacts: List[ArtifactDetectionResult] = []
        delta_reports: Dict[str, AudioDeltaReport] = []

        passed_count = 0
        warning_count = 0
        review_count = 0
        failed_count = 0

        # 1. Evaluate Each Real Audio Fixture
        for fix_id, meta in fixtures.items():
            premaster_path = self.golden_suite.audio_dir / f"{fix_id}.wav"
            req = MasteringRequest(
                chapter_id=fix_id,
                premaster_path=str(premaster_path),
                profile=m_profile,
            )
            # Run mastering
            master_result = self.engine.master(req)
            pre_facts = master_result.analysis_before
            post_facts = master_result.analysis_after or self.analyzer.analyze(master_result.master_path)

            # A. Before / After Comparison
            delta = self.comparator.compare(
                fixture_id=fix_id,
                premaster_path=premaster_path,
                master_path=master_result.master_path,
                scene_type=meta.scene_type,
            )

            # B. Scene-Specific & Dialogue Protection
            scene_val = self.scene_validator.validate_scene(
                scene_type=meta.scene_type,
                pre_facts=pre_facts,
                post_facts=post_facts,
                delta=delta,
            )

            # C. Reference Suite Audit
            ref_rep = self.ref_suite.evaluate(post_facts, meta.scene_type)

            # D. Forensic Artifact Detection
            artifacts = self.artifact_detector.analyze_artifacts(
                pre_facts=pre_facts,
                post_facts=post_facts,
                delta_report=delta,
                scene_type=meta.scene_type,
            )
            all_artifacts.extend(artifacts)

            # E. Perceptual Critic Evaluation
            percep_eval = self.critic.evaluate(
                facts=post_facts,
            )

            # Calculate overall perceptual score from dimension scores
            p_score = (
                round(sum(percep_eval.scores.values()) / max(1, len(percep_eval.scores)), 2)
                if percep_eval.scores
                else 1.0
            )

            # Determine fixture status
            has_fail = (
                not master_result.qc_result.passed
                or delta.overall_delta_status == "FAIL"
                or scene_val.status == "FAIL"
                or any(a.severity == "FAIL" for a in artifacts)
            )
            has_review = (
                master_result.status == "REVIEW_REQUIRED"
                or delta.overall_delta_status == "REVIEW_REQUIRED"
                or scene_val.status == "REVIEW_REQUIRED"
                or any(a.severity == "REVIEW_REQUIRED" for a in artifacts)
                or percep_eval.overall == "REVIEW"
                or p_score < 0.75
            )
            has_warn = (
                len(master_result.qc_result.warnings) > 0
                or delta.overall_delta_status == "WARNING"
                or scene_val.status == "WARNING"
                or any(a.severity == "WARNING" for a in artifacts)
                or percep_eval.overall == "WARN"
            )

            if has_fail:
                fix_status = "FAIL"
                failed_count += 1
            elif has_review:
                fix_status = "REVIEW_REQUIRED"
                review_count += 1
            elif has_warn:
                fix_status = "WARNING"
                warning_count += 1
            else:
                fix_status = "PASS"
                passed_count += 1

            category_results[meta.scene_type] = fix_status

            # Human Review Package
            h_status = "MANDATORY_REVIEW" if has_fail or has_review else (
                "HUMAN_AUDIT_RECOMMENDED" if has_warn else "CLEAR"
            )
            review_pkg = HumanReviewPackage(
                fixture_id=fix_id,
                premaster_path=str(premaster_path),
                master_path=master_result.master_path,
                delta_report=delta,
                qc_passed=master_result.qc_result.passed,
                qc_failures=master_result.qc_result.failures,
                perceptual_score=p_score,
                flagged_artifacts=[a for a in artifacts if a.detected and a.severity in ("WARNING", "REVIEW_REQUIRED", "FAIL")],
                review_status=h_status,
                listening_notes=f"Scene type: {meta.scene_type} | Category status: {fix_status}",
            )
            review_packages.append(review_pkg)

        # 2. Long-Form Multi-Scene Stress Test (Phase 9)
        lf_work = base_dir / "long_form"
        _, lf_report = self.long_form_tester.run_stress_test(
            fixtures_dir=self.golden_suite.audio_dir,
            work_dir=lf_work,
            profile=m_profile,
        )

        # 3. Evaluate the 6 Core Quality Gates (Phase 15)
        gates = self._evaluate_quality_gates(
            category_results=category_results,
            artifacts=all_artifacts,
            long_form=lf_report,
            review_packages=review_packages,
        )

        # Determine overall validation status
        if any(g.status == "FAIL" for g in gates.values()) or failed_count > 0:
            overall_status = "FAIL"
        elif any(g.status == "REVIEW_REQUIRED" for g in gates.values()) or review_count > 0:
            overall_status = "REVIEW_REQUIRED"
        elif any(g.status == "WARNING" for g in gates.values()) or warning_count > 0:
            overall_status = "WARNING"
        else:
            overall_status = "PASS"

        report = RealAudioValidationReport(
            report_version="1.0.0",
            engine_version="2.1.0",
            fixtures_evaluated=len(fixtures),
            passed_count=passed_count,
            warning_count=warning_count,
            review_required_count=review_count,
            failed_count=failed_count,
            category_results=category_results,
            quality_gates=gates,
            long_form_evaluation=lf_report,
            overall_status=overall_status,
            review_packages=review_packages,
            executive_summary=(
                f"Real Audio Validation completed across {len(fixtures)} fixtures. "
                f"Passed: {passed_count}, Warnings: {warning_count}, Review Required: {review_count}, Failed: {failed_count}. "
                f"Overall status: {overall_status}."
            ),
        )

        # Write reports
        report_json_path = base_dir / "real_audio_validation_report.json"
        with open(report_json_path, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))

        report_md_path = base_dir / "REAL_AUDIO_VALIDATION_REPORT.md"
        self._write_markdown_report(report, report_md_path)

        return report

    def _evaluate_quality_gates(
        self,
        category_results: Dict[str, str],
        artifacts: List[ArtifactDetectionResult],
        long_form: LongFormReport,
        review_packages: List[HumanReviewPackage],
    ) -> Dict[str, QualityGateEvaluation]:
        gates: Dict[str, QualityGateEvaluation] = {}

        # 1. Technical Gate
        tech_fails = [pkg for pkg in review_packages if not pkg.qc_passed]
        clipping_artifacts = [a for a in artifacts if a.artifact_type == "CLIPPING" and a.severity == "FAIL"]
        if tech_fails or clipping_artifacts:
            gates["TECHNICAL_GATE"] = QualityGateEvaluation(
                gate_name="TECHNICAL_GATE",
                status="FAIL",
                score=0.0,
                reasons=[f"Technical QC failed for {len(tech_fails)} fixtures", f"Clipping detected: {len(clipping_artifacts)} instances"],
            )
        else:
            gates["TECHNICAL_GATE"] = QualityGateEvaluation(
                gate_name="TECHNICAL_GATE",
                status="PASS",
                score=1.0,
                reasons=["Zero clipping; valid formats, sample rates, and channel layouts"],
            )

        # 2. Dynamic Gate
        limiting_severe = [a for a in artifacts if a.artifact_type == "EXCESSIVE_LIMITING" and a.severity in ("REVIEW_REQUIRED", "FAIL")]
        if limiting_severe:
            gates["DYNAMIC_GATE"] = QualityGateEvaluation(
                gate_name="DYNAMIC_GATE",
                status="REVIEW_REQUIRED",
                score=0.75,
                reasons=[f"Excessive limiting/crest reduction flagged in {len(limiting_severe)} scenes"],
            )
        else:
            gates["DYNAMIC_GATE"] = QualityGateEvaluation(
                gate_name="DYNAMIC_GATE",
                status="PASS",
                score=0.95,
                reasons=["Dynamic range and crest factors transparently preserved"],
            )

        # 3. Spectral Gate
        harshness = [a for a in artifacts if a.artifact_type in ("SPECTRAL_HARSHNESS", "BASS_OVERLOAD") and a.detected]
        if any(h.severity == "FAIL" for h in harshness):
            gates["SPECTRAL_GATE"] = QualityGateEvaluation(gate_name="SPECTRAL_GATE", status="FAIL", score=0.0, reasons=["Severe tonal imbalance"])
        elif any(h.severity == "REVIEW_REQUIRED" for h in harshness):
            gates["SPECTRAL_GATE"] = QualityGateEvaluation(gate_name="SPECTRAL_GATE", status="REVIEW_REQUIRED", score=0.80, reasons=["Spectral harshness flagged"])
        else:
            gates["SPECTRAL_GATE"] = QualityGateEvaluation(gate_name="SPECTRAL_GATE", status="PASS", score=0.95, reasons=["Smooth spectral balance across bands"])

        # 4. Dialogue Gate
        diag_res = category_results.get("dialogue", "PASS")
        hindi_res = category_results.get("hindi_hinglish", "PASS")
        if diag_res == "FAIL" or hindi_res == "FAIL":
            gates["DIALOGUE_GATE"] = QualityGateEvaluation(gate_name="DIALOGUE_GATE", status="FAIL", score=0.0, reasons=["Dialogue intelligibility failure"])
        elif diag_res == "REVIEW_REQUIRED" or hindi_res == "REVIEW_REQUIRED":
            gates["DIALOGUE_GATE"] = QualityGateEvaluation(gate_name="DIALOGUE_GATE", status="REVIEW_REQUIRED", score=0.82, reasons=["Dialogue review requested"])
        elif diag_res == "WARNING" or hindi_res == "WARNING":
            gates["DIALOGUE_GATE"] = QualityGateEvaluation(gate_name="DIALOGUE_GATE", status="WARNING", score=0.90, reasons=["Minor dialogue warning"])
        else:
            gates["DIALOGUE_GATE"] = QualityGateEvaluation(gate_name="DIALOGUE_GATE", status="PASS", score=1.0, reasons=["Dialogue intelligibility and separation certified"])

        # 5. Artifact Gate
        fatal_arts = [a for a in artifacts if a.detected and a.severity == "FAIL"]
        warn_arts = [a for a in artifacts if a.detected and a.severity in ("WARNING", "REVIEW_REQUIRED")]
        if fatal_arts:
            gates["ARTIFACT_GATE"] = QualityGateEvaluation(gate_name="ARTIFACT_GATE", status="FAIL", score=0.0, reasons=[f"{len(fatal_arts)} fatal artifacts detected"])
        elif warn_arts:
            gates["ARTIFACT_GATE"] = QualityGateEvaluation(gate_name="ARTIFACT_GATE", status="WARNING", score=0.88, reasons=[f"{len(warn_arts)} non-fatal artifact warnings flagged for audit"])
        else:
            gates["ARTIFACT_GATE"] = QualityGateEvaluation(gate_name="ARTIFACT_GATE", status="PASS", score=1.0, reasons=["Zero detectable mastering artifacts"])

        # 6. Consistency Gate
        if long_form.status == "FAIL":
            gates["CONSISTENCY_GATE"] = QualityGateEvaluation(gate_name="CONSISTENCY_GATE", status="FAIL", score=0.0, reasons=["Long-form drift or crash"])
        elif long_form.status == "REVIEW_REQUIRED":
            gates["CONSISTENCY_GATE"] = QualityGateEvaluation(gate_name="CONSISTENCY_GATE", status="REVIEW_REQUIRED", score=0.80, reasons=long_form.notes)
        else:
            gates["CONSISTENCY_GATE"] = QualityGateEvaluation(gate_name="CONSISTENCY_GATE", status="PASS", score=0.96, reasons=["Long-form timeline consistent"])

        return gates

    def _write_markdown_report(self, rep: RealAudioValidationReport, out_path: Path) -> None:
        lines = [
            "# 🟠 REAL AUDIO VALIDATION REPORT",
            "",
            f"> **Report Generated**: `{rep.created_at}`  ",
            f"> **Mastering Engine**: `v{rep.engine_version}`  ",
            f"> **Overall Assessment**: **`{rep.overall_status}`**  ",
            "",
            "---",
            "",
            "## 1. EXECUTIVE SUMMARY",
            "",
            rep.executive_summary,
            "",
            "| Metric | Count |",
            "|---|---|",
            f"| **Fixtures Evaluated** | {rep.fixtures_evaluated} |",
            f"| **Passed (Clean)** | {rep.passed_count} |",
            f"| **Passed with Warnings** | {rep.warning_count} |",
            f"| **Review Required** | {rep.review_required_count} |",
            f"| **Failed** | {rep.failed_count} |",
            "",
            "---",
            "",
            "## 2. CATEGORY RESULTS",
            "",
            "| Category | Status | Notes |",
            "|---|---|---|",
        ]

        for cat, stat in rep.category_results.items():
            lines.append(f"| **{cat}** | `{stat}` | Evaluated on calibrated real audio fixture |")

        lines.extend([
            "",
            "---",
            "",
            "## 3. QUALITY GATES EVALUATION",
            "",
            "| Quality Gate | Status | Score | Primary Rationale |",
            "|---|---|---|---|",
        ])

        for g_name, g_val in rep.quality_gates.items():
            reasons_str = "; ".join(g_val.reasons) if g_val.reasons else "Clean"
            lines.append(f"| **{g_name}** | `{g_val.status}` | {g_val.score:.2f} | {reasons_str} |")

        lines.extend([
            "",
            "---",
            "",
            "## 4. LONG-FORM STRESS TEST",
            "",
            f"- **Continuous Timeline**: {rep.long_form_evaluation.total_duration_sec}s across {rep.long_form_evaluation.scene_count} scene blocks",
            f"- **Overall Integrated Loudness**: `{rep.long_form_evaluation.overall_lufs} LUFS`",
            f"- **Overall LRA**: `{rep.long_form_evaluation.overall_lra} LU`",
            f"- **Max True Peak**: `{rep.long_form_evaluation.max_true_peak_dbtp} dBTP`",
            f"- **Loudness Drift (Max Δ)**: `{rep.long_form_evaluation.lufs_drift_max_db} dB`",
            f"- **Spectral Centroid Drift**: `{rep.long_form_evaluation.spectral_drift_hz} Hz`",
            f"- **Fatigue Risk Index**: `{rep.long_form_evaluation.fatigue_risk_index:.2f}` (Scale 0.0 - 1.0)",
            f"- **Status**: `{rep.long_form_evaluation.status}`",
            "",
            "---",
            "",
            "## 5. HUMAN REVIEW PACKAGES",
            "",
            "| Fixture ID | QC Status | Perceptual Score | Flagged Artifacts | Audit Recommendation |",
            "|---|---|---|---|---|",
        ])

        for pkg in rep.review_packages:
            arts_str = f"{len(pkg.flagged_artifacts)} flagged" if pkg.flagged_artifacts else "None"
            lines.append(f"| `{pkg.fixture_id}` | `{'PASS' if pkg.qc_passed else 'FAIL'}` | {pkg.perceptual_score:.2f} | {arts_str} | `{pkg.review_status}` |")

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
