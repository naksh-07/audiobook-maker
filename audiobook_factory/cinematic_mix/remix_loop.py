#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Module: remix_loop.py
Implements bounded remix loop orchestration, convergence tracking, and remediation application.

Enforces:
- Hard attempt ceiling (default: max 2 remix iterations / 3 renders total).
- Convergence detection (halts if remediation produces negligible improvement < epsilon).
- Safe parameter transformation back into MixAutomation timeline.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Callable, Tuple, Literal, TYPE_CHECKING
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger
if TYPE_CHECKING:
    from audiobook_factory.cinema_audio_engine import StemLedger
from audiobook_factory.cinematic_mix.scene_intent import SceneMixIntent
from audiobook_factory.cinematic_mix.attention_map import AttentionMap
from audiobook_factory.cinematic_mix.automation import MixAutomation, AutomationEvent
from audiobook_factory.cinematic_mix.perspective import AcousticPerspective
from audiobook_factory.cinematic_mix.silence import SilenceEvent
from audiobook_factory.cinematic_mix.impact import ImpactEvent
from audiobook_factory.cinematic_mix.judge import MixJudge, MixJudgeResult, RemixPlan, RemixAction


class RemixCycleRecord(BaseModel):
    """Snapshot of an individual render & judge attempt."""
    model_config = ConfigDict(extra="ignore")

    attempt: int
    status: str
    overall_score: float
    actions_applied: int
    score_improvement: float = 0.0
    failures: List[str] = Field(default_factory=list)


class RemixCycleResult(BaseModel):
    """Final outcome of a bounded remix loop execution."""
    model_config = ConfigDict(extra="ignore")

    final_result: MixJudgeResult
    total_attempts: int
    converged: bool
    halt_reason: str
    history: List[RemixCycleRecord] = Field(default_factory=list)


