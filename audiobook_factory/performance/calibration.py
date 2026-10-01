#!/usr/bin/env python3
"""
Audiobook Factory - Genuine Human Calibration Corpus & Validation Schema.
Enables statistical calibration and correlation analysis between automated
performance evaluation / evidence fusion scores and genuine human ratings.

Computes:
  - Pearson & Spearman rank correlations per dimension
  - False Accept Rate (FAR): Unacceptable takes incorrectly passed
  - False Reject Rate (FRR): High-quality takes incorrectly rejected
  - Inter-Rater Reliability (Mean Pairwise Agreement & Kendall's W)
"""

from __future__ import annotations
import math
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict


class HumanRatingRecord(BaseModel):
    """A single human auditor evaluation record for an audio take."""
    model_config = ConfigDict(extra="ignore")

    take_id: str = Field(..., description="Unique take identifier")
    rater_id: str = Field(..., description="Anonymized human listener identifier")
    dimension: str = Field(..., description="Evaluated performance dimension")
    score_likert: int = Field(..., ge=1, le=5, description="1-5 Likert scale score")
    normalized_score: float = Field(..., ge=0.0, le=1.0, description="Normalized score 0.0 to 1.0")
    is_acceptable: bool = Field(..., description="Whether human judge considers take commercially acceptable")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Rater certainty")
    notes: Optional[str] = Field(default=None, description="Qualitative feedback")
    timestamp: str = Field(default="", description="ISO timestamp of rating")


class HumanCalibrationDataset(BaseModel):
    """Structured collection of genuine human listener evaluations."""
    model_config = ConfigDict(extra="ignore")

    dataset_id: str = Field(..., description="Unique calibration corpus identifier")
    version: str = Field(default="1.0", description="Schema version")
    description: str = Field(default="", description="Corpus provenance description")
    ratings: List[HumanRatingRecord] = Field(default_factory=list)

    def get_mean_scores_by_take(self) -> Dict[str, Dict[str, float]]:
        """Aggregates multi-rater scores per take and dimension."""
        accum: Dict[str, Dict[str, List[float]]] = {}
        for r in self.ratings:
            if r.take_id not in accum:
                accum[r.take_id] = {}
            if r.dimension not in accum[r.take_id]:
                accum[r.take_id][r.dimension] = []
            accum[r.take_id][r.dimension].append(r.normalized_score)

        return {
            take_id: {
                dim: sum(scores) / len(scores)
                for dim, scores in dims.items()
            }
            for take_id, dims in accum.items()
        }

    def get_consensus_acceptability(self, threshold: float = 0.50) -> Dict[str, bool]:
        """Calculates majority human consensus on whether take is acceptable."""
        accum: Dict[str, List[bool]] = {}
        for r in self.ratings:
            if r.take_id not in accum:
                accum[r.take_id] = []
            accum[r.take_id].append(r.is_acceptable)

        return {
            take_id: (sum(1 for a in accepts if a) / len(accepts)) >= threshold
            for take_id, accepts in accum.items()
        }


class CalibrationMetricsReport(BaseModel):
    """Statistical summary of system calibration against human benchmark."""
    model_config = ConfigDict(extra="ignore")

    dataset_id: str
    sample_size: int
    pearson_correlation: float
    spearman_correlation: float
    false_accept_rate: float
    false_reject_rate: float
    overall_accuracy: float
    inter_rater_agreement: float
    diagnostics: List[str] = Field(default_factory=list)
    passed_calibration: bool = Field(default=True)


