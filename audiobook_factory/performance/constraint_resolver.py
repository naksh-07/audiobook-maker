#!/usr/bin/env python3
"""
Audiobook Factory - Performance Constraint Resolver (Phase 9 & Wave 3).
Resolves complex actor directions into:
1. Primary Intention (Core actioning verb and dominant delivery emotion)
2. Secondary Modifiers (Targeted physical state, proximity, and subtext nuances)
3. Forbidden Behaviors (Strict boundaries from Voice DNA and character rules)
Eliminates contradictory adjective bloat in Gemini TTS speechMetadata.style.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from .contracts import PerformanceDirection
from audiobook_factory.identity.voice_dna import VoiceDNA
from .scene_emotional_state import SceneEmotionalVector


class ResolvedPerformanceConstraints(BaseModel):
    """
    Resolved, prioritized actor directive ready for provider-specific TTS adapters.
    """
    model_config = ConfigDict(extra="ignore")

    primary_intention: str = Field(..., description="Lead actioning and delivery emotion")
    secondary_modifiers: List[str] = Field(default_factory=list, description="At most 2-3 essential modifiers")
    forbidden_behaviors: List[str] = Field(default_factory=list, description="Styles that must NOT occur")
    effective_temperature: float = Field(default=0.70, ge=0.5, le=1.0)
    clean_style_descriptor: str = Field(..., description="Concise, non-contradictory style descriptor for TTS API")


class PerformanceConstraintResolver:
    """
    Synthesizes and resolves prioritized performance constraints.
    Prevents adjective pileup and contradictory delivery instructions.
    """

    @classmethod
    def resolve_constraints(
        cls,
        direction: PerformanceDirection,
        voice_dna: Optional[VoiceDNA] = None,
        scene_vector: Optional[SceneEmotionalVector] = None,
        variant_type: str = "standard",
    ) -> ResolvedPerformanceConstraints:
        """
        Harmonizes PerformanceDirection, VoiceDNA, and SceneEmotionalVector into concise directives.
        """
        # 1. Primary Intention: actioning + delivery emotion
        surf_emo = direction.surface_emotion.lower().replace("_", " ")
        act_verb = direction.actioning.lower().replace("_", " ")

        if act_verb and act_verb not in ("speak", "inform", "say", "talk", "convey"):
            primary = f"{surf_emo}, acting to {act_verb}"
        else:
            primary = surf_emo

        if primary in ("neutral", "standard"):
            primary = "natural conversational delivery"

        # 2. Secondary Modifiers (Max 2 or 3 curated nuances)
        secondaries: List[str] = []

        # Restraint & Subtext
        restraint = direction.restraint
        if scene_vector:
            restraint = scene_vector.restraint

        if direction.social_mask:
            clean_mask = direction.social_mask.replace("_", " ")
            secondaries.append(clean_mask)
        elif restraint >= 0.75:
            secondaries.append("iron restraint")
        elif restraint <= 0.35:
            secondaries.append("unfiltered emotion")

        # Proximity & Intimacy
        if direction.proximity == "close_mic" or direction.intimacy_level == "intimate":
            secondaries.append("intimate close mic whisper")

        # Physical Staging
        if direction.physical_state == "wounded":
            secondaries.append("labored breath from injury")
        elif direction.physical_state == "exhausted":
            secondaries.append("heavy fatigue")
        elif direction.physical_state == "combat_strain":
            secondaries.append("physical combat strain")

        # Resonance & Pitch
        if direction.pitch_behavior == "low_resonant" and "intimate" not in secondaries:
            secondaries.append("low resonant chest register")
        elif direction.pitch_behavior == "high_tense":
            secondaries.append("tense strained pitch")

        # Variant Modifiers
        if variant_type == "restraint" and "iron restraint" not in secondaries:
            secondaries.append("suppressed emotion")
            secondaries.append("understated disciplined delivery")
        elif variant_type == "vulnerable":
            secondaries.append("underlying vulnerability")
        elif variant_type == "exposed":
            secondaries.append("heightened emotional adrenaline")
        elif variant_type == "alternative_cadence":
            secondaries.append("pregnant pauses and measured cadence")

        # Limit secondary modifiers to at most 3 to avoid adjective dilution
        curated_secondaries = secondaries[:3]

        # 3. Forbidden Behaviors
        forbidden: List[str] = []
        if voice_dna and voice_dna.forbidden.forbidden_behaviors:
            forbidden.extend(voice_dna.forbidden.forbidden_behaviors)

        # Contextual forbidden rules
        if restraint >= 0.70:
            forbidden.extend(["screaming", "melodrama", "uncontrolled sobbing"])
        if direction.proximity == "close_mic":
            forbidden.extend(["shouting", "loud projection"])

        # Deduplicate forbidden
        seen_f = set()
        clean_forbidden = []
        for f in forbidden:
            fl = f.strip().lower()
            if fl and fl not in seen_f:
                seen_f.add(fl)
                clean_forbidden.append(fl)

        # 4. Filter secondary modifiers against forbidden behaviors
        filtered_secondaries = []
        for sec in curated_secondaries:
            sec_l = sec.lower()
            if not any(f in sec_l for f in clean_forbidden):
                filtered_secondaries.append(sec)

        # 5. Compose Concise Style Descriptor
        style_parts = [primary]
        if filtered_secondaries:
            style_parts.extend(filtered_secondaries)

        # Clean style descriptor string
        clean_descriptor = ", ".join(style_parts)

        # 6. Temperature Micro-Entropy Calibration
        temp = 0.70
        if restraint >= 0.75 or variant_type == "restraint":
            temp = 0.65  # Tighter acoustic stability
        elif variant_type == "exposed" or (scene_vector and scene_vector.energy > 0.85):
            temp = 0.76  # Dynamic acting variance
        elif variant_type == "vulnerable":
            temp = 0.72

        return ResolvedPerformanceConstraints(
            primary_intention=primary,
            secondary_modifiers=filtered_secondaries,
            forbidden_behaviors=clean_forbidden,
            effective_temperature=round(temp, 2),
            clean_style_descriptor=clean_descriptor,
        )
