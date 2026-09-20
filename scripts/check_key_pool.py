#!/usr/bin/env python3
"""
Audiobook Factory - Persistent Key Pool Management & Quota Telemetry CLI.
Provides real-time inspection, synchronization from .env, and status auditing.
"""

import os
import sys
import json
from pathlib import Path

# Configure Windows UTF-8 stdout
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Auto-load .env
env_file = ROOT_DIR / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

from audiobook_factory.key_manager import get_persistent_key_pool, PersistentKeyPool


def print_status():
    pool = get_persistent_key_pool()
    summary = pool.get_status_summary()

    print("\n" + "=" * 80)
    print(f"  AUDIOBOOK FACTORY - PERSISTENT KEY QUOTA TELEMETRY ({summary['date']})")
    print("=" * 80)
    print(f"  Total Registered Keys : {summary['total_keys']}")
    print(f"  Active Keys           : {summary['active_keys']}")
    print(f"  Exhausted Today (10RPD): {summary['exhausted_today']}")
    print(f"  In Temp Backoff       : {summary['temp_backoff']}")
    print(f"  Invalid / Disabled    : {summary.get('invalid_keys', 0)}")
    print("-" * 80)
    print(f"  {'KEY PREVIEW':<18} {'STATUS':<16} {'CALLS (S/F)':<14} {'EXHAUSTED DATE':<16} {'LAST ERROR'}")
    print("-" * 80)

    for k in summary["keys"]:
        preview = k["key_preview"]
        status = k["status"]
        success = k.get("success_calls_today", 0)
        failed = k.get("failed_calls_today", 0)
        calls = f"{success}/{failed}"
        ex_date = k.get("exhausted_date") or "-"
        err = (k.get("last_error") or "-")[:24]
        print(f"  {preview:<18} {status:<16} {calls:<14} {ex_date:<16} {err}")

    print("=" * 80 + "\n")


def sync_env():
    pool = get_persistent_key_pool()
    raw = os.environ.get("GEMINI_API_KEYS", "")
    if raw:
        keys = [k.strip() for k in raw.split(",") if k.strip()]
    else:
        single = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        keys = [single] if single else []

    pool.register_keys(keys)
    print(f"[+] Successfully synced {len(keys)} API keys from .env to SQLite ledger.")
    print_status()


def reset_pool():
    pool = get_persistent_key_pool()
    pool.reset_all_for_today()
    print("[+] All API keys reset to ACTIVE state.")
    print_status()


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "status":
        print_status()
    elif action == "sync":
        sync_env()
    elif action == "reset":
        reset_pool()
    else:
        print(f"Unknown action: {action}. Usage: python scripts/check_key_pool.py [status|sync|reset]")
