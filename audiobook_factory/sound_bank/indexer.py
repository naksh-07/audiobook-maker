#!/usr/bin/env python3
"""
Audiobook Factory - Sound Bank Indexer Operations.
Scans disk directories, extracts audio durations via ffprobe/ffmpeg,
derives physical/dramatic metadata, and synchronizes the sound catalog.
"""

from __future__ import annotations
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


class IndexerMixin:
    """Directory crawling and metadata derivation mixin for SoundBank."""

    bank_root: Path

    @staticmethod
    def _extract_duration(file_path: Path) -> float:
        """Extract audio duration in seconds via ffprobe or ffmpeg."""
        ffprobe = shutil.which("ffprobe")
        if ffprobe:
            try:
                cmd = [
                    ffprobe, "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(file_path)
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
                if res.returncode == 0 and res.stdout.strip():
                    return float(res.stdout.strip())
            except Exception:
                pass

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            try:
                cmd = [ffmpeg, "-i", str(file_path)]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
                m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", res.stderr)
                if m:
                    h, m_val, s = m.groups()
                    return int(h) * 3600 + int(m_val) * 60 + float(s)
            except Exception:
                pass
        return 0.0

    @staticmethod
    def _derive_metadata(file_path: Path) -> Dict[str, str]:
        """Derive category, subcategory, mood, and tags from file and folder hierarchy."""
        name_lower = file_path.stem.lower()
        parts = [p.lower() for p in file_path.parts]

        # 1. Category
        category = "SFX"
        if any(k in parts for k in ("leitmotif", "leitmotifs", "character_theme", "character_themes")):
            category = "LEITMOTIF"
        elif any(k in parts for k in ("chapter_bed", "chapter_beds", "world_bed", "world_beds")):
            category = "CHAPTER_BED"
        elif any(k in parts for k in ("dynamic_stem", "dynamic_stems", "intensity_stems")):
            category = "DYNAMIC_STEM"
        elif any(k in parts for k in ("stinger", "stingers", "accents", "hits")):
            category = "STINGER"
        elif any(k in parts for k in ("ambience", "amb", "atmospheres", "environments")):
            category = "AMB"
        elif any(k in parts for k in ("foley", "fol", "footsteps", "movement")):
            category = "FOL"
        elif any(k in parts for k in ("stems", "music", "mus", "scores", "loops")):
            category = "MUS"

        # 2. Subcategory
        subcategory = "General"
        if any(k in name_lower or k in parts for k in ("weather", "rain", "thunder", "storm", "wind", "snow")):
            subcategory = "Weather"
        elif any(k in name_lower or k in parts for k in ("tavern", "crowd", "market", "chatter")):
            subcategory = "Tavern"
        elif any(k in name_lower or k in parts for k in ("footstep", "walk", "run", "gravel", "stone", "wood")):
            subcategory = "Footsteps"
        elif any(k in name_lower or k in parts for k in ("magic", "spell", "glow", "enchant", "igni", "aard", "quen", "axii", "yrden")):
            subcategory = "Magic"
        elif any(k in name_lower or k in parts for k in ("combat", "sword", "shield", "hit", "punch", "arrow", "parry", "clash", "thud")):
            subcategory = "Combat"
        elif any(k in name_lower or k in parts for k in ("monster", "beast", "creature", "striga", "ghoul", "wolf", "roar", "snarl")):
            subcategory = "Monster"
        elif any(k in name_lower or k in parts for k in ("crypt", "tomb", "dungeon", "hearth", "hall", "swamp", "marsh", "blizzard")):
            subcategory = "Fantasy"
        elif any(k in name_lower or k in parts for k in ("drone", "dark", "horror", "eerie", "creepy")):
            subcategory = "Drone"
        elif any(k in name_lower or k in parts for k in ("forest", "birds", "nature", "night", "crickets", "fire")):
            subcategory = "Nature"

        # 3. Mood
        mood = "default"
        if any(k in name_lower for k in ("peaceful", "calm", "relax", "meditation")):
            mood = "peaceful"
        elif any(k in name_lower for k in ("mysterious", "suspense", "secret", "archive")):
            mood = "mysterious"
        elif any(k in name_lower for k in ("tense", "danger", "dark", "chase", "heartbeat", "striga", "ghoul", "beast", "monster")):
            mood = "tense"
        elif any(k in name_lower for k in ("emotional", "sad", "melancholy", "poignant")):
            mood = "emotional"
        elif any(k in name_lower for k in ("epic", "triumph", "glory", "battle", "brass", "igni", "aard")):
            mood = "epic"

        # 4. Tags: tokens extracted from filename, subfolder, and semantic expansion dictionaries
        tokens = re.findall(r"[a-z0-9]+", name_lower + " " + " ".join(parts[-3:]))
        combined_text = name_lower + " " + " ".join(parts[-3:])
        semantic_expansions = {
            "igni": ["igni", "fire", "flame", "whoosh", "burst", "combustion", "spell", "magic", "blaze", "heat", "pyromancy"],
            "aard": ["aard", "shockwave", "blast", "concussive", "telekinetic", "push", "force", "air", "wave", "kinetic", "impact"],
            "quen": ["quen", "shield", "barrier", "protection", "forcefield", "hum", "resonance", "armor", "defense", "ward"],
            "axii": ["axii", "hypnotic", "chime", "charm", "psychic", "mind", "control", "stun", "daze", "calm", "suggestion"],
            "yrden": ["yrden", "trap", "glyph", "arcane", "circle", "spark", "electric", "zap", "binding", "slow", "rune"],
            "striga": ["striga", "monster", "beast", "roar", "screech", "demonic", "creature", "horror", "growl", "predator", "curse"],
            "ghoul": ["ghoul", "monster", "creature", "snarl", "growl", "necrophage", "scavenge", "flesh", "tear", "bite", "alghoul"],
            "wolf": ["wolf", "wolves", "howl", "howling", "canine", "pack", "wild", "beast", "predator", "forest", "night"],
            "sword": ["sword", "blade", "steel", "weapon", "scabbard", "draw", "clash", "parry", "strike", "swing", "slash"],
            "clash": ["clash", "parry", "strike", "hit", "metal", "duel", "fight", "combat", "steel", "ring", "sword"],
            "thud": ["thud", "body", "heavy", "impact", "fall", "stone", "hit", "ground", "crash", "bodyfall", "blunt"],
            "armor": ["armor", "plate", "chainmail", "metal", "movement", "gear", "knight", "suit", "clank", "rattle"],
            "crypt": ["crypt", "tomb", "dungeon", "subterranean", "stone", "cave", "drips", "damp", "reverberant", "ancient", "vault", "catacomb"],
            "dungeon": ["dungeon", "crypt", "tomb", "cell", "chains", "underground", "stone", "dark", "cave"],
            "hearth": ["hearth", "fireplace", "castle", "hall", "fire", "crackling", "warmth", "indoor", "room"],
            "castle": ["castle", "hall", "hearth", "fireplace", "court", "room", "chamber", "noble"],
            "swamp": ["swamp", "bog", "marsh", "wetland", "eerie", "murky", "night", "water", "mist", "reeds", "nocturnal"],
            "bog": ["bog", "swamp", "marsh", "wetland", "eerie", "murky", "night", "water", "mist", "reeds"],
            "blizzard": ["blizzard", "mountain", "snow", "howling", "wind", "storm", "cold", "winter", "frost", "gale", "ice", "freeze"],
        }
        for kw, exp_tags in semantic_expansions.items():
            if kw in combined_text:
                tokens.extend(exp_tags)

        # Remove noisy common tokens
        clean_tokens = set(t for t in tokens if len(t) > 2 and t not in ("mp3", "wav", "flac", "ogg", "audiobooks", "soundscapes"))
        tags = " ".join(sorted(clean_tokens))

        return {
            "category": category,
            "subcategory": subcategory,
            "mood": mood,
            "tags": tags,
        }

    def scan_and_index(self, extra_dirs: Optional[List[Path]] = None) -> Dict[str, int]:
        """
        Recursively scans local directories and upserts all audio files into SQLite FTS5 catalog.
        """
        target_dirs = [self.bank_root]
        if extra_dirs:
            target_dirs.extend(extra_dirs)

        stats = {"indexed": 0, "updated": 0, "skipped": 0, "total_files": 0}
        valid_exts = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aif", ".aiff"}

        candidate_files = []
        for t_dir in target_dirs:
            if not t_dir.exists():
                continue
            for root, _, files in os.walk(t_dir):
                for f in files:
                    p = Path(root) / f
                    if p.suffix.lower() in valid_exts and not p.name.startswith("."):
                        candidate_files.append(p)

        stats["total_files"] = len(candidate_files)

        existing_records = {}
        with self._get_conn() as conn:
            cur = conn.execute("SELECT id, filepath, size_bytes FROM sound_catalog")
            for row in cur.fetchall():
                existing_records[row["filepath"]] = (row["id"], row["size_bytes"])

        to_update = []
        to_insert = []

        for p in candidate_files:
            filepath_str = str(p.resolve()).replace("\\", "/")
            try:
                size_bytes = p.stat().st_size
            except OSError:
                continue

            existing = existing_records.get(filepath_str)
            if existing and existing[1] == size_bytes:
                stats["skipped"] += 1
                continue

            meta = self._derive_metadata(p)
            dur = self._extract_duration(p)

            if existing:
                to_update.append((
                    p.name, meta["category"], meta["subcategory"], meta["mood"], meta["tags"],
                    dur, size_bytes, p.suffix.lower(), existing[0]
                ))
            else:
                to_insert.append((
                    p.name, filepath_str, meta["category"], meta["subcategory"], meta["mood"],
                    meta["tags"], dur, size_bytes, p.suffix.lower()
                ))

        with self._get_conn() as conn:
            if to_update:
                conn.executemany("""
                    UPDATE sound_catalog
                    SET filename = ?, category = ?, subcategory = ?, mood = ?, tags = ?,
                        duration_sec = ?, size_bytes = ?, format = ?
                    WHERE id = ?
                """, to_update)
                stats["updated"] += len(to_update)

            if to_insert:
                conn.executemany("""
                    INSERT INTO sound_catalog
                    (filename, filepath, category, subcategory, mood, tags, duration_sec, size_bytes, format)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, to_insert)
                stats["indexed"] += len(to_insert)

            conn.commit()

        return stats
