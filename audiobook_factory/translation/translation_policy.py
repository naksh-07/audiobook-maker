#!/usr/bin/env python3
"""
Audiobook Factory - Central Translation Policy Engine.
Enforces immutable plot facts, strict semantic fidelity, permissible linguistic adaptation,
and the 'Nothing Above Source' standard.
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field


class TranslationPolicyConfig(BaseModel):
    version: str = "2.0.0"
    semantic_fidelity: str = "STRICT"
    plot_facts: str = "IMMUTABLE"
    character_actions: str = "IMMUTABLE"
    world_lore: str = "IMMUTABLE"
    relationship_facts: str = "IMMUTABLE"
    terminology: str = "CANONICAL"
    
    # Permissible adaptations
    idiom_adaptation: str = "ALLOWED"
    syntax_restructuring: str = "ALLOWED"
    spoken_naturalization: str = "ALLOWED"
    metaphor_adaptation: str = "CONTEXTUAL"
    literary_expansion: str = "LIMITED"
    
    # Strictly forbidden operations
    new_information: str = "FORBIDDEN"
    intensity_reduction: str = "FORBIDDEN"
    unjustified_intensity_amplification: str = "FORBIDDEN"
    sanitization: str = "FORBIDDEN"
    
    # Tone & Register
    target_register: str = "LITERARY_HINDUSTANI"
    urdu_seasoning: str = "CONTEXTUAL"  # "Aate mein Namak"
    adult_fidelity_mode: bool = True

    def get_prompt_instructions(self) -> str:
        """Returns clear, authoritative system instructions for translation prompts."""
        return (
            "TRANSLATION POLICY & PRODUCTION INVARIANTS (STRICT ENFORCEMENT):\n"
            "1. SEMANTIC FIDELITY & IMMUTABLE FACTS: All plot facts, character actions, physical injuries, "
            "deaths, and chronological events are IMMUTABLE. Never invert negations, never alter who did what to whom, "
            "and never introduce new information or actions unsupported by the source text.\n"
            "2. THE 'NOTHING ABOVE SOURCE' PRINCIPLE:\n"
            "   - If the source is raw, brutal, or vulgar -> Translate into authentic raw, visceral Hindustani.\n"
            "   - If the source is restrained, delicate, or formal -> Translate into refined, elegant, restrained Hindi.\n"
            "   - If the source contains sexual tension or somatic intimacy -> Preserve every nuance faithfully without "
            "sterile textbook clinical words ('योनि', 'लिंग'), but NEVER fabricate explicit acts not in the source.\n"
            "   - FORBIDDEN: Sanitizing mature literature OR gratuitously vulgarizing mild scenes.\n"
            "3. SPOKEN NATURALNESS & SYNTAX RESTRUCTURING: Translate sense-for-sense, NOT literal word-for-word. "
            "Break English subordinate clauses into natural, flowing Hindustani cadence suitable for voice performance.\n"
            "4. CONTEXTUAL HINDUSTANI (आटे में नमक जितनी उर्दू): Use Urdu vocabulary as natural atmospheric and emotional "
            "seasoning (रूह, ख़ौफ़, सन्नाटा, ज़ख़्म, ख़ंजर, दस्तक, जिस्म, हवस, सुकून, शराब) where scene atmosphere and character "
            "background justify it. Do not force an artificial quota.\n"
            "5. CHARACTER LINGUISTIC IDENTITY: Preserve each speaker's distinct voice, sentence rhythm, sarcasm, and honorific shifts. "
            "Do not reduce every character to the same generic Hindi narrator tone.\n"
            "6. CANONICAL TERMINOLOGY: Strictly adhere to the canonical Book Bible proper nouns and fantasy terminology.\n"
            "7. ZERO METADATA / ZERO CHATTER: Output ONLY the translated literary prose in Devanagari Markdown. "
            "Do not include translator notes, commentary, disclaimers, or scene overviews."
        )


def get_default_translation_policy() -> TranslationPolicyConfig:
    return TranslationPolicyConfig()
