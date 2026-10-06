#!/usr/bin/env python3
"""
Audiobook Factory - Google Gemini 3.8 Flash Speech Synthesis Provider.
Handles single-speaker and multi-speaker TTS synthesis with mathematical SNR gatekeeper,
stealth SDK headers, key pool rotation, and anti-bot rate limiting.
"""

from __future__ import annotations
import os
import sys
import time
import json
import uuid
import re
import random
import wave
import base64
import struct
import math
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.logger import logger
from audiobook_factory.restoration import extract_clean_pcm_from_gemini_container
from audiobook_factory.key_manager import (
    get_persistent_key_pool,
    classify_gemini_error,
    AllKeysExhaustedTodayError,
)
from audiobook_factory.cadence import (
    get_stealth_sdk_headers,
    get_human_cadence_controller,
)
from audiobook_factory.contracts import BatchPlanItem
from audiobook_factory.tts.constants import (
    DEFAULT_VOICE,
    DEFAULT_MODEL,
    ENABLE_EMERGENCY_FALLBACK,
    NUMERAL_NORMALIZATION,
)
from audiobook_factory.tts.rate_limiter import TokenBucketRateLimiter
from audiobook_factory.tts.providers.winrt import (
    _synthesize_local_winrt_fallback,
    _synthesize_local_batch_winrt,
)


def _resolve_key_pool():
    """Resolves active key pool, honoring test monkeypatches on tts_dispatcher facade if present."""
    td = sys.modules.get("audiobook_factory.tts_dispatcher")
    if td and hasattr(td, "get_persistent_key_pool"):
        try:
            return td.get_persistent_key_pool()
        except Exception:
            pass
    if td and hasattr(td, "global_key_pool"):
        return td.global_key_pool
    return get_persistent_key_pool()


def _resolve_cadence_controller():
    """Resolves active human cadence controller, honoring test monkeypatches on tts_dispatcher facade if present."""
    td = sys.modules.get("audiobook_factory.tts_dispatcher")
    if td and hasattr(td, "get_human_cadence_controller"):
        try:
            return td.get_human_cadence_controller()
        except Exception:
            pass
    return get_human_cadence_controller()


