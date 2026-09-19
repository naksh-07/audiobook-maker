#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.2: Dual-Engine TTS Dispatcher & Continuity Engine.
Routes speech segments to Google Gemini 3.1 Flash TTS or PC RTX 4050 Kokoro/Goonj server.
Maintains stateful character voice assignments and resume checkpoints.
"""

import os
import sys
import time
import json
import hashlib
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List


# Import local kokoro client if available
try:
    from kokoro_client import synthesize_speech as kokoro_synth, DEFAULT_API_URL as KOKORO_URL
except ImportError:
    kokoro_synth = None
    KOKORO_URL = "http://10.236.21.128:8880"


def get_gemini_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY is required for Gemini 3.1 TTS.")
    return key


def synthesize_gemini_tts(
    text: str,
    output_file: Path,
    voice: str = "Aoede",
    model: str = "gemini-3.1-flash-tts-preview",
) -> Path:
    """Synthesize speech using Google Gemini 3.1 Flash TTS."""
    api_key = get_gemini_api_key()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

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

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "AudiobookFactory/1.0"},
        method="POST"
    )

    import base64
    try:
        with urllib.request.urlopen(req, timeout=45.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            part = data["candidates"][0]["content"]["parts"][0]
            inline_data = part.get("inlineData", {})
            b64_audio = inline_data.get("data", "")
            raw_pcm = base64.b64decode(b64_audio)

            # Convert 24kHz raw PCM to WAV
            import wave
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(output_file), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(raw_pcm)

            return output_file
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Gemini TTS HTTP {e.code}: {err}")


def synthesize_kokoro_remote(
    text: str,
    output_file: Path,
    voice: str = "hi_meera",
    speed: float = 1.0,
    api_url: str = KOKORO_URL,
) -> Path:
    """Synthesize speech via laptop RTX 4050 Kokoro / Goonj server with auto sentence-chunking."""
    import re
    import shutil
    import subprocess

    output_file.parent.mkdir(parents=True, exist_ok=True)
    endpoint = f"{api_url}/v1/audio/speech"

    # StyleTTS2 handles strings under 220 chars natively
    if len(text) <= 220:
        payload = {"model": "kokoro", "input": text, "voice": voice, "speed": speed}
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            audio_bytes = resp.read()
        with open(output_file, "wb") as f:
            f.write(audio_bytes)
        return output_file

    # For longer passages: split into sentences on punctuation
    sentences = [s.strip() for s in re.split(r"(?<=[।\.?!])\s+", text) if s.strip()]
    if not sentences:
        sentences = [text]

    temp_files = []
    temp_dir = output_file.parent / f"tmp_{output_file.stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        for idx, sentence in enumerate(sentences):
            part_file = temp_dir / f"part_{idx:03d}.wav"
            payload = {"model": "kokoro", "input": sentence, "voice": voice, "speed": speed}
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                with open(part_file, "wb") as f:
                    f.write(resp.read())
            temp_files.append(part_file)

        # Stitch sentence WAVs with ffmpeg
        ffmpeg = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
        concat_list = temp_dir / "concat.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for tf in temp_files:
                f.write(f"file '{tf.resolve()}'\n")

        cmd = [
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(output_file)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output_file
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)



class TTSDispatcher:
    """Orchestrates speech synthesis with continuity memory and resume checkpoints."""

    def __init__(self, project_dir: Path, default_backend: str = "gemini_tts", default_voice: str = "Aoede"):
        self.project_dir = Path(project_dir).resolve()
        self.audio_dir = self.project_dir / "audio_chunks"
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.project_dir / "voice_registry.json"
        self.default_backend = default_backend
        self.default_voice = default_voice
        self.voice_map = self._load_voice_registry()

    def _load_voice_registry(self) -> Dict[str, Any]:
        if self.registry_file.exists():
            with open(self.registry_file, "r", encoding="utf-8") as f:
                return json.load(f)

        # Default voice assignments
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

    def synthesize_segment(self, segment: Dict[str, Any], chapter_num: int, seg_num: int) -> Path:
        """Synthesize a single speech segment with resume checkpointing."""
        text = segment.get("text", "").strip()
        if not text:
            raise ValueError("Empty segment text")

        speaker = segment.get("speaker", "Narrator")
        cfg = self.voice_map.get(speaker, self.voice_map.get("Narrator"))
        backend = cfg.get("backend", self.default_backend)
        voice = cfg.get("voice", self.default_voice)
        speed = float(cfg.get("speed", 1.0))

        # Checkpoint hash: includes text + voice + backend
        cache_key = f"{text}|{backend}|{voice}|{speed}".encode("utf-8")
        text_hash = hashlib.md5(cache_key).hexdigest()[:8]
        out_file = self.audio_dir / f"c{chapter_num:03d}_s{seg_num:04d}_{text_hash}.wav"

        # Resume checkpoint: skip if file already exists and valid
        if out_file.exists() and out_file.stat().st_size > 1000:
            return out_file

        # Dispatch
        if backend == "gemini_tts":
            synthesize_gemini_tts(text, out_file, voice=voice)
            # 4.5s pacing for free tier 15 RPM
            time.sleep(4.5)
        elif backend == "kokoro":
            synthesize_kokoro_remote(text, out_file, voice=voice, speed=speed)
        else:
            raise ValueError(f"Unknown TTS backend: {backend}")

        return out_file

    def synthesize_chapter_script(self, script_path: Path, chapter_num: int) -> List[Path]:
        """Synthesize all segments in a chapter script sequentially."""
        with open(script_path, "r", encoding="utf-8") as f:
            script = json.load(f)

        audio_files = []
        total = len(script)
        print(f"[*] Synthesizing Chapter {chapter_num} ({total} speech segments)...")

        for idx, segment in enumerate(script, 1):
            speaker = segment.get("speaker", "Narrator")
            try:
                audio_path = self.synthesize_segment(segment, chapter_num, idx)
                audio_files.append(audio_path)
                print(f"  [{idx}/{total}] Generated {speaker} ({audio_path.name})")
            except Exception as e:
                print(f"  [ERROR] Segment {idx} failed: {e}")
                raise e

        return audio_files
