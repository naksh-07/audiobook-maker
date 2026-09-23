#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 4: 4-Stem Decoupled Scene Soundscapes & Occlusion Curves (Pydantic v2).
"New Room 2": Manages rich multi-layered environmental soundscapes, continuous scene atmospheres,
spatial occlusion, and smooth acoustic crossfades.
Persisted as dedicated `chapter_XXX_scene_acoustics.json`.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal, Union

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

logger = logging.getLogger("audiobook_factory.scene_acoustics")


class AmbienceLayer(BaseModel):
    """
    Individual stem within a 4-tier decoupled scene soundscape.
    Separates constant room tone, weather elements, human wallah, and spot transients.
    """
    model_config = ConfigDict(extra="ignore")

    layer_type: Literal["base_room_tone", "weather_elements", "crowd_wallah", "spot_stochastic"] = Field(
        ..., description="Acoustic role of this ambient layer"
    )
    asset_path: str = Field(..., description="Audio file name or relative/absolute path in sound bank")
    target_lufs: float = Field(default=-32.0, ge=-60.0, le=-15.0, description="Calibrated ambient loudness target in LUFS")
    stereo_width: float = Field(default=1.0, ge=0.0, le=2.0, description="Stereo spread factor (1.0 = native stereo)")
    azimuth_pan: float = Field(default=0.0, ge=-1.0, le=1.0, description="Spatial pan coordinate (-1.0 = left, +1.0 = right)")
    high_pass_hz: Optional[int] = Field(default=None, ge=20, le=500, description="Low-cut rumble filter frequency in Hz")
    low_pass_hz: Optional[int] = Field(default=None, ge=1000, le=20000, description="High-cut acoustic damping / distance frequency in Hz")
    loop: bool = Field(default=True, description="Whether to seamlessly loop the ambient asset across scene duration")
    stochastic_interval_sec: Optional[float] = Field(default=None, ge=1.0, le=120.0, description="Average period for spot triggers")


class SceneAcousticProfile(BaseModel):
    """
    Acoustic atmosphere for an entire dramatic scene region.
    Supports 4-stem soundscapes, transition crossfading, and wall/obstacle occlusion.
    """
    model_config = ConfigDict(extra="ignore")

    scene_id: str = Field(..., description="Unique scene identifier (e.g. 'sc_001_tavern_interior')")
    act_index: int = Field(default=1, ge=1, le=10, description="Dramatic act grouping")
    start_ms: int = Field(default=0, ge=0, description="Scene start on chapter timeline in milliseconds")
    end_ms: int = Field(default=0, ge=0, description="Scene end on chapter timeline in milliseconds")
    environment_id: str = Field(default="default", description="Reference to WorldAcousticProfile in SonicBible")
    ir_preset: str = Field(default="room", description="Reverberation impulse response preset")
    layers: List[AmbienceLayer] = Field(
        default_factory=list,
        description="Up to 4 decoupled ambient stems (base room, weather, crowd, stochastic)"
    )
    transition_in: Literal["cut", "crossfade", "fade_from_silence"] = Field(
        default="crossfade", description="Incoming transition style"
    )
    transition_out: Literal["cut", "crossfade", "fade_to_silence"] = Field(
        default="crossfade", description="Outgoing transition style"
    )
    crossfade_ms: int = Field(default=2500, ge=100, le=10000, description="Acoustic crossfade duration in milliseconds")
    occlusion_cutoff_hz: int = Field(
        default=18000, ge=300, le=20000,
        description="Low-pass barrier occlusion frequency (e.g. 1500Hz behind closed oak door)"
    )

    @model_validator(mode="after")
    def validate_scene_bounds(self) -> SceneAcousticProfile:
        if self.end_ms <= self.start_ms:
            raise ValueError(f"Scene '{self.scene_id}' end_ms ({self.end_ms}) must be > start_ms ({self.start_ms}).")
        if len(self.layers) > 4:
            raise ValueError(f"Scene '{self.scene_id}' has {len(self.layers)} layers. Cinema spec allows max 4 decoupled stems.")
        return self


