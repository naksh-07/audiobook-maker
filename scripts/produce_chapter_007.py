#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 7 ("The Voice of Reason 4") Production Pipeline.
Executes Gates 4, 4.5, and 5 under the Gold Standard Multi-Gate Protocol:
- Strictly 1-Worker Stealth Human Cadence TTS synthesis across active key pool
- Gate 4.5 Sample-Accurate Timeline Ledger & Vocal Master Stem
- Gate 5 Creative Manifest Curation (70-75% silence sweet spot)
- Deterministic Multitrack Mastering & Broadcast EBU R128 Certification
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

    script_path = scripts_dir / "chapter_007_hi_script.json"
    if not script_path.exists():
        raise FileNotFoundError(f"Chapter 7 script missing at {script_path}")

    with open(script_path, "r", encoding="utf-8") as f:
        script_segments = json.load(f)
    total_segments = len(script_segments)

    print("=" * 80)
    print("  AUDIOBOOK FACTORY - CHAPTER 007 ('THE VOICE OF REASON 4') PRODUCTION")
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
    )

    t0 = time.time()
    audio_files = dispatcher.synthesize_chapter_script(
        script_path=script_path,
        chapter_num=7,
    )
    t_synth = time.time() - t0
    print(f"\n[+] Gate 4 Synthesis Complete in {t_synth:.1f}s ({t_synth/60:.1f}m).")
    print(f"    Total chunks generated/verified: {len(audio_files)}/{total_segments}")

    # Verify every chunk exists and is non-empty
    corrupt_or_missing = []
    for idx in range(1, total_segments + 1):
        matches = list(audio_chunks_dir.glob(f"c007_s{idx:04d}_*.wav"))
        if not matches or matches[0].stat().st_size < 1000:
            corrupt_or_missing.append(idx)

    if corrupt_or_missing:
        raise RuntimeError(f"Gate 4 Verification Failed: missing or corrupt segments: {corrupt_or_missing}")
    print("[+] Gate 4 Verification: 100% of chunks (36/36) verified intact on disk!")

    # -------------------------------------------------------------------------
    # STEP 2: GATE 4.5 - TIMELINE LEDGER & MASTER DIALOGUE STEM
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 2: GATE 4.5 - TIMELINE LEDGER & MASTER DIALOGUE STEM")
    print("-" * 80)

    ledger_path = scripts_dir / "chapter_007_timeline_ledger.json"
    dialogue_wav_path = mastered_dir / "chapter_007_dialogue.wav"

    ledger = build_audio_transcript_ledger(
        project_dir=project_dir,
        chapter_num=7,
        script_file=script_path,
        audio_dir=audio_chunks_dir,
        output_ledger_file=ledger_path,
        default_pause_ms=400,
    )

    stitch_dialogue_track_from_ledger(
        ledger=ledger,
        audio_dir=audio_chunks_dir,
        output_wav_path=dialogue_wav_path,
        sample_rate=24000,
    )

    # Audit Gate 4.5 Ledger Integrity (0ms drift & 100% text retention)
    audit_report = audit_gate4_ledger(
        ledger_file=ledger_path,
        script_file=script_path,
        audio_dir=audio_chunks_dir,
    )
    print(f"[+] Gate 4.5 Audit: {audit_report.get('status', 'OK')}")
    print(f"    Total Timeline Duration: {ledger.total_timeline_duration_ms / 1000.0:.2f}s ({ledger.total_timeline_duration_ms / 60000.0:.2f} min)")
    print(f"    Raw Speech Duration    : {ledger.total_dialogue_duration_ms / 1000.0:.2f}s")
    print(f"    Text Retention Ratio   : {audit_report.get('text_match_ratio', 1.0) * 100.0:.1f}%")

    # -------------------------------------------------------------------------
    # STEP 3: GATE 5 - CREATIVE MANIFEST CURATION
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 3: GATE 5 - CREATIVE MANIFEST CURATION (70-75% Silence Sweet Spot)")
    print("-" * 80)

    total_dur_ms = ledger.total_timeline_duration_ms
    total_dur_sec = total_dur_ms / 1000.0

    # Build timeline lookup map: segment_index -> start_ms, end_ms
    seg_map = {s.segment_index: (s.start_ms, s.end_ms) for s in ledger.segments}

    # Curate Witcher 3 OST Cues for Chapter 7's 6 Dramatic Acts
    # Target total music duration: ~25-28% of total time -> ~72-75% silence
    music_cues = [
        # Act 1 (Seg 1-4): Temple garden stillness, Iola's vow of silence
        MusicCue(
            cue_id="cue_01_temple_solitude",
            cue_type="EMOTIONAL_UNDERSCORE",
            track_name="004 The Fortress of Memory.mp3",
            section_name="INTRO_BED",
            start_ms=seg_map[1][0],
            duration_ms=36000,
            fade_in_ms=2000,
            fade_out_ms=3500,
            volume_db=-21.0,
            dramatic_justification="Establishes the contemplative, sacred stillness of the Melitele temple garden as Geralt begins his confession."
        ),
        # Act 2 (Seg 14-16): Kaer Morhen memories & Trial of the Grasses
        MusicCue(
            cue_id="cue_02_kaer_morhen_trial",
            cue_type="EMOTIONAL_UNDERSCORE",
            track_name="002 The Trail.mp3",
            section_name="RISING_TENSION",
            start_ms=seg_map[14][0],
            duration_ms=40000,
            fade_in_ms=2500,
            fade_out_ms=3500,
            volume_db=-22.0,
            dramatic_justification="Somber, mournful strings reflecting on the agony of the mutations and lost comrades of Kaer Morhen."
        ),
        # Act 3/4 Transition (Seg 22): Slaying beasts across ruins & dark crypts
        MusicCue(
            cue_id="cue_03_path_and_crypts",
            cue_type="TENSION_RISER",
            track_name="013 Chasing the Griffin.mp3",
            section_name="RISING_TENSION",
            start_ms=seg_map[22][0],
            duration_ms=35000,
            fade_in_ms=2000,
            fade_out_ms=3000,
            volume_db=-22.0,
            dramatic_justification="Rhythmic tension underscore beneath Geralt listing the monsters slain in the dark across decades."
        ),
        # Act 5 (Seg 27-28): The Butcher of Blaviken climax
        MusicCue(
            cue_id="cue_04_butcher_of_blaviken",
            cue_type="CLIMACTIC_ACTION_CUE",
            track_name="011 The Nilfgaardians.mp3",
            section_name="CLIMAX_DROP",
            start_ms=seg_map[27][0],
            duration_ms=38000,
            fade_in_ms=1500,
            fade_out_ms=3500,
            volume_db=-19.0,
            dramatic_justification="Haunting, tragic climax as Geralt bitterly laments failing the voice of reason and choosing the lesser evil."
        ),
        # Act 6 (Seg 32-34): Belleteyn, Yennefer, and Dusk Departure
        MusicCue(
            cue_id="cue_05_yennefer_and_dusk",
            cue_type="AFTERMATH_FADE",
            track_name="016 Yennefer of Vengerberg.mp3",
            section_name="AFTERMATH_FADE",
            start_ms=seg_map[32][0],
            duration_ms=42000,
            fade_in_ms=2000,
            fade_out_ms=4000,
            volume_db=-20.0,
            dramatic_justification="Melancholic romantic leitmotif as Geralt connects the child of surprise born on Belleteyn to Yennefer, fading into dusk."
        ),
    ]

    total_music_ms = sum(c.duration_ms for c in music_cues)
    silence_pct = round(max(0.0, (1.0 - (total_music_ms / total_dur_ms)) * 100.0), 2)
    print(f"[+] Music Cues Curated: {len(music_cues)} cues ({total_music_ms / 1000.0:.1f}s music coverage)")
    print(f"[+] Silence Ratio    : {silence_pct}% (Target: 70.0% - 75.0%)")

    # Curate Anchored Tactile Foley Cues
    foley_cues = [
        # Segment 8: Geralt showing the razor-sharp meteorite sword
        FoleyCue(
            cue_id="fol_01_sword_draw",
            segment_index=8,
            anchor_word="तलवार",
            pre_roll_ms=100,
            asset_path="C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobooks/sound_bank/foley/drawKnife1.ogg",
            asset_name="drawKnife1.ogg",
            gain_dbfs=-18.0,
            azimuth_pan=0.15,
            reverb_send=0.15,
            start_ms=seg_map[8][0] + 400,
            duration_ms=1200,
        ),
        # Segment 10: Sitting down on stone bench in garden
        FoleyCue(
            cue_id="fol_02_bench_settle",
            segment_index=10,
            anchor_word="बैठते",
            pre_roll_ms=100,
            asset_path="C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobooks/sound_bank/foley/creak1.ogg",
            asset_name="creak1.ogg",
            gain_dbfs=-22.0,
            azimuth_pan=0.0,
            reverb_send=0.15,
            start_ms=seg_map[10][0] + 600,
            duration_ms=1500,
        ),
        # Segment 29: Iola touches Geralt, Geralt recoils
        FoleyCue(
            cue_id="fol_03_recoil_step",
            segment_index=29,
            anchor_word="छुओ",
            pre_roll_ms=100,
            asset_path="C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobooks/sound_bank/foley/tiny_mud-steps-01.wav",
            asset_name="tiny_mud-steps-01.wav",
            gain_dbfs=-20.0,
            azimuth_pan=-0.2,
            reverb_send=0.15,
            start_ms=seg_map[29][0] + 200,
            duration_ms=1000,
        ),
        # Segment 33: Standing up at dusk
        FoleyCue(
            cue_id="fol_04_stand_dusk",
            segment_index=33,
            anchor_word="चलना",
            pre_roll_ms=100,
            asset_path="C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobooks/sound_bank/foley/tiny_mud-steps-01.wav",
            asset_name="tiny_mud-steps-01.wav",
            gain_dbfs=-21.0,
            azimuth_pan=0.1,
            reverb_send=0.15,
            start_ms=seg_map[33][0] + 300,
            duration_ms=1200,
        ),
    ]

    # Environmental Ambience Bed (Quiet Temple Garden with light wind)
    ambience_scenes = [
        AmbienceScene(
            scene_id=1,
            start_ms=0,
            end_ms=total_dur_ms,
            asset_path="C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobooks/sound_bank/cache/AMB/wind_howl.ogg",
            target_lufs=-33.0,
            reverb_preset="room",
            asset_name="wind_howl.ogg"
        )
    ]

    manifest = CreativeManifest(
        manifest_version="3.0",
        project_id="witcher1",
        chapter_id="chapter_007",
        silence_percentage=silence_pct,
        mastering=MasteringConfig(
            target_lufs=-19.0,
            true_peak_dbtp=-1.5,
            ducking_attenuation_db=-16.0,
            ducking_attack_ms=15,
            ducking_release_ms=350,
            spectral_carve_hz=2200,
            spectral_carve_gain_db=-5.5,
        ),
        ambience_scenes=ambience_scenes,
        music_cues=music_cues,
        foley_cues=foley_cues,
    )

    manifest_file = manifests_dir / "chapter_007_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        f.write(manifest.to_json(indent=2))
    print(f"[+] Creative Manifest compiled: {manifest_file.name}")

    # -------------------------------------------------------------------------
    # STEP 4: MASTER AUDIO COMPILATION & EBU R128 BROADCAST CERTIFICATION
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 4: MASTER COMPILATION & BROADCAST LOUDNESS CERTIFICATION")
    print("-" * 80)

    final_master_m4a = mastered_dir / "chapter_007_cinematic.m4a"
    sound_bank = get_sound_bank()

    t_render_start = time.time()
    render_manifest_soundscape(
        manifest=manifest,
        vocal_track_path=dialogue_wav_path,
        output_master_file=final_master_m4a,
        sound_bank=sound_bank,
    )
    t_render = time.time() - t_render_start
    print(f"[+] Master M4A rendered in {t_render:.1f}s -> {final_master_m4a.name} ({final_master_m4a.stat().st_size:,} bytes)")

    # Measure EBU R128 Loudness
    print("\n[*] Running FFmpeg EBU R128 Broadcast Compliance Analysis...")
    ff_cmd = [
        "ffmpeg", "-y", "-i", str(final_master_m4a),
        "-filter_complex", "ebur128=peak=true",
        "-f", "null", "-"
    ]
    res = subprocess.run(ff_cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")

    lines = res.stderr.splitlines()
    summary_lines = []
    in_summary = False
    for l in lines:
        if "Summary:" in l:
            in_summary = True
        if in_summary:
            summary_lines.append(l)

    print("\n" + "=" * 80)
    print("  CHAPTER 007 BROADCAST MASTER CERTIFICATION")
    print("=" * 80)
    print("\n".join(summary_lines[-16:]))
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
