#!/usr/bin/env python3
"""
Audiobook Studio - Room 1 Ingestion CLI Command.
Standard: v6.0-ENTERPRISE-DAG
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

from audiobook_factory.core.cache.ledger import PipelineLedger
from audiobook_factory.rooms.room1_ingest.engine import IngestionEngine


def configure_ingest_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Configures argument parser for 'ingest' subcommand."""
    parser = subparsers.add_parser(
        "ingest",
        help="Extract EPUB/PDF/TXT, build AST manifest, BookBible & CastLock (Room 1)",
    )
    parser.add_argument("source_file", help="Path to input novel/manuscript (.epub, .pdf, .txt, .md)")
    parser.add_argument("--project-id", default=None, help="Custom project ID slug (default: derived from filename)")
    parser.add_argument("--title", default=None, help="Novel title override")
    parser.add_argument("--author", default="Unknown Author", help="Novel author name")
    parser.add_argument(
        "--fidelity",
        choices=["RAW_UNRATED", "CLASSIC_REVERENT"],
        default="RAW_UNRATED",
        help="Translation & prose fidelity tier (default: RAW_UNRATED)",
    )
    parser.add_argument("--project-dir", default=None, help="Target project directory")
    return parser


def handle_ingest_command(args: argparse.Namespace) -> int:
    """Executes Room 1 Ingestion CLI handler."""
    src_path = Path(args.source_file).resolve()
    if not src_path.exists():
        print(f"❌ [Error]: Source file does not exist: {src_path}", file=sys.stderr)
        return 1

    proj_dir = Path(args.project_dir).resolve() if args.project_dir else Path.cwd() / "projects" / (args.project_id or src_path.stem.lower().replace(" ", "_"))
    proj_dir.mkdir(parents=True, exist_ok=True)

    ledger_path = proj_dir / "pipeline_ledger.db"
    ledger = PipelineLedger(db_path=ledger_path)
    engine = IngestionEngine(project_dir=proj_dir, ledger=ledger)

    print(f"[*] Ingesting source: {src_path.name}")
    print(f"[*] Output Project Directory: {proj_dir}")

    try:
        manifest, bible, cast_lock, gate_audit = engine.process_source(
            source_path=src_path,
            book_id=args.project_id,
            title=args.title,
            author=args.author,
            fidelity_tier=args.fidelity,
        )
    except Exception as e:
        print(f"❌ [Ingestion Failed]: {e}", file=sys.stderr)
        return 1

    print("\n==================================================")
    print(f" 📖 Ingestion Complete: {manifest.title} by {manifest.author}")
    print(f" - Book ID: {manifest.book_id}")
    print(f" - Total Chapters: {manifest.total_chapters}")
    print(f" - Total Sentences: {gate_audit.metrics.get('total_sentences', 0)}")
    print(f" - Gate 0.1 Decision: {gate_audit.decision}")
    print("==================================================")
    print(f" [+] Manifest: {proj_dir / 'raw_book_manifest.json'}")
    print(f" [+] BookBible: {proj_dir / 'book_bible.json'}")
    print(f" [+] CastLock: {proj_dir / 'cast_lock.json'}")

    return 0 if gate_audit.decision == "PASSED" else 1
