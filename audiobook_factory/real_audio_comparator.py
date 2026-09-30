#!/usr/bin/env python3
"""
Audiobook Factory - Real Audio Comparator (Phase 4).
===================================================
Forensic before/after comparison between premaster and master.
Measures acoustic delta across:
- Integrated Loudness (LUFS)
- True Peak (dBTP)
- Loudness Range (LRA)
- Crest Factor (dB)
- Spectral Centroid (Hz) & Band Energies (Low/Mid/High)
- Stereo Phase Correlation
- Silence Ratio & Duration Consistency
"""

from __future__ import annotations
import math
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

from audiobook_factory.mastering_contracts import MasteringAnalysisFacts
from audiobook_factory.mastering_analyzer import MasteringAnalyzer
from audiobook_factory.real_audio_contracts import (
    AudioMetricDelta,
    AudioDeltaReport,
)


class RealAudioComparator:
    """
    Compares premaster and master audio files to quantify what changed
    and verify that mastering improved/controlled the audio without destruction.
    """

    def __init__(self, analyzer: Optional[MasteringAnalyzer] = None):
        self.analyzer = analyzer or MasteringAnalyzer()

    def compare(
        self,
        fixture_id: str,
        premaster_path: str | Path,
        master_path: str | Path,
        scene_type: str = "narration",
    ) -> AudioDeltaReport:
        p_path = Path(premaster_path).resolve()
        m_path = Path(master_path).resolve()

        if not p_path.exists():
            raise FileNotFoundError(f"Premaster does not exist: {p_path}")
        if not m_path.exists():
            raise FileNotFoundError(f"Master deliverable does not exist: {m_path}")

        # Probing acoustic facts via MasteringAnalyzer
        pre_facts = self.analyzer.analyze(p_path)
        post_facts = self.analyzer.analyze(m_path)

        # 1. Integrated Loudness Delta
        lufs_pre = pre_facts.integrated_lufs
        lufs_post = post_facts.integrated_lufs
        lufs_delta = round(lufs_post - lufs_pre, 2)
        lufs_class = self._classify_lufs_delta(lufs_pre, lufs_post, lufs_delta, scene_type)
        lufs_metric = AudioMetricDelta(
            metric_name="integrated_lufs",
            before=lufs_pre,
            after=lufs_post,
            delta=lufs_delta,
            unit="LUFS",
            classification=lufs_class[0],
            rationale=lufs_class[1],
        )

        # 2. True Peak Delta
        tp_pre = pre_facts.true_peak_dbtp
        tp_post = post_facts.true_peak_dbtp
        tp_delta = round(tp_post - tp_pre, 2) if (tp_pre is not None and tp_post is not None) else None
        tp_class = self._classify_true_peak(tp_post)
        tp_metric = AudioMetricDelta(
            metric_name="true_peak_dbtp",
            before=tp_pre,
            after=tp_post,
            delta=tp_delta,
            unit="dBTP",
            classification=tp_class[0],
            rationale=tp_class[1],
        )

        # 3. Loudness Range (LRA) Delta
        lra_pre = pre_facts.loudness_range_lra
        lra_post = post_facts.loudness_range_lra
        lra_delta = round(lra_post - lra_pre, 2) if (lra_pre is not None and lra_post is not None) else None
        lra_class = self._classify_lra_delta(lra_pre, lra_post, lra_delta, scene_type)
        lra_metric = AudioMetricDelta(
            metric_name="loudness_range_lra",
            before=lra_pre,
            after=lra_post,
            delta=lra_delta,
            unit="LU",
            classification=lra_class[0],
            rationale=lra_class[1],
        )

        # 4. Crest Factor Delta
        crest_pre = pre_facts.crest_factor_db
        crest_post = post_facts.crest_factor_db
        crest_delta = round(crest_post - crest_pre, 2) if (crest_pre is not None and crest_post is not None) else None
        crest_class = self._classify_crest_delta(crest_pre, crest_post, crest_delta)
        crest_metric = AudioMetricDelta(
            metric_name="crest_factor_db",
            before=crest_pre,
            after=crest_post,
            delta=crest_delta,
            unit="dB",
            classification=crest_class[0],
            rationale=crest_class[1],
        )

        # 5. Spectral Centroid Delta
        sc_pre = pre_facts.spectral_centroid_hz
        sc_post = post_facts.spectral_centroid_hz
        sc_delta = round(sc_post - sc_pre, 1) if (sc_pre is not None and sc_post is not None) else None
        sc_class = self._classify_spectral_centroid(sc_pre, sc_post, sc_delta)
        sc_metric = AudioMetricDelta(
            metric_name="spectral_centroid_hz",
            before=sc_pre,
            after=sc_post,
            delta=sc_delta,
            unit="Hz",
            classification=sc_class[0],
            rationale=sc_class[1],
        )

        # 6. Stereo Phase Correlation Delta
        phase_pre = pre_facts.phase_correlation
        phase_post = post_facts.phase_correlation
        phase_delta = round(phase_post - phase_pre, 3)
        phase_class = self._classify_phase_delta(phase_post, phase_delta)
        phase_metric = AudioMetricDelta(
            metric_name="phase_correlation",
            before=phase_pre,
            after=phase_post,
            delta=phase_delta,
            unit="r",
            classification=phase_class[0],
            rationale=phase_class[1],
        )

        # 7. Low / Mid / High Band Energy Deltas
        low_delta, mid_delta, high_delta = self._measure_band_energy_deltas(p_path, m_path)

        # 8. Silence Ratio & Duration Deltas
        silence_pre = pre_facts.silence_ratio or 0.0
        silence_post = post_facts.silence_ratio or 0.0
        silence_delta = round(silence_post - silence_pre, 3)
        duration_delta = round(post_facts.duration_sec - pre_facts.duration_sec, 3)

        # Dimension Assessments
        dyn_assess = "FAIL" if (lra_class[0] == "FAIL" or crest_class[0] == "FAIL" or tp_class[0] == "FAIL") else (
            "SUSPICIOUS" if (lra_class[0] == "SUSPICIOUS" or crest_class[0] == "SUSPICIOUS") else "ACCEPTABLE"
        )
        spec_assess = "FAIL" if sc_class[0] == "FAIL" else (
            "SUSPICIOUS" if (sc_class[0] == "SUSPICIOUS" or (high_delta and high_delta > 4.0)) else "ACCEPTABLE"
        )
        stereo_assess = "FAIL" if phase_class[0] == "FAIL" else (
            "SUSPICIOUS" if phase_class[0] == "SUSPICIOUS" else "ACCEPTABLE"
        )

        # Overall Status
        statuses = [lufs_class[0], tp_class[0], lra_class[0], crest_class[0], sc_class[0], phase_class[0]]
        if "FAIL" in statuses or tp_class[0] == "FAIL":
            overall_status = "FAIL"
        elif "SUSPICIOUS" in statuses:
            overall_status = "REVIEW_REQUIRED"
        elif any(s != "EXPECTED" for s in statuses):
            overall_status = "WARNING"
        else:
            overall_status = "PASS"

        notes = []
        if tp_post and tp_post > -1.5:
            notes.append(f"True peak {tp_post} dBTP violates target ceiling (-1.5 dBTP)")
        if crest_delta and crest_delta < -4.5:
            notes.append(f"Significant crest factor reduction ({crest_delta} dB); inspect for heavy limiting")
        if abs(duration_delta) > 0.1:
            notes.append(f"Duration changed by {duration_delta}s between premaster and master")

        return AudioDeltaReport(
            fixture_id=fixture_id,
            premaster_path=str(p_path),
            master_path=str(m_path),
            integrated_lufs=lufs_metric,
            true_peak_dbtp=tp_metric,
            loudness_range_lra=lra_metric,
            crest_factor_db=crest_metric,
            spectral_centroid_hz=sc_metric,
            phase_correlation=phase_metric,
            low_band_delta_db=low_delta,
            mid_band_delta_db=mid_delta,
            high_band_delta_db=high_delta,
            silence_ratio_delta=silence_delta,
            duration_delta_sec=duration_delta,
            dynamic_assessment=dyn_assess,
            spectral_assessment=spec_assess,
            stereo_assessment=stereo_assess,
            overall_delta_status=overall_status,
            summary_notes=notes,
        )

    # --- Classification Helpers ---

    def _classify_lufs_delta(self, pre: float, post: float, delta: float, scene_type: str) -> Tuple[str, str]:
        # Audible / Broadcast standard target is -19.0 LUFS (±0.5 LU)
        if scene_type in ("whisper", "silence", "intimate"):
            # Permissive range for quiet dramatic moments
            if -25.0 <= post <= -17.5:
                return "EXPECTED", f"Master loudness {post} LUFS respects quiet scene intent"
            return "ACCEPTABLE", f"Master loudness {post} LUFS within acceptable bounds"
        if -19.5 <= post <= -18.5:
            return "EXPECTED", f"Master loudness {post} LUFS perfectly conforms to -19.0 LUFS target"
        if -21.0 <= post <= -17.0:
            return "ACCEPTABLE", f"Master loudness {post} LUFS within broadcast tolerance"
        if post > -14.0 or post < -27.0:
            return "FAIL", f"Master loudness {post} LUFS violates broadcast safety window"
        return "SUSPICIOUS", f"Master loudness {post} LUFS deviates from expected target"

    def _classify_true_peak(self, post: Optional[float]) -> Tuple[str, str]:
        if post is None:
            return "FAIL", "Missing true peak measurement"
        if post > 0.0:
            return "FAIL", f"Intersample clipping detected: {post} dBTP > 0.0 dBTP"
        if post > -1.0:
            return "SUSPICIOUS", f"True peak {post} dBTP exceeds standard -1.5 dBTP safety ceiling"
        return "EXPECTED", f"True peak {post} dBTP conforms to broadcast limit"

    def _classify_lra_delta(self, pre: Optional[float], post: Optional[float], delta: Optional[float], scene_type: str) -> Tuple[str, str]:
        if pre is None or post is None or delta is None:
            return "ACCEPTABLE", "LRA not available"
        if delta < -6.0:
            return "SUSPICIOUS", f"LRA collapsed by {delta} LU; possible excessive compression"
        if 4.0 <= post <= 12.0:
            return "EXPECTED", f"Master LRA {post} LU aligns with commercial audiobook dynamics"
        return "ACCEPTABLE", f"Master LRA {post} LU acceptable for {scene_type}"

    def _classify_crest_delta(self, pre: Optional[float], post: Optional[float], delta: Optional[float]) -> Tuple[str, str]:
        if pre is None or post is None or delta is None:
            return "ACCEPTABLE", "Crest factor not available"
        if delta < -5.0:
            return "SUSPICIOUS", f"Crest factor reduction of {delta} dB indicates severe peak limiting"
        if -3.5 <= delta <= 1.0:
            return "EXPECTED", f"Crest factor delta {delta} dB reflects transparent mastering"
        return "ACCEPTABLE", f"Crest factor delta {delta} dB is within normal range"

    def _classify_spectral_centroid(self, pre: Optional[float], post: Optional[float], delta: Optional[float]) -> Tuple[str, str]:
        if pre is None or post is None or delta is None:
            return "ACCEPTABLE", "Centroid not available"
        if abs(delta) > 900.0:
            return "SUSPICIOUS", f"Spectral centroid shifted significantly ({delta} Hz); tone drastically altered"
        if abs(delta) <= 450.0:
            return "EXPECTED", f"Spectral centroid shift {delta} Hz preserves natural timbre"
        return "ACCEPTABLE", f"Spectral centroid shift {delta} Hz within acceptable coloration"

    def _classify_phase_delta(self, post: float, delta: float) -> Tuple[str, str]:
        if post < 0.0:
            return "FAIL", f"Negative stereo phase correlation {post}; destructive mono cancellation"
        if post < 0.20:
            return "SUSPICIOUS", f"Narrow phase correlation {post}; weak mono compatibility"
        return "EXPECTED", f"Phase correlation {post} provides solid mono compatibility"

    def _measure_band_energy_deltas(self, pre_file: Path, post_file: Path) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculates energy deltas (dB) across Low (<250Hz), Mid (250Hz-4kHz), and High (>4kHz) bands."""
        try:
            data_pre, sr_pre = sf.read(str(pre_file), always_2d=True)
            data_post, sr_post = sf.read(str(post_file), always_2d=True)

            # Mono downmix for energy calculation
            m_pre = np.mean(data_pre, axis=1)
            m_post = np.mean(data_post, axis=1)

            # Bandpass energy helper
            def band_energy(sig: np.ndarray, sr: int, low_f: Optional[float], high_f: Optional[float]) -> float:
                nyq = 0.5 * sr
                if low_f is None and high_f is not None:
                    sos = butter(4, high_f / nyq, btype="lowpass", output="sos")
                elif low_f is not None and high_f is None:
                    sos = butter(4, low_f / nyq, btype="highpass", output="sos")
                elif low_f is not None and high_f is not None:
                    sos = butter(4, [low_f / nyq, high_f / nyq], btype="bandpass", output="sos")
                else:
                    return float(np.mean(sig ** 2) + 1e-12)
                filt = sosfilt(sos, sig)
                rms = float(np.mean(filt ** 2) + 1e-12)
                return 10.0 * math.log10(rms)

            low_pre = band_energy(m_pre, sr_pre, None, 250.0)
            low_post = band_energy(m_post, sr_post, None, 250.0)

            mid_pre = band_energy(m_pre, sr_pre, 250.0, 4000.0)
            mid_post = band_energy(m_post, sr_post, 250.0, 4000.0)

            high_pre = band_energy(m_pre, sr_pre, 4000.0, min(18000.0, 0.45 * sr_pre))
            high_post = band_energy(m_post, sr_post, 4000.0, min(18000.0, 0.45 * sr_post))

            low_delta = round(low_post - low_pre, 2)
            mid_delta = round(mid_post - mid_pre, 2)
            high_delta = round(high_post - high_pre, 2)
            return low_delta, mid_delta, high_delta
        except Exception:
            return None, None, None
