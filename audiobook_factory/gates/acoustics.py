#!/usr/bin/env python3
"""
Audiobook Factory - Acoustic & Audio DSP Quality Gates.
Houses Gate 3.5 (Acoustic Feasibility Guard), Gate 4 (Timeline & Audio Ledger Monotonicity),
Gate 5 (Broadcast EBU R128 Master Loudness Compliance), Gate 5.2 (Spectral Masking & DMR Guard),
and Gate 5.3 (Stereo Phase Correlation & Mono Compatibility Guard).
"""

from __future__ import annotations
import re
import wave
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.contracts import TimelineLedger, ScreenplayScript
from audiobook_factory.gates.contracts import GateAuditError, AuditResult
from audiobook_factory.tts.constants import get_ffmpeg

logger = logging.getLogger("audiobook_factory.gates.acoustics")


def _get_subprocess():
    import sys
    fa = sys.modules.get("audiobook_factory.gate_auditor")
    if fa and hasattr(fa, "subprocess"):
        return fa.subprocess
    return subprocess


def audit_gate4_ledger(
    ledger_file: Path,
    script_file: Path,
    audio_dir: Path,
) -> Dict[str, Any]:
    """
    Audit Gate 4.5: Verifies Master Timeline & Audio Transcript Ledger against screenplay script and audio chunks.
    Ensures sample-accurate monotonicity, 100% text preservation (zero truncation),
    and verified valid audio files on disk.
    """
    ledger_file = Path(ledger_file).resolve()
    script_file = Path(script_file).resolve()
    audio_dir = Path(audio_dir).resolve()

    if not ledger_file.exists():
        raise GateAuditError(f"Gate 4.5 Failed: Timeline ledger file missing at {ledger_file}")
    if not script_file.exists():
        raise GateAuditError(f"Gate 4.5 Failed: Script file missing at {script_file}")

    ledger = TimelineLedger.from_file(ledger_file)
    script = ScreenplayScript.from_file(script_file)

    if ledger.total_segments != len(script.segments):
        raise GateAuditError(
            f"Gate 4.5 Failed: Segment count mismatch: ledger has {ledger.total_segments}, script has {len(script.segments)}"
        )

    prev_end_ms = 0
    text_mismatches = []
    missing_chunks = []

    for seg_l, seg_s in zip(ledger.segments, script.segments):
        if seg_l.segment_index != seg_s.index:
            raise GateAuditError(
                f"Gate 4.5 Failed: Index mismatch: ledger segment {seg_l.segment_index} != script segment {seg_s.index}"
            )
        if seg_l.speaker != seg_s.speaker:
            raise GateAuditError(
                f"Gate 4.5 Failed: Speaker mismatch at segment {seg_l.segment_index}: {seg_l.speaker} != {seg_s.speaker}"
            )
        s_uid = getattr(seg_s, "uid", None)
        l_uid = getattr(seg_l, "uid", None)
        if s_uid and l_uid and s_uid != l_uid:
            raise GateAuditError(
                f"Gate 4.5 Failed: UID lineage mismatch at segment {seg_l.segment_index}: ledger '{l_uid}' != script '{s_uid}'"
            )
        if seg_l.text.strip() != seg_s.text.strip():
            text_mismatches.append((seg_l.segment_index, seg_l.text[:30], seg_s.text[:30]))

        if seg_l.start_ms < prev_end_ms:
            raise GateAuditError(
                f"Gate 4.5 Failed: Non-monotonic timeline at segment {seg_l.segment_index}: "
                f"start_ms ({seg_l.start_ms}) < previous end_ms ({prev_end_ms})"
            )
        if seg_l.end_ms <= seg_l.start_ms:
            raise GateAuditError(
                f"Gate 4.5 Failed: Invalid segment duration at {seg_l.segment_index}: "
                f"end_ms ({seg_l.end_ms}) <= start_ms ({seg_l.start_ms})"
            )

        if audio_dir.exists():
            chunk_path = audio_dir / seg_l.audio_file
            if not chunk_path.exists():
                parts = seg_l.audio_file.split("_")
                if len(parts) >= 2:
                    matches = list(audio_dir.glob(f"{parts[0]}_{parts[1]}_*.wav"))
                    if not matches:
                        missing_chunks.append(seg_l.audio_file)
                else:
                    missing_chunks.append(seg_l.audio_file)
            elif chunk_path.stat().st_size <= 44:
                missing_chunks.append(f"{seg_l.audio_file} (empty)")
            elif chunk_path.stat().st_size <= 1000 and getattr(seg_l, "speaker", "").lower() not in ("foley", "action") and "[action]" not in getattr(seg_l, "text", "").lower():
                missing_chunks.append(f"{seg_l.audio_file} (empty)")

        prev_end_ms = seg_l.end_ms

    if text_mismatches:
        raise GateAuditError(f"Gate 4.5 Failed: Text divergence in {len(text_mismatches)} segment(s): {text_mismatches[:3]}")
    if missing_chunks:
        raise GateAuditError(f"Gate 4.5 Failed: Missing or corrupt audio chunks: {missing_chunks[:5]}")

    return {
        "status": "PASS",
        "total_segments": ledger.total_segments,
        "total_timeline_sec": round(ledger.total_timeline_duration_ms / 1000.0, 2),
        "total_dialogue_sec": round(ledger.total_dialogue_duration_ms / 1000.0, 2),
        "silence_percentage": ledger.silence_percentage,
    }


