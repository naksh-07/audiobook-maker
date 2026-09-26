#!/usr/bin/env python3
"""
Audiobook Factory - Incompetech Source Adapter.
==============================================
Ingests Kevin MacLeod's high-utility cinematic orchestral, atmospheric,
and mood score catalog (1,400+ tracks) directly into the Sonic Intelligence Catalog.
"""

from __future__ import annotations
import json
import re
import urllib.parse
import urllib.request
from typing import Dict, Any, List, Optional, Generator
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.virtual_catalog.base_adapter import BaseSourceAdapter

INCOMPETECH_PIECES_URL = "https://incompetech.com/music/royalty-free/pieces.json"
INCOMPETECH_MP3_BASE = "https://incompetech.com/music/royalty-free/mp3-royaltyfree"


class IncompetechAdapter(BaseSourceAdapter):
    """Adapter for Kevin MacLeod's Incompetech music catalog."""

    source_name = "Incompetech"
    default_license = "CC-BY-4.0 (Kevin MacLeod / incompetech.com)"

    def __init__(self, cached_json_path: Optional[Path] = None):
        self.cached_json_path = cached_json_path

    def _parse_duration(self, length_str: str) -> float:
        """Parses 'HH:MM:SS' or 'MM:SS' into float seconds."""
        if not length_str:
            return 0.0
        parts = length_str.strip().split(":")
        try:
            if len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 1:
                return float(parts[0])
        except ValueError:
            pass
        return 0.0

    def fetch_records(self, limit: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        """Fetches pieces from remote JSON endpoint or local cache."""
        data = None

        # 1. Check local cache first if provided or in package data
        local_cand = self.cached_json_path or (Path(__file__).resolve().parent.parent / "data" / "incompetech_pieces.json")
        if local_cand and local_cand.exists():
            try:
                with open(local_cand, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read local incompetech cache: {e}")

        # 2. Fetch from remote if not loaded
        if not data:
            try:
                req = urllib.request.Request(
                    INCOMPETECH_PIECES_URL,
                    headers={"User-Agent": "AudiobookFactory/2.0 (SonicIntelligenceCatalog)"}
                )
                with urllib.request.urlopen(req, timeout=15.0) as resp:
                    raw_bytes = resp.read()
                    data = json.loads(raw_bytes.decode("utf-8"))
                    # Save to local cache for future offline runs
                    try:
                        local_cand.parent.mkdir(parents=True, exist_ok=True)
                        local_cand.write_bytes(raw_bytes)
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Could not reach Incompetech API ({e}); checking fallback.")

        if not data:
            return

        records = list(data.values()) if isinstance(data, dict) else data
        count = 0
        for item in records:
            if limit and count >= limit:
                break
            yield item
            count += 1

    def normalize_item(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        fname = raw.get("filename")
        title = raw.get("title") or (Path(fname).stem if fname else "")
        if not fname or not title:
            return None

        dur_sec = self._parse_duration(raw.get("length", ""))
        bpm = 0.0
        try:
            bpm = float(raw.get("bpm") or raw.get("tempo") or 0.0)
        except ValueError:
            bpm = 0.0

        raw_feel = raw.get("feel") or raw.get("feels") or ""
        feel = ", ".join(raw_feel) if isinstance(raw_feel, list) else str(raw_feel).strip()

        raw_inst = raw.get("instruments") or ""
        instruments = ", ".join(raw_inst) if isinstance(raw_inst, list) else str(raw_inst).strip()
        desc = (raw.get("description") or "").strip()

        # Derive dramatic mood and role
        mood = "peaceful"
        feel_lower = feel.lower()
        if any(w in feel_lower for w in ("tense", "dark", "horror", "creepy", "eerie", "dread", "chase")):
            mood = "tense"
        elif any(w in feel_lower for w in ("mysterious", "suspense", "secret", "investigative", "curious")):
            mood = "mysterious"
        elif any(w in feel_lower for w in ("epic", "action", "battle", "driving", "powerful", "intense")):
            mood = "epic"
        elif any(w in feel_lower for w in ("sad", "poignant", "somber", "melancholy", "grief", "emotional")):
            mood = "emotional"

        dramatic_role = "ambient_grounding"
        if bpm >= 120 or mood == "epic":
            dramatic_role = "action_confirmation"
        elif mood == "tense":
            dramatic_role = "threat_foreshadowing"
        elif mood == "emotional":
            dramatic_role = "emotional_resonance"

        # Determine subcategory
        subcat = "Orchestral"
        if any(w in feel_lower or w in desc.lower() for w in ("tavern", "folk", "medieval", "celtic", "ren faire")):
            subcat = "Tavern"
        elif any(w in feel_lower or w in desc.lower() for w in ("electronic", "synth", "techno", "ambient drone")):
            subcat = "Drone"
        elif any(w in feel_lower or w in desc.lower() for w in ("world", "african", "asian", "middle eastern")):
            subcat = "World"

        # Safe URL encoding for direct MP3 streaming
        quoted_fname = urllib.parse.quote(fname)
        source_url = f"{INCOMPETECH_MP3_BASE}/{quoted_fname}"
        mirror_url = f"{INCOMPETECH_MP3_BASE}/{fname}"
        source_page = f"https://incompetech.com/music/royalty-free/index.html?isrc={raw.get('isrc', '')}" if raw.get("isrc") else None

        # Tags
        tags = set(re.findall(r"[a-z0-9]+", f"{title} {feel} {instruments} {desc}".lower()))
        tags.update(["incompetech", "kevin_macleod", "music", "score", subcat.lower(), mood])
        clean_tags = " ".join(sorted(t for t in tags if len(t) > 2))

        # Sonic Genome v2 structure
        genome = {
            "version": "2.0",
            "physical": {
                "source_object": "orchestral_ensemble",
                "source_material": "strings_woodwinds_brass",
                "action_type": "musical_cue",
                "interaction_type": "acoustic_performance",
                "knowledge_class": "inferred",
                "confidence": 0.9,
            },
            "temporal": {
                "temporal_class": "sustained",
                "wave_style": "harmonic_swell" if bpm >= 100 else "sustained_bed",
                "energy_envelope": "high" if bpm >= 130 else ("low" if bpm < 80 else "medium"),
                "texture": "clean",
                "motion": "swelling" if bpm >= 100 else "static",
            },
            "dramatic": {
                "narrative_function": "EMOTIONAL_UNDERSCORE",
                "dramatic_role": dramatic_role,
                "foreground_strength": 0.45,
                "attention_demand": "MEDIUM",
            },
            "mix": {
                "voice_masking_risk": "MODERATE" if bpm >= 120 else "LOW",
                "dialogue_compatibility": 0.85,
                "whisper_compatibility": 0.70 if bpm < 100 else 0.40,
                "ducking_recommendation_db": -14.0,
            },
            "music": {
                "bpm": bpm,
                "lead_instruments": [i.strip() for i in instruments.split(",") if i.strip()],
                "energy_level": 7 if bpm >= 125 else (3 if bpm < 75 else 5),
            },
            "remote": {
                "source_collection": "Incompetech",
                "source_url": source_url,
                "mirror_url": mirror_url,
                "source_page_url": source_page,
                "license_type": self.default_license,
                "creator": "Kevin MacLeod",
                "attribution": "Music by Kevin MacLeod (incompetech.com), Licensed under Creative Commons: By Attribution 4.0 License",
            },
            "provenance_log": [
                {
                    "class": "curated",
                    "source": "Incompetech API",
                    "confidence": 0.95,
                    "notes": f"Catalog ISRC: {raw.get('isrc')}"
                }
            ]
        }

        return {
            "filename": fname,
            "filepath": f"virtual/incompetech/{fname}",
            "title": title,
            "description": desc or f"{title} ({feel}) by Kevin MacLeod",
            "category": "MUS",
            "subcategory": subcat,
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
            "is_downloaded": 0,
            "license": self.default_license,
            "creator_attribution": "Kevin MacLeod (incompetech.com)",
            "tempo_bpm": bpm,
            "key_tonality": "",
            "time_signature": "4/4",
            "wave_style": "harmonic_swell" if bpm >= 100 else "sustained_bed",
            "temporal_character": "sustained",
            "energy_profile": "high" if bpm >= 130 else ("low" if bpm < 80 else "medium"),
            "texture_profile": "clean",
            "exciter": "orchestral_strings",
            "resonator": "concert_hall",
            "action_type": "musical_cue",
            "surface": "studio",
            "perspective": "medium",
            "acoustic_space": "hall",
            "dramatic_role": dramatic_role,
            "foreground_strength": 0.45,
            "voice_masking_risk": "MODERATE" if bpm >= 120 else "LOW",
            "whisper_compatibility": 0.70 if bpm < 100 else 0.40,
            "sonic_genome": genome,
        }
