#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.2: Concurrent TTS Dispatcher & Token-Bucket Continuity Engine.
Routes speech segments to Google Gemini 3.1 Flash TTS with thread-safe rate-limiting,
transaction-safe SQLite segment ledgering, and multi-worker parallelism.
"""

import os
import sys
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
import concurrent.futures
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.logger import logger
from audiobook_factory.state import ProjectStateLedger
from audiobook_factory.key_manager import (
    get_persistent_key_pool,
    classify_gemini_error,
    AllKeysExhaustedTodayError,
)
from audiobook_factory.cadence import (
    get_stealth_sdk_headers,
    get_human_cadence_controller,
)


# Default Configuration from Environment
DEFAULT_BACKEND = os.environ.get("TTS_PRIMARY_BACKEND", "gemini_tts")
DEFAULT_VOICE = os.environ.get("GEMINI_DEFAULT_VOICE", "Aoede")
DEFAULT_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.1-flash-tts-preview")
ENABLE_EMERGENCY_FALLBACK = os.environ.get("ENABLE_EMERGENCY_FALLBACK", "false").lower() in ("true", "1", "yes")
# Default to 1 worker for authentic human studio cadence (prevents multi-thread IP clustering)
DEFAULT_WORKERS = int(os.environ.get("TTS_WORKERS", "1"))
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


def synthesize_gemini_tts(
    text: str,
    output_file: Path,
    voice: str = DEFAULT_VOICE,
    model: str = DEFAULT_MODEL,
    emotion: str = "neutral",
    max_retries: int = 4,
    rate_limiter: Optional[TokenBucketRateLimiter] = None,
) -> Tuple[Path, float]:
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": voice
                    }
                }
            }
        }
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
                    inline_data = {}
                    parts = resp_json.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                    for p in parts:
                        if "inlineData" in p:
                            inline_data = p["inlineData"]
                            break
                    b64_audio = inline_data.get("data", "")
                    if not b64_audio:
                        raise ValueError(f"No audio data found in Gemini response parts: {[p.get('text', '')[:40] for p in parts]}")
                    raw_pcm = base64.b64decode(b64_audio)

                    # Convert 24kHz raw PCM to WAV
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    with wave.open(str(output_file), "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(24000)
                        wf.writeframes(raw_pcm)

                    # Compute duration
                    frames = len(raw_pcm) // 2
                    dur_sec = frames / 24000.0

                    # Stutter Guard tuned for dramatic audiobook whisper/pause delivery
                    word_count = max(len(text.split()), 1)
                    ratio = dur_sec / word_count
                    is_stutter = (word_count > 3 and ratio > 2.2 and dur_sec >= 10.0)
                    is_empty = (dur_sec < 0.20 and word_count >= 3)

                    if (is_stutter or is_empty) and network_attempt < 2:
                        reason = "Stutter loop detected" if is_stutter else "Truncated empty audio"
                        logger.warning(
                            f"  [{reason.upper()}] Generated {dur_sec:.1f}s for {word_count} words "
                            f"(ratio: {ratio:.2f}s/word). Retrying segment (Attempt {network_attempt+1}/3)..."
                        )
                        time.sleep(2.0)
                        continue

                    # Record success in persistent key pool
                    pool.record_success(api_key)
                    return output_file, dur_sec

            except urllib.error.HTTPError as e:
                err = e.read().decode("utf-8", errors="ignore")
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
                        f"Cooling off {wait_sec:.1f}s (Attempt {network_attempt+1}/3)..."
                    )
                    if rate_limiter and hasattr(rate_limiter, "trigger_global_pause"):
                        rate_limiter.trigger_global_pause(wait_sec)
                    time.sleep(wait_sec)
                    continue

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


class TTSDispatcher:
    """Orchestrates concurrent speech synthesis with TokenBucket rate limiting and SQLite ledger state."""

    def __init__(
        self,
        project_dir: Path,
        default_backend: str = DEFAULT_BACKEND,
        default_voice: str = DEFAULT_VOICE,
        max_workers: int = DEFAULT_WORKERS,
        rpm: float = DEFAULT_RPM,
    ):
        self.project_dir = Path(project_dir).resolve()
        self.audio_dir = self.project_dir / "audio_chunks"
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.project_dir / "voice_registry.json"
        self.default_backend = default_backend
        self.default_voice = default_voice
        self.max_workers = max_workers
        self.rate_limiter = TokenBucketRateLimiter(rate_rpm=rpm)
        self.voice_map = self._load_voice_registry()
        self.ledger = ProjectStateLedger(self.project_dir)

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

    def synthesize_segment(self, segment: Dict[str, Any], chapter_num: int, seg_num: int) -> Tuple[Path, float]:
        """Synthesize a single speech segment with resume checkpointing."""
        text = segment.get("text", "").strip()
        if not text:
            raise ValueError("Empty segment text")

        speaker = segment.get("speaker", "Narrator")
        cfg = self.voice_map.get(speaker, self.voice_map.get("Narrator", {}))
        backend = cfg.get("backend", self.default_backend) if isinstance(cfg, dict) else self.default_backend
        voice = cfg.get("voice", self.default_voice) if isinstance(cfg, dict) else self.default_voice

        # Checkpoint hash: includes text + voice
        cache_key = f"{text}|{voice}".encode("utf-8")
        text_hash = hashlib.md5(cache_key).hexdigest()[:8]
        out_file = self.audio_dir / f"c{chapter_num:03d}_s{seg_num:04d}_{text_hash}.wav"

        # Resume checkpoint: skip if file already exists and valid
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

        # Dispatch with VibeVoice-style emotion prosody
        emotion = segment.get("emotion", "neutral")
        out_path, dur = synthesize_gemini_tts(
            text=text,
            output_file=out_file,
            voice=voice,
            emotion=emotion,
            rate_limiter=self.rate_limiter,
        )
        return out_path, dur

    def synthesize_chapter_script(self, script_path: Path, chapter_num: int) -> List[Path]:
        """
        Synthesize all segments in a chapter script concurrently using ThreadPoolExecutor.
        Updates the SQLite state ledger at every milestone.
        """
        with open(script_path, "r", encoding="utf-8") as f:
            script = json.load(f)

        total = len(script)
        cadence = get_human_cadence_controller()
        logger.info(
            f"[*] Synthesizing Chapter {chapter_num} ({total} speech segments, mode="
            f"{'STEALTH_HUMAN_CADENCE' if self.max_workers == 1 else f'PARALLEL_{self.max_workers}'})..."
        )

        # Register in SQLite state ledger
        self.ledger.register_script_segments(chapter_num, script, self.voice_map, self.default_voice)

        # Pre-allocate results array by index
        results: List[Optional[Path]] = [None] * total

        # STEALTH HUMAN CADENCE EXECUTION (max_workers == 1)
        if self.max_workers == 1:
            for idx, segment in enumerate(script, 1):
                speaker = segment.get("speaker", "Narrator")
                text = segment.get("text", "")
                voice_cfg = self.voice_map.get(speaker, self.voice_map.get("Narrator", {}))
                voice = voice_cfg.get("voice", self.default_voice) if isinstance(voice_cfg, dict) else self.default_voice
                cache_key = f"{text}|{voice}".encode("utf-8")
                seg_hash = hashlib.md5(cache_key).hexdigest()[:8]
                seg_id = f"c{chapter_num:03d}_s{idx:04d}_{seg_hash}"
                out_file = self.audio_dir / f"{seg_id}.wav"

                # If already cached, fast-forward with zero sleep
                if out_file.exists() and out_file.stat().st_size > 1000:
                    audio_path, dur = self.synthesize_segment(segment, chapter_num, idx)
                    results[idx - 1] = audio_path
                    self.ledger.mark_segment_completed(seg_id, str(audio_path), dur)
                    logger.info(f"  [{idx}/{total}] Cached {speaker} ({audio_path.name}, {dur:.1f}s)")
                    continue

                # Uncached segment: apply organic human reading & listening delay
                cadence.wait_before_segment(text, idx, total)
                self.ledger.mark_segment_started(seg_id)

                try:
                    audio_path, dur = self.synthesize_segment(segment, chapter_num, idx)
                    self.ledger.mark_segment_completed(seg_id, str(audio_path), dur)
                    cadence.record_completed_segment(dur)
                    results[idx - 1] = audio_path
                    logger.info(f"  [{idx}/{total}] Generated {speaker} ({audio_path.name}, {dur:.1f}s)")
                except AllKeysExhaustedTodayError as e:
                    logger.critical(
                        f"  [STEALTH QUOTA PAUSE] {e}. "
                        f"Safely checkpointed at segment {idx}/{total}. No wasted requests."
                    )
                    break
                except Exception as e:
                    self.ledger.mark_segment_failed(seg_id, str(e))
                    logger.error(f"  [ERROR] Segment {idx} ({speaker}) failed: {e}")

            # Targeted 1-pass recovery on transient missed segments
            missing_indices = [i + 1 for i, p in enumerate(results) if p is None]
            pool = get_persistent_key_pool()
            if missing_indices and pool.get_status_summary().get("active_keys", 0) > 0:
                logger.info(f"[*] Attempting 1-pass recovery for {len(missing_indices)} transient missed segment(s): {missing_indices}...")
                for idx in missing_indices:
                    seg = script[idx - 1]
                    try:
                        audio_path, dur = self.synthesize_segment(seg, chapter_num, idx)
                        results[idx - 1] = audio_path
                        logger.info(f"  [{idx}/{total}] Successfully recovered segment ({audio_path.name})")
                    except Exception as e:
                        logger.warning(f"  Could not recover segment {idx}: {e}")

        # PARALLEL THREADPOOL FALLBACK (when explicitly requested by user)
        else:
            def _worker_task(idx: int, segment: Dict[str, Any]) -> Tuple[int, Path]:
                speaker = segment.get("speaker", "Narrator")
                text = segment.get("text", "")
                voice_cfg = self.voice_map.get(speaker, self.voice_map.get("Narrator", {}))
                voice = voice_cfg.get("voice", self.default_voice) if isinstance(voice_cfg, dict) else self.default_voice
                cache_key = f"{text}|{voice}".encode("utf-8")
                seg_hash = hashlib.md5(cache_key).hexdigest()[:8]
                seg_id = f"c{chapter_num:03d}_s{idx:04d}_{seg_hash}"

                self.ledger.mark_segment_started(seg_id)
                try:
                    audio_path, dur = self.synthesize_segment(segment, chapter_num, idx)
                    self.ledger.mark_segment_completed(seg_id, str(audio_path), dur)
                    logger.info(f"  [{idx}/{total}] Generated {speaker} ({audio_path.name}, {dur:.1f}s)")
                    return idx, audio_path
                except Exception as e:
                    self.ledger.mark_segment_failed(seg_id, str(e))
                    logger.error(f"  [ERROR] Segment {idx} ({speaker}) failed: {e}")
                    raise e

            failed_segments: List[Tuple[int, Exception]] = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_idx = {
                    executor.submit(_worker_task, idx, seg): idx
                    for idx, seg in enumerate(script, 1)
                }
                for future in concurrent.futures.as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        _, path = future.result()
                        results[idx - 1] = path
                    except Exception as e:
                        logger.error(f"[ERROR] Synthesis failed on segment {idx}: {e}")
                        failed_segments.append((idx, e))

            # Targeted retry on failed segments
            if failed_segments:
                if any("AllKeysExhaustedTodayError" in str(err) for _, err in failed_segments):
                    logger.critical("[QUOTA HALT] Daily limits reached across pool. Pausing safely.")
                else:
                    logger.warning(f"Retrying {len(failed_segments)} failed segments for Chapter {chapter_num}...")
                    for idx, _ in failed_segments:
                        seg = script[idx - 1]
                        try:
                            _, path = _worker_task(idx, seg)
                            results[idx - 1] = path
                        except Exception as e:
                            logger.error(f"[CRITICAL] Retry failed on segment {idx}: {e}")

        missing = [i + 1 for i, p in enumerate(results) if p is None]
        if missing:
            raise RuntimeError(
                f"Chapter {chapter_num} synthesis incomplete: {len(missing)} segments pending ({missing[:5]}...)."
            )

        audio_files = [p for p in results if p is not None]
        logger.info(f"[+] Chapter {chapter_num} complete: {len(audio_files)} segments synthesized successfully.")
        return audio_files
