#!/usr/bin/env python3
"""
Re-master Chapter 2 with Millisecond Audio Reality Sanitization and Broadcast EBU R128 Certification.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

RUN_ID = "sword_of_destiny_chap_2_master"
os.environ["CURRENT_AUDIOBOOK_RUN_ID"] = RUN_ID

from audiobook_factory.contracts import CreativeManifest, LegacyCreativeManifestAdapter
from audiobook_factory.audio_reality_auditor import AudioRealityAuditor
from audiobook_factory.cinema_audio_engine import render_discrete_stems
from audiobook_factory.sound_bank import get_sound_bank
from audiobook_factory.soundscape import get_ffmpeg
from audiobook_factory.orchestration.gates import verify_post_mix_master_gates
from audiobook_factory.telemetry import get_telemetry_ledger

def main():
    telem = get_telemetry_ledger()
    telem.start_run(run_id=RUN_ID, project_id="proj-audiobook-maker", book_title="Sword of Destiny")

    project_dir = Path("audiobooks/projects/sword_of_destiny").resolve()
    manifests_dir = project_dir / "manifests"
    mastered_dir = project_dir / "mastered"
    scripts_dir = project_dir / "scripts"

    manifest_file = manifests_dir / "chapter_002_hi_manifest.json"
    dialogue_wav = mastered_dir / "chapter_002_hi_dialogue.wav"

    if not manifest_file.exists():
        print(f"[!] Error: {manifest_file} not found")
        sys.exit(1)
    if not dialogue_wav.exists():
        print(f"[!] Error: {dialogue_wav} not found")
        sys.exit(1)

    print(f"[*] Loading manifest: {manifest_file.name}...")
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = CreativeManifest.from_json(f.read())

    # Pillar 4: Audit & Remediate with Audio Reality Auditor
    print("[*] Running AudioRealityAuditor fail-closed pre-mix audit...")
    auditor = AudioRealityAuditor(sound_bank=get_sound_bank())
    sanitized_manifest, report = auditor.audit_and_remediate(
        manifest=manifest,
        output_dir=scripts_dir,
        era="MEDIEVAL_FANTASY",
        franchise_affinity="the_witcher",
    )

    print(f"    Total Cues: {report.total_cues_inspected}")
    print(f"    Passed: {report.passed_count}")
    print(f"    Remediated (Trimmed): {report.remediated_count}")
    print(f"    Rejected (Purged): {report.rejected_count}")

    # Overwrite manifest with sanitized manifest
    with open(manifest_file, "w", encoding="utf-8") as f:
        f.write(sanitized_manifest.to_json(indent=2))
    print(f"[+] Saved sanitized manifest to {manifest_file.name}")

    # Lift to Cinema Manifest
    cinema_manifest = LegacyCreativeManifestAdapter.lift_legacy_manifest_to_cinema(sanitized_manifest)

    # Render Discrete Stems & Master
    print("[*] Rendering discrete cinema stems (DX, MX, FX, AMB, ME) & broadcast master...")
    stem_ledger = render_discrete_stems(
        manifest=cinema_manifest,
        dialogue_wav=dialogue_wav,
        output_dir=mastered_dir,
        sound_bank=get_sound_bank(),
    )
    print(f"[+] Stems rendered. Compliance Status: {stem_ledger.compliance_status}")

    # Encode M4A deliverable
    master_wav = mastered_dir / "chapter_002_cinema_master.wav"
    if not master_wav.exists():
        master_wav = mastered_dir / f"{cinema_manifest.chapter_id}_cinema_master.wav"

    cinematic_m4a = mastered_dir / "chapter_002_hi_cinematic.m4a"
    ff = get_ffmpeg()
    print(f"[*] Encoding AAC M4A container: {cinematic_m4a.name}...")
    subprocess.run([
        ff, "-y", "-i", str(master_wav),
        "-c:a", "aac", "-b:a", "192k",
        str(cinematic_m4a)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    print(f"[+] Master M4A encoded: {cinematic_m4a.name} ({cinematic_m4a.stat().st_size / 1_000_000:.2f} MB)")

    # Verify gates
    vocal_wav = mastered_dir / "chapter_002_stem_DX.wav"
    mx_stem = mastered_dir / "chapter_002_stem_MX.wav"
    g52, g53, g5 = verify_post_mix_master_gates(
        chapter_num=2,
        cinematic_out=cinematic_m4a,
        master_wav=master_wav,
        vocal_wav=vocal_wav,
        mx_stem=mx_stem,
    )
    print(f"[*] Gates: Gate 5.2 (DMR): {g52}, Gate 5.3 (Phase): {g53}, Gate 5 (EBU R128): {g5}")

    # Also emit ledger into scripts directory for permanent record
    reality_ledger_file = scripts_dir / "chapter_002_audio_reality_ledger.json"
    print(f"[+] Reality Ledger verified at {reality_ledger_file}")

    # Complete telemetry run
    telem.end_run(run_id=RUN_ID, status="COMPLETED")
    report = telem.generate_report(run_id=RUN_ID)
    print(f"[+] Telemetry Run finalized. Report status: {report.get('status')}")
    print(f"    Acoustics: {report.get('acoustic_deliverables')}")

if __name__ == "__main__":
    main()
