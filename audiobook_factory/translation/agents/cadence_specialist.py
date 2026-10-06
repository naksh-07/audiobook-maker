#!/usr/bin/env python3
"""
Audiobook Factory - Room 2 Agent B: Hindustani Cadence Specialist.
Transforms literary written Hindi into rhythmic, spoken studio Hindustani.
Tunes dialogue breath pauses, prosody, and relational honorific power shifts (Aap/Tum/Tu/Maai-Baap).
"""

from __future__ import annotations
import os
import json
import time
from typing import Dict, Any, Optional, Callable

from audiobook_factory.logger import logger
from audiobook_factory.model_manager import get_model_manager, TaskType
from audiobook_factory.safety import get_dramatic_fiction_framing
from audiobook_factory.sanitizer import validate_and_sanitize_translation
from audiobook_factory.llm_client import call_gemini as default_call_gemini


class HindustaniCadenceSpecialist:
    """Agent B: Dialogue Flow, Spoken Prosody & Honorifics Power-Shift Specialist.
    Refines the initial draft so voice actors deliver organic, breathless, or imposing performances.
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        return get_model_manager().resolve_active_model(TaskType.TRANSLATION)

    def refine_cadence(
        self,
        source_text: str,
        draft_hindi: str,
        glossary: Dict[str, Any],
        block_title: str = "",
        preceding_context: str = "",
        call_llm_fn: Optional[Callable[..., str]] = None,
    ) -> str:
        """Optimizes the Hindi draft for spoken prosody, breath pauses, and honorific shifts."""
        model = self._resolve_model()

        # Extract character relationships / sociolects if available
        sociolect_context = ""
        if isinstance(glossary, dict):
            chars = glossary.get("characters", [])
            relationships = glossary.get("relationships", [])
            if chars:
                sociolect_context += f"\nKnown Characters & Sociolects: {json.dumps(chars, ensure_ascii=False)}"
            if relationships:
                sociolect_context += f"\nRelationship & Honorific Dynamics: {json.dumps(relationships, ensure_ascii=False)}"

        book_title = None
        book_author = None
        if isinstance(glossary, dict):
            meta = glossary.get("book_metadata") or {}
            book_title = meta.get("title") or glossary.get("title")
            book_author = meta.get("author") or glossary.get("author")

        fiction_framing = get_dramatic_fiction_framing(title=book_title, author=book_author)

        system_instruction = (
            fiction_framing +
            "You are a veteran Audio Drama Dialogue Director and Voice Cadence Specialist.\n"
            "Your task is to refine a Hindi literary draft for professional full-cast audiobook voice actors.\n\n"
            "Key Focus Areas:\n"
            "1. SPOKEN HINDUSTANI CADENCE (ANTI-SANSKRITIZATION): Eliminate stiff, written translation artifacts and Sanskritized bookish words. "
            "Never let actors say bookish words like 'युवतियां', 'साक्षात काल रूपी', 'तर्क', 'विस्मित', 'कदाचित'. "
            "Rewrite into fluid, natural spoken Hindustani ('लड़कियां/औरतें', 'मौत', 'सौदा', 'हैरान', 'शायद') that rolls effortlessly off an actor's tongue.\n"
            "2. ACTOR BREATH & PAUSE PUNCTUATION: Use natural punctuation (em-dashes '—', ellipses '...', commas ',') "
            "to guide voice actor breathing, dramatic hesitations, sudden interruptions, and suspenseful beats.\n"
            "3. HONORIFIC POWER DYNAMICS (TU <-> MAAI-BAAP): Check pronouns ('आप' vs 'तुम' vs 'तू'). Enforce dynamic shifts: "
            "when an arrogant thug is subdued, their speech collapses from arrogant 'तू' to pleading 'हुज़ूर / माई-बाप / सरकार'. "
            "When comrades share a drink, use casual 'तुम'. Formal nobility maintains cold 'आप'.\n"
            "4. COMBAT & TENSION STACCATO: During action beats or fight scenes, break down long sentences into rapid, "
            "punchy staccato fragments (e.g. 'कदम पीछे। तलवार का पैंतरा। वार। चूक गया!').\n"
            "5. PRESERVATION INVARIANT: Do NOT summarize, drop, or alter plot points, names, or actions from the draft. "
            "Output ONLY the refined passage in Devanagari Markdown without any meta-commentary, notes, or introductions."
        )

        prompt = f"""### CHARACTER & SOCIOLECT REGISTER:
{sociolect_context if sociolect_context else "Standard literary context."}

### ORIGINAL ENGLISH SOURCE ({block_title}):
\"\"\"
{source_text}
\"\"\"

### CURRENT HINDI DRAFT TO REFINE:
\"\"\"
{draft_hindi}
\"\"\"

Refine this draft for spoken audio drama cadence, actor breathing, and dynamic honorifics.
Output ONLY the refined Devanagari Markdown:
"""
        t0 = time.time()
        try:
            if call_llm_fn:
                raw = call_llm_fn(prompt=prompt, system_instruction=system_instruction, model=model).strip()
            else:
                raw = default_call_gemini(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    task_type=TaskType.TRANSLATION,
                    response_mime_type="text/plain",
                    max_output_tokens=16384,
                    max_retries=6,
                    model=model,
                    return_raw_text=True,
                    thinking_budget=512,
                ).strip()

            elapsed = time.time() - t0
            logger.info(f"  [HindustaniCadenceSpecialist] Cadence refined in {elapsed:.2f}s ({len(raw)} chars)")

            is_valid, cleaned, reason = validate_and_sanitize_translation(raw, is_hindi=True)
            if not is_valid:
                logger.warning(f"  [HindustaniCadenceSpecialist] Sanitizer warning: {reason}. Preserving previous draft.")
                return draft_hindi

            # Guard against accidental catastrophic truncation
            if len(cleaned.split()) < len(draft_hindi.split()) * 0.70:
                logger.warning("  [HindustaniCadenceSpecialist] Cadence pass caused significant truncation. Falling back to draft.")
                return draft_hindi

            return cleaned

        except Exception as e:
            logger.warning(f"  [!] HindustaniCadenceSpecialist error: {e}. Falling back to initial draft.")
            return draft_hindi
