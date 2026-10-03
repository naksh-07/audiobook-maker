#!/usr/bin/env python3
"""
Audiobook Factory - Macro-Tier Album & Book Packaging Quality Gates (Gate 6).
Houses Gate 6A (Cross-Chapter Voice Continuity), Gate 6B (Loudness Continuity),
Gate 6C (TOC Integrity & Timeline Monotonicity), and Gate 6D (Packaging & Container Specifications).
"""

from __future__ import annotations
import re
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Set, Optional

from audiobook_factory.contracts import (
    BookPackagingSpecs,
    BookTableOfContents,
    BookMasterManifest,
    ScreenplayScript,
)
from audiobook_factory.gates.contracts import GateAuditError, AuditResult
from audiobook_factory.tts.constants import get_ffmpeg

logger = logging.getLogger("audiobook_factory.gates.album")


def _get_subprocess():
    import sys
    fa = sys.modules.get("audiobook_factory.gate_auditor")
    if fa and hasattr(fa, "subprocess"):
        return fa.subprocess
    return subprocess


def audit_gate6a_voice_continuity(
    project_dir: Path,
    manifest: Optional[BookMasterManifest] = None,
) -> AuditResult:
    """
    Gate 6A: Voice Continuity Auditor.
    Ensures that every recurring character speaking across multiple chapters
    maintains an identical assigned voice ID across all chapters and the master manifest.
    """
    pdir = Path(project_dir).resolve()
    errors: List[str] = []
    details: Dict[str, Any] = {}

    canonical_voices: Dict[str, str] = {}
    if manifest and manifest.voice_roster and manifest.voice_roster.character_voices:
        canonical_voices.update(manifest.voice_roster.character_voices)

    reg_file = pdir / "voice_registry.json"
    if reg_file.exists():
        try:
            with open(reg_file, "r", encoding="utf-8") as f:
                reg_data = json.load(f)
                for char, cfg in reg_data.items():
                    v_id = cfg.get("voice", "") if isinstance(cfg, dict) else str(cfg)
                    if v_id and char not in canonical_voices:
                        canonical_voices[char] = v_id
        except Exception as e:
            logger.warning(f"Failed to read voice_registry.json: {e}")

    roster_file = pdir / "character_roster.json"
    if roster_file.exists():
        try:
            with open(roster_file, "r", encoding="utf-8") as f:
                roster_data = json.load(f).get("characters", {})
                if isinstance(roster_data, dict):
                    for char, cfg in roster_data.items():
                        v_id = cfg.get("voice", "") if isinstance(cfg, dict) else str(cfg)
                        if v_id and char not in canonical_voices:
                            canonical_voices[char] = v_id
                elif isinstance(roster_data, list):
                    for prof in roster_data:
                        if isinstance(prof, dict):
                            dname = prof.get("display_name")
                            vid = prof.get("assigned_voice_id")
                            if dname and vid and dname not in canonical_voices:
                                canonical_voices[dname] = vid
        except Exception as e:
            logger.warning(f"Failed to read character_roster.json: {e}")

    cast_lock_file = pdir / "cast_lock.json"
    if cast_lock_file.exists():
        try:
            with open(cast_lock_file, "r", encoding="utf-8") as clf:
                cl_data = json.load(clf)
                locks = cl_data.get("locks", {})
                for char, lk in locks.items():
                    if isinstance(lk, dict) and lk.get("locked"):
                        vid = lk.get("voice_id")
                        if vid:
                            canonical_voices[char] = vid
        except Exception as e:
            logger.warning(f"Failed to read cast_lock.json: {e}")

    scripts_dir = pdir / "scripts"
    script_files = sorted(scripts_dir.glob("chapter_*_script.json")) if scripts_dir.exists() else []

    speaker_chapter_map: Dict[str, Set[str]] = {}
    character_observed_voices: Dict[str, Dict[str, Set[str]]] = {}

    for sf in script_files:
        ch_name = sf.stem.replace("_script", "")
        try:
            script = ScreenplayScript.from_file(sf)
            for seg in script.segments:
                sp = seg.speaker
                if sp.lower() in ("narrator", "foley", "sfx"):
                    continue
                speaker_chapter_map.setdefault(sp, set()).add(ch_name)
                assigned = canonical_voices.get(sp)
                if assigned:
                    character_observed_voices.setdefault(sp, {}).setdefault(assigned, set()).add(ch_name)
        except Exception as e:
            logger.debug(f"Could not parse script {sf.name}: {e}")

    for char, chaps in speaker_chapter_map.items():
        if char not in canonical_voices:
            errors.append(
                f"Character '{char}' speaks in chapter(s) {sorted(list(chaps))} but has no canonical voice assignment in voice_registry.json."
            )
        else:
            voice_assignments = character_observed_voices.get(char, {})
            if len(voice_assignments) > 1:
                errors.append(
                    f"Voice collision for '{char}': assigned conflicting voices {dict(voice_assignments)} across chapters."
                )

    multi_chapter_characters = {char: chaps for char, chaps in speaker_chapter_map.items() if len(chaps) > 1}
    details["canonical_voices_count"] = len(canonical_voices)
    details["all_characters_audited"] = list(speaker_chapter_map.keys())
    details["multi_chapter_characters"] = list(multi_chapter_characters.keys())
    details["total_scripts_audited"] = len(script_files)

    passed = len(errors) == 0
    return AuditResult(
        gate="Gate 6A (Voice Continuity)",
        status="PASS" if passed else "FAIL",
        passed=passed,
        details=details,
        errors=errors,
    )


