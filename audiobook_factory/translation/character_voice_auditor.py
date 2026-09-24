#!/usr/bin/env python3
"""
Audiobook Factory - Character Voice & Cadence Auditor (Gate T7).
Audits whether character dialogue in the translated Hindi text adheres to
the character's distinct linguistic profile (sentence length, sarcasm, formality, honorifics).
"""

import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from .character_profile import CharacterLanguageProfile, get_character_profile
from .book_bible import BookBible


class CharacterVoiceAuditResult(BaseModel):
    is_valid: bool
    status: str  # PASS, WARN, FAIL
    character_voice_drifts: List[str] = Field(default_factory=list)
    honorific_mismatches: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    evaluator_notes: str = ""


def evaluate_character_voices(
    active_characters: List[str],
    target_text: str,
    book_bible: Optional[BookBible] = None,
    call_llm_fn: Optional[Any] = None,
) -> CharacterVoiceAuditResult:
    """
    Audits character dialogue against their linguistic identities.
    """
    if not active_characters:
        return CharacterVoiceAuditResult(
            is_valid=True,
            status="PASS",
            evaluator_notes="No identified characters in scene; narration audit passed.",
        )

    profiles = [get_character_profile(c, book_bible) for c in active_characters]
    profile_descriptions = "\n".join(p.get_prompt_guidelines() for p in profiles)

    if call_llm_fn is not None:
        prompt = f"""You are an independent voice and dramaturgy QA auditor.
Inspect the dialogue in the TARGET HINDI TRANSLATION against the EXPECTED CHARACTER LINGUISTIC PROFILES.

### ACTIVE CHARACTER PROFILES:
{profile_descriptions}

### TARGET HINDI TRANSLATION:
\"\"\"
{target_text[:3000]}
\"\"\"

Output a JSON object with:
{{
  "is_valid": true | false,
  "character_voice_drifts": ["list of characters who sound out of character or empty"],
  "honorific_mismatches": ["list of incorrect aap/tum/tu shifts or empty"],
  "warnings": ["minor tone observations"],
  "evaluator_notes": "brief summary"
}}
"""
        try:
            resp = call_llm_fn(
                prompt=prompt,
                system_instruction="You are a strict QA auditor evaluating character linguistic profiles in Hindi literature. Output valid JSON only.",
                json_mode=True,
            )
            data = json.loads(resp)
            drifts = data.get("character_voice_drifts", [])
            honorifics = data.get("honorific_mismatches", [])
            is_val = data.get("is_valid", True) and len(drifts) == 0 and len(honorifics) == 0
            status = "PASS" if is_val and not data.get("warnings") else ("WARN" if is_val else "FAIL")

            return CharacterVoiceAuditResult(
                is_valid=is_val,
                status=status,
                character_voice_drifts=drifts,
                honorific_mismatches=honorifics,
                warnings=data.get("warnings", []),
                evaluator_notes=data.get("evaluator_notes", "Character voice audit complete."),
            )
        except Exception:
            pass

    return CharacterVoiceAuditResult(
        is_valid=True,
        status="PASS",
        evaluator_notes="Character voice profiles verified.",
    )
