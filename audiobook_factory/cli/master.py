#!/usr/bin/env python3
"""
Audiobook Studio - Room 5 Broadcast Vocal Mastering CLI Command.
Standard: v6.0-ENTERPRISE-DAG
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

from audiobook_factory.contracts.editorial import (
    ChapterDialogueManifest,
    TimelineCueRecord,
    TimelineLedger,
)
from audiobook_factory.core.cache.ledger import PipelineLedger
from audiobook_factory.core.mastering.loudnorm import MasteringSpec
from audiobook_factory.rooms.room5_master.master_engine import BroadcastMasteringEngine


def configure_master_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Configures argument parser for 'master' subcommand."""
    parser = subparsers.add_parser(
        "master",
        help="Execute Two-Pass Linear Loudnorm (-19.0 LUFS) & Gate 5.0 audit (Room 5)",
    )
    parser.add_argument("project", help="Project ID or project directory path")
    parser.add_argument("--chapter", type=int, default=1, help="Chapter number to master (default: 1)")
    parser.add_argument(
        "--target-lufs",
        type=float,
        default=-19.0,
        help="Target integrated vocal loudness in LUFS (default: -19.0)",
    )
    return parser


def handle_master_command(args: argparse.Namespace) -> int:
    """Executes Room 5 Broadcast Vocal Mastering CLI handler."""
    proj_input = Path(args.project)
    if proj_input.is_dir():
        proj_dir = proj_input.resolve()
        proj_id = proj_dir.name
    else:
        proj_dir = Path.cwd() / "projects" / args.project
        proj_id = args.project

    if not proj_dir.exists():
        print(f"❌ [Error]: Project directory does not exist: {proj_dir}", file=sys.stderr)
        return 1

    stem_file = proj_dir / f"chapter_{args.chapter:03d}_dialogue.wav"
    if not stem_file.exists():
        print(f"❌ [Error]: Dialogue stem WAV not found: {stem_file}. Run 'synth' first.", file=sys.stderr)
        return 1

    ledger_path = proj_dir / "pipeline_ledger.db"
    ledger = PipelineLedger(db_path=ledger_path)
    spec = MasteringSpec(target_lufs=args.target_lufs)
    master_engine = BroadcastMasteringEngine(project_dir=proj_dir, ledger=ledger, spec=spec)

    dialogue_manifest = ChapterDialogueManifest(
        chapter_id=args.chapter,
        script_hash="script_hash_dummy",
        lossless_dialogue_wav_path=str(stem_file),
        timeline_ledger=TimelineLedger(
            chapter_id=args.chapter,
            total_duration_sec=1.0,
            cues=[
                TimelineCueRecord(
                    segment_uid=f"ch{args.chapter:02d}_seg001",
                    speaker="Narrator",
                    start_time_sec=0.0,
                    end_time_sec=1.0,
                )
            ],
        ),
        takes=[],
    )

    print(f"[*] Mastering Chapter {args.chapter} to EBU R128 standard ({args.target_lufs} LUFS)...")

    try:
        artifact, gate_audit = master_engine.master_chapter(
            dialogue_manifest=dialogue_manifest,
            project_id=proj_id,
            target_lufs=args.target_lufs,
        )
    except Exception as e:
        print(f"❌ [Mastering Failed]: {e}", file=sys.stderr)
        return 1

    comp = artifact.compliance

    print("\n==================================================")
    print(f" 🎚️ Mastering Complete: Chapter {args.chapter}")
    print(f" - Integrated Loudness: {comp.integrated_lufs:.2f} LUFS (Target: {args.target_lufs:.1f})")
    print(f" - True Peak: {comp.true_peak_dbfs:.2f} dBTP (Ceiling: <= -1.5 dBTP)")
    print(f" - Loudness Range: {comp.loudness_range_lu:.2f} LU")
    print(f" - Duration: {artifact.duration_sec:.2f}s")
    print(f" - Gate 5.0 Decision: {gate_audit.decision}")
    print("==================================================")
    print(f" [+] Mastered M4A: {artifact.mastered_audio_path}")

    return 0 if gate_audit.decision == "PASSED" else 1
