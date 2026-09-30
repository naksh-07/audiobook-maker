#!/usr/bin/env python3
"""
Audiobook Factory - Bridge & Synchronize Witcher 3 Game Sound Bank to Master Catalog.
=====================================================================================
Synchronizes the 26,906 enriched Witcher 3 studio audio assets into the master
Sound Bank (audiobooks/sound_bank/sound_bank.db):
1. In-place Filepaths: Points directly to existing WAVs (Zero disk bloat).
2. Dual Catalog Ingestion: Transfers all DSP facts, tags, dramatic roles, and lore tags.
3. Neural Vectors: Links 26,906 CLAP 512-dim embeddings for hybrid search.
4. FTS5 Indexing: Updates master search index for sub-millisecond keyword retrieval.
"""

import os
import sqlite3
import time
from pathlib import Path

W3_DB_PATH = Path(r"C:\Users\Suraj\Documents\antigravity\jolly-mendeleev\tools\w3_audio_extractor\Witcher3_Studio_Library\sound_catalog.sqlite")
W3_LIB_DIR = Path(r"C:\Users\Suraj\Documents\antigravity\jolly-mendeleev\tools\w3_audio_extractor\Witcher3_Studio_Library")
MASTER_DB_PATH = Path("audiobooks/sound_bank/sound_bank.db")

