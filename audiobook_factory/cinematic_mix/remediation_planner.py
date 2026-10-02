#!/usr/bin/env python3
"""
Audiobook Factory - Cinematic Mix v2: Remediation Planner.
Maps judging category failures and REMIX verdicts into structured diagnoses
and concrete parameter remediation actions for the next mix render iteration.
"""

from __future__ import annotations
from typing import Tuple, Optional

# Note: Imported conditionally or lazily to avoid circular imports
from audiobook_factory.cinematic_mix.judge import CategoryResult, MixDiagnosis, RemixAction


def map_category_to_remediation(
    cat: CategoryResult,
) -> Tuple[MixDiagnosis, Optional[RemixAction]]:
    """Maps an individual category REMIX into a structured diagnosis and actionable RemixAction."""
    if cat.name == "dialogue_focus":
        return (
            MixDiagnosis(
                category="dialogue_focus",
                status="REMIX",
                reason="insufficient_dialogue_protection",
                evidence=cat.evidence,
                likely_cause="Background music or effects bed is masking vocal speech frequencies.",
                recommended_action="Increase sidechain ducking depth on MX and apply -5.5 dB spectral notch at 2400 Hz.",
            ),
            RemixAction(
                target="MX",
                parameter="ducking",
                current_value=0.0,
                recommended_value=-8.0,
                action_code="increase_music_ducking",
                reason="Deepen music bed attenuation to restore dialogue intelligibility",
                priority=0.90,
            ),
        )

    elif cat.name == "music_integration":
        return (
            MixDiagnosis(
                category="music_integration",
                status="REMIX",
                reason="music_over_ducked",
                evidence=cat.evidence,
                likely_cause="Ducking envelope is excessively deep or gain transitions are pumping.",
                recommended_action="Soften music ducking depth by +4.0 dB and lengthen release curve.",
            ),
            RemixAction(
                target="MX",
                parameter="gain",
                current_value=-24.0,
                recommended_value=-16.0,
                action_code="soften_music_ducking",
                reason="Restore musical body and emotional thematic presence",
                priority=0.85,
            ),
        )

    elif cat.name == "ambience_naturalism":
        return (
            MixDiagnosis(
                category="ambience_naturalism",
                status="REMIX",
                reason="ambience_sterilized",
                evidence=cat.evidence,
                likely_cause="Ambience stem is being completely muted during dialogue.",
                recommended_action="Cap ambience ducking to maximum -3.5 dB to preserve room tone continuity.",
            ),
            RemixAction(
                target="AMB",
                parameter="gain",
                current_value=-24.0,
                recommended_value=-3.5,
                action_code="preserve_room_tone",
                reason="Maintain environmental naturalism invariant across speech intervals",
                priority=0.80,
            ),
        )

    elif cat.name == "fx_clarity":
        return (
            MixDiagnosis(
                category="fx_clarity",
                status="REMIX",
                reason="impact_transient_buried",
                evidence=cat.evidence,
                likely_cause="High-energy sound effect or combat impact was masked by music.",
                recommended_action="Deepen temporary music ducking during impact transient window.",
            ),
            RemixAction(
                target="MX",
                parameter="ducking",
                current_value=-4.0,
                recommended_value=-12.0,
                action_code="deepen_impact_ducking",
                reason="Create acoustic space for visceral impact transient slam",
                priority=0.88,
            ),
        )

    elif cat.name == "spatial_coherence":
        return (
            MixDiagnosis(
                category="spatial_coherence",
                status="REMIX",
                reason="perspective_mismatch",
                evidence=cat.evidence,
                likely_cause="Acoustic occlusion or distance requested but low-pass filtering omitted.",
                recommended_action="Inject dynamic low-pass filter at 2200 Hz for door or 1100 Hz for wall.",
            ),
            RemixAction(
                target="DX",
                parameter="lowpass_cutoff",
                current_value=20000.0,
                recommended_value=2200.0,
                action_code="apply_barrier_lowpass",
                reason="Simulate physical barrier transmission and high-frequency absorption",
                priority=0.85,
            ),
        )

    elif cat.name == "silence_behavior":
        return (
            MixDiagnosis(
                category="silence_behavior",
                status="REMIX",
                reason="silence_ineffective",
                evidence=cat.evidence,
                likely_cause="Silence floor too shallow or wrong stems preserved.",
                recommended_action="Deepen music cut to -20 dB while preserving room tone on AMB.",
            ),
            RemixAction(
                target="MX",
                parameter="gain",
                current_value=-8.0,
                recommended_value=-20.0,
                action_code="deepen_silence_cut",
                reason="Punctuate narrative dramatic pause with intentional negative sound design",
                priority=0.86,
            ),
        )

    # Default fallback diagnosis
    return (
        MixDiagnosis(
            category=cat.name,
            status="REMIX",
            reason="cinematic_remediation_needed",
            evidence=cat.evidence,
            likely_cause=cat.reason,
            recommended_action="Review and adjust mixing automation curves.",
        ),
        None,
    )
