#!/usr/bin/env python3
"""
Audiobook Factory - Stage 12: Mastering V2 Forensic Mastering Judge.
=====================================================================
Evaluates physical acoustic evidence probed by MasteringAnalyzer and generates
structured, prioritized, and strictly bounded corrective action plans.

Core Principles:
- Evidence-driven: Every issue is backed by measurable facts from MasteringAnalysisFacts.
- Priority-ranked: Audio integrity > Dialogue intelligibility > Harshness > Dynamics > Loudness.
- Confidence-calibrated: High confidence triggers bounded correction; low confidence reports only.
- Safety-bounded: Cannot bypass deterministic DSP bounds or invent arbitrary parameters.
- Separation of concerns: Judge decides and recommends; MasteringEngineV2 executes DSP.
"""

from __future__ import annotations
import math
from typing import Dict, Any, List, Optional, Tuple, Union

from audiobook_factory.logger import logger
from audiobook_factory.mastering_contracts import (
    MasteringProfile,
    MasteringAnalysisFacts,
    MasteringIssue,
    MasteringIssueSeverity,
    MasteringActionPlan,
    BookMasterProfile,
)


# Bounded DSP Safety Envelopes for Judge Recommendations
SAFETY_BOUNDS = {
    "target_lufs_min": -24.0,
    "target_lufs_max": -16.0,
    "max_lufs_shift": 1.5,
    "limiter_ceiling_min": -3.5,
    "limiter_ceiling_max": -1.0,
    "max_limiter_shift": 0.8,
    "subsonic_hz_min": 20,
    "subsonic_hz_max": 45,
    "max_subsonic_shift": 12,
    "target_lra_min": 5.0,
    "target_lra_max": 12.0,
}


