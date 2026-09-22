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
    target_lufs: float = -19.0,
    true_peak_db: float = -1.5,
    loudness_range: float = 11.0,
    target_sample_rate: int = 48000,
) -> Path:
    """
    Concatenates a list of audio segment WAVs, applies vocal mastering,
    and outputs a studio-mastered M4A/MP3 chapter file with dynamic mastering parameters.
    """
    if not audio_segments:
        raise ValueError("No audio segments provided to master.")

    ffmpeg = get_ffmpeg()
    output_chapter_file = Path(output_chapter_file).resolve()
    output_chapter_file.parent.mkdir(parents=True, exist_ok=True)

    import wave

    # Determine audio format (sample rate and channels) from the first segment
    sample_rate = 24000
    channels = 1
    try:
        with wave.open(str(audio_segments[0].resolve()), "rb") as wf:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
    except Exception:
        pass

    silence_file = None
    if pause_ms > 0 and len(audio_segments) > 1:
        silence_dur = max(0.05, pause_ms / 1000.0)
        silence_file = output_chapter_file.parent / f".silence_{sample_rate}_{channels}_{pause_ms}ms.wav"
        if not silence_file.exists():
            num_frames = int(sample_rate * silence_dur)
            silence_bytes = b"\x00" * (num_frames * channels * 2)
            with wave.open(str(silence_file), "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(silence_bytes)

    # 1. Create a concat list file for FFmpeg
    concat_list = output_chapter_file.parent / f"concat_{output_chapter_file.stem}.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for i, seg in enumerate(audio_segments):
            safe_path = str(seg.resolve()).replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")
            if silence_file and i < len(audio_segments) - 1:
                safe_silence = str(silence_file.resolve()).replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{safe_silence}'\n")

    # 2. Studio Mastering Filter Chain with dynamic loudnorm & resample parameters:
    # - aresample: resample to target_sample_rate so deesser operates on calibrated frequency
    # - highpass: cuts subsonic rumble below 60Hz
    # - afftdn: removes neural vocoder hiss (placed first to catch broadband noise)
    # - deesser: tames harsh sibilance at ~6.7kHz (f=0.14 = 6720 / 48000 calibrated for 48kHz)
    # - lowpass: eliminates high frequency hash above 14kHz (preserves vocal air/clarity)
    # - loudnorm: dynamic EBU R128 international broadcast loudness
    filter_chain = (
        f"aresample=osr={target_sample_rate},highpass=f=60,afftdn=nr=8:nf=-35,deesser=i=0.35:m=0.5:f=0.14,"
        f"lowpass=f=14000"
    )
    if loudnorm:
        filter_chain += (
            f",loudnorm=I={target_lufs}:TP={true_peak_db}:LRA={loudness_range},"
            f"alimiter=limit=0.89:attack=5:release=50"
        )

    ext = output_chapter_file.suffix.lower()
    if ext in (".m4a", ".m4b"):
        codec = "aac"
        bitrate_args = ["-b:a", "192k"]
    elif ext == ".wav":
        codec = "pcm_s16le"
        bitrate_args = []
    else:
        codec = "libmp3lame"
        bitrate_args = ["-b:a", "192k"]

    cmd = [
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-af", filter_chain,
        "-ac", "2",
        "-ar", str(target_sample_rate),
        "-c:a", codec,
        *bitrate_args,
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
        if silence_file and silence_file.exists():
            try:
                silence_file.unlink()
            except Exception:
                pass

    size_mb = round(output_chapter_file.stat().st_size / (1024 * 1024), 2)
    print(f"[+] Mastered chapter ready ({size_mb} MB) -> {output_chapter_file}")
    return output_chapter_file
