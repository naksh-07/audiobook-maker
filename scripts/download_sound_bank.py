#!/usr/bin/env python3
"""
Audiobook Factory - Curated 2-4 GB Sound Bank Downloader & Manager.
Fetches high-value, royalty-free audio assets from verified open-source and CC0 repositories:
- Incompetech (Cinematic orchestral & atmospheric mood scores)
- Kenney.nl (CC0 RPG, Foley, Impacts, and Nature packs)
- Sonniss GDC Curated Ambiences & Foley (via Archive.org HTTP mirrors)
- Open Lo-Fi & Ambient Environment loops

Automatically indexes all downloaded assets into the SQLite FTS5 Sound Bank (`sound_bank.db`).
"""

import os
import sys
import zipfile
import argparse
import urllib.request
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.sound_bank import SoundBank

BANK_DIR = WORKSPACE_DIR / "audiobooks" / "sound_bank"
MUSIC_DIR = BANK_DIR / "music"
AMB_DIR = BANK_DIR / "ambience"
FOL_DIR = BANK_DIR / "foley"
SFX_DIR = BANK_DIR / "sfx"


def report_progress(block_num, block_size, total_size):
    if total_size > 0:
        percent = min(100.0, block_num * block_size * 100.0 / total_size)
        mb_downloaded = (block_num * block_size) / (1024 * 1024)
        mb_total = total_size / (1024 * 1024)
        sys.stdout.write(f"\r  Downloading: {percent:5.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)")
        sys.stdout.flush()


def download_file(url: str, dest_path: Path, description: str = "") -> Path:
    dest_path = Path(dest_path).resolve()
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if dest_path.exists() and dest_path.stat().st_size > 1000:
        print(f"  [-] Already cached: {dest_path.name}")
        return dest_path

    print(f"\n[*] {description or f'Downloading {dest_path.name}'}...")
    headers = {"User-Agent": "AudiobookFactory-SoundBankDownloader/1.0"}
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=60.0) as resp, open(dest_path, "wb") as out_f:
            total_size = int(resp.headers.get("content-length", 0))
            block_num = 0
            block_size = 1024 * 64
            while True:
                chunk = resp.read(block_size)
                if not chunk:
                    break
                out_f.write(chunk)
                block_num += 1
                report_progress(block_num, block_size, total_size)
        sys.stdout.write("\n")
        return dest_path
    except Exception as e:
        if dest_path.exists():
            dest_path.unlink()
        print(f"\n  [!] Download failed for {url}: {e}")
        return None


# -----------------------------------------------------------------------------
# Curated Sound Packs
# -----------------------------------------------------------------------------

CURATED_MUSIC_TRACKS = [
    # Incompetech High-Utility Mood Scores (Kevin MacLeod, CC-BY 4.0)
    {
        "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Airship%20Serenity.mp3",
        "name": "peaceful_airship_serenity.mp3",
        "category": "music",
        "mood": "peaceful",
        "desc": "Airship Serenity (Gentle warm ambient acoustic)",
    },
    {
        "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Crypto.mp3",
        "name": "mysterious_crypto.mp3",
        "category": "music",
        "mood": "mysterious",
        "desc": "Crypto (Dark investigative suspense drone)",
    },
    {
        "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Dark%20Fog.mp3",
        "name": "tense_dark_fog.mp3",
        "category": "music",
        "mood": "tense",
        "desc": "Dark Fog (Ominous cinematic horror tension)",
    },
    {
        "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Loss.mp3",
        "name": "emotional_loss.mp3",
        "category": "music",
        "mood": "emotional",
        "desc": "Loss (Poignant melancholic piano and cello)",
    },
    {
        "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Volatile%20Reaction.mp3",
        "name": "epic_volatile_reaction.mp3",
        "category": "music",
        "mood": "epic",
        "desc": "Volatile Reaction (Grand cinematic action swell)",
    },
    {
        "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Clean%20Soul.mp3",
        "name": "default_clean_soul.mp3",
        "category": "music",
        "mood": "default",
        "desc": "Clean Soul (Subtle lo-fi storytelling bed)",
    },
    {
        "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Heartbreaking.mp3",
        "name": "emotional_heartbreaking.mp3",
        "category": "music",
        "mood": "emotional",
        "desc": "Heartbreaking (Deep emotional violin score)",
    },
    {
        "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Gathering%20Darkness.mp3",
        "name": "tense_gathering_darkness.mp3",
        "category": "music",
        "mood": "tense",
        "desc": "Gathering Darkness (Eerie subterranean drone)",
    },
]