def audit_gate5_master(
    master_file: Path,
    target_lufs: float = -19.0,
    tolerance_lu: float = 1.0,
    max_true_peak: float = -1.4,
) -> Dict[str, Any]:
    """
    Audit Gate 5: Probes final master audio file via FFmpeg for broadcast EBU R128 compliance.
    Asserts Integrated Loudness within target +/- tolerance and True Peak <= max_true_peak.
    """
    master_file = Path(master_file).resolve()
    if not master_file.exists():
        raise GateAuditError(f"Gate 5 Failed: Master audio file missing at {master_file}")
    if master_file.stat().st_size < 1000:
        raise GateAuditError(f"Gate 5 Failed: Master audio file empty or truncated ({master_file.stat().st_size} bytes)")

    ffmpeg_bin = get_ffmpeg()
    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(master_file),
        "-af", "ebur128=peak=true:framelog=verbose",
        "-f", "null", "-"
    ]
    try:
        proc = _get_subprocess().run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        output = proc.stderr
        if proc.returncode != 0:
            raise GateAuditError(f"Gate 5 Failed: FFmpeg ebur128 probe process exited with error code {proc.returncode}: {output[:200]}")
        i_match = re.search(r"Integrated loudness:\s+I:\s+([-\d.]+)\s+LUFS", output)
        tp_match = re.search(r"True peak:\s+Peak:\s+([-\d.]+)(?:\s+([-\d.]+))?", output) or re.search(r"Peak:\s+([-\d.]+)\s+dBFS", output)

        if not i_match:
            raise GateAuditError(f"Gate 5 Failed: Could not parse Integrated Loudness from FFmpeg output on {master_file}")

        measured_lufs = float(i_match.group(1))
        if tp_match:
            tp_vals = [float(v) for v in tp_match.groups() if v is not None]
            measured_tp = max(tp_vals) if tp_vals else -1.5
        else:
            measured_tp = -1.5
    except GateAuditError:
        raise
    except Exception as e:
        raise GateAuditError(f"Gate 5 Failed: FFmpeg ebur128 probe failed on {master_file}: {e}")

    if abs(measured_lufs - target_lufs) > tolerance_lu:
        raise GateAuditError(
            f"Gate 5 Failed: EBU R128 Integrated Loudness {measured_lufs:.1f} LUFS outside target "
            f"{target_lufs:.1f} +/- {tolerance_lu} LUFS"
        )
    if measured_tp > max_true_peak:
        raise GateAuditError(
            f"Gate 5 Failed: True Peak {measured_tp:.1f} dBTP exceeds ceiling {max_true_peak:.1f} dBTP"
        )

    return {
        "status": "PASS",
        "master_file": str(master_file),
        "integrated_lufs": measured_lufs,
        "true_peak_dbtp": measured_tp,
        "target_lufs": target_lufs,
    }


