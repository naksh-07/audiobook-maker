#!/usr/bin/env python3
"""
Audiobook Factory - TTS Constants, Configuration & Path Resolvers.
Provides default environment configuration, numeral normalizations, and FFmpeg/API key resolution.
"""

from __future__ import annotations
import os
import shutil
from pathlib import Path
from audiobook_factory.key_manager import get_persistent_key_pool

# Default Configuration from Environment
DEFAULT_BACKEND = os.environ.get("TTS_PRIMARY_BACKEND", "gemini_tts")
DEFAULT_VOICE = os.environ.get("GEMINI_DEFAULT_VOICE", "Aoede")
DEFAULT_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
DEFAULT_BATCHING_ENABLED = os.environ.get("TTS_BATCHING_ENABLED", "false").lower() in ("true", "1", "yes")
DEFAULT_FORCED_ALIGNMENT_ENABLED = os.environ.get("TTS_FORCED_ALIGNMENT_ENABLED", "true").lower() in ("true", "1", "yes")
DEFAULT_DECLICK_FADE_MS = float(os.environ.get("TTS_DECLICK_FADE_MS", "5.0"))
ENABLE_EMERGENCY_FALLBACK = os.environ.get("ENABLE_EMERGENCY_FALLBACK", "false").lower() in ("true", "1", "yes")
# Enforce strictly 1 worker for authentic human studio cadence and complete anti-clustering protection
DEFAULT_WORKERS = 1
DEFAULT_RPM = float(os.environ.get("GEMINI_TTS_RPM", "15.0"))


def get_ffmpeg() -> str:
    """Resolve FFmpeg binary path safely across Windows and Linux."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin

    # Windows standard paths
    fallbacks = [
        Path("C:/ffmpeg/bin/ffmpeg.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Links/ffmpeg.exe",
        Path(os.environ.get("ProgramFiles", "")) / "ffmpeg/bin/ffmpeg.exe",
    ]
    for fb in fallbacks:
        if fb.exists():
            return str(fb)
    return "ffmpeg"


def get_ffprobe() -> str:
    """Resolve FFprobe binary path safely across Windows and Linux."""
    probe_bin = shutil.which("ffprobe")
    if probe_bin:
        return probe_bin

    # Windows standard paths
    fallbacks = [
        Path("C:/ffmpeg/bin/ffprobe.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Links/ffprobe.exe",
        Path(os.environ.get("ProgramFiles", "")) / "ffmpeg/bin/ffprobe.exe",
    ]
    for fb in fallbacks:
        if fb.exists():
            return str(fb)
    return "ffprobe"


def get_gemini_api_key() -> str:
    """Acquires the next eligible active API key from the persistent SQLite quota pool."""
    pool = get_persistent_key_pool()
    return pool.get_key(service="tts")


# Singleton instance for backwards compatibility
global_key_pool = get_persistent_key_pool()


NUMERAL_NORMALIZATION = {
    "१": "भाग एक", "२": "भाग दो", "३": "भाग तीन", "४": "भाग चार", "५": "भाग पाँच",
    "६": "भाग छह", "७": "भाग सात", "८": "भाग आठ", "९": "भाग नौ", "१०": "भाग दस",
    "1": "भाग एक", "2": "भाग दो", "3": "भाग तीन", "4": "भाग चार", "5": "भाग पाँच",
    "6": "भाग छह", "7": "भाग सात", "8": "भाग आठ", "9": "भाग नौ", "10": "भाग दस",
    "I": "भाग एक", "II": "भाग दो", "III": "भाग तीन", "IV": "भाग चार", "V": "भाग पाँच",
    "VI": "भाग छह", "VII": "भाग सात", "VIII": "भाग आठ", "IX": "भाग नौ", "X": "भाग दस",
    "XI": "भाग ग्यारह", "XII": "भाग बारह", "XIII": "भाग तेरह", "XIV": "भाग चौदह", "XV": "भाग पंद्रह",
    "XVI": "भाग सोलह", "XVII": "भाग सत्रह", "XVIII": "भाग अठारह", "XIX": "भाग उन्नीस", "XX": "भाग बीस",
}


class UnregisteredSpeakerError(KeyError):
    """Raised when a dialogue segment requests an unregistered character voice."""
    pass