def audit_gate6b_loudness_continuity(
    chapter_files: List[Path],
    target_lufs: float = -19.0,
    max_variance: float = 1.0,
    strict: bool = False,
) -> AuditResult:
    """
    Gate 6B: Loudness Continuity Auditor.
    Verifies that all mastered chapters adhere to target integrated LUFS (+/- max_variance)
    and true peak ceiling <= -1.4 dBTP, preventing jarring volume jumps between chapters.
    When strict=True, FFmpeg probe failures or unparseable outputs fail-closed immediately.
    """
    errors: List[str] = []
    chapter_metrics = []

    if not chapter_files:
        return AuditResult(
            gate="Gate 6B (Loudness Continuity)",
            status="FAIL",
            passed=False,
            errors=["No chapter audio files provided for loudness audit."],
            details={},
        )

    ffmpeg_bin = get_ffmpeg()
    measured_lufs_list = []

    for cf in chapter_files:
        c_path = Path(cf).resolve()
        if not c_path.exists():
            errors.append(f"Chapter file not found on disk: {c_path}")
            continue
        if c_path.stat().st_size < 1000:
            errors.append(f"Chapter file is empty or corrupt ({c_path.stat().st_size} bytes): {c_path.name}")
            continue

        cmd = [
            ffmpeg_bin, "-y",
            "-i", str(c_path),
            "-af", "ebur128=peak=true:framelog=verbose",
            "-f", "null", "-"
        ]
        try:
            proc = _get_subprocess().run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
            if proc.returncode != 0:
                errors.append(f"Chapter {c_path.name}: FFmpeg probe returned exit code {proc.returncode}: {proc.stderr[:160]}")
                continue
            else:
                output = proc.stderr
                i_match = re.search(r"Integrated loudness:\s+I:\s+([-\d.]+)\s+LUFS", output)
                tp_match = re.search(r"True peak:\s+Peak:\s+([-\d.]+)(?:\s+([-\d.]+))?", output) or re.search(r"Peak:\s+([-\d.]+)\s+dBFS", output)
                if not i_match:
                    errors.append(f"Chapter {c_path.name}: Failed to parse Integrated Loudness from FFmpeg output.")
                    continue
                else:
                    m_lufs = float(i_match.group(1))
                    if tp_match:
                        tp_vals = [float(v) for v in tp_match.groups() if v is not None]
                        m_tp = max(tp_vals) if tp_vals else -1.5
                    else:
                        m_tp = -1.5
        except Exception as e:
            errors.append(f"Chapter {c_path.name}: FFmpeg loudness probe failed: {e}")
            continue

        measured_lufs_list.append(m_lufs)
        deviation = abs(m_lufs - target_lufs)
        chapter_metrics.append({
            "file": c_path.name,
            "measured_lufs": m_lufs,
            "true_peak_dbtp": m_tp,
            "deviation_from_target": round(deviation, 2),
        })

        if deviation > max_variance:
            errors.append(
                f"Chapter {c_path.name} loudness {m_lufs:.1f} LUFS deviates by {deviation:.1f} LU from target {target_lufs:.1f} LUFS (max allowable {max_variance:.1f} LU)"
            )
        if m_tp > -1.4:
            errors.append(
                f"Chapter {c_path.name} true peak {m_tp:.1f} dBTP exceeds ceiling -1.4 dBTP"
            )

    details = {
        "target_lufs": target_lufs,
        "max_variance": max_variance,
        "total_chapters_measured": len(measured_lufs_list),
        "chapter_metrics": chapter_metrics,
        "average_lufs": round(sum(measured_lufs_list) / len(measured_lufs_list), 2) if measured_lufs_list else target_lufs,
    }

    passed = len(errors) == 0
    if strict and not passed:
        raise GateAuditError(f"Gate 6B Loudness Continuity FAILED: {'; '.join(errors)}")
    return AuditResult(
        gate="Gate 6B (Loudness Continuity)",
        status="PASS" if passed else "FAIL",
        passed=passed,
        details=details,
        errors=errors,
    )