from audiobook_factory.audio_utils import _atomic_replace


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
    """
    Synthesizes single speech chunk using Gemini 3.8 Flash TTS with mathematical SNR verification,
    key pool rotation, and anti-censorship BLOCK_NONE safety thresholds.
    """
    if os.environ.get("TTS_PRIMARY_BACKEND", "").lower() == "local_winrt":
        return _synthesize_local_winrt_fallback(text, output_file, voice=voice)

    clean_text = text.strip()
    # Strip surrounding punctuation/quotes for numeral lookup: e.g. "८.", "'IV'", "(1)", "3,"
    stripped_token = re.sub(r"^[^\w\d\u0900-\u097F]+|[^\w\d\u0900-\u097F]+$", "", clean_text)
    if stripped_token in NUMERAL_NORMALIZATION:
        text = NUMERAL_NORMALIZATION[stripped_token]
    elif clean_text in NUMERAL_NORMALIZATION:
        text = NUMERAL_NORMALIZATION[clean_text]

    part_payload: Dict[str, Any] = {"text": text}
    base_temp = None
    if performance_direction:
        from audiobook_factory.performance.tts_adapter import GeminiTTSPerformanceAdapter
        adapter = GeminiTTSPerformanceAdapter()
        adapted = adapter.adapt_direction_to_payload(text, performance_direction, variant_type=variant_type)
        part_payload = adapted["part_payload"]
        base_temp = adapted.get("temperature")
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

    # --- TTS Temperature (Phase 2 Fix) ---
    # Old clamp: max(0.2, min(1.0, ...)) — floor of 0.2 kills expressive TTS performance.
    # Gemini TTS valid range is [0.0, 2.0]; dramatic audiobook range should be [0.70, 1.40].
    # Default spread widened from [0.685, 0.715] to [0.90, 1.10] for dramatic vocal range.
    gen_config = payload["generationConfig"]
    if base_temp is not None:
        jitter = random.uniform(-0.02, 0.02)
        gen_config["temperature"] = round(max(0.70, min(1.40, float(base_temp) + jitter)), 3)
    else:
        gen_config["temperature"] = round(random.uniform(0.90, 1.10), 3)

    data = json.dumps(payload).encode("utf-8")
    cadence = _resolve_cadence_controller()
    pool = _resolve_key_pool()

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

        try:
            api_key = pool.get_key(service="tts")  # Raises AllKeysExhaustedTodayError when all keys reach 10 RPD
        except AllKeysExhaustedTodayError:
            if ENABLE_EMERGENCY_FALLBACK:
                logger.warning(f"  [EMERGENCY FALLBACK] Gemini key pool exhausted. Falling back to local WinRT speech synthesis for: {output_file.name}")
                return _synthesize_local_winrt_fallback(text, output_file, voice=voice)
            raise
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        key_exhausted_or_invalid = False

        # Inner Loop: Network retries on the currently selected key (max 3 attempts)
        for network_attempt in range(3):
            if rate_limiter:
                rate_limiter.acquire()

            t_req_start = time.perf_counter()
            req = urllib.request.Request(
                url,
                data=data,
                headers=get_stealth_sdk_headers(api_key),
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=90.0) as resp:
                    latency_sec = time.perf_counter() - t_req_start
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
                    tmp_file = output_file.with_suffix(f".tmp_{uuid.uuid4().hex[:6]}.wav")
                    try:
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
                        faint_limit = 8.0 if ("whisper" in text.lower() or "whisper" in emotion.lower() or "tender" in emotion.lower() or "intimate" in emotion.lower() or "breathy" in emotion.lower()) else 20.0
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

                        # Atomically promote verified audio to target destination (Windows-resilient)
                        _atomic_replace(tmp_file, output_file)

                        # Record success in persistent key pool
                        pool.record_success(api_key)
                        run_id = os.environ.get("CURRENT_AUDIOBOOK_RUN_ID", "studio_run")
                        try:
                            from audiobook_factory.telemetry import get_telemetry_ledger
                            get_telemetry_ledger().record_api_call(
                                run_id=run_id,
                                service="gemini_tts",
                                endpoint=model,
                                status_code=200,
                                latency_sec=latency_sec,
                                is_rate_limit=False,
                                prompt_tokens=len(text.split()),
                                completion_tokens=int(dur_sec * 50),
                                est_cost_usd=0.0,
                            )
                        except Exception:
                            pass
                        return output_file, dur_sec
                    finally:
                        if tmp_file.exists():
                            try:
                                tmp_file.unlink()
                            except OSError:
                                pass

            except urllib.error.HTTPError as e:
                latency_sec = time.perf_counter() - t_req_start
                try:
                    err = e.read().decode("utf-8", errors="ignore")
                finally:
                    try:
                        e.close()
                    except Exception:
                        pass
                category, wait_sec, reason = classify_gemini_error(e.code, err)

                run_id = os.environ.get("CURRENT_AUDIOBOOK_RUN_ID", "studio_run")
                try:
                    from audiobook_factory.telemetry import get_telemetry_ledger
                    t_led = get_telemetry_ledger()
                    t_led.record_api_call(
                        run_id=run_id,
                        service="gemini_tts",
                        endpoint=model,
                        status_code=e.code,
                        latency_sec=latency_sec,
                        is_rate_limit=(e.code == 429),
                        prompt_tokens=0,
                        completion_tokens=0,
                        est_cost_usd=0.0,
                    )
                    if e.code == 429:
                        t_led.record_incident(
                            run_id=run_id,
                            stage_name="Gemini TTS",
                            incident_type="RATE_LIMIT_429",
                            details={"model": model, "key": f"...{api_key[-6:]}", "category": category, "wait_sec": wait_sec},
                        )
                except Exception:
                    pass

                if category == "DAILY_QUOTA_EXHAUSTED":
                    pool.mark_daily_quota_exhausted(api_key, err)
                    logger.warning(
                        f"  [KEY ROTATION] Key ...{api_key[-6:]} daily quota reached (10 RPD). "
                        f"Parked for today."
                    )
                    cadence.wait_for_key_switch(api_key[-6:], "next_project")
                    key_exhausted_or_invalid = True
                    break

                elif category == "INVALID_KEY":
                    pool.mark_invalid(api_key, err)
                    logger.error(
                        f"  [INVALID KEY] Key ...{api_key[-6:]} is invalid/disabled. Bypassing..."
                    )
                    key_exhausted_or_invalid = True
                    break

                elif category == "RPM_RATE_LIMIT":
                    pool.mark_temporary_backoff(api_key, wait_sec, err)
                    logger.warning(
                        f"  [RPM BURST] Key ...{api_key[-6:]} hit temporary rate limit. "
                        f"Cooling off {wait_sec:.1f}s. Switching key from pool..."
                    )
                    if rate_limiter and hasattr(rate_limiter, "trigger_global_pause"):
                        rate_limiter.trigger_global_pause(wait_sec)
                    key_exhausted_or_invalid = False
                    break

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
    temperature: Optional[float] = None,
) -> Tuple[Path, float]:
    """
    Synthesizes a multi-speaker dialogue batch using Gemini 3.8 Flash TTS
    with multiSpeakerVoiceConfig and per-part speechMetadata.
    """
    if os.environ.get("TTS_PRIMARY_BACKEND", "").lower() == "local_winrt":
        return _synthesize_local_batch_winrt(batch, output_file, voice_map=voice_map)

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

    # Expressive acting temperature for multi-speaker drama (Phase 3 Fix)
    if temperature is not None:
        jitter = random.uniform(-0.02, 0.02)
        batch_temp = round(max(0.70, min(1.40, float(temperature) + jitter)), 3)
    else:
        batch_temp = round(random.uniform(0.90, 1.10), 3)

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
            "temperature": batch_temp
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }

    data = json.dumps(payload).encode("utf-8")
    cadence = _resolve_cadence_controller()
    pool = _resolve_key_pool()

    MAX_KEY_ROTATIONS = 15
    rotation_count = 0

    while True:
        rotation_count += 1
        if rotation_count > MAX_KEY_ROTATIONS:
            raise RuntimeError(
                f"Multi-speaker batch TTS failed after {MAX_KEY_ROTATIONS} key rotations."
            )

        try:
            api_key = pool.get_key(service="tts")
        except AllKeysExhaustedTodayError:
            if ENABLE_EMERGENCY_FALLBACK:
                logger.warning(f"  [EMERGENCY FALLBACK] Gemini key pool exhausted. Falling back to local WinRT synthesis for batch {batch.batch_id}")
                return _synthesize_local_batch_winrt(batch, output_file, voice_map=voice_map)
            raise
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        key_exhausted_or_invalid = False

        for network_attempt in range(3):
            if rate_limiter:
                rate_limiter.acquire()

            t_req_start = time.perf_counter()
            req = urllib.request.Request(
                url,
                data=data,
                headers=get_stealth_sdk_headers(api_key),
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=120.0) as resp:
                    latency_sec = time.perf_counter() - t_req_start
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
                        raise ValueError(f"No audio data found in Gemini response parts: {[p.get('text', '')[:40] for p in cand_parts]}")
                    raw_bytes = base64.b64decode(b64_audio)
                    raw_pcm, sample_rate, frames = extract_clean_pcm_from_gemini_container(raw_bytes)

                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    tmp_file = output_file.with_suffix(f".tmp_{uuid.uuid4().hex[:6]}.wav")
                    try:
                        with wave.open(str(tmp_file), "wb") as wf:
                            wf.setnchannels(1)
                            wf.setsampwidth(2)
                            wf.setframerate(sample_rate)
                            wf.writeframes(raw_pcm)

                        dur_sec = frames / float(sample_rate)
                        total_words = max(sum(len(p["text"].split()) for p in parts), 1)

                        # Mathematical PCM Probe for Audio Defects
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
                        is_silent = (peak_amp == 0 or (total_words >= 3 and rms < 15.0))
                        is_dc_corrupted = (dur_sec >= 2.0 and dc_offset > 1500.0)

                        if is_clipped or is_silent or is_dc_corrupted:
                            defect = "Clipping" if is_clipped else ("Silent/Faint" if is_silent else "DC Offset")
                            if network_attempt < 2:
                                logger.warning(
                                    f"  [SNR GATEKEEPER: {defect}] Batch {batch.batch_id} failed quality check. "
                                    f"Retrying (Attempt {network_attempt+1}/3)..."
                                )
                                time.sleep(2.0)
                                continue
                            else:
                                raise ValueError(
                                    f"SNR Gatekeeper rejected batch audio after 3 attempts ({defect})"
                                )

                        _atomic_replace(tmp_file, output_file)
                        pool.record_success(api_key)
                        run_id = os.environ.get("CURRENT_AUDIOBOOK_RUN_ID", "studio_run")
                        try:
                            from audiobook_factory.telemetry import get_telemetry_ledger
                            get_telemetry_ledger().record_api_call(
                                run_id=run_id,
                                service="gemini_tts_multispeaker",
                                endpoint=model,
                                status_code=200,
                                latency_sec=latency_sec,
                                is_rate_limit=False,
                                prompt_tokens=total_words,
                                completion_tokens=int(dur_sec * 50),
                                est_cost_usd=0.0,
                            )
                        except Exception:
                            pass
                        return output_file, dur_sec
                    finally:
                        if tmp_file.exists():
                            try:
                                tmp_file.unlink()
                            except OSError:
                                pass

            except urllib.error.HTTPError as e:
                latency_sec = time.perf_counter() - t_req_start
                try:
                    err = e.read().decode("utf-8", errors="ignore")
                finally:
                    try:
                        e.close()
                    except Exception:
                        pass
                category, wait_sec, reason = classify_gemini_error(e.code, err)

                run_id = os.environ.get("CURRENT_AUDIOBOOK_RUN_ID", "studio_run")
                try:
                    from audiobook_factory.telemetry import get_telemetry_ledger
                    t_led = get_telemetry_ledger()
                    t_led.record_api_call(
                        run_id=run_id,
                        service="gemini_tts_multispeaker",
                        endpoint=model,
                        status_code=e.code,
                        latency_sec=latency_sec,
                        is_rate_limit=(e.code == 429),
                        prompt_tokens=0,
                        completion_tokens=0,
                        est_cost_usd=0.0,
                    )
                    if e.code == 429:
                        t_led.record_incident(
                            run_id=run_id,
                            stage_name="Gemini TTS Multi-Speaker",
                            incident_type="RATE_LIMIT_429",
                            details={"model": model, "key": f"...{api_key[-6:]}", "category": category, "wait_sec": wait_sec},
                        )
                except Exception:
                    pass

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
                    key_exhausted_or_invalid = False
                    break

                elif category == "TRANSIENT_SERVER_ERROR":
                    pool.mark_temporary_backoff(api_key, wait_sec, err)
                    time.sleep(wait_sec)
                    continue

                else:
                    time.sleep(5.0)
                    continue

            except (urllib.error.URLError, TimeoutError, ConnectionResetError, OSError) as net_err:
                time.sleep(6.0)
                continue

        if not key_exhausted_or_invalid:
            pool.mark_temporary_backoff(api_key, 25.0, "3 consecutive transient errors in multi-speaker batch")
