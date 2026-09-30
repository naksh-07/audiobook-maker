#!/usr/bin/env python3
"""
Audiobook Factory - Stage 12: Chapter Consistency Auditor & Reporter.
=====================================================================
Audits chapter-to-chapter acoustic coherence against the project's BookMasterProfile.

Critical Architectural Invariant:
- DEVIATION != ERROR: The auditor strictly distinguishes intentional dramatic variation
  (whispers, epic battles, suspenseful silence) from accidental engineering inconsistencies.
- Context-driven: Considers SceneMixIntent and dramatic intensity to validate deviations.
- Produces machine-readable ChapterConsistencyAudit and comprehensive BookConsistencyReport.
"""

from __future__ import annotations
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

from audiobook_factory.logger import logger
from audiobook_factory.mastering_contracts import (
    MasteringAnalysisFacts,
    BookMasterProfile,
    DimensionDeviation,
    ChapterConsistencyAudit,
    BookConsistencyReport,
)


class ChapterConsistencyAuditor:
    """
    Audits a single mastered chapter against the BookMasterProfile across 5 core dimensions:
    Loudness, Dynamics, Tonal Spectrum, Dialogue Anchor, and Stereo Phase.
    """

    def __init__(self, default_tolerance_lu: float = 0.8):
        self.default_tolerance_lu = default_tolerance_lu

    def audit_chapter(
        self,
        chapter_facts: MasteringAnalysisFacts,
        book_profile: BookMasterProfile,
        dialogue_facts: Optional[MasteringAnalysisFacts] = None,
        scene_intent: Optional[Any] = None,
        chapter_id: str = "ch_unknown",
    ) -> ChapterConsistencyAudit:
        """
        Compares chapter facts against book profile, classifying deviations as
        intentional dramatic variation or accidental engineering drift.
        """
        deviations: Dict[str, DimensionDeviation] = {}

        # 1. Detect Intentional Context from SceneMixIntent
        intent_category: Optional[str] = None
        is_combat = False
        is_whisper = False
        is_silence = False

        if scene_intent:
            raw_intent = str(getattr(scene_intent, "scene_type", "") or getattr(scene_intent, "intent", "")).lower()
            if any(w in raw_intent for w in ("combat", "action", "battle", "explosive", "shouting")):
                is_combat = True
                intent_category = "combat_action"
            elif any(w in raw_intent for w in ("whisper", "intimate", "quiet", "secret")):
                is_whisper = True
                intent_category = "whisper_intimate"
            elif any(w in raw_intent for w in ("silence", "tension", "suspense", "pause")):
                is_silence = True
                intent_category = "dramatic_silence"

        # 2. Dimension 1: Integrated Loudness
        measured_lufs = chapter_facts.integrated_lufs
        exp_lufs = book_profile.target_lufs_median
        delta_lufs = round(measured_lufs - exp_lufs, 2)
        tol_lufs = max(self.default_tolerance_lu, book_profile.target_lufs_iqr * 1.5)

        if abs(delta_lufs) <= tol_lufs:
            dev_status = "PASS"
            is_int = False
            rat = None
        else:
            if is_whisper and delta_lufs < 0:
                dev_status = "PASS"
                is_int = True
                rat = f"Intimate scene intentionally quieter ({measured_lufs:.1f} LUFS vs profile {exp_lufs:.1f} LUFS)."
            elif is_combat and delta_lufs > 0:
                dev_status = "PASS"
                is_int = True
                rat = f"High-energy combat scene intentionally louder ({measured_lufs:.1f} LUFS vs profile {exp_lufs:.1f} LUFS)."
            else:
                dev_status = "FAIL" if abs(delta_lufs) > tol_lufs * 2.0 else "WARN"
                is_int = False
                rat = f"Unintended loudness deviation: {delta_lufs:+.2f} LU from book median."

        deviations["loudness"] = DimensionDeviation(
            metric="integrated_loudness",
            measured_value=measured_lufs,
            expected_value=exp_lufs,
            delta=delta_lufs,
            tolerance=tol_lufs,
            status=dev_status,
            is_intentional=is_int,
            rationale=rat,
        )

        # 3. Dimension 2: Dynamics (Crest Factor & LRA)
        crest = chapter_facts.crest_factor_db or 8.0
        exp_crest = book_profile.crest_factor_median_db
        delta_crest = round(crest - exp_crest, 2)
        tol_crest = 2.5

        if abs(delta_crest) <= tol_crest:
            dev_status = "PASS"
            is_int = False
            rat = None
        else:
            if (is_combat or is_silence) and delta_crest > 0:
                dev_status = "PASS"
                is_int = True
                rat = f"Dynamic dramatic scene intentionally has wide crest factor ({crest:.1f} dB)."
            else:
                dev_status = "WARN"
                is_int = False
                rat = f"Dynamics deviation: crest factor is {delta_crest:+.1f} dB from book profile."

        deviations["dynamics"] = DimensionDeviation(
            metric="crest_factor",
            measured_value=crest,
            expected_value=exp_crest,
            delta=delta_crest,
            tolerance=tol_crest,
            status=dev_status,
            is_intentional=is_int,
            rationale=rat,
        )

        # 4. Dimension 3: Tonal Spectrum (Spectral Centroid)
        centroid = chapter_facts.spectral_centroid_hz or 1200.0
        exp_centroid = book_profile.spectral_centroid_median_hz
        delta_centroid = round(centroid - exp_centroid, 1)
        tol_centroid = 400.0

        if abs(delta_centroid) <= tol_centroid:
            dev_status = "PASS"
            is_int = False
            rat = None
        else:
            if is_combat and delta_centroid > 0:
                dev_status = "PASS"
                is_int = True
                rat = "Combat clash features elevated high-frequency metallic transients."
            elif is_whisper and delta_centroid < 0:
                dev_status = "PASS"
                is_int = True
                rat = "Whisper features warmer low-end proximity effect."
            else:
                dev_status = "WARN"
                is_int = False
                rat = f"Spectral tilt deviation: {delta_centroid:+.1f} Hz from book profile."

        deviations["tonal"] = DimensionDeviation(
            metric="spectral_centroid",
            measured_value=centroid,
            expected_value=exp_centroid,
            delta=delta_centroid,
            tolerance=tol_centroid,
            status=dev_status,
            is_intentional=is_int,
            rationale=rat,
        )

        # 5. Dimension 4: Dialogue Anchor Ratio
        if dialogue_facts and dialogue_facts.integrated_lufs > -65.0:
            anchor = round(dialogue_facts.integrated_lufs - measured_lufs, 2)
            exp_anchor = book_profile.dialogue_anchor_median_db
            delta_anchor = round(anchor - exp_anchor, 2)
            tol_anchor = 2.5

            if abs(delta_anchor) <= tol_anchor:
                dev_status = "PASS"
                is_int = False
                rat = None
            else:
                if is_whisper and delta_anchor < 0:
                    dev_status = "PASS"
                    is_int = True
                    rat = "Whisper scene intentional lower vocal presence."
                else:
                    dev_status = "FAIL" if delta_anchor < -tol_anchor * 1.5 else "WARN"
                    is_int = False
                    rat = f"Dialogue balance drift: {delta_anchor:+.1f} dB from book median."

            deviations["dialogue"] = DimensionDeviation(
                metric="dialogue_anchor_ratio",
                measured_value=anchor,
                expected_value=exp_anchor,
                delta=delta_anchor,
                tolerance=tol_anchor,
                status=dev_status,
                is_intentional=is_int,
                rationale=rat,
            )

        # 6. Dimension 5: Stereo Phase Correlation
        phase = chapter_facts.phase_correlation
        exp_phase = book_profile.phase_correlation_median
        delta_phase = round(phase - exp_phase, 3)
        tol_phase = 0.20

        if phase >= 0.20 and abs(delta_phase) <= tol_phase:
            dev_status = "PASS"
            is_int = False
            rat = None
        else:
            dev_status = "FAIL" if phase < 0.0 else "WARN"
            is_int = False
            rat = f"Stereo phase drift: r={phase:.2f} (profile median: {exp_phase:.2f})."

        deviations["stereo"] = DimensionDeviation(
            metric="stereo_phase",
            measured_value=phase,
            expected_value=exp_phase,
            delta=delta_phase,
            tolerance=tol_phase,
            status=dev_status,
            is_intentional=is_int,
            rationale=rat,
        )

        # 7. Aggregate Overall Chapter Status and Review Priority
        has_fail = any(d.status == "FAIL" for d in deviations.values())
        has_warn = any(d.status == "WARN" for d in deviations.values())
        any_intentional = any(d.is_intentional for d in deviations.values())

        if has_fail:
            overall_status = "REVIEW"
            review_priority = "HIGH"
        elif has_warn:
            overall_status = "WARN"
            review_priority = "MEDIUM"
        else:
            overall_status = "PASS"
            review_priority = "NONE"

        return ChapterConsistencyAudit(
            chapter_id=chapter_id,
            overall_status=overall_status,
            deviations=deviations,
            is_intentional_variation=any_intentional,
            intentional_intent=intent_category,
            confidence=book_profile.confidence,
            review_priority=review_priority,
            details={
                "book_profile_version": book_profile.version,
                "sample_count": book_profile.sample_count,
            },
        )


