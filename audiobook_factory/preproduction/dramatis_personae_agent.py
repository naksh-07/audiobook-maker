#!/usr/bin/env python3
"""
Audiobook Factory - Room 1 Agent A: Dramatis Personae Agent.
Discovers and profiles all characters across a novel's chapters:
extracts canonical Devanagari spellings, gender, aliases, vocal archetypes,
Hindustani sociolect traits, and default honorific power levels (Aap/Tum/Tu).
"""

from __future__ import annotations
import json
import logging
from typing import List, Dict, Any, Optional, Callable

from audiobook_factory.llm_client import call_gemini as default_call_gemini
from audiobook_factory.model_manager import get_model_manager, TaskType
from audiobook_factory.safety import get_dramatic_fiction_framing

logger = logging.getLogger("AudiobookFactory")


class DramatisPersonaeAgent:
    """Agent A: Full-Novel Casting & Character Profiling Specialist."""

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        return get_model_manager().resolve_active_model(TaskType.EXTRACTION)

    def extract_dramatis_personae(
        self,
        novel_text_sample: str,
        book_metadata: Dict[str, Any],
        book_dna: Optional[Dict[str, Any]] = None,
        call_llm_fn: Optional[Callable[..., Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Extracts complete character dossier across novel text."""
        model = self._resolve_model()
        book_title = book_metadata.get("title", "Unknown Novel")
        author = book_metadata.get("author", "Unknown Author")

        fiction_framing = get_dramatic_fiction_framing(title=book_title, author=author)

        dna_hint = ""
        if book_dna:
            trad = book_dna.get("literary_tradition", "")
            cadence = book_dna.get("regional_dialect_cadence", "")
            hon = book_dna.get("honorific_dynamics", "")
            dna_hint = f"\nLiterary Context: Tradition: {trad}, Cadence: {cadence}, Honorific Dynamic: {hon}\n"

        sys_prompt = (
            fiction_framing +
            "You are an expert Hollywood Casting Director and Literary Character Profiler.\n"
            "Analyze the novel's text and identify all characters. "
            "For each character, provide accurate Devanagari Hindi spellings, vocal archetypes, "
            "Hindustani sociolect traits, and default honorific levels.\n"
            + dna_hint + "\n"
            "Guidelines:\n"
            "- 'english_name': string (canonical name as written in English)\n"
            "- 'hindi_name': string (phonetically accurate Devanagari transliteration)\n"
            "- 'gender': 'male' | 'female' | 'other'\n"
            "- 'aliases': list of strings (alternative names, nicknames, titles)\n"
            "- 'prominence': 'lead' | 'major' | 'minor' | 'incidental'\n"
            "- 'vocal_archetype': string (e.g. 'deep gravelly baritone', 'caustic aristocratic alto', 'youthful tenor', 'weathered rustic bass')\n"
            "- 'sociolect_trait': string (dynamically derived sociolect fitting the novel's literary world and social hierarchy, e.g. 'POOR_OPPRESSED_PEASANT', 'ORTHODOX_PRIEST_LANDLORD', 'FEUDAL_ZAMINDAR', 'CYNICAL_MONSTER_HUNTER', 'STREET_THUG', 'ARISTOCRATIC_COMMANDER', 'NEUTRAL')\n"
            "- 'recommended_pronoun_level': 'aap' | 'tum' | 'tu'\n"
            "- 'speech_quirks': string (cadence quirks, verbal tics, laconic grunts, respectful deferrals, etc.)"
        )

        prompt = f"""Book Title: {book_title}
Author: {author}

Novel Passage Samples:
\"\"\"
{novel_text_sample[:120000]}
\"\"\"

Output JSON: A list of character profile objects:
[
  {{
    "english_name": string,
    "hindi_name": string,
    "gender": "male" | "female" | "other",
    "aliases": [string],
    "prominence": "lead" | "major" | "minor" | "incidental",
    "vocal_archetype": string,
    "sociolect_trait": string,
    "recommended_pronoun_level": "aap" | "tum" | "tu",
    "speech_quirks": string
  }}
]
"""
        logger.info(f"  [DramatisPersonaeAgent] Profiling characters across novel using {model}...")

        try:
            if call_llm_fn:
                raw = call_llm_fn(prompt=prompt, system_instruction=sys_prompt, model=model, json_mode=True)
                if isinstance(raw, str):
                    import json_repair
                    res = json_repair.loads(raw)
                else:
                    res = raw
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
            logger.warning(f"  [!] DramatisPersonaeAgent error: {e}")
            return []

        if isinstance(res, dict):
            for k in ("characters", "dramatis_personae", "roster", "items"):
                if k in res and isinstance(res[k], list):
                    res = res[k]
                    break

        return res if isinstance(res, list) else []
