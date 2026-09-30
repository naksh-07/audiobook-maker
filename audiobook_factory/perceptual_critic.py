#!/usr/bin/env python3
"""
Audiobook Factory - Stage 12: Perceptual Critic (P4).
=====================================================
Evaluates mastered audiobook audio as an *experience* across 7 perceptual dimensions:
1. Voice Intelligibility (speech clarity, masking avoidance)
2. Naturalness (processing transparency, anti-pumping, crest factor integrity)
3. Tonal Balance (spectral centroid coherence with Book Master Profile)
4. Dynamic Integrity (preserves intentional contrast: quiet != bad, loud != good)
5. Emotional Preservation (protects intimacy, tension, excitement, suspense)
6. Spatial Coherence (stereo stage stability, mono compatibility, phase correlation)
7. Fatigue Risk (measurable indicators of harsh high-end, excessive loudness, hyper-compression)

Core Invariant:
All criticisms are backed by measurable empirical evidence. The critic distinguishes
HIGH / MEDIUM / LOW confidence and prefers NO CHANGE over UNCERTAIN CHANGE.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional, Union

from audiobook_factory.mastering_contracts import (
    MasteringAnalysisFacts,
    MasteringIssue,
    BookMasterProfile,
    DialogueProtectionReport,
    PerceptualIssue,
    PerceptualEvaluation,
    PerceptualDimension,
)

logger = logging.getLogger("AudiobookFactory")

CRITIC_VERSION = "1.0.0"


class PerceptualCritic:
    """
    Forensic perceptual critic evaluating audio aesthetics, listening comfort,
    and narrative emotional preservation.
    """

    def __init__(self, version: str = CRITIC_VERSION):
        self.version = version

    def evaluate(
        self,
        facts: MasteringAnalysisFacts,
        judge_issues: Optional[List[MasteringIssue]] = None,
        book_profile: Optional[BookMasterProfile] = None,
        scene_intent: Optional[Any] = None,
        dialogue_report: Optional[DialogueProtectionReport] = None,
        previous_eval: Optional[PerceptualEvaluation] = None,
    ) -> PerceptualEvaluation:
        """
        Executes multi-dimensional perceptual evaluation across 7 aesthetic axes.
        Returns a structured PerceptualEvaluation with empirical evidence and confidence.
        """
        judge_issues = judge_issues or []
        evidence_ledger: List[str] = []
        issues: List[PerceptualIssue] = []
        scores: Dict[str, float] = {}

        # Determine evaluation confidence based on available telemetry and duration
        confidence = self._compute_confidence(facts, dialogue_report, book_profile, scene_intent)

        # 1. Voice Intelligibility
        score_intelligibility, intel_issues, intel_ev = self._evaluate_intelligibility(
            facts, dialogue_report, judge_issues
        )
        scores["intelligibility"] = round(score_intelligibility, 3)
        issues.extend(intel_issues)
        evidence_ledger.extend(intel_ev)

        # 2. Naturalness
        score_naturalness, nat_issues, nat_ev = self._evaluate_naturalness(
            facts, judge_issues
        )
        scores["naturalness"] = round(score_naturalness, 3)
        issues.extend(nat_issues)
        evidence_ledger.extend(nat_ev)

        # 3. Tonal Balance
        score_tonal, tonal_issues, tonal_ev = self._evaluate_tonal_balance(
            facts, book_profile, judge_issues
        )
        scores["tonal_balance"] = round(score_tonal, 3)
        issues.extend(tonal_issues)
        evidence_ledger.extend(tonal_ev)

        # 4. Dynamic Integrity (quiet != bad, loud != good)
        score_dynamics, dyn_issues, dyn_ev = self._evaluate_dynamic_integrity(
            facts, scene_intent, book_profile
        )
        scores["dynamic_integrity"] = round(score_dynamics, 3)
        issues.extend(dyn_issues)
        evidence_ledger.extend(dyn_ev)

        # 5. Emotional Preservation
        score_emotional, emo_issues, emo_ev = self._evaluate_emotional_preservation(
            facts, scene_intent, dialogue_report
        )
        scores["emotional_preservation"] = round(score_emotional, 3)
        issues.extend(emo_issues)
        evidence_ledger.extend(emo_ev)

        # 6. Spatial Coherence
        score_spatial, spat_issues, spat_ev = self._evaluate_spatial_coherence(facts)
        scores["spatial_coherence"] = round(score_spatial, 3)
        issues.extend(spat_issues)
        evidence_ledger.extend(spat_ev)

        # 7. Fatigue Risk Indicators
        score_fatigue, fatigue_issues, fatigue_ev = self._evaluate_fatigue_risk(
            facts, judge_issues
        )
        scores["fatigue_risk"] = round(score_fatigue, 3)
        issues.extend(fatigue_issues)
        evidence_ledger.extend(fatigue_ev)

        # Derive overall verdict
        overall = self._determine_overall_verdict(scores, issues, confidence)

        return PerceptualEvaluation(
            overall=overall,
            scores=scores,
            issues=issues,
            confidence=round(confidence, 2),
            evidence=evidence_ledger,
            critic_version=self.version,
        )

    def _compute_confidence(
        self,
        facts: MasteringAnalysisFacts,
        dialogue_report: Optional[DialogueProtectionReport],
        book_profile: Optional[BookMasterProfile],
        scene_intent: Optional[Any],
    ) -> float:
        """Computes evaluation confidence from data completeness and audio duration."""
        confidence = 0.60  # baseline for valid audio facts

        if facts.duration_sec < 1.0:
            return 0.35  # micro-sliver audio has low statistical confidence
        elif facts.duration_sec >= 3.0:
            confidence += 0.10

        if dialogue_report is not None:
            confidence += 0.10
        if book_profile is not None:
            confidence += 0.10
        if scene_intent is not None:
            confidence += 0.10

        return min(confidence, 1.0)

    def _evaluate_intelligibility(
        self,
        facts: MasteringAnalysisFacts,
        dialogue_report: Optional[DialogueProtectionReport],
        judge_issues: List[MasteringIssue],
    ) -> tuple[float, List[PerceptualIssue], List[str]]:
        """Evaluates dialogue clarity and speech intelligibility."""
        score = 1.0
        issues = []
        evidence = []

        if dialogue_report:
            if dialogue_report.masking_risk == "SEVERE":
                score -= 0.40
                issues.append(
                    PerceptualIssue(
                        dimension="intelligibility",
                        severity="CRITICAL",
                        description="Severe speech masking: background elements compete directly with dialogue.",
                        evidence=[f"masking_risk={dialogue_report.masking_risk}", f"clarity_score={dialogue_report.clarity_score}"],
                        confidence=0.95,
                        recommended_action="Increase dialogue-to-mix ratio or carve background pocket at 1-3kHz.",
                    )
                )
            elif dialogue_report.masking_risk == "MODERATE":
                score -= 0.20
                issues.append(
                    PerceptualIssue(
                        dimension="intelligibility",
                        severity="MAJOR",
                        description="Moderate speech masking detected in narrative dialogue.",
                        evidence=[f"masking_risk={dialogue_report.masking_risk}"],
                        confidence=0.85,
                        recommended_action="Ensure minimum +6.0 dB dialogue-to-mix ratio.",
                    )
                )

            if dialogue_report.clarity_score < 0.60:
                score -= 0.15
                evidence.append(f"dialogue_clarity_score={dialogue_report.clarity_score:.2f}")

        # Check for muffled vocal formant (< 250Hz centroid without dialogue boost)
        if facts.spectral_centroid_hz and facts.spectral_centroid_hz < 220.0 and facts.integrated_lufs > -40.0:
            score -= 0.15
            issues.append(
                PerceptualIssue(
                    dimension="intelligibility",
                    severity="MINOR",
                    description="Vocal clarity risk: low spectral centroid indicates muffled or bass-heavy speech.",
                    evidence=[f"spectral_centroid_hz={facts.spectral_centroid_hz:.1f}"],
                    confidence=0.75,
                    recommended_action="Apply gentle presence lift between 2.5kHz and 4.0kHz.",
                )
            )

        evidence.append(f"intelligibility_score={max(score, 0.0):.2f}")
        return max(score, 0.0), issues, evidence

    def _evaluate_naturalness(
        self,
        facts: MasteringAnalysisFacts,
        judge_issues: List[MasteringIssue],
    ) -> tuple[float, List[PerceptualIssue], List[str]]:
        """Evaluates processing transparency, avoiding over-compression and pumping."""
        score = 1.0
        issues = []
        evidence = []

        # Over-compression check via crest factor
        if facts.crest_factor_db is not None:
            if facts.crest_factor_db < 2.5:
                score -= 0.35
                issues.append(
                    PerceptualIssue(
                        dimension="naturalness",
                        severity="MAJOR",
                        description="Audible hyper-compression / brickwall limiting: crest factor collapsed below 2.5 dB.",
                        evidence=[f"crest_factor_db={facts.crest_factor_db:.2f}"],
                        confidence=0.90,
                        recommended_action="Raise limiter ceiling threshold or reduce loudnorm target compression.",
                    )
                )
            elif facts.crest_factor_db < 3.2:
                score -= 0.15
                evidence.append(f"low_crest_factor_db={facts.crest_factor_db:.2f}")

        # Excessive dynamics compression check from Judge
        for ji in judge_issues:
            if ji.issue_type == "excessive_dynamics_compression":
                score -= 0.10
                evidence.append("judge_flagged_excessive_compression")
            elif ji.issue_type == "excessive_limiter_activity":
                score -= 0.15
                evidence.append("judge_flagged_limiter_overload")

        evidence.append(f"naturalness_score={max(score, 0.0):.2f}")
        return max(score, 0.0), issues, evidence

    def _evaluate_tonal_balance(
        self,
        facts: MasteringAnalysisFacts,
        book_profile: Optional[BookMasterProfile],
        judge_issues: List[MasteringIssue],
    ) -> tuple[float, List[PerceptualIssue], List[str]]:
        """Evaluates tonal coherence and absence of harsh sibilance or boominess."""
        score = 1.0
        issues = []
        evidence = []

        centroid = facts.spectral_centroid_hz
        if centroid is not None:
            # Harshness indicator (> 3200Hz in non-sfx audio)
            if centroid > 3200.0:
                score -= 0.30
                issues.append(
                    PerceptualIssue(
                        dimension="tonal_balance",
                        severity="MAJOR",
                        description="Fatiguing high-frequency energy / harsh sibilance detected.",
                        evidence=[f"spectral_centroid_hz={centroid:.1f}"],
                        confidence=0.85,
                        recommended_action="Apply gentle high-shelf attenuation (-2.0 dB @ 6kHz).",
                    )
                )
            elif centroid > 2600.0:
                score -= 0.10
                evidence.append(f"elevated_spectral_centroid={centroid:.1f}Hz")

            # Check deviation from Book Master Profile
            if book_profile and book_profile.spectral_centroid_median_hz > 0:
                delta = abs(centroid - book_profile.spectral_centroid_median_hz)
                if delta > 1200.0:
                    score -= 0.15
                    issues.append(
                        PerceptualIssue(
                            dimension="tonal_balance",
                            severity="MINOR",
                            description="Tonal balance deviates significantly from Book Master Profile.",
                            evidence=[
                                f"chapter_centroid={centroid:.1f}Hz",
                                f"book_median_centroid={book_profile.spectral_centroid_median_hz:.1f}Hz",
                                f"delta={delta:.1f}Hz",
                            ],
                            confidence=0.80,
                            recommended_action="Check if tonal deviation is intentional narrative atmosphere.",
                        )
                    )

        evidence.append(f"tonal_balance_score={max(score, 0.0):.2f}")
        return max(score, 0.0), issues, evidence

    def _evaluate_dynamic_integrity(
        self,
        facts: MasteringAnalysisFacts,
        scene_intent: Optional[Any],
        book_profile: Optional[BookMasterProfile],
    ) -> tuple[float, List[PerceptualIssue], List[str]]:
        """
        Evaluates dynamic contrast preservation.
        Invariant: quiet != bad, loud != good. Intentional dynamic contrast is rewarded.
        """
        score = 1.0
        issues = []
        evidence = []

        is_whisper = False
        is_combat = False
        if scene_intent:
            focus = getattr(scene_intent, "focus", "")
            dynamic_preset = getattr(scene_intent, "dynamic_range_intent", "")
            if "intimate" in str(dynamic_preset).lower() or focus == "silence":
                is_whisper = True
            elif "wide" in str(dynamic_preset).lower() or getattr(scene_intent, "emotional_intensity", 0.0) > 0.8:
                is_combat = True

        # In whisper scenes, low integrated loudness is appropriate and protected
        if is_whisper and facts.integrated_lufs < -20.0:
            score = 1.0  # rewarded
            evidence.append(f"whisper_scene_dynamics_honored (LUFS={facts.integrated_lufs:.1f})")
            return score, issues, evidence

        # In combat scenes, high transient crest is expected
        if is_combat and facts.crest_factor_db and facts.crest_factor_db > 4.0:
            score = 1.0
            evidence.append(f"combat_scene_punch_honored (crest={facts.crest_factor_db:.1f}dB)")
            return score, issues, evidence

        # If audio is completely flattened (LRA < 1.0 LU) in normal dialogue
        if facts.loudness_range_lra is not None and facts.loudness_range_lra < 1.0 and facts.duration_sec >= 4.0:
            score -= 0.25
            issues.append(
                PerceptualIssue(
                    dimension="dynamic_integrity",
                    severity="MINOR",
                    description="Dynamic flattening: audio lacks natural narrative dynamics (LRA < 1.0 LU).",
                    evidence=[f"lra={facts.loudness_range_lra:.2f}LU"],
                    confidence=0.75,
                    recommended_action="Allow wider dynamic range to preserve conversational pacing.",
                )
            )

        evidence.append(f"dynamic_integrity_score={max(score, 0.0):.2f}")
        return max(score, 0.0), issues, evidence

    def _evaluate_emotional_preservation(
        self,
        facts: MasteringAnalysisFacts,
        scene_intent: Optional[Any],
        dialogue_report: Optional[DialogueProtectionReport],
    ) -> tuple[float, List[PerceptualIssue], List[str]]:
        """Evaluates whether processing preserved scene emotional intimacy/intensity."""
        score = 1.0
        issues = []
        evidence = []

        if dialogue_report and not dialogue_report.dynamic_contrast_preserved:
            score -= 0.30
            issues.append(
                PerceptualIssue(
                    dimension="emotional_preservation",
                    severity="MAJOR",
                    description="Emotional contrast compromised: quiet dramatic nuance lost during leveling.",
                    evidence=["dialogue_report.dynamic_contrast_preserved=False"],
                    confidence=0.85,
                    recommended_action="Relax target loudness by +1.0 LU to preserve delicate delivery.",
                )
            )

        evidence.append(f"emotional_preservation_score={max(score, 0.0):.2f}")
        return max(score, 0.0), issues, evidence

    def _evaluate_spatial_coherence(
        self,
        facts: MasteringAnalysisFacts,
    ) -> tuple[float, List[PerceptualIssue], List[str]]:
        """Evaluates stereo stage stability and mono compatibility."""
        score = 1.0
        issues = []
        evidence = []

        r = facts.phase_correlation
        if r < 0.0:
            score = 0.20
            issues.append(
                PerceptualIssue(
                    dimension="spatial_coherence",
                    severity="CRITICAL",
                    description="Severe out-of-phase cancellation: audio cancels out in mono playback.",
                    evidence=[f"phase_correlation_r={r:.3f}"],
                    confidence=0.98,
                    recommended_action="Collapse out-of-phase stereo content or check spatial panning.",
                )
            )
        elif r < 0.20:
            score = 0.50
            issues.append(
                PerceptualIssue(
                    dimension="spatial_coherence",
                    severity="MAJOR",
                    description="Poor phase correlation (r < 0.20): risks center dialogue cancellation.",
                    evidence=[f"phase_correlation_r={r:.3f}"],
                    confidence=0.90,
                    recommended_action="Narrow wide stereo stems to guarantee mono compatibility.",
                )
            )
        elif r < 0.50:
            score = 0.80
            evidence.append(f"moderate_stereo_width (r={r:.3f})")
        else:
            score = 1.0
            evidence.append(f"solid_stereo_coherence (r={r:.3f})")

        return score, issues, evidence

    def _evaluate_fatigue_risk(
        self,
        facts: MasteringAnalysisFacts,
        judge_issues: List[MasteringIssue],
    ) -> tuple[float, List[PerceptualIssue], List[str]]:
        """
        Evaluates fatigue risk indicators (measurable acoustic factors that cause listener strain).
        Note: Stated strictly as 'fatigue risk indicators', not claimed human fatigue.
        """
        score = 1.0
        issues = []
        evidence = []

        fatigue_penalties = 0.0

        # High-frequency harshness
        if facts.spectral_centroid_hz and facts.spectral_centroid_hz > 2800.0:
            fatigue_penalties += 0.20
            evidence.append(f"fatigue_risk_harsh_hf={facts.spectral_centroid_hz:.1f}Hz")

        # Hyper-compressed sustained loudness (> -17.5 LUFS with low crest factor)
        if facts.integrated_lufs > -17.5 and facts.crest_factor_db and facts.crest_factor_db < 3.5:
            fatigue_penalties += 0.25
            evidence.append(
                f"fatigue_risk_hyper_loudness_and_compression (LUFS={facts.integrated_lufs:.1f}, crest={facts.crest_factor_db:.1f}dB)"
            )

        # Multiple limiter activities
        limiter_flags = [ji for ji in judge_issues if "limiter" in ji.issue_type]
        if len(limiter_flags) > 0:
            fatigue_penalties += 0.15
            evidence.append("fatigue_risk_heavy_limiter_pumping")

        score = max(1.0 - fatigue_penalties, 0.0)

        if score < 0.65:
            issues.append(
                PerceptualIssue(
                    dimension="fatigue_risk",
                    severity="MAJOR",
                    description="Elevated listener fatigue risk indicators: combination of high frequency energy and aggressive loudness.",
                    evidence=evidence,
                    confidence=0.85,
                    recommended_action="Reduce target loudness to -19.5 LUFS and apply gentle high-shelf smoothing.",
                )
            )

        evidence.append(f"fatigue_risk_score={score:.2f}")
        return score, issues, evidence

    def _determine_overall_verdict(
        self,
        scores: Dict[str, float],
        issues: List[PerceptualIssue],
        confidence: float,
    ) -> str:
        """Determines PASS, WARN, or REVIEW verdict based on score thresholds and confidence."""
        critical_issues = [i for i in issues if i.severity == "CRITICAL"]
        if len(critical_issues) > 0:
            return "REVIEW"

        # If confidence is low and there are multiple major issues, flag for review
        major_issues = [i for i in issues if i.severity == "MAJOR"]
        if len(major_issues) >= 2 or (len(major_issues) >= 1 and confidence < 0.70):
            return "REVIEW"

        # Check dimension score minimums
        min_score = min(scores.values()) if scores else 1.0
        if min_score < 0.50:
            return "REVIEW"
        elif min_score < 0.75 or len(issues) > 0:
            return "WARN"

        return "PASS"
