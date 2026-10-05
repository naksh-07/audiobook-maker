"""
Audiobook Factory - Agent 4: Film Composer & Music Score Supervisor.
Scores the chapter dynamically with scene transition stingers, thematic character motifs,
and dramatic tension punctuation, replacing monolithic flat 4-minute loops while strictly respecting
the broadcast standard >= 60% acoustic silence rule.
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


class MusicCueDirective(BaseModel):
    """Dynamic musical score cue directive."""
    model_config = ConfigDict(extra="ignore")

    trigger_segment: int = Field(..., ge=1, description="1-based segment index where music cue enters")
    cue_type: str = Field(default="EMOTIONAL_UNDERSCORE", description="'TRANSITION_BRIDGE', 'EMOTIONAL_UNDERSCORE', 'DRAMATIC_PUNCTUATION', 'THEMATIC_MOTIF'")
    duration_sec: float = Field(default=30.0, ge=5.0, le=90.0, description="Duration of musical cue in seconds")
    fade_in_sec: float = Field(default=2.5, ge=0.5, le=8.0)
    fade_out_sec: float = Field(default=3.5, ge=0.5, le=10.0)
    narrative_archetype: str = Field(default="TENSION", description="Dramatic archetype (e.g. 'MYSTERY_PROLOGUE', 'TENSION', 'BITTERSWEET_PARTING', 'TAVERN_FOLK_TRANSITION')")
    mood: str = Field(default="tense", description="'mysterious', 'tense', 'melancholic', 'playful_folk', 'dark_ominous', 'epic'")
    tempo: str = Field(default="moderate", description="'slow', 'moderate', 'fast'")
    timbre: str = Field(default="dark strings", description="Primary instruments (e.g. 'solo cello', 'lute & acoustic guitar', 'hurdy-gurdy', 'low bass drone')")
    energy_section: str = Field(default="INTRO_BED", description="'INTRO_BED', 'RISING_TENSION', 'CLIMAX_DROP', 'TRANSITION'")
    search_query: str = Field(default="dark cello tension", description="Optimal 3-word query for Sound Bank music library")
    volume_db: float = Field(default=-24.0, ge=-32.0, le=-14.0, description="Target volume in dBFS")
    dramatic_justification: str = Field(default="", description="Explainable rationale for this musical cue")


class MusicScoringPlan(BaseModel):
    """Full chapter musical score composition plan."""
    model_config = ConfigDict(extra="ignore")

    chapter_id: str
    total_music_duration_sec: float = Field(default=0.0)
    silence_percentage: float = Field(default=100.0)
    cues: List[MusicCueDirective] = Field(default_factory=list)


class MusicSupervisorAgent:
    """Specialist Film Composer & Music Score Supervisor LLM Agent."""

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def score_chapter(
        self,
        showrunner_plan: ShowrunnerPlan,
        script_segments: List[Dict[str, Any]],
        total_duration_sec: float,
        era: str = "UNIVERSAL_CONTEMPORARY",
        title: str = "",
        author: str = "",
    ) -> MusicScoringPlan:
        """
        Synthesizes surgical scene transition stingers, thematic motifs, and dramatic underscores.
        Enforces that total music stays between 20% and 35% of chapter length (>= 65% silence).
        """
        logger.info(f"[*] MusicSupervisorAgent: Scoring chapter {showrunner_plan.chapter_id} ({total_duration_sec/60:.1f}m total duration)...")
        framing = get_dramatic_fiction_framing(title, author)

        max_music_sec = total_duration_sec * 0.35  # Cap music at 35% so silence is always >= 65%

        acts_json = json.dumps([a.model_dump() for a in showrunner_plan.acts], indent=2)
        transitions = showrunner_plan.scene_transition_segments
        pivots = showrunner_plan.pivotal_moments

        sys_prompt = (
            "You are an Academy-Award winning Film Composer and Music Supervisor for cinematic audio drama. "
            f"{framing}"
            "Your objective is to score the chapter with SURGICAL CINEMATIC CUES rather than endless flat looping beds. "
            "Score:\n"
            "1. Scene Transition Stingers (5–12s): Warm acoustic instruments (strings, piano, woodwinds, or traditional instruments matching the novel's culture) bridging scene changes.\n"
            "2. Thematic Underscores (25–50s): Low-volume ambient cello, piano, subtle bowed strings, or atmospheric drones under pivotal dialogues.\n"
            "3. Tension Punctuation (10–20s): Sudden atmospheric drop or crescendo on key revelations.\n"
            f"CRITICAL CONSTRAINT: Total music duration across ALL cues MUST NOT exceed {max_music_sec:.1f} seconds! "
            "At least 65% of the chapter MUST remain pure acoustic dialogue + room tone. "
            "Target 4 to 10 distinct, purposeful musical cues distributed across the chapter.\n\n"
            "VERIFIED SOUND BANK MUSIC TIMBRES & QUERIES (Ground search_query in these verified terms for instant resolution):\n"
            "- Timbres: dark strings, solo cello, melancholic piano, subtle woodwinds, ambient tension drone, "
            "low brass swell, bansuri flute, acoustic guitar, pizzicato suspense, emotional strings, orchestral brass.\n"
            "- Moods: tense, mysterious, melancholic, dark_ominous, emotional, peaceful, epic, playful_folk.\n"
            "- Optimal search_query examples: 'dark cello tension', 'melancholic piano slow', 'ambient drone suspense', 'subtle strings emotional', 'mystery pizzicato tension'."
        )

        prompt = f"""Chapter ID: {showrunner_plan.chapter_id}
