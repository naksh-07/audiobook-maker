"""
Audiobook Factory - Agent 3: Master Foley & Micro-Life Artist.
Spots both explicit physical action events (doors, blades, impacts) and implicit living-world micro-foley
(wooden tankard clatter, ale pouring, cloth/leather rustle, fireplace crackle, chair scuffs).
Eliminates dead acoustic voids and grounds characters in tactile physical reality.
"""

from __future__ import annotations
import json
from typing import Dict, Any, List, Optional, Literal
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
    action_verb: str = Field(..., description="Action identifier (e.g. 'tankard_slam', 'ale_pour', 'sword_draw', 'cloth_rustle', 'chair_creak', 'coin_drop', 'boots_flagstone')")
    object_material: str = Field(default="wood", description="'wood', 'pewter', 'metal', 'leather', 'cloth', 'stone', 'glass', 'water', 'fire'")
    trigger_mode: Literal["explicit_anchor", "implicit_scene_physics", "atmospheric_event"] = Field(
        default="implicit_scene_physics",
        description="Whether sound is anchored to a literal word or generated from implicit scene context"
    )
    beat_timing: Literal["pre_speech", "mid_speech_pause", "post_speech", "under_speech"] = Field(
        default="post_speech",
        description="Temporal placement relative to spoken dialogue delivery"
    )
    relative_position: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Fractional timeline offset within the segment duration (0.0=start, 1.0=end)"
    )
    anchor_word: Optional[str] = Field(default="", description="Word in dialogue or narration anchoring the sound if explicit")
    gain_dbfs: float = Field(default=-18.0, ge=-36.0, le=-10.0, description="Calibrated sound level")
    pan: float = Field(default=0.0, ge=-0.8, le=0.8, description="Stereo panning (-0.8 left to +0.8 right)")
    is_micro_foley: bool = Field(default=True, description="True if tactile ambient micro-movement (drink, clothing, chair), False if major action")
    foley_type: str = Field(default="micro", description="'macro' for primary actions, 'micro' for tactile living-world physics")
    duration_sec: Optional[float] = Field(default=None, description="Desired duration in seconds (optional)")
    description: str = Field(default="", description="Artistic description of physical event")
    dramatic_justification: str = Field(default="", description="Artistic rationale for physical action")


class MicroFoleyPlan(BaseModel):
    """Full chapter collection of macro and micro foley events."""
    model_config = ConfigDict(extra="ignore")

    chapter_id: str
    events: List[FoleyEventDirective] = Field(default_factory=list)


