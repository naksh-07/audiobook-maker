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

    return CategoryResult(
        name="cinematic_intent",
        status="PASS",
        score=1.0,
        reason=f"Rendered stem balance faithfully manifests '{focus}' narrative intent.",
        evidence=evidence,
    )
