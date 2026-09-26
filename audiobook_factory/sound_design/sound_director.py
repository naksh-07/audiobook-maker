#!/usr/bin/env python3
"""
Audiobook Factory - Capability 20: Master Sound Design Director & Timeline Engine.
===================================================================================
Coordinates all 20 sound design capabilities:
- Scene understanding and blueprint generation.
- Decoupled layered ambience and stateful cross-scene evolution.
- Contextual crowd walla with dialogue subordination.
- Intelligent foley scoring and low-value verb rejection.
- Character physics, material interaction matrix, and tableware isolation.
- Narrative hard SFX impacts and multi-tier creature sound design.
- Supernatural and magical sound language.
- Leitmotif variation and adaptive music cue direction.
- Intentional negative sound design (first-class silence events).
- Abstract room acoustics and virtual soundstage spatial geography.
Outputs a unified chronological SoundTimeline and SceneAudioBlueprint.
"""

from __future__ import annotations
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.sound_design.contracts import (
    SceneAudioBlueprint,
    SoundTimeline,
    SoundTimelineEvent,
    SceneAudioUnderstandingResult,
    RelativeIntensity,
    AttentionPriority,
    SpatialMetadata,
    MixIntent,
)
from audiobook_factory.sound_design.scene_understanding import get_scene_audio_analyzer
from audiobook_factory.sound_design.blueprint import get_blueprint_builder
from audiobook_factory.sound_design.ambience_engine import get_ambience_engine
from audiobook_factory.sound_design.walla_engine import get_walla_engine
from audiobook_factory.sound_design.silence_engine import get_silence_engine
from audiobook_factory.sound_design.foley_engine import get_foley_engine
from audiobook_factory.sound_design.foley_character_material import get_character_foley_registry
from audiobook_factory.sound_design.narrative_sfx import get_hard_sfx_engine, get_creature_engine
from audiobook_factory.sound_design.magical_sound import get_magical_sound_engine
from audiobook_factory.sound_design.music_motif_director import get_music_cue_director
from audiobook_factory.sound_design.spatial_acoustics import (
    get_spatial_acoustics_engine,
    get_spatial_geography_engine,
)
from audiobook_factory.sound_design.asset_retriever import get_asset_retriever


from audiobook_factory.sound_design.scene_state import get_scene_state_manager


