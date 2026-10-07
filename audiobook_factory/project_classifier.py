#!/usr/bin/env python3
"""
Audiobook Factory - Stage 0.5: Universal Project Classifier & World Resolver.
=============================================================================
Dynamically classifies book era, genre, franchise affinity, and world acoustic DNA
from title, author, book bible, and narrative prose with zero hardcoded single-book biases.
"""

from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict

from audiobook_factory.logger import logger


@dataclass
class ProjectClassification:
    era: str  # MEDIEVAL_FANTASY, SPACE_OPERA_SCIFI, RETRO_FUTURE_CYBERPUNK, PULP_NOIR_1940S, VICTORIAN_EDWARDIAN, MODERN_CONTEMPORARY, GENERAL_DRAMA
    genre: str  # fantasy, sci_fi, horror_thriller, detective_noir, historical, literary_fiction, contemporary
    franchise_affinity: Optional[str]  # e.g. "the_witcher", "dune", "tolkien_middle_earth", None
    primary_acoustic_env: str  # e.g. "stone_ruins_exterior", "tavern_interior", "spaceship_bridge", "domestic_room_quiet"
    dramatic_theme: str
    confidence: float


# Universal Literary Era & Genre Categories
UNIVERSAL_ERA_ACOUSTICS: Dict[str, Dict[str, str]] = {
    "MEDIEVAL_FANTASY": {
        "genre": "fantasy",
        "primary_acoustic_env": "tavern_interior",
        "theme": "Historical & Epic Fantasy Drama",
    },
    "SPACE_OPERA_SCIFI": {
        "genre": "sci_fi",
        "primary_acoustic_env": "spaceship_bridge",
        "theme": "Cinematic Speculative Sci-Fi",
    },
    "RETRO_FUTURE_CYBERPUNK": {
        "genre": "cyberpunk",
        "primary_acoustic_env": "cyberpunk_alley_rain",
        "theme": "Gritty Cyberpunk Noir",
    },
    "PULP_NOIR_1940S": {
        "genre": "detective_noir",
        "primary_acoustic_env": "detective_office",
        "theme": "Hardboiled Detective Noir",
    },
    "VICTORIAN_EDWARDIAN": {
        "genre": "historical",
        "primary_acoustic_env": "victorian_parlor_fire",
        "theme": "Period Historical Drama",
    },
    "MODERN_CONTEMPORARY": {
        "genre": "literary_fiction",
        "primary_acoustic_env": "room_tone",
        "theme": "Modern Literary Audio Drama",
    },
}



