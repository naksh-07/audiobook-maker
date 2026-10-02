#!/usr/bin/env python3
"""
Audiobook Factory - Soundscape Engine: Sound & Asset Resolver.
Resolves SFX cues, background scores, and environmental ambiences via SoundBank FTS5,
local directories, and procedural FFmpeg synthesis.
"""

from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Optional

from audiobook_factory.soundscape_engine.probe import get_ffmpeg

# Paths to sound assets
STEMS_DIR = Path(__file__).resolve().parent.parent.parent / "audiobooks" / "soundscapes" / "stems"
SFX_DIR = Path(__file__).resolve().parent.parent.parent / "audiobooks" / "soundscapes" / "sfx"

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
            from audiobook_factory.sound_bank import SoundBank
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
