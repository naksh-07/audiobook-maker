#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Module: engine_adapter.py
Bridges abstract MixAutomation into the concrete FFmpeg rendering operations
of CinemaAudioEngine without modifying the underlying DSP summing architecture.
"""

from __future__ import annotations
import math
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.cinematic_mix.automation import (
    MixAutomation,
    AutomationEvent,
    SAFETY_LIMIT_MIN_GAIN_DB,
    SAFETY_LIMIT_MAX_GAIN_DB,
    SAFETY_LIMIT_MAX_NOTCH_DB,
)


def build_stem_filter_chain(
    target: str,
    automation: Optional[MixAutomation] = None,
) -> str:
    """
    Builds a deterministic FFmpeg audio filter string for a target stem ('MX', 'FX', 'AMB')
    from the MixAutomation timeline.

    Supports:
    - Dynamic volume envelopes via volume='if(...)':eval=frame
    - Dynamic vocal corridor notch EQ via equalizer=f=...:g=...
    """
    if not automation or not automation.events:
        return ""

    filters: List[str] = []
    target_norm = target.strip().upper()

    # 1. Evaluate Dynamic Masking / EQ depth for MX stem (Dynamic Vocal Corridor Pocketing)
    if target_norm == "MX":
        eq_events = automation.get_events_for_target("MX", "eq_depth")
        # Filter to meaningful cuts (< -0.2 dB)
        active_eq_events = [e for e in eq_events if e.value < -0.2]
        if active_eq_events:
            deepest_event = min(active_eq_events, key=lambda e: e.value)
            depth_db = max(SAFETY_LIMIT_MAX_NOTCH_DB, min(0.0, deepest_event.value))
            freq_hz = deepest_event.metadata.get("frequency_hz", 2400)
            q_val = deepest_event.metadata.get("q", 1.5)

            # Check if events span distinct time intervals or entire scene
            # If windows are provided, apply speech-gated dynamic equalizer via 'enable'
            enable_terms = []
            for ev in active_eq_events[:12]:
                if ev.start is not None and ev.end is not None and ev.end > ev.start:
                    enable_terms.append(f"between(t,{ev.start:.2f},{ev.end:.2f})")

            if enable_terms:
                enable_expr = "+".join(enable_terms)
                filters.append(
                    f"equalizer=f={int(freq_hz)}:width_type=q:w={float(q_val):.2f}:g={depth_db:.2f}:enable='gt({enable_expr},0)'"
                )
            else:
                filters.append(
                    f"equalizer=f={int(freq_hz)}:width_type=q:w={float(q_val):.2f}:g={depth_db:.2f}"
                )

    # 2. Evaluate Gain / Attenuation events
    gain_events = automation.get_events_for_target(target_norm, "gain")
    # Filter to meaningful attenuation (< -0.2 dB)
    active_gain_events = [e for e in gain_events if e.value < -0.2]

    if active_gain_events:
        # Build nested if-between expressions for frame-level evaluation
        # Limit to max 12 distinct windows per pass to keep FFmpeg CLI short & Win32 safe
        windows = active_gain_events[:12]
        expr_terms = []
        for w in windows:
            clamped_db = max(SAFETY_LIMIT_MIN_GAIN_DB, min(SAFETY_LIMIT_MAX_GAIN_DB, w.value))
            lin_gain = round(10.0 ** (clamped_db / 20.0), 4)
            lin_gain = max(0.015, min(2.0, lin_gain))
            expr_terms.append(f"between(t,{w.start:.2f},{w.end:.2f})*{lin_gain:.4f}")

        # In FFmpeg eval=frame: if sum of conditions > 0 use min attenuation, else 1.0
        if len(windows) == 1:
            w = windows[0]
            lin_g = max(0.015, min(2.0, 10.0 ** (max(SAFETY_LIMIT_MIN_GAIN_DB, w.value) / 20.0)))
            filters.append(f"volume='if(between(t,{w.start:.2f},{w.end:.2f}),{lin_g:.4f},1.0)':eval=frame")
        else:
            # Nested ternary expression
            # e.g. if(between(t, 2, 4), 0.3, if(between(t, 6, 8), 0.5, 1.0))
            nested_expr = "1.0"
            for w in reversed(windows):
                lin_g = max(0.015, min(2.0, 10.0 ** (max(SAFETY_LIMIT_MIN_GAIN_DB, w.value) / 20.0)))
                nested_expr = f"if(between(t,{w.start:.2f},{w.end:.2f}),{lin_g:.4f},{nested_expr})"
            filters.append(f"volume='{nested_expr}':eval=frame")

    # 3. Evaluate Lowpass Cutoff (Acoustic Perspective & Occlusion)
    lp_events = automation.get_events_for_target(target_norm, "lowpass_cutoff")
    if lp_events:
        deepest_lp = min(lp_events, key=lambda e: e.value)
        cutoff_hz = int(max(200.0, min(18000.0, deepest_lp.value)))
        if cutoff_hz < 16000:
            filters.append(f"lowpass=f={cutoff_hz}")

    # 4. Evaluate Stereo Width
    width_events = automation.get_events_for_target(target_norm, "stereo_width")
    if width_events:
        top_w = width_events[0].value
        if abs(top_w - 1.0) > 0.08:
            filters.append(f"stereotools=mlev=1.00:slev={top_w:.2f}")

    return ",".join(filters)


def apply_automation_to_stem(
    input_stem_wav: Path,
    target: str,
    output_stem_wav: Path,
    automation: Optional[MixAutomation] = None,
    ffmpeg: Optional[str] = None,
) -> Path:
    """
    Applies MixAutomation filter chain to an uncompressed stem WAV file.
    If no automation applies, cleanly copies or hardlinks the stem.
    """
    input_p = Path(input_stem_wav).resolve()
    output_p = Path(output_stem_wav).resolve()
    output_p.parent.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg or shutil.which("ffmpeg") or "ffmpeg"

    filter_str = build_stem_filter_chain(target, automation)
    if not filter_str or not input_p.exists():
        if input_p != output_p and input_p.exists():
            shutil.copyfile(input_p, output_p)
        return output_p

    cmd = [
        ff, "-y",
        "-i", str(input_p),
        "-af", filter_str,
        "-c:a", "pcm_s16le",
        str(output_p),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0 or not output_p.exists():
        # Fallback to direct copy on filter error
        shutil.copyfile(input_p, output_p)
    return output_p
