#!/usr/bin/env python3
"""
Audiobook Studio Engine Bridge.
Standard: v6.0-ENTERPRISE-DAG
Provides programmatic JSON APIs for the Antigravity Plugin and UI Extension Sidecar.
Exposes project discovery, SQLite DAG state introspection, TakeBank cache metrics,
voice catalog queries, surgical beat patching, and diagnostic health checks.
"""

from __future__ import annotations
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from audiobook_factory.cli.doctor import run_doctor_diagnostics
from audiobook_factory.contracts.ingestion import RawBookManifest
from audiobook_factory.contracts.lore import BookBible, CastLock
from audiobook_factory.core.cache.ledger import PipelineLedger
from audiobook_factory.dag.diff_reconciler import DiffReconciler
from audiobook_factory.rooms.room2_translate.collective import TranslationCollective

WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECTS_DIR = WORKSPACE_DIR / "projects"
LEGACY_PROJECTS_DIR = WORKSPACE_DIR / "audiobooks" / "projects"
KEY_POOL_DB = WORKSPACE_DIR / "keys_pool.db"
VOICE_CATALOG_JSON = WORKSPACE_DIR / "audiobook_factory" / "tts" / "data" / "curated_voice_catalog.json"


def get_engine_status() -> Dict[str, Any]:
    """Returns engine health, active keys count, doctor report, and basic metadata."""
    doctor_report = run_doctor_diagnostics(WORKSPACE_DIR)
    
    projects_list = list_projects()

    return {
        "status": "ready",
        "engine_version": "6.0.0",
        "architecture_standard": "v6.0-ENTERPRISE-DAG",
        "python_version": sys.version.split()[0],
        "workspace_dir": str(WORKSPACE_DIR),
        "active_gemini_keys": doctor_report["keypool"]["total_active_keys"],
        "active_projects_count": len(projects_list),
        "doctor": doctor_report,
    }


def _find_all_project_dirs() -> List[Path]:
    """Discovers all valid project directories across v6 and legacy project roots."""
    dirs = []
    if PROJECTS_DIR.exists():
        dirs.extend([p for p in PROJECTS_DIR.iterdir() if p.is_dir()])
    if LEGACY_PROJECTS_DIR.exists():
        dirs.extend([p for p in LEGACY_PROJECTS_DIR.iterdir() if p.is_dir() and p not in dirs])
    return dirs


def list_projects() -> List[Dict[str, Any]]:
    """Scans project directories and returns structured summaries."""
    results = []
    pdirs = _find_all_project_dirs()

    for pdir in sorted(pdirs, key=lambda p: p.name):
        slug = pdir.name
        manifest_file = pdir / "raw_book_manifest.json"
        ledger_file = pdir / "pipeline_ledger.db"

        title = slug.replace("_", " ").title()
        author = "Unknown Author"
        total_chapters = 0
        progress_pct = 0.0
        has_master = False

        if manifest_file.exists():
            try:
                m = RawBookManifest.model_validate_json(manifest_file.read_text(encoding="utf-8"))
                title = m.title
                author = m.author
                total_chapters = m.total_chapters
            except Exception:
                pass

        if ledger_file.exists():
            try:
                ledger = PipelineLedger(db_path=ledger_file)
                dirty = ledger.get_dirty_stages(slug)
                # Count mastered stages
                with ledger._get_connection() as conn:
                    row = conn.execute(
                        "SELECT COUNT(*) FROM chapter_stage_ledger WHERE project_id = ? AND room_name = 'ROOM5_MASTER' AND status = 'COMPLETED';",
                        (slug,)
                    ).fetchone()
                    mastered_count = row[0] if row else 0
                    if total_chapters > 0:
                        progress_pct = round((mastered_count / total_chapters) * 100.0, 1)
            except Exception:
                pass

        mastered_files = list(pdir.glob("*.m4b")) + list(pdir.glob("*_mastered.m4a"))
        if mastered_files:
            has_master = True

        results.append({
            "slug": slug,
            "title": title,
            "author": author,
            "chapters_count": total_chapters,
            "progress_percent": progress_pct,
            "has_master": has_master,
            "path": str(pdir),
        })

    return results


