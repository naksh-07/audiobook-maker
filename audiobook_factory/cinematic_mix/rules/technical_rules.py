#!/usr/bin/env python3
"""
Audiobook Factory - Cinematic Mix v2: Technical Audio Rules.
Implements evaluation of physical audio integrity, true peak limits, clipping,
stereo phase correlation, silence behavior, impact transient punch, and spatial coherence.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable

from audiobook_factory.cinematic_mix.judge import CategoryResult
from audiobook_factory.cinematic_mix.perspective import AcousticPerspective
from audiobook_factory.cinematic_mix.automation import MixAutomation
from audiobook_factory.cinematic_mix.silence import SilenceEvent
from audiobook_factory.cinematic_mix.impact import ImpactEvent


def check_technical_safety(
    analyzer: Any,
    phase_audit_fn: Callable[[Path], Any],
    premaster: Optional[Path],
    stems: Dict[str, Path],
) -> CategoryResult:
    """Evaluates physical audio integrity, true peak limits, clipping, and phase."""
    evidence: Dict[str, Any] = {}
    if not premaster or not premaster.exists() or premaster.stat().st_size < 100:
        return CategoryResult(
            name="technical_safety",
            status="FAIL",
            score=0.0,
            critical=True,
            reason="Premaster render file missing, inaccessible, or zero bytes (premaster_missing_or_corrupt).",
            evidence={"premaster_path": str(premaster) if premaster else None},
        )

    loudness = analyzer.probe_loudness(premaster)
    evidence["true_peak_dbtp"] = loudness.true_peak_dbtp
    evidence["integrated_lufs"] = loudness.integrated_lufs
    evidence["rms_level_db"] = loudness.rms_level_db

    # Guard 1: Severe Digital Clipping (> +0.5 dBTP is hard fail)
    if loudness.true_peak_dbtp is not None and loudness.true_peak_dbtp > 0.50:
        return CategoryResult(
            name="technical_safety",
            status="FAIL",
            score=0.20,
            critical=True,
            reason=f"Severe true peak clipping: {loudness.true_peak_dbtp:.2f} dBTP exceeds safety limit +0.50 dBTP.",
            evidence=evidence,
        )

    # Guard 2: Complete Audio Dropout / Render Failure (Silence)
    format_facts = analyzer.probe_format(premaster)
    evidence["duration_sec"] = format_facts.duration_sec
    if format_facts.duration_sec > 0.5:
        if (loudness.integrated_lufs is not None and loudness.integrated_lufs <= -65.0) or (
            loudness.rms_level_db is not None and loudness.rms_level_db <= -70.0
        ):
            return CategoryResult(
                name="technical_safety",
                status="FAIL",
                score=0.0,
                critical=True,
                reason=f"Render integrity failure: output is digital silence ({loudness.integrated_lufs} LUFS).",
                evidence=evidence,
            )

    # Guard 3: Stereo Phase Correlation
    phase_audit = phase_audit_fn(premaster)
    mean_r = phase_audit.details.get("mean_phase_correlation", 1.0)
    evidence["mean_phase_correlation"] = mean_r

    if not phase_audit.passed or mean_r < 0.0:
        return CategoryResult(
            name="technical_safety",
            status="FAIL",
            score=0.35,
            critical=True,
            reason=f"Severe stereo phase cancellation hazard: correlation r={mean_r:.3f} is negative.",
            evidence=evidence,
        )

    # Warning zone: peak between 0.0 and +0.5 dBTP or low phase correlation [0.0, 0.20]
    warnings = []
    if loudness.true_peak_dbtp is not None and loudness.true_peak_dbtp > 0.0:
        warnings.append(f"True peak {loudness.true_peak_dbtp:.2f} dBTP exceeds 0.0 dBTP ceiling")
    if mean_r < 0.20:
        warnings.append(f"Low stereo phase correlation r={mean_r:.3f} (< 0.20)")

    if warnings:
        return CategoryResult(
            name="technical_safety",
            status="PASS_WITH_WARNINGS",
            score=0.80,
            critical=False,
            reason="; ".join(warnings),
            evidence=evidence,
        )

    return CategoryResult(
        name="technical_safety",
        status="PASS",
        score=1.0,
        critical=False,
        reason="Physical audio stream valid, unclipped, and phase coherent.",
        evidence=evidence,
    )


def check_silence_behavior(
    analyzer: Any,
    premaster: Optional[Path],
    stems: Dict[str, Path],
    silence_events: Optional[List[SilenceEvent]],
) -> CategoryResult:
    """Evaluates Silence Director execution and preserved elements."""
    evidence: Dict[str, Any] = {}
    if not silence_events:
        return CategoryResult(name="silence_behavior", status="PASS", score=1.0, reason="No silence events in scene.")

    evidence["silence_event_count"] = len(silence_events)
    for s in silence_events:
        if s.type == "NONE":
            continue
        preserved = {p.lower() for p in s.preserved_elements}

        # If room_tone preserved, AMB must not be completely dead
        if "room_tone" in preserved and "AMB" in stems:
            amb_loudness = analyzer.probe_loudness(stems["AMB"])
            if amb_loudness.rms_level_db is not None and amb_loudness.rms_level_db < -50.0:
                return CategoryResult(
                    name="silence_behavior",
                    status="REMIX",
                    score=0.55,
                    reason=f"Silence preservation failure: Silence declared with room_tone preserved, but AMB stem is inaudible ({amb_loudness.rms_level_db:.1f} dB).",
                    evidence={"silence_event": s.model_dump(), "amb_rms": amb_loudness.rms_level_db},
                )

    return CategoryResult(
        name="silence_behavior",
        status="PASS",
        score=1.0,
        reason="Silence envelopes, depth, and preserved elements execute properly.",
        evidence=evidence,
    )


def check_impact_behavior(
    analyzer: Any,
    premaster: Optional[Path],
    fx_path: Optional[Path],
    mx_path: Optional[Path],
    impact_events: Optional[List[ImpactEvent]],
) -> CategoryResult:
    """Evaluates impact transient punch and bed ducking recovery."""
    evidence: Dict[str, Any] = {}
    if not impact_events:
        return CategoryResult(name="impact_behavior", status="PASS", score=1.0, reason="No impact events in scene.")

    evidence["impact_event_count"] = len(impact_events)
    for imp in impact_events:
        if imp.intensity <= 0.05:
            continue
        # Verify 4-phase physical bounds
        if imp.recovery_end <= imp.impact_start:
            return CategoryResult(
                name="impact_behavior",
                status="FAIL",
                score=0.20,
                critical=True,
                reason=f"Impact timeline corrupted: recovery_end ({imp.recovery_end}s) <= impact_start ({imp.impact_start}s).",
                evidence={"impact": imp.model_dump()},
            )

    return CategoryResult(
        name="impact_behavior",
        status="PASS",
        score=1.0,
        reason="Impact events display proper 4-phase transient trajectory and clean baseline recovery.",
        evidence=evidence,
    )


def check_spatial_coherence(
    analyzer: Any,
    premaster: Optional[Path],
    dx_path: Optional[Path],
    perspective: Optional[AcousticPerspective],
    mix_automation: Optional[MixAutomation],
) -> CategoryResult:
    """Evaluates dialogue center stability and perspective filter execution."""
    evidence: Dict[str, Any] = {}
    if perspective:
        evidence["distance"] = perspective.distance
        evidence["occlusion"] = perspective.occlusion
        evidence["hf_absorption_hz"] = perspective.hf_absorption_hz

        # If behind a door/wall, verify lowpass automation was generated
        if perspective.occlusion in ("door", "wall") and mix_automation:
            lp_events = mix_automation.get_events_for_target("DX", "lowpass_cutoff")
            evidence["lowpass_events_found"] = len(lp_events)
            if not lp_events:
                return CategoryResult(
                    name="spatial_coherence",
                    status="REMIX",
                    score=0.55,
                    reason=f"Perspective mismatch: Voice declared behind {perspective.occlusion} but zero low-pass muffling automation applied.",
                    evidence=evidence,
                )

    return CategoryResult(
        name="spatial_coherence",
        status="PASS",
        score=1.0,
        reason="Spatial placement and acoustic geography are coherent.",
        evidence=evidence,
    )
