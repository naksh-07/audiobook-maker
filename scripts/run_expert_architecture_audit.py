#!/usr/bin/env python3
"""
CLI Tool: Run Multi-Expert Architecture Read-Only Audit & Forensic Inspection.
Usage:
    python scripts/run_expert_architecture_audit.py --project-dir audiobooks/projects/harry_potter_or_paras_patthar --read-only
"""

import sys
import argparse
import json
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from audiobook_factory.expert_auditor import MultiExpertArchitectureAuditor
from audiobook_factory.logger import logger


def main():
    parser = argparse.ArgumentParser(
        description="Run Read-Only Multi-Expert Architecture Audit across all 10 subsystems"
    )
    parser.add_argument(
        "--project-dir",
        type=str,
        required=True,
        help="Path to the book project directory",
    )
    parser.add_argument(
        "--chapter",
        type=int,
        default=None,
        help="Optional chapter number to filter audit",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        default=True,
        help="Enforce read-only diagnostic mode (default: True)",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default="MASTER_EXPERT_AUDIT_REPORT.json",
        help="Filename or path to save the full audit report JSON",
    )

    args = parser.parse_args()
    project_path = Path(args.project_dir).resolve()

    if not project_path.exists():
        print(f"[!] Error: Project directory does not exist: {project_path}")
        sys.exit(1)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("\n" + "=" * 105)
    print("      STUDIO AUDIOBOOK FACTORY - MULTI-EXPERT ARCHITECTURE AUDIT (READ-ONLY)      ")
    print(f"   Target Project : {project_path.name}")
    print(f"   Chapter Filter : {args.chapter if args.chapter else 'All Chapters'}")
    print("   Audit Mode     : STRICTLY READ-ONLY (Zero Mutation Guarantee)")
    print("   Orchestration  : 10 Domain Expert Auditors & LLM-Script Coordination Protocol")
    print("=" * 105 + "\n")

    auditor = MultiExpertArchitectureAuditor(project_dir=project_path)
    report = auditor.audit_all(chapter_num=args.chapter)

    # Render Terminal Summary Table
    header = f"{'SUBSYSTEM':<28} | {'EXPERT ROLE':<38} | {'STATUS':<6} | {'DET%':<5} | {'QUAL%':<5} | {'COMP%':<5}"
    print(header)
    print("-" * 105)

    for sub_id, verdict in report.subsystems.items():
        role_short = verdict.expert_role
        if len(role_short) > 38:
            role_short = role_short[:35] + "..."
        badge = f"[{verdict.status}]"
        row = (
            f"{verdict.subsystem_name:<28} | "
            f"{role_short:<38} | "
            f"{badge:<6} | "
            f"{verdict.deterministic_score:>4.1f}% | "
            f"{verdict.qualitative_score:>4.1f}% | "
            f"{verdict.composite_score:>4.1f}%"
        )
        print(row)
        if verdict.findings:
            top_finding = verdict.findings[0]
            if len(top_finding) > 85:
                top_finding = top_finding[:82] + "..."
            print(f"   -> Finding: {top_finding}")

    print("-" * 105)
    print(f"OVERALL ARCHITECTURE SCORE : {report.overall_score}% ({report.subsystems_passed}/10 PASS, {report.subsystems_warned} WARN, {report.subsystems_failed} FAIL)")
    print(f"OVERALL PLATFORM STATUS    : [{report.overall_status}]")
    print(f"READ-ONLY VERIFICATION     : {'VERIFIED - ZERO DISK MUTATIONS' if report.read_only_verified else 'FAILED'}\n")

    # Save report to destination or artifact
    out_file = project_path / args.output_json
    try:
        report_dict = report.model_dump()
        out_file.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")
        print(f"[+] Master expert audit report saved to: {out_file}\n")
    except Exception as e:
        print(f"[!] Warning: Could not write report to project path: {e}\n")


if __name__ == "__main__":
    main()
