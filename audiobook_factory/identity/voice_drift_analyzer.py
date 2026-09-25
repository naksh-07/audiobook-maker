#!/usr/bin/env python3
"""
Audiobook Factory - Voice Identity & Drift Analyzer (Gate 3.6 / Phase 15).
Compares synthesized takes against trusted Reference Voice Bank acoustic signatures.
Verifies that character vocal identity remains recognizable across thousands of lines
without penalizing authentic dramatic emotion.
"""

from __future__ import annotations
import math
import wave
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger
from .reference_bank import AcousticSignature, ReferenceVoiceBank
from .voice_dna import VoiceDNA


class VoiceIdentityDriftResult(BaseModel):
    """
    Verification outcome of a synthesized take against character acoustic identity.
    """
    model_config = ConfigDict(extra="ignore")

    take_id: str
    character_id: str
    voice_id: str
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    drift_detected: bool = False
    f0_measured_hz: float = 0.0
    f0_baseline_hz: float = 0.0
    f0_deviation_pct: float = 0.0
    centroid_measured_hz: float = 0.0
    centroid_baseline_hz: float = 0.0
    recommendation: Literal["pass", "regenerate", "downgrade"] = "pass"
    diagnostics: List[str] = Field(default_factory=list)


class VoiceIdentityAnalyzer:
    """
    World-Class Acoustic Voice Identity & Drift Detector.
    Evaluates fundamental pitch stability, formant envelope, and spectral brightness.
    Calibrates tolerance dynamically based on the dramatic intensity of the scene.
    """

    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate

    def analyze_take_identity(
        self,
        take_id: str,
        audio_path: Path | str,
        signature: Optional[AcousticSignature] = None,
        voice_dna: Optional[VoiceDNA] = None,
        dramatic_emotion: str = "neutral",
        intensity: str = "medium",
    ) -> VoiceIdentityDriftResult:
        """
        Analyzes a single take against character acoustic signature.
        """
        p = Path(audio_path).resolve()
        if not p.exists() or p.stat().st_size <= 44:
            return VoiceIdentityDriftResult(
                take_id=take_id,
                character_id=signature.character_id if signature else "unknown",
                voice_id=signature.voice_id if signature else "unknown",
                similarity_score=0.0,
                drift_detected=True,
                recommendation="regenerate",
                diagnostics=["Audio file missing or empty"],
            )

        # Default fallback signature if not yet established
        if not signature:
            return VoiceIdentityDriftResult(
                take_id=take_id,
                character_id=voice_dna.character_id if voice_dna else "unknown",
                voice_id=voice_dna.voice_id if voice_dna else "unknown",
                similarity_score=0.88,
                drift_detected=False,
                recommendation="pass",
                diagnostics=["No baseline signature registered; accepted as initial anchor"],
            )

        # 1. Read PCM samples
        try:
            with wave.open(str(p), "rb") as wf:
                n_frames = wf.getnframes()
                raw = wf.readframes(n_frames)
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        except Exception as e:
            return VoiceIdentityDriftResult(
                take_id=take_id,
                character_id=signature.character_id,
                voice_id=signature.voice_id,
                similarity_score=0.0,
                drift_detected=True,
                recommendation="regenerate",
                diagnostics=[f"WAV read error: {e}"],
            )

        if len(samples) < 512:
            return VoiceIdentityDriftResult(
                take_id=take_id,
                character_id=signature.character_id,
                voice_id=signature.voice_id,
                similarity_score=0.0,
                drift_detected=True,
                recommendation="regenerate",
                diagnostics=["Audio buffer too short for identity analysis"],
            )

        # 2. Extract Acoustic Metrics from Take
        measured_f0 = ReferenceVoiceBank._estimate_median_f0(samples, self.sample_rate)
        measured_centroid = ReferenceVoiceBank._estimate_spectral_centroid(samples, self.sample_rate)

        diagnostics: List[str] = []
        scores: List[float] = []

        # 3. Contextual Tolerance Scaling based on Character-Specific Reference Distribution
        baseline_f0 = signature.f0_median_hz
        baseline_centroid = signature.spectral_centroid_hz

        # Determine contextual dramatic mode
        clean_emo = dramatic_emotion.lower()
        clean_intensity = intensity.lower()
        target_mode = "neutral"
        if "anger" in clean_emo or "explosive" in clean_intensity or "battle" in clean_emo or "rage" in clean_emo:
            target_mode = "intense"
        elif "whisper" in clean_emo or "intimate" in clean_emo or "vulnerable" in clean_emo or "close" in clean_emo:
            target_mode = "intimate"
        elif "grief" in clean_emo or "cry" in clean_emo or "sad" in clean_emo or "sorrow" in clean_emo:
            target_mode = "emotional"
        elif "conversational" in clean_emo:
            target_mode = "conversational"

        # Check if character has a calibrated baseline for this dramatic mode
        mode_baselines = getattr(signature, "mode_baselines", {}) or {}
        if target_mode in mode_baselines:
            mode_data = mode_baselines[target_mode]
            baseline_f0 = mode_data.get("f0_median_hz", baseline_f0)
            baseline_centroid = mode_data.get("spectral_centroid_hz", baseline_centroid)

        # Calibrate pitch tolerance from character's own empirical dispersion/IQR
        char_dispersion = (
            signature.f0_dispersion_ratio
            if hasattr(signature, "f0_dispersion_ratio") and signature.f0_dispersion_ratio > 0.0
            else (signature.f0_iqr_hz / max(signature.f0_median_hz, 40.0))
        )
        # Contextual tolerance derived from character distribution, not hard-coded universal percentages
        max_allowed_f0_dev = max(0.25, min(0.60, char_dispersion * 1.8))
        if target_mode in ("intense", "emotional"):
            max_allowed_f0_dev = min(0.65, max_allowed_f0_dev * 1.3)
        elif target_mode == "intimate":
            max_allowed_f0_dev = min(0.55, max_allowed_f0_dev * 1.2)

        # 4. Fundamental Pitch (F0) Comparison
        f0_dev_pct = 0.0
        f0_score = 1.0
        if measured_f0 > 40.0 and baseline_f0 > 40.0:
            f0_dev_pct = abs(measured_f0 - baseline_f0) / baseline_f0
            if f0_dev_pct <= max_allowed_f0_dev:
                f0_score = 1.0 - (f0_dev_pct / max_allowed_f0_dev) * 0.25
                diagnostics.append(f"Pitch contour verified (F0: {measured_f0:.1f}Hz vs baseline {baseline_f0:.1f}Hz)")
            else:
                f0_score = max(0.2, 1.0 - (f0_dev_pct - max_allowed_f0_dev) * 2.0)
                diagnostics.append(f"Excessive pitch divergence ({f0_dev_pct*100:.1f}% shift vs calibrated tolerance {max_allowed_f0_dev*100:.1f}%)")
        scores.append(f0_score)

        # 5. Spectral Centroid / Vocal Brightness Comparison
        c_score = 1.0
        if measured_centroid > 200.0 and baseline_centroid > 200.0:
            c_dev_pct = abs(measured_centroid - baseline_centroid) / baseline_centroid
            # Formant brightness tolerance informed by character dispersion
            c_tol = max(0.35, min(0.55, char_dispersion * 2.0))
            if c_dev_pct <= c_tol:
                c_score = 1.0 - (c_dev_pct / c_tol) * 0.20
            else:
                c_score = max(0.3, 1.0 - (c_dev_pct - c_tol) * 1.5)
                diagnostics.append(f"Formant brightness shift ({c_dev_pct*100:.1f}% vs tolerance {c_tol*100:.1f}%)")
        scores.append(c_score)

        # Composite similarity calculation
        composite = float(np.mean(scores)) if scores else 0.85
        composite = round(max(0.0, min(1.0, composite)), 2)

        drift_detected = composite < 0.65 or f0_dev_pct > (max_allowed_f0_dev * 1.5)
        rec = "pass"
        if drift_detected:
            rec = "regenerate" if composite < 0.55 else "downgrade"

        # Catastrophic pitch or timbre divergence defense
        if f0_dev_pct > 1.0 or composite < 0.45:
            drift_detected = True
            rec = "regenerate"
            composite = min(composite, 0.40)
            if not any("Catastrophic" in d for d in diagnostics):
                diagnostics.append("Catastrophic voice drift: severe pitch or timbre divergence from character identity")

        return VoiceIdentityDriftResult(
            take_id=take_id,
            character_id=signature.character_id,
            voice_id=signature.voice_id,
            similarity_score=composite,
            drift_detected=drift_detected,
            f0_measured_hz=round(measured_f0, 1),
            f0_baseline_hz=round(baseline_f0, 1),
            f0_deviation_pct=round(f0_dev_pct * 100, 1),
            centroid_measured_hz=round(measured_centroid, 1),
            centroid_baseline_hz=round(baseline_centroid, 1),
            recommendation=rec,
            diagnostics=diagnostics,
        )