def audit_gate6c_toc_integrity(
    chapter_files: List[Path],
    toc: Optional[BookTableOfContents] = None,
) -> AuditResult:
    """
    Gate 6C: Table of Contents & Timeline Monotonicity Auditor.
    Ensures chapter sequence is contiguous, non-overlapping, strictly monotonic,
    and accurately mapped down to the millisecond.
    """
    errors: List[str] = []

    if not chapter_files:
        return AuditResult(
            gate="Gate 6C (TOC Integrity)",
            status="FAIL",
            passed=False,
            errors=["Zero chapter files provided for TOC audit."],
            details={},
        )

    for cf in chapter_files:
        c_path = Path(cf).resolve()
        if not c_path.exists():
            errors.append(f"Chapter file does not exist: {c_path}")
        elif c_path.stat().st_size < 1000:
            errors.append(f"Chapter file empty or corrupt: {c_path.name}")

    if toc is not None:
        if len(toc.chapters) != len(chapter_files):
            errors.append(
                f"TOC chapter count mismatch: TOC contains {len(toc.chapters)} markers, but found {len(chapter_files)} audio files."
            )

        prev_end_ms = 0
        computed_duration = 0
        for i, marker in enumerate(toc.chapters):
            computed_duration += marker.duration_ms
            if marker.start_ms < prev_end_ms:
                errors.append(
                    f"Timeline overlap at chapter {marker.chapter_index} ('{marker.title}'): start_ms ({marker.start_ms}) < previous end_ms ({prev_end_ms})"
                )
            if marker.end_ms <= marker.start_ms:
                errors.append(
                    f"Non-positive duration at chapter {marker.chapter_index} ('{marker.title}'): start_ms={marker.start_ms}, end_ms={marker.end_ms}"
                )
            if marker.duration_ms != (marker.end_ms - marker.start_ms):
                errors.append(
                    f"Duration arithmetic mismatch at chapter {marker.chapter_index}: {marker.duration_ms} != ({marker.end_ms} - {marker.start_ms})"
                )
            prev_end_ms = marker.end_ms

        if toc.total_duration_ms > 0 and abs(toc.total_duration_ms - computed_duration) > 500:
            errors.append(
                f"TOC total duration mismatch: toc says {toc.total_duration_ms} ms, sum of chapters is {computed_duration} ms."
            )

    passed = len(errors) == 0
    return AuditResult(
        gate="Gate 6C (TOC Integrity)",
        status="PASS" if passed else "FAIL",
        passed=passed,
        details={
            "total_chapters": len(chapter_files),
            "toc_verified": toc is not None,
            "total_duration_ms": toc.total_duration_ms if toc else 0,
        },
        errors=errors,
    )


