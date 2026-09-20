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


def detect_chapter_mood(chapter_text: str, model: str | None = None) -> Dict[str, Any]:
    """
    Use Gemini Flash to analyze the emotional narrative and tone of a chapter/scene.
    Returns recommended mood profile, intensity, and music generation prompts.
    """
    from audiobook_factory.tts_dispatcher import global_key_pool
    api_key = global_key_pool.get_key()
    if not api_key:
        return {"mood": "default", "intensity": 0.5, "prompt": MOOD_PRESETS["default"]["musicgen_prompt"]}

    if not model:
        model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3-flash-preview")

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
        headers={
            "Content-Type": "application/json",
            "X-goog-api-key": api_key,
            "User-Agent": "AudiobookFactory/1.0",
        },
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


STEMS_DIR = Path(__file__).resolve().parent.parent / "audiobooks" / "soundscapes" / "stems"
SFX_DIR = Path(__file__).resolve().parent.parent / "audiobooks" / "soundscapes" / "sfx"

# Procedural FFmpeg audio expressions for zero-cost, zero-disk instant sound effects
PROCEDURAL_SFX = {
    "wind_gust": "anoisesrc=d=3.5:c=pink:r=48000:a=0.08,bandpass=f=400:w=300,tremolo=f=0.5:d=0.7,afade=t=in:ss=0:d=0.8,afade=t=out:st=2.2:d=1.3",
    "rain": "anoisesrc=d=6.0:c=pink:r=48000:a=0.04,lowpass=f=2500,afade=t=in:ss=0:d=1.0,afade=t=out:st=4.5:d=1.5",
    "thunder": "anoisesrc=d=3.5:c=brown:r=48000:a=0.2,lowpass=f=180,afade=t=in:ss=0:d=0.15,afade=t=out:st=0.8:d=2.7",
    "heartbeat": "sine=f=55:d=0.15[s1];sine=f=45:d=0.2[s2];[s1][s2]concat=n=2:v=0:a=1,volume=0.35,afade=t=out:st=0.2:d=0.15",
    "lamp_ignite": "anoisesrc=d=0.6:c=white:r=48000:a=0.15,bandpass=f=1200:w=800,afade=t=in:ss=0:d=0.05,afade=t=out:st=0.15:d=0.45",
}


_SOUND_BANK_INSTANCE = None


def get_sound_bank():
    """Module-level singleton for SoundBank SQLite connection."""
    global _SOUND_BANK_INSTANCE
    if _SOUND_BANK_INSTANCE is None:
        try:
            from .sound_bank import SoundBank
            _SOUND_BANK_INSTANCE = SoundBank()
        except Exception:
            return None
    return _SOUND_BANK_INSTANCE


def resolve_sfx_cue(
    cue_name: str,
    output_file: Path,
    duration_sec: float = 2.0,
) -> Path | None:
    """
    Resolves an SFX cue:
    1. Checks SoundBank SQLite FTS5 for matches across local sound bank.
    2. Checks SFX_DIR for matching local audio files (.wav, .mp3).
    3. Synthesizes a procedural audio cue via FFmpeg lavfi expressions if missing.
    """
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    cue_key = cue_name.lower().strip()

    # 1. Check SoundBank FTS5 catalog
    bank = get_sound_bank()
    if bank:
        try:
            hit = bank.resolve_sound(cue_key, category="SFX") or bank.resolve_sound(cue_key, category="FOL") or bank.resolve_sound(cue_key)
            if hit and hit.exists():
                return hit
        except Exception:
            pass

    # 2. Check local SFX directory
    for ext in (".wav", ".mp3", ".ogg", ".flac"):
        cand = SFX_DIR / f"{cue_key}{ext}"
        if cand.exists():
            return cand

    # 3. Check procedural FFmpeg recipes
    if cue_key in PROCEDURAL_SFX:
        filter_expr = PROCEDURAL_SFX[cue_key]
        ffmpeg = get_ffmpeg()
        output_file = Path(output_file).resolve()
        output_file.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            ffmpeg, "-y",
            "-f", "lavfi", "-i", filter_expr,
            "-t", f"{duration_sec:.2f}",
            "-c:a", "pcm_s16le",
            str(output_file)
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return output_file
        except Exception as e:
            print(f"  [!] Procedural SFX failed for '{cue_key}': {e}")

    return None


