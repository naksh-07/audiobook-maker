#!/usr/bin/env python3
"""
Audiobook Factory - Room 3 Agent B: Stanislavski Subtext Director.
Directs voice acting subtext, transitive actioning verbs, concealed inner emotions,
acting delivery styles, and dynamic intensity headroom.
"""

from __future__ import annotations
import json
import logging
from typing import List, Dict, Any, Optional, Callable

from audiobook_factory.llm_client import call_gemini as default_call_gemini
from audiobook_factory.model_manager import get_model_manager, TaskType
from audiobook_factory.safety import get_dramatic_fiction_framing

logger = logging.getLogger("AudiobookFactory")


class StanislavskiSubtextDirector:
    """Agent B: Psychological Actioning & Acting Delivery Specialist."""

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        return get_model_manager().resolve_active_model(TaskType.SCREENPLAY)

    def direct_subtext(
        self,
        segments: List[Dict[str, Any]],
        dramatic_context: str = "",
        is_hindi: bool = False,
        call_llm_fn: Optional[Callable[..., Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Enriches segments with Stanislavski psychological subtext and acting directives."""
        if not segments:
            return segments

        compact_turns = [
            {
                "index": s.get("index", 1),
                "speaker": s.get("speaker", "Narrator"),
                "type": s.get("type", "narration"),
                "text": s.get("text", "")[:300],
            }
            for s in segments
        ]

        sys_prompt = (
            get_dramatic_fiction_framing()
            + "You are an Academy-Award winning Audio Drama Director and Stanislavski Performance Coach.\n"
            "Enrich each dialogue turn with deep psychological subtext, transitive actioning verbs, "
            "concealed inner emotions, dynamic intensity headroom, and acting delivery style.\n\n"
            "Guidelines:\n"
            "- 'actioning': transitive dramatic intent verb (e.g. 'threaten', 'deflect', 'reassure', 'confess', 'probe', 'comfort', 'intimidate', 'negotiate', 'mock', 'persuade', 'seduce').\n"
            "- 'subtext': unsaid psychological motivation or truth beneath the spoken words.\n"
            "- 'underlying_emotion': concealed emotional state conflicting with surface presentation.\n"
            "- 'intensity_level': 'low' (whispered/intimate/stealth), 'medium' (standard conversational), 'high' (confrontation/panic), 'explosive' (climactic screams/battle cries).\n"
            "- 'acting': {'delivery_style': 'whispering_fear' | 'cold_menace' | 'breathless_exhaustion' | 'ironic_mockery' | 'bellowing_rage' | 'combat_strain' | 'calm_authoritative' | 'gentle_tender' | 'neutral', 'pacing': float between 0.8 and 1.25}."
        )

        prompt = f"""{get_dramatic_fiction_framing()}Dramatic Scene & Beat Context:
{dramatic_context if dramatic_context else "Standard narrative encounter."}

Dialogue Turns to Direct (JSON):
```json
{json.dumps(compact_turns, ensure_ascii=False, indent=2)}
```

Output JSON: A list of objects matching by "index":
[
  {{
    "index": int,
    "actioning": string,
    "subtext": string,
    "underlying_emotion": string,
    "intensity_level": "low" | "medium" | "high" | "explosive",
    "acting": {{"delivery_style": string, "pacing": float}}
  }}
]
"""
        model = self._resolve_model()
        logger.info(f"  [StanislavskiSubtextDirector] Directing {len(segments)} segments with {model}...")

        try:
            if call_llm_fn:
                enriched = call_llm_fn(prompt=prompt, system_instruction=sys_prompt, model=model, json_mode=True)
                if isinstance(enriched, str):
                    import json_repair
                    enriched = json_repair.loads(enriched)
            else:
                enriched = default_call_gemini(
                    prompt=prompt,
                    system_instruction=sys_prompt,
                    task_type=TaskType.SCREENPLAY,
                    response_mime_type="application/json",
                    max_output_tokens=16384,
                    thinking_budget=1024,
                    max_retries=6,
                    model=model,
                )
        except Exception as e:
            logger.warning(f"  [!] StanislavskiSubtextDirector notice: {e}. Preserving input baseline.")
            return segments

        if isinstance(enriched, dict):
            for k in ("turns", "enriched", "segments", "items", "results"):
                if k in enriched and isinstance(enriched[k], list):
                    enriched = enriched[k]
                    break

        if not isinstance(enriched, list):
            return segments

        enrich_map = {item.get("index"): item for item in enriched if isinstance(item, dict) and "index" in item}
        for seg in segments:
            idx = seg.get("index")
            if idx in enrich_map:
                e = enrich_map[idx]
                if e.get("actioning"):
                    seg["actioning"] = e["actioning"]
                if e.get("subtext"):
                    seg["subtext"] = e["subtext"]
                if e.get("underlying_emotion"):
                    seg["underlying_emotion"] = e["underlying_emotion"]
                if e.get("intensity_level"):
                    seg["intensity_level"] = e["intensity_level"]
                if isinstance(e.get("acting"), dict):
                    seg.setdefault("acting", {})
                    seg["acting"].update(e["acting"])

        return segments
