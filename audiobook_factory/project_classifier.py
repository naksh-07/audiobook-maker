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


# Recognizable Literary Franchises & Lore Indicators
FRANCHISE_SIGNATURES: Dict[str, Dict[str, Any]] = {
    "the_witcher": {
        "authors": ["andrzej sapkowski", "sapkowski"],
        "titles": ["sword of destiny", "the last wish", "blood of elves", "time of contempt", "baptism of fire", "tower of the swallow", "lady of the lake", "season of storms"],
        "keywords": ["rivia", "vengerberg", "cintra", "witcher", "zerrikanian", "oxenfurt", "jaskier", "kaer morhen", "novigrad", "skellige", "temeria", "redania", "nilfgaard", "basilisk", "aelirenn"],
        "era": "MEDIEVAL_FANTASY",
        "genre": "fantasy",
        "primary_acoustic_env": "stone_ruins_exterior",
        "theme": "Dark Slavic Witcher Fantasy",
    },
    "dune": {
        "authors": ["frank herbert"],
        "titles": ["dune", "dune messiah", "children of dune", "god emperor of dune"],
        "keywords": ["paul atreides", "arrakis", "harkonnen", "fremen", "shai-hulud", "bene gesserit", "caladan", "melange", "spice"],
        "era": "SPACE_OPERA_SCIFI",
        "genre": "sci_fi",
        "primary_acoustic_env": "desert_dunes_wind",
        "theme": "Epic Desert Space Opera",
    },
    "tolkien_middle_earth": {
        "authors": ["j.r.r. tolkien", "tolkien"],
        "titles": ["the hobbit", "the fellowship of the ring", "the two towers", "the return of the king", "the silmarillion"],
        "keywords": ["frodo", "bilbo", "gandalf", "mordor", "shire", "aragorn", "legolas", "gimli", "rivendell", "sauron", "orc", "hobbit"],
        "era": "MEDIEVAL_FANTASY",
        "genre": "fantasy",
        "primary_acoustic_env": "deep_forest_night",
        "theme": "High Epic Fantasy",
    },
    "sherlock_holmes": {
        "authors": ["arthur conan doyle", "conan doyle"],
        "titles": ["a study in scarlet", "the sign of the four", "the hound of the baskervilles", "the valley of fear"],
        "keywords": ["sherlock", "holmes", "dr. watson", "baker street", "moriarty", "lestrade", "scotland yard"],
        "era": "VICTORIAN_EDWARDIAN",
        "genre": "detective_noir",
        "primary_acoustic_env": "victorian_parlor_fire",
        "theme": "Victorian Gaslight Detective Mystery",
    },
    "lovecraft_cthulhu": {
        "authors": ["h.p. lovecraft", "lovecraft"],
        "titles": ["the call of cthulhu", "at the mountains of madness", "the shadow over innsmouth"],
        "keywords": ["cthulhu", "arkham", "necronomicon", "miskatonic", "innsmouth", "shoggoth", "yog-sothoth", "elder god"],
        "era": "PULP_NOIR_1940S",
        "genre": "horror_thriller",
        "primary_acoustic_env": "crypt_catacomb",
        "theme": "Cosmic Horror & Eldritch Dread",
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

        # 2. Check Franchise Signatures first (highest fidelity)
        for franchise_key, sig in FRANCHISE_SIGNATURES.items():
            if any(a in author for a in sig["authors"]):
                logger.info(f"[+] ProjectClassifier: Match author '{author}' -> Franchise '{franchise_key}'")
                return ProjectClassification(
                    era=sig["era"],
                    genre=sig["genre"],
                    franchise_affinity=franchise_key,
                    primary_acoustic_env=sig["primary_acoustic_env"],
                    dramatic_theme=sig["theme"],
                    confidence=0.98,
                )

            if any(t in title for t in sig["titles"]):
                logger.info(f"[+] ProjectClassifier: Match title '{title}' -> Franchise '{franchise_key}'")
                return ProjectClassification(
                    era=sig["era"],
                    genre=sig["genre"],
                    franchise_affinity=franchise_key,
                    primary_acoustic_env=sig["primary_acoustic_env"],
                    dramatic_theme=sig["theme"],
                    confidence=0.95,
                )

            # Keyword density check
            kw_hits = sum(1 for kw in sig["keywords"] if re.search(r"\b" + re.escape(kw) + r"\b", combined_search))
            if kw_hits >= 2:
                logger.info(f"[+] ProjectClassifier: Keyword signature hits ({kw_hits}) -> Franchise '{franchise_key}'")
                return ProjectClassification(
                    era=sig["era"],
                    genre=sig["genre"],
                    franchise_affinity=franchise_key,
                    primary_acoustic_env=sig["primary_acoustic_env"],
                    dramatic_theme=sig["theme"],
                    confidence=0.90,
                )

        # 3. Universal Era & Genre Heuristic Analysis (for standalone novels)
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
