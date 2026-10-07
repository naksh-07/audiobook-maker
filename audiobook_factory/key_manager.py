import os
import re
import sys
import time
import random
import hashlib
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from zoneinfo import ZoneInfo
import contextlib

from audiobook_factory.guard_shield import (
    ModelQuotaProfile,
    resolve_model_profile,
    classify_universal_api_error,
    ApiErrorClassification,
    get_circuit_breaker,
)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "audiobooks" / "key_pool_state.db"


def _google_quota_date_str() -> str:
    """
    Google AI Studio resets daily quotas at Midnight US Pacific Time (PT).
    Uses IANA 'America/Los_Angeles' for automatic PDT/PST DST transitions,
    with a graceful fallback for environments lacking tzdata (e.g. Windows).
    """
    try:
        pacific_tz = ZoneInfo("America/Los_Angeles")
        pacific_now = datetime.now(pacific_tz)
    except Exception:
        # Fallback for Windows without tzdata package (approximate Pacific Time: UTC-7 PDT / UTC-8 PST)
        pacific_tz = timezone(timedelta(hours=-7))
        pacific_now = datetime.now(pacific_tz)
    return pacific_now.strftime("%Y-%m-%d")


def _utc_quota_date_str() -> str:
    """Standard UTC midnight rollover for OpenAI, Anthropic, Cerebras, Groq, OpenRouter."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_env_fallback():
    """Auto-load .env from project root if not already in os.environ."""
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        clean_v = v.strip().strip("'\"")
                        os.environ.setdefault(k.strip(), clean_v)
        except Exception:
            pass


_load_env_fallback()


def classify_gemini_error(status_code: int, error_body: str) -> Tuple[str, float, str]:
    """
    Backward-compatible facade wrapping classify_universal_api_error for Google Gemini.
    Returns: Tuple[category, wait_sec, message]
    """
    res = classify_universal_api_error(status_code=status_code, error_body=error_body, provider="gemini")
    return res.category, res.wait_sec, res.message


class AllKeysExhaustedTodayError(Exception):
    """Raised when all configured API keys have exhausted their daily quota for today."""
    pass


class PersistentKeyPool:
    """
    Gold Standard Thread-Safe Persistent Universal Key & Model Quota Pool.
    Guarantees:
    1. Multi-Provider & Multi-Model support: Gemini, OpenRouter, Cerebras, Groq, OpenAI, Anthropic, Local CUDA.
    2. Model-isolated quota ledger: Exhausting quota on one model (e.g. Gemini 2.5 Pro or TTS)
       does NOT block other models (e.g. Gemini 3.8 Flash, Flash-Lite) on the same key!
    3. Multi-timezone date rollovers (Midnight PT for Google, Midnight UTC for others).
    4. In-flight concurrency tracking preventing thread dogpiling on individual keys.
    5. Thread-safe SQLite ACID ledger with WAL mode and busy timeout.
    6. Jittered round-robin rotation favoring least-used and healthy keys.
    """

    def __init__(self, keys: Optional[List[str]] = None, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._init_db()

        # Load keys from environment if not explicitly passed
        if keys is not None:
            self.register_keys(keys, provider="gemini")
        else:
            self._auto_discover_and_register_env_keys()

    @contextlib.contextmanager
    def _connection(self):
        """Transaction-safe connection context manager that always closes file handles."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            # Base Key Ledger
            conn.execute("""
                CREATE TABLE IF NOT EXISTS key_quota_ledger (
                    key_hash TEXT PRIMARY KEY,
                    key_preview TEXT NOT NULL,
                    api_key TEXT NOT NULL,
                    status TEXT DEFAULT 'ACTIVE',       -- ACTIVE, EXHAUSTED_TODAY, TEMP_BACKOFF, INVALID
                    exhausted_date TEXT,                -- YYYY-MM-DD
                    total_calls_today INTEGER DEFAULT 0,
                    success_calls_today INTEGER DEFAULT 0,
                    failed_calls_today INTEGER DEFAULT 0,
                    last_used TIMESTAMP,
                    backoff_until TIMESTAMP,
                    last_error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_reset_date TEXT,
                    provider TEXT DEFAULT 'gemini',
                    in_flight INTEGER DEFAULT 0,
                    max_concurrency INTEGER DEFAULT 4
                );
            """)

            # Model-Specific Quota Ledger (Per key and per model isolation)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_quota_ledger (
                    key_hash TEXT,
                    provider TEXT DEFAULT 'gemini',
                    model TEXT NOT NULL,
                    status TEXT DEFAULT 'ACTIVE',       -- ACTIVE, EXHAUSTED_TODAY, TEMP_BACKOFF
                    exhausted_date TEXT,
                    total_calls_today INTEGER DEFAULT 0,
                    success_calls_today INTEGER DEFAULT 0,
                    failed_calls_today INTEGER DEFAULT 0,
                    total_tokens_today INTEGER DEFAULT 0,
                    last_used TIMESTAMP,
                    backoff_until TIMESTAMP,
                    last_error TEXT,
                    last_reset_date TEXT,
                    PRIMARY KEY (key_hash, model)
                );
            """)

            # Ensure columns exist if table was previously created with older schema
            columns = [col["name"] for col in conn.execute("PRAGMA table_info(key_quota_ledger);").fetchall()]
            if "success_calls_today" not in columns:
                conn.execute("ALTER TABLE key_quota_ledger ADD COLUMN success_calls_today INTEGER DEFAULT 0;")
            if "failed_calls_today" not in columns:
                conn.execute("ALTER TABLE key_quota_ledger ADD COLUMN failed_calls_today INTEGER DEFAULT 0;")
            if "last_reset_date" not in columns:
                conn.execute("ALTER TABLE key_quota_ledger ADD COLUMN last_reset_date TEXT;")
            if "provider" not in columns:
                conn.execute("ALTER TABLE key_quota_ledger ADD COLUMN provider TEXT DEFAULT 'gemini';")
            if "in_flight" not in columns:
                conn.execute("ALTER TABLE key_quota_ledger ADD COLUMN in_flight INTEGER DEFAULT 0;")
            if "max_concurrency" not in columns:
                conn.execute("ALTER TABLE key_quota_ledger ADD COLUMN max_concurrency INTEGER DEFAULT 4;")

            conn.commit()

    @staticmethod
    def _hash_key(api_key: str) -> str:
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _preview_key(api_key: str) -> str:
        if len(api_key) <= 14:
            return api_key
        return f"{api_key[:8]}...{api_key[-6:]}"

    @staticmethod
    def _today_str(provider: str = "gemini") -> str:
        if provider == "gemini":
            return _google_quota_date_str()
        return _utc_quota_date_str()

    def _auto_discover_and_register_env_keys(self):
        """Auto-discovers keys for all configured providers from environment."""
        provider_env_map = {
            "gemini": ["GEMINI_API_KEYS", "GEMINI_API_KEY", "GOOGLE_API_KEY"],
            "openrouter": ["OPENROUTER_API_KEYS", "OPENROUTER_API_KEY"],
            "cerebras": ["CEREBRAS_API_KEYS", "CEREBRAS_API_KEY"],
            "groq": ["GROQ_API_KEYS", "GROQ_API_KEY"],
            "openai": ["OPENAI_API_KEYS", "OPENAI_API_KEY"],
            "anthropic": ["ANTHROPIC_API_KEYS", "ANTHROPIC_API_KEY"],
            "elevenlabs": ["ELEVENLABS_API_KEYS", "ELEVENLABS_API_KEY"],
            "local": ["LOCAL_API_KEY"],
        }
        for provider, var_names in provider_env_map.items():
            found_keys: List[str] = []
            for var in var_names:
                val = os.environ.get(var, "")
                if val:
                    for k in val.split(","):
                        clean_k = k.strip()
                        if clean_k and clean_k not in found_keys:
                            found_keys.append(clean_k)
            if found_keys:
                self.register_keys(found_keys, provider=provider)

    def register_keys(self, keys: List[str], provider: str = "gemini"):
        """Register or sync API keys in persistent SQLite ledger without erasing existing quota history."""
        today = self._today_str(provider)
        with self.lock, self._connection() as conn:
            for k in keys:
                k = k.strip()
                if not k:
                    continue
                kh = self._hash_key(k)
                kp = self._preview_key(k)
                conn.execute("""
                    INSERT INTO key_quota_ledger (key_hash, key_preview, api_key, status, provider, last_reset_date)
                    VALUES (?, ?, ?, 'ACTIVE', ?, ?)
                    ON CONFLICT(key_hash) DO UPDATE SET
                        api_key = excluded.api_key,
                        key_preview = excluded.key_preview,
                        provider = excluded.provider;
                """, (kh, kp, k, provider, today))
            conn.commit()

    def _check_date_rollover(self, conn: sqlite3.Connection, provider: str = "gemini"):
        """Automatically re-activates keys whose exhausted_date is prior to today and resets daily counters."""
        today = self._today_str(provider)
        cursor = conn.execute("""
            UPDATE key_quota_ledger
            SET status = CASE WHEN status = 'EXHAUSTED_TODAY' THEN 'ACTIVE' ELSE status END,
                exhausted_date = NULL,
                total_calls_today = 0,
                success_calls_today = 0,
                failed_calls_today = 0,
                backoff_until = NULL,
                last_error = NULL,
                last_reset_date = ?
            WHERE (exhausted_date IS NOT NULL AND exhausted_date != ?)
               OR (last_reset_date IS NULL OR last_reset_date != ?);
        """, (today, today, today))

        # Also reset model quota ledger
        conn.execute("""
            UPDATE model_quota_ledger
            SET status = CASE WHEN status = 'EXHAUSTED_TODAY' THEN 'ACTIVE' ELSE status END,
                exhausted_date = NULL,
                total_calls_today = 0,
                success_calls_today = 0,
                failed_calls_today = 0,
                total_tokens_today = 0,
                backoff_until = NULL,
                last_error = NULL,
                last_reset_date = ?
            WHERE (exhausted_date IS NOT NULL AND exhausted_date != ?)
               OR (last_reset_date IS NULL OR last_reset_date != ?);
        """, (today, today, today))

        if cursor.rowcount > 0:
            from audiobook_factory.logger import logger
            logger.info(f"  [DATE ROLLOVER] Midnight passed for {provider}! Reset {cursor.rowcount} API keys to ACTIVE for {today}.")

    def get_key(self, service: str = "tts", provider: str = "gemini", model: Optional[str] = None) -> str:
        """
        Retrieves the next eligible API key using round-robin rotation.
        Supports:
        - service='tts': checks 'ACTIVE' status in key_quota_ledger.
        - service='text' with no model: selects valid keys not in active temp backoff.
        - model specified: checks both key validity and model-specific quota in model_quota_ledger!
          If key is exhausted on model A (e.g. Gemini 2.5 Pro or TTS), it can still be chosen for model B!
        - Balances load by lowest in-flight concurrency, oldest last_used, and fewest calls today.
        """
        while True:
            today = self._today_str(provider)
            now_ts = datetime.now().isoformat()
            sleep_dur = 0.0

            with self.lock:
                with self._connection() as conn:
                    self._check_date_rollover(conn, provider=provider)

                    # Clear expired temporary backoffs
                    conn.execute("""
                        UPDATE key_quota_ledger
                        SET status = 'ACTIVE', backoff_until = NULL
                        WHERE status = 'TEMP_BACKOFF' AND backoff_until <= ?;
                    """, (now_ts,))
                    conn.execute("""
                        UPDATE model_quota_ledger
                        SET status = 'ACTIVE', backoff_until = NULL
                        WHERE status = 'TEMP_BACKOFF' AND backoff_until <= ?;
                    """, (now_ts,))
                    conn.commit()

                    if model:
                        # Model-aware selection:
                        # For TTS, key MUST be ACTIVE in key_quota_ledger (exhausted_today keys cannot be used for TTS).
                        # For other services, key only needs to be != 'INVALID'.
                        is_tts_req = (service == "tts") or ("-tts" in model.lower())
                        key_status_clause = "k.status = 'ACTIVE'" if is_tts_req else "k.status != 'INVALID'"
                        query = f"""
                            SELECT k.api_key, k.key_preview, k.key_hash, k.in_flight
                            FROM key_quota_ledger k
                            LEFT JOIN model_quota_ledger m ON (k.key_hash = m.key_hash AND m.model = ?)
                            WHERE k.provider = ?
                              AND {key_status_clause}
                              AND (k.backoff_until IS NULL OR k.backoff_until <= ?)
                              AND (m.status IS NULL OR m.status = 'ACTIVE' OR (m.status = 'TEMP_BACKOFF' AND m.backoff_until <= ?))
                              AND (m.exhausted_date IS NULL OR m.exhausted_date != ?)
                            ORDER BY k.in_flight ASC, k.last_used ASC NULLS FIRST, k.success_calls_today ASC;
                        """
                        rows = conn.execute(query, (model, provider, now_ts, now_ts, today)).fetchall()
                    elif service == "tts":
                        # For TTS: only select ACTIVE keys (exhausted_today keys excluded)
                        rows = conn.execute("""
                            SELECT api_key, key_preview, key_hash, in_flight
                            FROM key_quota_ledger
                            WHERE provider = ? AND status = 'ACTIVE'
                            ORDER BY in_flight ASC, last_used ASC NULLS FIRST, success_calls_today ASC;
                        """, (provider,)).fetchall()
                    else:
                        # For Text (general): select valid keys not in active temp backoff
                        rows = conn.execute("""
                            SELECT api_key, key_preview, key_hash, in_flight
                            FROM key_quota_ledger
                            WHERE provider = ? AND status != 'INVALID' AND (backoff_until IS NULL OR backoff_until <= ?)
                            ORDER BY in_flight ASC, last_used ASC NULLS FIRST;
                        """, (provider, now_ts)).fetchall()

                    if rows:
                        chosen = rows[0]
                        conn.execute("""
                            UPDATE key_quota_ledger
                            SET last_used = CURRENT_TIMESTAMP,
                                total_calls_today = total_calls_today + 1
                            WHERE key_hash = ?;
                        """, (chosen["key_hash"],))
                        if model:
                            conn.execute("""
                                INSERT INTO model_quota_ledger (key_hash, provider, model, total_calls_today, last_used)
                                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                                ON CONFLICT(key_hash, model) DO UPDATE SET
                                    total_calls_today = total_calls_today + 1,
                                    last_used = CURRENT_TIMESTAMP;
                            """, (chosen["key_hash"], provider, model))
                        conn.commit()
                        return chosen["api_key"]

                    # Check if all keys exhausted today for TTS
                    if service == "tts" or (model and "-tts" in model.lower()):
                        exhausted_today = conn.execute("""
                            SELECT count(*) as count FROM key_quota_ledger
                            WHERE provider = ? AND status = 'EXHAUSTED_TODAY' AND exhausted_date = ?;
                        """, (provider, today)).fetchone()["count"]

                        total_valid = conn.execute("""
                            SELECT count(*) as count FROM key_quota_ledger
                            WHERE provider = ? AND status != 'INVALID';
                        """, (provider,)).fetchone()["count"]

                        if total_valid > 0 and exhausted_today >= total_valid:
                            raise AllKeysExhaustedTodayError(
                                f"All {total_valid} {provider.upper()} API keys have reached their daily TTS quota for date {today}. "
                                f"System is safely paused until midnight quota reset. (Text translation models remain usable)."
                            )

                    # Check if all keys exhausted today for this specific model
                    if model:
                        exhausted_model = conn.execute("""
                            SELECT count(*) as count FROM model_quota_ledger
                            WHERE provider = ? AND model = ? AND status = 'EXHAUSTED_TODAY' AND exhausted_date = ?;
                        """, (provider, model, today)).fetchone()["count"]

                        total_valid = conn.execute("""
                            SELECT count(*) as count FROM key_quota_ledger
                            WHERE provider = ? AND status != 'INVALID';
                        """, (provider,)).fetchone()["count"]

                        if total_valid > 0 and exhausted_model >= total_valid:
                            raise AllKeysExhaustedTodayError(
                                f"All {total_valid} {provider.upper()} API keys have reached their daily quota for model '{model}' on date {today}. "
                                f"System is safely paused until midnight quota reset."
                            )

                    # Check temp backoffs across key_quota_ledger and model_quota_ledger
                    if model:
                        temp_backoff_keys = conn.execute("""
                            SELECT backoff_until FROM (
                                SELECT backoff_until FROM key_quota_ledger
                                WHERE provider = ? AND status = 'TEMP_BACKOFF'
                                UNION ALL
                                SELECT backoff_until FROM model_quota_ledger
                                WHERE provider = ? AND model = ? AND status = 'TEMP_BACKOFF'
                            )
                            ORDER BY backoff_until ASC;
                        """, (provider, provider, model)).fetchall()
                    else:
                        temp_backoff_keys = conn.execute("""
                            SELECT backoff_until FROM key_quota_ledger
                            WHERE provider = ? AND status = 'TEMP_BACKOFF'
                            ORDER BY backoff_until ASC;
                        """, (provider,)).fetchall()

                    if temp_backoff_keys:
                        first_exp = temp_backoff_keys[0]["backoff_until"]
                        try:
                            exp_dt = datetime.fromisoformat(first_exp)
                            sleep_dur = max(1.0, min(20.0, (exp_dt - datetime.now()).total_seconds() + 0.5))
                        except Exception:
                            sleep_dur = 3.0

            if sleep_dur > 0:
                from audiobook_factory.logger import logger
                target_desc = f"{model} ({provider})" if model else f"{service.upper()} ({provider})"
                logger.info(f"  [KEY POOL] All active keys cooling down for {target_desc}. Waiting {sleep_dur:.1f}s...")
                time.sleep(sleep_dur)
                continue

            raise ValueError(f"No eligible {provider.upper()} API keys registered in key quota ledger.")

    @contextlib.contextmanager
    def lease_key(self, service: str = "text", provider: str = "gemini", model: Optional[str] = None):
        """Context manager leasing a key with active in-flight concurrency tracking."""
        key = self.get_key(service=service, provider=provider, model=model)
        kh = self._hash_key(key)
        with self.lock, self._connection() as conn:
            conn.execute("UPDATE key_quota_ledger SET in_flight = in_flight + 1 WHERE key_hash = ?;", (kh,))
            conn.commit()
        try:
            yield key
        finally:
            with self.lock, self._connection() as conn:
                conn.execute("UPDATE key_quota_ledger SET in_flight = MAX(0, in_flight - 1) WHERE key_hash = ?;", (kh,))
                conn.commit()

    def record_success(self, api_key: str, model: Optional[str] = None, provider: str = "gemini", tokens_used: int = 0):
        """Records a successful synthesis or generation call."""
        kh = self._hash_key(api_key)
        with self.lock, self._connection() as conn:
            conn.execute("""
                UPDATE key_quota_ledger
                SET status = CASE WHEN status = 'EXHAUSTED_TODAY' THEN status ELSE 'ACTIVE' END,
                    success_calls_today = success_calls_today + 1,
                    backoff_until = NULL,
                    last_error = NULL
                WHERE key_hash = ?;
            """, (kh,))
            if model:
                conn.execute("""
                    INSERT INTO model_quota_ledger (key_hash, provider, model, status, success_calls_today, total_tokens_today)
                    VALUES (?, ?, ?, 'ACTIVE', 1, ?)
                    ON CONFLICT(key_hash, model) DO UPDATE SET
                        status = 'ACTIVE',
                        success_calls_today = success_calls_today + 1,
                        total_tokens_today = total_tokens_today + excluded.total_tokens_today,
                        backoff_until = NULL,
                        last_error = NULL;
                """, (kh, provider, model, tokens_used))
            conn.commit()

        if model:
            get_circuit_breaker().record_success(provider, model)

    def mark_daily_quota_exhausted(self, api_key: str, error_msg: str, model: Optional[str] = None, provider: str = "gemini", service: str = ""):
        """
        Marks key as exhausted for today (e.g. 10 RPD reached on TTS).
        If model is specified and not TTS, only marks model_quota_ledger exhausted today!
        """
        from audiobook_factory.logger import logger
        today = self._today_str(provider)
        kh = self._hash_key(api_key)
        kp = self._preview_key(api_key)

        is_tts = (service == "tts") or (model is None) or ("-tts" in model.lower())

        with self.lock, self._connection() as conn:
            if is_tts:
                conn.execute("""
                    UPDATE key_quota_ledger
                    SET status = 'EXHAUSTED_TODAY',
                        exhausted_date = ?,
                        failed_calls_today = failed_calls_today + 1,
                        last_error = ?,
                        last_reset_date = ?
                    WHERE key_hash = ?;
                """, (today, error_msg[:200], today, kh))

            if model:
                conn.execute("""
                    INSERT INTO model_quota_ledger (key_hash, provider, model, status, exhausted_date, failed_calls_today, last_error, last_reset_date)
                    VALUES (?, ?, ?, 'EXHAUSTED_TODAY', ?, 1, ?, ?)
                    ON CONFLICT(key_hash, model) DO UPDATE SET
                        status = 'EXHAUSTED_TODAY',
                        exhausted_date = excluded.exhausted_date,
                        failed_calls_today = failed_calls_today + 1,
                        last_error = excluded.last_error,
                        last_reset_date = excluded.last_reset_date;
                """, (kh, provider, model, today, error_msg[:200], today))

            conn.commit()

            active_rem = conn.execute("""
                SELECT count(*) as count FROM key_quota_ledger WHERE provider = ? AND status = 'ACTIVE';
            """, (provider,)).fetchone()["count"]

            logger.warning(
                f"  [QUOTA LEDGER] Key {kp} marked EXHAUSTED_TODAY for date {today} (model={model or 'all'}). "
                f"Active keys remaining: {active_rem}"
            )

    def mark_temporary_backoff(self, api_key: str, backoff_seconds: float, error_msg: str = "", model: Optional[str] = None, provider: str = "gemini"):
        """Marks key for temporary backoff without burning it for the whole day."""
        from audiobook_factory.logger import logger
        kh = self._hash_key(api_key)
        kp = self._preview_key(api_key)
        backoff_until = datetime.fromtimestamp(time.time() + backoff_seconds).isoformat()

        with self.lock, self._connection() as conn:
            conn.execute("""
                UPDATE key_quota_ledger
                SET status = CASE WHEN status = 'EXHAUSTED_TODAY' THEN status ELSE 'TEMP_BACKOFF' END,
                    backoff_until = ?,
                    failed_calls_today = failed_calls_today + 1,
                    last_error = ?
                WHERE key_hash = ?;
            """, (backoff_until, error_msg[:200], kh))

            if model:
                conn.execute("""
                    INSERT INTO model_quota_ledger (key_hash, provider, model, status, backoff_until, failed_calls_today, last_error)
                    VALUES (?, ?, ?, 'TEMP_BACKOFF', ?, 1, ?)
                    ON CONFLICT(key_hash, model) DO UPDATE SET
                        status = CASE WHEN status = 'EXHAUSTED_TODAY' THEN status ELSE 'TEMP_BACKOFF' END,
                        backoff_until = excluded.backoff_until,
                        failed_calls_today = failed_calls_today + 1,
                        last_error = excluded.last_error;
                """, (kh, provider, model, backoff_until, error_msg[:200]))

            conn.commit()

            logger.warning(
                f"  [TEMP BACKOFF] Key {kp} cooling off for {backoff_seconds:.1f}s (model={model or 'key'})."
            )

        if model:
            get_circuit_breaker().record_failure(provider, model, error_msg)

    def mark_invalid(self, api_key: str, error_msg: str, provider: str = "gemini"):
        """Marks key as permanently invalid or disabled."""
        from audiobook_factory.logger import logger
        kh = self._hash_key(api_key)
        kp = self._preview_key(api_key)

        with self.lock, self._connection() as conn:
            conn.execute("""
                UPDATE key_quota_ledger
                SET status = 'INVALID',
                    last_error = ?
                WHERE key_hash = ?;
            """, (error_msg[:200], kh))
            conn.commit()

            logger.error(f"  [INVALID KEY] Key {kp} marked INVALID for {provider}: {error_msg[:100]}")

    def reset_all_for_today(self):
        """Force reset all keys and models back to ACTIVE state."""
        with self.lock, self._connection() as conn:
            conn.execute("""
                UPDATE key_quota_ledger
                SET status = 'ACTIVE',
                    exhausted_date = NULL,
                    backoff_until = NULL,
                    last_error = NULL;
            """)
            conn.execute("""
                UPDATE model_quota_ledger
                SET status = 'ACTIVE',
                    exhausted_date = NULL,
                    backoff_until = NULL,
                    last_error = NULL;
            """)
            conn.commit()
        get_circuit_breaker().force_reset()

    def get_status_summary(self, provider: str = "gemini") -> Dict[str, Any]:
        """Returns live statistics of all keys and models in the persistent ledger."""
        today = self._today_str(provider)
        with self.lock, self._connection() as conn:
            self._check_date_rollover(conn, provider=provider)
            rows = conn.execute("""
                SELECT key_preview, status, provider, exhausted_date, total_calls_today,
                       success_calls_today, failed_calls_today, last_used, backoff_until, in_flight, last_error
                FROM key_quota_ledger
                WHERE provider = ?
                ORDER BY key_preview ASC;
            """, (provider,)).fetchall()

            model_rows = conn.execute("""
                SELECT key_hash, model, status, total_calls_today, success_calls_today, total_tokens_today
                FROM model_quota_ledger
                WHERE provider = ?;
            """, (provider,)).fetchall()

            return {
                "date": today,
                "provider": provider,
                "total_keys": len(rows),
                "active_keys": sum(1 for r in rows if r["status"] == "ACTIVE"),
                "exhausted_today": sum(1 for r in rows if r["status"] == "EXHAUSTED_TODAY"),
                "temp_backoff": sum(1 for r in rows if r["status"] == "TEMP_BACKOFF"),
                "invalid_keys": sum(1 for r in rows if r["status"] == "INVALID"),
                "keys": [dict(r) for r in rows],
                "models": [dict(mr) for mr in model_rows]
            }


# Module singleton
_pool_instance: Optional[PersistentKeyPool] = None
_pool_lock = threading.Lock()


def get_persistent_key_pool() -> PersistentKeyPool:
    global _pool_instance
    if _pool_instance is None:
        with _pool_lock:
            if _pool_instance is None:
                _pool_instance = PersistentKeyPool()
    return _pool_instance