def resolve_ambient_score(
    mood: str,
    duration_sec: float,
    output_file: Path,
) -> Path:
    """
    Resolves background score:
    1. Checks SoundBank SQLite FTS5 for matching curated musical scores / ambiences.
    2. Checks STEMS_DIR for drop-in stem files.
    3. Synthesizes organic procedural ambient drone bed via FFmpeg.
    """
    STEMS_DIR.mkdir(parents=True, exist_ok=True)
    mood_key = mood.lower().strip()
    ffmpeg = get_ffmpeg()
    dur = max(duration_sec + 2.0, 5.0)

    # 1. Check SoundBank SQLite FTS5 index
    bank = get_sound_bank()
    if bank:
        try:
            hit = bank.resolve_sound(mood_key, category="MUS", prefer_mood=mood_key) or bank.resolve_sound(mood_key)
            if hit and hit.exists():
                print(f"  [+] Using Sound Bank track for '{mood_key}': {hit.name}")
                cmd = [
                    ffmpeg, "-y",
                    "-stream_loop", "-1",
                    "-i", str(hit),
                    "-t", f"{dur:.2f}",
                    "-af", f"afade=t=in:ss=0:d=2.5,afade=t=out:st={dur-3.0:.2f}:d=3.0,aresample=osr=48000",
                    "-c:a", "pcm_s16le",
                    str(output_file)
                ]
                try:
                    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    return output_file
                except Exception as e:
                    print(f"  [!] Sound bank track processing failed ({e}), checking stems...")
        except Exception:
            pass

    # 2. Check for user-provided custom stem files
    for ext in (".mp3", ".wav", ".m4a", ".flac", ".ogg"):
        stem_path = STEMS_DIR / f"{mood_key}{ext}"
        if stem_path.exists():
            print(f"  [+] Using custom ambient stem for '{mood_key}': {stem_path.name}")
            cmd = [
                ffmpeg, "-y",
                "-stream_loop", "-1",
                "-i", str(stem_path),
                "-t", f"{dur:.2f}",
                "-af", f"afade=t=in:ss=0:d=2.5,afade=t=out:st={dur-3.0:.2f}:d=3.0,aresample=osr=48000",
                "-c:a", "pcm_s16le",
                str(output_file)
            ]
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return output_file
            except Exception as e:
                print(f"  [!] Custom stem processing failed ({e}), falling back to procedural synthesis.")
                break

    # 3. Fallback to zero-cost procedural synthesis
    return generate_procedural_ambient_bed(mood, duration_sec, output_file)


