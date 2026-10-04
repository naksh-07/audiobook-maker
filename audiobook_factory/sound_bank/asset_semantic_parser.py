#!/usr/bin/env python3
"""
Audiobook Factory - Physical & Semantic Asset Feature Parser.
==============================================================
Extracts objective physical acoustics (exciter, resonator, action_type, surface)
and baseline dramatic indicators directly from asset naming conventions.
100% deterministic, zero LLM cost, zero hallucinations.
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Optional


class AssetSemanticParser:
    """Deterministic token parser for physical and acoustic properties."""

    @staticmethod
    def parse(filename: str, rel_path: str = "", category: str = "", subcategory: str = "") -> Dict[str, Any]:
        text = f"{rel_path} {filename}".lower().replace("\\", "/").replace("_", " ").replace("-", " ")
        tokens = set(re.findall(r"[a-z0-9]+", text))

        # -------------------------------------------------------------
        # 1. PHYSICAL EXCITERS (Primary energy injector)
        # -------------------------------------------------------------
        exciter = "unspecified"
        if "silver" in tokens:
            exciter = "silver"
        elif any(t in tokens for t in ["steel", "iron", "blade", "sword", "dagger", "knife", "metal"]):
            exciter = "steel"
        elif any(t in tokens for t in ["wood", "wooden", "branch", "table", "chair", "staff"]):
            exciter = "wood"
        elif any(t in tokens for t in ["leather", "boot", "shoe", "armor", "belt"]):
            exciter = "leather"
        elif any(t in tokens for t in ["stone", "rock", "gravel", "cobble", "boulder"]):
            exciter = "stone"
        elif any(t in tokens for t in ["fire", "flame", "torch", "igni", "burn", "spark"]):
            exciter = "fire"
        elif any(t in tokens for t in ["magic", "spell", "sign", "aard", "quen", "axii", "yrden", "arcane", "portal"]):
            exciter = "magic"
        elif any(t in tokens for t in ["wind", "gust", "breeze", "gale", "air"]):
            exciter = "wind"
        elif any(t in tokens for t in ["water", "rain", "splash", "swim", "dive", "river", "wave"]):
            exciter = "water"
        elif any(t in tokens for t in ["roar", "screech", "grunt", "snarl", "growl", "hiss", "voice", "scream"]):
            exciter = "vocal_cords"
        elif any(t in tokens for t in ["coin", "gold", "purse", "pouch", "clink"]):
            exciter = "coin"
        elif any(t in tokens for t in ["glass", "bottle", "vial", "potion"]):
            exciter = "glass"
        elif category == "AMB" or "amb" in tokens:
            exciter = "environment"

        # -------------------------------------------------------------
        # 2. PHYSICAL RESONATORS (Acoustic vibrating body)
        # -------------------------------------------------------------
        resonator = "room"
        if any(t in tokens for t in ["blade", "parry", "clash"]):
            resonator = "blade"
        elif any(t in tokens for t in ["shield", "armor", "chainmail", "breastplate"]):
            resonator = "armor"
        elif any(t in tokens for t in ["throat", "mouth", "chest"]):
            resonator = "throat"
        elif any(t in tokens for t in ["door", "gate", "chest", "barrel"]):
            resonator = "door"
        elif any(t in tokens for t in ["ground", "floor", "cobblestone", "dirt", "mud"]):
            resonator = "ground"
        elif any(t in tokens for t in ["open air", "forest", "mountain", "field"]) or category == "AMB":
            resonator = "open_air"
        elif any(t in tokens for t in ["cave", "crypt", "catacomb", "dungeon"]):
            resonator = "stone_cavern"
        elif any(t in tokens for t in ["tavern", "inn", "hall"]):
            resonator = "tavern"

        # -------------------------------------------------------------
        # 3. PHYSICAL ACTION TYPES (How the sound is made)
        # -------------------------------------------------------------
        action_type = "general"
        if any(t in tokens for t in ["parry", "block", "deflect"]):
            action_type = "parry"
        elif any(t in tokens for t in ["draw", "unsheathe", "holster", "sheathe"]):
            action_type = "draw"
        elif any(t in tokens for t in ["swing", "whoosh", "slash", "cut"]):
            action_type = "swing"
        elif any(t in tokens for t in ["hit", "impact", "strike", "bash", "slam"]):
            action_type = "impact"
        elif any(t in tokens for t in ["footstep", "step", "walk", "run", "stride"]):
            action_type = "footstep"
        elif any(t in tokens for t in ["roar", "screech", "howl", "growl", "bark"]):
            action_type = "roar"
        elif any(t in tokens for t in ["hiss", "snarl"]):
            action_type = "hiss"
        elif any(t in tokens for t in ["cast", "burst", "shockwave", "blast"]):
            action_type = "cast"
        elif any(t in tokens for t in ["creak", "groan"]):
            action_type = "creak"
        elif any(t in tokens for t in ["break", "splinter", "shatter", "crack"]):
            action_type = "break"
        elif any(t in tokens for t in ["drop", "fall", "clatter"]):
            action_type = "drop"
        elif any(t in tokens for t in ["rustle", "movement", "clink"]):
            action_type = "rustle"
        elif category == "AMB" or "amb" in tokens:
            action_type = "ambient_bed"
        elif category == "MUS" or "music" in tokens:
            action_type = "musical_cue"

        # -------------------------------------------------------------
        # 4. PHYSICAL SURFACE (Boundary interaction)
        # -------------------------------------------------------------
        surface = "unspecified"
        if any(t in tokens for t in ["metal", "steel", "blade", "armor"]):
            surface = "metal"
        elif any(t in tokens for t in ["wood", "floor", "table", "door"]):
            surface = "wood"
        elif any(t in tokens for t in ["stone", "cobble", "rock"]):
            surface = "stone"
        elif any(t in tokens for t in ["flesh", "body", "gore", "blood"]):
            surface = "flesh"
        elif any(t in tokens for t in ["dirt", "mud", "earth", "gravel"]):
            surface = "dirt"
        elif any(t in tokens for t in ["water", "stream", "puddle"]):
            surface = "water"

        # -------------------------------------------------------------
        # 5. DRAMATIC & NARRATIVE PROFILE
        # -------------------------------------------------------------
        dramatic_role = "general"
        valence = 0.0
        arousal = 0.5
        tension = 0.5
        archetypes = []

        if action_type in ("impact", "parry", "swing") or "combat" in tokens:
            dramatic_role = "action_confirmation"
            arousal = 0.8
            tension = 0.7
            archetypes.extend(["COMBAT", "PHYSICAL_ACTION"])
        elif any(t in tokens for t in ["monster", "creature", "beast", "drowner", "leshen", "griffin", "bruxa", "fiend"]):
            dramatic_role = "threat_foreshadowing"
            valence = -0.5
            arousal = 0.85
            tension = 0.85
            archetypes.extend(["MONSTER_THREAT", "DANGER"])
        elif any(t in tokens for t in ["magic", "sign", "spell", "arcane"]):
            dramatic_role = "action_confirmation"
            arousal = 0.75
            tension = 0.6
            archetypes.extend(["ARCANE_ACTION"])
        elif category == "AMB" or "amb" in tokens:
            dramatic_role = "ambient_grounding"
            arousal = 0.3
            tension = 0.4
            archetypes.extend(["SETTING_ATMOSPHERE"])
        elif category == "MUS" or "music" in tokens:
            dramatic_role = "emotional_resonance"
            arousal = 0.6
            tension = 0.6
            archetypes.extend(["DRAMATIC_SCORE"])
        elif action_type in ("footstep", "rustle"):
            dramatic_role = "punctuation"
            arousal = 0.4
            tension = 0.3
            archetypes.extend(["CHARACTER_MOVEMENT"])

        # Add monster name to archetypes if detected
        monsters = ["griffin", "drowner", "leshen", "bruxa", "fiend", "nekker", "golem", "wraith", "ghoul", "harpy", "siren", "vampire", "werewolf", "striga"]
        for m in monsters:
            if m in tokens:
                archetypes.append(m.upper())
                break

        # Add sign name to archetypes if detected
        signs = ["aard", "igni", "quen", "axii", "yrden"]
        for s in signs:
            if s in tokens:
                archetypes.append(s.upper())
                break

        # -------------------------------------------------------------
        # 6. MIX COMPATIBILITY DEFAULTS
        # -------------------------------------------------------------
        vocal_risk = "LOW"
        if exciter in ("vocal_cords", "screech") or (action_type in ("roar", "hiss") and arousal > 0.8):
            vocal_risk = "SEVERE"
        elif action_type in ("impact", "parry") and exciter in ("steel", "silver"):
            vocal_risk = "MODERATE"

        foreground_strength = 0.75 if dramatic_role in ("action_confirmation", "threat_foreshadowing") else (0.25 if dramatic_role == "ambient_grounding" else 0.50)

        return {
            "physical": {
                "exciter": exciter,
                "resonator": resonator,
                "action_type": action_type,
                "surface": surface,
            },
            "dramatic": {
                "dramatic_role": dramatic_role,
                "narrative_archetypes": archetypes,
                "valence": valence,
                "arousal": arousal,
                "tension": tension,
                "foreground_strength": foreground_strength,
            },
            "mix": {
                "voice_masking_risk": vocal_risk,
                "whisper_compatibility": 0.3 if vocal_risk == "SEVERE" else (0.6 if vocal_risk == "MODERATE" else 0.85),
                "ducking_recommendation_db": -16.0 if vocal_risk == "SEVERE" else (-12.0 if vocal_risk == "MODERATE" else -6.0),
            }
        }
