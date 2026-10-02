#!/usr/bin/env python3
"""
Audiobook Factory - Cinematic Mix v2: Acoustic Rules.
Implements evaluation of dialogue intelligibility (DMR in vocal corridor),
music bed integration/pumping, FX transient punch, ambience continuity, and ducking safety limits.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable

from audiobook_factory.cinematic_mix.judge import CategoryResult
from audiobook_factory.cinematic_mix.scene_intent import SceneMixIntent
from audiobook_factory.cinematic_mix.attention_map import AttentionMap
from audiobook_factory.cinematic_mix.automation import MixAutomation
from audiobook_factory.cinematic_mix.silence import SilenceEvent
from audiobook_factory.cinematic_mix.impact import ImpactEvent


def check_dialogue_focus(
    corridor_measurer: Callable[[Path], float],
    dx_path: Optional[Path],
    mx_path: Optional[Path],
    me_path: Optional[Path],
    scene_intent: Optional[SceneMixIntent],
    attention_map: Optional[AttentionMap],
) -> CategoryResult:
    """Evaluates whether intended dialogue is intelligible and properly foregrounded."""
    evidence: Dict[str, Any] = {}
    if not dx_path or not dx_path.exists():
        return CategoryResult(
            name="dialogue_focus",
            status="PASS",
            score=1.0,
            reason="No dialogue stem present in scene (non-vocal scene).",
            evidence={"dialogue_present": False},
        )

    competing_stem = mx_path if mx_path and mx_path.exists() else me_path
    if not competing_stem or not competing_stem.exists():
        return CategoryResult(
            name="dialogue_focus",
            status="PASS",
            score=1.0,
            reason="Dialogue active with zero competing bed stems.",
            evidence={"competing_stem_present": False},
        )

    # Measure Dialogue-to-Music Ratio (DMR) in vocal corridor (300Hz-3.5kHz)
    dx_corridor_db = corridor_measurer(dx_path)
    mx_corridor_db = corridor_measurer(competing_stem)
    dmr_db = round(dx_corridor_db - mx_corridor_db, 2)

    evidence["measured_dmr_db"] = dmr_db
    evidence["dialogue_corridor_db"] = dx_corridor_db
    evidence["music_corridor_db"] = mx_corridor_db

    # Check narrative intent context
    is_dialogue_focus = True
    is_whisper = False
    if scene_intent:
        if scene_intent.focus not in ("dialogue", "environment"):
            is_dialogue_focus = False
    if attention_map:
        for ev in attention_map.events:
            if any(w in ev.reason.lower() for w in ("whisper", "intimate", "quiet")):
                is_whisper = True
            if ev.focus_target == "music" and ev.priority >= 0.80:
                is_dialogue_focus = False

    # If scene explicitly focuses on music (e.g. dramatic musical score swell), low DMR is allowed
    if not is_dialogue_focus:
        return CategoryResult(
            name="dialogue_focus",
            status="PASS",
            score=0.90,
            reason=f"Scene intentionally focuses on {scene_intent.focus if scene_intent else 'music'}; dialogue is subordinate.",
            evidence=evidence,
        )

    # Whisper speech requires high clarity
    if is_whisper:
        if dmr_db < 6.0:
            return CategoryResult(
                name="dialogue_focus",
                status="REMIX",
                score=0.45,
                reason=f"Whisper dialogue masked: DMR is +{dmr_db:.1f} dB (minimum +6.0 dB required for whisper).",
                evidence=evidence,
            )
    else:
        if dmr_db < 3.0:
            return CategoryResult(
                name="dialogue_focus",
                status="REMIX",
                score=0.50,
                reason=f"Dialogue buried by background bed: DMR +{dmr_db:.1f} dB is below required +3.0 dB floor.",
                evidence=evidence,
            )
        elif dmr_db < 6.0:
            return CategoryResult(
                name="dialogue_focus",
                status="PASS_WITH_WARNINGS",
                score=0.75,
                reason=f"Dialogue presence slightly tight: DMR +{dmr_db:.1f} dB is below standard +6.0 dB.",
                evidence=evidence,
            )

    return CategoryResult(
        name="dialogue_focus",
        status="PASS",
        score=1.0,
        reason=f"Dialogue intelligibility confirmed in vocal corridor (DMR: +{dmr_db:.1f} dB).",
        evidence=evidence,
    )


def check_music_integration(
    analyzer: Any,
    mx_path: Optional[Path],
    dx_path: Optional[Path],
    scene_intent: Optional[SceneMixIntent],
    mix_automation: Optional[MixAutomation],
) -> CategoryResult:
    """Evaluates whether music supports the scene without over-ducking, under-ducking, or pumping."""
    evidence: Dict[str, Any] = {}
    if not mx_path or not mx_path.exists():
        return CategoryResult(
            name="music_integration",
            status="PASS",
            score=1.0,
            reason="No music stem in scene.",
            evidence={"music_present": False},
        )

    mx_loudness = analyzer.probe_loudness(mx_path)
    evidence["music_integrated_lufs"] = mx_loudness.integrated_lufs
    evidence["music_peak_dbtp"] = mx_loudness.true_peak_dbtp

    is_music_focus = bool(scene_intent and scene_intent.focus == "music")

    # 1. Over-ducking check
    if is_music_focus and mx_loudness.integrated_lufs is not None and mx_loudness.integrated_lufs < -40.0:
        return CategoryResult(
            name="music_integration",
            status="REMIX",
            score=0.40,
            reason=f"Music over-ducked: Music was declared scene focus but rendered at {mx_loudness.integrated_lufs:.1f} LUFS.",
            evidence=evidence,
        )

    # 2. Automation pumping / oscillation check
    if mix_automation:
        mx_events = mix_automation.get_events_for_target("MX", "gain")
        evidence["mx_gain_event_count"] = len(mx_events)
        rapid_oscillations = 0
        for i in range(len(mx_events) - 1):
            gap = round(mx_events[i+1].start - mx_events[i].end, 4)
            is_contiguous_phase = bool(
                abs(gap) < 0.001 and (
                    mx_events[i].metadata.get("phase") is not None
                    or any(k in mx_events[i].reason for k in ("Impact", "Silence"))
                )
            )
            if not is_contiguous_phase and 0.0 < gap < 0.20:
                depth = abs(mx_events[i].value - (mx_events[i].start_value or 0.0))
                if depth > 4.0:
                    rapid_oscillations += 1

        evidence["rapid_gain_oscillations"] = rapid_oscillations
        if rapid_oscillations >= 4:
            return CategoryResult(
                name="music_integration",
                status="REMIX",
                score=0.55,
                reason=f"Music fader pumping detected: {rapid_oscillations} rapid gain oscillations without adequate smoothing.",
                evidence=evidence,
            )

    return CategoryResult(
        name="music_integration",
        status="PASS",
        score=1.0,
        reason="Music stem integrates naturally with scene dynamics.",
        evidence=evidence,
    )


def check_fx_clarity(
    analyzer: Any,
    fx_path: Optional[Path],
    impact_events: Optional[List[ImpactEvent]],
    scene_intent: Optional[SceneMixIntent],
) -> CategoryResult:
    """Evaluates whether narrative sound effects and impacts remain clear and unburied."""
    evidence: Dict[str, Any] = {}
    if not fx_path or not fx_path.exists():
        return CategoryResult(
            name="fx_clarity",
            status="PASS",
            score=1.0,
            reason="No discrete FX stem in scene.",
            evidence={"fx_present": False},
        )

    fx_loudness = analyzer.probe_loudness(fx_path)
    evidence["fx_peak_level_db"] = fx_loudness.peak_level_db
    evidence["fx_rms_level_db"] = fx_loudness.rms_level_db

    if impact_events:
        high_impacts = [ev for ev in impact_events if ev.intensity >= 0.60]
        evidence["high_intensity_impact_count"] = len(high_impacts)
        if high_impacts:
            if fx_loudness.peak_level_db is not None and fx_loudness.peak_level_db < -36.0:
                return CategoryResult(
                    name="fx_clarity",
                    status="REMIX",
                    score=0.50,
                    reason=f"Impact transient buried: {len(high_impacts)} major impacts scheduled but FX peak is only {fx_loudness.peak_level_db:.1f} dB.",
                    evidence=evidence,
                )

    return CategoryResult(
        name="fx_clarity",
        status="PASS",
        score=1.0,
        reason="Foley and impact transients are crisp and discernible.",
        evidence=evidence,
    )


def check_ambience_naturalism(
    analyzer: Any,
    amb_path: Optional[Path],
    dx_path: Optional[Path],
    silence_events: Optional[List[SilenceEvent]],
    scene_intent: Optional[SceneMixIntent],
) -> CategoryResult:
    """Enforces the Environmental Naturalism Invariant (ambience never abruptly muted during dialogue)."""
    evidence: Dict[str, Any] = {}
    if not amb_path or not amb_path.exists():
        return CategoryResult(
            name="ambience_naturalism",
            status="PASS",
            score=1.0,
            reason="No discrete ambience bed in scene.",
            evidence={"ambience_present": False},
        )

    amb_loudness = analyzer.probe_loudness(amb_path)
    evidence["ambience_integrated_lufs"] = amb_loudness.integrated_lufs
    evidence["ambience_rms_db"] = amb_loudness.rms_level_db

    has_shock_silence = bool(
        silence_events and any(s.type.upper() == "SHOCK" for s in silence_events)
    )
    if dx_path and dx_path.exists() and not has_shock_silence:
        if amb_loudness.rms_level_db is not None and amb_loudness.rms_level_db < -55.0:
            return CategoryResult(
                name="ambience_naturalism",
                status="REMIX",
                score=0.45,
                reason=f"Environmental naturalism violation: Ambience is sterilized to digital silence ({amb_loudness.rms_level_db:.1f} dB) during dialogue.",
                evidence=evidence,
            )

    return CategoryResult(
        name="ambience_naturalism",
        status="PASS",
        score=1.0,
        reason="Ambient room tone preserved continuously without sterile dropouts.",
        evidence=evidence,
    )


def check_masking_ducking(
    dx_path: Optional[Path],
    mx_path: Optional[Path],
    mix_automation: Optional[MixAutomation],
) -> CategoryResult:
    """Evaluates dynamic masking and sidechain ducking guardrails."""
    evidence: Dict[str, Any] = {}
    if not mix_automation:
        return CategoryResult(name="masking_ducking", status="PASS", score=1.0, reason="No automation events.")

    for e in mix_automation.events:
        if e.parameter == "eq_depth" and e.value < -6.5:
            evidence["violation_event"] = e.model_dump()
            return CategoryResult(
                name="masking_ducking",
                status="REMIX",
                score=0.60,
                reason=f"Masking guardrail violated: Notch depth {e.value:.1f} dB exceeds maximum allowable -6.5 dB ceiling.",
                evidence=evidence,
            )
        if e.parameter in ("gain", "ducking") and (e.value < -36.0 or e.value > 6.0):
            evidence["violation_event"] = e.model_dump()
            return CategoryResult(
                name="masking_ducking",
                status="REMIX",
                score=0.50,
                reason=f"Gain safety limit violated: {e.value:.1f} dB outside [-36.0, +6.0] dB.",
                evidence=evidence,
            )

    return CategoryResult(
        name="masking_ducking",
        status="PASS",
        score=1.0,
        reason="Dynamic masking and ducking parameters comply with studio safety guardrails.",
        evidence=evidence,
    )
