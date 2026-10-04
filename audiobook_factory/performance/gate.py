#!/usr/bin/env python3
"""
Audiobook Factory - Gate 2.8: Pre-Mix Performance Fidelity Gate.
Validates actor direction completeness, anti-emotional teleportation compliance,
take evaluation scores, and explainable selection provenance before dialogue stems
are locked and handed over to CinemaAudioEngine.
"""

from __future__ import annotations
import os
import datetime
from typing import List, Dict

from audiobook_factory.logger import logger
from .contracts import (
    PerformanceDirection,
    TakeVariant,
    PerformanceFidelityReport,
)


class PerformanceFidelityGate:
    """
    Gate 2.8: Pre-Mix Independent Performance Fidelity Validator.
    Fails closed if bad acting, ungrounded emotional teleportation, or unverified takes
    attempt to enter the cinematic audio mastering chain.
    """

    VOLATILE_TRANSITIONS = {
        ("calm", "bellowing_rage"),
        ("peaceful", "explosive"),
        ("gentle_tender", "bellowing_battlecry"),
        ("whispering", "bellowing_rage"),
        ("calm", "rage"),
    }

    @classmethod
    def audit_chapter_performance(
        cls,
        chapter_id: str,
        directions: List[PerformanceDirection],
        selected_takes: List[TakeVariant],
        allow_warnings: bool = True,
    ) -> PerformanceFidelityReport:
        """
        Audits performance directions and selected takes for a chapter.
        """
        issues: List[str] = []
        teleportation_violations = 0

        if not directions:
            return PerformanceFidelityReport(
                chapter_id=chapter_id,
                passed=False,
                total_segments=0,
                total_takes_generated=0,
                avg_evaluation_score=0.0,
                dimension_averages={},
                teleportation_violations=1,
                unresolved_issues=["No performance directions found for chapter"],
                created_at=datetime.datetime.now().isoformat(),
            )

        # 1. Anti-Emotional Teleportation Audit
        for i in range(1, len(directions)):
            prev = directions[i - 1]
            curr = directions[i]
            if prev.speaker == curr.speaker and prev.speaker not in ("Narrator", "Foley"):
                p_emo = prev.surface_emotion.lower()
                c_emo = curr.surface_emotion.lower()
                if (p_emo, c_emo) in cls.VOLATILE_TRANSITIONS:
                    teleportation_violations += 1
                    issues.append(
                        f"Emotional Teleportation Violation at segment {curr.index} ({curr.speaker}): "
                        f"abrupt shift from '{p_emo}' to '{c_emo}' without transitional grounding."
                    )

        # 2. Selected Take Evaluation & Quality Audit
        eval_scores: List[float] = []
        dim_accum: Dict[str, List[float]] = {}
        critical_defects: List[str] = []

        take_by_seg = {t.segment_uid: t for t in selected_takes if t.is_selected}
        unselected_by_seg = {t.segment_uid: t for t in selected_takes if not t.is_selected}

        for d in directions:
            # Action beats / Foley cues don't generate spoken vocal takes
            if d.speaker == "Foley":
                continue
            take = take_by_seg.get(d.segment_uid)
            if not take:
                unselected = unselected_by_seg.get(d.segment_uid)
                if unselected:
                    sel_res = getattr(unselected, "selection_result", None)
                    status_str = getattr(sel_res, "status", "NO_ACCEPTABLE_TAKE") if sel_res else "NO_ACCEPTABLE_TAKE"
                    msg = (
                        f"Segment {d.index} ({d.speaker}): Critical defect - NO ACCEPTABLE TAKE selected "
                        f"(status: {status_str}, take_id: {unselected.take_id})."
                    )
                    issues.append(msg)
                    critical_defects.append(f"[CRITICAL] {msg}")
                else:
                    msg = f"Segment {d.index} ({d.speaker}): No selected take found in take registry."
                    issues.append(msg)
                    critical_defects.append(f"[CRITICAL] {msg}")
                continue

            ev = take.evaluation
            if ev:
                eval_scores.append(ev.overall_score)
                for dim_name, dim_val in ev.dimensions.items():
                    if dim_name not in dim_accum:
                        dim_accum[dim_name] = []
                    dim_accum[dim_name].append(dim_val.score)

                if ev.overall_score < 0.65:
                    msg = f"Take {take.take_id} score ({ev.overall_score:.2f}) below critical threshold (0.65)."
                    issues.append(msg)
                    critical_defects.append(f"[CRITICAL] {msg}")
                if ev.voice_drift_detected:
                    msg = f"Take {take.take_id} ({d.speaker}): Voice drift detected against reference acoustic signature."
                    issues.append(msg)
                    is_catastrophic = getattr(ev.evidence.voice_identity, "is_hard_gate_violation", False) if (ev.evidence and ev.evidence.voice_identity) else False
                    if is_catastrophic:
                        critical_defects.append(f"[CRITICAL] Catastrophic voice drift on take {take.take_id} ({d.speaker})")
                if not take.selection_reason:
                    issues.append(f"Take {take.take_id} lacks explainable selection rationale.")

            # Audit selection result and evidence fusion status
            if getattr(take, "selection_result", None) is not None:
                sel_res = take.selection_result
                sel_status = getattr(sel_res, "status", "")
                if sel_status == "NO_ACCEPTABLE_TAKE":
                    msg = f"Take {take.take_id} ({d.speaker}): Critical defect - NO ACCEPTABLE TAKE available."
                    issues.append(msg)
                    critical_defects.append(f"[CRITICAL] {msg}")
                elif sel_status == "REGENERATE":
                    msg = f"Take {take.take_id} ({d.speaker}): Take marked for regeneration."
                    issues.append(msg)
                    critical_defects.append(f"[CRITICAL] {msg}")
                fusion = getattr(sel_res, "fusion_result", None)
                if fusion and getattr(fusion, "hard_gate_reasons", []):
                    for hgr in fusion.hard_gate_reasons:
                        msg = f"Take {take.take_id} ({d.speaker}): Hard gate defect - {hgr}"
                        issues.append(msg)
                        critical_defects.append(f"[CRITICAL] {msg}")

        avg_score = float(sum(eval_scores) / len(eval_scores)) if eval_scores else 0.0
        dim_averages = {
            k: round(float(sum(v) / len(v)), 2)
            for k, v in dim_accum.items()
        }

        # Gate decision: Fail closed if ANY critical defect exists, regardless of allow_warnings
        has_critical = len(critical_defects) > 0
        is_mock = os.environ.get("MOCK_OFFLINE", "").lower() in ("true", "1", "yes")
        has_valid_eval = (len(eval_scores) > 0 and avg_score >= 0.70) or (is_mock and not eval_scores)
        passed = (
            (not has_critical)
            and (teleportation_violations == 0)
            and has_valid_eval
            and (len(issues) == 0 or allow_warnings)
        )

        if not eval_scores and not is_mock:
            passed = False
            critical_defects.append("[CRITICAL] Zero performance evaluation scores recorded for chapter takes")

        # Critical fails: teleportation or missing takes
        if teleportation_violations > 0:
            passed = False
            critical_defects.append(f"[CRITICAL] Chapter has {teleportation_violations} emotional teleportation violations")
        if len(take_by_seg) < len(directions) * 0.95 and selected_takes:
            passed = False
            critical_defects.append(f"[CRITICAL] Incomplete segment coverage: {len(take_by_seg)}/{len(directions)} segments selected")

        all_unresolved = critical_defects + [i for i in issues if f"[CRITICAL] {i}" not in critical_defects]

        report = PerformanceFidelityReport(
            chapter_id=chapter_id,
            passed=passed,
            total_segments=len(directions),
            total_takes_generated=len(selected_takes),
            avg_evaluation_score=round(avg_score, 2),
            dimension_averages=dim_averages,
            teleportation_violations=teleportation_violations,
            unresolved_issues=all_unresolved,
            created_at=datetime.datetime.now().isoformat(),
        )

        status_str = "PASSED" if passed else "FAILED"
        logger.info(
            f"[*] Gate 2.8 Performance Fidelity: {status_str} for {chapter_id} "
            f"(Avg Score: {avg_score:.2f}, Violations: {teleportation_violations}, Issues: {len(issues)})"
        )
        return report
