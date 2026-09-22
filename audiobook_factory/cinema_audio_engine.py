#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 4: Next-Gen Cinema Audio Drama Engine (Pydantic v2).
"New Room 4": Manages discrete DME stem generation (DX, MX, FX, AMB, ME), true broadcast summing,
and export ledger compliance tracking.
Persists `chapter_XXX_cinema_manifest.json` and `chapter_XXX_stem_ledger.json`.
"""

from __future__ import annotations
import math
import json
import shutil
import logging
import datetime
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal, Union

from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.contracts import (
    CreativeManifest,
    MusicCue,
    FoleyCue,
    AmbienceScene,
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

logger = logging.getLogger("audiobook_factory.cinema_audio_engine")


class StemMetadata(BaseModel):
    """Acoustic and technical metadata for a discrete audio stem."""
    model_config = ConfigDict(extra="ignore")

    stem_type: Literal["DX", "MX", "FX", "AMB", "ME", "FULL_MASTER"]
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
    ducking_policy: DuckingProfile = Field(default_factory=lambda: PROFILE_STANDARD)
    total_duration_sec: float = Field(default=0.0, ge=0.0)
    silence_percentage: float = Field(default=100.0, ge=0.0, le=100.0)
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
        "-af", "ebur128=framelog=verbose",
        "-f", "null", "-"
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
        output = proc.stderr
        import re
        i_match = re.search(r"Integrated loudness:\s+I:\s+([-\d.]+)\s+LUFS", output)
        tp_match = re.search(r"Peak:\s+([-\d.]+)\s+dBFS", output) or re.search(r"True peak:\s+([-\d.]+)\s+dBFS", output)
        dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", output)

        dur_sec = 0.0
        if dur_match:
            h, m, s = dur_match.groups()
            dur_sec = int(h) * 3600 + int(m) * 60 + float(s)

        lufs = float(i_match.group(1)) if i_match else -24.0
        peak = float(tp_match.group(1)) if tp_match else -1.5
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

    # 1. Probe dialogue duration
    d_metrics = measure_audio_metrics(d_path, ffmpeg=ff)
    total_dur = d_metrics.get("duration_sec", 0.0) or getattr(manifest, "total_duration_sec", 60.0) or 60.0

    stems_meta: Dict[str, StemMetadata] = {}

    # --- STEM 1: DX (Dialogue Stem) ---
    dx_file = out_dir / f"{ch_id}_stem_DX.wav"
    if d_path.exists():
        shutil.copyfile(d_path, dx_file)
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
    # Check if scene_acoustics exists on manifest
    scene_acoustics = getattr(manifest, "scene_acoustics", None)
    if scene_acoustics and scene_acoustics.scenes:
        # Render multi-scene ambient beds
        amb_cues: List[Tuple[Path, int, int, float]] = []
        for sc in scene_acoustics.scenes:
            for l in sc.layers:
                resolved_amb = bank.resolve_sound(l.asset_path, category="AMB") or bank.resolve_sound(l.asset_path)
                if resolved_amb and resolved_amb.exists():
                    amb_cues.append((resolved_amb, sc.start_ms, sc.end_ms, l.target_lufs))

        if amb_cues:
            # Render first valid layer with loop as primary bed
            first_amb, _, _, _ = amb_cues[0]
            cmd_amb = [
                ff, "-y",
                "-stream_loop", "-1",
                "-i", str(first_amb),
                "-t", f"{total_dur:.2f}",
                "-af", "volume=-12dB,afade=t=in:ss=0:d=2.0,afade=t=out:st=" + f"{max(0.1, total_dur - 2.0):.2f}:d=2.0,aresample=48000",
                "-c:a", "pcm_s16le",
                str(amb_file),
            ]
            subprocess.run(cmd_amb, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            cmd_amb = [ff, "-y", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={total_dur:.2f}", "-c:a", "pcm_s16le", str(amb_file)]
            subprocess.run(cmd_amb, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    elif hasattr(manifest, "ambience_scenes") and manifest.ambience_scenes:
        # Legacy AmbienceScene compatibility
        amb_scene = manifest.ambience_scenes[0]
        res_amb = bank.resolve_sound(amb_scene.asset_path, category="AMB") or bank.resolve_sound(amb_scene.asset_path)
        if res_amb and res_amb.exists():
            cmd_amb = [
                ff, "-y",
                "-stream_loop", "-1",
                "-i", str(res_amb),
                "-t", f"{total_dur:.2f}",
                "-af", "volume=-12dB,afade=t=in:ss=0:d=2.0,afade=t=out:st=" + f"{max(0.1, total_dur - 2.0):.2f}:d=2.0,aresample=48000",
                "-c:a", "pcm_s16le",
                str(amb_file),
            ]
            subprocess.run(cmd_amb, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            cmd_amb = [ff, "-y", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={total_dur:.2f}", "-c:a", "pcm_s16le", str(amb_file)]
            subprocess.run(cmd_amb, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        cmd_amb = [ff, "-y", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={total_dur:.2f}", "-c:a", "pcm_s16le", str(amb_file)]
        subprocess.run(cmd_amb, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    amb_m = measure_audio_metrics(amb_file, ffmpeg=ff)
    stems_meta["AMB"] = StemMetadata(
        stem_type="AMB",
        filepath=str(amb_file),
        duration_sec=amb_m["duration_sec"],
        integrated_lufs=amb_m["integrated_lufs"],
        true_peak_dbtp=amb_m["true_peak_dbtp"],
    )

    # --- STEM 5: ME (Music & Effects Mix) ---
    me_file = out_dir / f"{ch_id}_stem_ME.wav"
    ducking_prof = getattr(manifest, "ducking_policy", PROFILE_STANDARD)
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
        f"[0:a][1:a][2:a]amix=inputs=3:duration=first:normalize=0[memix];[memix]{notch_filter},aresample=48000[meout]",
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

    # --- STEM 6: FULL MASTER (DX + ME Final Sum) ---
    master_file = out_dir / f"{ch_id}_cinema_master.wav"
    # True broadcast summing with sidechain ducking & -19.0 LUFS mastering
    cmd_master = [
        ff, "-y",
        "-i", str(dx_file),
        "-i", str(me_file),
        "-filter_complex",
        f"[1:a][0:a]sidechaincompress=threshold=0.08:ratio=4:attack={ducking_prof.attack_ms}:release={ducking_prof.release_ms}[ducked_me];"
        f"[0:a][ducked_me]amix=inputs=2:duration=first:normalize=0[fullmix];"
        f"[fullmix]loudnorm=I=-19.0:TP=-1.5:LRA=8.5,aresample=48000[out]",
        "-map", "[out]",
        "-c:a", "pcm_s16le",
        str(master_file),
    ]
    subprocess.run(cmd_master, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    master_m = measure_audio_metrics(master_file, ffmpeg=ff)
    stems_meta["FULL_MASTER"] = StemMetadata(
        stem_type="FULL_MASTER",
        filepath=str(master_file),
        duration_sec=master_m["duration_sec"],
        integrated_lufs=master_m["integrated_lufs"],
        true_peak_dbtp=master_m["true_peak_dbtp"],
    )

    ledger = StemLedger(
        chapter_id=ch_id,
        stems=stems_meta,
        master_lufs=master_m["integrated_lufs"],
        master_peak=master_m["true_peak_dbtp"],
        compliance_status=(master_m["integrated_lufs"] >= -21.0 and master_m["true_peak_dbtp"] <= -1.4),
        metadata={
            "engine": "CinemaAudioEngine v4.0",
            "ducking_profile": ducking_prof.profile_name,
            "total_stems": len(stems_meta),
        },
    )

    ledger_path = out_dir / f"{ch_id}_stem_ledger.json"
    ledger.save_to_disk(ledger_path)
    return ledger
