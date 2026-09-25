#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.2: Concurrent TTS Dispatcher & Token-Bucket Continuity Engine.
Routes speech segments to Google Gemini 3.1 Flash TTS with thread-safe rate-limiting,
transaction-safe SQLite segment ledgering, and multi-worker parallelism.
"""

import os
import sys
import io
import time
import json
import re
import random
import wave
import shutil
import base64
import hashlib
import threading
import urllib.request
import urllib.error
import subprocess
import concurrent.futures
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.logger import logger
from audiobook_factory.restoration import extract_clean_pcm_from_gemini_container
from audiobook_factory.state import ProjectStateLedger
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
from audiobook_factory.contracts import (
    BatchPlanItem,
    BatchDispatchManifest,
    ScreenplaySegment,
)
from audiobook_factory.batch_planner import BatchDispatchPlanner
from audiobook_factory.forced_aligner import WorkstationForcedAligner


# Default Configuration from Environment
DEFAULT_BACKEND = os.environ.get("TTS_PRIMARY_BACKEND", "gemini_tts")
DEFAULT_VOICE = os.environ.get("GEMINI_DEFAULT_VOICE", "Aoede")
DEFAULT_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
DEFAULT_BATCHING_ENABLED = os.environ.get("TTS_BATCHING_ENABLED", "true").lower() in ("true", "1", "yes")
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


def get_gemini_api_key() -> str:
    """Acquires the next eligible active API key from the persistent SQLite quota pool."""
    pool = get_persistent_key_pool()
    return pool.get_key(service="tts")


# Singleton instance for backwards compatibility
global_key_pool = get_persistent_key_pool()


class TokenBucketRateLimiter:
    """
    Thread-safe Token Bucket Rate Limiter with Anti-Bot Organic Jitter.
    Enforces precise request rates (e.g. 15 RPM = 1 dispatch every 4.0s) across concurrent workers.
    Injects random uniform jitter (0.35s - 0.85s) to emulate natural, human-paced API traffic
    and prevent automated bot-detection heuristics.
    """

    def __init__(self, rate_rpm: float = DEFAULT_RPM, capacity: float = 2.0):
        self.rate_per_sec = rate_rpm / 60.0
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self.lock = threading.Lock()
        self.pause_event = threading.Event()
        self.pause_event.set()

    def acquire(self):
        # Wait if globally paused due to 429 quota backoff
        self.pause_event.wait()

        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_per_sec)

            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) / self.rate_per_sec
                self.tokens = 0.0
                self.last_update = now + wait_time
            else:
                self.tokens -= 1.0
                self.last_update = now
                wait_time = 0.0

        # Organic anti-bot jitter: random delay between 350ms and 850ms
        jitter = random.uniform(0.35, 0.85)
        total_wait = wait_time + jitter
        if total_wait > 0:
            time.sleep(total_wait)

    def trigger_global_pause(self, pause_seconds: float):
        """Pauses all worker threads simultaneously during an HTTP 429 backoff."""
        with self.lock:
            if not self.pause_event.is_set():
                return
            self.pause_event.clear()

        logger.warning(f"  [GLOBAL PAUSE] 429 backoff: Pausing all TTS workers for {pause_seconds:.1f}s...")

        def _resume():
            time.sleep(pause_seconds)
            with self.lock:
                self.last_update = time.monotonic()
                self.tokens = 0.0
                self.pause_event.set()
            logger.info(f"  [GLOBAL RESUME] TTS workers resumed after quota backoff.")

        threading.Thread(target=_resume, daemon=True).start()


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


def resolve_speech_metadata_style(
    acting: Any,
    emotion: str = "neutral",
    intensity: str = "medium",
    memory_vocal_constraint: Optional[str] = None,
) -> str:
    """
    Transforms Pydantic screenplay acting directives, emotion, and conservative Memory 2.0
    physical vocal constraints into a concise natural language style descriptor for Gemini speechMetadata.style.
    """
    descriptors = []

    style_val = getattr(acting, "delivery_style", None) if acting else None
    if not style_val and isinstance(acting, dict):
        style_val = acting.get("delivery_style")

    if style_val and str(style_val).lower() not in ("neutral", "standard"):
        descriptors.append(str(style_val).replace("_", " "))

    if emotion and emotion.lower() not in ("neutral", "standard"):
        descriptors.append(emotion.lower().replace("_", " "))

    if intensity == "explosive":
        descriptors.append("extreme intensity")
    elif intensity == "low":
        descriptors.append("subdued")

    # Conservative physical vocal constraint from Memory 2.0 (only applied when no conflicting explicit style overrides it)
    eff_constraint = memory_vocal_constraint
    if not eff_constraint and isinstance(acting, dict):
        eff_constraint = acting.get("memory_vocal_constraint")
    if eff_constraint and str(eff_constraint).lower() not in ("none", "normal", "neutral"):
        constraint_str = str(eff_constraint).replace("_", " ")
        if constraint_str not in descriptors:
            descriptors.append(constraint_str)

    if not descriptors:
        return "neutral"

    return ", ".join(descriptors)


def synthesize_gemini_tts(
    text: str,
    output_file: Path,
    voice: str = DEFAULT_VOICE,
    model: str = DEFAULT_MODEL,
    emotion: str = "neutral",
    acting: Any = None,
    intensity: str = "medium",
    memory_vocal_constraint: Optional[str] = None,
    performance_direction: Optional[Any] = None,
    variant_type: str = "standard",
    max_retries: int = 4,
    rate_limiter: Optional[TokenBucketRateLimiter] = None,
    voice_dna: Optional[Any] = None,
    scene_vector: Optional[Any] = None,
) -> Tuple[Path, float]:
    clean_text = text.strip()
    # Strip surrounding punctuation/quotes for numeral lookup: e.g. "८.", "'IV'", "(1)", "3,"
    stripped_token = re.sub(r"^[^\w\d\u0900-\u097F]+|[^\w\d\u0900-\u097F]+$", "", clean_text)
    if stripped_token in NUMERAL_NORMALIZATION:
        text = NUMERAL_NORMALIZATION[stripped_token]
    elif clean_text in NUMERAL_NORMALIZATION:
        text = NUMERAL_NORMALIZATION[clean_text]

    part_payload: Dict[str, Any] = {"text": text}
    if performance_direction:
        from audiobook_factory.performance.tts_adapter import GeminiTTSPerformanceAdapter
        adapter = GeminiTTSPerformanceAdapter()
        adapted = adapter.adapt_direction_to_payload(text, performance_direction, variant_type=variant_type)
        part_payload = adapted["part_payload"]
    else:
        style_desc = resolve_speech_metadata_style(acting, emotion, intensity, memory_vocal_constraint=memory_vocal_constraint)
        if style_desc and style_desc.lower() not in ("neutral", "standard"):
            part_payload["speechMetadata"] = {"style": style_desc}

    payload = {
        "contents": [{"parts": [part_payload]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": voice
                    }
                }
            }
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }

    # Note: gemini-3.1-flash-tts-preview does not support systemInstruction/Developer instruction (HTTP 400).
    # Emotion styling is governed by character voice mapping and punctuation prosody.

    # Subtle temperature micro-entropy (0.685 - 0.715) to avoid static robotic payload fingerprints
    gen_config = payload["generationConfig"]
    gen_config["temperature"] = round(random.uniform(0.685, 0.715), 3)

    data = json.dumps(payload).encode("utf-8")
    cadence = get_human_cadence_controller()
    pool = get_persistent_key_pool()

    # Outer Loop: Key Rotation (Rotates across all active keys in the pool)
    MAX_KEY_ROTATIONS = 15  # Circuit breaker: absolute upper bound before hard abort
    rotation_count = 0

    while True:
        rotation_count += 1
        if rotation_count > MAX_KEY_ROTATIONS:
            raise RuntimeError(
                f"TTS synthesis failed after {MAX_KEY_ROTATIONS} key rotations. "
                f"All keys cycling through transient errors. Aborting to prevent infinite loop."
            )

        api_key = pool.get_key(service="tts")  # Raises AllKeysExhaustedTodayError when all keys reach 10 RPD
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        key_exhausted_or_invalid = False

        # Inner Loop: Network retries on the currently selected key (max 3 attempts)
        for network_attempt in range(3):
            if rate_limiter:
                rate_limiter.acquire()

            req = urllib.request.Request(
                url,
                data=data,
                headers=get_stealth_sdk_headers(api_key),
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=90.0) as resp:
                    resp_json = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_json.get("candidates", [])
                    if not candidates:
                        fb = resp_json.get("promptFeedback", {})
                        raise ValueError(f"Gemini TTS blocked generation (promptFeedback: {fb})")
                    candidate = candidates[0]
                    finish_reason = candidate.get("finishReason")
                    if finish_reason in ("SAFETY", "RECITATION", "BLOCKLIST"):
                        raise ValueError(f"Gemini TTS generation blocked by finishReason: {finish_reason}")

                    inline_data = {}
                    parts = candidate.get("content", {}).get("parts", [])
                    for p in parts:
                        if "inlineData" in p:
                            inline_data = p["inlineData"]
                            break
                    b64_audio = inline_data.get("data", "")
                    if not b64_audio:
                        raise ValueError(f"No audio data found in Gemini response parts: {[p.get('text', '')[:40] for p in parts]}")
                    raw_bytes = base64.b64decode(b64_audio)
                    raw_pcm, sample_rate, frames = extract_clean_pcm_from_gemini_container(raw_bytes)

                    # Convert 24kHz raw PCM to temporary WAV before SNR inspection
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    tmp_file = output_file.with_suffix(".tmp.wav")
                    with wave.open(str(tmp_file), "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(sample_rate)
                        wf.writeframes(raw_pcm)

                    # Compute duration & raw PCM metrics
                    dur_sec = frames / float(sample_rate)
                    word_count = max(len(text.split()), 1)
                    ratio = dur_sec / word_count

                    # Audio Quality & SNR Gatekeeper (Mathematical PCM Probe)
                    import struct
                    import math
                    sample_count = len(raw_pcm) // 2
                    if sample_count > 0:
                        samples = struct.unpack(f"<{sample_count}h", raw_pcm)
                        peak_amp = max(abs(s) for s in samples)
                        sum_sq = sum(s * s for s in samples)
                        rms = math.sqrt(sum_sq / sample_count)
                        dc_offset = abs(sum(samples) / sample_count)
                    else:
                        peak_amp = 0
                        rms = 0.0
                        dc_offset = 0.0

                    # True flat-top clipping requires >= 6 consecutive samples pinned at rail
                    consec = 0
                    max_consec = 0
                    for s in samples:
                        if abs(s) >= 32760:
                            consec += 1
                            if consec > max_consec:
                                max_consec = consec
                        else:
                            consec = 0
                    is_clipped = (max_consec >= 6)
                    faint_limit = 8.0 if ("[whispers]" in text.lower() or "whisper" in emotion.lower() or "tender" in emotion.lower()) else 20.0
                    is_silent_faint = (peak_amp > 0 and word_count >= 3 and rms < faint_limit)
                    is_dc_corrupted = (peak_amp > 0 and dur_sec >= 2.0 and dc_offset > 1500.0)
                    is_stutter = (word_count > 3 and ratio > 3.2 and dur_sec >= 15.0)
                    is_empty = (dur_sec < 0.20 and word_count >= 3)

                    # Dead air / internal silence gap detector (prevents model pausing for 10s+ in long chunks)
                    has_long_silence = False
                    if dur_sec >= 6.0 and sample_count > 0:
                        window = 24000
                        silent_run = 0
                        max_silent_run = 0
                        for w_idx in range(0, sample_count, window):
                            sub = samples[w_idx:w_idx + window]
                            sub_rms = math.sqrt(sum(s * s for s in sub) / len(sub))
                            if sub_rms < 15.0:
                                silent_run += 1
                                if silent_run > max_silent_run:
                                    max_silent_run = silent_run
                            else:
                                silent_run = 0
                        if max_silent_run >= 4:
                            has_long_silence = True

                    has_defect = (is_clipped or is_silent_faint or is_dc_corrupted or is_stutter or is_empty or has_long_silence)
                    if has_defect:
                        tmp_file.unlink(missing_ok=True)
                        reasons = []
                        if is_clipped: reasons.append(f"Clipping Distortion (Consec Rail {max_consec} >= 6)")
                        if is_silent_faint: reasons.append(f"Faint Audio (RMS {rms:.1f} < {faint_limit})")
                        if is_dc_corrupted: reasons.append(f"DC Offset Anomaly ({dc_offset:.1f} > 1500)")
                        if is_stutter: reasons.append(f"Stutter Loop (Ratio {ratio:.2f}s/w)")
                        if is_empty: reasons.append("Empty Audio Truncation")
                        if has_long_silence: reasons.append("Excessive Dead Air (>= 4s internal silence)")
                        reason_str = " | ".join(reasons)
                        if network_attempt < 2:
                            logger.warning(
                                f"  [SNR GATEKEEPER: {reason_str}] Generated {dur_sec:.1f}s for {word_count} words. "
                                f"Retrying segment (Attempt {network_attempt+1}/3)..."
                            )
                            time.sleep(2.0)
                            continue
                        else:
                            raise ValueError(
                                f"SNR Gatekeeper rejected segment audio after 3 failed attempts: {reason_str} "
                                f"(dur={dur_sec:.1f}s, words={word_count}, peak={peak_amp}, rms={rms:.1f})"
                            )

                    # Atomically promote verified audio to target destination
                    tmp_file.replace(output_file)

                    # Record success in persistent key pool
                    pool.record_success(api_key)
                    return output_file, dur_sec

            except urllib.error.HTTPError as e:
                try:
                    err = e.read().decode("utf-8", errors="ignore")
                finally:
                    try:
                        e.close()
                    except Exception:
                        pass
                category, wait_sec, reason = classify_gemini_error(e.code, err)

                if category == "DAILY_QUOTA_EXHAUSTED":
                    pool.mark_daily_quota_exhausted(api_key, err)
                    logger.warning(
                        f"  [KEY ROTATION] Key ...{api_key[-6:]} daily quota reached (10 RPD). "
                        f"Parked for today."
                    )
                    # Decouple IP-level correlation: pause 18-32s before contacting next project
                    cadence.wait_for_key_switch(api_key[-6:], "next_project")
                    key_exhausted_or_invalid = True
                    break  # Break inner loop to acquire next active key

                elif category == "INVALID_KEY":
                    pool.mark_invalid(api_key, err)
                    logger.error(
                        f"  [INVALID KEY] Key ...{api_key[-6:]} is invalid/disabled. Bypassing..."
                    )
                    key_exhausted_or_invalid = True
                    break  # Break inner loop to acquire next active key

                elif category == "RPM_RATE_LIMIT":
                    pool.mark_temporary_backoff(api_key, wait_sec, err)
                    logger.warning(
                        f"  [RPM BURST] Key ...{api_key[-6:]} hit temporary rate limit. "
                        f"Cooling off {wait_sec:.1f}s. Switching key from pool..."
                    )
                    if rate_limiter and hasattr(rate_limiter, "trigger_global_pause"):
                        rate_limiter.trigger_global_pause(wait_sec)
                    key_exhausted_or_invalid = False
                    break  # Break inner loop to acquire next active key from pool

                elif category == "TRANSIENT_SERVER_ERROR":
                    pool.mark_temporary_backoff(api_key, wait_sec, err)
                    logger.warning(
                        f"  [SERVER GLITCH] HTTP {e.code} temporary Google hiccup. "
                        f"Cooling off {wait_sec:.1f}s (Attempt {network_attempt+1}/3)..."
                    )
                    time.sleep(wait_sec)
                    continue

                else:
                    logger.warning(f"  [HTTP {e.code}] Error: {err[:100]}. Cooling off 5s...")
                    time.sleep(5.0)
                    continue

            except (urllib.error.URLError, TimeoutError, ConnectionResetError, OSError) as net_err:
                logger.warning(
                    f"  [NETWORK GLITCH] {type(net_err).__name__}: {net_err}. "
                    f"Cooling off 6s before retry (Attempt {network_attempt+1}/3)..."
                )
                time.sleep(6.0)
                continue

        # If 3 network attempts failed on this key, cool it off and rotate to next key
        if not key_exhausted_or_invalid:
            logger.warning(f"  [KEY COOLOFF] Key ...{api_key[-6:]} had 3 consecutive transient errors. Cooling off 25s...")
            pool.mark_temporary_backoff(api_key, 25.0, "3 consecutive transient errors")




def synthesize_gemini_multispeaker_batch(
    batch: BatchPlanItem,
    output_file: Path,
    voice_map: Dict[str, str],
    model: str = DEFAULT_MODEL,
    rate_limiter: Optional[TokenBucketRateLimiter] = None,
) -> Tuple[Path, float]:
    """
    Synthesizes a multi-speaker dialogue batch using Gemini 3.8 Flash TTS
    with multiSpeakerVoiceConfig and per-part speechMetadata.
    """
    speakers = list(batch.speakers)
    if len(speakers) != 2:
        raise ValueError(
            f"multiSpeakerVoiceConfig strictly requires exactly 2 speakers, got {len(speakers)}: {speakers}"
        )

    spk_configs = []
    for spk in speakers:
        v_name = voice_map.get(spk, "Aoede")
        spk_configs.append({
            "speaker": spk,
            "voiceConfig": {
                "prebuiltVoiceConfig": {
                    "voiceName": v_name
                }
            }
        })

    parts = []
    for seg in batch.segments:
        # Prefer resolved spoken_text, falling back to literary text
        if hasattr(seg, "spoken_text") and seg.spoken_text:
            clean_text = seg.spoken_text.strip()
        elif isinstance(seg, dict) and seg.get("spoken_text"):
            clean_text = seg["spoken_text"].strip()
        else:
            clean_text = seg.text.strip() if hasattr(seg, "text") else seg.get("text", "").strip()
            stripped = re.sub(r"^[^\w\d\u0900-\u097F]+|[^\w\d\u0900-\u097F]+$", "", clean_text)
            if stripped in NUMERAL_NORMALIZATION:
                clean_text = NUMERAL_NORMALIZATION[stripped]
            elif clean_text in NUMERAL_NORMALIZATION:
                clean_text = NUMERAL_NORMALIZATION[clean_text]

        spk = seg.speaker if hasattr(seg, "speaker") else seg.get("speaker", "Narrator")
        acting = getattr(seg, "acting", None) if hasattr(seg, "acting") else seg.get("acting")
        emotion = getattr(seg, "emotion", "neutral") if hasattr(seg, "emotion") else seg.get("emotion", "neutral")
        intensity = getattr(seg, "intensity_level", "medium") if hasattr(seg, "intensity_level") else seg.get("intensity_level", "medium")
        mem_vc = getattr(seg, "memory_vocal_constraint", None) if hasattr(seg, "memory_vocal_constraint") else seg.get("memory_vocal_constraint")

        style_desc = resolve_speech_metadata_style(acting, emotion, intensity, memory_vocal_constraint=mem_vc)
        parts.append({
            "text": clean_text,
            "speechMetadata": {
                "speaker": spk,
                "style": style_desc
            }
        })

    payload = {
        "contents": [{
            "role": "user",
            "parts": parts
        }],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "multiSpeakerVoiceConfig": {
                    "speakerVoiceConfigs": spk_configs
                }
            },
            "temperature": round(random.uniform(0.685, 0.715), 3)
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }

    data = json.dumps(payload).encode("utf-8")
    cadence = get_human_cadence_controller()
    pool = get_persistent_key_pool()

    MAX_KEY_ROTATIONS = 15
    rotation_count = 0

    while True:
        rotation_count += 1
        if rotation_count > MAX_KEY_ROTATIONS:
            raise RuntimeError(
                f"Multi-speaker batch TTS failed after {MAX_KEY_ROTATIONS} key rotations."
            )

        api_key = pool.get_key(service="tts")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        key_exhausted_or_invalid = False

        for network_attempt in range(3):
            if rate_limiter:
                rate_limiter.acquire()

            req = urllib.request.Request(
                url,
                data=data,
                headers=get_stealth_sdk_headers(api_key),
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=120.0) as resp:
                    resp_json = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_json.get("candidates", [])
                    if not candidates:
                        fb = resp_json.get("promptFeedback", {})
                        raise ValueError(f"Gemini TTS blocked generation (promptFeedback: {fb})")
                    candidate = candidates[0]
                    finish_reason = candidate.get("finishReason")
                    if finish_reason in ("SAFETY", "RECITATION", "BLOCKLIST"):
                        raise ValueError(f"Gemini TTS generation blocked by finishReason: {finish_reason}")

                    inline_data = {}
                    cand_parts = candidate.get("content", {}).get("parts", [])
                    for p in cand_parts:
                        if "inlineData" in p:
                            inline_data = p["inlineData"]
                            break
                    b64_audio = inline_data.get("data", "")
                    if not b64_audio:
                        raise ValueError("No audio data found in Gemini multi-speaker response parts")

                    raw_bytes = base64.b64decode(b64_audio)
                    raw_pcm, sample_rate, frames = extract_clean_pcm_from_gemini_container(raw_bytes)
                    dur_sec = frames / float(sample_rate)
                    word_count = max(batch.total_words, 1)
                    ratio = dur_sec / word_count

                    # Audio Quality & SNR Gatekeeper (Mathematical PCM Probe)
                    import struct
                    import math
                    sample_count = len(raw_pcm) // 2
                    if sample_count > 0:
                        samples = struct.unpack(f"<{sample_count}h", raw_pcm)
                        peak_amp = max(abs(s) for s in samples)
                        sum_sq = sum(s * s for s in samples)
                        rms = math.sqrt(sum_sq / sample_count)
                        dc_offset = abs(sum(samples) / sample_count)
                    else:
                        peak_amp = 0
                        rms = 0.0
                        dc_offset = 0.0

                    # True flat-top clipping requires >= 6 consecutive samples pinned at rail
                    consec = 0
                    max_consec = 0
                    for s in samples:
                        if abs(s) >= 32760:
                            consec += 1
                            if consec > max_consec:
                                max_consec = consec
                        else:
                            consec = 0
                    is_clipped = (max_consec >= 6)

                    # For batches, check reasonable RMS floor (faint audio detection)
                    is_silent_faint = (peak_amp > 0 and word_count >= 3 and rms < 15.0)
                    is_dc_corrupted = (peak_amp > 0 and dur_sec >= 2.0 and dc_offset > 1500.0)
                    is_stutter = (word_count > 3 and ratio > 3.2 and dur_sec >= 15.0)
                    is_empty = (dur_sec < 0.20 and word_count >= 3)

                    # Dead air / internal silence gap detector (4s+ silence run)
                    has_long_silence = False
                    if dur_sec >= 6.0 and sample_count > 0:
                        window = 24000
                        silent_run = 0
                        max_silent_run = 0
                        for w_idx in range(0, sample_count, window):
                            sub = samples[w_idx:w_idx + window]
                            sub_rms = math.sqrt(sum(s * s for s in sub) / len(sub))
                            if sub_rms < 15.0:
                                silent_run += 1
                                if silent_run > max_silent_run:
                                    max_silent_run = silent_run
                            else:
                                silent_run = 0
                        if max_silent_run >= 4:
                            has_long_silence = True

                    has_defect = (is_clipped or is_silent_faint or is_dc_corrupted or is_stutter or is_empty or has_long_silence)
                    if has_defect:
                        reasons = []
                        if is_clipped: reasons.append(f"Clipping Distortion (Consec Rail {max_consec} >= 6)")
                        if is_silent_faint: reasons.append(f"Faint Audio (RMS {rms:.1f} < 15)")
                        if is_dc_corrupted: reasons.append(f"DC Offset Anomaly ({dc_offset:.1f} > 1500)")
                        if is_stutter: reasons.append(f"Stutter Loop (Ratio {ratio:.2f}s/w)")
                        if is_empty: reasons.append("Empty Audio Truncation")
                        if has_long_silence: reasons.append("Excessive Dead Air (>= 4s internal silence)")
                        reason_str = " | ".join(reasons)
                        if network_attempt < 2:
                            logger.warning(
                                f"  [SNR GATEKEEPER BATCH: {reason_str}] Generated {dur_sec:.1f}s for {word_count} words. "
                                f"Retrying batch (Attempt {network_attempt+1}/3)..."
                            )
                            time.sleep(2.0)
                            continue
                        else:
                            raise ValueError(
                                f"SNR Gatekeeper rejected batch audio after 3 failed attempts: {reason_str} "
                                f"(dur={dur_sec:.1f}s, words={word_count}, peak={peak_amp}, rms={rms:.1f})"
                            )

                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    tmp_file = output_file.with_suffix(".tmp.wav")
                    with wave.open(str(tmp_file), "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(sample_rate)
                        wf.writeframes(raw_pcm)

                    tmp_file.replace(output_file)
                    pool.record_success(api_key)
                    logger.info(
                        f"  [MULTI-SPEAKER BATCH] Rendered {batch.batch_id} ({dur_sec:.1f}s, {batch.total_words} words) via key ...{api_key[-6:]}"
                    )
                    return output_file, dur_sec

            except urllib.error.HTTPError as e:
                err = ""
                try:
                    err = e.read().decode("utf-8")
                except Exception:
                    pass
                category, wait_sec, reason = classify_gemini_error(e.code, err)
                if category == "DAILY_QUOTA_EXHAUSTED":
                    pool.mark_daily_quota_exhausted(api_key, err)
                    cadence.wait_for_key_switch(api_key[-6:], "next_project")
                    key_exhausted_or_invalid = True
                    break
                elif category == "INVALID_KEY":
                    pool.mark_invalid(api_key, err)
                    key_exhausted_or_invalid = True
                    break
                elif category == "RPM_RATE_LIMIT":
                    pool.mark_temporary_backoff(api_key, wait_sec, err)
                    if rate_limiter and hasattr(rate_limiter, "trigger_global_pause"):
                        rate_limiter.trigger_global_pause(wait_sec)
                    break
                elif category == "TRANSIENT_SERVER_ERROR":
                    pool.mark_temporary_backoff(api_key, wait_sec, err)
                    time.sleep(wait_sec)
                    continue
                else:
                    time.sleep(5.0)
                    continue
            except Exception as net_err:
                time.sleep(6.0)
                continue

        if not key_exhausted_or_invalid:
            pool.mark_temporary_backoff(api_key, 25.0, "3 consecutive transient errors in multi-speaker batch")


def compute_canonical_segment_filename(
    chapter_num: int,
    seg_num: int,
    text: str,
    sp_cfg: Optional[Dict[str, Any]] = None,
    default_voice: str = DEFAULT_VOICE,
) -> str:
    """Computes deterministic, reproducible audio chunk filename matching synthesis cache."""
    cfg = sp_cfg or {}
    voice = cfg.get("voice", default_voice)
    speed = float(cfg.get("speed", 1.0))
    pitch = float(cfg.get("pitch", 1.0))
    bass_boost_db = float(cfg.get("bass_boost_db", 0.0))
    clarity_cut_db = float(cfg.get("clarity_reduction_db", 0.0))
    lowpass_hz = int(cfg.get("lowpass_hz", 0))
    highpass_hz = int(cfg.get("highpass_hz", 0))
    presence_boost_db = float(cfg.get("presence_boost_db", 0.0))
    volume_gain_db = float(cfg.get("volume_gain_db", 0.0))
    calib_str = f"{voice}:{speed:.2f}:{pitch:.2f}:{bass_boost_db:.1f}:{clarity_cut_db:.1f}:{lowpass_hz}:{highpass_hz}:{presence_boost_db:.1f}:{volume_gain_db:.1f}"
    cache_key = f"{text}|{calib_str}".encode("utf-8")
    text_hash = hashlib.md5(cache_key).hexdigest()[:8]
    return f"c{chapter_num:03d}_s{seg_num:04d}_{text_hash}.wav"


def slice_and_declick_batch(
    raw_audio: Path,
    batch: BatchPlanItem,
    chapter_num: int,
    output_dir: Path,
    aligner: Optional[WorkstationForcedAligner] = None,
    declick_fade_ms: float = DEFAULT_DECLICK_FADE_MS,
    dispatcher: Optional[Any] = None,
) -> List[Tuple[Path, float]]:
    """
    Slices a merged multi-speaker WAV into individual canonical segment WAV files.
    Uses WorkstationForcedAligner on RTX 4050 GPU for sample-accurate boundaries,
    and applies a 25Hz DC filter + 5ms cosine micro-fade + character DSP calibration at slice boundaries.
    """
    if aligner is None:
        aligner = WorkstationForcedAligner()

    boundaries = aligner.align_batch(raw_audio, batch.segments)
    sliced_results: List[Tuple[Path, float]] = []
    ffmpeg_bin = get_ffmpeg()

    fade_sec = max(0.001, declick_fade_ms / 1000.0)

    for seg, (start_ms, end_ms) in zip(batch.segments, boundaries):
        dur_ms = max(200, end_ms - start_ms)
        dur_sec = dur_ms / 1000.0
        start_sec = start_ms / 1000.0

        sp_cfg = dispatcher.get_speaker_config(seg.speaker, getattr(seg, "type", "dialogue")) if dispatcher else {}
        voice_name = sp_cfg.get("voice") or batch.voice_map.get(seg.speaker, "Aoede")
        if not sp_cfg:
            sp_cfg = {"voice": voice_name}

        out_filename = compute_canonical_segment_filename(chapter_num, seg.index, seg.text, sp_cfg, default_voice=voice_name)
        out_wav = output_dir / out_filename

        fade_out_start = max(0.0, dur_sec - fade_sec)
        fade_sec = max(0.015, declick_fade_ms / 1000.0)
        fade_out_start = max(0.0, dur_sec - fade_sec)
        filter_parts = [
            "highpass=f=30",
            f"afade=t=in:ss=0:d={fade_sec:.3f}:curve=qsin",
            f"afade=t=out:st={fade_out_start:.3f}:d={fade_sec:.3f}:curve=qsin",
            "alimiter=limit=-1.2dB:attack=5:release=50:asc=true",
        ]

        if sp_cfg:
            highpass_hz = int(sp_cfg.get("highpass_hz", 0))
            bass_boost_db = float(sp_cfg.get("bass_boost_db", 0.0))
            presence_boost_db = float(sp_cfg.get("presence_boost_db", 0.0))
            volume_gain_db = float(sp_cfg.get("volume_gain_db", 0.0))
            clarity_cut_db = float(sp_cfg.get("clarity_reduction_db", 0.0))
            lowpass_hz = int(sp_cfg.get("lowpass_hz", 0))
            softclip_tanh = bool(sp_cfg.get("softclip_tanh", False))
            if highpass_hz > 25:
                filter_parts.append(f"highpass=f={highpass_hz}")
            if bass_boost_db > 0.1:
                filter_parts.append(f"equalizer=f=100:t=q:w=1.2:g={bass_boost_db:.1f}")
                filter_parts.append("equalizer=f=200:t=q:w=1.4:g=3.0")
            elif bass_boost_db < -0.1:
                filter_parts.append(f"equalizer=f=200:t=q:w=1.2:g={bass_boost_db:.1f}")
            if presence_boost_db > 0.1:
                filter_parts.append(f"equalizer=f=3200:t=q:w=1.4:g={presence_boost_db:.1f}")
            if abs(volume_gain_db) > 0.1:
                filter_parts.append(f"volume={volume_gain_db:+.1f}dB")
            if clarity_cut_db > 0.1:
                filter_parts.append(f"equalizer=f=3000:t=q:w=1.8:g=-{clarity_cut_db:.1f}")
            if lowpass_hz > 1000:
                filter_parts.append(f"lowpass=f={lowpass_hz}")
            if softclip_tanh or ("[shouting]" in seg.text.lower()):
                filter_parts.append("asoftclip=type=tanh:param=1.2")

        filter_str = ",".join(filter_parts)

        tmp_slice = out_wav.with_suffix(".tmp.wav")
        cmd = [
            ffmpeg_bin, "-y",
            "-ss", f"{start_sec:.3f}",
            "-t", f"{dur_sec:.3f}",
            "-i", str(raw_audio),
            "-af", filter_str,
            "-c:a", "pcm_s16le",
            str(tmp_slice),
        ]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # Enforce exact zero-crossing endpoints on sliced chunk
            try:
                with wave.open(str(tmp_slice), "rb") as in_wf:
                    p_params = in_wf.getparams()
                    p_pcm = in_wf.readframes(in_wf.getnframes())
                import numpy as _np
                p_samples = _np.frombuffer(p_pcm, dtype=_np.int16).copy()
                if len(p_samples) > 2:
                    p_samples[0] = 0
                    p_samples[-1] = 0
                with wave.open(str(tmp_slice), "wb") as out_wf:
                    out_wf.setparams(p_params)
                    out_wf.writeframes(p_samples.tobytes())
            except Exception:
                pass
            tmp_slice.replace(out_wav)
            actual_dur = dur_sec
            try:
                with wave.open(str(out_wav), "rb") as wf:
                    actual_dur = wf.getnframes() / float(wf.getframerate())
            except Exception:
                pass
            sliced_results.append((out_wav, actual_dur))
        except Exception as e:
            logger.error(f"[!] Failed to slice segment {seg.index} from batch {batch.batch_id}: {e}")
            if tmp_slice.exists():
                tmp_slice.unlink(missing_ok=True)
            raise RuntimeError(f"Acoustic slicing failed for segment {seg.index} in batch {batch.batch_id}: {e}") from e

    return sliced_results


class UnregisteredSpeakerError(KeyError):
    """Raised when a dialogue segment requests an unregistered character voice."""
    pass


class TTSDispatcher:
    """Orchestrates concurrent speech synthesis with TokenBucket rate limiting and SQLite ledger state."""

    def __init__(
        self,
        project_dir: Path,
        default_backend: str = DEFAULT_BACKEND,
        default_voice: str = DEFAULT_VOICE,
        max_workers: int = 1,
        rpm: float = DEFAULT_RPM,
        audio_dir: Optional[Path] = None,
        strict_speakers: bool = True,
    ):
        self.project_dir = Path(project_dir).resolve()
        self.audio_dir = Path(audio_dir).resolve() if audio_dir else (self.project_dir / "audio_chunks")
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.project_dir / "voice_registry.json"
        self.roster_file = self.project_dir / "character_roster.json"
        self.default_backend = default_backend
        self.default_voice = default_voice
        self.strict_speakers = strict_speakers
        if max_workers > 1:
            logger.info("  [STEALTH INVARIANT] Multi-worker network requests disabled to prevent IP clustering and quota flags. Operating strictly in 1-worker mode.")
        self.max_workers = 1
        self.rate_limiter = TokenBucketRateLimiter(rate_rpm=rpm)
        self.voice_map = self._load_voice_registry()
        self.alias_map, self.gender_map = self._load_character_roster()
        self.ledger = ProjectStateLedger(self.project_dir)
        self.batching_enabled = DEFAULT_BATCHING_ENABLED
        self.forced_aligner = WorkstationForcedAligner() if DEFAULT_FORCED_ALIGNMENT_ENABLED else None
        self.batch_planner = BatchDispatchPlanner()
        # Performance Realization Layer
        from audiobook_factory.performance import (
            PerformanceDirector,
            TakeBank,
            PerformanceEvaluator,
            IntelligentTakeSelector,
            PerformanceContinuityTracker,
        )
        pb = None
        for cand_pb in (self.project_dir / "performance_bible.json", self.project_dir / "dramaturgy" / "performance_bible.json"):
            if cand_pb.exists():
                try:
                    from audiobook_factory.dramaturgy.contracts import PerformanceBible
                    pb = PerformanceBible.load_from_file(cand_pb)
                    break
                except Exception:
                    pass
        self.performance_director = PerformanceDirector(performance_bible=pb)
        self.take_bank = TakeBank(self.audio_dir / "takes")
        self.evaluator = PerformanceEvaluator()
        self.take_selector = IntelligentTakeSelector(evaluator=self.evaluator)
        self.continuity_tracker = PerformanceContinuityTracker()
        for cand_cc in (self.project_dir / "character_continuity.json", self.project_dir / "performance" / "character_continuity.json"):
            if cand_cc.exists():
                self.continuity_tracker.load_from_file(cand_cc)
                break

        # Pronunciation & Spoken Language QA Subsystem
        from audiobook_factory.pronunciation import (
            PronunciationLexicon,
            PronunciationResolver,
            SpokenTextEngine,
            PronunciationAudioQA,
            PronunciationRepairEngine,
        )
        book_bible = None
        for cand_bb in (self.project_dir / "book_bible.json", self.project_dir / "translation" / "book_bible.json"):
            if cand_bb.exists():
                try:
                    from audiobook_factory.translation.book_bible import BookBible
                    book_bible = BookBible.load_from_project(self.project_dir)
                    break
                except Exception:
                    pass
        self.pronunciation_lexicon = PronunciationLexicon.load_or_create(self.project_dir, book_bible=book_bible)
        self.pronunciation_resolver = PronunciationResolver(lexicon=self.pronunciation_lexicon, book_bible=book_bible)
        self.spoken_text_engine = SpokenTextEngine(resolver=self.pronunciation_resolver)
        self.pronunciation_auditor = PronunciationAudioQA(forced_aligner=self.forced_aligner)
        self.pronunciation_repair = PronunciationRepairEngine(auditor=self.pronunciation_auditor)

        # Formal Cast Lock Subsystem (Wave 1 Upgrade)
        from audiobook_factory.casting import CastLockManager
        self.cast_lock_manager = CastLockManager(self.project_dir)

        # Character Voice DNA & Reference Subsystems (Wave 2 Upgrade)
        from audiobook_factory.identity import VoiceDNABank, ReferenceVoiceBank
        from audiobook_factory.performance.scene_emotional_state import SceneEmotionalStateTracker
        self.voice_dna_bank = VoiceDNABank(self.project_dir)
        self.reference_voice_bank = ReferenceVoiceBank(self.project_dir)
        self.scene_tracker = SceneEmotionalStateTracker()

    def _load_character_roster(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Loads character aliases and gender mappings from character_roster.json."""
        alias_map: Dict[str, str] = {}
        gender_map: Dict[str, str] = {}
        if not self.roster_file.exists():
            return alias_map, gender_map

        try:
            with open(self.roster_file, "r", encoding="utf-8") as f:
                roster_data = json.load(f)
            chars = roster_data.get("characters", roster_data)
            if isinstance(chars, dict):
                for canon_name, details in chars.items():
                    c_clean = canon_name.strip()
                    alias_map[c_clean.lower()] = c_clean
                    alias_map[c_clean.lower().replace("_", " ")] = c_clean
                    alias_map[c_clean.lower().replace(" ", "_")] = c_clean
                    if isinstance(details, dict):
                        gender_map[c_clean] = details.get("gender", "neutral").lower()
                        for alias in details.get("aliases", []):
                            if isinstance(alias, str) and alias.strip():
                                a_clean = alias.strip()
                                alias_map[a_clean.lower()] = c_clean
                                alias_map[a_clean.lower().replace("_", " ")] = c_clean
                                alias_map[a_clean.lower().replace(" ", "_")] = c_clean
            elif isinstance(chars, list):
                for item in chars:
                    if isinstance(item, dict):
                        canon_name = item.get("english_name") or item.get("display_name") or item.get("name", "")
                        if canon_name:
                            c_clean = canon_name.strip()
                            alias_map[c_clean.lower()] = c_clean
                            alias_map[c_clean.lower().replace("_", " ")] = c_clean
                            gender_map[c_clean] = item.get("gender", "neutral").lower()
                            hindi = item.get("hindi_name", "")
                            if hindi:
                                alias_map[hindi.strip().lower()] = c_clean
                            for alias in item.get("aliases", []):
                                if isinstance(alias, str) and alias.strip():
                                    a_clean = alias.strip()
                                    alias_map[a_clean.lower()] = c_clean
                                    alias_map[a_clean.lower().replace("_", " ")] = c_clean
        except Exception as e:
            logger.warning(f"  [ROSTER LOAD NOTICE] Failed to parse character_roster.json: {e}")

        return alias_map, gender_map

    def _load_voice_registry(self) -> Dict[str, Any]:
        if self.registry_file.exists():
            with open(self.registry_file, "r", encoding="utf-8") as f:
                return json.load(f)

        default_map = {
            "Narrator": {"backend": self.default_backend, "voice": self.default_voice, "speed": 1.0},
        }
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(default_map, f, indent=2)
        return default_map

    def assign_voice(self, speaker: str, backend: str, voice: str, speed: float = 1.0):
        """Assign voice to a specific character permanently."""
        self.voice_map[speaker] = {
            "backend": backend,
            "voice": voice,
            "speed": speed,
        }
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(self.voice_map, f, indent=2)

        if hasattr(self, "cast_lock_manager") and self.cast_lock_manager:
            self.cast_lock_manager.lock_character(
                character_id=speaker.lower().replace(" ", "_"),
                character_name=speaker,
                voice_id=voice,
                calibration_overrides={"speed": speed},
            )

    def get_speaker_config(self, speaker: str, seg_type: str = "narration") -> Dict[str, Any]:
        """
        Resolves complete speaker configuration (backend, voice, speed, pitch, bass_boost_db).
        Strictly prohibits silent fallback to Narrator (Aoede) for dialogue segments.
        """
        sp_clean = (speaker or "").strip()
        sp_lower = sp_clean.lower()

        # 0. Formal Cast Lock Resolution (Wave 1 Cast Lock takes authoritative priority)
        if hasattr(self, "cast_lock_manager") and self.cast_lock_manager:
            lock = self.cast_lock_manager.get_lock(sp_clean)
            if not lock and sp_lower in self.alias_map:
                lock = self.cast_lock_manager.get_lock(self.alias_map[sp_lower])
            if lock and lock.locked:
                cfg = {
                    "backend": "gemini_tts",
                    "voice": lock.voice_id,
                    "speed": lock.calibration_overrides.get("speed", 1.0),
                    "pitch": lock.calibration_overrides.get("pitch", 1.0),
                    "cast_locked": True,
                    "casting_version": lock.casting_version,
                }
                for k, v in lock.calibration_overrides.items():
                    if k not in cfg:
                        cfg[k] = v
                return cfg

        # 1. Exact match in voice_map
        if sp_clean in self.voice_map:
            return dict(self.voice_map[sp_clean])

        # 2. Case-insensitive / normalized underscore match in voice_map
        for k, cfg in self.voice_map.items():
            k_lower = k.strip().lower()
            if k_lower == sp_lower or k_lower.replace("_", " ") == sp_lower.replace("_", " "):
                return dict(cfg)

        # 3. Alias resolution via character_roster.json
        if sp_lower in self.alias_map:
            canon = self.alias_map[sp_lower]
            if canon in self.voice_map:
                return dict(self.voice_map[canon])
            canon_norm = canon.lower().replace("_", " ")
            for k, cfg in self.voice_map.items():
                if k.strip().lower() == canon.lower() or k.strip().lower().replace("_", " ") == canon_norm:
                    return dict(cfg)

        sp_norm = sp_lower.replace("_", " ")
        if sp_norm in self.alias_map:
            canon = self.alias_map[sp_norm]
            if canon in self.voice_map:
                return dict(self.voice_map[canon])
            canon_norm = canon.lower().replace("_", " ")
            for k, cfg in self.voice_map.items():
                if k.strip().lower() == canon.lower() or k.strip().lower().replace("_", " ") == canon_norm:
                    return dict(cfg)

        # 4. Narrator / Foley / Narration segment type
        if sp_clean in ("Narrator", "Foley") or sp_lower in ("narrator", "narration", "foley") or seg_type == "narration":
            narr_cfg = self.voice_map.get("Narrator", {})
            return {
                "backend": narr_cfg.get("backend", self.default_backend),
                "voice": narr_cfg.get("voice", self.default_voice),
                "speed": narr_cfg.get("speed", 1.0),
            }

        # 5. Unregistered Speaker in Dialogue Segment
        import difflib
        known_speakers = sorted(list(set(list(self.voice_map.keys()) + list(self.alias_map.keys()))))
        close = difflib.get_close_matches(sp_clean, known_speakers, n=3, cutoff=0.5)
        close_hint = f" Did you mean: {', '.join(close)}?" if close else ""

        if self.strict_speakers:
            raise UnregisteredSpeakerError(
                f"Speaker '{sp_clean}' (type: {seg_type}) is not registered in voice_registry.json "
                f"or character_roster.json!{close_hint} Silent fallback to Narrator is prohibited to prevent voice drift."
            )

        # Non-strict fallback with gender awareness
        logger.error(
            f"  [UNREGISTERED SPEAKER] '{sp_clean}' not in registry.{close_hint} Fallback initiated."
        )
        gender = self.gender_map.get(sp_clean, "neutral")
        if gender == "male":
            for male_fallback in ("Charon", "Fenrir", "Puck"):
                for k, cfg in self.voice_map.items():
                    if cfg.get("voice") == male_fallback:
                        return dict(cfg)
        narr_cfg = self.voice_map.get("Narrator", {})
        return {
            "backend": narr_cfg.get("backend", self.default_backend),
            "voice": narr_cfg.get("voice", self.default_voice),
            "speed": narr_cfg.get("speed", 1.0),
        }

    def get_speaker_voice(self, speaker: str, seg_type: str = "narration") -> Tuple[str, str]:
        """Backwards-compatible helper returning (backend, voice)."""
        cfg = self.get_speaker_config(speaker, seg_type)
        return cfg.get("backend", self.default_backend), cfg.get("voice", self.default_voice)

    def synthesize_segment(
        self,
        segment: Dict[str, Any],
        chapter_num: int,
        seg_num: int,
        performance_direction: Optional[Any] = None,
    ) -> Tuple[Path, float]:
        """Synthesize a single speech segment with resume checkpointing and post-DSP calibration."""
        seg_type = segment.get("type", "narration") if isinstance(segment, dict) else getattr(segment, "type", "narration")

        # Deterministic Action Beat: Generate silent stereo 48kHz WAV canvas matching pause_after_ms
        if seg_type == "action":
            pause_after = segment.get("pause_after_ms", 600) if isinstance(segment, dict) else getattr(segment, "pause_after_ms", 600)
            if pause_after is None or pause_after <= 0:
                pause_after = 600
            dur = pause_after / 1000.0

            cache_key = f"action|{chapter_num}|{seg_num}|{pause_after}".encode("utf-8")
            action_hash = hashlib.md5(cache_key).hexdigest()[:8]
            out_file = self.audio_dir / f"c{chapter_num:03d}_s{seg_num:04d}_{action_hash}.wav"

            if not (out_file.exists() and out_file.stat().st_size > 44):
                out_file.parent.mkdir(parents=True, exist_ok=True)
                sample_rate = 24000
                num_frames = int(round(sample_rate * dur))
                # 24kHz mono 16-bit PCM: 1 channel * 2 bytes/sample = 2 bytes/frame (identical to Gemini vocal chunks)
                silence_bytes = b"\x00" * (num_frames * 2)
                with wave.open(str(out_file), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(silence_bytes)

            logger.info(f"  [ACTION BEAT] Created clean {dur:.2f}s silent canvas for Foley -> {out_file.name}")
            return out_file, dur

        text = segment.get("text", "").strip() if isinstance(segment, dict) else getattr(segment, "text", "").strip()
        if not text:
            raise ValueError("Empty segment text")

        speaker = segment.get("speaker", "Narrator") if isinstance(segment, dict) else getattr(segment, "speaker", "Narrator")
        sp_cfg = self.get_speaker_config(speaker, seg_type)
        voice = sp_cfg.get("voice", self.default_voice)
        speed = float(sp_cfg.get("speed", 1.0))
        # Dynamic acting pacing multiplier (e.g. 0.88 - 1.15) from Master Director Screenplay
        acting = segment.get("acting", {})
        if isinstance(acting, dict):
            pacing_mult = float(acting.get("pacing", 1.0))
        else:
            pacing_mult = float(segment.get("pacing", 1.0))
        if 0.75 <= pacing_mult <= 1.35:
            speed = speed * pacing_mult

        pitch = float(sp_cfg.get("pitch", 1.0))
        bass_boost_db = float(sp_cfg.get("bass_boost_db", 0.0))
        denoise = bool(sp_cfg.get("denoise", False))
        clarity_cut_db = float(sp_cfg.get("clarity_reduction_db", 0.0))
        lowpass_hz = int(sp_cfg.get("lowpass_hz", 0))
        highpass_hz = int(sp_cfg.get("highpass_hz", 0))
        presence_boost_db = float(sp_cfg.get("presence_boost_db", 0.0))
        volume_gain_db = float(sp_cfg.get("volume_gain_db", 0.0))
        softclip_tanh = bool(sp_cfg.get("softclip_tanh", False))

        # Checkpoint hash: includes text + voice + calibration parameters
        out_filename = compute_canonical_segment_filename(chapter_num, seg_num, text, sp_cfg, default_voice=self.default_voice)
        out_file = self.audio_dir / out_filename

        # Resume checkpoint: skip if exact hash file already exists and valid
        if out_file.exists() and out_file.stat().st_size > 1000:
            dur = 0.0
            try:
                with wave.open(str(out_file), "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    dur = frames / float(rate)
            except Exception:
                dur = 1.0
            return out_file, dur

        # Resolve Character Voice DNA & Reference Signature
        voice_dna = None
        signature = None
        if hasattr(self, "voice_dna_bank") and self.voice_dna_bank:
            try:
                voice_dna = self.voice_dna_bank.get_dna(speaker)
            except Exception:
                voice_dna = None
        if hasattr(self, "reference_voice_bank") and self.reference_voice_bank:
            try:
                signature = self.reference_voice_bank.get_signature(speaker)
            except Exception:
                signature = None

        # Update Scene Emotional State
        scene_vector = None
        if hasattr(self, "scene_tracker") and self.scene_tracker:
            emotion_hint = segment.get("emotion", "neutral") if isinstance(segment, dict) else (getattr(segment, "emotion", "neutral") or "neutral")
            intensity_hint = segment.get("intensity_level", "medium") if isinstance(segment, dict) else (getattr(segment, "intensity_level", "medium") or "medium")
            causal_hint = segment.get("causal_trigger") if isinstance(segment, dict) else getattr(segment, "causal_trigger", None)
            scene_vector = self.scene_tracker.update_state(
                segment_index=seg_num,
                speaker=speaker,
                target_emotion=emotion_hint,
                intensity=intensity_hint,
                causal_trigger=causal_hint,
            )

        # Resolve Performance Direction
        p_dir = performance_direction
        if not p_dir:
            p_dir = self.performance_director.direct_segment(
                segment,
                scene_vector=scene_vector,
                voice_dna=voice_dna,
            )

        emotion = segment.get("emotion", "neutral") if isinstance(segment, dict) else getattr(segment, "emotion", "neutral")
        intensity = segment.get("intensity_level", "medium") if isinstance(segment, dict) else getattr(segment, "intensity_level", "medium")
        mem_vc = segment.get("memory_vocal_constraint") if isinstance(segment, dict) else getattr(segment, "memory_vocal_constraint", None)

        # Resolve Spoken Text representation (leaves segment literary text immutable)
        spoken_res = self.spoken_text_engine.resolve_screenplay_segment(segment)
        tts_text = spoken_res.spoken_text or text
        if isinstance(segment, dict):
            segment["spoken_text"] = tts_text
            segment["pronunciation_metadata"] = [r.model_dump() for r in spoken_res.resolutions]
        elif hasattr(segment, "spoken_text"):
            segment.spoken_text = tts_text
            segment.pronunciation_metadata = [r.model_dump() for r in spoken_res.resolutions]

        # Multi-Take Candidate Generation via TakeBank + GenerationStrategyResolver
        from audiobook_factory.performance.strategy_resolver import GenerationStrategyResolver
        strategy_plan = GenerationStrategyResolver.resolve_strategy(p_dir, text=tts_text)
        candidate_variants = self.take_bank.get_candidate_variants(p_dir, strategy_plan=strategy_plan, text=tts_text)
        takes_for_seg = []

        for v_type in candidate_variants:
            if v_type == "standard" and len(candidate_variants) == 1:
                take_target = out_file
            else:
                take_target = self.take_bank.takes_dir / f"c{chapter_num:03d}_s{seg_num:04d}_{v_type}.wav"

            if not (take_target.exists() and take_target.stat().st_size > 1000):
                synthesize_gemini_tts(
                    text=tts_text,
                    output_file=take_target,
                    voice=voice,
                    emotion=emotion,
                    acting=acting,
                    intensity=intensity,
                    memory_vocal_constraint=mem_vc,
                    performance_direction=p_dir,
                    variant_type=v_type,
                    rate_limiter=self.rate_limiter,
                    voice_dna=voice_dna,
                    scene_vector=scene_vector,
                )

            take_var = self.take_bank.create_take(
                segment_uid=p_dir.segment_uid,
                segment_index=seg_num,
                variant_type=v_type,
                audio_file=take_target,
                direction=p_dir,
            )
            takes_for_seg.append(take_var)

        # Intelligent Take Selection with Voice Identity & Reference Signature
        winning_take = self.take_selector.select_best_take(
            takes_for_seg,
            text,
            p_dir,
            signature=signature,
            voice_dna=voice_dna,
        )

        # Pronunciation Audio QA & Targeted Take Repair
        qa_res = self.pronunciation_auditor.audit_take(
            take_audio_path=winning_take.audio_path,
            spoken_result=spoken_res,
            take_id=winning_take.take_id,
            segment_uid=p_dir.segment_uid,
        )
        if not qa_res.passed:
            repaired_take = self.pronunciation_repair.attempt_repair(
                dispatcher=self,
                segment=segment if isinstance(segment, dict) else segment.model_dump(),
                failed_take=winning_take,
                qa_result=qa_res,
                chapter_num=chapter_num,
                seg_num=seg_num,
                p_dir=p_dir,
            )
            if repaired_take:
                winning_take = repaired_take

        if str(winning_take.audio_path) != str(out_file):
            shutil.copy2(winning_take.audio_path, str(out_file))

        out_path = out_file
        dur = winning_take.duration_sec

        # Apply speaker DSP calibration filters (noise reduction, pitch, tempo, warmth, clarity control)
        post_filters = []
        if highpass_hz > 20:
            post_filters.append(f"highpass=f={highpass_hz}")

        if denoise:
            post_filters.append("afftdn=nr=10:nf=-38")

        # Shouting / bellowing rage analog warmth & anti-harshness saturation
        if ("[shouting]" in text.lower()) or (isinstance(acting, dict) and acting.get("delivery_style") == "bellowing_rage"):
            softclip_tanh = True
            if presence_boost_db <= 0.1:
                presence_boost_db = 1.5
            elif presence_boost_db > 2.0:
                presence_boost_db = 2.0

        if softclip_tanh:
            post_filters.append("asoftclip=type=tanh:param=1.2")

        if abs(pitch - 1.0) > 0.005:
            new_rate = int(24000 * pitch)
            post_filters.append(f"asetrate={new_rate},aresample=24000")
            eff_tempo = speed / pitch
            if abs(eff_tempo - 1.0) > 0.01:
                post_filters.append(f"atempo={eff_tempo:.3f}")
        elif abs(speed - 1.0) > 0.01:
            post_filters.append(f"atempo={speed:.3f}")

        if bass_boost_db > 0.1:
            post_filters.append(f"equalizer=f=100:t=q:w=1.2:g={bass_boost_db:.1f}")
            post_filters.append("equalizer=f=200:t=q:w=1.4:g=3.0")
        elif bass_boost_db < -0.1:
            post_filters.append(f"equalizer=f=200:t=q:w=1.2:g={bass_boost_db:.1f}")

        if presence_boost_db > 0.1:
            post_filters.append(f"equalizer=f=3200:t=q:w=1.4:g={presence_boost_db:.1f}")

        if abs(volume_gain_db) > 0.1:
            post_filters.append(f"volume={volume_gain_db:+.1f}dB")

        if clarity_cut_db > 0.1:
            post_filters.append(f"equalizer=f=3000:t=q:w=1.8:g=-{clarity_cut_db:.1f}")

        if lowpass_hz > 1000:
            post_filters.append(f"lowpass=f={lowpass_hz}")

        if post_filters:
            # Enforce broadcast brickwall limiter and micro-fades to eliminate clipping and pops
            post_filters.append("alimiter=limit=-1.2dB:attack=5:release=50:asc=true")
            fade_dur_ms = 15.0
            f_sec = fade_dur_ms / 1000.0
            f_out_st = max(0.0, dur - f_sec)
            post_filters.append(f"afade=t=in:ss=0:d={f_sec:.3f}:curve=qsin")
            post_filters.append(f"afade=t=out:st={f_out_st:.3f}:d={f_sec:.3f}:curve=qsin")

            tmp_calib = out_file.with_suffix(".calib.wav")
            ffmpeg_bin = get_ffmpeg()
            cmd = [
                ffmpeg_bin, "-y",
                "-i", str(out_file),
                "-af", ",".join(post_filters),
                "-c:a", "pcm_s16le",
                str(tmp_calib),
            ]
            try:
                import subprocess
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                # Clamp exact zero endpoints on calibrated audio
                try:
                    with wave.open(str(tmp_calib), "rb") as in_wf:
                        c_params = in_wf.getparams()
                        c_pcm = in_wf.readframes(in_wf.getnframes())
                    import numpy as _np
                    c_samples = _np.frombuffer(c_pcm, dtype=_np.int16).copy()
                    if len(c_samples) > 2:
                        c_samples[0] = 0
                        c_samples[-1] = 0
                    with wave.open(str(tmp_calib), "wb") as out_wf:
                        out_wf.setparams(c_params)
                        out_wf.writeframes(c_samples.tobytes())
                except Exception:
                    pass
                tmp_calib.replace(out_file)
                with wave.open(str(out_file), "rb") as wf:
                    dur = wf.getnframes() / float(wf.getframerate())
            except Exception as e:
                logger.warning(f"  [!] Speaker DSP calibration notice: {e}")
                if tmp_calib.exists():
                    tmp_calib.unlink(missing_ok=True)

        if p_dir:
            self.continuity_tracker.record_direction(p_dir, dur)
            self.continuity_tracker.record_take(p_dir.speaker, take_id=out_path.stem, duration_sec=dur)

        return out_path, dur

    def synthesize_chapter_script(self, script_path: Path, chapter_num: int) -> List[Path]:
        """
        Synthesize all segments in a chapter script concurrently using ThreadPoolExecutor.
        Updates the SQLite state ledger at every milestone.
        """
        with open(script_path, "r", encoding="utf-8") as f:
            script = json.load(f)
        if isinstance(script, dict):
            script = script.get("segments", script)

        total = len(script)

        # Pre-flight voice registry validation across all segments (ADR-021 Zero Voice Drift)
        for seg_idx, seg in enumerate(script, 1):
            seg_t = seg.get("type", "narration")
            sp = seg.get("speaker", "Narrator")
            if seg_t == "dialogue" or (sp and sp not in ("Narrator", "Foley")):
                try:
                    self.get_speaker_config(sp, seg_t)
                except UnregisteredSpeakerError as e:
                    logger.error(
                        f"\n[!] PRE-FLIGHT SYNTHESIS HALT: Chapter {chapter_num}, Segment {seg_idx} has invalid speaker: {e}"
                    )
                    raise

        cadence = get_human_cadence_controller()
        logger.info(
            f"[*] Synthesizing Chapter {chapter_num} ({total} speech segments, mode="
            f"{'STEALTH_HUMAN_CADENCE' if self.max_workers == 1 else f'PARALLEL_{self.max_workers}'})..."
        )

        # Register in SQLite state ledger
        self.ledger.register_script_segments(chapter_num, script, self.voice_map, self.default_voice)

        # Pre-direct chapter script with conversational chemistry
        from audiobook_factory.performance.chemistry import ConversationalChemistry
        chapter_directions = self.performance_director.direct_chapter_script(script, voice_dna_bank=self.voice_dna_bank)
        chapter_directions = ConversationalChemistry.apply_conversational_chemistry(chapter_directions)
        dir_by_idx = {d.index: d for d in chapter_directions}

        # Pre-allocate results array by index
        results: List[Optional[Path]] = [None] * total

        # Batching Engine Optimization: If batching is enabled, group eligible dialogue into multi-speaker batches
        if self.batching_enabled and total > 1:
            try:
                parsed_segments = []
                for s in script:
                    if isinstance(s, ScreenplaySegment):
                        parsed_segments.append(s)
                    elif isinstance(s, dict):
                        parsed_segments.append(ScreenplaySegment.model_validate(s))

                voice_map_for_batch = {}
                for s in parsed_segments:
                    spk = s.speaker
                    if spk not in voice_map_for_batch:
                        _, v = self.get_speaker_voice(spk, s.type)
                        voice_map_for_batch[spk] = v

                manifest = self.batch_planner.plan_chapter_batches(
                    segments=parsed_segments,
                    chapter_id=f"chapter_{chapter_num:03d}",
                    chapter_num=chapter_num,
                    voice_map=voice_map_for_batch,
                )

                manifest_file = self.audio_dir / f"c{chapter_num:03d}_batch_manifest.json"
                with open(manifest_file, "w", encoding="utf-8") as f:
                    f.write(manifest.model_dump_json(indent=2))

                for batch in manifest.batches:
                    if batch.strategy in ("multi_speaker_duo", "narrator_chunk"):
                        all_exist = True
                        for seg in batch.segments:
                            existing = list(self.audio_dir.glob(f"c{chapter_num:03d}_s{seg.index:04d}_*.wav"))
                            if not existing or existing[0].stat().st_size <= 1000:
                                all_exist = False
                                break

                        if all_exist:
                            for seg in batch.segments:
                                existing = list(self.audio_dir.glob(f"c{chapter_num:03d}_s{seg.index:04d}_*.wav"))[0]
                                dur = 1.0
                                try:
                                    with wave.open(str(existing), "rb") as wf:
                                        dur = wf.getnframes() / float(wf.getframerate())
                                except Exception:
                                    pass
                                results[seg.index - 1] = existing
                                self.ledger.mark_segment_completed(existing.stem, str(existing), dur, chapter_num=chapter_num, seg_num=seg.index)
                            continue

                        batch_wav = self.audio_dir / f"{batch.batch_id}_raw.wav"
                        try:
                            cadence.wait_before_segment(" ".join(s.text for s in batch.segments[:2]), batch.segments[0].index, total)
                            if batch.strategy == "multi_speaker_duo":
                                synthesize_gemini_multispeaker_batch(
                                    batch=batch,
                                    output_file=batch_wav,
                                    voice_map=batch.voice_map,
                                    rate_limiter=self.rate_limiter,
                                )
                            else:
                                # Narrator super-chunk: synthesize unified text via single voice
                                narr_spk = batch.speakers[0] if batch.speakers else "Narrator"
                                narr_voice = batch.voice_map.get(narr_spk, self.default_voice)
                                combined_text = "  ".join(s.text.strip() for s in batch.segments)
                                synthesize_gemini_tts(
                                    text=combined_text,
                                    output_file=batch_wav,
                                    voice=narr_voice,
                                    rate_limiter=self.rate_limiter,
                                )

                            sliced = slice_and_declick_batch(
                                raw_audio=batch_wav,
                                batch=batch,
                                chapter_num=chapter_num,
                                output_dir=self.audio_dir,
                                aligner=self.forced_aligner,
                                dispatcher=self,
                            )
                            for seg, (s_file, dur) in zip(batch.segments, sliced):
                                results[seg.index - 1] = s_file
                                self.ledger.mark_segment_completed(s_file.stem, str(s_file), dur, chapter_num=chapter_num, seg_num=seg.index)
                                logger.info(f"  [{seg.index}/{total}] Batch Sliced: {seg.speaker} ({s_file.name}, {dur:.1f}s)")
                        except AllKeysExhaustedTodayError as e:
                            logger.critical(f"  [QUOTA PAUSE] All keys exhausted during batch {batch.batch_id}: {e}")
                            break
                        except Exception as e:
                            logger.warning(f"  [!] Batch {batch.batch_id} fallback ({e}). Falling back to granular synthesis.")
            except Exception as e:
                logger.warning(f"[!] Batch planning notice: {e}. Falling back to standard pipeline.")

        # STEALTH HUMAN CADENCE EXECUTION (Strictly 1-worker sequential pipeline)
        keys_exhausted = False
        for idx, segment in enumerate(script, 1):
            # If segment was already completed in batch execution, skip redundant single call
            if results[idx - 1] is not None:
                continue

            speaker = segment.get("speaker", "Narrator")
            text = segment.get("text", "")

            # If action beat: generate clean silent canvas instantly without human cadence delay or API calls
            if segment.get("type") == "action":
                audio_path, dur = self.synthesize_segment(segment, chapter_num, idx)
                self.ledger.mark_segment_completed(audio_path.stem, str(audio_path), dur, chapter_num=chapter_num, seg_num=idx)
                results[idx - 1] = audio_path
                logger.info(f"  [{idx}/{total}] Generated Action Beat Foley Canvas ({audio_path.name}, {dur:.1f}s)")
                continue

            # If already cached on disk, fast-forward with zero sleep
            existing_matches = list(self.audio_dir.glob(f"c{chapter_num:03d}_s{idx:04d}_*.wav"))
            if existing_matches and existing_matches[0].stat().st_size > 1000:
                audio_file = existing_matches[0]
                dur = 1.0
                try:
                    with wave.open(str(audio_file), "rb") as wf:
                        dur = wf.getnframes() / float(wf.getframerate())
                except Exception:
                    pass
                results[idx - 1] = audio_file
                self.ledger.mark_segment_completed(audio_file.stem, str(audio_file), dur, chapter_num=chapter_num, seg_num=idx)
                logger.info(f"  [{idx}/{total}] Cached {speaker} ({audio_file.name}, {dur:.1f}s)")
                continue

            # Uncached segment: apply organic human reading & listening delay
            _, voice = self.get_speaker_voice(speaker, segment.get("type", "narration"))
            cache_key = f"{text}|{voice}".encode("utf-8")
            seg_hash = hashlib.md5(cache_key).hexdigest()[:8]
            seg_id = f"c{chapter_num:03d}_s{idx:04d}_{seg_hash}"

            cadence.wait_before_segment(text, idx, total)
            self.ledger.mark_segment_started(seg_id, chapter_num=chapter_num, seg_num=idx)

            try:
                audio_path, dur = self.synthesize_segment(segment, chapter_num, idx, performance_direction=dir_by_idx.get(idx))
                self.ledger.mark_segment_completed(seg_id, str(audio_path), dur, chapter_num=chapter_num, seg_num=idx)
                cadence.record_completed_segment(dur)
                results[idx - 1] = audio_path
                logger.info(f"  [{idx}/{total}] Generated {speaker} ({audio_path.name}, {dur:.1f}s)")
            except AllKeysExhaustedTodayError as e:
                logger.critical(
                    f"  [STEALTH QUOTA PAUSE] {e}. "
                    f"Safely checkpointed at segment {idx}/{total}. No wasted requests."
                )
                keys_exhausted = True
                break
            except Exception as e:
                self.ledger.mark_segment_failed(seg_id, str(e), chapter_num=chapter_num, seg_num=idx)
                logger.error(f"  [ERROR] Segment {idx} ({speaker}) failed: {e}")

        # Targeted 1-pass recovery on transient missed segments
        missing_indices = [i + 1 for i, p in enumerate(results) if p is None]
        pool = get_persistent_key_pool()
        if missing_indices and pool.get_status_summary().get("active_keys", 0) > 0:
            logger.info(f"[*] Attempting 1-pass recovery for {len(missing_indices)} transient missed segment(s): {missing_indices}...")
            for idx in missing_indices:
                seg = script[idx - 1]
                try:
                    audio_path, dur = self.synthesize_segment(seg, chapter_num, idx, performance_direction=dir_by_idx.get(idx))
                    results[idx - 1] = audio_path
                    logger.info(f"  [{idx}/{total}] Successfully recovered segment ({audio_path.name})")
                except Exception as e:
                    logger.warning(f"  Could not recover segment {idx}: {e}")

        missing = [i + 1 for i, p in enumerate(results) if p is None]
        if missing:
            if keys_exhausted or pool.get_status_summary().get("active_keys", 0) == 0:
                raise AllKeysExhaustedTodayError(
                    f"All TTS API keys exhausted for today. Chapter {chapter_num} paused at segment {missing[0]}/{total}."
                )
            raise RuntimeError(
                f"Chapter {chapter_num} synthesis incomplete: {len(missing)} segments pending ({missing[:5]}...)."
            )

        # Performance Fidelity Gate 2.8 Audit & Manifest Persistence
        try:
            self.take_bank.save_manifest(self.audio_dir / f"c{chapter_num:03d}_take_bank.json")
            selected_takes = []
            for d in chapter_directions:
                cands = self.take_bank.get_takes_for_segment(d.segment_uid)
                sels = [t for t in cands if t.is_selected]
                if sels:
                    selected_takes.append(sels[0])
                elif cands:
                    selected_takes.append(cands[0])

            if selected_takes:
                from audiobook_factory.performance.gate import PerformanceFidelityGate
                gate_report = PerformanceFidelityGate.audit_chapter_performance(
                    chapter_id=f"chapter_{chapter_num:03d}",
                    directions=chapter_directions,
                    selected_takes=selected_takes,
                    allow_warnings=True,
                )
                rep_path = self.project_dir / "manifests" / f"chapter_{chapter_num:03d}_performance_report.json"
                rep_path.parent.mkdir(parents=True, exist_ok=True)
                with open(rep_path, "w", encoding="utf-8") as rf:
                    rf.write(gate_report.model_dump_json(indent=2))

            # Persist Long-Form Character Performance Continuity (Phase 18)
            self.continuity_tracker.advance_chapter(f"chapter_{chapter_num:03d}")
            self.continuity_tracker.save_to_file(self.project_dir / "character_continuity.json")
        except Exception as e:
            logger.warning(f"  [!] Performance Layer Gate 2.8 notice: {e}")

        audio_files = [p for p in results if p is not None]
        logger.info(f"[+] Chapter {chapter_num} complete: {len(audio_files)} segments synthesized successfully.")
        return audio_files

    # Method alias for external caller compatibility
    synthesize_segment_audio = synthesize_segment


def synthesize_segment_audio(
    segment: Dict[str, Any] | Any,
    chapter_num: int,
    seg_num: int,
    audio_dir: Optional[Path] = None,
    project_dir: Optional[Path] = None,
    dispatcher: Optional[TTSDispatcher] = None,
) -> Tuple[Path, float]:
    """
    Synthesize an individual segment audio or create a silent Foley canvas for action beats.
    Non-destructive helper ensuring external callers can invoke single-segment synthesis.
    """
    if dispatcher is None:
        p_dir = project_dir or (audio_dir.parent if audio_dir else Path("."))
        dispatcher = TTSDispatcher(project_dir=p_dir, audio_dir=audio_dir)
    return dispatcher.synthesize_segment(segment, chapter_num, seg_num)

