"""
Audiobook Factory - Agent 3: Master Foley & Micro-Life Artist.
Spots both explicit physical action events (doors, blades, impacts) and implicit living-world micro-foley
(wooden tankard clatter, ale pouring, cloth/leather rustle, fireplace crackle, chair scuffs).
Eliminates dead acoustic voids and grounds characters in tactile physical reality.
"""

from __future__ import annotations
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger
from audiobook_factory.llm_client import call_gemini
from audiobook_factory.model_manager import TaskType
from audiobook_factory.safety import get_dramatic_fiction_framing
from .showrunner_agent import ShowrunnerPlan


class FoleyEventDirective(BaseModel):
    """Rich foley directive emitted by the Master Foley Artist."""
    model_config = ConfigDict(extra="ignore")

    segment_index: int = Field(..., ge=1, description="1-based segment index where sound triggers")
    action_verb: str = Field(..., description="Action identifier (e.g. 'tankard_slam', 'ale_pour', 'sword_draw', 'cloth_rustle', 'chair_creak', 'coin_drop')")
    object_material: str = Field(default="wood", description="'wood', 'pewter', 'metal', 'leather', 'cloth', 'stone', 'glass', 'water', 'fire'")
    anchor_word: str = Field(default="", description="Word in dialogue or narration anchoring the sound")
    gain_dbfs: float = Field(default=-18.0, ge=-32.0, le=-10.0, description="Calibrated sound level")
    pan: float = Field(default=0.0, ge=-0.8, le=0.8, description="Stereo panning (-0.8 left to +0.8 right)")
    is_micro_foley: bool = Field(default=False, description="True if tactile ambient micro-movement (drink, clothing, chair), False if major action")
    foley_type: str = Field(default="macro", description="'macro' for primary actions, 'micro' for tactile living-world physics")
    duration_sec: Optional[float] = Field(default=None, description="Desired duration in seconds (optional)")
    description: str = Field(default="", description="Artistic justification for sound designer")


class MicroFoleyPlan(BaseModel):
    """Full chapter collection of macro and micro foley events."""
    model_config = ConfigDict(extra="ignore")

    chapter_id: str
    events: List[FoleyEventDirective] = Field(default_factory=list)


class MicroFoleyAgent:
    """Specialist Master Foley & Micro-Life LLM Agent."""

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def spot_foley_events(
        self,
        showrunner_plan: ShowrunnerPlan,
        script_segments: List[Dict[str, Any]],
        era: str = "MEDIEVAL_FANTASY",
        title: str = "",
        author: str = "",
    ) -> MicroFoleyPlan:
        """
        Executes hierarchical foley spotting across all acts.
        Processes each act cleanly so zero text is truncated.
        """
        logger.info(f"[*] MicroFoleyAgent: Spotting macro & micro foley across {len(script_segments)} segments in {len(showrunner_plan.acts)} acts...")
        framing = get_dramatic_fiction_framing(title, author)

        seg_by_idx = {s.get("index", idx + 1): s for idx, s in enumerate(script_segments)}
        all_events: List[FoleyEventDirective] = []

        # Process act-by-act to ensure dense, complete coverage across the entire chapter
        for act in showrunner_plan.acts:
            act_segs = [
                seg_by_idx[i]
                for i in range(act.start_segment, act.end_segment + 1)
                if i in seg_by_idx
            ]
            if not act_segs:
                continue

            lines = []
            for s in act_segs:
                s_idx = s.get("index", 1)
                spk = s.get("speaker", "Narrator")
                styp = (s.get("type") or "narration").upper()
                txt = (s.get("text") or "").strip()
                lines.append(f"[{s_idx:03d} | {styp} | {spk}]: {txt}")
            act_text = "\n".join(lines)

            sys_prompt = (
                "You are an elite Hollywood Foley Artist and Sound Designer (GraphicAudio & Audible Full-Cast benchmark). "
                f"{framing}"
                f"Setting: {act.location_setting} (Era: {era}, Environment: {act.environment_type}). "
                "Your objective is to make the scene sound ALIVE with physical presence. "
                "Spot BOTH major action sounds AND subtle tactile living-world micro-foley:\n"
                "1. Major Action Cues: Sword draws, blade clashes, door creaks/slams, punches, body falls, horse gallops.\n"
                "2. Living-World Micro-Foley: Pewter/wood tankards setting on rough table, pouring drinks, clinking clay bowls, "
                "forks/knives on plates, leather belts/scabbards creaking as characters sit or shift weight, wool cloak rustles, "
                "chairs scraping on floorboards, coins dropping onto wood, hearth fire crackling.\n"
                "Target density: Aim for 5 to 15 well-placed, organic sound cues per act (avoid long empty stretches of silence).\n"
                "Ensure every cue has a valid 'segment_index' within this act range."
            )

            prompt = f"""Act {act.act_index}: {act.act_title} (Segments {act.start_segment} to {act.end_segment})
Location: {act.location_setting} ({act.environment_type})
Dramatic Subtext: {act.emotional_subtext}

ACT SCREENPLAY:
\"\"\"
{act_text}
\"\"\"

Return a JSON array of foley cues for this act:
[
  {{
    "segment_index": {act.start_segment},
    "action_verb": "tankard_slam | ale_pour | cloth_rustle | chair_creak | sword_draw | coin_drop | fire_crackle | door_creak",
    "object_material": "pewter | wood | leather | cloth | metal | stone | water | glass",
    "anchor_word": "specific word from the segment text",
    "gain_dbfs": -18.0,
    "pan": -0.3,
    "is_micro_foley": true,
    "duration_sec": 1.2,
    "description": "Character sets down heavy mug on wooden table"
  }}
]
"""

            try:
                res = call_gemini(
                    prompt=prompt,
                    system_instruction=sys_prompt,
                    task_type=TaskType.SOUND_DESIGN,
                    response_mime_type="application/json",
                    temperature=0.60,
                    max_output_tokens=8192,
                    thinking_budget=1024,
                    model=self.model,
                    max_retries=6,
                )
                if isinstance(res, list):
                    for item in res:
                        try:
                            directive = FoleyEventDirective.model_validate(item)
                            # Ensure segment index is within chapter range
                            if 1 <= directive.segment_index <= len(script_segments):
                                all_events.append(directive)
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"  [!] MicroFoleyAgent LLM call warning for Act {act.act_index}: {e}")

        logger.info(f"[+] MicroFoleyAgent: Successfully spotted {len(all_events)} foley cues across the chapter.")
        return MicroFoleyPlan(chapter_id=showrunner_plan.chapter_id, events=all_events)
