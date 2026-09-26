#!/usr/bin/env python3
"""
Audiobook Factory - Capabilities 10 & 12: Narrative Hard SFX & Creature Sound Engines.
====================================================================================
Hard SFX System:
- Separates major narrative actions (impacts, explosions, gate slams, structural crashes)
  from subtle character foley.
- Emits high attention priority (HIGH / CRITICAL) and mix intent with sidechain triggers.

Creature Sound System:
- Models non-human creatures as coherent acoustic entities across 4 layers:
  vocalizations, respiration, heavy locomotion, and body surface texture.
- Tracks behavioral states (calm, alert, stalking, aggressive, attacking, retreating).
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.sound_design.contracts import (
    HardSFXEventSpec,
    CreatureSoundSpec,
    AttentionPriority,
    RelativeIntensity,
    MixIntent,
    SpatialMetadata,
    ProximityZone,
)


from audiobook_factory.sound_design.asset_retriever import get_asset_retriever


HARD_SFX_KEYWORD_MAP = [
    (re.compile(r"\b(explosion|exploded|blast|detonat|burst\s+apart)\b", re.IGNORECASE), "explosion_concussive", True, "CRITICAL"),
    (re.compile(r"\b(gate\s+slammed|slammed\s+shut|portcullis\s+fell|door\s+banged\s+shut)\b", re.IGNORECASE), "door_gate_slam", True, "HIGH"),
    (re.compile(r"\b(crush|smashed|collapsed|structural\s+failure|timber\s+snapped|shatter\w*|broken)\b", re.IGNORECASE), "destruction_crash", True, "HIGH"),
    (re.compile(r"\b(swords?\s+clashed|blade\s+struck|iron\s+collided|sparks\s+flew)\b", re.IGNORECASE), "impact_weapon", False, "HIGH"),
    (re.compile(r"\b(body\s+slammed|thrown\s+against|tackled\s+to|heavy\s+impact)\b", re.IGNORECASE), "impact_body", False, "HIGH"),
    (re.compile(r"\b(fireball|engulfed\s+in\s+flames|erupted\s+in\s+fire)\b", re.IGNORECASE), "fire_combustion", False, "HIGH"),
    (re.compile(r"\b(plunged\s+into\s+water|splash|wave\s+crashed)\b", re.IGNORECASE), "water_splash", False, "HIGH"),
    (re.compile(r"\b(carriage\s+overturned|wheel\s+shattered|wagon\s+crash)\b", re.IGNORECASE), "collision_structural", True, "HIGH"),
]

CREATURE_VOCAL_PATTERNS = [
    (re.compile(r"\b(roared|roar|roaring)\b", re.IGNORECASE), "vocalization", "aggressive"),
    (re.compile(r"\b(growled|growl|growling|snarled|snarl)\b", re.IGNORECASE), "vocalization", "stalking"),
    (re.compile(r"\b(screeched|screech|shrieked|screaming\s+beast)\b", re.IGNORECASE), "vocalization", "attacking"),
    (re.compile(r"\b(hissed|hiss|hissing)\b", re.IGNORECASE), "vocalization", "alert_curious"),
    (re.compile(r"\b(chattered|chitin\s+clicking|scuttling)\b", re.IGNORECASE), "body_mass_texture", "stalking"),
    (re.compile(r"\b(guttural\s+pant|wheezing\s+breath|snorted)\b", re.IGNORECASE), "breathing", "calm"),
    (re.compile(r"\b(heavy\s+thuds|talons\s+raking|wings\s+buffeted)\b", re.IGNORECASE), "locomotion_step", "stalking"),
    (re.compile(r"\b(whined|yelped|whimpered\s+in\s+pain)\b", re.IGNORECASE), "injured_reaction", "injured_pained"),
]


class HardSFXEngine:
    """
    Action & Hard SFX Event Detector and Planner.
    """

    def detect_events_from_segments(
        self,
        segments: List[Dict[str, Any]],
        tension_level: float = 0.5,
    ) -> List[HardSFXEventSpec]:
        """
        Detects major narrative impact events across screenplay segments.
        Anchors timing and resolution to actual segments.
        """
        events: List[HardSFXEventSpec] = []
        retriever = get_asset_retriever()

        for idx, seg in enumerate(segments):
            text = seg.get("text", "")
            sfx_cues = seg.get("sfx_cues") or []
            seg_idx = int(seg.get("segment_index") or seg.get("index") or (idx + 1))
            seg_start = int(seg.get("start_ms", 0))

            # Check explicit cues first
            for cue in sfx_cues:
                cue_lower = str(cue).lower()
                for pat, sfx_type, has_lfe, priority in HARD_SFX_KEYWORD_MAP:
                    if pat.search(cue_lower):
                        desc = retriever.resolve_hard_sfx_asset(sfx_type, context_tags=[str(seg.get("acoustic_env", ""))])
                        asset_p = desc.filepath if desc else ""
                        events.append(
                            HardSFXEventSpec(
                                event_id=f"hardsfx_{seg_idx}_{sfx_type}",
                                segment_index=seg_idx,
                                sfx_type=sfx_type,  # type: ignore
                                description=f"Narrative cue: {cue}",
                                start_ms=seg_start,
                                relative_intensity="explosive_impact" if priority == "CRITICAL" else "prominent",
                                priority=priority,  # type: ignore
                                has_lfe_sub_bass=has_lfe,
                                asset_path=asset_p,
                                decision_reason=f"Matched explicit screenplay sfx cue '{cue}'",
                                timing_rationale=f"Anchored to narrative cue '{cue}' in segment {seg_idx}",
                                dramatic_purpose=f"Concussive physical impact ({sfx_type})",
                                confidence=0.95,
                                provenance_segment_uid=seg.get("uid"),
                                provenance_beat_id=seg.get("beat_id"),
                            )
                        )
                        break

            # Check text prose
            for pat, sfx_type, has_lfe, priority in HARD_SFX_KEYWORD_MAP:
                match = pat.search(text)
                if match:
                    # Avoid duplicate if cue already caught it
                    if not any(e.segment_index == seg_idx and e.sfx_type == sfx_type for e in events):
                        desc = retriever.resolve_hard_sfx_asset(sfx_type, context_tags=[str(seg.get("acoustic_env", ""))])
                        asset_p = desc.filepath if desc else ""
                        events.append(
                            HardSFXEventSpec(
                                event_id=f"hardsfx_text_{seg_idx}_{sfx_type}",
                                segment_index=seg_idx,
                                sfx_type=sfx_type,  # type: ignore
                                description=f"Narrative action: {match.group(0)}",
                                start_ms=seg_start,
                                relative_intensity="explosive_impact" if priority == "CRITICAL" else "prominent",
                                priority=priority,  # type: ignore
                                has_lfe_sub_bass=has_lfe,
                                asset_path=asset_p,
                                decision_reason=f"Matched narrative verb '{match.group(0)}' in segment text",
                                timing_rationale=f"Anchored to narrative action '{match.group(0)}' in segment {seg_idx}",
                                dramatic_purpose=f"Concussive physical impact ({sfx_type})",
                                confidence=0.85,
                                provenance_segment_uid=seg.get("uid"),
                                provenance_beat_id=seg.get("beat_id"),
                            )
                        )

        return events


class CreatureSoundEngine:
    """
    Acoustic Creature Entity and Behavioral State Sound Engine.
    """

    def detect_creature_events(
        self,
        segments: List[Dict[str, Any]],
        creature_presence: Optional[str] = None,
        tension_level: float = 0.5,
    ) -> List[CreatureSoundSpec]:
        """
        Detects and structures creature audio events across scene segments.
        Anchors events to actual narrative moments.
        """
        events: List[CreatureSoundSpec] = []
        c_slug = (creature_presence or "beast").lower().strip()
        retriever = get_asset_retriever()

        for idx, seg in enumerate(segments):
            text = seg.get("text", "")
            seg_idx = int(seg.get("segment_index") or seg.get("index") or (idx + 1))
            seg_start = int(seg.get("start_ms", 0))

            for pat, elem, state in CREATURE_VOCAL_PATTERNS:
                m = pat.search(text)
                if m:
                    # Deduce proximity from tension
                    prox: ProximityZone = "mid_distance"
                    if tension_level > 0.8 or state == "attacking":
                        prox = "close"
                    elif tension_level < 0.4:
                        prox = "distant"

                    desc = retriever.resolve_creature_asset(c_slug, elem, emotion=state)
                    asset_p = desc.filepath if desc else ""

                    events.append(
                        CreatureSoundSpec(
                            event_id=f"creature_{c_slug}_{seg_idx}_{elem}",
                            creature_type=c_slug,
                            element=elem,  # type: ignore
                            emotional_state=state,  # type: ignore
                            proximity=prox,
                            relative_intensity="explosive_impact" if state == "attacking" else "prominent",
                            priority="CRITICAL" if state == "attacking" else "HIGH",
                            asset_path=asset_p,
                            decision_reason=f"Detected creature behavior '{m.group(0)}' for {c_slug}",
                            segment_index=seg_idx,
                            start_ms=seg_start,
                            timing_rationale=f"Anchored to creature behavioral beat '{m.group(0)}' in segment {seg_idx}",
                            dramatic_purpose=f"Acoustic creature manifestation: {c_slug} {elem} ({state})",
                            confidence=0.90,
                            provenance_segment_uid=seg.get("uid"),
                            provenance_beat_id=seg.get("beat_id"),
                        )
                    )
                    break

        return events


_GLOBAL_HARD_SFX: Optional[HardSFXEngine] = None
_GLOBAL_CREATURE_ENGINE: Optional[CreatureSoundEngine] = None

def get_hard_sfx_engine() -> HardSFXEngine:
    """Returns singleton instance of HardSFXEngine."""
    global _GLOBAL_HARD_SFX
    if _GLOBAL_HARD_SFX is None:
        _GLOBAL_HARD_SFX = HardSFXEngine()
    return _GLOBAL_HARD_SFX

def get_creature_engine() -> CreatureSoundEngine:
    """Returns singleton instance of CreatureSoundEngine."""
    global _GLOBAL_CREATURE_ENGINE
    if _GLOBAL_CREATURE_ENGINE is None:
        _GLOBAL_CREATURE_ENGINE = CreatureSoundEngine()
    return _GLOBAL_CREATURE_ENGINE
