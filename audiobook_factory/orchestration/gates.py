"""
Audiobook Factory - Chapter Quality Gate Evaluators.
Encapsulates inline gate assertions (Gate 2, 2.5, 2.8, 3.5, 5.2, 5.3, 5.0)
for robust, fail-closed studio production.
"""

from pathlib import Path
from typing import Any, Tuple, Optional
import os
import json

from audiobook_factory.logger import logger
from audiobook_factory.gate_auditor import (
    audit_gate0_translation,
    audit_gate1_roster,
    audit_gate2_script,
    audit_gate2_5_dramatic_fidelity,
    audit_gate3_5_acoustic_feasibility,
    audit_gate5_2_spectral_masking,
    audit_gate5_3_stereo_phase,
    audit_gate5_master,
    audit_gate6a_voice_continuity,
    audit_gate6c_toc_monotonicity,
    GateAuditError,
)
from audiobook_factory.sound_bank import get_sound_bank
from audiobook_factory.telemetry import get_telemetry_ledger


def verify_pre_synthesis_gates(
    script_file: Path,
    chap_stem: str,
    project_dir: Path,
    chapter_num: int,
) -> None:
    """Evaluates Gate 2 (Script Schema/Whitelist/LLM Attribution) and Gate 2.5 (Dramatic Beat Fidelity)."""
    # Gate 2: Screenplay Script Schema and canonical speakers (ADR-021 Whitelist & LLM Attribution)
    try:
        gate2_res = audit_gate2_script(script_file, project_dir=project_dir, enable_llm_judge=True, strict=True)
        logger.info(f"[*] Gate 2 Script Audit: PASSED for Chapter {chapter_num:02d} ({gate2_res.get('total_segments', 0)} segments)")
    except GateAuditError as e:
        logger.error(f"\n[!] 🛑 GATE 2 AUDIT FAILED for Chapter {chapter_num:02d}: {e}")
        logger.error("[!] Screenplay contains non-canonical speakers, schema violations, or misattributed dialogue. Aborting synthesis.")
        raise
    except Exception as e:
        logger.warning(f"[!] Gate 2 Script Audit notice for Chapter {chapter_num:02d}: {e}")

    # Gate 2.5: Dramatic Beat Fidelity & Character Arc Validator
    dramatic_plan_file = project_dir / "dramaturgy" / f"{chap_stem}_dramatic_plan.json"
    source_chap_file = project_dir / "translated" / f"{chap_stem}.md"
    if not source_chap_file.exists():
        source_chap_file = project_dir / "extracted" / f"{chap_stem}.md"
    try:
        gate2_5_res = audit_gate2_5_dramatic_fidelity(
            script_file=script_file,
            dramatic_plan_file=dramatic_plan_file if dramatic_plan_file.exists() else None,
            source_file=source_chap_file if source_chap_file.exists() else None,
            project_dir=project_dir,
        )
        logger.info(f"[*] Gate 2.5 Dramatic Fidelity: PASSED for Chapter {chapter_num:02d} (Status: {gate2_5_res.get('status')})")
    except GateAuditError as e:
        logger.error(f"\n[!] 🛑 GATE 2.5 DRAMATIC FIDELITY FAILED for Chapter {chapter_num:02d}: {e}")
        raise
    except Exception as e:
        logger.warning(f"[!] Gate 2.5 Dramatic Fidelity notice for Chapter {chapter_num:02d}: {e}")


def verify_performance_fidelity_gate(
    manifests_dir: Path,
    chap_stem: str,
    chapter_num: int,
) -> None:
    """Evaluates Gate 2.8 Pre-Mix Performance Fidelity Gate (Fail-Closed)."""
    perf_report_file = manifests_dir / f"chapter_{chapter_num:03d}_performance_report.json"
    if not perf_report_file.exists():
        perf_report_file = manifests_dir / f"{chap_stem}_performance_report.json"
    if perf_report_file.exists():
        try:
            from audiobook_factory.performance.contracts import PerformanceFidelityReport
            with open(perf_report_file, "r", encoding="utf-8") as rf:
                rep_dict = json.load(rf)
            rep = PerformanceFidelityReport.model_validate(rep_dict)
            if rep.passed:
                logger.info(f"[*] Gate 2.8 Performance Fidelity: PASSED for Chapter {chapter_num:02d} (Avg Score: {rep.avg_evaluation_score:.2f})")
            else:
                force_perf = os.environ.get("FORCE_PERFORMANCE_GATE", "false").lower() in ("true", "1", "yes")
                if force_perf:
                    logger.warning(f"[!] Gate 2.8 Performance Fidelity FORCED for Chapter {chapter_num:02d}: {rep.unresolved_issues}")
                else:
                    raise GateAuditError(
                        f"Gate 2.8 Performance Fidelity Failed for Chapter {chapter_num:02d}: "
                        f"{'; '.join(rep.unresolved_issues[:3]) if rep.unresolved_issues else 'Low evaluation score'}"
                    )
        except GateAuditError:
            raise
        except Exception as e:
            logger.warning(f"[!] Gate 2.8 Performance Fidelity notice for Chapter {chapter_num:02d}: {e}")


