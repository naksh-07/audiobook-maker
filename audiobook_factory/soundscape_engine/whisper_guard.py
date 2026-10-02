#!/usr/bin/env python3
"""
Audiobook Factory - Soundscape Engine: Whisper Guard.
Prevents Foley masking on intimate/whispered vocal segments by attenuating or shifting cues.
"""

from __future__ import annotations
from typing import List, Any


def attenuate_foley_whisper_collisions(
    foley_cues: List[Any],
    segments: List[Any],
    attenuation_db: float = -6.0,
    shift_offset_ms: int = 150,
) -> List[Any]:
    """
    Meso-Tier Verification Guard:
    Checks acoustic overlap between Foley cues and whisper/intimate speech segments
    (identified by '[whispers]' tag, emotion='whispering', delivery_style='whispering_fear',
    or intensity_level='low').
    Attenuates Foley gain by -6.0 dBFS (or shifts offset) to preserve whisper intelligibility
    and eliminate masking distortion.
    """
    if not foley_cues or not segments:
        return foley_cues

    whisper_indices = set()
    whisper_windows = []

    for seg in segments:
        seg_idx = getattr(seg, "index", None)
        if seg_idx is None:
            seg_idx = getattr(seg, "segment_index", None)
        if seg_idx is None and isinstance(seg, dict):
            seg_idx = seg.get("index", seg.get("segment_index"))

        text = ""
        emotion = ""
        intensity = ""
        delivery = ""

        if isinstance(seg, dict):
            text = str(seg.get("text", "")).lower()
            emotion = str(seg.get("emotion", "")).lower()
            intensity = str(seg.get("intensity_level", "")).lower()
            acting = seg.get("acting", {})
            if isinstance(acting, dict):
                delivery = str(acting.get("delivery_style", "")).lower()
        else:
            text = str(getattr(seg, "text", "") or "").lower()
            emotion = str(getattr(seg, "emotion", "") or "").lower()
            intensity = str(getattr(seg, "intensity_level", "") or "").lower()
            acting = getattr(seg, "acting", None)
            if isinstance(acting, dict):
                delivery = str(acting.get("delivery_style", "")).lower()
            elif hasattr(acting, "delivery_style"):
                delivery = str(getattr(acting, "delivery_style", "")).lower()

        is_whisper = (
            "[whispers]" in text or
            "[whisper]" in text or
            "whisper" in emotion or
            "whispering" in emotion or
            "whispering_fear" in delivery or
            intensity == "low"
        )

        if is_whisper:
            if seg_idx is not None:
                whisper_indices.add(seg_idx)
            start_ms = seg.get("start_ms") if isinstance(seg, dict) else getattr(seg, "start_ms", None)
            end_ms = seg.get("end_ms") if isinstance(seg, dict) else getattr(seg, "end_ms", None)
            if start_ms is not None and end_ms is not None:
                whisper_windows.append((start_ms, end_ms))

    for cue in foley_cues:
        c_seg_idx = cue.get("segment_index") if isinstance(cue, dict) else getattr(cue, "segment_index", None)
        c_start_ms = cue.get("start_ms") if isinstance(cue, dict) else getattr(cue, "start_ms", None)
        c_dur_ms = (cue.get("duration_ms") if isinstance(cue, dict) else getattr(cue, "duration_ms", None)) or 500

        collision = False
        if c_seg_idx is not None and c_seg_idx in whisper_indices:
            collision = True
        elif c_start_ms is not None and whisper_windows:
            c_end_ms = c_start_ms + c_dur_ms
            for w_start, w_end in whisper_windows:
                if not (c_end_ms <= w_start or c_start_ms >= w_end):
                    collision = True
                    break

        if collision:
            if hasattr(cue, "gain_dbfs"):
                cue.gain_dbfs = round(cue.gain_dbfs + attenuation_db, 2)
            elif isinstance(cue, dict) and "gain_dbfs" in cue:
                cue["gain_dbfs"] = round(cue["gain_dbfs"] + attenuation_db, 2)

            if hasattr(cue, "pre_roll_ms"):
                cue.pre_roll_ms = max(0, getattr(cue, "pre_roll_ms", 100) + shift_offset_ms)
            elif isinstance(cue, dict) and "pre_roll_ms" in cue:
                cue["pre_roll_ms"] = max(0, cue.get("pre_roll_ms", 100) + shift_offset_ms)

    return foley_cues