def sync_witcher3_to_master():
    print("=" * 80)
    print("  BRIDGING WITCHER 3 STUDIO LIBRARY TO MASTER SOUND BANK")
    print("=" * 80)
    print(f"  Source W3 DB : {W3_DB_PATH}")
    print(f"  Source W3 Dir: {W3_LIB_DIR}")
    print(f"  Master DB    : {MASTER_DB_PATH}")
    print("=" * 80)

    if not W3_DB_PATH.exists():
        print(f"[!] W3 DB not found at {W3_DB_PATH}")
        return

    if not MASTER_DB_PATH.exists():
        print(f"[!] Master DB not found at {MASTER_DB_PATH}")
        return

    w3_conn = sqlite3.connect(W3_DB_PATH)
    w3_conn.row_factory = sqlite3.Row

    master_conn = sqlite3.connect(MASTER_DB_PATH, timeout=60.0)
    master_conn.row_factory = sqlite3.Row
    master_conn.execute("PRAGMA journal_mode=WAL;")
    master_conn.execute("PRAGMA synchronous=NORMAL;")

    # Check how many are already synced
    already_synced = master_conn.execute(
        "SELECT count(*) FROM sound_catalog WHERE source_collection = 'Witcher3_Game_SFX'"
    ).fetchone()[0]

    print(f"[*] Currently synced Witcher 3 game assets in master DB: {already_synced}")

    if already_synced >= 26906:
        print("[+] All 26,906 Witcher 3 studio assets are already synced into master sound_bank.db!")
        w3_conn.close()
        master_conn.close()
        return

    t0 = time.perf_counter()

    # Read all W3 sound effects
    print("[*] Reading 26,906 enriched records from Witcher 3 database...")
    w3_rows = w3_conn.execute("SELECT * FROM sound_effects ORDER BY id").fetchall()

    # Read all W3 embeddings
    print("[*] Reading 26,906 CLAP embeddings from Witcher 3 database...")
    w3_emb_rows = w3_conn.execute(
        "SELECT track_id, model_id, model_version, embedding_dim, embedding_bytes, preprocessing_version, source_method FROM sound_embeddings"
    ).fetchall()
    emb_by_w3_id = {r[0]: r for r in w3_emb_rows}

    # Fetch existing filepaths in master DB to prevent any duplicate insertion
    existing_fps = {
        r[0] for r in master_conn.execute("SELECT filepath FROM sound_catalog WHERE filepath IS NOT NULL").fetchall()
    }

    # Prepare batch insert
    records_to_insert = []
    emb_to_insert = []

    print("[*] Preparing records for master catalog ingestion...")
    for row in w3_rows:
        w3_id = row["id"]
        rel_path = row["relative_path"]
        abs_path = str(W3_LIB_DIR / rel_path)

        if abs_path in existing_fps:
            continue

        filename = row["filename"]
        cat = row["category"]
        tags = row["tags"] or ""
        lore = row["lore_tags"] or ""
        role = row["dramatic_role"] or "combat_action"

        # Determine subcategory from relative path or category
        parts = rel_path.replace("\\", "/").split("/")
        subcat = parts[0] if len(parts) > 1 else cat

        rec = (
            filename,
            abs_path,
            "SFX",                       # category
            subcat,                      # subcategory
            "tense",                     # mood
            tags,                        # tags
            row["duration_sec"] or 0.0,
            row["size_bytes"] or 0,
            "wav",                       # format
            1,                           # is_downloaded
            filename,                    # title
            f"Witcher 3 Studio Audio: {rel_path}",  # description
            "Witcher3_Game_SFX",         # source_collection
            "CD PROJEKT RED (Studio Assets)", # license
            "CD PROJEKT RED",            # creator_attribution
            row["sample_rate"] or 48000,
            row["channels"] or 2,
            row["bit_depth"] or 16,
            row["integrated_lufs"],
            row["true_peak_db"],
            row["loudness_range_lu"],
            row["rms_level_db"],
            row["spectral_centroid_hz"],
            row["spectral_bandwidth_hz"],
            row["spectral_rolloff_hz"],
            row["spectral_flatness"],
            row["zero_crossing_rate"],
            row["silence_ratio"],
            role,                        # dramatic_role
            row["voice_masking_risk"] or "LOW",
            row["analysis_version"] or "v2.1-w3",
            row["last_analyzed_at"],
            "the_witcher",               # franchise_affinity
            lore,                        # lore_tags
            1.0                          # ip_priority
        )
        records_to_insert.append((w3_id, rec))

    print(f"[*] New records to insert: {len(records_to_insert)}")

    if records_to_insert:
        insert_sql = """
            INSERT INTO sound_catalog (
                filename, filepath, category, subcategory, mood, tags,
                duration_sec, size_bytes, format, is_downloaded,
                title, description, source_collection, license, creator_attribution,
                sample_rate, channels, bit_depth,
                integrated_lufs, true_peak_db, loudness_range_lu, rms_level_db,
                spectral_centroid_hz, spectral_bandwidth_hz, spectral_rolloff_hz,
                spectral_flatness, zero_crossing_rate, silence_ratio,
                dramatic_role, voice_masking_risk,
                analysis_version, last_analyzed_at,
                franchise_affinity, lore_tags, ip_priority
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?, ?
            )
        """

        master_cur = master_conn.cursor()
        print("[*] Committing sound catalog records...")

        # Insert records and track generated IDs
        master_conn.execute("BEGIN TRANSACTION;")
        for w3_id, rec in records_to_insert:
            master_cur.execute(insert_sql, rec)
            new_master_id = master_cur.lastrowid
            if w3_id in emb_by_w3_id:
                emb = emb_by_w3_id[w3_id]
                emb_to_insert.append((
                    new_master_id,
                    emb["model_id"],
                    emb["model_version"],
                    emb["embedding_dim"],
                    emb["embedding_bytes"],
                    emb["preprocessing_version"],
                    emb["source_method"]
                ))

        print(f"[*] Committing {len(emb_to_insert)} CLAP neural embeddings...")
        emb_insert_sql = """
            INSERT INTO sound_embeddings (
                track_id, model_id, model_version, embedding_dim,
                embedding_bytes, preprocessing_version, source_method
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        master_cur.executemany(emb_insert_sql, emb_to_insert)
        master_conn.commit()

        # Update FTS5 index
        print("[*] Rebuilding FTS5 full-text search index...")
        master_conn.execute("""
            INSERT INTO sound_catalog_fts (
                rowid, filename, title, description, category, subcategory,
                mood, wave_style, exciter, resonator, action_type, dramatic_role, tags
            )
            SELECT id, filename, title, description, category, subcategory,
                   mood, wave_style, exciter, resonator, action_type, dramatic_role, tags
            FROM sound_catalog
            WHERE source_collection = 'Witcher3_Game_SFX'
        """)
        master_conn.commit()

    t_elapsed = time.perf_counter() - t0
    final_synced = master_conn.execute(
        "SELECT count(*) FROM sound_catalog WHERE source_collection = 'Witcher3_Game_SFX'"
    ).fetchone()[0]
    total_master = master_conn.execute("SELECT count(*) FROM sound_catalog").fetchone()[0]
    total_embs = master_conn.execute("SELECT count(*) FROM sound_embeddings").fetchone()[0]

    print("=" * 80)
    print("  SYNCHRONIZATION COMPLETED SUCCESSFULLY")
    print("=" * 80)
    print(f"  Witcher 3 Assets Synced: {final_synced:,} / 26,906")
    print(f"  Master Catalog Total   : {total_master:,} sounds")
    print(f"  Master Embeddings Total: {total_embs:,} vectors")
    print(f"  Elapsed Time           : {t_elapsed:.2f} seconds")
    print("=" * 80)

    w3_conn.close()
    master_conn.close()

if __name__ == "__main__":
    sync_witcher3_to_master()
