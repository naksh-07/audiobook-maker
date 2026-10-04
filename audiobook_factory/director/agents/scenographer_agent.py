"""
Audiobook Factory - Agent 2: The Acoustic Scenographer & Room Physics Engineer.
Determines physical room dimensions, material reflections, and assigns Convolution Impulse Response (IR)
presets to eliminate vocal dryness and ground characters organically in their environment.
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


class SceneAcousticBlueprint(BaseModel):
    """Acoustic spatial profile for a specific dramatic act."""
    model_config = ConfigDict(extra="ignore")

    act_index: int = Field(..., ge=1)
    location_name: str
    environment_slug: str = Field(default="tavern_interior", description="Standardized environment identifier")
    room_dimensions: str = Field(default="medium", description="'intimate_small', 'medium_enclosed', 'cavernous_large', 'open_exterior'")
    primary_materials: List[str] = Field(default_factory=lambda: ["wood", "stone"], description="Physical wall/floor reflective materials")
    ir_preset: str = Field(
        default="tavern_timber_small",
        description="'tavern_timber_small', 'stone_crypt_damp', 'great_hall_stone', 'forest_open_mist', 'domestic_room', 'cave_catacomb'"
    )
    dx_reverb_wet_ratio: float = Field(
        default=0.12, ge=0.04, le=0.25,
        description="Subtle early reflection wet ratio convolved onto DX spoken track (0.10 - 0.15 is ideal)"
    )
    early_reflections_decay_ms: int = Field(default=220, ge=80, le=800)
    high_frequency_damping_hz: int = Field(default=7500, description="Air absorption high-cut filter")
    acoustic_presence_description: str = Field(default="", description="Artistic description of the acoustic atmosphere")


class ScenographyPlan(BaseModel):
    """Collection of acoustic blueprints across all acts."""
    model_config = ConfigDict(extra="ignore")

    chapter_id: str
    blueprints: List[SceneAcousticBlueprint] = Field(default_factory=list)


class ScenographerAgent:
    """Specialist Acoustic Scenographer LLM Agent."""

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def design_acoustic_spaces(
        self,
        showrunner_plan: ShowrunnerPlan,
        era: str = "MEDIEVAL_FANTASY",
        title: str = "",
        author: str = "",
    ) -> ScenographyPlan:
        """
        Synthesizes physical room geometry and convolution IR presets for each act.
        """
        logger.info(f"[*] ScenographerAgent: Designing physical acoustic spaces for {showrunner_plan.chapter_id} ({len(showrunner_plan.acts)} acts)...")
        framing = get_dramatic_fiction_framing(title, author)

        acts_json = json.dumps([a.model_dump() for a in showrunner_plan.acts], indent=2)

        sys_prompt = (
            "You are a Master Acoustic Scenographer and Spatial Audio Engineer for cinematic audio drama. "
            f"{framing}"
            "Your task is to establish the PHYSICAL ROOM ACOUSTICS for each act. "
            "Characters must NEVER sound like they are speaking in an anechoic studio isolation booth. "
            "Assign realistic room materials, dimensions, and convolution impulse response (IR) presets "
            "so the vocal track receives subtle, natural early reflections matching the scene's architecture."
        )

        prompt = f"""Chapter ID: {showrunner_plan.chapter_id}
Era: {era}
Dramatic Theme: {showrunner_plan.dramatic_theme}

DRAMATIC ACTS FROM SHOWRUNNER:
\"\"\"
{acts_json}
\"\"\"

Standard IR Presets available:
- 'tavern_timber_small': Warm, low ceiling, wooden walls, heavy absorption from crowd and cloth (decay 180-220ms, wet 0.12)
- 'stone_crypt_damp': Cold, wet masonry, slapback early reflections, cavernous (decay 450-600ms, wet 0.18)
- 'great_hall_stone': High vaulted stone ceilings, grand reflections (decay 500-750ms, wet 0.16)
- 'forest_open_mist': Open air, zero lateral reflections, ground absorption, distant diffuse echoes (decay 80-120ms, wet 0.06)
- 'domestic_room': Standard domestic plaster/wood interior (decay 160-200ms, wet 0.09)
- 'cave_catacomb': Irregular rock surfaces, dark flutter reflections (decay 400-550ms, wet 0.16)

Return a JSON array of blueprints, one for each act:
[
  {{
    "act_index": 1,
    "location_name": "Tavern Interior",
    "environment_slug": "tavern_interior",
    "room_dimensions": "intimate_small | medium_enclosed | cavernous_large | open_exterior",
    "primary_materials": ["aged pine", "clay tiles", "wool cloaks"],
    "ir_preset": "tavern_timber_small",
    "dx_reverb_wet_ratio": 0.12,
    "early_reflections_decay_ms": 220,
    "high_frequency_damping_hz": 7500,
    "acoustic_presence_description": "Warm, claustrophobic tavern taproom with low wooden beams"
  }}
]
"""

        try:
            res = call_gemini(
                prompt=prompt,
                system_instruction=sys_prompt,
                task_type=TaskType.DIRECTING,
                response_mime_type="application/json",
                temperature=0.35,
                max_output_tokens=4096,
                model=self.model,
                max_retries=6,
            )
            if isinstance(res, list):
                blueprints = [SceneAcousticBlueprint.model_validate(b) for b in res]
                logger.info(f"[+] ScenographerAgent: Configured {len(blueprints)} spatial acoustic blueprints.")
                return ScenographyPlan(chapter_id=showrunner_plan.chapter_id, blueprints=blueprints)
        except Exception as e:
            logger.warning(f"  [!] ScenographerAgent LLM call warning: {e}. Falling back to default acoustic blueprint.")

        # Baseline fallback
        blueprints = []
        for act in showrunner_plan.acts:
            env = act.environment_type.lower()
            ir_p = "tavern_timber_small" if "tavern" in env else ("stone_crypt_damp" if "crypt" in env or "stone" in env else "domestic_room")
            blueprints.append(
                SceneAcousticBlueprint(
                    act_index=act.act_index,
                    location_name=act.location_setting,
                    environment_slug=act.environment_type,
                    room_dimensions="medium_enclosed",
                    primary_materials=["wood", "stone"],
                    ir_preset=ir_p,
                    dx_reverb_wet_ratio=0.12,
                    early_reflections_decay_ms=220,
                    high_frequency_damping_hz=7500,
                    acoustic_presence_description=f"Atmospheric space for {act.location_setting}",
                )
            )
        return ScenographyPlan(chapter_id=showrunner_plan.chapter_id, blueprints=blueprints)