class RemixController:
    """
    Orchestrates the bounded remediation cycle between MixJudge and CinemaAudioEngine.
    Guarantees no infinite loops and halts if remixes fail to converge.
    """

    def __init__(
        self,
        judge: Optional[MixJudge] = None,
        max_attempts: int = 2,
        min_improvement_epsilon: float = 0.04,
    ):
        self.judge = judge or MixJudge()
        self.max_attempts = max_attempts
        self.min_improvement_epsilon = min_improvement_epsilon

    def apply_remix_plan(
        self,
        automation: MixAutomation,
        plan: RemixPlan,
    ) -> MixAutomation:
        """
        Applies actionable remediations from RemixPlan into a new cloned MixAutomation.
        Preserves non-destructive decision trace.
        """
        cloned_events = [e.model_copy(deep=True) for e in automation.events]
        decisions = list(automation.decisions)

        for act in plan.actions:
            target_norm = act.target.upper()
            param_norm = act.parameter.lower()

            if act.action_code == "increase_music_ducking":
                # Deepen existing ducking/gain events for MX
                modified = 0
                for e in cloned_events:
                    if e.target == "MX" and e.parameter in ("gain", "ducking"):
                        e.value = round(max(-30.0, e.value - 4.0), 2)
                        modified += 1
                if modified == 0:
                    # Inject ducking event across timeline
                    cloned_events.append(
                        AutomationEvent(
                            start=0.0,
                            end=round(automation.total_duration_sec, 4),
                            target="MX",
                            parameter="ducking",
                            value=act.recommended_value,
                            start_value=0.0,
                            curve="smooth",
                            priority=act.priority,
                            hierarchy="ATTENTION_PROTECTION",
                            reason=f"Remix Remediation: {act.reason}",
                        )
                    )
                decisions.append({
                    "cycle": plan.bounded_iteration,
                    "action": act.action_code,
                    "target": "MX",
                    "adjustment_db": -4.0,
                    "reason": act.reason,
                })

            elif act.action_code == "soften_music_ducking":
                # Soften over-ducked music events
                for e in cloned_events:
                    if e.target == "MX" and e.parameter in ("gain", "ducking"):
                        e.value = round(min(0.0, e.value + 4.0), 2)
                decisions.append({
                    "cycle": plan.bounded_iteration,
                    "action": act.action_code,
                    "target": "MX",
                    "adjustment_db": +4.0,
                    "reason": act.reason,
                })

            elif act.action_code == "preserve_room_tone":
                # Cap excessive ambience ducking to protect room tone
                for e in cloned_events:
                    if e.target == "AMB" and e.parameter in ("gain", "ducking"):
                        e.value = round(max(-5.0, e.value), 2)
                decisions.append({
                    "cycle": plan.bounded_iteration,
                    "action": act.action_code,
                    "target": "AMB",
                    "capped_db": -5.0,
                    "reason": act.reason,
                })

            elif act.action_code == "apply_barrier_lowpass":
                # Ensure lowpass filter is active on DX
                existing_lp = [e for e in cloned_events if e.target == "DX" and e.parameter == "lowpass_cutoff"]
                if existing_lp:
                    for e in existing_lp:
                        e.value = act.recommended_value
                else:
                    cloned_events.append(
                        AutomationEvent(
                            start=0.0,
                            end=round(automation.total_duration_sec, 4),
                            target="DX",
                            parameter="lowpass_cutoff",
                            value=act.recommended_value,
                            start_value=18000.0,
                            curve="smooth",
                            priority=act.priority,
                            hierarchy="CINEMATIC_BEHAVIOR",
                            reason=f"Remix Remediation: {act.reason}",
                        )
                    )
                decisions.append({
                    "cycle": plan.bounded_iteration,
                    "action": act.action_code,
                    "target": "DX",
                    "cutoff_hz": act.recommended_value,
                    "reason": act.reason,
                })

            elif act.action_code == "deepen_impact_ducking":
                # Deepen momentary ducking on competing stems during impacts
                for e in cloned_events:
                    if e.target in ("MX", "AMB") and e.hierarchy in ("MOMENTARY_EVENT", "CINEMATIC_BEHAVIOR"):
                        e.value = round(max(-24.0, e.value - 4.0), 2)
                decisions.append({
                    "cycle": plan.bounded_iteration,
                    "action": act.action_code,
                    "adjustment_db": -4.0,
                    "reason": act.reason,
                })

            elif act.action_code == "deepen_silence_cut":
                # Deepen silence floor events
                for e in cloned_events:
                    if "Silence Director" in e.reason and e.parameter == "gain":
                        e.value = round(max(-32.0, e.value - 6.0), 2)
                decisions.append({
                    "cycle": plan.bounded_iteration,
                    "action": act.action_code,
                    "adjustment_db": -6.0,
                    "reason": act.reason,
                })

        return MixAutomation(
            events=cloned_events,
            total_duration_sec=automation.total_duration_sec,
            scene_id=automation.scene_id,
            chapter_id=automation.chapter_id,
            decision_trace=decisions,
            metadata={
                **automation.metadata,
                "remix_iteration": plan.bounded_iteration,
                "actions_applied": [a.action_code for a in plan.actions],
            },
        )

    def execute_bounded_cycle(
        self,
        render_fn: Callable[[MixAutomation], Tuple[Dict[str, Path], Path]],
        initial_automation: MixAutomation,
        scene_intent: Optional[SceneMixIntent] = None,
        attention_map: Optional[AttentionMap] = None,
        acoustic_perspective: Optional[AcousticPerspective] = None,
        silence_events: Optional[List[SilenceEvent]] = None,
        impact_events: Optional[List[ImpactEvent]] = None,
    ) -> RemixCycleResult:
        """
        Executes bounded render -> judge -> remix loop.
        Guarantees termination within max_attempts.
        """
        current_auto = initial_automation
        history: List[RemixCycleRecord] = []
        prev_score = 0.0

        for attempt in range(1, self.max_attempts + 2):
            # Render audio stems & premaster
            stems, premaster = render_fn(current_auto)

            # Judge rendered result
            res = self.judge.evaluate(
                stems=stems,
                premaster_path=premaster,
                scene_intent=scene_intent,
                attention_map=attention_map,
                mix_automation=current_auto,
                acoustic_perspective=acoustic_perspective,
                silence_events=silence_events,
                impact_events=impact_events,
                iteration=attempt,
            )

            score_delta = round(res.overall_score - prev_score, 3) if attempt > 1 else 0.0
            history.append(
                RemixCycleRecord(
                    attempt=attempt,
                    status=res.status,
                    overall_score=res.overall_score,
                    actions_applied=len(res.remix_plan.actions) if res.remix_plan else 0,
                    score_improvement=score_delta,
                    failures=list(res.failures),
                )
            )

            # 1. Success condition: PASS or PASS_WITH_WARNINGS
            if res.status in ("PASS", "PASS_WITH_WARNINGS"):
                return RemixCycleResult(
                    final_result=res,
                    total_attempts=attempt,
                    converged=True,
                    halt_reason="Mix passed certification.",
                    history=history,
                )

            # 2. Hard Fail condition (technical clipping / corrupted files cannot be fixed by faders)
            if res.status == "FAIL":
                return RemixCycleResult(
                    final_result=res,
                    total_attempts=attempt,
                    converged=False,
                    halt_reason="Hard technical failure encountered; remediation halted.",
                    history=history,
                )

            # 3. Check attempt limit
            if attempt > self.max_attempts:
                return RemixCycleResult(
                    final_result=res,
                    total_attempts=attempt,
                    converged=False,
                    halt_reason=f"Exceeded maximum remediation attempts ({self.max_attempts}).",
                    history=history,
                )

            # 4. Check convergence (if attempt > 1 and improvement is negligible)
            if attempt > 1 and score_delta < self.min_improvement_epsilon:
                return RemixCycleResult(
                    final_result=res,
                    total_attempts=attempt,
                    converged=False,
                    halt_reason=f"Remix cycle failed to converge (score delta {score_delta:.3f} < {self.min_improvement_epsilon}).",
                    history=history,
                )

            # 5. Apply remediation plan to automation for next iteration
            if res.remix_plan and res.remix_plan.actions:
                prev_score = res.overall_score
                current_auto = self.apply_remix_plan(current_auto, res.remix_plan)
            else:
                return RemixCycleResult(
                    final_result=res,
                    total_attempts=attempt,
                    converged=False,
                    halt_reason="Remix status indicated but zero remediation actions generated.",
                    history=history,
                )

        # Fallback termination
        return RemixCycleResult(
            final_result=res,
            total_attempts=self.max_attempts,
            converged=False,
            halt_reason="Remix loop completed maximum iterations.",
            history=history,
        )
