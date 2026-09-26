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
from typing import List, Dict, Any, Optional


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
    script_segments: Optional[List[Dict[str, Any]]] = None,
    spatial_staging: bool = False,
    edit_plans: Optional[List[Any]] = None,
) -> Path:
    """
    Concatenates a list of audio segment WAVs, applies vocal mastering,
    and outputs a studio-mastered M4A/MP3 chapter file with dynamic mastering parameters.
    Supports script-aware dynamic pauses (pause_after_ms), organic breath timing (pre_roll_breath_ms),
    dialogue spatial soundstage positioning (spatial_staging), and editorial timeline realization (edit_plans).
    """
    if not audio_segments:
        raise ValueError("No audio segments provided to master.")

    ffmpeg = get_ffmpeg()
    output_chapter_file = Path(output_chapter_file).resolve()
    output_chapter_file.parent.mkdir(parents=True, exist_ok=True)

    import wave
    import math

    # Determine audio format (sample rate and channels) from the first segment
    sample_rate = 24000
    channels = 1
    try:
        with wave.open(str(audio_segments[0].resolve()), "rb") as wf:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
    except Exception:
        pass

    if spatial_staging:
        channels = 2

    silence_cache: Dict[int, Path] = {}
    spatial_cache: Dict[str, Path] = {}

    def _get_silence_file(dur_ms: int) -> Optional[Path]:
        dur_ms = max(20, min(3000, int(dur_ms)))
        if dur_ms in silence_cache:
            return silence_cache[dur_ms]
        s_file = output_chapter_file.parent / f".silence_{sample_rate}_{channels}_{dur_ms}ms.wav"
        if not s_file.exists():
            num_frames = int(sample_rate * (dur_ms / 1000.0))
            silence_bytes = b"\x00" * (num_frames * channels * 2)
            with wave.open(str(s_file), "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(silence_bytes)
        silence_cache[dur_ms] = s_file
        return s_file

    def _get_panned_segment(seg_path: Path, pan: float, s_idx: int) -> Path:
        clamped_pan = max(-1.0, min(1.0, float(pan)))
        # Constant-power panning rule: theta in [0, pi/2], center at pi/4
        theta = (math.pi / 4.0) * (1.0 + clamped_pan)
        gain_l = math.cos(theta)
        gain_r = math.sin(theta)

        panned_file = output_chapter_file.parent / f".panned_s{s_idx}_{clamped_pan:.2f}_{seg_path.stem}.wav"
        if not panned_file.exists():
            pan_filter = f"aresample={sample_rate},pan=stereo|c0={gain_l:.3f}*c0|c1={gain_r:.3f}*c0"
            p_cmd = [
                ffmpeg, "-y",
                "-i", str(seg_path.resolve()),
                "-af", pan_filter,
                "-c:a", "pcm_s16le",
                str(panned_file),
            ]
            res = subprocess.run(p_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode != 0 or not panned_file.exists():
                return seg_path
        spatial_cache[str(panned_file)] = panned_file
        return panned_file

    # Build segment dictionary by index if script_segments provided
    seg_meta_by_idx: Dict[int, Dict[str, Any]] = {}
    if script_segments:
        for s in script_segments:
            idx = s.get("index", 1) if isinstance(s, dict) else getattr(s, "index", 1)
            seg_meta_by_idx[idx] = s if isinstance(s, dict) else s.model_dump()

    # Index editorial plans if provided
    edit_plan_by_idx: Dict[int, Any] = {}
    if edit_plans:
        for p in edit_plans:
            matched_idx = None
            if hasattr(p, "metadata") and isinstance(p.metadata, dict) and "segment_index" in p.metadata:
                matched_idx = int(p.metadata["segment_index"])
            if matched_idx is None:
                st = getattr(p, "source_take", "")
                for part in st.split("_"):
                    if part.startswith("s") and part[1:].isdigit():
                        matched_idx = int(part[1:])
                        break
            if matched_idx is not None:
                edit_plan_by_idx[matched_idx] = p

    # 1. Create a concat list file for FFmpeg
    concat_list = output_chapter_file.parent / f"concat_{output_chapter_file.stem}.txt"
    try:
        with open(concat_list, "w", encoding="utf-8") as f:
            for i, seg in enumerate(audio_segments):
                # Extract segment index from filename if available (e.g. c001_s0005_hash.wav)
                s_idx = i + 1
                name_parts = seg.stem.split("_")
                for part in name_parts:
                    if part.startswith("s") and part[1:].isdigit():
                        s_idx = int(part[1:])
                        break

                seg_info = seg_meta_by_idx.get(s_idx, {})
                plan_for_seg = edit_plan_by_idx.get(s_idx)
                if plan_for_seg is None and edit_plans and i < len(edit_plans):
                    plan_for_seg = edit_plans[i]

                # Pre-roll breath / pause if specified
                pre_breath_ms = 0
                if plan_for_seg is not None and getattr(plan_for_seg, "pause_before_ms", 0) > 0:
                    pre_breath_ms = int(plan_for_seg.pause_before_ms)
                elif int(seg_info.get("pre_roll_breath_ms", 0) or 0) > 0:
                    pre_breath_ms = int(seg_info.get("pre_roll_breath_ms", 0))

                if pre_breath_ms > 0:
                    breath_silence = _get_silence_file(pre_breath_ms)
                    if breath_silence:
                        safe_breath = str(breath_silence.resolve()).replace("\\", "/").replace("'", "'\\''")
                        f.write(f"file '{safe_breath}'\n")

                if spatial_staging:
                    speaker = str(seg_info.get("speaker", "Narrator"))
                    seg_spatial = seg_info.get("spatial", {}) if isinstance(seg_info, dict) else getattr(seg_info, "spatial", None)
                    if isinstance(seg_spatial, dict):
                        pan = float(seg_spatial.get("pan", 0.0) or 0.0)
                    elif hasattr(seg_spatial, "pan"):
                        pan = float(getattr(seg_spatial, "pan", 0.0) or 0.0)
                    else:
                        pan = float(seg_info.get("spatial_pan", 0.0) or 0.0)

                    # Narrator lines remain dead-center
                    if speaker.lower() in ("narrator", "narration"):
                        pan = 0.0

                    panned_seg = _get_panned_segment(seg, pan, s_idx)
                    safe_path = str(panned_seg.resolve()).replace("\\", "/").replace("'", "'\\''")
                else:
                    safe_path = str(seg.resolve()).replace("\\", "/").replace("'", "'\\''")

                f.write(f"file '{safe_path}'\n")

                # Post-segment dramatic pause
                if i < len(audio_segments) - 1:
                    if plan_for_seg is not None and getattr(plan_for_seg, "pause_after_ms", None) is not None:
                        cur_pause_ms = int(plan_for_seg.pause_after_ms)
                    else:
                        cur_pause_ms = int(seg_info.get("pause_after_ms", pause_ms) or pause_ms)
                    if cur_pause_ms > 0:
                        s_file = _get_silence_file(cur_pause_ms)
                        if s_file:
                            safe_silence = str(s_file.resolve()).replace("\\", "/").replace("'", "'\\''")
                            f.write(f"file '{safe_silence}'\n")

        # 2. Studio Mastering Filter Chain with dynamic loudnorm & resample parameters:
        has_explosive = any(
            (s.get("intensity_level") if isinstance(s, dict) else getattr(s, "intensity_level", None)) in ("explosive", "high")
            for s in seg_meta_by_idx.values()
        ) if seg_meta_by_idx else False

        has_whisper = any(
            (s.get("intensity_level") if isinstance(s, dict) else getattr(s, "intensity_level", None)) in ("low", "whisper")
            for s in seg_meta_by_idx.values()
        ) if seg_meta_by_idx else False

        effective_lra = min(loudness_range, 6.0) if (has_whisper and not has_explosive) else loudness_range

        limiter_limit = 0.82 if has_explosive else 0.89
        limiter_attack = 2 if has_explosive else 5
        target_tp = min(true_peak_db, -2.0) if has_explosive else true_peak_db

        filter_chain = (
            f"aresample=osr={target_sample_rate},highpass=f=60,afftdn=nr=8:nf=-35,deesser=i=0.35:m=0.5:f=0.14,"
            f"lowpass=f=14000"
        )
        if loudnorm:
            filter_chain += (
                f",loudnorm=I={target_lufs}:TP={target_tp:.1f}:LRA={effective_lra:.1f},"
                f"alimiter=limit={limiter_limit}:attack={limiter_attack}:release=50"
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

        size_mb = round(output_chapter_file.stat().st_size / (1024 * 1024), 2)
        print(f"[+] Mastered chapter ready ({size_mb} MB) -> {output_chapter_file}")
        return output_chapter_file
    finally:
        if concat_list.exists():
            try:
                concat_list.unlink()
            except OSError:
                pass
        for s_file in silence_cache.values():
            if s_file and s_file.exists():
                try:
                    s_file.unlink()
                except OSError:
                    pass
        for p_file in spatial_cache.values():
            if p_file and p_file.exists():
                try:
                    p_file.unlink()
                except OSError:
                    pass
