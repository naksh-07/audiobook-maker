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
        Directs complete sound design for a single scene.
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

        # 3. Build Director Instruction Blueprint
        corpus = " ".join(s.get("text", "") for s in segments)
        corpus_hash = hashlib.sha256(corpus.encode("utf-8")).hexdigest()
        blueprint = self.blueprint_builder.build_blueprint(
            understanding=understanding,
            source_text_hash=corpus_hash,
        )

        # 4. Synthesize Layered Ambience
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

        # 5. Evaluate Walla (Crowd Human Presence)
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


        # 6. Evaluate Foley candidates (narrative relevance scoring & low-value verb rejection)
        scored_foley = self.foley_engine.process_scene_actions(
            candidates=understanding.action_candidates,
            tension_level=understanding.tension_level,
            restraint_target=blueprint.restraint_target,
        )

        # 7. Detect Action / Hard SFX impacts
        hard_sfx_events = self.hard_sfx_engine.detect_events_from_segments(
            segments=segments,
            tension_level=understanding.tension_level,
        )

        # 8. Detect Creature audio
        creature_events = self.creature_engine.detect_creature_events(
            segments=segments,
            creature_presence=understanding.creature_presence,
            tension_level=understanding.tension_level,
        )

        # 9. Detect Magic / Supernatural occurrences
        magic_events = self.magic_engine.detect_magic_events(
            segments=segments,
            tension_level=understanding.tension_level,
        )

        # 10. Direct Music Cues
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

        # 11. Plan Intentional Silence Events
        silence_events = self.silence_engine.plan_silence_events(
            scene_id=scene_id,
            scene_understanding=understanding,
            start_ms=start_ms,
            end_ms=end_ms,
            dramatic_beats=beats,
        )

        # ---------------------------------------------------------------------
        # Assemble Unified Chronological SoundTimeline
        # ---------------------------------------------------------------------
        timeline_events: List[SoundTimelineEvent] = []

        # A. Ambience layers across scene span
        for a_idx, amb in enumerate(ambience_layers):
            timeline_events.append(
                SoundTimelineEvent(
                    event_id=f"evt_amb_{scene_id}_{a_idx+1}_{amb.layer_tier.lower()}",
                    category="AMBIENCE",
                    start_ms=start_ms,
                    duration_ms=duration_ms,
                    relative_intensity=amb.relative_intensity,
                    priority="LOW",
                    asset_path=amb.asset_path,
                    asset_name=amb.asset_name,
                    spatial=amb.spatial,
                    mix_intent=amb.mix_intent,
                    decision_reason=f"Layered ambience tier {amb.layer_tier}",
                )
            )

        # B. Walla layer
        if walla_layer:
            timeline_events.append(
                SoundTimelineEvent(
                    event_id=f"evt_walla_{scene_id}_1",
                    category="WALLA",
                    start_ms=start_ms,
                    duration_ms=duration_ms,
                    relative_intensity=walla_layer.relative_intensity,
                    priority="LOW",
                    asset_path=walla_layer.asset_path,
                    asset_name=f"Walla {walla_layer.activity_type}",
                    spatial=SpatialMetadata(azimuth_pan=0.0, proximity=walla_layer.distance),
                    mix_intent=walla_layer.mix_intent,
                    decision_reason=f"Contextual walla activity: {walla_layer.activity_type}",
                )
            )

        # C. Accepted Foley events
        for f_idx, fol in enumerate(scored_foley):
            if fol.status != "ACCEPTED":
                continue
            seg_start = start_ms + int(duration_ms * (fol.segment_index / max(1, len(segments))))
            char_pos = self.spatial_geography.get_entity_position(scene_id, fol.subject)
            timeline_events.append(
                SoundTimelineEvent(
                    event_id=f"evt_foley_{scene_id}_{f_idx+1}",
                    category="FOLEY",
                    start_ms=seg_start,
                    duration_ms=450,
                    relative_intensity="subtle_bed",
                    priority="MEDIUM",
                    asset_path=f"foley_{fol.action_verb}_{fol.object_material}.wav",
                    asset_name=f"{fol.subject} {fol.action_verb}",
                    spatial=char_pos,
                    mix_intent=MixIntent(duck_under_dialogue=True),
                    decision_reason=f"Accepted foley action: {fol.action_verb} (score: {fol.foley_score:.2f})",
                    provenance_beat_id=fol.provenance_beat_id,
                )
            )

        # D. Hard SFX events
        for h_idx, hsfx in enumerate(hard_sfx_events):
            timeline_events.append(
                SoundTimelineEvent(
                    event_id=f"evt_hardsfx_{scene_id}_{h_idx+1}",
                    category="HARD_SFX",
                    start_ms=start_ms + hsfx.start_ms,
                    duration_ms=1200,
                    relative_intensity=hsfx.relative_intensity,
                    priority=hsfx.priority,
                    asset_path=hsfx.asset_path,
                    asset_name=hsfx.sfx_type,
                    spatial=hsfx.spatial,
                    mix_intent=hsfx.mix_intent,
                    decision_reason=hsfx.decision_reason,
                )
            )

        # E. Creature events
        for c_idx, crt in enumerate(creature_events):
            timeline_events.append(
                SoundTimelineEvent(
                    event_id=f"evt_creature_{scene_id}_{c_idx+1}",
                    category="CREATURE",
                    start_ms=start_ms + int(duration_ms * 0.35 + c_idx * 2000),
                    duration_ms=1500,
                    relative_intensity=crt.relative_intensity,
                    priority=crt.priority,
                    asset_path=crt.asset_path,
                    asset_name=f"{crt.creature_type} {crt.element}",
                    spatial=crt.spatial,
                    mix_intent=MixIntent(duck_under_dialogue=True, sidechain_trigger=True),
                    decision_reason=crt.decision_reason,
                )
            )

        # F. Magic events
        for m_idx, mag in enumerate(magic_events):
            timeline_events.append(
                SoundTimelineEvent(
                    event_id=f"evt_magic_{scene_id}_{m_idx+1}",
                    category="MAGIC",
                    start_ms=start_ms + int(duration_ms * 0.40 + m_idx * 1500),
                    duration_ms=1800,
                    relative_intensity=mag.relative_intensity,
                    priority=mag.priority,
                    asset_path=mag.asset_path,
                    asset_name=f"{mag.spell_or_artifact_name} {mag.stage}",
                    spatial=mag.spatial,
                    mix_intent=MixIntent(duck_under_dialogue=True, sidechain_trigger=True),
                    decision_reason=mag.decision_reason,
                )
            )

        # G. Music Cues
        for mc_idx, mc in enumerate(music_cues):
            timeline_events.append(
                SoundTimelineEvent(
                    event_id=f"evt_music_{scene_id}_{mc_idx+1}",
                    category="MUSIC",
                    start_ms=mc.start_ms,
                    duration_ms=mc.duration_ms,
                    relative_intensity=mc.relative_intensity,
                    priority=mc.priority,
                    asset_path=f"music_cue_{mc.cue_id}.wav",
                    asset_name=mc.track_name,
                    spatial=SpatialMetadata(azimuth_pan=0.0, proximity="normal_room"),
                    mix_intent=mc.mix_intent,
                    decision_reason=mc.dramatic_justification,
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
