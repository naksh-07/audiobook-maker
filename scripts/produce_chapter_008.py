#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 8 ("A Question of Price" / एक सवाल कीमत का) Production Pipeline.
Executes Gates 4, 4.5, and 5 under the Gold Standard Multi-Gate Protocol:
- Strictly 1-Worker Stealth Human Cadence TTS synthesis across 101 active keys
- Gate 4.5 Sample-Accurate Timeline Ledger & Master Dialogue Stem
- Gate 5 Creative Manifest Curation across 7 Dramatic Acts (70-75% silence sweet spot)
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

    script_path = scripts_dir / "chapter_008_hi_script.json"
    if not script_path.exists():
        raise FileNotFoundError(f"Chapter 8 script missing at {script_path}")

    with open(script_path, "r", encoding="utf-8") as f:
        script_segments = json.load(f)
    total_segments = len(script_segments)

    print("=" * 80)
    print("  AUDIOBOOK FACTORY - CHAPTER 008 ('A QUESTION OF PRICE') PRODUCTION")
    print("  Gold Standard Multi-Gate Protocol: 1-Worker Stealth Human Cadence")
    print("=" * 80)
    print(f"  Script: {script_path.name} ({total_segments} segments across 14 characters)")

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
        chapter_num=8,
    )
    t_synth = time.time() - t0
    print(f"\n[+] Gate 4 Synthesis Complete in {t_synth:.1f}s ({t_synth/60:.1f}m).")
    print(f"    Total chunks generated/verified: {len(audio_files)}/{total_segments}")

    # Verify every chunk exists and is non-empty
    corrupt_or_missing = []
    for idx in range(1, total_segments + 1):
        matches = list(audio_chunks_dir.glob(f"c008_s{idx:04d}_*.wav"))
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

    ledger_path = scripts_dir / "chapter_008_timeline_ledger.json"
    dialogue_wav_path = mastered_dir / "chapter_008_dialogue.wav"

    ledger = build_audio_transcript_ledger(
        project_dir=project_dir,
        chapter_num=8,
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

    # Curate Witcher 3 OST Cues for Chapter 8's 7 Dramatic Acts
    music_cues = [
        # Act I (Seg 1-4): The Ritual Bath & Castellan Haxo's Warning
        MusicCue(
            cue_id="cue_01_bath_and_castle_intrigue",
            cue_type="EMOTIONAL_UNDERSCORE",
            track_name="018 The Royal Palace in Vizima.mp3",
            section_name="INTRO_BED",
            start_ms=seg_map[1][0],
            duration_ms=45000,
            fade_in_ms=2500,
            fade_out_ms=3500,
            volume_db=-21.0,
            dramatic_justification="Establishes royal palace intrigue as Geralt is groomed and warned by Castellan Haxo."
        ),
        # Act II (Seg 67-70): Grand Banquet of Cintra & Skellige Suitors
        MusicCue(
            cue_id="cue_02_banquet_feasting",
            cue_type="EMOTIONAL_UNDERSCORE",
            track_name="147 Drinking Horns.mp3",
            section_name="INTRO_BED",
            start_ms=seg_map[67][0],
            duration_ms=50000,
            fade_in_ms=2000,
            fade_out_ms=3500,
            volume_db=-22.0,
            dramatic_justification="Festive, boisterous Skellige strings and drums as suitors toast and boast at the feast."
        ),
        # Act II Climax (Seg 220-224): Pavetta enters & Calanthe's Trap
        MusicCue(
            cue_id="cue_03_pavetta_entrance_parley",
            cue_type="TENSION_RISER",
            track_name="004 The Fortress of Memory.mp3",
            section_name="RISING_TENSION",
            start_ms=seg_map[220][0],
            duration_ms=45000,
            fade_in_ms=2000,
            fade_out_ms=3500,
            volume_db=-21.0,
            dramatic_justification="Ominous aristocratic tension as Calanthe demands Geralt execute her unspoken command."
        ),
        # Act III (Seg 287-290): The Arrival of the Urcheon of Erlenwald
        MusicCue(
            cue_id="cue_04_urcheon_arrival",
            cue_type="TENSION_RISER",
            track_name="002 The Trail.mp3",
            section_name="RISING_TENSION",
            start_ms=seg_map[287][0],
            duration_ms=48000,
            fade_in_ms=1500,
            fade_out_ms=3500,
            volume_db=-20.0,
            dramatic_justification="Dark, rhythmic urgency as the iron-clad knight strides into the banquet hall."
        ),
        # Act IV (Seg 381-385): The Law of Surprise & The Sacred Vow
        MusicCue(
            cue_id="cue_05_law_of_surprise_destiny",
            cue_type="EMOTIONAL_UNDERSCORE",
            track_name="190 Ithlinne's Prophecy.mp3",
            section_name="INTRO_BED",
            start_ms=seg_map[381][0],
            duration_ms=52000,
            fade_in_ms=2500,
            fade_out_ms=4000,
            volume_db=-21.0,
            dramatic_justification="Mystical, profound leitmotif as Duny invokes Destiny and Mousesack confirms the ancient sacred vow."
        ),
        # Act V (Seg 473-477): Midnight Unmasking & Clashing Steel
        MusicCue(
            cue_id="cue_06_midnight_brawl",
            cue_type="CLIMACTIC_ACTION_CUE",
            track_name="032 A Blade of Steel.mp3",
            section_name="CLIMAX_DROP",
            start_ms=seg_map[473][0],
            duration_ms=55000,
            fade_in_ms=1000,
            fade_out_ms=3000,
            volume_db=-18.5,
            dramatic_justification="Ferocious, driving combat strings as the castle clock tolls midnight and swords are drawn against Duny."
        ),
        # Act VI (Seg 511-515): Pavetta's Elder Blood Tempest
        MusicCue(
            cue_id="cue_07_elder_blood_tempest",
            cue_type="CLIMACTIC_ACTION_CUE",
            track_name="008 Silver for Monsters.mp3",
            section_name="CLIMAX_DROP",
            start_ms=seg_map[511][0],
            duration_ms=50000,
            fade_in_ms=1200,
            fade_out_ms=3500,
            volume_db=-18.0,
            dramatic_justification="Roaring supernatural intensity as Princess Pavetta unleashes the unchecked power of the Source."
        ),
        # Act VII (Seg 599-603): Dawn of Destiny & The Child of Surprise
        MusicCue(
            cue_id="cue_08_dawn_child_of_surprise",
            cue_type="AFTERMATH_FADE",
            track_name="016 Yennefer of Vengerberg.mp3",
            section_name="AFTERMATH_FADE",
            start_ms=seg_map[599][0],
            duration_ms=60000,
            fade_in_ms=2000,
            fade_out_ms=4500,
            volume_db=-20.0,
            dramatic_justification="Lyrical, transcendent aftermath theme as morning sun touches the ruined hall and Geralt claims his destiny."
        ),
    ]

    total_music_ms = sum(c.duration_ms for c in music_cues)
    silence_pct = round(max(0.0, (1.0 - (total_music_ms / total_dur_ms)) * 100.0), 2)
    print(f"[+] Music Cues Curated: {len(music_cues)} cues ({total_music_ms / 1000.0:.1f}s music coverage)")
    print(f"[+] Silence Ratio    : {silence_pct}% (Target: 70.0% - 75.0%)")

    # Curate Anchored Tactile Foley Cues
    foley_cues = [
        # Act I - Seg 12: Razor shave / towel touch
        FoleyCue(
            cue_id="fol_01_shave_towel",
            segment_index=12,
            anchor_word="तौलिया",
            pre_roll_ms=100,
            asset_path="C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobooks/sound_bank/foley/OGG/cloth1.ogg",
            asset_name="cloth1.ogg",
            gain_dbfs=-20.0,
            azimuth_pan=0.15,
            reverb_send=0.15,
            start_ms=seg_map[12][0] + 300,
            duration_ms=1200,
        ),
        # Act I - Seg 22: Tunic & Bear coat of arms
        FoleyCue(
            cue_id="fol_02_tunic_dress",
            segment_index=22,
            anchor_word="ट्यूनिक",
            pre_roll_ms=100,
            asset_path="C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobooks/sound_bank/foley/OGG/clothBelt.ogg",
            asset_name="clothBelt.ogg",
            gain_dbfs=-21.0,
            azimuth_pan=-0.1,
            reverb_send=0.15,
            start_ms=seg_map[22][0] + 200,
            duration_ms=1500,
        ),
        # Act II - Seg 95: Crach an Craite slams bone on table
        FoleyCue(
            cue_id="fol_03_bone_slam",
            segment_index=95,
            anchor_word="हड्डी",
            pre_roll_ms=50,
            asset_path="C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobooks/sound_bank/foley/OGG/bookPlace1.ogg",
            asset_name="bookPlace1.ogg",
            gain_dbfs=-16.0,
            azimuth_pan=-0.3,
            reverb_send=0.20,
            start_ms=seg_map[95][0] + 400,
            duration_ms=1000,
        ),
        # Act III - Seg 287: Iron hall doors swing open
        FoleyCue(
            cue_id="fol_04_iron_doors",
            segment_index=287,
            anchor_word="दरवाज़े",
            pre_roll_ms=100,
            asset_path="C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobooks/sound_bank/foley/OGG/creak1.ogg",
            asset_name="creak1.ogg",
            gain_dbfs=-18.0,
            azimuth_pan=0.0,
            reverb_send=0.25,
            start_ms=seg_map[287][0] + 200,
            duration_ms=2000,
        ),
        # Act V - Seg 474: Duny helmet unmasked & dropped
        FoleyCue(
            cue_id="fol_05_helmet_drop",
            segment_index=474,
            anchor_word="हेलमेट",
            pre_roll_ms=80,
            asset_path="C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobooks/sound_bank/foley/OGG/metalClick.ogg",
            asset_name="metalClick.ogg",
            gain_dbfs=-16.0,
            azimuth_pan=0.1,
            reverb_send=0.25,
            start_ms=seg_map[474][0] + 350,
            duration_ms=1500,
        ),
        # Act V - Seg 485: Swords clash in the brawl
        FoleyCue(
            cue_id="fol_06_sword_clash",
            segment_index=485,
            anchor_word="तलवार",
            pre_roll_ms=50,
            asset_path="C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobooks/sound_bank/foley/sword_clash_sword_clash.1.ogg",
            asset_name="sword_clash_sword_clash.1.ogg",
            gain_dbfs=-15.0,
            azimuth_pan=-0.2,
            reverb_send=0.20,
            start_ms=seg_map[485][0] + 250,
            duration_ms=1800,
        ),
        # Act VI - Seg 540: Magic shockwave / table crash
        FoleyCue(
            cue_id="fol_07_table_crash",
            segment_index=540,
            anchor_word="मेज़",
            pre_roll_ms=80,
            asset_path="C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobooks/sound_bank/foley/OGG/chop.ogg",
            asset_name="chop.ogg",
            gain_dbfs=-16.0,
            azimuth_pan=0.2,
            reverb_send=0.30,
            start_ms=seg_map[540][0] + 200,
            duration_ms=1500,
        ),
        # Act VII - Seg 605: Standing up at dawn
        FoleyCue(
            cue_id="fol_08_dawn_step",
            segment_index=605,
            anchor_word="कदम",
            pre_roll_ms=100,
            asset_path="C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobooks/sound_bank/foley/OGG/cloth2.ogg",
            asset_name="cloth2.ogg",
            gain_dbfs=-22.0,
            azimuth_pan=0.0,
            reverb_send=0.15,
            start_ms=seg_map[605][0] + 300,
            duration_ms=1200,
        ),
    ]

    # Environmental Ambience Bed (Stone castle great hall with distant hearth fire)
    ambience_scenes = [
        AmbienceScene(
            scene_id=1,
            start_ms=0,
            end_ms=total_dur_ms,
            asset_path="C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobooks/sound_bank/cache/AMB/fireplace_burning_loop.ogg",
            target_lufs=-34.0,
            reverb_preset="room",
            asset_name="fireplace_burning_loop.ogg"
        )
    ]

    manifest = CreativeManifest(
        manifest_version="3.0",
        project_id="witcher1",
        chapter_id="chapter_008",
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

    manifest_file = manifests_dir / "chapter_008_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        f.write(manifest.to_json(indent=2))
    print(f"[+] Creative Manifest compiled: {manifest_file.name}")

    # -------------------------------------------------------------------------
    # STEP 4: MASTER AUDIO COMPILATION & EBU R128 BROADCAST CERTIFICATION
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 4: MASTER COMPILATION & BROADCAST LOUDNESS CERTIFICATION")
    print("-" * 80)

    final_master_m4a = mastered_dir / "chapter_008_cinematic.m4a"
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
    print("  CHAPTER 008 BROADCAST MASTER CERTIFICATION")
    print("=" * 80)
    print("\n".join(summary_lines[-16:]))
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