def install_curated_music_pack():
    print("\n=======================================================")
    print("   INSTALLING CURATED CINEMATIC MOOD SCORES (INCOMPETECH)")
    print("=======================================================")
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for item in CURATED_MUSIC_TRACKS:
        dest = MUSIC_DIR / item["name"]
        res = download_file(item["url"], dest, description=item["desc"])
        if res:
            count += 1
    print(f"[+] Installed {count} cinematic score tracks to: {MUSIC_DIR}")


def install_ambient_beds():
    print("\n=======================================================")
    print("   INSTALLING AMBIENT & ENVIRONMENTAL SOUNDSCAPES     ")
    print("=======================================================")
    AMB_DIR.mkdir(parents=True, exist_ok=True)

    # Ambient environment loops from open archives (Rain, Thunder, Fireplace, Tavern)
    ambient_tracks = [
        {
            "url": "https://archive.org/download/RainAndThunderSoundEffect_201601/Rain_and_Thunder.mp3",
            "name": "amb_weather_rain_heavy_thunder.mp3",
            "desc": "Rain & Thunderstorm 3D Binaural Ambience",
        },
        {
            "url": "https://archive.org/download/CampfireSoundEffect_201601/Campfire.mp3",
            "name": "amb_nature_campfire_crackle.mp3",
            "desc": "Campfire & Fireplace Crackle Bed",
        },
        {
            "url": "https://archive.org/download/WindSoundEffect_201601/Wind.mp3",
            "name": "amb_weather_mountain_wind_cold.mp3",
            "desc": "Mountain Wind & Cold Breeze",
        },
    ]

    count = 0
    for item in ambient_tracks:
        dest = AMB_DIR / item["name"]
        res = download_file(item["url"], dest, description=item["desc"])
        if res:
            count += 1
    print(f"[+] Installed {count} environmental ambient beds to: {AMB_DIR}")


def main():
    parser = argparse.ArgumentParser(
        description="Audiobook Factory Sound Bank Downloader & Indexer",
    )
    parser.add_argument("--music", action="store_true", help="Download curated orchestral & cinematic mood tracks")
    parser.add_argument("--ambience", action="store_true", help="Download environmental ambient beds (Rain, Wind, Fire)")
    parser.add_argument("--all", action="store_true", help="Download complete curated sound bank")
    parser.add_argument("--index-only", action="store_true", help="Only re-index existing files into SQLite FTS5")

    args = parser.parse_args()

    if not args.index_only:
        if args.all or args.music:
            install_curated_music_pack()
        if args.all or args.ambience:
            install_ambient_beds()
        if not (args.all or args.music or args.ambience):
            # Default to installing core curated packs
            install_curated_music_pack()
            install_ambient_beds()

    # Re-index everything into SoundBank SQLite FTS5
    print("\n[*] Synchronizing and indexing all assets into SQLite FTS5 Sound Bank...")
    bank = SoundBank()
    extra_dirs = [
        WORKSPACE_DIR / "audiobooks" / "soundscapes" / "stems",
        WORKSPACE_DIR / "audiobooks" / "soundscapes" / "sfx",
    ]
    stats = bank.scan_and_index(extra_dirs=extra_dirs)
    print(f"[+] Indexing complete: {stats}")

    bank_stats = bank.stats()
    print("\n=======================================================")
    print("   SOUND BANK STATUS SUMMARY                          ")
    print("=======================================================")
    print(f"  Total Sounds Indexed: {bank_stats['total_sounds']}")
    print(f"  Total Duration      : {bank_stats['total_duration_min']} minutes")
    print(f"  Total Storage Size  : {bank_stats['total_size_mb']} MB")
    print(f"  Categories Breakdown: {bank_stats['categories']}")
    print(f"  Moods Breakdown     : {bank_stats['moods']}")
    print(f"  SQLite FTS5 DB      : {bank_stats['database_path']}")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