def build_scene_physics_context_matrix(location_setting: str, environment_type: str, era: str) -> str:
    """
    Constructs a rich tactile scene physics matrix dynamically derived from the act's
    environment, setting, and era. Ensures LLM spots living-world tactile presence
    even when prose contains zero explicit object mentions.
    Universal & Novel-Agnostic.
    """
    loc_lower = (location_setting or "").lower()
    env_lower = (environment_type or "").lower()

    if any(k in loc_lower or k in env_lower for k in ("tavern", "inn", "pub", "bar", "kitchen", "dining", "hall", "taproom")):
        return (
            "TACTILE SCENE PHYSICS MATRIX (Tavern / Inn / Interior Gathering):\n"
            "- Available Props & Surfaces: Heavy oak tables, rough wooden benches/stools, pewter & wood ale tankards, ceramic bowls, bread knives, iron fire poker, clay pipes.\n"
            "- Character Physical Micro-Beats:\n"
            "  * pre_speech: Heavy mug set down on wood before answering, scraping bench legs, clearing throat, resting elbows on timber.\n"
            "  * mid_speech_pause: Taking a swallow of ale, pipe puff, hearth log crackle/pop during silence, plate clatter.\n"
            "  * post_speech: Long drink, thumping mug onto table, leaning back (creaking wood), tossing copper coin onto table.\n"
            "  * under_speech: Gentle crackle of fireplace hearth, subtle shift in wooden chair, faint tankard slide."
        )
    elif any(k in loc_lower or k in env_lower for k in ("stone", "dungeon", "crypt", "castle", "fortress", "tower", "cellar", "vault", "throne")):
        return (
            "TACTILE SCENE PHYSICS MATRIX (Stone Chamber / Fortress / Crypt):\n"
            "- Available Props & Surfaces: Cold granite flagstones, iron torch sconces, heavy iron keys, chain links, scabbards, steel armor plates, leather belts, heavy oak doors.\n"
            "- Character Physical Micro-Beats:\n"
            "  * pre_speech: Boots scuffing on cold stone, leather glove tightening on pommel, shifting heavy armor plates.\n"
            "  * mid_speech_pause: Water drop echoing on stone, torch hiss, armor squeak on shift of posture.\n"
            "  * post_speech: Deep exhale through nose, scabbard slapping thigh, footsteps echoing into distance.\n"
            "  * under_speech: Subtle low reverberant room reflections, torch crackle, armor buckle settling."
        )
    elif any(k in loc_lower or k in env_lower for k in ("forest", "woods", "wilderness", "camp", "road", "swamp", "marsh", "mountain")):
        return (
            "TACTILE SCENE PHYSICS MATRIX (Wilderness / Forest / Road / Camp):\n"
            "- Available Props & Surfaces: Pine needles, dry twigs, mud, river stones, campfire embers, canvas tents, horse leather, travel cloaks, water skins.\n"
            "- Character Physical Micro-Beats:\n"
            "  * pre_speech: Boots crunching on twigs/needles, adjusting wet travel cloak, horse snorting.\n"
            "  * mid_speech_pause: Campfire pop/spark, wind rustling canopy, water skin slosh on drink.\n"
            "  * post_speech: Sheathing knife into leather, spitting into dirt, stirrup jingle, sigh.\n"
            "  * under_speech: Gentle breeze through branches, subtle wet leather creak, embers glowing."
        )
    else:
        return (
            "TACTILE SCENE PHYSICS MATRIX (General Dramatic Environment):\n"
            "- Available Props & Surfaces: Furniture, doors, cloth/clothing, footwear, small personal props (cups, coins, paper/books, cutlery).\n"
            "- Character Physical Micro-Beats:\n"
            "  * pre_speech: Shifting weight, scuffing shoes, setting down cup/prop before replying.\n"
            "  * mid_speech_pause: Brief pause marked by chair creak, sharp inhale, or small prop adjustment.\n"
            "  * post_speech: Turning away, closing book/door, sighing, settling into posture.\n"
            "  * under_speech: Subtle room tone physics, clothing rustle on movement."
        )


from concurrent.futures import ThreadPoolExecutor, as_completed