class MasteringJudge:
    """
    Deterministic rule-based forensic mastering judge.
    Inspects physical analyzer facts and formulates bounded corrective action plans.
    """

    def __init__(self, version: str = "2.1.0"):
        self.version = version

    def evaluate(
        self,
        premaster_facts: MasteringAnalysisFacts,
        dialogue_facts: Optional[MasteringAnalysisFacts] = None,
        profile: Optional[MasteringProfile] = None,
        book_profile: Optional[BookMasterProfile] = None,
        scene_intent: Optional[Any] = None,
        chapter_id: str = "ch_unknown",
    ) -> MasteringActionPlan:
        """
        Evaluates premaster analysis facts, dialogue relationship, and scene intent.
        Produces a prioritized MasteringActionPlan with bounded profile overrides.
        """
        prof = profile or MasteringProfile()
        issues: List[MasteringIssue] = []

        # 1. PRIORITY 1: Audio Integrity & Critical Technical Defects
        if not premaster_facts.is_valid_audio or premaster_facts.duration_sec <= 0.0:
            issues.append(
                MasteringIssue(
                    issue_type="corrupt_audio_integrity",
                    severity="CRITICAL",
                    confidence=1.0,
                    evidence={"duration_sec": premaster_facts.duration_sec, "is_valid": premaster_facts.is_valid_audio},
                    recommended_action="Halt mastering pipeline; regenerate audio stems from stage 11.",
                    bounded_parameters={},
                )
            )

        if premaster_facts.clipping_detected or (premaster_facts.true_peak_dbtp and premaster_facts.true_peak_dbtp > 0.0):
            issues.append(
                MasteringIssue(
                    issue_type="severe_digital_clipping",
                    severity="CRITICAL",
                    confidence=1.0,
                    evidence={"true_peak_dbtp": premaster_facts.true_peak_dbtp, "clipping_flag": premaster_facts.clipping_detected},
                    recommended_action="Apply aggressive lookahead limiting and input attenuation before linear loudnorm.",
                    bounded_parameters={"limiter_ceiling_adjust": -0.6},
                )
            )

        if premaster_facts.phase_correlation is not None:
            if premaster_facts.phase_correlation < 0.0:
                issues.append(
                    MasteringIssue(
                        issue_type="severe_anti_phase_cancellation",
                        severity="CRITICAL",
                        confidence=0.95,
                        evidence={"phase_correlation": premaster_facts.phase_correlation},
                        recommended_action="Flag stage 11 mix for severe anti-phase cancellation; mono summing will cancel speech.",
                        bounded_parameters={},
                    )
                )
            elif premaster_facts.phase_correlation < 0.20:
                issues.append(
                    MasteringIssue(
                        issue_type="narrow_stereo_phase_correlation",
                        severity="MINOR",
                        confidence=0.85,
                        evidence={"phase_correlation": premaster_facts.phase_correlation},
                        recommended_action="Mono compatibility warning; ensure core vocal energy is centered.",
                        bounded_parameters={},
                    )
                )

        # 2. PRIORITY 2: Dialogue Intelligibility & Masking
        if (
            dialogue_facts
            and dialogue_facts.integrated_lufs is not None
            and premaster_facts.integrated_lufs is not None
            and dialogue_facts.integrated_lufs > -65.0
        ):
            anchor_ratio = round(dialogue_facts.integrated_lufs - premaster_facts.integrated_lufs, 2)
            # Check scene intent context: whisper or combat might legitimately have different ratios
            is_whisper = False
            is_combat = False
            if scene_intent:
                intent_str = str(getattr(scene_intent, "scene_type", "") or getattr(scene_intent, "intent", "")).lower()
                is_whisper = "whisper" in intent_str or "intimate" in intent_str
                is_combat = "combat" in intent_str or "action" in intent_str or "battle" in intent_str

            if anchor_ratio < -4.0 and not is_whisper:
                # Dialogue is significantly quieter than composite mix
                conf = 0.90 if premaster_facts.duration_sec >= 2.0 else 0.70
                issues.append(
                    MasteringIssue(
                        issue_type="dialogue_weakness_masking_risk",
                        severity="MAJOR",
                        confidence=conf,
                        evidence={"dialogue_lufs": dialogue_facts.integrated_lufs, "premaster_lufs": premaster_facts.integrated_lufs, "anchor_ratio_db": anchor_ratio},
                        recommended_action="Dialogue is masked by music/ambience; apply vocal leveling and attenuate background bed.",
                        bounded_parameters={"target_lufs_adjust": -0.5, "vocal_boost_db": 1.5},
                    )
                )
            elif anchor_ratio > 4.5 and not is_combat:
                issues.append(
                    MasteringIssue(
                        issue_type="excessive_dialogue_dominance",
                        severity="MINOR",
                        confidence=0.80,
                        evidence={"anchor_ratio_db": anchor_ratio},
                        recommended_action="Dialogue significantly overpowers soundscape bed; atmospheric immersion reduced.",
                        bounded_parameters={},
                    )
                )

        # 3. PRIORITY 3: Excessive Harshness & Sibilance
        centroid = premaster_facts.spectral_centroid_hz
        rolloff = premaster_facts.spectral_rolloff_hz
        if centroid is not None and centroid > 3800.0:
            conf = min(0.95, 0.75 + (centroid - 3800.0) / 2000.0)
            issues.append(
                MasteringIssue(
                    issue_type="excessive_spectral_harshness",
                    severity="MAJOR",
                    confidence=conf,
                    evidence={"spectral_centroid_hz": centroid, "spectral_rolloff_hz": rolloff},
                    recommended_action="Elevated high-frequency energy detected; apply high-frequency damping or de-esser.",
                    bounded_parameters={"limiter_ceiling_adjust": -0.3},
                )
            )

        # Sibilance check via high crest factor in upper frequency band
        if centroid is not None and 4500.0 <= centroid <= 7500.0 and premaster_facts.transient_count and premaster_facts.transient_count > 40:
            issues.append(
                MasteringIssue(
                    issue_type="excessive_vocal_sibilance",
                    severity="MINOR",
                    confidence=0.75,
                    evidence={"spectral_centroid_hz": centroid, "transient_count": premaster_facts.transient_count},
                    recommended_action="High sibilance energy detected; recommend targeted 6kHz de-essing notch.",
                    bounded_parameters={},
                )
            )

        # 4. PRIORITY 4: Tonal Imbalance (Low-frequency rumble)
        if centroid is not None and centroid < 220.0 and premaster_facts.duration_sec >= 2.0:
            issues.append(
                MasteringIssue(
                    issue_type="excessive_low_frequency_rumble",
                    severity="MAJOR",
                    confidence=0.85,
                    evidence={"spectral_centroid_hz": centroid},
                    recommended_action="Significant sub-bass buildup; increase subsonic highpass cutoff to 35Hz.",
                    bounded_parameters={"subsonic_cutoff_adjust": 35},
                )
            )

        # 5. PRIORITY 5: Dynamics Over-Compression & Limiter Activity
        crest = premaster_facts.crest_factor_db
        lra = premaster_facts.loudness_range_lra
        if crest is not None and crest < 4.5:
            conf = 0.90 if premaster_facts.duration_sec >= 3.0 else 0.65
            issues.append(
                MasteringIssue(
                    issue_type="excessive_dynamics_compression",
                    severity="MAJOR",
                    confidence=conf,
                    evidence={"crest_factor_db": crest, "loudness_range_lra": lra},
                    recommended_action="Dynamics are heavily squashed (crest factor < 4.5 dB); relax limiter ceiling.",
                    bounded_parameters={"limiter_ceiling_adjust": 0.4},
                )
            )
        elif lra is not None and lra > 14.0:
            issues.append(
                MasteringIssue(
                    issue_type="insufficient_dynamics_control",
                    severity="MINOR",
                    confidence=0.80,
                    evidence={"loudness_range_lra": lra},
                    recommended_action="Loudness range exceeds commercial standard (LRA > 14 LU); recommend tightening dynamics.",
                    bounded_parameters={"target_lra_adjust": 9.0},
                )
            )

        # Check peak proximity to ceiling (Limiter slamming)
        sample_peak = premaster_facts.sample_peak_dbfs
        if sample_peak is not None and sample_peak >= prof.limiter_ceiling_db - 0.05 and crest is not None and crest < 5.5:
            issues.append(
                MasteringIssue(
                    issue_type="excessive_limiter_activity",
                    severity="MINOR",
                    confidence=0.75,
                    evidence={"sample_peak_dbfs": sample_peak, "limiter_ceiling_db": prof.limiter_ceiling_db},
                    recommended_action="Signal continuously hitting limiter threshold; pull back linear input gain.",
                    bounded_parameters={"limiter_ceiling_adjust": -0.3},
                )
            )

        # 6. PRIORITY 6: Loudness Consistency
        lufs_diff = abs(premaster_facts.integrated_lufs - prof.target_lufs)
        if lufs_diff > prof.tolerance_lu and premaster_facts.integrated_lufs > -65.0:
            # Significant deviation from target LUFS
            conf = 0.95 if premaster_facts.duration_sec >= 3.0 else 0.70
            direction = "hot" if premaster_facts.integrated_lufs > prof.target_lufs else "cold"
            issues.append(
                MasteringIssue(
                    issue_type="premaster_loudness_drift",
                    severity="MAJOR" if lufs_diff > prof.tolerance_lu * 2.0 else "MINOR",
                    confidence=conf,
                    evidence={"measured_lufs": premaster_facts.integrated_lufs, "target_lufs": prof.target_lufs, "delta_lu": round(lufs_diff, 2), "direction": direction},
                    recommended_action=f"Premaster is {direction} by {lufs_diff:.2f} LU; linear loudnorm pass 2 will normalize.",
                    bounded_parameters={},
                )
            )

        # Sort issues strictly by priority severity: CRITICAL > MAJOR > MINOR > INFO
        severity_order = {"CRITICAL": 0, "MAJOR": 1, "MINOR": 2, "INFO": 3}
        issues.sort(key=lambda x: (severity_order.get(x.severity, 4), -x.confidence))

        # Formulate Overall Verdict & Bounded Action Plan
        has_critical = any(i.severity == "CRITICAL" for i in issues)
        actionable_issues = [i for i in issues if i.confidence >= 0.60 and i.bounded_parameters]

        if has_critical:
            verdict = "REJECT"
            adjusted_profile = None
            explanation = f"Critical defects detected: {[i.issue_type for i in issues if i.severity == 'CRITICAL']}"
        elif actionable_issues:
            verdict = "ADJUST"
            adjusted_profile = self._derive_bounded_profile(prof, actionable_issues)
            explanation = f"Generated bounded profile adjustments for {len(actionable_issues)} issue(s): {[i.issue_type for i in actionable_issues]}"
        else:
            verdict = "PASS"
            adjusted_profile = None
            explanation = "Premaster meets acoustic standards; proceeding with standard deterministic profile."

        return MasteringActionPlan(
            chapter_id=chapter_id,
            issues=issues,
            overall_verdict=verdict,
            adjusted_profile=adjusted_profile,
            explanation=explanation,
        )

    def _derive_bounded_profile(
        self,
        base_profile: MasteringProfile,
        actionable_issues: List[MasteringIssue],
    ) -> MasteringProfile:
        """
        Derives an adjusted MasteringProfile with strictly clamped parameters,
        guaranteeing the Judge can NEVER exceed safety boundaries.
        """
        new_prof = base_profile.model_copy(deep=True)

        for issue in actionable_issues:
            params = issue.bounded_parameters
            # 1. Target LUFS adjustment
            if "target_lufs_adjust" in params:
                req_lufs = float(params["target_lufs_adjust"])
                delta = req_lufs - base_profile.target_lufs if req_lufs < -5.0 else req_lufs
                clamped_delta = max(-SAFETY_BOUNDS["max_lufs_shift"], min(SAFETY_BOUNDS["max_lufs_shift"], delta))
                effective_lufs = base_profile.target_lufs + clamped_delta
                new_prof.target_lufs = round(
                    max(SAFETY_BOUNDS["target_lufs_min"], min(SAFETY_BOUNDS["target_lufs_max"], effective_lufs)), 2
                )

            # 2. Limiter ceiling adjustment
            if "limiter_ceiling_adjust" in params:
                shift = float(params["limiter_ceiling_adjust"])
                clamped_shift = max(-SAFETY_BOUNDS["max_limiter_shift"], min(SAFETY_BOUNDS["max_limiter_shift"], shift))
                effective_limiter = base_profile.limiter_ceiling_db + clamped_shift
                new_prof.limiter_ceiling_db = round(
                    max(SAFETY_BOUNDS["limiter_ceiling_min"], min(SAFETY_BOUNDS["limiter_ceiling_max"], effective_limiter)), 2
                )

            # 3. Subsonic highpass cutoff adjustment
            if "subsonic_cutoff_adjust" in params:
                req_hz = int(params["subsonic_cutoff_adjust"])
                delta_hz = req_hz - base_profile.subsonic_highpass_hz
                clamped_delta_hz = max(-SAFETY_BOUNDS["max_subsonic_shift"], min(SAFETY_BOUNDS["max_subsonic_shift"], delta_hz))
                effective_hz = base_profile.subsonic_highpass_hz + clamped_delta_hz
                new_prof.subsonic_highpass_hz = int(
                    max(SAFETY_BOUNDS["subsonic_hz_min"], min(SAFETY_BOUNDS["subsonic_hz_max"], effective_hz))
                )

            # 4. Target LRA adjustment
            if "target_lra_adjust" in params:
                req_lra = float(params["target_lra_adjust"])
                new_prof.target_lra = round(
                    max(SAFETY_BOUNDS["target_lra_min"], min(SAFETY_BOUNDS["target_lra_max"], req_lra)), 2
                )

        return new_prof
