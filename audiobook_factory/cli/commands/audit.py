from __future__ import annotations
import os
import sys
import re
import json
from pathlib import Path

from audiobook_factory.cli.context import get_projects_dir, get_workspace_dir
from audiobook_factory.gate_auditor import audit_book_master, audit_chapter_gates, GateAuditError

def cmd_audit_book(args):
    """Executes Macro-Tier Gate 6 (6A, 6B, 6C, 6D) audit for an entire book project."""
    from audiobook_factory.gate_auditor import audit_book_master

    target = Path(args.project_dir)
    project_dir = target if (target.exists() and target.is_dir()) else (get_projects_dir() / args.project_dir)

    print(f"[*] Running Macro-Tier Gate 6 Master Audit on '{project_dir.name}'...")
    report = audit_book_master(project_dir)
    print("\n" + "=" * 65)
    print(f"📘 MACRO BOOK GATE 6 VERDICT: {report['overall_status']}")
    print("=" * 65)
    print(f"  Gate 6A (Voice Continuity):   {report['gate_6a']['status']}")
    if report['gate_6a'].get('errors'):
        for err in report['gate_6a']['errors']:
            print(f"     [!] {err}")
    print(f"  Gate 6B (Loudness Continuity): {report['gate_6b']['status']} (avg {report['gate_6b']['details'].get('average_lufs', -19.0)} LUFS)")
    if report['gate_6b'].get('errors'):
        for err in report['gate_6b']['errors']:
            print(f"     [!] {err}")
    print(f"  Gate 6C (TOC Integrity):       {report['gate_6c']['status']} ({report['gate_6c']['details'].get('total_chapters', 0)} chapters)")
    if report['gate_6c'].get('errors'):
        for err in report['gate_6c']['errors']:
            print(f"     [!] {err}")
    print(f"  Gate 6D (Packaging Specs):     {report['gate_6d']['status']}")
    if report['gate_6d'].get('errors'):
        for err in report['gate_6d']['errors']:
            print(f"     [!] {err}")
    print("=" * 65)
    if not report['overall_passed']:
        sys.exit(1)



def cmd_audit(args):
    """Executes multi-gate independent verification audit for a chapter."""
    from audiobook_factory.gate_auditor import audit_chapter_gates, GateAuditError

    project_dir = get_projects_dir() / args.book
    ch_num = args.chapter

    print(f"[*] Running Multi-Gate Independent Verification Audit on '{args.book}' Chapter {ch_num}...")
    try:
        report = audit_chapter_gates(project_dir, ch_num)
        print("\n" + "=" * 60)
        print(f"🎉 MULTI-GATE AUDIT VERDICT: {report['overall_status']}")
        print("=" * 60)
        print(f"  Gate 0 (Translation): {report['gate_0']['status']} ({report['gate_0']['translation_chars']:,} chars)")
        print(f"  Gate 1 (Voice Roster): {report['gate_1']['status']} ({report['gate_1']['active_roles']} roles, 0 collisions)")
        print(f"  Gate 2 (Screenplay):   {report['gate_2']['status']} ({report['gate_2']['total_segments']} segments)")
        acts_label = report['gate_3'].get('total_acts') or report['gate_3'].get('notice') or 'verified'
        print(f"  Gate 3 (Scenes Source): {report['gate_3']['status']} ({acts_label})")
        if "gate_4_ledger" in report:
            print(f"  Gate 4.5 (Timeline):   {report['gate_4_ledger']['status']} ({report['gate_4_ledger']['total_segments']} segments, {report['gate_4_ledger']['total_timeline_sec']}s, pause silence: {report['gate_4_ledger']['silence_percentage']}%)")
        print("=" * 60)
    except GateAuditError as e:
        print(f"\n[FAIL] Gate Audit Error: {e}", file=sys.stderr)
        sys.exit(1)


