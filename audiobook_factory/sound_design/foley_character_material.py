#!/usr/bin/env python3
"""
Audiobook Factory - Capabilities 08 & 09: Character Foley & Material Matrix.
=============================================================================
Models character-specific movement physics (mass, footwear, armor, condition)
and the physical interaction matrix between exciter materials and resonator surfaces.
Enforces strict acoustic isolation between domestic tableware and weapon clashes.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.sound_design.contracts import (
    CharacterPhysicalProfile,
    RelativeIntensity,
    MixIntent,
)


# Exciter and Resonator Material Types
SURFACE_RESONATORS = {
    "stone_flagstone": {"damping": 0.15, "brightness": "bright_hard", "thud_weight": "heavy"},
    "wood_floorboards": {"damping": 0.40, "brightness": "warm_hollow", "thud_weight": "resonant"},
    "gravel": {"damping": 0.65, "brightness": "crunchy_granular", "thud_weight": "light"},
    "wet_mud": {"damping": 0.85, "brightness": "squelch_dull", "thud_weight": "heavy"},
    "grass_turf": {"damping": 0.80, "brightness": "soft_muffled", "thud_weight": "light"},
    "snow_crunch": {"damping": 0.70, "brightness": "crisp_compression", "thud_weight": "light"},
    "carpet_rug": {"damping": 0.90, "brightness": "deep_muffled", "thud_weight": "subdued"},
    "tile_marble": {"damping": 0.10, "brightness": "sharp_echoing", "thud_weight": "hard"},
    "water_puddle": {"damping": 0.50, "brightness": "splash_liquid", "thud_weight": "medium"},
}

FOOTWEAR_CHARACTERISTICS = {
    "heavy_boots": {"impact_sharpness": "heavy_clack", "weight_mult": 1.4, "ucs_sub": "Boots"},
    "light_leather": {"impact_sharpness": "soft_scuff", "weight_mult": 0.9, "ucs_sub": "Leather"},
    "hobnailed_clogs": {"impact_sharpness": "metallic_tap", "weight_mult": 1.3, "ucs_sub": "Clogs"},
    "bare_feet": {"impact_sharpness": "fleshy_slap", "weight_mult": 0.7, "ucs_sub": "Bare"},
    "sandals": {"impact_sharpness": "flapping_strap", "weight_mult": 0.8, "ucs_sub": "Sandals"},
    "slippers": {"impact_sharpness": "whisper_slide", "weight_mult": 0.6, "ucs_sub": "Slippers"},
}

ARMOR_FOLEY_CHARACTERISTICS = {
    "full_plate": {"clank_intensity": "prominent", "sound_tag": "plate_metal_clank"},
    "chainmail": {"clank_intensity": "subtle_bed", "sound_tag": "chain_rattle_jingle"},
    "leather_gear": {"clank_intensity": "whisper_quiet", "sound_tag": "leather_creak_taut"},
    "robes": {"clank_intensity": "whisper_quiet", "sound_tag": "cloth_swish_silk"},
    "travel_cloak": {"clank_intensity": "whisper_quiet", "sound_tag": "heavy_wool_flap"},
    "unencumbered": {"clank_intensity": "whisper_quiet", "sound_tag": "none"},
}


class MaterialMatrixEngine:
    """
    Physical interaction matrix between exciter materials and resonator surfaces.
    """

    @staticmethod
    def is_weapon_vs_tableware_collision(exciter: str, resonator: str) -> bool:
        """
        Safety check: Detects and rejects accidental weapon vs domestic tableware confusion.
        Prevents dining hall eating sounds from sounding like sword clashes.
        """
        exc = exciter.lower().strip()
        res = resonator.lower().strip()

        is_tableware = any(w in exc or w in res for w in ("plate", "dish", "bowl", "fork", "spoon", "goblet", "cup", "tableware"))
        is_weapon = any(w in exc or w in res for w in ("sword", "blade", "dagger", "axe", "spear", "weapon", "clash"))

        return is_tableware and is_weapon

    @classmethod
    def resolve_surface_interaction(
        cls,
        exciter: str,
        surface: str,
        energy: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Computes acoustic descriptor for exciter impacting surface.
        """
        surf_clean = surface.lower().strip()
        matched_surf = None
        for s in SURFACE_RESONATORS:
            if s in surf_clean or surf_clean in s:
                matched_surf = s
                break
        if not matched_surf:
            matched_surf = "stone_flagstone"

        surf_props = SURFACE_RESONATORS[matched_surf]

        # Enforce tableware isolation
        if cls.is_weapon_vs_tableware_collision(exciter, surface):
            # Domestic tableware isolation: force domestic ceramic/glass profile
            logger.warning(
                f"[MaterialMatrix] Tableware vs Weapon collision detected for '{exciter}' on '{surface}'. Forcing DOMETabl isolation."
            )
            return {
                "ucs_category": "DOMETabl",
                "sound_slug": f"tableware_plate_clatter_on_{matched_surf}",
                "brightness": "sharp_ceramic",
                "damping": surf_props["damping"],
                "relative_intensity": "subtle_bed",
            }

        # Standard material resolution
        exc_clean = exciter.lower().strip()
        ucs = "FOLEOth"
        if any(w in exc_clean for w in ("sword", "blade", "steel", "dagger")):
            ucs = "WEAPSwd"
        elif any(w in exc_clean for w in ("plate", "bowl", "cup", "goblet")):
            ucs = "DOMETabl"
        elif any(w in exc_clean for w in ("wood", "chair", "table")):
            ucs = "FURNChr"
        elif any(w in exc_clean for w in ("cloth", "robe", "cloak")):
            ucs = "CLOTFab"

        intensity: RelativeIntensity = "prominent" if energy > 0.75 else ("subtle_bed" if energy > 0.35 else "whisper_quiet")

        return {
            "ucs_category": ucs,
            "sound_slug": f"{ucs.lower()}_{exc_clean}_on_{matched_surf}",
            "brightness": surf_props["brightness"],
            "damping": surf_props["damping"],
            "thud_weight": surf_props["thud_weight"],
            "relative_intensity": intensity,
        }


