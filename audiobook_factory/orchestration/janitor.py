"""
Audiobook Factory - Chapter Janitor.
Handles safe retention and cleanup of intermediate uncompressed WAV chunks.
"""

from pathlib import Path
import os
from audiobook_factory.logger import logger


def cleanup_chapter_chunks(
    audio_dir: Path,
    chapter_num: int,
    cinematic_out: Path,
    all_gates_certified: bool,
) -> None:
    """
    Cleans up intermediate uncompressed WAV chunks ONLY IF certified.
    Safety Invariant: Chunks are NEVER purged if cinematic master failed, is corrupt,
    if any Gate 5.x check failed, or unless PURGE_INTERMEDIATE_CHUNKS=true is explicitly set.
    By default, chunks are preserved for zero-cost DSP remastering without burning TTS quota.
    """
    purge_chunks_flag = os.environ.get("AUDIOBOOK_PURGE_CHUNKS", "false").lower() in ("1", "true", "yes")

    chunk_pattern = f"c{chapter_num:03d}_*.wav"
    all_chunks = list(audio_dir.glob(chunk_pattern))

    if not purge_chunks_flag:
        logger.info(f"  [JANITOR SHIELD] Retaining {len(all_chunks)} raw WAV chunks for chapter {chapter_num:02d} (Zero-cost remaster shield default).")
    elif not all_gates_certified:
        logger.warning(
            f"  [JANITOR SHIELD] Master render uncertified or Gate 5/5.2/5.3 failed for chapter {chapter_num:02d}. "
            f"Retaining {len(all_chunks)} raw WAV chunks to protect synthesized progress."
        )
    else:
        purged_count = 0
        for chunk_file in all_chunks:
            try:
                chunk_file.unlink(missing_ok=True)
                purged_count += 1
            except Exception:
                pass
        if purged_count:
            logger.info(f"  [JANITOR] Purged {purged_count} intermediate WAV chunks for chapter {chapter_num:02d}")
