#!/usr/bin/env python3
"""
Audiobook Factory - Local Sound Bank Ingestion & Enrichment Engine.
===================================================================
Enriches existing local audio files on disk (Witcher 3 OST, Kenney Foley,
Soundscapes Stems, Ambience, SFX) with:
1. Multi-threaded Deterministic DSP (EBU R128 LUFS, True Peak dB, Spectral Centroid).
2. Batched GPU CLAP Semantic Embeddings (512-dim vectors on RTX 4050).
3. Atomic SQLite commit to sound_catalog and sound_embeddings.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
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
from audiobook_factory.sound_bank import get_sound_bank


def _categorize_local_file(filepath: str, filename: str) -> Tuple[str, str, str, str]:
    """
    Infers (category, subcategory, collection, tags) from directory structure and file name.
    """
    fp_lower = filepath.lower().replace("\\", "/")
    fn_lower = filename.lower()
    base_name = Path(filename).stem.replace("_", " ").replace("-", " ")

    if "witcher3_ost" in fp_lower:
        cat = "MUS"
        sub = "Witcher Medieval Soundtrack"
        coll = "Witcher3_OST"
        tags = f"music bgm soundtrack witcher medieval fantasy slavic dramatic {base_name.lower()}"
    elif "/music" in fp_lower:
        cat = "MUS"
        sub = "Orchestral Score"
        coll = "Local_Music"
        tags = f"music bgm cinematic score dramatic {base_name.lower()}"
    elif "soundscapes/stems" in fp_lower:
        cat = "MUS"
        sub = "Atmospheric Stem"
        coll = "Soundscapes_Stems"
        tags = f"music bgm ambient stem soundscape {base_name.lower()}"
    elif "foley/kenney" in fp_lower or "foley/ogg" in fp_lower:
        cat = "FOL"
        sub = "Kenney RPG Foley"
        coll = "Kenney_RPG_Audio"
        tags = f"foley sfx kenney rpg game props items {base_name.lower()}"
    elif "/foley" in fp_lower:
        cat = "FOL"
        sub = "Combat & Physical Props"
        coll = "Curated_Foley"
        tags = f"foley physical props combat footsteps gear {base_name.lower()}"
    elif "/ambience" in fp_lower:
        cat = "AMB"
        sub = "Environmental Loop"
        coll = "Curated_Ambience"
        tags = f"ambience environment atmosphere weather room {base_name.lower()}"
    elif "/sfx" in fp_lower:
        cat = "SFX"
        sub = "Cinematic Impact & Magic"
        coll = "Curated_SFX"
        tags = f"sfx impact magic creature combat {base_name.lower()}"
    else:
        cat = "FOL"
        sub = "General"
        coll = "Local_Audio"
        tags = f"sound audio {base_name.lower()}"

    return cat, sub, coll, tags


def enrich_local_bank(batch_size: int = 32, max_dsp_workers: int = 12) -> Dict[str, Any]:
    """
    Scans sound_catalog for local files that exist on disk but lack DSP / CLAP enrichment,
    and processes them using 12-worker DSP + RTX 4050 batched CLAP.
    """
    bank = get_sound_bank()
    db_path = bank.db_path
    analyzer = DeterministicAudioAnalyzer()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")

    rows = conn.execute("""
        SELECT id, filename, filepath, source_collection, category, subcategory
        FROM sound_catalog
        WHERE filepath NOT LIKE 'virtual://%'
          AND integrated_lufs IS NULL
    """).fetchall()

    pending: List[sqlite3.Row] = []
    for r in rows:
        fp = r["filepath"]
        if fp and os.path.exists(fp):
            pending.append(r)

    print("=" * 75)
    print("  LOCAL SOUND BANK ACOUSTIC & SEMANTIC ENRICHMENT")
    print("=" * 75)
    print(f"  Target Database   : {db_path}")
    print(f"  Unanalyzed Files  : {len(pending)} on disk (of {len(rows)} unanalyzed local rows)")
    print(f"  DSP Workers       : {max_dsp_workers} threads")
    print(f"  GPU Batch Size    : {batch_size} (RTX 4050 Tensor Cores)")
    print("=" * 75 + "\n")

    if not pending:
        print("[+] All local audio files on disk are already 100% enriched!")
        conn.close()
        return {"status": "NOOP", "enriched": 0}

    t0 = time.perf_counter()

    # Stage 1: Parallel DSP Analysis
    print(f"[*] [Stage 1/2] Parallel DSP Analysis (EBU R128 + astats) on {len(pending)} files...")
    t_dsp_start = time.perf_counter()

    def _dsp_worker(r: sqlite3.Row):
        fp = r["filepath"]
        fn = r["filename"]
        try:
            sz = os.path.getsize(fp)
            facts, _ = analyzer.analyze_file(Path(fp))
            return (r, facts, sz)
        except Exception as e:
            logger.error(f"DSP error for {fn}: {e}")
            return None

    dsp_results: List[Tuple[sqlite3.Row, Any, int]] = []
    with ThreadPoolExecutor(max_workers=max_dsp_workers) as pool:
        futures = [pool.submit(_dsp_worker, r) for r in pending]
        for fut in as_completed(futures):
            res = fut.result()
            if res is not None:
                dsp_results.append(res)

    t_dsp = time.perf_counter() - t_dsp_start
    print(f"[+] DSP Analysis complete: {len(dsp_results)}/{len(pending)} files in {t_dsp:.2f}s ({len(dsp_results)/max(0.1, t_dsp):.1f} items/s)\n")

    # Stage 2: Batched GPU CLAP Vector Inference
    print(f"[*] [Stage 2/2] Loading LAION-CLAP Model & running GPU Batched Inference...")
    t_clap_start = time.perf_counter()
    clap_adapter = CLAPSemanticAdapter()

    audio_payloads = []
    for r, dsp_facts, sz in dsp_results:
        fp = r["filepath"]
        try:
            wf, sr = sf.read(fp, dtype="float32", always_2d=False)
            if wf.ndim > 1:
                wf = np.mean(wf, axis=0 if wf.shape[0] < wf.shape[1] else 1)
            dur = dsp_facts.format.duration_sec if dsp_facts.format.duration_sec > 0 else (len(wf) / sr)
            audio_payloads.append((r, dsp_facts, sz, wf, sr, dur))
        except Exception as e:
            logger.warning(f"Audio read failed for {fp}: {e}")

    raw_payloads = [(wf, sr, dur) for _, _, _, wf, sr, dur in audio_payloads]
    vectors_with_facts = clap_adapter.embed_audio_batch(raw_payloads, batch_size=batch_size)
    t_clap = time.perf_counter() - t_clap_start
    print(f"[+] GPU CLAP Inference complete: {len(vectors_with_facts)} vectors in {t_clap:.2f}s ({len(vectors_with_facts)/max(0.1, t_clap):.1f} items/s)\n")

    # Stage 3: Atomic SQLite Commit
    print(f"[*] [Stage 3/3] Committing {len(vectors_with_facts)} enriched tracks to SQLite (sound_bank.db)...")
    now_iso = datetime.now(timezone.utc).isoformat()
    committed = 0

    for (r, dsp, sz, _, _, _), (vec, _) in zip(audio_payloads, vectors_with_facts):
        track_id = r["id"]
        fn = r["filename"]
        fp = r["filepath"]

        cat, sub, coll, tags = _categorize_local_file(fp, fn)
        silence_val = dsp.temporal.silence_ratio if hasattr(dsp, "temporal") and dsp.temporal else None
        bpm_val = dsp.tonal.detected_bpm if hasattr(dsp, "tonal") and dsp.tonal else None

        conn.execute("""
            UPDATE sound_catalog
            SET integrated_lufs = ?, true_peak_db = ?, spectral_centroid_hz = ?,
                loudness_range_lu = ?, rms_level_db = ?,
                spectral_bandwidth_hz = ?, spectral_rolloff_hz = ?,
                spectral_flatness = ?, zero_crossing_rate = ?, silence_ratio = ?,
                sample_rate = ?, channels = ?, bit_depth = ?, tempo_bpm = ?,
                duration_sec = ?, size_bytes = ?, is_downloaded = 1,
                source_collection = COALESCE(NULLIF(source_collection, ''), ?),
                category = ?, subcategory = ?, tags = ?,
                analysis_version = 'v2.1-local', last_analyzed_at = ?
            WHERE id = ?
        """, (
            dsp.loudness.integrated_lufs,
            dsp.loudness.true_peak_dbtp,
            dsp.spectral.spectral_centroid_hz,
            dsp.loudness.loudness_range_lu,
            dsp.loudness.rms_level_db,
            dsp.spectral.spectral_bandwidth_hz,
            dsp.spectral.spectral_rolloff_hz,
            dsp.spectral.spectral_flatness,
            dsp.spectral.zero_crossing_rate,
            silence_val,
            dsp.format.sample_rate,
            dsp.format.channels,
            dsp.format.bit_depth,
            bpm_val,
            dsp.format.duration_sec,
            sz,
            coll,
            cat,
            sub,
            tags,
            now_iso,
            track_id,
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
                "local_bank_enricher",
            ))

        committed += 1

    conn.commit()
    conn.close()

    total_time = time.perf_counter() - t0
    print("=" * 75)
    print("  LOCAL ENRICHMENT COMPLETE")
    print("=" * 75)
    print(f"  Tracks Enriched   : {committed}")
    print(f"  Total Time        : {total_time:.2f} seconds ({total_time/60.0:.2f} minutes)")
    print(f"  Throughput        : {committed / max(0.1, total_time):.1f} tracks/second")
    print("=" * 75 + "\n")

    return {
        "status": "SUCCESS",
        "enriched": committed,
        "elapsed_seconds": round(total_time, 2),
    }


if __name__ == "__main__":
    enrich_local_bank()
