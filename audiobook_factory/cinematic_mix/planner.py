#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Module: planner.py
Automation Planner: Translates SceneMixIntent, AttentionMap, and Cinematic Behavior Directors
(Acoustic Perspective, Silence Director, Impact Director) into a continuous,
conflict-resolved MixAutomation timeline with inspectable decision traces.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from audiobook_factory.cinematic_mix.scene_intent import SceneMixIntent
from audiobook_factory.cinematic_mix.attention_map import AttentionMap, AttentionEvent
from audiobook_factory.cinematic_mix.automation import (
    MixAutomation,
    AutomationEvent,
    SAFETY_LIMIT_MIN_GAIN_DB,
)
from audiobook_factory.cinematic_mix.masking import DynamicMaskingAnalyzer
from audiobook_factory.cinematic_mix.stem_interaction import StemInteractionEngine, StemInteractionPlan
from audiobook_factory.cinematic_mix.perspective import AcousticPerspective, PerspectiveDirector
from audiobook_factory.cinematic_mix.silence import SilenceEvent, SilenceDirector
from audiobook_factory.cinematic_mix.impact import ImpactEvent, ImpactDirector

logger = logging.getLogger("audiobook_factory.cinematic_mix.planner")


class AutomationPlanner:
    """
    Main Stage 11 Mix Automation Planner.
    Coordinates the 3 Cinematic Behavior Directors (Perspective, Silence, Impact)
    with attention-driven dynamic masking and stem interactions.
    """

    def __init__(
        self,
        masking_analyzer: Optional[DynamicMaskingAnalyzer] = None,
        interaction_engine: Optional[StemInteractionEngine] = None,
        perspective_director: Optional[PerspectiveDirector] = None,
        silence_director: Optional[SilenceDirector] = None,
        impact_director: Optional[ImpactDirector] = None,
        attack_sec: float = 0.10,
        release_sec: float = 0.40,
    ):
        self.masking_analyzer = masking_analyzer or DynamicMaskingAnalyzer()
        self.interaction_engine = interaction_engine or StemInteractionEngine()
        self.perspective_director = perspective_director or PerspectiveDirector()
        self.silence_director = silence_director or SilenceDirector()
        self.impact_director = impact_director or ImpactDirector()
        self.attack_sec = attack_sec
        self.release_sec = release_sec

    def plan(
        self,
        scene_intent: Optional[SceneMixIntent] = None,
        attention_map: Optional[AttentionMap] = None,
        dialogue_segments: Optional[List[Dict[str, Any]]] = None,
        total_duration_sec: Optional[float] = None,
        has_dialogue: bool = True,
        has_music: bool = True,
        has_foley: bool = True,
        has_ambience: bool = True,
        speech_style_override: Optional[str] = None,
        estimated_dmr_db: Optional[float] = None,
        acoustic_perspective: Optional[AcousticPerspective] = None,
        silence_events: Optional[List[SilenceEvent]] = None,
        impact_events: Optional[List[ImpactEvent]] = None,
    ) -> MixAutomation:
        """
        Plans a complete mix automation timeline incorporating all cinematic behavior directors.
        """
        intent = scene_intent or SceneMixIntent()
        att_map = attention_map or AttentionMap()

        automation = MixAutomation(
            scene_id=intent.scene_id or att_map.scene_id,
            chapter_id=intent.chapter_id or att_map.chapter_id,
            total_duration_sec=total_duration_sec or att_map.total_duration_sec,
        )

        effective_dur = total_duration_sec or att_map.total_duration_sec or 60.0

        # --- 1. IMPACT DIRECTOR: Temporary Focus Shifts & 4-Phase Ducking ---
        if impact_events:
            # Non-destructively derive temporary attention overlay
            att_map = self.impact_director.derive_attention_shift(att_map, impact_events)
            for imp in impact_events:
                imp_events = self.impact_director.plan_impact(imp, total_duration_sec=effective_dur)
                for ev in imp_events:
                    automation.add_event(ev)
                    automation.record_decision(
                        time=ev.start,
                        focus=imp.focus_target,
                        target=ev.target,
                        parameter=ev.parameter,
                        before=0.0,
                        after=ev.value,
                        reason=ev.reason,
                        source="impact_director",
                        director="impact",
                        priority=ev.priority,
                        intensity=imp.intensity,
                        phase=ev.metadata.get("phase", "IMPACT"),
                        preserved_elements=imp.preserve_targets,
                    )

        # --- 2. SILENCE DIRECTOR: Intentional Negative Sound Design ---
        if silence_events:
            for s_ev in silence_events:
                s_events = self.silence_director.plan_silence(s_ev, total_duration_sec=effective_dur)
                for ev in s_events:
                    automation.add_event(ev)
                    automation.record_decision(
                        time=ev.start,
                        focus="silence",
                        target=ev.target,
                        parameter=ev.parameter,
                        before=0.0,
                        after=ev.value,
                        reason=ev.reason,
                        source="silence_director",
                        director="silence",
                        priority=ev.priority,
                        silence_type=s_ev.type,
                        preserved_elements=s_ev.preserved_elements,
                    )

        # --- 3. ACOUSTIC PERSPECTIVE: Distance Propagation & Occlusion ---
        persp = acoustic_perspective
        if persp is None and intent.spatial_depth is not None:
            if isinstance(intent.spatial_depth, str):
                s_depth = intent.spatial_depth.lower()
                if "intimate" in s_depth or "dry" in s_depth:
                    persp = AcousticPerspective(distance="close")
                elif "hall" in s_depth or "cavernous" in s_depth:
                    persp = AcousticPerspective(distance="far")
                elif "exterior" in s_depth:
                    persp = AcousticPerspective(distance="medium")

        if persp is not None:
            p_events = self.perspective_director.plan_perspective(
                perspective=persp,
                start_sec=0.0,
                end_sec=effective_dur,
                target_stem="DX",
            )
            for ev in p_events:
                automation.add_event(ev)
                automation.record_decision(
                    time=ev.start,
                    focus="acoustic_perspective",
                    target=ev.target,
                    parameter=ev.parameter,
                    before=0.0,
                    after=ev.value,
                    reason=ev.reason,
                    source="perspective_director",
                    director="perspective",
                    priority=ev.priority,
                    distance=str(persp.distance),
                    occlusion=str(persp.occlusion),
                )

        # Edge Case: Completely empty scene or zero events
        if not att_map.events and not dialogue_segments:
            logger.debug("[AutomationPlanner] Clean baseline pass-through.")
            return automation

        # Segment the timeline into discrete focus windows
        focus_windows = att_map.resolve_windows()

        # If attention map has no windows but dialogue segments exist, synthesize windows from segments
        if not focus_windows and dialogue_segments and has_dialogue:
            synthesized_events = []
            for seg in dialogue_segments:
                s_ms = float(seg.get("start_ms", 0) or 0)
                e_ms = float(seg.get("end_ms", s_ms + 1000) or s_ms + 1000)
                prio = 0.85 if "whisper" in str(seg.get("style", "")).lower() else 0.75
                synthesized_events.append(
                    AttentionEvent(
                        start=round(s_ms / 1000.0, 4),
                        end=round(e_ms / 1000.0, 4),
                        focus_target=seg.get("speaker", "dialogue"),
                        priority=prio,
                        reason="Synthesized from screenplay speech segment",
                    )
                )
            att_map = AttentionMap(events=synthesized_events)
            focus_windows = att_map.resolve_windows()

        for w_start, w_end, dom_event in focus_windows:
            w_dur = round(w_end - w_start, 4)
            if w_dur <= 0.05:
                # Anti-Jitter: Ignore micro-slivers < 50ms
                continue

            target_focus = dom_event.focus_target
            priority = dom_event.priority
            reason = dom_event.reason or f"Focus on {target_focus}"

            # Check if dialogue is actively speaking in this window
            is_speech_active = has_dialogue and dom_event.category == "dialogue"

            # 1. Evaluate multitrack stem interaction plan
            interaction = self.interaction_engine.evaluate_interactions(
                scene_intent=intent,
                focus_target=target_focus,
                focus_priority=priority,
                speech_style=speech_style_override,
                is_dialogue_active=is_speech_active,
            )

            # Attack / Release envelope framing
            ev_start = max(0.0, round(w_start - self.attack_sec, 4))
            ev_end = round(w_end + self.release_sec, 4)

            # --- Target Stem: MX (Music) ---
            if has_music and interaction.mx_attenuation_db < -0.1:
                automation.add_event(
                    AutomationEvent(
                        start=ev_start,
                        end=ev_end,
                        target="MX",
                        parameter="gain",
                        value=interaction.mx_attenuation_db,
                        start_value=0.0,
                        curve="smooth",
                        priority=priority,
                        hierarchy="ATTENTION_PROTECTION",
                        reason=interaction.reason or reason,
                    )
                )
                automation.record_decision(
                    time=w_start,
                    focus=target_focus,
                    target="MX",
                    parameter="gain",
                    before=0.0,
                    after=interaction.mx_attenuation_db,
                    reason=interaction.reason,
                    source="stem_interaction",
                    priority=priority,
                )

            # --- Target Stem: FX (Foley) ---
            if has_foley and interaction.fx_attenuation_db < -0.1:
                automation.add_event(
                    AutomationEvent(
                        start=ev_start,
                        end=ev_end,
                        target="FX",
                        parameter="gain",
                        value=interaction.fx_attenuation_db,
                        start_value=0.0,
                        curve="smooth",
                        priority=priority,
                        hierarchy="ATTENTION_PROTECTION",
                        reason=f"Selective Foley attenuation: {interaction.reason}",
                    )
                )

            # --- Target Stem: AMB (Ambience) ---
            if has_ambience and interaction.amb_attenuation_db < -0.1:
                automation.add_event(
                    AutomationEvent(
                        start=ev_start,
                        end=ev_end,
                        target="AMB",
                        parameter="gain",
                        value=interaction.amb_attenuation_db,
                        start_value=0.0,
                        curve="smooth",
                        priority=priority,
                        hierarchy="ATTENTION_PROTECTION",
                        reason=f"Ambience tuck: {interaction.reason}",
                    )
                )

            # --- Dynamic Dialogue Masking (Spectral Carving on MX) ---
            if has_music and is_speech_active and interaction.mx_notch_needed:
                masking_dec = self.masking_analyzer.evaluate_masking(
                    start_sec=w_start,
                    end_sec=w_end,
                    attention_target=target_focus,
                    attention_priority=priority,
                    speech_style=speech_style_override,
                    estimated_dmr_db=estimated_dmr_db,
                    music_priority=intent.music_priority,
                )
                if abs(masking_dec.depth_db) > 0.1:
                    masking_event = self.masking_analyzer.generate_masking_event(
                        start_sec=ev_start,
                        end_sec=ev_end,
                        decision=masking_dec,
                    )
                    automation.add_event(masking_event)
                    automation.record_decision(
                        time=w_start,
                        focus=target_focus,
                        target="MX",
                        parameter="eq_depth",
                        before=0.0,
                        after=masking_dec.depth_db,
                        reason=masking_dec.reason,
                        source="dynamic_masking",
                        priority=priority,
                        frequency_hz=masking_dec.frequency_hz,
                        guardrail_applied=masking_dec.guardrail_applied,
                    )

        return automation
