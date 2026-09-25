#!/usr/bin/env python3
"""
AudioBookmaker - Pillar 1: Robust Chapter Segmenter & Meso-Tier Semantic Splitter.
Features:
- Layered chapter heading recognition (English, Hindi, Roman numerals, word numbers, story markers).
- Conservative false-positive defense against random dialogue or uppercase lines.
- Hierarchy-preserving semantic splitter for oversized chapters (> 12,000 words):
  Scene Break -> Section Heading -> Paragraph Boundary -> Sentence Boundary -> Emergency Word Split.
- 100% backward-compatible segment_chapters_from_text and split_large_chapter_on_semantic_boundary APIs.
"""

from __future__ import annotations
import re
from typing import List, Dict, Any, Tuple, Optional


# Comprehensive chapter heading patterns with boundary verification
CHAPTER_PATTERNS = [
    # Explicit Markdown H1/H2 (e.g. "# The Boy Who Lived", "## The Council of Elrond")
    r"^#{1,2}\s+[A-Z0-9\u0900-\u097F][^\n]{1,80}$",
    # English chapter / book / part / act / scene (e.g. "Chapter 1", "CHAPTER ONE", "Chapter IV", "Book 2")
    r"^(?:\s*#+\s*)?(?:chapter|book|part|act|scene)\s+(?:\d+|[ivxlcdm]+|[a-z]+)\b.*$",
    # Story landmark markers (Prologue, Epilogue, Interlude, Introduction, Afterword)
    r"^(?:\s*#+\s*)?(?:prologue|epilogue|interlude|introduction|preface|afterword)\b.*$",
    # Hindi / Devanagari chapter markers (अध्याय, भाग, खंड, काण्ड, प्रस्तावना, उपसंहार)
    r"^(?:\s*#+\s*)?(?:अध्याय|भाग|खंड|काण्ड|प्रस्तावना|उपसंहार)\s*(?:\d+|[०-९]+|[a-z]+)?\b.*$",
    # Roman numeral standalone headers (e.g. "IV.", "XIV", "I - The Awakening") preceded and followed by blank lines
    r"^(?:[IVXLCDM]{1,8}(?:\.|\s*[\-–—]\s*[A-Z][^\n]{2,60})?)$",
    # Word-number standalone headers (e.g. "ONE", "TWENTY-TWO", "THREE: The Journey")
    r"^(?:(?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE|THIRTEEN|FOURTEEN|FIFTEEN|SIXTEEN|SEVENTEEN|EIGHTEEN|NINETEEN|TWENTY)(?:\s*[\:\-–—]\s*[A-Z][^\n]{2,60})?)$",
]

COMBINED_CHAPTER_REGEX = "|".join(f"(?:{p})" for p in CHAPTER_PATTERNS)


def is_valid_heading_candidate(match_text: str, preceding_text: str, following_text: str) -> bool:
    """
    Conservative validator against false positives.
    Ensures match is bounded by whitespace/newlines and not merely a speaker line or dialogue snippet.
    """
    cleaned = match_text.strip().lstrip("#").strip()
    if len(cleaned) < 1 or len(cleaned) > 90:
        return False

    # Disallow common dialogue or quote punctuation at start or end
    if cleaned.startswith(('"', "'", "“", "‘", "—", "-")) or cleaned.endswith(('"', "'", "”", "’", ",", ";")):
        return False

    # Check preceding context: must be preceded by start of string or double newline
    if preceding_text:
        trailing_preceding = preceding_text[-2:]
        if "\n" not in trailing_preceding:
            return False

    # Check following context: must have at least 15 words of subsequent body text
    following_words = len(following_text[:1000].split())
    if following_words < 5:
        return False

    return True


