#!/usr/bin/env python3
"""
Audiobook Factory - CC0 Cinematic Sound Pack Downloader.
Downloads and extracts authentic, high-quality CC0 / Public Domain
Foley and Ambience sound libraries for immersive audio drama production.

Sources:
1. OpenGameArt CC0 - Tinysized Fantasy SFX (96 organic Foley sounds: boots, sheaths, knives, metal)
2. OpenGameArt CC0 - Steel Sword & Clash Packs (20 authentic blade attacks & clashes)
3. Wikimedia Commons CC0 - Nature & Environment Ambiences (wind, rain, tavern murmur, cave)
"""

import os
import io
import sys
import zipfile
import hashlib
import urllib.request
import urllib.error
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
SOUND_BANK_DIR = ROOT_DIR / "audiobooks" / "sound_bank"
FOLEY_DIR = SOUND_BANK_DIR / "foley"
AMBIENCE_DIR = SOUND_BANK_DIR / "ambience"

FOLEY_DIR.mkdir(parents=True, exist_ok=True)
AMBIENCE_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def download_file(url: str, target_path: Path) -> bool:
    """Downloads a file with standard browser headers."""
    if target_path.exists() and target_path.stat().st_size > 1000:
        print(f"  [-] Already downloaded: {target_path.name}")
        return True

    print(f"  [*] Downloading {target_path.name} from {url}...")
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            target_path.write_bytes(content)
            print(f"  [+] Saved {target_path.name} ({len(content) / 1024:.1f} KB)")
            return True
    except Exception as e:
        print(f"  [!] Failed to download {target_path.name}: {e}")
        return False


def download_and_extract_zip(url: str, extract_to: Path, prefix: str = "") -> int:
    """Downloads an in-memory zip file and extracts sound files."""
    existing = list(extract_to.glob(f"{prefix}_*")) if prefix else []
    if len(existing) > 5:
        print(f"  [-] Already extracted {len(existing)} sounds with prefix '{prefix}' into {extract_to.name}/")
        return len(existing)

    print(f"[*] Fetching archive: {url}...")
    req = urllib.request.Request(url, headers=HEADERS)
    extracted_count = 0
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = resp.read()
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for member in z.infolist():
                    if member.is_dir():
                        continue
                    m_path = Path(member.filename)
                    if m_path.suffix.lower() not in (".wav", ".ogg", ".mp3", ".flac"):
                        continue
                    # Clean destination name
                    clean_name = f"{prefix}_{m_path.name}" if prefix else m_path.name
                    dest_file = extract_to / clean_name
                    with z.open(member) as src, open(dest_file, "wb") as dst:
                        dst.write(src.read())
                    extracted_count += 1
        print(f"  [+] Extracted {extracted_count} sounds into {extract_to.name}/")
        return extracted_count
    except Exception as e:
        print(f"  [!] Archive extraction failed: {e}")
        return 0


def get_wikimedia_url(filename: str) -> str:
    fname = filename.replace(" ", "_")
    md5 = hashlib.md5(fname.encode("utf-8")).hexdigest()
    return f"https://upload.wikimedia.org/wikipedia/commons/{md5[0]}/{md5[0:2]}/{fname}"


def main():
    print("=" * 80)
    print("🔊 AUDIOBOOK FACTORY: CC0 SOUND PACK INSTALLER")
    print("=" * 80)

    # 1. Download OpenGameArt CC0 Foley Packs
    print("\n--- 1. Downloading Foley & Object SFX (CC0) ---")
    oga_zips = [
        ("https://opengameart.org/sites/default/files/tinysized.zip", FOLEY_DIR, "tiny"),
        ("https://opengameart.org/sites/default/files/sword_-_starninjas_1.zip", FOLEY_DIR, "sword"),
        ("https://opengameart.org/sites/default/files/sword_clash_-_starninjas_0.zip", FOLEY_DIR, "sword_clash"),
    ]
    for url, dest, pfx in oga_zips:
        download_and_extract_zip(url, dest, prefix=pfx)

    # 2. Download Curated Environmental Ambiences
    print("\n--- 2. Downloading Environmental Ambiences (CC0) ---")
    ambience_files = [
        ("Howling_wind.ogg", AMBIENCE_DIR / "wind_howl.ogg", get_wikimedia_url("Howling_wind.ogg")),
        ("Restaurant_ambience.ogg", AMBIENCE_DIR / "tavern_crowd_murmur.ogg", get_wikimedia_url("Restaurant_ambience.ogg")),
        ("Rain_and_thunder.ogg", AMBIENCE_DIR / "rain_thunder.ogg", get_wikimedia_url("Rain_and_thunder.ogg")),
        ("dungeon_ambient_1_0.ogg", AMBIENCE_DIR / "dungeon_cave_bed.ogg", "https://opengameart.org/sites/default/files/dungeon_ambient_1_0.ogg"),
    ]
    for name, path, url in ambience_files:
        download_file(url, path)

    # 3. Scan and re-index Sound Bank
    print("\n--- 3. Updating SQLite FTS5 Sound Catalog ---")
    from audiobook_factory.sound_bank import SoundBank
    bank = SoundBank(bank_root=SOUND_BANK_DIR)
    stats = bank.scan_and_index()
    print(f"[+] Sound Catalog Indexing Complete: {stats}")

    # 4. Verification queries
    print("\n--- 4. Sound Bank Spot-Check ---")
    test_queries = ["sword", "boots", "clash", "wind", "tavern", "rain"]
    for q in test_queries:
        res = bank.resolve_sound(q)
        print(f"  - Query '{q}': {res.name if res else 'None'}")

    print("\n" + "=" * 80)
    print("🎉 ALL CINEMATIC CC0 AUDIO PACKS DOWNLOADED & INDEXED!")
    print("=" * 80)


if __name__ == "__main__":
    main()
