#!/usr/bin/env python3
"""
Audiobook Factory - Script Engine: Pass 2 Performance Director & Spatial Audio Staging.
Enriches isolated dialogue turns with Stanislavski subtext, actioning verbs, dynamic headroom,
and spatial positioning.
"""

from __future__ import annotations
import json
import logging
from typing import List, Dict, Any, Optional

from audiobook_factory.llm_client import call_gemini
from audiobook_factory.model_manager import TaskType, LLMUnavailableError
from audiobook_factory.script.dialogue_parser import _parse_dialogue_turns_llm

logger = logging.getLogger("AudiobookFactory")


def _enrich_performance_and_staging_llm(
    segments: List[Dict[str, Any]],
    dramatic_context: str = "",
    is_hindi: bool = False,
) -> List[Dict[str, Any]]:
    """
    Pass 2: Performance Director & Spatial Audio Staging.
    Focuses 100% on Stanislavski subtext, actioning verbs, dynamic headroom intensity,
    delivery styles, spatial proximity, and azimuth panning (-0.8 to +0.8).
    """
    if not segments:
        return segments

    # Prepare compact turn manifest for Pass 2 LLM
    compact_turns = []
    for s in segments:
        compact_turns.append({
            "index": s.get("index", 1),
            "speaker": s.get("speaker", "Narrator"),
            "type": s.get("type", "narration"),
            "text": s.get("text", "")[:300],
        })

    sys_prompt = (
        "You are an Academy-Award winning Audio Drama Director and Stanislavski Performance Coach. "
        "Enrich each dialogue turn with deep psychological subtext, transitive actioning verbs, "
        "concealed inner emotions, dynamic intensity headroom, acting delivery style, and spatial audio staging.\n\n"
        "Guidelines:\n"
        "- 'actioning': transitive dramatic intent verb (e.g. 'threaten', 'deflect', 'reassure', 'confess', 'probe', 'comfort', 'intimidate', 'negotiate', 'mock', 'persuade').\n"
        "- 'subtext': unsaid psychological motivation or truth beneath the dialogue.\n"
        "- 'underlying_emotion': concealed emotional state conflicting with surface presentation.\n"
        "- 'intensity_level': 'low' (whispered/intimate), 'medium' (standard), 'high' (confrontation), 'explosive' (climactic screams/battle cries).\n"
        "- 'acting': {'delivery_style': 'whispering_fear' | 'cold_menace' | 'breathless_exhaustion' | 'ironic_mockery' | 'bellowing_rage' | 'combat_strain' | 'calm_authoritative' | 'gentle_tender' | 'neutral'}.\n"
        "- 'spatial': {'proximity': 'intimate_close' | 'normal_room' | 'distant', 'azimuth_pan': float between -0.8 and +0.8 (e.g. speaker A at -0.3, speaker B at +0.3)}.\n"
        "- 'acoustic_env': environmental tone (e.g. 'domestic_room', 'suburban_street_day', 'dense_forest_night', 'stone_crypt')."
    )

    prompt = f"""Dramatic Scene & Beat Context:
{dramatic_context if dramatic_context else "Standard narrative encounter."}

Dialogue Turns to Enrich (JSON):
```json
{json.dumps(compact_turns, ensure_ascii=False, indent=2)}
```

Output JSON: A list of objects where each object corresponds by "index" to the input turns:
[
  {{
    "index": int,
    "actioning": string,
    "subtext": string,
    "underlying_emotion": string,
    "intensity_level": "low" | "medium" | "high" | "explosive",
    "acting": {{"delivery_style": string}},
    "spatial": {{"proximity": string, "azimuth_pan": float}},
    "acoustic_env": string
  }}
]
"""

    try:
        enriched_list = call_gemini(
            prompt=prompt,
            system_instruction=sys_prompt,
            task_type=TaskType.SCREENPLAY,
            response_mime_type="application/json",
            max_output_tokens=16384,
            thinking_budget=1024,
            max_retries=8,
        )
    except Exception as e:
        logger.warning(f"  [!] Pass 2 performance enrichment notice: {e}. Preserving Pass 1 baseline.")
        return segments

    if isinstance(enriched_list, dict):
        for k in ("turns", "enriched", "segments", "items"):
            if k in enriched_list and isinstance(enriched_list[k], list):
                enriched_list = enriched_list[k]
                break

    if not isinstance(enriched_list, list):
        return segments

    # Merge by index
    enrich_map = {item.get("index"): item for item in enriched_list if isinstance(item, dict) and "index" in item}
    for seg in segments:
        s_idx = seg.get("index")
        if s_idx in enrich_map:
            e = enrich_map[s_idx]
            if e.get("actioning"):
                seg["actioning"] = e["actioning"]
            if e.get("subtext"):
                seg["subtext"] = e["subtext"]
            if e.get("underlying_emotion"):
                seg["underlying_emotion"] = e["underlying_emotion"]
            if e.get("intensity_level"):
                seg["intensity_level"] = e["intensity_level"]
            if isinstance(e.get("acting"), dict):
                seg["acting"] = e["acting"]
            if isinstance(e.get("spatial"), dict):
                seg["spatial"] = e["spatial"]
            if e.get("acoustic_env"):
                seg["acoustic_env"] = e["acoustic_env"]

    return segments


def _parse_dramatized_chunk_llm(
    chunk_text: str,
    preceding_context: str = "",
    is_hindi: bool = False,
    character_roster: Optional[Dict[str, Any]] = None,
    api_key: str = "",
    model: str = "",
    max_retries: int = 3,
    dramatic_context: str = "",
) -> List[Dict[str, Any]]:
    """
    Two-Pass Decoupled Screenplay Parser:
    Pass 1: Pure Dialogue Isolation & Speaker Attribution.
    Pass 2: Performance Director & Spatial Audio Staging.
    """
    # Pass 1: Dialogue isolation and speaker attribution
    pass1_turns = _parse_dialogue_turns_llm(
        chunk_text=chunk_text,
        preceding_context=preceding_context,
        is_hindi=is_hindi,
        character_roster=character_roster,
    )
    if not pass1_turns:
        if chunk_text.strip():
            logger.error("  [!] STRICT HALT: Pass 1 Dialogue Parsing failed to return valid turns.")
            raise LLMUnavailableError(
                "STRICT HALT: Screenplay generation LLM failed to produce valid dialogue turns for chunk."
            )
        return []

    # Pass 2: Performance Director & Spatial Staging enrichment
    enriched_turns = _enrich_performance_and_staging_llm(
        segments=pass1_turns,
        dramatic_context=dramatic_context,
        is_hindi=is_hindi,
    )
    return enriched_turns
