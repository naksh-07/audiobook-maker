#!/usr/bin/env python3
"""
Audiobook Factory - Command Line Interface (Vocals-Only Studio Engine).
Fast, reliable, multi-voice audiobook generation and EBU R128 mastering.
100% focused on vocal clarity, character attribution, and pristine M4B delivery.
"""

import os
import sys
import argparse
from pathlib import Path

# Configure UTF-8 for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WORKSPACE_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = WORKSPACE_DIR / "audiobooks" / "projects"

# Modular command handlers from audiobook_factory.cli
from audiobook_factory.cli.commands.pipeline import (
    cmd_extract,
    cmd_translate,
    cmd_script,
    cmd_synthesize,
    cmd_master,
    cmd_produce,
    cmd_auto,
)
from audiobook_factory.cli.commands.audio import (
    cmd_package,
)
from audiobook_factory.cli.commands.audit import (
    cmd_audit_book,
    cmd_audit,
)

__all__ = [
    "cmd_extract",
    "cmd_translate",
    "cmd_script",
    "cmd_synthesize",
    "cmd_master",
    "cmd_produce",
    "cmd_auto",
    "cmd_package",
    "cmd_audit_book",
    "cmd_audit",
    "WORKSPACE_DIR",
    "PROJECTS_DIR",
]


def main():
    parser = argparse.ArgumentParser(
        prog="audiobook-factory",
        description="Vocals-Only Production Audiobook Factory (Extraction, Translation, Multi-Voice TTS, Mastering & M4B Packaging)",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Pipeline step to execute")

    # extract
    p_extract = subparsers.add_parser("extract", help="Extract and segment book file into clean Markdown chapters")
    p_extract.add_argument("file", help="Input book path (.epub, .pdf, .txt, .md)")
    p_extract.add_argument("--force-gate", action="store_true", help="Bypass Extraction Quality Gate REVIEW failure and force production")

    # translate
    p_translate = subparsers.add_parser("translate", help="Translate extracted chapters into literary Hindi")
    p_translate.add_argument("book", help="Project book slug (folder name)")
    p_translate.add_argument("--model", default="gemini-3.8-flash", help="Gemini translation model (default: gemini-3.8-flash)")
    p_translate.add_argument("--chapter", type=int, default=None, help="Specific chapter number to translate")
    p_translate.add_argument("--chapters", type=str, default=None, help="Comma-separated or range of chapters (e.g. 1-2 or 1,2)")
    p_translate.add_argument("--force-gate", action="store_true", help="Bypass translation quality gate REVIEW failure and force production")

    # script
    p_script = subparsers.add_parser("script", help="Generate screenplay script JSON with speaker tags")
    p_script.add_argument("book", help="Project book slug")
    p_script.add_argument("--hindi", action="store_true", help="Use translated Hindi chapters")
    p_script.add_argument("--dramatized", action="store_true", help="Multi-voice character attribution mode")
    p_script.add_argument("--chapter", type=int, default=None, help="Specific chapter number to script")
    p_script.add_argument("--chapters", type=str, default=None, help="Comma-separated or range of chapters (e.g. 1-2 or 1,2)")
    p_script.add_argument("--overwrite", action="store_true", help="Overwrite existing script files")

    # synthesize
    p_synth = subparsers.add_parser("synthesize", help="Synthesize audio segments via Gemini Cloud TTS")
    p_synth.add_argument("book", help="Project book slug")
    p_synth.add_argument("--backend", default="gemini_tts", choices=["gemini_tts"], help="TTS engine (default: gemini_tts)")
    p_synth.add_argument("--voice", default="Aoede", help="Default voice persona")

    # master
    p_master = subparsers.add_parser("master", help="Concatenate segments and master audio with EBU R128 (-19 LUFS)")
    p_master.add_argument("book", help="Project book slug")

    # package
    p_pack = subparsers.add_parser("package", help="Assemble final chapterized M4B container")
    p_pack.add_argument("book", help="Project book slug or path")
    p_pack.add_argument("--cover", default=None, help="Cover art image path")
    p_pack.add_argument("--enforce-gate6", action="store_true", help="Abort packaging if any Gate 6 verification check fails")

    # audit-book
    p_audit_book = subparsers.add_parser("audit-book", help="Run Macro-Tier Gate 6 master audit across entire book project")
    p_audit_book.add_argument("project_dir", help="Project directory or book slug")

    # auto
    p_auto = subparsers.add_parser("auto", help="Run entire end-to-end vocals-only pipeline in one command")
    p_auto.add_argument("file", help="Input book path")
    p_auto.add_argument("--hindi", action="store_true", help="Translate English book to Hindi")
    p_auto.add_argument("--backend", default="gemini_tts", choices=["gemini_tts"], help="TTS engine (default: gemini_tts)")
    p_auto.add_argument("--voice", default="Aoede", help="Voice persona")
    p_auto.add_argument("--dramatized", action="store_true", help="Multi-voice dramatization")
    p_auto.add_argument("--cover", default=None, help="Cover art image path")
    p_auto.add_argument("--workers", default=3, type=int, help="Number of concurrent TTS synthesis workers (default: 3)")
    p_auto.add_argument("--force-gate", action="store_true", help="Bypass Extraction Quality Gate REVIEW failure and force production")
    p_auto.add_argument("--chapter", type=int, default=None, help="Specific chapter number to produce")
    p_auto.add_argument("--chapters", type=str, default=None, help="Comma-separated or range of chapters (e.g. 1-2 or 1,2)")

    # produce
    p_produce = subparsers.add_parser("produce", help="Produce mastered vocal chapters with EBU R128 (-19 LUFS) & timeline ledger")
    p_produce.add_argument("book", help="Project book slug")
    p_produce.add_argument("--chapter", type=int, default=None, help="Specific chapter number to produce")
    p_produce.add_argument("--all", action="store_true", help="Produce all chapters in sequence")
    p_produce.add_argument("--voice", default="Aoede", help="Lead voice persona")
    p_produce.add_argument("--workers", default=3, type=int, help="TTS synthesis workers")

    # audit
    p_audit = subparsers.add_parser("audit", help="Run multi-gate verification audit on a chapter")
    p_audit.add_argument("book", help="Project book slug")
    p_audit.add_argument("--chapter", type=int, required=True, help="Chapter number to audit")

    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        sys.exit(1)

    cmds = {
        "extract": cmd_extract,
        "translate": cmd_translate,
        "script": cmd_script,
        "synthesize": cmd_synthesize,
        "master": cmd_master,
        "package": cmd_package,
        "produce": cmd_produce,
        "auto": cmd_auto,
        "audit": cmd_audit,
        "audit-book": cmd_audit_book,
    }
    try:
        cmds[args.subcommand](args)
    except KeyboardInterrupt:
        print("\n\n[!] Production aborted by user (Ctrl+C). Checkpoints safely preserved on disk.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n[!] Pipeline Error: {e}", file=sys.stderr)
        if os.environ.get("DEBUG"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
