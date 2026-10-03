#!/usr/bin/env python3
"""
Audiobook Factory - Soundscape Engine: Chapter Mood Detector.
Uses Gemini Flash Directing LLM to analyze emotional narrative and output
primary mood, intensity, summary, and music generation prompts.
"""

from __future__ import annotations
import json
import urllib.request
import urllib.error
from typing import Dict, Any

from audiobook_factory.logger import logger


def detect_chapter_mood(chapter_text: str, model: str | None = None) -> Dict[str, Any]:
    """
    Use Gemini to analyze the emotional narrative and tone of a chapter/scene.
    Returns recommended mood profile, intensity, and music generation prompts.
    """
    from audiobook_factory.tts_dispatcher import global_key_pool
    from audiobook_factory.model_manager import get_model_manager, TaskType, LLMUnavailableError
    api_key = global_key_pool.get_key(service="text")
    if not api_key:
        raise LLMUnavailableError("STRICT HALT: No text API key available for chapter mood detection.")

    from audiobook_factory.cadence import get_stealth_sdk_headers

    if not model:
        model = get_model_manager().resolve_active_model(TaskType.DIRECTING, api_key=api_key)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    # Sample beginning and climax for analysis (keep token size lean)
    sample_snippet = chapter_text[:2500]
    prompt = (
        "You are an expert audio director for cinematic audiobooks. "
        "Analyze the following excerpt from a book chapter and return a JSON object with: "
        "'primary_mood' (strictly one of: peaceful, mysterious, tense, emotional, epic, default), "
        "'intensity' (float from 0.1 to 1.0), "
        "'summary' (1 sentence summary of the scene atmosphere), "
        "'musicgen_prompt' (a detailed prompt for Meta MusicGen: instrumental ambient background score, NO vocals, NO loud drums, describing instruments and tempo).\n\n"
        f"Excerpt:\n{sample_snippet}\n\n"
        "Return ONLY raw valid JSON."
    )

    from audiobook_factory.safety import get_universal_safety_settings
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
        "safetySettings": get_universal_safety_settings(),
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=get_stealth_sdk_headers(api_key),
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(content)
    except Exception as e:
        logger.error(f"[!] Mood detection failed ({e}). STRICT HALT.")
        raise LLMUnavailableError(f"Chapter mood detection LLM failed: {e}. Production halted.")
