#!/usr/bin/env python3
"""
Audiobook Factory - Room 3: Screenplay Dramaturgy & Spatial Staging Coordinator.
Orchestrates the 4-agent screenplay room across the 100+ key pool:
1. DialogueTurnIsolator: Verbatim turn extraction & speaker identification.
2. StanislavskiSubtextDirector: Transitive actioning verbs, psychological subtext & intensity.
3. PhysicalBlockingDirector: Actor physical posture, proximity & azimuth panning (-0.8 to +0.8).
4. DramaturgyConsistencyJudge: Spatial continuity audit, narrator clamping & intensity calibration.
"""

from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional, Callable

from .dialogue_isolator import DialogueTurnIsolator
from .dialogue_attribution_auditor import DialogueAttributionAuditor
from .stanislavski_director import StanislavskiSubtextDirector
from .physical_blocking_director import PhysicalBlockingDirector
from .dramaturgy_judge import DramaturgyConsistencyJudge

logger = logging.getLogger("AudiobookFactory")


class ScreenplayDramaturgyRoom:
    """Coordinates the 5 screenplay dramaturgy, anti-swap attribution, and spatial staging agents."""

    def __init__(self, model: Optional[str] = None):
        self.model = model
        self.isolator = DialogueTurnIsolator(model=model)
        self.auditor = DialogueAttributionAuditor(model=model)
        self.stanislavski = StanislavskiSubtextDirector(model=model)
        self.blocking_director = PhysicalBlockingDirector(model=model)
        self.judge = DramaturgyConsistencyJudge()

    def process_chunk(
        self,
        chunk_text: str,
        preceding_context: str = "",
        dramatic_context: str = "",
        is_hindi: bool = False,
        character_roster: Optional[Dict[str, Any]] = None,
        call_llm_fn: Optional[Callable[..., Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Processes a chunk through the 5-agent Screenplay Room."""
        # Pass 1: Turn Isolation
        turns = self.isolator.isolate_turns(
            chunk_text=chunk_text,
            preceding_context=preceding_context,
            is_hindi=is_hindi,
            character_roster=character_roster,
        )
        if not turns:
            return []

        # Pass 1.5: Forensic Attribution & Speaker Anti-Swap Audit
        audited_turns, audit_report = self.auditor.audit_and_correct(
            turns=turns,
            chunk_text=chunk_text,
            preceding_context=preceding_context,
            is_hindi=is_hindi,
            character_roster=character_roster,
            call_llm_fn=call_llm_fn,
        )

        # Pass 2A: Stanislavski Subtext & Intensity
        directed_turns = self.stanislavski.direct_subtext(
            segments=audited_turns,
            dramatic_context=dramatic_context,
            is_hindi=is_hindi,
            call_llm_fn=call_llm_fn,
        )

        # Pass 2B: Physical Blocking & Azimuth Staging
        staged_turns = self.blocking_director.direct_blocking(
            segments=directed_turns,
            dramatic_context=dramatic_context,
            call_llm_fn=call_llm_fn,
        )

        # Pass 3: Consistency & Spatial Continuity Audit
        certified_turns, report = self.judge.audit_and_certify(
            segments=staged_turns,
            chunk_title="Screenplay Chunk",
        )

        return certified_turns


_room_instance: Optional[ScreenplayDramaturgyRoom] = None


def get_screenplay_room(model: Optional[str] = None) -> ScreenplayDramaturgyRoom:
    """Returns singleton ScreenplayDramaturgyRoom instance."""
    global _room_instance
    if _room_instance is None or (model and _room_instance.model != model):
        _room_instance = ScreenplayDramaturgyRoom(model=model)
    return _room_instance
