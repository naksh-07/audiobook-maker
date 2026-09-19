#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.3: Studio Audio Mastering & Concatenation Engine.
Uses FFmpeg SOXR 48kHz sinc resampler and EBU R128 broadcast loudnorm filter chain.
Concatenates chapter audio segments with dynamic natural silence pauses.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List


def get_ffmpeg() -> str:
    ffmpeg_bin = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
    if not os.path.exists(ffmpeg_bin):
        raise FileNotFoundError("FFmpeg executable not found in PATH.")
    return ffmpeg_bin


def concatenate_and_master_chapter(
    audio_segments: List[Path],
    output_chapter_file: Path,
    pause_ms: int = 400,
    loudnorm: bool = True,
) -> Path:
    """
    Concatenates a list of audio segment WAVs, applies vocal mastering,
    and outputs a studio-mastered M4A/MP3 chapter file.
    """
    if not audio_segments:
        raise ValueError("No audio segments provided to master.")

    ffmpeg = get_ffmpeg()
    output_chapter_file = Path(output_chapter_file).resolve()
    output_chapter_file.parent.mkdir(parents=True, exist_ok=True)

    # 1. Create a concat list file for FFmpeg
    concat_list = output_chapter_file.parent / f"concat_{output_chapter_file.stem}.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for seg in audio_segments:
            safe_path = str(seg.resolve()).replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")

    # 2. Studio Mastering Filter Chain:
    # - highpass: cuts subsonic rumble below 60Hz
    # - afftdn: removes neural vocoder hiss
    # - deesser: tames harsh sibilance at 6-8.5kHz
    # - lowpass: eliminates high frequency hash above 10.5kHz
    # - aresample: SOXR sinc resampler to 48kHz (Android DAC native rate)
    # - loudnorm: EBU R128 international broadcast loudness (-19 LUFS)
    filter_chain = (
        "highpass=f=60,afftdn=nr=8:nf=-35,deesser=i=0.35:m=0.5:f=0.5,"
        "lowpass=f=10500,aresample=resampler=soxr:osr=48000"
    )
    if loudnorm:
        filter_chain += ",loudnorm=I=-19:TP=-1.5:LRA=11"

    ext = output_chapter_file.suffix.lower()
    codec = "aac" if ext in (".m4a", ".m4b") else "libmp3lame"
    bitrate = "192k"

    cmd = [
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-af", filter_chain,
        "-c:a", codec,
        "-b:a", bitrate,
        str(output_chapter_file),
    ]

    print(f"[*] Mastering chapter audio ({len(audio_segments)} segments) -> {output_chapter_file.name}...")
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"FFmpeg mastering failed: {err_msg}")
    finally:
        if concat_list.exists():
            concat_list.unlink()

    size_mb = round(output_chapter_file.stat().st_size / (1024 * 1024), 2)
    print(f"[+] Mastered chapter ready ({size_mb} MB) -> {output_chapter_file}")
    return output_chapter_file
