#!/usr/bin/env python3
"""
Custom Standalone Producer: Chapter 2 Authentic Witcher 3 Soundscape & Remaster.
================================================================================
Zero howling wind loops.
Zero Greek market / modern traffic / radio chatter.
Pure Witcher 3 audio drama soundscape:
- Act 1: Ruined Cellar Entrance (dungeon_cave_bed, soil footsteps, dagger unsheathe, basilisk monster head thud)
- Act 2: Road & Settlement (calm country air, coin pouch toss, mud footsteps)
- Act 3: The Pensive Dragon Tavern (fireplace hearth, authentic medieval tavern murmur, wooden door open/close,
         ale pouring, wooden bowls/spoons, tankard clink, iconic Witcher 3 OST "The Inn by the Crossroads")
"""

import os
import sys
import json
import subprocess
from pathlib import Path

# Setup environment
os.environ["CURRENT_AUDIOBOOK_RUN_ID"] = "sword_of_destiny_chap_2_witcher_master"

from audiobook_factory.contracts import (
    CreativeManifest,
    FoleyCue,
    AmbienceScene,
    MusicCue,
    MasteringConfig,
    LegacyCreativeManifestAdapter,
)
from audiobook_factory.cinema_audio_engine import render_discrete_stems
from audiobook_factory.sound_bank import get_sound_bank
from audiobook_factory.soundscape import get_ffmpeg
from audiobook_factory.orchestration.gates import verify_post_mix_master_gates

