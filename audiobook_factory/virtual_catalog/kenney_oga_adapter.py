#!/usr/bin/env python3
"""
Audiobook Factory - Kenney CC0 & OpenGameArt Source Adapter.
===========================================================
Ingests public domain (CC0) RPG foley, combat impacts, weapon clashes,
magic zaps, footsteps, and atmospheric textures from Kenney.nl and OpenGameArt.
"""

from __future__ import annotations
import json
import re
import urllib.request
from typing import Dict, Any, List, Optional, Generator
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.virtual_catalog.base_adapter import BaseSourceAdapter

KENNEY_REPO_BASE = "https://raw.githubusercontent.com/iwenzhou/kenney/master/Audio%20(295%20files)"

KENNEY_FOLDERS = [
    {"name": "RPG sounds (50 sounds)", "cat": "FOL", "subcat": "Props", "api": "RPG%20sounds%20(50%20sounds)"},
    {"name": "Digital sounds (60 sounds)", "cat": "SFX", "subcat": "Magic", "api": "Digital%20sounds%20(60%20sounds)"},
    {"name": "UI sounds (50 sounds)", "cat": "FOL", "subcat": "Props", "api": "UI%20sounds%20(50%20sounds)"},
    {"name": "Casino sounds (50 sounds)", "cat": "FOL", "subcat": "Tavern", "api": "Casino%20sounds%20(50%20sounds)"},
]

CURATED_OGA_ASSETS = [
    {
        "name": "oga_sword_parry_steel_01.wav",
        "title": "OpenGameArt Steel Sword Parry Clash",
        "url": "https://opengameart.org/sites/default/files/sword_clash_0.wav",
        "cat": "FOL", "subcat": "Combat", "mood": "tense", "dur": 1.2,
        "action": "clash", "exciter": "steel", "resonator": "hall",
    },
    {
        "name": "oga_heavy_knife_slice_flesh.ogg",
        "title": "Dagger Cut & Blade Slice",
        "url": "https://opengameart.org/sites/default/files/knifeSlice.ogg",
        "cat": "FOL", "subcat": "Combat", "mood": "tense", "dur": 0.8,
        "action": "cut", "exciter": "steel", "resonator": "flesh",
    },
    {
        "name": "oga_dungeon_ambient_cave_loop.ogg",
        "title": "Dark Dungeon Cavern Wind & Drips",
        "url": "https://opengameart.org/sites/default/files/dungeon_ambient_1_0.ogg",
        "cat": "AMB", "subcat": "Fantasy", "mood": "mysterious", "dur": 42.0,
        "action": "ambient_bed", "exciter": "air", "resonator": "cave",
    },
]


