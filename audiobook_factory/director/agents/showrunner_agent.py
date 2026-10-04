"""
Audiobook Factory - Agent 1: The Showrunner & Macro Scenarist.
Ingests the complete chapter screenplay without text truncation.
Partitions the narrative into organic dramatic acts and establishes the emotional tension trajectory.
"""

from __future__ import annotations
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger
from audiobook_factory.llm_client import call_gemini
from audiobook_factory.model_manager import TaskType
from audiobook_factory.safety import get_dramatic_fiction_framing


class ActDefinition(BaseModel):
    """Organic narrative act boundary and dramatic temperature."""
    model_config = ConfigDict(extra="ignore")

    act_index: int = Field(..., ge=1, description="1-based act index")
    act_title: str = Field(default="", description="Descriptive dramatic title of this act")
    start_segment: int = Field(..., ge=1, description="Starting segment index")
    end_segment: int = Field(..., ge=1, description="Ending segment index (inclusive)")
    location_setting: str = Field(..., description="Physical location of the scene (e.g. 'Tavern Taproom', 'Stone Crypt')")
    environment_type: str = Field(default="tavern_interior", description="Standardized acoustic environment category")
    dramatic_intensity: float = Field(default=0.5, ge=0.0, le=1.0, description="Overall dramatic tension (0.0=whisper/calm, 1.0=climax)")
    pacing: str = Field(default="moderate", description="'slow_tense', 'moderate_dialogue', 'rapid_action'")
    emotional_subtext: str = Field(default="", description="Core psychological undercurrent")


class ShowrunnerPlan(BaseModel):
    """Macro dramatic and architectural blueprint for the chapter."""
    model_config = ConfigDict(extra="ignore")

    chapter_id: str
    dramatic_theme: str = Field(default="Cinematic Audio Drama")
    acts: List[ActDefinition] = Field(default_factory=list)
    pivotal_moments: List[int] = Field(default_factory=list, description="Segment indices where major dramatic pivots occur")
    scene_transition_segments: List[int] = Field(default_factory=list, description="Segment indices where scenes change")


class ShowrunnerAgent:
    """Specialist Showrunner LLM Agent."""

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def analyze_chapter(
        self,
        chapter_id: str,
        script_segments: List[Dict[str, Any]],
        total_duration_sec: float,
        era: str = "MEDIEVAL_FANTASY",
        dramatic_theme: str = "Cinematic Audio Drama",
        title: str = "",
        author: str = "",
    ) -> ShowrunnerPlan:
        """
        Executes macro dramatic partitioning over the full screenplay.
        Passes all segments without arbitrary character truncation.
        """
        total_segs = len(script_segments)
        logger.info(f"[*] ShowrunnerAgent: Analyzing full chapter {chapter_id} ({total_segs} segments, {total_duration_sec/60:.1f}m)...")

        framing = get_dramatic_fiction_framing(title, author)

        # Build complete, untruncated prose representation
        lines = []
        for s in script_segments:
            s_idx = s.get("index", 1)
            spk = s.get("speaker", "Narrator")
            styp = (s.get("type") or "narration").upper()
            txt = (s.get("text") or "").strip()
            env = s.get("acoustic_env", "")
            env_str = f" | ENV: {env}" if env else ""
            lines.append(f"[{s_idx:03d} | {styp} | {spk}{env_str}]: {txt}")
        full_prose = "\n".join(lines)

        sys_prompt = (
            "You are the Showrunner and Lead Executive Audio Director for an elite cinematic audio drama "
            "(modeled after GraphicAudio and Audible Full-Cast benchmarks). "
            f"{framing}"
            "Your job is to analyze the COMPLETE chapter script and partition it into 2 to 6 natural dramatic ACTS. "
            "Identify where the scene location shifts, the pacing changes, or major dramatic confrontations begin. "
            "Ensure that act boundaries span from segment 1 to the final segment without gaps or overlaps."
        )

        prompt = f"""Chapter ID: {chapter_id}
Era: {era}
Dramatic Theme: {dramatic_theme}
Total Segments: {total_segs}
Total Duration: {total_duration_sec:.1f} seconds

COMPLETE CHAPTER SCREENPLAY:
\"\"\"
{full_prose}
\"\"\"

Return a JSON object conforming to this exact schema:
{{
  "chapter_id": "{chapter_id}",
  "dramatic_theme": "{dramatic_theme}",
  "acts": [
    {{
      "act_index": 1,
      "act_title": "String title",
      "start_segment": 1,
      "end_segment": 45,
      "location_setting": "Specific physical setting",
      "environment_type": "standard_category (e.g. tavern_interior, forest_road, stone_dungeon, castle_hall, domestic_room)",
      "dramatic_intensity": 0.4,
      "pacing": "slow_tense | moderate_dialogue | rapid_action",
      "emotional_subtext": "Brief subtext description"
    }}
  ],
  "pivotal_moments": [list of integer segment indices where a key secret, threat, or dramatic climax occurs],
  "scene_transition_segments": [list of integer segment indices where the physical location or scene changes]
}}
"""

        try:
            res = call_gemini(
                prompt=prompt,
                system_instruction=sys_prompt,
                task_type=TaskType.DIRECTING,
                response_mime_type="application/json",
                temperature=0.40,
                max_output_tokens=8192,
                thinking_budget=1024,
                model=self.model,
                max_retries=6,
            )
            if isinstance(res, dict) and "acts" in res:
                plan = ShowrunnerPlan.model_validate(res)
                # Verify complete segment coverage
                if plan.acts:
                    plan.acts[0].start_segment = 1
                    plan.acts[-1].end_segment = total_segs
                logger.info(f"[+] ShowrunnerAgent: Partitioned {chapter_id} into {len(plan.acts)} dynamic acts.")
                return plan
        except Exception as e:
            logger.warning(f"  [!] ShowrunnerAgent LLM call warning: {e}. Falling back to single-act baseline.")

        # Robust fallback if LLM encounters issues
        return ShowrunnerPlan(
            chapter_id=chapter_id,
            dramatic_theme=dramatic_theme,
            acts=[
                ActDefinition(
                    act_index=1,
                    act_title="Primary Dramatic Sequence",
                    start_segment=1,
                    end_segment=total_segs,
                    location_setting="Narrative Setting",
                    environment_type="tavern_interior" if "tavern" in full_prose.lower() else "room_tone",
                    dramatic_intensity=0.5,
                    pacing="moderate_dialogue",
                    emotional_subtext="Continuous dramatic engagement",
                )
            ],
            pivotal_moments=[],
            scene_transition_segments=[],
        )
