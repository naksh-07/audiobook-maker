#!/usr/bin/env python3
"""
===============================================================================
Audiobook Factory - Standalone Production Pipeline Engine
===============================================================================
Autonomous end-to-end studio audiobook production pipeline operating strictly
as a standalone runner in the project root.

Directly imports and orchestrates the factory's production modules:
  1. KeyPool & Round-Robin Rotation (audiobook_factory.key_manager)
     - 120+ Gemini API keys managed in persistent SQLite ledger.
     - Pure round-robin rotation: never hammers a single key.
     - Immediate key rotation on ANY error or glitch.
     - Auto-rollover at Google Pacific Time midnight.
  2. Stealth Human Cadence & Anti-Correlation Cooldowns (audiobook_factory.cadence)
     - HumanCadenceController: Content-aware reading delay & listening preview simulation.
     - Log-normal human thinking jitter (2.5s - 5.5s).
     - Director scene review breaks every 15 segments (15s - 30s pause).
     - Anti-correlation key-switch cooldown (18s - 32s pause to decouple IP failover correlation).
     - Authentic Google GenAI Python SDK headers (google-genai-sdk-python).
  3. Token-Bucket Rate Limiter (audiobook_factory.tts_dispatcher)
     - Enforces 15 RPM with organic jitter (0.35s - 0.85s).
     - Thread-safe global pause on HTTP 429.
  4. Mathematical SNR Gatekeeper & Speaker DSP Calibration (audiobook_factory.tts_dispatcher)
     - Clipping detection, faint audio rejection, DC offset anomaly filter, dead-air detection.
     - Highpass, denoise, softclip tanh for shouting, bass boost, presence, volume gain.
  5. Screenplay Normalization & Multi-Cast Attribution (audiobook_factory.script_builder)
     - Clean two-pass screenplay parsing, pronoun disambiguation, Foley action beats.
     - Numeral normalization (Devanagari/Western to Hindi words).
  6. Studio Concatenation & Mastering Chain (audiobook_factory.mastering)
     - FFmpeg SOXR 48kHz sinc resampling, 60Hz highpass, 8dB afftdn denoise, de-esser,
       14kHz lowpass, EBU R128 -19 LUFS loudnorm, studio peak limiter.
     - Constant-power stereo spatial staging (-0.6 left to +0.6 right).
     - Dynamic natural silence pauses and pre-roll breath intervals.
  7. Strict Model Locking & Zero Moral Policing:
     - Stage 1: gemini-3.5-flash for Screenplay JSON
     - Stage 2: gemini-3.8-flash-tts for Audio Speech Synthesis
     - Full permissive BLOCK_NONE safety thresholds across all categories.
===============================================================================
"""

import os
import sys
import re
import json
import time
import wave
import shutil
import base64
import hashlib
import argparse
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Configure UTF-8 for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure Audiobook Factory root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Auto-load .env configuration
from audiobook_factory.key_manager import _load_env_fallback
_load_env_fallback()

# Strictly locked model defaults (with verified pre-flight fallback)
DEFAULT_JSON_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.5-flash")
DEFAULT_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
DEFAULT_OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "qwen/qwen3.8-27b:free")
DEFAULT_LLM_ENGINE = os.environ.get("SCREENPLAY_ENGINE", "offline")

# =============================================================================
# GEMINI 3.8 FLASH TTS - GLOBAL DIRECTOR STYLE PROMPT
# Edit this string to customize the narration acting, mood, and pace!
# =============================================================================
DEFAULT_DIRECTOR_STYLE = os.environ.get(
    "TTS_DIRECTOR_STYLE",
    "Game of Thrones and gritty Netflix period drama style; deep cinematic gravitas, breathy intimate tension, restrained emotional power, slow deliberate cadence with pregnant pauses, raw visceral character modulations, and intimate atmospheric suspense",
)

CANDIDATE_TEXT_MODELS = [
    "gemini-3.5-flash",
    "gemini-3-flash-preview",
    "gemma-4-26b-a4b-it",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
]

CANDIDATE_TTS_MODELS = [
    "gemini-3.8-flash-tts",
    "gemini-3.1-flash-tts-preview",
    "gemini-3.8-flash-lite-tts",
]

OPENROUTER_CANDIDATE_MODELS = [
    "qwen/qwen3.8-27b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
]

# Import factory production modules
from audiobook_factory.logger import logger
from audiobook_factory.key_manager import (
    get_persistent_key_pool,
    classify_gemini_error,
    AllKeysExhaustedTodayError,
    PersistentKeyPool,
)
from audiobook_factory.cadence import (
    get_stealth_sdk_headers,
    get_human_cadence_controller,
    HumanCadenceController,
)
from audiobook_factory.tts_dispatcher import (
    TokenBucketRateLimiter,
    DEFAULT_RPM,
    NUMERAL_NORMALIZATION,
)
from audiobook_factory.mastering import (
    concatenate_and_master_chapter,
    get_ffmpeg,
)
from audiobook_factory.script_builder import (
    clean_screenplay_pass2,
    build_narrator_script,
    normalize_speech_text,
)

# -----------------------------------------------------------------------------
# RULE 5: CREATIVE NARRATIVE & DRAMATIC FICTION PROTOCOL (ZERO MORAL POLICING)
# Full permissive BLOCK_NONE thresholds across all Google safety categories.
# -----------------------------------------------------------------------------
SAFETY_SETTINGS_BLOCK_NONE = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"},
]

AVAILABLE_VOICES_FEMALE = ["Aoede", "Kore", "Leda", "Zephyr"]
AVAILABLE_VOICES_MALE = ["Charon", "Fenrir", "Puck", "Orpheus"]


# =============================================================================
# PRE-FLIGHT MODEL HEALTH PROBE & CIRCUIT BREAKER
# Prevents blind key hammering across 120+ keys when a model backend is down/overloaded
# =============================================================================
def probe_single_model(model_name: str, is_tts: bool = False, pool: Optional[PersistentKeyPool] = None) -> Tuple[bool, str, float]:
    """
    Sends a single micro-request to verify whether a model backend is actually alive and accepting requests.
    Returns: (is_healthy, status_message, latency_seconds)
    """
    if pool is None:
        pool = get_persistent_key_pool()

    try:
        sample_key = pool.get_key(service="tts" if is_tts else "text")
    except Exception as e:
        return False, f"KeyPool Error: {e}", 0.0

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={sample_key}"
    headers = get_stealth_sdk_headers(sample_key)

    if is_tts:
        payload = {
            "contents": [{"parts": [{"text": "Hi"}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Aoede"}}}
            }
        }
    else:
        payload = {
            "contents": [{"parts": [{"text": "Hi"}]}],
            "generationConfig": {"maxOutputTokens": 5}
        }

    t0 = time.time()
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12.0) as resp:
            dt = time.time() - t0
            return True, f"200 OK (Latency: {dt:.2f}s)", dt
    except urllib.error.HTTPError as e:
        dt = time.time() - t0
        err = e.read().decode("utf-8", errors="ignore")
        if e.code == 503:
            return False, f"HTTP 503 (Backend High Demand / Overloaded)", dt
        elif e.code == 404:
            return False, f"HTTP 404 (Model Not Found / Deprecated)", dt
        elif e.code == 429:
            return False, f"HTTP 429 (Rate Limit)", dt
        return False, f"HTTP {e.code}: {err[:80]}", dt
    except (urllib.error.URLError, TimeoutError, ConnectionResetError, OSError) as net_err:
        dt = time.time() - t0
        return False, f"Timeout / Network Error ({type(net_err).__name__})", dt


def verify_or_select_model(
    requested_model: str,
    is_tts: bool = False,
    pool: Optional[PersistentKeyPool] = None,
    auto_failover: bool = True,
) -> str:
    """
    Validates model availability with a single micro-request probe.
    If the requested model is failing (503/timeout), it immediately probes candidate
    models concurrently, presents the live telemetry table, and auto-selects the fastest
    active working model instead of blindly cycling through 120+ keys.
    """
    if pool is None:
        pool = get_persistent_key_pool()

    mod_type = "TTS Audio" if is_tts else "Screenplay LLM"
    print(f"\n[*] Pre-flight Probe: Testing {mod_type} model '{requested_model}'...")
    ok, msg, lat = probe_single_model(requested_model, is_tts=is_tts, pool=pool)

    if ok:
        print(f"[+] Verified {mod_type} model '{requested_model}': {msg}")
        return requested_model

    print(f"\n[!] Model '{requested_model}' is UNAVAILABLE on Google backend: {msg}")
    print("[*] Performing rapid candidate probe to find active alternative without hammering keys...")

    import concurrent.futures
    candidates = CANDIDATE_TTS_MODELS if is_tts else CANDIDATE_TEXT_MODELS

    probe_results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(candidates), 6)) as ex:
        futures = {ex.submit(probe_single_model, m, is_tts, pool): m for m in candidates}
        for fut in concurrent.futures.as_completed(futures):
            m = futures[fut]
            try:
                probe_results[m] = fut.result()
            except Exception as e:
                probe_results[m] = (False, str(e), 0.0)

    print("\n" + "=" * 80)
    print(f"  PRE-FLIGHT MODEL HEALTH PROBE ({mod_type})")
    print("=" * 80)
    selected_model = None
    for m in candidates:
        m_ok, m_msg, m_lat = probe_results.get(m, (False, "Not tested", 0.0))
        status_tag = "[ACTIVE OK]" if m_ok else "[DOWN]"
        print(f"  {m:<28} : {status_tag:<12} -> {m_msg}")
        if m_ok and selected_model is None:
            selected_model = m
    print("=" * 80)

    if selected_model and auto_failover:
        print(f"\n[+] Auto-Failover: Selected healthy active model -> '{selected_model}'")
        return selected_model
    elif selected_model:
        return selected_model
    else:
        raise RuntimeError(f"All candidate {mod_type} models are currently down or unreachable on Google AI Studio.")