class KenneyOGAAdapter(BaseSourceAdapter):
    """Adapter for Kenney CC0 Audio and OpenGameArt curated sound packs."""

    source_name = "Kenney_OpenGameArt"
    default_license = "CC0 1.0 Universal (Public Domain)"

    def fetch_records(self, limit: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        count = 0

        # 1. Curated OGA assets
        for it in CURATED_OGA_ASSETS:
            if limit and count >= limit:
                break
            yield it
            count += 1

        # 2. Query Kenney collections via GitHub API with fallback
        for coll in KENNEY_FOLDERS:
            folder_api = coll["api"]
            api_url = f"https://api.github.com/repos/iwenzhou/kenney/contents/Audio%20(295%20files)/{folder_api}"
            items = []
            try:
                req = urllib.request.Request(api_url, headers={"User-Agent": "AudiobookFactory/2.0"})
                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    items = json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                logger.debug(f"Kenney GitHub API query skipped/failed for {coll['name']}: {e}")

            if isinstance(items, list):
                for item in items:
                    if limit and count >= limit:
                        break
                    if item.get("type") == "file" and item["name"].lower().endswith((".ogg", ".wav", ".mp3")):
                        item["folder_meta"] = coll
                        yield item
                        count += 1

    def normalize_item(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        fname = raw.get("name") or raw.get("filename")
        if not fname:
            return None

        # Check if curated OGA item
        if "url" in raw or "source_url" in raw:
            title = raw.get("title", fname)
            cat = raw.get("category") or raw.get("cat", "FOL")
            subcat = raw.get("subcategory") or raw.get("subcat", "Combat")
            mood = raw.get("mood", "default")
            dur = float(raw.get("dur") or raw.get("duration_sec", 1.5))
            act = raw.get("action", "impact")
            exc = raw.get("exciter", "steel")
            res = raw.get("surface") or raw.get("resonator", "hall")
            durl = raw.get("url") or raw.get("source_url", "")
        else:
            folder_meta = raw.get("folder_meta", {})
            cat = raw.get("category") or raw.get("cat") or folder_meta.get("cat", "FOL")
            subcat = raw.get("subcategory") or raw.get("subcat") or folder_meta.get("subcat", "Props")
            stem = Path(fname).stem.lower()
            mood = raw.get("mood", "default")

            act = raw.get("action", "impact")
            exc = raw.get("exciter", "wood")
            res = raw.get("surface") or raw.get("resonator", "room")
            if any(k in stem for k in ("sword", "blade", "chop", "clash", "parry")):
                subcat = "Combat"
                act = "clash"
                exc = "steel"
                mood = "tense"
            elif any(k in stem for k in ("magic", "zap", "spell", "power")):
                cat = "SFX"
                subcat = "Magic"
                act = "ignite"
                exc = "fire"
                mood = "mysterious"
            elif any(k in stem for k in ("footstep", "walk", "step")):
                subcat = "Footsteps"
                act = "footstep"
                exc = "leather"
                res = "ground"
            elif any(k in stem for k in ("creak", "door", "hinge")):
                subcat = "Doors"
                act = "creak"
                exc = "wood"
                res = "door"

            folder_api = folder_meta.get("api", "")
            durl = raw.get("download_url") or f"{KENNEY_REPO_BASE}/{folder_api}/{fname}"
            title = Path(fname).stem.replace("_", " ").title()
            dur = 2.0

        tags = set(re.findall(r"[a-z0-9]+", f"{title} {fname} {cat} {subcat} {act} {exc}".lower()))
        tags.update(["kenney", "cc0", "public_domain", cat.lower(), subcat.lower()])
        clean_tags = " ".join(sorted(t for t in tags if len(t) > 2))

        genome = {
            "version": "2.0",
            "physical": {
                "source_object": title,
                "source_material": exc,
                "action_type": act,
                "surface_material": res,
                "knowledge_class": "curated",
                "confidence": 0.90,
            },
            "temporal": {
                "temporal_class": "transient" if cat != "AMB" else "sustained",
                "wave_style": "staccato_hit" if act in ("clash", "cut") else "transient_percussive",
            },
            "dramatic": {
                "narrative_function": "ACTION_CUE" if cat in ("FOL", "SFX") else "AMBIENT_BED",
                "dramatic_role": "action_confirmation" if cat == "FOL" else "ambient_grounding",
                "foreground_strength": 0.6 if cat == "FOL" else 0.3,
            },
            "mix": {
                "voice_masking_risk": "LOW",
                "dialogue_compatibility": 0.85,
                "whisper_compatibility": 0.60,
                "ducking_recommendation_db": -8.0,
            },
            "remote": {
                "source_collection": "Kenney_OpenGameArt",
                "source_url": durl,
                "license_type": self.default_license,
                "creator": "Kenney Vleugels / OpenGameArt CC0 Authors",
                "attribution": "CC0 1.0 Universal (Kenney.nl & OpenGameArt)",
            }
        }

        return {
            "filename": fname,
            "filepath": f"virtual/kenney/{fname}",
            "title": title,
            "description": f"{title} - CC0 Audio Sample",
            "category": cat,
            "subcategory": subcat,
            "mood": mood,
            "tags": clean_tags,
            "duration_sec": dur,
            "size_bytes": raw.get("size", 0),
            "format": Path(fname).suffix.lower() or ".ogg",
            "source_collection": self.source_name,
            "source_url": durl,
            "mirror_url": None,
            "url_status": "available",
            "license": self.default_license,
            "creator_attribution": "Kenney.nl / OpenGameArt",
            "tempo_bpm": 0.0,
            "key_tonality": "",
            "time_signature": "4/4",
            "wave_style": "staccato_hit" if act in ("clash", "cut") else "transient_percussive",
            "temporal_character": "transient",
            "energy_profile": "medium",
            "texture_profile": "clean",
            "exciter": exc,
            "resonator": res,
            "action_type": act,
            "surface": res,
            "perspective": "close",
            "acoustic_space": "room",
            "dramatic_role": "action_confirmation" if cat == "FOL" else "ambient_grounding",
            "foreground_strength": 0.6 if cat == "FOL" else 0.3,
            "voice_masking_risk": "LOW",
            "whisper_compatibility": 0.60,
            "sonic_genome": genome,
        }
