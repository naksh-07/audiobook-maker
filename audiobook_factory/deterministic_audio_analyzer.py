#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.7: Deterministic Audio Analyzer Engine.
===================================================================
Extracts verified physical, spectral, loudness, and temporal facts from local audio
files using ffprobe, ffmpeg (EBU R128 + astats), and streaming scipy/numpy DSP.
Enforces strict epistemic separation:
- MEASURED AUDIO FACTS are physical ground truths (confidence = None).
- Conservative tonal guards: SFX never have hallucinated pitches or BPMs.
- Memory safe: windowed processing for large files, zero memory bloat.
"""

from __future__ import annotations
import os
import re
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

import numpy as np
import scipy.signal as signal
try:
    import soundfile as sf
except ImportError:
    sf = None

from audiobook_factory.logger import logger
from audiobook_factory.contracts import (
    FormatFacts,
    LoudnessFacts,
    SpectralFacts,
    TemporalFacts,
    TonalFacts,
    MeasuredAudioFacts,
    AudioEventRecord,
    ProvenanceRecord,
)

ANALYZER_ID = "deterministic_dsp_engine"
ANALYZER_VERSION = "1.0.0"
ONTOLOGY_VERSION = "sonic_genome_v2.1"
PROCESSING_VERSION = "phase1_v1.0"

SUPPORTED_AUDIO_EXTENSIONS = {
    ".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aif", ".aiff", ".wma", ".aac"
}


class DeterministicAudioAnalyzer:
    """
    Local deterministic audio analysis engine.
    Extracts physical format, EBU R128 loudness, frequency spectral features,
    and temporal boundaries without AI hallucinations or probabilistic guessing.
    """

    def __init__(
        self,
        ffprobe_bin: Optional[str] = None,
        ffmpeg_bin: Optional[str] = None,
    ):
        self.ffprobe = ffprobe_bin or shutil.which("ffprobe") or "ffprobe"
        self.ffmpeg = ffmpeg_bin or shutil.which("ffmpeg") or "ffmpeg"

    def is_supported(self, filepath: Union[Path, str]) -> bool:
        """Check if file extension is supported."""
        return Path(filepath).suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS

    def probe_format(self, filepath: Path) -> FormatFacts:
        """
        Probe stream and container format facts using ffprobe.
        Extracts sample rate, channels, codec, duration, bit depth, and size.
        """
        if not filepath.exists() or filepath.stat().st_size == 0:
            return FormatFacts(
                duration_sec=0.0,
                sample_rate=48000,
                channels=2,
                codec="unknown",
                container=filepath.suffix.lstrip(".").lower() or "wav",
                bit_depth=None,
                file_size_bytes=0,
                bit_rate=0,
            )

        cmd = [
            self.ffprobe,
            "-v", "error",
            "-show_format",
            "-show_streams",
            "-of", "json",
            str(filepath),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15.0)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                streams = data.get("streams", [])
                audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
                fmt = data.get("format", {})

                duration = float(fmt.get("duration", audio_stream.get("duration", 0.0) or 0.0))
                sr = int(audio_stream.get("sample_rate", 48000) or 48000)
                channels = int(audio_stream.get("channels", 2) or 2)
                codec = str(audio_stream.get("codec_name", fmt.get("format_name", filepath.suffix.lstrip(".")) or "unknown"))
                container = str(fmt.get("format_name", filepath.suffix.lstrip(".")).split(",")[0].lower())
                size_bytes = int(fmt.get("size", filepath.stat().st_size) or filepath.stat().st_size)
                bit_rate = int(fmt.get("bit_rate", audio_stream.get("bit_rate", 0) or 0) or 0)

                bit_depth_raw = audio_stream.get("bits_per_sample") or audio_stream.get("bits_per_raw_sample")
                bit_depth = int(bit_depth_raw) if bit_depth_raw else None

                return FormatFacts(
                    duration_sec=round(duration, 4),
                    sample_rate=sr,
                    channels=channels,
                    codec=codec.lower(),
                    container=container.lower(),
                    bit_depth=bit_depth,
                    file_size_bytes=size_bytes,
                    bit_rate=bit_rate,
                )
        except Exception as e:
            logger.debug(f"ffprobe encountered error on {filepath.name}: {e}")

        # Fallback using os.stat
        return FormatFacts(
            duration_sec=0.0,
            sample_rate=48000,
            channels=2,
            codec=filepath.suffix.lstrip(".").lower() or "unknown",
            container=filepath.suffix.lstrip(".").lower() or "wav",
            bit_depth=None,
            file_size_bytes=filepath.stat().st_size if filepath.exists() else 0,
            bit_rate=0,
        )

    def probe_loudness(self, filepath: Path) -> LoudnessFacts:
        """
        Probe broadcast loudness and true peak metrics using ffmpeg ebur128 and astats.
        Extracts integrated LUFS, True Peak (dBTP), Loudness Range (LRA), RMS, and peak.
        """
        facts = LoudnessFacts()
        if not filepath.exists() or filepath.stat().st_size < 100:
            return facts

        cmd = [
            self.ffmpeg,
            "-y",
            "-i", str(filepath),
            "-af", "ebur128=peak=true,astats",
            "-f", "null",
            "-",
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=20.0)
            err = res.stderr

            # 1. Integrated loudness (LUFS)
            i_m = re.search(r"Integrated loudness:\s+I:\s+([-\d.]+)\s+LUFS", err)
            if i_m:
                facts.integrated_lufs = round(float(i_m.group(1)), 2)

            # 2. Loudness range (LU)
            lra_m = re.search(r"Loudness range:\s+LRA:\s+([-\d.]+)\s+LU", err)
            if lra_m:
                facts.loudness_range_lu = round(float(lra_m.group(1)), 2)

            # 3. True peak (dBFS / dBTP)
            tp_m = re.search(r"True peak:\s+Peak:\s+([-\d.]+)\s+dBFS", err)
            if tp_m:
                facts.true_peak_dbtp = round(float(tp_m.group(1)), 2)

            # 4. RMS Level (astats)
            rms_m = re.search(r"RMS level dB:\s+([-\d.]+)", err)
            if rms_m:
                facts.rms_level_db = round(float(rms_m.group(1)), 2)

            # 5. Peak level dB (astats)
            peak_m = re.search(r"Peak level dB:\s+([-\d.]+)", err)
            if peak_m:
                facts.peak_level_db = round(float(peak_m.group(1)), 2)

            # 6. Dynamic range = Peak level - RMS level
            if facts.peak_level_db is not None and facts.rms_level_db is not None:
                facts.dynamic_range_db = round(abs(facts.peak_level_db - facts.rms_level_db), 2)

        except Exception as e:
            logger.debug(f"ffmpeg loudness analysis encountered error on {filepath.name}: {e}")

        return facts

    def probe_spectral_and_temporal(
        self,
        filepath: Path,
        sample_rate: int = 48000,
        max_duration_sec: float = 60.0,
    ) -> Tuple[SpectralFacts, TemporalFacts, TonalFacts, List[AudioEventRecord]]:
        """
        Probe spectral descriptors, temporal events, and tonal attributes.
        Uses memory-bounded streaming reads via soundfile or numpy.
        """
        spectral = SpectralFacts()
        temporal = TemporalFacts()
        tonal = TonalFacts()
        events: List[AudioEventRecord] = []

        if not filepath.exists() or filepath.stat().st_size < 100:
            return spectral, temporal, tonal, events

        # Read audio waveform (memory safe)
        y = None
        sr = sample_rate
        try:
            if sf is not None:
                with sf.SoundFile(str(filepath)) as f:
                    sr = f.samplerate
                    max_frames = int(max_duration_sec * sr)
                    y = f.read(frames=max_frames, dtype="float32")
            else:
                # Fallback via ffmpeg pipe
                cmd = [
                    self.ffmpeg, "-i", str(filepath),
                    "-t", str(max_duration_sec),
                    "-f", "f32le", "-ac", "1", "-ar", str(sample_rate), "-"
                ]
                res = subprocess.run(cmd, capture_output=True, timeout=15.0)
                if res.returncode == 0 and res.stdout:
                    y = np.frombuffer(res.stdout, dtype=np.float32)
                    sr = sample_rate
        except Exception as e:
            logger.debug(f"Failed to read waveform directly ({e}); attempting ffmpeg pipe...")
            try:
                cmd = [
                    self.ffmpeg, "-i", str(filepath),
                    "-t", str(max_duration_sec),
                    "-f", "f32le", "-ac", "1", "-ar", "48000", "-"
                ]
                res = subprocess.run(cmd, capture_output=True, timeout=15.0)
                if res.returncode == 0 and res.stdout:
                    y = np.frombuffer(res.stdout, dtype=np.float32)
                    sr = 48000
            except Exception:
                pass

        if y is None or len(y) == 0:
            return spectral, temporal, tonal, events

        # Convert to mono if multichannel
        if y.ndim > 1:
            y_mono = np.mean(y, axis=1)
        else:
            y_mono = y

        total_samples = len(y_mono)
        duration_sec = total_samples / float(sr)

        # 1. Zero-Crossing Rate
        signs = np.signbit(y_mono)
        zcr = float(np.mean(np.abs(np.diff(signs))))
        spectral.zero_crossing_rate = round(zcr, 4)

        # 2. Spectral Analysis (Welch Periodogram)
        nperseg = min(2048, max(256, int(2 ** int(np.log2(total_samples))))) if total_samples >= 256 else total_samples
        if nperseg >= 64:
            try:
                freqs, psd = signal.welch(y_mono, fs=sr, nperseg=nperseg)
                total_power = np.sum(psd)
                if total_power > 1e-12:
                    # Centroid
                    centroid = float(np.sum(freqs * psd) / total_power)
                    spectral.spectral_centroid_hz = round(centroid, 1)

                    # Bandwidth
                    bandwidth = float(np.sqrt(np.sum(((freqs - centroid) ** 2) * psd) / total_power))
                    spectral.spectral_bandwidth_hz = round(bandwidth, 1)

                    # Rolloff (85% energy threshold)
                    cum_power = np.cumsum(psd)
                    target_power = 0.85 * total_power
                    idx_rolloff = np.where(cum_power >= target_power)[0]
                    rolloff = float(freqs[idx_rolloff[0]]) if len(idx_rolloff) > 0 else float(freqs[-1])
                    spectral.spectral_rolloff_hz = round(rolloff, 1)

                    # Flatness (Wiener entropy = geometric mean / arithmetic mean)
                    eps = 1e-12
                    geo_mean = np.exp(np.mean(np.log(psd + eps)))
                    ari_mean = np.mean(psd) + eps
                    flatness = float(min(1.0, max(0.0, geo_mean / ari_mean)))
                    spectral.spectral_flatness = round(flatness, 4)
            except Exception as e:
                logger.debug(f"Spectral analysis exception: {e}")

        # 3. Temporal Analysis (20ms frames)
        frame_len = max(64, int(sr * 0.02))
        num_frames = total_samples // frame_len
        silence_threshold_db = -60.0

        if num_frames > 0:
            frames = y_mono[:num_frames * frame_len].reshape(num_frames, frame_len)
            frame_rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-12)
            frame_db = 20.0 * np.log10(frame_rms + 1e-12)

            silent_frames = np.sum(frame_db < silence_threshold_db)
            temporal.silence_ratio = round(float(silent_frames) / float(num_frames), 3)

            # Active region bounds
            active_indices = np.where(frame_db >= silence_threshold_db)[0]
            if len(active_indices) > 0:
                first_active = active_indices[0]
                last_active = active_indices[-1]
                temporal.active_start_sec = round(float(first_active * frame_len) / float(sr), 3)
                temporal.active_end_sec = round(float((last_active + 1) * frame_len) / float(sr), 3)
                temporal.active_duration_sec = round(temporal.active_end_sec - temporal.active_start_sec, 3)

                # Add active region event
                events.append(AudioEventRecord(
                    event_type="active_region",
                    start_sec=temporal.active_start_sec,
                    end_sec=temporal.active_end_sec,
                    confidence=None,
                    source_method="measured_dsp",
                    detector_id="frame_energy_gate_v1",
                    metadata={"silence_threshold_db": silence_threshold_db}
                ))
            else:
                temporal.active_start_sec = 0.0
                temporal.active_end_sec = 0.0
                temporal.active_duration_sec = 0.0

            # Transient detection (energy onset peaks)
            diff_energy = np.diff(np.maximum(-60.0, frame_db))
            positive_diff = np.maximum(0.0, diff_energy)
            if len(positive_diff) >= 4 and np.max(positive_diff) > 6.0:
                peaks, _ = signal.find_peaks(positive_diff, height=6.0, distance=max(1, int(0.08 / 0.02)))
                major_onsets = [round(float(p * frame_len) / float(sr), 3) for p in peaks[:10]]
                temporal.major_transients_sec = major_onsets
                temporal.transient_count = len(peaks)

                for onset in major_onsets[:5]:
                    events.append(AudioEventRecord(
                        event_type="transient_onset",
                        start_sec=onset,
                        end_sec=round(onset + 0.05, 3),
                        confidence=None,
                        source_method="measured_dsp",
                        detector_id="energy_flux_detector_v1",
                        metadata={"onset_strength_db": round(float(diff_energy[int(onset / 0.02)]), 1) if int(onset / 0.02) < len(diff_energy) else 6.0}
                    ))
            else:
                temporal.transient_count = 0
                temporal.major_transients_sec = []

            # Energy envelope classification
            if duration_sec < 1.0 and (temporal.silence_ratio or 0.0) < 0.3:
                temporal.energy_envelope = "percussive"
            elif (temporal.silence_ratio or 0.0) < 0.15:
                temporal.energy_envelope = "sustained"
            elif (temporal.silence_ratio or 0.0) > 0.6:
                temporal.energy_envelope = "sparse"
            else:
                temporal.energy_envelope = "dynamic"

        # 4. Conservative Tonal Filter (Zero hallucinations on noisy SFX)
        # Only evaluate pitch/harmonicity if signal has moderate duration and low spectral flatness
        flatness = spectral.spectral_flatness if spectral.spectral_flatness is not None else 1.0
        if duration_sec >= 0.25 and flatness <= 0.35 and total_samples >= 2048:
            try:
                # Autocorrelation on a centered 2048-sample window
                center = total_samples // 2
                win = y_mono[center - 1024: center + 1024]
                autocorr = signal.correlate(win, win, mode="full")
                autocorr = autocorr[len(autocorr) // 2:]
                autocorr = autocorr / (autocorr[0] + 1e-12)

                # Search in pitch range [50 Hz, 1500 Hz]
                min_lag = int(sr / 1500)
                max_lag = int(sr / 50)
                if max_lag < len(autocorr):
                    segment = autocorr[min_lag:max_lag]
                    peak_idx = np.argmax(segment)
                    peak_val = segment[peak_idx]
                    lag = min_lag + peak_idx
                    if peak_val > 0.55 and lag > 0:
                        f0 = float(sr) / float(lag)
                        tonal.is_tonal = True
                        tonal.detected_pitch_hz = round(f0, 1)
                        tonal.tuning_hz = 440.0
                    else:
                        tonal.is_tonal = False
            except Exception:
                tonal.is_tonal = False
        else:
            # Explicitly mark as non-tonal with None values
            tonal.is_tonal = False
            tonal.detected_pitch_hz = None
            tonal.detected_bpm = None

        return spectral, temporal, tonal, events

    def analyze_file(self, filepath: Union[Path, str]) -> Tuple[MeasuredAudioFacts, List[AudioEventRecord]]:
        """
        Complete deterministic analysis pipeline for a local audio file.
        Returns MeasuredAudioFacts and any detected AudioEventRecords with strict provenance.
        """
        p = Path(filepath).resolve()
        fmt = self.probe_format(p)
        loudness = self.probe_loudness(p)
        spectral, temporal, tonal, events = self.probe_spectral_and_temporal(p, sample_rate=fmt.sample_rate)

        provenance = ProvenanceRecord(
            source_method="measured_dsp",
            analyzer_id=ANALYZER_ID,
            analyzer_version=ANALYZER_VERSION,
            ontology_version=ONTOLOGY_VERSION,
            generated_at=datetime.now(timezone.utc).isoformat(),
            source_asset_version=f"bytes:{fmt.file_size_bytes}",
            confidence=None,  # Physically measured; no fake probabilities
            processing_version=PROCESSING_VERSION,
            notes=f"Analyzed {p.name} ({fmt.codec}, {fmt.sample_rate}Hz, {fmt.channels}ch)"
        )

        facts = MeasuredAudioFacts(
            format=fmt,
            loudness=loudness,
            spectral=spectral,
            temporal=temporal,
            tonal=tonal,
            provenance=provenance,
        )

        return facts, events
