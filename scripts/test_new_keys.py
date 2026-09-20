#!/usr/bin/env python3
"""
Audiobook Factory - Gemini API Key TTS Validator CLI.

Tests candidate Google AI Studio / Gemini API keys against the Gemini 3.1 Flash TTS
endpoint (gemini-3.1-flash-tts-preview) to verify active authorization and audio generation access.

Usage:
  # 1. From command-line arguments:
  python scripts/test_new_keys.py YOUR_KEY_1 YOUR_KEY_2

  # 2. From a file (one key per line):
  python scripts/test_new_keys.py --file my_keys.txt

  # 3. From default staging file (audiobooks/keys_staging.txt or candidate_keys.txt):
  python scripts/test_new_keys.py

  # 4. From current .env keys:
  python scripts/test_new_keys.py --env

  # 5. Piped from stdin:
  cat my_keys.txt | python scripts/test_new_keys.py -
"""

import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_STAGING_PATHS = [
    ROOT_DIR / "audiobooks" / "keys_staging.txt",
    ROOT_DIR / "candidate_keys.txt",
    ROOT_DIR / "keys_staging.txt",
]


def preview(key: str) -> str:
    """Format key into safe masked preview (e.g. KEY_HEAD...TAIL)."""
    if not key:
        return "<empty>"
    if len(key) <= 14:
        return key[:4] + "..." + key[-4:]
    return f"{key[:8]}...{key[-6:]}"


def test_key_tts_access(key: str, timeout: float = 15.0) -> Tuple[str, str, float]:
    """
    Test candidate key against Gemini TTS model endpoint.
    Returns (status, message, latency_seconds).
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-tts-preview?key={key}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "google-genai-sdk-python/0.8.3 gl-python/3.11.9 (windows/10.0.26100)",
            "x-goog-api-client": "gl-python/3.11.9 gax/2.24.0 gccl/0.8.3",
        },
        method="GET"
    )
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed = time.time() - start
            return "VALID", "OK", elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        err = e.read().decode("utf-8", errors="ignore")
        if e.code in (400, 403):
            return "INVALID", f"HTTP {e.code}: Forbidden / Invalid Key", elapsed
        elif e.code == 404:
            return "NO_TTS_ACCESS", "Model not accessible or not found", elapsed
        elif e.code == 429:
            return "RATE_LIMITED", "429 Rate Limit Exceeded", elapsed
        else:
            return "HTTP_ERROR", f"HTTP {e.code}", elapsed
    except Exception as e:
        elapsed = time.time() - start
        return "ERROR", str(e)[:50], elapsed


def load_keys_from_env() -> List[str]:
    """Load keys currently present in .env file."""
    env_file = ROOT_DIR / ".env"
    if not env_file.exists():
        return []
    keys = []
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("GEMINI_API_KEYS="):
                val = line.split("=", 1)[1].strip()
                keys.extend([k.strip() for k in val.split(",") if k.strip()])
            elif (line.startswith("GEMINI_API_KEY=") or line.startswith("GOOGLE_API_KEY=")) and not keys:
                val = line.split("=", 1)[1].strip()
                if val:
                    keys.append(val)
    return list(dict.fromkeys(keys))


def collect_candidate_keys(args: argparse.Namespace) -> List[str]:
    """Gather candidate keys from CLI arguments, flags, files, stdin, or interactive prompt."""
    raw_keys: List[str] = []

    # 1. Direct arguments
    if args.keys:
        if args.keys == ["-"]:
            # Stdin mode
            for line in sys.stdin:
                raw_keys.extend(line.strip().replace(",", " ").split())
        else:
            for item in args.keys:
                raw_keys.extend(item.replace(",", " ").split())

    # 2. Specific file flag
    elif args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"[!] Error: Specified key file does not exist: {file_path}")
            sys.exit(1)
        for line in file_path.read_text(encoding="utf-8").splitlines():
            raw_keys.extend(line.strip().replace(",", " ").split())

    # 3. Read from current .env
    elif args.env:
        raw_keys = load_keys_from_env()

    # 4. Default staging files
    else:
        for staging in DEFAULT_STAGING_PATHS:
            if staging.exists() and staging.stat().st_size > 0:
                print(f"[*] Reading candidate keys from local staging file: {staging.name}")
                for line in staging.read_text(encoding="utf-8").splitlines():
                    raw_keys.extend(line.strip().replace(",", " ").split())
                break

    # 5. Interactive paste fallback
    if not raw_keys:
        if sys.stdin.isatty():
            print("\nPaste candidate API keys below (one per line, press Enter twice or Ctrl+Z to finish):")
            try:
                while True:
                    line = input().strip()
                    if not line:
                        break
                    raw_keys.extend(line.replace(",", " ").split())
            except EOFError:
                pass
        else:
            # Piped stdin without '-'
            for line in sys.stdin:
                raw_keys.extend(line.strip().replace(",", " ").split())

    # Deduplicate while preserving order, remove comments/blanks
    cleaned = []
    seen = set()
    for k in raw_keys:
        k = k.strip().strip("'\"")
        if k and not k.startswith("#") and len(k) > 15 and k not in seen:
            seen.add(k)
            cleaned.append(k)

    return cleaned


def main():
    parser = argparse.ArgumentParser(description="Test Gemini API keys for working TTS endpoint access.")
    parser.add_argument("keys", nargs="*", help="API keys to test, or '-' for stdin.")
    parser.add_argument("-f", "--file", type=str, help="Path to text file containing keys (one per line).")
    parser.add_argument("-e", "--env", action="store_true", help="Test keys currently loaded in .env file.")
    parser.add_argument("-o", "--output", type=str, help="Save verified valid keys to output file.")
    args = parser.parse_args()

    candidate_keys = collect_candidate_keys(args)
    if not candidate_keys:
        print("[!] No candidate keys provided.")
        print("    Usage: python scripts/test_new_keys.py KEY1 KEY2 ...")
        print("       or: python scripts/test_new_keys.py --file keys.txt")
        print("       or: place keys in audiobooks/keys_staging.txt")
        sys.exit(0)

    print("=" * 80)
    print(f"  AUDIOBOOK FACTORY - GEMINI TTS KEY VALIDATOR")
    print(f"  Testing {len(candidate_keys)} candidate key(s) against gemini-3.1-flash-tts-preview...")
    print("=" * 80)
    print(f"  {'#':<4} {'KEY PREVIEW':<18} {'STATUS':<16} {'LATENCY':<10} {'DETAILS'}")
    print("-" * 80)

    results = {}
    for idx, key in enumerate(candidate_keys, 1):
        status, msg, latency = test_key_tts_access(key)
        results[key] = (status, msg, latency)
        p = preview(key)
        lat_str = f"{latency:.2f}s"
        print(f"  {idx:<4} {p:<18} {status:<16} {lat_str:<10} {msg}")

    valid_keys = [k for k, (st, _, _) in results.items() if st == "VALID"]

    print("=" * 80)
    print(f"  SUMMARY: {len(valid_keys)} Valid / {len(candidate_keys)} Tested ({len(candidate_keys) - len(valid_keys)} Failed)")
    print("=" * 80 + "\n")

    if args.output and valid_keys:
        out_p = Path(args.output)
        out_p.write_text("\n".join(valid_keys) + "\n", encoding="utf-8")
        print(f"[+] Saved {len(valid_keys)} valid keys to: {out_p}")


if __name__ == "__main__":
    main()