class SoundDesignDirector:
    """
    Master Sound Design Orchestrator.
    Produces comprehensive SceneAudioBlueprint and unified chronological SoundTimeline.
    """

    def __init__(self):
        self.analyzer = get_scene_audio_analyzer()
        self.blueprint_builder = get_blueprint_builder()
        self.ambience_engine = get_ambience_engine()
        self.walla_engine = get_walla_engine()
        self.silence_engine = get_silence_engine()
        self.foley_engine = get_foley_engine()
        self.character_registry = get_character_foley_registry()
        self.hard_sfx_engine = get_hard_sfx_engine()
        self.creature_engine = get_creature_engine()
        self.magic_engine = get_magical_sound_engine()
        self.music_director = get_music_cue_director()
        self.spatial_acoustics = get_spatial_acoustics_engine()
        self.spatial_geography = get_spatial_geography_engine()
        self.retriever = get_asset_retriever()
        self.state_manager = get_scene_state_manager()

    def direct_scene(
        self,
        scene_id: str,
        chapter_id: str,
        segments: List[Dict[str, Any]],
        start_ms: int,
        end_ms: int,
        dramatic_plan: Optional[Dict[str, Any]] = None,
        environment_override: Optional[str] = None,
        previous_scene_id: Optional[str] = None,
        characters_override: Optional[List[str]] = None,
        tension_override: Optional[float] = None,
        emotion_override: Optional[str] = None,
    ) -> Tuple[SceneAudioBlueprint, SoundTimeline]:
        """
        Directs complete sound design for a single scene with narrative beat anchoring
        and real asset resolution.
        """
        duration_ms = max(0, end_ms - start_ms)

        # 1. Scene Audio Understanding
        understanding = self.analyzer.analyze_scene(
            scene_id=scene_id,
            chapter_id=chapter_id,
            segments=segments,
            dramatic_plan=dramatic_plan,
        )
        if environment_override:
            understanding.environment_type = environment_override
            env_p = self.analyzer.env_registry.get_profile(environment_override)
            if env_p and env_p.typical_walla:
                understanding.requires_walla = True
                understanding.walla_description = env_p.typical_walla
        if characters_override:
            understanding.characters_present = characters_override
        if tension_override is not None:
            understanding.tension_level = tension_override
        if emotion_override:
            understanding.dominant_emotion = emotion_override

        # 2. Stage characters on virtual soundstage
        staged_positions = self.spatial_geography.stage_scene_characters(
            scene_id=scene_id,
            characters=understanding.characters_present,
        )

        # 3. Compute Segment Timing Map & Shared Acoustic State
        seg_bounds = self.state_manager.compute_segment_timing_map(segments, start_ms, end_ms)
        acoustic_state = self.state_manager.initialize_state(scene_id, understanding, staged_positions)

        # 4. Build Director Instruction Blueprint
        corpus = " ".join(s.get("text", "") for s in segments)
        corpus_hash = hashlib.sha256(corpus.encode("utf-8")).hexdigest()
        blueprint = self.blueprint_builder.build_blueprint(
            understanding=understanding,
            source_text_hash=corpus_hash,
        )

        # 5. Synthesize Layered Ambience
        ambience_layers = self.ambience_engine.build_scene_ambience(
            scene_id=scene_id,
            chapter_id=chapter_id,
            environment_id=understanding.environment_type,
            start_ms=start_ms,
            end_ms=end_ms,
            tension_level=understanding.tension_level,
            mood=understanding.dominant_emotion,
            previous_scene_id=previous_scene_id,
        )

        # 6. Evaluate Walla (Crowd Human Presence)
        all_sfx_cues = [c for s in segments for c in s.get("sfx_cues", [])]
        walla_layer = self.walla_engine.build_scene_walla(
            scene_id=scene_id,
            environment_id=understanding.environment_type,
            characters_present=understanding.characters_present,
            scene_text=corpus,
            tension_level=understanding.tension_level,
            dominant_emotion=understanding.dominant_emotion,
            requires_walla=understanding.requires_walla,
            walla_description=understanding.walla_description,
            sfx_cues=all_sfx_cues,
        )

        # 7. Evaluate Foley candidates (narrative relevance scoring & low-value verb rejection)
        scored_foley = self.foley_engine.process_scene_actions(
            candidates=understanding.action_candidates,
            tension_level=understanding.tension_level,
            restraint_target=blueprint.restraint_target,
        )

        # 8. Detect Action / Hard SFX impacts
        hard_sfx_events = self.hard_sfx_engine.detect_events_from_segments(
            segments=segments,
            tension_level=understanding.tension_level,
        )

        # 9. Detect Creature audio
        creature_events = self.creature_engine.detect_creature_events(
            segments=segments,
            creature_presence=understanding.creature_presence,
            tension_level=understanding.tension_level,
        )

        # 10. Detect Magic / Supernatural occurrences
        magic_events = self.magic_engine.detect_magic_events(
            segments=segments,
            tension_level=understanding.tension_level,
        )

        # 11. Cross-System Interaction Evaluation
        is_stealth = "stealth" in understanding.dominant_emotion.lower() or any("stealth" in s.get("text", "").lower() for s in segments)
        cross_reactions = self.state_manager.evaluate_cross_system_reactions(
            state=acoustic_state,
            has_magic=len(magic_events) > 0,
            has_creature=len(creature_events) > 0,
            has_hard_sfx=len(hard_sfx_events) > 0,
            is_stealth=is_stealth,
        )
        blueprint.metadata["cross_system_interactions"] = [r.model_dump() for r in cross_reactions]
        blueprint.metadata["narrative_phase"] = acoustic_state.active_phase

        # 12. Direct Music Cues
        beats = dramatic_plan.get("dramatic_beats", []) if dramatic_plan else []
        music_cues = self.music_director.direct_scene_cues(
            scene_id=scene_id,
            start_ms=start_ms,
            end_ms=end_ms,
            tension_level=understanding.tension_level,
            dominant_emotion=understanding.dominant_emotion,
            characters_present=understanding.characters_present,
            dramatic_beats=beats,
            restraint_target=blueprint.restraint_target,
        )

        # 13. Plan Intentional Silence Events
        silence_events = self.silence_engine.plan_silence_events(
            scene_id=scene_id,
            scene_understanding=understanding,
            start_ms=start_ms,
            end_ms=end_ms,
            dramatic_beats=beats,
        )

        # ---------------------------------------------------------------------
        # Assemble Unified Chronological SoundTimeline (Beat-Anchored + Real Assets)
        # ---------------------------------------------------------------------
        timeline_events: List[SoundTimelineEvent] = []

        # A. Ambience layers across scene span
        for a_idx, amb in enumerate(ambience_layers):
            amb_desc = self.retriever.resolve_ambience_asset(understanding.environment_type, tier=amb.layer_tier)
            asset_p = amb_desc.filepath if amb_desc else (amb.asset_path if (amb.asset_path and Path(amb.asset_path).exists()) else "")
            is_res = bool(asset_p)
            unres_r = None if is_res else f"No approved ambience asset for {understanding.environment_type} {amb.layer_tier}"

            timeline_events.append(
                SoundTimelineEvent(
                    event_id=f"evt_amb_{scene_id}_{a_idx+1}_{amb.layer_tier.lower()}",
                    category="AMBIENCE",
                    start_ms=start_ms,
                    duration_ms=duration_ms,
                    relative_intensity=amb.relative_intensity,
                    priority="LOW",
                    asset_path=asset_p,
                    asset_name=amb_desc.filename if amb_desc else amb.asset_name,
                    spatial=amb.spatial,
                    mix_intent=amb.mix_intent,
                    decision_reason=f"Layered ambience tier {amb.layer_tier}",
                    source_segment_index=1,
                    timing_rationale=f"Continuous environmental bed across scene [{start_ms}ms, {end_ms}ms]",
                    dramatic_purpose=f"Acoustic room tone ({understanding.environment_type})",
                    confidence=1.0,
                    is_resolved=is_res,
                    unresolved_reason=unres_r,
                    resolved_asset=amb_desc,
                )
            )

        # B. Walla layer
        if walla_layer and acoustic_state.walla_permitted:
            w_desc = self.retriever.resolve_walla_asset(walla_layer.activity_type, density=walla_layer.density, environment=understanding.environment_type)
            asset_p = w_desc.filepath if w_desc else (walla_layer.asset_path if (walla_layer.asset_path and Path(walla_layer.asset_path).exists()) else "")
            is_res = bool(asset_p)
            unres_r = None if is_res else f"No approved walla asset for {walla_layer.activity_type}"

            timeline_events.append(
                SoundTimelineEvent(
                    event_id=f"evt_walla_{scene_id}_1",
                    category="WALLA",
                    start_ms=start_ms,
                    duration_ms=duration_ms,
                    relative_intensity=walla_layer.relative_intensity,
                    priority="LOW",
                    asset_path=asset_p,
                    asset_name=w_desc.filename if w_desc else f"Walla {walla_layer.activity_type}",
                    spatial=SpatialMetadata(azimuth_pan=0.0, proximity=walla_layer.distance),
                    mix_intent=walla_layer.mix_intent,
                    decision_reason=f"Contextual walla activity: {walla_layer.activity_type}",
                    source_segment_index=1,
                    timing_rationale=f"Contextual crowd murmur across scene [{start_ms}ms, {end_ms}ms]",
                    dramatic_purpose=f"Background crowd presence ({walla_layer.activity_type})",
                    confidence=0.95,
                    is_resolved=is_res,
                    unresolved_reason=unres_r,
                    resolved_asset=w_desc,
                )
            )

        # C. Accepted Foley events (Segment-Anchored)
        for f_idx, fol in enumerate(scored_foley):
            if fol.status != "ACCEPTED":
                continue

            seg_info = seg_bounds.get(fol.segment_index, {})
            s_start = seg_info.get("start_ms", start_ms)
            s_end = seg_info.get("end_ms", s_start + 1000)
            foley_start = min(s_start + 80, max(start_ms, end_ms - 450))

            char_pos = self.spatial_geography.get_entity_position(scene_id, fol.subject)
            f_desc = self.retriever.resolve_foley_asset(
                action_verb=fol.action_verb,
                exciter_material=fol.object_material,
                surface_material=fol.surface_material,
            )
            asset_p = f_desc.filepath if f_desc else ""
            is_res = bool(asset_p)
            unres_r = None if is_res else f"No approved Foley asset in SoundBank for {fol.action_verb}_{fol.object_material}"

            timeline_events.append(
                SoundTimelineEvent(
                    event_id=f"evt_foley_{scene_id}_{f_idx+1}",
                    category="FOLEY",
                    start_ms=foley_start,
                    duration_ms=450,
                    relative_intensity="subtle_bed",
                    priority="MEDIUM",
                    asset_path=asset_p,
                    asset_name=f_desc.filename if f_desc else f"{fol.subject} {fol.action_verb}",
                    spatial=char_pos,
                    mix_intent=MixIntent(duck_under_dialogue=True),
                    decision_reason=f"Accepted foley action: {fol.action_verb} (score: {fol.foley_score:.2f})",
                    provenance_beat_id=fol.provenance_beat_id,
                    source_segment_index=fol.segment_index,
                    timing_rationale=fol.timing_rationale or f"Anchored to physical action '{fol.action_verb}' in segment {fol.segment_index}",
                    dramatic_purpose=fol.dramatic_purpose or f"Physical Foley ({fol.action_verb})",
                    confidence=fol.confidence,
                    is_resolved=is_res,
                    unresolved_reason=unres_r,
                    resolved_asset=f_desc,
                )
            )

        # D. Hard SFX events (Segment-Anchored)
        for h_idx, hsfx in enumerate(hard_sfx_events):
            seg_info = seg_bounds.get(hsfx.segment_index, {})
            s_start = seg_info.get("start_ms", start_ms)
            if hsfx.start_ms > 0 and hsfx.start_ms >= start_ms:
                sfx_start = hsfx.start_ms
            elif hsfx.start_ms > 0:
                sfx_start = start_ms + hsfx.start_ms
            else:
                sfx_start = s_start + 100 + (h_idx * 150)
            sfx_start = min(sfx_start, max(start_ms, end_ms - 1200))

            h_desc = self.retriever.resolve_hard_sfx_asset(hsfx.sfx_type) if not (hsfx.asset_path and Path(hsfx.asset_path).exists()) else None
            asset_p = hsfx.asset_path if (hsfx.asset_path and Path(hsfx.asset_path).exists()) else (h_desc.filepath if h_desc else "")
            is_res = bool(asset_p)
            unres_r = None if is_res else f"No approved Hard SFX asset in SoundBank for {hsfx.sfx_type}"

            timeline_events.append(
                SoundTimelineEvent(
                    event_id=f"evt_hardsfx_{scene_id}_{h_idx+1}",
                    category="HARD_SFX",
                    start_ms=sfx_start,
                    duration_ms=1200,
                    relative_intensity=hsfx.relative_intensity,
                    priority=hsfx.priority,
                    asset_path=asset_p,
                    asset_name=h_desc.filename if h_desc else hsfx.sfx_type,
                    spatial=hsfx.spatial,
                    mix_intent=hsfx.mix_intent,
                    decision_reason=hsfx.decision_reason,
                    provenance_segment_uid=hsfx.provenance_segment_uid,
                    provenance_beat_id=hsfx.provenance_beat_id,
                    source_segment_index=hsfx.segment_index,
                    timing_rationale=hsfx.timing_rationale or f"Anchored to impact in segment {hsfx.segment_index}",
                    dramatic_purpose=hsfx.dramatic_purpose or f"Physical impact ({hsfx.sfx_type})",
                    confidence=hsfx.confidence,
                    is_resolved=is_res,
                    unresolved_reason=unres_r,
                    resolved_asset=h_desc,
                )
            )

        # E. Creature events (Anchored to Narrative Beat, NO 35% SHORTCUT)
        for c_idx, crt in enumerate(creature_events):
            seg_idx = crt.segment_index or 1
            seg_info = seg_bounds.get(seg_idx, {})
            s_start = seg_info.get("start_ms", start_ms)
            c_start = min(s_start + 150 + (c_idx * 300), max(start_ms, end_ms - 1500))

            c_desc = self.retriever.resolve_creature_asset(crt.creature_type, crt.element, emotion=crt.emotional_state) if not (crt.asset_path and Path(crt.asset_path).exists()) else None
            asset_p = crt.asset_path if (crt.asset_path and Path(crt.asset_path).exists()) else (c_desc.filepath if c_desc else "")
            is_res = bool(asset_p)
            unres_r = None if is_res else f"No approved creature asset for {crt.creature_type} {crt.element}"

            timeline_events.append(
                SoundTimelineEvent(
                    event_id=f"evt_creature_{scene_id}_{c_idx+1}",
                    category="CREATURE",
                    start_ms=c_start,
                    duration_ms=1500,
                    relative_intensity=crt.relative_intensity,
                    priority=crt.priority,
                    asset_path=asset_p,
                    asset_name=c_desc.filename if c_desc else f"{crt.creature_type} {crt.element}",
                    spatial=crt.spatial,
                    mix_intent=MixIntent(duck_under_dialogue=True, sidechain_trigger=True),
                    decision_reason=crt.decision_reason,
                    provenance_segment_uid=crt.provenance_segment_uid,
                    provenance_beat_id=crt.provenance_beat_id,
                    source_segment_index=seg_idx,
                    timing_rationale=crt.timing_rationale or f"Anchored to creature vocalization in segment {seg_idx}",
                    dramatic_purpose=crt.dramatic_purpose or f"Acoustic creature manifestation ({crt.creature_type})",
                    confidence=crt.confidence,
                    is_resolved=is_res,
                    unresolved_reason=unres_r,
                    resolved_asset=c_desc,
                )
            )

        # F. Magic events (Anchored to Casting Beat, NO 40% SHORTCUT)
        for m_idx, mag in enumerate(magic_events):
            seg_idx = mag.segment_index or 1
            seg_info = seg_bounds.get(seg_idx, {})
            s_start = seg_info.get("start_ms", start_ms)
            stage_offset = 50 if mag.stage == "charge_hum" else (250 if mag.stage == "release_burst" else 450)
            m_start = min(s_start + stage_offset + (m_idx * 200), max(start_ms, end_ms - 1800))

            m_desc = self.retriever.resolve_magical_asset(mag.spell_or_artifact_name, mag.stage) if not (mag.asset_path and Path(mag.asset_path).exists()) else None
            asset_p = mag.asset_path if (mag.asset_path and Path(mag.asset_path).exists()) else (m_desc.filepath if m_desc else "")
            is_res = bool(asset_p)
            unres_r = None if is_res else f"No approved magical asset for {mag.spell_or_artifact_name} {mag.stage}"

            timeline_events.append(
                SoundTimelineEvent(
                    event_id=f"evt_magic_{scene_id}_{m_idx+1}",
                    category="MAGIC",
                    start_ms=m_start,
                    duration_ms=1800,
                    relative_intensity=mag.relative_intensity,
                    priority=mag.priority,
                    asset_path=asset_p,
                    asset_name=m_desc.filename if m_desc else f"{mag.spell_or_artifact_name} {mag.stage}",
                    spatial=mag.spatial,
                    mix_intent=MixIntent(duck_under_dialogue=True, sidechain_trigger=True),
                    decision_reason=mag.decision_reason,
                    provenance_segment_uid=mag.provenance_segment_uid,
                    provenance_beat_id=mag.provenance_beat_id,
                    source_segment_index=seg_idx,
                    timing_rationale=mag.timing_rationale or f"Anchored to magical casting in segment {seg_idx}",
                    dramatic_purpose=mag.dramatic_purpose or f"Magical supernatural action ({mag.spell_or_artifact_name})",
                    confidence=mag.confidence,
                    is_resolved=is_res,
                    unresolved_reason=unres_r,
                    resolved_asset=m_desc,
                )
            )

        # G. Music Cues
        for mc_idx, mc in enumerate(music_cues):
            m_desc = self.retriever.resolve_music_asset(track_name_or_mood=mc.track_name or mc.variation_mode, cue_type=mc.cue_type)
            asset_p = m_desc.filepath if m_desc else ""
            is_res = bool(asset_p)
            unres_r = None if is_res else f"No approved music score asset for {mc.track_name or mc.cue_id}"

            timeline_events.append(
                SoundTimelineEvent(
                    event_id=f"evt_music_{scene_id}_{mc_idx+1}",
                    category="MUSIC",
                    start_ms=mc.start_ms,
                    duration_ms=mc.duration_ms,
                    relative_intensity=mc.relative_intensity,
                    priority=mc.priority,
                    asset_path=asset_p,
                    asset_name=m_desc.filename if m_desc else mc.track_name,
                    spatial=SpatialMetadata(azimuth_pan=0.0, proximity="normal_room"),
                    mix_intent=mc.mix_intent,
                    decision_reason=mc.dramatic_justification,
                    source_segment_index=1,
                    timing_rationale=f"Anchored to dramatic scene cue window [{mc.start_ms}ms, {mc.start_ms + mc.duration_ms}ms]",
                    dramatic_purpose=mc.dramatic_justification or f"Score underscore ({mc.cue_type})",
                    confidence=0.95,
                    is_resolved=is_res,
                    unresolved_reason=unres_r,
                    resolved_asset=m_desc,
                )
            )

        # H. Intentional Silence Events
        for s_idx, sil in enumerate(silence_events):
            timeline_events.append(
                SoundTimelineEvent(
                    event_id=f"evt_silence_{scene_id}_{s_idx+1}",
                    category="SILENCE",
                    start_ms=sil.start_ms,
                    duration_ms=sil.duration_ms,
                    relative_intensity="whisper_quiet",
                    priority="HIGH",
                    asset_path="",
                    asset_name=sil.purpose,
                    spatial=SpatialMetadata(azimuth_pan=0.0, proximity="normal_room"),
                    mix_intent=MixIntent(duck_under_dialogue=False),
                    decision_reason=f"Intentional negative sound: {sil.purpose} ({sil.dramatic_rationale})",
                    source_segment_index=1,
                    timing_rationale=f"Intentional dramatic silence window [{sil.start_ms}ms, {sil.start_ms + sil.duration_ms}ms]",
                    dramatic_purpose=f"Negative sound design ({sil.purpose})",
                    confidence=1.0,
                    is_resolved=True,
                )
            )

        # Sort timeline chronologically
        timeline_events.sort(key=lambda e: e.start_ms)

        timeline = SoundTimeline(
            timeline_id=f"timeline_{scene_id}",
            chapter_id=chapter_id,
            scene_id=scene_id,
            total_duration_ms=duration_ms,
            events=timeline_events,
        )

        logger.info(
            f"[SoundDesignDirector] Scene '{scene_id}' directed successfully: {len(timeline_events)} sound events planned."
        )
        return blueprint, timeline


_GLOBAL_SOUND_DIRECTOR: Optional[SoundDesignDirector] = None

def get_sound_design_director() -> SoundDesignDirector:
    """Returns singleton instance of SoundDesignDirector."""
    global _GLOBAL_SOUND_DIRECTOR
    if _GLOBAL_SOUND_DIRECTOR is None:
        _GLOBAL_SOUND_DIRECTOR = SoundDesignDirector()
    return _GLOBAL_SOUND_DIRECTOR
