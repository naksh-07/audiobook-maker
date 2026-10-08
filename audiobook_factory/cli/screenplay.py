#!/usr/bin/env python3
"""
Audiobook Studio - Room 3 Screenplay & Anti-Swap Dramaturgy CLI Command.
Standard: v6.0-ENTERPRISE-DAG
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

from audiobook_factory.contracts.lore import CastLock
from audiobook_factory.contracts.screenplay import ScreenplayScript
from audiobook_factory.contracts.translation import TranslationManifest
from audiobook_factory.core.cache.ledger import PipelineLedger
from audiobook_factory.rooms.room3_screenplay.dramaturge import ScreenplayDramaturge


def configure_screenplay_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Configures argument parser for 'screenplay' subcommand."""
    parser = subparsers.add_parser(
        "screenplay",
        help="Generate multi-cast screenplay with 4D acoustic formants (Room 3)",
    )
    parser.add_argument("project", help="Project ID or project directory path")
    parser.add_argument("--chapter", type=int, default=1, help="Chapter number to script (default: 1)")
    parser.add_argument(
        "--reconcile",
        action="store_true",
        help="Reconcile existing screenplay script preserving user-locked segments",
    )
    return parser


def handle_screenplay_command(args: argparse.Namespace) -> int:
    """Executes Room 3 Screenplay Dramaturgy CLI handler."""
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

    trans_file = proj_dir / f"chapter_{args.chapter:03d}_translation.json"
    if not trans_file.exists():
        print(f"❌ [Error]: Translation manifest not found: {trans_file}. Run 'translate' first.", file=sys.stderr)
        return 1

    trans_manifest = TranslationManifest.model_validate_json(trans_file.read_text(encoding="utf-8"))

    cast_lock_file = proj_dir / "cast_lock.json"
    cast_lock = CastLock.model_validate_json(cast_lock_file.read_text(encoding="utf-8")) if cast_lock_file.exists() else None

    ledger_path = proj_dir / "pipeline_ledger.db"
    ledger = PipelineLedger(db_path=ledger_path)
    dramaturge = ScreenplayDramaturge(project_dir=proj_dir, ledger=ledger)

    script_file = proj_dir / f"chapter_{args.chapter:03d}_screenplay.json"

    if args.reconcile and script_file.exists():
        print(f"[*] Reconciling existing screenplay for Chapter {args.chapter} (preserving user locks)...")
        try:
            existing_script = ScreenplayScript.model_validate_json(script_file.read_text(encoding="utf-8"))
            reconciled_script = dramaturge.reconcile_screenplay(
                existing_script=existing_script,
                new_manifest=trans_manifest,
                cast_lock=cast_lock,
            )
            script_file.write_text(reconciled_script.to_canonical_json(), encoding="utf-8")
            gate_audit = dramaturge.audit_gate_2_0(reconciled_script)
            script = reconciled_script
        except Exception as e:
            print(f"❌ [Reconciliation Failed]: {e}", file=sys.stderr)
            return 1
    else:
        print(f"[*] Building screenplay for Chapter {args.chapter} (Beats: {len(trans_manifest.beats)})...")
        try:
            script, gate_audit = dramaturge.build_screenplay(
                manifest=trans_manifest,
                cast_lock=cast_lock,
                project_id=proj_id,
            )
        except Exception as e:
            print(f"❌ [Screenplay Generation Failed]: {e}", file=sys.stderr)
            return 1

    print("\n==================================================")
    print(f" 🎭 Screenplay Complete: Chapter {args.chapter}")
    print(f" - Total Segments: {len(script.segments)}")
    print(f" - Turn Inversions: {gate_audit.metrics.get('speaker_turn_inversions', 0)}")
    print(f" - Quote Leakage: {gate_audit.metrics.get('quote_leakage_count', 0)}")
    print(f" - Gate 2.0 Decision: {gate_audit.decision}")
    print("==================================================")
    print(f" [+] Screenplay Script: {script_file}")

    return 0 if gate_audit.decision == "PASSED" else 1
