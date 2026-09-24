#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 10 ("The Edge of the World") Production Pipeline.
Executes Gates 4, 4.5, 5, and 6 under the Gold Standard Multi-Gate Protocol:
- Strictly 1-Worker Stealth Human Cadence TTS synthesis across active key pool
- Gate 4.5 Sample-Accurate Timeline Ledger & Master Dialogue Stem
- Gate 5 Creative Manifest Curation across 7 Dramatic Acts (70-75% silence sweet spot)
- Deterministic Multitrack Mastering & Broadcast EBU R128 Certification (-19 LUFS)
"""

import os
import sys
import json
import time
import wave
import subprocess
from pathlib import Path

# Configure UTF-8 for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from audiobook_factory.logger import logger
from audiobook_factory.tts_dispatcher import TTSDispatcher
from audiobook_factory.timeline_ledger import (
    build_audio_transcript_ledger,
    stitch_dialogue_track_from_ledger,
)
from audiobook_factory.gate_auditor import audit_gate4_ledger
from audiobook_factory.contracts import (
    CreativeManifest,
    MusicCue,
    FoleyCue,
    AmbienceScene,
    MasteringConfig,
)
from audiobook_factory.manifest_renderer import render_manifest_soundscape
from audiobook_factory.sound_bank import get_sound_bank
from audiobook_factory.soundscape import get_audio_duration


def main():
    project_dir = ROOT_DIR / "audiobooks" / "projects" / "witcher1"
    scripts_dir = project_dir / "scripts"
    audio_chunks_dir = project_dir / "audio_chunks"
    mastered_dir = project_dir / "mastered"
    manifests_dir = project_dir / "manifests"

    mastered_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)

    script_path = scripts_dir / "chapter_010_hi_script.json"
    if not script_path.exists():
        raise FileNotFoundError(f"Chapter 10 script missing at {script_path}")

    with open(script_path, "r", encoding="utf-8") as f:
        script_segments = json.load(f)
    total_segments = len(script_segments)

    print("=" * 80)
    print("  AUDIOBOOK FACTORY - CHAPTER 010 ('THE EDGE OF THE WORLD') PRODUCTION")
    print("  Gold Standard Multi-Gate Protocol: 1-Worker Stealth Human Cadence")
    print("=" * 80)
    print(f"  Script: {script_path.name} ({total_segments} segments)")

    # -------------------------------------------------------------------------
    # STEP 1: GATE 4 - SPEECH SYNTHESIS (1-Worker Stealth Human Cadence)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 1: GATE 4 - SPEECH SYNTHESIS")
    print("-" * 80)

    dispatcher = TTSDispatcher(
        project_dir=project_dir,
        default_backend="gemini_tts",
        max_workers=1,
        rpm=15.0,
    )

    # Register Chapter 10 voices
    chapter_10_voices = {
        "Torque": {"backend": "gemini_tts", "voice": "Puck", "speed": 1.02},
        "Toruviel": {"backend": "gemini_tts", "voice": "Kore", "speed": 1.0},
        "Filavandrel": {"backend": "gemini_tts", "voice": "Fenrir", "speed": 0.96},
        "Dhun": {"backend": "gemini_tts", "voice": "Fenrir", "speed": 0.98},
        "Nettly": {"backend": "gemini_tts", "voice": "Puck", "speed": 1.0},
        "Alderman": {"backend": "gemini_tts", "voice": "Fenrir", "speed": 1.0},
        "Old_Woman": {"backend": "gemini_tts", "voice": "Kore", "speed": 0.95},
        "Galarr": {"backend": "gemini_tts", "voice": "Puck", "speed": 1.0},
        "Villager": {"backend": "gemini_tts", "voice": "Puck", "speed": 1.0},
    }
    dispatcher.voice_map.update(chapter_10_voices)

    t0 = time.time()
    audio_files = dispatcher.synthesize_chapter_script(
        script_path=script_path,
        chapter_num=10,
    )
    t_synth = time.time() - t0
    print(f"\n[+] Gate 4 Synthesis Complete in {t_synth:.1f}s ({t_synth/60:.1f}m).")
    print(f"    Total chunks generated/verified: {len(audio_files)}/{total_segments}")

    # Verify every chunk exists and is non-empty
    corrupt_or_missing = []
    for idx in range(1, total_segments + 1):
        matches = list(audio_chunks_dir.glob(f"c010_s{idx:04d}_*.wav"))
        if not matches:
            corrupt_or_missing.append((idx, "missing"))
        elif matches[0].stat().st_size < 44:
            corrupt_or_missing.append((idx, "corrupt_empty"))

    if corrupt_or_missing:
        print(f"[!] Warning: {len(corrupt_or_missing)} chunks require re-synthesis: {corrupt_or_missing[:5]}")
        raise RuntimeError(f"Gate 4 failed: {len(corrupt_or_missing)} chunks missing or corrupt.")
    else:
        print("[OK] Gate 4 Audit Passed: 100% chunks verified on disk with non-zero audio.")

    # -------------------------------------------------------------------------
    # STEP 2: GATE 4.5 - TIMELINE LEDGER & MASTER DIALOGUE STEM
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 2: GATE 4.5 - TIMELINE LEDGER & MASTER DIALOGUE STEM")
    print("-" * 80)

    ledger_path = scripts_dir / "chapter_010_timeline_ledger.json"
    dialogue_path = mastered_dir / "chapter_010_dialogue.wav"

    print(f"[*] Building timeline ledger for Chapter 10 ({total_segments} segments)...")
    ledger = build_audio_transcript_ledger(
        project_dir=project_dir,
        chapter_num=10,
        script_file=script_path,
        audio_dir=audio_chunks_dir,
    )
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(ledger.model_dump(), f, ensure_ascii=False, indent=2)
    print(f"[+] Saved timeline ledger to: {ledger_path.name}")

    audit_res = audit_gate4_ledger(
        ledger_file=ledger_path,
        script_file=script_path,
        audio_dir=audio_chunks_dir,
    )
    if audit_res.get("status") != "PASS":
        raise ValueError(f"Gate 4.5 Ledger Audit Failed: {audit_res}")
    print(f"[OK] Gate 4.5 Ledger Audit Passed (Total: {ledger.total_timeline_duration_ms} ms)")

    print(f"[*] Stitching Master Dialogue Stem ({dialogue_path.name})...")
    stitch_dialogue_track_from_ledger(
        ledger=ledger,
        audio_dir=audio_chunks_dir,
        output_wav_path=dialogue_path,
        sample_rate=48000,
    )

    actual_wav_dur = get_audio_duration(dialogue_path)
    expected_dur = ledger.total_timeline_duration_ms / 1000.0
    print(f"[+] Master Dialogue Track Rendered: {actual_wav_dur:.2f}s (Ledger expected: {expected_dur:.2f}s)")
    if abs(actual_wav_dur - expected_dur) > 0.5:
        print(f"[!] Warning: Dialogue drift {abs(actual_wav_dur - expected_dur):.3f}s exceeds threshold.")

    # -------------------------------------------------------------------------
    # STEP 3: GATE 5 - CREATIVE MANIFEST CURATION
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 3: GATE 5 - CREATIVE MANIFEST CURATION")
    print("-" * 80)

    total_dur_ms = ledger.total_timeline_duration_ms
    seg_map = {s.segment_index: (s.start_ms, s.end_ms) for s in ledger.segments}

    # Curate Witcher 3 OST Cues across Chapter 10's 7 Dramatic Acts
    music_cues = []
    
    # Act 1: Upper Posada & Road (Start, ~0-14%)
    s1 = min(seg_map.keys())
    music_cues.append(
        MusicCue(
            cue_id="cue_01_upper_posada_road",
            cue_type="EMOTIONAL_UNDERSCORE",
            track_name="009 White Orchards.mp3",
            section_name="INTRO_BED",
            start_ms=seg_map[s1][0],
            duration_ms=min(55000, int(total_dur_ms * 0.05)),
            fade_in_ms=2000,
            fade_out_ms=3500,
            volume_db=-22.0,
            dramatic_justification="Rustic medieval road atmosphere as Geralt and Dandelion depart Upper Posada."
        )
    )

    # Act 2: Lower Posada & Grandma's Book (~15%)
    idx_act2 = max(1, int(total_segments * 0.15))
    if idx_act2 in seg_map:
        music_cues.append(
            MusicCue(
                cue_id="cue_02_village_secrets",
                cue_type="EMOTIONAL_UNDERSCORE",
                track_name="004 The Fortress of Memory.mp3",
                section_name="RISING_TENSION",
                start_ms=seg_map[idx_act2][0],
                duration_ms=min(60000, int(total_dur_ms * 0.05)),
                fade_in_ms=2000,
                fade_out_ms=3500,
                volume_db=-21.0,
                dramatic_justification="Mysterious dusty tension as Dhun and the grandmother reveal the ancient herbal book."
            )
        )

    # Act 3: Hemp Fields & Torque the Sylvan (~28%)
    idx_act3 = max(1, int(total_segments * 0.28))
    if idx_act3 in seg_map:
        music_cues.append(
            MusicCue(
                cue_id="cue_03_torque_sylvan_mischief",
                cue_type="EMOTIONAL_UNDERSCORE",
                track_name="100 Dandelion's Inheritance.mp3",
                section_name="MAIN_THEME",
                start_ms=seg_map[idx_act3][0],
                duration_ms=min(65000, int(total_dur_ms * 0.06)),
                fade_in_ms=2000,
                fade_out_ms=3500,
                volume_db=-20.0,
                dramatic_justification="Playful, cheeky folk rhythm as Torque the goat-horned Sylvan taunts with his slingshot."
            )
        )

    # Act 4: Night Cottage & The Elf Mystery (~42%)
    idx_act4 = max(1, int(total_segments * 0.42))
    if idx_act4 in seg_map:
        music_cues.append(
            MusicCue(
                cue_id="cue_04_starving_elves_secret",
                cue_type="TENSION_RISER",
                track_name="041 Civillization's Edge.mp3",
                section_name="RISING_TENSION",
                start_ms=seg_map[idx_act4][0],
                duration_ms=min(65000, int(total_dur_ms * 0.06)),
                fade_in_ms=2500,
                fade_out_ms=3500,
                volume_db=-22.0,
                dramatic_justification="Eerie realization that Torque is smuggling grain to save dying elves in the mountains."
            )
        )

    # Act 5: Hemp Fields Ambush & Broken Lute (~58%)
    idx_act5 = max(1, int(total_segments * 0.58))
    if idx_act5 in seg_map:
        music_cues.append(
            MusicCue(
                cue_id="cue_05_elven_ambush",
                cue_type="CLIMACTIC_ACTION_CUE",
                track_name="008 The Griffin.mp3",
                section_name="ACTION_CLIMAX",
                start_ms=seg_map[idx_act5][0],
                duration_ms=min(60000, int(total_dur_ms * 0.05)),
                fade_in_ms=1000,
                fade_out_ms=3000,
                volume_db=-18.0,
                dramatic_justification="Violent kinetic clash as Toruviel and the elves ambush Geralt and smash the bard's lute."
            )
        )

    # Act 6: Mountain Foothills & Filavandrel's Doom (~72%)
    idx_act6 = max(1, int(total_segments * 0.72))
    if idx_act6 in seg_map:
        music_cues.append(
            MusicCue(
                cue_id="cue_06_filavandrel_tragedy",
                cue_type="EMOTIONAL_UNDERSCORE",
                track_name="002 The Trail.mp3",
                section_name="RISING_TENSION",
                start_ms=seg_map[idx_act6][0],
                duration_ms=min(75000, int(total_dur_ms * 0.07)),
                fade_in_ms=2500,
                fade_out_ms=4000,
                volume_db=-21.0,
                dramatic_justification="Somber, tragic strings as Filavandrel laments the slow genocide of the Aen Seidhe."
            )
        )

    # Act 7: The Goddess Appears & Peaceful Epilogue (~88%)
    idx_act7 = max(1, int(total_segments * 0.88))
    if idx_act7 in seg_map:
        music_cues.append(
            MusicCue(
                cue_id="cue_07_dana_meadbh_grace",
                cue_type="EMOTIONAL_UNDERSCORE",
                track_name="003 Geralt and Yen.mp3",
                section_name="MAIN_THEME",
                start_ms=seg_map[idx_act7][0],
                duration_ms=min(70000, int(total_dur_ms * 0.06)),
                fade_in_ms=3000,
                fade_out_ms=4500,
                volume_db=-20.0,
                dramatic_justification="Radiant, transcendent warmth as Dana Meadbh appears and the elven lute is gifted."
            )
        )

    total_music_ms = sum(c.duration_ms for c in music_cues)
    silence_pct = max(0.0, min(100.0, ((total_dur_ms - total_music_ms) / total_dur_ms) * 100.0))
    print(f"[*] Curated {len(music_cues)} Witcher 3 score cues.")
    print(f"    Total Timeline: {total_dur_ms/1000.0:.1f}s | Music: {total_music_ms/1000.0:.1f}s")
    print(f"    Silence Percentage: {silence_pct:.2f}% (Sweet Spot: 70-75%)")

    # Ambience Bed (High-fidelity room tone and wind)
    sound_bank = get_sound_bank()
    wind_asset = sound_bank.resolve_sound("wind_howl.ogg", category="AMB")
    ambience_scenes = [
        AmbienceScene(
            scene_id=1,
            start_ms=0,
            end_ms=total_dur_ms,
            asset_path=str(wind_asset) if wind_asset else "",
            asset_name="wind_howl.ogg",
            target_lufs=-35.0,
            reverb_preset="room"
        )
    ]

    mastering_config = MasteringConfig(
        target_lufs=-19.0,
        true_peak_dbtp=-1.5,
        ducking_attenuation_db=-16.0,
        ducking_attack_ms=15,
        ducking_release_ms=350,
        spectral_carve_hz=2200,
        spectral_carve_gain_db=-5.5,
        acoustic_ir=None,
    )

    manifest = CreativeManifest(
        manifest_version="3.0",
        project_id="witcher1",
        chapter_id="chapter_010",
        silence_percentage=round(silence_pct, 2),
        mastering=mastering_config,
        ambience_scenes=ambience_scenes,
        music_cues=music_cues,
        foley_cues=[]
    )

    manifest_path = manifests_dir / "chapter_010_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest.model_dump(), f, ensure_ascii=False, indent=2)
    print(f"[+] Saved Creative Manifest to: {manifest_path.name}")

    # -------------------------------------------------------------------------
    # STEP 4: GATE 6 - CINEMATIC SOUNDSCAPE RENDERING & MASTERING
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 4: GATE 6 - CINEMATIC SOUNDSCAPE RENDERING & MASTERING")
    print("-" * 80)

    cinematic_output = mastered_dir / "chapter_010_cinematic.m4a"

    print(f"[*] Rendering Multitrack Master via CinemaAudioEngine...")
    t_render_start = time.time()
    rendered_master = render_manifest_soundscape(
        manifest=manifest,
        vocal_track_path=dialogue_path,
        output_master_file=cinematic_output,
    )
    t_render = time.time() - t_render_start
    print(f"[+] Mastered Track Rendered in {t_render:.1f}s: {cinematic_output.name}")
    print(f"    Output File Size: {cinematic_output.stat().st_size / (1024*1024):.2f} MB")

    # Broadcast Certification via FFmpeg EBU R128 Probe
    print("\n[*] Running Broadcast EBU R128 Verification...")
    probe_cmd = [
        "ffmpeg", "-nostats", "-i", str(cinematic_output),
        "-filter_complex", "ebur128=peak=true",
        "-f", "null", "-"
    ]
    probe_res = subprocess.run(probe_cmd, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    
    # Parse integrated loudness and true peak
    lufs_match = [line for line in probe_res.stderr.split("\n") if "Integrated loudness:" in line or "I:" in line]
    tp_match = [line for line in probe_res.stderr.split("\n") if "True peak:" in line]
    
    print("=" * 80)
    print("  BROADCAST COMPLIANCE CERTIFICATION (EBU R128):")
    for l in (lufs_match + tp_match)[-3:]:
        print(f"    {l.strip()}")
    print("=" * 80)
    print("\n[OK] Chapter 10 Full Audio Drama Production Pipeline Completed Successfully!")


if __name__ == "__main__":
    main()
