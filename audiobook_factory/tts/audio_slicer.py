#!/usr/bin/env python3
"""
Audiobook Factory - Acoustic Batch Slicer & Zero-Crossing Declicker.
Applies GPU-accelerated MMS-FA forced alignment, Hann micro-fades, character DSP calibration,
and exact zero-crossing endpoint clamping to dialogue batch slices.
"""

from __future__ import annotations
import uuid
import wave
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.logger import logger
from audiobook_factory.contracts import BatchPlanItem
from audiobook_factory.forced_aligner import WorkstationForcedAligner
from audiobook_factory.tts.constants import (
    DEFAULT_VOICE,
    DEFAULT_DECLICK_FADE_MS,
    get_ffmpeg,
)


def compute_canonical_segment_filename(
    chapter_num: int,
    seg_num: int,
    text: str,
    sp_cfg: Optional[Dict[str, Any]] = None,
    default_voice: str = DEFAULT_VOICE,
) -> str:
    """Computes deterministic, reproducible audio chunk filename matching synthesis cache."""
    cfg = sp_cfg or {}
    voice = cfg.get("voice", default_voice)
    speed = float(cfg.get("speed", 1.0))
    pitch = float(cfg.get("pitch", 1.0))
    bass_boost_db = float(cfg.get("bass_boost_db", 0.0))
    clarity_cut_db = float(cfg.get("clarity_reduction_db", 0.0))
    lowpass_hz = int(cfg.get("lowpass_hz", 0))
    highpass_hz = int(cfg.get("highpass_hz", 0))
    presence_boost_db = float(cfg.get("presence_boost_db", 0.0))
    volume_gain_db = float(cfg.get("volume_gain_db", 0.0))
    calib_str = f"{voice}:{speed:.2f}:{pitch:.2f}:{bass_boost_db:.1f}:{clarity_cut_db:.1f}:{lowpass_hz}:{highpass_hz}:{presence_boost_db:.1f}:{volume_gain_db:.1f}"
    cache_key = f"{text}|{calib_str}".encode("utf-8")
    text_hash = hashlib.md5(cache_key).hexdigest()[:8]
    return f"c{chapter_num:03d}_s{seg_num:04d}_{text_hash}.wav"


