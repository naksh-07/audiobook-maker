#!/usr/bin/env python3
"""
Audiobook Studio - Room 2 Translation Collective CLI Command.
Standard: v6.0-ENTERPRISE-DAG
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from audiobook_factory.contracts.ingestion import RawBookManifest
from audiobook_factory.contracts.lore import BookBible
from audiobook_factory.core.cache.ledger import PipelineLedger
from audiobook_factory.rooms.room2_translate.collective import TranslationCollective


def configure_translate_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Configures argument parser for 'translate' subcommand."""
    parser = subparsers.add_parser(
        "translate",
        help="Execute 4-agent translation collective or patch a beat (Room 2)",
    )
    parser.add_argument("project", help="Project ID or project directory path")
    parser.add_argument("--chapter", type=int, default=1, help="Chapter number to translate (default: 1)")
    parser.add_argument(
        "--mode",
        choices=["RAW_UNRATED", "CLASSIC_REVERENT"],
        default="RAW_UNRATED",
        help="Translation mode & register (default: RAW_UNRATED)",
    )
    parser.add_argument("--patch-beat", default=None, help="Beat UID to surgically patch (e.g. ch01_beat002)")
    parser.add_argument("--patch-json", default=None, help="JSON string or file path containing patched sentences")
    return parser


def handle_translate_command(args: argparse.Namespace) -> int:
    """Executes Room 2 Translation CLI handler."""
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

    ledger_path = proj_dir / "pipeline_ledger.db"
    ledger = PipelineLedger(db_path=ledger_path)
    collective = TranslationCollective(project_dir=proj_dir, ledger=ledger)

    # Handle surgical beat patching if requested
    if args.patch_beat:
        if not args.patch_json:
            print("❌ [Error]: --patch-json is required when --patch-beat is specified.", file=sys.stderr)
            return 1
        
        # Load patched sentences JSON
        try:
            p_path = Path(args.patch_json)
            if p_path.exists():
                patch_data = json.loads(p_path.read_text(encoding="utf-8"))
            else:
                patch_data = json.loads(args.patch_json)
        except Exception as e:
            print(f"❌ [Error]: Failed to parse patch JSON: {e}", file=sys.stderr)
            return 1

        print(f"[*] Surgically patching beat '{args.patch_beat}' in Chapter {args.chapter}...")
        try:
            new_manifest = collective.patch_beat(
                chapter_id=args.chapter,
                beat_uid=args.patch_beat,
                patched_sentences=patch_data,
                project_id=proj_id,
            )
            print(f"✅ [Success]: Beat '{args.patch_beat}' patched. Downstream stages marked DIRTY.")
            return 0
        except Exception as e:
            print(f"❌ [Patch Failed]: {e}", file=sys.stderr)
            return 1

    # Standard translation workflow
    manifest_file = proj_dir / "raw_book_manifest.json"
    if not manifest_file.exists():
        print(f"❌ [Error]: Raw book manifest not found: {manifest_file}. Run 'ingest' first.", file=sys.stderr)
        return 1

    manifest = RawBookManifest.model_validate_json(manifest_file.read_text(encoding="utf-8"))
    target_chapter = next((c for c in manifest.chapters if c.chapter_id == args.chapter), None)
    if not target_chapter:
        print(f"❌ [Error]: Chapter {args.chapter} not found in manifest (Total: {len(manifest.chapters)}).", file=sys.stderr)
        return 1

    bible_file = proj_dir / "book_bible.json"
    bible = BookBible.model_validate_json(bible_file.read_text(encoding="utf-8")) if bible_file.exists() else None

    print(f"[*] Translating Chapter {args.chapter}: '{target_chapter.title}' (Sentences: {len(target_chapter.sentences)})...")

    try:
        trans_manifest, gate_audit = collective.translate_chapter(
            chapter=target_chapter,
            bible=bible,
            mode=args.mode,
            project_id=proj_id,
        )
    except Exception as e:
        print(f"❌ [Translation Failed]: {e}", file=sys.stderr)
        return 1

    print("\n==================================================")
    print(f" 🌐 Translation Complete: Chapter {args.chapter}")
    print(f" - Mode: {trans_manifest.translation_mode}")
    print(f" - Total Beats: {len(trans_manifest.beats)}")
    print(f" - Total Sentences: {gate_audit.metrics.get('total_sentences', 0)}")
    print(f" - Gate 1.0 Decision: {gate_audit.decision}")
    print("==================================================")
    print(f" [+] Output Manifest: {proj_dir / f'chapter_{args.chapter:03d}_translation.json'}")

    return 0 if gate_audit.decision == "PASSED" else 1