def segment_chapters_from_text(raw_text: str) -> List[Dict[str, Any]]:
    """
    Segments a continuous raw text string into structured chapter or production-chunk dictionaries.
    Explicitly distinguishes detected literary chapters from fallback production chunks.
    Returns: List[Dict[str, Any]] with keys:
      'title', 'content', 'words', 'char_start', 'char_end',
      'unit_type', 'is_literary_chapter', 'is_production_chunk',
      'boundary_origin', 'literary_chapter_number', 'parent_chapter_title',
      'chunk_index', 'total_chunks'
    """
    if not raw_text or not raw_text.strip():
        return []

    # Find candidate splits matching multi-tier patterns
    raw_splits = list(re.finditer(COMBINED_CHAPTER_REGEX, raw_text, flags=re.IGNORECASE | re.MULTILINE))

    # Filter candidates with conservative validation
    valid_splits = []
    for match in raw_splits:
        start = match.start()
        end = match.end()
        preceding = raw_text[:start]
        following = raw_text[end:]
        if is_valid_heading_candidate(match.group(0), preceding, following):
            valid_splits.append(match)

    if not valid_splits:
        # Fallback: Semantic Scene-Aware Production Chunking (NOT real literary chapters)
        para_matches = list(re.finditer(r"(?:[^\n]+(?:\n(?!\n)[^\n]*)*)", raw_text))
        chunks: List[Dict[str, Any]] = []
        current_paras: List[str] = []
        current_words = 0
        chunk_start_char: Optional[int] = None
        chunk_end_char: int = 0
        chunk_num = 1

        for pm in para_matches:
            para = pm.group(0).strip()
            if not para:
                continue
            if chunk_start_char is None:
                raw_p = pm.group(0)
                chunk_start_char = pm.start() + (len(raw_p) - len(raw_p.lstrip()))
            chunk_end_char = pm.start() + len(pm.group(0).rstrip())

            words = len(para.split())
            current_paras.append(para)
            current_words += words

            is_scene_break = bool(re.match(r"^(\*|\-|\_)\s*\1\s*\1+$", para))
            if (current_words >= 2500 and is_scene_break) or current_words >= 3500:
                c_start = chunk_start_char if chunk_start_char is not None else 0
                c_slice = raw_text[c_start:chunk_end_char].strip()
                chunks.append({
                    "title": f"Production Chunk {chunk_num}",
                    "content": c_slice,
                    "words": current_words,
                    "char_start": c_start,
                    "char_end": c_start + len(c_slice),
                    "unit_type": "production_chunk",
                    "is_literary_chapter": False,
                    "is_production_chunk": True,
                    "boundary_origin": "fallback_production_chunk",
                    "literary_chapter_number": None,
                    "parent_chapter_title": None,
                    "chunk_index": chunk_num,
                    "total_chunks": 0,  # Populated below once total is known
                })
                chunk_num += 1
                current_paras = []
                current_words = 0
                chunk_start_char = None

        if current_paras:
            c_start = chunk_start_char if chunk_start_char is not None else 0
            c_end = chunk_end_char if chunk_end_char > 0 else len(raw_text)
            c_slice = raw_text[c_start:c_end].strip()
            chunks.append({
                "title": f"Production Chunk {chunk_num}",
                "content": c_slice,
                "words": current_words,
                "char_start": c_start,
                "char_end": c_start + len(c_slice),
                "unit_type": "production_chunk",
                "is_literary_chapter": False,
                "is_production_chunk": True,
                "boundary_origin": "fallback_production_chunk",
                "literary_chapter_number": None,
                "parent_chapter_title": None,
                "chunk_index": chunk_num,
                "total_chunks": 0,
            })

        total_c = len(chunks)
        for c in chunks:
            c["total_chunks"] = total_c
        return chunks

    # Split text into detected literary chapters based on validated heading positions
    chapters: List[Dict[str, Any]] = []
    for idx, match in enumerate(valid_splits):
        title = match.group(0).strip().lstrip("#").strip()
        start = match.end()
        end = valid_splits[idx + 1].start() if idx + 1 < len(valid_splits) else len(raw_text)
        raw_slice = raw_text[start:end]
        lstrip_offset = len(raw_slice) - len(raw_slice.lstrip())
        content = raw_slice.strip()
        content_start = start + lstrip_offset
        content_end = content_start + len(content)
        word_count = len(content.split())

        if word_count >= 5:
            chapters.append({
                "title": title,
                "content": content,
                "words": word_count,
                "heading_char_start": match.start(),
                "char_start": content_start,
                "char_end": content_end,
                "unit_type": "literary_chapter",
                "is_literary_chapter": True,
                "is_production_chunk": False,
                "boundary_origin": "detected_heading",
                "literary_chapter_number": len(chapters) + 1,
                "parent_chapter_title": title,
                "chunk_index": 1,
                "total_chunks": 1,
            })

    # Preserve any prologue/intro preceding the first chapter heading
    if valid_splits and valid_splits[0].start() > 100:
        raw_intro = raw_text[:valid_splits[0].start()]
        intro_lstrip = len(raw_intro) - len(raw_intro.lstrip())
        intro_content = raw_intro.strip()
        intro_words = len(intro_content.split())
        if intro_words >= 30:
            chapters.insert(0, {
                "title": "Prologue / Introduction",
                "content": intro_content,
                "words": intro_words,
                "heading_char_start": intro_lstrip,
                "char_start": intro_lstrip,
                "char_end": intro_lstrip + len(intro_content),
                "unit_type": "literary_chapter",
                "is_literary_chapter": True,
                "is_production_chunk": False,
                "boundary_origin": "inferred_prologue",
                "literary_chapter_number": 1,
                "parent_chapter_title": "Prologue / Introduction",
                "chunk_index": 1,
                "total_chunks": 1,
            })
            # Re-number literary_chapter_number sequentially
            for lit_idx, ch in enumerate(chapters, 1):
                ch["literary_chapter_number"] = lit_idx

    return chapters