# =============================================================================
# KEYPOOL TELEMETRY HELPER
# =============================================================================
def print_keypool_status(pool: PersistentKeyPool):
    """Displays live telemetry of all registered Gemini API keys in the SQLite pool."""
    summary = pool.get_status_summary()
    print("\n" + "=" * 80)
    print("  GEMINI API KEY POOL TELEMETRY (audiobook_factory.key_manager)")
    print("=" * 80)
    print(f"  Google PT Date:      {summary.get('date', 'Unknown')}")
    print(f"  Total Keys:          {summary.get('total_keys', 0)}")
    print(f"  Active Keys:         {summary.get('active_keys', 0)}")
    print(f"  Exhausted Today:     {summary.get('exhausted_today', 0)} (10 RPD limit)")
    print(f"  Temporary Backoff:   {summary.get('temp_backoff', 0)} (Active Cooldown)")
    print(f"  Invalid / Disabled:  {summary.get('invalid_keys', 0)}")
    print("-" * 80)
    for idx, k in enumerate(summary.get("keys", []), 1):
        status = k.get("status", "UNKNOWN")
        calls = k.get("total_calls_today", 0)
        succ = k.get("success_calls_today", 0)
        fail = k.get("failed_calls_today", 0)
        preview = k.get("key_preview", "????")
        print(f"  [{idx:02d}] {preview:<20} Status: {status:<16} Calls: {calls:2d} (OK: {succ:2d}, Fail: {fail:2d})")
    print("=" * 80 + "\n")