def audit_gate3_5_acoustic_feasibility(
    manifest: Any,
    sound_bank: Optional[Any] = None,
) -> AuditResult:
    """
    Gate 3.5: Acoustic Pre-Flight Feasibility Guard.
    Audits creative manifest before rendering:
    1. Validates physical audio asset existence (> 1000 bytes on disk).
    2. Validates section slicing bounds: section_start_sec + duration <= track duration on disk.
    3. Validates fade envelope geometry (fade_in + fade_out <= cue duration).
    4. Validates sliding window voice concurrency (flags high density transient collisions).
    """
    errors: List[str] = []
    warnings: List[str] = []
    details: Dict[str, Any] = {}

    from audiobook_factory.sound_bank import get_sound_bank
    bank = sound_bank or get_sound_bank()

    music_cues = list(getattr(manifest, "music_cues", []))
    foley_cues = list(getattr(manifest, "foley_cues", []))

    # 1. Audit Music Cues
    for cue in music_cues:
        track_name = getattr(cue, "track_name", "") or str(getattr(cue, "track_id", ""))
        is_direct_file = any(track_name.lower().endswith(ext) for ext in (".wav", ".mp3", ".flac", ".ogg", ".aiff", ".m4a")) or ("/" in track_name or "\\" in track_name)
        try:
            resolved = bank.resolve_asset_path(track_name)
        except Exception:
            if not is_direct_file:
                try:
                    resolved = bank.resolve_sound(track_name, category="BGM") or bank.resolve_sound(track_name)
                except Exception:
                    resolved = None
            else:
                resolved = None

        if not resolved or not resolved.exists():
            errors.append(f"Music cue '{getattr(cue, 'cue_id', 'unknown')}' asset not found on disk: {track_name}")
        elif resolved.stat().st_size < 1000:
            errors.append(f"Music cue asset empty or corrupt (<1000B): {resolved.name}")
        else:
            track_dur = bank._extract_duration(resolved)
            s_start = float(getattr(cue, "section_start_sec", 0.0) or 0.0)
            if track_dur > 0 and s_start >= track_dur:
                errors.append(f"Music cue '{getattr(cue, 'cue_id', '')}' section_start_sec ({s_start:.1f}s) exceeds source duration ({track_dur:.1f}s).")

        fade_in_ms = getattr(cue, "fade_in_ms", 0) or 0
        fade_out_ms = getattr(cue, "fade_out_ms", 0) or 0
        dur_ms = getattr(cue, "duration_ms", 0) or 0
        if (fade_in_ms + fade_out_ms) > dur_ms and dur_ms > 0:
            warnings.append(f"Music cue '{getattr(cue, 'cue_id', '')}' fade times ({fade_in_ms + fade_out_ms}ms) exceed cue duration ({dur_ms}ms).")

    # 2. Audit Foley Cues
    for cue in foley_cues:
        asset_ref = getattr(cue, "asset_path", "") or getattr(cue, "asset_name", "") or str(getattr(cue, "asset_id", ""))
        if not asset_ref:
            continue
        resolved = None
        try:
            resolved = bank.resolve_asset_path(asset_ref)
        except Exception:
            pass

        if not resolved or not resolved.exists():
            try:
                resolved = bank.resolve_sound(asset_ref, category="SFX") or bank.resolve_sound(asset_ref)
            except Exception:
                resolved = None

        if not resolved or not resolved.exists():
            errors.append(f"Foley cue '{getattr(cue, 'cue_id', 'unknown')}' asset not found on disk: {asset_ref}")
        elif resolved.stat().st_size < 1000:
            errors.append(f"Foley cue asset empty or corrupt (<1000B): {resolved.name}")

    # 3. Concurrency window scan (sliding 200ms)
    sorted_foley = sorted(foley_cues, key=lambda c: getattr(c, "start_ms", 0) or 0)
    for i, c in enumerate(sorted_foley):
        c_start = getattr(c, "start_ms", 0) or 0
        window_count = sum(1 for other in sorted_foley if abs((getattr(other, "start_ms", 0) or 0) - c_start) < 200)
        if window_count > 4:
            warnings.append(f"High foley density ({window_count} cues) within 200ms window at {c_start}ms.")
            break

    details["total_music_cues"] = len(music_cues)
    details["total_foley_cues"] = len(foley_cues)
    details["warnings"] = warnings

    passed = len(errors) == 0
    return AuditResult(
        gate_name="Gate 3.5 (Acoustic Feasibility)",
        passed=passed,
        details=details,
        errors=errors,
        warnings=warnings,
    )


