#!/usr/bin/env python3
"""
Audiobook Factory - The Witcher 3 Full Game Audio Sonic Intelligence Ingestion Engine.
=====================================================================================
Processes all 26,906 CD Projekt RED Witcher 3 studio audio assets in-place:
1. Zero Audio Touch: 100% read-only access to existing WAV files on disk (0 bytes bloat).
2. Data Preservation: Preserves all existing columns/rows in sound_catalog.sqlite (sound_effects).
3. Sonic Intelligence Upgrade:
   - Parallel 12-worker DSP (EBU R128 LUFS, True Peak dB, Spectral Centroid, Bandwidth, Rolloff, Flatness).
   - Batched GPU CLAP Semantic Embeddings (512-dim vectors on RTX 4050 Tensor Cores).
   - Adds 'franchise_affinity = the_witcher', 'lore_tags', and 'ip_priority = 1.0' for automatic Director IP priority.
4. Crash-Proof Checkpointing:
   - Chunked execution (500 tracks per chunk).
   - Logs checkpoints in w3_ingestion_batches. Resumable anytime with zero data loss.
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf

from audiobook_factory.clap_semantic_adapter import CLAPSemanticAdapter
from audiobook_factory.deterministic_audio_analyzer import DeterministicAudioAnalyzer
from audiobook_factory.logger import logger

W3_DB_PATH = Path(r"C:\Users\Suraj\Documents\antigravity\jolly-mendeleev\tools\w3_audio_extractor\Witcher3_Studio_Library\sound_catalog.sqlite")
W3_LIB_DIR = Path(r"C:\Users\Suraj\Documents\antigravity\jolly-mendeleev\tools\w3_audio_extractor\Witcher3_Studio_Library")


def setup_w3_schema(conn: sqlite3.Connection):
    """Non-destructively adds Sonic Intelligence & IP Affinity columns to sound_effects."""
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")

    cols = {c[1] for c in conn.execute("PRAGMA table_info(sound_effects)").fetchall()}
    new_cols = [
        ("duration_sec", "REAL DEFAULT 0.0"),
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
        ("tags", "TEXT DEFAULT ''"),
        ("dramatic_role", "TEXT DEFAULT 'combat_action'"),
        ("voice_masking_risk", "TEXT DEFAULT 'LOW'"),
        ("ducking_recommendation_db", "REAL DEFAULT -12.0"),
        ("franchise_affinity", "TEXT DEFAULT 'the_witcher'"),
        ("lore_tags", "TEXT DEFAULT ''"),
        ("ip_priority", "REAL DEFAULT 1.0"),
        ("analysis_version", "TEXT DEFAULT 'v2.1-w3'"),
        ("last_analyzed_at", "TIMESTAMP DEFAULT NULL"),
    ]

    for col_name, col_type in new_cols:
        if col_name not in cols:
            conn.execute(f"ALTER TABLE sound_effects ADD COLUMN {col_name} {col_type};")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_w3_lufs ON sound_effects(integrated_lufs);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_w3_franchise ON sound_effects(franchise_affinity);")

    # Embeddings table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sound_embeddings (
            track_id INTEGER PRIMARY KEY,
            model_id TEXT,
            model_version TEXT,
            embedding_dim INTEGER,
            embedding_bytes BLOB,
            preprocessing_version TEXT,
            source_method TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Checkpoint tracking table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS w3_ingestion_batches (
            batch_index INTEGER PRIMARY KEY,
            chunk_start_id INTEGER,
            chunk_end_id INTEGER,
            total_assets INTEGER,
            elapsed_seconds REAL,
            status TEXT,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()


def extract_w3_lore_and_tags(filename: str, category: str, relative_path: str) -> Tuple[str, str, str]:
    """
    Extracts rich search tags, canonical lore tags, and dramatic role from Witcher 3 asset hierarchy.
    """
    p_lower = (relative_path + " " + filename).lower().replace("\\", " ").replace("/", " ").replace("_", " ")

    # 1. Lore detection
    lore_tokens = []
    monster_names = [
        "leshen", "bruxa", "bies", "fiend", "golem", "dettlaff", "crone", "witches",
        "drowner", "werewolf", "nekker", "wraith", "siren", "harpy", "griffin",
        "basilisk", "cockatrice", "elemental", "gargoyle", "rotfiend", "foglet",
        "arachas", "endriaga", "barghest", "kikimora", "sharley", "wight", "noonwraith"
    ]
    for m in monster_names:
        if m in p_lower:
            lore_tokens.append(f"monster_{m}")

    signs = ["aard", "igni", "quen", "axii", "yrden"]
    for s in signs:
        if s in p_lower:
            lore_tokens.append(f"sign_{s}")

    characters = ["geralt", "ciri", "yennefer", "triss", "dandelion", "roach", "vesemir", "lambert", "eskel", "keira", "dijkstra", "radovid", "emhyr"]
    for ch in characters:
        if ch in p_lower:
            lore_tokens.append(f"character_{ch}")

    locations = ["velen", "skellige", "novigrad", "oxenfurt", "kaer_morhen", "toussaint", "white_orchard"]
    for loc in locations:
        if loc in p_lower:
            lore_tokens.append(f"location_{loc}")

    lore_str = ", ".join(sorted(set(lore_tokens)))

    # 2. Dramatic role & tags
    cat_lower = category.lower()
    if "combat" in cat_lower or "weapon" in cat_lower:
        dramatic_role = "combat_impact"
        base_tags = "combat sword weapon blade parry impact flesh gore steel silver"
    elif "magic" in cat_lower or "sign" in cat_lower:
        dramatic_role = "magical_spell"
        base_tags = "magic sign spell aard igni quen axii yrden blast cast energy"
    elif "creature" in cat_lower or "monster" in cat_lower:
        dramatic_role = "monster_threat"
        base_tags = "creature monster beast roar snarl hiss growl attack dark"
    elif "foley" in cat_lower or "movement" in cat_lower:
        dramatic_role = "foley_movement"
        base_tags = "foley footstep armor leather gear movement walk run"
    elif "ambience" in cat_lower or "environment" in cat_lower:
        dramatic_role = "environmental_bed"
        base_tags = "ambience weather room forest wind rain swamp background"
    elif "music" in cat_lower or "stem" in cat_lower:
        dramatic_role = "musical_underscore"
        base_tags = "music bgm stem battle combat tension dramatic"
    elif "physics" in cat_lower:
        dramatic_role = "physics_interaction"
        base_tags = "physics door wood stone collision break fall"
    elif "voice" in cat_lower or "grunt" in cat_lower:
        dramatic_role = "character_vocal"
        base_tags = "voice grunt exertion effort pain breath vocal"
    else:
        dramatic_role = "general_sfx"
        base_tags = "sound effect sfx"

    # Combine tokens
    words = [w for w in re.sub(r"[^a-zA-Z0-9]+", " ", p_lower).split() if len(w) > 2 and not w.isdigit()]
    all_tags = f"the_witcher {base_tags} {lore_str.replace('_', ' ')} {' '.join(words[:15])}".strip()

    return all_tags, lore_str, dramatic_role


def run_witcher3_enrichment(
    chunk_size: int = 500,
    max_dsp_workers: int = 12,
    clap_batch_size: int = 32,
    limit_chunks: Optional[int] = None,
):
    """Executes chunk-by-chunk crash-proof Sonic Intelligence enrichment."""
    if not W3_DB_PATH.exists():
        print(f"[!] Database not found at {W3_DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(W3_DB_PATH, timeout=60.0)
    conn.row_factory = sqlite3.Row
    setup_w3_schema(conn)

    # Count pending
    total_in_db = conn.execute("SELECT count(*) FROM sound_effects").fetchone()[0]
    analyzed_count = conn.execute("SELECT count(*) FROM sound_effects WHERE integrated_lufs IS NOT NULL").fetchone()[0]
    pending_count = total_in_db - analyzed_count

    print("=" * 80)
    print("  THE WITCHER 3: WILD HUNT - STUDIO AUDIO SONIC INTELLIGENCE ENGINE")
    print("=" * 80)
    print(f"  Target Database   : {W3_DB_PATH}")
    print(f"  Audio Source Vault: {W3_LIB_DIR} (100% In-Place Read-Only)")
    print(f"  Total Sounds      : {total_in_db:,} WAV assets")
    print(f"  Already Enriched  : {analyzed_count:,} assets")
    print(f"  Pending to Process: {pending_count:,} assets")
    print(f"  Chunk Size        : {chunk_size} tracks per batch")
    print(f"  DSP Concurrency   : {max_dsp_workers} CPU worker threads")
    print(f"  GPU Inference     : NVIDIA GeForce RTX 4050 (Batch size {clap_batch_size})")
    print(f"  IP Stamping       : franchise_affinity = 'the_witcher' | ip_priority = 1.0")
    print("=" * 80 + "\n")

    if pending_count == 0:
        print("[+] All 26,906 Witcher 3 studio audio tracks are already 100% enriched!")
        conn.close()
        return

    # Initialize analyzers
    analyzer = DeterministicAudioAnalyzer()
    clap = CLAPSemanticAdapter()

    # Discover current batch index
    cur_batch = conn.execute("SELECT COALESCE(MAX(batch_index), 0) FROM w3_ingestion_batches").fetchone()[0]

    chunks_done = 0
    t_global_start = time.perf_counter()
    total_processed_this_run = 0

    while True:
        if limit_chunks and chunks_done >= limit_chunks:
            print(f"[*] Reached configured chunk limit ({limit_chunks}). Halting.")
            break

        # Fetch next chunk
        chunk_rows = conn.execute("""
            SELECT id, filename, category, relative_path
            FROM sound_effects
            WHERE integrated_lufs IS NULL
            ORDER BY id
            LIMIT ?
        """, (chunk_size,)).fetchall()

        if not chunk_rows:
            print("\n[+] All pending tracks have been fully processed!")
            break

        cur_batch += 1
        chunks_done += 1
        chunk_start_id = chunk_rows[0]["id"]
        chunk_end_id = chunk_rows[-1]["id"]
        t_chunk_start = time.perf_counter()

        print(f"\n>>> [CHUNK {cur_batch:03d}] Processing {len(chunk_rows)} tracks (IDs {chunk_start_id}..{chunk_end_id}) | Pending: {pending_count - total_processed_this_run:,} remaining")

        # Stage 1: Parallel DSP
        t_dsp0 = time.perf_counter()
        def _dsp_worker(r):
            fp = W3_LIB_DIR / r["relative_path"]
            try:
                facts, _ = analyzer.analyze_file(fp)
                return r, facts, fp
            except Exception as e:
                logger.error(f"DSP failed for {r['filename']}: {e}")
                return r, None, fp

        dsp_results = []
        with ThreadPoolExecutor(max_workers=max_dsp_workers) as pool:
            futs = [pool.submit(_dsp_worker, r) for r in chunk_rows]
            for fut in as_completed(futs):
                dsp_results.append(fut.result())

        t_dsp = time.perf_counter() - t_dsp0
        print(f"  [+] Stage 1 (DSP Analysis) : {len(dsp_results)} files in {t_dsp:.2f}s ({len(dsp_results)/max(0.1, t_dsp):.1f} items/s)")

        # Stage 2: Batched GPU CLAP Vectors
        t_clap0 = time.perf_counter()
        audio_payloads = []
        for r, facts, fp in dsp_results:
            try:
                wf, sr = sf.read(str(fp), dtype="float32", always_2d=False)
                if wf.ndim > 1:
                    wf = np.mean(wf, axis=0 if wf.shape[0] < wf.shape[1] else 1)
                dur = facts.format.duration_sec if (facts and facts.format.duration_sec > 0) else (len(wf) / sr)
                audio_payloads.append((r, facts, fp, wf, sr, dur))
            except Exception as e:
                logger.warning(f"Audio read error on {fp.name}: {e}")
                dummy_wf = np.zeros(16000, dtype=np.float32)
                audio_payloads.append((r, facts, fp, dummy_wf, 16000, 1.0))

        raw_payloads = [(wf, sr, dur) for _, _, _, wf, sr, dur in audio_payloads]
        vectors_with_facts = clap.embed_audio_batch(raw_payloads, batch_size=clap_batch_size)
        t_clap = time.perf_counter() - t_clap0
        print(f"  [+] Stage 2 (GPU CLAP AI)  : {len(vectors_with_facts)} vectors in {t_clap:.2f}s ({len(vectors_with_facts)/max(0.1, t_clap):.1f} items/s)")

        # Stage 3: Atomic SQLite Commit
        now_iso = datetime.now(timezone.utc).isoformat()
        for (r, facts, fp, _, _, _), (vec, _) in zip(audio_payloads, vectors_with_facts):
            track_id = r["id"]
            fn = r["filename"]
            cat = r["category"]
            rel_p = r["relative_path"]

            tags, lore, dramatic_role = extract_w3_lore_and_tags(fn, cat, rel_p)

            dur_sec = facts.format.duration_sec if facts else 0.0
            sr_val = facts.format.sample_rate if facts else 48000
            ch_val = facts.format.channels if facts else 2
            bd_val = facts.format.bit_depth if facts else 16
            lufs = facts.loudness.integrated_lufs if facts else None
            tp = facts.loudness.true_peak_dbtp if facts else None
            lra = facts.loudness.loudness_range_lu if facts else None
            rms = facts.loudness.rms_level_db if facts else None
            sc = facts.spectral.spectral_centroid_hz if facts else None
            sb = facts.spectral.spectral_bandwidth_hz if facts else None
            sro = facts.spectral.spectral_rolloff_hz if facts else None
            sf_val = facts.spectral.spectral_flatness if facts else None
            zcr = facts.spectral.zero_crossing_rate if facts else None
            silence = facts.temporal.silence_ratio if (facts and hasattr(facts, "temporal") and facts.temporal) else None

            # Calculate voice masking risk based on spectral centroid
            if sc is not None and 800 <= sc <= 3500:
                mask_risk = "HIGH"
                duck_db = -16.0
            elif sc is not None and (sc < 800 or sc > 3500):
                mask_risk = "LOW"
                duck_db = -10.0
            else:
                mask_risk = "MEDIUM"
                duck_db = -12.0

            conn.execute("""
                UPDATE sound_effects
                SET duration_sec = ?, sample_rate = ?, channels = ?, bit_depth = ?,
                    integrated_lufs = ?, true_peak_db = ?, loudness_range_lu = ?, rms_level_db = ?,
                    spectral_centroid_hz = ?, spectral_bandwidth_hz = ?, spectral_rolloff_hz = ?,
                    spectral_flatness = ?, zero_crossing_rate = ?, silence_ratio = ?,
                    tags = ?, dramatic_role = ?, voice_masking_risk = ?, ducking_recommendation_db = ?,
                    franchise_affinity = 'the_witcher', lore_tags = ?, ip_priority = 1.0,
                    analysis_version = 'v2.1-w3', last_analyzed_at = ?
                WHERE id = ?
            """, (
                dur_sec, sr_val, ch_val, bd_val,
                lufs, tp, lra, rms,
                sc, sb, sro, sf_val, zcr, silence,
                tags, dramatic_role, mask_risk, duck_db,
                lore, now_iso,
                track_id
            ))

            if vec is not None:
                conn.execute("""
                    INSERT OR REPLACE INTO sound_embeddings (
                        track_id, model_id, model_version, embedding_dim,
                        embedding_bytes, preprocessing_version, source_method
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    track_id,
                    "laion-clap-htsat-fused",
                    "2023",
                    512,
                    vec.tobytes(),
                    "v2.1",
                    "w3_studio_harvester"
                ))

        t_chunk = time.perf_counter() - t_chunk_start
        conn.execute("""
            INSERT INTO w3_ingestion_batches (
                batch_index, chunk_start_id, chunk_end_id, total_assets, elapsed_seconds, status
            ) VALUES (?, ?, ?, ?, ?, 'COMPLETED')
        """, (cur_batch, chunk_start_id, chunk_end_id, len(chunk_rows), round(t_chunk, 2)))
        conn.commit()

        total_processed_this_run += len(chunk_rows)
        progress_pct = ((analyzed_count + total_processed_this_run) / total_in_db) * 100.0
        overall_elapsed = time.perf_counter() - t_global_start
        overall_speed = total_processed_this_run / max(0.1, overall_elapsed)
        remaining_sec = (pending_count - total_processed_this_run) / max(0.1, overall_speed)

        print(f"  [OK] Chunk {cur_batch:03d} committed in {t_chunk:.2f}s ({len(chunk_rows)/t_chunk:.1f} items/s) | Total Progress: {progress_pct:.1f}% ({analyzed_count + total_processed_this_run:,}/{total_in_db:,}) | ETA: {remaining_sec/60.0:.1f} mins ({remaining_sec/3600.0:.2f} hours)")

    conn.close()
    t_global = time.perf_counter() - t_global_start
    print("\n" + "=" * 80)
    print("  WITCHER 3 STUDIO LIBRARY INGESTION RUN FINISHED")
    print("=" * 80)
    print(f"  Tracks Processed This Run : {total_processed_this_run:,}")
    print(f"  Total Time Elapsed        : {t_global:.2f} seconds ({t_global/60.0:.1f} minutes / {t_global/3600.0:.2f} hours)")
    print(f"  Average Processing Speed  : {total_processed_this_run / max(0.1, t_global):.2f} tracks/second")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Witcher 3 Studio Audio Sonic Intelligence Ingest Engine")
    parser.add_argument("--chunk-size", type=int, default=500, help="Batch size per atomic checkpoint")
    parser.add_argument("--workers", type=int, default=12, help="Parallel CPU workers for DSP")
    parser.add_argument("--clap-batch", type=int, default=32, help="GPU tensor mini-batch size")
    parser.add_argument("--limit-chunks", type=int, default=None, help="Stop after N chunks (default: full run)")
    args = parser.parse_args()

    run_witcher3_enrichment(
        chunk_size=args.chunk_size,
        max_dsp_workers=args.workers,
        clap_batch_size=args.clap_batch,
        limit_chunks=args.limit_chunks,
    )
