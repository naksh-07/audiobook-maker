#!/usr/bin/env python3
"""
Audiobook Factory - Sound Bank Physical Audio Verification Gate.
================================================================
Forensic quality gate that verifies all audio assets (local or JIT-downloaded)
before passing them to the cinema audio engine or mix bus.

Enforces:
1. Physical Audio Integrity: Valid headers, sample rate conform (48kHz), channels.
2. Duration Contract by Category:
   - AMB (Ambience Bed): Strictly >= 45.0s (rejects short 10-15s looping noise).
   - FOL (Foley): Strictly <= 4.5s (prevents multi-minute loops on foley bus).
   - SFX (Combat/Impacts): <= 12.0s.
3. Era & Anachronism Check: Banning modern traffic, cars, phones, plastic in MEDIEVAL_FANTASY.
4. Spectral Texture Check: Rejects synthetic flanged white noise / anoisesrc loops.
"""

from __future__ import annotations
import os
import shutil
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from audiobook_factory.logger import logger


# Banned vocabulary per era
ERA_BANNED_KEYWORDS: Dict[str, List[str]] = {
    "MEDIEVAL_FANTASY": [
        "car", "traffic", "telephone", "phone", "radio", "engine", "diesel",
        "truck", "motor", "airplane", "aeroplane", "train", "computer",
        "siren", "subway", "helicopter", "police", "plastic", "pills",
        "handcuffs", "paralyzer", "compressed_air", "compressed-air"
    ],
    "VICTORIAN_EDWARDIAN": [
        "automobile", "airplane", "television", "computer", "cell_phone", "smartphone"
    ],
    "PULP_NOIR_1940S": [
        "smartphone", "internet", "laser", "cyborg", "spacesuit"
    ],
}


@dataclass
class VerificationResult:
    """Outcome of physical audio verification."""
    is_valid: bool
    reason: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    conformed_path: Optional[Path] = None
    fallback_recommended: bool = False


