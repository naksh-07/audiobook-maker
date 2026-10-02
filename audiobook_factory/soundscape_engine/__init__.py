#!/usr/bin/env python3
"""
Audiobook Factory - Soundscape Engine Package.
Modular decomposition of Pillar 3.5: Soundscape, Ambience & Background Music Engine.
"""

from __future__ import annotations

from audiobook_factory.soundscape_engine.probe import (
    get_ffmpeg,
    get_audio_duration,
    resolve_timeline_start_offsets,
)
from audiobook_factory.soundscape_engine.mood_detector import (
    detect_chapter_mood,
)
from audiobook_factory.soundscape_engine.sound_resolver import (
    STEMS_DIR,
    SFX_DIR,
    PROCEDURAL_SFX,
    get_sound_bank,
    resolve_sfx_cue,
    resolve_ambient_score,
    generate_procedural_ambient_bed,
    resolve_environment_ambience,
    fetch_musicgen,
)
from audiobook_factory.soundscape_engine.ducking import (
    apply_dynamic_sidechain_ducking,
)
from audiobook_factory.soundscape_engine.planner import (
    generate_chapter_soundscape_plan,
    generate_project_soundscapes,
)
from audiobook_factory.soundscape_engine.mixer import (
    render_chapter_soundscape,
    normalize_to_3level_soundscape,
    render_hierarchical_soundscape,
    render_multitrack_chapter_audio,
)
from audiobook_factory.soundscape_engine.whisper_guard import (
    attenuate_foley_whisper_collisions,
)

__all__ = [
    "get_ffmpeg",
    "get_audio_duration",
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