Era: {era}
Dramatic Theme: {showrunner_plan.dramatic_theme}
Total Chapter Duration: {total_duration_sec:.1f}s (Max Music Budget: {max_music_sec:.1f}s)
Key Scene Transitions: {transitions}
Pivotal Dramatic Moments: {pivots}

DRAMATIC ACTS:
\"\"\"
{acts_json}
\"\"\"

Return a JSON array of MusicCueDirective objects:
[
  {{
    "trigger_segment": 1,
    "cue_type": "TRANSITION_BRIDGE | EMOTIONAL_UNDERSCORE | DRAMATIC_PUNCTUATION | THEMATIC_MOTIF",
    "duration_sec": 12.0,
    "fade_in_sec": 2.0,
    "fade_out_sec": 3.0,
    "narrative_archetype": "TAVERN_FOLK_TRANSITION",
    "mood": "playful_folk",
    "tempo": "moderate",
    "timbre": "lute & acoustic guitar",
    "energy_section": "TRANSITION",
    "search_query": "tavern lute folk",
    "volume_db": -24.0,
    "dramatic_justification": "Opening musical bridge establishing the rustic tavern atmosphere"
  }}
]
"""

        try:
            res = call_gemini(
                prompt=prompt,
                system_instruction=sys_prompt,
                task_type=TaskType.DIRECTING,
                response_mime_type="application/json",
                temperature=0.50,
                max_output_tokens=6144,
                thinking_budget=1024,
                model=self.model,
                max_retries=6,
            )
            if isinstance(res, list):
                cues = []
                total_m_sec = 0.0
                for item in res:
                    try:
                        c = MusicCueDirective.model_validate(item)
                        # Check segment validity
                        if 1 <= c.trigger_segment <= len(script_segments):
                            # Budget check: avoid exceeding max_music_sec
                            if total_m_sec + c.duration_sec <= max_music_sec:
                                cues.append(c)
                                total_m_sec += c.duration_sec
                    except Exception:
                        pass

                silence_pct = round(max(60.0, 100.0 * (1.0 - (total_m_sec / max(1.0, total_duration_sec)))), 2)
                logger.info(f"[+] MusicSupervisorAgent: Scored {len(cues)} dynamic cues ({total_m_sec:.1f}s music, {silence_pct}% silence).")
                return MusicScoringPlan(
                    chapter_id=showrunner_plan.chapter_id,
                    total_music_duration_sec=total_m_sec,
                    silence_percentage=silence_pct,
                    cues=cues,
                )
        except Exception as e:
            logger.warning(f"  [!] MusicSupervisorAgent LLM call warning: {e}. Falling back to baseline score.")

        # Minimal baseline fallback ensuring >= 75% silence
        return MusicScoringPlan(
            chapter_id=showrunner_plan.chapter_id,
            total_music_duration_sec=0.0,
            silence_percentage=100.0,
            cues=[],
        )
