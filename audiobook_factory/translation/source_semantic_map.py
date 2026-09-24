#!/usr/bin/env python3
"""
Audiobook Factory - Persistent Source Semantic Map Engine.
Builds and persists a stable structured representation of source propositions
(who, did what, to whom, negations, entities, key objects) per scene/chapter.
Enables Semantic QA to compare target against a frozen, immutable semantic ledger
rather than repeatedly calling LLMs to re-interpret raw source text.
"""

from __future__ import annotations
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class SemanticProposition(BaseModel):
    beat_id: str
    paragraph_idx: int
    source_sentence: str
    actors: List[str] = Field(default_factory=list)
    action: str = ""
    recipients: List[str] = Field(default_factory=list)
    has_negation: bool = False
    negation_keywords: List[str] = Field(default_factory=list)
    key_entities: List[str] = Field(default_factory=list)
    key_objects: List[str] = Field(default_factory=list)
    is_dialogue: bool = False
    speaker: Optional[str] = None


class SourceSemanticMap(BaseModel):
    scene_id: str
    total_beats: int
    source_hash: str
    propositions: List[SemanticProposition] = Field(default_factory=list)

    def save(self, output_path: Path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, file_path: Path) -> SourceSemanticMap:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)


NEGATION_TOKENS = {
    "not", "never", "no", "neither", "nor", "none", "cannot", "can't",
    "won't", "wouldn't", "didn't", "doesn't", "don't", "refused", "failed",
    "stopped", "without", "barely", "hardly", "seldom"
}


def build_source_semantic_map(
    scene_text: str,
    scene_id: str = "scene_001",
    known_entities: Optional[List[str]] = None,
    known_objects: Optional[List[str]] = None,
) -> SourceSemanticMap:
    """
    Parses source scene text into a structured Semantic Proposition Map.
    Extracts negations, actors, dialogue beats, and key entities dynamically for ANY novel.
    """
    import hashlib
    source_hash = hashlib.sha256(scene_text.encode("utf-8")).hexdigest()[:16]
    paragraphs = [p.strip() for p in scene_text.split("\n\n") if p.strip()]

    # If no known entities provided, dynamically discover capitalized names
    if not known_entities:
        candidates = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", scene_text)
        stop_words = {
            "The", "He", "She", "They", "Then", "After", "Before", "There", "When",
            "What", "It", "In", "On", "At", "And", "But", "Or", "So", "However",
            "Suddenly", "Meanwhile", "Later", "Now", "Just", "Even", "Though"
        }
        known_entities = list(set(c for c in candidates if c not in stop_words and len(c) > 2))

    propositions: List[SemanticProposition] = []
    beat_counter = 0

    for p_idx, para in enumerate(paragraphs):
        raw_sentences = re.split(r"(?<=[.!?])\s+", para)
        for s in raw_sentences:
            s_clean = s.strip()
            if not s_clean:
                continue

            beat_counter += 1
            words = re.findall(r"\b[a-zA-Z']+\b", s_clean.lower())
            
            # Negation detection
            found_negations = [w for w in words if w in NEGATION_TOKENS]
            has_neg = len(found_negations) > 0

            # Entity matching
            matched_entities = [e for e in known_entities if re.search(rf"\b{re.escape(e)}\b", s_clean, re.IGNORECASE)]

            # Dialogue detection
            is_diag = bool(re.search(r'["\u201c\u201d\'].+?["\u201c\u201d\']', s_clean))
            speaker = matched_entities[0] if (is_diag and matched_entities) else None

            # Object / Terminology keywords (dynamic from known_objects if available)
            matched_objects = []
            if known_objects:
                for obj in known_objects:
                    if re.search(rf"\b{re.escape(obj)}\b", s_clean, re.IGNORECASE):
                        matched_objects.append(obj)

            prop = SemanticProposition(
                beat_id=f"{scene_id}_b{beat_counter:03d}",
                paragraph_idx=p_idx,
                source_sentence=s_clean,
                actors=matched_entities[:1],
                recipients=matched_entities[1:],
                has_negation=has_neg,
                negation_keywords=found_negations,
                key_entities=matched_entities,
                key_objects=matched_objects,
                is_dialogue=is_diag,
                speaker=speaker,
            )
            propositions.append(prop)

    return SourceSemanticMap(
        scene_id=scene_id,
        total_beats=len(propositions),
        source_hash=source_hash,
        propositions=propositions,
    )
