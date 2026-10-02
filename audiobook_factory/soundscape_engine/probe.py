#!/usr/bin/env python3
"""
Audiobook Factory - Soundscape Engine: Probe & Timeline Utilities.
Handles FFmpeg binary discovery, audio duration extraction, and timeline offset resolution.
"""

from __future__ import annotations
import os
import shutil
import subprocess
import re
from pathlib import Path
from typing import Dict, Any, Optional, List


def get_ffmpeg() -> str:
    ffmpeg_bin = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
    if not os.path.exists(ffmpeg_bin):
        raise FileNotFoundError("FFmpeg executable not found in PATH.")
    return ffmpeg_bin


def get_audio_duration(file_path: Path) -> float:
    """Extract audio duration in seconds using ffprobe or ffmpeg."""
    file_path = Path(file_path).resolve()
    ffprobe = shutil.which("ffprobe") or "/usr/bin/ffprobe"
    if os.path.exists(ffprobe):
        cmd = [
            ffprobe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path)
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(res.stdout.strip())
        except Exception:
            pass

    # Fallback using ffmpeg stderr inspection
    ffmpeg = get_ffmpeg()
    cmd = [ffmpeg, "-i", str(file_path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", res.stderr)
    if m:
        hours, mins, secs = m.groups()
        return int(hours) * 3600 + int(mins) * 60 + float(secs)
    return 60.0


def resolve_timeline_start_offsets(
    segment_durations: Dict[int, float],
    timeline_ledger: Optional[Any] = None,
    script_segments: Optional[List[Dict[str, Any]]] = None,
    default_pause_ms: int = 400,
) -> Dict[int, float]:
    """
    Computes sample-accurate segment start offsets in seconds.
    Priority 1: Post-editorial TimelineLedger (actual rendered audio timestamps).
    Priority 2: Sum of script-aware dynamic pause_after_ms + pre_roll_breath_ms.
    Priority 3: Default pause_ms accumulation.
    """
    seg_starts: Dict[int, float] = {}
    if timeline_ledger:
        segs = getattr(timeline_ledger, "segments", None)
        if segs is None and isinstance(timeline_ledger, dict):
            segs = timeline_ledger.get("segments") or timeline_ledger.get("timeline")
        if segs:
            for seg in segs:
                if isinstance(seg, dict):
                    s_idx = seg.get("segment_index") if seg.get("segment_index") is not None else seg.get("index")
                    start_ms = seg.get("start_ms", seg.get("t_start_ms", 0.0))
                else:
                    s_idx = getattr(seg, "segment_index", None) or getattr(seg, "index", None)
                    start_ms = getattr(seg, "start_ms", 0.0)
                if s_idx is not None:
                    seg_starts[int(s_idx)] = float(start_ms) / 1000.0
            if seg_starts:
                return seg_starts

    # Priority 2: Script-aware dynamic pauses + pre_roll_breath_ms
    curr_t = 0.0
    seg_meta_by_idx = {}
    if script_segments:
        for s in script_segments:
            if isinstance(s, dict) and "index" in s:
                seg_meta_by_idx[int(s["index"])] = s
            elif hasattr(s, "index"):
                seg_meta_by_idx[int(getattr(s, "index"))] = s

    for s_idx in sorted(segment_durations.keys()):
        seg_info = seg_meta_by_idx.get(s_idx, {})
        if isinstance(seg_info, dict):
            pre_breath = float(seg_info.get("pre_roll_breath_ms", 0) or 0) / 1000.0
            pause_ms = float(seg_info.get("pause_after_ms", default_pause_ms) or default_pause_ms) / 1000.0
        else:
            pre_breath = float(getattr(seg_info, "pre_roll_breath_ms", 0) or 0) / 1000.0
            pause_ms = float(getattr(seg_info, "pause_after_ms", default_pause_ms) or default_pause_ms) / 1000.0

        seg_starts[s_idx] = curr_t + pre_breath
        curr_t = seg_starts[s_idx] + segment_durations[s_idx] + pause_ms

    return seg_starts