def get_project_detail(slug: str) -> Dict[str, Any]:
    """Returns comprehensive v6.0-ENTERPRISE-DAG project state, 5-room DAG timeline, lore, and TakeBank metrics."""
    # Locate project directory
    target_dir = PROJECTS_DIR / slug
    if not target_dir.exists():
        target_dir = LEGACY_PROJECTS_DIR / slug
    if not target_dir.exists() or not target_dir.is_dir():
        raise FileNotFoundError(f"Project not found: {slug}")

    manifest_file = target_dir / "raw_book_manifest.json"
    bible_file = target_dir / "book_bible.json"
    cast_file = target_dir / "cast_lock.json"
    ledger_file = target_dir / "pipeline_ledger.db"

    title = slug.replace("_", " ").title()
    author = "Unknown Author"
    chapters = []
    characters = []

    if manifest_file.exists():
        try:
            m = RawBookManifest.model_validate_json(manifest_file.read_text(encoding="utf-8"))
            title = m.title
            author = m.author
            for ch in m.chapters:
                chapters.append({
                    "chapter_id": ch.chapter_id,
                    "title": ch.title,
                    "sentence_count": len(ch.sentences),
                    "source_hash": ch.source_hash,
                })
        except Exception:
            pass

    if cast_file.exists():
        try:
            cast = CastLock.model_validate_json(cast_file.read_text(encoding="utf-8"))
            for name, dossier in cast.cast_assignments.items():
                characters.append({
                    "name": dossier.character_name,
                    "hindi_name": dossier.canonical_hindi_name,
                    "gender": dossier.gender,
                    "voice_id": dossier.suggested_voice_id,
                    "pitch_offset": dossier.pitch_offset,
                    "tempo_multiplier": dossier.tempo_multiplier,
                })
        except Exception:
            pass

    # Query DAG Stages & Gate Audits
    dag_stages = []
    gate_audits = []
    takebank_metrics = {"total_takes": 0, "cache_hits": 0, "cache_size_bytes": 0}

    if ledger_file.exists():
        try:
            ledger = PipelineLedger(db_path=ledger_file)
            with ledger._get_connection() as conn:
                s_rows = conn.execute("SELECT * FROM chapter_stage_ledger WHERE project_id = ? ORDER BY chapter_id, chapter_stage_uid;", (slug,)).fetchall()
                for r in s_rows:
                    dag_stages.append({
                        "stage_uid": r["chapter_stage_uid"],
                        "chapter_id": r["chapter_id"],
                        "room_name": r["room_name"],
                        "status": r["status"],
                        "error_message": r["error_message"],
                    })

                g_rows = conn.execute("SELECT * FROM gate_audit_records ORDER BY evaluated_at DESC LIMIT 20;").fetchall()
                for r in g_rows:
                    gate_audits.append({
                        "audit_uid": r["audit_uid"],
                        "gate_name": r["gate_name"],
                        "decision": r["decision"],
                        "metrics": json.loads(r["metrics_json"]) if r["metrics_json"] else {},
                    })

                t_row = conn.execute("SELECT COUNT(*) FROM segment_take_cache WHERE project_id = ?;", (slug,)).fetchone()
                takebank_metrics["total_takes"] = t_row[0] if t_row else 0
        except Exception:
            pass

    # Media / Audio deliverables
    media_files = []
    for ext in ("*.m4b", "*.m4a", "*.wav"):
        for f in target_dir.glob(ext):
            media_files.append({
                "name": f.name,
                "rel_path": str(f.relative_to(WORKSPACE_DIR)).replace("\\", "/") if f.is_relative_to(WORKSPACE_DIR) else f.name,
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                "modified": f.stat().st_mtime,
            })

    # Diff reconciliation report
    diff_reconciler = DiffReconciler(project_dir=target_dir)
    diff_report = diff_reconciler.reconcile_project(project_id=slug)

    return {
        "slug": slug,
        "title": title,
        "author": author,
        "chapters": chapters,
        "characters": characters,
        "dag_stages": dag_stages,
        "gate_audits": gate_audits,
        "takebank_metrics": takebank_metrics,
        "dirty_chapter_ids": list(diff_report.dirty_chapter_ids),
        "is_dag_clean": diff_report.is_clean,
        "media_files": media_files,
    }