class CharacterFoleyRegistry:
    """
    Roster registry maintaining character physical attributes for movement sound design.
    """

    def __init__(self):
        self._profiles: Dict[str, CharacterPhysicalProfile] = {}
        self.matrix = MaterialMatrixEngine()

    def register_character(self, profile: CharacterPhysicalProfile) -> None:
        """Register or update a character's physical profile."""
        self._profiles[profile.character_name.lower().strip()] = profile

    def get_character(self, character_name: str) -> Optional[CharacterPhysicalProfile]:
        """Fetch character physical profile."""
        if not character_name:
            return None
        return self._profiles.get(character_name.lower().strip())

    def resolve_movement_foley(
        self,
        character_name: str,
        surface: str = "stone_flagstone",
        movement_pace: str = "walk",
        stealth_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        Synthesizes movement foley parameters for a character on a specific surface.
        """
        profile = self.get_character(character_name) or CharacterPhysicalProfile(
            character_name=character_name or "Character",
            body_mass="average",
            footwear="heavy_boots",
            equipment_weight="leather_gear",
            physical_condition="stealthy_stalking" if stealth_mode else "normal",
        )

        fw = FOOTWEAR_CHARACTERISTICS.get(profile.footwear, FOOTWEAR_CHARACTERISTICS["heavy_boots"])
        armor = ARMOR_FOLEY_CHARACTERISTICS.get(profile.equipment_weight, ARMOR_FOLEY_CHARACTERISTICS["leather_gear"])
        surf_inter = self.matrix.resolve_surface_interaction(profile.footwear, surface)

        # Intensity derivation
        intensity: RelativeIntensity = "subtle_bed"
        if profile.physical_condition == "stealthy_stalking" or stealth_mode:
            intensity = "whisper_quiet"
        elif profile.body_mass == "imposing_heavy" or movement_pace in ("run", "charge", "march"):
            intensity = "prominent"

        # Footstep cadence
        interval_sec = 0.55
        if movement_pace == "run":
            interval_sec = 0.32
        elif profile.physical_condition == "injured_limping":
            interval_sec = 0.75  # Irregular asymmetric limp cadence

        return {
            "character": profile.character_name,
            "footwear": profile.footwear,
            "footwear_sub": fw["ucs_sub"],
            "surface": surface,
            "armor_layer": armor["sound_tag"] if armor["sound_tag"] != "none" else None,
            "relative_intensity": intensity,
            "step_interval_sec": interval_sec,
            "is_limping": profile.physical_condition == "injured_limping",
            "mix_intent": MixIntent(
                duck_under_dialogue=True,
                carve_vocal_presence=False,
            ),
        }


_GLOBAL_FOLEY_REGISTRY: Optional[CharacterFoleyRegistry] = None

def get_character_foley_registry() -> CharacterFoleyRegistry:
    """Returns singleton instance of CharacterFoleyRegistry."""
    global _GLOBAL_FOLEY_REGISTRY
    if _GLOBAL_FOLEY_REGISTRY is None:
        _GLOBAL_FOLEY_REGISTRY = CharacterFoleyRegistry()
    return _GLOBAL_FOLEY_REGISTRY
