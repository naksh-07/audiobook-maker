#!/usr/bin/env python3
"""
Audiobook Factory - Dedicated Spoken Text Resolution Stage.
Transforms literary screenplay text into optimized spoken text for TTS
while strictly preserving the immutability of the original literary text.
Safeguards neural acting tags (e.g. [whispers], [shouting]) from phonetic corruption.
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Optional, Tuple

from .contracts import (
    SpokenTextResult,
    PronunciationResolutionResult,
    PronunciationStatus,
)
from .resolver import PronunciationResolver


# Pattern to identify and protect bracketed neural performance tags
ACTING_TAG_PATTERN = re.compile(r"(\[[^\]]+\])")


class SpokenTextEngine:
    """
    Spoken-Text Transformation Engine.
    Keeps literary text immutable while producing calibrated spoken representations for TTS.
    """

    def __init__(self, resolver: PronunciationResolver):
        self.resolver = resolver

    def resolve_screenplay_segment(
        self,
        segment: Any,
        speaker_profile: Optional[Any] = None,
    ) -> SpokenTextResult:
        """
        Resolves spoken text for a ScreenplaySegment or dictionary.
        Does NOT mutate segment.text.
        """
        if isinstance(segment, dict):
            raw_text = segment.get("text", "")
            is_dialogue = (segment.get("type") == "dialogue")
        else:
            raw_text = getattr(segment, "text", "")
            is_dialogue = (getattr(segment, "type", "narration") == "dialogue")

        return self.resolve_text(
            literary_text=raw_text,
            speaker_profile=speaker_profile,
            is_dialogue=is_dialogue,
        )

    def resolve_text(
        self,
        literary_text: str,
        speaker_profile: Optional[Any] = None,
        is_dialogue: bool = True,
    ) -> SpokenTextResult:
        """
        Transforms literary text into spoken text:
        1. Preserves and isolates bracketed performance tags.
        2. Resolves multi-word canonical entities.
        3. Resolves individual sensitive tokens, numerals, currencies, and units.
        4. Re-assembles spoken text while maintaining original spacing and tags.
        """
        if not literary_text or not literary_text.strip():
            return SpokenTextResult(
                literary_text=literary_text,
                display_text="",
                spoken_text="",
                resolutions=[],
                has_unresolved_critical=False,
                requires_review=False,
            )

        # 1. Protect bracketed acting tags (e.g. [whispers], [gasp])
        # Split text into alternating [tag, non-tag, tag, non-tag] chunks
        parts = ACTING_TAG_PATTERN.split(literary_text)
        spoken_parts: List[str] = []
        resolutions: List[PronunciationResolutionResult] = []

        for part in parts:
            if not part:
                continue

            # If this part is a bracketed acting tag, pass through verbatim without pronunciation processing
            if ACTING_TAG_PATTERN.match(part):
                spoken_parts.append(part)
                continue

            # Process non-tag textual content
            transformed_part, part_resolutions = self._process_text_chunk(
                chunk=part,
                full_context=literary_text,
                speaker_profile=speaker_profile,
                is_dialogue=is_dialogue,
            )
            spoken_parts.append(transformed_part)
            resolutions.extend(part_resolutions)

        spoken_text = "".join(spoken_parts)

        # Display text: stripped of neural tags, clean for human reading / subtitles
        display_text = ACTING_TAG_PATTERN.sub("", literary_text).strip()
        display_text = re.sub(r"\s+", " ", display_text)

        has_unresolved = any(r.status in (PronunciationStatus.FAILED, PronunciationStatus.UNCERTAIN) for r in resolutions)
        requires_review = any(r.requires_review for r in resolutions)

        return SpokenTextResult(
            literary_text=literary_text,
            display_text=display_text,
            spoken_text=spoken_text,
            resolutions=resolutions,
            has_unresolved_critical=has_unresolved,
            requires_review=requires_review,
        )

    def _process_text_chunk(
        self,
        chunk: str,
        full_context: str,
        speaker_profile: Optional[Any],
        is_dialogue: bool,
    ) -> Tuple[str, List[PronunciationResolutionResult]]:
        """
        Processes a pure text chunk:
        - First checks multi-word canonical entities in the lexicon.
        - Then checks individual tokens.
        """
        resolutions: List[PronunciationResolutionResult] = []
        working_chunk = chunk

        # Multi-word entity matching (e.g. "Sherlock Holmes", "Kaer Morhen", "Temple of Melitele")
        if self.resolver.lexicon and self.resolver.lexicon.entries:
            multi_word_phrases = []
            for e in self.resolver.lexicon.entries.values():
                for cand in [e.canonical_text] + e.aliases:
                    if cand and " " in cand.strip():
                        multi_word_phrases.append(cand.strip())
            seen_phrases = set()
            unique_phrases = []
            for p in multi_word_phrases:
                if p.lower() not in seen_phrases:
                    seen_phrases.add(p.lower())
                    unique_phrases.append(p)
            unique_phrases.sort(key=lambda x: len(x), reverse=True)

            for pat in unique_phrases:
                escaped = re.escape(pat)
                match_pat = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
                if match_pat.search(working_chunk):
                    res = self.resolver.resolve_token(
                        token=pat,
                        sentence_context=full_context,
                        speaker_profile=speaker_profile,
                        is_dialogue=is_dialogue,
                    )
                    resolutions.append(res)
                    working_chunk = match_pat.sub(res.resolved_spoken, working_chunk)

        # Single token scanning
        tokens_with_delims = re.split(r"(\s+|[।,;!?\"\(\)\[\]«»“”])", working_chunk)
        final_parts: List[str] = []

        for item in tokens_with_delims:
            if not item:
                continue

            # If item is purely delimiter/whitespace, append
            if re.match(r"^(\s+|[।,;!?\"\(\)\[\]«»“”]+)$", item):
                final_parts.append(item)
                continue

            # Strip leading/trailing quotes/brackets for resolution check while preserving currency symbols
            m = re.match(r"^([^\w\u0900-\u097F\$₹%]*)([\w\u0900-\u097F\.\-\$₹%]+)([^\w\u0900-\u097F\$₹%]*)$", item)
            if m:
                pre, core, post = m.groups()
                # Check if core needs pronunciation resolution
                res = self.resolver.resolve_token(
                    token=core,
                    sentence_context=full_context,
                    speaker_profile=speaker_profile,
                    is_dialogue=is_dialogue,
                )
                if res.transformation_applied or res.requires_review:
                    resolutions.append(res)
                    final_parts.append(f"{pre}{res.resolved_spoken}{post}")
                else:
                    final_parts.append(item)
            else:
                final_parts.append(item)

        return "".join(final_parts), resolutions
