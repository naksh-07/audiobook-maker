#!/usr/bin/env python3
"""
Audiobook Factory - Cinema Audio Engine Stub (Vocals-Only Engine).
Provides lightweight stub classes for discrete stems and cinema manifests.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path


class StemMetadata:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class StemLedger:
    def __init__(self, chapter_id: str = "", **kwargs):
        self.chapter_id = chapter_id
        self.metadata: Dict[str, Any] = {
            "mix_judge_status": "BYPASSED_VOCALS_ONLY",
            "mix_judge_score": 1.0,
            "mastering_status": "BYPASSED_VOCALS_ONLY",
        }
        self.__dict__.update(kwargs)


class CinemaAudioManifest:
    def __init__(self, chapter_id: str = "", **kwargs):
        self.chapter_id = chapter_id
        self.__dict__.update(kwargs)


def render_discrete_stems(*args, **kwargs) -> StemLedger:
    """Returns a bypassed StemLedger in Vocals-Only mode."""
    chapter_id = kwargs.get("manifest", None)
    chap_id_str = getattr(chapter_id, "chapter_id", "") if chapter_id else ""
    return StemLedger(chapter_id=chap_id_str)
