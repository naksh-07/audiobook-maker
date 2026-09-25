#!/usr/bin/env python3
"""
Audiobook Factory - TTS Performance Adapter (Provider-Neutral Bridge).
Translates PerformanceDirection into provider-specific styling instructions
(e.g. Gemini 3.8 Flash TTS speechMetadata and generation configs) while guaranteeing
the author's literary text remains 100% sacred and unmutated.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from .contracts import PerformanceDirection


class BaseTTSPerformanceAdapter(ABC):
    """Abstract base provider-neutral TTS performance adapter."""

    @abstractmethod
    def adapt_direction_to_payload(
        self,
        text: str,
        direction: PerformanceDirection,
        variant_type: str = "standard",
    ) -> Dict[str, Any]:
        """
        Translates PerformanceDirection and raw text into provider-specific payload dict.
        Literary text MUST remain identical to input text.
        """
        pass


class GeminiTTSPerformanceAdapter(BaseTTSPerformanceAdapter):
    """
    Google Gemini 3.1 / 3.8 Flash TTS Performance Adapter.
    Maps PerformanceDirection into evocative, multi-token speechMetadata.style descriptors
    and calibrated temperature micro-entropy without altering dialogue content.
    """

    VARIANT_MODIFIERS: Dict[str, List[str]] = {
        "standard": [],
        "restraint": ["suppressed emotion", "iron restraint", "understated delivery", "guarded"],
        "vulnerable": ["underlying vulnerability", "cracked composure", "subtext rising", "exposed hesitation"],
        "exposed": ["raw emotional intensity", "direct confrontation", "heightened adrenaline"],
        "alternative_cadence": ["rhythmic syncopation", "deliberate cadence", "pregnant pauses"],
    }

    def compose_style_descriptor(
        self,
        direction: PerformanceDirection,
        variant_type: str = "standard",
    ) -> str:
        """
        Synthesizes a rich, multi-dimensional style descriptor for Gemini speechMetadata.style.
        Combines: delivery emotion + actioning + articulation + pitch/resonance + restraint + social mask + physique.
        """
        components: List[str] = []

        # 1. Actioning verb & Surface Delivery
        surf = direction.surface_emotion.lower().replace("_", " ")
        if surf not in ("neutral", "standard"):
            components.append(surf)

        act = direction.actioning.lower().replace("_", " ")
        if act and act not in ("speak", "inform", "say", "talk"):
            components.append(f"acting to {act}")

        # 2. Restraint & Social Mask
        if direction.social_mask:
            clean_mask = direction.social_mask.replace("_", " ")
            components.append(clean_mask)
        elif direction.restraint >= 0.75:
            components.append("iron restraint")
            components.append("tightly controlled")
        elif direction.restraint <= 0.35:
            components.append("unfiltered emotion")

        # 3. Pitch Contour & Resonance
        if direction.pitch_behavior == "low_resonant":
            components.append("low resonant chest register")
        elif direction.pitch_behavior == "high_tense":
            components.append("tense strained pitch")
        elif direction.pitch_behavior == "monotone":
            components.append("flat detached monotone")
        elif direction.pitch_behavior == "wavering":
            components.append("wavering voice")

        # 4. Articulation
        if direction.articulation in ("crisp", "deliberate_crisp", "sharp_high_status"):
            components.append("deliberate crisp articulation")
        elif direction.articulation in ("clipped", "guttural_blunt"):
            components.append("clipped phrasing")
        elif direction.articulation in ("rapid_hesitant", "breathless"):
            components.append("breathless hesitation")

        # 5. Physicality & Proximity
        if direction.proximity == "close_mic" or direction.intimacy_level == "intimate":
            components.append("intimate close mic whisper")
        if direction.physical_state == "wounded":
            components.append("labored breathing from physical injury")
        elif direction.physical_state == "exhausted":
            components.append("heavy fatigue")
        elif direction.physical_state == "combat_strain":
            components.append("physical combat strain")

        # 6. Take Variant Modulation
        if variant_type in self.VARIANT_MODIFIERS:
            for mod in self.VARIANT_MODIFIERS[variant_type]:
                if mod not in components:
                    components.append(mod)

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for c in components:
            cl = c.strip().lower()
            if cl and cl not in seen:
                seen.add(cl)
                unique.append(c.strip())

        if not unique:
            return "neutral"

        return ", ".join(unique)

    def adapt_direction_to_payload(
        self,
        text: str,
        direction: PerformanceDirection,
        variant_type: str = "standard",
    ) -> Dict[str, Any]:
        """
        Translates PerformanceDirection into Gemini TTS API payload format.
        Text is 100% sacred and unmutated.
        """
        clean_text = text.strip()
        style_desc = self.compose_style_descriptor(direction, variant_type=variant_type)

        part_payload: Dict[str, Any] = {"text": clean_text}
        if style_desc and style_desc.lower() not in ("neutral", "standard"):
            part_payload["speechMetadata"] = {"style": style_desc}

        # Temperature calibration: slight micro-entropy modulated by variant
        temp = 0.70
        if variant_type == "restraint":
            temp = 0.65  # More disciplined, less random
        elif variant_type == "exposed":
            temp = 0.76  # More raw dynamic entropy
        elif variant_type == "vulnerable":
            temp = 0.72

        return {
            "part_payload": part_payload,
            "style_descriptor": style_desc,
            "temperature": temp,
            "suggested_pacing": direction.pace,
            "pause_before_ms": direction.pause_before_ms,
            "pause_after_ms": direction.pause_after_ms,
            "pre_roll_breath_ms": direction.pre_roll_breath_ms,
            "post_roll_breath_ms": direction.post_roll_breath_ms,
        }
