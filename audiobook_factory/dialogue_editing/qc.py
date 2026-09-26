#!/usr/bin/env python3
"""
Audiobook Factory - Dialogue Editorial Quality Control & Safety Gate (DE-01 / QC).
Audits editorial decisions to guarantee zero speech truncation, alignment preservation,
and acoustic safety before dialogue is rendered into final stems.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import numpy as np

from audiobook_factory.alignment_contracts import AlignmentResult
from .contracts import DialogueEditPlan, DialogueQCReport, QCDiagnostic, DialogueEditorialConfig


class DialogueEditingQC:
    """
    Dialogue Editing Quality Control Gate.
    Verifies that editorial plans obey speech protection invariants.
    Fails closed on hard boundary violations, triggering fallback to original unedited performance.
    """

    def __init__(self, config: Optional[DialogueEditorialConfig] = None):
        self.config = config or DialogueEditorialConfig()

    def audit_segment_plan(
        self,
        plan: DialogueEditPlan,
        total_audio_ms: int,
        alignment: Optional[AlignmentResult] = None,
        samples: Optional[np.ndarray] = None,
    ) -> List[QCDiagnostic]:
        """
        Audits a single DialogueEditPlan against raw audio duration and word boundaries.

        Returns:
            List of QCDiagnostic (WARNING or HARD_FAILURE).
        """
        diagnostics: List[QCDiagnostic] = []

        # ---------------------------------------------------------------------
        # 1. Hard Boundary Checks (Speech Truncation)
        # ---------------------------------------------------------------------
        # Trim exceeds total file length
        if plan.head_trim_ms + plan.tail_trim_ms >= total_audio_ms:
            diagnostics.append(
                QCDiagnostic(
                    code="TOTAL_DURATION_EXCEEDED",
                    severity="HARD_FAILURE",
                    message=(
                        f"Edit plan trims {plan.head_trim_ms + plan.tail_trim_ms}ms, "
                        f"which completely wipes total audio ({total_audio_ms}ms)."
                    ),
                    segment_uid=plan.segment_uid,
                )
            )

        # Word boundary alignment collision check
        if alignment and alignment.words:
            first_w_start = min(w.start_ms for w in alignment.words)
            last_w_end = max(w.end_ms for w in alignment.words)

            if plan.head_trim_ms > first_w_start:
                diagnostics.append(
                    QCDiagnostic(
                        code="SPEECH_HEAD_TRUNCATION",
                        severity="HARD_FAILURE",
                        message=(
                            f"Head trim ({plan.head_trim_ms}ms) encroaches into first aligned "
                            f"word '{alignment.words[0].token}' starting at {first_w_start}ms."
                        ),
                        segment_uid=plan.segment_uid,
                        evidence={"first_word_start_ms": first_w_start, "head_trim_ms": plan.head_trim_ms},
                    )
                )

            effective_end_ms = total_audio_ms - plan.tail_trim_ms
            if effective_end_ms < last_w_end:
                diagnostics.append(
                    QCDiagnostic(
                        code="SPEECH_TAIL_TRUNCATION",
                        severity="HARD_FAILURE",
                        message=(
                            f"Tail trim leaves {effective_end_ms}ms, which truncates final "
                            f"word '{alignment.words[-1].token}' ending at {last_w_end}ms."
                        ),
                        segment_uid=plan.segment_uid,
                        evidence={"last_word_end_ms": last_w_end, "effective_end_ms": effective_end_ms},
                    )
                )

        # Negative timing
        if plan.pause_after_ms is not None and plan.pause_after_ms < 0:
            diagnostics.append(
                QCDiagnostic(
                    code="NEGATIVE_PAUSE_TIMING",
                    severity="HARD_FAILURE",
                    message=f"Negative pause_after_ms ({plan.pause_after_ms}ms) is invalid.",
                    segment_uid=plan.segment_uid,
                )
            )

        # Clipping and numerical stability audit if samples provided
        if samples is not None and len(samples) > 0:
            if np.isnan(samples).any() or np.isinf(samples).any():
                diagnostics.append(
                    QCDiagnostic(
                        code="NUMERICAL_INSTABILITY_NAN_INF",
                        severity="HARD_FAILURE",
                        message="Audio samples contain NaN or Inf values.",
                        segment_uid=plan.segment_uid,
                    )
                )
            pinned = int(np.sum(np.abs(samples) >= 32760))
            if pinned > 12:
                diagnostics.append(
                    QCDiagnostic(
                        code="SEVERE_CLIPPING_DETECTED",
                        severity="HARD_FAILURE",
                        message=f"Take contains {pinned} rail-pinned samples (>12 allowed).",
                        segment_uid=plan.segment_uid,
                    )
                )
        elif samples is not None and len(samples) == 0:
            diagnostics.append(
                QCDiagnostic(
                    code="EMPTY_AUDIO_SAMPLES",
                    severity="HARD_FAILURE",
                    message="Audio sample buffer is empty or corrupted.",
                    segment_uid=plan.segment_uid,
                )
            )

        # ---------------------------------------------------------------------
        # 2. Editorial Warnings (Non-blocking quality advisory)
        # ---------------------------------------------------------------------
        if plan.head_trim_ms > 800:
            diagnostics.append(
                QCDiagnostic(
                    code="AGGRESSIVE_HEAD_TRIM",
                    severity="WARNING",
                    message=f"Unusually aggressive head trim ({plan.head_trim_ms}ms).",
                    segment_uid=plan.segment_uid,
                )
            )

        if plan.tail_trim_ms > 1000:
            diagnostics.append(
                QCDiagnostic(
                    code="AGGRESSIVE_TAIL_TRIM",
                    severity="WARNING",
                    message=f"Unusually aggressive tail trim ({plan.tail_trim_ms}ms).",
                    segment_uid=plan.segment_uid,
                )
            )

        if plan.pause_after_ms is not None and plan.pause_after_ms > 2500:
            diagnostics.append(
                QCDiagnostic(
                    code="EXCESSIVE_PAUSE_DURATION",
                    severity="WARNING",
                    message=f"Contextual pause ({plan.pause_after_ms}ms) exceeds 2500ms.",
                    segment_uid=plan.segment_uid,
                )
            )

        if plan.pause_after_ms is not None and plan.pause_after_ms < 40 and plan.pause_classification != "INTERRUPTED_TURN":
            diagnostics.append(
                QCDiagnostic(
                    code="UNEXPECTED_SHORT_PAUSE",
                    severity="WARNING",
                    message=f"Pause gap ({plan.pause_after_ms}ms) is abnormally tight for non-interruption turn.",
                    segment_uid=plan.segment_uid,
                )
            )

        if plan.confidence < 0.50:
            diagnostics.append(
                QCDiagnostic(
                    code="LOW_EDITORIAL_CONFIDENCE",
                    severity="WARNING",
                    message=f"Editorial confidence {plan.confidence:.2f} is below 0.50.",
                    segment_uid=plan.segment_uid,
                )
            )

        return diagnostics

    def audit_chapter_plans(
        self,
        chapter_num: int,
        plans: List[DialogueEditPlan],
        segment_durations_ms: List[int],
        alignments: Optional[List[Optional[AlignmentResult]]] = None,
    ) -> DialogueQCReport:
        """
        Audits a chapter's collection of edit plans, checking intra-chapter rhythm and continuity.
        """
        all_warnings: List[QCDiagnostic] = []
        all_hard_failures: List[QCDiagnostic] = []

        breaths_kept = 0
        breaths_reduced = 0
        breaths_removed = 0
        pauses_adjusted = 0

        # Segment-by-segment audit
        for i, plan in enumerate(plans):
            dur_ms = segment_durations_ms[i] if i < len(segment_durations_ms) else 3000
            align = alignments[i] if (alignments and i < len(alignments)) else None

            diags = self.audit_segment_plan(plan, dur_ms, align)
            for d in diags:
                if d.severity == "HARD_FAILURE":
                    all_hard_failures.append(d)
                else:
                    all_warnings.append(d)

            # Check if plan already flagged hard failure during segment planning
            if plan.confidence == 0.0 or any("[HARD_FAILURE]" in d_msg for d_msg in plan.diagnostics):
                if not any(d.segment_uid == plan.segment_uid and d.severity == "HARD_FAILURE" for d in all_hard_failures):
                    all_hard_failures.append(
                        QCDiagnostic(
                            code="PLAN_HARD_FAILURE_RECORDED",
                            severity="HARD_FAILURE",
                            message=f"Plan for segment '{plan.segment_uid}' recorded hard failure: {plan.decision_reason}",
                            segment_uid=plan.segment_uid,
                        )
                    )

            # Breath counters
            if plan.pre_breath_action == "KEEP":
                breaths_kept += 1
            elif plan.pre_breath_action == "REDUCE":
                breaths_reduced += 1
            elif plan.pre_breath_action == "REMOVE":
                breaths_removed += 1

            if plan.post_breath_action == "KEEP":
                breaths_kept += 1
            elif plan.post_breath_action == "REDUCE":
                breaths_reduced += 1
            elif plan.post_breath_action == "REMOVE":
                breaths_removed += 1

            if plan.pause_after_ms is not None:
                pauses_adjusted += 1

        # Rhythm Continuity Audit: Check for robotic metronome pauses (4+ consecutive identical pauses)
        if len(plans) >= 4:
            consecutive_identical = 1
            for i in range(len(plans) - 1):
                p1 = plans[i].pause_after_ms or 0
                p2 = plans[i + 1].pause_after_ms or 0
                if abs(p1 - p2) <= 3 and p1 > 0:
                    consecutive_identical += 1
                    if consecutive_identical >= 4:
                        all_warnings.append(
                            QCDiagnostic(
                                code="REPETITIVE_PAUSE_CADENCE",
                                severity="WARNING",
                                message=(
                                    f"Detected {consecutive_identical} consecutive segments with "
                                    f"identical pause timing ({p1}ms). Rhythm anti-mechanical check suggested."
                                ),
                                segment_uid=plans[i + 1].segment_uid,
                            )
                        )
                        break
                else:
                    consecutive_identical = 1

        passed = len(all_hard_failures) == 0

        return DialogueQCReport(
            chapter_num=chapter_num,
            total_segments=len(plans),
            edited_segments=sum(1 for p in plans if p.head_trim_ms > 0 or p.tail_trim_ms > 0 or p.pre_breath_action != "KEEP" or p.post_breath_action != "KEEP"),
            breaths_kept=breaths_kept,
            breaths_reduced=breaths_reduced,
            breaths_removed=breaths_removed,
            pauses_adjusted=pauses_adjusted,
            warnings=all_warnings,
            hard_failures=all_hard_failures,
            passed=passed,
        )
