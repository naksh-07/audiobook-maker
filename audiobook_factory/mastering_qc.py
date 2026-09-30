#!/usr/bin/env python3
"""
Audiobook Factory - Stage 12: Mastering V2 Quality Control (QC) Engine.
=======================================================================
Machine-readable quality certification validating physical audio deliverables
against technical, broadcast loudness, true-peak, stereo phase, and integrity criteria.

Fail-Safe Policy:
- Critical defects (file corrupt, clipping overs, silence dropouts, anti-phase) trigger FAIL and halt certification.
- Non-critical acoustic variances trigger WARN with actionable logs.
"""

from __future__ import annotations
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

from audiobook_factory.mastering_contracts import (
    MasteringProfile,
    MasteringAnalysisFacts,
    MasteringQCResult,
)


class MasteringQCAgent:
    """
    Independent Stage 12 Mastering Quality Control Auditor.
    Inspects rendered master deliverables against broadcast specifications.
    """

    def __init__(self, profile: Optional[MasteringProfile] = None):
        self.profile = profile or MasteringProfile()

    def evaluate(
        self,
        master_facts: MasteringAnalysisFacts,
        premaster_facts: Optional[MasteringAnalysisFacts] = None,
        dialogue_facts: Optional[MasteringAnalysisFacts] = None,
        profile: Optional[MasteringProfile] = None,
    ) -> MasteringQCResult:
        """
        Executes complete multi-point verification on the post-master analysis facts.
        """
        prof = profile or self.profile
        checks: Dict[str, str] = {}
        failures: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # 1. Technical Audio File Integrity
        master_path = Path(master_facts.filepath)
        if not master_facts.is_valid_audio or not master_path.exists() or master_facts.duration_sec <= 0.0:
            failures.append("audio_integrity_failed_empty_or_corrupt")
            checks["audio_integrity"] = "FAIL"
        else:
            checks["audio_integrity"] = "PASS"

        # 2. Duration Continuity
        if premaster_facts and premaster_facts.duration_sec > 0.0:
            dur_delta = abs(master_facts.duration_sec - premaster_facts.duration_sec)
            details["duration_delta_sec"] = round(dur_delta, 3)
            # Allow up to 0.35s for trailing lookahead limiter / reverb release
            if dur_delta > 0.35:
                failures.append(f"duration_mismatch_exceeds_threshold: {dur_delta:.2f}s")
                checks["duration"] = "FAIL"
            elif dur_delta > 0.15:
                warnings.append(f"minor_duration_drift: {dur_delta:.2f}s")
                checks["duration"] = "WARN"
            else:
                checks["duration"] = "PASS"
        else:
            checks["duration"] = "PASS"

        # 3. Format Compliance (Sample Rate & Channels)
        sr_match = master_facts.sample_rate == prof.output_sample_rate
        ch_match = master_facts.channels == prof.output_channels
        details["sample_rate"] = master_facts.sample_rate
        details["channels"] = master_facts.channels
        if not sr_match or not ch_match:
            failures.append(f"format_mismatch: sr={master_facts.sample_rate} (expected {prof.output_sample_rate}), ch={master_facts.channels} (expected {prof.output_channels})")
            checks["format_compliance"] = "FAIL"
        else:
            checks["format_compliance"] = "PASS"

        # 4. Broadcast Integrated Loudness Compliance (EBU R128)
        lufs = master_facts.integrated_lufs
        details["measured_integrated_lufs"] = lufs
        details["target_lufs"] = prof.target_lufs
        details["loudness_error_lu"] = round(abs(lufs - prof.target_lufs), 2)

        if lufs <= -65.0:
            failures.append("complete_silence_dropout_detected")
            checks["loudness"] = "FAIL"
        elif abs(lufs - prof.target_lufs) > prof.tolerance_lu:
            # Over tolerance threshold
            if abs(lufs - prof.target_lufs) > prof.tolerance_lu * 2.0:
                failures.append(f"integrated_loudness_severe_violation: {lufs:.2f} LUFS outside target {prof.target_lufs} +/- {prof.tolerance_lu} LU")
                checks["loudness"] = "FAIL"
            else:
                warnings.append(f"integrated_loudness_minor_tolerance_exceeded: {lufs:.2f} LUFS")
                checks["loudness"] = "WARN"
        else:
            checks["loudness"] = "PASS"

        # 5. True-Peak Inter-Sample Ceiling Compliance
        tp = master_facts.true_peak_dbtp
        details["measured_true_peak_dbtp"] = tp
        details["true_peak_ceiling_dbtp"] = prof.true_peak_ceiling_dbtp

        if tp is not None:
            if tp > 0.0:
                failures.append(f"digital_clipping_overshoot_detected: {tp:.2f} dBTP exceeds 0.0 dBFS")
                checks["true_peak"] = "FAIL"
            elif tp > prof.true_peak_ceiling_dbtp:
                if tp > prof.true_peak_ceiling_dbtp + 0.3:
                    failures.append(f"true_peak_ceiling_violation: {tp:.2f} dBTP exceeds ceiling {prof.true_peak_ceiling_dbtp} dBTP")
                    checks["true_peak"] = "FAIL"
                else:
                    warnings.append(f"true_peak_near_ceiling_margin: {tp:.2f} dBTP")
                    checks["true_peak"] = "WARN"
            else:
                checks["true_peak"] = "PASS"
        else:
            checks["true_peak"] = "PASS"

        # 6. Stereo Phase Correlation & Mono Compatibility
        phase_r = master_facts.phase_correlation
        details["phase_correlation"] = phase_r
        if phase_r < 0.0:
            failures.append(f"severe_anti_phase_cancellation_detected: r={phase_r:.2f} < 0.0")
            checks["stereo_phase"] = "FAIL"
        elif phase_r < 0.20:
            warnings.append(f"low_stereo_phase_correlation: r={phase_r:.2f} < 0.20")
            checks["stereo_phase"] = "WARN"
        else:
            checks["stereo_phase"] = "PASS"

        # 7. Dead-Air Silence Run Check
        details["dead_air_sec"] = master_facts.dead_air_sec
        if master_facts.dead_air_sec > 6.0:
            failures.append(f"excessive_dead_air_silence_blocks: {master_facts.dead_air_sec:.1f}s")
            checks["dead_air"] = "FAIL"
        elif master_facts.dead_air_sec > 3.0:
            warnings.append(f"extended_silence_pause_observed: {master_facts.dead_air_sec:.1f}s")
            checks["dead_air"] = "WARN"
        else:
            checks["dead_air"] = "PASS"

        # 8. Dialogue Protection Vocal Anchor Check
        if dialogue_facts and dialogue_facts.integrated_lufs > -65.0:
            vocal_ratio = round(dialogue_facts.integrated_lufs - lufs, 2)
            details["dialogue_anchor_ratio_db"] = vocal_ratio
            if vocal_ratio < prof.min_dialogue_to_mix_ratio_db - 4.0:
                warnings.append(f"dialogue_energy_significantly_below_master: vocal_ratio={vocal_ratio:.1f} dB")
                checks["dialogue_protection"] = "WARN"
            else:
                checks["dialogue_protection"] = "PASS"

        # Determine Overall Status
        if failures:
            overall_status = "FAIL"
            passed = False
        elif warnings:
            overall_status = "WARN"
            passed = True
        else:
            overall_status = "PASS"
            passed = True

        return MasteringQCResult(
            status=overall_status,
            passed=passed,
            checks=checks,
            failures=failures,
            warnings=warnings,
            details=details,
        )
