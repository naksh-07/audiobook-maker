#!/usr/bin/env python3
"""
Audiobook Factory - Capability 11: Supernatural & Magical Sound Language Engine.
=================================================================================
Implements a coherent, reusable sonic vocabulary for magical and supernatural events:
- Deconstructs spells and supernatural acts into canonical stages:
  CHARGE -> RELEASE -> PROJECTILE -> IMPACT / SHIELD / TELEPORT / CURSE.
- Preserves acoustic continuity across recurring spells and artifacts.
- Structures power levels (subtle_minor, standard, high_potency, cataclysmic).
- Emits clean mix intent with sidechain triggers and high attention priority.
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Optional, Tuple, Literal
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.sound_design.contracts import (
    MagicalSoundSpec,
    RelativeIntensity,
    AttentionPriority,
    SpatialMetadata,
    MixIntent,
)


CANONICAL_SPELL_FAMILIES = {
    # Witcher Signs & Dark Fantasy
    "aard": {"family": "kinetic_telekinetic", "default_stage": "release_burst"},
    "igni": {"family": "elemental_fire", "default_stage": "release_burst"},
    "quen": {"family": "shield_barrier", "default_stage": "shield_barrier"},
    "axii": {"family": "enchantment_mind", "default_stage": "charge_hum"},
    "yrden": {"family": "runic_barrier", "default_stage": "shield_barrier"},

    # High Fantasy / Pottermore Archetypes
    "lumos": {"family": "celestial_illumination", "default_stage": "charge_hum"},
    "expelliarmus": {"family": "kinetic_disarm", "default_stage": "release_burst"},
    "stupefy": {"family": "concussive_stun", "default_stage": "release_burst"},
    "expecto patronum": {"family": "celestial_silver_shimmer", "default_stage": "release_burst"},
    "avada kedavra": {"family": "shadow_necrotic_lethal", "default_stage": "release_burst"},
    "alohomora": {"family": "runic_unlock", "default_stage": "release_burst"},
    "protego": {"family": "shield_barrier", "default_stage": "shield_barrier"},
    "reparo": {"family": "temporal_reconstruction", "default_stage": "charge_hum"},
}

MAGIC_KEYWORD_PATTERNS = [
    (re.compile(r"\b(incantation|cast|chanted|whispered\s+the\s+words|spoke\s+the\s+spell)\b", re.IGNORECASE), "charge_hum"),
    (re.compile(r"\b(wand\s+flashed|burst\s+of\s+sparks|flash\s+of\s+light|sign\s+flared)\b", re.IGNORECASE), "release_burst"),
    (re.compile(r"\b(streaked\s+across|jet\s+of\s+light|beam\s+hissed|whistling\s+bolt)\b", re.IGNORECASE), "projectile_travel"),
    (re.compile(r"\b(barrier\s+shimmered|shield\s+deflected|protective\s+ward|shield\s+flared)\b", re.IGNORECASE), "shield_barrier"),
    (re.compile(r"\b(dissipated|spell\s+struck|magical\s+impact|blast\s+shattered)\b", re.IGNORECASE), "impact_strike"),
    (re.compile(r"\b(disapparated|apparated|teleported|vanished\s+with\s+a\s+crack|inward\s+rush)\b", re.IGNORECASE), "teleport_displacement"),
    (re.compile(r"\b(transfigured|transformed|morphed\s+into|flesh\s+twisted)\b", re.IGNORECASE), "transformation"),
    (re.compile(r"\b(levitated|lifted\s+into\s+the\s+air|hovered|gravitational\s+hum)\b", re.IGNORECASE), "telekinesis"),
    (re.compile(r"\b(curse|necrotic|withered|dark\s+miasma|black\s+smoke)\b", re.IGNORECASE), "curse_necrotic"),
    (re.compile(r"\b(wound\s+knitted|healed|golden\s+warmth|soothing\s+light)\b", re.IGNORECASE), "healing_solace"),
    (re.compile(r"\b(runes\s+glowed|relic\s+hummed|artifact\s+pulsed|ancient\s+device)\b", re.IGNORECASE), "artifact_activation"),
]


class MagicalSoundEngine:
    """
    Supernatural and Magical Sound Language Engine.
    """

    def __init__(self):
        self._custom_spells: Dict[str, Dict[str, Any]] = dict(CANONICAL_SPELL_FAMILIES)

    def register_canonical_spell(self, name: str, family: str, default_stage: str = "release_burst") -> None:
        """Register or extend canonical spell definitions."""
        self._custom_spells[name.lower().strip()] = {
            "family": family,
            "default_stage": default_stage,
        }

    def detect_magic_events(
        self,
        segments: List[Dict[str, Any]],
        tension_level: float = 0.5,
    ) -> List[MagicalSoundSpec]:
        """
        Scans screenplay segments for supernatural occurrences, spell names, or magical keywords.
        """
        events: List[MagicalSoundSpec] = []

        for idx, seg in enumerate(segments):
            text = seg.get("text", "")
            sfx_cues = seg.get("sfx_cues") or []
            combined_text = (text + " " + " ".join(str(c) for c in sfx_cues)).lower()
            text_lower = combined_text

            # 1. Check known canonical spell names first
            detected_spell = None
            spell_info = None
            for s_name, info in self._custom_spells.items():
                if s_name in text_lower:
                    detected_spell = s_name
                    spell_info = info
                    break

            if detected_spell and spell_info:
                stage = spell_info["default_stage"]
                family = spell_info["family"]

                power: Literal["subtle_minor", "standard", "high_potency", "cataclysmic"] = "standard"
                if tension_level > 0.85 or "unforgivable" in text_lower or "cataclysm" in text_lower:
                    power = "high_potency"
                elif tension_level < 0.35:
                    power = "subtle_minor"

                events.append(
                    MagicalSoundSpec(
                        event_id=f"magic_{idx+1}_{detected_spell.replace(' ', '_')}",
                        spell_or_artifact_name=detected_spell.title(),
                        stage=stage,  # type: ignore
                        power_level=power,
                        relative_intensity="explosive_impact" if power in ("high_potency", "cataclysmic") else "prominent",
                        priority="CRITICAL" if power == "cataclysmic" else "HIGH",
                        sonic_identity_family=family,
                        asset_path=f"magic_{family}_{stage}_{power}.wav",
                        decision_reason=f"Recognized canonical spell '{detected_spell}' in segment text",
                    )
                )
                continue

            # 2. Check general magic patterns in text and cues
            for pat, stage in MAGIC_KEYWORD_PATTERNS:
                m = pat.search(text)
                if not m:
                    for cue in sfx_cues:
                        m = pat.search(str(cue))
                        if m:
                            break
                if m:
                    power = "standard"
                    if tension_level > 0.8:
                        power = "high_potency"

                    events.append(
                        MagicalSoundSpec(
                            event_id=f"magic_{idx+1}_{stage}",
                            spell_or_artifact_name=f"Spell_{stage.title()}",
                            stage=stage,  # type: ignore
                            power_level=power,
                            relative_intensity="explosive_impact" if power == "high_potency" else "prominent",
                            priority="HIGH",
                            sonic_identity_family="generic_arcane",
                            asset_path=f"magic_arcane_{stage}.wav",
                            decision_reason=f"Detected supernatural keyword '{m.group(0)}'",
                        )
                    )
                    break


        return events

    def synthesize_spell_sequence(
        self,
        spell_name: str,
        power_level: Literal["subtle_minor", "standard", "high_potency", "cataclysmic"] = "standard",
        target_stage: Optional[str] = None,
    ) -> List[MagicalSoundSpec]:
        """
        Generates full canonical stage sequence for a major magical act:
        CHARGE -> RELEASE -> IMPACT (or SHIELD).
        """
        s_clean = spell_name.lower().strip()
        info = self._custom_spells.get(s_clean, {"family": "generic_arcane", "default_stage": "release_burst"})
        family = info["family"]

        stages = ["charge_hum", "release_burst", "impact_strike"]
        if target_stage:
            stages = [target_stage]
        elif info["default_stage"] == "shield_barrier":
            stages = ["charge_hum", "shield_barrier"]

        specs: List[MagicalSoundSpec] = []
        for idx, st in enumerate(stages):
            specs.append(
                MagicalSoundSpec(
                    event_id=f"magic_seq_{s_clean.replace(' ', '_')}_{st}",
                    spell_or_artifact_name=spell_name.title(),
                    stage=st,  # type: ignore
                    power_level=power_level,
                    relative_intensity="explosive_impact" if st in ("release_burst", "impact_strike") and power_level != "subtle_minor" else "prominent",
                    priority="HIGH",
                    sonic_identity_family=family,
                    asset_path=f"magic_{family}_{st}_{power_level}.wav",
                    decision_reason=f"Synthesized sequence stage {idx+1}/{len(stages)} for {spell_name}",
                )
            )

        return specs


_GLOBAL_MAGIC_ENGINE: Optional[MagicalSoundEngine] = None

def get_magical_sound_engine() -> MagicalSoundEngine:
    """Returns singleton instance of MagicalSoundEngine."""
    global _GLOBAL_MAGIC_ENGINE
    if _GLOBAL_MAGIC_ENGINE is None:
        _GLOBAL_MAGIC_ENGINE = MagicalSoundEngine()
    return _GLOBAL_MAGIC_ENGINE
