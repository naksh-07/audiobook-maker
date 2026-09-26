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

        var_mode = self.variation_engine.derive_variation_mode(
            tension_level=tension_level,
            dominant_emotion=dominant_emotion,
        )

        # 2. Decision: Does the scene warrant music? (Correct decision can be NO MUSIC)
        beats = dramatic_beats or []
        has_dramatic_turning_beats = any(
            any(k in str(b.get("type", "") if isinstance(b, dict) else getattr(b, "type", "")).lower()
                for k in ("revelation", "discovery", "turn", "climax", "escalation", "shock", "entrance"))
            for b in beats
        )

        # High-restraint scenes without character motifs or turning points authentically choose NO MUSIC
        if not resolved_motif:
            is_intimate_or_subtle = (
                dominant_emotion.lower() in ("intimate", "grief", "stealth", "sorrow", "quiet", "whispering", "secretive", "subdued")
                or tension_level < 0.35
            )
            if (restraint_target == "high" and not has_dramatic_turning_beats) or (is_intimate_or_subtle and not has_dramatic_turning_beats):
                logger.info(
                    f"[MusicDirector] Directorial choice: NO MUSIC for scene '{scene_id}' (restraint: {restraint_target}, emotion: {dominant_emotion}). Negative space preserved."
                )
                return []

        # Formulate variation metadata (using resolved motif or authentic atmospheric score)
        if resolved_motif:
            variation = self.variation_engine.apply_variation(resolved_motif, var_mode)
            motif_id = resolved_motif.motif_id
            track_name = variation["track_name"]
            track_id = variation["track_id"]
        else:
            # Authentic atmospheric score without inventing generic fake character motifs
            variation_rules = VARIATION_MODE_RULES[var_mode]
            motif_id = None
            track_name = f"Atmospheric Score ({var_mode.title()} Underscore)"
            track_id = 1
            variation = {
                "motif_id": None,
                "associated_entity": "Atmosphere",
                "variation_mode": var_mode,
                "track_name": track_name,
                "track_id": 1,
                "primary_instrument": "Ambient Drone & Strings",
                "arrangement": variation_rules["arrangement"],
                "effective_tempo_bpm": 80,
                "relative_intensity": variation_rules["relative_intensity"],
                "priority": variation_rules["priority"],
                "cue_type": variation_rules["cue_type"],
                "reverb_send": variation_rules["reverb_send"],
            }

        # 3. Dramatic Beat-Aware Cue Placement
        if beats and has_dramatic_turning_beats:
            # Place cues anchored to actual dramatic beats
            for b_idx, beat in enumerate(beats):
                b_dict = beat if isinstance(beat, dict) else beat.__dict__
                b_type = str(b_dict.get("type", "")).lower()
                b_name = str(b_dict.get("name", b_dict.get("title", f"Beat_{b_idx+1}")))
                b_ts = int(b_dict.get("start_ms", b_dict.get("timestamp_ms", start_ms)))
                b_seg = b_dict.get("segment_index")

                # Check if beat warrants a music cue
                is_turn = any(k in b_type for k in ("revelation", "discovery", "turn", "climax", "escalation", "shock", "entrance", "aftermath"))
                if not is_turn:
                    continue

                pre_roll = 800 if "climax" in b_type or "shock" in b_type else 1200
                cue_start = max(start_ms, b_ts - pre_roll)
                max_avail = max(0, end_ms - cue_start)
                cue_dur = min(max_avail, 14000 if "climax" in b_type else 9000)
                if cue_dur < 1000:
                    continue

                # Determine dynamic entry, development, peak, and release
                if "climax" in b_type or tension_level > 0.85:
                    entry = "sudden_hit" if "shock" in b_type else "pre_roll_swell"
                    dev = "driving_rhythm"
                    rel = "reverb_spill" if "shock" in b_type else "fade_out"
                    c_type = "CLIMACTIC_ACTION_CUE"
                elif "revelation" in b_type or "discovery" in b_type:
                    entry = "pre_roll_swell"
                    dev = "emotional_swell"
                    rel = "sharp_cutoff"
                    c_type = "EMOTIONAL_UNDERSCORE"
                elif "escalation" in b_type:
                    entry = "subtle_drift"
                    dev = "tension_riser"
                    rel = "fade_out"
                    c_type = "TENSION_RISER"
                elif "aftermath" in b_type:
                    entry = "fade_in"
                    dev = "subdued_tail"
                    rel = "fade_out"
                    c_type = "AFTERMATH_FADE"
                else:
                    entry = "fade_in"
                    dev = "steady_bed"
                    rel = "fade_out"
                    c_type = variation["cue_type"]

                peak_ms = cue_start + min(4000, cue_dur // 2)

                cues.append(
                    MusicCueSpec(
                        cue_id=f"mc_{scene_id}_beat_{b_idx+1}",
                        motif_id=motif_id,
                        variation_mode=var_mode,
                        cue_type=c_type,
                        start_ms=cue_start,
                        duration_ms=cue_dur,
                        fade_in_ms=min(2000, max(100, cue_dur // 3)),
                        fade_out_ms=min(2500, max(100, cue_dur // 3)),
                        relative_intensity=variation["relative_intensity"],
                        priority=variation["priority"],
                        track_name=track_name,
                        track_id=track_id,
                        dramatic_justification=f"Anchored to dramatic beat '{b_name}' ({b_type})",
                        mix_intent=MixIntent(duck_under_dialogue=True, carve_vocal_presence=True),
                        trigger_beat=b_name,
                        trigger_segment_index=b_seg,
                        pre_roll_ms=pre_roll,
                        entry_type=entry,
                        development_arc=dev,
                        peak_ms=peak_ms,
                        release_type=rel,
                        narrative_rationale=f"Music responds to {b_type} with {dev} reaching peak at {peak_ms}ms",
                    )
                )
                if len(cues) >= 2:
                    break

        # Fallback to narrative-informed cue placement if no explicit beats triggered
        if not cues:
            if restraint_target == "high":
                # High restraint: single sparse, delicate entry
                cue_start = start_ms + min(2000, max(0, int(duration_ms * 0.15)))
                max_avail = max(0, end_ms - cue_start)
                cue_dur = min(max_avail, 8000)
                if cue_dur >= 1000:
                    cues.append(
                        MusicCueSpec(
                            cue_id=f"mc_{scene_id}_1",
                            motif_id=motif_id,
                            variation_mode=var_mode,
                            cue_type=variation["cue_type"],
                            start_ms=cue_start,
                            duration_ms=cue_dur,
                            fade_in_ms=min(2500, max(100, cue_dur // 2)),
                            fade_out_ms=min(3000, max(100, cue_dur // 2)),
                            relative_intensity=variation["relative_intensity"],
                            priority=variation["priority"],
                            track_name=track_name,
                            track_id=track_id,
                            dramatic_justification=f"Subtle {var_mode.lower()} motif in high-restraint scene",
                            mix_intent=MixIntent(duck_under_dialogue=True, carve_vocal_presence=True),
                            trigger_beat="scene_atmosphere",
                            pre_roll_ms=800,
                            entry_type="subtle_drift",
                            development_arc="subdued_tail",
                            peak_ms=cue_start + cue_dur // 2,
                            release_type="fade_out",
                            narrative_rationale="Restrained underscore providing negative space and dialogue breathing room",
                        )
                    )

            elif restraint_target == "moderate":
                # Moderate: balanced score underscore
                cue_start = start_ms + min(1000, max(0, int(duration_ms * 0.08)))
                max_avail = max(0, end_ms - cue_start)
                cue_dur = min(max_avail, 12000)
                if cue_dur >= 1000:
                    cues.append(
                        MusicCueSpec(
                            cue_id=f"mc_{scene_id}_1",
                            motif_id=motif_id,
                            variation_mode=var_mode,
                            cue_type=variation["cue_type"],
                            start_ms=cue_start,
                            duration_ms=cue_dur,
                            fade_in_ms=min(2000, max(100, cue_dur // 3)),
                            fade_out_ms=min(2500, max(100, cue_dur // 3)),
                            relative_intensity=variation["relative_intensity"],
                            priority=variation["priority"],
                            track_name=track_name,
                            track_id=track_id,
                            dramatic_justification=f"Emotional underscore reflecting {dominant_emotion}",
                            mix_intent=MixIntent(duck_under_dialogue=True, carve_vocal_presence=True),
                            trigger_beat="emotional_arc",
                            pre_roll_ms=600,
                            entry_type="pre_roll_swell",
                            development_arc="steady_bed",
                            peak_ms=cue_start + cue_dur // 2,
                            release_type="fade_out",
                            narrative_rationale=f"Underscore reflecting scene dominant emotion '{dominant_emotion}'",
                        )
                    )

            else:  # dense
                # Action / Climax: continuous driving cue
                cues.append(
                    MusicCueSpec(
                        cue_id=f"mc_{scene_id}_climax",
                        motif_id=motif_id,
                        variation_mode="CLIMAX",
                        cue_type="CLIMACTIC_ACTION_CUE",
                        start_ms=start_ms,
                        duration_ms=duration_ms,
                        fade_in_ms=1000,
                        fade_out_ms=2000,
                        relative_intensity="prominent",
                        priority="CRITICAL",
                        track_name=track_name,
                        track_id=track_id,
                        dramatic_justification="Full climactic score across high-energy conflict",
                        mix_intent=MixIntent(duck_under_dialogue=True, carve_vocal_presence=True),
                        trigger_beat="action_climax",
                        pre_roll_ms=0,
                        entry_type="sudden_hit",
                        development_arc="driving_rhythm",
                        peak_ms=start_ms + duration_ms // 2,
                        release_type="fade_out",
                        narrative_rationale="Continuous climactic score across full action sequence",
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
