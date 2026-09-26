#!/usr/bin/env python3
"""
Audiobook Factory - Sonniss #GameAudio GDC Source Adapter.
==========================================================
Ingests curated professional game audio sound libraries from the annual
Sonniss #GameAudio GDC Archives (commercial royalty-free license).
Covers high-end combat, weapon clashes, footsteps, magic, creatures, and ambiences.
"""

from __future__ import annotations
import json
import re
from typing import Dict, Any, List, Optional, Generator
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.virtual_catalog.base_adapter import BaseSourceAdapter

# Curated High-Impact Sonniss GDC Audio Collection with direct Archive.org / gamesounds mirrors
CURATED_SONNISS_REGISTRY = [
    {
        "filename": "Sonniss_Medieval_Broadsword_Draw_01.wav",
        "title": "Medieval Broadsword Draw (Leather Scabbard)",
        "desc": "Heavy steel broadsword drawn smoothly from a stiff leather scabbard with metallic scraping tail",
        "cat": "FOL", "subcat": "Combat", "mood": "tense",
        "dur": 1.45, "action": "draw", "exciter": "steel", "resonator": "scabbard",
        "wave_style": "transient_percussive", "role": "threat_foreshadowing",
        "url": "https://archive.org/download/SonnissGameAudioGDCPack1/Medieval_Broadsword_Draw_01.wav",
        "mirror": "https://gamesounds.xyz/Sonniss.com%20-%20GDC%202020%20-%20Game%20Audio%20Bundle/Medieval_Broadsword_Draw_01.wav",
    },
    {
        "filename": "Sonniss_Steel_Blade_Clash_Heavy_02.wav",
        "title": "Heavy Steel Blade Clash & High Ring",
        "desc": "Violent direct impact between two high-carbon steel blades with sharp transient and lingering overtone ring",
        "cat": "FOL", "subcat": "Combat", "mood": "tense",
        "dur": 1.82, "action": "clash", "exciter": "steel", "resonator": "stone_wall",
        "wave_style": "staccato_hit", "role": "action_confirmation",
        "url": "https://archive.org/download/SonnissGameAudioGDCPack1/Steel_Blade_Clash_Heavy_02.wav",
        "mirror": "https://gamesounds.xyz/Sonniss.com%20-%20GDC%202020%20-%20Game%20Audio%20Bundle/Steel_Blade_Clash_Heavy_02.wav",
    },
    {
        "filename": "Sonniss_Armor_Plate_Movement_Rustle_01.wav",
        "title": "Full Plate Armor Movement & Mail Rattle",
        "desc": "Knight walking in articulated steel plate armor over chainmail with leather strap tension",
        "cat": "FOL", "subcat": "Props", "mood": "default",
        "dur": 2.10, "action": "rustle", "exciter": "steel", "resonator": "ground",
        "wave_style": "transient_percussive", "role": "ambient_grounding",
        "url": "https://archive.org/download/SonnissGameAudioGDCPack1/Armor_Plate_Movement_Rustle_01.wav",
        "mirror": "https://gamesounds.xyz/Sonniss.com%20-%20GDC%202020%20-%20Game%20Audio%20Bundle/Armor_Plate_Movement_Rustle_01.wav",
    },
    {
        "filename": "Sonniss_Heavy_Boots_Wet_Gravel_Walk_01.wav",
        "title": "Heavy Boots Walking on Wet Gravel",
        "desc": "Deliberate heavy leather military boot footsteps crunching on wet muddy gravel road",
        "cat": "FOL", "subcat": "Footsteps", "mood": "default",
        "dur": 3.40, "action": "footstep", "exciter": "leather", "resonator": "ground",
        "wave_style": "transient_percussive", "role": "ambient_grounding",
        "url": "https://archive.org/download/SonnissGameAudioGDCPack1/Heavy_Boots_Wet_Gravel_Walk_01.wav",
        "mirror": "https://gamesounds.xyz/Sonniss.com%20-%20GDC%202020%20-%20Game%20Audio%20Bundle/Heavy_Boots_Wet_Gravel_Walk_01.wav",
    },
    {
        "filename": "Sonniss_Ancient_Dungeon_Crypt_Ambience_Loop.wav",
        "title": "Subterranean Crypt & Cave Drone",
        "desc": "Deep subterranean cave drone with subtle water drips, distant low rumbling air pressure, and heavy masonry reverb",
        "cat": "AMB", "subcat": "Fantasy", "mood": "mysterious",
        "dur": 60.0, "action": "ambient_bed", "exciter": "air", "resonator": "stone_wall",
        "wave_style": "textural_drone", "role": "ambient_grounding",
        "url": "https://archive.org/download/SonnissGameAudioGDCPack1/Ancient_Dungeon_Crypt_Ambience_Loop.wav",
        "mirror": "https://gamesounds.xyz/Sonniss.com%20-%20GDC%202020%20-%20Game%20Audio%20Bundle/Ancient_Dungeon_Crypt_Ambience_Loop.wav",
    },
    {
        "filename": "Sonniss_Arcane_Spell_Charge_Ignite_01.wav",
        "title": "Arcane Fire Combustion & Whoosh",
        "desc": "Subtle high-frequency magical charge hum followed by an explosive concussive flame burst whoosh",
        "cat": "SFX", "subcat": "Magic", "mood": "tense",
        "dur": 2.50, "action": "ignite", "exciter": "fire", "resonator": "open_air",
        "wave_style": "harmonic_swell", "role": "action_confirmation",
        "url": "https://archive.org/download/SonnissGameAudioGDCPack1/Arcane_Spell_Charge_Ignite_01.wav",
        "mirror": "https://gamesounds.xyz/Sonniss.com%20-%20GDC%202020%20-%20Game%20Audio%20Bundle/Arcane_Spell_Charge_Ignite_01.wav",
    },
    {
        "filename": "Sonniss_Beast_Throat_Snarl_Growl_01.wav",
        "title": "Guttural Monster Throat Growl",
        "desc": "Deep menacing predatory throat snarl with low sub-bass vibration and wet saliva breath",
        "cat": "SFX", "subcat": "Monster", "mood": "tense",
        "dur": 2.80, "action": "rumble", "exciter": "flesh", "resonator": "cave",
        "wave_style": "transient_percussive", "role": "threat_foreshadowing",
        "url": "https://archive.org/download/SonnissGameAudioGDCPack1/Beast_Throat_Snarl_Growl_01.wav",
        "mirror": "https://gamesounds.xyz/Sonniss.com%20-%20GDC%202020%20-%20Game%20Audio%20Bundle/Beast_Throat_Snarl_Growl_01.wav",
    },
    {
        "filename": "Sonniss_Heavy_Oak_Door_Creak_Slam_01.wav",
        "title": "Massive Iron-Bound Oak Door Creak & Heavy Thud",
        "desc": "Slow resonant groan of rusty iron hinges on a massive fortress oak door followed by a heavy solid latch thud",
        "cat": "FOL", "subcat": "Doors", "mood": "mysterious",
        "dur": 3.10, "action": "creak", "exciter": "wood", "resonator": "door",
        "wave_style": "transient_percussive", "role": "punctuation",
        "url": "https://archive.org/download/SonnissGameAudioGDCPack1/Heavy_Oak_Door_Creak_Slam_01.wav",
        "mirror": "https://gamesounds.xyz/Sonniss.com%20-%20GDC%202020%20-%20Game%20Audio%20Bundle/Heavy_Oak_Door_Creak_Slam_01.wav",
    },
    {
        "filename": "Sonniss_Tavern_Mug_Slam_Wooden_Table_01.wav",
        "title": "Wooden Tankard Slam on Oak Table",
        "desc": "Heavy pewter tankard slammed down violently onto a rough wooden tavern tabletop with liquid splash",
        "cat": "FOL", "subcat": "Tavern", "mood": "default",
        "dur": 1.20, "action": "impact", "exciter": "wood", "resonator": "wood_floor",
        "wave_style": "staccato_hit", "role": "punctuation",
        "url": "https://archive.org/download/SonnissGameAudioGDCPack1/Tavern_Mug_Slam_Wooden_Table_01.wav",
        "mirror": "https://gamesounds.xyz/Sonniss.com%20-%20GDC%202020%20-%20Game%20Audio%20Bundle/Tavern_Mug_Slam_Wooden_Table_01.wav",
    },
    {
        "filename": "Sonniss_Medieval_Horse_Carriage_Cobblestone_01.wav",
        "title": "Horse Drawn Carriage on Wet Cobblestones",
        "desc": "Continuous iron-rimmed carriage wheels rattling over wet cobblestones with clopping hooves and harness jingle",
        "cat": "AMB", "subcat": "Atmosphere", "mood": "default",
        "dur": 28.0, "action": "ambient_bed", "exciter": "stone", "resonator": "open_air",
        "wave_style": "sustained_bed", "role": "ambient_grounding",
        "url": "https://archive.org/download/SonnissGameAudioGDCPack1/Medieval_Horse_Carriage_Cobblestone_01.wav",
        "mirror": "https://gamesounds.xyz/Sonniss.com%20-%20GDC%202020%20-%20Game%20Audio%20Bundle/Medieval_Horse_Carriage_Cobblestone_01.wav",
    },
]


