#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 4: Next-Gen Cinema Audio Drama Engine (Pydantic v2).
"New Room 4": Manages discrete DME stem generation (DX, MX, FX, AMB, ME), true broadcast summing,
and export ledger compliance tracking.
Persists `chapter_XXX_cinema_manifest.json` and `chapter_XXX_stem_ledger.json`.
"""

from __future__ import annotations
import os
import re
import math
import json
import wave
import shutil
import logging
import datetime
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal, Union, Tuple

from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.contracts import (
    CreativeManifest,
    MusicCue,
    FoleyCue,
    AmbienceScene,
    ConvolutionIRConfig,
    WallahAutomationPoint,
)
from audiobook_factory.scene_acoustics import SceneSoundscapeManifest, SceneAcousticProfile
from audiobook_factory.acoustic_bus_matrix import (
    DuckingProfile,
    PROFILE_STANDARD,
    filter_concurrency_window,
    get_spectral_pocketing_filter,
)
from audiobook_factory.sound_bank import SoundBank, get_sound_bank
from audiobook_factory.manifest_renderer import render_music_bus, render_foley_bus
from audiobook_factory.cinematic_mix import (
    SceneMixIntent,
    AttentionMap,
    AttentionEvent,
    MixAutomation,
    AutomationPlanner,
    build_stem_filter_chain,
    apply_automation_to_stem,
    AcousticPerspective,
    PerspectiveDirector,
    SilenceEvent,
    SilenceDirector,
    ImpactEvent,
    ImpactDirector,
    MixJudge,
    MixJudgeResult,
    RemixController,
)
from audiobook_factory.mastering_contracts import MasteringRequest, MasteringProfile
from audiobook_factory.mastering_engine import MasteringEngineV2

logger = logging.getLogger("audiobook_factory.cinema_audio_engine")

ACOUSTIC_IR_PRESETS: Dict[str, Dict[str, Any]] = {
    "tavern_timber_small": {
        "delays": "18|36|54",
        "decays": "0.18|0.14|0.09",
        "hpf": 180,
        "lpf": 7500,
        "default_wet": 0.12,
    },
    "stone_crypt_damp": {
        "delays": "28|56|84",
        "decays": "0.22|0.16|0.11",
        "hpf": 160,
        "lpf": 6000,
        "default_wet": 0.15,
    },
    "great_hall_stone": {
        "delays": "35|70|105",
        "decays": "0.24|0.18|0.12",
        "hpf": 150,
        "lpf": 7000,
        "default_wet": 0.14,
    },
    "forest_open_mist": {
        "delays": "30|60",
        "decays": "0.08|0.04",
        "hpf": 200,
        "lpf": 5000,
        "default_wet": 0.06,
    },
    "domestic_room": {
        "delays": "14|28|42",
        "decays": "0.15|0.10|0.06",
        "hpf": 180,
        "lpf": 8000,
        "default_wet": 0.09,
    },
    "cave_catacomb": {
        "delays": "32|64|96",
        "decays": "0.25|0.19|0.14",
        "hpf": 140,
        "lpf": 5500,
        "default_wet": 0.15,
    },
}


def build_spatial_early_reflection_filter(staging_config: Any) -> str:
    """
    Constructs an FFmpeg filter_complex graph string for physical room convolution early reflections.
    Convolves room physical geometry onto DX vocal track to eliminate anechoic isolation booth dryness.
    """
    preset_name = getattr(staging_config, "preset_name", "tavern_timber_small") if staging_config else "tavern_timber_small"
    preset = ACOUSTIC_IR_PRESETS.get(preset_name, ACOUSTIC_IR_PRESETS["tavern_timber_small"])

    wet_ratio = getattr(staging_config, "wet_dry_ratio", None)
    if wet_ratio is None or wet_ratio <= 0.0:
        wet_ratio = preset["default_wet"]
    wet = max(0.04, min(0.22, float(wet_ratio)))
    dry = round(max(0.70, 1.0 - wet), 2)

    lpf = getattr(staging_config, "high_cut_hz", None) or preset["lpf"]
    hpf = preset.get("hpf", 180)
    delays = preset["delays"]
    decays = preset["decays"]

    return (
        f"[0:a]asplit=2[dry][wet_in];"
        f"[wet_in]aecho=0.8:0.88:{delays}:{decays},highpass=f={hpf},lowpass=f={lpf},volume={wet:.2f}[wet_refl];"
        f"[dry][wet_refl]amix=inputs=2:weights={dry:.2f} {wet:.2f},aresample=48000[dx_out]"
    )



class StemMetadata(BaseModel):
    """Acoustic and technical metadata for a discrete audio stem."""
    model_config = ConfigDict(extra="ignore")

    stem_type: Literal["DX", "MX", "FX", "AMB", "ME", "FULL_MASTER", "CINEMATIC_MIX_PREMASTER"]
    filepath: str
    duration_sec: float = 0.0
    integrated_lufs: float = -70.0
    true_peak_dbtp: float = -70.0
    sample_rate: int = 48000
    channels: int = 2
    status: str = "PASS"


class StemLedger(BaseModel):
    """
    Export ledger for discrete stems complying with Netflix / BBC cinema audio delivery specs.
    Persisted to `chapter_XXX_stem_ledger.json`.
    """
    model_config = ConfigDict(extra="ignore")

    chapter_id: str
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    stems: Dict[str, StemMetadata] = Field(default_factory=dict)
    master_lufs: float = -19.0
    master_peak: float = -1.5
    compliance_status: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def premaster(self) -> Optional[StemMetadata]:
        """Returns the Stage 11 cinematic mix premaster stem."""
        return self.stems.get("CINEMATIC_MIX_PREMASTER") or self.stems.get("FULL_MASTER")

    def save_to_disk(self, target_path: Union[str, Path]) -> Path:
        """Save stem ledger to disk."""
        p = Path(target_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"[+] Saved Stem Ledger to: {p}")
        return p

    @classmethod
    def load_from_disk(cls, target_path: Union[str, Path]) -> StemLedger:
        """Load stem ledger from disk."""
        p = Path(target_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Stem ledger not found: {p}")
        content = p.read_text(encoding="utf-8")
        return cls.model_validate(json.loads(content))


class CinemaAudioManifest(BaseModel):
    """
    Next-Gen Cinema Audio Drama Manifest Specification (Version 4.0).
    Decoupled modular architecture separating book sonic identity, 4-tier scene soundscapes,
    dynamic ducking profiles, and discrete stem routing.
    Persisted to `chapter_XXX_cinema_manifest.json`.
    """
    model_config = ConfigDict(extra="ignore")

    manifest_version: str = Field(default="4.0")
    chapter_id: str
    project_id: str = Field(default="")
    sonic_bible_ref: Optional[str] = Field(default=None, description="Path to `sound_bible.json`")
    scene_acoustics: Optional[SceneSoundscapeManifest] = Field(
        default=None, description="Detailed 4-stem scene atmospheres"
    )
    music_cues: List[MusicCue] = Field(default_factory=list)
    foley_cues: List[FoleyCue] = Field(default_factory=list)
    acoustic_staging: Dict[str, Any] = Field(default_factory=dict, description="Scene acoustic convolution staging configs")
    wallah_automations: List[Any] = Field(default_factory=list, description="Dynamic crowd breathing envelope points")
    ducking_policy: DuckingProfile = Field(default_factory=lambda: PROFILE_STANDARD)
    total_duration_sec: float = Field(default=0.0, ge=0.0)
    silence_percentage: float = Field(default=100.0, ge=0.0, le=100.0)
    scene_intent: Optional[SceneMixIntent] = Field(
        default=None, description="Stage 11 Scene Mix Intent"
    )
    attention_map: Optional[AttentionMap] = Field(
        default=None, description="Stage 11 Time-aware Listener Attention Map"
    )
    mix_automation: Optional[MixAutomation] = Field(
        default=None, description="Stage 11 Continuous Mix Automation Timeline"
    )
    acoustic_perspective: Optional[AcousticPerspective] = Field(
        default=None, description="Stage 11 Acoustic Perspective (distance & occlusion)"
    )
    silence_events: List[SilenceEvent] = Field(
        default_factory=list, description="Stage 11 Narrative Silence Events"
    )
    impact_events: List[ImpactEvent] = Field(
        default_factory=list, description="Stage 11 Cinematic Impact Events"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def save_to_disk(self, target_path: Union[str, Path]) -> Path:
        """Save CinemaAudioManifest to disk."""
        p = Path(target_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"[+] Saved Cinema Audio Manifest to: {p}")
        return p

    @classmethod
    def load_from_disk(cls, target_path: Union[str, Path]) -> CinemaAudioManifest:
        """Load CinemaAudioManifest from disk."""
        p = Path(target_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Cinema manifest not found: {p}")
        content = p.read_text(encoding="utf-8")
        return cls.model_validate(json.loads(content))


def measure_audio_metrics(audio_file: Path, ffmpeg: str = "ffmpeg") -> Dict[str, float]:
    """Measures EBU R128 Integrated Loudness and True Peak via FFmpeg."""
    p = Path(audio_file).resolve()
    if not p.exists() or p.stat().st_size < 1000:
        return {"integrated_lufs": -70.0, "true_peak_dbtp": -70.0, "duration_sec": 0.0}

    cmd = [
        ffmpeg, "-y",
        "-i", str(p),
        "-af", "ebur128=peak=true:framelog=verbose",
        "-f", "null", "-"
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600)
        output = proc.stderr
        import re
        i_match = re.search(r"Integrated loudness:\s+I:\s+([-\d.]+)\s+LUFS", output)
        tp_match = re.search(r"True peak:\s+Peak:\s+([-\d.]+)(?:\s+([-\d.]+))?", output) or re.search(r"Peak:\s+([-\d.]+)\s+dBFS", output)
        dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", output)

        dur_sec = 0.0
        if p.suffix.lower() == ".wav" and p.exists():
            try:
                with wave.open(str(p), "rb") as wf:
                    dur_sec = wf.getnframes() / float(wf.getframerate())
            except Exception:
                pass
        if dur_sec <= 0.0 and dur_match:
            h, m, s = dur_match.groups()
            dur_sec = int(h) * 3600 + int(m) * 60 + float(s)

        lufs = -24.0
        if i_match:
            try:
                lufs = float(i_match.group(1))
            except ValueError:
                lufs = -70.0

        peak = -1.5
        if tp_match:
            tp_vals = []
            for v in tp_match.groups():
                if v is not None:
                    try:
                        tp_vals.append(float(v))
                    except ValueError:
                        pass
            if tp_vals:
                peak = max(tp_vals)
        return {"integrated_lufs": round(lufs, 2), "true_peak_dbtp": round(peak, 2), "duration_sec": round(dur_sec, 2)}
    except Exception as e:
        logger.warning(f"Audio measurement failed for {p.name}: {e}")
        return {"integrated_lufs": -24.0, "true_peak_dbtp": -1.5, "duration_sec": 0.0}


def render_discrete_stems(
    manifest: Union[CinemaAudioManifest, CreativeManifest],
    dialogue_wav: Path,
    output_dir: Path,
    sound_bank: Optional[SoundBank] = None,
    ffmpeg: Optional[str] = None,
    enable_judge: bool = True,
    enable_remix: bool = False,
    max_remix_attempts: int = 2,
    judge: Optional[MixJudge] = None,
) -> StemLedger:
    """
    Renders discrete audio stems (DX, MX, FX, AMB, ME, FULL_MASTER)
    complying with cinema broadcast specifications.
    Generates `chapter_XXX_stem_ledger.json`.
    """
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    bank = sound_bank or get_sound_bank()
    ff = ffmpeg or shutil.which("ffmpeg") or "ffmpeg"
    d_path = Path(dialogue_wav).resolve()

    ch_id = manifest.chapter_id

    # Fail-Closed Audio Reality Pre-Flight Gate (Durations <= 3.5s, Anti-Repetition, Category Isolation)
    from audiobook_factory.audio_reality_auditor import AudioRealityAuditor
    auditor = AudioRealityAuditor(sound_bank=bank)
    manifest, reality_report = auditor.audit_and_remediate(
        manifest=manifest,
        output_dir=out_dir,
        era=(
            getattr(manifest, "era", None)
            or (getattr(manifest, "scene_intent", None) and getattr(manifest.scene_intent, "era", None))
            or (manifest.metadata.get("era") if hasattr(manifest, "metadata") and isinstance(manifest.metadata, dict) else None)
            or "UNIVERSAL_CONTEMPORARY"
        ),
        franchise_affinity=getattr(manifest, "franchise_affinity", None),
    )

    # 1. Probe dialogue duration
    d_metrics = measure_audio_metrics(d_path, ffmpeg=ff)
    total_dur = d_metrics.get("duration_sec", 0.0) or getattr(manifest, "total_duration_sec", 60.0) or 60.0

    stems_meta: Dict[str, StemMetadata] = {}

    # --- STEM 1: DX (Dialogue Stem) ---
    dx_file = (out_dir / f"{ch_id}_stem_DX.wav").resolve()

    # Check for acoustic staging convolution parameters
    acoustic_staging = getattr(manifest, "acoustic_staging", None)
    staging_cfg = None
    if isinstance(acoustic_staging, dict) and acoustic_staging:
        staging_cfg = next((c for c in acoustic_staging.values() if getattr(c, "enabled", True)), None)

    if d_path.exists():
        target_dest = dx_file
        temp_rendered = None
        if d_path == dx_file:
            temp_rendered = out_dir / f"{ch_id}_stem_DX_spatial.wav"
            target_dest = temp_rendered

        if staging_cfg is not None:
            sp_filter = build_spatial_early_reflection_filter(staging_cfg)
            cmd_dx = [
                ff, "-y",
                "-i", str(d_path),
                "-filter_complex", sp_filter,
                "-map", "[dx_out]",
                "-ac", "2",
                "-c:a", "pcm_s16le",
                str(target_dest),
            ]
            res_dx = subprocess.run(cmd_dx, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res_dx.returncode != 0 or not target_dest.exists():
                err_msg = res_dx.stderr.decode("utf-8", errors="ignore")[:200] if res_dx.stderr else "unknown error"
                logger.warning(f"Spatial DX reflection warning ({res_dx.returncode}): {err_msg}. Falling back to clean resample.")
                cmd_dx = [
                    ff, "-y",
                    "-i", str(d_path),
                    "-af", "aresample=48000",
                    "-ac", "2",
                    "-c:a", "pcm_s16le",
                    str(target_dest),
                ]
                subprocess.run(cmd_dx, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            if d_path != dx_file:
                cmd_dx = [
                    ff, "-y",
                    "-i", str(d_path),
                    "-af", "aresample=48000",
                    "-ac", "2",
                    "-c:a", "pcm_s16le",
                    str(target_dest),
                ]
                res_dx = subprocess.run(cmd_dx, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res_dx.returncode != 0 or not target_dest.exists():
                    shutil.copyfile(d_path, target_dest)

        if temp_rendered and temp_rendered.exists():
            shutil.move(str(temp_rendered), str(dx_file))
    else:
        # Generate clean silent fallback
        cmd_silence = [ff, "-y", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={total_dur:.2f}", "-c:a", "pcm_s16le", str(dx_file)]
        subprocess.run(cmd_silence, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    dx_m = measure_audio_metrics(dx_file, ffmpeg=ff)
    stems_meta["DX"] = StemMetadata(
        stem_type="DX",
        filepath=str(dx_file),
        duration_sec=dx_m["duration_sec"],
        integrated_lufs=dx_m["integrated_lufs"],
        true_peak_dbtp=dx_m["true_peak_dbtp"],
    )

    # --- STEM 2: MX (Music Stem) ---
    mx_file = out_dir / f"{ch_id}_stem_MX.wav"
    music_cues = list(manifest.music_cues)
    render_music_bus(
        music_cues=music_cues,
        total_duration_sec=total_dur,
        output_bus_file=mx_file,
        sound_bank=bank,
        ffmpeg=ff,
    )
    mx_m = measure_audio_metrics(mx_file, ffmpeg=ff)
    stems_meta["MX"] = StemMetadata(
        stem_type="MX",
        filepath=str(mx_file),
        duration_sec=mx_m["duration_sec"],
        integrated_lufs=mx_m["integrated_lufs"],
        true_peak_dbtp=mx_m["true_peak_dbtp"],
    )

    # --- STEM 3: FX (Foley & Transient Stem) ---
    fx_file = out_dir / f"{ch_id}_stem_FX.wav"
    raw_foley = list(manifest.foley_cues)
    scene_acoustics = getattr(manifest, "scene_acoustics", None)
    if isinstance(scene_acoustics, dict):
        try:
            from audiobook_factory.scene_acoustics import SceneSoundscapeManifest
            scene_acoustics = SceneSoundscapeManifest.model_validate(scene_acoustics)
        except Exception:
            pass

    # Idea 2 Integration: Merge procedural stochastic spot cues from scene acoustics into Foley bus (if not already added)
    has_stoch = any(getattr(c, "anchor_word", "") == "[STOCHASTIC]" for c in raw_foley)
    if not has_stoch and scene_acoustics and hasattr(scene_acoustics, "generate_stochastic_cues"):
        stoch_cues = scene_acoustics.generate_stochastic_cues(sound_bank=bank)
        if stoch_cues:
            existing_ids = {c.cue_id for c in raw_foley}
            for sc_cue in stoch_cues:
                if sc_cue.cue_id not in existing_ids:
                    raw_foley.append(sc_cue)

    # Apply Voice Limiter & Priority Stealing to prevent transient mud
    calibrated_foley = filter_concurrency_window(raw_foley, window_ms=200, max_concurrency=3)
    render_foley_bus(
        foley_cues=calibrated_foley,
        total_duration_sec=total_dur,
        output_bus_file=fx_file,
        sound_bank=bank,
        ffmpeg=ff,
    )
    fx_m = measure_audio_metrics(fx_file, ffmpeg=ff)
    stems_meta["FX"] = StemMetadata(
        stem_type="FX",
        filepath=str(fx_file),
        duration_sec=fx_m["duration_sec"],
        integrated_lufs=fx_m["integrated_lufs"],
        true_peak_dbtp=fx_m["true_peak_dbtp"],
    )

    # --- STEM 4: AMB (Environmental Ambience Stem) ---
    amb_file = out_dir / f"{ch_id}_stem_AMB.wav"

    # Collect all ambient cues across scenes: (path, start_ms, end_ms, target_lufs, cutoff_hz, stereo_width)
    amb_cues: List[Tuple[Path, int, int, float, int, float]] = []
    if scene_acoustics and scene_acoustics.scenes:
        for sc in scene_acoustics.scenes:
            occ_cutoff = getattr(sc, "occlusion_cutoff_hz", 18000)
            for l in sc.layers:
                # Stochastic spots are routed to FX stem, not looped in AMB bed
                if getattr(l, "layer_type", "") == "spot_stochastic":
                    continue
                resolved_amb = bank.resolve_sound(l.asset_path, category="AMB") or bank.resolve_sound(l.asset_path)
                if resolved_amb and resolved_amb.exists():
                    width = getattr(l, "stereo_width", 1.30)
                    cutoff = occ_cutoff if l.layer_type in ("weather_elements", "base_room_tone") and occ_cutoff < 18000 else 18000
                    amb_cues.append((resolved_amb, sc.start_ms, sc.end_ms, getattr(l, "target_lufs", -32.0), cutoff, width))
    elif hasattr(manifest, "ambience_scenes") and manifest.ambience_scenes:
        for amb_scene in manifest.ambience_scenes:
            res_amb = bank.resolve_sound(amb_scene.asset_path, category="AMB") or bank.resolve_sound(amb_scene.asset_path)
            if res_amb and res_amb.exists():
                amb_cues.append((res_amb, amb_scene.start_ms, amb_scene.end_ms, getattr(amb_scene, "target_lufs", -32.0), 18000, 1.30))

    if not amb_cues:
        cmd_amb = [ff, "-y", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={total_dur:.2f}", "-c:a", "pcm_s16le", str(amb_file)]
        subprocess.run(cmd_amb, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    elif len(amb_cues) == 1 and amb_cues[0][1] == 0 and amb_cues[0][2] >= int(total_dur * 1000):
        # Single scene covering whole chapter
        first_amb, _, _, _, cutoff, width = amb_cues[0]
        af_filters = ["volume=-12dB", "afade=t=in:ss=0:d=2.0", f"afade=t=out:st={max(0.1, total_dur - 2.0):.2f}:d=2.0"]
        if cutoff < 18000:
            af_filters.append(f"lowpass=f={cutoff}")
        af_filters.append("highshelf=f=6500:gain=-3.5:width=0.7")
        if width > 1.05:
            af_filters.append("stereotools=mlev=1.00:slev=1.15")
        af_filters.append("aresample=48000")
        cmd_amb = [
            ff, "-y",
            "-stream_loop", "-1",
            "-i", str(first_amb),
            "-t", f"{total_dur:.2f}",
            "-af", ",".join(af_filters),
            "-c:a", "pcm_s16le",
            str(amb_file),
        ]
        subprocess.run(cmd_amb, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        # Multi-scene / multi-layer sequential compositor with dynamic occlusion & stereo widening
        inputs = ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={total_dur:.2f}"]
        filters = []
        for i, (apath, s_ms, e_ms, tlufs, cutoff, width) in enumerate(amb_cues):
            # Probe asset duration for Anti-Looping verification
            asset_dur = 0.0
            try:
                with wave.open(str(apath), "rb") as wf:
                    asset_dur = wf.getnframes() / float(wf.getframerate())
            except Exception:
                pass
            if asset_dur <= 0.0:
                m_info = measure_audio_metrics(apath, ffmpeg=ff)
                asset_dur = m_info.get("duration_sec", 0.0)

            dur_ms = max(500, e_ms - s_ms)
            dur_sec = dur_ms / 1000.0

            # Anti-Looping Guard: If asset is short (< 30s) and scene is long (> 45s), do not infinite loop
            if asset_dur > 0.0 and asset_dur < 30.0 and dur_sec > 45.0:
                logger.warning(
                    f"[!] AntiLoopingGuard: Ambience asset '{apath.name}' ({asset_dur:.1f}s) is too short "
                    f"to loop continuously over {dur_sec:.1f}s scene. Playing once to prevent acoustic loop fatigue."
                )
                inputs.extend(["-i", str(apath)])
            else:
                inputs.extend(["-stream_loop", "-1", "-i", str(apath)])

            st_ms = max(0, s_ms)
            fade_in = min(1.5, dur_sec / 3.0)
            fade_out_st = max(0.1, dur_sec - fade_in)
            cue_vol_db = max(-36.0, min(-3.0, tlufs + 20.0))
            cue_filters = [
                "aformat=sample_rates=48000:channel_layouts=stereo",
                f"atrim=0:{dur_sec:.2f}",
                f"afade=t=in:ss=0:d={fade_in:.2f}",
                f"afade=t=out:st={fade_out_st:.2f}:d={fade_in:.2f}",
                f"volume={cue_vol_db:.1f}dB"
            ]
            if cutoff < 18000:
                cue_filters.append(f"lowpass=f={cutoff}")
            # Ambience high-shelf air damping (soften > 6.5kHz hiss to protect vocal sibilance clarity)
            cue_filters.append("highshelf=f=6500:gain=-3.5:width=0.7")
            if width > 1.05:
                cue_filters.append("stereotools=mlev=1.00:slev=1.15")
            cue_filters.append(f"adelay={st_ms}|{st_ms}")
            filters.append(f"[{i+1}:a]" + ",".join(cue_filters) + f"[amb_{i}]")
        mix_inputs = "[0:a]" + "".join(f"[amb_{i}]" for i in range(len(amb_cues)))
        filter_str = ";".join(filters) + f";{mix_inputs}amix=inputs={len(amb_cues)+1}:duration=first:normalize=0,alimiter=limit=0.95:attack=5:release=50[amb_out]"

        filter_script = None
        cmd_length_est = sum(len(str(x)) + 1 for x in inputs) + len(filter_str)
        if len(filter_str) > 3000 or cmd_length_est > 6000:
            filter_script = out_dir / f"{ch_id}_amb_filter.txt"
            filter_script.write_text(filter_str, encoding="utf-8")
            fc_args = ["-filter_complex_script", str(filter_script)]
        else:
            fc_args = ["-filter_complex", filter_str]

        cmd_amb = [
            ff, "-y",
            *inputs,
            *fc_args,
            "-map", "[amb_out]",
            "-c:a", "pcm_s16le",
            str(amb_file),
        ]
        try:
            res = subprocess.run(cmd_amb, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode != 0 or not amb_file.exists():
                err_msg = res.stderr.decode("utf-8", errors="ignore")[:300] if res.stderr else "unknown error"
                logger.warning(f"Ambience composite notice ({res.returncode}): {err_msg}")
                # Fallback to safe loop of first cue if complex graph exceeds bounds
                first_amb, _, _, _, _, _ = amb_cues[0]
                cmd_fallback = [
                    ff, "-y", "-stream_loop", "-1", "-i", str(first_amb), "-t", f"{total_dur:.2f}",
                    "-af", "volume=-12dB,aresample=48000", "-c:a", "pcm_s16le", str(amb_file)
                ]
                subprocess.run(cmd_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        finally:
            if filter_script and filter_script.exists():
                filter_script.unlink(missing_ok=True)

    # Dynamic Wallah & Crowd Breathing (Speech Ducking -6dB & Natural Recovery During Pauses)
    wallah_auto = getattr(manifest, "wallah_automations", None)
    if wallah_auto and dx_file.exists() and amb_file.exists() and dx_m.get("duration_sec", 0) > 0.5:
        tmp_ducked_amb = out_dir / f"{ch_id}_stem_AMB_breathed.wav"
        cmd_breath = [
            ff, "-y",
            "-i", str(amb_file),
            "-i", str(dx_file),
            "-filter_complex",
            "[0:a][1:a]sidechaincompress=threshold=0.015:knee=2.5:ratio=2.6:attack=25:release=350[breathed]",
            "-map", "[breathed]",
            "-c:a", "pcm_s16le",
            str(tmp_ducked_amb),
        ]
        res_breath = subprocess.run(cmd_breath, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res_breath.returncode == 0 and tmp_ducked_amb.exists() and tmp_ducked_amb.stat().st_size > 1000:
            shutil.move(str(tmp_ducked_amb), str(amb_file))

    amb_m = measure_audio_metrics(amb_file, ffmpeg=ff)
    stems_meta["AMB"] = StemMetadata(
        stem_type="AMB",
        filepath=str(amb_file),
        duration_sec=amb_m["duration_sec"],
        integrated_lufs=amb_m["integrated_lufs"],
        true_peak_dbtp=amb_m["true_peak_dbtp"],
    )

    # --- STAGE 11 MIX AUTOMATION & DYNAMIC MASKING EVALUATION ---
    mix_automation: Optional[MixAutomation] = getattr(manifest, "mix_automation", None)
    scene_intent = getattr(manifest, "scene_intent", None)
    attention_map = getattr(manifest, "attention_map", None)

    has_behaviors = bool(
        getattr(manifest, "acoustic_perspective", None)
        or getattr(manifest, "silence_events", None)
        or getattr(manifest, "impact_events", None)
    )

    if mix_automation is None and (scene_intent is not None or attention_map is not None or has_behaviors):
        has_dx = dx_file.exists() and dx_m.get("duration_sec", 0) > 0.05 and dx_m.get("integrated_lufs", -70) > -65.0
        has_mx = mx_file.exists() and mx_m.get("duration_sec", 0) > 0.05 and mx_m.get("integrated_lufs", -70) > -65.0
        has_fx = fx_file.exists() and fx_m.get("duration_sec", 0) > 0.05 and fx_m.get("integrated_lufs", -70) > -65.0
        has_amb = amb_file.exists() and amb_m.get("duration_sec", 0) > 0.05 and amb_m.get("integrated_lufs", -70) > -65.0

        est_dmr = round(dx_m["integrated_lufs"] - mx_m["integrated_lufs"], 2) if has_dx and has_mx else None

        planner = AutomationPlanner()
        mix_automation = planner.plan(
            scene_intent=scene_intent,
            attention_map=attention_map,
            total_duration_sec=total_dur,
            has_dialogue=has_dx,
            has_music=has_mx,
            has_foley=has_fx,
            has_ambience=has_amb,
            estimated_dmr_db=est_dmr,
            acoustic_perspective=getattr(manifest, "acoustic_perspective", None),
            silence_events=getattr(manifest, "silence_events", None),
            impact_events=getattr(manifest, "impact_events", None),
        )

    # Apply dynamic automation envelopes to discrete stems if planned
    has_dynamic_eq = False
    if mix_automation and mix_automation.events:
        for stem_name, stem_file in [("DX", dx_file), ("MX", mx_file), ("FX", fx_file), ("AMB", amb_file)]:
            if stem_file.exists():
                tmp_auto = out_dir / f"{ch_id}_stem_{stem_name}_auto.wav"
                try:
                    apply_automation_to_stem(stem_file, stem_name, tmp_auto, mix_automation, ffmpeg=ff)
                    if tmp_auto.exists() and tmp_auto.stat().st_size > 1000:
                        shutil.move(str(tmp_auto), str(stem_file))
                        # Refresh stem metadata with post-automation metrics
                        stem_m = measure_audio_metrics(stem_file, ffmpeg=ff)
                        stems_meta[stem_name] = StemMetadata(
                            stem_type=stem_name,
                            filepath=str(stem_file),
                            duration_sec=stem_m["duration_sec"],
                            integrated_lufs=stem_m["integrated_lufs"],
                            true_peak_dbtp=stem_m["true_peak_dbtp"],
                        )
                finally:
                    if tmp_auto.exists():
                        tmp_auto.unlink(missing_ok=True)
        has_dynamic_eq = bool(mix_automation.get_events_for_target("MX", "eq_depth"))

    # --- STEM 5: ME (Music & Effects Mix) ---
    me_file = out_dir / f"{ch_id}_stem_ME.wav"
    ducking_prof = getattr(manifest, "ducking_policy", PROFILE_STANDARD)
    if has_dynamic_eq:
        # Dynamic vocal corridor notch was already applied to MX via mix_automation
        notch_filter = "anull"
    else:
        notch_filter = get_spectral_pocketing_filter(
            notch_hz=ducking_prof.spectral_carve_hz,
            depth_db=ducking_prof.spectral_carve_depth_db,
        )

    # Sum MX, FX, AMB with spectral pocketing
    cmd_me = [
        ff, "-y",
        "-i", str(mx_file),
        "-i", str(fx_file),
        "-i", str(amb_file),
        "-filter_complex",
        f"[0:a]{notch_filter}[mx_notched];"
        f"[mx_notched][1:a][2:a]amix=inputs=3:duration=first:normalize=0,aresample=48000,alimiter=limit=0.95:attack=5:release=50[meout]",
        "-map", "[meout]",
        "-c:a", "pcm_s16le",
        str(me_file),
    ]
    subprocess.run(cmd_me, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    me_m = measure_audio_metrics(me_file, ffmpeg=ff)
    stems_meta["ME"] = StemMetadata(
        stem_type="ME",
        filepath=str(me_file),
        duration_sec=me_m["duration_sec"],
        integrated_lufs=me_m["integrated_lufs"],
        true_peak_dbtp=me_m["true_peak_dbtp"],
    )

    # --- STEM 6: CINEMATIC MIX PREMASTER (Stage 11 Mixdown Sum) ---
    # NOTE: Stage 11 produces the CINEMATIC_MIX_PREMASTER. Stage 12 performs mastering.
    premaster_file = out_dir / f"{ch_id}_cinema_premaster.wav"
    cmd_premaster = [
        ff, "-y",
        "-i", str(dx_file),
        "-i", str(me_file),
        "-filter_complex",
        f"[1:a]adelay=20|20[delayed_me];"
        f"[delayed_me][0:a]sidechaincompress=threshold=0.018:knee={getattr(ducking_prof, 'knee', 2.8)}:ratio={getattr(ducking_prof, 'ratio', 3.2)}:attack={ducking_prof.attack_ms}:release={ducking_prof.release_ms}[ducked_me];"
        f"[0:a][ducked_me]amix=inputs=2:duration=first:normalize=0,aresample=48000,volume=-1.5dB,alimiter=limit=0.85:attack=5:release=50[premaster_out]",
        "-map", "[premaster_out]",
        "-c:a", "pcm_s24le",
        str(premaster_file),
    ]
    subprocess.run(cmd_premaster, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    premaster_m = measure_audio_metrics(premaster_file, ffmpeg=ff)

    # Stage 11 semantic premaster
    stems_meta["CINEMATIC_MIX_PREMASTER"] = StemMetadata(
        stem_type="CINEMATIC_MIX_PREMASTER",
        filepath=str(premaster_file),
        duration_sec=premaster_m["duration_sec"],
        integrated_lufs=premaster_m["integrated_lufs"],
        true_peak_dbtp=premaster_m["true_peak_dbtp"],
    )

    # Anti-Overengineered DMR Validation (Dialogue-to-Masking Ratio Proxy)
    dmr_db = round(dx_m["integrated_lufs"] - me_m["integrated_lufs"], 2)
    dmr_compliant = bool(dmr_db >= 6.0 or me_m["integrated_lufs"] <= -30.0)

    ledger_meta = {
        "engine": "CinemaAudioEngine v4.0",
        "ducking_profile": ducking_prof.profile_name,
        "dialogue_masking_ratio_db": dmr_db,
        "dmr_compliant": dmr_compliant,
    }
    if mix_automation:
        ledger_meta["mix_automation"] = mix_automation.model_dump()
        ledger_meta["automation_decisions"] = mix_automation.decisions
        ledger_meta["automation_event_count"] = len(mix_automation.events)

    # --- STAGE 11 MIX JUDGE & AUTOMATIC DIAGNOSIS / REMIX PASS ---
    # Mix Judge / Remix settles the mixdown BEFORE Stage 12 Mastering executes.
    mix_judge_result: Optional[MixJudgeResult] = None
    if enable_judge:
        judge_instance = judge or MixJudge(ffmpeg_bin=ff)
        mix_judge_result = judge_instance.evaluate(
            stems={s: Path(meta.filepath) for s, meta in stems_meta.items() if meta.filepath},
            premaster_path=premaster_file,
            scene_intent=scene_intent,
            attention_map=attention_map,
            mix_automation=mix_automation,
            acoustic_perspective=getattr(manifest, "acoustic_perspective", None),
            silence_events=getattr(manifest, "silence_events", None),
            impact_events=getattr(manifest, "impact_events", None),
        )

        # Bounded remix remediation if requested and needed
        if enable_remix and mix_judge_result.status == "REMIX" and mix_judge_result.remix_plan and mix_automation:
            remix_controller = RemixController(judge=judge_instance, max_attempts=max_remix_attempts)
            remediated_auto = remix_controller.apply_remix_plan(mix_automation, mix_judge_result.remix_plan)
            # Re-apply automation to stems
            for stem_name, stem_file in [("DX", dx_file), ("MX", mx_file), ("FX", fx_file), ("AMB", amb_file)]:
                if stem_file.exists():
                    tmp_auto = out_dir / f"{ch_id}_stem_{stem_name}_remix.wav"
                    try:
                        apply_automation_to_stem(stem_file, stem_name, tmp_auto, remediated_auto, ffmpeg=ff)
                        if tmp_auto.exists() and tmp_auto.stat().st_size > 1000:
                            shutil.move(str(tmp_auto), str(stem_file))
                            stem_m = measure_audio_metrics(stem_file, ffmpeg=ff)
                            stems_meta[stem_name] = StemMetadata(
                                stem_type=stem_name,
                                filepath=str(stem_file),
                                duration_sec=stem_m["duration_sec"],
                                integrated_lufs=stem_m["integrated_lufs"],
                                true_peak_dbtp=stem_m["true_peak_dbtp"],
                            )
                    finally:
                        if tmp_auto.exists():
                            tmp_auto.unlink(missing_ok=True)
            # Re-sum ME
            subprocess.run(cmd_me, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            me_m = measure_audio_metrics(me_file, ffmpeg=ff)
            stems_meta["ME"] = StemMetadata(
                stem_type="ME",
                filepath=str(me_file),
                duration_sec=me_m["duration_sec"],
                integrated_lufs=me_m["integrated_lufs"],
                true_peak_dbtp=me_m["true_peak_dbtp"],
            )
            # Re-sum Premaster
            subprocess.run(cmd_premaster, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            premaster_m = measure_audio_metrics(premaster_file, ffmpeg=ff)
            stems_meta["CINEMATIC_MIX_PREMASTER"] = StemMetadata(
                stem_type="CINEMATIC_MIX_PREMASTER",
                filepath=str(premaster_file),
                duration_sec=premaster_m["duration_sec"],
                integrated_lufs=premaster_m["integrated_lufs"],
                true_peak_dbtp=premaster_m["true_peak_dbtp"],
            )

            # Invalidate any stale master deliverable so it never survives a remix
            stale_master = out_dir / f"{ch_id}_cinema_master.wav"
            if stale_master.exists():
                stale_master.unlink(missing_ok=True)

            # Re-evaluate with judge
            mix_judge_result = judge_instance.evaluate(
                stems={s: Path(meta.filepath) for s, meta in stems_meta.items() if meta.filepath},
                premaster_path=premaster_file,
                scene_intent=scene_intent,
                attention_map=attention_map,
                mix_automation=remediated_auto,
                acoustic_perspective=getattr(manifest, "acoustic_perspective", None),
                silence_events=getattr(manifest, "silence_events", None),
                impact_events=getattr(manifest, "impact_events", None),
                iteration=2,
            )
            mix_automation = remediated_auto
            ledger_meta["mix_automation"] = remediated_auto.model_dump()
            ledger_meta["automation_decisions"] = remediated_auto.decisions
            ledger_meta["automation_event_count"] = len(remediated_auto.events)
            ledger_meta["remix_cycles_executed"] = 1

        ledger_meta["mix_judge_audit"] = mix_judge_result.model_dump()
        ledger_meta["mix_judge_status"] = mix_judge_result.status
        ledger_meta["mix_judge_score"] = mix_judge_result.overall_score

    # --- STEM 7: FULL MASTER (Stage 12 Broadcast Mastering via MasteringEngineV2) ---
    # Master strictly from the final settled premaster
    master_file = out_dir / f"{ch_id}_cinema_master.wav"
    if master_file.exists():
        master_file.unlink(missing_ok=True)

    mastering_engine = MasteringEngineV2(ffmpeg_bin=ff)
    master_target_lufs = -19.0
    master_target_tp = -1.5
    if hasattr(manifest, "mastering") and manifest.mastering:
        master_target_lufs = getattr(manifest.mastering, "target_lufs", -19.0)
        master_target_tp = getattr(manifest.mastering, "true_peak_dbtp", getattr(manifest.mastering, "true_peak_db", -1.5))

    master_req = MasteringRequest(
        chapter_id=ch_id,
        premaster_path=str(premaster_file),
        output_master_path=str(master_file),
        dialogue_stem_path=str(dx_file) if dx_file.exists() else None,
        profile=MasteringProfile(
            target_lufs=master_target_lufs,
            true_peak_ceiling_dbtp=master_target_tp,
        ),
    )
    mastering_result = mastering_engine.master(master_req)
    if mastering_result.analysis_after:
        master_m = {
            "duration_sec": mastering_result.analysis_after.duration_sec,
            "integrated_lufs": mastering_result.analysis_after.integrated_lufs,
            "true_peak_dbtp": mastering_result.analysis_after.true_peak_dbtp if mastering_result.analysis_after.true_peak_dbtp is not None else -1.5,
        }
    else:
        master_m = measure_audio_metrics(master_file, ffmpeg=ff)

    stems_meta["FULL_MASTER"] = StemMetadata(
        stem_type="FULL_MASTER",
        filepath=str(master_file),
        duration_sec=master_m["duration_sec"],
        integrated_lufs=master_m["integrated_lufs"],
        true_peak_dbtp=master_m["true_peak_dbtp"],
    )
    ledger_meta["total_stems"] = len(stems_meta)
    ledger_meta["mastering_v2_audit"] = mastering_result.model_dump()
    ledger_meta["mastering_status"] = mastering_result.status

    ledger = StemLedger(
        chapter_id=ch_id,
        stems=stems_meta,
        master_lufs=master_m["integrated_lufs"],
        master_peak=master_m["true_peak_dbtp"],
        compliance_status=(
            master_m["integrated_lufs"] >= -21.0
            and master_m["true_peak_dbtp"] <= -1.4
            and dmr_compliant
            and (mix_judge_result is None or mix_judge_result.status != "FAIL")
            and (mastering_result.qc_result.passed)
        ),
        metadata=ledger_meta,
    )

    ledger_path = out_dir / f"{ch_id}_stem_ledger.json"
    ledger.save_to_disk(ledger_path)

    try:
        from audiobook_factory.telemetry import get_telemetry_ledger
        chap_num_match = re.search(r"\d+", ch_id)
        chap_num = int(chap_num_match.group(0)) if chap_num_match else 0
        measured_dur = float(master_m.get("duration_sec", 0.0) or 0.0)
        if measured_dur <= 0.0 and master_file.exists():
            measured_dur = float(measure_audio_metrics(master_file, ffmpeg=ff).get("duration_sec", total_dur))

        get_telemetry_ledger().record_acoustic_metrics(
            run_id=os.environ.get("CURRENT_AUDIOBOOK_RUN_ID", f"chap_{chap_num}"),
            chapter_num=chap_num,
            duration_sec=measured_dur,
            integrated_lufs=float(master_m.get("integrated_lufs", -19.0)),
            true_peak_dbtp=float(master_m.get("true_peak_dbtp", -1.5)),
            loudness_range_lu=float(master_m.get("loudness_range_lu", 0.0) or 0.0),
            phase_correlation=float(ledger_meta.get("phase_correlation", 0.85) or 0.85),
        )
    except Exception as e:
        logger.warning(f"Acoustic telemetry record failed: {e}")

    return ledger
