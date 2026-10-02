#!/usr/bin/env python3
"""
Audiobook Factory - Script Engine: Pass 1 Dialogue Isolation & Speaker Attribution.
Isolates spoken quotes into dedicated dialogue segments and attributes characters from roster.
"""

from __future__ import annotations
import json
from typing import List, Dict, Any, Optional

from audiobook_factory.llm_client import call_gemini
from audiobook_factory.model_manager import TaskType


def _parse_dialogue_turns_llm(
    chunk_text: str,
    preceding_context: str = "",
    is_hindi: bool = False,
    character_roster: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Pass 1: Pure Dialogue Isolation & Speaker Attribution.
    Focuses 100% on isolating spoken dialogue into discrete segments, attributing
    speakers from the canonical character roster, and adding neural vocal tags.
    """
    sys_prompt = (
        "You are a Hollywood Audio Drama Dialogue Supervisor. "
        "Your sole responsibility is absolute dialogue turn isolation and character attribution.\n\n"
        "Core Mandates:\n"
        "1. ABSOLUTE DIALOGUE TURN ISOLATION:\n"
        "   - EVERY spoken dialogue line (anything inside quotation marks \"...\", “...”, ‘...’ or dialogue dashes) MUST be its own discrete segment with type: 'dialogue' and the canonical speaker name.\n"
        "   - NEVER, under any circumstance, merge spoken dialogue into a 'narration' segment. Even a 1-word reply (e.g. 'Yes', 'हाँ', 'Little tyke') MUST be isolated as a character dialogue.\n"
        "   - Remove redundant dialogue tags like 'he said', 'she replied', 'उसने कहा' completely from character spoken text.\n"
        "   - Surrounding narrative actions and exposition MUST be placed in separate 'narration' segments for the Narrator.\n"
        "2. CANONICAL SPEAKER ASSIGNMENT: Attribute dialogue strictly to the canonical character from Known Canon Characters. "
        "Use 'Narrator' for narration and 'Foley' for action beats. Never invent new aliases, and never assign pronouns ('he', 'she', 'उसने', 'वह') as the speaker name.\n"
        "3. NEURAL VOCAL TAGS: Prepend vocal tags directly inside the 'text' field when dialogue demands it: "
        "`[whispers]`, `[shouting]`, `[cold menace]`, `[intimate, breathy]`, `[trembling voice]`, `[sighs]`, `[gasp]`, `[growl]`, `[bellowing rage]`, `[combat strain]`, `[mocking chuckle]`.\n"
        "4. PHYSICAL ACTION BEATS: When a major physical hit occurs (door slam, gunshot, blade clash, explosion), emit type: 'action', speaker: 'Foley', text: '[ACTION]'.\n"
    )

    roster_hint = ""
    if character_roster:
        chars = character_roster.get("characters", {})
        formatted_chars = []
        if isinstance(chars, dict):
            for cname, details in chars.items():
                if cname in ("Narrator", "Foley"):
                    continue
                gender = details.get("gender", "neutral") if isinstance(details, dict) else "neutral"
                aliases = details.get("aliases", []) if isinstance(details, dict) else []
                alias_str = f", aliases: {', '.join(aliases[:4])}" if aliases else ""
                formatted_chars.append(f"{cname} [{gender}{alias_str}]")
        elif isinstance(chars, list):
            for c in chars:
                if isinstance(c, dict):
                    cname = c.get("english_name", "")
                    if cname and cname not in ("Narrator", "Foley"):
                        gender = c.get("gender", "neutral")
                        aliases = c.get("aliases", [])
                        alias_str = f", aliases: {', '.join(aliases[:4])}" if aliases else ""
                        formatted_chars.append(f"{cname} [{gender}{alias_str}]")
        if formatted_chars:
            roster_hint = (
                "\nKnown Canon Characters in Project (Use canonical English name as 'speaker'):\n"
                + "\n".join(f"- {fc}" for fc in formatted_chars)
                + "\n"
            )

    prompt = f"""Language: {"Hindi (Devanagari)" if is_hindi else "English"}
Preceding Scene Context / Characters Speaking:
{preceding_context if preceding_context else "Beginning of scene."}
{roster_hint}
Current Scene Text:
\"\"\"
{chunk_text}
\"\"\"

Output JSON: A list of objects where each object has:
- "index": int (1-based relative to this chunk)
- "type": "narration" | "dialogue" | "action" (isolate every spoken quote into a dedicated "dialogue" segment)
- "speaker": canonical character name, "Narrator", or "Foley"
- "text": spoken dialogue or narrative text with optional inline vocal tags like [whispers], [shouting], or "[ACTION]"
- "emotion": "neutral" | "angry" | "whispering" | "sad" | "excited" | "growl" | "calm_raspy"
"""

    res = call_gemini(
        prompt=prompt,
        system_instruction=sys_prompt,
        task_type=TaskType.SCREENPLAY,
        response_mime_type="application/json",
        temperature=0.2,
        max_retries=4,
    )
    if isinstance(res, list):
        return res
    if isinstance(res, dict):
        for k in ("script", "segments", "turns", "dialogue"):
            if k in res and isinstance(res[k], list):
                return res[k]
        return [res]
    return []