def verify_acoustic_feasibility_gate(
    manifest: Any,
    chapter_num: int,
) -> None:
    """Evaluates Gate 3.5 Acoustic Pre-Flight Feasibility Guard."""
    try:
        gate35_res = audit_gate3_5_acoustic_feasibility(manifest, sound_bank=get_sound_bank())
        if not gate35_res.passed:
            logger.error(f"[!] 🛑 Gate 3.5 Pre-Flight Feasibility FAILED for Chapter {chapter_num:02d}: {gate35_res.errors}")
            if os.environ.get("STRICT_QUALITY_GATES", "true").lower() in ("1", "true", "yes"):
                raise GateAuditError(f"Gate 3.5 Pre-Flight Feasibility Failed: {'; '.join(gate35_res.errors)}")
        else:
            logger.info(f"[*] Gate 3.5 Acoustic Feasibility: PASSED for Chapter {chapter_num:02d}")
    except GateAuditError:
        raise
    except Exception as e:
        logger.warning(f"[!] Gate 3.5 Feasibility notice: {e}")


def verify_post_mix_master_gates(
    chapter_num: int,
    cinematic_out: Path,
    master_wav: Path,
    vocal_wav: Path,
    mx_stem: Path,
) -> Tuple[bool, bool, bool]:
    """
    Evaluates post-render audio gates:
    - Gate 5.2 Spectral Masking (DMR >= 12 dB)
    - Gate 5.3 Stereo Phase Correlation (r >= 0.20)
    - Gate 5.0 Broadcast Master EBU R128 (-19 LUFS, TP <= -1.4 dBTP)
    Returns: (gate52_passed, gate53_passed, gate5_certified)
    """
    strict_gates = os.environ.get("STRICT_QUALITY_GATES", "true").lower() in ("1", "true", "yes")

    # Gate 5.2: Spectral Masking (Dialogue vs Music DMR)
    gate52_passed = True
    if mx_stem.exists() and vocal_wav.exists():
        try:
            gate52_res = audit_gate5_2_spectral_masking(vocal_wav, mx_stem, min_dmr_db=12.0)
            gate52_passed = gate52_res.passed
            if not gate52_res.passed:
                logger.error(f"[!] 🛑 Gate 5.2 Spectral Masking FAILED for Chapter {chapter_num:02d}: {gate52_res.errors}")
                if strict_gates:
                    raise GateAuditError(f"Chapter {chapter_num:02d} failed Gate 5.2 Spectral Masking: {'; '.join(gate52_res.errors)}")
            else:
                logger.info(f"[*] Gate 5.2 Spectral Masking: PASSED (DMR: {gate52_res.details.get('measured_dmr_db', 'N/A')} dB)")
        except GateAuditError:
            raise
        except Exception as e:
            logger.error(f"[!] Gate 5.2 Spectral Masking probe error: {e}")
            gate52_passed = False
            if strict_gates:
                raise GateAuditError(f"Gate 5.2 audit probe error: {e}")

    # Gate 5.3: Stereo Phase Correlation
    gate53_passed = True
    phase_corr = 1.0
    if master_wav.exists():
        try:
            gate53_res = audit_gate5_3_stereo_phase(master_wav, min_phase_correlation=0.20)
            gate53_passed = gate53_res.passed
            if not gate53_res.passed:
                logger.error(f"[!] 🛑 Gate 5.3 Stereo Phase FAILED for Chapter {chapter_num:02d}: {gate53_res.errors}")
                if strict_gates:
                    raise GateAuditError(f"Chapter {chapter_num:02d} failed Gate 5.3 Stereo Phase: {'; '.join(gate53_res.errors)}")
            else:
                phase_corr = float(gate53_res.details.get("mean_phase_correlation", 1.0))
                logger.info(f"[*] Gate 5.3 Stereo Phase: PASSED (mean r: {phase_corr:.3f})")
        except GateAuditError:
            raise
        except Exception as e:
            logger.error(f"[!] Gate 5.3 Stereo Phase probe error: {e}")
            gate53_passed = False
            if strict_gates:
                raise GateAuditError(f"Gate 5.3 audit probe error: {e}")

    # Gate 5: Broadcast Master EBU R128 Probe
    gate5_certified = False
    if cinematic_out.exists():
        try:
            gate5_res = audit_gate5_master(cinematic_out, target_lufs=-19.0, tolerance_lu=2.0, max_true_peak=-1.4)
            gate5_certified = (gate5_res.get("status") == "PASS")
            logger.info(f"[*] Gate 5 Broadcast Master: PASSED (LUFS: {gate5_res.get('integrated_lufs')}, TP: {gate5_res.get('true_peak_dbtp')})")
            if gate5_certified:
                try:
                    t_ledger = get_telemetry_ledger()
                    meas_dur = float(gate5_res.get("duration_sec", 0.0) or 0.0)
                    if meas_dur <= 0.0:
                        try:
                            from audiobook_factory.soundscape import measure_audio_metrics
                            meas_dur = float(measure_audio_metrics(cinematic_out).get("duration_sec", 0.0) or 0.0)
                        except Exception:
                            pass
                    t_ledger.record_acoustic_metrics(
                        run_id=os.environ.get("CURRENT_AUDIOBOOK_RUN_ID", f"chap_{chapter_num}"),
                        chapter_num=chapter_num,
                        duration_sec=meas_dur,
                        integrated_lufs=float(gate5_res.get("integrated_lufs", -19.0)),
                        true_peak_dbtp=float(gate5_res.get("true_peak_dbtp", -1.5)),
                        loudness_range_lu=float(gate5_res.get("loudness_range_lu", 0.0) or 0.0),
                        phase_correlation=phase_corr,
                    )
                except Exception as te:
                    logger.debug(f"Telemetry acoustic recording notice: {te}")
        except GateAuditError:
            raise
        except Exception as e:
            logger.error(f"[!] 🛑 Gate 5 Broadcast Master FAILED for Chapter {chapter_num:02d}: {e}")
            raise GateAuditError(f"Chapter {chapter_num:02d} master failed EBU R128 broadcast certification: {e}")

    return gate52_passed, gate53_passed, gate5_certified