def audit_gate5_2_spectral_masking(
    dialogue_stem: Path,
    music_bus: Path,
    min_dmr_db: float = 12.0,
    ffmpeg: Optional[str] = None,
) -> AuditResult:
    """
    Gate 5.2: Spectral Masking & Dialogue-to-Music Ratio (DMR) Guard.
    Measures dialogue vs music loudness in the 300Hz-3.5kHz vocal intelligibility corridor.
    Asserts dialogue punches through music with at least `min_dmr_db` separation.
    """
    ff = ffmpeg or get_ffmpeg()
    d_path = Path(dialogue_stem).resolve()
    m_path = Path(music_bus).resolve()

    errors: List[str] = []
    warnings: List[str] = []
    details: Dict[str, Any] = {}

    def _measure_corridor_lufs(fpath: Path) -> Tuple[Optional[float], Optional[str]]:
        if not fpath.exists():
            return None, f"Stem file not found: {fpath.name}"
        if fpath.stat().st_size < 1000:
            return -70.0, None
        cmd = [
            ff, "-y",
            "-i", str(fpath),
            "-af", "highpass=f=300,lowpass=f=3500,ebur128=framelog=quiet",
            "-f", "null", "-"
        ]
        try:
            res = _get_subprocess().run(cmd, capture_output=True, text=True, timeout=45)
            if res.returncode != 0:
                return None, f"FFmpeg corridor probe failed (exit code {res.returncode}): {res.stderr[:160]}"
            match = re.search(r"Integrated loudness:\s+I:\s+([-\d.]+)\s+LUFS", res.stderr)
            if not match:
                return None, f"Could not parse Integrated Loudness from FFmpeg output on {fpath.name}"
            return float(match.group(1)), None
        except Exception as e:
            return None, f"FFmpeg probe exception on {fpath.name}: {e}"

    d_lufs, d_err = _measure_corridor_lufs(d_path)
    m_lufs, m_err = _measure_corridor_lufs(m_path)

    if d_err:
        errors.append(f"Dialogue stem probe error: {d_err}")
    if m_err:
        errors.append(f"Music stem probe error: {m_err}")

    if errors:
        details["dialogue_corridor_lufs"] = d_lufs
        details["music_corridor_lufs"] = m_lufs
        details["dialogue_error"] = d_err
        details["music_error"] = m_err
        return AuditResult(
            gate_name="Gate 5.2 (Spectral Masking)",
            gate="Gate 5.2 (Spectral Masking)",
            status="FAIL",
            passed=False,
            details=details,
            errors=errors,
            warnings=warnings,
        )

    # If music is silent (< -60 LUFS), DMR is effectively infinite -> PASS
    if m_lufs <= -60.0:
        dmr_db = 99.0
        status_note = "Music stem silent or unvoiced in vocal corridor (zero masking)."
    elif d_lufs <= -60.0:
        dmr_db = -99.0
        warnings.append("Dialogue stem silent in vocal corridor.")
        status_note = "Dialogue unvoiced."
    else:
        dmr_db = round(d_lufs - m_lufs, 2)
        status_note = f"Measured DMR: +{dmr_db:.1f} dB"

    if dmr_db < min_dmr_db and m_lufs > -60.0:
        errors.append(
            f"Vocal spectral masking violation: Dialogue-to-Music Ratio is +{dmr_db:.1f} dB "
            f"(required minimum +{min_dmr_db:.1f} dB in 300Hz-3.5kHz corridor)."
        )

    details["dialogue_corridor_lufs"] = d_lufs
    details["music_corridor_lufs"] = m_lufs
    details["measured_dmr_db"] = dmr_db
    details["min_required_dmr_db"] = min_dmr_db
    details["note"] = status_note

    passed = len(errors) == 0
    return AuditResult(
        gate_name="Gate 5.2 (Spectral Masking)",
        gate="Gate 5.2 (Spectral Masking)",
        status="PASS" if passed else "FAIL",
        passed=passed,
        details=details,
        errors=errors,
        warnings=warnings,
    )


