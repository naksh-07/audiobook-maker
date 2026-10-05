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
    environment_slug: str = Field(default="domestic_room", description="Standardized environment identifier")
    room_dimensions: str = Field(default="medium", description="'intimate_small', 'medium_enclosed', 'cavernous_large', 'open_exterior'")
    primary_materials: List[str] = Field(default_factory=lambda: ["wood", "stone"], description="Physical wall/floor reflective materials")
    ir_preset: str = Field(
        default="domestic_room",
        description="'tavern_timber_small', 'stone_crypt_damp', 'great_hall_stone', 'forest_open_mist', 'domestic_room', 'cave_catacomb', 'rural_courtyard_open', 'modern_office_carpet', 'urban_street_canyon', 'wooden_cottage_interior', 'cathedral_sacred_vault'"
    )
    dx_reverb_wet_ratio: float = Field(
        default=0.10, ge=0.04, le=0.25,
        description="Subtle early reflection wet ratio convolved onto DX spoken track (0.10 - 0.15 is ideal)"
    )
    early_reflections_decay_ms: int = Field(default=180, ge=80, le=800)
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
        era: str = "UNIVERSAL_CONTEMPORARY",
        title: str = "",
        author: str = "",
        sonic_bible: Optional[Dict[str, Any]] = None,
        book_dna: Optional[Dict[str, Any]] = None,
    ) -> ScenographyPlan:
        """
        Synthesizes physical room geometry and convolution IR presets for each act.
        """
        logger.info(f"[*] ScenographerAgent: Designing physical acoustic spaces for {showrunner_plan.chapter_id} ({len(showrunner_plan.acts)} acts)...")
        framing = get_dramatic_fiction_framing(title, author)

        acts_json = json.dumps([a.model_dump() for a in showrunner_plan.acts], indent=2)

        custom_spaces_prompt = ""
        if sonic_bible and sonic_bible.get("acoustic_spaces"):
            custom_spaces_prompt = f"\nPROJECT ACOUSTIC SPACES from sonic_bible:\n{json.dumps(sonic_bible.get('acoustic_spaces'), indent=2)}\n"

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
{custom_spaces_prompt}
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
- 'rural_courtyard_open': Rustic village courtyard, mud/brick walls, open sky diffusion (decay 120-180ms, wet 0.07)
- 'modern_office_carpet': Drywall, acoustic ceiling tiles, carpet absorption, corporate chamber (decay 80-140ms, wet 0.05)
- 'urban_street_canyon': City street corridor between tall buildings, vertical slapback echoes (decay 350-500ms, wet 0.12)
- 'wooden_cottage_interior': Intimate rustic timber walls, thatched ceiling, cozy hearth resonance (decay 150-200ms, wet 0.08)
- 'cathedral_sacred_vault': Grand sacred vault, soaring stone arches, long reverberant decay (decay 600-900ms, wet 0.18)

Return a JSON array of blueprints, one for each act:
[
  {{
    "act_index": 1,
    "location_name": "Main Room",
    "environment_slug": "domestic_room",
    "room_dimensions": "intimate_small | medium_enclosed | cavernous_large | open_exterior",
    "primary_materials": ["wood", "cloth", "plaster"],
    "ir_preset": "domestic_room",
    "dx_reverb_wet_ratio": 0.10,
    "early_reflections_decay_ms": 180,
    "high_frequency_damping_hz": 7500,
    "acoustic_presence_description": "Natural, intimate room with balanced early reflections"
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
            loc = act.location_setting.lower()
            combined = f"{env} {loc}"

            if any(k in combined for k in ("courtyard", "rural", "village", "veranda", "patio", "field", "farm")):
                ir_p = "rural_courtyard_open"
                wet_p = 0.07
                decay_p = 150
            elif any(k in combined for k in ("office", "modern", "carpet", "boardroom", "corridor", "flat", "apartment")):
                ir_p = "modern_office_carpet"
                wet_p = 0.05
                decay_p = 110
            elif any(k in combined for k in ("street", "canyon", "city", "alley", "urban", "bazaar", "market")):
                ir_p = "urban_street_canyon"
                wet_p = 0.12
                decay_p = 400
            elif any(k in combined for k in ("cottage", "hut", "cabin", "timber", "shack")):
                ir_p = "wooden_cottage_interior"
                wet_p = 0.08
                decay_p = 180
            elif any(k in combined for k in ("cathedral", "church", "temple", "vault", "sanctuary", "mosque")):
                ir_p = "cathedral_sacred_vault"
                wet_p = 0.18
                decay_p = 750
            elif any(k in combined for k in ("tavern", "inn", "pub", "bar", "kitchen")):
                ir_p = "tavern_timber_small"
                wet_p = 0.12
                decay_p = 220
            elif any(k in combined for k in ("crypt", "stone", "dungeon", "cellar")):
                ir_p = "stone_crypt_damp"
                wet_p = 0.18
                decay_p = 500
            elif any(k in combined for k in ("hall", "palace", "ballroom")):
                ir_p = "great_hall_stone"
                wet_p = 0.16
                decay_p = 600
            elif any(k in combined for k in ("forest", "woods", "mountain", "outdoor", "exterior")):
                ir_p = "forest_open_mist"
                wet_p = 0.06
                decay_p = 100
            elif any(k in combined for k in ("cave", "mine", "catacomb")):
                ir_p = "cave_catacomb"
                wet_p = 0.16
                decay_p = 480
            else:
                ir_p = "domestic_room"
                wet_p = 0.09
                decay_p = 180

            blueprints.append(
                SceneAcousticBlueprint(
                    act_index=act.act_index,
                    location_name=act.location_setting,
                    environment_slug=act.environment_type,
                    room_dimensions="medium_enclosed",
                    primary_materials=["wood", "stone"],
                    ir_preset=ir_p,
                    dx_reverb_wet_ratio=wet_p,
                    early_reflections_decay_ms=decay_p,
                    high_frequency_damping_hz=7500,
                    acoustic_presence_description=f"Atmospheric space for {act.location_setting}",
                )
            )
        return ScenographyPlan(chapter_id=showrunner_plan.chapter_id, blueprints=blueprints)