class MicroFoleyAgent:
    """Specialist Master Foley & Micro-Life LLM Agent with Implicit Scene Physics."""

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def _spot_act_foley(
        self,
        act: Any,
        act_segs: List[Dict[str, Any]],
        script_segments: List[Dict[str, Any]],
        era: str,
        framing: str,
    ) -> List[FoleyEventDirective]:
        lines = []
        for s in act_segs:
            s_idx = s.get("index", 1)
            spk = s.get("speaker", "Narrator")
            styp = (s.get("type") or "narration").upper()
            txt = (s.get("text") or "").strip()
            lines.append(f"[{s_idx:03d} | {styp} | {spk}]: {txt}")
        act_text = "\n".join(lines)

        physics_matrix = build_scene_physics_context_matrix(
            location_setting=act.location_setting,
            environment_type=act.environment_type,
            era=era,
        )

        sys_prompt = (
            "You are an elite Hollywood Foley Artist and Sound Designer (GraphicAudio & Audible Full-Cast benchmark). "
            f"{framing}"
            f"Setting: {act.location_setting} (Era: {era}, Environment: {act.environment_type}).\n\n"
            f"{physics_matrix}\n\n"
            "CRITICAL HOLLYWOOD LIVING-WORLD MANDATE:\n"
            "Do NOT limit sound design to words explicitly spoken or narrated in text! "
            "In real life and top-tier audio dramas, living physical actions happen continuously around dialogue:\n"
            "- A speaker sets down their mug with a wooden thud before replying ('pre_speech').\n"
            "- A listener's chair creaks or clothes rustle as they lean in during a dramatic pause ('mid_speech_pause').\n"
            "- A character takes a swallow, thumps a cup, tosses a coin, or taps their sword hilt after speaking ('post_speech').\n"
            "- The hearth fire crackles or armor rustles softly beneath dialogue ('under_speech').\n\n"
            "For implicit actions, set trigger_mode='implicit_scene_physics' and leave anchor_word=''. "
            "Only use trigger_mode='explicit_anchor' when a specific object (e.g. 'sword', 'door') is literally spoken in text.\n"
            "Target density: Aim for 10 to 25 organic, tactile cues per act so the scene feels physically alive with texture."
        )

        prompt = f"""Act {act.act_index}: {act.act_title} (Segments {act.start_segment} to {act.end_segment})
Location: {act.location_setting} ({act.environment_type})
Dramatic Subtext: {act.emotional_subtext}

ACT SCREENPLAY:
\"\"\"
{act_text}
\"\"\"

Return a JSON array of foley cues for this act. Include BOTH major actions and implicit living-world physics:
[
  {{
    "segment_index": {act.start_segment},
    "action_verb": "tankard_thump | ale_pour | cloth_rustle | chair_creak | sword_draw | coin_drop | fire_crackle | boots_flagstone",
    "object_material": "pewter | wood | leather | cloth | metal | stone | water | fire",
    "trigger_mode": "implicit_scene_physics | explicit_anchor",
    "beat_timing": "pre_speech | mid_speech_pause | post_speech | under_speech",
    "relative_position": 0.5,
    "anchor_word": "",
    "gain_dbfs": -18.0,
    "pan": -0.2,
    "is_micro_foley": true,
    "foley_type": "micro",
    "duration_sec": 0.8,
    "description": "Character sets down heavy mug on table before speaking",
    "dramatic_justification": "Physical punctuation of disagreement"
  }}
]
"""
        act_events: List[FoleyEventDirective] = []
        try:
            res = call_gemini(
                prompt=prompt,
                system_instruction=sys_prompt,
                task_type=TaskType.SOUND_DESIGN,
                response_mime_type="application/json",
                temperature=0.60,
                max_output_tokens=16384,
                thinking_budget=512,
                model=self.model,
                max_retries=8,
            )
            if isinstance(res, list):
                for item in res:
                    try:
                        directive = FoleyEventDirective.model_validate(item)
                        if 1 <= directive.segment_index <= len(script_segments):
                            act_events.append(directive)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"  [!] MicroFoleyAgent LLM call warning for Act {act.act_index}: {e}")
        return act_events

    def spot_foley_events(
        self,
        showrunner_plan: ShowrunnerPlan,
        script_segments: List[Dict[str, Any]],
        era: str = "MEDIEVAL_FANTASY",
        title: str = "",
        author: str = "",
    ) -> MicroFoleyPlan:
        """
        Executes concurrent hierarchical foley spotting across all acts.
        Processes each act cleanly in parallel with rich Implicit Scene Physics so zero text is truncated
        and living world physics trigger naturally without requiring literal word anchors.
        """
        logger.info(f"[*] MicroFoleyAgent: Spotting macro & implicit living-world foley across {len(script_segments)} segments in {len(showrunner_plan.acts)} acts...")
        framing = get_dramatic_fiction_framing(title, author)

        seg_by_idx = {s.get("index", idx + 1): s for idx, s in enumerate(script_segments)}
        all_events: List[FoleyEventDirective] = []

        act_tasks = []
        for act in showrunner_plan.acts:
            act_segs = [
                seg_by_idx[i]
                for i in range(act.start_segment, act.end_segment + 1)
                if i in seg_by_idx
            ]
            if act_segs:
                act_tasks.append((act, act_segs))

        # Concurrently process all acts across the 100+ key pool
        with ThreadPoolExecutor(max_workers=min(4, max(1, len(act_tasks)))) as executor:
            futures = [
                executor.submit(self._spot_act_foley, act, act_segs, script_segments, era, framing)
                for act, act_segs in act_tasks
            ]
            for future in as_completed(futures):
                try:
                    events = future.result()
                    all_events.extend(events)
                except Exception as e:
                    logger.warning(f"  [!] Act foley spotting worker notice: {e}")

        # Sort all events chronologically by segment index
        all_events.sort(key=lambda x: x.segment_index)
        logger.info(f"[+] MicroFoleyAgent: Successfully spotted {len(all_events)} foley cues across the chapter.")
        return MicroFoleyPlan(chapter_id=showrunner_plan.chapter_id, events=all_events)