class ProjectClassifier:
    """Universal analyzer that determines novel era, genre, and world acoustic DNA."""

    @staticmethod
    def classify(
        project_dir: Optional[Path] = None,
        metadata: Optional[Dict[str, Any]] = None,
        sample_prose: Optional[str] = None,
    ) -> ProjectClassification:
        meta = metadata or {}
        pdir = Path(project_dir) if project_dir else None

        # 1. Load metadata.json if available from disk
        if not meta and pdir:
            meta_path = pdir / "metadata.json"
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                except Exception as e:
                    logger.debug(f"ProjectClassifier: could not load metadata.json: {e}")

        # Check for explicit manual override in metadata
        if meta.get("era") and meta.get("genre"):
            return ProjectClassification(
                era=str(meta.get("era")).upper(),
                genre=str(meta.get("genre")).lower(),
                franchise_affinity=meta.get("franchise_affinity") or meta.get("franchise"),
                primary_acoustic_env=meta.get("primary_acoustic_env", "room_tone"),
                dramatic_theme=meta.get("dramatic_theme", f"{meta.get('genre', 'General').title()} Audio Drama"),
                confidence=1.0,
            )

        title = str(meta.get("title", "")).lower().strip()
        author = str(meta.get("author", "")).lower().strip()
        narrative_voice = str(meta.get("narrative_voice", "")).lower().strip()

        # Gather sample text if none provided
        text_corpus = sample_prose or ""
        if not text_corpus and pdir:
            # Try reading book_bible.json or first chapter
            bb_file = pdir / "book_bible.json"
            if bb_file.exists():
                try:
                    with open(bb_file, "r", encoding="utf-8") as bf:
                        text_corpus += " " + bf.read()
                except Exception:
                    pass

            for chap_cand in [pdir / "chapter_001.md", pdir / "chapter_002.md"]:
                if chap_cand.exists():
                    try:
                        with open(chap_cand, "r", encoding="utf-8") as cf:
                            text_corpus += " " + cf.read()[:5000]
                    except Exception:
                        pass

        combined_search = f"{title} {author} {narrative_voice} {text_corpus[:10000]}".lower()

        # 2. Universal Era & Genre Heuristic Analysis (for any novel)
        fantasy_keywords = [
            "sword", "blade", "sorcerer", "wizard", "magic", "dragon", "tavern", "castle",
            "shield", "scabbard", "king", "queen", "dungeon", "crypt", "monster", "beast",
            "तलवार", "जादू", "राक्षस", "किला", "खंडहर"
        ]
        scifi_keywords = [
            "spaceship", "galaxy", "orbit", "laser", "plasma", "starship", "warp", "alien",
            "cyborg", "cybernetic", "robot", "shuttle", "console", "spacecraft", "fleet"
        ]
        cyberpunk_keywords = [
            "neon", "cyberdeck", "decker", "implant", "megacorp", "hacker", "cyberspace", "augmented"
        ]
        noir_keywords = [
            "revolver", "detective", "trenchcoat", "fedora", "cigarette", "speakeasy", "gunman"
        ]
        historical_keywords = [
            "carriage", "horse", "coach", "petticoat", "regiment", "musket", "emperor", "monarchy"
        ]

        scores = {
            "MEDIEVAL_FANTASY": sum(1 for w in fantasy_keywords if re.search(r"\b" + re.escape(w) + r"\b", combined_search)),
            "SPACE_OPERA_SCIFI": sum(1 for w in scifi_keywords if re.search(r"\b" + re.escape(w) + r"\b", combined_search)),
            "RETRO_FUTURE_CYBERPUNK": sum(1 for w in cyberpunk_keywords if re.search(r"\b" + re.escape(w) + r"\b", combined_search)),
            "PULP_NOIR_1940S": sum(1 for w in noir_keywords if re.search(r"\b" + re.escape(w) + r"\b", combined_search)),
            "VICTORIAN_EDWARDIAN": sum(1 for w in historical_keywords if re.search(r"\b" + re.escape(w) + r"\b", combined_search)),
        }

        best_era = max(scores, key=scores.get)
        best_score = scores[best_era]

        if best_score >= 2:
            genre_map = {
                "MEDIEVAL_FANTASY": ("fantasy", "tavern_interior", "Epic Historical / Fantasy Audio Drama"),
                "SPACE_OPERA_SCIFI": ("sci_fi", "spaceship_bridge", "Cinematic Sci-Fi Drama"),
                "RETRO_FUTURE_CYBERPUNK": ("cyberpunk", "cyberpunk_alley_rain", "Gritty Cyberpunk Noir"),
                "PULP_NOIR_1940S": ("detective_noir", "detective_office", "Hardboiled Noir Drama"),
                "VICTORIAN_EDWARDIAN": ("historical", "victorian_parlor_fire", "Period Historical Drama"),
            }
            genre, env, theme = genre_map[best_era]
            return ProjectClassification(
                era=best_era,
                genre=genre,
                franchise_affinity=None,
                primary_acoustic_env=env,
                dramatic_theme=theme,
                confidence=min(0.85, 0.40 + (best_score * 0.10)),
            )

        # Default fallback for contemporary / modern works
        return ProjectClassification(
            era="MODERN_CONTEMPORARY",
            genre="literary_fiction",
            franchise_affinity=None,
            primary_acoustic_env="room_tone",
            dramatic_theme="Modern Cinematic Audio Drama",
            confidence=0.50,
        )

    @classmethod
    def persist_classification(cls, project_dir: Path, metadata: Optional[Dict[str, Any]] = None) -> ProjectClassification:
        """Classifies the project and writes the authoritative attributes to metadata.json."""
        classification = cls.classify(project_dir=project_dir, metadata=metadata)
        meta_file = project_dir / "metadata.json"
        meta_data: Dict[str, Any] = {}
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta_data = json.load(f)
            except Exception:
                pass

        meta_data["era"] = classification.era
        meta_data["genre"] = classification.genre
        meta_data["franchise_affinity"] = classification.franchise_affinity
        meta_data["primary_acoustic_env"] = classification.primary_acoustic_env
        meta_data["dramatic_theme"] = classification.dramatic_theme
        meta_data["classification_confidence"] = classification.confidence

        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=2)

        logger.info(
            f"[+] ProjectClassifier: Authoritatively persisted book profile -> "
            f"Era: {classification.era}, Genre: {classification.genre}, Franchise: {classification.franchise_affinity or 'None'}"
        )
        return classification
