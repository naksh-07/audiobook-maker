#!/usr/bin/env python3
"""
Audiobook Factory - Centralized Chunking & Token Budget Policy.
Defines explicit token and word limits across all pipeline stages to prevent
LLM cognitive fatigue, attention drift ('Lost-in-the-Middle'), and creative degradation.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkingPolicy:
    """
    Standardized chunking and token limits across production stages.
    Enforces maximum cognitive stamina and authentic dramatic cadence.
    """

    # Literary Translation (Pillar 2):
    # 650-750 words (~1,000 input tokens) produces ~1,500 Devanagari output tokens.
    # Eliminates attention drift and allows Gemini/Claude to maintain authentic
    # visceral somatic intimacy, rustic curses, and poetic regional cadence.
    TRANSLATION_MAX_WORDS: int = 750
    TRANSLATION_TARGET_WORDS: int = 650

    # Screenplay Parsing & Dialogue Attribution (Pillar 3.1):
    # 300-350 words ceiling guarantees 100% dialogue turn isolation without merging
    # rapid-fire dialogue or short one-word replies into narrator text.
    SCREENPLAY_MAX_WORDS: int = 350
    SCREENPLAY_TARGET_WORDS: int = 280

    # Scene Dramaturgy & Subtext Analysis:
    # 3,500 characters (~600 words) ceiling per scene analysis pass to allow
    # deep psychological and acoustic comprehension without generic filler.
    DRAMATURGY_SCENE_MAX_CHARS: int = 3500

    # Standard Narrator Speech Chunks (Audiobook Mode):
    # Optimal reading chunks for TTS synthesis and dramatic pacing.
    NARRATOR_CHUNK_MIN_WORDS: int = 200
    NARRATOR_CHUNK_MAX_WORDS: int = 450


# Global singleton instance for convenient import
chunking_policy = ChunkingPolicy()
