"""
Audiobook Factory - Agent 5: Dynamic Wallah & World Atmosphere Director.
Creates multi-layered ambient soundscapes (base room tone + crowd wallah + stochastic weather/spots)
and establishes dynamic speech-reactive breathing envelopes (crowd murmurs duck by -6dB during dialogue
and swell by +3dB during dramatic pauses).
"""

from __future__ import annotations
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger
from audiobook_factory.llm_client import call_gemini
from audiobook_factory.model_manager import TaskType
from audiobook_factory.safety import get_dramatic_fiction_framing
from audiobook_factory.contracts.manifest import WallahAutomationPoint
from .showrunner_agent import ShowrunnerPlan
from .scenographer_agent import ScenographyPlan


class EnvironmentLayerDirective(BaseModel):
    """Multi-layer environmental acoustic component."""
    model_config = ConfigDict(extra="ignore")

    layer_type: str = Field(default="base_room_tone", description="'base_room_tone', 'crowd_wallah', 'weather_bed', 'stochastic_spot'")
    search_query: str = Field(..., description="FTS5 search query for Sound Bank")
    target_lufs: float = Field(default=-32.0, ge=-45.0, le=-20.0)
    pan: float = Field(default=0.0, ge=-0.8, le=0.8)
    stereo_width: float = Field(default=1.15, ge=0.8, le=1.4)
    stochastic_interval_sec: Optional[float] = Field(default=None)


class ActEnvironmentBlueprint(BaseModel):
    """Environmental sound design for an act."""
    model_config = ConfigDict(extra="ignore")

    act_index: int = Field(..., ge=1)
    setting_title: str
    layers: List[EnvironmentLayerDirective] = Field(default_factory=list)
    wallah_ducking_speech_db: float = Field(default=-6.0, description="Ducking depth on crowd murmur during speech")
    wallah_pause_swell_db: float = Field(default=3.0, description="Swell boost during dialogue pause >= 1.0s")


class WallahEnvironmentPlan(BaseModel):
    """Full chapter collection of environmental layers and breathing automations."""
    model_config = ConfigDict(extra="ignore")

    chapter_id: str
    act_blueprints: List[ActEnvironmentBlueprint] = Field(default_factory=list)
    wallah_automations: List[WallahAutomationPoint] = Field(default_factory=list)


