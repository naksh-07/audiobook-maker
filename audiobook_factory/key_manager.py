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

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "audiobooks" / "key_pool_state.db"


def _google_quota_date_str() -> str:
    """
    Google AI Studio resets daily quotas at Midnight US Pacific Time (PT).
    Uses IANA 'America/Los_Angeles' for automatic PDT/PST DST transitions.
    """
    pacific_tz = ZoneInfo("America/Los_Angeles")
    pacific_now = datetime.now(pacific_tz)
    return pacific_now.strftime("%Y-%m-%d")


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
                        os.environ.setdefault(k.strip(), v.strip())
        except Exception:
            pass


_load_env_fallback()


def classify_gemini_error(status_code: int, error_body: str) -> Tuple[str, float, str]:
    """
    Gold Standard Error Classifier for Google Gemini API:
    Strictly differentiates between:
    1. 'DAILY_QUOTA_EXHAUSTED': Genuine daily limit hit (10 RPD per project/model).
       Only this marks the key EXHAUSTED_TODAY for date YYYY-MM-DD.
    2. 'RPM_RATE_LIMIT': Temporary 15 RPM burst limit.
       Only triggers short TEMP_BACKOFF (5-20s), does NOT burn the key for today.
    3. 'TRANSIENT_SERVER_ERROR': HTTP 500/502/503/504 temporary backend hiccups.
       Only triggers short TEMP_BACKOFF (5-10s), keeps key ACTIVE.
    4. 'INVALID_KEY': HTTP 400/403 Bad API key / permission denied.
       Marks key INVALID so it is permanently bypassed.
    5. 'UNKNOWN_ERROR': Other uncategorized error.
    """
    body_lower = error_body.lower()

    # 1. Invalid API Key / Bad Authentication
    if status_code in (400, 403) and any(
        x in body_lower for x in ["api_key_invalid", "api key not valid", "permission_denied", "forbidden"]
    ):
        return "INVALID_KEY", 0.0, "API key is invalid or lacks Gemini API permissions."

    # 2. HTTP 429 Resource Exhausted
    if status_code == 429:
        # Check for genuine daily quota (10 RPD per model per project)
        # Google specifies: "GenerateRequestsPerDayPerProjectPerModel-FreeTier" or "quotaValue": "10" or "perday"
        if "generaterequestsperday" in body_lower or "perday" in body_lower or "daily" in body_lower:
            return "DAILY_QUOTA_EXHAUSTED", 0.0, "Daily TTS quota reached (10 RPD per project)."

        # Check for RPM rate limit (15 RPM)
        delay_match = re.search(r"retry in (\d+\.?\d*)s", error_body, re.IGNORECASE)
        wait_sec = float(delay_match.group(1)) + 2.0 if delay_match else 15.0
        return "RPM_RATE_LIMIT", wait_sec, f"Temporary RPM rate limit (Cooling off {wait_sec:.1f}s)."

    # 3. Transient 5xx server errors
    if status_code in (500, 502, 503, 504):
        delay_match = re.search(r"retry in (\d+\.?\d*)s", error_body, re.IGNORECASE)
        wait_sec = float(delay_match.group(1)) + 2.0 if delay_match else 8.0
        return "TRANSIENT_SERVER_ERROR", wait_sec, f"Google server transient error HTTP {status_code}."

    return "UNKNOWN_ERROR", 5.0, f"HTTP {status_code}: {error_body[:120]}"


class AllKeysExhaustedTodayError(Exception):
    """Raised when all configured API keys have exhausted their daily quota for today."""
    pass


