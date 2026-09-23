#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 4: Cinema Acoustic Bus Matrix & Dynamic Ducking (Pydantic v2).
"New Room 3": Manages multi-bus dynamic ducking profiles, UCS taxonomy classification,
voice concurrency limiting (priority stealing), and formant spectral pocketing.
"""

from __future__ import annotations
import re
import logging
from typing import Dict, Any, List, Optional, Literal, Union

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger("audiobook_factory.acoustic_bus_matrix")


class DuckingProfile(BaseModel):
    """
    Sidechain ducking profile parameters calibrated to narrative dramatic intensity.
    Protects dialogue intelligibility without jarring pumping artifacts.
    """
    model_config = ConfigDict(extra="ignore")

    profile_name: Literal["intimate_dialogue", "standard_speech", "combat_shouting", "heavy_impact", "combat_shock"] = Field(
        ..., description="Dramatic voice level profile"
    )
    attenuation_db: float = Field(default=-16.0, ge=-40.0, le=-3.0, description="Music/ambience attenuation gain while dialogue speaks in dB")
    attack_ms: int = Field(default=15, ge=1, le=200, description="Compressor attack time in milliseconds")
    release_ms: int = Field(default=350, ge=50, le=5000, description="Compressor release time in milliseconds")
    spectral_carve_hz: int = Field(default=2400, ge=800, le=5000, description="Center frequency for vocal formant notch pocket in Hz")
    spectral_carve_depth_db: float = Field(default=-6.0, ge=-18.0, le=-1.0, description="Notch attenuation gain in dB")


# Standard Calibrated Industry Presets
DUCKING_PRESETS: Dict[str, DuckingProfile] = {
    "intimate_dialogue": DuckingProfile(
        profile_name="intimate_dialogue",
        attenuation_db=-10.0,
        attack_ms=30,
        release_ms=600,
        spectral_carve_hz=2200,
        spectral_carve_depth_db=-4.0,
    ),
    "standard_speech": DuckingProfile(
        profile_name="standard_speech",
        attenuation_db=-16.0,
        attack_ms=15,
        release_ms=350,
        spectral_carve_hz=2400,
        spectral_carve_depth_db=-6.0,
    ),
    "combat_shouting": DuckingProfile(
        profile_name="combat_shouting",
        attenuation_db=-22.0,
        attack_ms=8,
        release_ms=250,
        spectral_carve_hz=2600,
        spectral_carve_depth_db=-8.0,
    ),
    "heavy_impact": DuckingProfile(
        profile_name="heavy_impact",
        attenuation_db=-26.0,
        attack_ms=5,
        release_ms=800,
        spectral_carve_hz=1500,
        spectral_carve_depth_db=-10.0,
    ),
    "combat_shock": DuckingProfile(
        profile_name="combat_shock",
        attenuation_db=-24.0,
        attack_ms=8,
        release_ms=4000,
        spectral_carve_hz=2600,
        spectral_carve_depth_db=-10.0,
    ),
}

PROFILE_INTIMATE = DUCKING_PRESETS["intimate_dialogue"]
PROFILE_STANDARD = DUCKING_PRESETS["standard_speech"]
PROFILE_COMBAT = DUCKING_PRESETS["combat_shouting"]
PROFILE_HEAVY_IMPACT = DUCKING_PRESETS["heavy_impact"]
PROFILE_COMBAT_SHOCK = DUCKING_PRESETS["combat_shock"]


def get_ducking_profile(name_or_scene_type: str) -> DuckingProfile:
    """Resolves ducking profile by name or dramatic scene mood/intensity."""
    q = (name_or_scene_type or "").lower().strip()
    if "shock" in q or "tinnitus" in q or "concussion" in q:
        return PROFILE_COMBAT_SHOCK
    elif "combat" in q or "battle" in q or "fight" in q or "action" in q:
        return PROFILE_COMBAT
    elif "intimate" in q or "whisper" in q or "emotional" in q or "quiet" in q:
        return PROFILE_INTIMATE
    elif "impact" in q or "explosion" in q or "climax" in q or "heavy" in q:
        return PROFILE_HEAVY_IMPACT
    return DUCKING_PRESETS.get(q, PROFILE_STANDARD)


# Universal Category System (UCS) Category Lookup
UCS_RULES = [
    (("sword", "blade", "parry", "clash", "sheathe", "draw"), "WEAPSwd"),
    (("knife", "dagger"), "WEAPKnf"),
    (("plate", "armor", "cuirass", "chainmail", "iron_shield"), "WEAPMtl"),
    (("mace", "warhammer", "blunt", "club"), "WEAPBlun"),
    (("bow", "arrow", "whipcrack", "flyby", "arrow_whistle"), "WEAPBow"),
    (("punch", "kick", "fist", "strike"), "FGHFPun"),
    (("bone", "snap", "flesh", "cartilage", "blood", "squelch", "tear"), "GOREAnat"),
    (("footstep", "walk", "run", "gravel", "boots"), "FOLEFoot"),
    (("cloth", "belt", "leather"), "FOLEMov"),
    (("body", "fall", "thud", "collapse"), "IMPTBody"),
    (("sub_drop", "lfe", "thump", "solar_plexus", "shockwave"), "LFEDrop"),
    (("metal", "clank", "chain", "anvil"), "IMPTMtl"),
    (("wood", "timber", "floor"), "IMPTWod"),
    (("door", "gate", "latch"), "DOORWood"),
    (("magic", "spell", "igni", "aard", "quen", "axii", "yrden", "zap", "spark"), "MAGCSpell"),
    (("fire", "flame", "torch", "hearth", "burn"), "FIREComb"),
    (("wind", "gale", "blizzard", "breeze"), "WNDDAmbi"),
    (("rain", "storm", "thunder"), "RAINStr"),
    (("monster", "beast", "striga", "ghoul", "wolf", "roar", "snarl", "howl"), "CREAVoc"),
    (("grunt", "groan", "battlecry", "pant", "choke", "gasp", "spits"), "VOXExrt"),
    (("tavern", "crowd", "murmur", "chatter"), "CROWGen"),
]


def derive_ucs_category(action_verb_or_cue: str, exciter: str = "") -> str:
    """
    Resolves Universal Category System (UCS) 7-character Category ID
    from action beat, cue name, or physical exciter description.
    """
    text = f"{action_verb_or_cue} {exciter}".lower()
    for keywords, ucs_code in UCS_RULES:
        if any(re.search(rf"\b{re.escape(kw)}", text) for kw in keywords):
            return ucs_code
    return "MISCGnl"


def filter_concurrency_window(
    cues: List[Any],
    window_ms: int = 200,
    max_concurrency: int = 3,
) -> List[Any]:
    """
    Voice Limiter & Priority Stealing Algorithm.
    Prevents acoustic clutter / transient mud by ensuring no sliding window of `window_ms`
    exceeds `max_concurrency` overlapping Foley/SFX triggers.
    Preserves highest priority / loudest cues and drops lowest priority collisions.
    """
    if not cues or len(cues) <= max_concurrency:
        return cues

    # Sort primarily by timeline start_ms, secondarily by gain/priority
    def _cue_priority(cue: Any) -> float:
        gain = getattr(cue, "gain_dbfs", -15.0)
        return float(gain)

    # Sort chronological
    sorted_cues = sorted(cues, key=lambda c: getattr(c, "start_ms", 0) or 0)
    accepted_cues: List[Any] = []

    for cue in sorted_cues:
        c_start = getattr(cue, "start_ms", 0) or 0
        # Count overlapping cues in sliding window [c_start - window_ms, c_start + window_ms]
        window_cues = [
            ac for ac in accepted_cues
            if abs((getattr(ac, "start_ms", 0) or 0) - c_start) < window_ms
        ]

        if len(window_cues) < max_concurrency:
            accepted_cues.append(cue)
        else:
            # Check if current cue has higher gain than the weakest cue in the window
            window_cues.sort(key=_cue_priority)
            weakest = window_cues[0]
            if _cue_priority(cue) > _cue_priority(weakest):
                # Priority steal: replace weakest cue
                accepted_cues.remove(weakest)
                accepted_cues.append(cue)
                logger.debug(
                    f"  [Acoustic Bus] Priority steal: dropped cue at {getattr(weakest, 'start_ms', 0)}ms "
                    f"for higher-priority cue at {c_start}ms"
                )

    # Re-sort accepted list chronologically
    return sorted(accepted_cues, key=lambda c: getattr(c, "start_ms", 0) or 0)


def get_spectral_pocketing_filter(
    notch_hz: int = 2400,
    depth_db: float = -6.0,
    q: float = 1.5,
) -> str:
    """
    Generates an FFmpeg parametric equalizer filter string for vocal formant spectral carving.
    Carves out vocal presence frequencies in music/effects stems to guarantee zero vocal masking.
    """
    n_hz = max(400, min(8000, int(notch_hz)))
    d_db = max(-24.0, min(-1.0, float(depth_db)))
    q_val = max(0.5, min(5.0, float(q)))
    return f"equalizer=f={n_hz}:width_type=q:w={q_val:.2f}:g={d_db:.2f}"
