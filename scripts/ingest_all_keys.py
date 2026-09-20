#!/usr/bin/env python3
"""
Audiobook Factory - Gemini API Key Ingestion & Pool Registration CLI.

Collects, validates, deduplicates, and ingests Gemini API keys into:
1. .env file (GEMINI_API_KEYS comma-separated variable)
2. Persistent SQLite ledger (audiobooks/key_pool_state.db)

Usage:
  # 1. From command-line arguments:
  python scripts/ingest_all_keys.py YOUR_KEY_1 YOUR_KEY_2

  # 2. From a file (one key per line):
  python scripts/ingest_all_keys.py --file candidate_keys.txt

  # 3. From default staging file (audiobooks/keys_staging.txt):
  python scripts/ingest_all_keys.py

  # 4. Skip network validation test (fast merge):
  python scripts/ingest_all_keys.py --file keys.txt --skip-test
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from audiobook_factory.key_manager import get_persistent_key_pool
from scripts.test_new_keys import (
    collect_candidate_keys,
    test_key_tts_access,
    preview,
    load_keys_from_env,
)


def update_env_file(new_keys: List[str], env_path: Path) -> int:
    """Update GEMINI_API_KEYS in .env while preserving formatting and other configs."""
    if not env_path.exists():
        env_path.write_text(f"GEMINI_API_KEYS={','.join(new_keys)}\n", encoding="utf-8")
        return len(new_keys)

    content = env_path.read_text(encoding="utf-8")
    joined = ",".join(new_keys)

    if re.search(r"^GEMINI_API_KEYS=.*$", content, flags=re.MULTILINE):
        new_content = re.sub(
            r"^GEMINI_API_KEYS=.*$",
            f"GEMINI_API_KEYS={joined}",
            content,
            flags=re.MULTILINE
        )
    else:
        new_content = content.rstrip() + f"\nGEMINI_API_KEYS={joined}\n"

    # Also ensure primary GEMINI_API_KEY is set if missing or empty
    if new_keys and not re.search(r"^GEMINI_API_KEY=.+$", new_content, flags=re.MULTILINE):
        new_content = f"GEMINI_API_KEY={new_keys[0]}\n" + new_content

    env_path.write_text(new_content, encoding="utf-8")
    return len(new_keys)


def main():
    parser = argparse.ArgumentParser(description="Ingest and register Gemini API keys into .env and SQLite pool.")
    parser.add_argument("keys", nargs="*", help="API keys to ingest, or '-' for stdin.")
    parser.add_argument("-f", "--file", type=str, help="Path to text file containing candidate keys.")
    parser.add_argument("-e", "--env", action="store_true", help="Sync existing keys from .env directly into SQLite.")
    parser.add_argument("--skip-test", action="store_true", help="Skip Gemini TTS validation test before ingestion.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate ingestion without writing to disk or database.")
    args = parser.parse_args()

    env_path = ROOT_DIR / ".env"
    existing_keys = load_keys_from_env()

    # If --env was specified, simply re-sync existing keys
    if args.env:
        candidate_keys = []
    else:
        candidate_keys = collect_candidate_keys(args)

    print("=" * 80)
    print("  AUDIOBOOK FACTORY - KEY POOL INGESTION & LEDGER SYNC")
    print("=" * 80)
    print(f"  Existing keys in .env: {len(existing_keys)}")

    # Filter out keys already present
    new_candidates = [k for k in candidate_keys if k not in existing_keys]
    print(f"  New candidate keys to ingest: {len(new_candidates)} (Total input: {len(candidate_keys)})")

    if not new_candidates and not args.env:
        if candidate_keys:
            print("[+] All provided candidate keys are already present in .env! Nothing to add.")
        else:
            print("[!] No candidate keys provided to ingest.")
            print("    Usage: python scripts/ingest_all_keys.py KEY1 KEY2 ...")
            print("       or: python scripts/ingest_all_keys.py --file candidate_keys.txt")
        sys.exit(0)

    # Validate new candidates against Gemini TTS endpoint
    valid_new_keys: List[str] = []
    if new_candidates:
        if args.skip_test:
            print("[*] Skipping network validation (--skip-test enabled).")
            valid_new_keys = new_candidates
        else:
            print("\n[*] Validating new candidate keys against Gemini TTS endpoint...")
            for idx, key in enumerate(new_candidates, 1):
                status, msg, lat = test_key_tts_access(key)
                p = preview(key)
                if status == "VALID":
                    valid_new_keys.append(key)
                    print(f"  [{idx:02d}/{len(new_candidates)}] {p:<18} -> VALID (OK, {lat:.2f}s)")
                else:
                    print(f"  [{idx:02d}/{len(new_candidates)}] {p:<18} -> {status} ({msg}) [DISCARDED]")

            print(f"[*] Validation complete: {len(valid_new_keys)} valid / {len(new_candidates)} candidate keys.")

    # Combine existing + new valid keys
    combined = list(dict.fromkeys(existing_keys + valid_new_keys))

    if args.dry_run:
        print("\n[DRY RUN] Simulation complete. No changes made.")
        print(f"  Would have resulted in {len(combined)} total active keys.")
        sys.exit(0)

    # 1. Update .env
    if valid_new_keys:
        update_env_file(combined, env_path)
        print(f"\n[+] Updated {env_path.name}: {len(combined)} keys registered ({len(valid_new_keys)} new added).")

    # 2. Register into SQLite PersistentKeyPool
    pool = get_persistent_key_pool()
    pool.register_keys(combined)
    print(f"[+] Synced {len(combined)} keys into SQLite key pool ({pool.db_path.name}).")

    # Print summary
    summary = pool.get_status_summary()
    print("-" * 80)
    print(f"  Total Keys in Ledger: {summary['total_keys']}")
    print(f"  Active Today (10RPD): {summary['active_keys']}")
    print(f"  Daily Quota Capacity: {summary['active_keys'] * 10} TTS Requests / Day")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
