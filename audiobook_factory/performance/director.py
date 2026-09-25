#!/usr/bin/env python3
"""
Audiobook Factory - Performance Director Agent (Pillar 3.3).
Transforms Stage 3 Dramatic Intelligence, Performance Bibles, and Screenplay Segments
into actionable, explainable actor delivery directives (PerformanceDirection).
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.contracts import ScreenplaySegment
from audiobook_factory.dramaturgy.contracts import (
    DramaticPlan,
    DramaticBeat,
    SceneDramaticPlan,
    PerformanceBible,
    CharacterPerformanceProfile,
)
from .contracts import (
    PerformanceDirection,
    PerformanceProvenanceMode,
    PerformancePriority,
    SilenceType,
    InterruptionBehavior,
    TurnTakingBehavior,
    PitchBehavior,
    ResonancePlacement,
    VocalTexture,
    BreathBehavior,
    PowerPosition,
    LeverageLevel,
    IntimacyLevel,
    PhysicalStagingState,
)
from .timing_realizer import TimingRealizer


class PerformanceDirector:
    """
    World-Class Audio Drama Performance Director.
    Answers: 'Given what is happening dramatically in this exact beat, how should this character perform this exact line?'
    """

    VOLATILE_TRANSITIONS = {
        ("calm", "bellowing_rage"),
        ("peaceful", "explosive"),
        ("gentle_tender", "bellowing_battlecry"),
        ("whispering", "bellowing_rage"),
        ("joyous", "despair"),
        ("calm", "rage"),
    }

    def __init__(
        self,
        performance_bible: Optional[PerformanceBible] = None,
        dramatic_plan: Optional[DramaticPlan] = None,
    ):
        self.performance_bible = performance_bible or PerformanceBible()
        self.dramatic_plan = dramatic_plan

    def direct_segment(
        self,
        segment: Any,
        dramatic_beat: Optional[DramaticBeat] = None,
        scene_plan: Optional[SceneDramaticPlan] = None,
        previous_direction: Optional[PerformanceDirection] = None,
        target_character: Optional[str] = None,
        performance_bible: Optional[PerformanceBible] = None,
        scene_vector: Optional[Any] = None,
        voice_dna: Optional[Any] = None,
    ) -> PerformanceDirection:
        """
        Directs a single screenplay segment into a complete PerformanceDirection.
        """
        pb = performance_bible or self.performance_bible

        # Normalize segment access (BaseModel or dict)
        if isinstance(segment, dict):
            s_uid = str(segment.get("uid", ""))
            s_idx = int(segment.get("index", 1))
            s_spk = str(segment.get("speaker", "Narrator"))
            s_txt = str(segment.get("text", "")).strip()
            s_type = str(segment.get("type", "dialogue"))
            s_emo = str(segment.get("emotion", "neutral"))
            s_intensity = str(segment.get("intensity_level", "medium"))
            s_pacing = float(segment.get("acting", {}).get("pacing", 1.0) if isinstance(segment.get("acting"), dict) else getattr(segment.get("acting", None), "pacing", 1.0))
            s_pause_after = segment.get("pause_after_ms", 400)
            s_obj = segment.get("character_objective")
            s_actioning = segment.get("actioning")
            s_subtext = segment.get("subtext")
            s_subtext_conf = float(segment.get("subtext_confidence", 0.0) or 0.0)
            s_surf_emo = segment.get("surface_emotion") or s_emo
            s_under_emo = segment.get("underlying_emotion")
            s_t_before = float(segment.get("tension_before", 0.5) if segment.get("tension_before") is not None else 0.5)
            s_t_after = float(segment.get("tension_after", 0.5) if segment.get("tension_after") is not None else 0.5)
            s_prio = str(segment.get("performance_priority", "standard"))
            s_leverage = segment.get("leverage_holder")
            s_rel_shift = segment.get("relationship_shift")
            s_blocking = segment.get("blocking_directive")
            s_mode = str(segment.get("narrative_mode", "direct_dialogue"))
            s_is_interruption = bool(segment.get("is_interruption", False))
            s_dynamic = segment.get("conversational_dynamic")
            s_silence_intent = segment.get("silence_intent")
            s_hesitation = segment.get("hesitation_pause_ms")
            s_spatial = segment.get("spatial", {})
            s_pan = float(s_spatial.get("pan", 0.0) if isinstance(s_spatial, dict) else getattr(s_spatial, "pan", 0.0))
            s_prox = str(s_spatial.get("proximity", "normal_room") if isinstance(s_spatial, dict) else getattr(s_spatial, "proximity", "normal_room"))
        else:
            s_uid = getattr(segment, "uid", "")
            s_idx = getattr(segment, "index", 1)
            s_spk = getattr(segment, "speaker", "Narrator")
            s_txt = str(getattr(segment, "text", "")).strip()
            s_type = getattr(segment, "type", "dialogue")
            s_emo = getattr(segment, "emotion", "neutral")
            s_intensity = getattr(segment, "intensity_level", "medium") or "medium"
            acting = getattr(segment, "acting", None)
            s_pacing = getattr(acting, "pacing", 1.0) if acting else 1.0
            s_pause_after = getattr(segment, "pause_after_ms", 400)
            s_obj = getattr(segment, "character_objective", None)
            s_actioning = getattr(segment, "actioning", None)
            s_subtext = getattr(segment, "subtext", None)
            s_subtext_conf = float(getattr(segment, "subtext_confidence", 0.0) or 0.0)
            s_surf_emo = getattr(segment, "surface_emotion", None) or s_emo
            s_under_emo = getattr(segment, "underlying_emotion", None)
            s_t_before = float(getattr(segment, "tension_before", 0.5) if getattr(segment, "tension_before", None) is not None else 0.5)
            s_t_after = float(getattr(segment, "tension_after", 0.5) if getattr(segment, "tension_after", None) is not None else 0.5)
            s_prio = getattr(segment, "performance_priority", "standard") or "standard"
            s_leverage = getattr(segment, "leverage_holder", None)
            s_rel_shift = getattr(segment, "relationship_shift", None)
            s_blocking = getattr(segment, "blocking_directive", None)
            s_mode = getattr(segment, "narrative_mode", "direct_dialogue") or "direct_dialogue"
            s_is_interruption = bool(getattr(segment, "is_interruption", False))
            s_dynamic = getattr(segment, "conversational_dynamic", None)
            s_silence_intent = getattr(segment, "silence_intent", None)
            s_hesitation = getattr(segment, "hesitation_pause_ms", None)
            spatial = getattr(segment, "spatial", None)
            s_pan = getattr(spatial, "pan", 0.0) if spatial else 0.0
            s_prox = getattr(spatial, "proximity", "normal_room") if spatial else "normal_room"

        # 1. Resolve Character Profile from PerformanceBible
        char_profile: Optional[CharacterPerformanceProfile] = None
        if s_spk and s_spk not in ("Narrator", "Foley", ""):
            char_profile = pb.get_profile(s_spk)

        # Baseline performance variables
        base_pace = char_profile.baseline_pace if char_profile else 1.0
        base_energy = char_profile.baseline_energy if char_profile else 0.75
        articulation = char_profile.articulation if char_profile else "natural"
        restraint = char_profile.restraint_level if char_profile else 0.50

        # Grounding with VoiceDNA if available
        if voice_dna:
            v_beh = getattr(voice_dna, "behavior", None)
            if v_beh:
                base_pace = getattr(v_beh, "baseline_pace", base_pace)
                base_energy = getattr(v_beh, "baseline_energy", base_energy)
                articulation = getattr(v_beh, "articulation", articulation)
                restraint = getattr(v_beh, "restraint", restraint)

        # Narrator special handling
        if s_spk == "Narrator" or s_type == "narration":
            narr_style = pb.narrator_style or {}
            base_pace = float(narr_style.get("baseline_pace", 1.0))
            restraint = 0.80  # Narrator maintains high objective restraint
            articulation = "crisp"

        # Pacing modulation from screenplay
        effective_pace = max(0.65, min(1.45, base_pace * s_pacing))

        # 2. Objective, Actioning, and Emotional Layering
        effective_objective = s_obj or (dramatic_beat.objective.immediate_goal if dramatic_beat and dramatic_beat.objective else "convey thought")
        effective_actioning = s_actioning or (dramatic_beat.objective.actioning if dramatic_beat and dramatic_beat.objective else "inform")
        surface_emotion = s_surf_emo or "neutral"
        underlying_emotion = s_under_emo or (dramatic_beat.underlying_emotion if dramatic_beat else None)
        subtext = s_subtext or (dramatic_beat.subtext if dramatic_beat else None)
        subtext_confidence = s_subtext_conf or (dramatic_beat.subtext_confidence if dramatic_beat else 0.0)

        # 3. Restraint and Acting Delivery Modulation
        # Emotional behavior profile check: does character express emotion with specific style?
        if char_profile and char_profile.emotional_behaviors:
            clean_emo = surface_emotion.lower().strip()
            for emo_key, custom_style in char_profile.emotional_behaviors.items():
                if emo_key in clean_emo:
                    surface_emotion = custom_style
                    break
        elif voice_dna and hasattr(voice_dna, "get_emotional_tendency"):
            custom_style = voice_dna.get_emotional_tendency(surface_emotion)
            if custom_style and custom_style.lower() != surface_emotion.lower() and not custom_style.startswith(f"{surface_emotion} delivery with"):
                surface_emotion = custom_style

        # Pitch & Resonance Modulation
        pitch_behavior: PitchBehavior = "neutral"
        resonance: ResonancePlacement = "chest"
        breath_behavior: BreathBehavior = "steady"
        vocal_texture: VocalTexture = "smooth"

        if voice_dna and hasattr(voice_dna, "identity"):
            dna_res = getattr(voice_dna.identity, "resonance", None)
            if dna_res and dna_res in ("chest", "throat", "head", "whisper_air"):
                resonance = dna_res

        if restraint >= 0.75:
            # High restraint: suppressed emotion, low resonant pitch, controlled breathing
            pitch_behavior = "low_resonant"
            breath_behavior = "suppressed"
            if "rage" in surface_emotion.lower() or "anger" in surface_emotion.lower():
                vocal_texture = "gravelly"
            elif "fear" in surface_emotion.lower() or "terror" in surface_emotion.lower():
                pitch_behavior = "monotone"
                vocal_texture = "brittle"
        elif restraint <= 0.40:
            # Low restraint: expressive, dynamic pitch shifts, audible breaths
            if "rage" in surface_emotion.lower() or "explosive" in s_intensity:
                pitch_behavior = "high_tense"
                resonance = "throat"
                vocal_texture = "harsh"
                breath_behavior = "labored"
            elif "sadness" in surface_emotion.lower() or "grief" in surface_emotion.lower():
                pitch_behavior = "wavering"
                breath_behavior = "trembling"

        # Energy Modulation
        effective_energy = base_energy
        if s_intensity == "explosive":
            effective_energy = min(1.0, base_energy + 0.25)
        elif s_intensity == "high":
            effective_energy = min(0.95, base_energy + 0.15)
        elif s_intensity == "low":
            effective_energy = max(0.35, base_energy - 0.20)

        # Smooth with SceneEmotionalVector if provided
        if scene_vector:
            sc_energy = getattr(scene_vector, "energy", None)
            if sc_energy is not None:
                effective_energy = round(0.6 * effective_energy + 0.4 * float(sc_energy), 2)
            sc_restraint = getattr(scene_vector, "restraint", None)
            if sc_restraint is not None:
                restraint = round(0.6 * restraint + 0.4 * float(sc_restraint), 2)
            sc_tension = getattr(scene_vector, "tension", None)
            if sc_tension is not None:
                s_t_before = round(0.5 * s_t_before + 0.5 * float(sc_tension), 2)

        # 4. Anti-Emotional Teleportation Defense
        if previous_direction and previous_direction.speaker == s_spk and s_spk != "Narrator":
            prev_emo = previous_direction.surface_emotion.lower()
            curr_emo = surface_emotion.lower()
            if (prev_emo, curr_emo) in self.VOLATILE_TRANSITIONS:
                # Volatile transition without causal trigger
                causal = getattr(segment, "causal_trigger", None) if hasattr(segment, "causal_trigger") else (segment.get("causal_trigger") if isinstance(segment, dict) else None)
                if not causal and (not dramatic_beat or not dramatic_beat.causal_trigger):
                    # Dampen the extreme leap: transition through tense suppression
                    logger.info(
                        f"  [PERFORMANCE SMOOTHER] Preventing teleportation for {s_spk}: "
                        f"'{prev_emo}' -> '{curr_emo}'. Grounding transition."
                    )
                    surface_emotion = f"suppressed_{curr_emo}"
                    restraint = min(1.0, restraint + 0.20)
                    pitch_behavior = "low_resonant"

        # 5. Relationship, Power & Leverage
        resolved_target = target_character or (dramatic_beat.target_character if dramatic_beat else None)
        power_pos: PowerPosition = "neutral"
        leverage_level: LeverageLevel = "equal"
        vulnerability = 0.3

        if s_leverage:
            clean_lev = str(s_leverage).strip().lower()
            if clean_lev == s_spk.lower():
                power_pos = "dominant"
                leverage_level = "commanding"
                vulnerability = max(0.1, vulnerability - 0.2)
            elif resolved_target and clean_lev == resolved_target.lower():
                power_pos = "submissive"
                leverage_level = "vulnerable"
                vulnerability = min(0.9, vulnerability + 0.35)
                effective_pace *= 0.96  # Cautious pacing
            else:
                power_pos = "contested"

        # Social Mask
        social_mask = None
        if underlying_emotion and underlying_emotion.lower() != surface_emotion.lower() and restraint >= 0.5:
            social_mask = f"masking_{underlying_emotion.lower()}_with_{surface_emotion.lower()}"

        # Intimacy & Proximity
        intimacy: IntimacyLevel = "formal"
        if s_prox == "close_mic" or "[whispers]" in s_txt.lower() or s_mode == "internal_monologue":
            intimacy = "intimate"
            effective_energy = max(0.3, effective_energy - 0.25)
            resonance = "whisper_air"

        # Physical Staging
        phys_state: PhysicalStagingState = "normal"
        if s_blocking:
            b_low = str(s_blocking).lower()
            if "wound" in b_low or "bleed" in b_low or "pain" in b_low:
                phys_state = "wounded"
                breath_behavior = "labored"
            elif "exhaust" in b_low or "collapse" in b_low or "stagger" in b_low:
                phys_state = "exhausted"
                effective_pace *= 0.90
            elif "fight" in b_low or "sword" in b_low or "strike" in b_low:
                phys_state = "combat_strain"

        # 6. Timing & Silence Realization
        timing_dict = TimingRealizer.calculate_performance_timing(
            text=s_txt,
            speaker=s_spk,
            is_interruption=s_is_interruption,
            silence_intent=s_silence_intent,
            conversational_dynamic=s_dynamic,
            hesitation_pause_ms=s_hesitation,
            tension=s_t_before,
            restraint=restraint,
            physical_state=phys_state,
            existing_pause_after_ms=s_pause_after,
            target_character=resolved_target,
            power_position=power_pos,
        )

        # 7. Priority & Required Takes
        prio_clean = s_prio.lower()
        if prio_clean not in ("standard", "focused", "high", "climactic"):
            prio_clean = "standard"
        prio_typed: PerformancePriority = prio_clean  # type: ignore

        if prio_typed == "climactic":
            req_takes = 3
        elif prio_typed == "high":
            req_takes = 2
        elif prio_typed == "focused":
            req_takes = 2
        else:
            req_takes = 1

        # Wave 3 Upgrade: Generation Risk Engine dynamic calibration
        try:
            from .risk_engine import GenerationRiskEngine
            prelim_dir = PerformanceDirection(
                direction_id=f"prelim_{s_idx:04d}",
                index=s_idx,
                speaker=s_spk,
                narrative_mode=s_mode,
                surface_emotion=surface_emotion,
                intensity=s_intensity,
                pace=round(effective_pace, 2),
                physical_state=phys_state,
                interruption_behavior=timing_dict.get("interruption_behavior", "none"),
                social_mask=social_mask,
                subtext_confidence=subtext_confidence,
                proximity=s_prox,
                intimacy_level=intimacy,
            )
            risk_rep = GenerationRiskEngine.calculate_segment_risk(prelim_dir, text=s_txt)
            if prio_clean == "standard" and risk_rep.recommended_takes > 1:
                req_takes = risk_rep.recommended_takes
                if risk_rep.risk_tier == "critical":
                    prio_typed = "climactic"
                elif risk_rep.risk_tier == "elevated":
                    prio_typed = "high"
                else:
                    prio_typed = "focused"
        except Exception:
            pass

        # 8. Delivery Intent Summary (Explainable Actor Directive)
        summary_parts = [
            f"Action: {effective_actioning}",
            f"Delivery: {surface_emotion}",
        ]
        if underlying_emotion:
            summary_parts.append(f"Underlying: {underlying_emotion}")
        if social_mask:
            summary_parts.append(f"Mask: {social_mask}")
        if power_pos != "neutral":
            summary_parts.append(f"Power: {power_pos}")
        if phys_state != "normal":
            summary_parts.append(f"Physique: {phys_state}")
        delivery_intent_summary = "; ".join(summary_parts)

        # 9. Provenance Mode
        prov_mode: PerformanceProvenanceMode = "SOURCE_DIRECT"
        if subtext_confidence > 0.6 or underlying_emotion:
            prov_mode = "INFERRED_PERFORMANCE"
        if dramatic_beat and dramatic_beat.provenance_mode == "DRAMATIC_INTERPRETATION":
            prov_mode = "DRAMATIC_INTERPRETATION"

        return PerformanceDirection(
            direction_id=f"pd_{s_idx:04d}_{s_spk.lower().replace(' ', '_')}",
            segment_uid=s_uid or f"s{s_idx:04d}_{s_spk}",
            index=s_idx,
            speaker=s_spk,
            target_character=resolved_target,
            narrative_mode=s_mode,
            provenance_mode=prov_mode,
            character_state=surface_emotion,
            objective=effective_objective,
            actioning=effective_actioning,
            surface_emotion=surface_emotion,
            underlying_emotion=underlying_emotion,
            subtext=subtext,
            subtext_confidence=subtext_confidence,
            intensity=s_intensity,
            tension_before=s_t_before,
            tension_after=s_t_after,
            relationship_to_target=s_rel_shift,
            power_position=power_pos,
            leverage=leverage_level,
            vulnerability=round(vulnerability, 2),
            trust_level=0.5,
            social_mask=social_mask,
            intimacy_level=intimacy,
            pace=round(effective_pace, 2),
            energy=round(effective_energy, 2),
            pitch_behavior=pitch_behavior,
            articulation=articulation,
            resonance=resonance,
            breath_behavior=breath_behavior,
            vocal_texture=vocal_texture,
            restraint=round(restraint, 2),
            pause_before_ms=timing_dict["pause_before_ms"],
            pause_after_ms=timing_dict["pause_after_ms"],
            pre_roll_breath_ms=timing_dict["pre_roll_breath_ms"],
            post_roll_breath_ms=timing_dict["post_roll_breath_ms"],
            hesitation_ms=timing_dict["hesitation_ms"],
            silence_type=timing_dict["silence_type"],
            interruption_behavior=timing_dict["interruption_behavior"],
            turn_taking_behavior=timing_dict["turn_taking_behavior"],
            physical_state=phys_state,
            blocking_directive=s_blocking,
            spatial_intent=s_prox,
            proximity=s_prox,
            pan=s_pan,
            performance_priority=prio_typed,
            required_takes=req_takes,
            delivery_intent_summary=delivery_intent_summary,
        )

    def direct_chapter_script(
        self,
        script_segments: List[Any],
        dramatic_plan: Optional[DramaticPlan] = None,
        performance_bible: Optional[PerformanceBible] = None,
        voice_dna_bank: Optional[Any] = None,
    ) -> List[PerformanceDirection]:
        """
        Directs an entire chapter's screenplay script into a continuous sequence of PerformanceDirections.
        Maintains emotional continuity across consecutive beats and dialogic turns.
        """
        from .scene_emotional_state import SceneEmotionalStateTracker

        pb = performance_bible or self.performance_bible
        plan = dramatic_plan or self.dramatic_plan

        directions: List[PerformanceDirection] = []
        prev_dir: Optional[PerformanceDirection] = None
        scene_tracker = SceneEmotionalStateTracker(scene_id="chapter_script")

        # Build beat lookup if plan is present
        all_beats: List[DramaticBeat] = []
        if plan and plan.scenes:
            for sc in plan.scenes:
                all_beats.extend(sc.beats)

        num_segs = len(script_segments)
        num_bts = len(all_beats)

        for i, seg in enumerate(script_segments):
            # Resolve corresponding dramatic beat
            d_beat: Optional[DramaticBeat] = None
            if num_bts > 0:
                segs_per_beat = max(1, num_segs // num_bts)
                b_idx = min(i // segs_per_beat, num_bts - 1)
                d_beat = all_beats[b_idx]

            # Resolve target character by looking backward at previous dialogue speaker
            target_char: Optional[str] = None
            curr_spk = seg.get("speaker") if isinstance(seg, dict) else getattr(seg, "speaker", None)
            curr_emo = seg.get("emotion", "neutral") if isinstance(seg, dict) else (getattr(seg, "emotion", "neutral") or "neutral")
            curr_int = seg.get("intensity_level", "medium") if isinstance(seg, dict) else (getattr(seg, "intensity_level", "medium") or "medium")
            causal = seg.get("causal_trigger") if isinstance(seg, dict) else getattr(seg, "causal_trigger", None)

            sc_vec = scene_tracker.update_state(
                segment_index=i + 1,
                speaker=curr_spk or "Narrator",
                target_emotion=curr_emo,
                intensity=curr_int,
                causal_trigger=causal,
            )

            for prev_s in reversed(directions):
                if prev_s.speaker not in ("Narrator", "Foley", curr_spk):
                    target_char = prev_s.speaker
                    break

            dna = None
            if voice_dna_bank and curr_spk:
                try:
                    dna = voice_dna_bank.get_dna(curr_spk)
                except Exception:
                    dna = None

            direction = self.direct_segment(
                segment=seg,
                dramatic_beat=d_beat,
                previous_direction=prev_dir,
                target_character=target_char,
                performance_bible=pb,
                scene_vector=sc_vec,
                voice_dna=dna,
            )
            directions.append(direction)
            prev_dir = direction

        return directions
