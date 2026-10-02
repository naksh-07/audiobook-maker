#!/usr/bin/env python3
"""
Audiobook Factory - Soundscape Engine: Dynamic Sidechain Compression & Ducking.
Ducks background musical beds and ambience relative to dialogue energy levels.
"""

from __future__ import annotations
import subprocess
from pathlib import Path

from audiobook_factory.soundscape_engine.probe import get_ffmpeg, get_audio_duration


def apply_dynamic_sidechain_ducking(
    vocal_file: Path,
    bgm_file: Path,
    output_file: Path,
    duck_attenuation_db: float = -16.0,
    attack_ms: int = 150,
    release_ms: int = 850,
) -> Path:
    """
    Apply broadcast-grade Dynamic Sidechain Compression.
    Ducks the BGM volume automatically by `duck_attenuation_db` whenever vocal dialogue is active,
    and smoothly allows the background score to swell during sentence and chapter pauses.
    """
    ffmpeg = get_ffmpeg()
    vocal_file = Path(vocal_file).resolve()
    bgm_file = Path(bgm_file).resolve()
    output_file = Path(output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    vocal_dur = get_audio_duration(vocal_file)

    # Compute compression ratio and threshold dynamically from duck_attenuation_db
    attenuation = abs(duck_attenuation_db)
    ratio = max(2.0, min(20.0, attenuation / 2.0))
    threshold = max(0.02, min(0.12, 0.06 * (16.0 / max(4.0, attenuation))))

    # Sidechain compression filter chain:
    # 1. Loop BGM if shorter than vocal track, trim to vocal duration + 1.0s tail
    # 2. Sidechain compressor: uses vocal track (input 1) to attenuate BGM (input 0)
    # 3. Mix ducked BGM with vocals, preserving crisp speech intelligibility
    filter_complex = (
        f"[1:a]asplit=2[voc_sc][voc_clean];"
        f"[0:a]aloop=loop=-1:size=2e+09,atrim=0:{vocal_dur + 1.5:.2f},"
        f"volume=0.35,afade=t=in:ss=0:d=2.0,afade=t=out:st={max(0.0, vocal_dur - 2.0):.2f}:d=3.5[bgm_trimmed];"
        f"[bgm_trimmed][voc_sc]sidechaincompress=threshold={threshold:.3f}:ratio={ratio:.1f}:attack={attack_ms}:release={release_ms}:knee=2.5[bgm_ducked];"
        f"[voc_clean]volume=1.0[voc_gain];"
        f"[bgm_ducked][voc_gain]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[mixed];"
        f"[mixed]aresample=osr=48000,loudnorm=I=-19:TP=-1.5:LRA=11,alimiter=limit=0.89:attack=5:release=50[out]"
    )

    ext = output_file.suffix.lower()
    codec = "aac" if ext in (".m4a", ".m4b") else "pcm_s16le"
    bitrate_args = ["-b:a", "192k"] if codec == "aac" else []

    cmd = [
        ffmpeg, "-y",
        "-i", str(bgm_file),
        "-i", str(vocal_file),
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-ac", "2",
        "-ar", "48000",
        "-c:a", codec,
        *bitrate_args,
        str(output_file)
    ]

    print(f"[*] Applying dynamic sidechain ducking ({vocal_file.name} + {bgm_file.name}) -> {output_file.name}...")
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"[+] Ducked master audio ready -> {output_file}")
        return output_file
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"Sidechain ducking failed: {err}")
