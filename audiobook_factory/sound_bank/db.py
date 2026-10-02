#!/usr/bin/env python3
"""
Audiobook Factory - Sound Bank Database & Schema Operations.
Manages SQLite connection pooling, WAL mode, FTS5 virtual tables, triggers,
indexing, and proportional musical section seeding.
"""

from __future__ import annotations
import re
import sqlite3
import contextlib
from pathlib import Path
from typing import Generator, Optional

DEFAULT_BANK_DIR = Path(__file__).resolve().parents[2] / "audiobooks" / "sound_bank"
DEFAULT_DB_PATH = DEFAULT_BANK_DIR / "sound_bank.db"


class DatabaseMixin:
    """Database connection and schema initialization mixin for SoundBank."""

    db_path: Path
    bank_root: Path

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
        music_tracks = conn.execute("""
            SELECT id, filename, duration_sec FROM sound_catalog
            WHERE category IN ('MUS', 'LEITMOTIF', 'CHAPTER_BED', 'DYNAMIC_STEM')
        """).fetchall()

        for track in music_tracks:
            t_id = track["id"]
            dur = float(track["duration_sec"] or 0.0)
            if dur <= 0.0:
                continue

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
