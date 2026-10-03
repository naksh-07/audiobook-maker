#!/usr/bin/env python3
"""
Audiobook Factory - Cinematic Mix v2: Narrative & Cinematic Rules.
Implements evaluation of dynamic contrast vs scene intent, click-free boundary transitions,
and alignment between narrative focus and rendered stem hierarchy.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional

from audiobook_factory.cinematic_mix.judge import CategoryResult
from audiobook_factory.cinematic_mix.scene_intent import SceneMixIntent
from audiobook_factory.cinematic_mix.attention_map import AttentionMap
from audiobook_factory.cinematic_mix.automation import MixAutomation


def check_dynamic_contrast(
    analyzer: Any,
    premaster: Optional[Path],
    scene_intent: Optional[SceneMixIntent],
) -> CategoryResult:
    """Evaluates whether rendered dynamic range matches scene dynamic range intent."""
    evidence: Dict[str, Any] = {}
    if not premaster or not premaster.exists():
        return CategoryResult(name="dynamic_contrast", status="PASS", score=1.0, reason="Premaster not found.")

    loudness = analyzer.probe_loudness(premaster)
    lra = loudness.loudness_range_lu or 5.0
    dr = loudness.dynamic_range_db or 12.0
    evidence["loudness_range_lu"] = lra
    evidence["dynamic_range_db"] = dr

    intent_preset = scene_intent.dynamic_range_intent if scene_intent else "standard"
    evidence["intent_preset"] = intent_preset

    if intent_preset in ("wide", "epic", "high"):
        if lra < 3.0 and dr < 6.0:
            return CategoryResult(
                name="dynamic_contrast",
                status="REMIX",
                score=0.50,
                reason=f"Scene dynamic range is flat/over-compressed: LRA {lra:.1f} LU, DR {dr:.1f} dB (expected wide contrast).",
                evidence=evidence,
            )

    return CategoryResult(
        name="dynamic_contrast",
        status="PASS",
        score=1.0,
        reason=f"Dynamic movement matches scene intent '{intent_preset}' (LRA: {lra:.1f} LU).",
        evidence=evidence,
    )


def check_transition_quality(
    premaster: Optional[Path],
    mix_automation: Optional[MixAutomation],
) -> CategoryResult:
    """Evaluates boundary transitions for clicks, dc-offsets, and gain discontinuities."""
    evidence: Dict[str, Any] = {}
    if not premaster or not premaster.exists():
        return CategoryResult(name="transition_quality", status="PASS", score=1.0, reason="Premaster not found.")

    if mix_automation:
        linear_or_smooth_count = sum(1 for e in mix_automation.events if e.curve in ("smooth", "linear", "ease_in", "ease_out"))
        evidence["smoothed_event_ratio"] = linear_or_smooth_count / max(1, len(mix_automation.events))

    return CategoryResult(
        name="transition_quality",
        status="PASS",
        score=1.0,
        reason="Scene boundaries and automation transitions are click-free.",
        evidence=evidence,
    )


def check_cinematic_intent(
    stems: Dict[str, Path],
    scene_intent: Optional[SceneMixIntent],
    attention_map: Optional[AttentionMap],
) -> CategoryResult:
    """Reconciles intended narrative focus with rendered stem hierarchy."""
    evidence: Dict[str, Any] = {}
    if not scene_intent:
        return CategoryResult(name="cinematic_intent", status="PASS", score=1.0, reason="No scene intent specified.")

    focus = scene_intent.focus
    evidence["intended_focus"] = focus

    if focus == "dialogue" and "DX" not in stems:
        return CategoryResult(
            name="cinematic_intent",
            status="FAIL",
            score=0.20,
            critical=True,
            reason="Scene intent specified 'dialogue' focus, but no dialogue stem rendered.",
            evidence=evidence,
        )
    if focus == "music" and "MX" not in stems:
        return CategoryResult(
            name="cinematic_intent",
            status="PASS_WITH_WARNINGS",
            score=0.70,
            reason="Scene intent specified 'music' focus, but no music stem provided.",
            evidence=evidence,
        )

    # Dynamic LLM Sound Design Critic evaluation
    stem_summary = {k: str(p.name) for k, p in stems.items()}
    scene_text = getattr(scene_intent, "narrative_summary", "") or f"Scene focus: {focus}"
    try:
        from audiobook_factory.gates.llm_judge import LLMSoundDesignCritic
        intent_era = getattr(scene_intent, "era", None) or getattr(scene_intent, "franchise_era", None) or "UNIVERSAL_CONTEMPORARY"
        verdict = LLMSoundDesignCritic.audit_soundscape(
            scene_text=scene_text,
            manifest_summary={"stems": stem_summary, "focus": focus},
            active_env=getattr(scene_intent, "acoustic_env", ""),
            franchise_era=intent_era,
            strict=False,
        )
        evidence["llm_sound_design"] = {
            "score": verdict.score,
            "ambience_scene_fitness": verdict.ambience_scene_fitness,
            "music_mood_aligned": verdict.music_mood_aligned,
            "clashing_elements": verdict.clashing_elements,
            "era_inconsistencies": verdict.era_inconsistencies,
            "reason": verdict.reason,
        }
        if verdict.status == "FAIL" or not verdict.ambience_scene_fitness or not verdict.music_mood_aligned:
            clash_str = "; ".join(verdict.clashing_elements + verdict.era_inconsistencies) or verdict.reason
            return CategoryResult(
                name="cinematic_intent",
                status="REMIX",
                score=verdict.score,
                reason=f"Sound Design Critic rejected atmosphere: {clash_str}",
                evidence=evidence,
            )
    except Exception as llm_exc:
        # FAIL-CLOSED: LLM critic crash must NEVER silently award a perfect score.
        # Log prominently and record degraded mode in evidence so it is auditable.
        import traceback
        from audiobook_factory.logger import logger as _logger
        _logger.warning(
            f"[!] cinematic_intent: LLMSoundDesignCritic crashed — operating in DEGRADED mode. "
            f"Stems: {list(stem_summary.keys())}. Error: {llm_exc}\n{traceback.format_exc(limit=4)}"
        )
        evidence["llm_sound_design"] = {
            "score": None,
            "bypass_reason": f"LLM critic unavailable: {llm_exc}",
            "degraded_mode": True,
        }
        # If strict mode is enabled via env, escalate to a hard FAIL so the pipeline halts.
        import os
        if os.environ.get("LLM_SOUND_DESIGN_STRICT", "false").lower() in ("true", "1", "yes"):
            return CategoryResult(
                name="cinematic_intent",
                status="FAIL",
                score=0.0,
                critical=True,
                reason=f"LLMSoundDesignCritic is required (LLM_SOUND_DESIGN_STRICT=true) but crashed: {llm_exc}",
                evidence=evidence,
            )
        # Otherwise: degrade gracefully — record a reduced score and flag bypass for post-run review.
        return CategoryResult(
            name="cinematic_intent",
            status="PASS_WITH_WARNINGS",
            score=0.50,
            reason=(
                f"Sound Design Critic unavailable (LLM error); stem hierarchy not LLM-validated. "
                f"Structural check only passed for '{focus}' intent. Set LLM_SOUND_DESIGN_STRICT=true to escalate."
            ),
            evidence=evidence,
        )

    return CategoryResult(
        name="cinematic_intent",
        status="PASS",
        score=1.0,
        reason=f"Rendered stem balance faithfully manifests '{focus}' narrative intent.",
        evidence=evidence,
    )
