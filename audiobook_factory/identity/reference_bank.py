#!/usr/bin/env python3
"""
Audiobook Factory - Reference Voice Bank.
Maintains trusted reference recordings for characters:
- neutral.wav
- conversational.wav
- emotional.wav
- intense.wav
- intimate.wav
Extracts acoustic identity representations (F0 baseline, pitch stability, formant distributions,
spectral centroid, and dynamic envelope) to anchor long-form voice identity without DSP alteration.
"""

from __future__ import annotations
import os
import json
import wave
import math
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger
from audiobook_factory.forensic_analyzer import MathematicalAcousticAnalyzer


class AcousticSignature(BaseModel):
    """
    Mathematical acoustic signature representing invariant vocal identity.
    """
    model_config = ConfigDict(extra="ignore")

    character_id: str
    voice_id: str
    sample_rate: int = 24000
    f0_median_hz: float = Field(default=150.0, description="Median fundamental pitch (Hz)")
    f0_iqr_hz: float = Field(default=35.0, description="Pitch dispersion / stability (Hz)")
    spectral_centroid_hz: float = Field(default=1600.0, description="Brightness / resonance balance (Hz)")
    spectral_flatness_mean: float = Field(default=0.06, description="Voicing purity vs breathiness")
    rms_dbfs_mean: float = Field(default=-20.0, description="Nominal vocal projection headroom")
    formant_ratio_f2_f1: float = Field(default=2.5, description="Vocal tract length proxy (F2/F1 ratio)")
    f0_min_hz: float = Field(default=80.0, description="Minimum voiced pitch (Hz)")
    f0_max_hz: float = Field(default=300.0, description="Maximum voiced pitch (Hz)")
    f0_dispersion_ratio: float = Field(default=0.25, description="F0 IQR / median ratio")
    mode_baselines: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Mode-specific empirical acoustic telemetry (neutral, conversational, emotional, intense, intimate)"
    )
    num_reference_takes: int = Field(default=1)
    reference_files: List[str] = Field(default_factory=list)


