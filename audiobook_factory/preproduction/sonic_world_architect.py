#!/usr/bin/env python3
"""
Audiobook Factory - Room 1 Agent B: Sonic World Architect.
Analyzes a novel's physical environment, period setting, and recurring spaces.
Generates sonic_bible.json containing world acoustic DNA, room impulse reverb targets,
and signature foley palettes for living-world audio drama mixing.
"""

from __future__ import annotations
import json
import logging
from typing import Dict, Any, Optional, Callable

from audiobook_factory.llm_client import call_gemini as default_call_gemini
from audiobook_factory.model_manager import get_model_manager, TaskType
from audiobook_factory.safety import get_dramatic_fiction_framing

logger = logging.getLogger("AudiobookFactory")


class SonicWorldArchitect:
    """Agent B: Acoustic Worldbuilding & Sonic Genome Architect."""

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        return get_model_manager().resolve_active_model(TaskType.DIRECTING)

    def design_sonic_bible(
        self,
        novel_text_sample: str,
        book_metadata: Dict[str, Any],
        call_llm_fn: Optional[Callable[..., Any]] = None,
    ) -> Dict[str, Any]:
        """Synthesizes the complete sonic_bible.json for the novel."""
        model = self._resolve_model()
        book_title = book_metadata.get("title", "Unknown Novel")
        author = book_metadata.get("author", "Unknown Author")

        fiction_framing = get_dramatic_fiction_framing(title=book_title, author=author)

        sys_prompt = (
            fiction_framing +
            "You are an Academy-Award winning Audio Drama Supervising Sound Editor and Acoustic Architect.\n"
            "Analyze the novel's environments, physical props, recurring locations, and era. "
            "Synthesize an authoritative sonic_bible.json specifying the world's acoustic DNA, "
            "convolution reverb profiles per environment, and signature tactile foley palettes.\n\n"
            "Requirements:\n"
            "- 'primary_era': string (e.g. 'medieval_dark_fantasy', 'victorian_gothic', 'contemporary_noir', 'cyberpunk')\n"
            "- 'acoustic_spaces': map of location keys to objects containing:\n"
            "  * 'reverb_type': string (e.g. 'medium_wooden_tavern', 'stone_keep_hall', 'dense_outdoor_forest', 'damp_cavern')\n"
            "  * 'wet_mix': float (0.05 to 0.35)\n"
            "  * 'predelay_ms': int (5 to 45)\n"
            "  * 'decay_time_s': float (0.5 to 3.5)\n"
            "  * 'dominant_materials': list of strings (e.g. ['wood', 'stone', 'pewter', 'iron'])\n"
            "- 'signature_foley_palettes': map of character/archetype to list of tactile foley actions\n"
            "- 'world_ambience_motifs': list of objects with 'name', 'description', 'time_of_day'"
        )

        prompt = f"""Book Title: {book_title}
Author: {author}

Sample Passages Across Novel:
\"\"\"
{novel_text_sample[:16000]}
\"\"\"

Output JSON: An object representing sonic_bible.json:
{{
  "project_id": "proj-{book_metadata.get('project_slug', 'novel')}",
  "book_title": "{book_title}",
  "primary_era": string,
  "acoustic_spaces": {{
    "environment_name": {{
      "reverb_type": string,
      "wet_mix": float,
      "predelay_ms": int,
      "decay_time_s": float,
      "dominant_materials": [string]
    }}
  }},
  "signature_foley_palettes": {{
    "archetype_or_character": [string]
  }},
  "world_ambience_motifs": [
    {{
      "name": string,
      "description": string,
      "time_of_day": string
    }}
  ]
}}
"""
        logger.info(f"  [SonicWorldArchitect] Synthesizing sonic bible for '{book_title}' using {model}...")

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
                    task_type=TaskType.DIRECTING,
                    response_mime_type="application/json",
                    max_output_tokens=16384,
                    thinking_budget=1024,
                    max_retries=6,
                    model=model,
                )
        except Exception as e:
            logger.warning(f"  [!] SonicWorldArchitect error: {e}. Falling back to default universal acoustic bible.")
            res = {}

        if not isinstance(res, dict) or not res.get("acoustic_spaces"):
            res = {
                "project_id": f"proj-{book_metadata.get('project_slug', 'novel')}",
                "book_title": book_title,
                "primary_era": "universal_contemporary",
                "acoustic_spaces": {
                    "indoor_room": {
                        "reverb_type": "medium_room",
                        "wet_mix": 0.15,
                        "predelay_ms": 20,
                        "decay_time_s": 1.2,
                        "dominant_materials": ["wood", "cloth"],
                    },
                    "outdoor_open": {
                        "reverb_type": "open_outdoor",
                        "wet_mix": 0.06,
                        "predelay_ms": 8,
                        "decay_time_s": 0.6,
                        "dominant_materials": ["dirt", "vegetation"],
                    },
                },
                "signature_foley_palettes": {
                    "general": ["cloth_rustle", "footstep", "table_physics"],
                },
                "world_ambience_motifs": [],
            }

        return res
