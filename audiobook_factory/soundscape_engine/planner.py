#!/usr/bin/env python3
"""
Audiobook Factory - Soundscape Engine: Director Soundscape Planner.
Generates structured Soundscape JSON plans mapping screenplay segments to stems and SFX cues.
"""

from __future__ import annotations
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any

from audiobook_factory.logger import logger


def generate_chapter_soundscape_plan(
    chapter_text: Any,
    script_data: Any,
    model: str | None = None,
) -> Dict[str, Any]:
    """
    Generate a Director Soundscape JSON Plan via Gemini Flash.
    Maps screenplay segment index ranges to scene moods, audio stems, and SFX cues.
    Handles flexible caller signatures (e.g. chapter_id + chapter_text/script_data).
    """
    from audiobook_factory.key_manager import get_persistent_key_pool
    from audiobook_factory.model_manager import get_model_manager, TaskType, LLMUnavailableError

    pool = get_persistent_key_pool()
    api_key = pool.get_key(service="text") if pool else None
    if not api_key:
        try:
            from audiobook_factory.tts_dispatcher import global_key_pool
            api_key = global_key_pool.get_key(service="text")
        except Exception:
            pass

    if not api_key:
        raise LLMUnavailableError("STRICT HALT: No text API key available for soundscape plan generation.")

    from audiobook_factory.cadence import get_stealth_sdk_headers

    if not model:
        model = get_model_manager().resolve_active_model(TaskType.SOUND_DESIGN, api_key=api_key)

    # Coerce script_data if passed as string or non-list
    if isinstance(script_data, str):
        script_list = [{"text": script_data}]
    elif isinstance(script_data, list):
        script_list = script_data
    else:
        script_list = []

    # Sample screenplay segments for prompt context (compact)
    seg_summary = []
    for idx, s in enumerate(script_list[:50]):
        if isinstance(s, dict):
            seg_summary.append({
                "index": s.get("index", idx + 1),
                "type": s.get("type", "narration"),
                "speaker": s.get("speaker", "Narrator"),
                "emotion": s.get("emotion", "neutral"),
                "text": str(s.get("text", ""))[:70],
            })
        else:
            seg_summary.append({
                "index": idx + 1,
                "type": "narration",
                "speaker": "Narrator",
                "emotion": "neutral",
                "text": str(s)[:70],
            })

    prompt = f"""You are an expert audio drama sound director.
Given this chapter's screenplay segments, produce a structured Soundscape JSON Plan.

Available Audio Stems (moods):
- "peaceful": Calm, warm acoustic or ambient pad (nature, morning, peaceful discussion)
- "mysterious": Eerie suspense, ancient ruins, investigation, curiosity, subtle low drone
- "tense": Heart-pounding suspense, urgency, darkness, danger, confrontation
- "emotional": Melancholic, poignant, reflective drama (sadness, memory, farewell)
- "epic": Grand, majestic orchestral swell (discovery, climax, triumph)
- "default": Warm cinematic lo-fi background bed

Available SFX Cues:
- "lamp_ignite", "wind_gust", "page_turn", "door_creak", "thunder", "footsteps", "heartbeat", "rain"

Screenplay Segments:
{json.dumps(seg_summary, ensure_ascii=False, indent=2)}

Output JSON Schema:
{{
  "primary_mood": "peaceful" | "mysterious" | "tense" | "emotional" | "epic" | "default",
  "ducking_attenuation_db": -16.0,
  "scenes": [
    {{
      "scene_id": 1,
      "segment_start": 1,
      "segment_end": int,
      "mood": "peaceful" | "mysterious" | "tense" | "emotional" | "epic" | "default",
      "stem": "peaceful" | "mysterious" | "tense" | "emotional" | "epic" | "default",
      "ambient_volume": float (between 0.2 and 0.4),
      "description": "Brief scene description"
    }}
  ],
  "sfx_cues": [
    {{
      "segment_index": int,
      "cue": str,
      "timing": "before" | "under" | "after",
      "volume": float (between 0.3 and 0.6)
    }}
  ]
}}
Return ONLY valid JSON.
"""

    from audiobook_factory.safety import get_universal_safety_settings
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
        "safetySettings": get_universal_safety_settings(),
    }

    max_retries = 3
    for attempt in range(max_retries):
        if not api_key:
            api_key = pool.get_key(service="text") if pool else None
            if not api_key:
                try:
                    from audiobook_factory.tts_dispatcher import global_key_pool
                    api_key = global_key_pool.get_key(service="text")
                except Exception:
                    pass
            if not api_key:
                break
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=get_stealth_sdk_headers(api_key),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=35.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(content)
        except urllib.error.HTTPError as e:
            if e.code == 429 and pool:
                pool.mark_temporary_backoff(api_key, 15.0)
            if e.code in (429, 503) and attempt < max_retries - 1:
                wait_sec = 2.0 * (attempt + 1)
                print(f"  [WAIT] Gemini API HTTP {e.code}. Rotating key and retrying in {wait_sec}s (Attempt {attempt+1}/{max_retries})...")
                time.sleep(wait_sec)
                api_key = pool.get_key(service="text") if pool else None
                continue
            logger.error(f"  [!] Soundscape plan generation HTTP error ({e.code}). STRICT HALT.")
            raise LLMUnavailableError(f"Soundscape plan generation HTTP {e.code} error: {e}. Production strictly halted.")
        except Exception as e:
            logger.error(f"  [!] Soundscape plan generation failed ({e}). STRICT HALT.")
            raise LLMUnavailableError(f"Soundscape plan generation failed: {e}. Production strictly halted.")

    logger.error("  [!] STRICT HALT: Soundscape plan generation exhausted all retries.")
    raise LLMUnavailableError("Soundscape plan generation exhausted all retries. Production strictly halted.")


def generate_project_soundscapes(project_dir: Path) -> Path:
    """Generates JSON soundscape plans for all chapters in project."""
    project_dir = Path(project_dir).resolve()
    scripts_dir = project_dir / "scripts"
    soundscapes_dir = project_dir / "soundscapes"
    soundscapes_dir.mkdir(parents=True, exist_ok=True)

    script_files = sorted(scripts_dir.glob("chapter_*_script.json"))
    if not script_files:
        raise FileNotFoundError(f"No screenplay scripts found in {scripts_dir}")

    print(f"[*] Building Soundscape JSON Plans for {len(script_files)} chapters...")
    for sf in script_files:
        chap_stem = sf.stem.replace("_script", "")
        plan_file = soundscapes_dir / f"{chap_stem}_soundscape.json"
        if plan_file.exists() and plan_file.stat().st_size > 50:
            print(f"  [-] Soundscape plan already exists: {plan_file.name} (Skipping)")
            continue

        with open(sf, "r", encoding="utf-8") as f:
            script_data = json.load(f)

        plan = generate_chapter_soundscape_plan("", script_data)
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        print(f"  [+] Soundscape plan generated -> {plan_file.name}")

    return soundscapes_dir