class BookConsistencyReportBuilder:
    """
    Assembles multiple ChapterConsistencyAudits into a book-level report.
    Produces both structured JSON and human-readable Markdown summaries.
    """

    def build_report(
        self,
        book_id: str,
        chapter_audits: Dict[str, ChapterConsistencyAudit],
        book_profile: BookMasterProfile,
    ) -> BookConsistencyReport:
        total = len(chapter_audits)
        passed = sum(1 for a in chapter_audits.values() if a.overall_status == "PASS")
        warn = sum(1 for a in chapter_audits.values() if a.overall_status == "WARN")
        review = sum(1 for a in chapter_audits.values() if a.overall_status == "REVIEW")

        # Generate ASCII / Markdown Summary Table
        md_lines = [
            f"# BOOK CONSISTENCY AUDIT REPORT: {book_id}",
            f"**Book Profile Version**: {book_profile.version} (Confidence: {book_profile.confidence * 100:.0f}%)",
            f"**Total Chapters**: {total} | **PASS**: {passed} | **WARN**: {warn} | **REVIEW**: {review}",
            "",
            "| Chapter | Status | Priority | Intentional? | Primary Deviations |",
            "| :--- | :---: | :---: | :---: | :--- |",
        ]

        for ch_id, audit in sorted(chapter_audits.items()):
            dev_summaries = []
            for dim_name, dev in audit.deviations.items():
                if dev.status != "PASS":
                    dev_summaries.append(f"{dim_name} ({dev.delta:+.1f})")
                elif dev.is_intentional:
                    dev_summaries.append(f"{dim_name} [intentional]")

            dev_text = ", ".join(dev_summaries) if dev_summaries else "All within tolerance"
            int_flag = f"Yes ({audit.intentional_intent})" if audit.is_intentional_variation else "No"
            md_lines.append(
                f"| **{ch_id}** | `{audit.overall_status}` | {audit.review_priority} | {int_flag} | {dev_text} |"
            )

        markdown_summary = "\n".join(md_lines)

        return BookConsistencyReport(
            book_id=book_id,
            profile_version=book_profile.version,
            total_chapters=total,
            passed_count=passed,
            warn_count=warn,
            review_count=review,
            chapter_audits=chapter_audits,
            summary_markdown=markdown_summary,
        )
