#!/usr/bin/env python3
"""
Audiobook Factory - BBC Sound Effects Source Adapter.
=====================================================
Ingests the official BBC Sound Effects catalog (16,000+ authentic real-world,
environmental, and historical foley effects) into the Sonic Intelligence Catalog.
"""

from __future__ import annotations
import csv
import io
import re
import urllib.request
from typing import Dict, Any, List, Optional, Generator
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.virtual_catalog.base_adapter import BaseSourceAdapter

BBC_CSV_URL = "https://raw.githubusercontent.com/FThompson/BBCSoundDownloader/master/BBCSoundEffects.csv"
BBC_MEDIA_MP3_BASE = "https://sound-effects-media.bbcrewind.co.uk/mp3"
BBC_ACROPOLIS_BASE = "http://bbcsfx.acropolis.org.uk/assets"


class BBCSoundEffectsAdapter(BaseSourceAdapter):
    """Adapter for the BBC Sound Effects Archive."""

    source_name = "BBC_Sound_Effects"
    default_license = "BBC RemArc (Personal / Educational / Research)"

    def __init__(self, cached_csv_path: Optional[Path] = None):
        self.cached_csv_path = cached_csv_path

    def fetch_records(self, limit: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        """Streams records from remote CSV or local cache."""
        raw_text = None

        local_cand = self.cached_csv_path or (Path(__file__).resolve().parent.parent / "data" / "BBCSoundEffects.csv")
        if local_cand and local_cand.exists():
            try:
                raw_text = local_cand.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"Could not read local BBC CSV: {e}")

        if not raw_text:
            try:
                req = urllib.request.Request(
                    BBC_CSV_URL,
                    headers={"User-Agent": "AudiobookFactory/2.0 (SonicIntelligenceCatalog)"}
                )
                with urllib.request.urlopen(req, timeout=20.0) as resp:
                    raw_bytes = resp.read()
                    raw_text = raw_bytes.decode("utf-8", errors="ignore")
                    try:
                        local_cand.parent.mkdir(parents=True, exist_ok=True)
                        local_cand.write_bytes(raw_bytes)
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Could not fetch BBC CSV from GitHub ({e}); checking fallback.")

        if not raw_text:
            return

        reader = csv.DictReader(io.StringIO(raw_text))
        count = 0
        for row in reader:
            if limit and count >= limit:
                break
            yield row
            count += 1

    def normalize_item(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        location = (raw.get("location") or raw.get("Location") or "").strip()
        desc = (raw.get("description") or raw.get("Description") or raw.get("TrackTitle") or "").strip()
        if not location or not desc:
            return None

        clean_id = location.replace(".wav", "").replace(".mp3", "")
        mp3_name = f"{clean_id}.mp3"
        source_url = f"{BBC_MEDIA_MP3_BASE}/{clean_id}.mp3"
        mirror_url = f"{BBC_ACROPOLIS_BASE}/{location}"
        source_page = f"https://sound-effects.bbcrewind.co.uk/search?q={clean_id}"

        dur_sec = 0.0
        raw_dur = raw.get("secs") or raw.get("Duration") or raw.get("duration") or ""
        try:
            if ":" in str(raw_dur):
                parts = str(raw_dur).split(":")
                if len(parts) == 2:
                    dur_sec = float(parts[0]) * 60 + float(parts[1])
                elif len(parts) == 3:
                    dur_sec = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            else:
                dur_sec = float(raw_dur or 0.0)
        except ValueError:
            dur_sec = 0.0

        src_cat = (raw.get("category") or raw.get("Category") or "General").strip()
        desc_lower = desc.lower()

        # Categorize into standard Audiobook Factory taxonomy
        category = "SFX"
        subcategory = "Props"
        wave_style = "general"
        exciter = "metal"
        resonator = "room"
        action_type = "interaction"
        dramatic_role = "ambient_grounding"
        mood = "default"

        if any(w in desc_lower or w in src_cat.lower() for w in ("footstep", "walking", "running", "shoes", "boots", "steps")):
            category = "FOL"
            subcategory = "Footsteps"
            action_type = "footstep"
            exciter = "leather"
            resonator = "ground"
            wave_style = "transient_percussive"
        elif any(w in desc_lower or w in src_cat.lower() for w in ("door", "creak", "latch", "lock", "shut", "open", "hinge")):
            category = "FOL"
            subcategory = "Doors"
            action_type = "creak"
            exciter = "wood"
            resonator = "door"
            wave_style = "transient_percussive"
        elif any(w in desc_lower or w in src_cat.lower() for w in ("weather", "wind", "rain", "thunder", "storm", "blizzard", "breeze")):
            category = "AMB"
            subcategory = "Weather"
            action_type = "ambient_bed"
            exciter = "wind" if "wind" in desc_lower else "water"
            resonator = "sky"
            wave_style = "sustained_bed"
            mood = "tense" if "thunder" in desc_lower or "storm" in desc_lower else "peaceful"
        elif any(w in desc_lower or w in src_cat.lower() for w in ("tavern", "crowd", "market", "chatter", "applause", "people", "voices")):
            category = "AMB"
            subcategory = "Tavern"
            action_type = "ambient_bed"
            exciter = "flesh"
            resonator = "tavern"
            wave_style = "sustained_bed"
        elif any(w in desc_lower or w in src_cat.lower() for w in ("sword", "blade", "fight", "punch", "smash", "impact", "clash", "crash", "explosion")):
            category = "FOL" if "sword" in desc_lower or "blade" in desc_lower else "SFX"
            subcategory = "Combat"
            action_type = "clash" if "sword" in desc_lower else "impact"
            exciter = "steel" if "sword" in desc_lower else "metal"
            resonator = "hall"
            wave_style = "staccato_hit" if "sword" in desc_lower else "transient_percussive"
            dramatic_role = "action_confirmation"
            mood = "tense"
        elif any(w in desc_lower or w in src_cat.lower() for w in ("nature", "birds", "forest", "countryside", "river", "sea", "stream")):
            category = "AMB"
            subcategory = "Nature"
            action_type = "ambient_bed"
            exciter = "water" if "water" in desc_lower or "river" in desc_lower else "air"
            resonator = "open_air"
            wave_style = "sustained_bed"
            mood = "peaceful"
        elif dur_sec > 25.0:
            category = "AMB"
            subcategory = "Atmosphere"
            wave_style = "sustained_bed"
        else:
            category = "FOL" if "horse" in desc_lower or "carriage" in desc_lower or "bottle" in desc_lower else "SFX"
            subcategory = "Props"
            wave_style = "transient_percussive"

        # Tags
        tokens = set(re.findall(r"[a-z0-9]+", f"{desc} {src_cat} {clean_id}".lower()))
        tokens.update(["bbc", "bbc_sound_effects", category.lower(), subcategory.lower(), exciter, resonator])
        clean_tags = " ".join(sorted(t for t in tokens if len(t) > 2))

        # Title
        short_title = desc.split(",")[0].strip() if "," in desc else (desc[:60] + "..." if len(desc) > 60 else desc)

        # Sonic Genome v2
        genome = {
            "version": "2.0",
            "physical": {
                "source_object": short_title,
                "source_material": exciter,
                "action_type": action_type,
                "surface_material": resonator,
                "knowledge_class": "inferred",
                "confidence": 0.80,
            },
            "temporal": {
                "temporal_class": "sustained" if category == "AMB" else "transient",
                "wave_style": wave_style,
                "energy_envelope": "high" if "explosion" in desc_lower or "thunder" in desc_lower else "medium",
                "texture": "organic",
            },
            "dramatic": {
                "narrative_function": "AMBIENT_BED" if category == "AMB" else "ACTION_CUE",
                "dramatic_role": dramatic_role,
                "foreground_strength": 0.3 if category == "AMB" else 0.7,
                "attention_demand": "LOW" if category == "AMB" else "MEDIUM",
            },
            "mix": {
                "voice_masking_risk": "SEVERE" if "explosion" in desc_lower or "thunder" in desc_lower else "LOW",
                "dialogue_compatibility": 0.90 if category == "AMB" else 0.75,
                "whisper_compatibility": 0.80 if category == "AMB" and mood == "peaceful" else 0.45,
                "ducking_recommendation_db": -12.0 if category == "AMB" else -6.0,
            },
            "remote": {
                "source_collection": "BBC_Sound_Effects",
                "source_url": source_url,
                "mirror_url": mirror_url,
                "source_page_url": source_page,
                "license_type": self.default_license,
                "creator": "BBC Sound Archive",
                "attribution": "BBC Sound Effects (C) British Broadcasting Corporation",
            },
            "provenance_log": [
                {
                    "class": "curated",
                    "source": "BBC Research & Development",
                    "confidence": 0.90,
                    "notes": f"CD: {raw.get('CDName', '')} ({raw.get('CDNumber', '')})"
                }
            ]
        }

        return {
            "filename": mp3_name,
            "filepath": f"virtual/bbc/{mp3_name}",
            "title": short_title,
            "description": desc,
            "category": category,
            "subcategory": subcategory,
            "mood": mood,
            "tags": clean_tags,
            "duration_sec": dur_sec,
            "size_bytes": 0,
            "format": ".mp3",
            "source_collection": self.source_name,
            "source_url": source_url,
            "mirror_url": mirror_url,
            "source_page_url": source_page,
            "url_status": "available",
            "license": self.default_license,
            "creator_attribution": "BBC Sound Archive",
            "tempo_bpm": 0.0,
            "key_tonality": "",
            "time_signature": "4/4",
            "wave_style": wave_style,
            "temporal_character": "sustained" if category == "AMB" else "transient",
            "energy_profile": "medium",
            "texture_profile": "organic",
            "exciter": exciter,
            "resonator": resonator,
            "action_type": action_type,
            "surface": next((s for s in ("stone", "granite", "wood", "metal", "gravel", "grass", "dirt", "mud", "water", "concrete", "carpet", "glass") if s in desc_lower), resonator),
            "perspective": "medium",
            "acoustic_space": "room",
            "dramatic_role": dramatic_role,
            "foreground_strength": 0.3 if category == "AMB" else 0.7,
            "voice_masking_risk": "SEVERE" if "explosion" in desc_lower or "thunder" in desc_lower else "LOW",
            "whisper_compatibility": 0.80 if category == "AMB" and mood == "peaceful" else 0.45,
            "sonic_genome": genome,
        }
