#!/usr/bin/env python3
"""
Audiobook Factory - Room 1 Agent C: Phonetic & Lexicon Dramaturge.
Extracts world locations, factions, weapons, creatures, and lore terminology across the novel.
Establishes canonical Devanagari spellings and phonetic pronunciation standards (70/30 rule).
"""

from __future__ import annotations
import json
import logging
from typing import Dict, Any, Optional, Callable

from audiobook_factory.llm_client import call_gemini as default_call_gemini
from audiobook_factory.model_manager import get_model_manager, TaskType
from audiobook_factory.safety import get_dramatic_fiction_framing

logger = logging.getLogger("AudiobookFactory")


class PhoneticLexiconDramaturge:
    """Agent C: World Lexicographer & Phonetic Lore Specialist."""

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        return get_model_manager().resolve_active_model(TaskType.EXTRACTION)

    def extract_lexicon_and_phonetics(
        self,
        novel_text_sample: str,
        book_metadata: Dict[str, Any],
        call_llm_fn: Optional[Callable[..., Any]] = None,
    ) -> Dict[str, Any]:
        """Extracts locations, factions, creatures, and terms with Devanagari pronunciations."""
        model = self._resolve_model()
        book_title = book_metadata.get("title", "Unknown Novel")
        author = book_metadata.get("author", "Unknown Author")

        fiction_framing = get_dramatic_fiction_framing(title=book_title, author=author)

        sys_prompt = (
            fiction_framing +
            "You are a master Worldbuilding Lexicographer and Phonetic Director.\n"
            "Analyze the novel's text and extract all locations, factions, creatures, artifacts, and lore terms.\n"
            "Enforce the 70/30 Invariant: Proper nouns and geographic places preserve their authentic European / fantasy "
            "names in phonetically accurate Devanagari script. Fictional concepts, weapons, and creature types receive "
            "cinematic, atmospheric Hindustani equivalents.\n\n"
            "Output JSON schema with:\n"
            "- 'locations': {EnglishName: DevanagariName}\n"
            "- 'organizations': {EnglishName: DevanagariName}\n"
            "- 'creatures': {EnglishName: DevanagariName}\n"
            "- 'objects': {EnglishName: DevanagariName}\n"
            "- 'terminology': {EnglishTerm: DevanagariTranslation}"
        )

        prompt = f"""Book Title: {book_title}
Author: {author}

Novel Sample Passages:
\"\"\"
{novel_text_sample[:100000]}
\"\"\"

Output JSON: An object matching the required schema:
{{
  "locations": {{}},
  "organizations": {{}},
  "creatures": {{}},
  "objects": {{}},
  "terminology": {{}}
}}
"""
        logger.info(f"  [PhoneticLexiconDramaturge] Extracting lore lexicon for '{book_title}' using {model}...")

        try:
            if call_llm_fn:
                res = call_llm_fn(prompt=prompt, system_instruction=sys_prompt, model=model, json_mode=True)
                if isinstance(res, str):
                    import json_repair
                    res = json_repair.loads(res)
            else:
                res = default_call_gemini(
                    prompt=prompt,
                    system_instruction=sys_prompt,
                    task_type=TaskType.EXTRACTION,
                    response_mime_type="application/json",
                    max_output_tokens=16384,
                    thinking_budget=1024,
                    max_retries=6,
                    model=model,
                )
        except Exception as e:
            logger.warning(f"  [!] PhoneticLexiconDramaturge error: {e}")
            res = {}

        if not isinstance(res, dict):
            res = {}

        return {
            "locations": res.get("locations", {}),
            "organizations": res.get("organizations", {}),
            "creatures": res.get("creatures", {}),
            "objects": res.get("objects", {}),
            "terminology": res.get("terminology", {}),
        }