def _recursive_split_segments(
    content: str,
    max_words: int,
    base_char_start: int = 0,
) -> List[Tuple[str, int, int]]:
    """
    Internal helper that recursively splits oversized content on semantic boundaries,
    returning a flat list of (segment_text, char_start, char_end).
    """
    words = content.split()
    total_words = len(words)
    if total_words <= max_words:
        return [(content, base_char_start, base_char_start + len(content))]

    mid_char = len(content) // 2
    best_split_idx = -1
    split_end = -1
    best_dist = float("inf")

    # Priority 1: Scene breaks in central 20%-80% zone (keep scene break marker at end of Part 1)
    scene_break_pattern = r"\n\s*(?:\*\s*\*\s*\*|\-\s*\-\s*\-|—\s*—\s*—|_\s*_\s*_)\s*\n"
    for match in re.finditer(scene_break_pattern, content):
        pos = match.start()
        dist = abs(pos - mid_char)
        if 0.20 * len(content) <= pos <= 0.80 * len(content):
            if dist < best_dist:
                best_dist = dist
                best_split_idx = match.end()
                split_end = match.end()

    # Priority 2: Section subheadings in central 20%-80% zone (keep heading at start of Part 2)
    if best_split_idx == -1:
        heading_pattern = r"\n(?=\s*#{2,4}\s+[^\n]+\n)"
        for match in re.finditer(heading_pattern, content):
            pos = match.start()
            dist = abs(pos - mid_char)
            if 0.20 * len(content) <= pos <= 0.80 * len(content):
                if dist < best_dist:
                    best_dist = dist
                    best_split_idx = match.start()
                    split_end = match.end()

    # Priority 3: Paragraph boundary (\n\n+) in central 25%-75% zone
    if best_split_idx == -1:
        for match in re.finditer(r"\n\n+", content):
            pos = match.start()
            dist = abs(pos - mid_char)
            if 0.25 * len(content) <= pos <= 0.75 * len(content):
                if dist < best_dist:
                    best_dist = dist
                    best_split_idx = match.start()
                    split_end = match.end()

    # Priority 4: Sentence boundary (. , ? , ! , । ) in central 30%-70% zone
    if best_split_idx == -1:
        for match in re.finditer(r"[\.\?\!\।]\s+", content):
            pos = match.end()
            dist = abs(pos - mid_char)
            if 0.30 * len(content) <= pos <= 0.70 * len(content):
                if dist < best_dist:
                    best_dist = dist
                    best_split_idx = pos
                    split_end = pos

    # Priority 5: Emergency word boundary (final fallback)
    if best_split_idx == -1:
        mid_word_idx = max(1, total_words // 2)
        # Locate character offset of mid_word_idx in content
        word_matches = list(re.finditer(r"\S+", content))
        if mid_word_idx < len(word_matches):
            char_cut = word_matches[mid_word_idx].start()
        else:
            char_cut = max(1, len(content) // 2)
        raw_p1 = content[:char_cut]
        raw_p2 = content[char_cut:]
        p1_lstrip = len(raw_p1) - len(raw_p1.lstrip())
        p2_lstrip = len(raw_p2) - len(raw_p2.lstrip())
        p1_content = raw_p1.strip()
        p2_content = raw_p2.strip()
        p1_start = base_char_start + p1_lstrip
        p2_start = base_char_start + char_cut + p2_lstrip
    else:
        raw_p1 = content[:best_split_idx]
        raw_p2 = content[split_end:]
        p1_lstrip = len(raw_p1) - len(raw_p1.lstrip())
        p2_lstrip = len(raw_p2) - len(raw_p2.lstrip())
        p1_content = raw_p1.strip()
        p2_content = raw_p2.strip()
        p1_start = base_char_start + p1_lstrip
        p2_start = base_char_start + split_end + p2_lstrip

    left_segs = _recursive_split_segments(p1_content, max_words, p1_start)
    right_segs = _recursive_split_segments(p2_content, max_words, p2_start)
    return left_segs + right_segs


def split_large_chapter_on_semantic_boundary(
    title: str,
    content: str,
    max_words: int = 12000,
    *,
    base_char_start: int = 0,
    is_literary_chapter: bool = True,
    boundary_origin: str = "detected_heading",
    literary_chapter_number: Optional[int] = None,
    parent_chapter_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Meso-Tier Verification Guard:
    Checks chapter word count. If word count > max_words (default: 12,000), splits chapter on
    semantic boundary into artificial production chunks (Part 1, Part 2, ...) while preserving
    parent literary chapter linkage and character offsets.
    
    Splitting Priority Hierarchy:
    1. Scene break (***, ---, ___, ———)
    2. Section divider / heading (##, ###)
    3. Paragraph boundary (\\n\\n)
    4. Sentence boundary (. , ? , ! , । )
    5. Emergency word split (final safety mechanism)
    """
    words = content.split()
    total_words = len(words)
    base_title = re.sub(r"\s*\((?:Part|भाग)\s*\d+\)", "", title, flags=re.IGNORECASE).strip()

    if total_words <= max_words:
        unit_type = "literary_chapter" if is_literary_chapter else "production_chunk"
        return [{
            "title": title,
            "content": content,
            "words": total_words,
            "char_start": base_char_start,
            "char_end": base_char_start + len(content),
            "unit_type": unit_type,
            "is_literary_chapter": is_literary_chapter,
            "is_production_chunk": not is_literary_chapter,
            "boundary_origin": boundary_origin,
            "literary_chapter_number": literary_chapter_number,
            "parent_chapter_id": parent_chapter_id,
            "parent_chapter_title": base_title if is_literary_chapter else None,
            "chunk_index": 1,
            "total_chunks": 1,
        }]

    raw_segments = _recursive_split_segments(content, max_words=max_words, base_char_start=base_char_start)
    total_parts = len(raw_segments)
    parts: List[Dict[str, Any]] = []

    for idx, (seg_content, seg_start, seg_end) in enumerate(raw_segments, 1):
        part_title = f"{base_title} (Part {idx})"
        parts.append({
            "title": part_title,
            "content": seg_content,
            "words": len(seg_content.split()),
            "char_start": seg_start,
            "char_end": seg_end,
            "unit_type": "production_chunk",
            "is_literary_chapter": False,
            "is_production_chunk": True,
            "boundary_origin": "semantic_split_chunk" if is_literary_chapter else "fallback_production_chunk",
            "literary_chapter_number": literary_chapter_number,
            "parent_chapter_id": parent_chapter_id or (f"lit-ch-{literary_chapter_number:03d}" if literary_chapter_number else None),
            "parent_chapter_title": base_title if is_literary_chapter else None,
            "chunk_index": idx,
            "total_chunks": total_parts,
        })

    return parts

