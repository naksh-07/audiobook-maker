#!/usr/bin/env python3
"""
Audiobook Factory - Virtual Catalog Seed Generator & Hydrator.
=============================================================
Compiles metadata records from all source adapters into a compact,
offline, compressed seed ledger (`virtual_catalog_seed.json.gz`).
Allows instant catalog hydration in < 1 second on fresh workspace clones.
"""

from __future__ import annotations
import gzip
import json
import sqlite3
from typing import Dict, Any, List, Optional
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.sound_bank import SoundBank
from audiobook_factory.virtual_catalog.incompetech_adapter import IncompetechAdapter
from audiobook_factory.virtual_catalog.bbc_sfx_adapter import BBCSoundEffectsAdapter
from audiobook_factory.virtual_catalog.sonniss_gdc_adapter import SonnissGDCAdapter
from audiobook_factory.virtual_catalog.kenney_oga_adapter import KenneyOGAAdapter

SEED_FILE_PATH = Path(__file__).resolve().parent.parent / "data" / "virtual_catalog_seed.json.gz"


def generate_seed_file(output_path: Optional[Path] = None, limits_per_adapter: Optional[Dict[str, int]] = None) -> Path:
    """
    Runs all adapters and compiles normalized records into a compressed seed file.
    """
    out_p = Path(output_path or SEED_FILE_PATH).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)
    limits = limits_per_adapter or {}

    adapters = [
        SonnissGDCAdapter(),
        KenneyOGAAdapter(),
        IncompetechAdapter(),
        BBCSoundEffectsAdapter(),
    ]

    all_records: List[Dict[str, Any]] = []
    seen_fnames = set()

    for adp in adapters:
        lim = limits.get(adp.source_name)
        logger.info(f"[*] Compiling seed records from adapter: {adp.source_name} (limit={lim})...")
        count = 0
        for raw in adp.fetch_records(limit=lim):
            norm = adp.normalize_item(raw)
            if norm and norm["filename"] not in seen_fnames:
                seen_fnames.add(norm["filename"])
                all_records.append(norm)
                count += 1
        logger.info(f"  [+] Added {count} records from {adp.source_name}")

    # Compress to gzip JSON
    raw_json = json.dumps(all_records, ensure_ascii=False)
    with gzip.open(out_p, "wt", encoding="utf-8") as gz_f:
        gz_f.write(raw_json)

    size_mb = out_p.stat().st_size / (1024 * 1024)
    logger.info(f"[+] Virtual Catalog Seed generated: {len(all_records)} sounds, {size_mb:.2f} MB at {out_p}")
    return out_p


def hydrate_from_seed(bank: SoundBank, seed_path: Optional[Path] = None) -> Dict[str, int]:
    """
    Rapidly loads the compressed seed file into SQLite FTS5 in a single atomic transaction.
    Returns stats dict (indexed, updated, skipped, total).
    """
    seed_p = Path(seed_path or SEED_FILE_PATH).resolve()
    if not seed_p.exists():
        logger.info(f"[*] Seed file {seed_p} not found; generating initial curated seed...")
        # Generate lightweight seed with curated records
        seed_p = generate_seed_file(
            output_path=seed_p,
            limits_per_adapter={"BBC_Sound_Effects": 500, "Incompetech": 200, "Kenney_OpenGameArt": 100}
        )

    with gzip.open(seed_p, "rt", encoding="utf-8") as gz_f:
        records = json.load(gz_f)

    if not isinstance(records, list):
        return {"error": "Invalid seed format"}

    stats = {"added": 0, "updated": 0, "total": len(records)}

    with bank._get_conn() as conn:
        # Check existing filenames
        cur = conn.execute("SELECT filename FROM sound_catalog")
        existing_fnames = {row["filename"] for row in cur.fetchall()}

        to_insert = []
        for it in records:
            fname = it["filename"]
            if fname in existing_fnames:
                continue

            genome_json = json.dumps(it.get("sonic_genome", {})) if isinstance(it.get("sonic_genome"), dict) else str(it.get("sonic_genome", "{}"))
            to_insert.append((
                fname,
                it.get("filepath") or f"virtual/{it.get('source_collection', 'catalog')}/{fname}",
                it.get("title", ""),
                it.get("description", ""),
                it.get("category", "SFX"),
                it.get("subcategory", "General"),
                it.get("mood", "default"),
                it.get("tags", ""),
                float(it.get("duration_sec") or 0.0),
                int(it.get("size_bytes") or 0),
                it.get("format", ".mp3"),
                it.get("source_collection", ""),
                it.get("source_url", ""),
                it.get("mirror_url"),
                it.get("source_page_url"),
                it.get("url_status", "available"),
                0,  # is_downloaded = 0
                float(it.get("tempo_bpm") or 0.0),
                it.get("key_tonality", ""),
                it.get("time_signature", "4/4"),
                it.get("wave_style", "general"),
                it.get("temporal_character", "transient"),
                it.get("energy_profile", "medium"),
                it.get("texture_profile", "organic"),
                it.get("exciter", ""),
                it.get("resonator", ""),
                it.get("action_type", ""),
                it.get("surface", ""),
                it.get("perspective", "medium"),
                it.get("acoustic_space", ""),
                it.get("dramatic_role", "general"),
                float(it.get("foreground_strength") or 0.5),
                it.get("voice_masking_risk", "LOW"),
                float(it.get("whisper_compatibility") or 0.5),
                genome_json,
            ))

        if to_insert:
            conn.executemany("""
                INSERT INTO sound_catalog (
                    filename, filepath, title, description, category, subcategory,
                    mood, tags, duration_sec, size_bytes, format, source_collection,
                    source_url, mirror_url, source_page_url, url_status, is_downloaded,
                    tempo_bpm, key_tonality, time_signature, wave_style, temporal_character,
                    energy_profile, texture_profile, exciter, resonator, action_type,
                    surface, perspective, acoustic_space, dramatic_role, foreground_strength,
                    voice_masking_risk, whisper_compatibility, sonic_genome
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?
                )
            """, to_insert)
            stats["added"] = len(to_insert)

    logger.info(f"[+] Hydrated Sound Bank from seed: {stats['added']} virtual tracks added to catalog.")
    return stats
