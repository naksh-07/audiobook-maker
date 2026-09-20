#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.6: High-Performance Local Sound Bank Engine.
Manages a curated 2-4 GB audio library using SQLite FTS5 (Full-Text Search).
Enables sub-millisecond query resolution for ambiences, foley, SFX, and musical beds
with ZERO context bloat for AI agents.
"""

import os
import re
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

DEFAULT_BANK_DIR = Path(__file__).resolve().parent.parent / "audiobooks" / "sound_bank"
DEFAULT_DB_PATH = DEFAULT_BANK_DIR / "sound_bank.db"


class SoundBank:
    """High-performance SQLite FTS5 Sound Bank catalog for audio drama production."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        bank_root: Optional[Path] = None,
    ):
        self.bank_root = Path(bank_root or DEFAULT_BANK_DIR).resolve()
        self.bank_root.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path or (self.bank_root / "sound_bank.db")).resolve()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_db(self):
        """Initialize relational metadata table and SQLite FTS5 index."""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sound_catalog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    filepath TEXT UNIQUE NOT NULL,
                    category TEXT,       -- AMB (Ambience), FOL (Foley), SFX (Sound FX), MUS (Music/Score)
                    subcategory TEXT,    -- Weather, Tavern, Steps, Magic, Combat, Drone, Nature
                    mood TEXT,           -- mysterious, tense, peaceful, epic, emotional, default
                    tags TEXT,           -- Space-separated searchable tokens
                    duration_sec REAL DEFAULT 0.0,
                    size_bytes INTEGER DEFAULT 0,
                    format TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS sound_catalog_fts USING fts5(
                    filename,
                    category,
                    subcategory,
                    mood,
                    tags,
                    content='sound_catalog',
                    content_rowid='id'
                );
            """)
            # Triggers to keep FTS5 synchronized with main catalog table
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS sound_catalog_ai AFTER INSERT ON sound_catalog BEGIN
                    INSERT INTO sound_catalog_fts(rowid, filename, category, subcategory, mood, tags)
                    VALUES (new.id, new.filename, new.category, new.subcategory, new.mood, new.tags);
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS sound_catalog_ad AFTER DELETE ON sound_catalog BEGIN
                    INSERT INTO sound_catalog_fts(sound_catalog_fts, rowid, filename, category, subcategory, mood, tags)
                    VALUES ('delete', old.id, old.filename, old.category, old.subcategory, old.mood, old.tags);
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS sound_catalog_au AFTER UPDATE ON sound_catalog BEGIN
                    INSERT INTO sound_catalog_fts(sound_catalog_fts, rowid, filename, category, subcategory, mood, tags)
                    VALUES ('delete', old.id, old.filename, old.category, old.subcategory, old.mood, old.tags);
                    INSERT INTO sound_catalog_fts(rowid, filename, category, subcategory, mood, tags)
                    VALUES (new.id, new.filename, new.category, new.subcategory, new.mood, new.tags);
                END;
            """)
            conn.commit()

    @staticmethod
    def _extract_duration(file_path: Path) -> float:
        """Extract audio duration in seconds via ffprobe or ffmpeg."""
        ffprobe = shutil.which("ffprobe")
        if ffprobe:
            try:
                cmd = [
                    ffprobe, "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(file_path)
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
                if res.returncode == 0 and res.stdout.strip():
                    return float(res.stdout.strip())
            except Exception:
                pass

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            try:
                cmd = [ffmpeg, "-i", str(file_path)]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
                m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", res.stderr)
                if m:
                    h, m_val, s = m.groups()
                    return int(h) * 3600 + int(m_val) * 60 + float(s)
            except Exception:
                pass
        return 0.0

    @staticmethod
    def _derive_metadata(file_path: Path) -> Dict[str, str]:
        """Derive category, subcategory, mood, and tags from file and folder hierarchy."""
        name_lower = file_path.stem.lower()
        parts = [p.lower() for p in file_path.parts]

        # 1. Category
        category = "SFX"
        if any(k in parts for k in ("ambience", "amb", "atmospheres", "environments")):
            category = "AMB"
        elif any(k in parts for k in ("foley", "fol", "footsteps", "movement")):
            category = "FOL"
        elif any(k in parts for k in ("stems", "music", "mus", "scores", "loops")):
            category = "MUS"

        # 2. Subcategory
        subcategory = "General"
        if any(k in name_lower or k in parts for k in ("weather", "rain", "thunder", "storm", "wind", "snow")):
            subcategory = "Weather"
        elif any(k in name_lower or k in parts for k in ("tavern", "crowd", "market", "chatter")):
            subcategory = "Tavern"
        elif any(k in name_lower or k in parts for k in ("footstep", "walk", "run", "gravel", "stone", "wood")):
            subcategory = "Footsteps"
        elif any(k in name_lower or k in parts for k in ("magic", "spell", "glow", "enchant")):
            subcategory = "Magic"
        elif any(k in name_lower or k in parts for k in ("combat", "sword", "shield", "hit", "punch", "arrow")):
            subcategory = "Combat"
        elif any(k in name_lower or k in parts for k in ("drone", "dark", "horror", "eerie", "creepy")):
            subcategory = "Drone"
        elif any(k in name_lower or k in parts for k in ("forest", "birds", "nature", "night", "crickets", "fire")):
            subcategory = "Nature"

        # 3. Mood
        mood = "default"
        if any(k in name_lower for k in ("peaceful", "calm", "relax", "meditation")):
            mood = "peaceful"
        elif any(k in name_lower for k in ("mysterious", "suspense", "secret", "archive")):
            mood = "mysterious"
        elif any(k in name_lower for k in ("tense", "danger", "dark", "chase", "heartbeat")):
            mood = "tense"
        elif any(k in name_lower for k in ("emotional", "sad", "melancholy", "poignant")):
            mood = "emotional"
        elif any(k in name_lower for k in ("epic", "triumph", "glory", "battle", "brass")):
            mood = "epic"

        # 4. Tags: tokens extracted from filename and subfolder
        tokens = re.findall(r"[a-z0-9]+", name_lower + " " + " ".join(parts[-3:]))
        # Remove noisy common tokens
        clean_tokens = set(t for t in tokens if len(t) > 2 and t not in ("mp3", "wav", "flac", "ogg", "audiobooks", "soundscapes"))
        tags = " ".join(sorted(clean_tokens))

        return {
            "category": category,
            "subcategory": subcategory,
            "mood": mood,
            "tags": tags,
        }

    def scan_and_index(self, extra_dirs: Optional[List[Path]] = None) -> Dict[str, int]:
        """
        Recursively scans local directories and upserts all audio files into SQLite FTS5 catalog.
        """
        target_dirs = [self.bank_root]
        if extra_dirs:
            target_dirs.extend(extra_dirs)

        stats = {"indexed": 0, "updated": 0, "skipped": 0, "total_files": 0}
        valid_exts = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aif", ".aiff"}

        with self._get_conn() as conn:
            for t_dir in target_dirs:
                if not t_dir.exists():
                    continue
                for root, _, files in os.walk(t_dir):
                    for f in files:
                        p = Path(root) / f
                        if p.suffix.lower() not in valid_exts or p.name.startswith("."):
                            continue

                        stats["total_files"] += 1
                        filepath_str = str(p.resolve()).replace("\\", "/")
                        size_bytes = p.stat().st_size

                        # Check if already indexed with same size
                        cur = conn.execute("SELECT id, size_bytes FROM sound_catalog WHERE filepath = ?", (filepath_str,))
                        row = cur.fetchone()
                        if row and row["size_bytes"] == size_bytes:
                            stats["skipped"] += 1
                            continue

                        meta = self._derive_metadata(p)
                        dur = self._extract_duration(p)

                        if row:
                            conn.execute("""
                                UPDATE sound_catalog
                                SET filename = ?, category = ?, subcategory = ?, mood = ?, tags = ?,
                                    duration_sec = ?, size_bytes = ?, format = ?
                                WHERE id = ?
                            """, (
                                p.name, meta["category"], meta["subcategory"], meta["mood"], meta["tags"],
                                dur, size_bytes, p.suffix.lower(), row["id"]
                            ))
                            stats["updated"] += 1
                        else:
                            conn.execute("""
                                INSERT INTO sound_catalog
                                (filename, filepath, category, subcategory, mood, tags, duration_sec, size_bytes, format)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                p.name, filepath_str, meta["category"], meta["subcategory"], meta["mood"],
                                meta["tags"], dur, size_bytes, p.suffix.lower()
                            ))
                            stats["indexed"] += 1

            conn.commit()

        return stats

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        mood: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Executes sub-millisecond FTS5 search against local sound bank.
        Query words are combined with prefix matching for high recall.
        """
        raw_words = re.findall(r"[a-zA-Z0-9]+", query.strip())
        if not raw_words:
            return []

        # Construct FTS5 query: word1* OR word2* OR "word1 word2"
        fts_query = " OR ".join(f"{w}*" for w in raw_words)

        sql = """
            SELECT c.id, c.filename, c.filepath, c.category, c.subcategory, c.mood, c.tags,
                   c.duration_sec, c.size_bytes, rank
            FROM sound_catalog_fts f
            JOIN sound_catalog c ON f.rowid = c.id
            WHERE sound_catalog_fts MATCH ?
        """
        params = [fts_query]

        if category:
            sql += " AND c.category = ?"
            params.append(category.upper())

        if mood:
            sql += " AND c.mood = ?"
            params.append(mood.lower())

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        with self._get_conn() as conn:
            cur = conn.execute(sql, params)
            results = [dict(row) for row in cur.fetchall()]

        return results

    def resolve_sound(
        self,
        query: str,
        category: Optional[str] = None,
        prefer_mood: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Resolves the single best matching audio file for a given cue or scene mood.
        Returns absolute Path if found and file exists, else None.
        """
        # Try exact category & mood first
        results = self.search(query, category=category, mood=prefer_mood, limit=3)
        if not results and (category or prefer_mood):
            # Relax filters if no direct match
            results = self.search(query, limit=3)

        if results:
            cand = Path(results[0]["filepath"])
            if cand.exists():
                return cand
        return None

    def stats(self) -> Dict[str, Any]:
        """Returns storage and catalog statistics for the local sound bank."""
        with self._get_conn() as conn:
            total_sounds = conn.execute("SELECT COUNT(*) FROM sound_catalog").fetchone()[0]
            total_dur = conn.execute("SELECT COALESCE(SUM(duration_sec), 0.0) FROM sound_catalog").fetchone()[0]
            total_bytes = conn.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM sound_catalog").fetchone()[0]

            cat_counts = {}
            for r in conn.execute("SELECT category, COUNT(*) as cnt FROM sound_catalog GROUP BY category"):
                cat_counts[r["category"] or "OTHER"] = r["cnt"]

            mood_counts = {}
            for r in conn.execute("SELECT mood, COUNT(*) as cnt FROM sound_catalog GROUP BY mood"):
                mood_counts[r["mood"] or "default"] = r["cnt"]

        return {
            "total_sounds": total_sounds,
            "total_duration_min": round(total_dur / 60.0, 1),
            "total_size_mb": round(total_bytes / (1024 * 1024), 2),
            "categories": cat_counts,
            "moods": mood_counts,
            "database_path": str(self.db_path),
        }
