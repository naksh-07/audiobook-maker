#!/usr/bin/env python3
"""
Audiobook Studio Engine Bridge.
Provides programmatic JSON APIs for the Antigravity Plugin and UI Extension.
Exposes project discovery, SQLite state introspection, voice catalog queries,
and pipeline dispatch without requiring shell CLI flags.
"""

from __future__ import annotations

import os
import sys
import json
import sqlite3
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECTS_DIR = WORKSPACE_DIR / "audiobooks" / "projects"
KEY_POOL_DB = WORKSPACE_DIR / "audiobooks" / "key_pool_state.db"
VOICE_CATALOG_JSON = WORKSPACE_DIR / "audiobook_factory" / "tts" / "data" / "curated_voice_catalog.json"


def get_engine_status() -> Dict[str, Any]:
    """Returns engine health, active keys count, and basic metadata."""
    active_keys = 0
    total_keys = 0
    if KEY_POOL_DB.exists():
        try:
            conn = sqlite3.connect(str(KEY_POOL_DB), timeout=5.0)
            cur = conn.cursor()
            cur.execute("SELECT status, COUNT(*) FROM key_quota_ledger GROUP BY status")
            rows = dict(cur.fetchall())
            active_keys = rows.get("ACTIVE", 0)
            total_keys = sum(rows.values())
            conn.close()
        except Exception:
            pass

    projects = []
    if PROJECTS_DIR.exists():
        projects = [p.name for p in PROJECTS_DIR.iterdir() if p.is_dir() and (p / "project_state.db").exists()]

    return {
        "status": "ready",
        "engine_version": "5.1.0",
        "python_version": sys.version.split()[0],
        "workspace_dir": str(WORKSPACE_DIR),
        "projects_dir": str(PROJECTS_DIR),
        "active_gemini_keys": active_keys,
        "total_gemini_keys": total_keys,
        "active_projects_count": len(projects),
    }


