from __future__ import annotations
import os
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.logger import logger
from audiobook_factory.contracts import AmbienceScene
from audiobook_factory.scene_acoustics import SceneSoundscapeManifest, SceneAcousticProfile, AmbienceLayer

class SceneAcousticsMixin:
    def _partition_script_ambience_scenes(
        self,
        script_segments: Optional[List[Dict[str, Any]]],
        seg_starts_ms: Optional[Dict[int, int]],
        segment_durations_sec: Optional[Dict[int, float]],
        total_duration_ms: int,
    ) -> List[Tuple[str, int, int]]:
        """Partitions chapter segments into dynamic scene acoustic blocks based on acoustic_env shifts."""
        if not script_segments or not seg_starts_ms:
            return []

        blocks: List[Tuple[str, int, int]] = []
        cur_env: Optional[str] = None
        cur_start = 0
        cur_end = 0

        for seg in script_segments:
            s_idx = seg.get("index", 1)
            raw_env = (seg.get("acoustic_env") or "").strip()
            if not raw_env or raw_env.lower() in ("default", "none"):
                raw_env = "room_tone"
            s_start = seg_starts_ms.get(s_idx, 0)
            dur_ms = int((segment_durations_sec.get(s_idx, 4.0) if segment_durations_sec else 4.0) * 1000)
            s_end = s_start + dur_ms

            if cur_env is None:
                cur_env = raw_env
                cur_start = s_start
                cur_end = s_end
            elif raw_env == cur_env:
                cur_end = max(cur_end, s_end)
            else:
                blocks.append((cur_env, cur_start, cur_end))
                cur_env = raw_env
                cur_start = s_start
                cur_end = s_end

        if cur_env is not None:
            blocks.append((cur_env, cur_start, max(cur_end, total_duration_ms)))

        # Clean block boundaries so there are no negative durations and contiguous coverage
        cleaned: List[Tuple[str, int, int]] = []
        for i, (env, s, e) in enumerate(blocks):
            if i < len(blocks) - 1:
                next_s = blocks[i+1][1]
                e = max(s + 500, next_s)
            else:
                e = max(s + 500, total_duration_ms)
            cleaned.append((env, s, e))
        return cleaned

    def _resolve_ambience_scenes(
        self,
        amb_plan: List[Dict[str, Any]],
        total_duration_ms: int,
        script_segments: Optional[List[Dict[str, Any]]] = None,
        seg_starts_ms: Optional[Dict[int, int]] = None,
        segment_durations_sec: Optional[Dict[int, float]] = None,
    ) -> List[AmbienceScene]:
        """Resolves environmental room tone / ambience scenes for continuous backdrop."""
        # 1. Dynamic scene partitioning based on script segment acoustic environments
        blocks = self._partition_script_ambience_scenes(
            script_segments=script_segments,
            seg_starts_ms=seg_starts_ms,
            segment_durations_sec=segment_durations_sec,
            total_duration_ms=total_duration_ms,
        )

        scenes: List[AmbienceScene] = []

        if len(blocks) > 1:
            for idx, (env_name, b_start, b_end) in enumerate(blocks):
                amb_path = (
                    self.sound_bank.resolve_sound(f"{env_name}.ogg", category="AMB") or
                    self.sound_bank.resolve_sound(f"{env_name}.wav", category="AMB") or
                    self.sound_bank.resolve_sound(env_name, category="AMB") or
                    self.sound_bank.resolve_sound(env_name)
                )
                if not amb_path:
                    results = (
                        self.sound_bank.search(env_name.replace("_", " "), category="ambience", limit=1) or
                        self.sound_bank.search("room_tone", category="ambience", limit=1)
                    )
                    if results:
                        amb_path = Path(results[0]["filepath"])

                if amb_path and amb_path.exists():
                    scenes.append(
                        AmbienceScene(
                            scene_id=idx + 1,
                            start_ms=b_start,
                            end_ms=b_end,
                            asset_name=amb_path.name,
                            asset_path=str(amb_path.resolve()).replace("\\", "/"),
                            target_lufs=-32.0,
                        )
                    )
            if scenes:
                return scenes

        # 2. Plan-based / single-scene fallback
        for idx, amb in enumerate(amb_plan):
            amb_name = amb.get("name", "room_tone")
            amb_path = (
                self.sound_bank.resolve_sound(f"{amb_name}.ogg", category="AMB") or
                self.sound_bank.resolve_sound(amb_name, category="AMB") or
                self.sound_bank.resolve_sound(amb_name)
            )
            if not amb_path:
                results = (
                    self.sound_bank.search(amb_name, category="ambience", limit=1) or
                    self.sound_bank.search("room_tone", category="ambience", limit=1)
                )
                if results:
                    amb_path = Path(results[0]["filepath"])
            if amb_path and amb_path.exists():
                scenes.append(
                    AmbienceScene(
                        scene_id=idx + 1,
                        start_ms=0,
                        end_ms=total_duration_ms,
                        asset_name=amb_path.name,
                        asset_path=str(amb_path.resolve()).replace("\\", "/"),
                        target_lufs=float(amb.get("target_lufs", -32.0)),
                    )
                )

        if not scenes:
            dyn_results = (
                self.sound_bank.search("room_tone", category="ambience", limit=1) or
                self.sound_bank.search("ambience", category="ambience", limit=1)
            )
            if dyn_results:
                def_path = Path(dyn_results[0]["filepath"])
                if def_path.exists():
                    scenes.append(
                        AmbienceScene(
                            scene_id=1,
                            start_ms=0,
                            end_ms=total_duration_ms,
                            asset_name=def_path.name,
                            asset_path=str(def_path.resolve()).replace("\\", "/"),
                            target_lufs=-32.0,
                        )
                    )

        return scenes

    def _resolve_scene_acoustics(
        self,
        chapter_id: str,
        dramaturgy_plan: Dict[str, Any],
        total_duration_ms: int,
        sonic_bible: Optional[Any] = None,
        script_segments: Optional[List[Dict[str, Any]]] = None,
        seg_starts_ms: Optional[Dict[int, int]] = None,
        segment_durations_sec: Optional[Dict[int, float]] = None,
    ) -> Any:
        """
        Pillar 4 / Idea 1 & 2: Resolves rich 4-stem decoupled scene acoustics manifest.
        Creates scene profiles with Base Room Tone, Weather Elements, Crowd Wallah, and Stochastic Spots.
        """
        from audiobook_factory.scene_acoustics import SceneSoundscapeManifest, SceneAcousticProfile, AmbienceLayer

        scene_manifest = SceneSoundscapeManifest(chapter_id=chapter_id)

        # Check if plan already has explicit scene profiles
        raw_scenes = dramaturgy_plan.get("scene_acoustics") or dramaturgy_plan.get("scenes")
        if raw_scenes and isinstance(raw_scenes, list):
            for sc_data in raw_scenes:
                try:
                    profile = SceneAcousticProfile.model_validate(sc_data)
                    scene_manifest.add_scene(profile)
                except Exception as e:
                    logger.debug(f"Could not parse custom scene profile: {e}")

        # Check if script segments delineate multiple acoustic scenes
        blocks = self._partition_script_ambience_scenes(
            script_segments=script_segments,
            seg_starts_ms=seg_starts_ms,
            segment_durations_sec=segment_durations_sec,
            total_duration_ms=total_duration_ms,
        )

        theme_str = str(dramaturgy_plan.get("dramatic_theme", "")).lower()

        from audiobook_factory.sound_design.environment_profiles import get_environment_registry
        env_reg = get_environment_registry()

        if not scene_manifest.scenes and len(blocks) > 1:
            for idx, (env_name, b_start, b_end) in enumerate(blocks):
                layers: List[AmbienceLayer] = []
                comb_str = f"{env_name} {theme_str}".lower()
                env_prof = env_reg.get_profile(env_name) or env_reg.resolve_from_text(comb_str)

                # 1. Base Room Tone from canonical profile
                base_asset_name = env_prof.typical_ambience_layers[0] if env_prof.typical_ambience_layers else env_name
                base_res = (
                    self.sound_bank.resolve_sound(base_asset_name, category="AMB") or
                    self.sound_bank.resolve_sound(f"{env_name}.ogg", category="AMB") or
                    self.sound_bank.resolve_sound(f"{env_name}.wav", category="AMB") or
                    self.sound_bank.resolve_sound(env_name, category="AMB") or
                    self.sound_bank.resolve_sound("room_tone", category="AMB") or
                    self.sound_bank.resolve_sound("amb_castle_hall_hearth.wav", category="AMB")
                )
                base_path = base_res.name if base_res else base_asset_name
                layers.append(
                    AmbienceLayer(
                        layer_type="base_room_tone",
                        asset_path=base_path,
                        target_lufs=-34.0,
                        stereo_width=1.35,
                        loop=True,
                    )
                )

                # 2. Weather Elements
                weather_path = None
                if len(env_prof.typical_ambience_layers) > 1:
                    w_cand = env_prof.typical_ambience_layers[1]
                    w_res = self.sound_bank.resolve_sound(w_cand, category="AMB") or self.sound_bank.resolve_sound(w_cand)
                    if w_res:
                        weather_path = w_res.name
                if not weather_path:
                    if "rain" in comb_str or "storm" in comb_str:
                        weather_path = "rain_thunder.ogg"
                    elif any(k in comb_str for k in ("wind", "snow", "blizzard", "mountain")):
                        weather_path = "amb_blizzard_mountain_gale.wav"
                    elif any(k in comb_str for k in ("swamp", "bog")):
                        weather_path = "amb_bog_swamp_night.wav"
                    elif any(k in comb_str for k in ("crypt", "tomb")):
                        weather_path = "amb_crypt_tomb_drips.wav"

                if weather_path:
                    layers.append(
                        AmbienceLayer(
                            layer_type="weather_elements",
                            asset_path=weather_path,
                            target_lufs=-32.0,
                            stereo_width=1.40,
                            loop=True,
                        )
                    )

                # 3. Crowd Walla
                if env_prof.typical_walla or any(k in comb_str for k in ("tavern", "crowd", "brawl", "hall", "market", "whisper", "people", "street", "office")):
                    if any(k in comb_str for k in ("tavern", "inn", "pub", "brawl", "tankard")):
                        w_asset = "tavern_crowd_murmur.ogg"
                    elif any(k in comb_str for k in ("market", "bazaar", "square")):
                        w_asset = "market_bustle.ogg"
                    elif any(k in comb_str for k in ("whisper", "office", "court", "secret")):
                        w_asset = "07039098.mp3"  # Crowd Whispering / Muffled murmur
                    else:
                        w_asset = env_prof.typical_walla or "tavern_crowd_murmur.ogg"

                    w_res = self.sound_bank.resolve_sound(w_asset, category="AMB") or self.sound_bank.resolve_sound(w_asset)
                    layers.append(
                        AmbienceLayer(
                            layer_type="crowd_wallah",
                            asset_path=w_res.name if w_res else w_asset,
                            target_lufs=-30.0,
                            stereo_width=1.30,
                            loop=True,
                        )
                    )

                # 4. Spot Stochastic (Gentle occasional atmospheric transients)
                stoch_asset = "dry_grass_fireplace_raw.ogg"
                if env_prof.typical_foley:
                    for tf in env_prof.typical_foley:
                        tf_res = self.sound_bank.resolve_sound(tf, category="FX") or self.sound_bank.resolve_sound(tf)
                        if tf_res and not any(b in tf_res.name.lower() for b in ("jump", "boot", "sword", "blade")):
                            stoch_asset = tf_res.name
                            break
                if any(k in comb_str for k in ("crickets", "suburban_night", "owl")):
                    stoch_asset = "07042032.mp3"  # Tawny Owl with crickets
                elif any(k in comb_str for k in ("water", "dungeon", "crypt")):
                    stoch_asset = "tiny_water-drop-01.wav"

                layers.append(
                    AmbienceLayer(
                        layer_type="spot_stochastic",
                        asset_path=stoch_asset,
                        target_lufs=-26.0,
                        stochastic_interval_sec=120.0,
                        loop=False,
                    )
                )

                occ_cutoff = env_prof.occlusion_barrier_hz
                ir_preset = "hall" if env_prof.estimated_rt60_ms > 1800 else "room"
                scene_manifest.add_scene(
                    SceneAcousticProfile(
                        scene_id=f"sc_{idx+1:03d}_{chapter_id}",
                        act_index=idx + 1,
                        start_ms=b_start,
                        end_ms=b_end,
                        ir_preset=ir_preset,
                        layers=layers,
                        occlusion_cutoff_hz=occ_cutoff,
                    )
                )

        if not scene_manifest.scenes:
            amb_list = dramaturgy_plan.get("ambience", [])
            primary_name = amb_list[0].get("name", "room_tone") if amb_list else "room_tone"
            env_prof = env_reg.get_profile(primary_name) or env_reg.resolve_from_text(f"{primary_name} {theme_str}")
            layers = []

            base_asset_name = env_prof.typical_ambience_layers[0] if env_prof.typical_ambience_layers else primary_name
            base_res = (
                self.sound_bank.resolve_sound(base_asset_name, category="AMB") or
                self.sound_bank.resolve_sound(f"{primary_name}.ogg", category="AMB") or
                self.sound_bank.resolve_sound(primary_name, category="AMB") or
                self.sound_bank.resolve_sound("room_tone", category="AMB") or
                self.sound_bank.resolve_sound("amb_castle_hall_hearth.wav", category="AMB")
            )
            base_path = base_res.name if base_res else base_asset_name
            layers.append(
                AmbienceLayer(
                    layer_type="base_room_tone",
                    asset_path=base_path,
                    target_lufs=-34.0,
                    stereo_width=1.35,
                    loop=True,
                )
            )

            weather_path = None
            if len(env_prof.typical_ambience_layers) > 1:
                w_cand = env_prof.typical_ambience_layers[1]
                w_res = self.sound_bank.resolve_sound(w_cand, category="AMB") or self.sound_bank.resolve_sound(w_cand)
                if w_res:
                    weather_path = w_res.name
            if not weather_path:
                if "rain" in theme_str or "storm" in theme_str:
                    weather_path = "rain_thunder.ogg"
                elif any(k in theme_str for k in ("wind", "snow", "blizzard", "mountain")):
                    weather_path = "amb_blizzard_mountain_gale.wav"
                elif "swamp" in theme_str or "bog" in theme_str:
                    weather_path = "amb_bog_swamp_night.wav"
                elif "crypt" in theme_str or "tomb" in theme_str:
                    weather_path = "amb_crypt_tomb_drips.wav"

            if weather_path:
                layers.append(
                    AmbienceLayer(
                        layer_type="weather_elements",
                        asset_path=weather_path,
                        target_lufs=-32.0,
                        stereo_width=1.40,
                        loop=True,
                    )
                )

            if env_prof.typical_walla or any(k in theme_str for k in ("tavern", "crowd", "brawl", "hall")):
                w_asset = env_prof.typical_walla or "tavern_crowd_murmur.ogg"
                w_res = self.sound_bank.resolve_sound(w_asset, category="AMB") or self.sound_bank.resolve_sound(w_asset)
                layers.append(
                    AmbienceLayer(
                        layer_type="crowd_wallah",
                        asset_path=w_res.name if w_res else "tavern_crowd_murmur.ogg",
                        target_lufs=-30.0,
                        stereo_width=1.30,
                        loop=True,
                    )
                )

            stoch_asset = "tiny_floor-creak-01.wav"
            if env_prof.typical_foley:
                for tf in env_prof.typical_foley:
                    tf_res = self.sound_bank.resolve_sound(tf, category="FX") or self.sound_bank.resolve_sound(tf)
                    if tf_res:
                        stoch_asset = tf_res.name
                        break
            if stoch_asset == "tiny_floor-creak-01.wav":
                if "fire" in theme_str or "torch" in theme_str or "hearth" in theme_str:
                    stoch_asset = "dry_grass_fireplace_raw.ogg"
                elif "water" in theme_str or "dungeon" in theme_str:
                    stoch_asset = "tiny_water-drop-01.wav"

            layers.append(
                AmbienceLayer(
                    layer_type="spot_stochastic",
                    asset_path=stoch_asset,
                    target_lufs=-24.0,
                    stochastic_interval_sec=35.0,
                    loop=False,
                )
            )

            occ_cutoff = env_prof.occlusion_barrier_hz
            ir_preset = "hall" if env_prof.estimated_rt60_ms > 1800 else "room"

            scene_manifest.add_scene(
                SceneAcousticProfile(
                    scene_id=f"sc_001_{chapter_id}",
                    act_index=1,
                    start_ms=0,
                    end_ms=max(1000, total_duration_ms),
                    ir_preset=ir_preset,
                    layers=layers,
                    occlusion_cutoff_hz=occ_cutoff,
                )
            )

        return scene_manifest