def main():
    root_dir = Path(__file__).resolve().parent.parent
    project_dir = root_dir / "audiobooks" / "projects" / "sword_of_destiny"
    sound_bank_dir = root_dir / "audiobooks" / "sound_bank"
    manifests_dir = project_dir / "manifests"
    mastered_dir = project_dir / "mastered"
    scripts_dir = project_dir / "scripts"

    dialogue_wav = mastered_dir / "chapter_002_hi_dialogue.wav"
    timeline_file = scripts_dir / "chapter_002_hi_timeline_ledger.json"

    if not dialogue_wav.exists():
        print(f"[!] Critical Error: Dialogue WAV not found at {dialogue_wav}")
        sys.exit(1)
    if not timeline_file.exists():
        print(f"[!] Critical Error: Timeline ledger not found at {timeline_file}")
        sys.exit(1)

    print("[*] Loading timeline ledger...")
    timeline_data = json.loads(timeline_file.read_text(encoding="utf-8"))
    timeline_items = timeline_data.get("timeline", [])
    seg_starts_ms = {item["segment_index"]: int(item["t_start_ms"]) for item in timeline_items}
    total_dur_ms = int(timeline_data.get("total_duration_ms", 781580))

    print(f"[*] Total duration: {total_dur_ms / 1000.0:.2f}s ({len(seg_starts_ms)} segments)")

    # -------------------------------------------------------------------------
    # 1. Define Authentic Ambience Scenes
    # -------------------------------------------------------------------------
    # Act 1: 0ms -> 333000ms (Ruined cellar pit outside village)
    # Act 2: 333000ms -> 568000ms (Departure & road)
    # Act 3: 568000ms -> end (The Pensive Dragon Tavern / Inn)
    amb_scenes = [
        AmbienceScene(
            scene_id=1,
            start_ms=0,
            end_ms=333000,
            asset_path=str((sound_bank_dir / "ambience" / "dungeon_cave_bed.ogg").resolve()).replace("\\", "/"),
            target_lufs=-36.0,
            reverb_preset="cave",
            asset_name="dungeon_cave_bed.ogg",
        ),
        AmbienceScene(
            scene_id=2,
            start_ms=333000,
            end_ms=568000,
            asset_path=str((sound_bank_dir / "ambience" / "amb_bog_swamp_night.wav").resolve()).replace("\\", "/"),
            target_lufs=-38.0,
            reverb_preset="room",
            asset_name="amb_bog_swamp_night.wav",
        ),
        AmbienceScene(
            scene_id=3,
            start_ms=568000,
            end_ms=total_dur_ms,
            asset_path=str((sound_bank_dir / "ambience" / "amb_castle_hall_hearth.wav").resolve()).replace("\\", "/"),
            target_lufs=-34.0,
            reverb_preset="room",
            asset_name="amb_castle_hall_hearth.wav",
        ),
        AmbienceScene(
            scene_id=4,
            start_ms=568000,
            end_ms=total_dur_ms,
            asset_path=str((sound_bank_dir / "ambience" / "tavern_crowd_murmur.ogg").resolve()).replace("\\", "/"),
            target_lufs=-38.0,
            reverb_preset="room",
            asset_name="tavern_crowd_murmur.ogg",
        ),
    ]

    # -------------------------------------------------------------------------
    # 2. Define Authentic Witcher 3 Music Underscore Cues
    # -------------------------------------------------------------------------
    music_cues = [
        MusicCue(
            cue_id="mx_001",
            cue_type="TENSION_RISER",
            section_name="ruins_tension",
            track_name=str((sound_bank_dir / "music" / "witcher3_ost" / "006 A Nightmare of Frost.mp3").resolve()).replace("\\", "/"),
            start_ms=2000,
            duration_ms=102000,
            volume_db=-34.0,
            fade_in_ms=4000,
            fade_out_ms=5000,
        ),
        MusicCue(
            cue_id="mx_002",
            cue_type="EMOTIONAL_UNDERSCORE",
            section_name="geralt_theme",
            track_name=str((sound_bank_dir / "music" / "witcher3_ost" / "001 The White Wolf.mp3").resolve()).replace("\\", "/"),
            start_ms=333000,
            duration_ms=140000,
            volume_db=-33.0,
            fade_in_ms=4000,
            fade_out_ms=5000,
        ),
        MusicCue(
            cue_id="mx_003",
            cue_type="EMOTIONAL_UNDERSCORE",
            section_name="tavern_inn",
            track_name=str((sound_bank_dir / "music" / "witcher3_ost" / "022 The Inn by the Crossroads.mp3").resolve()).replace("\\", "/"),
            start_ms=570000,
            duration_ms=150000,
            volume_db=-32.0,
            fade_in_ms=3000,
            fade_out_ms=6000,
        ),
    ]

    # -------------------------------------------------------------------------
    # 3. Define Authentic Foley Cues (Physical Props & Story Actions)
    # -------------------------------------------------------------------------
    foley_cues = [
        # Act 1: Pit & Thugs
        FoleyCue(
            cue_id="fc_001",
            segment_index=4,
            anchor_word="कदम",
            asset_path=str((sound_bank_dir / "foley" / "tiny_soil-steps-01.wav").resolve()).replace("\\", "/"),
            asset_name="tiny_soil-steps-01.wav",
            start_ms=seg_starts_ms.get(4, 38000) + 150,
            duration_ms=1800,
            gain_dbfs=-18.0,
            azimuth_pan=-0.2,
        ),
        FoleyCue(
            cue_id="fc_002",
            segment_index=8,
            anchor_word="तलवार",
            asset_path=str((sound_bank_dir / "foley" / "tiny_knife-unsheathe-02.wav").resolve()).replace("\\", "/"),
            asset_name="tiny_knife-unsheathe-02.wav",
            start_ms=seg_starts_ms.get(8, 74000) + 200,
            duration_ms=1200,
            gain_dbfs=-15.0,
            azimuth_pan=0.2,
        ),
        FoleyCue(
            cue_id="fc_003",
            segment_index=17,
            anchor_word="म्यान",
            asset_path=str((sound_bank_dir / "foley" / "tiny_seax-sheathe-01.wav").resolve()).replace("\\", "/"),
            asset_name="tiny_seax-sheathe-01.wav",
            start_ms=seg_starts_ms.get(17, 182000) + 150,
            duration_ms=1100,
            gain_dbfs=-16.0,
            azimuth_pan=0.3,
        ),
        FoleyCue(
            cue_id="fc_004",
            segment_index=30,
            anchor_word="गिरा",
            asset_path=str((sound_bank_dir / "foley" / "tiny_metal-hammer-hit-02.wav").resolve()).replace("\\", "/"),
            asset_name="tiny_metal-hammer-hit-02.wav",
            start_ms=seg_starts_ms.get(30, 325000) + 500,
            duration_ms=1500,
            gain_dbfs=-14.0,
            azimuth_pan=0.0,
        ),

        # Act 2: Settlement & Departure
        FoleyCue(
            cue_id="fc_005",
            segment_index=33,
            anchor_word="सिक्के",
            asset_path=str((sound_bank_dir / "foley" / "OGG" / "handleCoins2.ogg").resolve()).replace("\\", "/"),
            asset_name="handleCoins2.ogg",
            start_ms=seg_starts_ms.get(33, 345000) + 300,
            duration_ms=1200,
            gain_dbfs=-15.0,
            azimuth_pan=-0.1,
        ),
        FoleyCue(
            cue_id="fc_006",
            segment_index=36,
            anchor_word="खटका",
            asset_path=str((sound_bank_dir / "foley" / "tiny_coins-shake-01.wav").resolve()).replace("\\", "/"),
            asset_name="tiny_coins-shake-01.wav",
            start_ms=seg_starts_ms.get(36, 375000) + 200,
            duration_ms=1400,
            gain_dbfs=-16.0,
            azimuth_pan=-0.2,
        ),
        FoleyCue(
            cue_id="fc_007",
            segment_index=44,
            anchor_word="चले",
            asset_path=str((sound_bank_dir / "foley" / "tiny_mud-steps-01.wav").resolve()).replace("\\", "/"),
            asset_name="tiny_mud-steps-01.wav",
            start_ms=seg_starts_ms.get(44, 520000) + 100,
            duration_ms=1600,
            gain_dbfs=-18.0,
            azimuth_pan=0.1,
        ),

        # Act 3: The Pensive Dragon Tavern
        FoleyCue(
            cue_id="fc_008",
            segment_index=51,
            anchor_word="दरवाजा",
            asset_path=str((sound_bank_dir / "foley" / "OGG" / "doorOpen_1.ogg").resolve()).replace("\\", "/"),
            asset_name="doorOpen_1.ogg",
            start_ms=seg_starts_ms.get(51, 569000) + 100,
            duration_ms=1800,
            gain_dbfs=-15.0,
            azimuth_pan=-0.3,
        ),
        FoleyCue(
            cue_id="fc_009",
            segment_index=52,
            anchor_word="बंद",
            asset_path=str((sound_bank_dir / "foley" / "OGG" / "doorClose_1.ogg").resolve()).replace("\\", "/"),
            asset_name="doorClose_1.ogg",
            start_ms=seg_starts_ms.get(52, 574000) + 200,
            duration_ms=1500,
            gain_dbfs=-15.0,
            azimuth_pan=-0.3,
        ),
        FoleyCue(
            cue_id="fc_010",
            segment_index=53,
            anchor_word="बैठे",
            asset_path=str((sound_bank_dir / "foley" / "tiny_floor-creak-01.wav").resolve()).replace("\\", "/"),
            asset_name="tiny_floor-creak-01.wav",
            start_ms=seg_starts_ms.get(53, 580000) + 300,
            duration_ms=1400,
            gain_dbfs=-16.0,
            azimuth_pan=0.2,
        ),
        FoleyCue(
            cue_id="fc_011",
            segment_index=55,
            anchor_word="उड़ेला",
            asset_path=str((sound_bank_dir / "foley" / "tiny_water-pour-01.wav").resolve()).replace("\\", "/"),
            asset_name="tiny_water-pour-01.wav",
            start_ms=seg_starts_ms.get(55, 590000) + 250,
            duration_ms=1900,
            gain_dbfs=-14.0,
            azimuth_pan=0.1,
        ),
        FoleyCue(
            cue_id="fc_012",
            segment_index=58,
            anchor_word="थाली",
            asset_path=str((sound_bank_dir / "foley" / "tiny_wood-bowl-spoon-01.wav").resolve()).replace("\\", "/"),
            asset_name="tiny_wood-bowl-spoon-01.wav",
            start_ms=seg_starts_ms.get(58, 625000) + 200,
            duration_ms=1500,
            gain_dbfs=-16.0,
            azimuth_pan=0.0,
        ),
        FoleyCue(
            cue_id="fc_013",
            segment_index=62,
            anchor_word="प्याला",
            asset_path=str((sound_bank_dir / "foley" / "OGG" / "metalClick.ogg").resolve()).replace("\\", "/"),
            asset_name="metalClick.ogg",
            start_ms=seg_starts_ms.get(62, 705000) + 300,
            duration_ms=900,
            gain_dbfs=-15.0,
            azimuth_pan=0.2,
        ),
        FoleyCue(
            cue_id="fc_014",
            segment_index=65,
            anchor_word="सिक्का",
            asset_path=str((sound_bank_dir / "foley" / "tiny_coin-spin-fall-01.wav").resolve()).replace("\\", "/"),
            asset_name="tiny_coin-spin-fall-01.wav",
            start_ms=seg_starts_ms.get(65, 735000) + 150,
            duration_ms=1300,
            gain_dbfs=-16.0,
            azimuth_pan=-0.1,
        ),
        FoleyCue(
            cue_id="fc_015",
            segment_index=70,
            anchor_word="कटोरा",
            asset_path=str((sound_bank_dir / "foley" / "tiny_wood-bowl-spoon-02.wav").resolve()).replace("\\", "/"),
            asset_name="tiny_wood-bowl-spoon-02.wav",
            start_ms=seg_starts_ms.get(70, 775000) + 100,
            duration_ms=1400,
            gain_dbfs=-17.0,
            azimuth_pan=0.0,
        ),
    ]

    # -------------------------------------------------------------------------
    # 4. Construct Fresh Manifest
    # -------------------------------------------------------------------------
    clean_manifest = CreativeManifest(
        manifest_version="3.0",
        chapter_id="chapter_002",
        project_id="proj-audiobook-maker",
        total_duration_ms=total_dur_ms,
        silence_percentage=65.0,
        mastering=MasteringConfig(
            target_lufs=-19.0,
            true_peak_dbtp=-1.5,
            ducking_attenuation_db=-16.0,
            ducking_attack_ms=20,
            ducking_release_ms=400,
            spectral_carve_hz=2200,
            spectral_carve_gain_db=-5.5,
        ),
        ambience_scenes=amb_scenes,
        music_cues=music_cues,
        foley_cues=foley_cues,
        metadata={
            "era": "MEDIEVAL_FANTASY",
            "franchise_affinity": "the_witcher",
            "curation": "authentic_witcher_sound_design",
            "wind_howl_purged": True,
            "greek_market_purged": True,
        },
    )

    manifest_file = manifests_dir / "chapter_002_hi_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        f.write(clean_manifest.to_json(indent=2))
    print(f"[+] Saved clean authentic manifest to: {manifest_file.name}")

    # -------------------------------------------------------------------------
    # 5. Lift to Cinema Manifest & Render Discrete Stems
    # -------------------------------------------------------------------------
    print("[*] Lifting to Cinema Audio Manifest...")
    cinema_manifest = LegacyCreativeManifestAdapter.lift_legacy_manifest_to_cinema(clean_manifest)

    print("[*] Rendering discrete cinema stems (DX, MX, FX, AMB, ME) & broadcast mastering...")
    stem_ledger = render_discrete_stems(
        manifest=cinema_manifest,
        dialogue_wav=dialogue_wav,
        output_dir=mastered_dir,
        sound_bank=get_sound_bank(),
    )
    print(f"[+] Stems successfully rendered. Compliance Status: {stem_ledger.compliance_status}")

    # -------------------------------------------------------------------------
    # 6. Encode AAC M4A Deliverable
    # -------------------------------------------------------------------------
    master_wav = mastered_dir / "chapter_002_cinema_master.wav"
    if not master_wav.exists():
        master_wav = mastered_dir / f"{cinema_manifest.chapter_id}_cinema_master.wav"

    cinematic_m4a = mastered_dir / "chapter_002_hi_cinematic.m4a"
    ff = get_ffmpeg()
    print(f"[*] Encoding master M4A: {cinematic_m4a.name}...")
    subprocess.run([
        ff, "-y", "-i", str(master_wav),
        "-c:a", "aac", "-b:a", "192k",
        str(cinematic_m4a)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    print(f"[+] Final Master Deliverable: {cinematic_m4a.name} ({cinematic_m4a.stat().st_size / 1_000_000:.2f} MB)")

    # -------------------------------------------------------------------------
    # 7. Quality Gate Verification
    # -------------------------------------------------------------------------
    vocal_wav = mastered_dir / "chapter_002_stem_DX.wav"
    mx_stem = mastered_dir / "chapter_002_stem_MX.wav"
    g52, g53, g5 = verify_post_mix_master_gates(
        chapter_num=2,
        cinematic_out=cinematic_m4a,
        master_wav=master_wav,
        vocal_wav=vocal_wav,
        mx_stem=mx_stem,
    )
    print(f"[*] Broadcast Certification Gates:")
    print(f"    - Gate 5.2 (Dialogue to Music Ratio DMR >= 12 dB): {g52}")
    print(f"    - Gate 5.3 (Stereo Phase Correlation r >= 0.20): {g53}")
    print(f"    - Gate 5.0 (EBU R128 Master -19 LUFS): {g5}")

    print("\n[SUCCESS] Chapter 2 completely remastered with authentic Witcher 3 sound design!")

if __name__ == "__main__":
    main()
