#!/usr/bin/env python3
"""
Audiobook Factory - Capabilities 13, 14, 15: Music Motifs, Variation & Cue Director.
=====================================================================================
Leitmotif Intelligence & Dynamic Score Dramaturgy:
- Reuses and extends LeitmotifDefinition from sonic_bible.py.
- Dynamically transforms motifs across 6 narrative variation modes:
  INTIMATE, MYSTERIOUS, TRAGIC, TENSE, CLIMAX, AFTERMATH.
- Directs musical cue placement with adaptive scene density (no universal 60% rule).
- Converts to standard MusicCue contracts for downstream mixing and stem alignment.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple, Literal
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.sonic_bible import LeitmotifDefinition, SonicBible
from audiobook_factory.sound_design.contracts import (
    MusicCueSpec,
    MotifVariationMode,
    AttentionPriority,
    RelativeIntensity,
    MixIntent,
)
from audiobook_factory.contracts import MusicCue, MusicCueType


VARIATION_MODE_RULES: Dict[MotifVariationMode, Dict[str, Any]] = {
    "INTIMATE": {
        "arrangement": "solo_instrument_delicate",
        "relative_intensity": "whisper_quiet",
        "priority": "LOW",
        "reverb_send": 0.05,
        "cue_type": "EMOTIONAL_UNDERSCORE",
        "tempo_mult": 0.85,
    },
    "MYSTERIOUS": {
        "arrangement": "dissonant_pad_and_drone",
        "relative_intensity": "subtle_bed",
        "priority": "MEDIUM",
        "reverb_send": 0.35,
        "cue_type": "EMOTIONAL_UNDERSCORE",
        "tempo_mult": 1.0,
    },
    "TRAGIC": {
        "arrangement": "minor_solo_strings_sustained",
        "relative_intensity": "prominent",
        "priority": "HIGH",
        "reverb_send": 0.40,
        "cue_type": "EMOTIONAL_UNDERSCORE",
        "tempo_mult": 0.80,
    },
    "TENSE": {
        "arrangement": "tremolo_strings_ostinato_pulse",
        "relative_intensity": "prominent",
        "priority": "HIGH",
        "reverb_send": 0.15,
        "cue_type": "TENSION_RISER",
        "tempo_mult": 1.15,
    },
    "CLIMAX": {
        "arrangement": "full_orchestra_driving_percussion",
        "relative_intensity": "prominent",
        "priority": "CRITICAL",
        "reverb_send": 0.20,
        "cue_type": "CLIMACTIC_ACTION_CUE",
        "tempo_mult": 1.25,
    },
    "AFTERMATH": {
        "arrangement": "sparse_woodwind_warm_ambient_tail",
        "relative_intensity": "subtle_bed",
        "priority": "LOW",
        "reverb_send": 0.45,
        "cue_type": "AFTERMATH_FADE",
        "tempo_mult": 0.75,
    },
}


class MotifVariationEngine:
    """
    Transforms recurring Leitmotifs dynamically into scene-specific arrangements.
    """

    @staticmethod
    def derive_variation_mode(tension_level: float, dominant_emotion: str) -> MotifVariationMode:
        """
        Deduces optimal motif variation mode from dramatic tension and dominant emotion.
        """
        emo = dominant_emotion.lower().strip()

        if tension_level > 0.85:
            return "CLIMAX"
        if emo in ("grief", "sorrow", "mourning", "loss", "tragic"):
            return "TRAGIC"
        if emo in ("intimate", "tender", "whispering", "romantic", "secretive"):
            return "INTIMATE"
        if tension_level > 0.60 or emo in ("suspense", "dread", "anxious", "threat"):
            return "TENSE"
        if emo in ("peace", "resolution", "relief", "somber_calm"):
            return "AFTERMATH"
        if emo in ("mysterious", "wonder", "curious", "strange") or tension_level < 0.40:
            return "MYSTERIOUS"

        return "MYSTERIOUS"

    def apply_variation(
        self,
        motif: LeitmotifDefinition,
        mode: MotifVariationMode,
    ) -> Dict[str, Any]:
        """
        Applies narrative variation rules to a canonical Leitmotif.
        """
        rules = VARIATION_MODE_RULES[mode]
        target_tempo = int(motif.canonical_tempo_bpm * rules["tempo_mult"])

        return {
            "motif_id": motif.motif_id,
            "associated_entity": motif.associated_entity,
            "variation_mode": mode,
            "track_name": f"{motif.track_name} ({mode.title()} Variation)",
            "track_id": motif.track_id,
            "primary_instrument": motif.primary_instrument,
            "arrangement": rules["arrangement"],
            "effective_tempo_bpm": target_tempo,
            "relative_intensity": rules["relative_intensity"],
            "priority": rules["priority"],
            "cue_type": rules["cue_type"],
            "reverb_send": rules["reverb_send"],
        }


class MusicCueDirector:
    """
    Directs scene-level musical cue placement with adaptive density.
    """

    def __init__(self, sonic_bible: Optional[SonicBible] = None):
        self.bible = sonic_bible or SonicBible(book_title="Cinematic Score")
        self.variation_engine = MotifVariationEngine()

    def direct_scene_cues(
        self,
        scene_id: str,
        start_ms: int,
        end_ms: int,
        tension_level: float = 0.5,
        dominant_emotion: str = "neutral",
        characters_present: Optional[List[str]] = None,
        dramatic_beats: Optional[List[Dict[str, Any]]] = None,
        restraint_target: str = "moderate",
    ) -> List[MusicCueSpec]:
        """
        Plans musical cue placements for a scene based on dramatic beats,
        character presence, and adaptive restraint.
        """
        duration_ms = max(0, end_ms - start_ms)
        if duration_ms < 5000:
            return []

        cues: List[MusicCueSpec] = []
        chars = characters_present or []

        # 1. Resolve relevant character or thematic motif
        resolved_motif: Optional[LeitmotifDefinition] = None
        for ch in chars:
            resolved_motif = self.bible.resolve_theme_for_character(ch)
            if resolved_motif:
                break

        # Fallback default dramatic motif if none found
        if not resolved_motif:
            resolved_motif = LeitmotifDefinition(
                motif_id="lm_destiny_theme",
                entity_type="philosophical_theme",
                associated_entity="Narrative",
                track_id=1,
                track_name="Ancient Destiny",
                primary_instrument="Solo Cello & Strings",
                canonical_tempo_bpm=80,
                dramatic_intent="General thematic underscore",
                priority_level=5,
            )

        var_mode = self.variation_engine.derive_variation_mode(
            tension_level=tension_level,
            dominant_emotion=dominant_emotion,
        )
        variation = self.variation_engine.apply_variation(resolved_motif, var_mode)

        # 2. Adaptive Cue Allocation based on Restraint Target
        if restraint_target == "high":
            # High restraint: sparse single cue, plenty of negative space
            cue_start = start_ms + int(duration_ms * 0.25)
            max_avail_ms = max(0, (start_ms + duration_ms) - cue_start)
            cue_dur = min(max_avail_ms, 8000)
            if cue_dur >= 500:
                cues.append(
                    MusicCueSpec(
                        cue_id=f"mc_{scene_id}_1",
                        motif_id=resolved_motif.motif_id,
                        variation_mode=var_mode,
                        cue_type=variation["cue_type"],
                        start_ms=cue_start,
                        duration_ms=cue_dur,
                        fade_in_ms=min(2500, max(100, cue_dur // 2)),
                        fade_out_ms=min(3000, max(100, cue_dur // 2)),
                        relative_intensity=variation["relative_intensity"],
                        priority=variation["priority"],
                        track_name=variation["track_name"],
                        track_id=variation["track_id"],
                        dramatic_justification=f"Subtle {var_mode.lower()} motif in high-restraint scene",
                        mix_intent=MixIntent(duck_under_dialogue=True, carve_vocal_presence=True),
                    )
                )

        elif restraint_target == "moderate":
            # Moderate: 1-2 cues (e.g. entry underscore and emotional shift)
            cue_start = start_ms + min(1000, int(duration_ms * 0.1))
            max_avail_ms = max(0, (start_ms + duration_ms) - cue_start)
            cue_dur = min(max_avail_ms, 12000)
            if cue_dur >= 500:
                cues.append(
                    MusicCueSpec(
                        cue_id=f"mc_{scene_id}_1",
                        motif_id=resolved_motif.motif_id,
                        variation_mode=var_mode,
                        cue_type=variation["cue_type"],
                        start_ms=cue_start,
                        duration_ms=cue_dur,
                        fade_in_ms=min(2000, max(100, cue_dur // 2)),
                        fade_out_ms=min(2500, max(100, cue_dur // 2)),
                        relative_intensity=variation["relative_intensity"],
                        priority=variation["priority"],
                        track_name=variation["track_name"],
                        track_id=variation["track_id"],
                        dramatic_justification=f"Emotional underscore reflecting {dominant_emotion}",
                        mix_intent=MixIntent(duck_under_dialogue=True, carve_vocal_presence=True),
                    )
                )

        else:  # dense
            # Action / Climax: continuous driving cue
            cues.append(
                MusicCueSpec(
                    cue_id=f"mc_{scene_id}_climax",
                    motif_id=resolved_motif.motif_id,
                    variation_mode="CLIMAX",
                    cue_type="CLIMACTIC_ACTION_CUE",
                    start_ms=start_ms,
                    duration_ms=duration_ms,
                    fade_in_ms=1000,
                    fade_out_ms=2000,
                    relative_intensity="prominent",
                    priority="CRITICAL",
                    track_name=variation["track_name"],
                    track_id=variation["track_id"],
                    dramatic_justification="Full climactic score across high-energy conflict",
                    mix_intent=MixIntent(duck_under_dialogue=True, carve_vocal_presence=True),
                )
            )

        return cues

    def to_legacy_music_cues(self, specs: List[MusicCueSpec]) -> List[MusicCue]:
        """
        Converts MusicCueSpec items into standard legacy MusicCue objects
        for downstream mixing and stem alignment compatibility.
        """
        legacy_cues: List[MusicCue] = []
        for s in specs:
            cue_type_map: Dict[str, MusicCueType] = {
                "TRANSITION_BRIDGE": "TRANSITION_BRIDGE",
                "EMOTIONAL_UNDERSCORE": "EMOTIONAL_UNDERSCORE",
                "TENSION_RISER": "TENSION_RISER",
                "CLIMACTIC_ACTION_CUE": "CLIMACTIC_ACTION",
                "AFTERMATH_FADE": "AFTERMATH_FADE",
            }
            c_type = cue_type_map.get(s.cue_type, "EMOTIONAL_UNDERSCORE")

            legacy_cues.append(
                MusicCue(
                    cue_id=s.cue_id,
                    cue_type=c_type,
                    track_id=int(s.track_id) if str(s.track_id).isdigit() else 0,
                    track_name=s.track_name or "Soundtrack Theme",
                    section_name=f"{s.variation_mode}_VARIATION",
                    section_start_sec=0.0,
                    start_ms=s.start_ms,
                    duration_ms=s.duration_ms,
                    fade_in_ms=s.fade_in_ms,
                    fade_out_ms=s.fade_out_ms,
                    gain_dbfs=-18.0 if s.relative_intensity == "subtle_bed" else -14.0,
                )
            )

        return legacy_cues


_GLOBAL_CUE_DIRECTOR: Optional[MusicCueDirector] = None

def get_music_cue_director() -> MusicCueDirector:
    """Returns singleton instance of MusicCueDirector."""
    global _GLOBAL_CUE_DIRECTOR
    if _GLOBAL_CUE_DIRECTOR is None:
        _GLOBAL_CUE_DIRECTOR = MusicCueDirector()
    return _GLOBAL_CUE_DIRECTOR