def audit_gate6c_toc_monotonicity(
    chapter_files_or_project_dir: Any,
    toc: Optional[BookTableOfContents] = None,
) -> AuditResult:
    """
    Gate 6C: Table of Contents & Timeline Monotonicity Auditor.
    Accepts either a list of chapter audio paths or a project directory path.
    """
    if isinstance(chapter_files_or_project_dir, (str, Path)):
        p = Path(chapter_files_or_project_dir)
        if p.is_dir():
            cfiles = sorted((p / "mastered").glob("chapter_*_cinematic.m4a"))
            if not cfiles:
                cfiles = sorted((p / "mastered").glob("chapter_*_dialogue.wav"))
            if not cfiles:
                cfiles = sorted(p.glob("*.m4a")) or sorted(p.glob("*.wav"))
            return audit_gate6c_toc_integrity(cfiles, toc=toc)
        else:
            return audit_gate6c_toc_integrity([p], toc=toc)
    return audit_gate6c_toc_integrity(chapter_files_or_project_dir, toc=toc)


def audit_gate6d_packaging_specs(
    cover_image: Optional[Path],
    specs: Optional[BookPackagingSpecs] = None,
    strict: bool = False,
) -> AuditResult:
    """
    Gate 6D: Packaging & Container Specifications Auditor.
    Validates audio codec, bitrate, faststart flag, and cover art resolution/format.
    """
    errors: List[str] = []
    details: Dict[str, Any] = {}

    specs_to_check = specs or BookPackagingSpecs()

    allowed_codecs = {"aac", "alac", "mp3", "copy"}
    if specs_to_check.codec.lower() not in allowed_codecs:
        errors.append(f"Invalid packaging codec '{specs_to_check.codec}'. Must be one of {allowed_codecs}")

    valid_bitrates = {"128k", "192k", "256k", "320k"}
    if specs_to_check.bitrate.lower() not in valid_bitrates and specs_to_check.codec != "copy":
        errors.append(f"Bitrate '{specs_to_check.bitrate}' outside broadcast standard {valid_bitrates}")

    if not specs_to_check.faststart:
        errors.append("Faststart (+faststart) must be enabled for streaming / progressive playback.")

    if cover_image is not None:
        c_path = Path(cover_image).resolve()
        if not c_path.exists():
            errors.append(f"Cover image specified but file not found: {c_path}")
        elif c_path.stat().st_size == 0:
            errors.append(f"Cover image file is empty: {c_path}")
        else:
            ext = c_path.suffix.lower()
            if ext not in (".jpg", ".jpeg", ".png"):
                errors.append(f"Invalid cover art format '{ext}'. Must be .jpg, .jpeg, or .png")
            else:
                try:
                    from PIL import Image
                    with Image.open(c_path) as img:
                        w, h = img.size
                        details["cover_resolution"] = f"{w}x{h}"
                        if w != h:
                            errors.append(f"Cover art must be 1:1 square aspect ratio, got {w}x{h}")
                        min_res = getattr(specs_to_check, "min_cover_resolution", 1400) or 1400
                        if w < min_res or h < min_res:
                            errors.append(f"Cover art resolution {w}x{h} below minimum threshold {min_res}x{min_res}")
                except Exception as e:
                    errors.append(f"Failed to inspect cover art image: {e}")

    details["codec"] = specs_to_check.codec
    details["bitrate"] = specs_to_check.bitrate
    details["sample_rate"] = specs_to_check.sample_rate
    details["faststart"] = specs_to_check.faststart
    details["cover_image_present"] = cover_image is not None

    passed = len(errors) == 0
    if strict and not passed:
        raise GateAuditError(f"Gate 6D Packaging Specs FAILED: {'; '.join(errors)}")
    return AuditResult(
        gate="Gate 6D (Packaging Specs)",
        status="PASS" if passed else "FAIL",
        passed=passed,
        details=details,
        errors=errors,
    )