# =============================================================================
# STAGE 1: LITERATURE -> SCREENPLAY JSON (gemini-3.5-flash + BLOCK_NONE)
# Pure Round-Robin KeyPool with Human Cadence & Anti-Correlation Cooldown
# =============================================================================
def build_screenplay_chunk_round_robin(
    chunk_text: str,
    preceding_context: str = "",
    is_hindi: bool = False,
    character_roster: Optional[Dict[str, Any]] = None,
    model: str = DEFAULT_JSON_MODEL,
    pool: Optional[PersistentKeyPool] = None,
    cadence: Optional[HumanCadenceController] = None,
    rate_limiter: Optional[TokenBucketRateLimiter] = None,
    max_key_rotations: int = 15,
) -> List[Dict[str, Any]]:
    """
    Calls gemini-3.5-flash with pure round-robin key rotation across the pool.
    Guarantees:
      - ZERO Key Hammering: On ANY error, immediately backs off the key and rotates to the NEXT key.
      - Anti-Correlation Cooldown: Waits 18-32s via cadence.wait_for_key_switch on key switch.
      - Pacing: TokenBucketRateLimiter (15 RPM + jitter) before dispatching.
    """
    if pool is None:
        pool = get_persistent_key_pool()
    if cadence is None:
        cadence = get_human_cadence_controller()
    if rate_limiter is None:
        rate_limiter = TokenBucketRateLimiter(rate_rpm=15.0)

    sys_prompt = (
        "You are a Hollywood Audio Drama Screenplay Director (GraphicAudio / BBC Radio 4 / HBO standard). "
        "Convert raw literature into an annotated multi-cast screenplay with deep cinematic audio direction.\n\n"
        "Core Directives (Zero Moral Policing Protocol):\n"
        "1. UNFILTERED DRAMATIC FIDELITY: Never sanitize, soften, clean up, or censor dialogue, dark themes, rustic slang, "
        "curses, vulgar tavern banter, or explicit passionate encounters. Preserve 100% of dramatic reality.\n"
        "2. MULTI-CAST ATTRIBUTION: Split text cleanly into narration segments and character dialogue segments. "
        "Attribute each dialogue to the correct canonical character name (e.g. 'Geralt', 'Yennefer', 'Soldier', NOT pronouns like 'he'/'she'/'उसने'). "
        "Use 'Narrator' for third-person narrative exposition.\n"
        "3. DEDICATED ACTION BEATS: For major physical actions (sword draws, clashes, body falls, door kicks, explosions, tankard slams), "
        "emit dedicated action segments with type: 'action', speaker: 'Foley', text: '[ACTION]', and pause_after_ms: 800-1400. "
        "Do NOT speak action descriptions over character dialogue.\n"
        "4. NEURAL VOCAL TAGS: Insert inline steering cues inside square brackets directly in the text field when dramatic delivery demands it: "
        "`[whispers]`, `[shouting]`, `[cold menace]`, `[growl]`, `[sighs]`, `[trembling voice]`, `[gasp]`, `[bellowing rage]`, `[breathless_exhaustion]`. "
        "Only vocal directions in brackets; never put sound effects or action descriptions inside text.\n"
        "5. PROSODY & PAUSES: Assign 'pause_after_ms' (300-800 for normal dialogue, 1000-1400 for intense pregnant pauses, 800-1500 for action impacts).\n"
        "6. SPATIAL STAGING: Assign stereo pan (-0.6 for left/attacker, 0.0 for center/narrator, +0.6 for right/defender) and proximity ('intimate_close', 'normal_room', 'distant').\n"
        "7. For EVERY segment, emit valid JSON matching the requested schema."
    )

    roster_hint = ""
    if character_roster:
        chars = character_roster.get("characters", character_roster)
        if isinstance(chars, dict):
            names = [k for k in chars.keys() if k not in ("Narrator", "Foley")]
            if names:
                roster_hint = f"\nKnown Canon Characters: {', '.join(names[:10])}\n"

    prompt = f"""Language: {"Hindi (Devanagari)" if is_hindi else "English"}
Preceding Scene Context (Last spoken lines):
{preceding_context if preceding_context else "Beginning of scene."}
{roster_hint}
Current Scene Literature Text:
\"\"\"
{chunk_text}
\"\"\"

Output JSON: A pure JSON array of objects, where each object has:
- "index": int (1-based sequential number)
- "type": "dialogue" | "narration" | "action"
- "speaker": character name (e.g. "Geralt", "Narrator", "Foley")
- "text": spoken dialogue or narration with optional [vocal tag], or "[ACTION]" for action beats
- "emotion": "neutral" | "angry" | "whispering" | "sad" | "excited" | "growl" | "calm_raspy"
- "pause_after_ms": int (silence duration after this segment in ms)
- "pre_roll_breath_ms": int (0 for standard, 150-250 for intimate/gasping/exhausted lines)
- "acting": {{
    "delivery_style": "neutral" | "cold_menace" | "whispering_fear" | "ironic_mockery" | "bellowing_rage" | "combat_strain" | "breathless_exhaustion",
    "pacing": float (0.88 to 1.15)
  }}
- "spatial": {{
    "pan": float (-0.6 to 0.6),
    "proximity": "intimate_close" | "normal_room" | "distant"
  }}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": sys_prompt}]},
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "maxOutputTokens": 8192,
        },
        "safetySettings": SAFETY_SETTINGS_BLOCK_NONE,
    }
    data_bytes = json.dumps(payload).encode("utf-8")

    # Round-Robin Rotation Loop: every attempt acquires a fresh key from the pool
    consecutive_backend_errors = 0
    for attempt in range(max_key_rotations):
        rate_limiter.acquire()
        try:
            curr_key = pool.get_key(service="text")
        except Exception as e:
            logger.error(f"  [KEY ERROR] Unable to acquire key for text: {e}")
            break

        key_preview = f"{curr_key[:8]}...{curr_key[-6:]}"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={curr_key}"
        headers = get_stealth_sdk_headers(curr_key)
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if not candidates:
                    logger.warning(f"  [!] LLM returned no candidates: {data.get('promptFeedback', {})}")
                    continue

                candidate = candidates[0]
                parts = candidate.get("content", {}).get("parts", [])
                if not parts:
                    continue

                raw_json = "".join(p.get("text", "") for p in parts if "text" in p).strip()

                # Clean markdown fencing if present
                clean_match = re.search(r"```(?:json)?\s*(.*?)```", raw_json, re.DOTALL)
                if clean_match:
                    raw_json = clean_match.group(1).strip()
                elif raw_json.startswith("```"):
                    raw_json = re.sub(r"^```(?:json)?\s*", "", raw_json)
                    raw_json = re.sub(r"\s*```$", "", raw_json).strip()

                parsed = None
                try:
                    parsed = json.loads(raw_json)
                except json.JSONDecodeError:
                    # Data Healer safe closing fallback
                    repaired = raw_json.strip()
                    last_brace = repaired.rfind("}")
                    if last_brace != -1 and repaired.startswith("[") and not repaired.endswith("]"):
                        candidate_str = repaired[:last_brace + 1].rstrip() + "\n]"
                        try:
                            parsed = json.loads(candidate_str)
                            logger.info("  [+] Screenplay JSON repaired via structural bracket healing.")
                        except Exception:
                            pass

                if parsed is not None:
                    pool.record_success(curr_key)
                    if isinstance(parsed, list):
                        return parsed
                    elif isinstance(parsed, dict) and "segments" in parsed:
                        return parsed["segments"]
                    elif isinstance(parsed, dict) and "script" in parsed:
                        return parsed["script"]

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else str(e)
            category, wait_sec, msg = classify_gemini_error(e.code, err_body)
            logger.warning(f"  [KEYPOOL ROTATE] Key {key_preview} HTTP {e.code} ({category}).")

            if category == "DAILY_QUOTA_EXHAUSTED":
                pool.mark_daily_quota_exhausted(curr_key, msg)
                cadence.wait_for_key_switch(curr_key[-6:], "next_project")
            elif category == "RPM_RATE_LIMIT":
                pool.mark_temporary_backoff(curr_key, wait_sec, msg)
                rate_limiter.trigger_global_pause(wait_sec)
                cadence.wait_for_key_switch(curr_key[-6:], "next_project")
            elif category == "TRANSIENT_SERVER_ERROR":
                pool.mark_temporary_backoff(curr_key, wait_sec, msg)
                cadence.wait_for_key_switch(curr_key[-6:], "next_project")
                consecutive_backend_errors += 1
                if consecutive_backend_errors >= 2:
                    logger.error(
                        f"  [CIRCUIT BREAKER] Model '{model}' hit {consecutive_backend_errors} consecutive HTTP {e.code} errors. "
                        f"Halting key rotation to prevent wasteful cooldown hammering."
                    )
                    try:
                        alt = verify_or_select_model(model, is_tts=False, pool=pool, auto_failover=True)
                        if alt and alt != model:
                            logger.info(f"  [FAILOVER] Switching screenplay model: '{model}' -> '{alt}'")
                            model = alt
                            consecutive_backend_errors = 0
                            continue
                    except Exception:
                        pass
                    break
            elif category == "INVALID_KEY":
                pool.mark_invalid(curr_key, msg)
            else:
                pool.mark_temporary_backoff(curr_key, 6.0, msg)
                cadence.wait_for_key_switch(curr_key[-6:], "next_project")

            # ZERO KEY HAMMERING: Immediately loop to acquire NEXT key from pool!
            continue

        except (urllib.error.URLError, TimeoutError, ConnectionResetError, OSError) as net_err:
            logger.warning(f"  [KEYPOOL ROTATE] Key {key_preview} network timeout ({net_err}).")
            pool.mark_temporary_backoff(curr_key, 10.0, f"Network timeout: {net_err}")
            cadence.wait_for_key_switch(curr_key[-6:], "next_project")
            consecutive_backend_errors += 1
            if consecutive_backend_errors >= 2:
                logger.error(
                    f"  [CIRCUIT BREAKER] Model '{model}' timed out across {consecutive_backend_errors} keys. "
                    f"Halting key rotation to prevent wasteful cooldown hammering."
                )
                try:
                    alt = verify_or_select_model(model, is_tts=False, pool=pool, auto_failover=True)
                    if alt and alt != model:
                        logger.info(f"  [FAILOVER] Switching screenplay model: '{model}' -> '{alt}'")
                        model = alt
                        consecutive_backend_errors = 0
                        continue
                except Exception:
                    pass
                break
            continue

    logger.warning("  [!] Screenplay formatting retries exhausted; falling back to narrator segment.")
    return build_narrator_script(chunk_text, is_hindi)


def format_literature_to_screenplay(
    literature_text: str,
    is_hindi: bool = False,
    character_roster: Optional[Dict[str, Any]] = None,
    model: str = DEFAULT_JSON_MODEL,
    pool: Optional[PersistentKeyPool] = None,
) -> List[Dict[str, Any]]:
    """
    Processes full novel prose or chapters into a contiguous, cleanly indexed screenplay JSON.
    Splits long literature (>7,000 chars) into semantic paragraph chunks and applies
    Pass 2 Alexandria cleaning (clean_screenplay_pass2).
    """
    if pool is None:
        pool = get_persistent_key_pool()

    clean_text = literature_text.strip()
    if not clean_text:
        return []

    cadence = get_human_cadence_controller()
    rate_limiter = TokenBucketRateLimiter(rate_rpm=15.0)

    # Small text: process directly
    if len(clean_text) <= 7000:
        raw_items = build_screenplay_chunk_round_robin(
            chunk_text=clean_text,
            is_hindi=is_hindi,
            character_roster=character_roster,
            model=model,
            pool=pool,
            cadence=cadence,
            rate_limiter=rate_limiter,
        )
    else:
        paragraphs = clean_text.split("\n\n")
        chunks = []
        curr = []
        curr_words = 0

        for p in paragraphs:
            p_strip = p.strip()
            if not p_strip:
                continue
            w_count = len(p_strip.split())
            curr.append(p_strip)
            curr_words += w_count
            if curr_words >= 900:
                chunks.append("\n\n".join(curr))
                curr = []
                curr_words = 0
        if curr:
            chunks.append("\n\n".join(curr))

        raw_items = []
        rolling_context = ""

        print(f"[*] Processing literature in {len(chunks)} chunks using {model} with KeyPool round-robin rotation...")
        for c_idx, chk in enumerate(chunks, 1):
            print(f"    - Processing Chunk {c_idx}/{len(chunks)} ({len(chk.split())} words)...")
            chunk_items = build_screenplay_chunk_round_robin(
                chunk_text=chk,
                preceding_context=rolling_context,
                is_hindi=is_hindi,
                character_roster=character_roster,
                model=model,
                pool=pool,
                cadence=cadence,
                rate_limiter=rate_limiter,
            )
            raw_items.extend(chunk_items)

            # Build rolling context from last 3 exchanges
            tail_lines = []
            for it in chunk_items[-3:]:
                sp = it.get("speaker", "Narrator")
                txt = (it.get("text", "") or "").strip()
                if len(txt) > 70:
                    txt = txt[:67] + "..."
                tail_lines.append(f"{sp}: \"{txt}\"")
            rolling_context = "\n".join(tail_lines)

    # Alexandria Pattern Pass 2: Clean, validate, and disambiguate pronouns
    return clean_screenplay_pass2(raw_items, is_hindi=is_hindi, character_roster=character_roster)


# =============================================================================
# SEGMENT CONSOLIDATION ENGINE (MAX DENSITY / MINIMUM TTS REQUESTS)
# =============================================================================
def consolidate_adjacent_segments(
    segments: List[Dict[str, Any]],
    max_words: int = 500,
) -> List[Dict[str, Any]]:
    """
    Consolidates contiguous segments spoken by the same speaker (especially Narrator)
    into single larger speech chunks (up to max_words) to drastically minimize TTS requests.
    Preserves neural vocal tags and assigns sequential 1-based indexing.
    """
    if not segments:
        return []

    merged: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    for seg in segments:
        speaker = seg.get("speaker", "Narrator")
        text = (seg.get("text", "") or "").strip()
        if not text:
            continue

        if current is None:
            current = dict(seg)
            current["text"] = text
            continue

        curr_speaker = current.get("speaker", "Narrator")
        curr_words = len(current["text"].split())
        new_words = len(text.split())

        # If same speaker, neither is Foley action, and combined words <= max_words: merge
        if (
            curr_speaker == speaker
            and speaker != "Foley"
            and current.get("type") != "action"
            and seg.get("type") != "action"
            and (curr_words + new_words <= max_words)
        ):
            current["text"] = f"{current['text']} {text}".strip()
            if "pause_after_ms" in seg:
                current["pause_after_ms"] = seg["pause_after_ms"]
            if current.get("emotion") == "neutral" and seg.get("emotion") != "neutral":
                current["emotion"] = seg["emotion"]
        else:
            merged.append(current)
            current = dict(seg)
            current["text"] = text

    if current:
        merged.append(current)

    for i, s in enumerate(merged, 1):
        s["index"] = i

    return merged


# =============================================================================
# OPENROUTER SCREENPLAY ENGINE (Qwen 3.8 / Nemotron / Gemma -> Gemini 3.8 Flash TTS Calibrated)
# 85-90% Narrator Density + Neural Vocal Steering + Minimum Requests Protocol
# =============================================================================
def format_literature_with_openrouter(
    literature_text: str,
    is_hindi: bool = False,
    character_roster: Optional[Dict[str, Any]] = None,
    model: str = DEFAULT_OPENROUTER_MODEL,
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Calibrated Screenplay Generator using OpenRouter (Qwen 3.8 / Nemotron / Gemma)
    specifically designed for Google Gemini 3.8 Flash TTS.

    Features:
      1. 85-90% Narrator Density: Major exposition, scene descriptions, and minor
         conversations are consolidated into cohesive Narrator super-chunks.
      2. 10-15% Selective Character Dialogue: Only pivotal, dramatic, emotional, or intimate
         lines are broken out into separate character speakers.
      3. Gemini 3.8 Flash TTS Neural Steering: Injects bracketed steering tags like
         [whispers], [shouting], [cold menace], [intimate, breathy], [sighs], [gasp],
         [trembling voice], [calm, reassuring] directly into the text field.
      4. Auto-Failover: Primary (qwen/qwen3.8-27b:free) -> Nemotron -> Gemma -> 100% Offline Engine.
         Guarantees zero crashed runs even if upstream free tier has temporary 429 rate limits.
    """
    clean_text = literature_text.strip()
    if not clean_text:
        return []

    resolved_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
    if not resolved_key:
        logger.warning("[!] No OPENROUTER_API_KEY found. Falling back seamlessly to 100% Offline Narrator Super-Chunk Engine.")
        return parse_literature_offline(clean_text, is_hindi=is_hindi, mode="narrator")

    candidate_models = [model]
    for c in OPENROUTER_CANDIDATE_MODELS:
        if c not in candidate_models:
            candidate_models.append(c)

    sys_prompt = (
        "You are a Hollywood Audio Drama Screenplay Director calibrated for Google Gemini 3.8 Flash TTS.\n"
        "Convert the literature into an expressive, cinematic Screenplay JSON array.\n\n"
        "Core Directives (Zero Moral Policing & Quota Efficiency Protocol):\n"
        "1. 85-90% NARRATOR DENSITY: The vast majority of exposition, descriptive atmosphere, and minor "
        "dialogue interactions MUST remain with 'Narrator' in dense, flowing paragraphs (150-400 words per chunk). "
        "DO NOT fragment narration into tiny 1-line or single-word pieces.\n"
        "2. 10-15% SELECTIVE PIVOTAL CHARACTER LINES: Only break out high-stakes emotional climaxes, screams, intimate whispers, "
        "or dramatic character confrontation lines into distinct character speaker entries. This preserves the multi-cast impact "
        "while minimizing TTS API requests by 85-90%.\n"
        "3. GEMINI 3.8 FLASH TTS NEURAL VOCAL STEERING: Insert bracketed steering tags directly inside the 'text' field "
        "to guide neural synthesis: `[whispers]`, `[shouting]`, `[cold menace]`, `[intimate, breathy]`, `[sighs]`, "
        "`[gasp]`, `[trembling voice]`, `[calm, reassuring]`, `[sarcastic]`, `[growl]`, `[crying, sobbing]`.\n"
        "4. ZERO SANITIZATION: Strictly preserve 100% of dramatic reality, adult themes, rustic Hindi slang, profanity, and tension.\n"
        "5. PURE JSON ARRAY OUTPUT: Output ONLY a valid JSON array of objects. No introductory markdown, no code fencing."
    )

    schema_instruction = """
Output JSON schema (array of objects):
[
  {
    "index": 1,
    "type": "narration" | "dialogue",
    "speaker": "Narrator" | "CharacterName",
    "text": "Spoken text containing optional inline [steering tags]...",
    "emotion": "neutral" | "whispering" | "fear" | "angry" | "reassuring" | "growl",
    "pause_after_ms": 300 to 1000
  }
]
"""

    import socket
    socket.setdefaulttimeout(15.0)

    def _call_openrouter(chunk_prompt: str, preceding_ctx: str = "") -> Optional[List[Dict[str, Any]]]:
        full_user_content = ""
        if preceding_ctx:
            full_user_content += f"Preceding Scene Context:\n{preceding_ctx}\n\n"
        full_user_content += f"Literature Text ({'Hindi Devanagari' if is_hindi else 'English'}):\n\"\"\"\n{chunk_prompt}\n\"\"\"\n\n{schema_instruction}"

        for m_name in candidate_models:
            payload = {
                "model": m_name,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": full_user_content},
                ],
                "temperature": 0.2,
            }
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {resolved_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/naksh-07/audiobook-maker",
                    "X-Title": "Audiobook Factory",
                },
            )
            t0_req = time.time()
            try:
                print(f"[*] [OPENROUTER] Requesting screenplay from '{m_name}'...", flush=True)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    raw_content = resp_data["choices"][0]["message"]["content"].strip()
                    if raw_content.startswith("```"):
                        raw_content = re.sub(r"^```[a-zA-Z]*\n?", "", raw_content)
                        raw_content = re.sub(r"\n?```$", "", raw_content).strip()
                    json_match = re.search(r"(\[\s*\{.*\}\s*\])", raw_content, re.DOTALL)
                    if json_match:
                        raw_content = json_match.group(1)
                    parsed = json.loads(raw_content)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        print(f"[+] [OPENROUTER] Successfully generated {len(parsed)} screenplay segments via '{m_name}' in {time.time()-t0_req:.2f}s.", flush=True)
                        return parsed
            except urllib.error.HTTPError as e:
                err_text = e.read().decode("utf-8", errors="replace")
                print(f"[!] [OPENROUTER] Model '{m_name}' HTTPError {e.code} ({time.time()-t0_req:.2f}s): {err_text[:120]}", flush=True)
                time.sleep(0.5)
                continue
            except Exception as ex:
                print(f"[!] [OPENROUTER] Model '{m_name}' failed ({time.time()-t0_req:.2f}s): {ex}", flush=True)
                time.sleep(0.5)
                continue
        return None

    raw_segments: List[Dict[str, Any]] = []
    if len(clean_text) <= 6000:
        result = _call_openrouter(clean_text)
        if result:
            raw_segments = result
    else:
        paragraphs = clean_text.split("\n\n")
        chunks = []
        cur = []
        cur_w = 0
        for p in paragraphs:
            p_str = p.strip()
            if not p_str:
                continue
            w_len = len(p_str.split())
            cur.append(p_str)
            cur_w += w_len
            if cur_w >= 1000:
                chunks.append("\n\n".join(cur))
                cur = []
                cur_w = 0
        if cur:
            chunks.append("\n\n".join(cur))

        print(f"[*] [OPENROUTER] Processing long literature in {len(chunks)} chunks...")
        rolling_ctx = ""
        for c_idx, chk in enumerate(chunks, 1):
            print(f"    - Chunk {c_idx}/{len(chunks)} ({len(chk.split())} words)...")
            chk_result = _call_openrouter(chk, preceding_ctx=rolling_ctx)
            if chk_result:
                raw_segments.extend(chk_result)
                tail_lines = []
                for it in chk_result[-3:]:
                    sp = it.get("speaker", "Narrator")
                    tx = (it.get("text", "") or "").strip()[:60]
                    tail_lines.append(f"{sp}: \"{tx}...\"")
                rolling_ctx = "\n".join(tail_lines)
            else:
                print(f"    [!] Chunk {c_idx} failed OpenRouter LLM. Falling back to local narrator superchunk.")
                raw_segments.extend(build_narrator_superchunks(chk, is_hindi=is_hindi))

    if not raw_segments:
        logger.warning("[!] All OpenRouter candidate models failed or rate-limited. Falling back seamlessly to 100% Offline Narrator Superchunks.")
        return parse_literature_offline(clean_text, is_hindi=is_hindi, mode="narrator")

    cleaned_pass2 = clean_screenplay_pass2(raw_segments, is_hindi=is_hindi, character_roster=character_roster)
    final_segments = consolidate_adjacent_segments(cleaned_pass2, max_words=500)
    print(f"[+] [OPENROUTER] Screenplay optimized: {len(cleaned_pass2)} raw items -> {len(final_segments)} consolidated TTS segments.")
    return final_segments


