#!/usr/bin/env python3
"""
Audiobook Factory - Dramaturgy: Performance Bible Generator.
Projects canonical Character Memory and Book Bible profiles into performance-oriented
delivery guidelines (baseline pace, energy, articulation, emotional behaviors, and restraint).
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from .contracts import CharacterPerformanceProfile, PerformanceBible


class PerformanceBibleGenerator:
    """
    Constructs a project-level PerformanceBible projecting character canon
    into concrete acoustic and dramatic delivery behaviors.
    """

    SOCIOLECT_PRESETS: Dict[str, Dict[str, Any]] = {
        "COLD_CYNIC": {
            "baseline_pace": 0.92,
            "baseline_energy": 0.70,
            "articulation": "deliberate_crisp",
            "restraint_level": 0.85,
            "emotional_behaviors": {
                "anger": "cold_menace",
                "fear": "silent_vigilance",
                "sadness": "weary_resignation",
                "affection": "terse_protective_brevity",
                "humor": "cynical_mocking_chuckle",
                "excitement": "calculating_focus",
            },
            "speech_quirks": ["cynical grunt prosody ([growl] हूँ...)", "1.2s pregnant pause before retort"],
            "performance_rules": [
                "Never shout unless physically mortally wounded",
                "Maintain low, resonant chest register",
                "Subsume emotional outbursts into laconic understatements",
            ],
        },
        "CAUSTIC_ARISTOCRAT": {
            "baseline_pace": 1.04,
            "baseline_energy": 0.85,
            "articulation": "sharp_high_status",
            "restraint_level": 0.75,
            "emotional_behaviors": {
                "anger": "cutting_condescension",
                "fear": "brittle_disdain",
                "sadness": "aloof_melancholy",
                "affection": "veiled_condescension",
                "humor": "wry_amused_sneer",
                "excitement": "commanding_authority",
            },
            "speech_quirks": ["elongated elegant vowels", "rapid dismissive cadence"],
            "performance_rules": [
                "Emphasize precise consonants to convey superiority",
                "Treat dialogue as verbal fencing where every pause asserts status",
            ],
        },
        "THARKI_BARD": {
            "baseline_pace": 1.08,
            "baseline_energy": 0.90,
            "articulation": "lyrical_colloquial",
            "restraint_level": 0.30,
            "emotional_behaviors": {
                "anger": "theatrical_indignation",
                "fear": "dramatic_flustered_panic",
                "sadness": "poetic_self_pity",
                "affection": "effusive_flirtatious_warmth",
                "humor": "boisterous_banter",
                "excitement": "breathless_hyperbole",
            },
            "speech_quirks": ["melodic upward pitch inflections", "audible dramatic gasps"],
            "performance_rules": [
                "Maximize dynamic vocal range and performative flair",
                "Speak with theatrical urgency even during mundane observations",
            ],
        },
        "RUSTIC_WARRIOR": {
            "baseline_pace": 0.96,
            "baseline_energy": 0.88,
            "articulation": "guttural_blunt",
            "restraint_level": 0.50,
            "emotional_behaviors": {
                "anger": "bellowing_rage",
                "fear": "defiant_combat_strain",
                "sadness": "stony_silence",
                "affection": "clumsy_gruff_warmth",
                "humor": "booming_belly_laugh",
                "excitement": "battlecry_surge",
            },
            "speech_quirks": ["guttural exhalations", "short punchy phrasing"],
            "performance_rules": [
                "Lean into diaphragm strain on aggressive lines",
                "Clip sentence endings abruptly to convey physical solidity",
            ],
        },
        "VULNERABLE_SCHOLAR": {
            "baseline_pace": 1.02,
            "baseline_energy": 0.65,
            "articulation": "rapid_hesitant",
            "restraint_level": 0.40,
            "emotional_behaviors": {
                "anger": "trembling_indignation",
                "fear": "breathless_stammer",
                "sadness": "quiet_withdrawn_despair",
                "affection": "hesitant_tender_warmth",
                "humor": "nervous_self_deprecating_chuckle",
                "excitement": "feverish_intellectual_rush",
            },
            "speech_quirks": ["frequent self-corrections", "breath intakes on high tension"],
            "performance_rules": [
                "Inject subtle hesitations and ellipses when under scrutiny",
                "Pitch shifts upward under direct intimidation",
            ],
        },
        "DEFAULT_DRAMATIC": {
            "baseline_pace": 1.0,
            "baseline_energy": 0.80,
            "articulation": "natural",
            "restraint_level": 0.50,
            "emotional_behaviors": {
                "anger": "steely_firmness",
                "fear": "tense_vigilance",
                "sadness": "subdued_gravity",
                "affection": "warm_sincerity",
                "humor": "easy_amusement",
                "excitement": "forward_momentum",
            },
            "speech_quirks": [],
            "performance_rules": ["Deliver lines with dramatic clarity and narrative purpose"],
        },
    }

    @classmethod
    def generate_bible_for_project(
        cls,
        project_dir: Path | str,
        book_bible: Optional[Any] = None,
        roster_data: Optional[Dict[str, Any]] = None,
    ) -> PerformanceBible:
        """
        Synthesizes a PerformanceBible projecting all known characters in the project.
        """
        pdir = Path(project_dir).resolve()
        characters: Dict[str, CharacterPerformanceProfile] = {}

        # 1. From BookBible if present
        if book_bible is not None and hasattr(book_bible, "characters"):
            b_chars = book_bible.characters
            if isinstance(b_chars, dict):
                for name, entity in b_chars.items():
                    c_name = str(getattr(entity, "english_name", name)).strip()
                    if c_name and c_name not in ("Narrator", "Foley"):
                        sociolect = getattr(entity, "sociolect_archetype", "DEFAULT_DRAMATIC")
                        characters[c_name] = cls._build_character_profile(c_name, sociolect)
            elif isinstance(b_chars, list):
                for entity in b_chars:
                    c_name = str(getattr(entity, "english_name", "")).strip()
                    if c_name and c_name not in ("Narrator", "Foley"):
                        sociolect = getattr(entity, "sociolect_archetype", "DEFAULT_DRAMATIC")
                        characters[c_name] = cls._build_character_profile(c_name, sociolect)

        # 2. From character_roster.json if characters dictionary is empty
        if not characters and roster_data and "characters" in roster_data:
            r_chars = roster_data["characters"]
            if isinstance(r_chars, dict):
                for name, details in r_chars.items():
                    if name not in ("Narrator", "Foley"):
                        sociolect = "DEFAULT_DRAMATIC"
                        if isinstance(details, dict):
                            sociolect = details.get("sociolect_trait", "DEFAULT_DRAMATIC")
                        characters[name] = cls._build_character_profile(name, sociolect)
            elif isinstance(r_chars, list):
                for c in r_chars:
                    if isinstance(c, dict):
                        cname = c.get("english_name", c.get("display_name", ""))
                        if cname and cname not in ("Narrator", "Foley"):
                            sociolect = c.get("sociolect_trait", "DEFAULT_DRAMATIC")
                            characters[cname] = cls._build_character_profile(cname, sociolect)

        # 3. Add canonical Narrator performance profile
        bible = PerformanceBible(
            characters=characters,
            narrator_style={
                "baseline_pace": 1.0,
                "tone": "objective_cinematic_observer",
                "pause_multiplier": 1.0,
                "room_impulse": "neutral_studio",
                "delivery": "authoritative_restrained",
            },
            version="1.0",
        )
        return bible

    @classmethod
    def _build_character_profile(cls, name: str, sociolect: str) -> CharacterPerformanceProfile:
        preset_key = str(sociolect).strip().upper()
        preset = cls.SOCIOLECT_PRESETS.get(preset_key, cls.SOCIOLECT_PRESETS["DEFAULT_DRAMATIC"])

        return CharacterPerformanceProfile(
            character_name=name,
            baseline_pace=preset["baseline_pace"],
            baseline_energy=preset["baseline_energy"],
            articulation=preset["articulation"],
            emotional_behaviors=dict(preset["emotional_behaviors"]),
            restraint_level=preset["restraint_level"],
            speech_quirks=list(preset["speech_quirks"]),
            performance_rules=list(preset["performance_rules"]),
        )
