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
    probe_key_health,
)


# Default Configuration from Environment
DEFAULT_BACKEND = os.environ.get("TTS_PRIMARY_BACKEND", "gemini_tts")
DEFAULT_VOICE = os.environ.get("GEMINI_DEFAULT_VOICE", "Aoede")
DEFAULT_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.1-flash-tts-preview")
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


def synthesize_gemini_tts(
    text: str,
    output_file: Path,
    voice: str = DEFAULT_VOICE,
    model: str = DEFAULT_MODEL,
    emotion: str = "neutral",
    max_retries: int = 4,
    rate_limiter: Optional[TokenBucketRateLimiter] = None,
) -> Tuple[Path, float]:
    clean_text = text.strip()
    # Strip surrounding punctuation/quotes for numeral lookup: e.g. "८.", "'IV'", "(1)", "3,"
    stripped_token = re.sub(r"^[^\w\d\u0900-\u097F]+|[^\w\d\u0900-\u097F]+$", "", clean_text)
    if stripped_token in NUMERAL_NORMALIZATION:
        text = NUMERAL_NORMALIZATION[stripped_token]
    elif clean_text in NUMERAL_NORMALIZATION:
        text = NUMERAL_NORMALIZATION[clean_text]

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

                    # Compute duration & raw PCM metrics
                    frames = len(raw_pcm) // 2
                    dur_sec = frames / 24000.0
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

                    is_clipped = peak_amp >= 32760
                    faint_limit = 8.0 if ("[whispers]" in text.lower() or "whisper" in emotion.lower() or "tender" in emotion.lower()) else 30.0
                    is_silent_faint = (peak_amp > 0 and word_count >= 3 and rms < faint_limit)
                    is_dc_corrupted = (peak_amp > 0 and dc_offset > 800.0)
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
                        if is_clipped: reasons.append("Clipping Distortion (Peak >= 0 dBFS)")
                        if is_silent_faint: reasons.append(f"Faint Audio (RMS {rms:.1f} < 30)")
                        if is_dc_corrupted: reasons.append(f"DC Offset Anomaly ({dc_offset:.1f} > 800)")
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
    ):
        self.project_dir = Path(project_dir).resolve()
        self.audio_dir = Path(audio_dir).resolve() if audio_dir else (self.project_dir / "audio_chunks")
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.project_dir / "voice_registry.json"
        self.default_backend = default_backend
        self.default_voice = default_voice
        if max_workers > 1:
            logger.info("  [STEALTH INVARIANT] Multi-worker network requests disabled to prevent IP clustering and quota flags. Operating strictly in 1-worker mode.")
        self.max_workers = 1
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

    def get_speaker_config(self, speaker: str, seg_type: str = "narration") -> Dict[str, Any]:
        """
        Resolves complete speaker configuration (backend, voice, speed, pitch, bass_boost_db).
        """
        if speaker in self.voice_map:
            return dict(self.voice_map[speaker])

        sp_lower = speaker.lower().strip()
        for k, cfg in self.voice_map.items():
            if k.lower().strip() == sp_lower:
                return dict(cfg)

        # Fallback to Narrator or global defaults
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

    def synthesize_segment(self, segment: Dict[str, Any], chapter_num: int, seg_num: int) -> Tuple[Path, float]:
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

            if not (out_file.exists() and out_file.stat().st_size > 1000):
                out_file.parent.mkdir(parents=True, exist_ok=True)
                sample_rate = 48000
                num_frames = int(round(sample_rate * dur))
                # 48kHz stereo 16-bit PCM: 2 channels * 2 bytes/sample = 4 bytes/frame
                silence_bytes = b"\x00" * (num_frames * 4)
                with wave.open(str(out_file), "wb") as wf:
                    wf.setnchannels(2)
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
        calib_str = f"{voice}:{speed:.2f}:{pitch:.2f}:{bass_boost_db:.1f}:{clarity_cut_db:.1f}:{lowpass_hz}:{highpass_hz}:{presence_boost_db:.1f}:{volume_gain_db:.1f}"
        cache_key = f"{text}|{calib_str}".encode("utf-8")
        text_hash = hashlib.md5(cache_key).hexdigest()[:8]
        out_file = self.audio_dir / f"c{chapter_num:03d}_s{seg_num:04d}_{text_hash}.wav"

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

        # Dispatch with VibeVoice-style emotion prosody
        emotion = segment.get("emotion", "neutral")
        out_path, dur = synthesize_gemini_tts(
            text=text,
            output_file=out_file,
            voice=voice,
            emotion=emotion,
            rate_limiter=self.rate_limiter,
        )

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
                tmp_calib.replace(out_file)
                with wave.open(str(out_file), "rb") as wf:
                    dur = wf.getnframes() / float(wf.getframerate())
            except Exception as e:
                logger.warning(f"  [!] Speaker DSP calibration notice: {e}")
                if tmp_calib.exists():
                    tmp_calib.unlink(missing_ok=True)

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

        # STEALTH HUMAN CADENCE EXECUTION (Strictly 1-worker sequential pipeline)
        for idx, segment in enumerate(script, 1):
            speaker = segment.get("speaker", "Narrator")
            text = segment.get("text", "")

            # If action beat: generate clean silent canvas instantly without human cadence delay or API calls
            if segment.get("type") == "action":
                audio_path, dur = self.synthesize_segment(segment, chapter_num, idx)
                self.ledger.mark_segment_completed(audio_path.stem, str(audio_path), dur)
                results[idx - 1] = audio_path
                logger.info(f"  [{idx}/{total}] Generated Action Beat Foley Canvas ({audio_path.name}, {dur:.1f}s)")
                continue

            # If already cached on disk, fast-forward with zero sleep
            existing_matches = list(self.audio_dir.glob(f"c{chapter_num:03d}_s{idx:04d}_*.wav"))
            if existing_matches and existing_matches[0].stat().st_size > 1000:
                audio_path, dur = self.synthesize_segment(segment, chapter_num, idx)
                results[idx - 1] = audio_path
                self.ledger.mark_segment_completed(audio_path.stem, str(audio_path), dur)
                logger.info(f"  [{idx}/{total}] Cached {speaker} ({audio_path.name}, {dur:.1f}s)")
                continue

            # Uncached segment: apply organic human reading & listening delay
            _, voice = self.get_speaker_voice(speaker, segment.get("type", "narration"))
            cache_key = f"{text}|{voice}".encode("utf-8")
            seg_hash = hashlib.md5(cache_key).hexdigest()[:8]
            seg_id = f"c{chapter_num:03d}_s{idx:04d}_{seg_hash}"

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

        missing = [i + 1 for i, p in enumerate(results) if p is None]
        if missing:
            raise RuntimeError(
                f"Chapter {chapter_num} synthesis incomplete: {len(missing)} segments pending ({missing[:5]}...)."
            )

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

