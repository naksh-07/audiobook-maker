#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.4: Final M4B Packaging & Chapter Inserter.
Combines mastered chapter audio files, injects FFMETADATA1 chapter markers,
embeds cover art, and writes industry-standard .m4b audiobooks.
"""

import os
import re
import shutil
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from audiobook_factory.contracts import BookMasterManifest
from audiobook_factory.gate_auditor import (
    audit_gate6a_voice_continuity,
    audit_gate6b_loudness_continuity,
    audit_gate6c_toc_integrity,
    audit_gate6d_packaging_specs,
    GateAuditError,
)


def get_audio_duration_ms(file_path: Path) -> int:
    """Get exact duration of an audio file in milliseconds via ffprobe."""
    ffprobe = shutil.which("ffprobe") or "/usr/bin/ffprobe"
    cmd = [
        ffprobe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]
    try:
        res = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        sec = float(res.stdout.strip())
        return int(sec * 1000)
    except Exception:
        # Fallback estimation
        return 0


def generate_ffmetadata(
    metadata: Dict[str, Any],
    chapter_durations: List[Dict[str, Any]],
    output_file: Path,
) -> Path:
    """Generate standard FFMETADATA1 file with title, author, and chapter timestamps."""
    lines = [
        ";FFMETADATA1",
        f"title={metadata.get('title', 'Audiobook')}",
        f"artist={metadata.get('author', 'Unknown Author')}",
        f"album_artist={metadata.get('author', 'Unknown Author')}",
        f"album={metadata.get('title', 'Audiobook')}",
        "genre=Audiobook",
        "date=2026",
        "",
    ]

    current_start = 0
    for chap in chapter_durations:
        dur = chap.get("duration_ms", 0)
        end = current_start + dur
        title = chap.get("title", f"Chapter {chap.get('number', 1)}")

        lines.append("[CHAPTER]")
        lines.append("TIMEBASE=1/1000")
        lines.append(f"START={current_start}")
        lines.append(f"END={end}")
        lines.append(f"title={title}")
        lines.append("")

        current_start = end

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_file


def package_m4b_audiobook(
    project_dir: Path,
    output_filename: str | None = None,
    cover_image: Path | None = None,
    manifest: Optional[BookMasterManifest] = None,
    enforce_gate6: bool = False,
) -> Path:
    """
    Packages all mastered chapters of a project into a single, chapterized .m4b audiobook.
    Accepts optional BookMasterManifest, runs Gate 6 pre-flight audit, embeds chapters with +faststart.
    """
    project_dir = Path(project_dir).resolve()
    mastered_dir = project_dir / "mastered"
    output_dir = project_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve manifest if not passed
    if manifest is None:
        m_file = project_dir / "book_master_manifest.json"
        if m_file.exists():
            try:
                manifest = BookMasterManifest.from_file(m_file)
            except Exception as e:
                print(f"[!] Warning: Could not load book_master_manifest.json: {e}")

    meta_file = project_dir / "metadata.json"
    metadata = {}
    if meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

    title = (manifest.title if manifest else None) or metadata.get("title", project_dir.name.replace("_", " ").title())
    author = (manifest.author if manifest else None) or metadata.get("author", "Unknown Author")
    if not cover_image and manifest and manifest.packaging_specs and manifest.packaging_specs.cover_art_path:
        cover_image = manifest.packaging_specs.cover_art_path

    if not output_filename:
        safe_name = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
        output_filename = f"{safe_name}.m4b"

    final_m4b = output_dir / output_filename
    ffmpeg = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"

    # Robust per-chapter resolution: for each chapter, prefer cinematic if available, else mastered
    all_audio = list(mastered_dir.glob("*.m4a")) + list(mastered_dir.glob("*.mp3")) + list(mastered_dir.glob("*.wav"))
    chap_nums = set()
    for f in all_audio:
        m = re.search(r"chapter[_-]?(\d+)", f.name, re.IGNORECASE)
        if m:
            chap_nums.add(int(m.group(1)))

    chapter_audio_files = []
    if chap_nums:
        for c_num in sorted(chap_nums):
            # 1. Prefer cinematic
            candidates = sorted(mastered_dir.glob(f"*chapter_{c_num:03d}*_cinematic.*")) or sorted(mastered_dir.glob(f"*chapter_{c_num}*_cinematic.*"))
            if not candidates:
                # 2. Fall back to mastered
                candidates = sorted(mastered_dir.glob(f"*chapter_{c_num:03d}*_mastered.*")) or sorted(mastered_dir.glob(f"*chapter_{c_num}*_mastered.*"))
            if not candidates:
                # 3. Fall back to any file with chapter number
                candidates = sorted(mastered_dir.glob(f"*chapter_{c_num:03d}.*")) or sorted(mastered_dir.glob(f"*chapter_{c_num}.*"))
            if candidates:
                chapter_audio_files.append(candidates[0])
    else:
        # Fallback to general sorting if no chapter numbers detected
        chapter_audio_files = sorted(mastered_dir.glob("*_cinematic.m4a")) or sorted(mastered_dir.glob("*_mastered.m4a")) or sorted(all_audio)

    if not chapter_audio_files:
        raise FileNotFoundError(f"No mastered chapter files found in {mastered_dir}")

    # Invoke Gate 6 Pre-Flight Audit Suite
    print(f"[*] Macro-Tier Gate 6 Pre-flight Verification Suite...")
    r_6a = audit_gate6a_voice_continuity(project_dir, manifest=manifest)
    r_6b = audit_gate6b_loudness_continuity(chapter_audio_files)
    r_6c = audit_gate6c_toc_integrity(chapter_audio_files, toc=manifest.toc if manifest else None)
    r_6d = audit_gate6d_packaging_specs(cover_image=cover_image, specs=manifest.packaging_specs if manifest else None)

    print(f"  Gate 6A (Voice Continuity)  : {r_6a.status}")
    print(f"  Gate 6B (Loudness Continuity): {r_6b.status}")
    print(f"  Gate 6C (TOC Integrity)      : {r_6c.status}")
    print(f"  Gate 6D (Packaging Specs)    : {r_6d.status}")

    all_passed = all([r_6a.passed, r_6b.passed, r_6c.passed, r_6d.passed])
    if enforce_gate6 and not all_passed:
        all_errs = r_6a.errors + r_6b.errors + r_6c.errors + r_6d.errors
        raise GateAuditError(f"Gate 6 Pre-Flight Audit Failed: {'; '.join(all_errs)}")

    print(f"[*] Packaging {len(chapter_audio_files)} mastered chapters into M4B audiobook...")

    # Calculate timestamps and durations
    chapter_durations = []
    total_ms = 0
    concat_list = output_dir / "m4b_concat.txt"
    is_all_aac = all(f.suffix.lower() in (".m4a", ".aac") for f in chapter_audio_files)

    with open(concat_list, "w", encoding="utf-8") as f:
        for idx, cf in enumerate(chapter_audio_files, 1):
            dur_ms = get_audio_duration_ms(cf)
            safe_path = str(cf.resolve()).replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")

            # Match title from metadata if available
            chap_title = f"Chapter {idx}"
            if "chapters" in metadata and idx - 1 < len(metadata["chapters"]):
                chap_title = metadata["chapters"][idx - 1].get("title", chap_title)

            chapter_durations.append({
                "number": idx,
                "title": chap_title,
                "duration_ms": dur_ms,
            })
            total_ms += dur_ms

    # Generate metadata file
    meta_txt = output_dir / "chapters.txt"
    generate_ffmetadata(metadata, chapter_durations, meta_txt)

    # Assemble M4B directly from concat demuxer with +faststart
    has_cover = cover_image and Path(cover_image).exists()
    audio_codec_args = ["-c:a", "copy"] if is_all_aac else ["-c:a", "aac", "-b:a", "192k"]

    pack_cmd = [
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-i", str(meta_txt),
    ]

    if has_cover:
        pack_cmd.extend(["-i", str(cover_image)])
        pack_cmd.extend(["-map", "0:a", "-map", "2:v", "-map_metadata", "1"])
        pack_cmd.extend(audio_codec_args + ["-c:v", "mjpeg", "-disposition:v", "attached_pic"])
    else:
        pack_cmd.extend(["-map", "0:a", "-map_metadata", "1"])
        pack_cmd.extend(audio_codec_args)

    pack_cmd.extend(["-movflags", "+faststart"])
    pack_cmd.append(str(final_m4b))

    try:
        subprocess.run(pack_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        # Fallback to two-step intermediate concatenation if single-pass demuxer metadata mapping fails
        temp_concat = output_dir / "temp_full.m4a"
        concat_cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list)] + audio_codec_args + [str(temp_concat)]
        subprocess.run(concat_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        fb_pack_cmd = [ffmpeg, "-y", "-i", str(temp_concat), "-i", str(meta_txt)]
        if has_cover:
            fb_pack_cmd.extend(["-i", str(cover_image), "-map", "0:a", "-map", "2:v", "-map_metadata", "1", "-c:a", "copy", "-c:v", "mjpeg", "-disposition:v", "attached_pic"])
        else:
            fb_pack_cmd.extend(["-map", "0:a", "-map_metadata", "1", "-c:a", "copy"])
        fb_pack_cmd.extend(["-movflags", "+faststart"])
        fb_pack_cmd.append(str(final_m4b))
        try:
            subprocess.run(fb_pack_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        finally:
            if temp_concat.exists():
                temp_concat.unlink()
    finally:
        if concat_list.exists():
            concat_list.unlink()

    # Sync to configured output directory or shared storage
    configured_out = os.environ.get("AUDIO_OUTPUT_DIR")
    if configured_out:
        out_target = Path(configured_out).resolve()
        out_target.mkdir(parents=True, exist_ok=True)
        if out_target != final_m4b.parent:
            dest = out_target / final_m4b.name
            shutil.copy2(final_m4b, dest)
            print(f"[+] Synced to output directory: {dest}")

    size_mb = round(final_m4b.stat().st_size / (1024 * 1024), 2)
    duration_min = round(total_ms / (1000 * 60), 1)
    print(f"[SUCCESS] Audiobook packaging complete! ({size_mb} MB, {duration_min} mins) -> {final_m4b}")
    return final_m4b
