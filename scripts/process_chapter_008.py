#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 8 Complete Production & Broadcast Mastering.
Executes Gate 4.5, Gate 5 (Agent Director + Sound Bible + FTS5), and Broadcast Mastering.
"""

import sys
import json
import time
import subprocess
from pathlib import Path

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
from audiobook_factory.timeline_ledger import (
    build_audio_transcript_ledger,
    stitch_dialogue_track_from_ledger,
)
from audiobook_factory.gate_auditor import audit_gate4_ledger
from audiobook_factory.agent_director import AgentDirector
from audiobook_factory.sonic_bible import SonicBible
from audiobook_factory.sound_bank import get_sound_bank
from audiobook_factory.manifest_renderer import render_manifest_soundscape


def main():
    project_dir = ROOT_DIR / "audiobooks" / "projects" / "witcher1"
    scripts_dir = project_dir / "scripts"
    audio_chunks_dir = project_dir / "audio_chunks"
    mastered_dir = project_dir / "mastered"
    manifests_dir = project_dir / "manifests"

    mastered_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)

    script_path = scripts_dir / "chapter_008_hi_script.json"
    bible_path = project_dir / "sound_bible.json"
    manifest_file = manifests_dir / "chapter_008_manifest.json"
    ledger_path = scripts_dir / "chapter_008_timeline_ledger.json"
    dialogue_wav_path = mastered_dir / "chapter_008_dialogue.wav"
    final_master_m4a = mastered_dir / "chapter_008_cinematic.m4a"

    print("=" * 80)
    print("  AUDIOBOOK FACTORY - CHAPTER 008 PRODUCTION & MASTERING")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # STEP 1: Verify Gate 4 Audio Chunks (706/706)
    # -------------------------------------------------------------------------
    print("\n[*] Verifying Gate 4 Chunks on disk (706 segments)...")
    with open(script_path, "r", encoding="utf-8") as f:
        script_segments = json.load(f)
    total_segments = len(script_segments)

    missing = []
    for idx in range(1, total_segments + 1):
        matches = list(audio_chunks_dir.glob(f"c008_s{idx:04d}_*.wav"))
        if not matches or matches[0].stat().st_size < 1000:
            missing.append(idx)

    if missing:
        raise RuntimeError(f"Gate 4 Incomplete: missing chunks: {missing}")
    print(f"[+] Gate 4 Complete: 100% of chunks ({total_segments}/{total_segments}) verified intact on disk!")

    # -------------------------------------------------------------------------
    # STEP 2: GATE 4.5 - TIMELINE LEDGER & MASTER DIALOGUE STEM
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 2: GATE 4.5 - TIMELINE LEDGER & MASTER DIALOGUE STEM")
    print("-" * 80)

    print("[*] Building sample-accurate timeline ledger...")
    ledger = build_audio_transcript_ledger(
        project_dir=project_dir,
        chapter_num=8,
        script_file=script_path,
        audio_dir=audio_chunks_dir,
        output_ledger_file=ledger_path,
        default_pause_ms=400,
    )

    print(f"[*] Stitching dialogue master stem -> {dialogue_wav_path.name}...")
    stitch_dialogue_track_from_ledger(
        ledger=ledger,
        audio_dir=audio_chunks_dir,
        output_wav_path=dialogue_wav_path,
        sample_rate=24000,
    )

    print("[*] Running Gate 4.5 Forensic Audit...")
    audit_report = audit_gate4_ledger(
        ledger_file=ledger_path,
        script_file=script_path,
        audio_dir=audio_chunks_dir,
    )
    print(f"[+] Gate 4.5 Audit Status: {audit_report.get('status', 'OK')}")
    print(f"    Total Timeline Duration: {ledger.total_timeline_duration_ms / 1000.0:.2f}s ({ledger.total_timeline_duration_ms / 60000.0:.2f} min)")
    print(f"    Raw Speech Duration    : {ledger.total_dialogue_duration_ms / 1000.0:.2f}s")
    print(f"    Text Retention Ratio   : {audit_report.get('text_match_ratio', 1.0) * 100.0:.1f}%")

    # -------------------------------------------------------------------------
    # STEP 3: GATE 5 - AGENT DIRECTOR & SONIC BIBLE CREATIVE MANIFEST
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 3: GATE 5 - CREATIVE MANIFEST (AgentDirector + Sonic Bible + FTS5)")
    print("-" * 80)

    sound_bank = get_sound_bank()
    active_bible = SonicBible.load_from_disk(bible_path) if bible_path.exists() else None
    director = AgentDirector(
        sound_bank=sound_bank,
        sonic_bible=active_bible,
        project_dir=project_dir,
    )

    manifest = director.direct_chapter_manifest(
        chapter_id="chapter_008",
        script_segments=script_segments,
        segment_durations_sec={s.segment_index: s.duration_ms / 1000.0 for s in ledger.segments},
        dialogue_stem_path=dialogue_wav_path,
        total_duration_sec=ledger.total_timeline_duration_ms / 1000.0,
        timeline_ledger=ledger,
        project_dir=project_dir,
        sonic_bible=active_bible,
    )

    with open(manifest_file, "w", encoding="utf-8") as f:
        f.write(manifest.to_json(indent=2))
    print(f"[+] Creative Manifest generated: {manifest_file.name}")
    print(f"    Music Cues     : {len(manifest.music_cues)}")
    print(f"    Foley Cues     : {len(manifest.foley_cues)}")
    print(f"    Ambience Beds  : {len(manifest.ambience_scenes)}")
    print(f"    Silence Sweet Spot: {manifest.silence_percentage}%")

    # -------------------------------------------------------------------------
    # STEP 4: MASTER AUDIO COMPILATION & EBU R128 BROADCAST CERTIFICATION
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 4: MASTER COMPILATION & BROADCAST LOUDNESS CERTIFICATION")
    print("-" * 80)

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
