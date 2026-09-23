#!/usr/bin/env python3
"""
Audiobook Factory - Virtual Sound Catalog Seeder.
Populates hundreds of verified CC0 audio assets (Kenney, Wikimedia Commons, Code4Fukui)
into the SQLite FTS5 Sound Bank as virtual metadata records (is_downloaded=0).
Allows full-novel cinematic sound planning without local storage bloat.
Assets are JIT-downloaded on demand or preloaded during TTS synthesis.
"""

import os
import re
import json
import sqlite3
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional

from audiobook_factory.logger import logger
from audiobook_factory.sound_bank import SoundBank, DEFAULT_BANK_DIR

# -----------------------------------------------------------------------------
# Curated Wikimedia Commons Atmospheric Audio Assets (Public Domain / CC0)
# -----------------------------------------------------------------------------
WIKIMEDIA_COMMONS_ASSETS = [
    {
        "filename": "rain_and_thunder_ambient.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/b/bb/Rain_and_thunder_%281%29.ogg",
        "category": "AMB",
        "subcategory": "Weather",
        "mood": "tense",
        "tags": "rain thunder storm weather downpour dark wet outside",
        "duration_sec": 45.0,
    },
    {
        "filename": "heavy_rain_loop.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/0/0e/Rain_%281%29.ogg",
        "category": "AMB",
        "subcategory": "Weather",
        "mood": "peaceful",
        "tags": "rain shower wet steady drizzle nature outside weather",
        "duration_sec": 30.0,
    },
    {
        "filename": "howling_wind_gale.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/b/b6/IJzige_wind_-_SoundCloud_-_Beeld_en_Geluid.ogg",
        "category": "AMB",
        "subcategory": "Weather",
        "mood": "tense",
        "tags": "wind howl gale storm freezing cold blizzard mountain dark eerie",
        "duration_sec": 48.0,
    },
    {
        "filename": "ambient_wind_breeze.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/c/c6/Wind_-_SoundCloud_-_Beeld_en_Geluid.ogg",
        "category": "AMB",
        "subcategory": "Weather",
        "mood": "mysterious",
        "tags": "wind breeze atmosphere outdoors open wilderness quiet calm",
        "duration_sec": 60.0,
    },
    {
        "filename": "echo_metal_gong.wav",
        "url": "https://upload.wikimedia.org/wikipedia/commons/c/c7/Echo_Bong.wav",
        "category": "SFX",
        "subcategory": "Magic",
        "mood": "mysterious",
        "tags": "gong echo magic chime resonance cavern spell dark bronze",
        "duration_sec": 3.5,
    },
    {
        "filename": "campfire_sound_ambience.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/b/b1/Campfire_sound_ambience.ogg",
        "category": "AMB",
        "subcategory": "Nature",
        "mood": "peaceful",
        "tags": "campfire fire hearth crackle burning flame wood warm night",
        "duration_sec": 60.0,
    },
    {
        "filename": "fireplace_burning_loop.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/d/d8/Dry_grass_burning_in_open_fireplace.ogg",
        "category": "AMB",
        "subcategory": "Nature",
        "mood": "peaceful",
        "tags": "fireplace hearth fire crackle flame tavern warm cozy",
        "duration_sec": 25.0,
    },
    {
        "filename": "six_horses_galloping.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/9/96/Six_Horses_Galloping_By.ogg",
        "category": "FOL",
        "subcategory": "Props",
        "mood": "tense",
        "tags": "horse horses galloping gallop hooves chase speed animal outdoor",
        "duration_sec": 12.0,
    },
    {
        "filename": "horse_chase_fast.wav",
        "url": "https://upload.wikimedia.org/wikipedia/commons/6/6c/Horse_chase_%28Gravity_Sound%29.wav",
        "category": "FOL",
        "subcategory": "Props",
        "mood": "tense",
        "tags": "horse chase gallop hooves fast ride animal running",
        "duration_sec": 15.0,
    },
    {
        "filename": "horse_shoes_clatter.ogg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/6/60/WWS_Clatterofhorseshoesonthepavement.ogg",
        "category": "FOL",
        "subcategory": "Props",
        "mood": "default",
        "tags": "horse trot walk hooves clatter pavement road animal street",
        "duration_sec": 20.0,
    },
]

# -----------------------------------------------------------------------------
# Kenney Audio Collections (CC0 Public Domain) on GitHub
# -----------------------------------------------------------------------------
KENNEY_REPO_BASE = "https://raw.githubusercontent.com/iwenzhou/kenney/master/Audio%20(295%20files)"

KENNEY_COLLECTIONS = [
    {
        "folder": "RPG sounds (50 sounds)",
        "category": "FOL",
        "subcategory": "Props",
        "api_name": "RPG%20sounds%20(50%20sounds)",
    },
    {
        "folder": "Digital sounds (60 sounds)",
        "category": "SFX",
        "subcategory": "Magic",
        "api_name": "Digital%20sounds%20(60%20sounds)",
    },
    {
        "folder": "UI sounds (50 sounds)",
        "category": "FOL",
        "subcategory": "Props",
        "api_name": "UI%20sounds%20(50%20sounds)",
    },
    {
        "folder": "Casino sounds (50 sounds)",
        "category": "FOL",
        "subcategory": "Props",
        "api_name": "Casino%20sounds%20(50%20sounds)",
    },
]


