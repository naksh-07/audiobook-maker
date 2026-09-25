#!/usr/bin/env python3
"""
Audiobook Factory - Translation Decision Memory Ledger.
Persists challenging translation decisions, idioms, and contextual choices
to prevent re-inventing solutions across subsequent chapters.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class TranslationDecision(BaseModel):
    source_concept: str
    chosen_translation: str
    candidates_considered: List[str] = Field(default_factory=list)
    literary_rationale: str = ""
    chapter_num: int = 1
    scene_id: Optional[str] = None
    character_context: Optional[str] = None
    confidence: float = 1.0


class TranslationDecisionMemory(BaseModel):
    decisions: Dict[str, TranslationDecision] = Field(default_factory=dict)

    def record_decision(self, decision: TranslationDecision):
        self.decisions[decision.source_concept.lower()] = decision

    def lookup(self, concept: str) -> Optional[TranslationDecision]:
        return self.decisions.get(concept.lower())

    def save(self, file_path: Path):
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, file_path: Path) -> TranslationDecisionMemory:
        if not file_path.exists():
            return cls()
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)
