#!/usr/bin/env python3
"""
Audiobook Factory - Capability 01: Scene Audio Understanding.
============================================================
Interprets dramatic text, screenplay segments, character emotions, blocking,
and narrative stakes to formulate acoustic and sound design intent.
Policy: Primarily reuses existing screenplay, dramaturgy, and character metadata.
LLM reasoning is used strictly selectively for creative ambiguity, not for every simple verb.
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.logger import logger
from audiobook_factory.sound_design.contracts import (
    ActionCandidate,
    SceneAudioUnderstandingResult,
)
from audiobook_factory.sound_design.environment_profiles import get_environment_registry


class SceneAudioAnalyzer:
    """
    Scene Audio Understanding Engine.
    Transforms screenplay segments and dramaturgy into high-level sound intent.
    """

    def __init__(self):
        self.env_registry = get_environment_registry()

    def analyze_scene(
        self,
        scene_id: str,
        chapter_id: str,
        segments: List[Dict[str, Any]],
        dramatic_plan: Optional[Dict[str, Any]] = None,
        sonic_bible: Optional[Any] = None,
    ) -> SceneAudioUnderstandingResult:
        """
        Analyzes a scene's segments and dramatic structure to extract sound design intent.
        Reuses existing metadata from ScreenplaySegment and DramaticPlan directly.
        """
        if not segments:
            return SceneAudioUnderstandingResult(
                scene_id=scene_id,
                chapter_id=chapter_id,
                environment_type="indoor_room",
                time_and_weather="indoor_calm",
            )

        # 1. Environment & Acoustic Space Resolution
        # Check first segment's acoustic_env or dramatic plan's location
        acoustic_env_tag = ""
        for s in segments:
            if s.get("acoustic_env") and s.get("acoustic_env") not in ("default", "none", ""):
                acoustic_env_tag = str(s["acoustic_env"])
                break

        location_tag = ""
        if dramatic_plan:
            location_tag = str(dramatic_plan.get("location", ""))

        env_candidate_text = f"{acoustic_env_tag} {location_tag}".strip() or "castle_corridor"
        resolved_env = self.env_registry.resolve_from_text(env_candidate_text)

        # 2. Characters Present & Dominant Emotion
        characters_present: Set[str] = set()
        emotion_counts: Dict[str, int] = {}
        tensions: List[float] = []

        for seg in segments:
            speaker = seg.get("speaker", "Narrator")
            if speaker and speaker.lower() not in ("narrator", "foley", "header", "action"):
                characters_present.add(speaker)

            emo = str(seg.get("emotion", "neutral")).lower()
            if emo:
                emotion_counts[emo] = emotion_counts.get(emo, 0) + 1

            if seg.get("tension_after") is not None:
                try:
                    tensions.append(float(seg["tension_after"]))
                except (ValueError, TypeError):
                    pass

        dom_emotion = max(emotion_counts, key=emotion_counts.get) if emotion_counts else "neutral"
        avg_tension = sum(tensions) / len(tensions) if tensions else 0.5

        # 3. Physical Action & Foley Candidates Discovery
        action_candidates: List[ActionCandidate] = []
        hard_sfx_candidates: List[Dict[str, Any]] = []
        magical_phenomena: List[str] = []
        creatures_found: List[str] = []
        silence_opportunities: List[str] = []

        # Action Keywords Taxonomy (Devanagari & English inflections)
        foley_action_map = {
            "draw": ("draw", "steel"),
            "draws": ("draw", "steel"),
            "drew": ("draw", "steel"),
            "drawn": ("draw", "steel"),
            "unsheathe": ("draw", "steel"),
            "unsheathes": ("draw", "steel"),
            "unsheathed": ("draw", "steel"),
            "खींची": ("draw", "steel"),
            "निकाली": ("draw", "steel"),
            "निकाल": ("draw", "steel"),
            "slam": ("slam", "wood"),
            "slams": ("slam", "wood"),
            "slammed": ("slam", "wood"),
            "पटक": ("slam", "wood"),
            "creak": ("creak", "wood"),
            "creaks": ("creak", "wood"),
            "creaked": ("creak", "wood"),
            "चूं": ("creak", "wood"),
            "clash": ("clash", "steel"),
            "clashes": ("clash", "steel"),
            "clashed": ("clash", "steel"),
            "टकरा": ("clash", "steel"),
            "pour": ("pour", "liquid"),
            "pours": ("pour", "liquid"),
            "poured": ("pour", "liquid"),
            "उड़ेल": ("pour", "liquid"),
            "quill": ("scratch", "paper"),
            "parchment": ("rustle", "paper"),
            "ignite": ("ignite", "torch"),
            "ignites": ("ignite", "torch"),
            "ignited": ("ignite", "torch"),
            "step": ("step", "stone"),
            "steps": ("step", "stone"),
            "stepped": ("step", "stone"),
            "stride": ("step", "stone"),
            "strode": ("step", "stone"),
            "कदम": ("step", "stone"),
            "tankard": ("tableware", "plate"),
            "dish": ("tableware", "plate"),
            "थाली": ("tableware", "plate"),
        }

        # Hard SFX Keywords
        hard_sfx_keywords = {
            "explosion": "explosion_concussive",
            "blast": "explosion_concussive",
            "collapse": "destruction_crash",
            "crash": "collision_structural",
            "thunder": "fire_combustion",
            "smash": "collision_structural",
        }

        # Magic Keywords
        magic_keywords = {
            "igni": "igni_fire_burst",
            "aard": "aard_kinetic_blast",
            "quen": "quen_shield_barrier",
            "axii": "axii_hypnotic_chime",
            "yrden": "yrden_binding_trap",
            "lumos": "lumos_light_chime",
            "expelliarmus": "expelliarmus_kinetic_pulse",
            "teleport": "teleport_displacement",
            "spell": "generic_spell_release",
            "magic": "arcane_energy_hum",
        }

        # Creature Keywords
        creature_keywords = {
            "striga": "striga",
            "ghoul": "ghoul",
            "wolf": "wolf_pack",
            "beast": "generic_beast",
            "monster": "generic_monster",
            "dragon": "dragon",
        }

        for seg in segments:
            s_idx = seg.get("index", 1)
            text = str(seg.get("text", "")).lower()
            sfx_cues = seg.get("sfx_cues", [])
            speaker = seg.get("speaker", "Character")

            # A. Check explicit sfx_cues
            for cue in sfx_cues:
                cue_str = (cue.get("tag", "") if isinstance(cue, dict) else str(cue)).lower()
                for kw, sfx_type in hard_sfx_keywords.items():
                    if kw in cue_str:
                        hard_sfx_candidates.append({
                            "segment_index": s_idx,
                            "sfx_type": sfx_type,
                            "description": f"Explicit hard SFX cue: {cue_str}",
                        })
                for kw, mag_name in magic_keywords.items():
                    if kw in cue_str and mag_name not in magical_phenomena:
                        magical_phenomena.append(mag_name)

            # B. Check action candidates from text & tokens
            tokens = [t.strip(".,!?;:\"'()[]{}—–") for t in text.split()]
            for tok in tokens:
                for verb_kw, (canon_verb, default_mat) in foley_action_map.items():
                    if verb_kw in tok:
                        # Determine material context
                        mat = default_mat
                        if any(w in text for w in ("stone", "पत्थर")):
                            mat = "stone"
                        elif any(w in text for w in ("iron", "metal", "steel", "लोहा")):
                            mat = "steel"
                        elif any(w in text for w in ("parchment", "paper", "कागज")):
                            mat = "paper"

                        candidate = ActionCandidate(
                            segment_index=s_idx,
                            subject=speaker,
                            action_verb=canon_verb,
                            object_material=mat,
                            anchor_word=tok,
                            narrative_weight=0.7 if seg.get("type") == "action" else 0.5,
                            is_explicit_blocking=bool(seg.get("blocking_directive")),
                        )
                        action_candidates.append(candidate)
                        break

            # C. Check creature presence in text and sfx_cues
            combined_cue_and_text = f"{text} {' '.join(str(c) for c in sfx_cues)}".lower()
            for kw, c_slug in creature_keywords.items():
                if kw in combined_cue_and_text and c_slug not in creatures_found:
                    creatures_found.append(c_slug)

            # D. Silence opportunities discovery from segment pauses
            pause_after = int(seg.get("pause_after_ms", 300) or 300)
            if pause_after >= 650 or "[whispers]" in text or seg.get("silence_intent"):
                silence_opportunities.append(f"Pause after segment {s_idx} ({pause_after}ms)")

        # Global dramatic silence opportunities across scene text & emotion
        full_corpus = " ".join(s.get("text", "") for s in segments).lower()
        if any(w in full_corpus for w in ("traitor", "accuse", "shock", "stunned", "silence", "not a sound")) or dom_emotion == "shock":
            silence_opportunities.append("Stunned silence / reveal breath upon revelation")
        if any(w in full_corpus for w in ("dawn", "aftermath", "contemplation", "stillness", "peace", "quiet")) or dom_emotion in ("peace", "grief"):
            silence_opportunities.append("Aftermath contemplation / quiet negative space")
        if any(w in full_corpus for w in ("alone", "intimate", "confession", "burden", "whisper", "whispered")) or dom_emotion in ("intimate", "secretive"):
            silence_opportunities.append("Intimate pause / breath space for emotional vulnerability")
        if any(w in full_corpus for w in ("hold breath", "stealth", "creeping", "held her breath", "held his breath")) or dom_emotion in ("stealth", "suspense"):
            silence_opportunities.append("Foley suppression and breath holding in suspense")

        # 4. Walla requirement analysis
        requires_walla = False
        walla_desc = None
        if resolved_env.typical_walla:
            # Check if crowd is actually present in dramatic context or text
            crowd_keywords = (
                "tavern", "market", "classroom", "court", "crowd", "banquet",
                "feast", "cheers", "patrons", "brawl", "rally", "siege",
                "soldiers", "brawlers", "courtiers", "lords", "gathering", "assembly"
            )
            combined_search = (env_candidate_text + " " + full_corpus).lower()
            if any(w in combined_search for w in crowd_keywords):
                requires_walla = True
                walla_desc = resolved_env.typical_walla


        # 5. Build and return structured understanding result
        creature_name = creatures_found[0] if creatures_found else None

        return SceneAudioUnderstandingResult(
            scene_id=scene_id,
            chapter_id=chapter_id,
            environment_type=resolved_env.env_id,
            time_and_weather=resolved_env.typical_weather or "indoor_calm",
            characters_present=sorted(list(characters_present)),
            action_candidates=action_candidates,
            hard_sfx_candidates=hard_sfx_candidates,
            creature_presence=creature_name,
            magical_phenomena=magical_phenomena,
            requires_walla=requires_walla,
            walla_description=walla_desc,
            music_required=True,
            dominant_emotion=dom_emotion,
            tension_level=avg_tension,
            silence_opportunities=silence_opportunities,
            metadata={
                "total_segments": len(segments),
                "resolved_environment": resolved_env.display_name,
                "rt60_ms": resolved_env.estimated_rt60_ms,
            },
        )


_GLOBAL_ANALYZER: Optional[SceneAudioAnalyzer] = None

# Ergonomic aliases
SceneAudioUnderstandingEngine = SceneAudioAnalyzer

def get_scene_audio_analyzer() -> SceneAudioAnalyzer:
    """Returns singleton instance of SceneAudioAnalyzer."""
    global _GLOBAL_ANALYZER
    if _GLOBAL_ANALYZER is None:
        _GLOBAL_ANALYZER = SceneAudioAnalyzer()
    return _GLOBAL_ANALYZER

def get_scene_understanding_engine() -> SceneAudioAnalyzer:
    """Ergonomic alias for get_scene_audio_analyzer."""
    return get_scene_audio_analyzer()

