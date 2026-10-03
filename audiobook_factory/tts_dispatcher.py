#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.2: Concurrent TTS Dispatcher & Token-Bucket Continuity Engine.
Backward-compatible facade re-exporting symbols from audiobook_factory.tts.
"""

from __future__ import annotations

# Re-export key manager & cadence hooks for legacy callers and test patchers
from audiobook_factory.key_manager import (
    get_persistent_key_pool,
    classify_gemini_error,
    AllKeysExhaustedTodayError,
)
from audiobook_factory.cadence import (
    get_stealth_sdk_headers,
    get_human_cadence_controller,
    probe_key_health,
)

# Re-export all TTS package components
from audiobook_factory.tts import (
    DEFAULT_BACKEND,
    DEFAULT_VOICE,
    DEFAULT_MODEL,
    DEFAULT_BATCHING_ENABLED,
    DEFAULT_FORCED_ALIGNMENT_ENABLED,
    DEFAULT_DECLICK_FADE_MS,
    ENABLE_EMERGENCY_FALLBACK,
    DEFAULT_WORKERS,
    DEFAULT_RPM,
    NUMERAL_NORMALIZATION,
    get_ffmpeg,
    get_ffprobe,
    get_gemini_api_key,
    global_key_pool,
    UnregisteredSpeakerError,
    TokenBucketRateLimiter,
    _synthesize_local_winrt_fallback,
    _synthesize_local_batch_winrt,
    resolve_speech_metadata_style,
    synthesize_gemini_tts,
    synthesize_gemini_multispeaker_batch,
    compute_canonical_segment_filename,
    slice_and_declick_batch,
    TTSDispatcher,
    synthesize_segment_audio,
)

__all__ = [
    "DEFAULT_BACKEND",
    "DEFAULT_VOICE",
    "DEFAULT_MODEL",
    "DEFAULT_BATCHING_ENABLED",
    "DEFAULT_FORCED_ALIGNMENT_ENABLED",
    "DEFAULT_DECLICK_FADE_MS",
    "ENABLE_EMERGENCY_FALLBACK",
    "DEFAULT_WORKERS",
    "DEFAULT_RPM",
    "NUMERAL_NORMALIZATION",
    "get_ffmpeg",
    "get_ffprobe",
    "get_gemini_api_key",
    "global_key_pool",
    "get_persistent_key_pool",
    "get_human_cadence_controller",
    "get_stealth_sdk_headers",
    "probe_key_health",
    "classify_gemini_error",
    "AllKeysExhaustedTodayError",
    "UnregisteredSpeakerError",
    "TokenBucketRateLimiter",
    "_synthesize_local_winrt_fallback",
    "_synthesize_local_batch_winrt",
    "resolve_speech_metadata_style",
    "synthesize_gemini_tts",
    "synthesize_gemini_multispeaker_batch",
    "compute_canonical_segment_filename",
    "slice_and_declick_batch",
    "TTSDispatcher",
    "synthesize_segment_audio",
]
