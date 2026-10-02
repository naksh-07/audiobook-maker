#!/usr/bin/env python3
"""
Audiobook Factory - Script Package.
Modular decomposition of Pillar 3.1: Screenplay Script Builder & Speech Normalizer.
"""

from __future__ import annotations

from audiobook_factory.script.normalizer import (
    normalize_speech_text,
    build_narrator_script,
)
from audiobook_factory.script.dialogue_parser import (
    _parse_dialogue_turns_llm,
)
from audiobook_factory.script.staging_enricher import (
    _enrich_performance_and_staging_llm,
    _parse_dramatized_chunk_llm,
)
from audiobook_factory.script.screenplay_cleaner import (
    clean_screenplay_pass2,
)
from audiobook_factory.script.dramatized_builder import (
    build_dramatized_script_llm,
)
from audiobook_factory.script.project_generator import (
    generate_project_scripts,
)

__all__ = [
    "normalize_speech_text",
    "build_narrator_script",
    "_parse_dialogue_turns_llm",
    "_enrich_performance_and_staging_llm",
    "_parse_dramatized_chunk_llm",
    "clean_screenplay_pass2",
    "build_dramatized_script_llm",
    "generate_project_scripts",
]