class SonnissGDCAdapter(BaseSourceAdapter):
    """Adapter for Sonniss #GameAudio GDC Archives."""

    source_name = "Sonniss_GDC"
    default_license = "Commercial Royalty-Free (Sonniss GDC Archive)"

    def __init__(self, registry_file: Optional[Path] = None):
        self.registry_file = registry_file

    def fetch_records(self, limit: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        records = list(CURATED_SONNISS_REGISTRY)

        # Check for expanded registry file in package data
        local_cand = self.registry_file or (Path(__file__).resolve().parent.parent / "data" / "sonniss_registry.json")
        if local_cand and local_cand.exists():
            try:
                with open(local_cand, "r", encoding="utf-8") as f:
                    extra = json.load(f)
                    if isinstance(extra, list):
                        records.extend(extra)
            except Exception as e:
                logger.warning(f"Failed to load expanded sonniss registry: {e}")

        count = 0
        for item in records:
            if limit and count >= limit:
                break
            yield item
            count += 1

    def normalize_item(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        fname = raw.get("filename")
        if not fname:
            return None

        title = raw.get("title", fname)
        desc = raw.get("desc") or raw.get("description") or title
        cat = raw.get("cat") or raw.get("category") or "SFX"
        subcat = raw.get("subcat") or raw.get("subcategory") or "Combat"
        mood = raw.get("mood", "tense")
        dur = float(raw.get("dur") or raw.get("duration_sec") or 2.0)
        act = raw.get("action", "impact")
        exc = raw.get("exciter", "steel")
        res = raw.get("surface") or raw.get("resonator", "hall")
        w_style = raw.get("wave_style", "transient_percussive")
        d_role = raw.get("role") or raw.get("dramatic_role") or "action_confirmation"

        archive_id = raw.get("archive_id") or "SonnissGameAudioGDCPack1"
        source_url = raw.get("url") or raw.get("source_url") or (f"https://archive.org/download/{archive_id}/{fname}" if fname else "")
        mirror_url = raw.get("mirror") or raw.get("mirror_url")

        tags = set(re.findall(r"[a-z0-9]+", f"{title} {desc} {cat} {subcat} {act} {exc} {res}".lower()))
        tags.update(["sonniss", "gdc", "gameaudio", "professional", cat.lower(), subcat.lower()])
        clean_tags = " ".join(sorted(t for t in tags if len(t) > 2))

        # Sonic Genome v2
        genome = {
            "version": "2.0",
            "physical": {
                "source_object": title,
                "source_material": exc,
                "action_type": act,
                "surface_material": res,
                "impact_force": "heavy" if "heavy" in title.lower() else "medium",
                "knowledge_class": "curated",
                "confidence": 0.95,
            },
            "temporal": {
                "temporal_class": "sustained" if cat == "AMB" else "transient",
                "wave_style": w_style,
                "energy_envelope": "high" if "heavy" in title.lower() or "clash" in title.lower() else "medium",
                "texture": "metallic" if exc == "steel" else "organic",
            },
            "dramatic": {
                "narrative_function": "ACTION_CUE" if cat in ("FOL", "SFX") else "AMBIENT_BED",
                "dramatic_role": d_role,
                "foreground_strength": 0.8 if cat == "FOL" and act in ("clash", "draw") else 0.3,
                "attention_demand": "HIGH" if act == "clash" else "MEDIUM",
            },
            "mix": {
                "voice_masking_risk": "MODERATE" if act == "clash" else "LOW",
                "dialogue_compatibility": 0.70 if act == "clash" else 0.90,
                "whisper_compatibility": 0.25 if act == "clash" else 0.65,
                "ducking_recommendation_db": -12.0,
            },
            "remote": {
                "source_collection": "Sonniss_GDC",
                "source_url": source_url,
                "mirror_url": mirror_url,
                "license_type": self.default_license,
                "creator": "Sonniss GDC Contributor Sound Designers",
                "attribution": "Sonniss #GameAudio GDC Archive (Commercial Royalty Free)",
            },
            "provenance_log": [
                {
                    "class": "curated",
                    "source": "Sonniss Game Audio Archive",
                    "confidence": 0.95,
                    "notes": "Verified high-resolution game audio track"
                }
            ]
        }

        return {
            "filename": fname,
            "filepath": f"virtual/sonniss/{fname}",
            "title": title,
            "description": desc,
            "category": cat,
            "subcategory": subcat,
            "mood": mood,
            "tags": clean_tags,
            "duration_sec": dur,
            "size_bytes": 0,
            "format": Path(fname).suffix.lower() or ".wav",
            "source_collection": self.source_name,
            "source_url": source_url,
            "mirror_url": mirror_url,
            "url_status": "available",
            "license": self.default_license,
            "creator_attribution": "Sonniss GDC Archive",
            "tempo_bpm": 0.0,
            "key_tonality": "",
            "time_signature": "4/4",
            "wave_style": w_style,
            "temporal_character": "transient" if cat != "AMB" else "sustained",
            "energy_profile": "high" if "heavy" in title.lower() else "medium",
            "texture_profile": "metallic" if exc == "steel" else "organic",
            "exciter": exc,
            "resonator": res,
            "action_type": act,
            "surface": res,
            "perspective": "close" if cat == "FOL" else "medium",
            "acoustic_space": res,
            "dramatic_role": d_role,
            "foreground_strength": 0.8 if act in ("clash", "draw") else 0.4,
            "voice_masking_risk": "MODERATE" if act == "clash" else "LOW",
            "whisper_compatibility": 0.25 if act == "clash" else 0.65,
            "sonic_genome": genome,
        }
