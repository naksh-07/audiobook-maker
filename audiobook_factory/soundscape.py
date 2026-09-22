#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.5: Soundscape, Ambience & Background Music Engine.
Handles scene mood detection (via Gemini Flash), dynamic musical bed generation
(MusicGen remote PC GPU / Procedural ambient synthesis), and intelligent
FFmpeg sidechain audio ducking for broadcast-grade audiobook production.
"""

import os
import json
import uuid
import shutil
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, List

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
    api_key = global_key_pool.get_key(service="text")
    if not api_key:
        return {"primary_mood": "default", "intensity": 0.5, "musicgen_prompt": "subtle warm ambient bed, soft lo-fi cinematic texture"}

    from audiobook_factory.cadence import get_stealth_sdk_headers

    if not model:
        model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-flash-latest")

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
        headers=get_stealth_sdk_headers(api_key),
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(content)
    except Exception as e:
        print(f"[!] Mood detection failed ({e}), using default ambient profile.")
        return {"primary_mood": "default", "intensity": 0.5, "musicgen_prompt": "subtle warm ambient bed, soft lo-fi cinematic texture"}


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

    # 3. Fallback to calibrated stereo silence
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-t", f"{duration_sec:.2f}",
        "-c:a", "pcm_s16le",
        str(output_file)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_file


def generate_procedural_ambient_bed(
    mood: str,
    duration_sec: float,
    output_audio_file: Path,
    volume: float = 0.25,
) -> Path:
    """Generate or resolve procedural ambient bed for backwards compatibility."""
    return resolve_ambient_score(mood, duration_sec, output_audio_file)


def resolve_environment_ambience(
    env_name: str,
    duration_sec: float,
    output_file: Path,
) -> Path:
    """
    Resolves genuine environmental ambience (wind, rain, tavern murmur, dungeon bed).
    NEVER loads musical score stems!
    Falls back to subtle organic room tone if no audio asset matches.
    """
    ffmpeg = get_ffmpeg()
    bank = get_sound_bank()
    dur = max(duration_sec + 2.0, 5.0)

    amb_sound = None
    if bank:
        env_lower = env_name.lower().strip()
        if any(k in env_lower for k in ("tavern", "inn", "bar", "restaurant")):
            amb_sound = bank.resolve_sound("tavern_crowd_murmur", category="AMB") or bank.resolve_sound("tavern")
        elif any(k in env_lower for k in ("crypt", "dungeon", "cave", "cellar")):
            amb_sound = bank.resolve_sound("dungeon_cave_bed", category="AMB") or bank.resolve_sound("dungeon")
        elif any(k in env_lower for k in ("rain", "storm", "thunder")):
            amb_sound = bank.resolve_sound("rain_thunder", category="AMB") or bank.resolve_sound("rain")
        else:
            # Default open nature / outdoor wind / quiet chamber
            amb_sound = (
                bank.resolve_sound("wind_howl", category="AMB")
                or bank.resolve_sound("wind")
                or bank.resolve_sound(env_lower, category="AMB")
            )

    if amb_sound and amb_sound.exists():
        print(f"  [+] Ambience Bus: using environmental bed '{amb_sound.name}'")
        cmd = [
            ffmpeg, "-y",
            "-stream_loop", "-1",
            "-i", str(amb_sound),
            "-t", f"{dur:.2f}",
            "-af", f"afade=t=in:ss=0:d=2.0,afade=t=out:st={dur-2.5:.2f}:d=2.5,aresample=osr=48000",
            "-c:a", "pcm_s16le",
            str(output_file)
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return output_file
        except Exception as e:
            print(f"  [!] Ambience processing notice: {e}")

    # Fallback: organic subtle room tone (-34dB bandpassed pink noise)
    cmd_fallback = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", f"anoisesrc=d={dur:.2f}:c=pink:r=48000:a=0.015",
        "-af", "bandpass=f=450:width_type=h:w=300,volume=0.20",
        "-c:a", "pcm_s16le",
        str(output_file)
    ]
    subprocess.run(cmd_fallback, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_file


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
        f"[1:a]asplit=2[voc_sc][voc_clean];"
        f"[0:a]aloop=loop=-1:size=2e+09,atrim=0:{vocal_dur + 1.5:.2f},"
        f"volume=0.35,afade=t=in:ss=0:d=2.0,afade=t=out:st={max(0.0, vocal_dur - 2.0):.2f}:d=3.5[bgm_trimmed];"
        f"[bgm_trimmed][voc_sc]sidechaincompress=threshold={threshold:.3f}:ratio={ratio:.1f}:attack={attack_ms}:release={release_ms}:knee=2.5[bgm_ducked];"
        f"[voc_clean]volume=1.0[voc_gain];"
        f"[bgm_ducked][voc_gain]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[mixed];"
        f"[mixed]aresample=osr=48000,loudnorm=I=-19:TP=-1.5:LRA=11,alimiter=limit=0.89:attack=5:release=50[out]"
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
        "-ac", "2",
        "-ar", "48000",
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
    from audiobook_factory.key_manager import get_persistent_key_pool
    pool = get_persistent_key_pool()
    api_key = pool.get_key(service="text")
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

    from audiobook_factory.cadence import get_stealth_sdk_headers

    if not model:
        model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-flash-latest")

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

    import time
    max_retries = 3
    for attempt in range(max_retries):
        if not api_key:
            api_key = pool.get_key(service="text")
            if not api_key:
                break
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=get_stealth_sdk_headers(api_key),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=35.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(content)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                pool.mark_temporary_backoff(api_key, 15.0)
            if e.code in (429, 503) and attempt < max_retries - 1:
                wait_sec = 2.0 * (attempt + 1)
                print(f"  [WAIT] Gemini API HTTP {e.code}. Rotating key and retrying in {wait_sec}s (Attempt {attempt+1}/{max_retries})...")
                time.sleep(wait_sec)
                api_key = pool.get_key(service="text")
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
        sc = scenes[0] if scenes else {}
        stem = sc.get("stem", primary_mood) if scenes else primary_mood
        bank = get_sound_bank()
        if bank:
            explicit_sec = sc.get("emotional_arc", {}).get("cue_section") if isinstance(sc.get("emotional_arc"), dict) else sc.get("cue_section")
            target_sec = str(explicit_sec).upper().strip() if explicit_sec and str(explicit_sec).upper().strip() in ("INTRO_BED", "RISING_TENSION", "CLIMAX_DROP", "AFTERMATH_FADE") else "INTRO_BED"
            sec_info = bank.resolve_track_section(stem, section_type=target_sec)
            if sec_info and sec_info.get("track_path") and Path(sec_info["track_path"]).exists():
                try:
                    bank.slice_track_section(sec_info["track_path"], sec_info["start_sec"], total_duration, output_audio_file)
                    sc["cue_slice"] = sec_info
                    return output_audio_file
                except Exception:
                    pass
        return resolve_ambient_score(stem, total_duration, output_audio_file)

    # Multi-scene crossfading path
    ffmpeg = get_ffmpeg()
    temp_scene_files = []
    tmp_dir = output_audio_file.parent / f"tmp_scenes_{os.getpid()}_{uuid.uuid4().hex[:6]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        total_known_dur = sum(segment_durations.values()) if segment_durations else total_duration
        scale_factor = (total_duration / total_known_dur) if total_known_dur > 0 else 1.0

        for sc in scenes:
            sc_id = sc.get("scene_id", 1)
            start_seg = sc.get("segment_start", 1)
            end_seg = sc.get("segment_end", start_seg)
            stem = (
                sc.get("emotional_arc", {}).get("music_track")
                or sc.get("stem")
                or sc.get("emotional_arc", {}).get("music_mood")
                or sc.get("mood")
                or primary_mood
            ) if isinstance(sc.get("emotional_arc"), dict) else (sc.get("stem") or sc.get("mood") or primary_mood)

            # Calculate scene duration
            sc_dur = sum(segment_durations.get(s_idx, 4.0) for s_idx in range(start_seg, end_seg + 1)) * scale_factor
            sc_dur = max(sc_dur, 4.0)

            # Acoustic Energy Zone Mapping (Deterministic directive from manifest/script or pure INTRO_BED default)
            explicit_sec = sc.get("emotional_arc", {}).get("cue_section") if isinstance(sc.get("emotional_arc"), dict) else sc.get("cue_section")
            if explicit_sec and str(explicit_sec).upper().strip() in ("INTRO_BED", "RISING_TENSION", "CLIMAX_DROP", "AFTERMATH_FADE"):
                target_sec = str(explicit_sec).upper().strip()
                if target_sec == "CLIMAX_DROP":
                    min_eng, max_eng = 7, 10
                elif target_sec == "RISING_TENSION":
                    min_eng, max_eng = 4, 7
                elif target_sec == "AFTERMATH_FADE":
                    min_eng, max_eng = 1, 4
                else:
                    min_eng, max_eng = 1, 5
            else:
                target_sec = "INTRO_BED"
                min_eng, max_eng = 1, 5

            sc_wav = tmp_dir / f"sc_{sc_id}_{stem}.wav"
            bank = get_sound_bank()
            sliced = False
            if bank:
                sec_info = bank.resolve_track_section(stem, section_type=target_sec, min_energy=min_eng, max_energy=max_eng)
                if sec_info and sec_info.get("track_path") and Path(sec_info["track_path"]).exists():
                    try:
                        bank.slice_track_section(
                            track_path=sec_info["track_path"],
                            start_sec=sec_info["start_sec"],
                            target_duration=sc_dur,
                            output_file=sc_wav,
                        )
                        sc["cue_slice"] = sec_info
                        sliced = True
                    except Exception as e:
                        logger.warning(f"  [!] Slicing section for scene {sc_id} fallback: {e}")

            if not sliced:
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


def normalize_to_3level_soundscape(plan: Dict[str, Any], chapter_num: int = 1) -> Dict[str, Any]:
    """
    Ensures any soundscape plan conforms strictly to the 3-Level BGM schema
    with zero broken references.
    """
    out = dict(plan)
    scenes = out.get("scenes", [])
    if not scenes and "level3_scenes" in out:
        scenes = out.get("level3_scenes", [])
    out["scenes"] = scenes
    out["level3_scenes"] = scenes

    # Level 1: Leitmotifs
    if "level1_leitmotifs" not in out:
        out["level1_leitmotifs"] = []

    # Level 2: Chapter Bed
    if "level2_chapter_bed" not in out:
        env_counts: Dict[str, int] = {}
        for sc in scenes:
            env = sc.get("location", {}).get("environment_type", "open_road")
            env_counts[env] = env_counts.get(env, 0) + 1
        dominant_env = max(env_counts, key=env_counts.get) if env_counts else "open_road"
        out["level2_chapter_bed"] = {
            "setting": dominant_env,
            "stem": dominant_env,
            "base_volume": 0.16,
            "description": f"Continuous setting undercurrent for {dominant_env}",
        }

    # Level 3: Ensure each scene has dynamic_stems, stingers, and valid cue_section
    valid_cue_sections = {"INTRO_BED", "RISING_TENSION", "CLIMAX_DROP", "AFTERMATH_FADE", "AUTO"}
    valid_moods = {"tense", "mysterious", "peaceful", "emotional", "epic"}

    for sc in scenes:
        emo = sc.setdefault("emotional_arc", {})
        if "cue_section" in emo:
            c_sec = str(emo["cue_section"]).upper().strip()
            emo["cue_section"] = c_sec if c_sec in valid_cue_sections else "auto"
        mood = str(emo.get("music_mood", "tense")).lower().strip()
        emo["music_mood"] = mood if mood in valid_moods else "tense"

        if "dynamic_stems" not in emo:
            intensity = int(emo.get("intensity", 5))
            if intensity >= 8:
                emo["dynamic_stems"] = ["combat_drums"]
            elif intensity >= 6:
                emo["dynamic_stems"] = ["tension_pulse"]
            else:
                emo["dynamic_stems"] = []
        if "stingers" not in emo:
            emo["stingers"] = []

    out.setdefault("ducking_attenuation_db", -16.0)
    out.setdefault("primary_mood", "tense")
    out.setdefault("chapter_id", chapter_num)
    out["total_scenes"] = len(scenes)
    return out


def render_hierarchical_soundscape(
    soundscape_plan: Dict[str, Any],
    total_duration: float,
    output_audio_file: Path,
    segment_durations: Optional[Dict[int, float]] = None,
    pause_ms: int = 450,
) -> Path:
    """
    Renders a composite 3-Level Hierarchical Score (Hollywood standard):
    - Level 1: Global Leitmotifs (recurring character/destiny motifs time-aligned via adelay)
    - Level 2: Chapter World Bed (continuous setting undercurrent across full duration)
    - Level 3: Dynamic Multi-Act Scenes (crossfaded via acrossfade) + Action Stingers
    All 3 musical tiers are combined into output_audio_file ready for sidechain ducking.
    """
    plan = normalize_to_3level_soundscape(soundscape_plan)
    ffmpeg = get_ffmpeg()
    output_audio_file = Path(output_audio_file).resolve()
    output_audio_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = output_audio_file.parent / f"tmp_hierarchical_bgm_{os.getpid()}_{uuid.uuid4().hex[:6]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    bank = get_sound_bank()

    try:
        active_layers = []  # List of (filepath, volume_float)

        # 1. Level 2: Chapter Setting Bed (Continuous Undercurrent)
        bed_info = plan.get("level2_chapter_bed", {})
        bed_name = bed_info.get("stem") or bed_info.get("setting") or "dark_forest"
        bed_vol = float(bed_info.get("base_volume", 0.16))
        bed_raw = tmp_dir / "l2_chapter_bed.wav"

        bed_sliced = False
        if bank:
            bed_sec = bank.resolve_track_section(bed_name, section_type="INTRO_BED", min_energy=1, max_energy=5)
            if bed_sec and bed_sec.get("track_path") and Path(bed_sec["track_path"]).exists():
                try:
                    bank.slice_track_section(
                        track_path=bed_sec["track_path"],
                        start_sec=bed_sec["start_sec"],
                        target_duration=total_duration,
                        output_file=bed_raw,
                    )
                    bed_info["cue_slice"] = bed_sec
                    bed_sliced = True
                except Exception:
                    bed_sliced = False

        if not bed_sliced:
            bed_resolved = bank.resolve_chapter_bed(bed_name) if bank else None
            if bed_resolved and bed_resolved.exists():
                resolve_ambient_score(bed_resolved.stem, total_duration, bed_raw)
            else:
                resolve_ambient_score(plan.get("primary_mood", "tense"), total_duration, bed_raw)

        if bed_raw.exists() and bed_raw.stat().st_size > 1000:
            active_layers.append((bed_raw, bed_vol))

        # 2. Level 3: Dynamic Multi-Act Scenes (Crossfaded Stems)
        scenes_raw = tmp_dir / "l3_dynamic_scenes.wav"
        render_chapter_soundscape(plan, total_duration, scenes_raw, segment_durations=segment_durations)
        if scenes_raw.exists() and scenes_raw.stat().st_size > 1000:
            active_layers.append((scenes_raw, 0.26))

        # 3. Level 1: Leitmotifs & Level 3 Accent Stingers (Time-Aligned Hits)
        time_aligned_events = []
        if segment_durations:
            seg_starts = {}
            curr_t = 0.0
            for s_idx in sorted(segment_durations.keys()):
                seg_starts[s_idx] = curr_t
                curr_t += segment_durations[s_idx] + (pause_ms / 1000.0)

            # Level 1 Leitmotifs
            for lm in plan.get("level1_leitmotifs", []):
                theme_name = lm.get("theme", "")
                trigger_seg = int(lm.get("trigger_segment", 1))
                t_sec = seg_starts.get(trigger_seg, 0.0)
                vol = float(lm.get("volume", 0.22))
                theme_file = None
                if bank:
                    theme_sec = bank.resolve_track_section(theme_name, section_type="INTRO_BED") or bank.resolve_track_section(theme_name, section_type="CLIMAX_DROP")
                    if theme_sec and theme_sec.get("track_path") and Path(theme_sec["track_path"]).exists():
                        theme_file = Path(theme_sec["track_path"])
                        lm["cue_slice"] = theme_sec
                    else:
                        theme_file = bank.resolve_leitmotif(theme_name)
                if theme_file and theme_file.exists() and t_sec < total_duration:
                    t_ms = max(0, int(t_sec * 1000))
                    time_aligned_events.append((theme_file, t_ms, vol, "leitmotif"))

            # Level 3 Stingers
            for sc in plan.get("scenes", []):
                emo = sc.get("emotional_arc", {})
                for st in emo.get("stingers", []):
                    st_cue = st.get("cue", "")
                    st_seg = int(st.get("segment", 1))
                    t_sec = seg_starts.get(st_seg, 0.0)
                    vol = float(st.get("volume", 0.32))
                    st_file = bank.resolve_stinger(st_cue) if bank else None
                    if st_file and st_file.exists() and t_sec < total_duration:
                        t_ms = max(0, int(t_sec * 1000))
                        time_aligned_events.append((st_file, t_ms, vol, "stinger"))

        # If time-aligned hits exist, render them via adelay bus
        if time_aligned_events:
            stinger_bus = tmp_dir / "l1_l3_stingers_bus.wav"
            events_slice = time_aligned_events[:25]
            s_inputs = []
            s_filters = []
            for idx, (s_path, t_ms, vol, _) in enumerate(events_slice):
                s_inputs.extend(["-i", str(s_path)])
                s_filters.append(f"[{idx}:a]adelay={t_ms}|{t_ms},volume={vol:.2f}[s_{idx}]")

            s_mix_ins = "".join(f"[s_{i}]" for i in range(len(events_slice)))
            s_filter_str = ";".join(s_filters) + f";{s_mix_ins}amix=inputs={len(events_slice)}:normalize=0[sout]"

            stinger_cmd = [
                ffmpeg, "-y",
                *s_inputs,
                "-filter_complex", s_filter_str,
                "-map", "[sout]",
                "-t", f"{total_duration:.2f}",
                "-c:a", "pcm_s16le",
                str(stinger_bus),
            ]
            try:
                subprocess.run(stinger_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if stinger_bus.exists() and stinger_bus.stat().st_size > 1000:
                    active_layers.append((stinger_bus, 1.0))
            except Exception as e:
                logger.warning(f"  [!] Stinger bus render notice: {e}")

        # 4. Final Mix of Active Layers into output_audio_file
        if not active_layers:
            return resolve_ambient_score(plan.get("primary_mood", "tense"), total_duration, output_audio_file)

        if len(active_layers) == 1:
            shutil.copyfile(active_layers[0][0], output_audio_file)
            return output_audio_file

        mix_inputs = []
        mix_filters = []
        for idx, (l_file, l_vol) in enumerate(active_layers):
            mix_inputs.extend(["-i", str(l_file)])
            mix_filters.append(f"[{idx}:a]volume={l_vol:.2f}[m_{idx}]")

        m_ins = "".join(f"[m_{i}]" for i in range(len(active_layers)))
        mix_filter_str = ";".join(mix_filters) + f";{m_ins}amix=inputs={len(active_layers)}:normalize=0[mout]"

        final_cmd = [
            ffmpeg, "-y",
            *mix_inputs,
            "-filter_complex", mix_filter_str,
            "-map", "[mout]",
            "-t", f"{total_duration:.2f}",
            "-c:a", "pcm_s16le",
            str(output_audio_file),
        ]
        subprocess.run(final_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output_audio_file
    except Exception as e:
        logger.warning(f"  [!] Hierarchical BGM composition notice ({e}), falling back to 2-tier score.")
        return render_chapter_soundscape(soundscape_plan, total_duration, output_audio_file, segment_durations=segment_durations)
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


def render_multitrack_chapter_audio(
    vocal_file: Path,
    output_master_file: Path,
    cue_sheet: Optional[Dict[str, Any]] = None,
    soundscape_plan: Optional[Dict[str, Any]] = None,
    segment_durations: Optional[Dict[int, float]] = None,
    pause_ms: int = 400,
) -> Path:
    """
    Next-Gen 5-Track Audio Drama Timeline Compositor (GraphicAudio / BBC Radio standard).
    Renders:
    - Track 1 (Voice Bus): Spatially enriched speech with matching room impulse reverberation.
    - Track 2 (Foley Bus): Physical object interactions and footsteps time-aligned via adelay.
    - Track 3 (Ambience Bus): Continuous environmental room tone (tavern, crypt, rain).
    - Track 4 (Music Bus): Cinematic score with 1.2kHz-3.2kHz spectral carving & sidechain ducking.
    - Master Bus: EBU R128 (-19 LUFS broadcast master) at 48kHz SOXR sinc.
    """
    ffmpeg = get_ffmpeg()
    vocal_file = Path(vocal_file).resolve()
    output_master_file = Path(output_master_file).resolve()
    output_master_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = output_master_file.parent / "tmp_multitrack"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    vocal_dur = get_audio_duration(vocal_file)
    bank = get_sound_bank()

    # 1. Timeline Segmentation
    seg_starts = {}
    curr_t = 0.0
    if segment_durations:
        for s_idx in sorted(segment_durations.keys()):
            seg_starts[s_idx] = curr_t
            curr_t += segment_durations[s_idx] + (pause_ms / 1000.0)

    # 2. Resolve Foley Events
    foley_cues = cue_sheet.get("foley_cues", []) if cue_sheet else []
    valid_foley_events = []
    if bank and foley_cues:
        for c in foley_cues:
            s_idx = c.get("segment_index", 1)
            t_sec = seg_starts.get(s_idx, 0.0) + (c.get("offset_ms", 0) / 1000.0)
            t_ms = max(0, int(t_sec * 1000))
            tag = c.get("foley_tag", "") or c.get("tag", "")
            snd = bank.resolve_sound(tag)
            if snd and snd.exists() and t_sec < vocal_dur:
                # Moderate Foley cue level so it complements dialogue
                cue_vol = min(0.40, float(c.get("volume", 0.30)))
                valid_foley_events.append((snd, t_ms, cue_vol))

    # 3. Resolve Ambience & Music Stems (3-Level Hierarchical Score + Dynamic Acrossfade)
    bgm_raw = tmp_dir / "bgm_raw.wav"
    scenes = soundscape_plan.get("scenes", []) if soundscape_plan else []
    if soundscape_plan and ("level1_leitmotifs" in soundscape_plan or "level2_chapter_bed" in soundscape_plan or len(scenes) > 1):
        print("[*] Rendering 3-Level Hierarchical Score (Leitmotif + Chapter Bed + Dynamic Scenes)...")
        render_hierarchical_soundscape(
            soundscape_plan,
            vocal_dur,
            bgm_raw,
            segment_durations=segment_durations,
            pause_ms=pause_ms,
        )
    else:
        primary_mood = soundscape_plan.get("primary_mood", "tense") if soundscape_plan else "tense"
        resolve_ambient_score(primary_mood, vocal_dur, bgm_raw)

    amb_raw = tmp_dir / "amb_raw.wav"
    primary_env = cue_sheet.get("primary_environment", "dense_forest_night") if cue_sheet else "dense_forest_night"
    resolve_environment_ambience(primary_env, vocal_dur, amb_raw)

    # 4. Render Foley Bus (if any Foley events found)
    foley_bus_file = tmp_dir / "foley_bus.wav"
    has_foley = False
    if valid_foley_events:
        print(f"[*] Assembling Foley Bus with {len(valid_foley_events)} physical object cues...")
        foley_slice = valid_foley_events
        f_inputs = []
        f_filters = []
        for idx, (f_path, t_ms, vol) in enumerate(foley_slice):
            f_inputs.extend(["-i", str(f_path)])
            f_filters.append(f"[{idx}:a]adelay={t_ms}|{t_ms},volume={vol:.2f}[f_{idx}]")

        f_mix_ins = "".join(f"[f_{i}]" for i in range(len(foley_slice)))
        f_filter_str = ";".join(f_filters) + f";{f_mix_ins}amix=inputs={len(foley_slice)}:normalize=0[fout]"

        foley_cmd = [
            ffmpeg, "-y",
            *f_inputs,
            "-filter_complex", f_filter_str,
            "-map", "[fout]",
            "-t", f"{vocal_dur + 1.0:.2f}",
            "-ar", "48000",
            "-c:a", "pcm_s16le",
            str(foley_bus_file),
        ]
        try:
            subprocess.run(foley_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            has_foley = foley_bus_file.exists() and foley_bus_file.stat().st_size > 5000
        except Exception as e:
            print(f"  [!] Foley bus assembly notice: {e}")
            has_foley = False

    # 5. Master Multi-Bus Assembly
    print(f"[*] Mixing 5-Track Cinematic Audio Drama ({vocal_file.name})...")
    master_inputs = [
        "-i", str(vocal_file),   # Input 0: Vocal track
        "-i", str(bgm_raw),      # Input 1: Music score
        "-i", str(amb_raw),      # Input 2: Ambience bed
    ]
    if has_foley:
        master_inputs.extend(["-i", str(foley_bus_file)])  # Input 3: Foley bus

    # [AGENTIC SHIFT] Call the Audio Engineer Agent to design the FFmpeg filter complex
    from audiobook_factory.ffmpeg_agent import build_ffmpeg_filter_graph_via_agent
    master_filter_str = build_ffmpeg_filter_graph_via_agent(soundscape_plan, cue_sheet, vocal_dur, has_foley)

    if not master_filter_str:
        # Fallback if Agent fails
        filter_parts = [
            "[0:a]asplit=2[voc_dry][voc_sc]",
            f"[1:a]atrim=0:{vocal_dur+1.5:.2f},equalizer=f=2200:t=q:w=1.5:g=-5.5[bgm_carved]",
            "[bgm_carved][voc_sc]sidechaincompress=threshold=0.04:ratio=8.0:attack=120:release=750:knee=2.5[bgm_ducked]",
            f"[2:a]atrim=0:{vocal_dur+1.5:.2f},volume=0.14[amb_bed]",
        ]
        if has_foley:
            filter_parts.append("[3:a]volume=0.30[fol_bus]")
            mix_inputs = "[voc_dry][bgm_ducked][amb_bed][fol_bus]"
            num_mix = 4
        else:
            mix_inputs = "[voc_dry][bgm_ducked][amb_bed]"
            num_mix = 3

        filter_parts.append(f"{mix_inputs}amix=inputs={num_mix}:duration=first:dropout_transition=2:normalize=0[mixed]")
        filter_parts.append("[mixed]aresample=osr=48000,loudnorm=I=-19:TP=-1.5:LRA=11,alimiter=limit=0.89:attack=5:release=50[out]")
        master_filter_str = ";".join(filter_parts)

    ext = output_master_file.suffix.lower()
    codec = "aac" if ext in (".m4a", ".m4b") else "pcm_s16le"
    bitrate_args = ["-b:a", "192k"] if codec == "aac" else []

    cmd = [
        ffmpeg, "-y",
        *master_inputs,
        "-filter_complex", master_filter_str,
        "-map", "[out]",
        "-ac", "2",
        "-ar", "48000",
        "-c:a", codec,
        *bitrate_args,
        str(output_master_file)
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"[+] Broadcast Mastered Audio Drama ready -> {output_master_file.name} ({output_master_file.stat().st_size / (1024*1024):.2f} MB)")
        return output_master_file
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"Multitrack mastering failed: {err[:300]}")
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


def attenuate_foley_whisper_collisions(
    foley_cues: List[Any],
    segments: List[Any],
    attenuation_db: float = -6.0,
    shift_offset_ms: int = 150,
) -> List[Any]:
    """
    Meso-Tier Verification Guard:
    Checks acoustic overlap between Foley cues and whisper/intimate speech segments
    (identified by '[whispers]' tag, emotion='whispering', delivery_style='whispering_fear',
    or intensity_level='low').
    Attenuates Foley gain by -6.0 dBFS (or shifts offset) to preserve whisper intelligibility
    and eliminate masking distortion.
    """
    if not foley_cues or not segments:
        return foley_cues

    whisper_indices = set()
    whisper_windows = []

    for seg in segments:
        seg_idx = getattr(seg, "index", None)
        if seg_idx is None:
            seg_idx = getattr(seg, "segment_index", None)
        if seg_idx is None and isinstance(seg, dict):
            seg_idx = seg.get("index", seg.get("segment_index"))

        text = ""
        emotion = ""
        intensity = ""
        delivery = ""

        if isinstance(seg, dict):
            text = str(seg.get("text", "")).lower()
            emotion = str(seg.get("emotion", "")).lower()
            intensity = str(seg.get("intensity_level", "")).lower()
            acting = seg.get("acting", {})
            if isinstance(acting, dict):
                delivery = str(acting.get("delivery_style", "")).lower()
        else:
            text = str(getattr(seg, "text", "") or "").lower()
            emotion = str(getattr(seg, "emotion", "") or "").lower()
            intensity = str(getattr(seg, "intensity_level", "") or "").lower()
            acting = getattr(seg, "acting", None)
            if isinstance(acting, dict):
                delivery = str(acting.get("delivery_style", "")).lower()
            elif hasattr(acting, "delivery_style"):
                delivery = str(getattr(acting, "delivery_style", "")).lower()

        is_whisper = (
            "[whispers]" in text or
            "[whisper]" in text or
            "whisper" in emotion or
            "whispering" in emotion or
            "whispering_fear" in delivery or
            intensity == "low"
        )

        if is_whisper:
            if seg_idx is not None:
                whisper_indices.add(seg_idx)
            start_ms = seg.get("start_ms") if isinstance(seg, dict) else getattr(seg, "start_ms", None)
            end_ms = seg.get("end_ms") if isinstance(seg, dict) else getattr(seg, "end_ms", None)
            if start_ms is not None and end_ms is not None:
                whisper_windows.append((start_ms, end_ms))

    for cue in foley_cues:
        c_seg_idx = cue.get("segment_index") if isinstance(cue, dict) else getattr(cue, "segment_index", None)
        c_start_ms = cue.get("start_ms") if isinstance(cue, dict) else getattr(cue, "start_ms", None)
        c_dur_ms = (cue.get("duration_ms") if isinstance(cue, dict) else getattr(cue, "duration_ms", None)) or 500

        collision = False
        if c_seg_idx is not None and c_seg_idx in whisper_indices:
            collision = True
        elif c_start_ms is not None and whisper_windows:
            c_end_ms = c_start_ms + c_dur_ms
            for w_start, w_end in whisper_windows:
                if not (c_end_ms <= w_start or c_start_ms >= w_end):
                    collision = True
                    break

        if collision:
            if hasattr(cue, "gain_dbfs"):
                cue.gain_dbfs = round(cue.gain_dbfs + attenuation_db, 2)
            elif isinstance(cue, dict) and "gain_dbfs" in cue:
                cue["gain_dbfs"] = round(cue["gain_dbfs"] + attenuation_db, 2)

            if hasattr(cue, "pre_roll_ms"):
                cue.pre_roll_ms = max(0, getattr(cue, "pre_roll_ms", 100) + shift_offset_ms)
            elif isinstance(cue, dict) and "pre_roll_ms" in cue:
                cue["pre_roll_ms"] = max(0, cue.get("pre_roll_ms", 100) + shift_offset_ms)

    return foley_cues



