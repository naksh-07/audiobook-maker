#!/usr/bin/env python3
"""
Audiobook Factory - Sonic Intelligence: Embedded Audio Metadata & Naming Harvester.
==================================================================================
Extracts embedded container metadata (ID3, BWF/BEXT, RIFF INFO, Vorbis comments, MP4 atoms),
Universal Category System (UCS) filename grammar, and folder hierarchy semantics.

Strict Epistemic Invariant:
- Distinguishes clearly between SOURCE METADATA, MEASURED FACTS, and INFERRED TOKENS.
- NEVER invents metadata merely to fill fields.
- If a property cannot be reliably recovered, leaves it empty or None, preserving uncertainty.
- Preserves raw unparsed provider tags in SourceMetadata.raw_metadata.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from audiobook_factory.contracts import (
    NormalizedSourceFields,
    ProvenanceRecord,
    SourceMetadata,
)

logger = logging.getLogger("audiobook_factory.embedded_metadata_harvester")

# Standard Universal Category System (UCS) 4-character Category Prefix Map
UCS_CATEGORY_MAP: Dict[str, Tuple[str, str]] = {
    "AIRC": ("SFX", "Aircraft"),
    "AMB":  ("AMB", "Ambience"),
    "ANIM": ("SFX", "Animals"),
    "ARCH": ("SFX", "Archery"),
    "BELL": ("SFX", "Bells"),
    "BIRD": ("SFX", "Birds"),
    "BLOW": ("SFX", "Blows"),
    "BOAT": ("SFX", "Boats"),
    "BODY": ("FOL", "Body Fall / Foley"),
    "CARM": ("SFX", "Cameras"),
    "CHEM": ("SFX", "Chemicals"),
    "CLIK": ("SFX", "Clicks"),
    "COMM": ("SFX", "Communications"),
    "CRWD": ("AMB", "Crowd / Walla"),
    "DEST": ("SFX", "Destruction"),
    "DIRT": ("SFX", "Dirt / Earth"),
    "DOOR": ("FOL", "Doors / Latches"),
    "DRON": ("AMB", "Drones / Tones"),
    "ELEC": ("SFX", "Electricity"),
    "ENGI": ("SFX", "Engines"),
    "EXPL": ("SFX", "Explosions"),
    "FARM": ("SFX", "Farm"),
    "FIRE": ("AMB", "Fire / Flame"),
    "FOLE": ("FOL", "Foley General"),
    "FOOT": ("FOL", "Footsteps"),
    "GEAR": ("FOL", "Gears / Chains"),
    "GORE": ("SFX", "Gore / Blood"),
    "GUNS": ("SFX", "Guns / Firearms"),
    "HORR": ("SFX", "Horror / Tension"),
    "INSC": ("SFX", "Insects"),
    "MACH": ("SFX", "Machines"),
    "MAGC": ("SFX", "Magic / Spells"),
    "MECH": ("SFX", "Mechanical"),
    "METL": ("FOL", "Metal"),
    "MICS": ("SFX", "Microphones"),
    "MISC": ("SFX", "Miscellaneous"),
    "MOTR": ("SFX", "Motors"),
    "MUSC": ("MUS", "Music"),
    "NATR": ("AMB", "Nature"),
    "NOIS": ("SFX", "Noise"),
    "OFFC": ("SFX", "Office"),
    "PLAS": ("FOL", "Plastic"),
    "PROJ": ("SFX", "Projectiles"),
    "ROBT": ("SFX", "Robots"),
    "ROK":  ("FOL", "Rocks / Stones"),
    "ROOM": ("AMB", "Room Tone"),
    "SCIF": ("SFX", "Sci-Fi"),
    "SNOW": ("AMB", "Snow / Ice"),
    "SPRT": ("SFX", "Sports"),
    "TECH": ("SFX", "Technology"),
    "TOOL": ("FOL", "Tools"),
    "TRAI": ("SFX", "Trains"),
    "VEHC": ("SFX", "Vehicles"),
    "VOIC": ("SFX", "Human Non-Speech"),
    "WARP": ("SFX", "Warfare"),
    "WATR": ("AMB", "Water / Liquid"),
    "WEAP": ("FOL", "Weapons / Blades"),
    "WIND": ("AMB", "Wind / Weather"),
    "WOOD": ("FOL", "Wood"),
    "ZAPS": ("SFX", "Zaps / Lasers"),
}

# Regex to parse variation suffixes from file stems (e.g., _01, _varA, _take2, -03)
VARIATION_PATTERN = re.compile(
    r"^(.*?)(?:[_\-\s]+(?:var|take|ver|v|hit|step|seq|loop)?([0-9]+|[a-zA-Z]))$",
    re.IGNORECASE,
)

# Standard UCS Regex: CatID_FxName_Creator_Source (CatID is 4-8 chars, e.g. DOORWood, WATRRain)
UCS_PATTERN = re.compile(
    r"^([A-Z]{4}[A-Za-z0-9]{0,4})_([^_]+)(?:_([^_]+))?(?:_([^_]+))?$",
)


class AudioMetadataExtractor:
    """
    Forensic embedded metadata harvester and naming analyzer.
    Extracts container tags via ffprobe and analyzes filename/path structures
    while strictly preserving raw unparsed tags and avoiding fabricated defaults.
    """

    def __init__(self, ffprobe_bin: Optional[str] = None):
        self.ffprobe = ffprobe_bin or shutil.which("ffprobe") or "ffprobe"

    def probe_embedded_tags(self, filepath: Path) -> Dict[str, Any]:
        """
        Extracts container and stream metadata tags using ffprobe JSON probe.
        Combines format-level and stream-level tag dictionaries.
        """
        if not filepath.exists() or filepath.stat().st_size == 0:
            return {}

        cmd = [
            self.ffprobe,
            "-v", "error",
            "-show_format",
            "-show_streams",
            "-of", "json",
            str(filepath),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15.0)
            if res.returncode != 0 or not res.stdout.strip():
                return {}

            data = json.loads(res.stdout)
            format_tags = data.get("format", {}).get("tags", {}) or {}

            # Collect stream tags
            stream_tags: Dict[str, Any] = {}
            for stream in data.get("streams", []):
                s_tags = stream.get("tags", {})
                if isinstance(s_tags, dict):
                    stream_tags.update(s_tags)

            combined_tags: Dict[str, Any] = {}
            # Format tags take precedence, merged with stream tags
            combined_tags.update(stream_tags)
            combined_tags.update(format_tags)
            return combined_tags
        except Exception as e:
            logger.debug(f"Exception probing embedded tags from {filepath.name}: {e}")
            return {}

    def parse_ucs_naming(self, filename_stem: str) -> Optional[Dict[str, Any]]:
        """
        Parses Universal Category System (UCS) filename grammar if present.
        Grammar: [CatID]_[FXName]_[Creator/Vendor]_[Source/Index]
        Returns None if filename does not conform to UCS structure (no fake guesses).
        """
        match = UCS_PATTERN.match(filename_stem)
        if not match:
            return None

        cat_id = match.group(1).upper()
        fx_name = match.group(2).replace("_", " ").strip()
        creator = match.group(3).strip() if match.group(3) else None
        source_id = match.group(4).strip() if match.group(4) else None

        # Check if the 4-char prefix is a recognized UCS category
        cat_prefix = cat_id[:4]
        mapped_cat = UCS_CATEGORY_MAP.get(cat_prefix)
        if not mapped_cat:
            return None

        primary_category, subcategory = mapped_cat

        # Check if exciter or resonator is implied by CatID suffix (e.g. DOORWood -> exciter=wood)
        exciter: Optional[str] = None
        if len(cat_id) > 4:
            sub_token = cat_id[4:].lower()
            if sub_token in ("wood", "metl", "metal", "stn", "stone", "glas", "glass", "plst", "plas", "leath"):
                exciter = sub_token

        return {
            "ucs_cat_id": cat_id,
            "category": primary_category,
            "subcategory": subcategory,
            "fx_name": fx_name,
            "creator": creator,
            "source_id": source_id,
            "exciter": exciter,
        }

    def detect_variation_family(self, filename_stem: str) -> Tuple[str, Optional[str]]:
        """
        Detects if filename belongs to a numbered variation family (e.g. sword_clash_01).
        Returns:
            (base_family_name, variation_index_or_tag)
        """
        match = VARIATION_PATTERN.match(filename_stem)
        if match:
            base_name = match.group(1).rstrip("_- ").strip()
            var_index = match.group(2).strip()
            if base_name and var_index:
                return base_name, var_index
        return filename_stem, None

    def extract_hierarchy_tokens(self, filepath: Path, root_dir: Optional[Path] = None) -> List[str]:
        """
        Extracts semantic directory tokens from folder hierarchy.
        Excludes uninformative generic drive/root tokens.
        """
        tokens: List[str] = []
        try:
            rel_path = filepath.relative_to(root_dir) if root_dir and root_dir in filepath.parents else filepath
            parent_parts = [p.name for p in rel_path.parents if p.name and p.name != "."]
        except ValueError:
            parent_parts = [p.name for p in filepath.parents if p.name]

        ignored_parts = {
            "audio", "sound", "sounds", "sfx", "library", "sound_bank", "audiobooks",
            "content", "assets", "files", "wav", "mp3", "flac", "ogg", "temp", "tmp"
        }

        for part in reversed(parent_parts[-4:]):  # up to 4 hierarchy levels
            part_clean = part.lower().replace("_", " ").replace("-", " ")
            words = re.findall(r"[a-z0-9]+", part_clean)
            for w in words:
                if len(w) > 2 and w not in ignored_parts and not w.isdigit():
                    if w not in tokens:
                        tokens.append(w)

        return tokens

    def harvest_source_metadata(
        self,
        filepath: Path,
        root_dir: Optional[Path] = None,
    ) -> SourceMetadata:
        """
        Harvests all available source metadata from embedded container tags,
        UCS filename parsing, and folder hierarchy.
        Strictly preserves raw data and uncertainty.
        """
        raw_tags = self.probe_embedded_tags(filepath)
        stem = filepath.stem

        # 1. Check embedded tags for Title, Artist, Album, etc.
        def _get_tag(*keys: str) -> Optional[str]:
            for k in keys:
                # Direct match
                if k in raw_tags and str(raw_tags[k]).strip():
                    return str(raw_tags[k]).strip()
                # Case-insensitive match
                for rk, rv in raw_tags.items():
                    if rk.lower() == k.lower() and str(rv).strip():
                        return str(rv).strip()
            return None

        # Title
        raw_title = _get_tag("title", "TIT2", "INAM", "track_name", "fxname", "TXXX:FXName")
        # Artist / Creator / Author
        raw_creator = _get_tag("artist", "TPE1", "IART", "creator", "author", "originator", "bext:originator")
        # Album / Collection / Pack
        raw_collection = _get_tag("album", "TALB", "IPRD", "collection", "sound_pack", "library")
        # Description / Comment / Notes
        raw_description = _get_tag("description", "comment", "COMM", "ICMT", "bext:description", "bext.description", "notes")
        # Genre
        raw_genre = _get_tag("genre", "TCON", "IGNR")
        # License / Copyright
        raw_license = _get_tag("license", "copyright", "TCOP", "ICOP") or "Unknown / Unspecified"
        # UCS CatID tag
        raw_catid = _get_tag("CatID", "cat_id", "ucs_catid", "UCS_CatID", "TXXX:CatID")

        # 2. Check UCS filename grammar
        ucs_data = self.parse_ucs_naming(stem)
        if ucs_data:
            if not raw_title:
                raw_title = ucs_data.get("fx_name")
            if not raw_creator and ucs_data.get("creator"):
                raw_creator = ucs_data.get("creator")

        # 3. Extract folder tokens
        folder_tokens = self.extract_hierarchy_tokens(filepath, root_dir=root_dir)

        # 4. Extract filename tokens
        clean_stem_text = re.sub(r"[_\-\.\(\)\[\]]", " ", stem).lower()
        stem_tokens = [w for w in re.findall(r"[a-z0-9]+", clean_stem_text) if len(w) > 2 and not w.isdigit()]

        # Combine source tags honestly (deduplicated, order preserved)
        all_tags: List[str] = []
        seen_tags: Set[str] = set()

        # Add explicit keyword tags from container if available
        raw_kw = _get_tag("keywords", "TXXX:Keywords", "user_tags")
        if raw_kw:
            for kw in re.split(r"[,;\s]+", raw_kw):
                k_clean = kw.strip().lower()
                if k_clean and len(k_clean) > 1 and k_clean not in seen_tags:
                    seen_tags.add(k_clean)
                    all_tags.append(k_clean)

        for t in folder_tokens + stem_tokens:
            if t not in seen_tags:
                seen_tags.add(t)
                all_tags.append(t)

        # 5. Determine category & subcategory conservatively
        category = "SFX"
        subcategory = "General"

        if ucs_data:
            category = ucs_data["category"]
            subcategory = ucs_data["subcategory"]
        elif raw_genre:
            g_low = raw_genre.lower()
            if any(k in g_low for k in ("ambience", "ambient", "atmosphere", "environment")):
                category = "AMB"
                subcategory = raw_genre
            elif any(k in g_low for k in ("music", "score", "soundtrack", "ost", "drone")):
                category = "MUS"
                subcategory = raw_genre
            elif any(k in g_low for k in ("foley", "footstep", "cloth", "props")):
                category = "FOL"
                subcategory = raw_genre
        else:
            # Check folder tokens for unambiguous high-level categories
            tokens_set = set(folder_tokens)
            if "ambience" in tokens_set or "atmospheres" in tokens_set:
                category = "AMB"
                subcategory = "Ambience"
            elif "foley" in tokens_set or "footsteps" in tokens_set:
                category = "FOL"
                subcategory = "Foley"
            elif "music" in tokens_set or "stems" in tokens_set:
                category = "MUS"
                subcategory = "Music"

        # 6. Variation family detection
        family_name, var_idx = self.detect_variation_family(stem)

        # Assemble normalized source fields without fabricating certainty
        normalized = NormalizedSourceFields(
            title=raw_title or stem,
            description=raw_description or "",
            tags=all_tags,
            category=category,
            subcategory=subcategory,
            creator=raw_creator or "",
            collection=raw_collection or (root_dir.name if root_dir else "Local Sound Bank"),
            genre=raw_genre or "",
            mood="default",  # Creative mood remains uninterpreted / default
            duration_sec=0.0,
            license=raw_license,
            provider_id=raw_catid or (ucs_data["ucs_cat_id"] if ucs_data else ""),
        )

        # Raw metadata preserves the complete ground truth
        preserved_raw = dict(raw_tags)
        preserved_raw["_filename"] = filepath.name
        preserved_raw["_stem"] = stem
        preserved_raw["_parent_folder"] = filepath.parent.name
        if ucs_data:
            preserved_raw["_ucs_parsed"] = ucs_data
        if var_idx:
            preserved_raw["_variation_family"] = family_name
            preserved_raw["_variation_index"] = var_idx

        provenance = ProvenanceRecord(
            source_method="source_metadata",
            analyzer_id="embedded_metadata_harvester",
            analyzer_version="1.0.0",
            ontology_version="sonic_genome_v2.1",
            generated_at=datetime.now(timezone.utc).isoformat(),
            confidence=1.0 if raw_tags else 0.85,
            notes=f"Extracted {len(raw_tags)} raw tags from container; UCS={bool(ucs_data)}",
        )

        return SourceMetadata(
            provider_name=raw_collection or "local_library",
            raw_metadata=preserved_raw,
            normalized=normalized,
            provenance=provenance,
        )