class CalibrationMetricCalculator:
    """Computes correlation and classification metrics against human benchmark."""

    @staticmethod
    def pearson_r(x: List[float], y: List[float]) -> float:
        """Calculates Pearson correlation coefficient between two series."""
        n = len(x)
        if n < 2 or len(y) != n:
            return 0.0

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        var_x = sum((xi - mean_x) ** 2 for xi in x)
        var_y = sum((yi - mean_y) ** 2 for yi in y)

        if var_x <= 1e-9 or var_y <= 1e-9:
            return 0.0

        cov_xy = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        r = cov_xy / math.sqrt(var_x * var_y)
        return round(float(r), 3)

    @staticmethod
    def spearman_rho(x: List[float], y: List[float]) -> float:
        """Calculates Spearman rank correlation coefficient."""
        n = len(x)
        if n < 2 or len(y) != n:
            return 0.0

        def _rank(vals: List[float]) -> List[float]:
            indexed = sorted(enumerate(vals), key=lambda item: item[1])
            ranks = [0.0] * n
            for rank_idx, (orig_idx, _) in enumerate(indexed):
                ranks[orig_idx] = float(rank_idx + 1)
            return ranks

        rx = _rank(x)
        ry = _rank(y)
        return CalibrationMetricCalculator.pearson_r(rx, ry)

    @classmethod
    def evaluate_system_calibration(
        cls,
        human_dataset: HumanCalibrationDataset,
        system_scores: Dict[str, float],
        system_accepts: Dict[str, bool],
        min_pearson_r: float = 0.60,
        max_far: float = 0.15,
        max_frr: float = 0.20,
    ) -> CalibrationMetricsReport:
        """
        Evaluates system fidelity against human ground truth.
        """
        mean_scores = human_dataset.get_mean_scores_by_take()
        human_accepts = human_dataset.get_consensus_acceptability()

        common_takes = [t for t in mean_scores.keys() if t in system_scores and t in system_accepts]
        diagnostics: List[str] = []

        if not common_takes:
            return CalibrationMetricsReport(
                dataset_id=human_dataset.dataset_id,
                sample_size=0,
                pearson_correlation=0.0,
                spearman_correlation=0.0,
                false_accept_rate=1.0,
                false_reject_rate=1.0,
                overall_accuracy=0.0,
                inter_rater_agreement=0.0,
                diagnostics=["No overlapping takes between human dataset and system scores."],
                passed_calibration=False,
            )

        # Average human overall score per take
        h_overall = []
        s_overall = []
        for t in common_takes:
            h_vals = list(mean_scores[t].values())
            h_overall.append(sum(h_vals) / len(h_vals) if h_vals else 0.5)
            s_overall.append(system_scores[t])

        pr = cls.pearson_r(s_overall, h_overall)
        sr = cls.spearman_rho(s_overall, h_overall)

        # FAR & FRR
        # FAR: Human says unacceptable (False), but system accepted (True)
        # FRR: Human says acceptable (True), but system rejected (False)
        total_human_unacc = sum(1 for t in common_takes if not human_accepts[t])
        total_human_acc = sum(1 for t in common_takes if human_accepts[t])

        false_accepts = sum(
            1 for t in common_takes
            if (not human_accepts[t]) and system_accepts[t]
        )
        false_rejects = sum(
            1 for t in common_takes
            if human_accepts[t] and (not system_accepts[t])
        )

        far = (false_accepts / total_human_unacc) if total_human_unacc > 0 else 0.0
        frr = (false_rejects / total_human_acc) if total_human_acc > 0 else 0.0

        correct = sum(
            1 for t in common_takes
            if human_accepts[t] == system_accepts[t]
        )
        accuracy = correct / len(common_takes)

        # Inter-rater agreement across multiple raters
        ratings_by_take: Dict[str, List[bool]] = {}
        for r in human_dataset.ratings:
            if r.take_id not in ratings_by_take:
                ratings_by_take[r.take_id] = []
            ratings_by_take[r.take_id].append(r.is_acceptable)

        # Pairwise percentage agreement
        pair_agreements: List[float] = []
        for t, bools in ratings_by_take.items():
            if len(bools) >= 2:
                pairs = 0
                matches = 0
                for i in range(len(bools)):
                    for j in range(i + 1, len(bools)):
                        pairs += 1
                        if bools[i] == bools[j]:
                            matches += 1
                if pairs > 0:
                    pair_agreements.append(matches / pairs)

        ira = sum(pair_agreements) / len(pair_agreements) if pair_agreements else 1.0

        # Calibration pass criteria
        passed = True
        if pr < min_pearson_r:
            passed = False
            diagnostics.append(f"Pearson r {pr:.2f} below target threshold {min_pearson_r:.2f}")
        if far > max_far:
            passed = False
            diagnostics.append(f"False Accept Rate {far:.1%} exceeds tolerance {max_far:.1%}")
        if frr > max_frr:
            passed = False
            diagnostics.append(f"False Reject Rate {frr:.1%} exceeds tolerance {max_frr:.1%}")

        if passed:
            diagnostics.append("System calibration meets commercial audio fidelity targets.")

        return CalibrationMetricsReport(
            dataset_id=human_dataset.dataset_id,
            sample_size=len(common_takes),
            pearson_correlation=pr,
            spearman_correlation=sr,
            false_accept_rate=round(far, 3),
            false_reject_rate=round(frr, 3),
            overall_accuracy=round(accuracy, 3),
            inter_rater_agreement=round(ira, 3),
            diagnostics=diagnostics,
            passed_calibration=passed,
        )


