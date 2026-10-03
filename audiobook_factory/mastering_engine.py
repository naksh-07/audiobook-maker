#!/usr/bin/env python3
"""
Audiobook Factory - Stage 12: Mastering V2 Deterministic Engine.
================================================================
Implements the P0 Mastering Core engine:
- Subsonic highpass filtering (28Hz rumble cut).
- Dual-pass measured linear EBU R128 loudnorm (avoids dynamic pumping on mixed audio).
- Lookahead peak limiter with transparent brickwall protection.
- High-precision Kaiser windowed sinc resampling with TPDF dither.
- Closed-loop verification with MasteringAnalyzer and MasteringQCAgent.
- Bounded remediation retry loop (max_retries=2).
- Provenance ledger persistence (chapter_XXX_mastering_ledger.json).
"""

from __future__ import annotations
import datetime
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

from audiobook_factory.logger import logger
from audiobook_factory.mastering_contracts import (
    MasteringProfile,
    MasteringAnalysisFacts,
    MasteringQCResult,
    MasteringRequest,
    MasteringResult,
    MasteringLedger,
    MasteringActionPlan,
    DialogueProtectionReport,
    ChapterConsistencyAudit,
    PerceptualEvaluation,
    ReferenceProfile,
    ReferenceComparisonResult,
    SceneMasteringDecision,
    FinalCertificationReport,
    FinalArtifactInfo,
)
from audiobook_factory.mastering_analyzer import MasteringAnalyzer
from audiobook_factory.mastering_qc import MasteringQCAgent
from audiobook_factory.mastering_judge import MasteringJudge
from audiobook_factory.dialogue_protection import DialogueProtectionAgent
from audiobook_factory.chapter_consistency import ChapterConsistencyAuditor
from audiobook_factory.perceptual_critic import PerceptualCritic
from audiobook_factory.reference_mastering import ReferenceMasteringAuditor
from audiobook_factory.scene_aware_engine import SceneAwareDecisionEngine
from audiobook_factory.mastering_certification import MasteringCertifier

MASTERING_ENGINE_VERSION = "2.2.0"


