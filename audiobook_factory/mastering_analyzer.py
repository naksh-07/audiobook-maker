#!/usr/bin/env python3
"""
Audiobook Factory - Stage 12: Mastering V2 Forensic Audio Analyzer.
===================================================================
Deterministic, side-effect-free forensic analyzer measuring ground-truth physical,
acoustic, spectral, and loudness metrics directly from rendered audio artifacts.

Reuses DeterministicAudioAnalyzer and GateAuditor phase correlation infrastructure,
adding short-term/momentary metering, crest factor calculation, mono compatibility,
dead-air detection, and dialogue vocal anchor analysis.
"""

from __future__ import annotations
import math
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

from audiobook_factory.logger import logger
from audiobook_factory.deterministic_audio_analyzer import DeterministicAudioAnalyzer
from audiobook_factory.gate_auditor import audit_gate5_3_stereo_phase
from audiobook_factory.mastering_contracts import MasteringAnalysisFacts

ANALYZER_ENGINE_VERSION = "2.0.0"


class MasteringAnalyzer:
    """
    Forensic acoustic and loudness analyzer for Stage 12 Mastering.
    Produces deterministic MasteringAnalysisFacts from physical audio files.
    """

    def __init__(
        self,
        base_analyzer: Optional[DeterministicAudioAnalyzer] = None,
        ffmpeg_bin: Optional[str] = None,
        ffprobe_bin: Optional[str] = None,
    ):
        self.ffmpeg = ffmpeg_bin or shutil.which("ffmpeg") or "ffmpeg"
        self.ffprobe = ffprobe_bin or shutil.which("ffprobe") or "ffprobe"
        self.base_analyzer = base_analyzer or DeterministicAudioAnalyzer(
            ffprobe_bin=self.ffprobe,
            ffmpeg_bin=self.ffmpeg,
        )
        self.version = ANALYZER_ENGINE_VERSION
        # Stat-based analysis cache: (resolved_path, file_size, mtime_ns) -> MasteringAnalysisFacts
        self._analysis_cache: Dict[Tuple[str, int, int], MasteringAnalysisFacts] = {}

    def clear_cache(self) -> None:
        """Clears in-memory caches."""
        self._analysis_cache.clear()
        self.base_analyzer.clear_cache()

    def analyze(
        self,
        audio_path: Union[str, Path],
        dialogue_stem_path: Optional[Union[str, Path]] = None,
    ) -> MasteringAnalysisFacts:
        """
        Analyzes a physical audio file and returns comprehensive MasteringAnalysisFacts.
        Results are cached based on file inode stat (path, size, mtime).
        """
        p = Path(audio_path).resolve()
        if not p.exists() or p.stat().st_size < 100:
            return MasteringAnalysisFacts(
                filepath=str(p),
                duration_sec=0.0,
                sample_rate=48000,
                channels=2,
                integrated_lufs=-70.0,
                clipping_detected=False,
                is_valid_audio=False,
            )

        st = p.stat()
        cache_key = (str(p), st.st_size, st.st_mtime_ns)
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key].model_copy(deep=True)

        # 1. Format facts via base analyzer
        fmt = self.base_analyzer.probe_format(p)

        # 2. Basic Loudness facts (integrated LUFS, True Peak, LRA, RMS, Peak)
        loud = self.base_analyzer.probe_loudness(p)

        # 3. Spectral and Temporal facts
        spectral, temporal, _, _ = self.base_analyzer.probe_spectral_and_temporal(p)

        # 4. Stereo Phase Correlation & Mono Compatibility
        phase_r = None
        mono_compatible = None
        if fmt.channels > 1:
            try:
                phase_audit = audit_gate5_3_stereo_phase(p)
                raw_phase = phase_audit.details.get("mean_phase_correlation", phase_audit.details.get("phase_correlation"))
                if raw_phase is not None:
                    phase_val = float(raw_phase)
                    if not math.isnan(phase_val) and not math.isinf(phase_val):
                        phase_r = phase_val
                        mono_compatible = bool(phase_r >= 0.20)
            except Exception as e:
                logger.debug(f"Phase correlation probe error on {p.name}: {e}")
        else:
            # Mono audio is trivially in-phase and mono-compatible
            phase_r = 1.0
            mono_compatible = True

        # 5. Short-term & Momentary loudness via FFmpeg ebur128 framelog
        short_term_max = None
        momentary_max = None
        cmd_ebur = [
            self.ffmpeg, "-y",
            "-i", str(p),
            "-af", "ebur128=peak=true:framelog=verbose",
            "-f", "null", "-",
        ]
        try:
            proc = subprocess.run(cmd_ebur, capture_output=True, text=True, errors="ignore", timeout=600.0)
            err = proc.stderr
            st_matches = re.findall(r"S:\s+([-\d.]+)\s+LUFS", err)
            if st_matches:
                valid_st = [float(v) for v in st_matches if float(v) > -120.0 and not math.isnan(float(v))]
                if valid_st:
                    short_term_max = round(max(valid_st), 2)

            mom_matches = re.findall(r"M:\s+([-\d.]+)\s+LUFS", err)
            if mom_matches:
                valid_mom = [float(v) for v in mom_matches if float(v) > -120.0 and not math.isnan(float(v))]
                if valid_mom:
                    momentary_max = round(max(valid_mom), 2)
        except Exception as e:
            logger.debug(f"Short-term ebur128 probe error on {p.name}: {e}")

        # 6. Dead air / excessive silence detection (runs > 2.0s below -50dB)
        total_dead_air_sec = 0.0
        cmd_silence = [
            self.ffmpeg, "-y",
            "-i", str(p),
            "-af", "silencedetect=noise=-50dB:d=2.0",
            "-f", "null", "-",
        ]
        try:
            sil_proc = subprocess.run(cmd_silence, capture_output=True, text=True, errors="ignore", timeout=300.0)
            sil_durs = re.findall(r"silence_duration:\s+([-\d.]+)", sil_proc.stderr)
            if sil_durs:
                valid_durs = [float(d) for d in sil_durs if not math.isnan(float(d))]
                # Longest contiguous dead-air block (industry check is against individual drops > 6s)
                total_dead_air_sec = round(max(valid_durs), 2) if valid_durs else 0.0
        except Exception as e:
            logger.debug(f"Silence detection probe error on {p.name}: {e}")

        # 7. Crest factor and dynamic range calculations
        crest_factor = None
        if loud.peak_level_db is not None and loud.rms_level_db is not None:
            crest_factor = round(abs(loud.peak_level_db - loud.rms_level_db), 2)

        # 8. Clipping detection (True peak > 0.0 dBTP or Sample peak >= -0.01 dBFS)
        clipping = False
        if loud.true_peak_dbtp is not None and loud.true_peak_dbtp > 0.0:
            clipping = True
        elif loud.peak_level_db is not None and loud.peak_level_db >= -0.01:
            clipping = True

        # 9. Verify audio validity (duration > 0, non-nan loudness)
        is_valid = bool(
            fmt.duration_sec > 0.0
            and loud.integrated_lufs is not None
            and not math.isnan(loud.integrated_lufs)
            and not math.isinf(loud.integrated_lufs)
        )

        facts = MasteringAnalysisFacts(
            filepath=str(p),
            duration_sec=fmt.duration_sec,
            sample_rate=fmt.sample_rate,
            channels=fmt.channels,
            integrated_lufs=loud.integrated_lufs if loud.integrated_lufs is not None else -70.0,
            short_term_max_lufs=short_term_max,
            momentary_max_lufs=momentary_max,
            loudness_range_lra=loud.loudness_range_lu,
            true_peak_dbtp=loud.true_peak_dbtp,
            sample_peak_dbfs=loud.peak_level_db,
            rms_level_dbfs=loud.rms_level_db,
            dynamic_range_db=loud.dynamic_range_db,
            crest_factor_db=crest_factor,
            spectral_centroid_hz=spectral.spectral_centroid_hz,
            spectral_rolloff_hz=spectral.spectral_rolloff_hz,
            spectral_flatness=spectral.spectral_flatness,
            phase_correlation=round(phase_r, 4) if phase_r is not None else 1.0,
            mono_compatible=mono_compatible if mono_compatible is not None else True,
            silence_ratio=temporal.silence_ratio,
            dead_air_sec=total_dead_air_sec,
            transient_count=temporal.transient_count,
            clipping_detected=clipping,
            is_valid_audio=is_valid,
        )

        self._analysis_cache[cache_key] = facts
        return facts.model_copy(deep=True)

    def calculate_vocal_anchor_ratio(
        self,
        dialogue_stem_path: Union[str, Path],
        master_path: Union[str, Path],
    ) -> float:
        """
        Calculates the Dialogue Protection Ratio: (DX_LUFS - Master_LUFS).
        A healthy mix keeps vocal anchor ratio >= -4.0 dB so speech is never buried.
        """
        dx_facts = self.analyze(dialogue_stem_path)
        master_facts = self.analyze(master_path)
        if dx_facts.integrated_lufs is None or master_facts.integrated_lufs is None:
            return 0.0
        if dx_facts.integrated_lufs <= -65.0:
            return 0.0
        return round(dx_facts.integrated_lufs - master_facts.integrated_lufs, 2)