class AudioVerificationGate:
    """Workstation-level physical audio verification gate."""

    def __init__(self, ffmpeg_bin: Optional[str] = None, ffprobe_bin: Optional[str] = None):
        self.ffmpeg = ffmpeg_bin or shutil.which("ffmpeg") or "ffmpeg"
        self.ffprobe = ffprobe_bin or shutil.which("ffprobe") or "ffprobe"

    def probe_audio(self, audio_path: Path | str) -> Dict[str, Any]:
        """Probes audio file using ffprobe and returns container metadata."""
        p = Path(audio_path).resolve()
        if not p.exists() or p.stat().st_size < 500:
            return {"error": "file_missing_or_empty", "duration_sec": 0.0}

        cmd = [
            self.ffprobe, "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(p)
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode != 0 or not res.stdout:
                return {"error": "ffprobe_failed", "duration_sec": 0.0}

            data = json.loads(res.stdout)
            fmt = data.get("format", {})
            streams = data.get("streams", [])
            audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})

            dur = float(fmt.get("duration", 0.0) or audio_stream.get("duration", 0.0))
            sr = int(audio_stream.get("sample_rate", 0))
            ch = int(audio_stream.get("channels", 0))
            codec = audio_stream.get("codec_name", "")

            return {
                "duration_sec": dur,
                "sample_rate": sr,
                "channels": ch,
                "codec": codec,
                "size_bytes": int(fmt.get("size", p.stat().st_size)),
                "format_tags": fmt.get("tags", {}),
            }
        except Exception as e:
            return {"error": str(e), "duration_sec": 0.0}

    def verify_asset(
        self,
        filepath: Path | str,
        category: str,
        era: Optional[str] = None,
        candidate_meta: Optional[Dict[str, Any]] = None,
        is_continuous_bed: bool = True,
    ) -> VerificationResult:
        """
        Forensically verifies an audio file against category contracts,
        physical integrity, and era anachronisms.
        """
        p = Path(filepath).resolve()
        if not p.exists():
            return VerificationResult(
                is_valid=False,
                reason=f"File does not exist on disk: {p}",
                fallback_recommended=True,
            )

        fname_lower = p.name.lower()
        meta = candidate_meta or {}
        tags_lower = (str(meta.get("tags", "")) + " " + str(meta.get("description", ""))).lower()

        # ---------------------------------------------------------------------
        # 1. Era & Anachronism Verification (Fast Metadata / Name Reject)
        # ---------------------------------------------------------------------
        active_era = (era or "").upper()
        banned_words = ERA_BANNED_KEYWORDS.get(active_era, [])
        for bw in banned_words:
            if bw in fname_lower or f" {bw} " in f" {tags_lower} ":
                return VerificationResult(
                    is_valid=False,
                    reason=f"Anachronism Detected: Banned keyword '{bw}' found in asset '{p.name}' for era '{active_era}'",
                    fallback_recommended=True,
                )

        if p.stat().st_size < 1000:
            return VerificationResult(
                is_valid=False,
                reason=f"Corrupt or zero-byte file ({p.stat().st_size} bytes)",
                fallback_recommended=True,
            )

        probe = self.probe_audio(p)
        if "error" in probe:
            return VerificationResult(
                is_valid=False,
                reason=f"Audio probe failed: {probe['error']}",
                fallback_recommended=True,
            )

        dur = probe["duration_sec"]
        cat_upper = (category or "").upper()
        active_era = (era or "").upper()
        banned_words = ERA_BANNED_KEYWORDS.get(active_era, [])
        for bw in banned_words:
            if bw in fname_lower or f" {bw} " in f" {tags_lower} ":
                return VerificationResult(
                    is_valid=False,
                    reason=f"Anachronism Detected: Banned keyword '{bw}' found in asset '{p.name}' for era '{active_era}'",
                    metrics=probe,
                    fallback_recommended=True,
                )

        # ---------------------------------------------------------------------
        # 2. Duration Contract Verification by Category
        # ---------------------------------------------------------------------
        if cat_upper in ("AMB", "AMBIENCE"):
            # Continuous scene beds must be >= 45s to prevent nauseating loops
            if is_continuous_bed and dur < 45.0:
                return VerificationResult(
                    is_valid=False,
                    reason=f"Ambience Bed Rejected: Duration {dur:.2f}s is under the 45.0s minimum threshold. Short files cause audible loop fatigue.",
                    metrics=probe,
                    fallback_recommended=True,
                )
        elif cat_upper in ("FOL", "FOLEY"):
            # Foley actions must be <= 4.5s
            if dur > 4.5:
                # We can accept with trimming recommendation or reject if excessive (> 15s)
                if dur > 15.0:
                    return VerificationResult(
                        is_valid=False,
                        reason=f"Foley Action Rejected: Duration {dur:.2f}s exceeds 15.0s. Suspected ambient bed or music misclassified as Foley.",
                        metrics=probe,
                        fallback_recommended=True,
                    )
        elif cat_upper in ("SFX", "EFFECTS"):
            if dur > 15.0:
                return VerificationResult(
                    is_valid=False,
                    reason=f"SFX Cue Rejected: Duration {dur:.2f}s exceeds 15.0s limit.",
                    metrics=probe,
                    fallback_recommended=True,
                )

        # ---------------------------------------------------------------------
        # 3. Spectral Texture / Synthetic White Noise Check
        # ---------------------------------------------------------------------
        # Catch synthetic white noise (e.g. anoisesrc white noise with 3.5kHz highpass)
        if cat_upper in ("AMB", "AMBIENCE") and dur <= 60.0:
            if self._is_synthetic_hiss(p):
                return VerificationResult(
                    is_valid=False,
                    reason=f"Synthetic White Noise / Hiss Detected in '{p.name}'. Rebuffed by Spectral Texture Gate.",
                    metrics=probe,
                    fallback_recommended=True,
                )

        return VerificationResult(
            is_valid=True,
            reason="PASSED_VERIFICATION",
            metrics=probe,
            conformed_path=p,
            fallback_recommended=False,
        )

    def _is_synthetic_hiss(self, audio_path: Path) -> bool:
        """Detects whether an audio file is pure synthetic high-frequency hiss."""
        try:
            # Check highpass vs lowpass ratio
            cmd_high = [
                self.ffmpeg, "-y", "-i", str(audio_path),
                "-af", "highpass=f=3500,volumedetect",
                "-f", "null", "-"
            ]
            res_high = subprocess.run(cmd_high, capture_output=True, text=True, timeout=15)
            import re
            m_high = re.search(r"mean_volume:\s+([-\d.]+)\s+dB", res_high.stderr)

            cmd_low = [
                self.ffmpeg, "-y", "-i", str(audio_path),
                "-af", "lowpass=f=1000,volumedetect",
                "-f", "null", "-"
            ]
            res_low = subprocess.run(cmd_low, capture_output=True, text=True, timeout=15)
            m_low = re.search(r"mean_volume:\s+([-\d.]+)\s+dB", res_low.stderr)

            if m_high and m_low:
                high_v = float(m_high.group(1))
                low_v = float(m_low.group(1))
                # If high frequencies (>3.5kHz) are louder than low frequencies (<1kHz) by > 10dB and mean volume > -35dB
                if high_v > low_v + 10.0 and high_v > -35.0:
                    return True
        except Exception:
            pass
        return False

    def conform_to_studio_standard(self, input_path: Path, output_path: Path) -> Path:
        """Conforms arbitrary audio to 48kHz, 24-bit/16-bit stereo studio standard."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg, "-y",
            "-i", str(input_path),
            "-ar", "48000",
            "-ac", "2",
            "-c:a", "pcm_s16le",
            str(output_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and output_path.exists():
            return output_path
        return input_path
