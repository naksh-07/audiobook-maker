#!/usr/bin/env python3
"""
Audiobook Factory - Sound Design Adapter.
=========================================
Clean collaborator boundary between AgentDirector and SoundDesignDirector.
Prevents AgentDirector from becoming a monolithic god object.
Translates SoundDesignDirector's SceneAudioBlueprint and SoundTimeline into
standard CreativeManifest and SceneSoundscapeManifest structures.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.contracts import CreativeManifest, MusicCue, FoleyCue, AmbienceScene
from audiobook_factory.scene_acoustics import SceneSoundscapeManifest, SceneAcousticProfile
from audiobook_factory.sound_design.sound_director import SoundDesignDirector, get_sound_design_director
from audiobook_factory.sound_design.contracts import SceneAudioBlueprint, SoundTimeline
from audiobook_factory.sound_design.ambience_engine import get_ambience_engine
from audiobook_factory.sound_design.foley_engine import get_foley_engine
from audiobook_factory.sound_design.music_motif_director import get_music_cue_director
from audiobook_factory.sound_design.qc import get_sound_design_qc_auditor


class SoundDesignAdapter:
    """
    Adapter bridging SoundDesignDirector with AgentDirector and downstream pipeline.
    """

    def __init__(self, sound_director: Optional[SoundDesignDirector] = None):
        self.director = sound_director or get_sound_design_director()
        self.ambience_engine = get_ambience_engine()
        self.foley_engine = get_foley_engine()
        self.music_director = get_music_cue_director()
        self.qc_auditor = get_sound_design_qc_auditor()

    def direct_and_adapt_scene(
        self,
        scene_id: str,
        chapter_id: str,
        segments: List[Dict[str, Any]],
        start_ms: int,
        end_ms: int,
        dramatic_plan: Optional[Dict[str, Any]] = None,
        environment_override: Optional[str] = None,
        previous_scene_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Directs sound design for a scene and translates the output into
        standard contracts (SceneAcousticProfile, legacy MusicCue, legacy FoleyCue).
        """
        blueprint, timeline = self.director.direct_scene(
            scene_id=scene_id,
            chapter_id=chapter_id,
            segments=segments,
            start_ms=start_ms,
            end_ms=end_ms,
            dramatic_plan=dramatic_plan,
            environment_override=environment_override,
            previous_scene_id=previous_scene_id,
        )

        # 1. Convert Ambience to SceneAcousticProfile (audiobook_factory.scene_acoustics)
        # Filter timeline ambience specs or reconstruct
        amb_events = [e for e in timeline.events if e.category == "AMBIENCE"]
        # Use ambience engine conversion
        amb_layers = self.ambience_engine.build_scene_ambience(
            scene_id=scene_id,
            chapter_id=chapter_id,
            environment_id=blueprint.location_id,
            start_ms=start_ms,
            end_ms=end_ms,
            previous_scene_id=previous_scene_id,
        )
        acoustic_profile = self.ambience_engine.to_scene_acoustic_profile(
            scene_id=scene_id,
            start_ms=start_ms,
            end_ms=end_ms,
            environment_id=blueprint.location_id,
            layers=amb_layers,
        )

        # 2. Extract legacy FoleyCues
        foley_events = [e for e in timeline.events if e.category == "FOLEY"]
        foley_cues: List[FoleyCue] = []
        for idx, f_evt in enumerate(foley_events):
            foley_cues.append(
                FoleyCue(
                    cue_id=f"fc_{scene_id}_{idx+1}",
                    segment_index=idx + 1,
                    anchor_word=f_evt.asset_name.split()[-1] if f_evt.asset_name else "step",
                    pre_roll_ms=80,
                    asset_id=200 + idx,
                    asset_path=f_evt.asset_path or "foley.wav",
                    asset_name=f_evt.asset_name,
                    gain_dbfs=-16.0,
                    azimuth_pan=f_evt.spatial.azimuth_pan,
                )
            )

        # 3. Extract legacy MusicCues
        music_events = [e for e in timeline.events if e.category == "MUSIC"]
        music_cues: List[MusicCue] = []
        for idx, m_evt in enumerate(music_events):
            music_cues.append(
                MusicCue(
                    cue_id=f"mc_{scene_id}_{idx+1}",
                    cue_type="EMOTIONAL_UNDERSCORE",
                    track_id=1,
                    track_name=m_evt.asset_name or "Score Underscore",
                    section_name="THEMATIC_VARIATION",
                    section_start_sec=0.0,
                    start_ms=m_evt.start_ms,
                    duration_ms=m_evt.duration_ms,
                    gain_dbfs=-16.0,
                )
            )

        # 4. Run QC Audit
        qc_report = self.qc_auditor.audit_scene_sound_design(blueprint, timeline)

        return {
            "blueprint": blueprint,
            "timeline": timeline,
            "scene_acoustic_profile": acoustic_profile,
            "foley_cues": foley_cues,
            "music_cues": music_cues,
            "qc_report": qc_report,
        }

    def enrich_creative_manifest(
        self,
        manifest: CreativeManifest,
        blueprints: List[SceneAudioBlueprint],
        timelines: List[SoundTimeline],
    ) -> CreativeManifest:
        """
        Enriches an existing CreativeManifest with multi-signal cues derived from sound design.
        """
        all_foley: List[FoleyCue] = list(manifest.foley_cues)
        all_music: List[MusicCue] = list(manifest.music_cues)
        all_profiles: List[SceneAcousticProfile] = []

        for bp, tl in zip(blueprints, timelines):
            # Extract additional foley
            for idx, evt in enumerate(tl.events):
                if evt.category == "FOLEY":
                    all_foley.append(
                        FoleyCue(
                            cue_id=f"fc_sd_{evt.event_id}",
                            segment_index=1,
                            anchor_word="action",
                            asset_path=evt.asset_path or "foley.wav",
                            azimuth_pan=evt.spatial.azimuth_pan,
                            gain_dbfs=-16.0,
                        )
                    )
                elif evt.category == "MUSIC":
                    all_music.append(
                        MusicCue(
                            cue_id=f"mc_sd_{evt.event_id}",
                            cue_type="EMOTIONAL_UNDERSCORE",
                            track_id=1,
                            track_name=evt.asset_name or "Score",
                            section_name="SCORE_UNDERSCORE",
                            section_start_sec=0.0,
                            start_ms=evt.start_ms,
                            duration_ms=evt.duration_ms,
                            gain_dbfs=-16.0,
                        )
                    )


        # Create updated manifest copy
        manifest_dict = manifest.model_dump()
        manifest_dict["foley_cues"] = [c.model_dump() for c in all_foley]
        manifest_dict["music_cues"] = [c.model_dump() for c in all_music]
        manifest_dict["metadata"]["sound_design_blueprints"] = len(blueprints)
        manifest_dict["metadata"]["sound_design_timeline_events"] = sum(len(t.events) for t in timelines)

        return CreativeManifest.model_validate(manifest_dict)


_GLOBAL_ADAPTER: Optional[SoundDesignAdapter] = None

def get_sound_design_adapter() -> SoundDesignAdapter:
    """Returns singleton instance of SoundDesignAdapter."""
    global _GLOBAL_ADAPTER
    if _GLOBAL_ADAPTER is None:
        _GLOBAL_ADAPTER = SoundDesignAdapter()
    return _GLOBAL_ADAPTER
