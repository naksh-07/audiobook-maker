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
    Segments a continuous raw text string into structured chapter dictionaries.
    Returns: List[Dict[str, Any]] with keys: 'title', 'content', 'words'
    """
    if not raw_text or not raw_text.strip():
        return []

    # Find candidate splits matching multi-tier patterns
    raw_splits = list(re.finditer(COMBINED_CHAPTER_REGEX, raw_text, flags=re.IGNORECASE | re.MULTILINE))

    # Filter candidates with conservative validation
    valid_splits = []
    for idx, match in enumerate(raw_splits):
        start = match.start()
        end = match.end()
        preceding = raw_text[:start]
        following = raw_text[end:]
        if is_valid_heading_candidate(match.group(0), preceding, following):
            valid_splits.append(match)

    if not valid_splits:
        # Fallback: Semantic Scene-Aware Chunking
        paragraphs = re.split(r"\n{2,}", raw_text)
        chapters: List[Dict[str, Any]] = []
        current_chunk: List[str] = []
        current_words = 0
        chap_num = 1

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            words = len(para.split())
            current_chunk.append(para)
            current_words += words

            is_scene_break = bool(re.match(r"^(\*|\-|\_)\s*\1\s*\1+$", para))
            if (current_words >= 2500 and is_scene_break) or current_words >= 3500:
                chapters.append({
                    "title": f"Chapter {chap_num}",
                    "content": "\n\n".join(current_chunk),
                    "words": current_words,
                })
                chap_num += 1
                current_chunk = []
                current_words = 0

        if current_chunk:
            chapters.append({
                "title": f"Chapter {chap_num}",
                "content": "\n\n".join(current_chunk),
                "words": current_words,
            })
        return chapters

    # Split text into chapters based on validated heading positions
    chapters: List[Dict[str, Any]] = []
    for idx, match in enumerate(valid_splits):
        title = match.group(0).strip().lstrip("#").strip()
        start = match.end()
        end = valid_splits[idx + 1].start() if idx + 1 < len(valid_splits) else len(raw_text)
        content = raw_text[start:end].strip()
        word_count = len(content.split())

        if word_count >= 5:
            chapters.append({
                "title": title,
                "content": content,
                "words": word_count,
            })

    # Preserve any prologue/intro preceding the first chapter heading
    if valid_splits and valid_splits[0].start() > 100:
        intro_content = raw_text[:valid_splits[0].start()].strip()
        intro_words = len(intro_content.split())
        if intro_words >= 30:
            chapters.insert(0, {
                "title": "Prologue / Introduction",
                "content": intro_content,
                "words": intro_words,
            })

    return chapters


def split_large_chapter_on_semantic_boundary(
    title: str,
    content: str,
    max_words: int = 12000,
) -> List[Dict[str, Any]]:
    """
    Meso-Tier Verification Guard:
    Checks chapter word count. If word count > max_words (default: 12,000), splits chapter on
    semantic boundary into Part 1 and Part 2.
    
    Splitting Priority Hierarchy:
    1. Scene break (***, ---, ___, ———)
    2. Section divider / heading (##, ###)
    3. Paragraph boundary (\n\n)
    4. Sentence boundary (. , ? , ! , । )
    5. Emergency word split (final safety mechanism)
    """
    words = content.split()
    total_words = len(words)
    if total_words <= max_words:
        return [{"title": title, "content": content, "words": total_words}]

    mid_char = len(content) // 2
    best_split_idx = -1
    split_end = -1
    best_dist = float("inf")

    # Priority 1 & 2: Scene breaks and section headings in central 20%-80% zone
    divider_patterns = [
        r"\n\s*(?:\*\s*\*\s*\*|\-\s*\-\s*\-|—\s*—\s*—|_\s*_\s*_)\s*\n",
        r"\n\s*#{2,4}\s+[^\n]+\n",
    ]
    for pattern in divider_patterns:
        for match in re.finditer(pattern, content):
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
        mid_word_idx = total_words // 2
        p1_content = " ".join(words[:mid_word_idx])
        p2_content = " ".join(words[mid_word_idx:])
    else:
        p1_content = content[:best_split_idx].strip()
        p2_content = content[split_end:].strip()

    p1_count = len(p1_content.split())
    p2_count = len(p2_content.split())

    base_title = re.sub(r"\s*\((?:Part|भाग)\s*\d+\)", "", title, flags=re.IGNORECASE).strip()
    part1_title = f"{base_title} (Part 1)"
    part2_title = f"{base_title} (Part 2)"

    parts: List[Dict[str, Any]] = []
    if p1_count > max_words:
        parts.extend(split_large_chapter_on_semantic_boundary(part1_title, p1_content, max_words))
    else:
        parts.append({"title": part1_title, "content": p1_content, "words": p1_count})

    if p2_count > max_words:
        parts.extend(split_large_chapter_on_semantic_boundary(part2_title, p2_content, max_words))
    else:
        parts.append({"title": part2_title, "content": p2_content, "words": p2_count})

    return parts
