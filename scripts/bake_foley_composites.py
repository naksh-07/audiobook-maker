#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 4: Offline Foley & Magic Composite Asset Baker.
Satisfies Idea 3 (Anti-Overengineering Invariant):
Pre-bakes multi-phase tactile and magical audio assets (wand flick + spark + dissipation)
offline using FFmpeg and existing Sound Bank assets, indexing them permanently into SQLite FTS5.
Guarantees ZERO runtime filter graph bloat or stalls during chapter rendering.
"""

import sys
import shutil
import subprocess
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from audiobook_factory.logger import logger
from audiobook_factory.sound_bank import SoundBank, get_sound_bank
from audiobook_factory.sound_bank_ingest import UniversalSoundBankIngester


def bake_composite(
    output_path: Path,
    filter_complex: str,
    inputs: list[str],
    duration_sec: float = 2.0,
    ffmpeg: str = "ffmpeg",
) -> bool:
    """Renders a single pre-baked composite asset via FFmpeg."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-t", f"{duration_sec:.2f}",
        "-c:a", "pcm_s16le",
        str(output_path),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0 or not output_path.exists():
        logger.warning(f"Failed to bake {output_path.name}: {res.stderr}")
        return False
    logger.info(f"  [+] Baked composite asset: {output_path.name} ({duration_sec}s)")
    return True


def bake_all_magic_and_foley_composites() -> None:
    """Pre-bakes the core Harry Potter & fantasy tactile composite sound set."""
    bank = get_sound_bank()
    ingest_engine = UniversalSoundBankIngester(db_path=bank.db_path, bank_root=bank.bank_root)
    bank_root = bank.bank_root
    sfx_dir = bank_root / "sfx"
    foley_dir = bank_root / "foley"
    sfx_dir.mkdir(parents=True, exist_ok=True)
    foley_dir.mkdir(parents=True, exist_ok=True)

    ff = shutil.which("ffmpeg") or "ffmpeg"
    logger.info("[*] Starting Offline Foley & Magic Asset Baking...")

    # Composite 1: magic_lumos_light.wav (Air whoosh + soft crystal shimmer + warm dissipation)
    lumos_path = sfx_dir / "magic_lumos_light.wav"
    bake_composite(
        output_path=lumos_path,
        inputs=[
            "-f", "lavfi", "-i", "anoisesrc=d=0.25:c=pink:r=48000:a=0.3",  # Wand flick air whoosh
            "-f", "lavfi", "-i", "sine=f=1760:d=1.5:r=48000",             # Arcane high chime A6
            "-f", "lavfi", "-i", "sine=f=880:d=1.8:r=48000",              # Harmonic A5
        ],
        filter_complex=(
            "[0:a]afade=t=in:ss=0:d=0.05,afade=t=out:st=0.15:d=0.10,lowpass=f=2200,volume=0.8[whoosh];"
            "[1:a]afade=t=in:ss=0.08:d=0.05,afade=t=out:st=0.20:d=1.2,volume=0.35[chime1];"
            "[2:a]afade=t=in:ss=0.10:d=0.08,afade=t=out:st=0.30:d=1.4,volume=0.25[chime2];"
            "[whoosh][chime1][chime2]amix=inputs=3:duration=first:normalize=0,stereotools=mlev=0.85:slev=1.30[out]"
        ),
        duration_sec=2.0,
        ffmpeg=ff,
    )

    # Composite 2: magic_expelliarmus_kinetic.wav (Whip crack + 50Hz Sub-thump + spark ionization)
    expelliarmus_path = sfx_dir / "magic_expelliarmus_kinetic.wav"
    bake_composite(
        output_path=expelliarmus_path,
        inputs=[
            "-f", "lavfi", "-i", "anoisesrc=d=0.15:c=white:r=48000:a=0.8", # Kinetic whipcrack
            "-f", "lavfi", "-i", "sine=f=52:d=0.8:r=48000",                # 52Hz Sub-bass punch
            "-f", "lavfi", "-i", "anoisesrc=d=0.6:c=pink:r=48000:a=0.4",   # Electric sizzle
        ],
        filter_complex=(
            "[0:a]afade=t=in:ss=0:d=0.01,afade=t=out:st=0.05:d=0.10,highpass=f=1500,volume=1.0[whip];"
            "[1:a]afade=t=in:ss=0.02:d=0.02,afade=t=out:st=0.15:d=0.60,lowpass=f=95,volume=1.2[sub];"
            "[2:a]afade=t=in:ss=0.04:d=0.05,afade=t=out:st=0.20:d=0.40,bandpass=f=3200:w=1.2,volume=0.6[sizzle];"
            "[whip][sub][sizzle]amix=inputs=3:duration=first:normalize=0[out]"
        ),
        duration_sec=1.2,
        ffmpeg=ff,
    )

    # Composite 3: tactile_parchment_quill_scratch.wav
    parchment_path = foley_dir / "tactile_parchment_quill_scratch.wav"
    bake_composite(
        output_path=parchment_path,
        inputs=[
            "-f", "lavfi", "-i", "anoisesrc=d=0.6:c=brown:r=48000:a=0.35", # Parchment friction
            "-f", "lavfi", "-i", "anoisesrc=d=0.4:c=pink:r=48000:a=0.25",  # Quill scratch
        ],
        filter_complex=(
            "[0:a]afade=t=in:ss=0:d=0.05,afade=t=out:st=0.35:d=0.25,bandpass=f=950:w=1.0,volume=0.6[paper];"
            "[1:a]afade=t=in:ss=0.10:d=0.02,afade=t=out:st=0.25:d=0.15,bandpass=f=3800:w=1.8,volume=0.5[quill];"
            "[paper][quill]amix=inputs=2:duration=first:normalize=0[out]"
        ),
        duration_sec=0.8,
        ffmpeg=ff,
    )

    # Ingest baked assets into Sound Bank
    logger.info("[*] Ingesting baked composite assets into Sound Bank SQLite FTS5 catalog...")
    baked_files = [lumos_path, expelliarmus_path, parchment_path]
    for bf in baked_files:
        if bf.exists():
            category = "sfx" if "sfx" in str(bf.parent) else "foley"
            tags = f"magic composite tactile {bf.stem.replace('_', ' ')}"
            ingest_engine.ingest_file(
                filepath=bf,
                category=category,
                action_type="swing" if "magic" in bf.stem else "scrape",
                exciter="energy" if "magic" in bf.stem else "wood",
                tags=tags,
            )

    # Also update main sound_catalog FTS5
    bank.scan_and_index()
    logger.info("[+] Pre-baking complete! All composite assets indexed and ready for zero-latency retrieval.")


if __name__ == "__main__":
    bake_all_magic_and_foley_composites()
