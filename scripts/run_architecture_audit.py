#!/usr/bin/env python3
"""
CLI Tool: Run Architecture-Wide Read-Only Audit & Coordination Inspection.
Usage:
    python scripts/run_architecture_audit.py --project-dir audiobooks/projects/harry_potter_or_paras_patthar --read-only
"""

import sys
import argparse
import json
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from audiobook_factory.architecture_auditor import ArchitectureAuditor
from audiobook_factory.logger import logger


def main():
    parser = argparse.ArgumentParser(
        description="Run Read-Only Architecture Audit across all 10 subsystems"
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
        default="ARCHITECTURE_AUDIT_REPORT.json",
        help="Filename or path to save the full audit report JSON",
    )

    args = parser.parse_args()
    project_path = Path(args.project_dir).resolve()

    if not project_path.exists():
        print(f"[!] Error: Project directory does not exist: {project_path}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("   STUDIO AUDIOBOOK ENGINE - READ-ONLY ARCHITECTURE AUDIT   ")
    print(f"   Target Project: {project_path.name}")
    print(f"   Chapter Filter: {args.chapter if args.chapter else 'All Chapters'}")
    print("   Mode          : STRICTLY READ-ONLY (Zero File Modifications)")
    print("=" * 70 + "\n")

    auditor = ArchitectureAuditor(project_dir=project_path)
    report = auditor.audit_all(chapter_num=args.chapter)

    # Render Terminal Summary Table
    print(f"{'SUBSYSTEM':<32} | {'STATUS':<6} | {'DIAGNOSTIC SUMMARY'}")
    print("-" * 75)

    system_labels = {
        "system1_ingestion": "1. Ingestion & Extraction",
        "system2_translation": "2. Translation & Lore",
        "system3_screenplay": "3. Screenplay & Dramaturgy",
        "system4_tts_casting": "4. Voice Casting & TTS",
        "system5_sonic_intelligence": "5. Sonic Intelligence (FTS5)",
        "system6_editorial": "6. Dialogue Editorial",
        "system7_mixing": "7. 5-Track Mixing (DME)",
        "system8_mastering": "8. Broadcast Mastering",
        "system9_packaging": "9. Packaging & M4B",
        "system10_orchestration": "10. State & Telemetry",
    }

    for key, label in system_labels.items():
        sub = report["subsystems"].get(key, {})
        status = sub.get("status", "UNKNOWN")
        msg = sub.get("message", "")
        # Color coding for terminal if available
        color_badge = f"[{status}]"
        print(f"{label:<32} | {color_badge:<6} | {msg}")

    print("-" * 75)
    summary = report["summary"]
    print(f"OVERALL ARCHITECTURE SCORE : {summary['overall_score']}% ({summary['passed']}/{summary['total_subsystems']} PASS, {summary['warned']} WARN, {summary['failed']} FAIL)")
    print(f"SONIC INTELLIGENCE HIT RATE: {summary['sonic_intelligence_hit_rate']}%\n")

    # Save report
    out_file = project_path / args.output_json
    try:
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"[+] Full Diagnostic Report saved to: {out_file}\n")
    except Exception as e:
        print(f"[!] Warning: Could not write report to {out_file}: {e}")

    # Return exit code based on failure count
    sys.exit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
