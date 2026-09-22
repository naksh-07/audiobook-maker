#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 6 Screenplay Parser Runner.
Processes Chapter 6 ('The Lesser Evil') in semantic chunks with rolling context,
retaining 100% text, attributing dialogue to canon characters, and assigning
rich audio drama metadata.
"""

import sys
import json
import time
import logging
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from audiobook_factory.script_builder import (
    _parse_dramatized_chunk_llm,
    clean_screenplay_pass2,
    build_narrator_script,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_ch6_screenplay")

CHARACTER_ROSTER = {
    "characters": {
        "Geralt": {"gender": "male", "aliases": ["गेराल्ट", "रिविया का गेराल्ट", "विचर"]},
        "Narrator": {"gender": "neutral", "aliases": ["कथावाचक"]},
        "Caldemeyn": {"gender": "male", "aliases": ["काल्डेमेन", "कैल्डेमेन", "मुखिया"]},
        "Stregobor": {"gender": "male", "aliases": ["स्ट्रेगोबोर", "मास्टर इरिअन", "इरिअन", "जादूगर"]},
        "Renfri": {"gender": "female", "aliases": ["रेनफ़्री", "रेनफ्री", "श्राईक", "राजकुमारी"]},
        "Marilka": {"gender": "female", "aliases": ["मारिल्का"]},
        "Nohorn": {"gender": "male", "aliases": ["नोहॉर्न"]},
        "Civril": {"gender": "male", "aliases": ["सिव्रिल"]},
        "Libushe": {"gender": "female", "aliases": ["लिबुशे"]},
    }
}


def main():
    hi_file = root_dir / "audiobooks" / "projects" / "witcher1" / "translation" / "chapter_006_hi.md"
    out_file = root_dir / "audiobooks" / "projects" / "witcher1" / "scripts" / "chapter_006_hi_script.json"
    cache_file = root_dir / "audiobooks" / "projects" / "witcher1" / "scripts" / "chapter_006_raw_chunks_cache.json"

    logger.info(f"Reading Hindi chapter text from {hi_file}...")
    with open(hi_file, "r", encoding="utf-8") as f:
        full_text = f.read().strip()

    # Split on double newlines
    paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
    logger.info(f"Total paragraphs in chapter: {len(paragraphs)}")

    # Chunk into semantic ~1,000 word blocks
    chunks = []
    cur = []
    cur_words = 0
    for p in paragraphs:
        # Avoid breaking on Act headings
        w = len(p.split())
        cur.append(p)
        cur_words += w
        if cur_words >= 900:
            chunks.append("\n\n".join(cur))
            cur = []
            cur_words = 0
    if cur:
        chunks.append("\n\n".join(cur))

    logger.info(f"Divided chapter into {len(chunks)} semantic chunks for LLM parsing.")

    # Load cache if partially processed
    cached_items_by_chunk = {}
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_items_by_chunk = json.load(f)
            logger.info(f"Loaded existing checkpoint with {len(cached_items_by_chunk)}/{len(chunks)} chunks.")
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}. Starting fresh.")

    all_raw_items = []
    rolling_context = ""

    for idx, chunk_str in enumerate(chunks, 1):
        idx_str = str(idx)
        if idx_str in cached_items_by_chunk:
            logger.info(f"[{idx}/{len(chunks)}] Loading chunk from checkpoint cache ({len(cached_items_by_chunk[idx_str])} items)...")
            chunk_items = cached_items_by_chunk[idx_str]
        else:
            logger.info(f"[{idx}/{len(chunks)}] Parsing chunk ({len(chunk_str)} chars, ~{len(chunk_str.split())} words)...")
            chunk_items = _parse_dramatized_chunk_llm(
                chunk_text=chunk_str,
                preceding_context=rolling_context,
                is_hindi=True,
                character_roster=CHARACTER_ROSTER,
                model="gemini-flash-lite-latest",
                max_retries=4,
            )
            if not chunk_items:
                logger.warning(f"  [!] Fallback to narrator script for chunk {idx}")
                chunk_items = build_narrator_script(chunk_str, is_hindi=True)

            cached_items_by_chunk[idx_str] = chunk_items
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cached_items_by_chunk, f, ensure_ascii=False, indent=2)

        all_raw_items.extend(chunk_items)
        recent_speakers = [it.get("speaker", "Narrator") for it in chunk_items[-2:]]
        rolling_context = f"Scene chunk {idx} ended with speakers: {', '.join(recent_speakers)}."

    logger.info(f"Assembled {len(all_raw_items)} raw screenplay items. Running Alexandria Pass 2 cleanup...")
    cleaned_script = clean_screenplay_pass2(
        all_raw_items,
        is_hindi=True,
        character_roster=CHARACTER_ROSTER,
    )

    logger.info(f"Cleaned screenplay generated: {len(cleaned_script)} final segments.")

    # Speaker distribution stats
    speakers = {}
    for s in cleaned_script:
        spk = s.get("speaker", "Unknown")
        speakers[spk] = speakers.get(spk, 0) + 1
    for spk, count in sorted(speakers.items(), key=lambda x: -x[1]):
        logger.info(f"  - {spk}: {count} segments")

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(cleaned_script, f, ensure_ascii=False, indent=2)

    logger.info(f"[+] Screenplay written to {out_file} successfully!")


if __name__ == "__main__":
    main()
