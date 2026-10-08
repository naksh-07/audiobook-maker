#!/usr/bin/env python3
"""
Audiobook Studio - Main Central Developer CLI Entry Point.
Standard: v6.0-ENTERPRISE-DAG
Provides subcommands: ingest, translate, screenplay, synth, master, package, doctor.
"""

from __future__ import annotations
import argparse
import sys
from typing import List, Optional

from audiobook_factory.cli.doctor import format_doctor_report, run_doctor_diagnostics
from audiobook_factory.cli.ingest import configure_ingest_parser, handle_ingest_command
from audiobook_factory.cli.translate import configure_translate_parser, handle_translate_command
from audiobook_factory.cli.screenplay import configure_screenplay_parser, handle_screenplay_command
from audiobook_factory.cli.synth import configure_synth_parser, handle_synth_command
from audiobook_factory.cli.master import configure_master_parser, handle_master_command
from audiobook_factory.cli.package import configure_package_parser, handle_package_command


def build_cli_parser() -> argparse.ArgumentParser:
    """Builds and returns the comprehensive Audiobook Studio CLI ArgumentParser."""
    parser = argparse.ArgumentParser(
        prog="audiobook-studio",
        description="Studio-Grade Pure Vocals-Only Audiobook Production Engine (v6.0-ENTERPRISE-DAG)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="Audiobook Studio v6.0.0 (Standard: v6.0-ENTERPRISE-DAG)",
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Studio Room or Diagnostic Tool to execute")

    # Room 1: Ingest
    configure_ingest_parser(subparsers)

    # Room 2: Translate
    configure_translate_parser(subparsers)

    # Room 3: Screenplay
    configure_screenplay_parser(subparsers)

    # Room 4: Synth
    configure_synth_parser(subparsers)

    # Room 5: Master
    configure_master_parser(subparsers)

    # Room 5 Packager: Package
    configure_package_parser(subparsers)

    # System Doctor
    p_doctor = subparsers.add_parser("doctor", help="Run comprehensive diagnostic health check")
    p_doctor.add_argument("--json", action="store_true", help="Output diagnostic report in JSON format")

    return parser


def main(args: Optional[List[str]] = None) -> int:
    """Main CLI entry point returning exit code (0 for success, non-zero for error)."""
    parser = build_cli_parser()
    try:
        parsed_args = parser.parse_args(args=args)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0

    if not parsed_args.subcommand:
        parser.print_help()
        return 0

    if parsed_args.subcommand == "ingest":
        return handle_ingest_command(parsed_args)
    elif parsed_args.subcommand == "translate":
        return handle_translate_command(parsed_args)
    elif parsed_args.subcommand == "screenplay":
        return handle_screenplay_command(parsed_args)
    elif parsed_args.subcommand == "synth":
        return handle_synth_command(parsed_args)
    elif parsed_args.subcommand == "master":
        return handle_master_command(parsed_args)
    elif parsed_args.subcommand == "package":
        return handle_package_command(parsed_args)
    elif parsed_args.subcommand == "doctor":
        report = run_doctor_diagnostics()
        if getattr(parsed_args, "json", False):
            import json
            print(json.dumps(report, indent=2))
        else:
            print(format_doctor_report(report))
        return 0
    else:
        print(f"❌ [Error]: Unknown subcommand: {parsed_args.subcommand}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
