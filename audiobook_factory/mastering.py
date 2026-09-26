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
from typing import List, Dict, Any, Optional, Tuple
import numpy as np


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
    overlap_cache: Dict[str, Path] = {}

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

    def _read_wav_pcm(path: Path) -> Tuple[np.ndarray, int, int]:
        with wave.open(str(path), "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            sw = wf.getsampwidth()
            frames = wf.getnframes()
            raw = wf.readframes(frames)
        if sw == 2:
            data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        elif sw == 3:
            raw_arr = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
            padded = np.pad(raw_arr, ((0, 0), (1, 0)), mode="constant", constant_values=0)
            data = (padded.view("<i4").flatten() >> 8).astype(np.float32) / 256.0
        elif sw == 4:
            data = np.frombuffer(raw, dtype=np.float32) * 32768.0
        else:
            data = np.zeros(frames * ch, dtype=np.float32)
        if ch > 1:
            data = data.reshape(-1, ch)
        return data, sr, ch

    def _write_wav_pcm(target_path: Path, data: np.ndarray, sr: int, ch: int) -> Path:
        int16_data = np.clip(np.round(data), -32768.0, 32767.0).astype(np.int16)
        with wave.open(str(target_path), "wb") as wf:
            wf.setnchannels(ch)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(int16_data.tobytes())
        overlap_cache[str(target_path)] = target_path
        return target_path

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
        # Check if any segment has overlap rendering requested (DE-05)
        has_overlap = any(
            getattr(edit_plan_by_idx.get(idx, None) or (edit_plans[i] if edit_plans and i < len(edit_plans) else None), "overlap_ms", 0) > 0
            for i, idx in enumerate(
                [
                    next((int(p[1:]) for p in seg.stem.split("_") if p.startswith("s") and p[1:].isdigit()), i + 1)
                    for i, seg in enumerate(audio_segments)
                ]
            )
        ) if edit_plans else False

        with open(concat_list, "w", encoding="utf-8") as f:
            if not has_overlap:
                # Standard sequential playback path
                for i, seg in enumerate(audio_segments):
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
            else:
                # Overlap-aware timeline realization (DE-05)
                # 1. Resolve spatial panning for all segments first
                resolved_segs: List[Path] = []
                seg_indices: List[int] = []
                for i, seg in enumerate(audio_segments):
                    s_idx = i + 1
                    for part in seg.stem.split("_"):
                        if part.startswith("s") and part[1:].isdigit():
                            s_idx = int(part[1:])
                            break
                    seg_indices.append(s_idx)
                    seg_info = seg_meta_by_idx.get(s_idx, {})
                    if spatial_staging:
                        speaker = str(seg_info.get("speaker", "Narrator"))
                        seg_spatial = seg_info.get("spatial", {}) if isinstance(seg_info, dict) else getattr(seg_info, "spatial", None)
                        if isinstance(seg_spatial, dict):
                            pan = float(seg_spatial.get("pan", 0.0) or 0.0)
                        elif hasattr(seg_spatial, "pan"):
                            pan = float(getattr(seg_spatial, "pan", 0.0) or 0.0)
                        else:
                            pan = float(seg_info.get("spatial_pan", 0.0) or 0.0)
                        if speaker.lower() in ("narrator", "narration"):
                            pan = 0.0
                        panned_seg = _get_panned_segment(seg, pan, s_idx)
                        resolved_segs.append(panned_seg)
                    else:
                        resolved_segs.append(seg)

                # 2. Iterate and render cross-talk overlap transitions
                current_data: Optional[np.ndarray] = None
                for i in range(len(audio_segments)):
                    s_idx = seg_indices[i]
                    seg_info = seg_meta_by_idx.get(s_idx, {})
                    plan_for_seg = edit_plan_by_idx.get(s_idx)
                    if plan_for_seg is None and edit_plans and i < len(edit_plans):
                        plan_for_seg = edit_plans[i]

                    # Pre-roll breath / pause if specified (only if starting fresh take)
                    if current_data is None:
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

                        current_data, cur_sr, cur_ch = _read_wav_pcm(resolved_segs[i])
                    else:
                        cur_sr = sample_rate
                        cur_ch = channels

                    ov_ms = int(getattr(plan_for_seg, "overlap_ms", 0) or 0)
                    if ov_ms > 0 and i < len(audio_segments) - 1:
                        next_raw_data, next_sr, next_ch = _read_wav_pcm(resolved_segs[i + 1])
                        dur_curr_ms = int(len(current_data) / cur_sr * 1000.0)
                        dur_next_ms = int(len(next_raw_data) / next_sr * 1000.0)
                        effective_ov_ms = min(ov_ms, int(dur_curr_ms * 0.45), int(dur_next_ms * 0.45), 400)

                        if effective_ov_ms >= 30:
                            n_ov = int(effective_ov_ms / 1000.0 * cur_sr)
                            body_i = current_data[:-n_ov]
                            tail_i = current_data[-n_ov:]
                            head_next = next_raw_data[:n_ov]
                            remainder_next = next_raw_data[n_ov:]

                            # Equal-power mixing for overlap window
                            mix_data = np.clip(tail_i + head_next, -32768.0, 32767.0)
                            if len(mix_data) > 2:
                                mix_data[0] = 0
                                mix_data[-1] = 0

                            if len(body_i) > 20:
                                b_path = output_chapter_file.parent / f".overlap_body_s{s_idx}.wav"
                                _write_wav_pcm(b_path, body_i, cur_sr, cur_ch)
                                safe_b = str(b_path.resolve()).replace("\\", "/").replace("'", "'\\''")
                                f.write(f"file '{safe_b}'\n")

                            t_path = output_chapter_file.parent / f".overlap_trans_s{s_idx}_s{seg_indices[i+1]}.wav"
                            _write_wav_pcm(t_path, mix_data, cur_sr, cur_ch)
                            safe_t = str(t_path.resolve()).replace("\\", "/").replace("'", "'\\''")
                            f.write(f"file '{safe_t}'\n")

                            current_data = remainder_next
                            continue

                    # If no overlap, flush current segment audio
                    if current_data is not None and len(current_data) > 0:
                        orig_len = len(_read_wav_pcm(resolved_segs[i])[0])
                        if len(current_data) != orig_len:
                            rem_path = output_chapter_file.parent / f".overlap_rem_s{s_idx}.wav"
                            _write_wav_pcm(rem_path, current_data, cur_sr, cur_ch)
                            safe_seg = str(rem_path.resolve()).replace("\\", "/").replace("'", "'\\''")
                        else:
                            safe_seg = str(resolved_segs[i].resolve()).replace("\\", "/").replace("'", "'\\''")
                        f.write(f"file '{safe_seg}'\n")
                        current_data = None

                    # Post-segment dramatic pause (only when no overlap into next segment)
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
        for o_file in overlap_cache.values():
            if o_file and o_file.exists():
                try:
                    o_file.unlink()
                except OSError:
                    pass