def fetch_musicgen(
    prompt: str,
    duration_sec: float,
    output_file: Path,
) -> Path:
    """
    Synthesize ambient background bed (procedural / stem fallback).
    """
    return resolve_ambient_score("default", duration_sec, output_file)


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

    # Compute compression ratio and threshold dynamically from duck_attenuation_db
    attenuation = abs(duck_attenuation_db)
    ratio = max(2.0, min(20.0, attenuation / 2.0))
    threshold = max(0.02, min(0.12, 0.06 * (16.0 / max(4.0, attenuation))))

    # Sidechain compression filter chain:
    # 1. Loop BGM if shorter than vocal track, trim to vocal duration + 1.0s tail
    # 2. Sidechain compressor: uses vocal track (input 1) to attenuate BGM (input 0)
    # 3. Mix ducked BGM with vocals, preserving crisp speech intelligibility
    filter_complex = (
        f"[0:a]aloop=loop=-1:size=2e+09,atrim=0:{vocal_dur + 1.5:.2f},"
        f"volume=0.35,afade=t=in:ss=0:d=2.0,afade=t=out:st={vocal_dur-2.0:.2f}:d=3.5[bgm_trimmed];"
        f"[bgm_trimmed][1:a]sidechaincompress=threshold={threshold:.3f}:ratio={ratio:.1f}:attack={attack_ms}:release={release_ms}:knee=2.5[bgm_ducked];"
        f"[1:a]volume=1.0[voc_clean];"
        f"[bgm_ducked][voc_clean]amix=inputs=2:duration=first:dropout_transition=2[mixed];"
        f"[mixed]aresample=osr=48000,loudnorm=I=-19:TP=-1.5:LRA=11[out]"
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


def generate_chapter_soundscape_plan(
    chapter_text: str,
    script_data: list,
    model: str | None = None,
) -> Dict[str, Any]:
    """
    Generate a Director Soundscape JSON Plan via Gemini Flash.
    Maps screenplay segment index ranges to scene moods, audio stems, and SFX cues.
    """
    from audiobook_factory.tts_dispatcher import global_key_pool
    api_key = global_key_pool.get_key()
    total_segs = len(script_data) if script_data else 1

    if not api_key:
        return {
            "primary_mood": "default",
            "ducking_attenuation_db": -16.0,
            "scenes": [
                {
                    "scene_id": 1,
                    "segment_start": 1,
                    "segment_end": total_segs,
                    "mood": "default",
                    "stem": "default",
                    "ambient_volume": 0.25,
                    "description": "Default storytelling bed",
                }
            ],
            "sfx_cues": [],
        }

    if not model:
        model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3-flash-preview")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    # Sample screenplay segments for prompt context (compact)
    seg_summary = [
        {
            "index": s.get("index", idx + 1),
            "type": s.get("type", "narration"),
            "speaker": s.get("speaker", "Narrator"),
            "emotion": s.get("emotion", "neutral"),
            "text": s.get("text", "")[:70],
        }
        for idx, s in enumerate(script_data[:50])
    ]

    prompt = f"""You are an expert audio drama sound director.
Given this chapter's screenplay segments, produce a structured Soundscape JSON Plan.

Available Audio Stems (moods):
- "peaceful": Calm, warm acoustic or ambient pad (nature, morning, peaceful discussion)
- "mysterious": Eerie suspense, ancient ruins, investigation, curiosity, subtle low drone
- "tense": Heart-pounding suspense, urgency, darkness, danger, confrontation
- "emotional": Melancholic, poignant, reflective drama (sadness, memory, farewell)
- "epic": Grand, majestic orchestral swell (discovery, climax, triumph)
- "default": Warm cinematic lo-fi background bed

Available SFX Cues:
- "lamp_ignite", "wind_gust", "page_turn", "door_creak", "thunder", "footsteps", "heartbeat", "rain"

Screenplay Segments:
{json.dumps(seg_summary, ensure_ascii=False, indent=2)}

Output JSON Schema:
{{
  "primary_mood": "peaceful" | "mysterious" | "tense" | "emotional" | "epic" | "default",
  "ducking_attenuation_db": -16.0,
  "scenes": [
    {{
      "scene_id": 1,
      "segment_start": 1,
      "segment_end": int,
      "mood": "peaceful" | "mysterious" | "tense" | "emotional" | "epic" | "default",
      "stem": "peaceful" | "mysterious" | "tense" | "emotional" | "epic" | "default",
      "ambient_volume": float (between 0.2 and 0.4),
      "description": "Brief scene description"
    }}
  ],
  "sfx_cues": [
    {{
      "segment_index": int,
      "cue": str,
      "timing": "before" | "under" | "after",
      "volume": float (between 0.3 and 0.6)
    }}
  ]
}}
Return ONLY valid JSON.
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-goog-api-key": api_key,
            "User-Agent": "AudiobookFactory/1.0",
        },
        method="POST",
    )

    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=35.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(content)
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < max_retries - 1:
                wait_sec = 2.0 * (attempt + 1)
                print(f"  [WAIT] Gemini API HTTP {e.code}. Retrying in {wait_sec}s (Attempt {attempt+1}/{max_retries})...")
                time.sleep(wait_sec)
                continue
            print(f"[!] Soundscape plan generation HTTP error ({e.code}), using default profile.")
            break
        except Exception as e:
            print(f"[!] Soundscape plan generation failed ({e}), using default profile.")
            break

    return {
        "primary_mood": "default",
        "ducking_attenuation_db": -16.0,
        "scenes": [
            {
                "scene_id": 1,
                "segment_start": 1,
                "segment_end": total_segs,
                "mood": "default",
                "stem": "default",
                "ambient_volume": 0.25,
                "description": "Fallback ambient bed",
            }
        ],
        "sfx_cues": [],
    }


def render_chapter_soundscape(
    soundscape_plan: Dict[str, Any],
    total_duration: float,
    output_audio_file: Path,
    segment_durations: Optional[Dict[int, float]] = None,
) -> Path:
    """
    Renders a complete, multi-scene background ambient bed with optional SFX cues
    based on the Soundscape JSON Plan.
    """
    output_audio_file = Path(output_audio_file).resolve()
    output_audio_file.parent.mkdir(parents=True, exist_ok=True)
    scenes = soundscape_plan.get("scenes", [])
    primary_mood = soundscape_plan.get("primary_mood", "default")

    # Simple path: single scene or fallback
    if len(scenes) <= 1 or not segment_durations:
        stem = scenes[0].get("stem", primary_mood) if scenes else primary_mood
        return resolve_ambient_score(stem, total_duration, output_audio_file)

    # Multi-scene crossfading path
    ffmpeg = get_ffmpeg()
    temp_scene_files = []
    tmp_dir = output_audio_file.parent / "tmp_scenes"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        total_known_dur = sum(segment_durations.values()) if segment_durations else total_duration
        scale_factor = (total_duration / total_known_dur) if total_known_dur > 0 else 1.0

        for sc in scenes:
            sc_id = sc.get("scene_id", 1)
            start_seg = sc.get("segment_start", 1)
            end_seg = sc.get("segment_end", start_seg)
            stem = sc.get("stem", primary_mood)

            # Calculate scene duration
            sc_dur = sum(segment_durations.get(s_idx, 4.0) for s_idx in range(start_seg, end_seg + 1)) * scale_factor
            sc_dur = max(sc_dur, 4.0)

            sc_wav = tmp_dir / f"sc_{sc_id}_{stem}.wav"
            resolve_ambient_score(stem, sc_dur, sc_wav)
            temp_scene_files.append((sc_wav, sc_dur))

        # Concatenate scene stems with smooth crossfade
        if len(temp_scene_files) == 1:
            shutil.copyfile(temp_scene_files[0][0], output_audio_file)
        else:
            # Build FFmpeg acrossfade filter complex
            filter_parts = []
            inputs = []
            for idx, (sw, _) in enumerate(temp_scene_files):
                inputs.extend(["-i", str(sw)])

            curr_tag = "0"
            for i in range(1, len(temp_scene_files)):
                next_tag = f"sc_{i}" if i < len(temp_scene_files) - 1 else "out"
                filter_parts.append(f"[{curr_tag}][{i}]acrossfade=d=2.0:c1=tri:c2=tri[{next_tag}]")
                curr_tag = next_tag

            filter_str = ";".join(filter_parts)
            cmd = [
                ffmpeg, "-y",
                *inputs,
                "-filter_complex", filter_str,
                "-map", "[out]",
                "-t", f"{total_duration:.2f}",
                "-c:a", "pcm_s16le",
                str(output_audio_file)
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        return output_audio_file
    except Exception as e:
        print(f"  [!] Multi-scene crossfade failed ({e}), falling back to single primary stem.")
        return resolve_ambient_score(primary_mood, total_duration, output_audio_file)
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


def generate_project_soundscapes(project_dir: Path) -> Path:
    """Generates JSON soundscape plans for all chapters in project."""
    project_dir = Path(project_dir).resolve()
    scripts_dir = project_dir / "scripts"
    soundscapes_dir = project_dir / "soundscapes"
    soundscapes_dir.mkdir(parents=True, exist_ok=True)

    script_files = sorted(scripts_dir.glob("chapter_*_script.json"))
    if not script_files:
        raise FileNotFoundError(f"No screenplay scripts found in {scripts_dir}")

    print(f"[*] Building Soundscape JSON Plans for {len(script_files)} chapters...")
    for sf in script_files:
        chap_stem = sf.stem.replace("_script", "")
        plan_file = soundscapes_dir / f"{chap_stem}_soundscape.json"
        if plan_file.exists() and plan_file.stat().st_size > 50:
            print(f"  [-] Soundscape plan already exists: {plan_file.name} (Skipping)")
            continue

        with open(sf, "r", encoding="utf-8") as f:
            script_data = json.load(f)

        plan = generate_chapter_soundscape_plan("", script_data)
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        print(f"  [+] Soundscape plan generated -> {plan_file.name}")

    return soundscapes_dir

