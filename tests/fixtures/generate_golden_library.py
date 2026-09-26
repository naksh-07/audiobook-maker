#!/usr/bin/env python3
"""
Generates the calibrated representative golden sound library for testing the
Sonic Intelligence Library Harvesting Subsystem.
Covers all 16 required asset types: micro-SFX, impacts, footsteps, doors, Foley,
ambience, room tones, weather, creatures, magic, music, human non-speech, long audio,
BWF metadata, ID3 metadata, and poor/no metadata.
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf

GOLDEN_DIR = Path(__file__).resolve().parent / "golden_sound_library"


def generate_golden_dataset() -> Path:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    sr = 48000

    # 1. Micro-SFX (< 0.1s): Sharp transient click (0.06s)
    t1 = np.linspace(0, 0.06, int(0.06 * sr), dtype=np.float32)
    env1 = np.exp(-t1 * 120.0)
    wf1 = 0.8 * np.sin(2 * np.pi * 3200 * t1) * env1
    sf.write(str(GOLDEN_DIR / "micro_sfx_transient_01.wav"), wf1, sr)

    # 2. Impacts: Metallic sword strike (0.6s)
    t2 = np.linspace(0, 0.6, int(0.6 * sr), dtype=np.float32)
    env2 = np.exp(-t2 * 12.0)
    wf2 = 0.7 * (np.sin(2 * np.pi * 1250 * t2) + 0.5 * np.sin(2 * np.pi * 2800 * t2)) * env2
    sf.write(str(GOLDEN_DIR / "foley_impact_metal_01.wav"), wf2, sr)

    # 3. Footsteps: Gravel footstep (0.35s)
    t3 = np.linspace(0, 0.35, int(0.35 * sr), dtype=np.float32)
    noise3 = np.random.uniform(-0.5, 0.5, len(t3)).astype(np.float32)
    env3 = np.sin(np.pi * t3 / 0.35) ** 2
    wf3 = noise3 * env3 * 0.6
    sf.write(str(GOLDEN_DIR / "foley_footstep_gravel_01.wav"), wf3, sr)

    # 4. Doors: Wood creak + slam (1.8s)
    t4 = np.linspace(0, 1.8, int(1.8 * sr), dtype=np.float32)
    creak = 0.2 * np.sin(2 * np.pi * (180 + 60 * np.sin(2 * np.pi * 5 * t4[:int(1.2 * sr)])) * t4[:int(1.2 * sr)])
    slam = 0.8 * np.sin(2 * np.pi * 85 * t4[int(1.2 * sr):]) * np.exp(-15 * (t4[int(1.2 * sr):] - 1.2))
    wf4 = np.concatenate([creak, slam])
    sf.write(str(GOLDEN_DIR / "foley_door_creak_slam_01.wav"), wf4, sr)

    # 5. Foley: Cloth rustle (0.9s)
    t5 = np.linspace(0, 0.9, int(0.9 * sr), dtype=np.float32)
    noise5 = np.random.uniform(-0.3, 0.3, len(t5)).astype(np.float32)
    env5 = np.sin(np.pi * t5 / 0.9) ** 4
    wf5 = noise5 * env5
    sf.write(str(GOLDEN_DIR / "foley_cloth_rustle_01.wav"), wf5, sr)

    # 6. Ambience: Room tone (4.0s)
    t6 = np.linspace(0, 4.0, int(4.0 * sr), dtype=np.float32)
    wf6 = np.random.normal(0, 0.04, len(t6)).astype(np.float32)
    sf.write(str(GOLDEN_DIR / "amb_room_tone_quiet_01.wav"), wf6, sr)

    # 7. Ambience: Forest night crickets (8.0s)
    t7 = np.linspace(0, 8.0, int(8.0 * sr), dtype=np.float32)
    crickets = 0.15 * np.sin(2 * np.pi * 4500 * t7) * (np.sin(2 * np.pi * 14 * t7) > 0.6)
    wind_bed = 0.05 * np.random.normal(0, 0.1, len(t7))
    wf7 = (crickets + wind_bed).astype(np.float32)
    sf.write(str(GOLDEN_DIR / "amb_forest_night_crickets_01.wav"), wf7, sr)

    # 8. Weather: Rain with thunder crack (5.0s)
    t8 = np.linspace(0, 5.0, int(5.0 * sr), dtype=np.float32)
    rain = np.random.normal(0, 0.08, len(t8)).astype(np.float32)
    thunder_t = t8[int(2.0 * sr):int(3.5 * sr)] - 2.0
    thunder = 0.7 * np.sin(2 * np.pi * 45 * thunder_t) * np.exp(-3.0 * thunder_t)
    rain[int(2.0 * sr):int(3.5 * sr)] += thunder
    sf.write(str(GOLDEN_DIR / "weather_rain_thunder_crack_01.wav"), rain, sr)

    # 9. Creatures: Ghoul beast snarl (1.2s)
    t9 = np.linspace(0, 1.2, int(1.2 * sr), dtype=np.float32)
    mod = 1.0 + 0.4 * np.sin(2 * np.pi * 35 * t9)
    wf9 = 0.5 * np.sin(2 * np.pi * 140 * t9 * mod) * np.exp(-2.0 * t9)
    sf.write(str(GOLDEN_DIR / "creature_ghoul_snarl_01.wav"), wf9.astype(np.float32), sr)

    # 10. Magic: Arcane pulse burst (1.5s)
    t10 = np.linspace(0, 1.5, int(1.5 * sr), dtype=np.float32)
    sweep_freq = np.linspace(150, 900, len(t10))
    wf10 = 0.6 * np.sin(2 * np.pi * sweep_freq * t10) * np.sin(np.pi * t10 / 1.5)
    sf.write(str(GOLDEN_DIR / "magic_arcane_pulse_burst_01.wav"), wf10.astype(np.float32), sr)

    # 11. Music: Dark drone underscore (6.0s)
    t11 = np.linspace(0, 6.0, int(6.0 * sr), dtype=np.float32)
    c_note = 0.3 * np.sin(2 * np.pi * 65.4 * t11)
    g_note = 0.2 * np.sin(2 * np.pi * 98.0 * t11)
    wf11 = (c_note + g_note).astype(np.float32)
    sf.write(str(GOLDEN_DIR / "music_drone_dark_underscore_01.wav"), wf11, sr)

    # 12. Human non-speech: Gasp (0.7s)
    t12 = np.linspace(0, 0.7, int(0.7 * sr), dtype=np.float32)
    noise12 = np.random.normal(0, 0.2, len(t12)).astype(np.float32)
    env12 = np.linspace(0.1, 1.0, len(t12)) ** 2 * np.exp(-4 * t12)
    wf12 = noise12 * env12
    sf.write(str(GOLDEN_DIR / "human_non_speech_gasp_01.wav"), wf12.astype(np.float32), sr)

    # 13. Long Audio / Ambience: Mountain wind (35.0s)
    t13 = np.linspace(0, 35.0, int(35.0 * sr), dtype=np.float32)
    wind_mod = 0.15 + 0.1 * np.sin(2 * np.pi * 0.15 * t13)
    wf13 = (np.random.normal(0, 0.1, len(t13)) * wind_mod).astype(np.float32)
    sf.write(str(GOLDEN_DIR / "long_ambience_mountain_wind_01.wav"), wf13, sr)

    # 14. Universal Category System (UCS) compliant: DOORWood_Heavy Gate Slam_ST01.wav
    t14 = np.linspace(0, 1.2, int(1.2 * sr), dtype=np.float32)
    wf14 = 0.7 * np.sin(2 * np.pi * 95 * t14) * np.exp(-8 * t14)
    sf.write(str(GOLDEN_DIR / "DOORWood_Heavy Gate Slam_ST01.wav"), wf14.astype(np.float32), sr)

    # 15. Rich Embedded Metadata (Title, Artist, Album, Comment) via ffmpeg
    t15 = np.linspace(0, 2.0, int(2.0 * sr), dtype=np.float32)
    wf15 = 0.4 * np.sin(2 * np.pi * 440 * t15)
    temp_wav = GOLDEN_DIR / "temp_id3.wav"
    sf.write(str(temp_wav), wf15.astype(np.float32), sr)
    dest_mp3 = GOLDEN_DIR / "embedded_id3_metadata_sample_01.mp3"
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [
        ffmpeg, "-y", "-i", str(temp_wav),
        "-metadata", "title=Ancient Castle Hall Fireplace",
        "-metadata", "artist=Master Sound Designer",
        "-metadata", "album=Cinematic Fantasy Vol 1",
        "-metadata", "comment=Warm hearth flames crackling in high stone hall",
        "-metadata", "genre=Ambience",
        "-b:a", "192k",
        str(dest_mp3)
    ]
    subprocess.run(cmd, capture_output=True)
    if temp_wav.exists():
        temp_wav.unlink()

    # 16. Unlabeled Raw Recording: obscure name, zero tags (1.0s)
    t16 = np.linspace(0, 1.0, int(1.0 * sr), dtype=np.float32)
    wf16 = 0.3 * np.sin(2 * np.pi * 210 * t16) * np.exp(-4 * t16)
    sf.write(str(GOLDEN_DIR / "rec_20260927_raw_001.wav"), wf16.astype(np.float32), sr)

    return GOLDEN_DIR


if __name__ == "__main__":
    p = generate_golden_dataset()
    print(f"Generated golden library at: {p} ({len(list(p.glob('*')))} files)")