def slice_and_declick_batch(
    raw_audio: Path,
    batch: BatchPlanItem,
    chapter_num: int,
    output_dir: Path,
    aligner: Optional[WorkstationForcedAligner] = None,
    declick_fade_ms: float = DEFAULT_DECLICK_FADE_MS,
    dispatcher: Optional[Any] = None,
) -> List[Tuple[Path, float, List[Dict[str, Any]]]]:
    """
    Slices a merged multi-speaker WAV into individual canonical segment WAV files.
    Uses WorkstationForcedAligner on RTX 4050 GPU for sample-accurate boundaries,
    and applies a 25Hz DC filter + 5ms cosine micro-fade + character DSP calibration at slice boundaries.
    """
    if aligner is None:
        aligner = WorkstationForcedAligner()

    alignment_results = aligner.align_batch_detailed(raw_audio, batch.segments)
    sliced_results: List[Tuple[Path, float, List[Dict[str, Any]]]] = []
    ffmpeg_bin = get_ffmpeg()

    fade_sec = max(0.001, declick_fade_ms / 1000.0)

    for seg, align_res in zip(batch.segments, alignment_results):
        start_ms = align_res.start_ms
        end_ms = align_res.end_ms
        dur_ms = max(200, end_ms - start_ms)
        dur_sec = dur_ms / 1000.0
        words_metadata = [w.model_dump(mode="json") for w in align_res.words]
        start_sec = start_ms / 1000.0

        sp_cfg = dispatcher.get_speaker_config(seg.speaker, getattr(seg, "type", "dialogue")) if dispatcher else {}
        voice_name = sp_cfg.get("voice") or batch.voice_map.get(seg.speaker, "Aoede")
        if not sp_cfg:
            sp_cfg = {"voice": voice_name}

        out_filename = compute_canonical_segment_filename(chapter_num, seg.index, seg.text, sp_cfg, default_voice=voice_name)
        out_wav = output_dir / out_filename

        fade_sec = max(0.015, declick_fade_ms / 1000.0)
        fade_out_start = max(0.0, dur_sec - fade_sec)
        filter_parts = [
            "highpass=f=30",
            f"afade=t=in:ss=0:d={fade_sec:.3f}:curve=qsin",
            f"afade=t=out:st={fade_out_start:.3f}:d={fade_sec:.3f}:curve=qsin",
            "alimiter=limit=-1.2dB:attack=5:release=50:asc=true",
        ]

        if sp_cfg:
            highpass_hz = int(sp_cfg.get("highpass_hz", 0))
            bass_boost_db = float(sp_cfg.get("bass_boost_db", 0.0))
            presence_boost_db = float(sp_cfg.get("presence_boost_db", 0.0))
            volume_gain_db = float(sp_cfg.get("volume_gain_db", 0.0))
            clarity_cut_db = float(sp_cfg.get("clarity_reduction_db", 0.0))
            lowpass_hz = int(sp_cfg.get("lowpass_hz", 0))
            softclip_tanh = bool(sp_cfg.get("softclip_tanh", False))
            if highpass_hz > 25:
                filter_parts.append(f"highpass=f={highpass_hz}")
            if bass_boost_db > 0.1:
                filter_parts.append(f"equalizer=f=100:t=q:w=1.2:g={bass_boost_db:.1f}")
                filter_parts.append("equalizer=f=200:t=q:w=1.4:g=3.0")
            elif bass_boost_db < -0.1:
                filter_parts.append(f"equalizer=f=200:t=q:w=1.2:g={bass_boost_db:.1f}")
            if presence_boost_db > 0.1:
                filter_parts.append(f"equalizer=f=3200:t=q:w=1.4:g={presence_boost_db:.1f}")
            if abs(volume_gain_db) > 0.1:
                filter_parts.append(f"volume={volume_gain_db:+.1f}dB")
            if clarity_cut_db > 0.1:
                filter_parts.append(f"equalizer=f=3000:t=q:w=1.8:g=-{clarity_cut_db:.1f}")
            if lowpass_hz > 1000:
                filter_parts.append(f"lowpass=f={lowpass_hz}")
            if softclip_tanh or ("[shouting]" in seg.text.lower()):
                filter_parts.append("asoftclip=type=tanh:param=1.2")

        filter_str = ",".join(filter_parts)

        tmp_slice = out_wav.with_suffix(f".tmp_{uuid.uuid4().hex[:6]}.wav")
        cmd = [
            ffmpeg_bin, "-y",
            "-ss", f"{start_sec:.3f}",
            "-t", f"{dur_sec:.3f}",
            "-i", str(raw_audio),
            "-af", filter_str,
            "-c:a", "pcm_s16le",
            str(tmp_slice),
        ]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # Enforce exact zero-crossing endpoints on sliced chunk
            try:
                with wave.open(str(tmp_slice), "rb") as in_wf:
                    p_params = in_wf.getparams()
                    p_pcm = in_wf.readframes(in_wf.getnframes())
                import numpy as _np
                p_samples = _np.frombuffer(p_pcm, dtype=_np.int16).copy()
                if len(p_samples) > 2:
                    p_samples[0] = 0
                    p_samples[-1] = 0
                with wave.open(str(tmp_slice), "wb") as out_wf:
                    out_wf.setparams(p_params)
                    out_wf.writeframes(p_samples.tobytes())
            except Exception:
                pass
            tmp_slice.replace(out_wav)
            actual_dur = dur_sec
            try:
                with wave.open(str(out_wav), "rb") as wf:
                    actual_dur = wf.getnframes() / float(wf.getframerate())
            except Exception:
                pass
            sliced_results.append((out_wav, actual_dur, words_metadata))
        except Exception as e:
            logger.error(f"[!] Failed to slice segment {seg.index} from batch {batch.batch_id}: {e}")
            if tmp_slice.exists():
                tmp_slice.unlink(missing_ok=True)
            raise RuntimeError(f"Acoustic slicing failed for segment {seg.index} in batch {batch.batch_id}: {e}") from e

    return sliced_results
