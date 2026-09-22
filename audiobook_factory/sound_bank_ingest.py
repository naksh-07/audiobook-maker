#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 5: Universal Sound Bank Ingestion & Acoustic Characterization Engine.
Recursively scans, characterises, and indexes raw audio assets (WAV, FLAC, OGG, MP3)
into SQLite FTS5 using ffprobe and EBU R128 / spectral DSP analysis.
Extracts category, action_type, exciter, resonator, and acoustic loudness metrics.
"""

from __future__ import annotations
import os
import re
import json
import sqlite3
import contextlib
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List, Optional, Generator, Tuple, Union, Callable

from audiobook_factory.logger import logger

DEFAULT_BANK_DIR = Path(__file__).resolve().parent.parent / "audiobooks" / "sound_bank"
DEFAULT_DB_PATH = DEFAULT_BANK_DIR / "sound_bank.db"

# Supported audio formats for universal ingestion
SUPPORTED_EXTENSIONS = {".wav", ".flac", ".ogg", ".mp3"}

# Rule-based Foley & Sound Design Taxonomy Maps
ACTION_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "footstep": ["step", "footstep", "walk", "stride", "soil_step", "mud_step", "boot"],
    "impact": ["hit", "punch", "smash", "slam", "strike", "blunt", "body_fall", "drop", "collapse"],
    "clash": ["clash", "sword_clash", "parry", "deflect", "blade_hit", "metal_hit"],
    "draw": ["unsheathe", "draw", "drawknife", "blade_draw", "seax_unsheathe"],
    "sheathe": ["sheathe", "sheath", "holster"],
    "scrape": ["scrape", "knife_scrape", "grind", "drag"],
    "swing": ["whoosh", "swoosh", "swing", "blade_swing", "moulinet", "whistle"],
    "pour": ["pour", "water_pour", "fill", "drink", "tankard"],
    "splash": ["splash", "drip", "water_drop", "fountain"],
    "ignite": ["ignite", "light", "match", "lighter", "torch", "burn", "fire", "crackle"],
    "creak": ["creak", "door_creak", "floor_creak", "wood_creak", "groan"],
    "open": ["open", "door_open", "unlock", "uncork"],
    "close": ["close", "door_close", "shut", "slam"],
    "rustle": ["rustle", "cloth", "leather", "quiver", "pouch", "armor", "belt"],
    "clink": ["coin", "coins", "clink", "jingle", "shake", "flip"],
    "snap": ["snap", "break", "twigs_break", "branch"],
    "rumble": ["thunder", "earthquake", "rumble", "drone", "tremor"],
    "howl": ["wind", "howl", "gust", "breeze", "storm"],
    "gallop": ["gallop", "horse_chase", "horses", "hoof", "hooves", "trot", "clatter"],
    "cut": ["cut", "slice", "chop", "impale", "stab"],
    "chime": ["bell", "chime", "ring", "whistle"],
    "ambient_bed": ["ambience", "ambient", "background", "loop", "room_tone", "weather"],
    "musical_cue": ["music", "theme", "ost", "orchestral", "strings", "score", "drone_bed"],
}

EXCITER_KEYWORDS: Dict[str, List[str]] = {
    "steel": ["sword", "blade", "knife", "dagger", "steel", "seax", "iron", "metal"],
    "leather": ["boots", "leather", "belt", "quiver", "scabbard"],
    "wood": ["wood", "twigs", "branch", "door", "floor", "bowl", "stick", "timber"],
    "stone": ["stone", "rock", "gravel", "cobble", "pavement"],
    "water": ["water", "splash", "pour", "rain", "river", "liquid", "stream"],
    "fire": ["fire", "campfire", "flame", "torch", "match", "hearth"],
    "wind": ["wind", "gust", "storm", "breeze", "air"],
    "coin": ["coin", "gold", "silver", "metalpot"],
    "cloth": ["cloth", "pouch", "fabric", "cloak"],
    "horse": ["horse", "hoof", "equine"],
    "flesh": ["body", "punch", "fist", "grunt", "footstep"],
    "glass": ["glass", "bottle", "vial"],
    "string": ["string", "violin", "cello", "lute", "orchestra"],
    "brass": ["horn", "brass", "trumpet"],
    "percussion": ["drum", "taiko", "percussion", "cymbal"],
}

RESONATOR_KEYWORDS: Dict[str, List[str]] = {
    "hall": ["hall", "castle", "corridor", "interior", "great_hall", "church"],
    "wood_floor": ["wood", "floor", "plank", "timber"],
    "stone_wall": ["stone", "dungeon", "cave", "cellar", "crypt"],
    "ground": ["ground", "soil", "mud", "dirt", "grass", "path"],
    "tavern": ["tavern", "inn", "bar", "pub", "cellar"],
    "door": ["door", "gate", "portal", "shutter"],
    "sky": ["sky", "exterior", "open_air", "atmosphere"],
    "hearth": ["hearth", "fireplace", "chimney"],
    "scabbard": ["scabbard", "sheath"],
    "goblet": ["goblet", "tankard", "bowl", "cup"],
    "bottle": ["bottle", "vial", "flagon"],
    "room": ["room", "chamber", "indoor", "living"],
    "air": ["air", "wind", "open", "outdoor"],
}


class UniversalSoundBankIngester:
    """
    Universal Sound Bank Ingestion & Acoustic Characterization Engine.
    Parses directories of audio files, runs full format and EBU R128 / spectral probes,
    classifies physical sound design semantics, and populates SQLite FTS5 search tables.
    """

    def __init__(
        self,
        db_path: Optional[Union[Path, str]] = None,
        bank_root: Optional[Union[Path, str]] = None,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
    ):
        self.bank_root = Path(bank_root or DEFAULT_BANK_DIR).resolve()
        self.bank_root.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path or (self.bank_root / "sound_bank.db")).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ffmpeg = ffmpeg_bin
        self.ffprobe = ffprobe_bin
        self._lock = threading.Lock()
        self._init_db()

    @contextlib.contextmanager
    def _get_conn(self) -> Generator[sqlite3.Connection, None, None]:
        """Provide a thread-safe connection with WAL journal mode and busy timeout."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=10000;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize the sound_assets relational table, FTS5 virtual table, and triggers."""
        with self._lock, self._get_conn() as conn:
            # 1. Primary Sound Assets Catalog
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sound_assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filepath TEXT UNIQUE NOT NULL,
                    filename TEXT NOT NULL,
                    category TEXT NOT NULL,          -- foley, ambience, music, sfx
                    action_type TEXT NOT NULL,       -- impact, footstep, clash, draw, whoosh, etc.
                    exciter TEXT NOT NULL,           -- metal, leather, wood, stone, water, etc.
                    resonator TEXT NOT NULL,         -- ground, hall, room, wood_floor, etc.
                    tags TEXT NOT NULL,              -- Space-delimited searchable tokens
                    duration_sec REAL DEFAULT 0.0,
                    sample_rate INTEGER DEFAULT 48000,
                    channels INTEGER DEFAULT 2,
                    format TEXT,                    -- wav, mp3, flac, ogg
                    file_size_bytes INTEGER DEFAULT 0,
                    bit_rate INTEGER DEFAULT 0,
                    integrated_lufs REAL DEFAULT -70.0,
                    true_peak_db REAL DEFAULT -70.0,
                    loudness_range_lu REAL DEFAULT 0.0,
                    spectral_centroid_hz REAL DEFAULT 0.0,
                    rms_level_db REAL DEFAULT -70.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. SQLite FTS5 Virtual Search Table
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS sound_assets_fts USING fts5(
                    filename,
                    category,
                    action_type,
                    exciter,
                    resonator,
                    tags,
                    content='sound_assets',
                    content_rowid='id'
                );
            """)

            # 3. Synchronisation Triggers
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS sound_assets_ai AFTER INSERT ON sound_assets BEGIN
                    INSERT INTO sound_assets_fts(rowid, filename, category, action_type, exciter, resonator, tags)
                    VALUES (new.id, new.filename, new.category, new.action_type, new.exciter, new.resonator, new.tags);
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS sound_assets_ad AFTER DELETE ON sound_assets BEGIN
                    INSERT INTO sound_assets_fts(sound_assets_fts, rowid, filename, category, action_type, exciter, resonator, tags)
                    VALUES ('delete', old.id, old.filename, old.category, old.action_type, old.exciter, old.resonator, old.tags);
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS sound_assets_au AFTER UPDATE ON sound_assets BEGIN
                    INSERT INTO sound_assets_fts(sound_assets_fts, rowid, filename, category, action_type, exciter, resonator, tags)
                    VALUES ('delete', old.id, old.filename, old.category, old.action_type, old.exciter, old.resonator, old.tags);
                    INSERT INTO sound_assets_fts(rowid, filename, category, action_type, exciter, resonator, tags)
                    VALUES (new.id, new.filename, new.category, new.action_type, new.exciter, new.resonator, new.tags);
                END;
            """)

            # 4. Performance B-Tree Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sound_assets_category ON sound_assets(category);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sound_assets_action ON sound_assets(action_type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sound_assets_exciter ON sound_assets(exciter);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sound_assets_resonator ON sound_assets(resonator);")
            conn.commit()

    def probe_format(self, filepath: Union[Path, str]) -> Dict[str, Any]:
        """Probe technical stream format parameters using ffprobe."""
        p = Path(filepath).resolve()
        if not p.exists() or p.stat().st_size == 0:
            return {
                "duration_sec": 0.0,
                "sample_rate": 48000,
                "channels": 2,
                "format": p.suffix.lstrip(".").lower(),
                "file_size_bytes": 0,
                "bit_rate": 0,
            }

        cmd = [
            self.ffprobe,
            "-v", "error",
            "-show_format",
            "-show_streams",
            "-of", "json",
            str(p),
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
            if res.returncode != 0:
                logger.warning(f"  [!] ffprobe error on {p.name}: {res.stderr[:200]}")
                return self._fallback_format(p)

            data = json.loads(res.stdout)
            streams = data.get("streams", [])
            audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
            fmt = data.get("format", {})

            duration = float(fmt.get("duration", audio_stream.get("duration", 0.0)))
            sr = int(audio_stream.get("sample_rate", 48000))
            channels = int(audio_stream.get("channels", 2))
            codec = audio_stream.get("codec_name", fmt.get("format_name", p.suffix.lstrip(".")))
            size_b = int(fmt.get("size", p.stat().st_size))
            br = int(fmt.get("bit_rate", audio_stream.get("bit_rate", 0)))

            return {
                "duration_sec": round(duration, 3),
                "sample_rate": sr,
                "channels": channels,
                "format": codec.split(",")[0].lower(),
                "file_size_bytes": size_b,
                "bit_rate": br,
            }
        except Exception as e:
            logger.warning(f"  [!] Exception probing format of {p.name}: {e}")
            return self._fallback_format(p)

    def _fallback_format(self, p: Path) -> Dict[str, Any]:
        """Fallback format probe if ffprobe command fails."""
        return {
            "duration_sec": 0.0,
            "sample_rate": 48000,
            "channels": 2,
            "format": p.suffix.lstrip(".").lower(),
            "file_size_bytes": p.stat().st_size if p.exists() else 0,
            "bit_rate": 0,
        }

    def probe_audio_metrics(self, filepath: Union[Path, str], sample_rate: int = 48000) -> Dict[str, float]:
        """
        Probe acoustic loudness and spectral features using ffmpeg ebur128 and astats filters.
        Extracts Integrated LUFS, Loudness Range (LU), True Peak (dBFS), RMS level (dB),
        and dominant Spectral Centroid estimate (Hz).
        """
        p = Path(filepath).resolve()
        metrics = {
            "integrated_lufs": -70.0,
            "true_peak_db": -70.0,
            "loudness_range_lu": 0.0,
            "rms_level_db": -70.0,
            "spectral_centroid_hz": 0.0,
        }
        if not p.exists() or p.stat().st_size == 0:
            return metrics

        cmd = [
            self.ffmpeg,
            "-y",
            "-i", str(p),
            "-af", "ebur128=peak=true,astats",
            "-f", "null",
            "-",
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
            err = res.stderr

            # 1. EBU R128 Integrated Loudness
            i_match = re.search(r"Integrated loudness:\s+I:\s+([-\d.]+)\s+LUFS", err)
            if i_match:
                metrics["integrated_lufs"] = float(i_match.group(1))

            # 2. EBU R128 Loudness Range
            lra_match = re.search(r"Loudness range:\s+LRA:\s+([-\d.]+)\s+LU", err)
            if lra_match:
                metrics["loudness_range_lu"] = float(lra_match.group(1))

            # 3. EBU R128 True Peak
            tp_match = re.search(r"True peak:\s+Peak:\s+([-\d.]+)\s+dBFS", err)
            if tp_match:
                metrics["true_peak_db"] = float(tp_match.group(1))

            # 4. RMS Level from astats
            rms_match = re.search(r"RMS level dB:\s+([-\d.]+)", err)
            if rms_match:
                metrics["rms_level_db"] = float(rms_match.group(1))

            # 5. Spectral Centroid / Brightness from Zero Crossings Rate
            zcr_match = re.search(r"Zero crossings rate:\s+([-\d.]+)", err)
            if zcr_match:
                zcr = float(zcr_match.group(1))
                # Spectral centroid approximate via zero-crossing rate: ZCR * Nyquist Frequency
                nyquist = sample_rate / 2.0
                metrics["spectral_centroid_hz"] = round(zcr * nyquist, 1)

        except Exception as e:
            logger.warning(f"  [!] Exception measuring audio metrics on {p.name}: {e}")

        return metrics

    def classify_semantics(self, filepath: Union[Path, str]) -> Dict[str, str]:
        """
        Classify sound design taxonomy: category, action_type, exciter, resonator,
        and auto-generate clean space-separated tags based on path, filename tokens, and synonyms.
        """
        p = Path(filepath)
        name_stem = p.stem.lower()
        parts = [p.name.lower()] + [parent.name.lower() for parent in p.parents if parent.name]
        full_text = " ".join(parts).replace("_", " ").replace("-", " ")
        tokens = set(re.findall(r"[a-z0-9]+", full_text))

        # 1. Determine Category (foley, ambience, music, sfx)
        category = "foley"
        if any(w in tokens for w in ["ambience", "ambient", "weather", "wind", "rain", "tavern", "forest", "room"]):
            category = "ambience"
        elif any(w in tokens for w in ["music", "score", "ost", "theme", "bed", "orchestral", "track", "incompetech"]):
            category = "music"
        elif any(w in tokens for w in ["magic", "spell", "blast", "explosion", "whoosh", "riser", "sfx"]):
            category = "sfx"

        # 2. Determine Action Type
        action_type = "impact"
        for act, keywords in ACTION_TYPE_KEYWORDS.items():
            if any(k in tokens or k in name_stem for k in keywords):
                action_type = act
                break

        # 3. Determine Exciter
        exciter = "wood"
        for exc, keywords in EXCITER_KEYWORDS.items():
            if any(k in tokens or k in name_stem for k in keywords):
                exciter = exc
                break

        # 4. Determine Resonator
        resonator = "room"
        for res, keywords in RESONATOR_KEYWORDS.items():
            if any(k in tokens or k in name_stem for k in keywords):
                resonator = res
                break

        # 5. Build Enriched Search Tags
        tag_list = list(tokens)
        tag_list.extend([category, action_type, exciter, resonator])
        # Deduplicate while preserving order
        seen = set()
        clean_tags = []
        for t in tag_list:
            t_clean = t.strip().lower()
            if t_clean and len(t_clean) > 1 and t_clean not in seen and not t_clean.isdigit():
                seen.add(t_clean)
                clean_tags.append(t_clean)

        return {
            "category": category,
            "action_type": action_type,
            "exciter": exciter,
            "resonator": resonator,
            "tags": " ".join(clean_tags),
        }

    def ingest_file(
        self,
        filepath: Union[Path, str],
        category: Optional[str] = None,
        action_type: Optional[str] = None,
        exciter: Optional[str] = None,
        resonator: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> Optional[int]:
        """
        Probe, classify, and insert an individual audio file into sound_assets & sound_assets_fts.
        Performs an atomic upsert on conflict of filepath.
        """
        p = Path(filepath).resolve()
        if not p.exists() or p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return None

        # 1. Technical Format Probe
        fmt_info = self.probe_format(p)

        # 2. Acoustic Metrics Probe (EBU R128 & Spectral)
        metrics = self.probe_audio_metrics(p, sample_rate=fmt_info.get("sample_rate", 48000))

        # 3. Semantic Taxonomy
        semantics = self.classify_semantics(p)
        cat = category or semantics["category"]
        act = action_type or semantics["action_type"]
        exc = exciter or semantics["exciter"]
        res_name = resonator or semantics["resonator"]
        tag_str = tags or semantics["tags"]

        norm_path = str(p).replace("\\", "/")
        filename = p.name

        with self._lock, self._get_conn() as conn:
            cur = conn.execute("""
                INSERT INTO sound_assets (
                    filepath, filename, category, action_type, exciter, resonator, tags,
                    duration_sec, sample_rate, channels, format, file_size_bytes, bit_rate,
                    integrated_lufs, true_peak_db, loudness_range_lu, spectral_centroid_hz,
                    rms_level_db, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(filepath) DO UPDATE SET
                    filename=excluded.filename,
                    category=excluded.category,
                    action_type=excluded.action_type,
                    exciter=excluded.exciter,
                    resonator=excluded.resonator,
                    tags=excluded.tags,
                    duration_sec=excluded.duration_sec,
                    sample_rate=excluded.sample_rate,
                    channels=excluded.channels,
                    format=excluded.format,
                    file_size_bytes=excluded.file_size_bytes,
                    bit_rate=excluded.bit_rate,
                    integrated_lufs=excluded.integrated_lufs,
                    true_peak_db=excluded.true_peak_db,
                    loudness_range_lu=excluded.loudness_range_lu,
                    spectral_centroid_hz=excluded.spectral_centroid_hz,
                    rms_level_db=excluded.rms_level_db,
                    updated_at=CURRENT_TIMESTAMP
                RETURNING id;
            """, (
                norm_path, filename, cat, act, exc, res_name, tag_str,
                fmt_info["duration_sec"], fmt_info["sample_rate"], fmt_info["channels"],
                fmt_info["format"], fmt_info["file_size_bytes"], fmt_info["bit_rate"],
                metrics["integrated_lufs"], metrics["true_peak_db"], metrics["loudness_range_lu"],
                metrics["spectral_centroid_hz"], metrics["rms_level_db"]
            ))
            row = cur.fetchone()
            return row[0] if row else None

    def ingest_directory(
        self,
        dir_path: Union[Path, str],
        recursive: bool = True,
        max_workers: int = 4,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Recursively discovers all audio files (WAV, FLAC, OGG, MP3) in directory
        and concurrently ingests them into the sound catalog.
        """
        root = Path(dir_path).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Source directory does not exist: {root}")

        pattern = "**/*" if recursive else "*"
        audio_files = [
            f for f in root.glob(pattern)
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        ]

        total = len(audio_files)
        logger.info(f"[*] Starting ingestion of {total} audio assets from {root}...")

        stats = {
            "scanned": total,
            "ingested": 0,
            "failed": 0,
            "total_duration_sec": 0.0,
        }

        if total == 0:
            return stats

        with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 8))) as executor:
            future_to_file = {executor.submit(self.ingest_file, f): f for f in audio_files}
            for i, future in enumerate(as_completed(future_to_file), start=1):
                f = future_to_file[future]
                try:
                    asset_id = future.result()
                    if asset_id is not None:
                        stats["ingested"] += 1
                    else:
                        stats["failed"] += 1
                except Exception as e:
                    stats["failed"] += 1
                    logger.warning(f"  [!] Failed to ingest {f.name}: {e}")

                if progress_callback:
                    progress_callback(i, total, f.name)

        # Compute summary stats
        with self._get_conn() as conn:
            row = conn.execute("SELECT SUM(duration_sec) FROM sound_assets;").fetchone()
            stats["total_duration_sec"] = round(row[0] or 0.0, 2)

        logger.info(
            f"[+] Ingestion complete: {stats['ingested']} indexed, {stats['failed']} failed, "
            f"{stats['total_duration_sec']/60:.1f} minutes of audio in bank."
        )
        return stats

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        action_type: Optional[str] = None,
        exciter: Optional[str] = None,
        resonator: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Fast multi-parameter acoustic search using FTS5 index and relational filters.
        """
        with self._get_conn() as conn:
            params: List[Any] = []
            where_clauses: List[str] = []

            # 1. Full-text search
            clean_q = re.sub(r"[^\w\s]", "", query).strip()
            if clean_q:
                fts_terms = " ".join(f"{term}*" for term in clean_q.split())
                where_clauses.append("sound_assets.id IN (SELECT rowid FROM sound_assets_fts WHERE sound_assets_fts MATCH ?)")
                params.append(fts_terms)

            # 2. Relational filters
            if category:
                where_clauses.append("sound_assets.category = ?")
                params.append(category.lower())
            if action_type:
                where_clauses.append("sound_assets.action_type = ?")
                params.append(action_type.lower())
            if exciter:
                where_clauses.append("sound_assets.exciter = ?")
                params.append(exciter.lower())
            if resonator:
                where_clauses.append("sound_assets.resonator = ?")
                params.append(resonator.lower())

            where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            sql = f"""
                SELECT
                    id, filepath, filename, category, action_type, exciter, resonator, tags,
                    duration_sec, sample_rate, channels, format, file_size_bytes, bit_rate,
                    integrated_lufs, true_peak_db, loudness_range_lu, spectral_centroid_hz,
                    rms_level_db
                FROM sound_assets
                {where_str}
                ORDER BY duration_sec ASC
                LIMIT ?;
            """
            params.append(limit)

            try:
                rows = conn.execute(sql, params).fetchall()
                return [dict(r) for r in rows]
            except sqlite3.OperationalError as e:
                logger.warning(f"  [!] FTS5 search error '{e}', falling back to LIKE...")
                return self._fallback_like_search(conn, clean_q, category, action_type, exciter, resonator, limit)

    def _fallback_like_search(
        self,
        conn: sqlite3.Connection,
        query: str,
        category: Optional[str],
        action_type: Optional[str],
        exciter: Optional[str],
        resonator: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Graceful LIKE query fallback if FTS syntax query fails."""
        where_clauses = ["(tags LIKE ? OR filename LIKE ?)"]
        params: List[Any] = [f"%{query}%", f"%{query}%"]
        if category:
            where_clauses.append("category = ?")
            params.append(category.lower())
        if action_type:
            where_clauses.append("action_type = ?")
            params.append(action_type.lower())
        if exciter:
            where_clauses.append("exciter = ?")
            params.append(exciter.lower())
        if resonator:
            where_clauses.append("resonator = ?")
            params.append(resonator.lower())

        sql = f"""
            SELECT * FROM sound_assets
            WHERE {' AND '.join(where_clauses)}
            LIMIT ?;
        """
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_asset_by_id(self, asset_id: int) -> Optional[Dict[str, Any]]:
        """Fetch asset metadata record by numeric ID."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM sound_assets WHERE id = ?;", (asset_id,)).fetchone()
            return dict(row) if row else None

    def get_asset_by_path(self, filepath: Union[Path, str]) -> Optional[Dict[str, Any]]:
        """Fetch asset metadata record by normalized file path."""
        norm_path = str(Path(filepath).resolve()).replace("\\", "/")
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM sound_assets WHERE filepath = ?;", (norm_path,)).fetchone()
            return dict(row) if row else None

    def get_stats(self) -> Dict[str, Any]:
        """Aggregate catalog metrics and category counts."""
        with self._get_conn() as conn:
            total_assets = conn.execute("SELECT COUNT(*) FROM sound_assets;").fetchone()[0]
            total_dur = conn.execute("SELECT SUM(duration_sec) FROM sound_assets;").fetchone()[0] or 0.0
            avg_lufs = conn.execute("SELECT AVG(integrated_lufs) FROM sound_assets WHERE integrated_lufs > -60.0;").fetchone()[0] or -19.0

            cat_rows = conn.execute("SELECT category, COUNT(*) FROM sound_assets GROUP BY category;").fetchall()
            by_category = {r[0]: r[1] for r in cat_rows}

            act_rows = conn.execute("SELECT action_type, COUNT(*) FROM sound_assets GROUP BY action_type ORDER BY COUNT(*) DESC LIMIT 10;").fetchall()
            by_action = {r[0]: r[1] for r in act_rows}

            return {
                "total_assets": total_assets,
                "total_duration_minutes": round(total_dur / 60.0, 2),
                "average_integrated_lufs": round(avg_lufs, 2),
                "by_category": by_category,
                "top_actions": by_action,
            }


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Universal Sound Bank Ingestion & Acoustic Characterization Engine")
    parser.add_argument("directory", help="Directory path to scan and ingest")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to SQLite database")
    parser.add_argument("--workers", type=int, default=4, help="Concurrency workers")
    parser.add_argument("--no-recursive", action="store_true", help="Do not scan subdirectories")

    args = parser.parse_args()
    ingester = UniversalSoundBankIngester(db_path=args.db)
    res = ingester.ingest_directory(args.directory, recursive=not args.no_recursive, max_workers=args.workers)
    print(f"\nIngestion Results:\n{json.dumps(res, indent=2)}")
    print(f"\nBank Stats:\n{json.dumps(ingester.get_stats(), indent=2)}")
