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
    # Category Implementations
    # -------------------------------------------------------------------------

    def _check_technical_safety(
        self,
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

        loudness = self.analyzer.probe_loudness(premaster)
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
        format_facts = self.analyzer.probe_format(premaster)
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
        phase_audit = self._get_phase_audit(premaster)
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

    def _check_dialogue_focus(
        self,
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

        # Measure Dialogue-to-Music Ratio (DMR) in vocal corridor (300Hz-3.5kHz) with cache
        dx_corridor_db = self._measure_vocal_corridor_db(dx_path)
        mx_corridor_db = self._measure_vocal_corridor_db(competing_stem)
        dmr_db = round(dx_corridor_db - mx_corridor_db, 2)

        evidence["measured_dmr_db"] = dmr_db
        evidence["dialogue_corridor_db"] = dx_corridor_db
        evidence["music_corridor_db"] = mx_corridor_db
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

        # If scene explicitly focuses on music (e.g. dramatic musical score swell),
        # low DMR is allowed and intended!
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

    def _check_music_integration(
        self,
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

        mx_loudness = self.analyzer.probe_loudness(mx_path)
        evidence["music_integrated_lufs"] = mx_loudness.integrated_lufs
        evidence["music_peak_dbtp"] = mx_loudness.true_peak_dbtp

        is_music_focus = bool(scene_intent and scene_intent.focus == "music")

        # 1. Over-ducking check
        # If music is ducked so hard it is practically muted (< -45 LUFS) when it shouldn't be
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
            # Count rapid separate ducking pulses (gap < 0.20s with substantial depth > 4.0 dB)
            rapid_oscillations = 0
            for i in range(len(mx_events) - 1):
                gap = round(mx_events[i+1].start - mx_events[i].end, 4)
                # Contiguous phases of the same behavior event touch seamlessly (gap == 0)
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

    def _check_fx_clarity(
        self,
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

        fx_loudness = self.analyzer.probe_loudness(fx_path)
        evidence["fx_peak_level_db"] = fx_loudness.peak_level_db
        evidence["fx_rms_level_db"] = fx_loudness.rms_level_db

        # If high-intensity impacts were scheduled, verify FX has acoustic energy
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

    def _check_ambience_naturalism(
        self,
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

        amb_loudness = self.analyzer.probe_loudness(amb_path)
        evidence["ambience_integrated_lufs"] = amb_loudness.integrated_lufs
        evidence["ambience_rms_db"] = amb_loudness.rms_level_db

        # If dialogue exists, check that ambience is not sterilized down to digital silence (< -60 dB)
        # unless an intentional near-black SHOCK silence was scheduled
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

    def _check_dynamic_contrast(
        self,
        premaster: Optional[Path],
        scene_intent: Optional[SceneMixIntent],
    ) -> CategoryResult:
        """Evaluates whether rendered dynamic range matches scene dynamic range intent."""
        evidence: Dict[str, Any] = {}
        if not premaster or not premaster.exists():
            return CategoryResult(name="dynamic_contrast", status="PASS", score=1.0, reason="Premaster not found.")

        loudness = self.analyzer.probe_loudness(premaster)
        lra = loudness.loudness_range_lu or 5.0
        dr = loudness.dynamic_range_db or 12.0
        evidence["loudness_range_lu"] = lra
        evidence["dynamic_range_db"] = dr

        intent_preset = scene_intent.dynamic_range_intent if scene_intent else "standard"
        evidence["intent_preset"] = intent_preset

        # If wide/high dynamic range was requested (e.g. combat/epic)
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

    def _check_spatial_coherence(
        self,
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

    def _check_masking_ducking(
        self,
        dx_path: Optional[Path],
        mx_path: Optional[Path],
        mix_automation: Optional[MixAutomation],
    ) -> CategoryResult:
        """Evaluates dynamic masking and sidechain ducking guardrails."""
        evidence: Dict[str, Any] = {}
        if not mix_automation:
            return CategoryResult(name="masking_ducking", status="PASS", score=1.0, reason="No automation events.")

        # Check guardrail limits across all automation events
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

    def _check_silence_behavior(
        self,
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
                amb_loudness = self.analyzer.probe_loudness(stems["AMB"])
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

    def _check_impact_behavior(
        self,
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

    def _check_transition_quality(
        self,
        premaster: Optional[Path],
        mix_automation: Optional[MixAutomation],
    ) -> CategoryResult:
        """Evaluates boundary transitions for clicks, dc-offsets, and gain discontinuities."""
        evidence: Dict[str, Any] = {}
        if not premaster or not premaster.exists():
            return CategoryResult(name="transition_quality", status="PASS", score=1.0, reason="Premaster not found.")

        # Check for un-smoothed step changes in automation
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

    def _check_cinematic_intent(
        self,
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

        # Verify that intended focus exists as an active stem
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
        if cat.name == "dialogue_focus":
            dmr = cat.evidence.get("measured_dmr_db", 0.0)
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
