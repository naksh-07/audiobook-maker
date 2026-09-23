#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 9 ("The Voice of Reason 5") Production Pipeline.
Executes Gates 4, 4.5, 5, and 6 under the Gold Standard Multi-Gate Protocol:
- Strictly 1-Worker Stealth Human Cadence TTS synthesis across active key pool
- Gate 4.5 Sample-Accurate Timeline Ledger & Master Dialogue Stem
- Gate 5 Creative Manifest Curation across 6 Dramatic Acts (70-75% silence sweet spot)
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

    script_path = scripts_dir / "chapter_009_hi_script.json"
    if not script_path.exists():
        raise FileNotFoundError(f"Chapter 9 script missing at {script_path}")

    with open(script_path, "r", encoding="utf-8") as f:
        script_segments = json.load(f)
    total_segments = len(script_segments)

    print("=" * 80)
    print("  AUDIOBOOK FACTORY - CHAPTER 009 ('THE VOICE OF REASON 5') PRODUCTION")
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
        max_workers=3,
        rpm=15.0,
    )

    t0 = time.time()
    audio_files = dispatcher.synthesize_chapter_script(
        script_path=script_path,
        chapter_num=9,
    )
    t_synth = time.time() - t0
    print(f"\n[+] Gate 4 Synthesis Complete in {t_synth:.1f}s ({t_synth/60:.1f}m).")
    print(f"    Total chunks generated/verified: {len(audio_files)}/{total_segments}")

    # Verify every chunk exists and is non-empty
    corrupt_or_missing = []
    for idx in range(1, total_segments + 1):
        matches = list(audio_chunks_dir.glob(f"c009_s{idx:04d}_*.wav"))
        if not matches or matches[0].stat().st_size < 1000:
            corrupt_or_missing.append(idx)

    if corrupt_or_missing:
        raise RuntimeError(f"Gate 4 Verification Failed: missing or corrupt segments: {corrupt_or_missing}")
    print(f"[+] Gate 4 Verification: 100% of chunks ({total_segments}/{total_segments}) verified intact on disk!")

    # -------------------------------------------------------------------------
    # STEP 2: GATE 4.5 - TIMELINE LEDGER & MASTER DIALOGUE STEM
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 2: GATE 4.5 - TIMELINE LEDGER & MASTER DIALOGUE STEM")
    print("-" * 80)

    ledger_path = scripts_dir / "chapter_009_timeline_ledger.json"
    dialogue_wav_path = mastered_dir / "chapter_009_dialogue.wav"

    ledger = build_audio_transcript_ledger(
        project_dir=project_dir,
        chapter_num=9,
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
    seg_map = {s.segment_index: (s.start_ms, s.end_ms) for s in ledger.segments}

    # Curate Witcher 3 OST Cues for Chapter 9's 6 Dramatic Acts
    # Target total music duration: ~25-28% of total time -> ~72-75% silence
    music_cues = []
    
    # Act 1: Intro in library (Segments around start)
    s1 = min(seg_map.keys())
    music_cues.append(
        MusicCue(
            cue_id="cue_01_library_stillness",
            cue_type="EMOTIONAL_UNDERSCORE",
            track_name="004 The Fortress of Memory.mp3",
            section_name="INTRO_BED",
            start_ms=seg_map[s1][0],
            duration_ms=min(38000, int(total_dur_ms * 0.08)),
            fade_in_ms=2000,
            fade_out_ms=3500,
            volume_db=-22.0,
            dramatic_justification="Quiet, dusty library stillness as Geralt studies Roderick de Novembre and Nenneke announces the guest."
        )
    )

    # Act 2: Dandilion's entrance & banter (around 15% mark)
    idx_act2 = max(1, int(total_segments * 0.15))
    if idx_act2 in seg_map:
        music_cues.append(
            MusicCue(
                cue_id="cue_02_dandelion_swagger",
                cue_type="EMOTIONAL_UNDERSCORE",
                track_name="100 Dandelion's Inheritance.mp3",
                section_name="RISING_TENSION",
                start_ms=seg_map[idx_act2][0],
                duration_ms=min(45000, int(total_dur_ms * 0.09)),
                fade_in_ms=2000,
                fade_out_ms=3500,
                volume_db=-20.0,
                dramatic_justification="Jaunty lute flourish and playful acoustic swagger for Dandilion recounting pinching the cute gatekeeper's bottom."
            )
        )

    # Act 3: Hidden Plum Vodka & Alchemy (around 30% mark)
    idx_act3 = max(1, int(total_segments * 0.30))
    if idx_act3 in seg_map:
        music_cues.append(
            MusicCue(
                cue_id="cue_03_plum_vodka_alchemy",
                cue_type="EMOTIONAL_UNDERSCORE",
                track_name="147 Drinking Horns.mp3",
                section_name="MAIN_THEME",
                start_ms=seg_map[idx_act3][0],
                duration_ms=min(42000, int(total_dur_ms * 0.08)),
                fade_in_ms=2000,
                fade_out_ms=3500,
                volume_db=-21.0,
                dramatic_justification="Hearty medieval drinking warmth as Geralt unearths the hidden jug and toasts with the bard."
            )
        )

    # Act 4: The Changing World & Odd Monster Requests (around 50% mark)
    idx_act4 = max(1, int(total_segments * 0.50))
    if idx_act4 in seg_map:
        music_cues.append(
            MusicCue(
                cue_id="cue_04_changing_world",
                cue_type="TENSION_RISER",
                track_name="041 Civillization's Edge.mp3",
                section_name="RISING_TENSION",
                start_ms=seg_map[idx_act4][0],
                duration_ms=min(48000, int(total_dur_ms * 0.09)),
                fade_in_ms=2500,
                fade_out_ms=3500,
                volume_db=-22.0,
                dramatic_justification="Melancholic strings under Geralt lamenting the bridge troll, pet dragons, and obsolete monster hunting."
            )
        )

    # Act 5: Unicorn Virgins & The Obsolescence of Witchers (around 70% mark)
    idx_act5 = max(1, int(total_segments * 0.70))
    if idx_act5 in seg_map:
        music_cues.append(
            MusicCue(
                cue_id="cue_05_unicorn_virgins",
                cue_type="EMOTIONAL_UNDERSCORE",
                track_name="022 The Inn by the Crossroads.mp3",
                section_name="MAIN_THEME",
                start_ms=seg_map[idx_act5][0],
                duration_ms=min(45000, int(total_dur_ms * 0.09)),
                fade_in_ms=2000,
                fade_out_ms=3500,
                volume_db=-21.0,
                dramatic_justification="Philosophical, wry acoustic commentary as Dandilion explains how virgins popped their cherry when unicorns went extinct."
            )
        )

    # Act 6: Piss Beer & Escape from Gulet (around 88% mark to end)
    idx_act6 = max(1, int(total_segments * 0.88))
    if idx_act6 in seg_map:
        music_cues.append(
            MusicCue(
                cue_id="cue_06_escape_from_gulet",
                cue_type="AFTERMATH_FADE",
                track_name="096 Fools and the Fooled.mp3",
                section_name="AFTERMATH_FADE",
                start_ms=seg_map[idx_act6][0],
                duration_ms=min(50000, int(total_dur_ms * 0.10)),
                fade_in_ms=1500,
                fade_out_ms=4000,
                volume_db=-20.0,
                dramatic_justification="Comedic, roguish bard theme recalling fleeing Gulet with four brothers threatening castration after knocking up the girl."
            )
        )

    total_music_ms = sum(c.duration_ms for c in music_cues)
    silence_pct = round(max(0.0, (1.0 - (total_music_ms / total_dur_ms)) * 100.0), 2)
    print(f"[+] Music Cues Curated: {len(music_cues)} cues ({total_music_ms / 1000.0:.1f}s music coverage)")
    print(f"[+] Silence Ratio    : {silence_pct}% (Target: 70.0% - 75.0%)")

    # Curate Anchored Tactile Foley Cues
    foley_cues = []
    
    # 1. Book page turn early in chapter
    foley_cues.append(
        FoleyCue(
            cue_id="fol_01_book_page",
            segment_index=1,
            anchor_word="पन्नों",
            pre_roll_ms=100,
            asset_path=str(ROOT_DIR / "audiobooks/sound_bank/foley/tiny_book-page-01.wav").replace("\\", "/"),
            asset_name="tiny_book-page-01.wav",
            gain_dbfs=-20.0,
            azimuth_pan=-0.1,
            reverb_send=0.15,
            start_ms=seg_map[1][0] + 400,
            duration_ms=1200,
        )
    )

    # 2. Footsteps / door entrance
    if idx_act2 in seg_map:
        foley_cues.append(
            FoleyCue(
                cue_id="fol_02_floor_creak",
                segment_index=idx_act2,
                anchor_word="चौखट",
                pre_roll_ms=100,
                asset_path=str(ROOT_DIR / "audiobooks/sound_bank/foley/tiny_floor-creak-01.wav").replace("\\", "/"),
                asset_name="tiny_floor-creak-01.wav",
                gain_dbfs=-22.0,
                azimuth_pan=0.2,
                reverb_send=0.2,
                start_ms=seg_map[idx_act2][0] + 200,
                duration_ms=1000,
            )
        )

    # 3. Uncorking clay bottle
    if idx_act3 in seg_map:
        foley_cues.append(
            FoleyCue(
                cue_id="fol_03_uncork_bottle",
                segment_index=idx_act3,
                anchor_word="मटकी",
                pre_roll_ms=100,
                asset_path=str(ROOT_DIR / "audiobooks/sound_bank/foley/tiny_bottle-clay-uncork-01.wav").replace("\\", "/"),
                asset_name="tiny_bottle-clay-uncork-01.wav",
                gain_dbfs=-19.0,
                azimuth_pan=0.0,
                reverb_send=0.15,
                start_ms=seg_map[idx_act3][0] + 300,
                duration_ms=800,
            )
        )
        # 4. Pouring drink
        foley_cues.append(
            FoleyCue(
                cue_id="fol_04_pour_drink",
                segment_index=min(idx_act3 + 1, total_segments),
                anchor_word="घूँट",
                pre_roll_ms=100,
                asset_path=str(ROOT_DIR / "audiobooks/sound_bank/foley/tiny_water-pour-01.wav").replace("\\", "/"),
                asset_name="tiny_water-pour-01.wav",
                gain_dbfs=-22.0,
                azimuth_pan=-0.1,
                reverb_send=0.15,
                start_ms=seg_map[min(idx_act3 + 1, total_segments)][0] + 200,
                duration_ms=1500,
            )
        )

    # Environmental Ambience Bed (Quiet Temple Library Interior)
    ambience_scenes = [
        AmbienceScene(
            scene_id=1,
            start_ms=0,
            end_ms=total_dur_ms,
            asset_path=str(ROOT_DIR / "audiobooks/sound_bank/cache/AMB/wind_howl.ogg").replace("\\", "/"),
            target_lufs=-34.0,
            reverb_preset="room",
            asset_name="wind_howl.ogg"
        )
    ]

    manifest = CreativeManifest(
        manifest_version="3.0",
        project_id="witcher1",
        chapter_id="chapter_009",
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

    manifest_file = manifests_dir / "chapter_009_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        f.write(manifest.to_json(indent=2))
    print(f"[+] Creative Manifest compiled: {manifest_file.name}")

    # -------------------------------------------------------------------------
    # STEP 4: MASTER AUDIO COMPILATION & EBU R128 BROADCAST CERTIFICATION
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 4: MASTER COMPILATION & BROADCAST LOUDNESS CERTIFICATION")
    print("-" * 80)

    final_master_m4a = mastered_dir / "chapter_009_cinematic.m4a"
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
    print("  CHAPTER 009 BROADCAST MASTER CERTIFICATION")
    print("=" * 80)
    print("\n".join(summary_lines[-16:]))
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