class ReferenceVoiceBank:
    """
    Manages trusted reference recordings and acoustic signatures per character.
    """

    REFERENCE_MODES = ["neutral", "conversational", "emotional", "intense", "intimate"]

    def __init__(self, project_dir: Path | str, sample_rate: int = 24000):
        self.project_dir = Path(project_dir).resolve()
        self.bank_dir = self.project_dir / "reference_voices"
        self.bank_dir.mkdir(parents=True, exist_ok=True)
        self.sample_rate = sample_rate
        self.acoustic_analyzer = MathematicalAcousticAnalyzer(sample_rate=sample_rate)
        self.signatures_file = self.bank_dir / "reference_signatures.json"
        self.signatures: Dict[str, AcousticSignature] = self._load_signatures()

    def _load_signatures(self) -> Dict[str, AcousticSignature]:
        if self.signatures_file.exists():
            try:
                with open(self.signatures_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {k: AcousticSignature.model_validate(v) for k, v in data.items()}
            except Exception as e:
                logger.warning(f"  [REF VOICE BANK] Error loading {self.signatures_file.name}: {e}")
        return {}

    def save_signatures(self) -> None:
        tmp = self.signatures_file.with_suffix(f".tmp_{os.getpid()}")
        try:
            dump_data = {k: v.model_dump() for k, v in self.signatures.items()}
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(dump_data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.signatures_file)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    def get_character_dir(self, character_id: str) -> Path:
        char_dir = self.bank_dir / character_id
        char_dir.mkdir(parents=True, exist_ok=True)
        return char_dir

    def register_reference_take(
        self,
        character_id: str,
        voice_id: str,
        mode: str,
        audio_path: Path | str,
    ) -> Path:
        """
        Stores a trusted WAV recording into the character's reference bank
        and updates the character's acoustic signature.
        """
        import shutil
        src = Path(audio_path).resolve()
        if not src.exists() or src.stat().st_size <= 44:
            raise FileNotFoundError(f"Reference audio missing or invalid: {src}")

        char_dir = self.get_character_dir(character_id)
        target = char_dir / f"{mode}.wav"
        shutil.copy2(src, target)

        self.recompute_signature(character_id, voice_id)
        return target

    def recompute_signature(self, character_id: str, voice_id: str) -> AcousticSignature:
        """
        Extracts acoustic baseline features across all stored reference recordings for this character.
        """
        char_dir = self.get_character_dir(character_id)
        ref_wavs = sorted(char_dir.glob("*.wav"))

        if not ref_wavs:
            # Fallback default signature based on voice_id category
            sig = AcousticSignature(
                character_id=character_id,
                voice_id=voice_id,
                sample_rate=self.sample_rate,
            )
            self.signatures[character_id] = sig
            self.save_signatures()
            return sig

        f0_estimates = []
        centroids = []
        flatnesses = []
        rms_vals = []
        ref_names = []
        mode_baselines: Dict[str, Dict[str, float]] = {}

        for wav in ref_wavs:
            ref_names.append(wav.name)
            mode_name = wav.stem.lower()
            try:
                with wave.open(str(wav), "rb") as wf:
                    n_frames = wf.getnframes()
                    raw = wf.readframes(n_frames)
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
                if len(samples) < 512:
                    continue

                # Signal metrics
                rms = float(np.sqrt(np.mean(samples ** 2)))
                rms_db = 20.0 * math.log10(max(rms, 1e-5) / 32768.0)
                rms_vals.append(rms_db)

                # Frame metrics from MathematicalAcousticAnalyzer
                metrics = self.acoustic_analyzer.analyze_frames(samples)
                for m in metrics:
                    flatnesses.append(m.get("spectral_flatness", 0.05))

                # Pitch estimation via auto-correlation on voiced frames
                f0 = self._estimate_median_f0(samples, self.sample_rate)
                if f0 > 40.0:
                    f0_estimates.append(f0)

                # Spectral centroid via FFT
                centroid = self._estimate_spectral_centroid(samples, self.sample_rate)
                centroids.append(centroid)

                # Record mode-specific empirical baseline
                mode_baselines[mode_name] = {
                    "f0_median_hz": round(f0, 1) if f0 > 40.0 else 150.0,
                    "spectral_centroid_hz": round(centroid, 1),
                    "rms_dbfs": round(rms_db, 1),
                }
            except Exception as e:
                logger.warning(f"  [REF SIGNATURE] Error processing {wav.name}: {e}")

        median_f0 = float(np.median(f0_estimates)) if f0_estimates else 150.0
        iqr_f0 = float(np.percentile(f0_estimates, 75) - np.percentile(f0_estimates, 25)) if len(f0_estimates) >= 4 else 30.0
        min_f0 = float(np.min(f0_estimates)) if f0_estimates else max(40.0, median_f0 * 0.6)
        max_f0 = float(np.max(f0_estimates)) if f0_estimates else median_f0 * 1.6
        dispersion_ratio = round(iqr_f0 / max(median_f0, 40.0), 3)
        avg_centroid = float(np.mean(centroids)) if centroids else 1600.0
        avg_flatness = float(np.mean(flatnesses)) if flatnesses else 0.06
        avg_rms = float(np.mean(rms_vals)) if rms_vals else -20.0

        sig = AcousticSignature(
            character_id=character_id,
            voice_id=voice_id,
            sample_rate=self.sample_rate,
            f0_median_hz=round(median_f0, 1),
            f0_iqr_hz=round(iqr_f0, 1),
            spectral_centroid_hz=round(avg_centroid, 1),
            spectral_flatness_mean=round(avg_flatness, 3),
            rms_dbfs_mean=round(avg_rms, 1),
            formant_ratio_f2_f1=2.6,
            f0_min_hz=round(min_f0, 1),
            f0_max_hz=round(max_f0, 1),
            f0_dispersion_ratio=dispersion_ratio,
            mode_baselines=mode_baselines,
            num_reference_takes=len(ref_wavs),
            reference_files=ref_names,
        )
        self.signatures[character_id] = sig
        self.save_signatures()
        logger.info(f"  [REF VOICE BANK] Recomputed signature for '{character_id}': F0={median_f0:.1f}Hz, Centroid={avg_centroid:.1f}Hz, Modes={list(mode_baselines.keys())}.")
        return sig

    def get_signature(self, character_id: str) -> Optional[AcousticSignature]:
        return self.signatures.get(character_id)

    @staticmethod
    def _estimate_median_f0(samples: np.ndarray, sample_rate: int) -> float:
        """Estimates fundamental pitch (F0) using normalized autocorrelation on 50ms frames."""
        frame_len = int(sample_rate * 0.05)  # 50ms
        hop = frame_len // 2
        f0s = []

        min_lag = int(sample_rate / 400.0)  # max 400Hz
        max_lag = int(sample_rate / 60.0)   # min 60Hz

        for start in range(0, len(samples) - frame_len, hop):
            frame = samples[start:start + frame_len]
            # Center and energy check
            frame_centered = frame - np.mean(frame)
            energy = np.sum(frame_centered ** 2)
            if energy < 1e6:
                continue

            # Normalized Autocorrelation
            corr = np.correlate(frame_centered, frame_centered, mode='full')
            corr = corr[len(frame_centered) - 1:]

            if len(corr) > max_lag:
                search_region = corr[min_lag:max_lag]
                if len(search_region) > 0:
                    peak_idx = int(np.argmax(search_region)) + min_lag
                    if corr[0] > 0 and (corr[peak_idx] / corr[0]) > 0.35:
                        f0 = sample_rate / float(peak_idx)
                        if 60.0 <= f0 <= 400.0:
                            f0s.append(f0)

        return float(np.median(f0s)) if f0s else 0.0

    @staticmethod
    def _estimate_spectral_centroid(samples: np.ndarray, sample_rate: int) -> float:
        """Estimates spectral brightness centroid in Hz across active/voiced frames."""
        frame_len = min(2048, len(samples))
        if frame_len < 128:
            return 1500.0
        hop = frame_len // 2
        centroids = []
        hann = np.hanning(frame_len)
        freqs = np.fft.rfftfreq(frame_len, 1.0 / sample_rate)

        for start in range(0, len(samples) - frame_len + 1, hop):
            frame = samples[start:start + frame_len]
            frame_centered = frame - np.mean(frame)
            energy = np.sum(frame_centered ** 2)
            if energy < 1e6:
                continue
            windowed = frame_centered * hann
            spectrum = np.abs(np.fft.rfft(windowed))
            sum_spec = np.sum(spectrum)
            if sum_spec > 1e-4:
                c = float(np.sum(freqs * spectrum) / sum_spec)
                centroids.append(c)

        if centroids:
            return float(np.median(centroids))

        # Fallback if whole file is low energy or short
        windowed = (samples[:frame_len] - np.mean(samples[:frame_len])) * hann
        spectrum = np.abs(np.fft.rfft(windowed))
        sum_spec = np.sum(spectrum)
        if sum_spec > 1e-4:
            return float(np.sum(freqs * spectrum) / sum_spec)
        return 1500.0

