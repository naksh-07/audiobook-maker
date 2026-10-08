#!/usr/bin/env python3
"""
Audiobook Studio - Room 4 Multi-Cast TTS & Dialogue Editorial CLI Command.
Standard: v6.0-ENTERPRISE-DAG
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

from audiobook_factory.contracts.screenplay import ScreenplayScript
from audiobook_factory.core.cache.ledger import PipelineLedger
from audiobook_factory.core.cache.take_bank import TakeBank
from audiobook_factory.rooms.room4_synth.synth_engine import SynthesisAndEditorialEngine


def configure_synth_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Configures argument parser for 'synth' subcommand."""
    parser = subparsers.add_parser(
        "synth",
        help="Synthesize chapter takes with TakeBank caching & assemble dialogue stem (Room 4)",
    )
    parser.add_argument("project", help="Project ID or project directory path")
    parser.add_argument("--chapter", type=int, default=1, help="Chapter number to synthesize (default: 1)")
    parser.add_argument("--workers", type=int, default=4, help="Max concurrent TTS workers (default: 4)")
    return parser


def handle_synth_command(args: argparse.Namespace) -> int:
    """Executes Room 4 Multi-Cast TTS & Editorial CLI handler."""
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

    script_file = proj_dir / f"chapter_{args.chapter:03d}_screenplay.json"
    if not script_file.exists():
        print(f"❌ [Error]: Screenplay script not found: {script_file}. Run 'screenplay' first.", file=sys.stderr)
        return 1

    script = ScreenplayScript.model_validate_json(script_file.read_text(encoding="utf-8"))

    ledger_path = proj_dir / "pipeline_ledger.db"
    ledger = PipelineLedger(db_path=ledger_path)
    take_bank = TakeBank(cache_dir=proj_dir / ".cache", ledger=ledger)
    synth_engine = SynthesisAndEditorialEngine(
        project_dir=proj_dir,
        take_bank=take_bank,
        ledger=ledger,
    )

    print(f"[*] Synthesizing Chapter {args.chapter} (Segments: {len(script.segments)})...")

    try:
        manifest, gate_audit = synth_engine.synthesize_chapter(
            script=script,
            project_id=proj_id,
            max_workers=args.workers,
        )
    except Exception as e:
        print(f"❌ [Synthesis Failed]: {e}", file=sys.stderr)
        return 1

    total_takes = len(manifest.takes)
    cache_hits = sum(1 for t in manifest.takes if t.was_cache_hit)
    hit_rate = (cache_hits / total_takes * 100.0) if total_takes > 0 else 0.0

    print("\n==================================================")
    print(f" 🎙️ Synthesis & Stem Assembly Complete: Chapter {args.chapter}")
    print(f" - Total Takes: {total_takes}")
    print(f" - TakeBank Cache Hits: {cache_hits}/{total_takes} ({hit_rate:.1f}%)")
    print(f" - Stem Duration: {manifest.timeline_ledger.total_duration_sec:.2f}s")
    print(f" - Timeline Cues: {len(manifest.timeline_ledger.cues)}")
    print(f" - Gate 4.0 Decision: {gate_audit.decision}")
    print("==================================================")
    print(f" [+] Dialogue Stem WAV: {manifest.lossless_dialogue_wav_path}")

    return 0 if gate_audit.decision == "PASSED" else 1