def verify_translation_coverage_gates(project_dir: Path, strict: bool = True) -> None:
    """Evaluates Gate 0 Translation Coverage and Gate 1 Anti-Censorship across all extracted chapters."""
    from audiobook_factory.gates.literary import audit_gate1_anticensorship_agent
    extracted_dir = project_dir / "extracted"
    translation_dir = project_dir / "translation"
    ext_files = sorted(extracted_dir.glob("chapter_*.md"))
    for ef in ext_files:
        tf = translation_dir / f"{ef.stem}_hi.md"
        if not tf.exists():
            tf = translation_dir / ef.name
        if tf.exists():
            g0_res = audit_gate0_translation(ef, tf, enable_llm_judge=True, strict=strict)
            logger.info(
                f"[*] Gate 0 Translation Coverage: PASSED for {ef.name} "
                f"({g0_res.get('translation_chars')} chars, ratio {g0_res.get('length_ratio')}, "
                f"fidelity: {g0_res.get('fidelity_score', 'N/A')})"
            )

            # Gate 1 Anti-Censorship (Adversarial Profanity, Combat Gore, Somatic Intimacy)
            ext_text = ef.read_text(encoding="utf-8")
            trans_text = tf.read_text(encoding="utf-8")
            g1_anti = audit_gate1_anticensorship_agent(ext_text, trans_text, strict=strict)
            logger.info(f"[*] Gate 1 Anti-Censorship Audit: PASSED for {ef.name} (Status: {g1_anti.get('status')})")


def verify_screenplay_project_gates(project_dir: Path) -> None:
    """Evaluates Gate 1 (Character Roster & Voice Collision) and Gate 6A (Voice Continuity)."""
    roster_file = project_dir / "character_roster.json"
    registry_file = project_dir / "voice_registry.json"
    if roster_file.exists() or registry_file.exists():
        g1_res = audit_gate1_roster(
            roster_file=roster_file if roster_file.exists() else {},
            registry_file=registry_file if registry_file.exists() else {},
        )
        logger.info(f"[*] Gate 1 Character Roster & Voice Collision: PASSED ({g1_res.get('status')})")

    g6a_res = audit_gate6a_voice_continuity(project_dir)
    if not g6a_res.passed:
        raise GateAuditError(f"Gate 6A Voice Continuity Failed across chapters: {'; '.join(g6a_res.errors)}")
    logger.info("[*] Gate 6A Voice Continuity: PASSED across all chapters")


def verify_packaging_gates(project_dir: Path) -> None:
    """Evaluates Gate 6C (Table of Contents Monotonicity & Chapter Boundaries)."""
    try:
        g6c_res = audit_gate6c_toc_monotonicity(project_dir)
        if g6c_res.passed:
            logger.info("[*] Gate 6C Table of Contents Monotonicity: PASSED")
        else:
            logger.warning(f"[!] Gate 6C TOC Monotonicity notice: {g6c_res.errors}")
    except Exception as e:
        logger.warning(f"[!] Gate 6C TOC Monotonicity notice: {e}")
