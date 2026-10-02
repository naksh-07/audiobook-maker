#!/usr/bin/env python3
"""
Audiobook Factory - Sound Bank Virtual Asset Downloader.
Handles JIT downloading, atomic streaming verification, mirror fallbacks,
thread synchronization, and cache LRU management.
"""

from __future__ import annotations
import errno
import shutil
import threading
import time
import urllib.request
import urllib.error
import uuid
from pathlib import Path
from typing import Dict, Optional

from audiobook_factory.logger import logger


class DownloaderMixin:
    """Thread-safe virtual asset streaming and cache management mixin."""

    bank_root: Path
    cache_dir: Path
    cache_manager: Any

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
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT filename, category, source_url, mirror_url, url_status FROM sound_catalog WHERE id = ?",
                (sound_id,)
            ).fetchone()
            if row:
                if row["url_status"] == "broken":
                    return None
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

        with DownloaderMixin._get_asset_download_lock(sound_id):
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
                        with urllib.request.urlopen(req, timeout=5.0) as resp:
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
                    except urllib.error.HTTPError as e:
                        last_err = e
                        if temp_path.exists():
                            try:
                                temp_path.unlink(missing_ok=True)
                            except Exception:
                                pass
                        if e.code in (400, 401, 403, 404, 410, 500, 502, 503):
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