def list_curated_voices() -> List[Dict[str, Any]]:
    """Returns curated Gemini voices catalog for voice auditions and casting."""
    return [
        {"voice_id": "Aoede", "language": "hi-IN", "gender": "female", "style": "Calm, Steady, Articulate Lead Narrator"},
        {"voice_id": "Charon", "language": "hi-IN", "gender": "male", "style": "Deep, Resonant, Earthy Protagonist"},
        {"voice_id": "Puck", "language": "hi-IN", "gender": "male", "style": "Agile, Quick, Witty Rogue"},
        {"voice_id": "Fenrir", "language": "hi-IN", "gender": "male", "style": "Gruff, Gravelly, Veteran Warrior"},
        {"voice_id": "Kore", "language": "hi-IN", "gender": "female", "style": "Ethereal, Regal, Sorceress / Queen"},
        {"voice_id": "Leda", "language": "hi-IN", "gender": "female", "style": "Warm, Compassionate, Companion"},
        {"voice_id": "Orus", "language": "hi-IN", "gender": "male", "style": "Authoritative, Commanding Monarch"},
        {"voice_id": "Zephyr", "language": "hi-IN", "gender": "male", "style": "Gentle, Scholarly, Melodious Narrator"},
    ]


def patch_translation_beat(slug: str, chapter_id: int, beat_uid: str, patch_json: str) -> Dict[str, Any]:
    """Surgically patches a beat and returns updated manifest summary."""
    target_dir = PROJECTS_DIR / slug
    if not target_dir.exists():
        target_dir = LEGACY_PROJECTS_DIR / slug
    if not target_dir.exists():
        raise FileNotFoundError(f"Project not found: {slug}")

    ledger = PipelineLedger(db_path=target_dir / "pipeline_ledger.db")
    collective = TranslationCollective(project_dir=target_dir, ledger=ledger)
    patch_data = json.loads(patch_json)

    manifest = collective.patch_beat(
        chapter_id=chapter_id,
        beat_uid=beat_uid,
        patched_sentences=patch_data,
        project_id=slug,
    )

    return {
        "status": "success",
        "chapter_id": chapter_id,
        "beat_uid": beat_uid,
        "manifest_hash": manifest.compute_sha256_hash(),
    }


def main():
    parser = argparse.ArgumentParser(description="Audiobook Studio Bridge JSON API (v6.0-ENTERPRISE-DAG)")
    parser.add_argument("command", choices=["status", "list-projects", "project-detail", "list-voices", "patch-beat", "doctor"])
    parser.add_argument("--slug", help="Project slug")
    parser.add_argument("--chapter", type=int, default=1, help="Chapter ID")
    parser.add_argument("--beat-uid", help="Beat UID for patch-beat")
    parser.add_argument("--patch-json", help="JSON string for patch-beat")

    args = parser.parse_args()

    try:
        if args.command == "status":
            out = get_engine_status()
        elif args.command == "list-projects":
            out = list_projects()
        elif args.command == "project-detail":
            if not args.slug:
                parser.error("--slug is required for project-detail")
            out = get_project_detail(args.slug)
        elif args.command == "list-voices":
            out = list_curated_voices()
        elif args.command == "patch-beat":
            if not args.slug or not args.beat_uid or not args.patch_json:
                parser.error("--slug, --beat-uid, and --patch-json are required for patch-beat")
            out = patch_translation_beat(args.slug, args.chapter, args.beat_uid, args.patch_json)
        elif args.command == "doctor":
            out = run_doctor_diagnostics(WORKSPACE_DIR)
        else:
            out = {"error": f"Unknown command {args.command}"}

        print(json.dumps(out, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
