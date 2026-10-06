#!/usr/bin/env python3
"""
Audiobook Factory - Room 3 Agent A: Dialogue Turn Isolator.
Extracts verbatim dialogue turns and narration beats from source prose,
performing character attribution against the project Character Roster.
"""

from __future__ import annotations
import json
import logging
from typing import List, Dict, Any, Optional

from audiobook_factory.script.dialogue_parser import _parse_dialogue_turns_llm

logger = logging.getLogger("AudiobookFactory")


class DialogueTurnIsolator:
    """Agent A: Speaker Attribution and Dialogue Turn Extraction Specialist."""

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def isolate_turns(
        self,
        chunk_text: str,
        preceding_context: str = "",
        is_hindi: bool = False,
        character_roster: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Isolates dialogue turns and attributes speakers cleanly."""
        logger.info("  [DialogueTurnIsolator] Isolating dialogue turns from prose...")
        turns = _parse_dialogue_turns_llm(
            chunk_text=chunk_text,
            preceding_context=preceding_context,
            is_hindi=is_hindi,
            character_roster=character_roster,
        )
        logger.info(f"  [DialogueTurnIsolator] Successfully extracted {len(turns)} turns.")
        return turns
