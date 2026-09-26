#!/usr/bin/env python3
"""
Audiobook Factory - Capabilities 04 & 05: Ambience Engine & Evolution Continuity.
================================================================================
Implements layered environmental soundscapes across 5 decoupled tiers:
- BASE: Bedrock room tone
- MIDGROUND: Environmental motion (wind, fire, water)
- FOREGROUND: Spot transients (creaks, ember pops)
- DISTANT: Horizon elements (distant thunder, bells, carriage)
- MICRO_TEXTURE: Room density and warmth

Evolution & Continuity:
- Tracks persistent soundscape state across scene boundaries.
- Avoids restarting ambient loops when consecutive scenes share the same setting.
- Transforms layer density smoothly based on dramatic tension.
- Compatible with SceneSoundscapeManifest and AmbienceScene.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.sound_design.contracts import (
    AmbienceLayerSpec,
    AmbienceEvolutionState,
    AmbienceTier,
    RelativeIntensity,
    MixIntent,
    SpatialMetadata,
)
from audiobook_factory.sound_design.environment_profiles import get_environment_registry
from audiobook_factory.sound_design.asset_retriever import get_asset_retriever
from audiobook_factory.scene_acoustics import SceneAcousticProfile, AmbienceLayer, SceneSoundscapeManifest


class AmbienceEngine:
    """
    Stateful Layered Ambience & Soundscape Evolution Engine.
    """

    def __init__(self, asset_retriever=None):
        self.registry = get_environment_registry()
        self.retriever = asset_retriever or get_asset_retriever()
        self._state_tracker: Dict[str, AmbienceEvolutionState] = {}

    def reset(self) -> None:
        """Clears persistent chapter evolution state tracker."""
        self._state_tracker.clear()

    def build_scene_ambience(
        self,
        scene_id: str,
        chapter_id: str,
        environment_id: str,
        start_ms: int,
        end_ms: int,
        tension_level: float = 0.5,
        mood: str = "calm",
        previous_scene_id: Optional[str] = None,
    ) -> List[AmbienceLayerSpec]:
        """
        Builds the layered ambience specifications for a scene, maintaining
        cross-scene continuity if continuing in the same environment.
        """
        env_profile = self.registry.get_profile(environment_id) or self.registry.get_profile("castle_stone_corridor")
        prev_state = self._state_tracker.get(chapter_id)
        is_continuous = (
            prev_state is not None
            and prev_state.active_environment_id == env_profile.env_id
            and previous_scene_id == prev_state.last_scene_id
        )

        # Determine narrative phase from tension and mood
        phase: str = "CALM"
        if tension_level > 0.85 or mood.lower() in ("terror", "cataclysm", "battle"):
            phase = "EVENT" if tension_level > 0.9 else "THREAT"
        elif tension_level > 0.65 or mood.lower() in ("tense", "dread", "suspense"):
            phase = "TENSION"
        elif tension_level > 0.40 or mood.lower() in ("unease", "anxious", "mysterious"):
            phase = "UNEASE"
        elif mood.lower() in ("aftermath", "somber_calm", "grief"):
            phase = "AFTERMATH"
        elif mood.lower() in ("recovery", "relief"):
            phase = "RECOVERY"

        layers: List[AmbienceLayerSpec] = []

        # 1. BASE Tier: Continuous Bedrock Room Tone
        base_asset = None
        base_desc = None
        if is_continuous and prev_state and prev_state.active_layers:
            base_layers = [l for l in prev_state.active_layers if l.layer_tier == "BASE"]
            if base_layers:
                base_asset = base_layers[0].asset_path

        if not base_asset:
            base_desc = self.retriever.resolve_ambience_asset(env_profile.env_id, tier="BASE")
            if not base_desc and env_profile.typical_ambience_layers:
                base_desc = self.retriever.resolve_ambience_asset(env_profile.typical_ambience_layers[0], tier="BASE")
            base_asset = base_desc.filepath if base_desc else ""

        # Modulate BASE by phase
        base_intensity: RelativeIntensity = "whisper_quiet" if phase in ("THREAT", "EVENT") else "subtle_bed"
        layers.append(
            AmbienceLayerSpec(
                layer_tier="BASE",
                asset_id=base_desc.asset_id if base_desc else env_profile.env_id,
                asset_name=Path(base_asset).name if base_asset else env_profile.display_name,
                asset_path=base_asset,
                relative_intensity=base_intensity,
                loop=True,
                stereo_width=1.35 if phase != "THREAT" else 1.0,
                transition_behavior="crossfade",
                mix_intent=MixIntent(duck_under_dialogue=False, swell_in_dialogue_pauses=True),
            )
        )

        # 2. MIDGROUND Tier: Weather / Active Environmental Elements (Wind, Hearth, Rain)
        mid_desc = None
        mid_target = None
        if len(env_profile.typical_ambience_layers) > 1:
            mid_target = env_profile.typical_ambience_layers[1]
        elif env_profile.typical_weather:
            mid_target = env_profile.typical_weather

        if mid_target:
            mid_desc = self.retriever.resolve_ambience_asset(mid_target, tier="MIDGROUND")
            mid_path = mid_desc.filepath if mid_desc else ""
            if mid_path:
                mid_intensity: RelativeIntensity = (
                    "prominent" if phase in ("TENSION", "EVENT") else ("whisper_quiet" if phase == "THREAT" else "subtle_bed")
                )
                layers.append(
                    AmbienceLayerSpec(
                        layer_tier="MIDGROUND",
                        asset_id=mid_desc.asset_id if mid_desc else mid_target,
                        asset_name=Path(mid_path).name,
                        asset_path=mid_path,
                        relative_intensity=mid_intensity,
                        loop=True,
                        stereo_width=1.40,
                        mix_intent=MixIntent(duck_under_dialogue=True, swell_in_dialogue_pauses=True),
                    )
                )

        # 3. FOREGROUND Tier: Stochastic Spot Transients (Creaks, Drops, Rustles)
        # Suppressed during THREAT (unnatural silence) and EVENT (action takeover)
        if phase not in ("THREAT", "EVENT"):
            stoch_interval = 20.0 if phase == "TENSION" else (30.0 if phase == "UNEASE" else 45.0)
            fore_query = "wood_creak"
            if env_profile.category == "outdoor_nature":
                fore_query = "twig_snap"
            elif "crypt" in env_profile.env_id or "cave" in env_profile.env_id:
                fore_query = "water_drip"
            elif env_profile.category == "settlement":
                fore_query = "candle_pop"

            fore_desc = self.retriever.resolve_ambience_asset(fore_query, tier="FOREGROUND")
            fore_path = fore_desc.filepath if fore_desc else ""
            if fore_path:
                layers.append(
                    AmbienceLayerSpec(
                        layer_tier="FOREGROUND",
                        asset_id=fore_desc.asset_id if fore_desc else fore_query,
                        asset_name=Path(fore_path).name,
                        asset_path=fore_path,
                        relative_intensity="subtle_bed",
                        loop=False,
                        stochastic_interval_sec=stoch_interval,
                        mix_intent=MixIntent(duck_under_dialogue=True),
                    )
                )

        # 4. DISTANT Tier: Horizon Acoustic Elements (Far thunder, bells, carriage, wolf howl)
        if env_profile.distant_sounds and phase in ("UNEASE", "TENSION", "CALM"):
            dist_slug = env_profile.distant_sounds[0]
            dist_desc = self.retriever.resolve_ambience_asset(dist_slug, tier="DISTANT")
            dist_path = dist_desc.filepath if dist_desc else ""
            if dist_path:
                layers.append(
                    AmbienceLayerSpec(
                        layer_tier="DISTANT",
                        asset_id=dist_desc.asset_id if dist_desc else dist_slug,
                        asset_name=Path(dist_path).name,
                        asset_path=dist_path,
                        relative_intensity="whisper_quiet",
                        loop=False,
                        spatial=SpatialMetadata(azimuth_pan=-0.6, proximity="distant"),
                        mix_intent=MixIntent(duck_under_dialogue=True),
                    )
                )

        # 5. MICRO_TEXTURE Tier: Intimate Room Air, Warmth, or Settling Dust
        # Active in CALM, AFTERMATH, and RECOVERY; suppressed during intense conflict
        if phase in ("CALM", "AFTERMATH", "RECOVERY", "UNEASE"):
            micro_desc = self.retriever.resolve_ambience_asset(f"{env_profile.env_id}_micro", tier="MICRO_TEXTURE")
            if not micro_desc:
                micro_desc = self.retriever.resolve_ambience_asset("room_tone", tier="MICRO_TEXTURE")
            micro_path = micro_desc.filepath if micro_desc else ""
            if micro_path and micro_path != base_asset:
                layers.append(
                    AmbienceLayerSpec(
                        layer_tier="MICRO_TEXTURE",
                        asset_id=micro_desc.asset_id if micro_desc else "micro_tone",
                        asset_name=Path(micro_path).name,
                        asset_path=micro_path,
                        relative_intensity="whisper_quiet",
                        loop=True,
                        stereo_width=1.10,
                        spatial=SpatialMetadata(azimuth_pan=0.0, proximity="intimate"),
                        mix_intent=MixIntent(duck_under_dialogue=False, swell_in_dialogue_pauses=False),
                    )
                )

        # Update persistent chapter evolution state
        self._state_tracker[chapter_id] = AmbienceEvolutionState(
            active_environment_id=env_profile.env_id,
            dramatic_mood=mood,
            tension_level=tension_level,
            active_layers=layers,
            accumulated_duration_ms=max(0, end_ms - start_ms),
            last_scene_id=scene_id,
        )

        return layers

    def to_scene_acoustic_profile(
        self,
        scene_id: str,
        start_ms: int,
        end_ms: int,
        environment_id: str,
        layers: List[AmbienceLayerSpec],
        act_index: int = 1,
    ) -> SceneAcousticProfile:
        """
        Converts sound design AmbienceLayerSpec collection into standard
        SceneAcousticProfile (audiobook_factory.scene_acoustics) for 100% downstream compatibility.
        """
        env_profile = self.registry.get_profile(environment_id) or self.registry.get_profile("castle_stone_corridor")
        legacy_layers: List[AmbienceLayer] = []

        # Map up to 4 stems to comply with cinema stem engine constraints
        for idx, l in enumerate(layers[:4]):
            legacy_type = "base_room_tone"
            if l.layer_tier == "MIDGROUND":
                legacy_type = "weather_elements"
            elif l.layer_tier == "FOREGROUND":
                legacy_type = "spot_stochastic"
            elif l.layer_tier == "DISTANT":
                legacy_type = "spot_stochastic"

            # Derive relative LUFS calibration for legacy downstream renderers
            lufs = -34.0
            if l.relative_intensity == "whisper_quiet":
                lufs = -40.0
            elif l.relative_intensity == "prominent":
                lufs = -28.0

            legacy_layers.append(
                AmbienceLayer(
                    layer_type=legacy_type,  # type: ignore
                    asset_path=l.asset_path or "room_tone",
                    target_lufs=lufs,
                    stereo_width=l.stereo_width,
                    loop=l.loop,
                    stochastic_interval_sec=l.stochastic_interval_sec,
                )
            )

        return SceneAcousticProfile(
            scene_id=scene_id,
            act_index=act_index,
            start_ms=start_ms,
            end_ms=end_ms,
            environment_id=environment_id,
            ir_preset="hall" if env_profile.estimated_rt60_ms > 1800 else "room",
            layers=legacy_layers,
            occlusion_cutoff_hz=env_profile.occlusion_barrier_hz,
        )


_GLOBAL_AMBIENCE_ENGINE: Optional[AmbienceEngine] = None

def get_ambience_engine() -> AmbienceEngine:
    """Returns singleton instance of AmbienceEngine."""
    global _GLOBAL_AMBIENCE_ENGINE
    if _GLOBAL_AMBIENCE_ENGINE is None:
        _GLOBAL_AMBIENCE_ENGINE = AmbienceEngine()
    return _GLOBAL_AMBIENCE_ENGINE