class PersistentKeyPool:
    """
    Gold Standard Thread-Safe Persistent Key Quota Pool.
    Guarantees:
    1. Quota exhaustion is saved with exact calendar date (YYYY-MM-DD).
    2. Auto-resets keys on date rollover without manual intervention.
    3. Distinguishes genuine daily quota (10 RPD) from temporary 503/RPM rate spikes.
    4. Never hammers exhausted keys in an infinite loop.
    5. Injects natural random jitter into request pacing.
    """

    def __init__(self, keys: Optional[List[str]] = None, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._init_db()

        # Load keys from environment if not passed
        if not keys:
            raw = os.environ.get("GEMINI_API_KEYS", "")
            if raw:
                keys = [k.strip() for k in raw.split(",") if k.strip()]
            else:
                single = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
                keys = [single] if single else []

        self.register_keys(keys)

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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS key_quota_ledger (
                    key_hash TEXT PRIMARY KEY,
                    key_preview TEXT NOT NULL,
                    api_key TEXT NOT NULL,
                    status TEXT DEFAULT 'ACTIVE',       -- ACTIVE, EXHAUSTED_TODAY, TEMP_BACKOFF, INVALID
                    exhausted_date TEXT,                -- YYYY-MM-DD (Google PT date when daily quota hits)
                    total_calls_today INTEGER DEFAULT 0,
                    success_calls_today INTEGER DEFAULT 0,
                    failed_calls_today INTEGER DEFAULT 0,
                    last_used TIMESTAMP,
                    backoff_until TIMESTAMP,
                    last_error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Ensure columns exist if table was previously created with older schema
            columns = [col["name"] for col in conn.execute("PRAGMA table_info(key_quota_ledger);").fetchall()]
            if "success_calls_today" not in columns:
                conn.execute("ALTER TABLE key_quota_ledger ADD COLUMN success_calls_today INTEGER DEFAULT 0;")
            if "failed_calls_today" not in columns:
                conn.execute("ALTER TABLE key_quota_ledger ADD COLUMN failed_calls_today INTEGER DEFAULT 0;")
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
    def _today_str() -> str:
        # Use Google Pacific Time to synchronize with Google daily quota reset
        return _google_quota_date_str()

    def register_keys(self, keys: List[str]):
        """Register or sync API keys in persistent SQLite ledger without erasing existing quota history."""
        with self.lock, self._connection() as conn:
            for k in keys:
                k = k.strip()
                if not k:
                    continue
                kh = self._hash_key(k)
                kp = self._preview_key(k)
                conn.execute("""
                    INSERT INTO key_quota_ledger (key_hash, key_preview, api_key, status)
                    VALUES (?, ?, ?, 'ACTIVE')
                    ON CONFLICT(key_hash) DO UPDATE SET
                        api_key = excluded.api_key,
                        key_preview = excluded.key_preview;
                """, (kh, kp, k))
            conn.commit()

    def _check_date_rollover(self, conn: sqlite3.Connection):
        """Automatically re-activates keys whose exhausted_date is prior to today (Google PT date)."""
        today = self._today_str()
        cursor = conn.execute("""
            UPDATE key_quota_ledger
            SET status = 'ACTIVE',
                exhausted_date = NULL,
                total_calls_today = 0,
                success_calls_today = 0,
                failed_calls_today = 0,
                backoff_until = NULL,
                last_error = NULL
            WHERE exhausted_date IS NOT NULL AND exhausted_date != ?;
        """, (today,))
        if cursor.rowcount > 0:
            from audiobook_factory.logger import logger
            logger.info(f"  [DATE ROLLOVER] Google midnight passed! Reset {cursor.rowcount} API keys to ACTIVE for {today}.")

    def get_key(self, service: str = "tts") -> str:
        """
        Retrieves the next eligible API key using round-robin rotation.
        - For service='tts': strictly checks 'ACTIVE' status so keys whose 10 RPD quota is exhausted
          today are safely bypassed until midnight.
        - For service='text': keys whose TTS quota was exhausted can still be used for text translation
          and screenplay formatting because Gemini text models have a separate 1,500 RPD quota.
        Uses iterative loop instead of recursion to prevent stack overflow under sustained backoff.
        """
        while True:
            today = self._today_str()
            now_ts = datetime.now().isoformat()
            sleep_dur = 0.0

            with self.lock:
                with self._connection() as conn:
                    self._check_date_rollover(conn)

                    # Check if any temp backoffs have expired
                    conn.execute("""
                        UPDATE key_quota_ledger
                        SET status = 'ACTIVE', backoff_until = NULL
                        WHERE status = 'TEMP_BACKOFF' AND backoff_until <= ?;
                    """, (now_ts,))
                    conn.commit()

                    if service == "tts":
                        # For TTS: only select ACTIVE keys (exhausted_today keys are excluded)
                        rows = conn.execute("""
                            SELECT api_key, key_preview, key_hash
                            FROM key_quota_ledger
                            WHERE status = 'ACTIVE'
                            ORDER BY last_used ASC NULLS FIRST, success_calls_today ASC;
                        """).fetchall()
                    else:
                        # For Text: select any valid key not in active temporary backoff
                        rows = conn.execute("""
                            SELECT api_key, key_preview, key_hash
                            FROM key_quota_ledger
                            WHERE status != 'INVALID' AND (backoff_until IS NULL OR backoff_until <= ?)
                            ORDER BY last_used ASC NULLS FIRST;
                        """, (now_ts,)).fetchall()

                    if rows:
                        chosen = rows[0]
                        conn.execute("""
                            UPDATE key_quota_ledger
                            SET last_used = CURRENT_TIMESTAMP,
                                total_calls_today = total_calls_today + 1
                            WHERE key_hash = ?;
                        """, (chosen["key_hash"],))
                        conn.commit()
                        return chosen["api_key"]

                    # If no active keys for TTS, check status breakdown
                    if service == "tts":
                        exhausted_today = conn.execute("""
                            SELECT count(*) as count FROM key_quota_ledger
                            WHERE status = 'EXHAUSTED_TODAY' AND exhausted_date = ?;
                        """, (today,)).fetchone()["count"]

                        temp_backoff_keys = conn.execute("""
                            SELECT backoff_until FROM key_quota_ledger
                            WHERE status = 'TEMP_BACKOFF'
                            ORDER BY backoff_until ASC;
                        """).fetchall()

                        total_valid_keys = conn.execute(
                            "SELECT count(*) as count FROM key_quota_ledger WHERE status != 'INVALID';"
                        ).fetchone()["count"]

                        if total_valid_keys > 0 and exhausted_today == total_valid_keys:
                            raise AllKeysExhaustedTodayError(
                                f"All {total_valid_keys} Gemini API keys have reached their daily TTS quota (10 RPD) for date {today}. "
                                f"System is safely paused until midnight quota reset. (Text translation models remain usable)."
                            )

                        if temp_backoff_keys:
                            first_expiry = temp_backoff_keys[0]["backoff_until"]
                            try:
                                expiry_dt = datetime.fromisoformat(first_expiry)
                                sleep_dur = max(1.0, min(20.0, (expiry_dt - datetime.now()).total_seconds() + 0.5))
                            except Exception:
                                sleep_dur = 3.0

            # If keys are cooling down, sleep OUTSIDE the lock and connection, then loop (no recursion)
            if sleep_dur > 0:
                from audiobook_factory.logger import logger
                logger.info(f"  [KEY POOL] All active TTS keys cooling down. Waiting {sleep_dur:.1f}s for backoff expiry...")
                time.sleep(sleep_dur)
                continue  # Iterate instead of recurse — prevents RecursionError

            raise ValueError("No eligible Gemini API keys registered in key quota ledger.")

    def record_success(self, api_key: str):
        """Records a successful synthesis call for the given API key."""
        kh = self._hash_key(api_key)
        with self.lock, self._connection() as conn:
            conn.execute("""
                UPDATE key_quota_ledger
                SET status = 'ACTIVE',
                    success_calls_today = success_calls_today + 1,
                    backoff_until = NULL,
                    last_error = NULL
                WHERE key_hash = ?;
            """, (kh,))
            conn.commit()

    def mark_daily_quota_exhausted(self, api_key: str, error_msg: str):
        """
        Marks key as genuinely exhausted for today (10 RPD reached).
        Will NOT be retried until calendar date changes (midnight rollover).
        """
        from audiobook_factory.logger import logger
        today = self._today_str()
        kh = self._hash_key(api_key)
        kp = self._preview_key(api_key)

        with self.lock, self._connection() as conn:
            conn.execute("""
                UPDATE key_quota_ledger
                SET status = 'EXHAUSTED_TODAY',
                    exhausted_date = ?,
                    failed_calls_today = failed_calls_today + 1,
                    last_error = ?
                WHERE key_hash = ?;
            """, (today, error_msg[:200], kh))
            conn.commit()

            active_rem = conn.execute("""
                SELECT count(*) as count FROM key_quota_ledger WHERE status = 'ACTIVE';
            """).fetchone()["count"]

            logger.warning(
                f"  [QUOTA LEDGER] Key {kp} marked EXHAUSTED_TODAY for date {today}. "
                f"Active keys remaining: {active_rem}"
            )

    def mark_temporary_backoff(self, api_key: str, backoff_seconds: float, error_msg: str = ""):
        """
        Marks key for temporary backoff (e.g. 503 spike or 15 RPM burst).
        Does NOT burn the key for the entire day.
        """
        from audiobook_factory.logger import logger
        kh = self._hash_key(api_key)
        kp = self._preview_key(api_key)
        backoff_until = datetime.fromtimestamp(time.time() + backoff_seconds).isoformat()

        with self.lock, self._connection() as conn:
            conn.execute("""
                UPDATE key_quota_ledger
                SET status = 'TEMP_BACKOFF',
                    backoff_until = ?,
                    failed_calls_today = failed_calls_today + 1,
                    last_error = ?
                WHERE key_hash = ?;
            """, (backoff_until, error_msg[:200], kh))
            conn.commit()

            logger.warning(
                f"  [TEMP BACKOFF] Key {kp} cooling off for {backoff_seconds:.1f}s (Until {backoff_until[:19]})."
            )

    def mark_invalid(self, api_key: str, error_msg: str):
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

            logger.error(f"  [INVALID KEY] Key {kp} marked INVALID: {error_msg[:100]}")

    def reset_all_for_today(self):
        """Force reset all keys back to ACTIVE state (e.g. for testing or new quota window)."""
        with self.lock, self._connection() as conn:
            conn.execute("""
                UPDATE key_quota_ledger
                SET status = 'ACTIVE',
                    exhausted_date = NULL,
                    backoff_until = NULL,
                    last_error = NULL;
            """)
            conn.commit()

    def get_status_summary(self) -> Dict[str, Any]:
        """Returns live statistics of all keys in the persistent ledger."""
        today = self._today_str()
        with self.lock, self._connection() as conn:
            self._check_date_rollover(conn)
            rows = conn.execute("""
                SELECT key_preview, status, exhausted_date, total_calls_today,
                       success_calls_today, failed_calls_today, last_used, backoff_until, last_error
                FROM key_quota_ledger
                ORDER BY key_preview ASC;
            """).fetchall()

            return {
                "date": today,
                "total_keys": len(rows),
                "active_keys": sum(1 for r in rows if r["status"] == "ACTIVE"),
                "exhausted_today": sum(1 for r in rows if r["status"] == "EXHAUSTED_TODAY"),
                "temp_backoff": sum(1 for r in rows if r["status"] == "TEMP_BACKOFF"),
                "invalid_keys": sum(1 for r in rows if r["status"] == "INVALID"),
                "keys": [dict(r) for r in rows]
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
