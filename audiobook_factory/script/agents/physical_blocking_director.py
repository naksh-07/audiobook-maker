#!/usr/bin/env python3
"""
Audiobook Factory - Room 3 Agent C: Physical Blocking & Spatial Director.
Directs character physical blocking (standing, sitting, pacing, leaning in),
maps choreography to spatial proximity zones ('intimate_close', 'normal_room', 'distant'),
and establishes stable stereo azimuth panning coordinates (-0.8 to +0.8).
"""

from __future__ import annotations
import json
import logging
from typing import List, Dict, Any, Optional, Callable

from audiobook_factory.llm_client import call_gemini as default_call_gemini
from audiobook_factory.model_manager import get_model_manager, TaskType

logger = logging.getLogger("AudiobookFactory")


class PhysicalBlockingDirector:
    """Agent C: Physical Choreography & Spatial Audio Staging Specialist."""

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        return get_model_manager().resolve_active_model(TaskType.SCREENPLAY)

    def direct_blocking(
        self,
        segments: List[Dict[str, Any]],
        dramatic_context: str = "",
        call_llm_fn: Optional[Callable[..., Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Directs physical blocking postures, proximity, and azimuth panning coordinates."""
        if not segments:
            return segments

        # Build speaker list to help LLM assign stable acoustic soundstage
        speakers = sorted(list({s.get("speaker", "Narrator") for s in segments}))

        compact_turns = [
            {
                "index": s.get("index", 1),
                "speaker": s.get("speaker", "Narrator"),
                "type": s.get("type", "narration"),
                "text": s.get("text", "")[:250],
            }
            for s in segments
        ]

        sys_prompt = (
            "You are an expert Hollywood Spatial Audio Designer and Theatrical Blocking Director.\n"
            "Your task is to position characters physically in the soundscape and assign spatial audio coordinates.\n\n"
            "Directing Invariants:\n"
            "1. NARRATOR PLACEMENT: The Narrator MUST ALWAYS be centered (pan: 0.0, proximity: 'normal_room', blocking: 'standing').\n"
            "2. SOUNDSTAGE SEPARATION: Distinct characters engaging in dialogue MUST occupy distinct stereo coordinates "
            "(e.g., Speaker A at pan -0.35, Speaker B at pan +0.35). Do NOT clump all speakers at 0.0.\n"
            "3. STABLE SPATIAL ANCHORS: A character's pan coordinate must remain consistent across dialogue turns, "
            "UNLESS the narrative describes them physically moving (e.g., walking across the room, approaching, circling).\n"
            "4. PHYSICAL BLOCKING: Assign character physical posture/choreography: "
            "'sitting', 'standing', 'pacing', 'leaning_close', 'retreating', 'lying_down', 'approaching'.\n"
            "5. PROXIMITY ZONES: Choose from 'intimate_close' (whispers, lovers, knife at throat), 'normal_room' (conversation), 'distant' (shouts from doorway, calls across square).\n"
            "6. ACOUSTIC ENV: Select the acoustic environment (e.g. 'tavern_hearth', 'stone_keep', 'dense_forest_night', 'open_road', 'quiet_chamber')."
        )

        prompt = f"""Dramatic Scene Context:
{dramatic_context if dramatic_context else "Standard narrative encounter."}

Active Speakers in Scene: {json.dumps(speakers, ensure_ascii=False)}

Dialogue Turns to Stage (JSON):
```json
{json.dumps(compact_turns, ensure_ascii=False, indent=2)}
```

Output JSON: A list of objects matching by "index":
[
  {{
    "index": int,
    "physical_blocking": "sitting" | "standing" | "pacing" | "leaning_close" | "retreating" | "lying_down" | "approaching",
    "spatial": {{
      "proximity": "intimate_close" | "normal_room" | "distant",
      "azimuth_pan": float between -0.8 and +0.8
    }},
    "acoustic_env": string
  }}
]
"""
        model = self._resolve_model()
        logger.info(f"  [PhysicalBlockingDirector] Staging physical blocking for {len(segments)} segments...")

        try:
            if call_llm_fn:
                staged = call_llm_fn(prompt=prompt, system_instruction=sys_prompt, model=model, json_mode=True)
                if isinstance(staged, str):
                    import json_repair
                    staged = json_repair.loads(staged)
            else:
                staged = default_call_gemini(
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
            logger.warning(f"  [!] PhysicalBlockingDirector notice: {e}. Preserving input baseline.")
            return segments

        if isinstance(staged, dict):
            for k in ("turns", "staged", "segments", "items", "results"):
                if k in staged and isinstance(staged[k], list):
                    staged = staged[k]
                    break

        if not isinstance(staged, list):
            return segments

        stage_map = {item.get("index"): item for item in staged if isinstance(item, dict) and "index" in item}
        for seg in segments:
            idx = seg.get("index")
            if idx in stage_map:
                s = stage_map[idx]
                if s.get("physical_blocking"):
                    seg["physical_blocking"] = s["physical_blocking"]
                if isinstance(s.get("spatial"), dict):
                    sp = s["spatial"]
                    seg.setdefault("spatial", {})
                    if "proximity" in sp:
                        seg["spatial"]["proximity"] = sp["proximity"]
                    if "azimuth_pan" in sp:
                        seg["spatial"]["pan"] = float(sp["azimuth_pan"])
                    elif "pan" in sp:
                        seg["spatial"]["pan"] = float(sp["pan"])
                    if s.get("physical_blocking"):
                        seg["spatial"]["physical_blocking"] = s["physical_blocking"]
                if s.get("acoustic_env"):
                    seg["acoustic_env"] = s["acoustic_env"]

        return segments