class SceneSoundscapeManifest(BaseModel):
    """
    Chapter-Level Soundscape & Acoustic Profile Manifest.
    Dedicated room for all scene atmospheres and spatial transition curves for a chapter.
    Persisted to `chapter_XXX_scene_acoustics.json`.
    """
    model_config = ConfigDict(extra="ignore")

    schema_version: str = Field(default="2.0", description="Schema version")
    chapter_id: str = Field(..., description="Target chapter identifier (e.g. 'chapter_008')")
    scenes: List[SceneAcousticProfile] = Field(default_factory=list, description="Ordered sequence of scenes")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def add_scene(self, scene: SceneAcousticProfile) -> None:
        """Add a scene acoustic profile."""
        self.scenes.append(scene)

    def save_to_disk(self, target_path: Union[str, Path]) -> Path:
        """Saves SceneSoundscapeManifest to dedicated JSON file."""
        p = Path(target_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"[+] Saved Scene Acoustics to: {p}")
        return p

    @classmethod
    def load_from_disk(cls, target_path: Union[str, Path]) -> SceneSoundscapeManifest:
        """Loads SceneSoundscapeManifest from disk."""
        p = Path(target_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Scene soundscape file not found: {p}")
        content = p.read_text(encoding="utf-8")
        data = json.loads(content)
        return cls.model_validate(data)

    def audit_scene_acoustics_integrity(self, sound_bank: Optional[Any] = None) -> Dict[str, Any]:
        """
        Level 2 Guard: Act/Scene-Level Soundscape Integrity Guard.
        Validates:
        - Strict 4-layer stem bounds per scene.
        - Non-negative timestamps and strictly positive durations (`end_ms > start_ms`).
        - Continuous timeline order without reverse time warps.
        - Physical existence and resolution of every layer audio asset via SoundBank.
        """
        errors: List[str] = []
        warnings: List[str] = []
        total_layers_audited = 0
        prev_end_ms = 0

        if not self.scenes:
            errors.append(f"Chapter '{self.chapter_id}' has zero scene acoustic profiles defined.")

        for idx, sc in enumerate(self.scenes):
            if sc.start_ms < 0:
                errors.append(f"Scene '{sc.scene_id}' start_ms ({sc.start_ms}) cannot be negative.")
            if sc.end_ms <= sc.start_ms:
                errors.append(f"Scene '{sc.scene_id}' duration is non-positive ({sc.start_ms} to {sc.end_ms}).")
            if idx > 0 and sc.start_ms < self.scenes[idx - 1].start_ms:
                errors.append(f"Scene '{sc.scene_id}' start_ms ({sc.start_ms}) is backwards in time.")

            # Validate layers
            if len(sc.layers) > 4:
                errors.append(f"Scene '{sc.scene_id}' exceeds 4-stem limit ({len(sc.layers)} layers).")

            for l_idx, layer in enumerate(sc.layers):
                total_layers_audited += 1
                if not layer.asset_path.strip():
                    errors.append(f"Scene '{sc.scene_id}' layer {l_idx} ({layer.layer_type}) has empty asset_path.")
                elif sound_bank is not None:
                    # Check resolution
                    resolved = None
                    try:
                        resolved = sound_bank.resolve_sound(layer.asset_path, category="AMB") or sound_bank.resolve_sound(layer.asset_path)
                    except Exception:
                        pass
                    if not resolved or not resolved.exists():
                        warnings.append(
                            f"Scene '{sc.scene_id}' layer '{layer.layer_type}' asset '{layer.asset_path}' could not be resolved in SoundBank."
                        )

            prev_end_ms = max(prev_end_ms, sc.end_ms)

        passed = len(errors) == 0
        return {
            "guard": "Level 2 (Scene Acoustics Integrity Guard)",
            "status": "PASS" if passed else "FAIL",
            "passed": passed,
            "chapter_id": self.chapter_id,
            "total_scenes": len(self.scenes),
            "total_layers": total_layers_audited,
            "warnings": warnings,
            "errors": errors,
        }

    def generate_stochastic_cues(
        self,
        timeline_ledger: Optional[Any] = None,
        sound_bank: Optional[Any] = None,
        seed: int = 42,
    ) -> List[Any]:
        """
        Pillar 4 / Idea 2: Zero-Token Local Stochastic Transient Generator.
        Generates subtle non-repetitive Layer 4 spot cues (owls, floor creaks, candle crackle, clock ticks)
        bounded within each scene's start_ms and end_ms, prioritizing dialogue pauses to prevent vocal masking.
        """
        from audiobook_factory.contracts import FoleyCue
        from audiobook_factory.acoustic_bus_matrix import derive_ucs_category

        generated_cues: List[FoleyCue] = []
        cue_counter = 0

        for sc in self.scenes:
            spot_layers = [l for l in sc.layers if l.layer_type == "spot_stochastic"]
            if not spot_layers:
                continue

            scene_dur_sec = max(1.0, (sc.end_ms - sc.start_ms) / 1000.0)

            # Discover pause slots in this scene from timeline_ledger if available
            pause_slots: List[int] = []
            if timeline_ledger and hasattr(timeline_ledger, "segments"):
                segs = [s for s in timeline_ledger.segments if sc.start_ms <= s.start_ms < sc.end_ms]
                for i in range(len(segs) - 1):
                    gap = segs[i + 1].start_ms - segs[i].end_ms
                    if gap >= 600:
                        # Place spot transient 150ms into pause
                        pause_slots.append(segs[i].end_ms + 150)

            for layer in spot_layers:
                interval_sec = layer.stochastic_interval_sec or 30.0
                num_cues = max(1, int(scene_dur_sec / interval_sec))

                # Resolve candidate sound assets from sound bank
                candidates: List[Path] = []
                if sound_bank is not None:
                    res = sound_bank.resolve_sound(layer.asset_path, category="FOL") or sound_bank.resolve_sound(layer.asset_path)
                    if res and res.exists():
                        candidates.append(res)
                    else:
                        q = layer.asset_path.replace("_", " ").strip() or "wood creak"
                        search_res = sound_bank.search(q, category="foley", limit=6)
                        if not search_res:
                            search_res = sound_bank.search(q, limit=6)
                        for r in search_res:
                            fp = Path(r.get("filepath", ""))
                            if fp.exists() and fp not in candidates:
                                candidates.append(fp)

                asset_str = layer.asset_path
                asset_name = Path(layer.asset_path).name

                used_timestamps: List[int] = []
                if pause_slots:
                    stride = max(1, len(pause_slots) // num_cues)
                    for k in range(min(num_cues, len(pause_slots))):
                        used_timestamps.append(pause_slots[(k * stride) % len(pause_slots)])
                else:
                    scene_len = max(100, sc.end_ms - sc.start_ms)
                    step_ms = int(scene_len / (num_cues + 1))
                    margin_ms = min(500, max(50, int(scene_len * 0.05)))
                    max_jitter = max(20, min(300, step_ms // 3))

                    for k in range(num_cues):
                        jitter = int(((seed + k * 17) % 11 - 5) / 5.0 * max_jitter)
                        ts = sc.start_ms + step_ms * (k + 1) + jitter
                        # Safe clamping respecting scene duration
                        if sc.end_ms - sc.start_ms > 2 * margin_ms:
                            ts = max(sc.start_ms + margin_ms, min(sc.end_ms - margin_ms, ts))
                        else:
                            ts = sc.start_ms + int(scene_len / 2)
                        used_timestamps.append(ts)

                used_timestamps.sort()
                gain_target = layer.target_lufs if -40.0 <= layer.target_lufs <= -10.0 else -24.0

                for idx, t_ms in enumerate(used_timestamps):
                    cue_counter += 1
                    chosen_path = asset_str
                    chosen_name = asset_name
                    if candidates:
                        chosen_asset = candidates[(seed + idx + cue_counter) % len(candidates)]
                        chosen_path = str(chosen_asset.resolve()).replace("\\", "/")
                        chosen_name = chosen_asset.name

                    pan = layer.azimuth_pan
                    if pan == 0.0:
                        pan = 0.35 if (cue_counter % 2 == 0) else -0.35

                    ucs = derive_ucs_category(layer.asset_path, "spot")

                    cue = FoleyCue(
                        cue_id=f"stoch_{sc.scene_id}_{cue_counter:03d}",
                        segment_index=0,
                        anchor_word="[STOCHASTIC]",
                        pre_roll_ms=100,
                        asset_id=0,
                        asset_path=chosen_path,
                        asset_name=chosen_name,
                        gain_dbfs=gain_target,
                        azimuth_pan=pan,
                        reverb_send=0.20,
                        start_ms=t_ms,
                        duration_ms=0,
                        ucs_category=ucs,
                    )
                    generated_cues.append(cue)

        return generated_cues


def generate_stochastic_cues(
    manifest: SceneSoundscapeManifest,
    timeline_ledger: Optional[Any] = None,
    sound_bank: Optional[Any] = None,
    seed: int = 42,
) -> List[Any]:
    """Helper functional interface to generate stochastic spot foley cues from a SceneSoundscapeManifest."""
    return manifest.generate_stochastic_cues(timeline_ledger=timeline_ledger, sound_bank=sound_bank, seed=seed)