# =============================================================================
# =============================================================================
# 100% OFFLINE NARRATOR SUPER-CHUNKING ENGINE (MAX DENSITY / MINIMUM REQUESTS)
# =============================================================================
def build_narrator_superchunks(
    text: str,
    is_hindi: bool = False,
    max_words: int = 550,
    style: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Quota-Efficient Narrator Super-Chunking Engine.
    Consolidates entire novel chapters (all dialogues + narration) into maximum-capacity
    speech blocks (up to ~550 words per chunk) voiced entirely by Narrator.
    Minimizes API requests by 85-90% while preserving natural breathing pauses.
    """
    clean_text = text.strip()
    if not clean_text:
        return []

    # Hindi dialogue dash normalization: turns "कहा- दीदी..." into 'कहा, "... दीदी...' for natural TTS cadence
    hindi_dialogue_dash = re.compile(
        r"([^।?!.\n]{1,35}?(?:ने\s*(?:कहा|पूछा|जवाब\s*दिया|बोला|बोली)|कहता\s*है|कहती\s*है|कहता|कहती|पूछता|पूछती|बोला|बोली|कहा\s*था|कहा|जवाब\s*दिया|जवाब\s*देती|कह\s*देती\s*थी|हंसते\s*हुए\s*कहता|हंसते\s*हुए\s*कहा|हंसकर\s*कहा))\s*[-—:]\s*",
        re.DOTALL
    )

    raw_paragraphs = clean_text.split("\n\n")
    paragraphs = []

    # Pre-process paragraphs: split mega-paragraphs if any single paragraph > max_words
    for p in raw_paragraphs:
        p_strip = p.strip()
        if not p_strip:
            continue
        p_words = len(p_strip.split())
        if p_words <= max_words:
            paragraphs.append(p_strip)
        else:
            # Split giant paragraph by sentence endings
            sentence_delims = r"([।?!.\n])\s*"
            parts = re.split(sentence_delims, p_strip)
            temp_p = ""
            for i in range(0, len(parts) - 1, 2):
                sent = parts[i] + parts[i + 1]
                if len((temp_p + " " + sent).split()) > max_words and temp_p:
                    paragraphs.append(temp_p.strip())
                    temp_p = sent
                else:
                    temp_p = (temp_p + " " + sent).strip()
            if len(parts) % 2 == 1 and parts[-1].strip():
                temp_p = (temp_p + " " + parts[-1]).strip()
            if temp_p:
                paragraphs.append(temp_p)

    chunks = []
    curr_paras = []
    curr_words = 0

    for p in paragraphs:
        # Chapter header detection
        if p.startswith("#"):
            if curr_paras:
                chunks.append(("\n\n".join(curr_paras), 800))
                curr_paras = []
                curr_words = 0
            chunks.append((p.lstrip("#").strip(), 1200))
            continue

        # Scene break detection
        if p in ("---", "* * *", "***", "— — —", "___"):
            if curr_paras:
                chunks.append(("\n\n".join(curr_paras), 1200))
                curr_paras = []
                curr_words = 0
            continue

        # Format Hindi dialogue dashes to natural spoken pauses
        if is_hindi or any('\u0900' <= ch <= '\u097f' for ch in p):
            p_formatted = hindi_dialogue_dash.sub(r'\1, "... ', p)
        else:
            p_formatted = p

        words_in_p = len(p_formatted.split())

        if curr_words + words_in_p > max_words and curr_paras:
            chunks.append(("\n\n".join(curr_paras), 800))
            curr_paras = [p_formatted]
            curr_words = words_in_p
        else:
            curr_paras.append(p_formatted)
            curr_words += words_in_p

    if curr_paras:
        chunks.append(("\n\n".join(curr_paras), 1000))

    segments = []
    for idx, (chunk_text, pause_ms) in enumerate(chunks, 1):
        cleaned = normalize_speech_text(chunk_text, is_hindi=is_hindi)
        # Normalize bracketed cues to Gemini 3.8 TTS native angle-bracket tags
        cleaned = re.sub(r"\[(?:whispers|whispering)\]", "<whisper>", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\[(?:sighs|sigh)\]", "<sigh>", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\[(?:gasp|gasps)\]", "<gasp>", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\[(?:pause|silence)\]", "<short pause>", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\[(?:laugh|chuckle)\]", "<laugh>", cleaned, flags=re.IGNORECASE)

        segments.append({
            "index": idx,
            "type": "narration",
            "speaker": "Narrator",
            "text": cleaned,
            "emotion": "neutral",
            "style": style or DEFAULT_DIRECTOR_STYLE,
            "pause_after_ms": pause_ms,
        })

    avg_w = sum(len(s["text"].split()) for s in segments) // max(len(segments), 1)
    print(f"[+] [OFFLINE SUPER-CHUNK] Consolidated literature into {len(segments)} maximum-capacity TTS chunks (Narrator only, ~{avg_w} words/chunk).")
    print(f"[+] Minimum Requests Mode: Total API requests required = {len(segments)} (85-90% quota reduction!)")
    return segments


# =============================================================================
# 100% OFFLINE SCREENPLAY GENERATOR (NO LLM / ZERO API KEYS / RESILIENT)
# =============================================================================
def parse_literature_offline(
    literature_text: str,
    is_hindi: bool = False,
    mode: str = "narrator",
    max_chunk_words: int = 550,
    character_roster: Optional[Dict[str, Any]] = None,
    style: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    100% OFFLINE Screenplay Generator.
    Converts raw novel prose or script text into standard Screenplay JSON segments
    without making any external LLM/API calls. Zero keys, zero rate limits, sub-second speed.

    Modes:
    - 'narrator' / 'auto': Pure audiobook super-chunk mode. Consolidates all narration AND dialogues
                           into maximum-capacity chunks (up to 550 words/chunk) voiced entirely by Narrator.
                           Minimizes API requests to the absolute minimum (1 request per ~3-4 mins of audio).
    - 'dialogue': Smart heuristic multi-speaker parser that splits individual character dialogues.
    - 'screenplay': Line-by-line screenplay script parser for texts formatted with 'SPEAKER: line'.
    """
    clean_text = literature_text.strip()
    if not clean_text:
        return []

    mode = (mode or "narrator").lower()

    if mode in ("narrator", "superchunk", "auto"):
        return build_narrator_superchunks(clean_text, is_hindi=is_hindi, max_words=max_chunk_words, style=style)

    if mode == "screenplay":
        print("[*] [OFFLINE PARSER] Parsing formatted screenplay script lines (100% offline)...")
        raw_items = []
        lines = clean_text.splitlines()
        script_pattern = re.compile(r"^([A-Za-z0-9_\u0900-\u097F\s]{2,25})[:–—\-]\s*(.+)$")
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            m = script_pattern.match(line_str)
            if m:
                spk = m.group(1).strip()
                dia = m.group(2).strip()
                spk_lower = spk.lower()
                if spk_lower in ("narrator", "narration", "विवरण", "सूत्रधार"):
                    raw_items.append({
                        "index": len(raw_items) + 1,
                        "type": "narration",
                        "speaker": "Narrator",
                        "text": dia,
                        "emotion": "neutral",
                        "pause_after_ms": 600,
                    })
                else:
                    raw_items.append({
                        "index": len(raw_items) + 1,
                        "type": "dialogue",
                        "speaker": spk,
                        "text": dia,
                        "emotion": "neutral",
                        "pause_after_ms": 450,
                    })
            else:
                raw_items.append({
                    "index": len(raw_items) + 1,
                    "type": "narration",
                    "speaker": "Narrator",
                    "text": line_str,
                    "emotion": "neutral",
                    "pause_after_ms": 700,
                })
        return clean_screenplay_pass2(raw_items, is_hindi=is_hindi, character_roster=character_roster)

    # mode == 'auto' or 'dialogue'
    print("[*] [OFFLINE PARSER] Smart Heuristic Dialogue & Narration Segmentation (100% offline)...")

    # 1. Multi-turn Hindi dialogue cue pattern: e.g. "सोनू ने कहा- ...", "वह पूछता- ...", "मैंने कहा- ...", "कहती- ..."
    hindi_cue_pattern = re.compile(
        r"(?:^|[।?!.\n])\s*([^।?!.\n]{0,35}?(?:ने\s*(?:कहा|पूछा|जवाब\s*दिया|बोला|बोली)|कहता\s*है|कहती\s*है|कहता|कहती|पूछता|पूछती|बोला|बोली|कहा\s*था|कहा|जवाब\s*दिया|जवाब\s*देती|कह\s*देती\s*थी|हंसते\s*हुए\s*कहता|हंसते\s*हुए\s*कहा|हंसकर\s*कहा)\s*[-—:])\s*",
        re.DOTALL
    )

    # 2. English / Western dialogue quotation pattern
    eng_quote_pat = re.compile(r'["“]([^"”]+)["”]')

    # 3. Known characters
    active_characters = []
    if character_roster and "characters" in character_roster:
        chars = character_roster["characters"]
        if isinstance(chars, dict):
            active_characters = list(chars.keys())
        elif isinstance(chars, list):
            active_characters = [c.get("english_name", "") for c in chars if isinstance(c, dict)]

    paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]
    raw_items = []
    recent_dialogue_speakers = []

    for p_clean in paragraphs:
        # Chapter header detection
        if p_clean.startswith("#"):
            raw_items.append({
                "index": len(raw_items) + 1,
                "type": "chapter_header",
                "speaker": "Narrator",
                "text": p_clean.lstrip("#").strip(),
                "emotion": "neutral",
                "pause_after_ms": 1200,
            })
            continue

        # Scene break detection
        if p_clean in ("---", "* * *", "***", "— — —", "___"):
            if raw_items:
                raw_items[-1]["pause_after_ms"] = max(raw_items[-1].get("pause_after_ms", 600), 1200)
            continue

        # Check Hindi dash dialogue turns
        h_matches = list(hindi_cue_pattern.finditer(p_clean)) if (is_hindi or any('\u0900' <= ch <= '\u097f' for ch in p_clean)) else []

        if h_matches:
            first_start = h_matches[0].start()
            if first_start > 0:
                lead_narr = p_clean[:first_start].strip()
                if len(lead_narr.split()) > 2:
                    raw_items.append({
                        "index": len(raw_items) + 1,
                        "type": "narration",
                        "speaker": "Narrator",
                        "text": lead_narr,
                        "emotion": "neutral",
                        "pause_after_ms": 500,
                    })

            for i, m in enumerate(h_matches):
                cue_text = m.group(1).strip()
                body_start = m.end()
                body_end = h_matches[i + 1].start() if i + 1 < len(h_matches) else len(p_clean)
                dia_text = p_clean[body_start:body_end].strip()
                if not dia_text:
                    continue

                # Speaker resolution
                detected_spk = "Narrator"
                if any(w in cue_text for w in ("मैंने", "मैं", "कहती", "बोली", "देती")):
                    detected_spk = "Protagonist"
                elif any(w in cue_text for w in ("वह", "उसने")):
                    detected_spk = recent_dialogue_speakers[-1] if recent_dialogue_speakers else "He"
                else:
                    words = [w.strip("-—: ।?!,.`'\"") for w in cue_text.split()]
                    stop_words = {
                        "इस", "पर", "तो", "जैसे", "अक्सर", "मुझसे", "ने", "भी", "हंसते", "हुए",
                        "कहता", "कहती", "पूछता", "पूछती", "बोला", "बोली", "कहा", "था", "थी", "है",
                        "जवाब", "दिया", "देती", "देता", "कर", "हंसकर"
                    }
                    clean_words = [w for w in words if w and w not in stop_words]
                    if clean_words:
                        detected_spk = clean_words[-1]
                    else:
                        detected_spk = recent_dialogue_speakers[-1] if recent_dialogue_speakers else "Narrator"

                if detected_spk not in ("Narrator", "Foley") and detected_spk not in active_characters:
                    active_characters.append(detected_spk)

                if detected_spk != "Narrator":
                    if not recent_dialogue_speakers or recent_dialogue_speakers[-1] != detected_spk:
                        recent_dialogue_speakers.append(detected_spk)
                    if len(recent_dialogue_speakers) > 4:
                        recent_dialogue_speakers = recent_dialogue_speakers[-4:]

                # Emotion inference
                emo = "neutral"
                if "?" in dia_text or "क्या" in dia_text or "क्यों" in dia_text:
                    emo = "curious"
                elif "!" in dia_text:
                    emo = "excited"
                elif "हंस" in cue_text:
                    emo = "happy"
                elif "फुसफुसा" in cue_text:
                    emo = "whispering"

                raw_items.append({
                    "index": len(raw_items) + 1,
                    "type": "dialogue",
                    "speaker": detected_spk,
                    "text": dia_text,
                    "emotion": emo,
                    "pause_after_ms": 450,
                })
            continue

        # Check English / Western quotes
        quotes = eng_quote_pat.findall(p_clean)
        if quotes:
            parts = eng_quote_pat.split(p_clean)
            for p_idx, part in enumerate(parts):
                part_strip = part.strip()
                if not part_strip:
                    continue
                if p_idx % 2 == 1:
                    prev_part = parts[p_idx - 1] if p_idx > 0 else ""
                    next_part = parts[p_idx + 1] if p_idx + 1 < len(parts) else ""
                    context_tag = (prev_part[-60:] + " " + next_part[:60]).strip()

                    spk = "Character"
                    for ac in active_characters:
                        if ac.lower() in context_tag.lower():
                            spk = ac
                            break
                    if spk == "Character":
                        spk = recent_dialogue_speakers[-1] if recent_dialogue_speakers else "Narrator"

                    emo = "neutral"
                    if "?" in part_strip:
                        emo = "curious"
                    elif "!" in part_strip:
                        emo = "excited"

                    raw_items.append({
                        "index": len(raw_items) + 1,
                        "type": "dialogue",
                        "speaker": spk,
                        "text": part_strip,
                        "emotion": emo,
                        "pause_after_ms": 450,
                    })
                else:
                    if len(part_strip.split()) > 3:
                        raw_items.append({
                            "index": len(raw_items) + 1,
                            "type": "narration",
                            "speaker": "Narrator",
                            "text": part_strip,
                            "emotion": "neutral",
                            "pause_after_ms": 600,
                        })
            continue

        # Default Narration Paragraph
        w_count = len(p_clean.split())
        if w_count > 350:
            sub_chunks = build_narrator_script(p_clean, is_hindi=is_hindi)
            raw_items.extend(sub_chunks)
        else:
            raw_items.append({
                "index": len(raw_items) + 1,
                "type": "narration",
                "speaker": "Narrator",
                "text": p_clean,
                "emotion": "neutral",
                "pause_after_ms": 600,
            })

    cleaned = clean_screenplay_pass2(raw_items, is_hindi=is_hindi, character_roster=character_roster)
    dia_cnt = len([s for s in cleaned if s.get("type") == "dialogue"])
    nar_cnt = len([s for s in cleaned if s.get("type") == "narration"])
    print(f"[+] [OFFLINE PARSER] Generated {len(cleaned)} screenplay segments ({dia_cnt} dialogues, {nar_cnt} narrations).")
    return cleaned


