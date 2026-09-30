#!/usr/bin/env python3
"""
Audiobook Factory - Stage 12: Dialogue Protection Engine.
=========================================================
Forensic speech intelligibility and dynamic protection agent.
Guarantees dialogue remains pristine, intelligible, and acoustically anchored,
while strictly preserving emotional dynamic contrast (whispers, shouting, tension).

Key Invariants:
- Speech is primary: Spoken narrative intelligibility is never sacrificed for score.
- Dynamic contrast is sacred: Whispers remain intimate; shouts remain impactful.
- Never flatten: Avoid crushing speech dynamics into corporate monotone leveling.
- Context-aware: Consults SceneMixIntent to differentiate intended whisper from masking.
"""

from __future__ import annotations
import math
from typing import Dict, Any, List, Optional, Tuple, Union

from audiobook_factory.logger import logger
from audiobook_factory.mastering_contracts import (
    MasteringAnalysisFacts,
    DialogueProtectionReport,
)


class DialogueProtectionAgent:
    """
    Forensic dialogue protection evaluator.
    Audits the acoustic relationship between isolated dialogue stems and composite mix.
    """

    def __init__(self, target_anchor_ratio_db: float = 0.0):
        self.target_anchor_ratio = target_anchor_ratio_db

    def evaluate(
        self,
        mix_facts: MasteringAnalysisFacts,
        dialogue_facts: Optional[MasteringAnalysisFacts] = None,
        scene_intent: Optional[Any] = None,
        chapter_id: str = "ch_unknown",
    ) -> DialogueProtectionReport:
        """
        Audits dialogue intelligibility against composite mix facts.
        """
        if not dialogue_facts or dialogue_facts.integrated_lufs <= -65.0:
            # No separate dialogue stem or silent dialogue
            return DialogueProtectionReport(
                chapter_id=chapter_id,
                dialogue_lufs=-70.0,
                mix_lufs=mix_facts.integrated_lufs,
                dialogue_anchor_ratio_db=0.0,
                masking_risk="NONE",
                clarity_score=1.0,
                dynamic_contrast_preserved=True,
                recommended_adjustments={},
                status="PASS",
            )

        dx_lufs = dialogue_facts.integrated_lufs
        mix_lufs = mix_facts.integrated_lufs
        anchor_ratio = round(dx_lufs - mix_lufs, 2)

        # Context evaluation from SceneMixIntent
        intent_type = "normal"
        if scene_intent:
            raw_intent = str(getattr(scene_intent, "scene_type", "") or getattr(scene_intent, "intent", "")).lower()
            if any(w in raw_intent for w in ("whisper", "intimate", "secret")):
                intent_type = "whisper"
            elif any(w in raw_intent for w in ("combat", "action", "battle", "shouting")):
                intent_type = "combat"
            elif any(w in raw_intent for w in ("silence", "tension", "suspense")):
                intent_type = "silence"

        # Speech clarity evaluation based on spectral centroid
        clarity_score = 1.0
        centroid = dialogue_facts.spectral_centroid_hz or 1200.0
        if centroid < 600.0:
            clarity_score = max(0.5, round(centroid / 600.0, 2))
        elif centroid > 4000.0:
            clarity_score = max(0.6, round(1.0 - (centroid - 4000.0) / 4000.0, 2))

        # Evaluate Masking Risk and Dynamic Contrast Preservation
        recommended: Dict[str, Any] = {}
        contrast_preserved = True
        status = "PASS"
        masking_risk = "NONE"

        if intent_type == "whisper":
            # In a whisper scene, dialogue is quieter, but mix bed must be ducked even deeper
            # Safe anchor ratio: between -4.5 dB and +1.5 dB
            if anchor_ratio < -5.0:
                masking_risk = "MODERATE"
                status = "WARN"
                recommended["background_attenuation_db"] = -2.5
                recommended["rationale"] = "Whisper vocal is drowned by background bed; duck music/ambience further."
            else:
                masking_risk = "LOW"
                contrast_preserved = True

        elif intent_type == "combat":
            # In combat, dialogue is high energy and explosive
            if anchor_ratio < -3.0:
                masking_risk = "MODERATE"
                status = "WARN"
                recommended["dialogue_boost_db"] = 1.5
                recommended["rationale"] = "Combat dialogue competing with heavy battle FX; apply speech formant boost."
            else:
                masking_risk = "LOW"

        else:
            # Standard scene: dialogue should lead the mix (anchor ratio >= -2.5 dB)
            if anchor_ratio < -4.5:
                masking_risk = "SEVERE"
                status = "FAIL"
                contrast_preserved = False
                recommended["dialogue_boost_db"] = min(2.0, abs(anchor_ratio + 2.0))
                recommended["background_attenuation_db"] = -2.0
                recommended["rationale"] = "Severe speech masking detected in standard scene; dialogue level is buried."
            elif anchor_ratio < -2.5:
                masking_risk = "LOW"
                status = "WARN"
                recommended["dialogue_boost_db"] = 1.0
                recommended["rationale"] = "Minor dialogue masking risk; slight vocal boost recommended."
            elif anchor_ratio > 5.0:
                masking_risk = "NONE"
                status = "WARN"
                recommended["rationale"] = "Dialogue severely overpowers background; ambience bed is disconnected."

        return DialogueProtectionReport(
            chapter_id=chapter_id,
            dialogue_lufs=dx_lufs,
            mix_lufs=mix_lufs,
            dialogue_anchor_ratio_db=anchor_ratio,
            masking_risk=masking_risk,
            clarity_score=clarity_score,
            dynamic_contrast_preserved=contrast_preserved,
            recommended_adjustments=recommended,
            status=status,
        )
