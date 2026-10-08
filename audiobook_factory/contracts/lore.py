#!/usr/bin/env python3
"""
Audiobook Factory - Lore & Casting Contracts (BookBible, CastLock, CharacterDossier).
Standard: v6.0-ENTERPRISE-DAG
"""

from __future__ import annotations
from typing import Dict
from pydantic import Field
from audiobook_factory.contracts.base import ContractBaseModel


class CharacterDossier(ContractBaseModel):
    """Detailed character vocal profile and dramatic persona."""
    character_name: str = Field(..., description="Character name in Latin source script")
    canonical_hindi_name: str = Field(..., description="Devanagari phonetic transliteration")
    gender: str = Field(..., pattern="^(MALE|FEMALE|NEUTRAL|NARRATOR)$", description="Gender archetype")
    vocal_weight: str = Field(default="MEDIUM", description="LIGHT, MEDIUM, HEAVY, GRUFF")
    social_register: str = Field(default="STANDARD", description="ROYAL, RUSTIC, SCHOLARLY, ROGUE")
    suggested_voice_id: str = Field(..., description="Gemini Voice ID, e.g., 'Puck', 'Charon'")
    pitch_offset: float = Field(default=0.0, ge=-12.0, le=12.0, description="Pitch delta percentage")
    tempo_multiplier: float = Field(default=1.0, ge=0.85, le=1.15, description="Tempo multiplier")
    eq_profile_name: str = Field(default="FLAT", description="4D EQ curve profile")


class BookBible(ContractBaseModel):
    """World lore, terminology glossary, and extracted character profiles."""
    book_id: str = Field(..., description="Project slug")
    literary_tradition: str = Field(default="HIGH_FANTASY", description="Genre/Tradition classification")
    fidelity_tier: str = Field(default="RAW_UNRATED", pattern="^(CLASSIC_REVERENT|RAW_UNRATED)$")
    terminology_map: Dict[str, str] = Field(
        default_factory=dict,
        description="Proper nouns and terms mapped to Hindi transliterations"
    )
    characters: Dict[str, CharacterDossier] = Field(
        default_factory=dict,
        description="Extracted character dossiers"
    )


class CastLock(ContractBaseModel):
    """Immutable director voice casting and narrator locks."""
    project_id: str = Field(..., description="Project slug")
    narrator_voice_id: str = Field(default="Aoede", description="Lead narrator voice ID")
    narrator_temperature: float = Field(default=0.32, ge=0.30, le=0.52, description="Restrained narrator temperature")
    cast_assignments: Dict[str, CharacterDossier] = Field(
        default_factory=dict,
        description="Locked speaker -> voice and formant mappings"
    )