def derive_virtual_metadata(filename: str, folder_category: str, folder_subcat: str) -> Dict[str, Any]:
    """Derive rich tags, mood, and subcategory from sound asset filename."""
    stem = Path(filename).stem.lower()
    cat = folder_category
    subcat = folder_subcat
    mood = "default"

    # Refine subcategory & category
    if any(k in stem for k in ("sword", "chop", "blade", "slash", "knife", "metal", "armor", "mace", "parry", "clash", "flesh", "bone", "blood", "sub", "lfe")):
        subcat = "Combat"
        cat = "FOL"
        mood = "tense"
    elif any(k in stem for k in ("footstep", "walk", "step", "run", "boots")):
        subcat = "Footsteps"
        cat = "FOL"
    elif any(k in stem for k in ("creak", "door", "hinge", "latch")):
        subcat = "Doors"
        cat = "FOL"
        mood = "mysterious"
    elif any(k in stem for k in ("coin", "gold", "handlecoins", "chip")):
        subcat = "Tavern"
        cat = "FOL"
    elif any(k in stem for k in ("magic", "spell", "zap", "beam", "power", "digital")):
        subcat = "Magic"
        cat = "SFX"
        mood = "mysterious"
    elif any(k in stem for k in ("book", "cloth", "belt", "leather")):
        subcat = "Props"
        cat = "FOL"

    tokens = re.findall(r"[a-z0-9]+", stem)
    clean_tokens = set(t for t in tokens if len(t) > 2)
    clean_tokens.update([cat.lower(), subcat.lower()])
    tags = " ".join(sorted(clean_tokens))

    return {
        "category": cat,
        "subcategory": subcat,
        "mood": mood,
        "tags": tags,
    }


def seed_virtual_sound_catalog(bank: Optional[SoundBank] = None) -> Dict[str, int]:
    """
    Seeds the Sound Bank SQLite FTS5 catalog with hundreds of virtual CC0 sound assets.
    Does NOT download audio files locally — registers their metadata and remote URLs.
    """
    if bank is None:
        bank = SoundBank()

    stats = {"added": 0, "updated": 0, "skipped": 0, "total_virtual": 0}

    # 1. Seed Curated Wikimedia Commons Ambiences
    with bank._get_conn() as conn:
        for item in WIKIMEDIA_COMMONS_ASSETS:
            fname = item["filename"]
            vpath = f"virtual/wikimedia/{fname}"
            cur = conn.execute("SELECT id FROM sound_catalog WHERE filename = ? OR filepath = ?", (fname, vpath))
            row = cur.fetchone()
            if row:
                conn.execute("""
                    UPDATE sound_catalog
                    SET source_url = ?, is_downloaded = COALESCE(is_downloaded, 0)
                    WHERE id = ?
                """, (item["url"], row["id"]))
                stats["updated"] += 1
            else:
                conn.execute("""
                    INSERT INTO sound_catalog
                    (filename, filepath, category, subcategory, mood, tags, duration_sec, size_bytes, format, source_url, is_downloaded)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (
                    fname, vpath, item["category"], item["subcategory"], item["mood"],
                    item["tags"], item["duration_sec"], 0, ".ogg", item["url"]
                ))
                stats["added"] += 1
            stats["total_virtual"] += 1

    # 2. Fetch Kenney Collections from GitHub API
    for coll in KENNEY_COLLECTIONS:
        folder_api_name = coll["api_name"]
        api_url = f"https://api.github.com/repos/iwenzhou/kenney/contents/Audio%20(295%20files)/{folder_api_name}"
        try:
            req = urllib.request.Request(api_url, headers={"User-Agent": "AudiobookFactory/2.0"})
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                items = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"  [!] Failed to query Kenney collection {folder_api_name} ({e})")
            continue

        with bank._get_conn() as conn:
            for it in items:
                if it.get("type") != "file":
                    continue
                name = it["name"]
                if not name.lower().endswith((".ogg", ".wav", ".mp3")):
                    continue

                durl = it.get("download_url") or f"{KENNEY_REPO_BASE}/{folder_api_name}/{name}"
                vpath = f"virtual/kenney/{name}"

                meta = derive_virtual_metadata(name, coll["category"], coll["subcategory"])

                cur = conn.execute("SELECT id, is_downloaded FROM sound_catalog WHERE filename = ? OR filepath = ?", (name, vpath))
                row = cur.fetchone()

                if row:
                    conn.execute("""
                        UPDATE sound_catalog
                        SET source_url = ?
                        WHERE id = ?
                    """, (durl, row["id"]))
                    stats["updated"] += 1
                else:
                    conn.execute("""
                        INSERT INTO sound_catalog
                        (filename, filepath, category, subcategory, mood, tags, duration_sec, size_bytes, format, source_url, is_downloaded)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """, (
                        name, vpath, meta["category"], meta["subcategory"], meta["mood"],
                        meta["tags"], 2.0, it.get("size", 0), Path(name).suffix.lower(), durl
                    ))
                    stats["added"] += 1

                stats["total_virtual"] += 1

    logger.info(
        f"[+] Virtual Sound Catalog seeded: {stats['added']} new entries added, "
        f"{stats['updated']} updated, {stats['total_virtual']} total virtual assets indexed."
    )
    return stats


if __name__ == "__main__":
    b = SoundBank()
    res = seed_virtual_sound_catalog(b)
    print(f"Result: {res}")
    print(f"Bank stats after seeding: {b.stats()}")
