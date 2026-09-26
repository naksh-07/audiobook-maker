#!/usr/bin/env python3
"""
Sonic Query Embedding Cache (Phase 3).
=====================================
Thread-safe, bounded LRU cache for 512-d normalized CLAP text query embeddings.
Keys account for:
- normalized text query
- model_id
- model_version
- preprocessing_version

Prevents redundant neural inference across repeated queries and batch chapter runs.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple, Union
from pathlib import Path
import numpy as np

from audiobook_factory.logger import logger


class QueryEmbeddingCache:
    """
    Thread-safe, high-speed LRU and SQLite-backed query embedding cache.
    """

    def __init__(
        self,
        max_memory_entries: Union[int, Path, str, Any] = 1000,
        db_path: Optional[Any] = None,
    ):
        # Support both signatures:
        # QueryEmbeddingCache(max_memory_entries=1000, db_path=path)
        # QueryEmbeddingCache(db_path_or_conn_factory, max_memory_entries=1000)
        self._conn_factory = None
        if isinstance(max_memory_entries, (Path, str)) or callable(max_memory_entries):
            passed_db = max_memory_entries
            actual_max_mem = db_path if isinstance(db_path, int) else 1000
            db_path = passed_db
            max_memory_entries = actual_max_mem

        self.max_memory_entries = int(max_memory_entries) if isinstance(max_memory_entries, (int, float)) else 1000

        if callable(db_path):
            self._conn_factory = db_path
            self.db_path = None
        elif db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = None

        self._lock = threading.RLock()
        self._memory_cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
        }
        self._init_db_table()

    def _get_db_conn(self):
        """Returns database connection or context manager if configured."""
        if self._conn_factory is not None:
            return self._conn_factory()
        elif self.db_path is not None:
            return sqlite3.connect(str(self.db_path), timeout=10.0)
        return None

    def _init_db_table(self) -> None:
        """Initializes persistent SQLite table if db is provided."""
        conn_cm = self._get_db_conn()
        if not conn_cm:
            return
        try:
            with conn_cm as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS query_embedding_cache (
                        cache_key TEXT PRIMARY KEY,
                        normalized_query TEXT NOT NULL,
                        model_id TEXT NOT NULL,
                        model_version TEXT NOT NULL,
                        preprocessing_version TEXT NOT NULL,
                        embedding_dim INTEGER NOT NULL,
                        embedding_bytes BLOB NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                if hasattr(conn, "commit"):
                    conn.commit()
        except Exception as e:
            logger.debug(f"QueryEmbeddingCache db initialization warning: {e}")

    @staticmethod
    def compute_cache_key(
        normalized_query: str,
        model_id: str,
        model_version: str,
        preprocessing_version: str = "v1",
    ) -> str:
        """
        Computes deterministic SHA-256 cache key based on query text and model specifications.
        """
        raw_key = f"{normalized_query.strip().lower()}:{model_id}:{model_version}:{preprocessing_version}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def get(
        self,
        normalized_query: str,
        model_id: str,
        model_version: str,
        preprocessing_version: str = "v1",
    ) -> Optional[np.ndarray]:
        """
        Retrieves cached 512-d float32 vector if present in memory or disk.
        """
        cache_key = self.compute_cache_key(normalized_query, model_id, model_version, preprocessing_version)

        with self._lock:
            # 1. Memory check (O(1))
            if cache_key in self._memory_cache:
                self._memory_cache.move_to_end(cache_key)
                self._stats["hits"] += 1
                return self._memory_cache[cache_key].copy()

        # 2. SQLite disk check
        conn_cm = self._get_db_conn()
        if conn_cm:
            try:
                with conn_cm as conn:
                    row = conn.execute(
                        "SELECT embedding_bytes FROM query_embedding_cache WHERE cache_key = ?",
                        (cache_key,)
                    ).fetchone()
                    if row and row[0]:
                        vec = np.frombuffer(row[0], dtype=np.float32).copy()
                        # Promote to memory
                        with self._lock:
                            self._put_memory(cache_key, vec)
                            self._stats["hits"] += 1
                        return vec
            except Exception as e:
                logger.debug(f"QueryEmbeddingCache sqlite read warning: {e}")

        with self._lock:
            self._stats["misses"] += 1
        return None

    def put(
        self,
        normalized_query: str,
        model_id: str,
        model_version: str,
        vector: np.ndarray,
        preprocessing_version: str = "v1",
    ) -> None:
        """
        Stores computed float32 vector in memory and persistent SQLite store.
        """
        if vector is None or vector.size == 0:
            return

        cache_key = self.compute_cache_key(normalized_query, model_id, model_version, preprocessing_version)
        vec_copy = vector.astype(np.float32).copy()

        with self._lock:
            self._put_memory(cache_key, vec_copy)

        # Persist to SQLite
        conn_cm = self._get_db_conn()
        if conn_cm:
            try:
                with conn_cm as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO query_embedding_cache (
                            cache_key, normalized_query, model_id, model_version,
                            preprocessing_version, embedding_dim, embedding_bytes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        cache_key,
                        normalized_query.strip().lower(),
                        model_id,
                        model_version,
                        preprocessing_version,
                        int(len(vec_copy)),
                        vec_copy.tobytes(),
                    ))
                    if hasattr(conn, "commit"):
                        conn.commit()
            except Exception as e:
                logger.debug(f"QueryEmbeddingCache sqlite write warning: {e}")

    def get_or_compute(
        self,
        normalized_query: str,
        compute_fn: Any,
        model_id: str = "laion/clap-htsat-unfused",
        model_version: str = "2023",
        preprocessing_version: str = "v1",
    ) -> np.ndarray:
        """
        Thread-safe get-or-compute wrapper: retrieves vector from cache,
        or computes via compute_fn(normalized_query) and stores it.
        """
        cached = self.get(normalized_query, model_id, model_version, preprocessing_version)
        if cached is not None:
            return cached

        with self._lock:
            # Double check memory cache inside lock
            cache_key = self.compute_cache_key(normalized_query, model_id, model_version, preprocessing_version)
            if cache_key in self._memory_cache:
                self._memory_cache.move_to_end(cache_key)
                self._stats["hits"] += 1
                return self._memory_cache[cache_key].copy()

            res = compute_fn(normalized_query)
            if isinstance(res, tuple):
                vec = res[0]
            else:
                vec = res

            if isinstance(vec, np.ndarray):
                vec = vec.astype(np.float32)

            self.put(normalized_query, model_id, model_version, vec, preprocessing_version)
            return vec

    def _put_memory(self, cache_key: str, vector: np.ndarray) -> None:
        """Internal helper to insert into memory cache with LRU eviction."""
        if cache_key in self._memory_cache:
            self._memory_cache.move_to_end(cache_key)
        else:
            if len(self._memory_cache) >= self.max_memory_entries:
                self._memory_cache.popitem(last=False)
                self._stats["evictions"] += 1
            self._memory_cache[cache_key] = vector

    def stats(self) -> Dict[str, Any]:
        """Returns cache telemetry and hit ratio."""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_ratio = round(self._stats["hits"] / total, 3) if total > 0 else 0.0
            return {
                "memory_entries": len(self._memory_cache),
                "max_memory_entries": self.max_memory_entries,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "evictions": self._stats["evictions"],
                "hit_ratio": hit_ratio,
            }

    def clear(self) -> None:
        """Clears memory and persistent cache."""
        with self._lock:
            self._memory_cache.clear()
            self._stats = {"hits": 0, "misses": 0, "evictions": 0}
        if self.db_path and self.db_path.exists():
            try:
                with sqlite3.connect(str(self.db_path), timeout=5.0) as conn:
                    conn.execute("DELETE FROM query_embedding_cache;")
                    conn.commit()
            except Exception:
                pass


_GLOBAL_QUERY_CACHE: Optional[QueryEmbeddingCache] = None


def get_query_embedding_cache(db_path: Optional[Path] = None) -> QueryEmbeddingCache:
    """Singleton accessor for query embedding cache."""
    global _GLOBAL_QUERY_CACHE
    if _GLOBAL_QUERY_CACHE is None:
        _GLOBAL_QUERY_CACHE = QueryEmbeddingCache(db_path=db_path)
    return _GLOBAL_QUERY_CACHE
