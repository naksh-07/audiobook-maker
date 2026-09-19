#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.4: Final M4B Packaging & Chapter Inserter.
Combines mastered chapter audio files, injects FFMETADATA1 chapter markers,
embeds cover art, and writes industry-standard .m4b audiobooks.
"""

import os
import shutil
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any


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
) -> Path:
    """
    Packages all mastered chapters of a project into a single, chapterized .m4b audiobook.
    """
    project_dir = Path(project_dir).resolve()
    mastered_dir = project_dir / "mastered"
    output_dir = project_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    meta_file = project_dir / "metadata.json"
    metadata = {}
    if meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

    title = metadata.get("title", project_dir.name.replace("_", " ").title())
    author = metadata.get("author", "Unknown Author")
    if not output_filename:
        safe_name = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
        output_filename = f"{safe_name}.m4b"

    final_m4b = output_dir / output_filename
    ffmpeg = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"

    # Find mastered audio files
    chapter_audio_files = sorted(mastered_dir.glob("*.m4a")) or sorted(mastered_dir.glob("*.mp3"))
    if not chapter_audio_files:
        raise FileNotFoundError(f"No mastered chapter files found in {mastered_dir}")

    print(f"[*] Packaging {len(chapter_audio_files)} mastered chapters into M4B audiobook...")

    # Calculate timestamps and durations
    chapter_durations = []
    total_ms = 0
    concat_list = output_dir / "m4b_concat.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for idx, cf in enumerate(chapter_audio_files, 1):
            dur_ms = get_audio_duration_ms(cf)
            safe_path = str(cf.resolve()).replace("'", "'\\''")
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

    # Temporary concatenated audio
    temp_concat = output_dir / "temp_full.m4a"
    concat_cmd = [
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(temp_concat),
    ]
    subprocess.run(concat_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Assemble M4B with chapters and cover
    pack_cmd = [
        ffmpeg,
        "-y",
        "-i", str(temp_concat),
        "-i", str(meta_txt),
    ]

    has_cover = cover_image and Path(cover_image).exists()
    if has_cover:
        pack_cmd.extend(["-i", str(cover_image)])
        pack_cmd.extend(["-map", "0:a", "-map", "2:v", "-map_metadata", "1"])
        pack_cmd.extend(["-c:a", "copy", "-c:v", "mjpeg", "-disposition:v", "attached_pic"])
    else:
        pack_cmd.extend(["-map", "0:a", "-map_metadata", "1"])
        pack_cmd.extend(["-c:a", "copy"])

    pack_cmd.append(str(final_m4b))

    try:
        subprocess.run(pack_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        if concat_list.exists():
            concat_list.unlink()
        if temp_concat.exists():
            temp_concat.unlink()

    # Sync to Android shared storage
    shared_out = Path("/storage/emulated/0/Documents/Termux/Audiobooks/output")
    if shared_out.exists() and os.access(shared_out, os.W_OK):
        dest = shared_out / final_m4b.name
        shutil.copy2(final_m4b, dest)
        print(f"[+] Synced to mobile shared storage: {dest}")

    size_mb = round(final_m4b.stat().st_size / (1024 * 1024), 2)
    duration_min = round(total_ms / (1000 * 60), 1)
    print(f"[SUCCESS] Audiobook packaging complete! ({size_mb} MB, {duration_min} mins) -> {final_m4b}")
    return final_m4b