def list_projects() -> List[Dict[str, Any]]:
    """Scans projects directory and returns summary of each project."""
    if not PROJECTS_DIR.exists():
        return []

    results = []
    for pdir in sorted(PROJECTS_DIR.iterdir()):
        if not pdir.is_dir():
            continue

        state_db = pdir / "project_state.db"
        meta_file = pdir / "metadata.json"

        # Basic metadata
        title = pdir.name
        author = "Unknown"
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta_data = json.load(f)
                    title = meta_data.get("title", title)
                    author = meta_data.get("author", author)
            except Exception:
                pass

        total_segments = 0
        completed_segments = 0
        failed_segments = 0
        in_progress_segments = 0
        total_duration_min = 0.0
        chapters_count = 0
        has_master = False

        if state_db.exists():
            try:
                conn = sqlite3.connect(str(state_db), timeout=5.0)
                conn.row_factory = sqlite3.Row
                c_cur = conn.cursor()
                c_cur.execute("SELECT COUNT(*) FROM chapters")
                chapters_count = c_cur.fetchone()[0]

                s_cur = conn.cursor()
                s_cur.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
                        SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed,
                        SUM(CASE WHEN status = 'IN_PROGRESS' THEN 1 ELSE 0 END) as in_progress,
                        COALESCE(SUM(duration_sec), 0.0) / 60.0 as dur_min
                    FROM segments
                """)
                row = s_cur.fetchone()
                if row:
                    total_segments = row["total"] or 0
                    completed_segments = row["completed"] or 0
                    failed_segments = row["failed"] or 0
                    in_progress_segments = row["in_progress"] or 0
                    total_duration_min = round(float(row["dur_min"] or 0.0), 1)

                m_cur = conn.cursor()
                m_cur.execute("SELECT COUNT(*) FROM chapters WHERE mastered_status = 'COMPLETED' OR m4a_path IS NOT NULL")
                if m_cur.fetchone()[0] > 0:
                    has_master = True
                conn.close()
            except Exception:
                pass

        # Check for final m4b / m4a files on disk
        mastered_files = list(pdir.glob("*.m4b")) + list(pdir.glob("*_mastered.m4a"))
        if mastered_files:
            has_master = True

        progress_pct = round((completed_segments / total_segments * 100), 1) if total_segments > 0 else 0.0

        results.append({
            "slug": pdir.name,
            "title": title,
            "author": author,
            "chapters_count": chapters_count,
            "total_segments": total_segments,
            "completed_segments": completed_segments,
            "failed_segments": failed_segments,
            "in_progress_segments": in_progress_segments,
            "progress_percent": progress_pct,
            "total_duration_min": total_duration_min,
            "has_master": has_master,
            "path": str(pdir),
        })

    return results


def get_project_detail(slug: str) -> Dict[str, Any]:
    """Returns deep details for a single project: chapters, characters, recent files."""
    pdir = PROJECTS_DIR / slug
    if not pdir.exists() or not pdir.is_dir():
        raise FileNotFoundError(f"Project not found: {slug}")

    state_db = pdir / "project_state.db"
    meta_file = pdir / "metadata.json"
    cast_file = pdir / "character_roster.json"
    bible_file = pdir / "book_bible.json"

    meta_data = {}
    if meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta_data = json.load(f)
        except Exception:
            pass

    # Cast list
    characters = []
    if cast_file.exists():
        try:
            with open(cast_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                raw_cast = raw_data.get("characters", raw_data) if isinstance(raw_data, dict) else raw_data
                if isinstance(raw_cast, dict):
                    for name, details in raw_cast.items():
                        if isinstance(details, dict):
                            voice = (
                                details.get("assigned_voice_id")
                                or details.get("voice_id")
                                or details.get("voice", "Aoede")
                            )
                            characters.append({
                                "name": details.get("display_name") or name,
                                "voice": voice,
                                "gender": details.get("gender", "unknown"),
                                "dialect": details.get("dialect", "Standard"),
                                "pitch_shift": details.get("pitch_shift", 0),
                                "notes": details.get("notes", ""),
                            })
                        elif isinstance(details, str):
                            characters.append({"name": name, "voice": details})
                elif isinstance(raw_cast, list):
                    characters = raw_cast
        except Exception:
            pass
    elif bible_file.exists():
        try:
            with open(bible_file, "r", encoding="utf-8") as f:
                bible_data = json.load(f)
                cast_dict = bible_data.get("characters") or bible_data.get("dramatis_personae") or {}
                for name, details in cast_dict.items():
                    if isinstance(details, dict):
                        characters.append({
                            "name": name,
                            "voice": details.get("voice_persona", "Aoede"),
                            "archetype": details.get("archetype", ""),
                        })
        except Exception:
            pass

    # Chapters & Segment detail
    chapters = []
    segments_summary = {"total": 0, "completed": 0, "failed": 0, "in_progress": 0, "pending": 0}
    if state_db.exists():
        try:
            conn = sqlite3.connect(str(state_db), timeout=5.0)
            conn.row_factory = sqlite3.Row
            c_cur = conn.cursor()
            c_cur.execute("SELECT chapter_num, title, word_count, scripted_status, mastered_status, m4a_path FROM chapters ORDER BY chapter_num")
            for row in c_cur.fetchall():
                m4a_exists = bool(row["m4a_path"] and Path(row["m4a_path"]).exists())
                chapters.append({
                    "chapter_num": row["chapter_num"],
                    "title": row["title"],
                    "word_count": row["word_count"],
                    "scripted_status": row["scripted_status"],
                    "mastered_status": row["mastered_status"],
                    "m4a_path": row["m4a_path"],
                    "m4a_exists": m4a_exists,
                })

            s_cur = conn.cursor()
            s_cur.execute("SELECT status, COUNT(*) FROM segments GROUP BY status")
            for st, cnt in s_cur.fetchall():
                key = str(st).lower()
                if key in segments_summary:
                    segments_summary[key] = cnt
                segments_summary["total"] += cnt
            conn.close()
        except Exception:
            pass

    # Media / Audio exports
    media_files = []
    for ext in ("*.m4b", "*.m4a"):
        for f in pdir.glob(ext):
            media_files.append({
                "name": f.name,
                "rel_path": str(f.relative_to(PROJECTS_DIR)).replace("\\", "/"),
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                "modified": f.stat().st_mtime,
            })

    return {
        "slug": slug,
        "title": meta_data.get("title", slug),
        "author": meta_data.get("author", "Unknown"),
        "language": meta_data.get("target_language", "hi"),
        "chapters": chapters,
        "characters": characters,
        "segments_summary": segments_summary,
        "media_files": media_files,
    }


def list_curated_voices() -> List[Dict[str, Any]]:
    """Returns curated voices catalog for voice auditions and casting."""
    if VOICE_CATALOG_JSON.exists():
        try:
            with open(VOICE_CATALOG_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    voices_list = []
                    langs = data.get("languages", {})
                    for lang, details in langs.items():
                        vlist = details.get("voices", []) if isinstance(details, dict) else details
                        if isinstance(vlist, list):
                            for v in vlist:
                                if isinstance(v, dict):
                                    v.setdefault("language", lang)
                                    voices_list.append(v)
                    if voices_list:
                        return voices_list
        except Exception:
            pass
    # Fallback minimal roster
    return [
        {"voice_id": "Aoede", "language": "en", "gender": "female", "style": "Warm Third-Person Narrative"},
        {"voice_id": "Charon", "language": "en", "gender": "male", "style": "Deep Resonant First-Person Male"},
        {"voice_id": "hi-in-podcaster-12", "language": "hi-IN", "gender": "male", "style": "Rustic Fighter / Energetic Young Adult"},
        {"voice_id": "hi-in-advisor-9", "language": "hi-IN", "gender": "male", "style": "Grounded Veteran / Gravelly Commander"},
        {"voice_id": "hi-in-training-2", "language": "hi-IN", "gender": "female", "style": "Dignified Matriarch / Sorceress"},
        {"voice_id": "hi-in-tutor-3", "language": "hi-IN", "gender": "female", "style": "Gentle Companion / Melodious Healer"},
        {"voice_id": "hi-in-commercial-5", "language": "hi-IN", "gender": "female", "style": "Agile Youth / Bright Resonance"},
    ]


def main():
    parser = argparse.ArgumentParser(description="Audiobook Studio Bridge JSON API")
    parser.add_argument("command", choices=["status", "list-projects", "project-detail", "list-voices"])
    parser.add_argument("--slug", help="Project slug for project-detail")

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
        else:
            out = {"error": f"Unknown command {args.command}"}

        print(json.dumps(out, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
