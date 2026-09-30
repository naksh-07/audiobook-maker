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
import errno
import shutil
import sqlite3
import contextlib
import subprocess
import urllib.request
import urllib.error
import threading
import uuid
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, List, Optional, Generator, Union, Tuple, Callable
import numpy as np

from audiobook_factory.logger import logger
from audiobook_factory.sound_bank_cache import SoundBankCacheManager
from audiobook_factory.contracts import (
    SonicGenome,
    MeasuredAudioFacts,
    SourceMetadata,
    NormalizedSourceFields,
    ProvenanceRecord,
    AudioEventRecord,
    ClassifierInferences,
    ClassifierPrediction,
    SemanticEmbeddingFacts,
)
from audiobook_factory.deterministic_audio_analyzer import (
    DeterministicAudioAnalyzer,
    ANALYZER_VERSION,
    ANALYZER_ID,
    ONTOLOGY_VERSION,
)

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
        self.bank_dir = self.bank_root
        self.cache_dir = self.bank_root / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path or (self.bank_root / "sound_bank.db")).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_manager = SoundBankCacheManager(db_path=self.db_path, cache_dir=self.cache_dir)
        self.audio_analyzer = DeterministicAudioAnalyzer()
        self._init_db()

    @contextlib.contextmanager
    def _get_conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Initialize relational metadata table, FTS5 virtual table, and relationship index."""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sound_catalog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    filepath TEXT UNIQUE,
                    category TEXT,       -- AMB, FOL, SFX, MUS, LEITMOTIF, CHAPTER_BED, DYNAMIC_STEM, STINGER
                    subcategory TEXT,    -- Weather, Tavern, Steps, Magic, Combat, Drone, Nature, Props, etc.
                    mood TEXT,           -- mysterious, tense, peaceful, epic, emotional, dark, default
                    tags TEXT,           -- Space-separated searchable tokens
                    duration_sec REAL DEFAULT 0.0,
                    size_bytes INTEGER DEFAULT 0,
                    format TEXT,
                    source_url TEXT,
                    is_downloaded INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Non-destructively auto-migrate all Sonic Intelligence schema columns
            existing_cols = {c[1] for c in conn.execute("PRAGMA table_info(sound_catalog)").fetchall()}
            column_defs = [
                ("category", "TEXT DEFAULT 'SFX'"),
                ("subcategory", "TEXT DEFAULT 'General'"),
                ("mood", "TEXT DEFAULT 'default'"),
                ("tags", "TEXT DEFAULT ''"),
                ("duration_sec", "REAL DEFAULT 0.0"),
                ("size_bytes", "INTEGER DEFAULT 0"),
                ("format", "TEXT DEFAULT ''"),
                ("title", "TEXT DEFAULT ''"),
                ("description", "TEXT DEFAULT ''"),
                ("source_collection", "TEXT DEFAULT ''"),
                ("license", "TEXT DEFAULT 'Royalty-Free'"),
                ("creator_attribution", "TEXT DEFAULT ''"),
                ("source_url", "TEXT DEFAULT NULL"),
                ("mirror_url", "TEXT DEFAULT NULL"),
                ("source_page_url", "TEXT DEFAULT NULL"),
                ("url_status", "TEXT DEFAULT 'unverified'"),
                ("last_verified_at", "TIMESTAMP DEFAULT NULL"),
                ("is_downloaded", "INTEGER DEFAULT 1"),
                ("tempo_bpm", "REAL DEFAULT 0.0"),
                ("key_tonality", "TEXT DEFAULT ''"),
                ("time_signature", "TEXT DEFAULT '4/4'"),
                ("wave_style", "TEXT DEFAULT 'general'"),
                ("temporal_character", "TEXT DEFAULT 'transient'"),
                ("energy_profile", "TEXT DEFAULT 'medium'"),
                ("texture_profile", "TEXT DEFAULT 'organic'"),
                ("exciter", "TEXT DEFAULT ''"),
                ("resonator", "TEXT DEFAULT ''"),
                ("action_type", "TEXT DEFAULT ''"),
                ("surface", "TEXT DEFAULT ''"),
                ("perspective", "TEXT DEFAULT 'medium'"),
                ("acoustic_space", "TEXT DEFAULT ''"),
                ("reverb_character", "TEXT DEFAULT ''"),
                ("dramatic_role", "TEXT DEFAULT 'general'"),
                ("foreground_strength", "REAL DEFAULT 0.5"),
                ("voice_masking_risk", "TEXT DEFAULT 'LOW'"),
                ("whisper_compatibility", "REAL DEFAULT 0.5"),
                ("last_accessed_at", "TIMESTAMP DEFAULT NULL"),
                ("cache_pin_status", "TEXT DEFAULT 'normal'"),
                ("sonic_genome", "TEXT DEFAULT '{}'"),
                # Measured DSP facts & deterministic analysis columns
                ("sample_rate", "INTEGER DEFAULT 48000"),
                ("channels", "INTEGER DEFAULT 2"),
                ("bit_depth", "INTEGER DEFAULT 16"),
                ("integrated_lufs", "REAL DEFAULT NULL"),
                ("true_peak_db", "REAL DEFAULT NULL"),
                ("loudness_range_lu", "REAL DEFAULT NULL"),
                ("rms_level_db", "REAL DEFAULT NULL"),
                ("spectral_centroid_hz", "REAL DEFAULT NULL"),
                ("spectral_bandwidth_hz", "REAL DEFAULT NULL"),
                ("spectral_rolloff_hz", "REAL DEFAULT NULL"),
                ("spectral_flatness", "REAL DEFAULT NULL"),
                ("zero_crossing_rate", "REAL DEFAULT NULL"),
                ("silence_ratio", "REAL DEFAULT NULL"),
                ("analysis_version", "TEXT DEFAULT ''"),
                ("last_analyzed_at", "TIMESTAMP DEFAULT NULL"),
                # Metadata Harvesting Pilot additions (non-destructive)
                ("raw_metadata", "TEXT DEFAULT '{}'"),
                ("source_provenance", "TEXT DEFAULT '{}'"),
                ("bundle_name", "TEXT DEFAULT ''"),
                ("source_asset_id", "TEXT DEFAULT ''"),
                ("variation_group", "TEXT DEFAULT ''"),
                ("duplicate_of_id", "INTEGER DEFAULT NULL"),
                # IP Lore & Franchise Affinity System
                ("franchise_affinity", "TEXT DEFAULT 'generic'"),
                ("lore_tags", "TEXT DEFAULT ''"),
                ("ip_priority", "REAL DEFAULT 0.0"),
            ]
            for col_name, col_type in column_defs:
                if col_name not in existing_cols:
                    if not re.match(r"^[a-zA-Z0-9_]+$", col_name):
                        raise ValueError(f"Invalid column name: {col_name}")
                    conn.execute(f"ALTER TABLE sound_catalog ADD COLUMN {col_name} {col_type};")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_sound_catalog_lufs ON sound_catalog(integrated_lufs);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sound_catalog_centroid ON sound_catalog(spectral_centroid_hz);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sound_catalog_bundle ON sound_catalog(bundle_name);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sound_catalog_source_asset_id ON sound_catalog(source_asset_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sound_catalog_duplicate_of ON sound_catalog(duplicate_of_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sound_catalog_franchise ON sound_catalog(franchise_affinity);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sound_catalog_ip_priority ON sound_catalog(ip_priority);")

            # Check if FTS5 table needs upgrade to cover rich fields
            fts_cols = set()
            try:
                fts_cols = {c[1] for c in conn.execute("PRAGMA table_info(sound_catalog_fts)").fetchall()}
            except Exception:
                pass

            target_fts_cols = {"title", "description", "wave_style", "exciter", "resonator", "action_type", "dramatic_role"}
            if not target_fts_cols.issubset(fts_cols):
                conn.execute("DROP TRIGGER IF EXISTS sound_catalog_ai;")
                conn.execute("DROP TRIGGER IF EXISTS sound_catalog_au;")
                conn.execute("DROP TRIGGER IF EXISTS sound_catalog_ad;")
                conn.execute("DROP TABLE IF EXISTS sound_catalog_fts;")
                conn.execute("""
                    CREATE VIRTUAL TABLE sound_catalog_fts USING fts5(
                        filename,
                        title,
                        description,
                        category,
                        subcategory,
                        mood,
                        wave_style,
                        exciter,
                        resonator,
                        action_type,
                        dramatic_role,
                        tags,
                        content='sound_catalog',
                        content_rowid='id'
                    );
                """)
                # Populate FTS5 from existing content table
                try:
                    conn.execute("INSERT INTO sound_catalog_fts(sound_catalog_fts) VALUES('rebuild');")
                except Exception:
                    pass

            # Triggers to keep FTS5 synchronized with main catalog table
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS sound_catalog_ai AFTER INSERT ON sound_catalog BEGIN
                    INSERT INTO sound_catalog_fts(rowid, filename, title, description, category, subcategory, mood, wave_style, exciter, resonator, action_type, dramatic_role, tags)
                    VALUES (new.id, new.filename, new.title, new.description, new.category, new.subcategory, new.mood, new.wave_style, new.exciter, new.resonator, new.action_type, new.dramatic_role, new.tags);
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS sound_catalog_ad AFTER DELETE ON sound_catalog BEGIN
                    INSERT INTO sound_catalog_fts(sound_catalog_fts, rowid, filename, title, description, category, subcategory, mood, wave_style, exciter, resonator, action_type, dramatic_role, tags)
                    VALUES ('delete', old.id, old.filename, old.title, old.description, old.category, old.subcategory, old.mood, old.wave_style, old.exciter, old.resonator, old.action_type, old.dramatic_role, old.tags);
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS sound_catalog_au AFTER UPDATE ON sound_catalog BEGIN
                    INSERT INTO sound_catalog_fts(sound_catalog_fts, rowid, filename, title, description, category, subcategory, mood, wave_style, exciter, resonator, action_type, dramatic_role, tags)
                    VALUES ('delete', old.id, old.filename, old.title, old.description, old.category, old.subcategory, old.mood, old.wave_style, old.exciter, old.resonator, old.action_type, old.dramatic_role, old.tags);
                    INSERT INTO sound_catalog_fts(rowid, filename, title, description, category, subcategory, mood, wave_style, exciter, resonator, action_type, dramatic_role, tags)
                    VALUES (new.id, new.filename, new.title, new.description, new.category, new.subcategory, new.mood, new.wave_style, new.exciter, new.resonator, new.action_type, new.dramatic_role, new.tags);
                END;
            """)

            # Asset Relationships Table for micro-sequencing and sound families
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sound_asset_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_asset_id INTEGER NOT NULL,
                    target_asset_id INTEGER NOT NULL,
                    relationship_type TEXT NOT NULL, -- predecessor, successor, companion, variation, intensity_variant
                    confidence REAL DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_asset_id) REFERENCES sound_catalog(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_asset_id) REFERENCES sound_catalog(id) ON DELETE CASCADE
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_asset_rel_src ON sound_asset_relationships(source_asset_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_asset_rel_type ON sound_asset_relationships(relationship_type);")
            conn.commit()

            # Sound Track Sections table for intelligent cue-slicing & energy zones
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sound_track_sections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER NOT NULL,
                    section_name TEXT NOT NULL,      -- INTRO_BED, RISING_TENSION, CLIMAX_DROP, AFTERMATH_FADE
                    start_sec REAL NOT NULL,
                    end_sec REAL NOT NULL,
                    energy_level INTEGER NOT NULL,   -- 1 to 10
                    tempo_bpm INTEGER DEFAULT 0,
                    tags TEXT,
                    FOREIGN KEY (track_id) REFERENCES sound_catalog(id) ON DELETE CASCADE
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_track_sections ON sound_track_sections(track_id, section_name);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_section_energy ON sound_track_sections(energy_level);")

            # Analysis Runs & Provenance Ledger Table (idempotent run logs for all 6 epistemic stages)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sound_analysis_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER NOT NULL,
                    analyzer_id TEXT NOT NULL,
                    analyzer_version TEXT NOT NULL,
                    analysis_stage TEXT NOT NULL,
                    execution_status TEXT NOT NULL,
                    error_message TEXT,
                    measured_facts TEXT,
                    provenance_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (track_id) REFERENCES sound_catalog(id) ON DELETE CASCADE
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_runs_track ON sound_analysis_runs(track_id, analyzer_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_runs_stage ON sound_analysis_runs(analysis_stage);")

            # Temporal Audio Events Table (transients, active regions, silence, classifier events)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sound_temporal_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    start_sec REAL NOT NULL,
                    end_sec REAL NOT NULL,
                    confidence REAL,
                    source_method TEXT NOT NULL,
                    detector_id TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (track_id) REFERENCES sound_catalog(id) ON DELETE CASCADE
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_temporal_events_track ON sound_temporal_events(track_id, event_type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_temporal_events_timing ON sound_temporal_events(track_id, start_sec, end_sec);")

            # Phase 2: Dedicated Vector Embeddings Table (compact float32 BLOB storage)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sound_embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER NOT NULL,
                    model_id TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    embedding_dim INTEGER NOT NULL,
                    embedding_bytes BLOB NOT NULL,
                    preprocessing_version TEXT NOT NULL,
                    source_method TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (track_id) REFERENCES sound_catalog(id) ON DELETE CASCADE,
                    UNIQUE(track_id, model_id, model_version)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_track ON sound_embeddings(track_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_model ON sound_embeddings(model_id, model_version);")

            # Phase 2: Dedicated Classifier Inferences Table (preserves raw scores & ranks)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sound_classifier_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER NOT NULL,
                    model_id TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    ontology_id TEXT NOT NULL,
                    raw_label TEXT NOT NULL,
                    normalized_label TEXT,
                    raw_score REAL NOT NULL,
                    calibrated_score REAL,
                    rank INTEGER NOT NULL,
                    start_sec REAL,
                    end_sec REAL,
                    source_method TEXT DEFAULT 'classifier',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (track_id) REFERENCES sound_catalog(id) ON DELETE CASCADE
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_classifier_tags_track ON sound_classifier_tags(track_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_classifier_tags_raw_label ON sound_classifier_tags(raw_label);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_classifier_tags_norm_label ON sound_classifier_tags(normalized_label);")

            # Sonic Genome non-destructive column check & generated columns
            cols = [col[1] for col in conn.execute("PRAGMA table_info(sound_catalog)")]
            if "sonic_genome" not in cols:
                conn.execute("ALTER TABLE sound_catalog ADD COLUMN sonic_genome TEXT DEFAULT '{}';")
            if "genome_valence" not in cols:
                try:
                    conn.execute("ALTER TABLE sound_catalog ADD COLUMN genome_valence REAL GENERATED ALWAYS AS (json_extract(sonic_genome, '$.semantic.valence')) VIRTUAL;")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_sonic_valence ON sound_catalog(genome_valence);")
                except Exception:
                    pass
            if "genome_arousal" not in cols:
                try:
                    conn.execute("ALTER TABLE sound_catalog ADD COLUMN genome_arousal REAL GENERATED ALWAYS AS (json_extract(sonic_genome, '$.semantic.arousal')) VIRTUAL;")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_sonic_arousal ON sound_catalog(genome_arousal);")
                except Exception:
                    pass
            conn.commit()

            # Harmonized sound_assets table for rich EBU R128 LUFS & True Peak DSP metrics
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
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sound_assets_category ON sound_assets(category);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sound_assets_action ON sound_assets(action_type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sound_assets_exciter ON sound_assets(exciter);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sound_assets_resonator ON sound_assets(resonator);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sound_catalog_lru ON sound_catalog(is_downloaded, cache_pin_status, last_accessed_at);")

            # Sliding-Window Streaming Ingestion Batches table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ingestion_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_index INTEGER NOT NULL,
                    source_name TEXT NOT NULL,
                    total_assets INTEGER DEFAULT 0,
                    bytes_downloaded INTEGER DEFAULT 0,
                    bytes_reclaimed INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'PENDING',
                    error_message TEXT DEFAULT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP DEFAULT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ingestion_batches_source ON ingestion_batches(source_name, status);")
            conn.commit()


            # Auto-seed sections if empty
            sec_row = conn.execute("SELECT COUNT(*) FROM sound_track_sections").fetchone()
            if sec_row and sec_row[0] == 0:
                self._seed_track_sections(conn)

    def _seed_track_sections(self, conn: sqlite3.Connection):
        """Seed 100% proportional and novel-agnostic energy landmarks for musical tracks."""
        # Fetch all music tracks
        music_tracks = conn.execute("""
            SELECT id, filename, duration_sec FROM sound_catalog
            WHERE category IN ('MUS', 'LEITMOTIF', 'CHAPTER_BED', 'DYNAMIC_STEM')
        """).fetchall()

        for track in music_tracks:
            t_id = track["id"]
            dur = float(track["duration_sec"] or 0.0)
            if dur <= 0.0:
                continue

            # Proportional landmarks based on track duration percentages:
            # INTRO_BED 0-25%, RISING_TENSION 25-60%, CLIMAX_DROP 60-85%, AFTERMATH_FADE 85-100%
            if dur >= 15.0:
                sections = [
                    ("INTRO_BED", 0.0, round(dur * 0.25, 2), 3, "intro ambient bed exposition quiet"),
                    ("RISING_TENSION", round(dur * 0.25, 2), round(dur * 0.60, 2), 6, "rising tension suspense progression"),
                    ("CLIMAX_DROP", round(dur * 0.60, 2), round(dur * 0.85, 2), 9, "climax drop peak battle dramatic"),
                    ("AFTERMATH_FADE", round(dur * 0.85, 2), round(dur, 2), 3, "aftermath decay resolution outro fade"),
                ]
            else:
                sections = [
                    ("INTRO_BED", 0.0, round(dur, 2), 5, "short stem full cue"),
                ]

            for s_name, s_start, s_end, s_energy, s_tags in sections:
                conn.execute("""
                    INSERT INTO sound_track_sections (track_id, section_name, start_sec, end_sec, energy_level, tags)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (t_id, s_name, s_start, s_end, s_energy, s_tags))

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
        if any(k in parts for k in ("leitmotif", "leitmotifs", "character_theme", "character_themes")):
            category = "LEITMOTIF"
        elif any(k in parts for k in ("chapter_bed", "chapter_beds", "world_bed", "world_beds")):
            category = "CHAPTER_BED"
        elif any(k in parts for k in ("dynamic_stem", "dynamic_stems", "intensity_stems")):
            category = "DYNAMIC_STEM"
        elif any(k in parts for k in ("stinger", "stingers", "accents", "hits")):
            category = "STINGER"
        elif any(k in parts for k in ("ambience", "amb", "atmospheres", "environments")):
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
        elif any(k in name_lower or k in parts for k in ("magic", "spell", "glow", "enchant", "igni", "aard", "quen", "axii", "yrden")):
            subcategory = "Magic"
        elif any(k in name_lower or k in parts for k in ("combat", "sword", "shield", "hit", "punch", "arrow", "parry", "clash", "thud")):
            subcategory = "Combat"
        elif any(k in name_lower or k in parts for k in ("monster", "beast", "creature", "striga", "ghoul", "wolf", "roar", "snarl")):
            subcategory = "Monster"
        elif any(k in name_lower or k in parts for k in ("crypt", "tomb", "dungeon", "hearth", "hall", "swamp", "marsh", "blizzard")):
            subcategory = "Fantasy"
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
        elif any(k in name_lower for k in ("tense", "danger", "dark", "chase", "heartbeat", "striga", "ghoul", "beast", "monster")):
            mood = "tense"
        elif any(k in name_lower for k in ("emotional", "sad", "melancholy", "poignant")):
            mood = "emotional"
        elif any(k in name_lower for k in ("epic", "triumph", "glory", "battle", "brass", "igni", "aard")):
            mood = "epic"

        # 4. Tags: tokens extracted from filename, subfolder, and semantic expansion dictionaries
        tokens = re.findall(r"[a-z0-9]+", name_lower + " " + " ".join(parts[-3:]))
        combined_text = name_lower + " " + " ".join(parts[-3:])
        semantic_expansions = {
            "igni": ["igni", "fire", "flame", "whoosh", "burst", "combustion", "spell", "magic", "blaze", "heat", "pyromancy"],
            "aard": ["aard", "shockwave", "blast", "concussive", "telekinetic", "push", "force", "air", "wave", "kinetic", "impact"],
            "quen": ["quen", "shield", "barrier", "protection", "forcefield", "hum", "resonance", "armor", "defense", "ward"],
            "axii": ["axii", "hypnotic", "chime", "charm", "psychic", "mind", "control", "stun", "daze", "calm", "suggestion"],
            "yrden": ["yrden", "trap", "glyph", "arcane", "circle", "spark", "electric", "zap", "binding", "slow", "rune"],
            "striga": ["striga", "monster", "beast", "roar", "screech", "demonic", "creature", "horror", "growl", "predator", "curse"],
            "ghoul": ["ghoul", "monster", "creature", "snarl", "growl", "necrophage", "scavenge", "flesh", "tear", "bite", "alghoul"],
            "wolf": ["wolf", "wolves", "howl", "howling", "canine", "pack", "wild", "beast", "predator", "forest", "night"],
            "sword": ["sword", "blade", "steel", "weapon", "scabbard", "draw", "clash", "parry", "strike", "swing", "slash"],
            "clash": ["clash", "parry", "strike", "hit", "metal", "duel", "fight", "combat", "steel", "ring", "sword"],
            "thud": ["thud", "body", "heavy", "impact", "fall", "stone", "hit", "ground", "crash", "bodyfall", "blunt"],
            "armor": ["armor", "plate", "chainmail", "metal", "movement", "gear", "knight", "suit", "clank", "rattle"],
            "crypt": ["crypt", "tomb", "dungeon", "subterranean", "stone", "cave", "drips", "damp", "reverberant", "ancient", "vault", "catacomb"],
            "dungeon": ["dungeon", "crypt", "tomb", "cell", "chains", "underground", "stone", "dark", "cave"],
            "hearth": ["hearth", "fireplace", "castle", "hall", "fire", "crackling", "warmth", "indoor", "room"],
            "castle": ["castle", "hall", "hearth", "fireplace", "court", "room", "chamber", "noble"],
            "swamp": ["swamp", "bog", "marsh", "wetland", "eerie", "murky", "night", "water", "mist", "reeds", "nocturnal"],
            "bog": ["bog", "swamp", "marsh", "wetland", "eerie", "murky", "night", "water", "mist", "reeds"],
            "blizzard": ["blizzard", "mountain", "snow", "howling", "wind", "storm", "cold", "winter", "frost", "gale", "ice", "freeze"],
        }
        for kw, exp_tags in semantic_expansions.items():
            if kw in combined_text:
                tokens.extend(exp_tags)

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

        candidate_files = []
        for t_dir in target_dirs:
            if not t_dir.exists():
                continue
            for root, _, files in os.walk(t_dir):
                for f in files:
                    p = Path(root) / f
                    if p.suffix.lower() in valid_exts and not p.name.startswith("."):
                        candidate_files.append(p)

        stats["total_files"] = len(candidate_files)

        # Quick read of existing records to minimize lock time
        existing_records = {}
        with self._get_conn() as conn:
            cur = conn.execute("SELECT id, filepath, size_bytes FROM sound_catalog")
            for row in cur.fetchall():
                existing_records[row["filepath"]] = (row["id"], row["size_bytes"])

        to_update = []
        to_insert = []

        for p in candidate_files:
            filepath_str = str(p.resolve()).replace("\\", "/")
            try:
                size_bytes = p.stat().st_size
            except OSError:
                continue

            existing = existing_records.get(filepath_str)
            if existing and existing[1] == size_bytes:
                stats["skipped"] += 1
                continue

            meta = self._derive_metadata(p)
            dur = self._extract_duration(p)

            if existing:
                to_update.append((
                    p.name, meta["category"], meta["subcategory"], meta["mood"], meta["tags"],
                    dur, size_bytes, p.suffix.lower(), existing[0]
                ))
            else:
                to_insert.append((
                    p.name, filepath_str, meta["category"], meta["subcategory"], meta["mood"],
                    meta["tags"], dur, size_bytes, p.suffix.lower()
                ))

        # Commit batch inserts and updates in a single rapid transaction
        with self._get_conn() as conn:
            if to_update:
                conn.executemany("""
                    UPDATE sound_catalog
                    SET filename = ?, category = ?, subcategory = ?, mood = ?, tags = ?,
                        duration_sec = ?, size_bytes = ?, format = ?
                    WHERE id = ?
                """, to_update)
                stats["updated"] += len(to_update)

            if to_insert:
                conn.executemany("""
                    INSERT INTO sound_catalog
                    (filename, filepath, category, subcategory, mood, tags, duration_sec, size_bytes, format)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, to_insert)
                stats["indexed"] += len(to_insert)

            conn.commit()

        return stats

    _asset_download_locks: Dict[int, threading.Lock] = {}
    _asset_locks_guard = threading.Lock()

    @classmethod
    def _get_asset_download_lock(cls, sound_id: int) -> threading.Lock:
        with cls._asset_locks_guard:
            if sound_id not in cls._asset_download_locks:
                cls._asset_download_locks[sound_id] = threading.Lock()
            return cls._asset_download_locks[sound_id]

    def download_virtual_asset(
        self,
        sound_id: int,
        source_url: Optional[str] = None,
        filename: Optional[str] = None,
        category: Optional[str] = None,
        mirror_url: Optional[str] = None,
        max_retries: int = 2,
    ) -> Optional[Path]:
        """
        JIT downloads a virtual sound asset from remote URL directly to local cache.
        Thread-safe and atomic with unique temporary files, stream verification,
        mirror URL fallback, and post-download local DSP enrichment.
        Updates sound_catalog so future lookups are local.
        """
        # If source_url or filename omitted, query from database
        if not source_url or not filename:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT filename, category, source_url, mirror_url FROM sound_catalog WHERE id = ?",
                    (sound_id,)
                ).fetchone()
                if row:
                    filename = filename or row["filename"]
                    category = category or row["category"] or "SFX"
                    source_url = source_url or row["source_url"]
                    mirror_url = mirror_url or row["mirror_url"]

        category = category or "SFX"
        urls_to_try = [u for u in [source_url, mirror_url] if u]
        if not urls_to_try or not filename:
            return None

        target_dir = self.cache_dir / category
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename

        with SoundBank._get_asset_download_lock(sound_id):
            if target_path.exists() and target_path.stat().st_size > 500:
                with self._get_conn() as conn:
                    conn.execute("UPDATE sound_catalog SET last_accessed_at = CURRENT_TIMESTAMP WHERE id = ?", (sound_id,))
                return target_path

            downloaded = False
            last_err = None

            for url in urls_to_try:
                for attempt in range(max_retries + 1):
                    temp_path = target_path.with_suffix(target_path.suffix + f".{uuid.uuid4().hex[:8]}.part")
                    try:
                        req = urllib.request.Request(
                            url,
                            headers={"User-Agent": "AudiobookFactory/2.0 (https://github.com/naksh-07/audiobook-maker)"}
                        )
                        with urllib.request.urlopen(req, timeout=20.0) as resp:
                            with open(temp_path, "wb") as out_f:
                                shutil.copyfileobj(resp, out_f)

                        # Sanity check: file exists and is not an HTML 404/403 page
                        file_size = temp_path.stat().st_size
                        if file_size <= 0:
                            raise ValueError(f"Downloaded file empty ({file_size} bytes)")

                        with open(temp_path, "rb") as check_f:
                            head = check_f.read(128).lower()
                            if b"<!doctype html" in head or b"<html" in head or b"404 not found" in head:
                                raise ValueError("Remote server returned HTML error page instead of audio stream")

                        temp_path.replace(target_path)
                        downloaded = True
                        break
                    except Exception as e:
                        last_err = e
                        if isinstance(e, OSError) and getattr(e, "errno", None) == errno.ENOSPC:
                            logger.error(f"  [CRITICAL] Out of disk space downloading {filename}: {e}")
                            if temp_path.exists():
                                try:
                                    temp_path.unlink(missing_ok=True)
                                except Exception:
                                    pass
                            return None

                        if temp_path.exists():
                            try:
                                temp_path.unlink(missing_ok=True)
                            except Exception:
                                pass
                        if attempt < max_retries:
                            import time
                            time.sleep(0.5 * (attempt + 1))
                if downloaded:
                    break

            if not downloaded:
                logger.warning(f"  [!] Failed to download virtual asset '{filename}' from all URLs: {last_err}")
                with self._get_conn() as conn:
                    conn.execute("""
                        UPDATE sound_catalog
                        SET url_status = 'broken', last_verified_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (sound_id,))
                return None

            size_bytes = target_path.stat().st_size
            dur = self._extract_duration(target_path)
            norm_path = str(target_path.resolve()).replace("\\", "/")

            with self._get_conn() as conn:
                conn.execute("""
                    UPDATE sound_catalog
                    SET filepath = ?, is_downloaded = 1, size_bytes = ?, duration_sec = ?,
                        url_status = 'available', last_verified_at = CURRENT_TIMESTAMP,
                        last_accessed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (norm_path, size_bytes, dur, sound_id))

            # Post-download DSP Enrichment: extract verified measured facts and update Sonic Genome
            try:
                self.enrich_asset(sound_id=sound_id, force=True)
            except Exception as e:
                logger.debug(f"Post-download DSP enrichment encountered warning for {filename}: {e}")

            # Maintain LRU cache quota
            try:
                self.cache_manager.prune_lru()
            except Exception as e:
                logger.debug(f"LRU pruning check encountered warning: {e}")

            return target_path

    def search_virtual_catalog(
        self,
        query: str = "",
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        wave_style: Optional[str] = None,
        exciter: Optional[str] = None,
        resonator: Optional[str] = None,
        action_type: Optional[str] = None,
        dramatic_role: Optional[str] = None,
        mood: Optional[str] = None,
        min_bpm: Optional[float] = None,
        max_bpm: Optional[float] = None,
        min_duration: Optional[float] = None,
        max_duration: Optional[float] = None,
        whisper_safe_only: bool = False,
        is_downloaded_only: bool = False,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid Sonic Intelligence Retrieval across local and virtual sound catalogs.
        Evaluates multi-dimensional criteria (physical, temporal, dramatic, mix compatibility)
        and returns explainable candidate cards with detailed scoring.
        """
        raw_words = re.findall(r"[a-zA-Z0-9]+", query.strip())
        meaningful_words = [
            w for w in raw_words
            if w.lower() not in ("wav", "mp3", "flac", "ogg", "aiff", "m4a", "and", "or", "not", "near")
        ]

        where_clauses = []
        params = []

        fts_match = False
        if meaningful_words:
            fts_query_and = " AND ".join(f'"{w}"*' for w in meaningful_words)
            where_clauses.append("c.id IN (SELECT rowid FROM sound_catalog_fts WHERE sound_catalog_fts MATCH ?)")
            params.append(fts_query_and)
            fts_match = True

        if category:
            cat_norm = category.upper()
            if cat_norm in ("FOLEY", "FOL", "SFX"):
                where_clauses.append("c.category IN ('FOL', 'SFX')")
            elif cat_norm in ("MUSIC", "MUS"):
                where_clauses.append("c.category IN ('MUS', 'LEITMOTIF', 'CHAPTER_BED', 'DYNAMIC_STEM')")
            elif cat_norm in ("AMBIENCE", "AMB"):
                where_clauses.append("c.category IN ('AMB', 'CHAPTER_BED')")
            else:
                where_clauses.append("c.category = ?")
                params.append(cat_norm)

        if subcategory:
            where_clauses.append("LOWER(c.subcategory) = LOWER(?)")
            params.append(subcategory)

        if wave_style:
            where_clauses.append("LOWER(c.wave_style) = LOWER(?)")
            params.append(wave_style)

        if exciter:
            where_clauses.append("(LOWER(c.exciter) LIKE ? OR LOWER(c.tags) LIKE ?)")
            params.extend([f"%{exciter.lower()}%", f"%{exciter.lower()}%"])

        if resonator:
            where_clauses.append("(LOWER(c.resonator) LIKE ? OR LOWER(c.tags) LIKE ?)")
            params.extend([f"%{resonator.lower()}%", f"%{resonator.lower()}%"])

        if action_type:
            where_clauses.append("(LOWER(c.action_type) LIKE ? OR LOWER(c.tags) LIKE ?)")
            params.extend([f"%{action_type.lower()}%", f"%{action_type.lower()}%"])

        if dramatic_role:
            where_clauses.append("LOWER(c.dramatic_role) = LOWER(?)")
            params.append(dramatic_role)

        if mood:
            where_clauses.append("LOWER(c.mood) = LOWER(?)")
            params.append(mood)

        if min_bpm is not None:
            where_clauses.append("c.tempo_bpm >= ?")
            params.append(min_bpm)
        if max_bpm is not None:
            where_clauses.append("c.tempo_bpm <= ?")
            params.append(max_bpm)

        if min_duration is not None:
            where_clauses.append("c.duration_sec >= ?")
            params.append(min_duration)
        if max_duration is not None:
            where_clauses.append("c.duration_sec <= ?")
            params.append(max_duration)

        if whisper_safe_only:
            where_clauses.append("c.whisper_compatibility >= 0.4 AND c.voice_masking_risk != 'SEVERE'")

        if is_downloaded_only:
            where_clauses.append("c.is_downloaded = 1")

        sql = """
            SELECT c.*,
                   a.integrated_lufs as dsp_lufs,
                   a.true_peak_db as dsp_peak,
                   a.spectral_centroid_hz as dsp_centroid
            FROM sound_catalog c
            LEFT JOIN sound_assets a ON (a.filepath = c.filepath OR a.filename = c.filename)
        """
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        sql += " ORDER BY c.is_downloaded DESC, c.id ASC LIMIT ?"
        params.append(limit * 3)

        with self._get_conn() as conn:
            cur = conn.execute(sql, params)
            candidates = [dict(row) for row in cur.fetchall()]

        # If strict AND FTS yielded nothing, try broad recall fallback
        if not candidates and fts_match and len(meaningful_words) > 1:
            fts_query_or = " OR ".join(f"{w}*" for w in meaningful_words)
            where_clauses[0] = "c.id IN (SELECT rowid FROM sound_catalog_fts WHERE sound_catalog_fts MATCH ?)"
            params[0] = fts_query_or
            sql_fallback = """
                SELECT c.*,
                       a.integrated_lufs as dsp_lufs,
                       a.true_peak_db as dsp_peak,
                       a.spectral_centroid_hz as dsp_centroid
                FROM sound_catalog c
                LEFT JOIN sound_assets a ON (a.filepath = c.filepath OR a.filename = c.filename)
                WHERE """ + " AND ".join(where_clauses) + " ORDER BY c.is_downloaded DESC, c.id ASC LIMIT ?"
            with self._get_conn() as conn:
                cur = conn.execute(sql_fallback, params)
                candidates = [dict(row) for row in cur.fetchall()]

        # Explainable multi-signal scoring
        scored_results = []
        for cand in candidates:
            score = 0.5
            reasons = []

            # Physical semantic alignment
            if exciter and (exciter.lower() in cand.get("exciter", "").lower() or exciter.lower() in cand.get("tags", "").lower()):
                score += 0.25
                reasons.append(f"Physical exciter '{exciter}' matched")
            if resonator and (resonator.lower() in cand.get("resonator", "").lower() or resonator.lower() in cand.get("tags", "").lower()):
                score += 0.20
                reasons.append(f"Resonator acoustic space '{resonator}' matched")
            if action_type and action_type.lower() in cand.get("action_type", "").lower():
                score += 0.20
                reasons.append(f"Physical action '{action_type}' matched")

            # Dramatic alignment
            if mood and cand.get("mood", "").lower() == mood.lower():
                score += 0.15
                reasons.append(f"Dramatic mood '{mood}' matched")
            if dramatic_role and cand.get("dramatic_role", "").lower() == dramatic_role.lower():
                score += 0.15
                reasons.append(f"Dramatic role '{dramatic_role}' matched")

            # Mix safety
            w_comp = float(cand.get("whisper_compatibility") or 0.5)
            if whisper_safe_only:
                score += (w_comp * 0.2)
                reasons.append(f"Whisper compatibility {w_comp:.2f}")

            v_risk = cand.get("voice_masking_risk", "LOW")
            if v_risk == "SEVERE":
                score -= 0.20
                reasons.append("Severe voice masking penalty applied (-0.20)")

            # Local availability bonus
            if cand.get("is_downloaded"):
                score += 0.05
                reasons.append("Locally cached asset (+0.05)")

            cand["retrieval_score"] = round(min(1.0, max(0.0, score)), 2)
            cand["why_matched"] = reasons if reasons else ["General catalog text match"]
            scored_results.append(cand)

        scored_results.sort(key=lambda x: (x["retrieval_score"], x.get("is_downloaded", 0)), reverse=True)
        return scored_results[:limit]

    def format_agent_sound_card(self, candidate_or_id: Any) -> str:
        """
        Formats an explainable Agent Sound Card from a candidate dictionary, asset ID, or AgentSoundCard.
        """
        if hasattr(candidate_or_id, "to_agent_markdown"):
            return candidate_or_id.to_agent_markdown()

        if isinstance(candidate_or_id, int):
            return self.get_agent_sound_card(candidate_or_id)

        cand = candidate_or_id
        aid = cand.get("id", 0)
        fname = cand.get("filename", "")
        title = cand.get("title") or fname
        cat = cand.get("category", "SFX")
        subcat = cand.get("subcategory", "General")
        dur = float(cand.get("duration_sec") or 0.0)
        status = "LOCAL (Cached)" if cand.get("is_downloaded") else "VIRTUAL (JIT Ready)"

        exc = cand.get("exciter") or "unspecified"
        res = cand.get("resonator") or "unspecified"
        act = cand.get("action_type") or "unspecified"
        surf = cand.get("surface") or "unspecified"

        lufs = cand.get("integrated_lufs") or cand.get("dsp_lufs") or -23.0
        peak = cand.get("true_peak_db") or cand.get("dsp_peak") or -1.5
        w_style = cand.get("wave_style") or "general"
        d_role = cand.get("dramatic_role") or "general"
        fg_str = float(cand.get("foreground_strength") or 0.5)

        v_risk = cand.get("voice_masking_risk") or "LOW"
        w_compat = float(cand.get("whisper_compatibility") or 0.5)
        duck_db = -16.0 if v_risk == "SEVERE" else (-12.0 if v_risk == "MODERATE" else -6.0)

        why_matched = cand.get("why_matched") or []
        why_str = ""
        if why_matched:
            why_lines = "\n  - " + "\n  - ".join(why_matched)
            why_str = f"\n- **Why Matched**:{why_lines}"

        card = (
            f"### 🎵 Sound Asset Card: [{cat}] {title} (ID: {aid})\n"
            f"- **File / Source**: `{fname}` | {cand.get('source_collection') or 'SoundBank'} ({cand.get('license', 'Royalty-Free')})\n"
            f"- **Duration**: {dur:.2f}s | **Status**: {status}\n"
            f"- **Sonic Genome**:\n"
            f"  - Exciter: `{exc}` | Resonator: `{res}`\n"
            f"  - Action: `{act}` | Surface: `{surf}`\n"
            f"  - Acoustic: `{w_style}` | LUFS: {lufs:.1f} | True Peak: {peak:.1f} dBTP\n"
            f"  - Dramatic: `{d_role}` | Foreground Strength: {fg_str:.2f}\n"
            f"  - Voice Masking Risk: `{v_risk}` (Whisper Safe: {w_compat:.2f})\n"
            f"- **Mix Recommendation**: Ducking {duck_db:.0f} dB"
            f"{why_str}"
        )
        return card

    def get_agent_sound_card(self, asset_id: int) -> str:
        """
        Formats a compact, high-density Agent Sound Card for any asset in the catalog.
        Allows the AI creative director to reason about sounds without listening to audio.
        """
        with self._get_conn() as conn:
            cur = conn.execute("""
                SELECT c.*,
                       a.integrated_lufs as dsp_lufs,
                       a.true_peak_db as dsp_peak,
                       a.spectral_centroid_hz as dsp_centroid
                FROM sound_catalog c
                LEFT JOIN sound_assets a ON (a.filepath = c.filepath OR a.filename = c.filename)
                WHERE c.id = ?
            """, (asset_id,))
            row = cur.fetchone()
            if not row:
                return f"[Sound Card] Asset ID {asset_id} not found in catalog."
            cand = dict(row)

        aid = cand["id"]
        fname = cand["filename"]
        title = cand.get("title") or fname
        cat = cand.get("category", "SFX")
        subcat = cand.get("subcategory", "General")
        dur = float(cand.get("duration_sec") or 0.0)
        status = "LOCAL (Cached)" if cand.get("is_downloaded") else "VIRTUAL (JIT Ready)"

        exc = cand.get("exciter") or "unspecified"
        res = cand.get("resonator") or "unspecified"
        act = cand.get("action_type") or "unspecified"
        surf = cand.get("surface") or "unspecified"

        lufs = cand.get("dsp_lufs") or -23.0
        peak = cand.get("dsp_peak") or -1.5
        w_style = cand.get("wave_style") or "general"
        d_role = cand.get("dramatic_role") or "general"
        fg_str = float(cand.get("foreground_strength") or 0.5)

        v_risk = cand.get("voice_masking_risk") or "LOW"
        w_compat = float(cand.get("whisper_compatibility") or 0.5)
        duck_db = -16.0 if v_risk == "SEVERE" else (-12.0 if v_risk == "MODERATE" else -6.0)

        card = (
            f"=== AGENT SOUND CARD: [ID: {aid}] {title} ===\n"
            f"TYPE:      {cat} / {subcat} | Status: {status} ({dur:.2f}s)\n"
            f"PHYSICAL:  exciter: {exc} | resonator: {res} | action: {act} | surface: {surf}\n"
            f"ACOUSTIC:  wave_style: {w_style} | LUFS: {lufs:.1f} | Peak: {peak:.1f} dBTP\n"
            f"DRAMATIC:  role: {d_role} | foreground_strength: {fg_str:.2f} | mood: {cand.get('mood', 'default')}\n"
            f"MIX:       voice_masking: {v_risk} | whisper_compat: {w_compat:.2f} | rec_ducking: {duck_db:.0f}dB\n"
            f"BEST USE:  {cand.get('description') or cand.get('tags') or 'dramatic underscore & action'}\n"
            f"AVOID:     {'whispered dialogue' if w_compat < 0.4 else 'dense overlapping dialogue' if v_risk == 'SEVERE' else 'none'}\n"
            f"SOURCE:    {cand.get('source_collection') or 'SoundBank'} ({cand.get('license', 'Royalty-Free')})"
        )
        return card

    def link_assets(self, source_id: int, target_id: int, relationship_type: str, confidence: float = 1.0) -> bool:
        """Creates a directional relationship between two sound assets."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sound_asset_relationships (source_asset_id, target_asset_id, relationship_type, confidence)
                VALUES (?, ?, ?, ?)
            """, (source_id, target_id, relationship_type, confidence))
            return True

    def get_related_assets(self, asset_id: int, relationship_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Finds related assets (e.g. variations, predecessors, successors, companions)."""
        sql = """
            SELECT r.relationship_type, r.confidence, c.*
            FROM sound_asset_relationships r
            JOIN sound_catalog c ON c.id = r.target_asset_id
            WHERE r.source_asset_id = ?
        """
        params = [asset_id]
        if relationship_type:
            sql += " AND r.relationship_type = ?"
            params.append(relationship_type)
        with self._get_conn() as conn:
            cur = conn.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        mood: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Executes sub-millisecond FTS5 search against sound bank (local + virtual).
        First tries high-precision AND matching across terms; falls back to OR matching.
        """
        raw_words = re.findall(r"[a-zA-Z0-9]+", query.strip())
        if not raw_words:
            return []

        # Filter out common audio file extension tokens from search terms if there are other tokens
        meaningful_words = [w for w in raw_words if w.lower() not in ("wav", "mp3", "flac", "ogg", "aiff", "m4a")]
        search_words = meaningful_words if meaningful_words else raw_words

        fts_query_and = " AND ".join(f"{w}*" for w in search_words)
        fts_query_or = " OR ".join(f"{w}*" for w in search_words)

        def _execute_fts(fts_term: str) -> List[Dict[str, Any]]:
            sql = """
                SELECT c.id, c.filename, c.filepath, c.category, c.subcategory, c.mood, c.tags,
                       c.duration_sec, c.size_bytes, c.source_url, c.is_downloaded, rank,
                       a.integrated_lufs, a.true_peak_db, a.spectral_centroid_hz
                FROM sound_catalog_fts f
                JOIN sound_catalog c ON f.rowid = c.id
                LEFT JOIN sound_assets a ON (a.filepath = c.filepath OR a.filename = c.filename)
                WHERE sound_catalog_fts MATCH ?
            """
            params = [fts_term]

            if category:
                cat_norm = category.upper()
                if cat_norm in ("FOLEY", "FOL", "SFX"):
                    sql += " AND c.category IN ('FOL', 'SFX')"
                elif cat_norm in ("MUSIC", "MUS"):
                    sql += " AND c.category IN ('MUS', 'LEITMOTIF', 'CHAPTER_BED', 'DYNAMIC_STEM')"
                elif cat_norm in ("AMBIENCE", "AMB"):
                    sql += " AND c.category IN ('AMB', 'CHAPTER_BED')"
                elif cat_norm in ("STINGER",):
                    sql += " AND c.category IN ('SFX', 'DYNAMIC_STEM', 'MUS')"
                else:
                    sql += " AND c.category = ?"
                    params.append(cat_norm)

            if mood:
                sql += " AND c.mood = ?"
                params.append(mood.lower())

            sql += " ORDER BY c.is_downloaded DESC, rank LIMIT ?"
            params.append(limit)

            with self._get_conn() as conn:
                cur = conn.execute(sql, params)
                return [dict(row) for row in cur.fetchall()]

        # High-precision AND search first
        results = _execute_fts(fts_query_and)
        if not results and len(search_words) > 1:
            # Broad-recall OR fallback
            results = _execute_fts(fts_query_or)

        return results

    def resolve_sound(
        self,
        query: str,
        category: Optional[str] = None,
        prefer_mood: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Resolves the single best matching audio file for a given cue or scene mood
        using pure SQLite FTS5 queries with zero static map fallbacks.
        If the best match is a virtual cloud entry, JIT downloads it on demand.
        Returns absolute Path if found/downloaded, else None.
        """
        # 1. Direct filename or exact path check first
        direct_p = Path(query)
        if direct_p.is_file() and direct_p.exists():
            return direct_p

        q_clean = query.lower().strip()

        # Helper to test candidate path existence and virtual download
        def _check_cand(cand: Dict[str, Any]) -> Optional[Path]:
            raw_fp = cand.get("filepath") or ""
            if raw_fp:
                cand_path = Path(raw_fp)
                if cand_path.is_file() and cand_path.exists():
                    return cand_path

            # Also check relative to bank_root if relative path or moved
            if cand.get("filename"):
                rel_p = self.bank_root / cand["filename"]
                if rel_p.is_file() and rel_p.exists():
                    return rel_p
                # Check category subdirectories
                cat = cand.get("category", "")
                if cat:
                    cat_p = self.bank_root / cat.lower() / cand["filename"]
                    if cat_p.is_file() and cat_p.exists():
                        return cat_p

            # Virtual entry with remote source_url -> JIT download
            if cand.get("source_url") or cand.get("mirror_url"):
                downloaded = self.download_virtual_asset(
                    sound_id=cand["id"],
                    source_url=cand.get("source_url"),
                    filename=cand.get("filename"),
                    category=cand.get("category", "SFX") or "SFX",
                    mirror_url=cand.get("mirror_url"),
                )
                if downloaded and downloaded.exists():
                    return downloaded
            return None

        # 2. Try exact category & mood match (limit 20 to prevent ghost depletion)
        results = self.search(q_clean, category=category, mood=prefer_mood, limit=20)
        for cand in results:
            resolved = _check_cand(cand)
            if resolved:
                return resolved

        # 3. Relax mood filter if not found
        if prefer_mood:
            results = self.search(q_clean, category=category, limit=20)
            for cand in results:
                resolved = _check_cand(cand)
                if resolved:
                    return resolved

        # 4. If still not found and category was provided, try broad category search
        if category:
            cat_aliases = {
                "FOL": ["foley", "SFX"],
                "foley": ["FOL", "SFX"],
                "AMB": ["ambience", "CHAPTER_BED"],
                "ambience": ["AMB", "CHAPTER_BED"],
                "MUS": ["music", "DYNAMIC_STEM", "CHAPTER_BED"],
                "music": ["MUS", "DYNAMIC_STEM", "CHAPTER_BED"],
            }
            for alt_cat in cat_aliases.get(category, []):
                results = self.search(q_clean, category=alt_cat, limit=10)
                for cand in results:
                    resolved = _check_cand(cand)
                    if resolved:
                        return resolved

        # 5. Broad search without category constraint
        results = self.search(q_clean, limit=20)
        for cand in results:
            resolved = _check_cand(cand)
            if resolved:
                return resolved

        return None

    def resolve_leitmotif(self, theme_name: str) -> Optional[Path]:
        """Resolve Level 1 recurring character or world leitmotif track via pure FTS5."""
        res = self.resolve_sound(theme_name, category="LEITMOTIF")
        if not res:
            res = self.resolve_sound(theme_name, category="MUS")
        return res

    def resolve_chapter_bed(self, bed_name: str, prefer_mood: Optional[str] = None) -> Optional[Path]:
        """Resolve Level 2 continuous setting atmosphere bed via pure FTS5."""
        res = self.resolve_sound(bed_name, category="CHAPTER_BED", prefer_mood=prefer_mood)
        if not res:
            res = self.resolve_sound(bed_name, category="AMB", prefer_mood=prefer_mood)
        if not res:
            res = self.resolve_sound(bed_name, category="MUS", prefer_mood=prefer_mood)
        return res

    def resolve_dynamic_stem(self, stem_name: str, intensity: Optional[str] = None) -> Optional[Path]:
        """Resolve Level 3 dynamic scene intensity stem via pure FTS5."""
        res = self.resolve_sound(stem_name, category="DYNAMIC_STEM")
        if not res:
            res = self.resolve_sound(stem_name, category="MUS")
        return res

    def resolve_stinger(self, stinger_cue: str) -> Optional[Path]:
        """Resolve Level 3 micro dramatic action/revelation stinger hit via pure FTS5."""
        res = self.resolve_sound(stinger_cue, category="STINGER")
        if not res:
            res = self.resolve_sound(stinger_cue, category="SFX")
        return res

    def resolve_track_section(
        self,
        query: str,
        section_type: str = "INTRO_BED",
        min_energy: int = 1,
        max_energy: int = 10,
    ) -> Optional[Dict[str, Any]]:
        """
        Resolves an exact acoustic energy section within a soundtrack track.
        Guarantees original source track file remains untouched on disk.
        Returns:
            Dict containing track metadata, section name, start/end timestamps, and energy level.
        """
        sec_name = section_type.upper().strip()
        # 1. Resolve candidate track file (direct track/cue match first, then specialized resolvers)
        cand = (
            self.resolve_sound(query)
            or self.resolve_dynamic_stem(query)
            or self.resolve_leitmotif(query)
            or self.resolve_chapter_bed(query)
        )

        with self._get_conn() as conn:
            row = None
            if cand and cand.exists():
                cand_resolved_fwd = str(cand.resolve()).replace("\\", "/")
                cand_resolved_win = str(cand.resolve()).replace("/", "\\")
                # Try exact section_name and energy range on resolved track
                row = conn.execute("""
                    SELECT s.*, c.filename, c.filepath, c.duration_sec
                    FROM sound_track_sections s
                    JOIN sound_catalog c ON s.track_id = c.id
                    WHERE (c.filepath = ? OR c.filepath = ? OR c.filename = ?)
                      AND s.section_name = ?
                      AND s.energy_level BETWEEN ? AND ?
                    ORDER BY s.energy_level DESC
                    LIMIT 1
                """, (cand_resolved_fwd, cand_resolved_win, cand.name, sec_name, min_energy, max_energy)).fetchone()

                if not row:
                    # Relax energy filter
                    row = conn.execute("""
                        SELECT s.*, c.filename, c.filepath, c.duration_sec
                        FROM sound_track_sections s
                        JOIN sound_catalog c ON s.track_id = c.id
                        WHERE (c.filepath = ? OR c.filepath = ? OR c.filename = ?)
                          AND s.section_name = ?
                        LIMIT 1
                    """, (cand_resolved_fwd, cand_resolved_win, cand.name, sec_name)).fetchone()

                if not row:
                    # Fallback to any section of that track
                    row = conn.execute("""
                        SELECT s.*, c.filename, c.filepath, c.duration_sec
                        FROM sound_track_sections s
                        JOIN sound_catalog c ON s.track_id = c.id
                        WHERE (c.filepath = ? OR c.filepath = ? OR c.filename = ?)
                        LIMIT 1
                    """, (cand_resolved_fwd, cand_resolved_win, cand.name)).fetchone()

            if not row:
                # 2. Try searching by section_name / tags in catalog if track wasn't directly resolved
                q_clean = query.lower().strip()
                row = conn.execute("""
                    SELECT s.*, c.filename, c.filepath, c.duration_sec
                    FROM sound_track_sections s
                    JOIN sound_catalog c ON s.track_id = c.id
                    WHERE s.section_name = ?
                      AND (s.tags LIKE ? OR c.tags LIKE ? OR c.filename LIKE ?)
                      AND s.energy_level BETWEEN ? AND ?
                    ORDER BY RANDOM()
                    LIMIT 1
                """, (sec_name, f"%{q_clean}%", f"%{q_clean}%", f"%{q_clean}%", min_energy, max_energy)).fetchone()

            if row:
                return {
                    "track_id": row["track_id"],
                    "track_name": row["filename"],
                    "track_path": Path(row["filepath"]),
                    "section_name": row["section_name"],
                    "start_sec": float(row["start_sec"]),
                    "end_sec": float(row["end_sec"]),
                    "duration": round(float(row["end_sec"]) - float(row["start_sec"]), 2),
                    "energy_level": int(row["energy_level"]),
                    "tags": row["tags"] or "",
                }

            # Dynamic fallback if audio file exists on disk but wasn't indexed in sections
            if cand and cand.exists():
                dur = self._extract_duration(cand)
                return {
                    "track_id": 0,
                    "track_name": cand.name,
                    "track_path": cand,
                    "section_name": sec_name,
                    "start_sec": 0.0,
                    "end_sec": dur,
                    "duration": round(dur, 2),
                    "energy_level": 5,
                    "tags": "dynamic_fallback",
                }

        return None

    @staticmethod
    def slice_track_section(
        track_path: Path,
        start_sec: float,
        target_duration: float,
        output_file: Path,
        fade_in_sec: float = 2.0,
        fade_out_sec: float = 2.0,
    ) -> Path:
        """
        Non-destructively carves a precise sub-slice from a source audio track.
        Guarantees source track is NEVER modified, deleted, or overwritten.
        Applies smooth micro-fades and 48kHz broadcast resampling.
        """
        track_path = Path(track_path).resolve()
        output_file = Path(output_file).resolve()
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if os.path.normcase(str(track_path.resolve())) == os.path.normcase(str(output_file.resolve())):
            raise ValueError(f"Safety Violation: Cannot overwrite original source track file: {track_path}")

        if not track_path.exists():
            raise FileNotFoundError(f"Source soundtrack file not found: {track_path}")

        ffmpeg = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
        target_dur = max(float(target_duration), 1.0)
        s_start = max(0.0, float(start_sec))

        fade_in = min(float(fade_in_sec), target_dur / 3.0)
        fade_out = min(float(fade_out_sec), target_dur / 3.0)
        fade_out_start = max(0.0, target_dur - fade_out)

        af_expr = f"afade=t=in:ss=0:d={fade_in:.2f},afade=t=out:st={fade_out_start:.2f}:d={fade_out:.2f},aresample=osr=48000"

        track_dur = SoundBank._extract_duration(track_path)
        available_slice = max(0.1, track_dur - s_start) if track_dur > 0 else target_dur

        if target_dur <= available_slice:
            # Sliced section is sufficiently long; no looping required
            cmd = [
                ffmpeg, "-y",
                "-ss", f"{s_start:.2f}",
                "-i", str(track_path),
                "-t", f"{target_dur:.2f}",
                "-af", af_expr,
                "-c:a", "pcm_s16le",
                str(output_file)
            ]
        else:
            # Sliced section requires looping; use aloop filter to loop only from s_start onward
            af_loop = (
                f"asetpts=PTS-STARTPTS,aloop=loop=-1:size=2e+09,atrim=0:{target_dur:.2f},"
                f"afade=t=in:ss=0:d={fade_in:.2f},afade=t=out:st={fade_out_start:.2f}:d={fade_out:.2f},"
                f"aresample=osr=48000"
            )
            cmd = [
                ffmpeg, "-y",
                "-ss", f"{s_start:.2f}",
                "-i", str(track_path),
                "-af", af_loop,
                "-c:a", "pcm_s16le",
                str(output_file)
            ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg slice failed for {track_path.name}: {res.stderr[:200]}")

        return output_file

    def preload_cues(self, cues: List[str], max_workers: int = 4) -> List[Path]:
        """
        Pre-downloads all virtual sound assets needed for a list of cues in parallel.
        Useful to run during TTS speech synthesis so all sound assets are hot in cache.
        """
        unique_cues = list(dict.fromkeys(c for c in cues if c))
        resolved_paths: List[Path] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_cue = {executor.submit(self.resolve_sound, cue): cue for cue in unique_cues}
            for future in future_to_cue:
                try:
                    p = future.result()
                    if p and p.exists():
                        resolved_paths.append(p)
                except Exception:
                    pass

        return resolved_paths

    def search_music_catalog(
        self,
        query: str,
        section_type: Optional[str] = None,
        max_energy: Optional[int] = None,
        target_valence: Optional[float] = None,
        target_arousal: Optional[float] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Dynamically searches the full music soundtrack catalog and energy sections.
        Returns candidate tracks with energy levels, start/end seconds, tags, and Sonic Genome.
        Zero hardcoded track lists, 100% dynamic FTS5 search across all 230 tracks.
        """
        raw_words = re.findall(r"[a-zA-Z0-9]+", query.strip())
        if not raw_words:
            return []
        fts_query = " OR ".join(f"{w}*" for w in raw_words)

        sql = """
            SELECT c.id, c.filename, c.filepath, c.mood, c.tags, c.duration_sec, c.sonic_genome,
                   c.genome_valence, c.genome_arousal,
                   s.id as section_id, s.section_name, s.start_sec, s.end_sec, s.energy_level, s.tempo_bpm, s.tags as section_tags,
                   rank
            FROM sound_catalog_fts f
            JOIN sound_catalog c ON f.rowid = c.id
            LEFT JOIN sound_track_sections s ON s.track_id = c.id
            WHERE sound_catalog_fts MATCH ?
              AND c.category IN ('MUS', 'CHAPTER_BED', 'LEITMOTIF', 'DYNAMIC_STEM')
        """
        params: List[Any] = [fts_query]

        if section_type and section_type != "ANY":
            sql += " AND s.section_name = ?"
            params.append(section_type)

        if max_energy is not None:
            sql += " AND (s.energy_level IS NULL OR s.energy_level <= ?)"
            params.append(max_energy)

        if target_valence is not None:
            sql += " AND (c.genome_valence IS NULL OR abs(c.genome_valence - ?) <= 0.45)"
            params.append(target_valence)

        if target_arousal is not None:
            sql += " AND (c.genome_arousal IS NULL OR abs(c.genome_arousal - ?) <= 0.45)"
            params.append(target_arousal)

        sql += " GROUP BY c.id ORDER BY rank LIMIT ?"
        params.append(limit)

        with self._get_conn() as conn:
            cur = conn.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def resolve_asset_path(self, identifier: Union[str, int]) -> Path:
        """
        Deterministic asset resolver. Resolves an exact ID or filename/filepath.
        Raises FileNotFoundError if the file cannot be located on disk.
        ZERO heuristics, ZERO fallbacks to default tracks.
        """
        # 1. If integer ID
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            with self._get_conn() as conn:
                row = conn.execute("SELECT filepath FROM sound_catalog WHERE id = ?", (int(identifier),)).fetchone()
                if row and row["filepath"]:
                    p = Path(row["filepath"])
                    if p.exists():
                        return p
            raise FileNotFoundError(f"Sound bank asset ID {identifier} not found on disk.")

        # 2. If direct path
        p = Path(identifier)
        if p.is_file() and p.exists():
            return p

        # 3. Check relative to sound bank root
        p_root = self.bank_root / identifier
        if p_root.is_file() and p_root.exists():
            return p_root

        # 4. Try exact filename lookup in catalog
        with self._get_conn() as conn:
            row = conn.execute("SELECT filepath FROM sound_catalog WHERE filename = ?", (p.name,)).fetchone()
            if row and row["filepath"]:
                fp = Path(row["filepath"])
                if fp.exists():
                    return fp

        # 5. If not an explicit file reference with extension, try resolve_sound
        if not p.suffix and "/" not in str(identifier) and "\\" not in str(identifier):
            found = self.resolve_sound(str(identifier))
            if found and found.exists():
                return found

        raise FileNotFoundError(f"Sound asset '{identifier}' could not be resolved in sound bank.")

    def get_asset_metrics(self, identifier: Union[str, int, Path]) -> Optional[Dict[str, Any]]:
        """
        Retrieves EBU R128 LUFS, True Peak, and Spectral Centroid metrics
        from the harmonized sound_assets table.
        """
        resolved_p: Optional[Path] = None
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            with self._get_conn() as conn:
                row = conn.execute("SELECT filepath FROM sound_catalog WHERE id = ?", (int(identifier),)).fetchone()
                if row and row["filepath"]:
                    resolved_p = Path(row["filepath"])
        elif isinstance(identifier, (str, Path)):
            p = Path(identifier)
            if p.exists():
                resolved_p = p
            else:
                resolved_p = self.resolve_sound(str(identifier))

        with self._get_conn() as conn:
            table_check = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='sound_assets'"
            ).fetchone()[0]
            if not table_check:
                return None

            row = None
            if resolved_p:
                norm_fwd = str(resolved_p.resolve()).replace("\\", "/")
                norm_win = str(resolved_p.resolve()).replace("/", "\\")
                row = conn.execute("""
                    SELECT * FROM sound_assets
                    WHERE filepath = ? OR filepath = ? OR filename = ?
                    LIMIT 1
                """, (norm_fwd, norm_win, resolved_p.name)).fetchone()

            if not row and isinstance(identifier, (str, int)):
                row = conn.execute("""
                    SELECT * FROM sound_assets WHERE id = ? OR filename = ? LIMIT 1
                """, (identifier, str(identifier))).fetchone()

            if row:
                return {
                    "id": row["id"],
                    "filename": row["filename"],
                    "filepath": row["filepath"],
                    "category": row["category"],
                    "action_type": row["action_type"],
                    "integrated_lufs": float(row["integrated_lufs"]) if row["integrated_lufs"] is not None else -23.0,
                    "true_peak_db": float(row["true_peak_db"]) if row["true_peak_db"] is not None else -1.5,
                    "spectral_centroid_hz": float(row["spectral_centroid_hz"]) if row["spectral_centroid_hz"] is not None else 0.0,
                    "sample_rate": int(row["sample_rate"]) if row["sample_rate"] is not None else 48000,
                    "channels": int(row["channels"]) if row["channels"] is not None else 2,
                    "duration_sec": float(row["duration_sec"]) if row["duration_sec"] is not None else 0.0,
                }
        return None

    def stats(self) -> Dict[str, Any]:
        """Returns storage and catalog statistics for the local sound bank."""
        with self._get_conn() as conn:
            total_sounds = conn.execute("SELECT COUNT(*) FROM sound_catalog").fetchone()[0]
            total_dur = conn.execute("SELECT COALESCE(SUM(duration_sec), 0.0) FROM sound_catalog").fetchone()[0]
            total_bytes = conn.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM sound_catalog").fetchone()[0]

            total_sections = 0
            has_sections_table = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='sound_track_sections'").fetchone()[0]
            if has_sections_table:
                total_sections = conn.execute("SELECT COUNT(*) FROM sound_track_sections").fetchone()[0]

            cat_counts = {}
            for r in conn.execute("SELECT category, COUNT(*) as cnt FROM sound_catalog GROUP BY category"):
                cat_counts[r["category"] or "OTHER"] = r["cnt"]

            mood_counts = {}
            for r in conn.execute("SELECT mood, COUNT(*) as cnt FROM sound_catalog GROUP BY mood"):
                mood_counts[r["mood"] or "default"] = r["cnt"]

        return {
            "total_sounds": total_sounds,
            "total_sections": total_sections,
            "total_duration_min": round(total_dur / 60.0, 1),
            "total_size_mb": round(total_bytes / (1024 * 1024), 2),
            "categories": cat_counts,
            "moods": mood_counts,
            "database_path": str(self.db_path),
        }

    # -------------------------------------------------------------------------
    # Sonic Intelligence Domain Service Interface (Phase 1)
    # -------------------------------------------------------------------------

    def analyze_local_audio(self, filepath: Union[Path, str]) -> Tuple[MeasuredAudioFacts, List[AudioEventRecord]]:
        """
        Runs deterministic audio analysis on a local audio file.
        Returns measured physical facts and detected audio events with full provenance.
        """
        return self.audio_analyzer.analyze_file(Path(filepath).resolve())

    def enrich_asset(self, sound_id: int, force: bool = False) -> SonicGenome:
        """
        Enriches an asset in sound_catalog with deterministic audio analysis.
        Extracts format, EBU R128 loudness, spectral features, temporal boundaries,
        and conservative tonal facts.
        Idempotent: updates existing columns, preserves previous epistemic layers,
        logs to sound_analysis_runs, and updates sound_temporal_events.
        """
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM sound_catalog WHERE id = ?", (sound_id,)).fetchone()
            if not row:
                raise ValueError(f"Sound asset ID {sound_id} not found in sound_catalog.")

        row_dict = dict(row)
        filepath_str = row_dict.get("filepath")
        local_path = Path(filepath_str).resolve() if filepath_str else None

        # Check existing sonic_genome
        raw_genome_str = row_dict.get("sonic_genome") or "{}"
        try:
            genome_dict = json.loads(raw_genome_str) if isinstance(raw_genome_str, str) else raw_genome_str
            if not isinstance(genome_dict, dict):
                genome_dict = {}
        except Exception:
            genome_dict = {}

        # If not force and already analyzed with current version, return current genome
        current_version = row_dict.get("analysis_version") or ""
        if not force and current_version == ANALYZER_VERSION and row_dict.get("last_analyzed_at"):
            try:
                genome_dict["track_id"] = sound_id
                genome_dict["filename"] = row_dict.get("filename", "")
                return SonicGenome.model_validate(genome_dict)
            except Exception:
                pass

        # If local file does not exist (virtual), return SonicGenome without measured DSP facts
        if not local_path or not local_path.exists() or local_path.stat().st_size == 0:
            genome_dict["track_id"] = sound_id
            genome_dict["filename"] = row_dict.get("filename", "")
            genome_dict["version"] = "2.1"
            return SonicGenome.model_validate(genome_dict)

        # Run deterministic DSP analysis on local audio file
        facts, events = self.audio_analyzer.analyze_file(local_path)

        # Load or create SonicGenome
        try:
            genome = SonicGenome.model_validate(genome_dict)
            genome.version = "2.1"
        except Exception:
            genome = SonicGenome(
                version="2.1",
                track_id=sound_id,
                filename=row_dict.get("filename", local_path.name),
            )

        genome.track_id = sound_id
        genome.filename = row_dict.get("filename", local_path.name)
        genome.measured_facts = facts
        genome.events = events
        genome.sync_measured_to_acoustic()

        # Append to provenance ledger
        genome.provenance_ledger.append(facts.provenance)
        genome.provenance_log.append({
            "source_method": facts.provenance.source_method,
            "analyzer_id": facts.provenance.analyzer_id,
            "analyzer_version": facts.provenance.analyzer_version,
            "timestamp": facts.provenance.generated_at,
            "confidence": None,
        })

        # Update source metadata in genome if present in row
        if row_dict.get("source_collection") or row_dict.get("source_url"):
            genome.source_metadata.provider_name = row_dict.get("source_collection") or "local"
            genome.source_metadata.normalized.title = row_dict.get("title") or ""
            genome.source_metadata.normalized.description = row_dict.get("description") or ""
            genome.source_metadata.normalized.category = row_dict.get("category") or "SFX"
            genome.source_metadata.normalized.subcategory = row_dict.get("subcategory") or "General"
            genome.source_metadata.normalized.mood = row_dict.get("mood") or "default"
            genome.source_metadata.normalized.source_url = row_dict.get("source_url")
            genome.source_metadata.normalized.license = row_dict.get("license") or "Royalty-Free"

        # Update inferred taxonomy in genome
        genome.inferred.category = row_dict.get("category") or "SFX"
        genome.inferred.action_type = row_dict.get("action_type") or ""
        genome.inferred.exciter = row_dict.get("exciter") or ""
        genome.inferred.resonator = row_dict.get("resonator") or ""

        genome_json = genome.model_dump_json()

        # Database transaction: update sound_catalog, record run, record temporal events
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE sound_catalog
                SET size_bytes = ?, duration_sec = ?, format = ?,
                    sample_rate = ?, channels = ?, bit_depth = ?,
                    integrated_lufs = ?, true_peak_db = ?, loudness_range_lu = ?, rms_level_db = ?,
                    spectral_centroid_hz = ?, spectral_bandwidth_hz = ?, spectral_rolloff_hz = ?,
                    spectral_flatness = ?, zero_crossing_rate = ?, silence_ratio = ?,
                    analysis_version = ?, last_analyzed_at = CURRENT_TIMESTAMP,
                    sonic_genome = ?
                WHERE id = ?
            """, (
                facts.format.file_size_bytes,
                facts.format.duration_sec,
                facts.format.container,
                facts.format.sample_rate,
                facts.format.channels,
                facts.format.bit_depth,
                facts.loudness.integrated_lufs,
                facts.loudness.true_peak_dbtp,
                facts.loudness.loudness_range_lu,
                facts.loudness.rms_level_db,
                facts.spectral.spectral_centroid_hz,
                facts.spectral.spectral_bandwidth_hz,
                facts.spectral.spectral_rolloff_hz,
                facts.spectral.spectral_flatness,
                facts.spectral.zero_crossing_rate,
                facts.temporal.silence_ratio,
                ANALYZER_VERSION,
                genome_json,
                sound_id,
            ))

            # Idempotent analysis run logging
            conn.execute("""
                INSERT INTO sound_analysis_runs (
                    track_id, analyzer_id, analyzer_version, analysis_stage,
                    execution_status, error_message, measured_facts, provenance_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sound_id,
                ANALYZER_ID,
                ANALYZER_VERSION,
                "MEASURED_AUDIO_FACTS",
                "SUCCESS",
                None,
                facts.model_dump_json(),
                facts.provenance.model_dump_json(),
            ))

            # Clean and re-insert temporal events for this track and detector
            conn.execute("""
                DELETE FROM sound_temporal_events
                WHERE track_id = ? AND detector_id IN ('frame_energy_gate_v1', 'energy_flux_detector_v1')
            """, (sound_id,))

            for ev in events:
                conn.execute("""
                    INSERT INTO sound_temporal_events (
                        track_id, event_type, start_sec, end_sec, confidence,
                        source_method, detector_id, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sound_id,
                    ev.event_type,
                    ev.start_sec,
                    ev.end_sec,
                    ev.confidence,
                    ev.source_method,
                    ev.detector_id,
                    json.dumps(ev.metadata),
                ))

        return genome

    def get_sonic_genome(self, sound_id: int) -> Optional[SonicGenome]:
        """
        Retrieves the typed SonicGenome v2.1 for a sound catalog record.
        """
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM sound_catalog WHERE id = ?", (sound_id,)).fetchone()
            if not row:
                return None
            row_dict = dict(row)

        g_str = row_dict.get("sonic_genome") or "{}"
        try:
            g_dict = json.loads(g_str) if isinstance(g_str, str) else g_str
            if not isinstance(g_dict, dict):
                g_dict = {}
        except Exception:
            g_dict = {}

        g_dict["track_id"] = sound_id
        g_dict["filename"] = row_dict.get("filename", "")
        if "version" not in g_dict:
            g_dict["version"] = "2.1"

        try:
            return SonicGenome.model_validate(g_dict)
        except Exception as e:
            logger.debug(f"Failed to parse SonicGenome for track {sound_id}: {e}")
            return SonicGenome(track_id=sound_id, filename=row_dict.get("filename", ""))

    def get_asset_provenance(self, sound_id: int) -> List[Dict[str, Any]]:
        """
        Retrieves complete audit-trail provenance records for an asset across all analysis runs.
        """
        records: List[Dict[str, Any]] = []
        with self._get_conn() as conn:
            cur = conn.execute("""
                SELECT id, track_id, analyzer_id, analyzer_version, analysis_stage,
                       execution_status, error_message, provenance_data, created_at
                FROM sound_analysis_runs
                WHERE track_id = ?
                ORDER BY created_at DESC
            """, (sound_id,))
            for r in cur.fetchall():
                row_d = dict(r)
                if row_d.get("provenance_data"):
                    try:
                        row_d["provenance_data"] = json.loads(row_d["provenance_data"])
                    except Exception:
                        pass
                records.append(row_d)
        return records

    def rerun_analysis(self, sound_id: int, force: bool = True) -> SonicGenome:
        """Safely recomputes deterministic audio analysis without duplicating records."""
        return self.enrich_asset(sound_id=sound_id, force=force)

    def ingest_source_metadata(self, item: Dict[str, Any], source_name: str) -> int:
        """
        Ingests source metadata for an asset into sound_catalog, preserving raw fields
        and recording the run in sound_analysis_runs.
        """
        fname = item.get("filename")
        if not fname:
            raise ValueError("Item must contain a 'filename'")

        title = item.get("title", "")
        desc = item.get("description", "")
        cat = item.get("category", "SFX")
        subcat = item.get("subcategory", "General")
        mood = item.get("mood", "default")
        tags = item.get("tags", "")
        dur = float(item.get("duration_sec") or 0.0)
        source_url = item.get("source_url")
        mirror_url = item.get("mirror_url")
        source_page = item.get("source_page_url")
        license_str = item.get("license", "Royalty-Free")
        creator = item.get("creator_attribution", "")
        tempo = float(item.get("tempo_bpm") or 0.0)

        # Build SourceMetadata
        src_meta = SourceMetadata(
            provider_name=source_name,
            raw_metadata=item.get("raw_metadata") or item,
            normalized=NormalizedSourceFields(
                title=title,
                description=desc,
                tags=tags.split() if isinstance(tags, str) else list(tags),
                category=cat,
                subcategory=subcat,
                creator=creator,
                collection=source_name,
                mood=mood,
                tempo_bpm=tempo if tempo > 0 else None,
                duration_sec=dur,
                source_url=source_url,
                license=license_str,
                provider_id=str(item.get("id") or item.get("isrc") or fname),
            ),
            provenance=ProvenanceRecord(
                source_method="source_metadata",
                analyzer_id=f"{source_name.lower()}_adapter",
                analyzer_version="1.0.0",
                confidence=None,
            )
        )

        genome = SonicGenome(
            version="2.1",
            filename=fname,
            source_metadata=src_meta,
        )
        genome.provenance_ledger.append(src_meta.provenance)
        genome_json = genome.model_dump_json()

        with self._get_conn() as conn:
            cur = conn.execute("""
                INSERT INTO sound_catalog (
                    filename, filepath, title, description, category, subcategory,
                    mood, tags, duration_sec, source_collection, license, creator_attribution,
                    source_url, mirror_url, source_page_url, url_status, is_downloaded,
                    tempo_bpm, sonic_genome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unverified', 0, ?, ?)
                RETURNING id;
            """, (
                fname, f"virtual/{source_name.lower()}/{fname}", title, desc, cat, subcat,
                mood, tags, dur, source_name, license_str, creator,
                source_url, mirror_url, source_page, tempo, genome_json
            ))
            track_id = cur.fetchone()[0]

            # Log source ingestion run
            conn.execute("""
                INSERT INTO sound_analysis_runs (
                    track_id, analyzer_id, analyzer_version, analysis_stage,
                    execution_status, measured_facts, provenance_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                track_id,
                f"{source_name.lower()}_adapter",
                "1.0.0",
                "SOURCE_METADATA",
                "SUCCESS",
                "{}",
                src_meta.provenance.model_dump_json(),
            ))

        return track_id

    def enrich_asset_phase2(
        self,
        sound_id: int,
        force: bool = False,
        run_classifier: bool = True,
        run_clap: bool = True,
    ) -> Optional[SonicGenome]:
        """
        Phase 2 AI Enrichment: Runs dedicated audio classifiers (AST AudioSet 527)
        and CLAP semantic embeddings (512-d).
        Preserves raw model evidence, isolates errors, and maintains idempotency.
        """
        import numpy as np

        # 1. Fetch catalog record
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM sound_catalog WHERE id = ?", (sound_id,)).fetchone()
            if not row:
                raise ValueError(f"Sound track ID {sound_id} not found in sound_catalog")
            row_dict = dict(row)

        # 2. Check idempotency unless force=True
        if not force:
            with self._get_conn() as conn:
                existing_run = conn.execute("""
                    SELECT execution_status FROM sound_analysis_runs
                    WHERE track_id = ? AND analysis_stage = 'PHASE2_AI_ENRICHMENT' AND execution_status = 'SUCCESS'
                """, (sound_id,)).fetchone()
                if existing_run:
                    return self.get_sonic_genome(sound_id)

        # 3. Resolve audio file path (downloading JIT if virtual)
        file_path_str = row_dict.get("filepath")
        resolved_path: Optional[Path] = None
        if file_path_str:
            p = Path(file_path_str)
            if p.exists() and p.stat().st_size > 0:
                resolved_path = p

        if resolved_path is None and row_dict.get("source_url"):
            resolved_path = self.download_virtual_asset(sound_id)

        if resolved_path is None or not resolved_path.exists():
            error_msg = f"Audio file not accessible on disk for track {sound_id} ({file_path_str})"
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO sound_analysis_runs (
                        track_id, analyzer_id, analyzer_version, analysis_stage,
                        execution_status, error_message, measured_facts, provenance_data
                    ) VALUES (?, 'phase2_orchestrator', '1.0.0', 'PHASE2_AI_ENRICHMENT', 'FAILED', ?, '{}', '{}')
                """, (sound_id, error_msg))
            raise FileNotFoundError(error_msg)

        # 4. Load audio waveform
        import soundfile as sf
        waveform = None
        sr = 48000
        duration_sec = 0.0

        try:
            waveform, sr = sf.read(str(resolved_path), dtype="float32", always_2d=False)
            if waveform.ndim > 1:
                waveform = np.mean(waveform, axis=0 if waveform.shape[0] < waveform.shape[1] else 1)
            duration_sec = float(len(waveform) / sr)
        except Exception:
            try:
                import librosa
                waveform, sr = librosa.load(str(resolved_path), sr=None, mono=True)
                duration_sec = float(len(waveform) / sr)
            except Exception:
                # Robust fallback via ffmpeg raw PCM pipe
                ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
                try:
                    cmd = [
                        ffmpeg, "-v", "error", "-i", str(resolved_path),
                        "-f", "f32le", "-ac", "1", "-ar", "48000", "-"
                    ]
                    res = subprocess.run(cmd, capture_output=True, timeout=25.0)
                    if res.returncode == 0 and res.stdout:
                        waveform = np.frombuffer(res.stdout, dtype=np.float32)
                        sr = 48000
                        duration_sec = float(len(waveform) / sr)
                    else:
                        raise RuntimeError(res.stderr.decode("utf-8", errors="ignore"))
                except Exception as e3:
                    error_msg = f"Failed to decode audio for track {sound_id}: {e3}"
                    with self._get_conn() as conn:
                        conn.execute("""
                            INSERT INTO sound_analysis_runs (
                                track_id, analyzer_id, analyzer_version, analysis_stage,
                                execution_status, error_message, measured_facts, provenance_data
                            ) VALUES (?, 'phase2_orchestrator', '1.0.0', 'PHASE2_AI_ENRICHMENT', 'FAILED', ?, '{}', '{}')
                        """, (sound_id, error_msg))
                    raise RuntimeError(error_msg)

        # 5. Execute Classifier (with error isolation)
        from audiobook_factory.audio_classifier_adapters import ASTClassifierAdapter
        from audiobook_factory.clap_semantic_adapter import CLAPSemanticAdapter

        classifier_inferences: Optional[ClassifierInferences] = None
        temporal_events: List[AudioEventRecord] = []
        classifier_err: Optional[str] = None

        if run_classifier:
            try:
                adapter = ASTClassifierAdapter()
                classifier_inferences = adapter.classify(waveform, sr, duration_sec)
                temporal_events = adapter.detect_temporal_events(waveform, sr, duration_sec)
            except Exception as e:
                logger.warning(f"Phase 2 Classifier encountered error for track {sound_id}: {e}")
                classifier_err = str(e)

        # 6. Execute CLAP Semantic Adapter (with error isolation)
        clap_vector: Optional[np.ndarray] = None
        clap_facts: Optional[SemanticEmbeddingFacts] = None
        clap_err: Optional[str] = None

        if run_clap:
            try:
                clap_adapter = CLAPSemanticAdapter()
                clap_vector, clap_facts = clap_adapter.embed_audio(waveform, sr, duration_sec)
            except Exception as e:
                logger.warning(f"Phase 2 CLAP embedding encountered error for track {sound_id}: {e}")
                clap_err = str(e)

        # 7. Determine overall execution status
        if classifier_err and clap_err:
            overall_status = "FAILED"
            error_message = f"Classifier: {classifier_err} | CLAP: {clap_err}"
        elif classifier_err or clap_err:
            overall_status = "PARTIAL"
            error_message = f"Classifier: {classifier_err}" if classifier_err else f"CLAP: {clap_err}"
        else:
            overall_status = "SUCCESS"
            error_message = None

        # 8. Update database inside transaction
        genome = self.get_sonic_genome(sound_id) or SonicGenome(track_id=sound_id, filename=row_dict.get("filename", ""))
        genome.record_ai_inference(
            classifier=classifier_inferences,
            semantic=clap_facts,
            events=temporal_events,
        )
        genome_json = genome.model_dump_json()

        with self._get_conn() as conn:
            conn.execute("UPDATE sound_catalog SET sonic_genome = ? WHERE id = ?", (genome_json, sound_id))

            if classifier_inferences:
                conn.execute("DELETE FROM sound_classifier_tags WHERE track_id = ?", (sound_id,))
                for pred in classifier_inferences.predictions:
                    conn.execute("""
                        INSERT INTO sound_classifier_tags (
                            track_id, model_id, model_version, ontology_id,
                            raw_label, normalized_label, raw_score, calibrated_score,
                            rank, start_sec, end_sec, source_method
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sound_id,
                        classifier_inferences.model_id,
                        classifier_inferences.model_version,
                        classifier_inferences.ontology_id,
                        pred.raw_label,
                        pred.normalized_label,
                        pred.raw_score,
                        pred.calibrated_score,
                        pred.rank,
                        pred.start_sec,
                        pred.end_sec,
                        "classifier",
                    ))

                conn.execute("""
                    DELETE FROM sound_temporal_events
                    WHERE track_id = ? AND source_method = 'classifier'
                """, (sound_id,))
                for ev in temporal_events:
                    conn.execute("""
                        INSERT INTO sound_temporal_events (
                            track_id, event_type, start_sec, end_sec,
                            confidence, source_method, detector_id, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sound_id,
                        ev.event_type,
                        ev.start_sec,
                        ev.end_sec,
                        ev.confidence,
                        ev.source_method,
                        ev.detector_id,
                        json.dumps(ev.metadata),
                    ))

            if clap_vector is not None and clap_facts is not None:
                embedding_bytes = clap_vector.tobytes()
                conn.execute("""
                    INSERT OR REPLACE INTO sound_embeddings (
                        track_id, model_id, model_version, embedding_dim,
                        embedding_bytes, preprocessing_version, source_method
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    sound_id,
                    clap_facts.model_id,
                    clap_facts.model_version,
                    clap_facts.embedding_dim,
                    embedding_bytes,
                    clap_facts.preprocessing_version,
                    "semantic_model",
                ))

            conn.execute("""
                INSERT INTO sound_analysis_runs (
                    track_id, analyzer_id, analyzer_version, analysis_stage,
                    execution_status, error_message, measured_facts, provenance_data
                ) VALUES (?, 'phase2_ai_orchestrator', '1.0.0', 'PHASE2_AI_ENRICHMENT', ?, ?, ?, ?)
            """, (
                sound_id,
                overall_status,
                error_message,
                json.dumps({
                    "has_classifier": classifier_inferences is not None,
                    "has_clap": clap_vector is not None,
                    "top_classifier_label": classifier_inferences.top_labels[0] if classifier_inferences and classifier_inferences.top_labels else None,
                }),
                json.dumps([p.model_dump(mode="json") for p in genome.provenance_ledger[-2:]]),
            ))

        return genome

    def get_sound_embedding(self, sound_id: int, model_id: Optional[str] = None) -> Optional[np.ndarray]:
        """Retrieves stored 512-d CLAP embedding vector as a float32 numpy array."""
        import numpy as np
        with self._get_conn() as conn:
            if model_id:
                row = conn.execute("""
                    SELECT embedding_bytes FROM sound_embeddings
                    WHERE track_id = ? AND model_id = ?
                    ORDER BY id DESC LIMIT 1
                """, (sound_id, model_id)).fetchone()
            else:
                row = conn.execute("""
                    SELECT embedding_bytes FROM sound_embeddings
                    WHERE track_id = ?
                    ORDER BY id DESC LIMIT 1
                """, (sound_id,)).fetchone()

            if not row or not row["embedding_bytes"]:
                return None

            return np.frombuffer(row["embedding_bytes"], dtype=np.float32)

    def embed_text_query(self, query: str) -> np.ndarray:
        """Encodes a natural language text query into a 512-d normalized CLAP vector."""
        from audiobook_factory.clap_semantic_adapter import CLAPSemanticAdapter
        adapter = CLAPSemanticAdapter()
        vector, _ = adapter.embed_text(query)
        return vector

    def get_classifier_tags(self, sound_id: int) -> List[Dict[str, Any]]:
        """Retrieves all classifier tags and raw scores for a sound asset ordered by rank."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT raw_label, normalized_label, raw_score, calibrated_score, rank, ontology_id, start_sec, end_sec
                FROM sound_classifier_tags
                WHERE track_id = ?
                ORDER BY rank ASC
            """, (sound_id,)).fetchall()
            return [dict(r) for r in rows]

    def search_intelligence(
        self,
        intent: str,
        limit: int = 10,
        weights: Optional[Any] = None,
        apply_diversity: bool = True,
        diversity_threshold: Optional[float] = None,
    ) -> Any:
        """
        Phase 3 Hybrid Sonic Intelligence Retrieval delegate method.
        Accepts natural language intent (English, Hindi, Hinglish), generates multi-source
        candidates, performs transparent reranking, and returns SoundRetrievalResult.
        """
        from audiobook_factory.sonic_intelligence_engine import SonicIntelligenceEngine
        engine = SonicIntelligenceEngine(sound_bank=self)
        return engine.search_sounds(
            intent=intent,
            limit=limit,
            weights=weights,
            apply_diversity=apply_diversity,
            diversity_threshold=diversity_threshold,
        )

    def get_agent_sound_card_v3(self, sound_id: int) -> Any:
        """
        Retrieves the typed Phase 3 AgentSoundCard with full epistemic transparency.
        """
        from audiobook_factory.sonic_intelligence_engine import SonicIntelligenceEngine
        engine = SonicIntelligenceEngine(sound_bank=self)
        return engine.get_sound_card(sound_id)

    def harvest_library(
        self,
        directory: Union[Path, str],
        recursive: bool = True,
        stage: str = "all",
        max_workers: int = 4,
        batch_size: int = 25,
        force: bool = False,
        retry_failed: bool = False,
        progress_callback: Optional[Callable[[int, int, str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Executes the autonomous 11-stage Sonic Intelligence harvesting pipeline
        on a local audio directory, populating sound_catalog with rich metadata,
        measured DSP facts, AST classifications, and CLAP semantic embeddings.
        """
        from audiobook_factory.sonic_harvester import SonicLibraryHarvester
        harvester = SonicLibraryHarvester(
            db_path=self.db_path,
            conn_factory=self._get_conn,
        )
        return harvester.harvest_directory(
            directory=directory,
            recursive=recursive,
            stage=stage,
            max_workers=max_workers,
            batch_size=batch_size,
            force=force,
            retry_failed=retry_failed,
            progress_callback=progress_callback,
        )

    def get_harvest_status(self) -> Dict[str, Any]:
        """
        Aggregates catalog-wide harvest intelligence and coverage telemetry.
        """
        with self._get_conn() as conn:
            total_sounds = conn.execute("SELECT COUNT(*) FROM sound_catalog").fetchone()[0]
            local_sounds = conn.execute("SELECT COUNT(*) FROM sound_catalog WHERE is_downloaded = 1 OR filepath IS NOT NULL").fetchone()[0]
            dsp_analyzed = conn.execute("SELECT COUNT(*) FROM sound_catalog WHERE integrated_lufs IS NOT NULL").fetchone()[0]
            clap_embedded = conn.execute("SELECT COUNT(DISTINCT track_id) FROM sound_embeddings").fetchone()[0]
            classifier_tagged = conn.execute("SELECT COUNT(DISTINCT track_id) FROM sound_classifier_tags").fetchone()[0]
            failed_runs = conn.execute("SELECT COUNT(*) FROM sound_analysis_runs WHERE execution_status = 'FAILED'").fetchone()[0]

            formats = conn.execute("SELECT format, COUNT(*) FROM sound_catalog WHERE format != '' GROUP BY format").fetchall()
            format_breakdown = {r[0]: r[1] for r in formats}

            categories = conn.execute("SELECT category, COUNT(*) FROM sound_catalog GROUP BY category").fetchall()
            category_breakdown = {r[0]: r[1] for r in categories}

            return {
                "total_sounds": total_sounds,
                "local_sounds": local_sounds,
                "dsp_analyzed": dsp_analyzed,
                "dsp_coverage_pct": round((dsp_analyzed / max(1, local_sounds)) * 100, 1),
                "clap_embedded": clap_embedded,
                "clap_coverage_pct": round((clap_embedded / max(1, local_sounds)) * 100, 1),
                "classifier_tagged": classifier_tagged,
                "classifier_coverage_pct": round((classifier_tagged / max(1, local_sounds)) * 100, 1),
                "failed_runs": failed_runs,
                "format_breakdown": format_breakdown,
                "category_breakdown": category_breakdown,
                "database_path": str(self.db_path),
            }

    def rebuild_search_index(self) -> bool:
        """
        Rebuilds the SQLite FTS5 virtual table for sound_catalog.
        """
        with self._get_conn() as conn:
            try:
                conn.execute("INSERT INTO sound_catalog_fts(sound_catalog_fts) VALUES('rebuild');")
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to rebuild FTS5 index: {e}")
                return False

    def run_metadata_pilot(
        self,
        export_dir: Optional[Any] = None,
        force: bool = False,
        bbc_csv_limit: int = 150,
        limit_per_bundle: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Executes the non-destructive metadata-harvesting pilot across target Foley and Ambience bundles.
        """
        from audiobook_factory.metadata_pilot_harvester import MetadataPilotHarvester
        harvester = MetadataPilotHarvester(sound_bank=self)
        return harvester.run_pilot(
            export_dir=export_dir,
            force=force,
            bbc_csv_limit=bbc_csv_limit,
            bundle_limit=limit_per_bundle,
        )

    def stream_harvest(
        self,
        source: str = "bbc",
        batch_size_gb: float = 10.0,
        batch_limit_items: int = 500,
        max_batches: Optional[int] = None,
        workers: int = 4,
        ai_mode: str = "full",
        scratch_dir: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Executes sliding-window ephemeral batch streaming ingestion:
        Download -> Extract Metadata + DSP + CLAP -> Commit to SQLite -> Wipe Scratch.
        """
        from audiobook_factory.streaming_harvester import (
            StreamingBatchConfig,
            StreamingLibraryHarvester,
        )
        cfg = StreamingBatchConfig(
            source=source,
            batch_size_bytes=int(batch_size_gb * 1024 * 1024 * 1024),
            max_items_per_batch=batch_limit_items,
            max_batches=max_batches,
            workers=workers,
            ai_mode=ai_mode,
            scratch_dir=Path(scratch_dir) if scratch_dir else (self.bank_root / "temp_scratch"),
        )
        harvester = StreamingLibraryHarvester(sound_bank=self, config=cfg)
        return harvester.run_streaming_pipeline()




_GLOBAL_SOUND_BANK: Optional[SoundBank] = None


def get_sound_bank(bank_dir: Optional[Path] = None) -> SoundBank:
    """Returns singleton instance of SoundBank."""
    global _GLOBAL_SOUND_BANK
    if _GLOBAL_SOUND_BANK is None:
        _GLOBAL_SOUND_BANK = SoundBank(bank_root=bank_dir or DEFAULT_BANK_DIR)
    return _GLOBAL_SOUND_BANK

