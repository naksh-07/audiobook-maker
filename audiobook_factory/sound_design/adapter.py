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
        # Reconstruct AmbienceLayerSpec from existing timeline AMBIENCE events (prevents duplicate execution & state corruption)
        amb_events = [e for e in timeline.events if e.category == "AMBIENCE"]
        amb_layers: List[Any] = []
        for idx, evt in enumerate(amb_events):
            tier = "BASE" if idx == 0 else "MIDGROUND"
            if "MIDGROUND" in evt.decision_reason:
                tier = "MIDGROUND"
            elif "FOREGROUND" in evt.decision_reason:
                tier = "FOREGROUND"
            elif "DISTANT" in evt.decision_reason:
                tier = "DISTANT"

            from audiobook_factory.sound_design.contracts import AmbienceLayerSpec
            amb_layers.append(
                AmbienceLayerSpec(
                    layer_tier=tier,  # type: ignore
                    asset_name=evt.asset_name or Path(evt.asset_path).name,
                    asset_path=evt.asset_path,
                    relative_intensity=evt.relative_intensity,
                    loop=True,
                    spatial=evt.spatial,
                    mix_intent=evt.mix_intent,
                )
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
                    asset_path=f_evt.asset_path or "",
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
        existing_foley_ids = {c.cue_id for c in manifest.foley_cues}
        all_music: List[MusicCue] = list(manifest.music_cues)
        all_profiles: List[SceneAcousticProfile] = []
        silence_records: List[Dict[str, Any]] = []

        for bp, tl in zip(blueprints, timelines):
            # 1. Reconstruct AmbienceLayerSpec from timeline AMBIENCE events
            amb_events = [e for e in tl.events if e.category == "AMBIENCE"]
            amb_layers: List[Any] = []
            for idx, evt in enumerate(amb_events):
                tier = "BASE" if idx == 0 else "MIDGROUND"
                if "MIDGROUND" in evt.decision_reason:
                    tier = "MIDGROUND"
                elif "FOREGROUND" in evt.decision_reason:
                    tier = "FOREGROUND"
                elif "DISTANT" in evt.decision_reason:
                    tier = "DISTANT"

                from audiobook_factory.sound_design.contracts import AmbienceLayerSpec
                amb_layers.append(
                    AmbienceLayerSpec(
                        layer_tier=tier,  # type: ignore
                        asset_name=evt.asset_name or (Path(evt.asset_path).name if evt.asset_path else "room_tone"),
                        asset_path=evt.asset_path or "room_tone",
                        relative_intensity=evt.relative_intensity,
                        loop=True,
                        spatial=evt.spatial,
                        mix_intent=evt.mix_intent,
                    )
                )

            # Derive scene start/end bounds from timeline events
            sc_start_ms = amb_events[0].start_ms if amb_events else min((e.start_ms for e in tl.events), default=0)
            sc_duration_ms = max(tl.total_duration_ms, amb_events[0].duration_ms if amb_events else 1000)
            sc_end_ms = sc_start_ms + max(1000, sc_duration_ms)

            profile = self.ambience_engine.to_scene_acoustic_profile(
                scene_id=bp.scene_id,
                start_ms=sc_start_ms,
                end_ms=sc_end_ms,
                environment_id=bp.location_id,
                layers=amb_layers,
            )
            all_profiles.append(profile)

            # 2. Extract foley cues (deduplicated)
            for idx, evt in enumerate(tl.events):
                if evt.category == "FOLEY" and evt.asset_path:
                    cue_id = f"fc_sd_{evt.event_id}"
                    if cue_id not in existing_foley_ids:
                        existing_foley_ids.add(cue_id)
                        all_foley.append(
                            FoleyCue(
                                cue_id=cue_id,
                                segment_index=evt.source_segment_index or 1,
                                anchor_word=evt.asset_name.split()[-1] if evt.asset_name else "action",
                                pre_roll_ms=80,
                                asset_path=evt.asset_path,
                                asset_name=evt.asset_name,
                                azimuth_pan=evt.spatial.azimuth_pan,
                                gain_dbfs=-16.0,
                            )
                        )
                elif evt.category == "MUSIC" and evt.asset_name:
                    all_music.append(
                        MusicCue(
                            cue_id=f"mc_sd_{evt.event_id}",
                            cue_type="EMOTIONAL_UNDERSCORE",
                            track_id=1,
                            track_name=evt.asset_name,
                            section_name="SCORE_UNDERSCORE",
                            section_start_sec=0.0,
                            start_ms=evt.start_ms,
                            duration_ms=evt.duration_ms,
                            gain_dbfs=-16.0,
                        )
                    )
                elif evt.category == "SILENCE":
                    silence_records.append({
                        "scene_id": bp.scene_id,
                        "event_id": evt.event_id,
                        "start_ms": evt.start_ms,
                        "duration_ms": evt.duration_ms,
                        "reason": evt.decision_reason,
                    })

        # Apply Voice Limiter & Priority Stealing to prevent transient congestion
        from audiobook_factory.acoustic_bus_matrix import filter_concurrency_window
        all_foley = filter_concurrency_window(all_foley, window_ms=200, max_concurrency=3)

        # Create updated manifest copy
        manifest_dict = manifest.model_dump()
        manifest_dict["foley_cues"] = [c.model_dump() for c in all_foley]
        manifest_dict["music_cues"] = [c.model_dump() for c in all_music]

        if all_profiles:
            soundscape_manifest = SceneSoundscapeManifest(
                chapter_id=manifest.chapter_id,
                scenes=all_profiles,
            )
            manifest_dict["scene_acoustics"] = soundscape_manifest.model_dump()

            # Ensure backward-compatible ambience_scenes if empty
            if not manifest.ambience_scenes:
                legacy_ambience = []
                for p_idx, prof in enumerate(all_profiles):
                    p_path = prof.layers[0].asset_path if prof.layers else "room_tone"
                    p_lufs = prof.layers[0].target_lufs if prof.layers else -32.0
                    legacy_ambience.append(
                        AmbienceScene(
                            scene_id=p_idx + 1,
                            start_ms=prof.start_ms,
                            end_ms=prof.end_ms,
                            asset_name=Path(p_path).stem if p_path else "room_tone",
                            asset_path=p_path,
                            target_lufs=p_lufs,
                            reverb_preset=prof.ir_preset,
                        ).model_dump()
                    )
                manifest_dict["ambience_scenes"] = legacy_ambience

        if "metadata" not in manifest_dict or manifest_dict["metadata"] is None:
            manifest_dict["metadata"] = {}
        manifest_dict["metadata"]["sound_design_blueprints"] = len(blueprints)
        manifest_dict["metadata"]["sound_design_timeline_events"] = sum(len(t.events) for t in timelines)
        if silence_records:
            manifest_dict["metadata"]["silence_events"] = silence_records

        # Ensure silence percentage compliance
        if manifest.total_duration_ms and manifest.total_duration_ms > 0:
            tot_music_ms = sum(c.duration_ms for c in all_music)
            c_silence = max(0.0, 100.0 * (1.0 - (tot_music_ms / manifest.total_duration_ms)))
            if c_silence >= 60.0:
                manifest_dict["silence_percentage"] = round(c_silence, 2)

        return CreativeManifest.model_validate(manifest_dict)


_GLOBAL_ADAPTER: Optional[SoundDesignAdapter] = None

def get_sound_design_adapter() -> SoundDesignAdapter:
    """Returns singleton instance of SoundDesignAdapter."""
    global _GLOBAL_ADAPTER
    if _GLOBAL_ADAPTER is None:
        _GLOBAL_ADAPTER = SoundDesignAdapter()
    return _GLOBAL_ADAPTER
