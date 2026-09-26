#!/usr/bin/env python3
"""
Audiobook Factory - Sound Bank Bounded LRU Cache Manager.
=========================================================
Manages local audio file caching with strict capacity bounds,
active-render protection, and zero-bloat metadata preservation.

Core Invariants:
1. Hard capacity bound: Defaults to 1536 MB (1.5 GB), configurable via MAX_SOUND_BANK_CACHE_MB.
2. Protection hierarchy: ACTIVE_RENDER > CURRENT_CHAPTER > PINNED > NORMAL.
3. Metadata preservation: Eviction deletes the local audio file but leaves 100% of
   catalog metadata, Sonic Genome, and measured DSP facts intact in SQLite.
"""

from __future__ import annotations
import os
import shutil
import sqlite3
import contextlib
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Generator, Union, Tuple

from audiobook_factory.logger import logger

DEFAULT_MAX_CACHE_MB = 1536  # 1.5 GB default disk budget
DEFAULT_BANK_DIR = Path(__file__).resolve().parent.parent / "audiobooks" / "sound_bank"


class SoundBankCacheManager:
    """
    Thread-safe Bounded LRU Cache Manager for the Sound Bank.
    Guarantees zero disk bloat while protecting currently rendered audio stems.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        cache_dir: Optional[Path] = None,
        max_cache_mb: Optional[int] = None,
    ):
        self.bank_root = Path(cache_dir.parent if cache_dir else DEFAULT_BANK_DIR).resolve()
        self.cache_dir = Path(cache_dir or (self.bank_root / "cache")).resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path or (self.bank_root / "sound_bank.db")).resolve()

        env_max = os.environ.get("MAX_SOUND_BANK_CACHE_MB")
        if max_cache_mb is not None:
            self.max_cache_mb = max_cache_mb
        elif env_max and env_max.isdigit():
            self.max_cache_mb = int(env_max)
        else:
            self.max_cache_mb = DEFAULT_MAX_CACHE_MB

        self._lock = threading.RLock()
        self._recover_stale_active_renders()

    def _recover_stale_active_renders(self):
        """Self-heals any active_render pins left over from prior process crashes."""
        if not self.db_path.exists():
            return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    UPDATE sound_catalog
                    SET cache_pin_status = 'normal'
                    WHERE cache_pin_status = 'active_render'
                """)
        except Exception as e:
            logger.debug(f"Stale active render recovery skipped: {e}")

    @contextlib.contextmanager
    def _get_conn(self) -> Generator[sqlite3.Connection, None, None]:
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

    def get_disk_usage_bytes(self, fast: bool = False) -> int:
        """Calculates total bytes occupied by files in the cache directory."""
        if fast and self.db_path.exists():
            try:
                with self._get_conn() as conn:
                    row = conn.execute(
                        "SELECT COALESCE(SUM(size_bytes), 0) FROM sound_catalog WHERE is_downloaded = 1"
                    ).fetchone()
                    if row and row[0] is not None:
                        return int(row[0])
            except Exception:
                pass
        if not self.cache_dir.exists():
            return 0
        total = 0
        for root, _, files in os.walk(self.cache_dir):
            for f in files:
                p = Path(root) / f
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
        return total

    def get_cache_stats(self) -> Dict[str, Any]:
        """Returns comprehensive cache capacity, file counts, and virtual ledger stats."""
        with self._lock:
            disk_bytes = self.get_disk_usage_bytes()
            disk_mb = round(disk_bytes / (1024 * 1024), 2)
            utilization = round((disk_mb / self.max_cache_mb) * 100.0, 1) if self.max_cache_mb > 0 else 0.0

            total_virtual = 0
            total_downloaded = 0
            pinned_count = 0
            active_render_count = 0
            represented_sec = 0.0

            if self.db_path.exists():
                try:
                    with self._get_conn() as conn:
                        row = conn.execute("""
                            SELECT 
                                COUNT(*) as total_count,
                                SUM(CASE WHEN is_downloaded = 1 THEN 1 ELSE 0 END) as downloaded_count,
                                SUM(CASE WHEN cache_pin_status = 'pinned' THEN 1 ELSE 0 END) as pinned_cnt,
                                SUM(CASE WHEN cache_pin_status = 'active_render' THEN 1 ELSE 0 END) as active_cnt,
                                SUM(duration_sec) as total_duration
                            FROM sound_catalog
                        """).fetchone()
                        if row:
                            total_virtual = row["total_count"] or 0
                            total_downloaded = row["downloaded_count"] or 0
                            pinned_count = row["pinned_cnt"] or 0
                            active_render_count = row["active_cnt"] or 0
                            represented_sec = row["total_duration"] or 0.0
                except Exception as e:
                    logger.debug(f"Could not read sound_catalog stats for cache manager: {e}")

            return {
                "max_cache_mb": self.max_cache_mb,
                "max_size_mb": self.max_cache_mb,
                "used_cache_mb": disk_mb,
                "current_size_mb": disk_mb,
                "free_cache_mb": max(0.0, round(self.max_cache_mb - disk_mb, 2)),
                "utilization_percent": min(100.0, utilization),
                "utilization_pct": min(100.0, utilization),
                "is_over_budget": disk_mb > self.max_cache_mb,
                "downloaded_files_count": total_downloaded,
                "pinned_files_count": pinned_count,
                "active_render_files_count": active_render_count,
                "protected_files": pinned_count + active_render_count,
                "evictable_files": max(0, total_downloaded - (pinned_count + active_render_count)),
                "total_catalog_tracks": total_virtual,
                "represented_duration_hours": round(represented_sec / 3600.0, 1),
            }

    @contextlib.contextmanager
    def protect_active_render(self, asset_ids: List[int]) -> Generator[None, None, None]:
        """
        Context manager ensuring assets required by an active rendering pass
        are marked 'active_render' and are 100% immune to LRU eviction.
        """
        valid_ids = [int(aid) for aid in asset_ids if aid]
        if not valid_ids or not self.db_path.exists():
            yield
            return

        with self._lock:
            with self._get_conn() as conn:
                placeholders = ",".join("?" for _ in valid_ids)
                conn.execute(f"""
                    UPDATE sound_catalog
                    SET cache_pin_status = 'active_render', last_accessed_at = CURRENT_TIMESTAMP
                    WHERE id IN ({placeholders}) AND cache_pin_status != 'pinned'
                """, valid_ids)

        try:
            yield
        finally:
            with self._lock:
                with self._get_conn() as conn:
                    conn.execute(f"""
                        UPDATE sound_catalog
                        SET cache_pin_status = 'normal'
                        WHERE id IN ({placeholders}) AND cache_pin_status = 'active_render'
                    """, valid_ids)

    def pin_asset(self, asset_id: int, status: str = "pinned") -> bool:
        """Manually pins an asset to protect it from LRU eviction."""
        if not self.db_path.exists():
            return False
        with self._lock, self._get_conn() as conn:
            conn.execute("""
                UPDATE sound_catalog
                SET cache_pin_status = ?, last_accessed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, asset_id))
            return True

    def unpin_asset(self, asset_id: int) -> bool:
        """Restores an asset to normal evictable status."""
        return self.pin_asset(asset_id, status="normal")

    def prune_to_budget(self, target_mb: Optional[float] = None) -> Tuple[int, int]:
        """
        Convenience method that prunes to target budget and returns:
        (freed_bytes, evicted_count).
        """
        res = self.prune_lru(target_mb=target_mb)
        freed_bytes = int(res.get("freed_mb", 0.0) * 1024 * 1024)
        return freed_bytes, res.get("evicted_count", 0)

    def prune_lru(self, target_mb: Optional[float] = None) -> Dict[str, Any]:
        """
        Prunes least-recently-used (LRU) files until total cached size <= target_mb.
        CRITICAL INVARIANT: Deletes local file, sets is_downloaded = 0, filepath = NULL,
        but strictly leaves all Sonic Genome & DSP metadata intact.
        """
        limit_mb = target_mb if target_mb is not None else float(self.max_cache_mb)
        stats = {
            "evicted_count": 0,
            "freed_mb": 0.0,
            "initial_mb": 0.0,
            "final_mb": 0.0,
        }

        with self._lock:
            initial_bytes = self.get_disk_usage_bytes()
            stats["initial_mb"] = round(initial_bytes / (1024 * 1024), 2)

            if stats["initial_mb"] <= limit_mb or not self.db_path.exists():
                stats["final_mb"] = stats["initial_mb"]
                return stats

            with self._get_conn() as conn:
                # Query candidate evictable tracks (ordered oldest accessed first)
                cur = conn.execute("""
                    SELECT id, filename, filepath, size_bytes
                    FROM sound_catalog
                    WHERE is_downloaded = 1
                      AND cache_pin_status = 'normal'
                    ORDER BY last_accessed_at ASC, id ASC
                """)
                candidates = cur.fetchall()

                current_bytes = initial_bytes
                target_bytes = int(limit_mb * 1024 * 1024)

                for row in candidates:
                    if current_bytes <= target_bytes:
                        break

                    track_id = row["id"]
                    fp_str = row["filepath"]
                    fpath = Path(fp_str) if fp_str else None

                    file_size = 0
                    if fpath:
                        try:
                            if fpath.exists():
                                file_size = fpath.stat().st_size
                                fpath.unlink(missing_ok=True)
                        except OSError as e:
                            logger.warning(f"Failed to unlink evicted cache file {fpath}: {e}")

                    # Reset local download status in database while keeping all Sonic Genome metadata!
                    conn.execute("""
                        UPDATE sound_catalog
                        SET is_downloaded = 0, filepath = NULL
                        WHERE id = ?
                    """, (track_id,))

                    current_bytes -= file_size
                    stats["evicted_count"] += 1
                    stats["freed_mb"] += round(file_size / (1024 * 1024), 2)

            final_bytes = self.get_disk_usage_bytes()
            stats["final_mb"] = round(final_bytes / (1024 * 1024), 2)
            logger.info(
                f"[+] LRU Cache Pruned: Evicted {stats['evicted_count']} files, "
                f"freed {stats['freed_mb']:.1f} MB (Cache: {stats['final_mb']:.1f} / {self.max_cache_mb} MB)"
            )
            return stats
