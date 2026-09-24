#!/usr/bin/env python3
"""
Audiobook Factory - Dynamic Relationship State Engine.
Tracks multi-dimensional interpersonal dynamics (respect, familiarity, hostility, authority, intimacy)
and resolves contextual honorifics (Aap/Tum/Tu) with evidence-driven mutation rules.
"""

from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field


class DynamicRelationshipState(BaseModel):
    speaker: str
    target: str
    respect: int = Field(default=3, ge=0, le=5)
    familiarity: int = Field(default=2, ge=0, le=5)
    hostility: int = Field(default=0, ge=0, le=5)
    intimacy: int = Field(default=1, ge=0, le=5)
    authority_differential: int = Field(default=0, ge=-5, le=5)  # positive = speaker has authority
    fear: int = Field(default=0, ge=0, le=5)
    trust: int = Field(default=3, ge=0, le=5)
    current_pronoun: str = "tum"  # aap, tum, tu
    current_vocabulary_register: str = "casual"  # formal, casual, derogatory, intimate
    recent_interaction_notes: str = ""


class RelationshipStateEngine:
    @staticmethod
    def resolve_pronoun_level(rel: DynamicRelationshipState) -> str:
        """
        Dynamically calculates the appropriate Hindi pronoun (aap, tum, tu)
        based on multidimensional interpersonal dynamics.
        """
        # Fear or severe subordinate status -> Aap / Maai-Baap
        if rel.fear >= 4 or rel.authority_differential <= -3:
            return "aap"

        # High hostility with equal or superior authority -> Tu (aggressive)
        if rel.hostility >= 3 and rel.authority_differential >= 0:
            return "tu"

        # High intimate closeness -> Tu or Tum depending on familiarity
        if rel.intimacy >= 4 and rel.familiarity >= 4:
            return "tu"

        # High respect and formality -> Aap
        if rel.respect >= 4 and rel.familiarity <= 2:
            return "aap"

        # Close brothers-in-arms / camaraderie -> Tum or Tu
        if rel.familiarity >= 3 and rel.hostility == 0:
            return "tum"

        # Default fallback
        return rel.current_pronoun or "tum"

    @staticmethod
    def get_relationship_prompt_guidelines(
        speaker: str,
        target: str,
        rel: Optional[DynamicRelationshipState] = None
    ) -> str:
        """Formats dynamic relationship guidelines for translation prompts."""
        if not rel:
            return f"- Interaction [{speaker} -> {target}]: Default polite 'tum' with balanced respect."

        resolved_pronoun = RelationshipStateEngine.resolve_pronoun_level(rel)
        tone_descriptor = []
        if rel.hostility >= 3:
            tone_descriptor.append("tense/hostile")
        if rel.intimacy >= 3:
            tone_descriptor.append("intimate/somatically close")
        if rel.respect >= 4:
            tone_descriptor.append("reverent/respectful")
        if rel.fear >= 3:
            tone_descriptor.append("intimidated/guarded")
        if not tone_descriptor:
            tone_descriptor.append("natural conversational")

        tone_str = ", ".join(tone_descriptor)
        return (
            f"- INTERACTION [{speaker} addresses {target}]:\n"
            f"  * Mandatory Pronoun: '{resolved_pronoun}'\n"
            f"  * Dynamic Stance: {tone_str}\n"
            f"  * Interpersonal Tone: Respect {rel.respect}/5, Familiarity {rel.familiarity}/5, Hostility {rel.hostility}/5\n"
            f"  * Invariant: Never artificially polite if hostile, and never dismissive if addressing high status."
        )
