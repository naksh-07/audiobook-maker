#!/usr/bin/env python3
"""
Audiobook Factory - Pronunciation Provenance & Cache Invalidation Engine.
Tracks and hashes pronunciation decisions so that modifying an entity's spoken form
cleanly invalidates downstream cached takes and triggers re-certification.
"""

from __future__ import annotations
import json
import hashlib
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from .contracts import PronunciationProvenanceRecord, PronunciationEntry


class PronunciationProvenanceTracker:
    """
    Computes deterministic SHA256 hashes of the pronunciation lexicon state.
    """

    @staticmethod
    def compute_lexicon_hash(lexicon_entries: Dict[str, PronunciationEntry]) -> str:
        """
        Computes deterministic SHA256 hash across all active pronunciation entries.
        """
        clean_state = {
            cid: {
                "canonical_text": e.canonical_text,
                "spoken_form": e.spoken_form,
                "pronunciation_hint": e.pronunciation_hint,
                "status": e.status.value,
                "source": e.source.value,
                "version": e.version,
            }
            for cid, e in sorted(lexicon_entries.items())
        }
        dumped = json.dumps(clean_state, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def create_provenance_record(
        entity_id: str,
        surface_form: str,
        resolved_spoken: str,
        resolver_source: str,
        chapter_num: int = 1,
        segment_uid: str = "",
        tts_model: str = "gemini-3.8-flash-tts",
        take_id: str = "",
        qa_status: str = "VERIFIED",
        repair_attempt: int = 0,
        certified: bool = False,
    ) -> PronunciationProvenanceRecord:
        """Creates an auditable provenance record for a pronunciation event."""
        return PronunciationProvenanceRecord(
            entity_id=entity_id,
            occurrence_chapter=chapter_num,
            occurrence_segment_uid=segment_uid,
            surface_form=surface_form,
            resolved_spoken=resolved_spoken,
            resolver_source=resolver_source,
            tts_model=tts_model,
            take_id=take_id,
            qa_status=qa_status,
            repair_attempt=repair_attempt,
            certified=certified,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