class MasteringEngineV2:
    """
    Stage 12 Mastering Engine executing deterministic dual-pass mastering
    and closed-loop QC verification for audio drama production.
    """

    def __init__(
        self,
        analyzer: Optional[MasteringAnalyzer] = None,
        qc_agent: Optional[MasteringQCAgent] = None,
        judge: Optional[MasteringJudge] = None,
        dialogue_agent: Optional[DialogueProtectionAgent] = None,
        consistency_auditor: Optional[ChapterConsistencyAuditor] = None,
        scene_engine: Optional[SceneAwareDecisionEngine] = None,
        perceptual_critic: Optional[PerceptualCritic] = None,
        reference_auditor: Optional[ReferenceMasteringAuditor] = None,
        certifier: Optional[MasteringCertifier] = None,
        ffmpeg_bin: Optional[str] = None,
    ):
        self.ffmpeg = ffmpeg_bin or shutil.which("ffmpeg") or "ffmpeg"
        self.analyzer = analyzer or MasteringAnalyzer(ffmpeg_bin=self.ffmpeg)
        self.qc_agent = qc_agent or MasteringQCAgent()
        self.judge = judge or MasteringJudge()
        self.dialogue_agent = dialogue_agent or DialogueProtectionAgent()
        self.consistency_auditor = consistency_auditor or ChapterConsistencyAuditor()
        self.scene_engine = scene_engine or SceneAwareDecisionEngine()
        self.perceptual_critic = perceptual_critic or PerceptualCritic()
        self.reference_auditor = reference_auditor or ReferenceMasteringAuditor()
        self.certifier = certifier or MasteringCertifier()
        self.version = MASTERING_ENGINE_VERSION
        self._ffmpeg_version = self._detect_ffmpeg_version()

    def _detect_ffmpeg_version(self) -> str:
        """Detects and returns FFmpeg version banner string."""
        try:
            res = subprocess.run([self.ffmpeg, "-version"], capture_output=True, text=True, timeout=5.0)
            first_line = res.stdout.splitlines()[0] if res.stdout else "ffmpeg unknown"
            return first_line.strip()
        except Exception:
            return "ffmpeg unknown"

    def _compute_sha256(self, file_path: Union[str, Path]) -> str:
        """Computes SHA-256 hex digest of a physical file."""
        p = Path(file_path).resolve()
        if not p.exists():
            return "file_missing"
        h = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def _measure_loudnorm_pass1(
        self,
        audio_path: Path,
        target_lufs: float,
        profile: MasteringProfile,
    ) -> Dict[str, str]:
        """
        Executes Pass 1 measurement run of EBU R128 loudnorm with subsonic filtering.
        Returns parsed dictionary of measured stats: input_i, input_tp, input_lra, input_thresh, target_offset.
        """
        cmd_pass1 = [
            self.ffmpeg, "-y",
            "-i", str(audio_path.resolve()),
            "-af", (
                f"highpass=f={profile.subsonic_highpass_hz},"
                f"loudnorm=I={target_lufs:.1f}:TP={profile.true_peak_ceiling_dbtp:.1f}:"
                f"LRA={profile.target_lra:.1f}:print_format=json"
            ),
            "-f", "null", "-",
        ]
        proc = subprocess.run(cmd_pass1, capture_output=True, text=True, errors="ignore", timeout=600.0)
        if proc.returncode != 0:
            raise RuntimeError(f"Pass 1 loudnorm execution failed on {audio_path.name} (code {proc.returncode}): {proc.stderr[-300:]}")

        match = re.search(r"\{[\s\S]*?\"input_i\"[\s\S]*?\}", proc.stderr)
        if not match:
            raise RuntimeError(f"Pass 1 loudnorm failed to parse JSON on {audio_path.name}: {proc.stderr[-300:]}")

        try:
            stats = json.loads(match.group(0))
        except Exception as e:
            raise RuntimeError(f"Failed to decode Pass 1 loudnorm JSON on {audio_path.name}: {e}")

        required_keys = ["input_i", "input_tp", "input_lra", "input_thresh", "target_offset"]
        missing_keys = [k for k in required_keys if k not in stats]
        if missing_keys:
            raise RuntimeError(f"Pass 1 loudnorm JSON missing keys {missing_keys} on {audio_path.name}: {stats}")

        return {k: str(stats[k]) for k in required_keys}

    def _render_master(
        self,
        premaster_path: Path,
        output_path: Path,
        profile: MasteringProfile,
        target_lufs: float,
        limiter_ceiling_db: float,
        pass1_stats: Dict[str, str],
    ) -> Path:
        """
        Executes Pass 2 deterministic linear rendering:
        Subsonic Highpass -> Measured Linear Loudnorm -> Lookahead Limiter -> Kaiser Sinc Resample + TPDF.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Convert limiter ceiling from dBFS to linear factor (e.g. -1.6 dBFS -> ~0.8318)
        lim_linear = min(1.0, max(0.0625, 10.0 ** (limiter_ceiling_db / 20.0)))

        # Dither method mapping
        dither_method = "triangular"
        if profile.dither_type.lower() == "triangular_hp":
            dither_method = "triangular_hp"
        elif profile.dither_type.lower() == "none":
            dither_method = "none"

        is_silent = (
            pass1_stats.get("input_i") in ("-inf", "inf")
            or float(pass1_stats.get("input_i", 0.0)) <= -69.0
        )

        filter_chain_parts = [f"highpass=f={profile.subsonic_highpass_hz}"]

        if profile.enable_dual_pass_linear and not is_silent:
            loudnorm_filter = (
                f"loudnorm=I={target_lufs:.1f}:TP={profile.true_peak_ceiling_dbtp:.1f}:"
                f"LRA={profile.target_lra:.1f}:"
                f"measured_I={pass1_stats['input_i']}:"
                f"measured_TP={pass1_stats['input_tp']}:"
                f"measured_LRA={pass1_stats['input_lra']}:"
                f"measured_thresh={pass1_stats['input_thresh']}:"
                f"offset={pass1_stats['target_offset']}:"
                f"linear=true"
            )
            filter_chain_parts.append(loudnorm_filter)
        else:
            # Fallback or silent pass
            loudnorm_filter = (
                f"loudnorm=I={target_lufs:.1f}:TP={profile.true_peak_ceiling_dbtp:.1f}:"
                f"LRA={profile.target_lra:.1f}"
            )
            filter_chain_parts.append(loudnorm_filter)

        filter_chain_parts.append(
            f"alimiter=limit={lim_linear:.4f}:attack=5:release={profile.limiter_release_ms}:asc=0:level=0"
        )

        if dither_method == "none":
            filter_chain_parts.append(
                f"aresample=osr={profile.output_sample_rate}:filter_type=kaiser"
            )
        else:
            filter_chain_parts.append(
                f"aresample=osr={profile.output_sample_rate}:filter_type=kaiser:dither_method={dither_method}"
            )

        filter_chain = ",".join(filter_chain_parts)

        cmd_pass2 = [
            self.ffmpeg, "-y",
            "-i", str(premaster_path.resolve()),
            "-af", filter_chain,
            "-ac", str(profile.output_channels),
            "-ar", str(profile.output_sample_rate),
            "-c:a", "pcm_s24le",
            str(output_path.resolve()),
        ]

        proc = subprocess.run(cmd_pass2, capture_output=True, text=True, errors="ignore", timeout=600.0)
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg master pass 2 failed (code {proc.returncode}): {proc.stderr[-400:]}")

        return output_path

    def master(self, request: MasteringRequest) -> MasteringResult:
        """
        Executes the complete Stage 12 Mastering workflow:
        1. Pre-master analysis.
        2. Closed-loop render and analysis with bounded remediation.
        3. Quality Control (QC) verification.
        4. Provenance tracking and ledger serialization.
        """
        premaster_path = Path(request.premaster_path).resolve()
        if not premaster_path.exists():
            raise FileNotFoundError(f"Premaster audio file does not exist: {premaster_path}")

        # Idempotency / Double-master protection
        if not request.is_premaster:
            raise ValueError(f"Double-master protection: input is flagged as already mastered: {premaster_path}")

        # Target output path
        if request.output_master_path:
            master_path = Path(request.output_master_path).resolve()
        else:
            master_path = premaster_path.parent / f"{request.chapter_id}_cinema_master.wav"

        profile = request.profile
        premaster_sha256 = self._compute_sha256(premaster_path)
        profile_sha256 = hashlib.sha256(profile.model_dump_json().encode("utf-8")).hexdigest()

        # Step 1: Pre-master Analysis
        analysis_before = self.analyzer.analyze(
            premaster_path,
            dialogue_stem_path=request.dialogue_stem_path,
        )

        # Fail-closed guard: invalid or empty premaster input
        if not analysis_before.is_valid_audio or analysis_before.duration_sec <= 0.0:
            qc_fail = MasteringQCResult(
                status="FAIL",
                passed=False,
                checks={"audio_integrity": "FAIL"},
                failures=["premaster_audio_integrity_failed_empty_or_corrupt"],
                warnings=[],
                details={"input_premaster": str(premaster_path)},
            )
            return MasteringResult(
                status="FAILED",
                chapter_id=request.chapter_id,
                premaster_path=str(premaster_path),
                master_path=str(master_path),
                profile=profile,
                analysis_before=analysis_before,
                analysis_after=None,
                qc_result=qc_fail,
                iteration_count=1,
                provenance={
                    "engine": "MasteringEngineV2",
                    "engine_version": self.version,
                    "ffmpeg_version": self._ffmpeg_version,
                    "premaster_sha256": premaster_sha256,
                    "profile_sha256": profile_sha256,
                },
                error_message="Input premaster audio is empty or corrupt.",
            )

        dialogue_facts = None
        if request.dialogue_stem_path and Path(request.dialogue_stem_path).exists():
            dialogue_facts = self.analyzer.analyze(request.dialogue_stem_path)

        # Step 1.4: Scene-Aware Decision Engine
        scene_decision = self.scene_engine.evaluate_scene(
            facts=analysis_before,
            scene_intent=request.scene_intent,
            book_profile=request.book_profile,
            chapter_metadata=request.metadata,
        )
        profile_with_scene = self.scene_engine.apply_scene_adjustments(profile, scene_decision)

        # Step 1.5: Stage 12 Forensic Mastering Judge Evaluation
        action_plan = self.judge.evaluate(
            premaster_facts=analysis_before,
            dialogue_facts=dialogue_facts,
            profile=profile_with_scene,
            book_profile=request.book_profile,
            scene_intent=request.scene_intent,
            chapter_id=request.chapter_id,
        )

        if action_plan.overall_verdict == "REJECT":
            qc_fail = MasteringQCResult(
                status="FAIL",
                passed=False,
                checks={"mastering_judge": "FAIL"},
                failures=[f"judge_rejected: {action_plan.explanation}"],
                warnings=[],
                details={"action_plan": action_plan.model_dump()},
            )
            return MasteringResult(
                status="FAILED",
                chapter_id=request.chapter_id,
                premaster_path=str(premaster_path),
                master_path=str(master_path),
                profile=profile,
                analysis_before=analysis_before,
                analysis_after=None,
                qc_result=qc_fail,
                action_plan=action_plan,
                iteration_count=1,
                provenance={
                    "engine": "MasteringEngineV2",
                    "engine_version": self.version,
                    "ffmpeg_version": self._ffmpeg_version,
                    "premaster_sha256": premaster_sha256,
                    "profile_sha256": profile_sha256,
                },
                error_message=f"MasteringJudge rejected premaster: {action_plan.explanation}",
            )

        # Apply bounded profile override if recommended by Judge
        active_profile = (
            action_plan.adjusted_profile
            if (action_plan.overall_verdict == "ADJUST" and action_plan.adjusted_profile)
            else profile_with_scene
        )
        if action_plan.overall_verdict == "ADJUST":
            logger.info(f"[*] MasteringJudge applied bounded profile adjustments: {action_plan.explanation}")

        # Step 2: Closed-Loop Mastering & Remediation Loop
        target_lufs = active_profile.target_lufs
        limiter_ceiling_db = active_profile.limiter_ceiling_db
        initial_profile_sha256 = profile_sha256
        remediation_actions: List[Dict[str, Any]] = []
        attempts_history: List[Dict[str, Any]] = []
        analysis_after: Optional[MasteringAnalysisFacts] = None
        qc_result: Optional[MasteringQCResult] = None
        iterations_run = 0
        winning_attempt = 1

        max_attempts = 1 + active_profile.max_retries

        for attempt in range(1, max_attempts + 1):
            iterations_run = attempt
            winning_attempt = attempt
            logger.info(
                f"[*] Stage 12 Mastering (Attempt {attempt}/{max_attempts}) for {request.chapter_id} "
                f"[Target: {target_lufs:.1f} LUFS, Limiter: {limiter_ceiling_db:.1f} dBFS]..."
            )

            try:
                # Pass 1: Measure
                pass1_stats = self._measure_loudnorm_pass1(
                    audio_path=premaster_path,
                    target_lufs=target_lufs,
                    profile=active_profile,
                )

                # Pass 2: Render
                self._render_master(
                    premaster_path=premaster_path,
                    output_path=master_path,
                    profile=active_profile,
                    target_lufs=target_lufs,
                    limiter_ceiling_db=limiter_ceiling_db,
                    pass1_stats=pass1_stats,
                )

                self.analyzer.clear_cache()
                # Analyze Rendered Deliverable
                analysis_after = self.analyzer.analyze(
                    master_path,
                    dialogue_stem_path=request.dialogue_stem_path,
                )

                # QC Audit
                qc_result = self.qc_agent.evaluate(
                    master_facts=analysis_after,
                    premaster_facts=analysis_before,
                    dialogue_facts=dialogue_facts,
                    profile=active_profile,
                )
            except Exception as e:
                logger.error(f"[!] Stage 12 Mastering render failed on attempt {attempt}: {e}")
                self.analyzer.clear_cache()
                analysis_after = self.analyzer.analyze(
                    master_path if master_path.exists() else premaster_path,
                    dialogue_stem_path=request.dialogue_stem_path,
                )
                qc_result = MasteringQCResult(
                    status="FAIL",
                    passed=False,
                    checks={"dsp_render": "FAIL"},
                    failures=[f"mastering_dsp_render_failed: {str(e)[:150]}"],
                    warnings=[],
                    details={"error": str(e)},
                )

            attempts_history.append({
                "attempt": attempt,
                "target_lufs": target_lufs,
                "limiter_ceiling_db": limiter_ceiling_db,
                "qc_passed": qc_result.passed if qc_result else False,
                "qc_status": qc_result.status if qc_result else "FAIL",
                "integrated_lufs": analysis_after.integrated_lufs if analysis_after else None,
                "true_peak_dbtp": analysis_after.true_peak_dbtp if analysis_after else None,
                "failures": qc_result.failures if qc_result else [],
            })

            if qc_result.passed:
                logger.info(
                    f"[+] Stage 12 Mastering QC {qc_result.status} for {request.chapter_id} "
                    f"in {attempt} pass(es) (LUFS: {analysis_after.integrated_lufs:.2f}, TP: {analysis_after.true_peak_dbtp} dBTP)"
                )
                break

            # Attempt Remediation if retries remain
            if attempt < max_attempts:
                remediated = False
                # Remediation 1: Loudness deviation
                measured_lufs = qc_result.details.get("measured_integrated_lufs", analysis_after.integrated_lufs)
                if measured_lufs is not None:
                    lufs_diff = measured_lufs - active_profile.target_lufs
                    if qc_result.checks.get("loudness") in ("FAIL", "WARN") or abs(lufs_diff) > active_profile.tolerance_lu:
                        # Adjust target offset inverse to measured delta with bounded feedback
                        adjustment = lufs_diff if abs(lufs_diff) > 0.05 else 0.5
                        bounded_adj = max(-5.0, min(5.0, adjustment))
                        new_target = max(-35.0, min(-10.0, round(target_lufs - bounded_adj, 2)))
                        remediation_actions.append({
                            "attempt": attempt,
                            "type": "loudness_offset_compensation",
                            "measured_lufs": measured_lufs,
                            "target_lufs_before": target_lufs,
                            "target_lufs_adjusted": new_target,
                        })
                        target_lufs = new_target
                        remediated = True

                # Remediation 2: True peak overshoot
                tp = qc_result.details.get("measured_true_peak_dbtp", analysis_after.true_peak_dbtp)
                if qc_result.checks.get("true_peak") in ("FAIL", "WARN") or (tp is not None and tp > active_profile.true_peak_ceiling_dbtp):
                    overshoot = (tp - active_profile.true_peak_ceiling_dbtp) if tp is not None else 0.3
                    new_limiter = round(limiter_ceiling_db - max(0.3, overshoot + 0.2), 2)
                    new_limiter = max(-3.5, new_limiter)
                    remediation_actions.append({
                        "attempt": attempt,
                        "type": "limiter_ceiling_backoff",
                        "measured_true_peak": tp,
                        "limiter_before": limiter_ceiling_db,
                        "limiter_adjusted": new_limiter,
                    })
                    limiter_ceiling_db = new_limiter
                    remediated = True

                if not remediated:
                    logger.warning(
                        f"[!] Stage 12 Mastering failure on attempt {attempt} has no DSP parameter remedy: {qc_result.failures}"
                    )
                    break
            else:
                logger.error(
                    f"[!] Stage 12 Mastering retries exhausted for {request.chapter_id}: {qc_result.failures}"
                )

        # Step 3: Post-Master Forensic Intelligence
        assert analysis_after is not None
        assert qc_result is not None

        dialogue_report = self.dialogue_agent.evaluate(
            mix_facts=analysis_after,
            dialogue_facts=dialogue_facts,
            scene_intent=request.scene_intent,
            chapter_id=request.chapter_id,
        )

        consistency_audit = None
        if request.book_profile:
            consistency_audit = self.consistency_auditor.audit_chapter(
                chapter_facts=analysis_after,
                book_profile=request.book_profile,
                dialogue_facts=dialogue_facts,
                scene_intent=request.scene_intent,
                chapter_id=request.chapter_id,
            )

        # Step 3.5: Optional Reference Comparison
        reference_comp = None
        if request.reference_profile is not None:
            reference_comp = self.reference_auditor.compare_to_reference(
                facts=analysis_after,
                reference=request.reference_profile,
                scene_type=scene_decision.scene_type,
            )

        # Step 3.6: Perceptual Critic Evaluation
        perceptual_eval = self.perceptual_critic.evaluate(
            facts=analysis_after,
            judge_issues=action_plan.issues if action_plan else [],
            book_profile=request.book_profile,
            scene_intent=request.scene_intent,
            dialogue_report=dialogue_report,
        )

        # Step 3.7: Multi-Pass Perceptual Review & Reversion Guard
        if (
            request.allow_perceptual_multipass
            and perceptual_eval.overall == "WARN"
            and iterations_run < max_attempts
            and master_path.exists()
        ):
            fatigue_issues = [i for i in perceptual_eval.issues if i.dimension == "fatigue_risk" and i.confidence >= 0.80]
            if fatigue_issues:
                logger.info(
                    f"[*] Perceptual multi-pass review triggered for {request.chapter_id}: {fatigue_issues[0].description}"
                )
                backup_master_path = master_path.with_suffix(".p4_bak.wav")
                try:
                    shutil.copy2(master_path, backup_master_path)
                    corrective_target_lufs = round(target_lufs - 0.4, 2)
                    corrective_profile = MasteringProfile(
                        **{
                            **active_profile.model_dump(),
                            "target_lufs": corrective_target_lufs,
                            "limiter_release_ms": min(active_profile.limiter_release_ms + 20, 150),
                        }
                    )
                    pass1_c = self._measure_loudnorm_pass1(premaster_path, corrective_target_lufs, corrective_profile)
                    self._render_master(
                        premaster_path, master_path, corrective_profile, corrective_target_lufs, limiter_ceiling_db, pass1_c
                    )

                    self.analyzer.clear_cache()
                    new_analysis = self.analyzer.analyze(master_path, dialogue_stem_path=request.dialogue_stem_path)
                    new_qc = self.qc_agent.evaluate(new_analysis, analysis_before, dialogue_facts, corrective_profile)
                    new_eval = self.perceptual_critic.evaluate(
                        facts=new_analysis,
                        judge_issues=action_plan.issues if action_plan else [],
                        book_profile=request.book_profile,
                        scene_intent=request.scene_intent,
                        dialogue_report=dialogue_report,
                        previous_eval=perceptual_eval,
                    )

                    # Reversion guard: only accept if QC passes and aesthetic scores did not degrade
                    if new_qc.passed and (min(new_eval.scores.values()) >= min(perceptual_eval.scores.values())):
                        logger.info(f"[+] Perceptual multi-pass accepted: improved aesthetic score for {request.chapter_id}")
                        self.analyzer.clear_cache()
                        analysis_after = new_analysis
                        qc_result = new_qc
                        # Invalidate stale reports from MASTER A and completely re-evaluate on MASTER B
                        dialogue_report = self.dialogue_agent.evaluate(
                            mix_facts=analysis_after,
                            dialogue_facts=dialogue_facts,
                            scene_intent=request.scene_intent,
                            chapter_id=request.chapter_id,
                        )
                        if request.book_profile:
                            consistency_audit = self.consistency_auditor.audit_chapter(
                                chapter_facts=analysis_after,
                                book_profile=request.book_profile,
                                dialogue_facts=dialogue_facts,
                                scene_intent=request.scene_intent,
                                chapter_id=request.chapter_id,
                            )
                        if request.reference_profile is not None:
                            reference_comp = self.reference_auditor.compare_to_reference(
                                facts=analysis_after,
                                reference=request.reference_profile,
                                scene_type=scene_decision.scene_type,
                            )
                        perceptual_eval = new_eval
                        iterations_run += 1
                        winning_attempt = iterations_run
                        active_profile = corrective_profile
                        attempts_history.append({
                            "attempt": iterations_run,
                            "type": "p4_perceptual_refinement",
                            "target_lufs": corrective_target_lufs,
                            "limiter_ceiling_db": limiter_ceiling_db,
                            "qc_passed": new_qc.passed,
                            "qc_status": new_qc.status,
                            "integrated_lufs": new_analysis.integrated_lufs,
                            "true_peak_dbtp": new_analysis.true_peak_dbtp,
                        })
                    else:
                        logger.info(f"[!] Perceptual multi-pass reverted: correction did not improve audio, restoring previous master.")
                        shutil.copy2(backup_master_path, master_path)
                        self.analyzer.clear_cache()
                finally:
                    if backup_master_path.exists():
                        backup_master_path.unlink(missing_ok=True)

        # Step 4: Final Certification Arbiter with Physical Artifact Authority
        master_sha256 = self._compute_sha256(master_path) if master_path.exists() else "render_failed"
        effective_profile_sha256 = hashlib.sha256(active_profile.model_dump_json().encode("utf-8")).hexdigest()

        artifact_info = None
        if master_path.exists() and master_sha256 != "render_failed":
            st = master_path.stat()
            artifact_info = FinalArtifactInfo(
                filepath=str(master_path),
                sha256=master_sha256,
                size_bytes=st.st_size,
                duration_sec=analysis_after.duration_sec if analysis_after else 0.0,
                sample_rate=analysis_after.sample_rate if analysis_after else 48000,
                channels=analysis_after.channels if analysis_after else 2,
                bit_depth=16,
                audio_format="wav",
                analyzer_version=self.analyzer.version,
                mastering_version=self.version,
                certifier_version=self.certifier.version,
            )

        cert_report = self.certifier.certify(
            chapter_id=request.chapter_id,
            qc_result=qc_result,
            dialogue_report=dialogue_report,
            consistency_audit=consistency_audit,
            perceptual_eval=perceptual_eval,
            reference_comp=reference_comp,
            artifact_info=artifact_info,
            provenance={
                "engine": "MasteringEngineV2",
                "engine_version": self.version,
                "ffmpeg_version": self._ffmpeg_version,
                "premaster_sha256": premaster_sha256,
                "master_sha256": master_sha256,
                "initial_profile_sha256": initial_profile_sha256,
                "effective_profile_sha256": effective_profile_sha256,
            },
        )

        # Final Status determination (Strict Conservative Precedence)
        if not qc_result.passed and iterations_run > 1:
            status = "RETRY_EXHAUSTED"
            error_msg = f"Mastering QC failed after {iterations_run} passes: {', '.join(qc_result.failures)}"
        elif cert_report.certification == "REJECTED":
            status = "FAILED"
            first_ev = cert_report.review_items[0].get("evidence") if cert_report.review_items else "Critical defect"
            error_msg = f"Mastering certification REJECTED: {first_ev}"
        elif cert_report.certification == "REVIEW_REQUIRED":
            status = "REVIEW_REQUIRED"
            first_item = cert_report.review_items[0] if cert_report.review_items else {}
            error_msg = f"Mastering requires human review: {first_item.get('evidence', 'Uncertain acoustic presentation')}"
        elif not qc_result.passed:
            status = "FAILED"
            error_msg = f"Mastering QC failed: {', '.join(qc_result.failures)}"
        elif dialogue_report.status == "FAIL":
            status = "FAILED"
            error_msg = f"Dialogue protection critical failure: {dialogue_report.masking_risk} speech masking risk"
        elif cert_report.certification in ("CERTIFIED", "WARNINGS"):
            status = "SUCCESS"
            error_msg = None
        else:
            status = "FAILED"
            error_msg = f"Unknown certification state: {cert_report.certification}"

        provenance = {
            "engine": "MasteringEngineV2",
            "engine_version": self.version,
            "ffmpeg_version": self._ffmpeg_version,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "premaster_path": str(premaster_path),
            "premaster_sha256": premaster_sha256,
            "master_path": str(master_path),
            "master_sha256": master_sha256,
            "profile_name": active_profile.profile_name,
            "profile_sha256": effective_profile_sha256,
            "initial_profile_sha256": initial_profile_sha256,
            "effective_profile_sha256": effective_profile_sha256,
            "iteration_count": iterations_run,
            "winning_attempt": winning_attempt,
            "attempts_history": attempts_history,
            "remediation_actions": remediation_actions,
            "judge_verdict": action_plan.overall_verdict,
            "dialogue_protection_status": dialogue_report.status,
            "consistency_status": consistency_audit.overall_status if consistency_audit else "UNSPECIFIED",
            "scene_type": scene_decision.scene_type,
            "perceptual_status": perceptual_eval.overall,
            "certification": cert_report.certification,
            "reference_match": reference_comp.comparison_status if reference_comp else "NONE",
        }

        result = MasteringResult(
            status=status,
            chapter_id=request.chapter_id,
            premaster_path=str(premaster_path),
            master_path=str(master_path),
            profile=active_profile,
            analysis_before=analysis_before,
            analysis_after=analysis_after,
            qc_result=qc_result,
            action_plan=action_plan,
            dialogue_protection=dialogue_report,
            consistency_audit=consistency_audit,
            perceptual_evaluation=perceptual_eval,
            scene_decision=scene_decision,
            reference_comparison=reference_comp,
            certification_report=cert_report,
            iteration_count=iterations_run,
            provenance=provenance,
            error_message=error_msg,
        )

        # Persistent Audit Ledger Serialization
        ledger = MasteringLedger(
            chapter_id=request.chapter_id,
            request=request,
            result=result,
            metadata={
                "engine_version": self.version,
                "remediation_count": len(remediation_actions),
                "judge_verdict": action_plan.overall_verdict,
                "dialogue_protection_status": dialogue_report.status,
                "consistency_status": consistency_audit.overall_status if consistency_audit else "UNSPECIFIED",
                "scene_type": scene_decision.scene_type,
                "perceptual_status": perceptual_eval.overall,
                "certification": cert_report.certification,
            },
        )
        ledger_path = master_path.parent / f"{request.chapter_id}_mastering_ledger.json"
        ledger.save_to_disk(ledger_path)

        return result
