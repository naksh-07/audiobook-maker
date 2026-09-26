#!/usr/bin/env python3
"""
Audiobook Factory - Virtual Sound Source Base Adapter.
======================================================
Defines the standard abstract interface for open-source audio collection
adapters, providing normalization, deduplication, URL validation,
and atomic database upserting.
"""

from __future__ import annotations
import abc
import json
import sqlite3
from typing import Dict, Any, List, Optional, Generator
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.sound_bank import SoundBank


class BaseSourceAdapter(abc.ABC):
    """Abstract base class for all remote collection metadata ingesters."""

    source_name: str = "generic_source"
    default_license: str = "Royalty-Free"

    @abc.abstractmethod
    def fetch_records(self, limit: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        """Yields raw metadata items from remote API, CSV, or cached local seed."""
        pass

    @abc.abstractmethod
    def normalize_item(self, raw_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Normalizes a raw source item into the unified Sonic Intelligence schema:
        - filename, title, description, category, subcategory, mood, tags
        - source_collection, source_url, mirror_url, source_page_url, license, creator
        - tempo_bpm, key_tonality, time_signature, duration_sec
        - wave_style, temporal_character, energy_profile, texture_profile
        - exciter, resonator, action_type, surface, perspective
        - dramatic_role, foreground_strength, voice_masking_risk, whisper_compatibility
        - sonic_genome (JSON v2)
        """
        pass

    def ingest(
        self,
        bank: SoundBank,
        limit: Optional[int] = None,
        batch_size: int = 500,
    ) -> Dict[str, int]:
        """
        Ingests and indexes items from this source into the Sound Bank.
        Returns ingestion statistics (added, updated, skipped, total).
        """
        stats = {"added": 0, "updated": 0, "skipped": 0, "total": 0}
        batch: List[Dict[str, Any]] = []

        for raw in self.fetch_records(limit=limit):
            norm = self.normalize_item(raw)
            if not norm:
                stats["skipped"] += 1
                continue

            batch.append(norm)
            stats["total"] += 1

            if len(batch) >= batch_size:
                added, updated = self._upsert_batch(bank, batch)
                stats["added"] += added
                stats["updated"] += updated
                batch = []

        if batch:
            added, updated = self._upsert_batch(bank, batch)
            stats["added"] += added
            stats["updated"] += updated

        logger.info(
            f"[+] Ingested source '{self.source_name}': {stats['added']} added, "
            f"{stats['updated']} updated, {stats['skipped']} skipped ({stats['total']} total)."
        )
        return stats

    def _upsert_batch(self, bank: SoundBank, items: List[Dict[str, Any]]) -> tuple[int, int]:
        """Atomically upserts a batch of normalized records into sound_catalog."""
        added = 0
        updated = 0

        with bank._get_conn() as conn:
            # Query existing filenames in this batch
            fnames = [it["filename"] for it in items]
            placeholders = ",".join("?" for _ in fnames)
            cur = conn.execute(f"SELECT id, filename, is_downloaded FROM sound_catalog WHERE filename IN ({placeholders})", fnames)
            existing_map = {row["filename"]: (row["id"], row["is_downloaded"]) for row in cur.fetchall()}

            to_insert = []
            to_update = []

            for it in items:
                fname = it["filename"]
                genome_json = json.dumps(it.get("sonic_genome", {})) if isinstance(it.get("sonic_genome"), dict) else str(it.get("sonic_genome", "{}"))

                if fname in existing_map:
                    rec_id, is_dl = existing_map[fname]
                    to_update.append((
                        it.get("title", ""),
                        it.get("description", ""),
                        it.get("source_collection", self.source_name),
                        it.get("license", self.default_license),
                        it.get("creator_attribution", ""),
                        it.get("source_url", ""),
                        it.get("mirror_url"),
                        it.get("source_page_url"),
                        it.get("url_status", "unverified"),
                        it.get("tempo_bpm", 0.0),
                        it.get("key_tonality", ""),
                        it.get("wave_style", "general"),
                        it.get("exciter", ""),
                        it.get("resonator", ""),
                        it.get("action_type", ""),
                        it.get("dramatic_role", "general"),
                        it.get("voice_masking_risk", "LOW"),
                        it.get("whisper_compatibility", 0.5),
                        genome_json,
                        rec_id,
                    ))
                else:
                    vpath = it.get("filepath") or f"virtual/{self.source_name}/{fname}"
                    to_insert.append((
                        fname,
                        vpath,
                        it.get("title", ""),
                        it.get("description", ""),
                        it.get("category", "SFX"),
                        it.get("subcategory", "General"),
                        it.get("mood", "default"),
                        it.get("tags", ""),
                        float(it.get("duration_sec") or 0.0),
                        int(it.get("size_bytes") or 0),
                        it.get("format", ".mp3"),
                        it.get("source_collection", self.source_name),
                        it.get("source_url", ""),
                        it.get("mirror_url"),
                        it.get("source_page_url"),
                        it.get("url_status", "unverified"),
                        0,  # is_downloaded = 0 (virtual)
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
                added += len(to_insert)

            if to_update:
                conn.executemany("""
                    UPDATE sound_catalog
                    SET title = ?, description = ?, source_collection = ?, license = ?,
                        creator_attribution = ?, source_url = ?, mirror_url = ?, source_page_url = ?,
                        url_status = ?, tempo_bpm = ?, key_tonality = ?, wave_style = ?,
                        exciter = ?, resonator = ?, action_type = ?, dramatic_role = ?,
                        voice_masking_risk = ?, whisper_compatibility = ?, sonic_genome = ?
                    WHERE id = ?
                """, to_update)
                updated += len(to_update)

        return added, updated