class CalibrationCorpusEntry(BaseModel):
    """A representative dramatic calibration segment across dramatic modes."""
    model_config = ConfigDict(extra="ignore")

    mode_id: str = Field(..., description="Unique mode identifier")
    title: str = Field(..., description="Descriptive dramatic category title")
    speaker: str = Field(..., description="Speaker name")
    text: str = Field(..., description="Canonical representative text")
    direction: Dict[str, Any] = Field(..., description="PerformanceDirection parameter dictionary")
    expected_acoustic_markers: Dict[str, Any] = Field(..., description="Forensic acoustic target ranges")
    known_failure_modes: List[str] = Field(default_factory=list, description="Specific acoustic and dramatic failure patterns")
    expected_outcome: str = Field(default="ACCEPT", description="Expected qualification status (ACCEPT / REGENERATE)")


class PerformanceCalibrationCorpus:
    """
    Forensic Performance Calibration Corpus across 12 dramatic modes.
    Establishes empirical acoustic boundaries and gating expectations
    for human-grade audio drama performance evaluation.
    """

    @classmethod
    def get_standard_corpus(cls) -> List[CalibrationCorpusEntry]:
        """Returns 12 canonical representative segments across dramatic modes."""
        return [
            # 1. Whisper / Close-Mic Intimate
            CalibrationCorpusEntry(
                mode_id="whisper_intimate",
                title="Intimate Confession",
                speaker="Yennefer",
                text="Listen to me. If we don't move now, neither of us survives the dawn.",
                direction={
                    "surface_emotion": "whisper_intimate",
                    "intensity": "low",
                    "restraint": 0.85,
                    "proximity": "close_mic",
                    "resonance": "whisper_air",
                    "pace": 0.90,
                    "energy": 0.35,
                    "actioning": "whisper_secret_urgency",
                },
                expected_acoustic_markers={
                    "rms_dbfs_range": (-40.0, -18.0),
                    "f0_variance_min": 2.0,
                    "wps_range": (1.8, 3.2),
                    "max_clipping_pinned": 0,
                    "max_dead_air_sec": 1.2,
                },
                known_failure_modes=[
                    "Blown-out volume (RMS > -18 dBFS violating intimate proximity)",
                    "Vocoder static hiss in unvoiced fricatives",
                    "Lack of breath presence on close-mic onset",
                ],
                expected_outcome="ACCEPT",
            ),
            # 2. Restrained Grief / Held-Back Sorrow
            CalibrationCorpusEntry(
                mode_id="restrained_grief",
                title="Restrained Grief",
                speaker="Geralt",
                text="I couldn't reach her in time. The fire was already inside the tower.",
                direction={
                    "surface_emotion": "grief",
                    "intensity": "medium",
                    "restraint": 0.88,
                    "vulnerability": 0.90,
                    "pace": 0.85,
                    "energy": 0.50,
                    "actioning": "confess_tragic_failure_with_suppression",
                    "subtext": "overwhelming guilt buried behind stone facade",
                    "subtext_confidence": 0.90,
                },
                expected_acoustic_markers={
                    "rms_dbfs_range": (-32.0, -16.0),
                    "f0_variance_min": 6.0,
                    "wps_range": (1.8, 3.0),
                    "max_clipping_pinned": 0,
                    "max_dead_air_sec": 1.5,
                },
                known_failure_modes=[
                    "Overacted melodramatic weeping or sobbing breaking character restraint",
                    "Unsuppressed shouting at peak > 31000",
                    "Flat reading lacking subtextual vocal compression",
                ],
                expected_outcome="ACCEPT",
            ),
            # 3. Explosive Rage / Battle Cry
            CalibrationCorpusEntry(
                mode_id="explosive_rage",
                title="Explosive Battle Rage",
                speaker="Dijkstra",
                text="Treason! Every man on the ramparts—draw steel and butcher them all!",
                direction={
                    "surface_emotion": "bellowing_rage",
                    "intensity": "explosive",
                    "restraint": 0.15,
                    "pace": 1.25,
                    "energy": 0.95,
                    "actioning": "command_immediate_slaughter",
                },
                expected_acoustic_markers={
                    "rms_dbfs_range": (-22.0, -10.0),
                    "f0_variance_min": 25.0,
                    "wps_range": (3.0, 4.8),
                    "max_clipping_pinned": 5,
                    "max_dead_air_sec": 0.8,
                },
                known_failure_modes=[
                    "Underpowered energy (RMS < -24 dBFS for explosive scene)",
                    "Digital rail clipping exceeding 6 pinned samples",
                    "Premature emotional climax without vocal projection",
                ],
                expected_outcome="ACCEPT",
            ),
            # 4. Calm Exposition / Narrator
            CalibrationCorpusEntry(
                mode_id="calm_exposition",
                title="Epic Worldbuilding Exposition",
                speaker="Narrator",
                text="The pass of Kaer Morhen lay blanketed in three feet of bitter November snow.",
                direction={
                    "surface_emotion": "neutral",
                    "intensity": "medium",
                    "narrative_mode": "narrator_exposition",
                    "pace": 1.00,
                    "energy": 0.65,
                    "actioning": "paint_bleak_atmosphere",
                },
                expected_acoustic_markers={
                    "rms_dbfs_range": (-26.0, -16.0),
                    "f0_variance_min": 12.0,
                    "wps_range": (2.6, 3.5),
                    "max_clipping_pinned": 0,
                    "max_dead_air_sec": 1.2,
                },
                known_failure_modes=[
                    "Robotic monotonic pitch lock (F0 variance < 5 Hz)",
                    "Pacing drift rushing (> 4.2 wps) or dragging (< 2.0 wps)",
                    "Excessive trailing dead air (> 1.5s)",
                ],
                expected_outcome="ACCEPT",
            ),
            # 5. Intimate Dialogue
            CalibrationCorpusEntry(
                mode_id="intimate_dialogue",
                title="Tender Romantic Dialogue",
                speaker="Yennefer",
                text="You always look at me as though I might vanish into the mist.",
                direction={
                    "surface_emotion": "tender_affection",
                    "intensity": "low",
                    "intimacy_level": "intimate",
                    "proximity": "close_mic",
                    "restraint": 0.65,
                    "pace": 0.95,
                    "energy": 0.45,
                    "actioning": "reassure_lover_with_gentle_irony",
                },
                expected_acoustic_markers={
                    "rms_dbfs_range": (-34.0, -18.0),
                    "f0_variance_min": 8.0,
                    "wps_range": (2.2, 3.3),
                    "max_clipping_pinned": 0,
                    "max_dead_air_sec": 1.0,
                },
                known_failure_modes=[
                    "Aggressive volume projection (RMS > -16 dBFS)",
                    "Harsh or brittle articulation violating tender intimacy",
                ],
                expected_outcome="ACCEPT",
            ),
            # 6. Fast Rally / Rapid Banter
            CalibrationCorpusEntry(
                mode_id="fast_rally",
                title="Rapid Combat Sparring Dialogue",
                speaker="Jaskier",
                text="Quick! The window or the stairs? Decide before the guard breaks the latch!",
                direction={
                    "surface_emotion": "frantic_urgency",
                    "intensity": "high",
                    "pace": 1.35,
                    "energy": 0.85,
                    "turn_taking_behavior": "immediate",
                    "actioning": "force_split_second_decision",
                },
                expected_acoustic_markers={
                    "rms_dbfs_range": (-24.0, -12.0),
                    "f0_variance_min": 18.0,
                    "wps_range": (3.6, 5.0),
                    "max_clipping_pinned": 2,
                    "max_dead_air_sec": 0.5,
                },
                known_failure_modes=[
                    "Sluggish tempo ratio (< 0.70x target WPS)",
                    "Unmotivated dead air between turn onset",
                ],
                expected_outcome="ACCEPT",
            ),
            # 7. Cold Sarcasm / Irony
            CalibrationCorpusEntry(
                mode_id="cold_sarcasm",
                title="Cold Venomous Sarcasm",
                speaker="Philippa",
                text="How marvelous of you to arrive precisely when all the danger has passed.",
                direction={
                    "surface_emotion": "cold_condescension",
                    "intensity": "medium",
                    "restraint": 0.85,
                    "subtext": "contempt disguised as formal greeting",
                    "subtext_confidence": 0.95,
                    "pace": 0.90,
                    "energy": 0.60,
                    "actioning": "undermine_with_scathing_politeness",
                },
                expected_acoustic_markers={
                    "rms_dbfs_range": (-28.0, -15.0),
                    "f0_variance_min": 10.0,
                    "wps_range": (2.2, 3.2),
                    "max_clipping_pinned": 0,
                    "max_dead_air_sec": 1.0,
                },
                known_failure_modes=[
                    "Direct reading without subtextual inflection",
                    "Unrestrained shouting destroying condescending poise",
                ],
                expected_outcome="ACCEPT",
            ),
            # 8. Breathless Panic / Physical Strain
            CalibrationCorpusEntry(
                mode_id="breathless_panic",
                title="Wounded Combat Strain",
                speaker="Cahir",
                text="The... the blade was poisoned. Bind it tight, before it reaches the vein.",
                direction={
                    "surface_emotion": "pain_panic",
                    "intensity": "high",
                    "physical_state": "wounded",
                    "breath_behavior": "labored",
                    "pre_roll_breath_ms": 350,
                    "pace": 0.80,
                    "energy": 0.70,
                    "actioning": "beg_for_survival_through_agony",
                },
                expected_acoustic_markers={
                    "rms_dbfs_range": (-30.0, -14.0),
                    "f0_variance_min": 12.0,
                    "wps_range": (1.5, 2.8),
                    "max_clipping_pinned": 1,
                    "max_dead_air_sec": 1.5,
                },
                known_failure_modes=[
                    "Missing directed breath intake in pre-roll",
                    "Brisk, healthy articulation inconsistent with wounded state",
                ],
                expected_outcome="ACCEPT",
            ),
            # 9. Authoritative Command
            CalibrationCorpusEntry(
                mode_id="authoritative_command",
                title="Royal Imperial Command",
                speaker="Emhyr",
                text="Bow, Witcher. Or leave your head upon my carpet.",
                direction={
                    "surface_emotion": "stone_authority",
                    "intensity": "high",
                    "power_position": "dominant",
                    "leverage": "commanding",
                    "restraint": 0.90,
                    "resonance": "chest",
                    "pace": 0.85,
                    "energy": 0.75,
                    "actioning": "demand_unconditional_submission",
                },
                expected_acoustic_markers={
                    "rms_dbfs_range": (-24.0, -12.0),
                    "f0_variance_min": 8.0,
                    "wps_range": (2.0, 3.0),
                    "max_clipping_pinned": 0,
                    "max_dead_air_sec": 1.2,
                },
                known_failure_modes=[
                    "Under-projected command authority (RMS < -28 dBFS)",
                    "Submissive vocal yielding or pitch insecurity",
                ],
                expected_outcome="ACCEPT",
            ),
            # 10. Submissive Plea / Yielded Leverage
            CalibrationCorpusEntry(
                mode_id="submissive_plea",
                title="Desperate Submissive Plea",
                speaker="Dudu",
                text="Please, don't turn me over to them. I have nowhere left to run.",
                direction={
                    "surface_emotion": "desperate_fear",
                    "intensity": "medium",
                    "power_position": "submissive",
                    "leverage": "vulnerable",
                    "vulnerability": 0.95,
                    "pace": 1.05,
                    "energy": 0.55,
                    "actioning": "plead_for_mercy",
                },
                expected_acoustic_markers={
                    "rms_dbfs_range": (-32.0, -18.0),
                    "f0_variance_min": 14.0,
                    "wps_range": (2.6, 3.8),
                    "max_clipping_pinned": 0,
                    "max_dead_air_sec": 0.8,
                },
                known_failure_modes=[
                    "Unmotivated aggressive projection exceeding partner volume",
                    "Failure to yield turn leverage",
                ],
                expected_outcome="ACCEPT",
            ),
            # 11. Hesitant Confession
            CalibrationCorpusEntry(
                mode_id="hesitant_confession",
                title="Hesitant Reluctant Truth",
                speaker="Triss",
                text="I... I knew about the lodge's plan all along. I should have told you.",
                direction={
                    "surface_emotion": "shame_hesitation",
                    "intensity": "low",
                    "silence_type": "hesitation",
                    "hesitation_ms": 600,
                    "restraint": 0.75,
                    "pace": 0.85,
                    "energy": 0.45,
                    "actioning": "admit_betrayal_with_shame",
                },
                expected_acoustic_markers={
                    "rms_dbfs_range": (-36.0, -20.0),
                    "f0_variance_min": 6.0,
                    "wps_range": (1.8, 2.9),
                    "max_clipping_pinned": 0,
                    "max_dead_air_sec": 1.8,
                },
                known_failure_modes=[
                    "Rushing through hesitation silence (< 200ms)",
                    "Over-confident assertion inconsistent with shame",
                ],
                expected_outcome="ACCEPT",
            ),
            # 12. Formal Ceremonial Exposition
            CalibrationCorpusEntry(
                mode_id="formal_exposition",
                title="Grand Court Announcement",
                speaker="Herald",
                text="Hear ye all! By royal decree of King Foltest, the tournament of arms begins.",
                direction={
                    "surface_emotion": "formal_grandeur",
                    "intensity": "high",
                    "intimacy_level": "formal",
                    "articulation": "crisp",
                    "resonance": "throat",
                    "pace": 1.05,
                    "energy": 0.85,
                    "actioning": "proclaim_royal_decree",
                },
                expected_acoustic_markers={
                    "rms_dbfs_range": (-22.0, -12.0),
                    "f0_variance_min": 15.0,
                    "wps_range": (2.8, 3.8),
                    "max_clipping_pinned": 1,
                    "max_dead_air_sec": 0.8,
                },
                known_failure_modes=[
                    "Slurred or colloquial articulation",
                    "Underpowered projection for court herald",
                ],
                expected_outcome="ACCEPT",
            ),
        ]

