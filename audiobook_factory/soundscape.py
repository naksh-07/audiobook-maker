#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.5: Soundscape, Ambience & Background Music Engine.
Handles scene mood detection (via Gemini Flash), dynamic musical bed generation
(MusicGen remote PC GPU / Procedural ambient synthesis), and intelligent
FFmpeg sidechain audio ducking for broadcast-grade audiobook production.
"""

import os
import json
import shutil
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional

# Default mood definitions and musical cues
MOOD_PRESETS = {
    "peaceful": {
        "description": "Gentle, calm, warm acoustic or ambient pad",
        "musicgen_prompt": "gentle acoustic ambient pad, warm calming strings, peaceful meditation background, subtle, no drums, low tempo",
        "synth_notes": [130.81, 164.81, 196.00],  # C3, E3, G3 (C Major)
        "lowpass_hz": 800,
    },
    "mysterious": {
        "description": "Eerie suspense, curiosity, subtle low drone",
        "musicgen_prompt": "slow mysterious ambient cello and low strings, eerie suspenseful atmosphere, dark drone, cinematic thriller, no drums",
        "synth_notes": [110.00, 130.81, 155.56],  # A2, C3, Eb3 (A Diminished / Tension)
        "lowpass_hz": 650,
    },
    "tense": {
        "description": "Heart-pounding suspense, urgency, dark atmospheric tone",
        "musicgen_prompt": "tense dark cinematic drone, subtle pulsing heartbeat, dark atmospheric cello, suspenseful underscore, quiet",
        "synth_notes": [82.41, 98.00, 123.47],   # E2, G2, B2 (E Minor)
        "lowpass_hz": 500,
    },
    "emotional": {
        "description": "Melancholic, poignant, heartfelt storytelling",
        "musicgen_prompt": "emotional melancholic piano and warm cello, poignant reflective background music, cinematic drama, subtle, slow",
        "synth_notes": [110.00, 146.83, 174.61],  # A2, D3, F3 (D Minor inversion)
        "lowpass_hz": 900,
    },
    "epic": {
        "description": "Grand, triumphant, expansive world-building",
        "musicgen_prompt": "epic orchestral atmospheric swell, deep brass pads and strings, majestic cinematic soundscape, ambient, slow build",
        "synth_notes": [130.81, 196.00, 261.63],  # C3, G3, C4 (Open Power Fifth)
        "lowpass_hz": 1200,
    },
    "default": {
        "description": "Subtle warm cinematic lo-fi background bed",
        "musicgen_prompt": "subtle warm ambient bed, soft lo-fi cinematic texture, quiet storytelling underscore, acoustic resonance, no drums",
        "synth_notes": [110.00, 164.81, 196.00],  # A2, E3, G3
        "lowpass_hz": 750,
    },
}


def get_ffmpeg() -> str:
    ffmpeg_bin = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
    if not os.path.exists(ffmpeg_bin):
        raise FileNotFoundError("FFmpeg executable not found in PATH.")
    return ffmpeg_bin


def get_audio_duration(file_path: Path) -> float:
    """Extract audio duration in seconds using ffprobe or ffmpeg."""
    file_path = Path(file_path).resolve()
    ffprobe = shutil.which("ffprobe") or "/usr/bin/ffprobe"
    if os.path.exists(ffprobe):
        cmd = [
            ffprobe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path)
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(res.stdout.strip())
        except Exception:
            pass

    # Fallback using ffmpeg stderr inspection
    ffmpeg = get_ffmpeg()
    cmd = [ffmpeg, "-i", str(file_path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", res.stderr)
    if m:
        hours, mins, secs = m.groups()
        return int(hours) * 3600 + int(mins) * 60 + float(secs)
    return 60.0


def detect_chapter_mood(chapter_text: str, model: str = "gemini-2.5-flash") -> Dict[str, Any]:
    """
    Use Gemini Flash to analyze the emotional narrative and tone of a chapter/scene.
    Returns recommended mood profile, intensity, and music generation prompts.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return {"mood": "default", "intensity": 0.5, "prompt": MOOD_PRESETS["default"]["musicgen_prompt"]}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    # Sample beginning and climax for analysis (keep token size lean)
    sample_snippet = chapter_text[:2500]
    prompt = (
        "You are an expert audio director for cinematic audiobooks. "
        "Analyze the following excerpt from a book chapter and return a JSON object with: "
        "'primary_mood' (strictly one of: peaceful, mysterious, tense, emotional, epic, default), "
        "'intensity' (float from 0.1 to 1.0), "
        "'summary' (1 sentence summary of the scene atmosphere), "
        "'musicgen_prompt' (a detailed prompt for Meta MusicGen: instrumental ambient background score, NO vocals, NO loud drums, describing instruments and tempo).\n\n"
        f"Excerpt:\n{sample_snippet}\n\n"
        "Return ONLY raw valid JSON."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(content)
    except Exception as e:
        print(f"[!] Mood detection failed ({e}), using default ambient profile.")
        return {"primary_mood": "default", "intensity": 0.5, "musicgen_prompt": MOOD_PRESETS["default"]["musicgen_prompt"]}


def generate_procedural_ambient_bed(
    mood: str,
    duration_sec: float,
    output_file: Path,
) -> Path:
    """
    Synthesize an organic, zero-latency ambient drone bed using pure FFmpeg audio expressions.
    Requires 0 external APIs and 0 internet bandwidth; produces warm, soothing, non-intrusive harmonic beds.
    """
    ffmpeg = get_ffmpeg()
    output_file = Path(output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    preset = MOOD_PRESETS.get(mood.lower(), MOOD_PRESETS["default"])
    notes = preset.get("synth_notes", [110.00, 164.81, 196.00])
    lpf = preset.get("lowpass_hz", 750)

    # Construct harmonic tri-tone sine waves with gentle detuning and slow tremolo
    # f1, f2, f3 generate harmonic warmth; anoisesrc adds subtle vinyl/room air
    f1, f2, f3 = notes[0], notes[1], notes[2]
    dur = max(duration_sec + 4.0, 5.0)

    filter_complex = (
        f"sine=frequency={f1}:duration={dur}[s1];"
        f"sine=frequency={f2}:duration={dur}[s2];"
        f"sine=frequency={f3}:duration={dur}[s3];"
        f"anoisesrc=d={dur}:c=pink:r=48000:a=0.003[noise];"
        f"[s1]volume=0.08[v1];"
        f"[s2]volume=0.06[v2];"
        f"[s3]volume=0.05[v3];"
        f"[v1][v2][v3][noise]amix=inputs=4:duration=longest[raw];"
        f"[raw]lowpass=f={lpf},flanger=delay=15:depth=4:speed=0.2:shape=sinusoidal,"
        f"tremolo=f=0.15:d=0.3,volume=0.25,"
        f"afade=t=in:ss=0:d=3.0,afade=t=out:st={dur-3.0}:d=3.0[out]"
    )

    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-t", f"{duration_sec:.2f}",
        "-c:a", "pcm_s16le",
        str(output_file)
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output_file
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Procedural ambient synthesis failed: {e.stderr.decode('utf-8', errors='ignore')}")


def fetch_remote_musicgen(
    prompt: str,
    duration_sec: float,
    output_file: Path,
    api_url: str = "http://10.236.21.128:8881/v1/audio/music",
) -> Path:
    """
    Synthesize high-fidelity instrumental music using Meta MusicGen running
    on the PC / Laptop RTX 4050 workstation.
    """
    output_file = Path(output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "prompt": prompt,
        "duration": int(min(duration_sec, 300)),
        "temperature": 1.0,
        "top_k": 250,
    }

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120.0) as resp:
            audio_bytes = resp.read()
            with open(output_file, "wb") as f:
                f.write(audio_bytes)
            return output_file
    except Exception as e:
        print(f"[!] Remote MusicGen failed ({e}), falling back to procedural ambient bed...")
        return generate_procedural_ambient_bed("default", duration_sec, output_file)


def apply_dynamic_sidechain_ducking(
    vocal_file: Path,
    bgm_file: Path,
    output_file: Path,
    duck_attenuation_db: float = -16.0,
    attack_ms: int = 150,
    release_ms: int = 850,
) -> Path:
    """
    Apply broadcast-grade Dynamic Sidechain Compression.
    Ducks the BGM volume automatically by `duck_attenuation_db` whenever vocal dialogue is active,
    and smoothly allows the background score to swell during sentence and chapter pauses.
    """
    ffmpeg = get_ffmpeg()
    vocal_file = Path(vocal_file).resolve()
    bgm_file = Path(bgm_file).resolve()
    output_file = Path(output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    vocal_dur = get_audio_duration(vocal_file)

    # Sidechain compression filter chain:
    # 1. Loop BGM if shorter than vocal track, trim to vocal duration + 1.0s tail
    # 2. Sidechain compressor: uses vocal track (input 1) to attenuate BGM (input 0)
    # 3. Mix ducked BGM with vocals, preserving crisp speech intelligibility
    filter_complex = (
        f"[0:a]aloop=loop=-1:size=2e+09,atrim=0:{vocal_dur + 1.5:.2f},"
        f"volume=0.35,afade=t=in:ss=0:d=2.0,afade=t=out:st={vocal_dur-2.0:.2f}:d=3.5[bgm_trimmed];"
        f"[bgm_trimmed][1:a]sidechaincompress=threshold=0.06:ratio=8:attack={attack_ms}:release={release_ms}:knee=2.5[bgm_ducked];"
        f"[1:a]volume=1.0[voc_clean];"
        f"[bgm_ducked][voc_clean]amix=inputs=2:duration=first:dropout_transition=2[mixed];"
        f"[mixed]aresample=resampler=soxr:osr=48000,loudnorm=I=-19:TP=-1.5:LRA=11[out]"
    )

    ext = output_file.suffix.lower()
    codec = "aac" if ext in (".m4a", ".m4b") else "pcm_s16le"
    bitrate_args = ["-b:a", "192k"] if codec == "aac" else []

    cmd = [
        ffmpeg, "-y",
        "-i", str(bgm_file),
        "-i", str(vocal_file),
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:a", codec,
        *bitrate_args,
        str(output_file)
    ]

    print(f"[*] Applying dynamic sidechain ducking ({vocal_file.name} + {bgm_file.name}) -> {output_file.name}...")
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"[+] Ducked master audio ready -> {output_file}")
        return output_file
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"Sidechain ducking failed: {err}")
