#!/usr/bin/env python3
"""
Audiobook Factory - Soundscape & Audio Probe Facade (Vocals-Only Engine).
Provides lightweight backward compatibility for duration and FFmpeg probes.
Procedural BGM, SFX, and multitrack mixing are decoupled in the Vocals-Only engine.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional

from audiobook_factory.audio_utils import (
    get_ffmpeg,
    get_ffprobe,
    get_audio_duration,
    get_audio_duration_ms,
    measure_audio_metrics,
)

STEMS_DIR = Path("audiobooks/soundscapes/stems")
SFX_DIR = Path("audiobooks/soundscapes/sfx")
PROCEDURAL_SFX: Dict[str, str] = {}


def get_sound_bank():
    return None


def detect_chapter_mood(text: str) -> str:
    return "default"


def resolve_sfx_cue(*args, **kwargs):
    return None


def resolve_ambient_score(*args, **kwargs):
    return None


def generate_procedural_ambient_bed(*args, **kwargs):
    return None


def resolve_environment_ambience(*args, **kwargs):
    return None


def fetch_musicgen(*args, **kwargs):
    return None


def apply_dynamic_sidechain_ducking(*args, **kwargs):
    return None


def generate_chapter_soundscape_plan(*args, **kwargs):
    return {}


def generate_project_soundscapes(*args, **kwargs):
    return Path("audiobooks/soundscapes")


def render_chapter_soundscape(*args, **kwargs):
    return None


def normalize_to_3level_soundscape(plan: Dict[str, Any], chapter_num: int = 1) -> Dict[str, Any]:
    out = dict(plan)
    scenes = out.get("scenes", [])
    if not scenes and "level3_scenes" in out:
        scenes = out.get("level3_scenes", [])
    out["scenes"] = scenes
    out["level3_scenes"] = scenes

    if "level1_leitmotifs" not in out:
        out["level1_leitmotifs"] = []

    if "level2_chapter_bed" not in out:
        out["level2_chapter_bed"] = {
            "setting": "open_road",
            "stem": "open_road",
            "base_volume": 0.16,
            "description": "Continuous setting undercurrent",
        }

    valid_cue_sections = {"INTRO_BED", "RISING_TENSION", "CLIMAX_DROP", "AFTERMATH_FADE", "AUTO"}
    valid_moods = {"tense", "mysterious", "peaceful", "emotional", "epic"}

    for sc in scenes:
        emo = sc.setdefault("emotional_arc", {})
        if "cue_section" in emo:
            c_sec = str(emo["cue_section"]).upper().strip()
            emo["cue_section"] = c_sec if c_sec in valid_cue_sections else "auto"
        mood = str(emo.get("music_mood", "tense")).lower().strip()
        emo["music_mood"] = mood if mood in valid_moods else "tense"

    return out


def render_hierarchical_soundscape(*args, **kwargs):
    return None


def render_multitrack_chapter_audio(*args, **kwargs):
    return None


def attenuate_foley_whisper_collisions(
    foley_cues: List[Any],
    segments: List[Any],
    attenuation_db: float = -6.0,
    shift_offset_ms: int = 150,
) -> List[Any]:
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
            "[whispers]" in text
            or "[whisper]" in text
            or "whisper" in emotion
            or "whispering" in emotion
            or "whispering_fear" in delivery
            or intensity == "low"
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


def resolve_timeline_start_offsets(*args, **kwargs):
    return []


__all__ = [
    "get_ffmpeg",
    "get_ffprobe",
    "get_audio_duration",
    "get_audio_duration_ms",
    "measure_audio_metrics",
    "resolve_timeline_start_offsets",
    "detect_chapter_mood",
    "STEMS_DIR",
    "SFX_DIR",
    "PROCEDURAL_SFX",
    "get_sound_bank",
    "resolve_sfx_cue",
    "resolve_ambient_score",
    "generate_procedural_ambient_bed",
    "resolve_environment_ambience",
    "fetch_musicgen",
    "apply_dynamic_sidechain_ducking",
    "generate_chapter_soundscape_plan",
    "generate_project_soundscapes",
    "render_chapter_soundscape",
    "normalize_to_3level_soundscape",
    "render_hierarchical_soundscape",
    "render_multitrack_chapter_audio",
    "attenuate_foley_whisper_collisions",
]