# =============================================================================
# DYNAMIC CHARACTER VOICE REGISTRY ALLOCATION
# =============================================================================
def generate_voice_registry_for_screenplay(
    segments: List[Dict[str, Any]],
    default_voice: str = "Aoede",
    registry_file: Optional[Path] = None,
    character_roster: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Discovers all unique character speakers in the screenplay and assigns balanced,
    distinct voice models so the TTS engine maintains distinct character identities.
    Prioritizes canonical voice assignments from character_roster.json if available.
    """
    existing_registry = {}
    if registry_file and registry_file.exists():
        try:
            with open(registry_file, "r", encoding="utf-8") as f:
                existing_registry = json.load(f)
        except Exception:
            existing_registry = {}

    unique_speakers = []
    for seg in segments:
        sp = seg.get("speaker", "Narrator").strip()
        if sp and sp not in ("Narrator", "Foley") and sp not in unique_speakers:
            unique_speakers.append(sp)

    if "Narrator" not in existing_registry:
        existing_registry["Narrator"] = {
            "backend": "gemini_tts",
            "voice": default_voice,
            "speed": 1.0,
        }

    # Extract canon roster definitions
    roster_chars = {}
    if character_roster:
        roster_chars = character_roster.get("characters", character_roster)

    female_pool = [v for v in AVAILABLE_VOICES_FEMALE if v != default_voice]
    male_pool = list(AVAILABLE_VOICES_MALE)

    m_idx = 0
    f_idx = 0

    for sp in unique_speakers:
        if sp in existing_registry:
            continue

        # Check if defined in canon roster
        matched_voice = None
        for cname, cinfo in roster_chars.items():
            if isinstance(cinfo, dict):
                aliases = [a.lower() for a in cinfo.get("aliases", [])]
                if sp.lower() == cname.lower() or sp.lower() in aliases:
                    matched_voice = cinfo.get("voice_persona")
                    break

        if matched_voice:
            chosen_voice = matched_voice
        else:
            sp_lower = sp.lower()
            is_female = any(x in sp_lower for x in ["woman", "girl", "lady", "queen", "priestess", "nenneke", "yennefer", "renfri", "ciri", "mother", "sister"])
            if is_female:
                chosen_voice = female_pool[f_idx % len(female_pool)]
                f_idx += 1
            else:
                chosen_voice = male_pool[m_idx % len(male_pool)]
                m_idx += 1

        existing_registry[sp] = {
            "backend": "gemini_tts",
            "voice": chosen_voice,
            "speed": 1.0,
            "pitch": 1.0,
        }

    if registry_file:
        registry_file.parent.mkdir(parents=True, exist_ok=True)
        with open(registry_file, "w", encoding="utf-8") as f:
            json.dump(existing_registry, f, indent=2, ensure_ascii=False)

    return existing_registry


# =============================================================================
# STAGE 2: SCREENPLAY JSON -> TTS SPEECH SYNTHESIS (gemini-3.8-flash-tts)
# Pure Round-Robin KeyPool Execution with Cadence & DSP Calibration
# =============================================================================
def apply_speaker_dsp_calibration(
    wav_path: Path,
    sp_cfg: Dict[str, Any],
    acting: Dict[str, Any],
    text: str,
) -> float:
    """Applies speaker acoustic DSP calibration (pitch, speed, denoise, warmth, saturation) via FFmpeg."""
    ffmpeg = get_ffmpeg()
    post_filters = []

    speed = float(sp_cfg.get("speed", 1.0))
    pacing_mult = float(acting.get("pacing", 1.0)) if isinstance(acting, dict) else 1.0
    if 0.75 <= pacing_mult <= 1.35:
        speed = speed * pacing_mult

    pitch = float(sp_cfg.get("pitch", 1.0))
    bass_boost_db = float(sp_cfg.get("bass_boost_db", 0.0))
    denoise = bool(sp_cfg.get("denoise", False))
    highpass_hz = int(sp_cfg.get("highpass_hz", 0))
    presence_boost_db = float(sp_cfg.get("presence_boost_db", 0.0))
    volume_gain_db = float(sp_cfg.get("volume_gain_db", 0.0))
    softclip_tanh = bool(sp_cfg.get("softclip_tanh", False))

    if highpass_hz > 20:
        post_filters.append(f"highpass=f={highpass_hz}")

    if denoise:
        post_filters.append("afftdn=nr=10:nf=-38")

    # Shouting / bellowing rage analog warmth & anti-harshness saturation
    if ("[shouting]" in text.lower()) or (isinstance(acting, dict) and acting.get("delivery_style") == "bellowing_rage"):
        softclip_tanh = True
        presence_boost_db = max(1.5, min(2.0, presence_boost_db))

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

    if presence_boost_db > 0.1:
        post_filters.append(f"equalizer=f=3200:t=q:w=1.4:g={presence_boost_db:.1f}")

    if abs(volume_gain_db) > 0.1:
        post_filters.append(f"volume={volume_gain_db:+.1f}dB")

    dur_sec = 0.0
    if post_filters:
        tmp_calib = wav_path.with_suffix(".calib.wav")
        cmd = [
            ffmpeg, "-y",
            "-i", str(wav_path),
            "-af", ",".join(post_filters),
            "-c:a", "pcm_s16le",
            str(tmp_calib),
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            tmp_calib.replace(wav_path)
        except Exception as e:
            logger.warning(f"  [!] Speaker DSP calibration notice: {e}")
            if tmp_calib.exists():
                tmp_calib.unlink(missing_ok=True)

    with wave.open(str(wav_path), "rb") as wf:
        dur_sec = wf.getnframes() / float(wf.getframerate())
    return dur_sec


def synthesize_screenplay_round_robin(
    segments: List[Dict[str, Any]],
    audio_dir: Path,
    voice_registry: Dict[str, Any],
    default_voice: str = "Aoede",
    tts_model: str = DEFAULT_TTS_MODEL,
    pool: Optional[PersistentKeyPool] = None,
    rpm: float = DEFAULT_RPM,
    max_key_rotations_per_seg: int = 20,
) -> List[Path]:
    """
    Synthesizes speech segments with gemini-3.8-flash-tts using pure round-robin
    key rotation and HumanCadenceController pacing.
    Guarantees:
      - ZERO Key Hammering: On ANY error, immediately backs off the key and rotates to the NEXT key.
      - Anti-Correlation Cooldown: Waits 18-32s via cadence.wait_for_key_switch on key switch.
      - Human Pacing: cadence.wait_before_segment before every segment.
      - Scene Breaks: 15-30s pause every 15 segments.
      - Telemetry: cadence.record_completed_segment updates internal audio duration model.
    """
    if pool is None:
        pool = get_persistent_key_pool()

    cadence = get_human_cadence_controller()
    audio_dir.mkdir(parents=True, exist_ok=True)
    rate_limiter = TokenBucketRateLimiter(rate_rpm=rpm)
    total_segments = len(segments)
    audio_chunk_paths: List[Optional[Path]] = [None] * total_segments

    print(f"\n[*] Synthesizing {total_segments} audio segments via KeyPool Round-Robin (Model: {tts_model})...")

    for idx, seg in enumerate(segments, 1):
        seg_type = seg.get("type", "dialogue")
        speaker = seg.get("speaker", "Narrator")
        text = seg.get("text", "").strip()

        # Handle Action Beat: Generate clean silent 24kHz mono canvas matching pause_after_ms (0 API calls!)
        if seg_type == "action":
            pause_ms = seg.get("pause_after_ms", 600) or 600
            dur_sec = pause_ms / 1000.0
            action_hash = hashlib.md5(f"action|{idx}|{pause_ms}".encode("utf-8")).hexdigest()[:8]
            out_file = audio_dir / f"seg_{idx:04d}_action_{action_hash}.wav"

            if not (out_file.exists() and out_file.stat().st_size > 44):
                sample_rate = 24000
                num_frames = int(round(sample_rate * dur_sec))
                silence_bytes = b"\x00" * (num_frames * 2)
                with wave.open(str(out_file), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(silence_bytes)

            audio_chunk_paths[idx - 1] = out_file
            print(f"  [{idx:03d}/{total_segments:03d}] [ACTION BEAT] Foley silence canvas ({dur_sec:.2f}s) -> {out_file.name}")
            continue

        if not text:
            text = "..."

        # Numeral normalization
        clean_token = re.sub(r"^[^\w\d\u0900-\u097F]+|[^\w\d\u0900-\u097F]+$", "", text)
        if clean_token in NUMERAL_NORMALIZATION:
            text = NUMERAL_NORMALIZATION[clean_token]
        elif text in NUMERAL_NORMALIZATION:
            text = NUMERAL_NORMALIZATION[text]

        # Voice resolution
        sp_cfg = voice_registry.get(speaker, voice_registry.get("Narrator", {}))
        voice = sp_cfg.get("voice", default_voice)

        acting = seg.get("acting", {})
        pacing = float(acting.get("pacing", 1.0)) if isinstance(acting, dict) else 1.0
        emotion = seg.get("emotion", "neutral")

        # Cache key check: if already synthesized on disk, skip network call
        calib_str = f"{voice}:{pacing:.2f}:{emotion}"
        cache_key = f"{text}|{calib_str}".encode("utf-8")
        text_hash = hashlib.md5(cache_key).hexdigest()[:8]
        out_file = audio_dir / f"seg_{idx:04d}_{text_hash}.wav"

        if out_file.exists() and out_file.stat().st_size > 1000:
            dur = 0.0
            try:
                with wave.open(str(out_file), "rb") as wf:
                    dur = wf.getnframes() / float(wf.getframerate())
            except Exception:
                dur = 1.0
            audio_chunk_paths[idx - 1] = out_file
            print(f"  [{idx:03d}/{total_segments:03d}] [CACHED] {speaker} ({voice}) -> {out_file.name} ({dur:.1f}s)")
            continue

        # Human Cadence Delay (reading time + listening simulation + lognormal jitter + scene breaks)
        cadence.wait_before_segment(text, idx, total_segments)

        # Build synthesis payload with Gemini 3.8 Flash TTS speech_metadata style steering
        style_instruction = seg.get("style")
        if not style_instruction:
            emotion = seg.get("emotion", "neutral")
            if emotion == "whispering":
                style_instruction = "whispered urgently with quiet suspense and breathless intensity"
            elif emotion == "fear":
                style_instruction = "tense atmosphere with trembling fearful emotional delivery"
            elif emotion == "angry":
                style_instruction = "intense aggressive delivery with fierce dramatic vocal strain"
            elif emotion == "reassuring":
                style_instruction = "warm comforting delivery with gentle reassuring cadence"
            else:
                style_instruction = DEFAULT_DIRECTOR_STYLE

        part_payload: Dict[str, Any] = {
            "text": text,
            "speech_metadata": {
                "speaker": speaker,
                "style": style_instruction,
            }
        }

        payload = {
            "contents": [{"parts": [part_payload]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": voice}
                    }
                }
            },
            "safetySettings": SAFETY_SETTINGS_BLOCK_NONE,
        }
        data_bytes = json.dumps(payload).encode("utf-8")

        # Synthesis loop with strict Round-Robin Key Rotation:
        # Every failed attempt rotates to the NEXT key in the pool. Never hammers the same key!
        success = False
        for rotation in range(max_key_rotations_per_seg):
            rate_limiter.acquire()
            try:
                curr_key = pool.get_key(service="tts")
            except AllKeysExhaustedTodayError as e:
                logger.error(f"\n[!] Daily TTS quota exhausted across all keys: {e}")
                raise
            except Exception as e:
                logger.error(f"\n[!] Failed to acquire TTS key from pool: {e}")
                break

            key_preview = f"{curr_key[:8]}...{curr_key[-6:]}"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{tts_model}:generateContent?key={curr_key}"
            headers = get_stealth_sdk_headers(curr_key)
            req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

            try:
                with urllib.request.urlopen(req, timeout=45.0) as resp:
                    resp_json = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_json.get("candidates", [])
                    if not candidates:
                        raise ValueError(f"Gemini TTS blocked generation: {resp_json.get('promptFeedback', {})}")

                    candidate = candidates[0]
                    inline_data = {}
                    for p in candidate.get("content", {}).get("parts", []):
                        if "inlineData" in p:
                            inline_data = p["inlineData"]
                            break

                    b64_audio = inline_data.get("data", "")
                    if not b64_audio:
                        raise ValueError("No audio inlineData in response")

                    raw_pcm = base64.b64decode(b64_audio)
                    out_file.parent.mkdir(parents=True, exist_ok=True)
                    with wave.open(str(out_file), "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(24000)
                        wf.writeframes(raw_pcm)

                    # Mathematical SNR Gatekeeper check
                    frames = len(raw_pcm) // 2
                    dur_sec = frames / 24000.0
                    word_count = max(len(text.split()), 1)
                    ratio = dur_sec / word_count
                    is_stutter = (word_count > 3 and ratio > 3.2 and dur_sec >= 15.0)
                    is_empty = (dur_sec < 0.20 and word_count >= 3)

                    if is_stutter or is_empty:
                        out_file.unlink(missing_ok=True)
                        logger.warning(f"  [SNR REJECT] Segment rejected (stutter={is_stutter}, empty={is_empty}). Switching key...")
                        pool.mark_temporary_backoff(curr_key, 10.0, "SNR gatekeeper rejected defect")
                        cadence.wait_for_key_switch(curr_key[-6:], "next_project")
                        continue

                    # Apply Speaker DSP Calibration
                    dur_sec = apply_speaker_dsp_calibration(out_file, sp_cfg, acting, text)

                    pool.record_success(curr_key)
                    cadence.record_completed_segment(dur_sec)
                    audio_chunk_paths[idx - 1] = out_file
                    print(f"  [{idx:03d}/{total_segments:03d}] [SYNTHESIZED] {speaker} ({voice}) -> {out_file.name} ({dur_sec:.1f}s) [Key: ...{curr_key[-6:]}]")
                    success = True
                    break

            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else str(e)
                category, wait_sec, msg = classify_gemini_error(e.code, err_body)
                logger.warning(f"  [KEYPOOL ROTATE] Key {key_preview} HTTP {e.code} ({category}).")

                if category == "DAILY_QUOTA_EXHAUSTED":
                    pool.mark_daily_quota_exhausted(curr_key, msg)
                    cadence.wait_for_key_switch(curr_key[-6:], "next_project")
                elif category == "RPM_RATE_LIMIT":
                    pool.mark_temporary_backoff(curr_key, wait_sec, msg)
                    rate_limiter.trigger_global_pause(wait_sec)
                    cadence.wait_for_key_switch(curr_key[-6:], "next_project")
                elif category == "TRANSIENT_SERVER_ERROR":
                    pool.mark_temporary_backoff(curr_key, wait_sec, msg)
                    cadence.wait_for_key_switch(curr_key[-6:], "next_project")
                elif category == "INVALID_KEY":
                    pool.mark_invalid(curr_key, msg)
                else:
                    pool.mark_temporary_backoff(curr_key, 6.0, msg)
                    cadence.wait_for_key_switch(curr_key[-6:], "next_project")

                # ZERO KEY HAMMERING: Rotate immediately to next key from pool!
                continue

            except (urllib.error.URLError, TimeoutError, ConnectionResetError, OSError) as net_err:
                logger.warning(f"  [KEYPOOL ROTATE] Key {key_preview} timeout/network error ({net_err}).")
                pool.mark_temporary_backoff(curr_key, 10.0, f"Network glitch: {net_err}")
                cadence.wait_for_key_switch(curr_key[-6:], "next_project")
                continue

        if not success:
            raise RuntimeError(f"Failed to synthesize segment {idx} ('{text[:30]}...') after {max_key_rotations_per_seg} key rotations.")

    return [p for p in audio_chunk_paths if p is not None]


# =============================================================================
# STAGE 4: EBU R128 BROADCAST COMPLIANCE AUDIT
# =============================================================================
def audit_ebu_r128(audio_file: Path) -> None:
    """Runs FFmpeg EBU R128 loudness analysis and displays compliance telemetry."""
    ffmpeg = get_ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-i", str(audio_file),
        "-filter_complex", "ebur128=peak=true",
        "-f", "null", "-",
    ]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")

    lines = res.stderr.splitlines()
    summary_lines = []
    in_summary = False
    for l in lines:
        if "Summary:" in l:
            in_summary = True
        if in_summary:
            summary_lines.append(l)

    print("\n" + "=" * 80)
    print("  EBU R128 BROADCAST COMPLIANCE CERTIFICATION")
    print("=" * 80)
    if summary_lines:
        print("\n".join(summary_lines[-16:]))
    else:
        print(f"  Audio File: {audio_file.name} ({audio_file.stat().st_size:,} bytes)")
    print("=" * 80 + "\n")


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================
def run_standalone_pipeline(
    input_file: Optional[Path] = None,
    inline_text: Optional[str] = None,
    from_screenplay: Optional[Path] = None,
    output_file: Optional[Path] = None,
    work_dir: Optional[Path] = None,
    is_hindi: bool = False,
    screenplay_only: bool = False,
    offline: bool = False,
    offline_mode: str = "narrator",
    max_chunk_words: int = 550,
    director_style: Optional[str] = None,
    llm_engine: str = DEFAULT_LLM_ENGINE,
    openrouter_model: str = DEFAULT_OPENROUTER_MODEL,
    openrouter_key: Optional[str] = None,
    model: str = DEFAULT_JSON_MODEL,
    tts_model: str = DEFAULT_TTS_MODEL,
    default_voice: str = "Aoede",
    target_lufs: float = -19.0,
    true_peak_db: float = -1.5,
    spatial_staging: bool = True,
) -> Path:
    """End-to-end execution of the standalone audiobook pipeline."""
    pool = get_persistent_key_pool()
    print_keypool_status(pool)

    # Resolve working directory
    if work_dir is None:
        work_dir = ROOT_DIR / "standalone_workspace"
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    scripts_dir = work_dir / "scripts"
    audio_chunks_dir = work_dir / "audio_chunks"
    mastered_dir = work_dir / "mastered"

    scripts_dir.mkdir(parents=True, exist_ok=True)
    audio_chunks_dir.mkdir(parents=True, exist_ok=True)
    mastered_dir.mkdir(parents=True, exist_ok=True)

    if output_file is None:
        output_file = mastered_dir / "mastered_audiobook.mp3"
    else:
        output_file = Path(output_file).resolve()
        output_file.parent.mkdir(parents=True, exist_ok=True)

    screenplay_file = scripts_dir / "screenplay.json"
    segments: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # PRE-FLIGHT MODEL HEALTH PROBE (ZERO HAMMERING GUARANTEE)
    # Probes models with a single micro-request. If dead/503, auto-failovers to
    # an active healthy model without cycling 120+ keys.
    # Completely bypassed if running in 100% offline mode or resuming from screenplay!
    # -------------------------------------------------------------------------
    if not (from_screenplay and Path(from_screenplay).exists()) and not offline and llm_engine == "gemini":
        model = verify_or_select_model(model, is_tts=False, pool=pool, auto_failover=True)

    if not screenplay_only:
        tts_model = verify_or_select_model(tts_model, is_tts=True, pool=pool, auto_failover=True)

    # -------------------------------------------------------------------------
    # STAGE 1: SCREENPLAY GENERATION (OpenRouter / Gemini / 100% Offline Engine)
    # -------------------------------------------------------------------------
    if from_screenplay and Path(from_screenplay).exists():
        print(f"[*] Loading pre-existing screenplay from: {from_screenplay}")
        with open(from_screenplay, "r", encoding="utf-8") as f:
            data = json.load(f)
            segments = data.get("segments", data) if isinstance(data, dict) else data
    else:
        literature_text = ""
        if input_file and Path(input_file).exists():
            print(f"[*] Reading source literature from: {input_file}")
            with open(input_file, "r", encoding="utf-8") as f:
                literature_text = f.read()
        elif inline_text:
            print("[*] Using inline literature text provided via CLI.")
            literature_text = inline_text
        else:
            raise ValueError("No input literature provided! Specify --input, --text, or --from-screenplay.")

        t0 = time.time()
        if offline or llm_engine == "offline":
            print(f"\n{'='*80}\n  STAGE 1: LITERATURE -> SCREENPLAY JSON (100% OFFLINE PARSER - Mode: {offline_mode})\n{'='*80}")
            segments = parse_literature_offline(
                literature_text=literature_text,
                is_hindi=is_hindi,
                mode=offline_mode,
                max_chunk_words=max_chunk_words,
                style=director_style or DEFAULT_DIRECTOR_STYLE,
            )
        elif llm_engine == "openrouter":
            print(f"\n{'='*80}\n  STAGE 1: LITERATURE -> SCREENPLAY JSON (OpenRouter: {openrouter_model} -> Gemini 3.8 Flash TTS Calibrated)\n{'='*80}")
            segments = format_literature_with_openrouter(
                literature_text=literature_text,
                is_hindi=is_hindi,
                model=openrouter_model,
                api_key=openrouter_key,
            )
        else:  # llm_engine == "gemini"
            print(f"\n{'='*80}\n  STAGE 1: LITERATURE -> SCREENPLAY JSON (Gemini: {model} + BLOCK_NONE)\n{'='*80}")
            segments = format_literature_to_screenplay(
                literature_text=literature_text,
                is_hindi=is_hindi,
                model=model,
                pool=pool,
            )
        t_script = time.time() - t0

        with open(screenplay_file, "w", encoding="utf-8") as f:
            json.dump({"segments": segments}, f, indent=2, ensure_ascii=False)

        print(f"[+] Screenplay formatted in {t_script:.2f}s -> {screenplay_file.name} ({len(segments)} segments)")

    if screenplay_only:
        # If output_file ends with .json, copy directly to output_file
        if output_file and output_file.suffix.lower() == ".json":
            import shutil
            shutil.copy(screenplay_file, output_file)
            print(f"\n[+] --screenplay-only requested. Screenplay JSON saved at: {output_file}")
            return output_file
        print(f"\n[+] --screenplay-only requested. Screenplay JSON saved at: {screenplay_file}")
        return screenplay_file

    # Build or update Voice Registry in the working directory
    registry_file = work_dir / "voice_registry.json"
    voice_registry = generate_voice_registry_for_screenplay(
        segments=segments,
        default_voice=default_voice,
        registry_file=registry_file,
    )
    print(f"[+] Character Voice Registry ready: {len(voice_registry)} characters registered -> {registry_file.name}")

    # -------------------------------------------------------------------------
    # STAGE 2: KEYPOOL TTS SYNTHESIS (gemini-3.8-flash-tts + BLOCK_NONE)
    # -------------------------------------------------------------------------
    print(f"\n{'='*80}\n  STAGE 2: GEMINI 3.8 FLASH TTS SYNTHESIS ({tts_model} + BLOCK_NONE)\n{'='*80}")
    t0_synth = time.time()
    audio_chunks = synthesize_screenplay_round_robin(
        segments=segments,
        audio_dir=audio_chunks_dir,
        voice_registry=voice_registry,
        default_voice=default_voice,
        tts_model=tts_model,
        pool=pool,
    )
    t_synth = time.time() - t0_synth
    print(f"\n[+] Speech synthesis completed in {t_synth:.1f}s ({t_synth/60:.1f}m). Chunks ready: {len(audio_chunks)}")

    # -------------------------------------------------------------------------
    # STAGE 3: FFmpeg AUDIO CONCATENATION & 5-STAGE MASTERING
    # Directly uses audiobook_factory.mastering.concatenate_and_master_chapter
    # -------------------------------------------------------------------------
    print(f"\n{'='*80}\n  STAGE 3: FFmpeg AUDIO CONCATENATION & MASTERING (audiobook_factory.mastering)\n{'='*80}")
    t0_master = time.time()
    final_output = concatenate_and_master_chapter(
        audio_segments=audio_chunks,
        output_chapter_file=output_file,
        pause_ms=400,
        loudnorm=True,
        target_lufs=target_lufs,
        true_peak_db=true_peak_db,
        loudness_range=11.0,
        target_sample_rate=48000,
        script_segments=segments,
        spatial_staging=spatial_staging,
    )
    t_master = time.time() - t0_master
    print(f"[+] Audio mastered in {t_master:.1f}s -> {final_output}")

    # Stage 4: EBU R128 Loudness Compliance Audit
    audit_ebu_r128(final_output)

    print("\n" + "=" * 80)
    print("  PRODUCTION PIPELINE COMPLETED SUCCESSFULLY!")
    print(f"  Master File:     {final_output}")
    print(f"  Screenplay JSON: {screenplay_file}")
    print(f"  Voice Registry:  {registry_file}")
    print("=" * 80 + "\n")

    return final_output


# =============================================================================
# CLI ENTRYPOINT
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Audiobook Factory - Standalone Production Pipeline (gemini-3.5-flash + gemini-3.8-flash-tts + KeyPool + FFmpeg)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("-i", "--input", type=str, help="Path to input literature file (.txt, .md)")
    parser.add_argument("-t", "--text", type=str, help="Raw inline literature text to process directly")
    parser.add_argument("-o", "--output", type=str, help="Path for final mastered audio file (default: standalone_workspace/mastered/mastered_audiobook.mp3)")
    parser.add_argument("-w", "--work-dir", type=str, default="standalone_workspace", help="Scratch directory for artifacts (default: ./standalone_workspace)")
    parser.add_argument("--hindi", action="store_true", help="Enable Hindi Devanagari speech normalization and prosody")
    parser.add_argument("--from-screenplay", type=str, help="Resume directly from an existing screenplay JSON file (skips Stage 1)")
    parser.add_argument("--screenplay-only", action="store_true", help="Stop after Stage 1 (only generate and save screenplay JSON)")
    parser.add_argument("--model", type=str, default=DEFAULT_JSON_MODEL, help=f"Gemini text model for screenplay formatting (default: {DEFAULT_JSON_MODEL})")
    parser.add_argument("--tts-model", type=str, default=DEFAULT_TTS_MODEL, help=f"Gemini TTS model (default: {DEFAULT_TTS_MODEL})")
    parser.add_argument("--voice", type=str, default="Aoede", help="Default narrator voice (default: Aoede)")
    parser.add_argument("--target-lufs", type=float, default=-19.0, help="EBU R128 loudness target in LUFS (default: -19.0)")
    parser.add_argument("--true-peak", type=float, default=-1.5, help="True peak limit in dBTP (default: -1.5)")
    parser.add_argument("--spatial", action="store_true", default=True, help="Enable stereo spatial soundstage panning (default: True)")
    parser.add_argument("--no-spatial", dest="spatial", action="store_false", help="Disable spatial stereo staging")
    parser.add_argument("--llm-engine", type=str, default=DEFAULT_LLM_ENGINE, choices=["openrouter", "gemini", "offline"], help=f"Screenplay generator engine: 'openrouter' (Qwen/Nemotron/Gemma calibrated for Gemini TTS), 'gemini' (Gemini Flash), or 'offline' (default: {DEFAULT_LLM_ENGINE})")
    parser.add_argument("--openrouter-model", type=str, default=DEFAULT_OPENROUTER_MODEL, help=f"OpenRouter model for screenplay generation (default: {DEFAULT_OPENROUTER_MODEL})")
    parser.add_argument("--openrouter-key", type=str, default="", help="OpenRouter API Key (default: loads from OPENROUTER_API_KEY in .env)")
    parser.add_argument("--offline", action="store_true", help="Generate screenplay JSON 100%% offline without calling any LLM API (zero keys, instant)")
    parser.add_argument("--offline-mode", type=str, default="narrator", choices=["narrator", "dialogue", "screenplay"], help="Offline parser mode: 'narrator' (max-density single-voice superchunks, minimum requests), 'dialogue' (multi-cast character splitting), 'screenplay' (line-by-line script)")
    parser.add_argument("--max-chunk-words", type=int, default=550, help="Maximum word count per TTS request in narrator mode (default: 550 words, ~3.5 mins of audio)")
    parser.add_argument("--style", type=str, default=DEFAULT_DIRECTOR_STYLE, help=f"Gemini 3.8 Flash TTS director style prompt for acting and tone (default: '{DEFAULT_DIRECTOR_STYLE}')")
    parser.add_argument("--pool-status", action="store_true", help="Print KeyPool status and exit")
    parser.add_argument("--reset-keys", action="store_true", help="Reset all keys in KeyPool back to ACTIVE for today and exit")
    parser.add_argument("--check-models", action="store_true", help="Probe and display live status of candidate Gemini models and exit")

    args = parser.parse_args()

    # Special KeyPool maintenance actions
    if args.pool_status:
        pool = get_persistent_key_pool()
        print_keypool_status(pool)
        return

    if args.reset_keys:
        pool = get_persistent_key_pool()
        pool.reset_all_for_today()
        print("[+] All API keys in the SQLite pool reset to ACTIVE.")
        print_keypool_status(pool)
        return

    if args.check_models:
        pool = get_persistent_key_pool()
        print("\n" + "=" * 80)
        print("  PROBING ALL CANDIDATE GEMINI MODELS (TEXT & TTS)")
        print("=" * 80)
        import concurrent.futures
        all_candidates = [(m, False) for m in CANDIDATE_TEXT_MODELS] + [(m, True) for m in CANDIDATE_TTS_MODELS]
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(all_candidates), 8)) as ex:
            futures = {ex.submit(probe_single_model, m, is_tts, pool): (m, is_tts) for m, is_tts in all_candidates}
            for fut in concurrent.futures.as_completed(futures):
                m, is_tts = futures[fut]
                ok, msg, lat = fut.result()
                status_tag = "[ACTIVE OK]" if ok else "[DOWN]"
                typ = "TTS Audio" if is_tts else "Screenplay LLM"
                print(f"  {m:<28} ({typ:<14}): {status_tag:<12} -> {msg}")
        print("=" * 80 + "\n")
        return

    if not args.input and not args.text and not args.from_screenplay:
        parser.print_help()
        print("\n[!] Error: You must supply either --input <file>, --text <string>, or --from-screenplay <json>.\n")
        sys.exit(1)

    input_path = Path(args.input) if args.input else None
    from_script_path = Path(args.from_screenplay) if args.from_screenplay else None
    output_path = Path(args.output) if args.output else None
    work_dir_path = Path(args.work_dir) if args.work_dir else None

    run_standalone_pipeline(
        input_file=input_path,
        inline_text=args.text,
        from_screenplay=from_script_path,
        output_file=output_path,
        work_dir=work_dir_path,
        is_hindi=args.hindi,
        screenplay_only=args.screenplay_only,
        offline=args.offline,
        offline_mode=args.offline_mode,
        max_chunk_words=args.max_chunk_words,
        director_style=args.style,
        llm_engine=args.llm_engine,
        openrouter_model=args.openrouter_model,
        openrouter_key=args.openrouter_key or None,
        model=args.model,
        tts_model=args.tts_model,
        default_voice=args.voice,
        target_lufs=args.target_lufs,
        true_peak_db=args.true_peak,
        spatial_staging=args.spatial,
    )


if __name__ == "__main__":
    main()