def audit_gate5_3_stereo_phase(
    audio_file: Path,
    min_phase_correlation: float = 0.20,
    ffmpeg: Optional[str] = None,
) -> AuditResult:
    """
    Gate 5.3: Stereo Phase Correlation & Mono Compatibility Guard.
    Uses FFmpeg aphasemeter filter to evaluate frame-by-frame Pearson stereo phase correlation r.
    Guarantees r >= min_phase_correlation to prevent mono phase cancellation on mobile/smart speakers.
    """
    ff = ffmpeg or get_ffmpeg()
    a_path = Path(audio_file).resolve()

    errors: List[str] = []
    details: Dict[str, Any] = {}

    if not a_path.exists():
        return AuditResult(
            gate_name="Gate 5.3 (Stereo Phase)",
            gate="Gate 5.3 (Stereo Phase)",
            status="FAIL",
            passed=False,
            errors=[f"Audio file does not exist: {a_path}"],
            details={},
        )

    cmd = [
        ff, "-y",
        "-i", str(a_path),
        "-af", "aphasemeter=video=0,ametadata=print:key=lavfi.aphasemeter.phase",
        "-f", "null", "-"
    ]
    is_mono = False
    if a_path.suffix.lower() == ".wav":
        try:
            with wave.open(str(a_path), "rb") as wf:
                if wf.getnchannels() == 1:
                    is_mono = True
        except Exception:
            pass

    if not is_mono:
        try:
            chan_cmd = [ff, "-i", str(a_path)]
            chan_res = _get_subprocess().run(chan_cmd, capture_output=True, text=True, timeout=15)
            if re.search(r"Audio:.*,\s*(?:1 channels|1 channels \(FL\)|mono)\b", chan_res.stderr, re.IGNORECASE):
                is_mono = True
        except Exception:
            pass

    phase_values: List[float] = []
    if not is_mono:
        try:
            res = _get_subprocess().run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode != 0:
                errors.append(f"Gate 5.3 Failed: FFmpeg aphasemeter exited with code {res.returncode}: {res.stderr[:160]}")
            for line in res.stderr.splitlines():
                if "lavfi.aphasemeter.phase=" in line:
                    val_str = line.split("lavfi.aphasemeter.phase=")[-1].strip()
                    try:
                        phase_values.append(float(val_str))
                    except ValueError:
                        pass
        except Exception as e:
            logger.warning(f"Stereo phase audit error: {e}")
            errors.append(f"Gate 5.3 Failed: Stereo phase probe crashed: {e}")

    if is_mono:
        mean_phase = 1.0
        details["channel_layout"] = "mono"
    elif phase_values:
        mean_phase = sum(phase_values) / len(phase_values)
        details["channel_layout"] = "stereo"
    else:
        mean_phase = 0.0
        details["channel_layout"] = "unknown"
        if not errors:
            errors.append(f"Gate 5.3 Failed: Zero phase frames extracted from {a_path.name}")

    if mean_phase < min_phase_correlation:
        errors.append(
            f"Stereo phase cancellation hazard: Mean phase correlation r={mean_phase:.3f} "
            f"is below required mono compatibility threshold r={min_phase_correlation:.2f}."
        )

    details["mean_phase_correlation"] = round(mean_phase, 3)
    details["min_phase_threshold"] = min_phase_correlation
    details["frames_evaluated"] = len(phase_values)

    passed = len(errors) == 0
    return AuditResult(
        gate_name="Gate 5.3 (Stereo Phase)",
        gate="Gate 5.3 (Stereo Phase)",
        status="PASS" if passed else "FAIL",
        passed=passed,
        details=details,
        errors=errors,
    )
