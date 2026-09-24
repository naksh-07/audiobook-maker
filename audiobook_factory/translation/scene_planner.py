#!/usr/bin/env python3
"""
Audiobook Factory - Scene Segmentation & Planning Engine.
Segments chapters into cohesive dramatic scenes based on ACTUAL narrative transitions
(location changes, time shifts, character entrances/exits, narrative breaks),
rather than enforcing an arbitrary fixed scene count.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field


class ScenePlan(BaseModel):
    scene_id: str
    scene_title: str
    start_paragraph_idx: int
    end_paragraph_idx: int
    text_block: str
    location: str = "Unspecified"
    time: str = "Unspecified"
    active_characters: List[str] = Field(default_factory=list)
    danger_level: int = 1  # 0 to 5
    emotional_state: str = "neutral"
    key_objects: List[str] = Field(default_factory=list)
    register_flavor: str = "balanced_dramatic"

    def get_prompt_context(self) -> str:
        """Formats the structured scene plan as clean context for translation prompts."""
        chars = ", ".join(self.active_characters) if self.active_characters else "None identified"
        objs = ", ".join(self.key_objects) if self.key_objects else "None"
        return (
            f"STRUCTURED SCENE PLAN ({self.scene_title}):\n"
            f"- Location & Setting: {self.location}\n"
            f"- Narrative Time: {self.time}\n"
            f"- Active Characters: {chars}\n"
            f"- Danger Level: {self.danger_level}/5 | Prevailing Emotional State: {self.emotional_state}\n"
            f"- Key Narrative Objects/Elements: {objs}\n"
            f"- Recommended Register: {self.register_flavor}"
        )


class ChapterPlan(BaseModel):
    chapter_title: str
    total_paragraphs: int
    total_words: int
    scenes: List[ScenePlan]


class ScenePlanner:
    # Heuristic markers for narrative transitions
    TIME_TRANSITION_PATTERNS = [
        r"\b(?:the next morning|at dawn|by dusk|later that evening|several hours later|at midnight|next day|the following day)\b",
        r"\b(?:in the morning|after sunset|as darkness fell|days passed|weeks passed)\b",
    ]
    LOCATION_TRANSITION_PATTERNS = [
        r"\b(?:left the|entered the|arrived at|walked into|stepped outside|in the courtyard|in the temple|in the tavern|in the library)\b",
        r"\b(?:at the gates?|on the road|by the river|in the forest|under the bridge)\b",
    ]
    COMPILED_TIME_PATTERNS = [re.compile(p, re.IGNORECASE) for p in TIME_TRANSITION_PATTERNS]
    COMPILED_LOC_PATTERNS = [re.compile(p, re.IGNORECASE) for p in LOCATION_TRANSITION_PATTERNS]

    @classmethod
    def plan_chapter(
        cls,
        chapter_text: str,
        chapter_title: str = "Chapter",
        known_characters: Optional[List[str]] = None,
    ) -> ChapterPlan:
        """
        Segments chapter into natural scenes based on narrative boundaries.
        Scene count is strictly governed by narrative structure, not a rigid quota.
        """
        paragraphs = [p.strip() for p in chapter_text.split("\n\n") if p.strip()]
        total_paras = len(paragraphs)
        words = len(chapter_text.split())

        if total_paras == 0:
            return ChapterPlan(chapter_title=chapter_title, total_paragraphs=0, total_words=0, scenes=[])

        # Short chapters (< 4 paragraphs and < 800 words) remain a single organic scene
        if total_paras <= 3 and words < 800:
            active_chars = cls._find_active_characters(chapter_text, known_characters)
            single_scene = ScenePlan(
                scene_id="scene_001",
                scene_title=f"{chapter_title} (Full Scene)",
                start_paragraph_idx=0,
                end_paragraph_idx=total_paras - 1,
                text_block=chapter_text,
                active_characters=active_chars,
                register_flavor="cinematic_dramatic",
            )
            return ChapterPlan(
                chapter_title=chapter_title,
                total_paragraphs=total_paras,
                total_words=words,
                scenes=[single_scene],
            )

        # Multi-paragraph scene boundary discovery
        boundaries: List[int] = [0]
        curr_words = 0

        for i, para in enumerate(paragraphs):
            p_words = len(para.split())
            curr_words += p_words

            # Explicit markdown divider
            if para.strip() in ("---", "***", "* * *", "___"):
                if i not in boundaries and (i - boundaries[-1]) >= 2:
                    boundaries.append(i)
                    curr_words = 0
                continue

            # Check for narrative transitions after at least 2 paragraphs or 250 words
            if curr_words >= 250 or (i - boundaries[-1]) >= 2:
                has_time_shift = any(pat.search(para) for pat in cls.COMPILED_TIME_PATTERNS)
                has_loc_shift = any(pat.search(para) for pat in cls.COMPILED_LOC_PATTERNS)

                if has_time_shift or has_loc_shift:
                    boundaries.append(i)
                    curr_words = 0

        # Construct scenes from discovered boundaries
        scenes: List[ScenePlan] = []
        for s_idx in range(len(boundaries)):
            start_p = boundaries[s_idx]
            end_p = boundaries[s_idx + 1] - 1 if (s_idx + 1) < len(boundaries) else total_paras - 1
            scene_paras = paragraphs[start_p : end_p + 1]
            scene_text = "\n\n".join(scene_paras)

            active_chars = cls._find_active_characters(scene_text, known_characters)
            loc, time_str = cls._infer_setting(scene_text)

            plan = ScenePlan(
                scene_id=f"scene_{s_idx + 1:03d}",
                scene_title=f"{chapter_title} - Scene {s_idx + 1}",
                start_paragraph_idx=start_p,
                end_paragraph_idx=end_p,
                text_block=scene_text,
                location=loc,
                time=time_str,
                active_characters=active_chars,
                danger_level=cls._infer_danger(scene_text),
                emotional_state=cls._infer_emotion(scene_text),
                register_flavor="cinematic_dramatic",
            )
            scenes.append(plan)

        return ChapterPlan(
            chapter_title=chapter_title,
            total_paragraphs=total_paras,
            total_words=words,
            scenes=scenes,
        )

    @classmethod
    def _find_active_characters(cls, text: str, known_characters: Optional[List[str]]) -> List[str]:
        if known_characters:
            found = []
            for name in known_characters:
                if re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
                    found.append(name)
            if found:
                return found

        # Dynamic proper noun extraction for any book/genre
        candidates = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", text)
        stop_words = {
            "The", "He", "She", "They", "Then", "After", "Before", "There", "When",
            "What", "It", "In", "On", "At", "And", "But", "Or", "So", "However",
            "Suddenly", "Meanwhile", "Later", "Now", "Just", "Even", "Though"
        }
        freq: Dict[str, int] = {}
        for c in candidates:
            if c not in stop_words and len(c) > 2:
                freq[c] = freq.get(c, 0) + 1

        # Return top mentioned proper nouns as active characters
        top = [name for name, count in sorted(freq.items(), key=lambda x: x[1], reverse=True) if count >= 1]
        return top[:6]

    @classmethod
    def _infer_setting(cls, text: str) -> Tuple[str, str]:
        loc = "Unspecified Setting"
        common_settings = (
            "bridge", "chamber", "library", "tavern", "courtyard", "palace", "hall",
            "keep", "forest", "corridor", "room", "office", "street", "alley",
            "ship", "cabin", "station", "bunker", "desert", "temple", "garden"
        )
        for candidate in common_settings:
            if re.search(rf"\b{candidate}\b", text, re.IGNORECASE):
                loc = candidate.title()
                break

        time_str = "Day"
        for t_candidate in ("night", "midnight", "dawn", "dusk", "morning", "evening", "twilight"):
            if re.search(rf"\b{t_candidate}\b", text, re.IGNORECASE):
                time_str = t_candidate.title()
                break

        return loc, time_str

    @classmethod
    def _infer_danger(cls, text: str) -> int:
        conflict_terms = [
            "sword", "blade", "blood", "kill", "monster", "beast", "death", "cut",
            "wound", "gun", "shot", "bullet", "explosion", "laser", "attack", "threat"
        ]
        hits = sum(1 for term in conflict_terms if re.search(rf"\b{term}\b", text, re.IGNORECASE))
        if hits >= 5:
            return 4
        elif hits >= 2:
            return 2
        return 1

    @classmethod
    def _infer_emotion(cls, text: str) -> str:
        t_low = text.lower()
        if any(w in t_low for w in ("laugh", "joke", "wine", "beer", "chuckle", "smile", "amused")):
            return "witty / cynical banter"
        if any(w in t_low for w in ("fear", "tremble", "scream", "dread", "corpse", "horror", "terror")):
            return "tense / existential dread"
        if any(w in t_low for w in ("touch", "kiss", "naked", "caress", "bed", "lips", "breath", "whisper")):
            return "intimate / somatic passion"
        if any(w in t_low for w in ("shout", "rage", "bellow", "fury", "strike", "clash")):
            return "visceral combat fury"
        return "restrained dramatic focus"
