#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Module: judge.py
Implements the Stage-11 Mix Judge, Automatic Diagnosis, and RemixPlan architecture.

Operates on the RENDERED result (Cinematic Mix Premaster + Discrete Stems),
evaluating technical safety and narrative cinematic intent across 12 categories:
1. Technical Safety
2. Dialogue Focus
3. Music Integration
4. FX Clarity
5. Ambience Naturalism
6. Dynamic Contrast
7. Spatial Coherence
8. Masking / Ducking
9. Silence Behavior
10. Impact Behavior
11. Transition Quality
12. Cinematic Intent

Produces deterministic, explainable verdicts: PASS, PASS_WITH_WARNINGS, REMIX, or FAIL.
"""

from __future__ import annotations
import math
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal, Tuple, Union, TYPE_CHECKING

from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger
if TYPE_CHECKING:
    from audiobook_factory.cinema_audio_engine import StemMetadata, StemLedger
from audiobook_factory.deterministic_audio_analyzer import DeterministicAudioAnalyzer
from audiobook_factory.gate_auditor import (
    audit_gate5_2_spectral_masking,
    audit_gate5_3_stereo_phase,
    AuditResult,
)
from audiobook_factory.cinematic_mix.scene_intent import SceneMixIntent
from audiobook_factory.cinematic_mix.attention_map import AttentionMap
from audiobook_factory.cinematic_mix.automation import MixAutomation, AutomationEvent
from audiobook_factory.cinematic_mix.perspective import AcousticPerspective
from audiobook_factory.cinematic_mix.silence import SilenceEvent
from audiobook_factory.cinematic_mix.impact import ImpactEvent


JudgeStatus = Literal["PASS", "PASS_WITH_WARNINGS", "REMIX", "FAIL"]
CategoryStatus = Literal["PASS", "PASS_WITH_WARNINGS", "REMIX", "FAIL"]


class CategoryResult(BaseModel):
    """Evaluation result for an individual mix judging category."""
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="Category identifier")
    status: CategoryStatus = Field(default="PASS", description="Category verdict")
    score: float = Field(default=1.0, ge=0.0, le=1.0, description="Normalized score [0.0, 1.0]")
    reason: str = Field(default="", description="Detailed narrative explanation")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Concrete measurable evidence")
    critical: bool = Field(default=False, description="Whether failure here causes a hard FAIL vs REMIX")


class MixDiagnosis(BaseModel):
    """Structured, actionable diagnosis explaining WHY a mix failed or needs remixing."""
    model_config = ConfigDict(extra="ignore")

    category: str = Field(..., description="Affected category")
    status: Literal["FAIL", "REMIX", "WARNING"] = Field(..., description="Severity level")
    reason: str = Field(..., description="Root cause error code")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Measured metrics triggering diagnosis")
    likely_cause: str = Field(default="", description="Engineering explanation of failure")
    recommended_action: str = Field(default="", description="Concrete remedy targeting Stage 11 controls")


class RemixAction(BaseModel):
    """An individual actionable parameter remediation recommendation."""
    model_config = ConfigDict(extra="ignore")

    target: str = Field(..., description="Target stem: DX, MX, FX, AMB, ME, master")
    parameter: str = Field(..., description="Mixing parameter: gain, ducking, eq_depth, lowpass_cutoff")
    current_value: float = Field(..., description="Observed parameter value")
    recommended_value: float = Field(..., description="Recommended target value for remix pass")
    action_code: str = Field(..., description="Machine-readable action identifier")
    reason: str = Field(..., description="Directorial justification for this adjustment")
    priority: float = Field(default=0.80, ge=0.0, le=1.0, description="Priority weight")


class RemixPlan(BaseModel):
    """A structured remix plan consumable by the next render iteration."""
    model_config = ConfigDict(extra="ignore")

    scene_id: Optional[str] = Field(default=None, description="Identifier of the scene being remixed")
    actions: List[RemixAction] = Field(default_factory=list, description="Ordered remediation actions")
    bounded_iteration: int = Field(default=1, description="Current remediation cycle count")
    convergence_score: float = Field(default=0.0, description="Score delta from previous attempt")
    explanation: str = Field(default="", description="Overall remediation summary")


class MixJudgeResult(BaseModel):
    """Comprehensive verdict returned by the Stage 11 Mix Judge."""
    model_config = ConfigDict(extra="ignore")

    status: JudgeStatus = Field(..., description="Overall verdict: PASS, PASS_WITH_WARNINGS, REMIX, FAIL")
    overall_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Interpretable score [0.0, 1.0]")
    category_results: List[CategoryResult] = Field(default_factory=list, description="Results per category")
    failures: List[str] = Field(default_factory=list, description="Critical blocking failures")
    warnings: List[str] = Field(default_factory=list, description="Non-blocking warning flags")
    diagnosis: List[MixDiagnosis] = Field(default_factory=list, description="Detailed causal diagnoses")
    remix_plan: Optional[RemixPlan] = Field(default=None, description="Actionable remix plan if status is REMIX")
    recommended_action: str = Field(default="PROCEED", description="Next pipeline step: PROCEED, REMIX, HALT")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Consolidated metrics ledger")


class MixJudge:
    """
    Independent Stage-11 Cinematic Mix Quality Judge.
    Evaluates rendered audio stems and premaster against scene intent, attention maps,
    and behavior events to guarantee both technical safety and narrative excellence.
    """

    def __init__(
        self,
        analyzer: Optional[DeterministicAudioAnalyzer] = None,
        ffmpeg_bin: Optional[str] = None,
    ):
        self.analyzer = analyzer or DeterministicAudioAnalyzer(ffmpeg_bin=ffmpeg_bin)
        self.ffmpeg = ffmpeg_bin or shutil.which("ffmpeg") or "ffmpeg"
        self._corridor_cache: Dict[Tuple[str, int, int], float] = {}
        self._phase_cache: Dict[Tuple[str, int, int], AuditResult] = {}

    def clear_cache(self) -> None:
        """Clears in-memory DSP and phase analysis caches."""
        self._corridor_cache.clear()
        self._phase_cache.clear()
        self.analyzer.clear_cache()

    def _get_phase_audit(self, filepath: Path) -> AuditResult:
        """Probes stereo phase correlation with cache acceleration."""
        cache_key = None
        try:
            st = filepath.stat()
            cache_key = (str(filepath.resolve()), st.st_size, st.st_mtime_ns)
            if cache_key in self._phase_cache:
                return self._phase_cache[cache_key]
        except Exception:
            cache_key = None

        res = audit_gate5_3_stereo_phase(filepath, min_phase_correlation=0.0, ffmpeg=self.ffmpeg)
        if cache_key:
            self._phase_cache[cache_key] = res
        return res

    def _measure_vocal_corridor_db(self, path: Path) -> float:
        """Measures 300Hz-3500Hz vocal corridor energy with cache acceleration."""
        cache_key = None
        try:
            st = path.stat()
            cache_key = (str(path.resolve()), st.st_size, st.st_mtime_ns)
            if cache_key in self._corridor_cache:
                return self._corridor_cache[cache_key]
        except Exception:
            cache_key = None

        corridor_db = -60.0
        try:
            import soundfile as sf
            import scipy.signal as signal
            import numpy as np
            data, sr = sf.read(str(path))
            y = data[:, 0] if data.ndim > 1 else data
            sos = signal.butter(4, [300, 3500], btype="bandpass", fs=sr, output="sos")
            filt = signal.sosfilt(sos, y)
            rms = float(20.0 * np.log10(np.sqrt(np.mean(filt**2)) + 1e-9))
            corridor_db = round(rms, 2)
        except Exception:
            loudness = self.analyzer.probe_loudness(path)
            corridor_db = round(loudness.integrated_lufs or loudness.rms_level_db or -30.0, 2)

        if cache_key:
            self._corridor_cache[cache_key] = corridor_db
        return corridor_db

    def evaluate(
        self,
        stem_ledger: Optional[StemLedger] = None,
        stems: Optional[Dict[str, Union[Path, str]]] = None,
        premaster_path: Optional[Union[Path, str]] = None,
        scene_intent: Optional[SceneMixIntent] = None,
        attention_map: Optional[AttentionMap] = None,
        mix_automation: Optional[MixAutomation] = None,
        acoustic_perspective: Optional[AcousticPerspective] = None,
        silence_events: Optional[List[SilenceEvent]] = None,
        impact_events: Optional[List[ImpactEvent]] = None,
        iteration: int = 1,
    ) -> MixJudgeResult:
        """
        Executes comprehensive multi-signal evaluation across all 12 categories.
        """
        # Resolve file paths from ledger or direct dictionaries
        resolved_stems: Dict[str, Path] = {}
        target_premaster: Optional[Path] = None

        if stem_ledger:
            for s_type, meta in stem_ledger.stems.items():
                if meta.filepath:
                    p = Path(meta.filepath).resolve()
                    if p.exists():
                        resolved_stems[s_type] = p
            if "CINEMATIC_MIX_PREMASTER" in stem_ledger.stems:
                target_premaster = Path(stem_ledger.stems["CINEMATIC_MIX_PREMASTER"].filepath).resolve()
            elif "FULL_MASTER" in stem_ledger.stems:
                target_premaster = Path(stem_ledger.stems["FULL_MASTER"].filepath).resolve()

        if stems:
            for s_type, s_path in stems.items():
                p = Path(s_path).resolve()
                if p.exists():
                    resolved_stems[s_type] = p

        if premaster_path:
            p = Path(premaster_path).resolve()
            if p.exists():
                target_premaster = p

        if not target_premaster and "CINEMATIC_MIX_PREMASTER" in resolved_stems:
            target_premaster = resolved_stems["CINEMATIC_MIX_PREMASTER"]
        elif not target_premaster and "master" in resolved_stems:
            target_premaster = resolved_stems["master"]

        # Run individual category checks
        cat_results: List[CategoryResult] = []

        # 1. Technical Safety (Critical)
        cat_results.append(self._check_technical_safety(target_premaster, resolved_stems))

        # 2. Dialogue Focus
        cat_results.append(
            self._check_dialogue_focus(
                resolved_stems.get("DX"),
                resolved_stems.get("MX"),
                resolved_stems.get("ME"),
                scene_intent,
                attention_map,
            )
        )

        # 3. Music Integration
        cat_results.append(
            self._check_music_integration(
                resolved_stems.get("MX"),
                resolved_stems.get("DX"),
                scene_intent,
                mix_automation,
            )
        )

        # 4. FX Clarity
        cat_results.append(
            self._check_fx_clarity(
                resolved_stems.get("FX"),
                impact_events,
                scene_intent,
            )
        )

        # 5. Ambience Naturalism
        cat_results.append(
            self._check_ambience_naturalism(
                resolved_stems.get("AMB"),
                resolved_stems.get("DX"),
                silence_events,
                scene_intent,
            )
        )

        # 6. Dynamic Contrast
        cat_results.append(
            self._check_dynamic_contrast(
                target_premaster,
                scene_intent,
            )
        )

        # 7. Spatial Coherence
        cat_results.append(
            self._check_spatial_coherence(
                target_premaster,
                resolved_stems.get("DX"),
                acoustic_perspective,
                mix_automation,
            )
        )

        # 8. Masking / Ducking
        cat_results.append(
            self._check_masking_ducking(
                resolved_stems.get("DX"),
                resolved_stems.get("MX"),
                mix_automation,
            )
        )

        # 9. Silence Behavior
        cat_results.append(
            self._check_silence_behavior(
                target_premaster,
                resolved_stems,
                silence_events,
            )
        )

        # 10. Impact Behavior
        cat_results.append(
            self._check_impact_behavior(
                target_premaster,
                resolved_stems.get("FX"),
                resolved_stems.get("MX"),
                impact_events,
            )
        )

        # 11. Transition Quality
        cat_results.append(
            self._check_transition_quality(
                target_premaster,
                mix_automation,
            )
        )

        # 12. Cinematic Intent
        cat_results.append(
            self._check_cinematic_intent(
                resolved_stems,
                scene_intent,
                attention_map,
            )
        )

        # Synthesize Overall Status and Actionable Diagnoses
        return self._synthesize_result(cat_results, iteration=iteration)

    # -------------------------------------------------------------------------
    # Category Implementations (Delegated to Modular Rules Engine)
    # -------------------------------------------------------------------------

    def _check_technical_safety(
        self,
        premaster: Optional[Path],
        stems: Dict[str, Path],
    ) -> CategoryResult:
        from audiobook_factory.cinematic_mix.rules import check_technical_safety
        return check_technical_safety(self.analyzer, self._get_phase_audit, premaster, stems)

    def _check_dialogue_focus(
        self,
        dx_path: Optional[Path],
        mx_path: Optional[Path],
        me_path: Optional[Path],
        scene_intent: Optional[SceneMixIntent],
        attention_map: Optional[AttentionMap],
    ) -> CategoryResult:
        from audiobook_factory.cinematic_mix.rules import check_dialogue_focus
        return check_dialogue_focus(self._measure_vocal_corridor_db, dx_path, mx_path, me_path, scene_intent, attention_map)

    def _check_music_integration(
        self,
        mx_path: Optional[Path],
        dx_path: Optional[Path],
        scene_intent: Optional[SceneMixIntent],
        mix_automation: Optional[MixAutomation],
    ) -> CategoryResult:
        from audiobook_factory.cinematic_mix.rules import check_music_integration
        return check_music_integration(self.analyzer, mx_path, dx_path, scene_intent, mix_automation)

    def _check_fx_clarity(
        self,
        fx_path: Optional[Path],
        impact_events: Optional[List[ImpactEvent]],
        scene_intent: Optional[SceneMixIntent],
    ) -> CategoryResult:
        from audiobook_factory.cinematic_mix.rules import check_fx_clarity
        return check_fx_clarity(self.analyzer, fx_path, impact_events, scene_intent)

    def _check_ambience_naturalism(
        self,
        amb_path: Optional[Path],
        dx_path: Optional[Path],
        silence_events: Optional[List[SilenceEvent]],
        scene_intent: Optional[SceneMixIntent],
    ) -> CategoryResult:
        from audiobook_factory.cinematic_mix.rules import check_ambience_naturalism
        return check_ambience_naturalism(self.analyzer, amb_path, dx_path, silence_events, scene_intent)

    def _check_dynamic_contrast(
        self,
        premaster: Optional[Path],
        scene_intent: Optional[SceneMixIntent],
    ) -> CategoryResult:
        from audiobook_factory.cinematic_mix.rules import check_dynamic_contrast
        return check_dynamic_contrast(self.analyzer, premaster, scene_intent)

    def _check_spatial_coherence(
        self,
        premaster: Optional[Path],
        dx_path: Optional[Path],
        perspective: Optional[AcousticPerspective],
        mix_automation: Optional[MixAutomation],
    ) -> CategoryResult:
        from audiobook_factory.cinematic_mix.rules import check_spatial_coherence
        return check_spatial_coherence(self.analyzer, premaster, dx_path, perspective, mix_automation)

    def _check_masking_ducking(
        self,
        dx_path: Optional[Path],
        mx_path: Optional[Path],
        mix_automation: Optional[MixAutomation],
    ) -> CategoryResult:
        from audiobook_factory.cinematic_mix.rules import check_masking_ducking
        return check_masking_ducking(dx_path, mx_path, mix_automation)

    def _check_silence_behavior(
        self,
        premaster: Optional[Path],
        stems: Dict[str, Path],
        silence_events: Optional[List[SilenceEvent]],
    ) -> CategoryResult:
        from audiobook_factory.cinematic_mix.rules import check_silence_behavior
        return check_silence_behavior(self.analyzer, premaster, stems, silence_events)

    def _check_impact_behavior(
        self,
        premaster: Optional[Path],
        fx_path: Optional[Path],
        mx_path: Optional[Path],
        impact_events: Optional[List[ImpactEvent]],
    ) -> CategoryResult:
        from audiobook_factory.cinematic_mix.rules import check_impact_behavior
        return check_impact_behavior(self.analyzer, premaster, fx_path, mx_path, impact_events)

    def _check_transition_quality(
        self,
        premaster: Optional[Path],
        mix_automation: Optional[MixAutomation],
    ) -> CategoryResult:
        from audiobook_factory.cinematic_mix.rules import check_transition_quality
        return check_transition_quality(premaster, mix_automation)

    def _check_cinematic_intent(
        self,
        stems: Dict[str, Path],
        scene_intent: Optional[SceneMixIntent],
        attention_map: Optional[AttentionMap],
    ) -> CategoryResult:
        from audiobook_factory.cinematic_mix.rules import check_cinematic_intent
        return check_cinematic_intent(stems, scene_intent, attention_map)

    # -------------------------------------------------------------------------
    # Result Synthesis & Actionable RemixPlan
    # -------------------------------------------------------------------------

    def _synthesize_result(
        self,
        category_results: List[CategoryResult],
        iteration: int = 1,
    ) -> MixJudgeResult:
        """Synthesizes category results into overall status, actionable diagnoses, and remix plan."""
        failures: List[str] = []
        warnings: List[str] = []
        diagnoses: List[MixDiagnosis] = []
        remix_actions: List[RemixAction] = []

        has_hard_fail = False
        has_remix = False
        has_warnings = False

        total_weight = 0.0
        weighted_score = 0.0

        for cat in category_results:
            w = 2.0 if cat.critical or cat.name in ("technical_safety", "dialogue_focus") else 1.0
            total_weight += w
            weighted_score += cat.score * w

            if cat.status == "FAIL":
                has_hard_fail = True
                failures.append(f"[{cat.name}] {cat.reason}")
                diagnoses.append(
                    MixDiagnosis(
                        category=cat.name,
                        status="FAIL",
                        reason=cat.reason,
                        evidence=cat.evidence,
                        likely_cause="Technical audio corruption, clipping, or missing stem.",
                        recommended_action="Halt pipeline and inspect upstream render logs.",
                    )
                )

            elif cat.status == "REMIX":
                has_remix = True
                failures.append(f"[{cat.name}] {cat.reason}")
                diag, act = self._map_category_to_remediation(cat)
                diagnoses.append(diag)
                if act:
                    remix_actions.append(act)

            elif cat.status == "PASS_WITH_WARNINGS":
                has_warnings = True
                warnings.append(f"[{cat.name}] {cat.reason}")

        overall_score = round(weighted_score / max(1.0, total_weight), 3)

        if has_hard_fail:
            status: JudgeStatus = "FAIL"
            rec_action = "HALT"
        elif has_remix:
            status = "REMIX"
            rec_action = "REMIX"
        elif has_warnings:
            status = "PASS_WITH_WARNINGS"
            rec_action = "PROCEED"
        else:
            status = "PASS"
            rec_action = "PROCEED"

        remix_plan = None
        if status == "REMIX":
            remix_plan = RemixPlan(
                actions=remix_actions,
                bounded_iteration=iteration,
                convergence_score=overall_score,
                explanation=f"Generated {len(remix_actions)} actionable mixing remediation(s) to resolve cinematic mismatches.",
            )

        return MixJudgeResult(
            status=status,
            overall_score=overall_score,
            category_results=category_results,
            failures=failures,
            warnings=warnings,
            diagnosis=diagnoses,
            remix_plan=remix_plan,
            recommended_action=rec_action,
            evidence={cat.name: cat.evidence for cat in category_results},
        )

    def _map_category_to_remediation(
        self,
        cat: CategoryResult,
    ) -> Tuple[MixDiagnosis, Optional[RemixAction]]:
        """Maps an individual category REMIX into a structured diagnosis and actionable RemixAction."""
        from audiobook_factory.cinematic_mix.remediation_planner import map_category_to_remediation
        return map_category_to_remediation(cat)

