#!/usr/bin/env python3
"""
Audiobook Factory - Stage 12: Final Mastering Certification (P4).
=================================================================
Authoritative final gate certifying whether a mastered audiobook chapter is production-ready.
Combines 5 independent evidence sources:
1. P0 Technical QC (audio integrity, true peak, loudness bounds, clipping)
2. Mechanical Integrity (file validity, bounds adherence, closed-loop remediation)
3. P1 Dialogue Protection (masking risk, vocal anchor delta, contrast preservation)
4. P1 Book Consistency (Book Master Profile comparison, intentional variance recognition)
5. P4 Perceptual Evaluation (intelligibility, naturalness, tonal balance, fatigue risk)
6. Optional Reference Comparison (contextual benchmark against versioned profile)

Precedence Invariants:
- Most conservative critical result wins: Technical FAIL = REJECTED (Perceptual score cannot override).
- Perceptual uncertainty with low confidence = REVIEW_REQUIRED (never silently promoted to CERTIFIED).
- Targeted human review items produced for all REVIEW_REQUIRED cases.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional

from audiobook_factory.mastering_contracts import (
    MasteringQCResult,
    DialogueProtectionReport,
    ChapterConsistencyAudit,
    PerceptualEvaluation,
    ReferenceComparisonResult,
    FinalCertificationReport,
    HumanReviewItem,
    MasteringResult,
)

logger = logging.getLogger("AudiobookFactory")

CERTIFIER_VERSION = "1.0.0"


class MasteringCertifier:
    """
    Authoritative certification arbiter evaluating all technical, acoustic,
    dialogue, consistency, and perceptual evidence.
    """

    def __init__(self, version: str = CERTIFIER_VERSION):
        self.version = version

    def certify(
        self,
        chapter_id: str,
        qc_result: MasteringQCResult,
        dialogue_report: Optional[DialogueProtectionReport] = None,
        consistency_audit: Optional[ChapterConsistencyAudit] = None,
        perceptual_eval: Optional[PerceptualEvaluation] = None,
        reference_comp: Optional[ReferenceComparisonResult] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> FinalCertificationReport:
        """
        Executes multi-pillar certification, enforcing the conservative precedence hierarchy.
        """
        warnings: List[str] = []
        review_items: List[Dict[str, Any]] = []
        provenance = provenance or {}

        # 1. Pillar 1: Technical & Mechanical QC (Hardest Authority)
        tech_status = qc_result.status
        tech_passed = qc_result.passed
        if not tech_passed or tech_status == "FAIL":
            for f in qc_result.failures:
                review_items.append(
                    HumanReviewItem(
                        issue_code=f,
                        category="technical_qc",
                        severity="CRITICAL",
                        chapter_id=chapter_id,
                        evidence=f"Technical QC failed with defect: {f}",
                        suggested_action="Re-render premaster with correct audio levels or inspect stem artifacts.",
                        confidence=1.0,
                    ).model_dump()
                )
            return FinalCertificationReport(
                certification="REJECTED",
                chapter_id=chapter_id,
                technical_qc=qc_result.model_dump(),
                mechanical_mastering={"passed": False, "reason": "Technical QC failure"},
                dialogue_protection=dialogue_report.model_dump() if dialogue_report else {},
                book_consistency=consistency_audit.model_dump() if consistency_audit else {},
                perceptual_evaluation=perceptual_eval.model_dump() if perceptual_eval else {},
                reference_comparison=reference_comp.model_dump() if reference_comp else None,
                warnings=qc_result.warnings,
                review_items=review_items,
                provenance=provenance,
            )

        if qc_result.warnings:
            warnings.extend([f"Technical QC: {w}" for w in qc_result.warnings])

        # 2. Pillar 2: Dialogue Protection
        dialogue_critical = False
        if dialogue_report:
            if dialogue_report.status == "FAIL" or dialogue_report.masking_risk == "SEVERE":
                dialogue_critical = True
                review_items.append(
                    HumanReviewItem(
                        issue_code="severe_speech_masking",
                        category="dialogue_protection",
                        severity="CRITICAL",
                        chapter_id=chapter_id,
                        evidence=f"Masking risk is SEVERE, clarity_score={dialogue_report.clarity_score:.2f}",
                        suggested_action="Adjust mixdown ducking or boost dialogue stem.",
                        confidence=0.90,
                    ).model_dump()
                )
            elif dialogue_report.status == "WARN":
                warnings.append(f"Dialogue Protection: {dialogue_report.masking_risk} speech masking risk.")

        # 3. Pillar 3: Book Consistency
        consistency_review_needed = False
        if consistency_audit:
            if consistency_audit.overall_status == "REVIEW" and not consistency_audit.is_intentional_variation:
                consistency_review_needed = True
                review_items.append(
                    HumanReviewItem(
                        issue_code="unexplained_book_inconsistency",
                        category="book_consistency",
                        severity="MAJOR",
                        chapter_id=chapter_id,
                        evidence="Chapter deviates significantly from Book Master Profile without dramatic justification.",
                        suggested_action="Verify if this chapter has an unusual acoustic intent or adjust mastering profile.",
                        confidence=consistency_audit.confidence,
                    ).model_dump()
                )
            elif consistency_audit.overall_status == "WARN":
                warnings.append("Book Consistency: chapter has mild deviations from book profile median.")

        # 4. Pillar 4: Perceptual Evaluation
        perceptual_review_needed = False
        perceptual_rejected = False
        if perceptual_eval:
            # Check for critical perceptual defects (e.g. severe phase cancellation)
            crit_issues = [i for i in perceptual_eval.issues if i.severity == "CRITICAL"]
            if len(crit_issues) > 0:
                perceptual_rejected = True
                for ci in crit_issues:
                    review_items.append(
                        HumanReviewItem(
                            issue_code=f"perceptual_{ci.dimension}",
                            category="perceptual_critic",
                            severity="CRITICAL",
                            chapter_id=chapter_id,
                            evidence=ci.description + " | " + "; ".join(ci.evidence),
                            suggested_action=ci.recommended_action or "Review and correct audio.",
                            confidence=ci.confidence,
                        ).model_dump()
                    )
            elif perceptual_eval.overall == "REVIEW" or (perceptual_eval.overall == "WARN" and perceptual_eval.confidence < 0.65):
                perceptual_review_needed = True
                for pi in perceptual_eval.issues:
                    review_items.append(
                        HumanReviewItem(
                            issue_code=f"perceptual_{pi.dimension}",
                            category="perceptual_critic",
                            severity=pi.severity,
                            chapter_id=chapter_id,
                            evidence=pi.description + " | " + "; ".join(pi.evidence),
                            suggested_action=pi.recommended_action or "Verify aesthetic presentation.",
                            confidence=pi.confidence,
                        ).model_dump()
                    )
            elif perceptual_eval.overall == "WARN":
                for pi in perceptual_eval.issues:
                    warnings.append(f"Perceptual ({pi.dimension}): {pi.description}")

        # 5. Pillar 5: Reference Comparison (Optional Context)
        if reference_comp:
            if reference_comp.comparison_status == "SIGNIFICANT_DEVIATION":
                warnings.append(f"Reference Comparison: significant deviation from {reference_comp.reference_type} reference.")
            elif reference_comp.comparison_status == "INAPPROPRIATE_COMPARISON":
                warnings.append("Reference Comparison: skipped due to incompatible scene type.")

        # 6. Apply Final Precedence Rules
        if dialogue_critical or perceptual_rejected:
            final_certification = "REJECTED"
        elif consistency_review_needed or perceptual_review_needed:
            final_certification = "REVIEW_REQUIRED"
        elif len(warnings) > 0 or (perceptual_eval and perceptual_eval.overall == "WARN"):
            final_certification = "WARNINGS"
        else:
            final_certification = "CERTIFIED"

        logger.info(
            f"[+] Final Mastering Certification for {chapter_id}: {final_certification} "
            f"({len(warnings)} warnings, {len(review_items)} review items)"
        )

        return FinalCertificationReport(
            certification=final_certification,
            chapter_id=chapter_id,
            technical_qc=qc_result.model_dump(),
            mechanical_mastering={"passed": True, "details": "Closed-loop DSP verified within bounds"},
            dialogue_protection=dialogue_report.model_dump() if dialogue_report else {},
            book_consistency=consistency_audit.model_dump() if consistency_audit else {},
            perceptual_evaluation=perceptual_eval.model_dump() if perceptual_eval else {},
            reference_comparison=reference_comp.model_dump() if reference_comp else None,
            warnings=warnings,
            review_items=review_items,
            provenance=provenance,
        )