class WallahDirectorAgent:
    """Specialist Dynamic Wallah & World Atmosphere LLM Agent."""

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def direct_world_ambience(
        self,
        showrunner_plan: ShowrunnerPlan,
        scenography_plan: ScenographyPlan,
        script_segments: List[Dict[str, Any]],
        seg_starts_ms: Dict[int, int],
        segment_durations_sec: Dict[int, float],
        era: str = "MEDIEVAL_FANTASY",
        title: str = "",
        author: str = "",
    ) -> WallahEnvironmentPlan:
        """
        Synthesizes layered world ambience and computes sample-accurate wallah breathing automation points.
        """
        logger.info(f"[*] WallahDirectorAgent: Directing living world ambience and crowd breathing for {showrunner_plan.chapter_id}...")
        framing = get_dramatic_fiction_framing(title, author)

        acts_json = json.dumps([a.model_dump() for a in showrunner_plan.acts], indent=2)

        sys_prompt = (
            "You are a Supervising Ambient Sound Designer and Foley Wallah Director for cinematic audio drama. "
            f"{framing}"
            "For each act, design a rich 2-to-3 layer environmental soundscape that avoids static loops:\n"
            "- Layer 1 (base_room_tone): Constant subtle room tone / wind / tavern air (-34 LUFS).\n"
            "- Layer 2 (crowd_wallah / weather_bed): Tavern patrons murmuring, forest canopy breeze, rain on roof (-28 to -32 LUFS).\n"
            "- Layer 3 (stochastic_spot): Hearth fire crackling, distant horse snort, clock ticking, wind gust (-24 to -28 LUFS).\n"
            "Ensure the crowd is alive and dynamic: configure speech ducking (-6dB) and pause swell (+3dB)."
        )

        prompt = f"""Chapter ID: {showrunner_plan.chapter_id}
Era: {era}

DRAMATIC ACTS:
\"\"\"
{acts_json}
\"\"\"

Return a JSON array of ActEnvironmentBlueprint objects:
[
  {{
    "act_index": 1,
    "setting_title": "Tavern Taproom",
    "layers": [
      {{
        "layer_type": "base_room_tone",
        "search_query": "tavern room tone warm",
        "target_lufs": -34.0,
        "pan": 0.0,
        "stereo_width": 1.15
      }},
      {{
        "layer_type": "crowd_wallah",
        "search_query": "tavern crowd murmur medieval patrons",
        "target_lufs": -30.0,
        "pan": 0.0,
        "stereo_width": 1.25
      }},
      {{
        "layer_type": "stochastic_spot",
        "search_query": "hearth fire crackle warm embers",
        "target_lufs": -26.0,
        "pan": 0.4,
        "stereo_width": 1.0,
        "stochastic_interval_sec": 45.0
      }}
    ],
    "wallah_ducking_speech_db": -6.0,
    "wallah_pause_swell_db": 3.0
  }}
]
"""

        act_blueprints: List[ActEnvironmentBlueprint] = []
        try:
            res = call_gemini(
                prompt=prompt,
                system_instruction=sys_prompt,
                task_type=TaskType.SOUND_DESIGN,
                response_mime_type="application/json",
                temperature=0.40,
                max_output_tokens=4096,
                model=self.model,
                max_retries=6,
            )
            if isinstance(res, list):
                for item in res:
                    try:
                        act_blueprints.append(ActEnvironmentBlueprint.model_validate(item))
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"  [!] WallahDirectorAgent LLM call warning: {e}. Falling back to default layers.")

        if not act_blueprints:
            for act in showrunner_plan.acts:
                act_blueprints.append(
                    ActEnvironmentBlueprint(
                        act_index=act.act_index,
                        setting_title=act.location_setting,
                        layers=[
                            EnvironmentLayerDirective(
                                layer_type="base_room_tone",
                                search_query=f"{act.environment_type} room tone",
                                target_lufs=-34.0,
                            ),
                            EnvironmentLayerDirective(
                                layer_type="crowd_wallah",
                                search_query="tavern crowd murmur" if "tavern" in act.environment_type else "gentle wind atmosphere",
                                target_lufs=-30.0,
                            ),
                        ],
                        wallah_ducking_speech_db=-6.0,
                        wallah_pause_swell_db=3.0,
                    )
                )

        # Compute deterministic Wallah Breathing Automation points from dialogue timeline
        automations: List[WallahAutomationPoint] = []
        for i, s in enumerate(script_segments):
            s_idx = s.get("index", i + 1)
            s_start = seg_starts_ms.get(s_idx, 0)
            dur_ms = int(segment_durations_sec.get(s_idx, 4.0) * 1000)
            s_end = s_start + dur_ms

            # 1. Ducking point during dialogue speech
            automations.append(
                WallahAutomationPoint(
                    start_ms=s_start,
                    end_ms=s_end,
                    target_attenuation_db=-6.0,
                    swell_during_pause_db=0.0,
                    is_pause_swell=False,
                )
            )

            # 2. Pause swell point if gap between segments is >= 1.0s (1000ms)
            if i < len(script_segments) - 1:
                next_seg = script_segments[i + 1]
                next_idx = next_seg.get("index", i + 2)
                next_start = seg_starts_ms.get(next_idx, s_end + 300)
                gap_ms = next_start - s_end
                if gap_ms >= 1000:
                    automations.append(
                        WallahAutomationPoint(
                            start_ms=s_end + 150,
                            end_ms=next_start - 150,
                            target_attenuation_db=0.0,
                            swell_during_pause_db=3.0,
                            is_pause_swell=True,
                        )
                    )

        logger.info(f"[+] WallahDirectorAgent: Created {len(act_blueprints)} act ambience blueprints and {len(automations)} dynamic breathing points.")
        return WallahEnvironmentPlan(
            chapter_id=showrunner_plan.chapter_id,
            act_blueprints=act_blueprints,
            wallah_automations=automations,
        )
